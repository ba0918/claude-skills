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
