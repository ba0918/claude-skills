"""md_links.py の unittest。

markdown 相対リンクの抽出・チェック可能判定・推移的クロージャの純関数を検証する。
挙動は scripts/validate_repo.py のリンク抽出と整合させる（アンカー除去 /
プレースホルダ・URL・タイムスタンプ例示の除外）。
"""
import os
import tempfile
import unittest

import md_links


def _write(root, rel, content=""):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


class TestExtractMdLinks(unittest.TestCase):
    def test_extracts_relative_md_links(self):
        text = "see [a](references/a.md) and [b](../shared/references/b.md)"
        self.assertEqual(
            md_links.extract_md_links(text),
            ["references/a.md", "../shared/references/b.md"],
        )

    def test_strips_anchor(self):
        self.assertEqual(
            md_links.extract_md_links("[x](a.md#section-1)"), ["a.md"]
        )

    def test_ignores_non_md_targets(self):
        self.assertEqual(md_links.extract_md_links("[x](a.png) [y](b.json)"), [])


class TestIsCheckableLink(unittest.TestCase):
    def test_relative_md_is_checkable(self):
        self.assertTrue(md_links.is_checkable_link("references/a.md"))

    def test_urls_and_absolute_are_not(self):
        for link in ("https://x.example/a.md", "http://x/a.md", "/abs/a.md",
                     "mailto:a@example.com"):
            self.assertFalse(md_links.is_checkable_link(link), link)

    def test_placeholders_are_not(self):
        self.assertFalse(md_links.is_checkable_link("docs/plans/{ts}_{slug}.md"))
        self.assertFalse(md_links.is_checkable_link("docs/plans/*.md"))

    def test_timestamp_examples_are_not(self):
        self.assertFalse(
            md_links.is_checkable_link("docs/plans/20260101120000_example.md")
        )


class TestClosure(unittest.TestCase):
    def test_includes_start_file(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/a/SKILL.md", "no links")
            self.assertEqual(
                md_links.closure(root, "skills/a/SKILL.md"),
                ["skills/a/SKILL.md"],
            )

    def test_follows_links_transitively(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/a/SKILL.md",
                   "[c](../shared/references/contract.md)")
            _write(root, "skills/shared/references/contract.md",
                   "[other](other.md)")
            _write(root, "skills/shared/references/other.md", "end")
            self.assertEqual(
                md_links.closure(root, "skills/a/SKILL.md"),
                [
                    "skills/a/SKILL.md",
                    "skills/shared/references/contract.md",
                    "skills/shared/references/other.md",
                ],
            )

    def test_cycle_safe(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "a.md", "[b](b.md)")
            _write(root, "b.md", "[a](a.md)")
            self.assertEqual(md_links.closure(root, "a.md"), ["a.md", "b.md"])

    def test_skips_missing_and_uncheckable_targets(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "a.md",
                   "[gone](missing.md) [url](https://x/y.md) [ph]({var}.md)")
            self.assertEqual(md_links.closure(root, "a.md"), ["a.md"])

    def test_skips_links_escaping_root(self):
        with tempfile.TemporaryDirectory() as root:
            inner = os.path.join(root, "repo")
            _write(inner, "a.md", "[esc](../outside.md)")
            _write(root, "outside.md", "outside the repo")
            self.assertEqual(md_links.closure(inner, "a.md"), ["a.md"])

    def test_missing_start_returns_empty(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(md_links.closure(root, "nope.md"), [])


if __name__ == "__main__":
    unittest.main()
