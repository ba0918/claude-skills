"""validate_repo.py の純関数ユニットテスト。

実行: python3 -m unittest discover scripts
"""
import os
import subprocess
import tempfile
import unittest

import json

from validate_repo import (
    _skill_dirs,
    extract_md_links,
    is_checkable_link,
    parse_frontmatter_fields,
    find_broken_symlinks,
    check_contract_conformance,
    check_changelog_sync,
    check_unreleased_section,
    check_description_quality,
    check_frontmatter_yaml_compat,
    collect_link_sources,
    check_relative_links,
    check_portable_resource_refs,
    mentions_name,
    check_dossiers,
    check_artifact_store,
    check_human_readable_summary,
    check_manifests,
    check_command_skill_mapping,
    check_design_token_sync,
    check_legacy_claude_paths,
    check_plugin_hooks,
    check_fixtures,
    check_rename_allowlist_staleness,
    check_workspace_policy,
    parse_version,
    HUMAN_READABLE_SUMMARY_LABEL,
    HUMAN_READABLE_SUMMARY_SKILLS,
    CONTRACT_VOCAB,
)


def _valid_dossier():
    return {
        "schema_version": 1,
        "status": "draft",
        "superseded_by": None,
        "goal": {"statement": "g", "non_goals": ["x"], "ssot": "docs/"},
        "oracles": [{
            "id": "oracle:a", "type": "true", "command": "true",
            "oracle_files": [".agents/artifacts/status.md"], "owner": "me",
        }],
        "fragments": [{
            "id": "frag:a", "wire_to": "goal-loop", "exit_to": "ci_gate",
            "routing_proof": "p", "auto_fix_allowed": False,
            "why_not_auto_fix": "r", "self_modification_risk": "low",
            "blocked_by": [],
        }],
        "sensors": [{"id": "sensor:a",
                     "rules": ["r"],
                     "findings_policy": {"fix_action": "REPORT_ONLY", "enqueue": False}}],
        "inbox": [{"id": "inbox:q", "question": "?", "reclassify_when": "w"}],
        "measurement": {"metrics": ["m"], "stop_conditions": ["s"]},
    }


class TestCheckDossiers(unittest.TestCase):
    """チェック13: .agents/artifacts/loop/dossiers/*.json を dossier_lint で in-process 検査。"""

    def _write(self, root, name, obj_or_text):
        ddir = os.path.join(root, ".agents", "artifacts", "loop", "dossiers")
        os.makedirs(ddir, exist_ok=True)
        path = os.path.join(ddir, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(obj_or_text if isinstance(obj_or_text, str)
                    else json.dumps(obj_or_text))

    def test_absent_dir_is_noop(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(check_dossiers(root), [])

    def test_empty_dir_is_noop(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, ".agents", "artifacts", "loop", "dossiers"))
            self.assertEqual(check_dossiers(root), [])

    def test_valid_dossier_passes(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "ok.json", _valid_dossier())
            self.assertEqual(check_dossiers(root), [])

    def test_error_dossier_is_reported(self):
        with tempfile.TemporaryDirectory() as root:
            bad = _valid_dossier()
            del bad["status"]  # GD002 error
            self._write(root, "bad.json", bad)
            errors = check_dossiers(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("[dossier]", errors[0])
            self.assertIn("GD002", errors[0])

    def test_warn_only_dossier_does_not_fail(self):
        with tempfile.TemporaryDirectory() as root:
            warn = _valid_dossier()
            warn["goal"]["non_goals"] = []  # GD302 warn only
            self._write(root, "warn.json", warn)
            self.assertEqual(check_dossiers(root), [])

    def test_broken_json_reports_parse_error_without_crashing(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "broken.json", "{ not json ")
            errors = check_dossiers(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("[dossier]", errors[0])
            self.assertIn("parse-error", errors[0])


class TestCheckArtifactStore(unittest.TestCase):
    def setUp(self):
        self._orig_env = {}
        git_env = {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@test",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@test",
        }
        for key, val in git_env.items():
            self._orig_env[key] = os.environ.get(key)
            os.environ[key] = val

    def tearDown(self):
        for key, val in self._orig_env.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val

    def _repo(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = temp.name
        # git hook の中では GIT_DIR などが環境に置かれており、引き継ぐと
        # ここの init が呼び出し元のリポジトリを指して失敗する。
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        subprocess.run(["git", "init", "-q"], cwd=root, check=True, env=env)
        os.makedirs(os.path.join(root, ".agents"), exist_ok=True)
        with open(os.path.join(root, ".gitignore"), "w", encoding="utf-8") as handle:
            handle.write("/.agents/artifacts/\n")
        return root

    def test_valid_local_policy_passes(self):
        root = self._repo()
        with open(os.path.join(root, ".agents", "artifacts.yml"), "w", encoding="utf-8") as handle:
            handle.write(
                "schema_version: 1\nroot: .agents/artifacts\n"
                "visibility: local\nworktree_scope: worktree\n"
            )
        self.assertEqual([], check_artifact_store(root))

    def test_unknown_schema_is_reported(self):
        root = self._repo()
        with open(os.path.join(root, ".agents", "artifacts.yml"), "w", encoding="utf-8") as handle:
            handle.write(
                "schema_version: 2\nroot: .agents/artifacts\n"
                "visibility: local\nworktree_scope: worktree\n"
            )
        errors = check_artifact_store(root)
        self.assertEqual(1, len(errors))
        self.assertIn("schema_version", errors[0])


class TestCheckWorkspacePolicy(unittest.TestCase):
    def _repo(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = temp.name
        os.makedirs(os.path.join(root, ".agents"), exist_ok=True)
        return root

    def _write_policy(self, root, text):
        with open(os.path.join(root, ".agents", "workspace.yml"), "w", encoding="utf-8") as handle:
            handle.write(text)

    def test_missing_policy_is_valid(self):
        self.assertEqual([], check_workspace_policy(self._repo()))

    def test_worktree_policy_passes(self):
        root = self._repo()
        self._write_policy(root, "isolation: worktree\n")
        self.assertEqual([], check_workspace_policy(root))

    def test_inplace_policy_passes(self):
        root = self._repo()
        self._write_policy(root, "isolation: inplace\n")
        self.assertEqual([], check_workspace_policy(root))

    def test_unknown_isolation_value_is_reported(self):
        root = self._repo()
        self._write_policy(root, "isolation: hybrid\n")
        errors = check_workspace_policy(root)
        self.assertEqual(1, len(errors))
        self.assertIn("[workspace-policy]", errors[0])

    def test_extra_key_is_reported(self):
        root = self._repo()
        self._write_policy(root, "isolation: worktree\nmode: fast\n")
        errors = check_workspace_policy(root)
        self.assertEqual(1, len(errors))
        self.assertIn("[workspace-policy]", errors[0])


class TestExtractMdLinks(unittest.TestCase):
    def test_extracts_relative_links(self):
        text = "詳細は [criteria](references/review-criteria.md) と [shared](../shared/references/team-config.md) を参照。"
        self.assertEqual(
            extract_md_links(text),
            ["references/review-criteria.md", "../shared/references/team-config.md"],
        )

    def test_ignores_non_link_parens(self):
        text = "関数 f(x) や (注釈) はリンクではない。"
        self.assertEqual(extract_md_links(text), [])

    def test_strips_anchor(self):
        text = "[section](references/guide.md#step-2)"
        self.assertEqual(extract_md_links(text), ["references/guide.md"])


class TestIsCheckableLink(unittest.TestCase):
    def test_relative_md_is_checkable(self):
        self.assertTrue(is_checkable_link("references/review-criteria.md"))
        self.assertTrue(is_checkable_link("../shared/references/team-config.md"))

    def test_placeholder_is_skipped(self):
        self.assertFalse(is_checkable_link("{slug}.md"))
        self.assertFalse(is_checkable_link(".agents/artifacts/plans/{timestamp}_{slug}.md"))

    def test_url_and_anchor_are_skipped(self):
        self.assertFalse(is_checkable_link("https://example.com/page.md"))
        self.assertFalse(is_checkable_link("#local-anchor"))

    def test_example_timestamp_path_is_skipped(self):
        # 例示用のタイムスタンプ付きパス（docs/ 配下の生成物例）は検証対象外
        self.assertFalse(is_checkable_link("20260323143000_fix-login.md"))

    def test_non_md_is_skipped(self):
        self.assertFalse(is_checkable_link("references/tokens-schema.json"))


class TestParseFrontmatterFields(unittest.TestCase):
    def test_parses_name_and_description(self):
        text = "---\nname: my-skill\ndescription: すごいスキル\n---\n\n# Body\n"
        fields = parse_frontmatter_fields(text)
        self.assertEqual(fields.get("name"), "my-skill")
        self.assertEqual(fields.get("description"), "すごいスキル")

    def test_no_frontmatter_returns_empty(self):
        self.assertEqual(parse_frontmatter_fields("# タイトルだけ\n本文"), {})

    def test_ignores_fields_after_closing_delimiter(self):
        text = "---\nname: a\n---\ndescription: 本文中の偽フィールド\n"
        fields = parse_frontmatter_fields(text)
        self.assertIn("name", fields)
        self.assertNotIn("description", fields)


class TestFindBrokenSymlinks(unittest.TestCase):
    def test_detects_broken_and_ignores_valid(self):
        with tempfile.TemporaryDirectory() as root:
            target = os.path.join(root, "real.md")
            with open(target, "w") as f:
                f.write("x")
            os.symlink(target, os.path.join(root, "ok.md"))
            os.symlink(os.path.join(root, "missing.md"), os.path.join(root, "broken.md"))
            result = find_broken_symlinks(root)
            self.assertEqual([os.path.basename(p) for p in result], ["broken.md"])

    def test_skips_excluded_dirs(self):
        with tempfile.TemporaryDirectory() as root:
            gitdir = os.path.join(root, ".git")
            os.mkdir(gitdir)
            os.symlink(os.path.join(root, "nope"), os.path.join(gitdir, "broken"))
            self.assertEqual(find_broken_symlinks(root), [])


class TestMentionsName(unittest.TestCase):
    """チェック7/8のドリフト検出: bare substring だと issue ⊂ github-issue 等が誤合格する。"""

    def test_exact_word_matches(self):
        self.assertTrue(mentions_name("| issue | issue 管理 |", "issue"))
        self.assertTrue(mentions_name("`issue` スキル", "issue"))

    def test_longer_hyphenated_name_does_not_match_shorter(self):
        self.assertFalse(mentions_name("github-issue を使う", "issue"))
        self.assertFalse(mentions_name("team-plan で計画する", "plan"))
        self.assertFalse(mentions_name("issue-close を呼ぶ", "issue"))

    def test_path_segments_match(self):
        self.assertTrue(mentions_name("skills/issue/SKILL.md", "issue"))
        self.assertTrue(mentions_name("codex-skills/plan/", "plan"))

    def test_plugin_prefix_form_matches(self):
        self.assertTrue(mentions_name("/claude-skills:issue を実行", "issue"))

    def test_shorter_name_inside_word_does_not_match(self):
        self.assertFalse(mentions_name("displanned", "plan"))

    def test_hyphenated_skill_name_matches_exactly(self):
        self.assertTrue(mentions_name("github-issue polling", "github-issue"))
        self.assertFalse(mentions_name("github-issue2 という別物", "github-issue"))


class TestSkillDirs(unittest.TestCase):
    def _mkdir(self, root, rel):
        os.makedirs(os.path.join(root, rel), exist_ok=True)

    def test_lists_skill_directories(self):
        with tempfile.TemporaryDirectory() as root:
            self._mkdir(root, "skills/a")
            self._mkdir(root, "skills/b")
            self.assertEqual(_skill_dirs(root, "skills"), ["a", "b"])

    def test_dot_directories_are_not_skills(self):
        # エージェントがリポジトリ本体を cwd にすると skills/.claude/ のような
        # セッション用スキャフォールドが現れ、無関係な理由でチェックが落ちる
        with tempfile.TemporaryDirectory() as root:
            self._mkdir(root, "skills/a")
            self._mkdir(root, "skills/.claude")
            self.assertEqual(_skill_dirs(root, "skills"), ["a"])

    def test_shared_is_excluded(self):
        with tempfile.TemporaryDirectory() as root:
            self._mkdir(root, "skills/a")
            self._mkdir(root, "skills/shared")
            self.assertEqual(_skill_dirs(root, "skills"), ["a"])


class TestCollectLinkSources(unittest.TestCase):
    """チェック5の対象収集: SKILL.md / commands/*.md に加えて references/*.md も含む。"""

    def _write(self, root, rel, content="x"):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def test_includes_skill_md_commands_and_references(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "skills/a/SKILL.md")
            self._write(root, "skills/a/references/detail.md")
            self._write(root, "commands/z.md")
            rels = {os.path.relpath(p, root) for p in collect_link_sources(root)}
            self.assertEqual(
                rels,
                {"skills/a/SKILL.md", "skills/a/references/detail.md",
                 "commands/z.md"},
            )

    def test_includes_shared_references(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "skills/shared/references/contract.md")
            rels = {os.path.relpath(p, root) for p in collect_link_sources(root)}
            self.assertEqual(
                rels,
                {"skills/shared/references/contract.md"},
            )

    def test_non_md_files_in_references_are_excluded(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "skills/a/SKILL.md")
            self._write(root, "skills/a/references/schema.json")
            rels = {os.path.relpath(p, root) for p in collect_link_sources(root)}
            self.assertEqual(rels, {"skills/a/SKILL.md"})


class TestCheckRelativeLinks(unittest.TestCase):
    def _write(self, root, rel, content="x"):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def test_broken_link_in_references_is_reported(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "skills/a/references/detail.md",
                        "[ghost](../../shared/references/ghost.md) を参照。")
            errors = check_relative_links(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("skills/a/references/detail.md", errors[0])
            self.assertIn("ghost.md", errors[0])

    def test_valid_links_pass(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "skills/shared/references/contract.md")
            self._write(root, "skills/a/SKILL.md",
                        "[契約](../shared/references/contract.md) 参照。")
            self._write(root, "skills/a/references/detail.md",
                        "[契約](../../shared/references/contract.md) 参照。")
            self.assertEqual(check_relative_links(root), [])

    def test_placeholder_links_are_skipped(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "skills/a/references/detail.md",
                        "[plan](.agents/artifacts/plans/{timestamp}_{slug}.md) を生成する。")
            self.assertEqual(check_relative_links(root), [])

    def test_exempt_file_is_skipped(self):
        # テンプレファイル内のリンクは生成先プロジェクトの構造を指す例示
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "skills/a/references/template.md",
                        "[archive](./session-history.md) を参照。")
            exempt = {"skills/a/references/template.md": "テンプレの例示リンク"}
            self.assertEqual(check_relative_links(root, exempt=exempt), [])
            self.assertEqual(len(check_relative_links(root, exempt={})), 1)


class TestCheckPortableResourceRefs(unittest.TestCase):
    def _write(self, root, rel, content="x"):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def test_legacy_rules_reference_is_reported(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(
                root,
                "skills/a/SKILL.md",
                "Read `rules/testing-anti-patterns.md`.",
            )
            errors = check_portable_resource_refs(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("rules/testing-anti-patterns.md", errors[0])

    def test_shared_reference_passes(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(
                root,
                "skills/a/SKILL.md",
                "[rules](../shared/references/testing-anti-patterns.md)",
            )
            self.assertEqual(check_portable_resource_refs(root), [])

    def test_claude_rules_path_and_glob_are_not_resource_dependencies(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(
                root,
                "skills/a/SKILL.md",
                "Inspect `.claude/rules/example.md` and `rules/*.md`.",
            )
            self.assertEqual(check_portable_resource_refs(root), [])


class TestCheckContractConformance(unittest.TestCase):
    """チェック12: 契約語彙を使う unit（skill dir / command file）は契約を md リンクすること。"""

    VOCAB = [
        ("skills/shared/references/fake-contract.md",
         ("ALPHA_ONE", "ALPHA_TWO", "ALPHA_THREE"), 2),
    ]

    def _write(self, root, rel, content):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _base(self, root):
        self._write(root, "skills/shared/references/fake-contract.md",
                    "ALPHA_ONE / ALPHA_TWO / ALPHA_THREE の定義。")

    def test_usage_without_link_is_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._base(root)
            self._write(root, "skills/a/SKILL.md",
                        "findings を ALPHA_ONE と ALPHA_TWO に分類する。")
            errors = check_contract_conformance(root, vocab=self.VOCAB, exempt={})
            self.assertEqual(len(errors), 1)
            self.assertIn("skills/a", errors[0])
            self.assertIn("fake-contract.md", errors[0])

    def test_link_in_any_unit_file_satisfies(self):
        with tempfile.TemporaryDirectory() as root:
            self._base(root)
            self._write(root, "skills/a/SKILL.md",
                        "分類は ALPHA_ONE / ALPHA_TWO。詳細は references を参照。")
            self._write(root, "skills/a/references/detail.md",
                        "[契約](../../shared/references/fake-contract.md) に従う。")
            self.assertEqual(
                check_contract_conformance(root, vocab=self.VOCAB, exempt={}), [])

    def test_below_min_distinct_is_not_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._base(root)
            self._write(root, "skills/a/SKILL.md", "ALPHA_ONE だけ言及する。")
            self.assertEqual(
                check_contract_conformance(root, vocab=self.VOCAB, exempt={}), [])

    def test_command_file_is_its_own_unit(self):
        with tempfile.TemporaryDirectory() as root:
            self._base(root)
            self._write(root, "commands/x.md", "ALPHA_ONE と ALPHA_THREE を使う。")
            self._write(
                root, "commands/y.md",
                "ALPHA_ONE と ALPHA_THREE を使う。"
                "[契約](../skills/shared/references/fake-contract.md) 参照。")
            errors = check_contract_conformance(root, vocab=self.VOCAB, exempt={})
            self.assertEqual(len(errors), 1)
            self.assertIn("commands/x.md", errors[0])

    def test_exempt_unit_is_skipped(self):
        with tempfile.TemporaryDirectory() as root:
            self._base(root)
            self._write(root, "skills/a/SKILL.md", "ALPHA_ONE と ALPHA_TWO。")
            self.assertEqual(
                check_contract_conformance(
                    root, vocab=self.VOCAB,
                    exempt={"skills/a": "理由"}), [])

    def test_shared_contract_files_are_not_units(self):
        with tempfile.TemporaryDirectory() as root:
            self._base(root)  # 契約自身が語彙を全部含むが unit ではない
            self.assertEqual(
                check_contract_conformance(root, vocab=self.VOCAB, exempt={}), [])


class TestCoverageLedgerContractVocab(unittest.TestCase):
    """coverage ledger 契約（4値・min_distinct=3）の登録と執行を検証する。

    reviewed/skipped/unsupported は汎用語で偽陽性を招きやすいため、
    4値中3値の共起でのみ契約リンクを要求する（min_distinct=3）。
    """

    # 本物の CONTRACT_VOCAB エントリと同形の fixture。
    VOCAB = [
        ("skills/shared/references/coverage-ledger.md",
         ("reviewed", "skipped", "unsupported", "inconclusive"), 3),
    ]

    def _write(self, root, rel, content):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _base(self, root):
        self._write(root, "skills/shared/references/coverage-ledger.md",
                    "reviewed / skipped / unsupported / inconclusive の定義。")

    def test_entry_is_registered_in_real_vocab(self):
        entry = ("skills/shared/references/coverage-ledger.md",
                 ("reviewed", "skipped", "unsupported", "inconclusive"), 3)
        self.assertIn(entry, CONTRACT_VOCAB)

    def test_three_values_without_link_is_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._base(root)
            self._write(root, "skills/review-x/SKILL.md",
                        "評価範囲を reviewed / skipped / inconclusive に分類する。")
            errors = check_contract_conformance(root, vocab=self.VOCAB, exempt={})
            self.assertEqual(len(errors), 1)
            self.assertIn("skills/review-x", errors[0])
            self.assertIn("coverage-ledger.md", errors[0])

    def test_three_values_with_link_passes(self):
        with tempfile.TemporaryDirectory() as root:
            self._base(root)
            self._write(root, "skills/review-x/SKILL.md",
                        "評価範囲を reviewed / skipped / inconclusive に分類する。"
                        "[台帳](../shared/references/coverage-ledger.md) 参照。")
            self.assertEqual(
                check_contract_conformance(root, vocab=self.VOCAB, exempt={}), [])

    def test_two_values_are_not_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._base(root)
            self._write(root, "skills/review-x/SKILL.md",
                        "reviewed と skipped のみ言及する（2値なので非対象）。")
            self.assertEqual(
                check_contract_conformance(root, vocab=self.VOCAB, exempt={}), [])


class TestCheckChangelogSync(unittest.TestCase):
    """チェック12: plugin.json の version に対応するエントリが CHANGELOG.md にあること。

    version bump だけして CHANGELOG への起票を忘れるドリフト
    （実例: 1.45.1〜1.46.1 の 4 エントリ欠落）を機械的に止める。
    """

    def _write(self, root, rel, content):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path) or root, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _plugin(self, root, version="1.47.0"):
        self._write(root, ".claude-plugin/plugin.json",
                    json.dumps({"name": "x", "version": version}))

    def test_matching_entry_passes(self):
        with tempfile.TemporaryDirectory() as root:
            self._plugin(root, "1.47.0")
            self._write(root, "CHANGELOG.md", "# Changelog\n\n## 1.47.0\n\n変更内容。\n")
            self.assertEqual(check_changelog_sync(root), [])

    def test_missing_entry_is_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._plugin(root, "1.47.0")
            self._write(root, "CHANGELOG.md", "# Changelog\n\n## 1.46.0\n\n古い内容。\n")
            errors = check_changelog_sync(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("[changelog]", errors[0])
            self.assertIn("1.47.0", errors[0])

    def test_longer_version_heading_does_not_match_shorter(self):
        # 「## 1.46.10」は version 1.46.1 のエントリではない。
        # 逆方向の観点では 1.46.10 > 1.46.1 なので未配布エントリでもある（2 件とも上がる）
        with tempfile.TemporaryDirectory() as root:
            self._plugin(root, "1.46.1")
            self._write(root, "CHANGELOG.md", "## 1.46.10\n")
            errors = check_changelog_sync(root)
            self.assertEqual(len(errors), 2)
            self.assertTrue(any("に対応する" in e for e in errors), errors)
            self.assertTrue(any("未配布バージョン" in e for e in errors), errors)

    def test_heading_with_trailing_note_passes(self):
        with tempfile.TemporaryDirectory() as root:
            self._plugin(root, "1.47.0")
            self._write(root, "CHANGELOG.md", "## 1.47.0 (2026-07-12)\n")
            self.assertEqual(check_changelog_sync(root), [])

    def test_version_inside_body_text_does_not_count(self):
        # 本文中の言及では見出しにならない（エントリ起票を要求する）
        with tempfile.TemporaryDirectory() as root:
            self._plugin(root, "1.47.0")
            self._write(root, "CHANGELOG.md",
                        "# Changelog\n\n## 1.46.0\n\n1.47.0 で対応予定。\n")
            self.assertEqual(len(check_changelog_sync(root)), 1)

    def test_missing_changelog_file_is_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._plugin(root, "1.47.0")
            errors = check_changelog_sync(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("[changelog]", errors[0])

    def test_repo_without_plugin_manifest_is_noop(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "CHANGELOG.md", "# Changelog\n")
            self.assertEqual(check_changelog_sync(root), [])

    def test_entry_ahead_of_plugin_version_is_flagged(self):
        # 起票済みだが bump 保留 = 配布されていない変更が配布済みに見える
        with tempfile.TemporaryDirectory() as root:
            self._plugin(root, "1.65.0")
            self._write(root, "CHANGELOG.md",
                        "## 1.67.0\n\n未配布。\n\n## 1.65.0\n\n配布済み。\n")
            errors = check_changelog_sync(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("未配布バージョン", errors[0])
            self.assertIn("1.67.0", errors[0])

    def test_multiple_ahead_entries_are_each_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._plugin(root, "1.65.0")
            self._write(root, "CHANGELOG.md",
                        "## 1.67.0\n\nx\n\n## 1.66.0\n\ny\n\n## 1.65.0\n\nz\n")
            errors = check_changelog_sync(root)
            self.assertEqual(len(errors), 2)
            self.assertIn("1.66.0", errors[0])
            self.assertIn("1.67.0", errors[1])

    def test_older_entries_are_not_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._plugin(root, "1.65.0")
            self._write(root, "CHANGELOG.md",
                        "## 1.65.0\n\nx\n\n## 1.64.0\n\ny\n\n## 1.9.0\n\nz\n")
            self.assertEqual(check_changelog_sync(root), [])

    def test_ahead_comparison_is_numeric_not_lexical(self):
        # 文字列比較なら "1.9.0" > "1.10.0" と誤判定する
        with tempfile.TemporaryDirectory() as root:
            self._plugin(root, "1.10.0")
            self._write(root, "CHANGELOG.md", "## 1.10.0\n\nx\n\n## 1.9.0\n\ny\n")
            self.assertEqual(check_changelog_sync(root), [])

    def test_non_numeric_heading_is_ignored(self):
        with tempfile.TemporaryDirectory() as root:
            self._plugin(root, "1.65.0")
            self._write(root, "CHANGELOG.md",
                        "## Unreleased\n\nx\n\n## 1.65.0\n\ny\n")
            self.assertEqual(check_changelog_sync(root), [])

    def test_misplaced_unreleased_is_reported_through_sync(self):
        with tempfile.TemporaryDirectory() as root:
            self._plugin(root, "1.65.0")
            self._write(root, "CHANGELOG.md",
                        "## 1.65.0\n\nx\n\n## Unreleased\n\ny\n")
            errors = check_changelog_sync(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("より下にある", errors[0])


class TestCheckUnreleasedSection(unittest.TestCase):
    """チェック12b: 未配布の起票先 `## Unreleased` が常に一意に定まること。

    PR ごとの bump をやめて起票を Unreleased へ集約する運用を機械的に支える。
    リリース時に番号へ昇格させる対象が曖昧になる状態（表記ゆれ・重複・配布済み
    エントリより下）を違反として止める。
    """

    def test_changelog_without_unreleased_passes(self):
        self.assertEqual(check_unreleased_section("## 1.65.0\n\nx\n"), [])

    def test_unreleased_above_latest_release_passes(self):
        changelog = "# Changelog\n\n## Unreleased\n\n- 変更。\n\n## 1.65.0\n\nx\n"
        self.assertEqual(check_unreleased_section(changelog), [])

    def test_empty_unreleased_section_passes(self):
        # リリース直後は見出しだけが残る。空であること自体は違反ではない
        self.assertEqual(
            check_unreleased_section("## Unreleased\n\n## 1.65.0\n\nx\n"), []
        )

    def test_unreleased_without_any_release_entry_passes(self):
        self.assertEqual(check_unreleased_section("## Unreleased\n\n- 初回。\n"), [])

    def test_bracketed_label_is_flagged(self):
        errors = check_unreleased_section("## [Unreleased]\n\nx\n\n## 1.65.0\n\ny\n")
        self.assertEqual(len(errors), 1)
        self.assertIn("統一する", errors[0])

    def test_lowercase_label_is_flagged(self):
        errors = check_unreleased_section("## unreleased\n\nx\n\n## 1.65.0\n\ny\n")
        self.assertEqual(len(errors), 1)
        self.assertIn("[changelog]", errors[0])

    def test_duplicate_unreleased_sections_are_flagged(self):
        changelog = "## Unreleased\n\nx\n\n## Unreleased\n\ny\n\n## 1.65.0\n\nz\n"
        errors = check_unreleased_section(changelog)
        self.assertEqual(len(errors), 1)
        self.assertIn("2 個", errors[0])

    def test_unreleased_below_release_entry_is_flagged(self):
        errors = check_unreleased_section("## 1.65.0\n\nx\n\n## Unreleased\n\ny\n")
        self.assertEqual(len(errors), 1)
        self.assertIn("より下にある", errors[0])


class TestCheckCommandSkillMapping(unittest.TestCase):
    """チェック16: command 名がスキル名と対応しないとき description で名指しする。

    `/debug` → systematic-debugging のように名前がずれると、利用者からは
    command とスキルが別々の名前空間に見える。改名・削除はしない方針なので、
    説明文で対応関係を可視化することを機械的に要求する。
    """

    def _write(self, root, rel, content):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _command(self, root, name, description, target):
        self._write(root, f"commands/{name}.md",
                    f"---\ndescription: \"{description}\"\n---\n\n"
                    f"スキル `claude-skills:{target}` を実行する。")

    def _skill(self, root, name):
        self._write(root, f"skills/{name}/SKILL.md",
                    f"---\nname: {name}\ndescription: x で起動。\n---\n")

    def test_command_named_after_skill_needs_no_mention(self):
        with tempfile.TemporaryDirectory() as root:
            self._skill(root, "commit")
            self._command(root, "commit", "変更をコミットする", "commit")
            self.assertEqual(check_command_skill_mapping(root), [])

    def test_workflow_suffix_needs_no_mention(self):
        with tempfile.TemporaryDirectory() as root:
            self._skill(root, "issue")
            self._command(root, "issue-list", "未解決 issue の一覧", "issue")
            self.assertEqual(check_command_skill_mapping(root), [])

    def test_mismatched_name_without_mention_is_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._skill(root, "systematic-debugging")
            self._command(root, "debug", "4フェーズ構造化デバッグ",
                          "systematic-debugging")
            errors = check_command_skill_mapping(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("commands/debug.md", errors[0])
            self.assertIn("systematic-debugging", errors[0])

    def test_mismatched_name_with_mention_passes(self):
        with tempfile.TemporaryDirectory() as root:
            self._skill(root, "systematic-debugging")
            self._command(root, "debug",
                          "systematic-debugging スキルの入口。4フェーズ構造化デバッグ",
                          "systematic-debugging")
            self.assertEqual(check_command_skill_mapping(root), [])

    def test_prefix_collision_still_requires_mention(self):
        # plan-review は plan スキルではなく plan-reviewer を起動する。
        # `plan-` 接尾辞として自明扱いされないこと
        with tempfile.TemporaryDirectory() as root:
            self._skill(root, "plan")
            self._skill(root, "plan-reviewer")
            self._command(root, "plan-review", "計画をレビューする", "plan-reviewer")
            errors = check_command_skill_mapping(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("plan-reviewer", errors[0])

    def test_command_invoking_unknown_skill_is_ignored(self):
        with tempfile.TemporaryDirectory() as root:
            self._command(root, "foo", "説明", "not-a-skill")
            self.assertEqual(check_command_skill_mapping(root), [])

    def test_repo_without_commands_dir_is_noop(self):
        with tempfile.TemporaryDirectory() as root:
            self._skill(root, "commit")
            self.assertEqual(check_command_skill_mapping(root), [])


class TestCheckFixtures(unittest.TestCase):
    """チェック17: skills/*/fixtures.json の契約適合を CI で強制する。"""

    def _write(self, root, rel, content):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _valid(self):
        return {
            "skill": "demo",
            "scenarios": [{
                "id": "d-001", "title": "t", "source": "manual", "prompt": "p",
                "requirements": [{"text": "r", "critical": True}],
            }],
        }

    def test_valid_fixture_passes(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "skills/demo/fixtures.json", json.dumps(self._valid()))
            self.assertEqual(check_fixtures(root), [])

    def test_fixture_without_critical_requirement_is_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            bad = self._valid()
            bad["scenarios"][0]["requirements"] = [{"text": "r", "critical": False}]
            self._write(root, "skills/demo/fixtures.json", json.dumps(bad))
            errors = check_fixtures(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("critical", errors[0])

    def test_unknown_setup_key_is_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            bad = self._valid()
            bad["scenarios"][0]["setup"] = {"symlinks": {}}
            self._write(root, "skills/demo/fixtures.json", json.dumps(bad))
            self.assertTrue(any("未知の setup キー" in e for e in check_fixtures(root)))

    def test_broken_json_is_flagged_without_crashing(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "skills/demo/fixtures.json", "{ not json")
            errors = check_fixtures(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("JSON として読めない", errors[0])

    def test_skill_without_fixtures_is_skipped(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "skills/demo/SKILL.md", "---\nname: demo\n---\n")
            self.assertEqual(check_fixtures(root), [])

    def test_repo_without_skills_dir_is_noop(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(check_fixtures(root), [])


class TestParseVersion(unittest.TestCase):
    """バージョン比較は数値タプルで行う（文字列比較は 1.9.0 > 1.10.0 と誤る）。"""

    def test_dotted_numbers_become_tuple(self):
        self.assertEqual(parse_version("1.65.0"), (1, 65, 0))

    def test_ordering_is_numeric(self):
        self.assertLess(parse_version("1.9.0"), parse_version("1.10.0"))

    def test_non_numeric_component_is_uncomparable(self):
        self.assertIsNone(parse_version("1.0.0-rc1"))

    def test_empty_is_uncomparable(self):
        self.assertIsNone(parse_version(""))


class TestCheckManifests(unittest.TestCase):
    """チェック15: 配布 manifest の name / version / リポジトリ slug / LICENSE の整合。

    3 つの manifest が別々に手編集されるため、一致すべき項目が黙ってドリフトする。
    実際に .claude-plugin/plugin.json の repository が実在しない owner を指していた。
    """

    def _write(self, root, rel, content):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path) or root, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _base(self, root, *, repository="https://github.com/owner/claude-skills",
              version="1.0.0", license_field="MIT", readme_owner="owner",
              with_license_file=True):
        plugin = {"name": "claude-skills", "version": version}
        if repository:
            plugin["repository"] = repository
        if license_field:
            plugin["license"] = license_field
        self._write(root, ".claude-plugin/plugin.json", json.dumps(plugin))
        self._write(root, ".claude-plugin/marketplace.json", json.dumps({
            "name": "claude-skills",
            "plugins": [{"name": "claude-skills", "version": version}],
        }))
        self._write(root, ".codex-plugin/plugin.json", json.dumps({
            "name": "claude-skills", "version": version,
        }))
        if readme_owner:
            self._write(root, "README.md",
                        f"claude plugin marketplace add {readme_owner}/claude-skills\n")
        if with_license_file:
            self._write(root, "LICENSE", "MIT License\n")

    def test_consistent_manifests_pass(self):
        with tempfile.TemporaryDirectory() as root:
            self._base(root)
            self.assertEqual(check_manifests(root), [])

    def test_readme_pointing_at_other_owner_is_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._base(root, repository="https://github.com/wrong/claude-skills",
                       readme_owner="real")
            errors = check_manifests(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("別 owner", errors[0])
            self.assertIn("real/claude-skills", errors[0])

    def test_version_drift_between_manifests_is_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._base(root, version="1.0.0")
            self._write(root, ".codex-plugin/plugin.json",
                        json.dumps({"name": "claude-skills", "version": "0.9.0"}))
            errors = check_manifests(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("version", errors[0])

    def test_name_drift_between_manifests_is_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._base(root)
            self._write(root, ".codex-plugin/plugin.json",
                        json.dumps({"name": "renamed", "version": "1.0.0"}))
            errors = check_manifests(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("name", errors[0])

    def test_declared_license_without_file_is_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._base(root, with_license_file=False)
            errors = check_manifests(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("LICENSE ファイルがない", errors[0])

    def test_no_license_declaration_does_not_require_file(self):
        with tempfile.TemporaryDirectory() as root:
            self._base(root, license_field=None, with_license_file=False)
            self.assertEqual(check_manifests(root), [])

    def test_unparsable_repository_is_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._base(root, repository="git@example.invalid:something")
            errors = check_manifests(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("解釈できない", errors[0])

    def test_ssh_style_repository_is_accepted(self):
        with tempfile.TemporaryDirectory() as root:
            self._base(root, repository="git@github.com:owner/claude-skills.git")
            self.assertEqual(check_manifests(root), [])

    def test_filesystem_path_is_not_treated_as_slug(self):
        # README の `--plugin-dir /path/to/claude-skills` を install slug と誤読しない
        with tempfile.TemporaryDirectory() as root:
            self._base(root)
            self._write(root, "README.md",
                        "claude plugin marketplace add owner/claude-skills\n"
                        "claude --plugin-dir /path/to/claude-skills\n")
            self.assertEqual(check_manifests(root), [])

    def test_repo_without_manifests_is_noop(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "README.md", "# x\n")
            self.assertEqual(check_manifests(root), [])

    def test_invalid_json_is_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._base(root)
            self._write(root, ".codex-plugin/plugin.json", "{not json")
            errors = check_manifests(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("JSON として読めない", errors[0])


class TestCheckDescriptionQuality(unittest.TestCase):
    """check 8: SKILL.md description のトリガー語・長さ・免除を検証する。"""

    def _write(self, root, rel, content):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _skill(self, root, name, description):
        self._write(root, f"skills/{name}/SKILL.md",
                    f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n")

    def test_valid_trigger_japanese_passes(self):
        with tempfile.TemporaryDirectory() as root:
            self._skill(root, "my-skill", "コードを分析して問題を検出する。「my-skill」で起動。")
            self.assertEqual(check_description_quality(root), [])

    def test_valid_trigger_english_passes(self):
        with tempfile.TemporaryDirectory() as root:
            self._skill(root, "my-skill", "Analyze code. Use when you need linting.")
            self.assertEqual(check_description_quality(root), [])

    def test_valid_trigger_use_suffix_passes(self):
        with tempfile.TemporaryDirectory() as root:
            self._skill(root, "my-skill", "コード分析スキル。コード検証時に使用する。「my-skill」で使用。")
            self.assertEqual(check_description_quality(root), [])

    def test_missing_trigger_is_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._skill(root, "no-trigger", "コードを分析して問題を検出する。")
            errors = check_description_quality(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("[description]", errors[0])
            self.assertIn("トリガー語", errors[0])
            self.assertIn("no-trigger", errors[0])

    def test_exceeds_max_length_is_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            long_desc = "あ" * 1025 + "。「long」で起動。"
            self._skill(root, "long", long_desc)
            errors = check_description_quality(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("[description]", errors[0])
            self.assertIn("超過", errors[0])

    def test_exempt_skill_is_not_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._skill(root, "exempt-one", "トリガー語なしの説明。")
            errors = check_description_quality(
                root, trigger_exempt={"skills/exempt-one": "テスト用免除"})
            self.assertEqual(errors, [])

    def test_missing_description_is_not_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "skills/no-desc/SKILL.md",
                        "---\nname: no-desc\n---\n\n# no-desc\n")
            self.assertEqual(check_description_quality(root), [])

    def test_shared_dir_is_excluded(self):
        with tempfile.TemporaryDirectory() as root:
            self._skill(root, "shared", "トリガー語なしだが shared は対象外。")
            self.assertEqual(check_description_quality(root), [])


class TestCheckFrontmatterYamlCompat(unittest.TestCase):
    """チェック13: frontmatter のクォートなし値が strict YAML でも同じ意味で読めること。

    寛容な行ベースパーサでは動くが strict YAML 実装（PyYAML / Go yaml 等）が
    parse error や黙殺を起こすパターン（実例: description 内の生の `: ` で
    3 スキルが他プラットフォームのツールから読めなかった）を機械的に止める。
    """

    def _write(self, root, rel, content):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _skill(self, root, name, description_line):
        self._write(root, f"skills/{name}/SKILL.md",
                    f"---\nname: {name}\ndescription: {description_line}\n---\n\n# {name}\n")

    def test_plain_value_with_colon_space_is_reported(self):
        with tempfile.TemporaryDirectory() as root:
            self._skill(root, "my-skill", "モードを切り替え: save / restore。「my-skill」で起動。")
            errors = check_frontmatter_yaml_compat(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("[frontmatter-yaml]", errors[0])
            self.assertIn("skills/my-skill/SKILL.md (description)", errors[0])

    def test_plain_value_with_trailing_colon_is_reported(self):
        with tempfile.TemporaryDirectory() as root:
            self._skill(root, "my-skill", "以下のいずれかで起動:")
            self.assertEqual(len(check_frontmatter_yaml_compat(root)), 1)

    def test_plain_value_with_hash_comment_is_reported(self):
        with tempfile.TemporaryDirectory() as root:
            self._skill(root, "my-skill", "チャンネル #general に投稿する。「my-skill」で起動。")
            self.assertEqual(len(check_frontmatter_yaml_compat(root)), 1)

    def test_quoted_value_with_colon_space_passes(self):
        with tempfile.TemporaryDirectory() as root:
            self._skill(root, "my-skill",
                        '"Migrate files. Triggers: \\"migrate\\", \\"rename\\"."')
            self.assertEqual(check_frontmatter_yaml_compat(root), [])

    def test_block_scalar_with_colon_space_passes(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "skills/my-skill/SKILL.md",
                        "---\nname: my-skill\ndescription: >-\n"
                        "  モードを切り替え: save / restore。\n---\n")
            self.assertEqual(check_frontmatter_yaml_compat(root), [])

    def test_clean_plain_value_passes(self):
        with tempfile.TemporaryDirectory() as root:
            self._skill(root, "my-skill", "全角コロンは対象外：save / restore。「my-skill」で起動。")
            self.assertEqual(check_frontmatter_yaml_compat(root), [])

    def test_commands_frontmatter_is_checked(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "commands/my-cmd.md",
                        "---\ndescription: 実行モード: run / check\n---\n\n本文。\n")
            errors = check_frontmatter_yaml_compat(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("commands/my-cmd.md (description)", errors[0])


class TestCheckHumanReadableSummary(unittest.TestCase):
    """チェック14: ヒューマンリーダブル要約契約の横展開ガード。

    契約ファイルの存在・before/after ワークト例と、対象 6 スキルの完了表示が
    契約リンク + 固定要約ラベルを持つことをテキストレベルで機械検証する。
    """

    def _contract(self, root, *, before_after=True):
        cdir = os.path.join(root, "skills", "shared", "references")
        os.makedirs(cdir, exist_ok=True)
        body = "# ヒューマンリーダブル要約契約\n\n"
        if before_after:
            body += ("## Before / After ワークト例\n\nBefore: ✅ 保存しました\n"
                     f"After: {HUMAN_READABLE_SUMMARY_LABEL} ...\n")
        with open(os.path.join(cdir, "human-readable-summary.md"), "w",
                  encoding="utf-8") as f:
            f.write(body)

    def _skill(self, root, name, *, link=True, label=True):
        sdir = os.path.join(root, "skills", name)
        os.makedirs(sdir, exist_ok=True)
        body = "---\nname: {n}\ndescription: d\n---\n\n本文。\n".format(n=name)
        if link:
            body += "\n参照: [契約](../shared/references/human-readable-summary.md)\n"
        if label:
            body += "\n完了表示:\n```\n{label} 〜を保存したよ\n```\n".format(
                label=HUMAN_READABLE_SUMMARY_LABEL)
        with open(os.path.join(sdir, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(body)

    def _all_conforming(self, root):
        self._contract(root)
        for name in HUMAN_READABLE_SUMMARY_SKILLS:
            self._skill(root, name)

    def test_all_conforming_passes(self):
        with tempfile.TemporaryDirectory() as root:
            self._all_conforming(root)
            self.assertEqual([], check_human_readable_summary(root))

    def test_missing_contract_is_reported(self):
        with tempfile.TemporaryDirectory() as root:
            for name in HUMAN_READABLE_SUMMARY_SKILLS:
                self._skill(root, name)
            errors = check_human_readable_summary(root)
            self.assertTrue(any("human-readable-summary.md" in e for e in errors))

    def test_contract_without_before_after_example_is_reported(self):
        with tempfile.TemporaryDirectory() as root:
            self._contract(root, before_after=False)
            for name in HUMAN_READABLE_SUMMARY_SKILLS:
                self._skill(root, name)
            errors = check_human_readable_summary(root)
            self.assertTrue(any("before/after" in e.lower() for e in errors))

    def test_skill_missing_contract_link_is_reported(self):
        with tempfile.TemporaryDirectory() as root:
            self._all_conforming(root)
            self._skill(root, HUMAN_READABLE_SUMMARY_SKILLS[0], link=False)
            errors = check_human_readable_summary(root)
            self.assertTrue(any(
                HUMAN_READABLE_SUMMARY_SKILLS[0] in e and "リンク" in e
                for e in errors))

    def test_skill_missing_summary_label_is_reported(self):
        with tempfile.TemporaryDirectory() as root:
            self._all_conforming(root)
            self._skill(root, HUMAN_READABLE_SUMMARY_SKILLS[0], label=False)
            errors = check_human_readable_summary(root)
            self.assertTrue(any(
                HUMAN_READABLE_SUMMARY_SKILLS[0] in e and "ラベル" in e
                for e in errors))


if __name__ == "__main__":
    unittest.main()


class TestCheckDesignTokenSync(unittest.TestCase):
    """チェック18: authoring 層と配布層のデザイントークンが同一であること。

    片方だけ更新すると lint も配布物検査も素通りし、「lint は通るのに配布物は
    古い配色」という無検証の乖離が残る。
    """

    def _write(self, root, rel, content):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _both(self, root, authored, distributed):
        self._write(root, ".design/tokens.css", authored)
        self._write(root, "skills/brief/assets/tokens.css", distributed)

    def test_identical_layers_pass(self):
        with tempfile.TemporaryDirectory() as root:
            self._both(root, ":root { --a: 1px; }\n", ":root { --a: 1px; }\n")
            self.assertEqual(check_design_token_sync(root), [])

    def test_diverged_layers_are_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._both(root, ":root { --a: 1px; }\n", ":root { --a: 2px; }\n")
            errors = check_design_token_sync(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("乖離している", errors[0])

    def test_absent_authoring_layer_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "skills/brief/assets/tokens.css", ":root { --a: 1px; }\n")
            self.assertEqual(check_design_token_sync(root), [])

class TestCheckPluginHooks(unittest.TestCase):
    """チェック21: hook が壊れても CI が緑のまま注入だけ止まる状態を塞ぐ。"""

    HOOKS_JSON = (
        '{"hooks": {"SessionStart": [{"matcher": "startup",'
        ' "hooks": [{"type": "command",'
        ' "command": "\\"${CLAUDE_PLUGIN_ROOT}\\"/hooks/inject-skill-routing.sh"},'
        ' {"type": "command",'
        ' "command": "\\"${CLAUDE_PLUGIN_ROOT}\\"/hooks/inject-quality-gate.sh"}]}]}}'
    )

    def _write(self, root, rel, content, executable=False):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        if executable:
            os.chmod(path, 0o755)

    def _full_setup(self, root):
        self._write(root, "hooks/hooks.json", self.HOOKS_JSON)
        self._write(root, "hooks/inject-skill-routing.sh",
                    "#!/bin/sh\ncat rules/skill-routing.md\n", executable=True)
        self._write(root, "rules/skill-routing.md", "# routing\n")
        self._write(root, "hooks/inject-quality-gate.sh",
                    "#!/bin/sh\nprintf 'pointer\\n'\n", executable=True)
        self._write(root,
                    "skills/shared/references/quality-gate-contract.md",
                    "# contract\n")

    def test_absent_hooks_json_is_noop(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(check_plugin_hooks(root), [])

    def test_conforming_hooks_pass(self):
        with tempfile.TemporaryDirectory() as root:
            self._full_setup(root)
            self.assertEqual(check_plugin_hooks(root), [])

    def test_unparseable_hooks_json_is_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._full_setup(root)
            self._write(root, "hooks/hooks.json", "{not json")
            errors = check_plugin_hooks(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("JSON として読めない", errors[0])

    def test_missing_command_script_is_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._full_setup(root)
            os.remove(os.path.join(root, "hooks/inject-skill-routing.sh"))
            errors = check_plugin_hooks(root)
            self.assertTrue(any("実体が存在しない" in e for e in errors))

    def test_missing_exec_bit_is_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._full_setup(root)
            os.chmod(os.path.join(root, "hooks/inject-skill-routing.sh"), 0o644)
            errors = check_plugin_hooks(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("実行ビットがない", errors[0])

    def test_missing_routing_table_is_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._full_setup(root)
            os.remove(os.path.join(root, "rules/skill-routing.md"))
            errors = check_plugin_hooks(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("正本が存在しない", errors[0])

    def test_missing_quality_gate_contract_is_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._full_setup(root)
            os.remove(os.path.join(
                root, "skills/shared/references/quality-gate-contract.md"))
            errors = check_plugin_hooks(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("inject-quality-gate.sh が参照する正本が存在しない",
                          errors[0].replace(os.sep, "/"))

    def test_absent_hook_script_skips_its_source_check(self):
        # スクリプトを同梱しない配布形態では、その正本の欠落を咎めない
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "hooks/hooks.json",
                        '{"hooks": {"SessionStart": [{"matcher": "startup",'
                        ' "hooks": [{"type": "command",'
                        ' "command": "\\"${CLAUDE_PLUGIN_ROOT}\\"'
                        '/hooks/inject-skill-routing.sh"}]}]}}')
            self._write(root, "hooks/inject-skill-routing.sh",
                        "#!/bin/sh\ncat rules/skill-routing.md\n",
                        executable=True)
            self._write(root, "rules/skill-routing.md", "# routing\n")
            self.assertEqual(check_plugin_hooks(root), [])

    def test_whitespace_only_command_is_flagged_not_crash(self):
        with tempfile.TemporaryDirectory() as root:
            self._full_setup(root)
            self._write(root, "hooks/hooks.json",
                        '{"hooks": {"SessionStart": [{"hooks":'
                        ' [{"type": "command", "command": "   "}]}]}}')
            errors = check_plugin_hooks(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("command がない", errors[0])

    def test_non_object_top_level_is_flagged_not_crash(self):
        with tempfile.TemporaryDirectory() as root:
            self._full_setup(root)
            for payload in ("[]", "null", '"hooks"'):
                self._write(root, "hooks/hooks.json", payload)
                errors = check_plugin_hooks(root)
                self.assertEqual(len(errors), 1, payload)
                self.assertIn("トップレベルが object でない", errors[0])

    def test_non_object_hooks_key_is_flagged_not_crash(self):
        with tempfile.TemporaryDirectory() as root:
            self._full_setup(root)
            self._write(root, "hooks/hooks.json", '{"hooks": []}')
            errors = check_plugin_hooks(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("object でない", errors[0])

    def test_non_list_event_entries_are_flagged_not_crash(self):
        with tempfile.TemporaryDirectory() as root:
            self._full_setup(root)
            self._write(root, "hooks/hooks.json",
                        '{"hooks": {"SessionStart": {"hooks": []}}}')
            errors = check_plugin_hooks(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("配列でない", errors[0])

    def test_malformed_entry_structure_is_flagged_not_crash(self):
        with tempfile.TemporaryDirectory() as root:
            self._full_setup(root)
            self._write(root, "hooks/hooks.json",
                        '{"hooks": {"SessionStart": ["not-an-object"]}}')
            errors = check_plugin_hooks(root)
            self.assertEqual(len(errors), 1)
            self.assertIn("構造が不正", errors[0])


class TestCheckLegacyClaudePaths(unittest.TestCase):
    """チェック19: agent 生成物の置き場に `.claude/` を使っていないこと。

    共有契約は provider 名入りのパスを禁じており、#76 で `.agents/tmp/` と
    `.agents/config/` へ移行した。ガードが無いと次に書かれた 1 行から静かに戻る。
    同時に、Claude Code の実体パス（監査対象・入力ソース・配置先）を誤検出しては
    ならない。誤検出するガードは無効化され、検出力が 0 になる。
    """

    def _write(self, root, rel, content):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def test_migrated_paths_pass(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "skills/demo/SKILL.md",
                        "中間結果は `.agents/tmp/demo/` に置く。\n"
                        "レビュー規則は `.agents/config/review-rules.md`。\n")
            self.assertEqual(check_legacy_claude_paths(root), [])

    def test_legacy_tmp_reference_is_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "skills/demo/SKILL.md", "中間結果は `.claude/tmp/demo/`。\n")
            errors = check_legacy_claude_paths(root)
            self.assertEqual(len(errors), 1)
            self.assertIn(".claude/tmp", errors[0])
            self.assertIn("skills/demo/SKILL.md:1", errors[0])

    def test_legacy_review_rules_reference_is_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "skills/demo/references/r.md", "`.claude/review-rules.md`\n")
            self.assertEqual(len(check_legacy_claude_paths(root)), 1)

    def test_legacy_baseline_reference_is_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "skills/demo/scripts/s.py",
                        'BASE = ".claude/skill-interface-audit-baseline.json"\n')
            self.assertEqual(len(check_legacy_claude_paths(root)), 1)

    def test_claude_code_real_paths_are_not_flagged(self):
        """監査対象・入力ソース・配置先は `.claude/` のままが正しい。"""
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "skills/demo/SKILL.md",
                        "セッションログは `~/.claude/projects/` から読む。\n"
                        "監査対象は `~/.claude/CLAUDE.md` と `.claude/rules/`。\n"
                        "配置先は `.claude/skills` と `~/.claude/plugins/cache/`。\n"
                        "`.claude/settings.local.json` は個人設定。\n")
            self.assertEqual(check_legacy_claude_paths(root), [])

    def test_fixture_source_provenance_is_exempt(self):
        """`source` は捕獲場所の来歴であって現在の書き込み先ではない。"""
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "skills/demo/fixtures.json",
                        '{\n  "scenarios": [\n'
                        '    { "source": ".claude/tmp/empirical/20260725-x/" }\n'
                        '  ]\n}\n')
            self.assertEqual(check_legacy_claude_paths(root), [])

    def test_non_source_line_in_fixtures_is_still_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "skills/demo/fixtures.json",
                        '{ "text": "中間置き場 .claude/tmp/demo/ を残していない" }\n')
            self.assertEqual(len(check_legacy_claude_paths(root)), 1)

    def test_another_key_on_the_same_line_as_source_is_still_flagged(self):
        """除外は行単位ではなく値単位。同じ行の別キーを巻き添えにしない。"""
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "skills/demo/fixtures.json",
                        '{ "source": ".claude/tmp/empirical/x/", '
                        '"text": "中間置き場 .claude/tmp/demo/ を残していない" }\n')
            self.assertEqual(len(check_legacy_claude_paths(root)), 1)

    def test_ledger_note_recording_the_migration_is_exempt(self):
        """`note` は過去の検証イベントの記録。移行を述べた記録自体が違反にならない。"""
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "skills/demo/ledger.json",
                        '{ "demo": { "note": "#76 の .claude/tmp → .agents/tmp 移行に'
                        '伴う再評価。escaped \\" quote も含む" } }\n')
            self.assertEqual(check_legacy_claude_paths(root), [])

    def test_another_key_on_the_same_line_as_note_is_still_flagged(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "skills/demo/fixtures.json",
                        '{ "note": "移行前は .claude/tmp/x/ だった", '
                        '"text": "中間置き場 .claude/tmp/demo/ を残していない" }\n')
            self.assertEqual(len(check_legacy_claude_paths(root)), 1)


class TestCheckRenameAllowlistStaleness(unittest.TestCase):
    """チェック20: リネーム許可表の失効エントリ検出。

    identifier_preservation の許可表エントリは、baseline から old が消えたら
    役目を終えている。残すと「消えた識別子を無条件で許す穴」が恒久化するため、
    baseline に old が存在しないエントリを失効として報告する。
    """

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = temp.name
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self._git("init", "-q")
        self._git("config", "user.email", "test@example.com")
        self._git("config", "user.name", "test")
        self._git("checkout", "-q", "-B", "main")

    def _git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.root, env=self.env,
            check=True, capture_output=True, text=True,
        ).stdout

    def _write(self, rel, content):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _commit(self, message):
        self._git("add", "-A")
        self._git("commit", "-q", "-m", message)

    def test_missing_allowlist_is_noop(self):
        self._write("skills/a/SKILL.md", "# A\n")
        self._commit("init")
        self.assertEqual(check_rename_allowlist_staleness(self.root), [])

    def test_empty_allowlist_is_noop(self):
        self._write("skills/a/SKILL.md", "# A\n")
        self._write("scripts/rename-allowlist.json", "[]")
        self._commit("init")
        self.assertEqual(check_rename_allowlist_staleness(self.root), [])

    def test_valid_entry_passes_when_old_exists_in_baseline(self):
        """baseline に old が存在するエントリは失効していない。"""
        self._write("skills/a/SKILL.md", "# A\n\n`executor_model` を指定する。\n")
        self._write("scripts/rename-allowlist.json", json.dumps([
            {"old": "executor_model", "new": "executor_tier",
             "reason": "platform-independent", "added": "2026-07-28"}
        ]))
        self._commit("init")
        self.assertEqual(check_rename_allowlist_staleness(self.root), [])

    def test_stale_entry_is_flagged_when_old_not_in_baseline(self):
        """baseline に old が存在しないエントリは失効（受け入れ条件 3）。"""
        self._write("skills/a/SKILL.md", "# A\n\n`executor_tier` を指定する。\n")
        self._write("scripts/rename-allowlist.json", json.dumps([
            {"old": "executor_model", "new": "executor_tier",
             "reason": "platform-independent", "added": "2026-07-28"}
        ]))
        self._commit("init")
        errors = check_rename_allowlist_staleness(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("executor_model", errors[0])
        self.assertIn("失効", errors[0])

    def test_no_resolvable_baseline_returns_empty(self):
        """baseline を解決できない環境では skip して pass する。"""
        self._write("skills/a/SKILL.md", "# A\n")
        self._write("scripts/rename-allowlist.json", json.dumps([
            {"old": "foo", "new": "bar", "reason": "x", "added": "2026-07-28"}
        ]))
        self._commit("init")
        self._git("branch", "-m", "detached-work")
        self.assertEqual(check_rename_allowlist_staleness(self.root), [])

    def test_entry_is_valid_during_rename_branch_and_stale_after_merge(self):
        """feature branch でリネーム中は valid、main へマージ後は stale。"""
        self._write("skills/a/SKILL.md", "# A\n\n`executor_model` を指定する。\n")
        self._commit("baseline with old identifier")
        self._git("checkout", "-q", "-b", "rename-branch")
        self._write("skills/a/SKILL.md", "# A\n\nSpecify `executor_tier`.\n")
        self._write("scripts/rename-allowlist.json", json.dumps([
            {"old": "executor_model", "new": "executor_tier",
             "reason": "platform-independent", "added": "2026-07-28"}
        ]))
        self._commit("rename executor_model to executor_tier")
        # feature branch 上: main にはまだ old がある → valid
        self.assertEqual(check_rename_allowlist_staleness(self.root), [])
        # main にマージ → old が消える → stale
        self._git("checkout", "-q", "main")
        self._git("merge", "-q", "rename-branch")
        errors = check_rename_allowlist_staleness(self.root)
        self.assertEqual(len(errors), 1)
        self.assertIn("executor_model", errors[0])
