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


if __name__ == "__main__":
    unittest.main()
