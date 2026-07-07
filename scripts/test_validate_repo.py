"""validate_repo.py の純関数ユニットテスト。

実行: python3 -m unittest discover scripts
"""
import os
import tempfile
import unittest

from validate_repo import (
    extract_md_links,
    is_checkable_link,
    parse_frontmatter_fields,
    extract_command_refs,
    find_broken_symlinks,
    resolve_codex_source,
    check_sync_manifest,
    check_contract_conformance,
    collect_link_sources,
    check_relative_links,
    mentions_name,
)


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
        self.assertFalse(is_checkable_link("docs/plans/{timestamp}_{slug}.md"))

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


class TestExtractCommandRefs(unittest.TestCase):
    def test_extracts_command_paths(self):
        text = (
            "commands/plan-create.md  →  skills/plan/SKILL.md\n"
            "commands/cycle.md        →  plan-refine + plan-implement\n"
        )
        self.assertEqual(
            extract_command_refs(text),
            {"commands/plan-create.md", "commands/cycle.md"},
        )

    def test_dedupes(self):
        text = "commands/commit.md commands/commit.md"
        self.assertEqual(extract_command_refs(text), {"commands/commit.md"})


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


class TestResolveCodexSource(unittest.TestCase):
    def test_default_maps_to_skills_dir(self):
        self.assertEqual(resolve_codex_source("plan"), "skills/plan/SKILL.md")
        self.assertEqual(resolve_codex_source("commit"), "skills/commit/SKILL.md")

    def test_cycle_maps_to_command(self):
        # cycle は Claude 側にスキル実体がなく commands/cycle.md がソース
        self.assertEqual(resolve_codex_source("cycle"), "commands/cycle.md")


class TestCheckSyncManifest(unittest.TestCase):
    PAIRS = [("codex-skills/plan/SKILL.md", "skills/plan/SKILL.md")]

    def _manifest(self, sha):
        return {
            "codex-skills/plan/SKILL.md": {
                "source": "skills/plan/SKILL.md",
                "source_sha256": sha,
            }
        }

    def test_in_sync_returns_no_errors(self):
        hashes = {"skills/plan/SKILL.md": "abc123"}
        self.assertEqual(
            check_sync_manifest(self.PAIRS, self._manifest("abc123"), hashes), []
        )

    def test_source_changed_reports_drift(self):
        hashes = {"skills/plan/SKILL.md": "NEWHASH"}
        errors = check_sync_manifest(self.PAIRS, self._manifest("abc123"), hashes)
        self.assertEqual(len(errors), 1)
        self.assertIn("未同期", errors[0])

    def test_unregistered_pair_reports_error(self):
        hashes = {"skills/plan/SKILL.md": "abc123"}
        errors = check_sync_manifest(self.PAIRS, {}, hashes)
        self.assertEqual(len(errors), 1)
        self.assertIn("未登録", errors[0])

    def test_missing_source_reports_error(self):
        errors = check_sync_manifest(self.PAIRS, self._manifest("abc123"), {})
        self.assertEqual(len(errors), 1)
        self.assertIn("存在しない", errors[0])

    def test_stale_manifest_entry_reports_error(self):
        manifest = self._manifest("abc123")
        manifest["codex-skills/ghost/SKILL.md"] = {
            "source": "skills/ghost/SKILL.md",
            "source_sha256": "dead",
        }
        hashes = {"skills/plan/SKILL.md": "abc123"}
        errors = check_sync_manifest(self.PAIRS, manifest, hashes)
        self.assertEqual(len(errors), 1)
        self.assertIn("実在しない", errors[0])

    def test_source_path_mismatch_reports_error(self):
        manifest = self._manifest("abc123")
        manifest["codex-skills/plan/SKILL.md"]["source"] = "skills/other/SKILL.md"
        hashes = {"skills/plan/SKILL.md": "abc123"}
        errors = check_sync_manifest(self.PAIRS, manifest, hashes)
        self.assertEqual(len(errors), 1)
        self.assertIn("source が不一致", errors[0])


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

    def test_includes_shared_and_codex_references(self):
        # shared は _skill_dirs から除外されるが、共有契約こそリンク検査が必要
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "skills/shared/references/contract.md")
            self._write(root, "codex-skills/b/SKILL.md")
            self._write(root, "codex-skills/b/references/nested/deep.md")
            self._write(root, "codex-skills/shared/references/tool-mapping.md")
            rels = {os.path.relpath(p, root) for p in collect_link_sources(root)}
            self.assertEqual(
                rels,
                {"skills/shared/references/contract.md",
                 "codex-skills/b/SKILL.md",
                 "codex-skills/b/references/nested/deep.md",
                 "codex-skills/shared/references/tool-mapping.md"},
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
                        "[plan](docs/plans/{timestamp}_{slug}.md) を生成する。")
            self.assertEqual(check_relative_links(root), [])

    def test_exempt_file_is_skipped(self):
        # テンプレファイル内のリンクは生成先プロジェクトの構造を指す例示
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "skills/a/references/template.md",
                        "[archive](./session-history.md) を参照。")
            exempt = {"skills/a/references/template.md": "テンプレの例示リンク"}
            self.assertEqual(check_relative_links(root, exempt=exempt), [])
            self.assertEqual(len(check_relative_links(root, exempt={})), 1)


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


if __name__ == "__main__":
    unittest.main()
