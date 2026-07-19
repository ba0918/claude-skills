"""validate_repo.py の純関数ユニットテスト。

実行: python3 -m unittest discover scripts
"""
import os
import subprocess
import tempfile
import unittest

import json

from validate_repo import (
    extract_md_links,
    is_checkable_link,
    parse_frontmatter_fields,
    find_broken_symlinks,
    check_contract_conformance,
    check_changelog_sync,
    check_description_quality,
    check_frontmatter_yaml_compat,
    collect_link_sources,
    check_relative_links,
    check_portable_resource_refs,
    mentions_name,
    check_dossiers,
    check_artifact_store,
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
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
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
        # 「## 1.46.10」は version 1.46.1 のエントリではない
        with tempfile.TemporaryDirectory() as root:
            self._plugin(root, "1.46.1")
            self._write(root, "CHANGELOG.md", "## 1.46.10\n")
            self.assertEqual(len(check_changelog_sync(root)), 1)

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


if __name__ == "__main__":
    unittest.main()
