"""check_language_coverage のユニットテスト。

ゲート（check_translation_parity）が import する strip_frontmatter / measure /
untranslated / prose_lines の境界挙動を固定する。

実行: python3 -m unittest discover scripts
"""
import pathlib
import unittest

from check_language_coverage import (
    strip_frontmatter,
    prose_lines,
    untranslated,
    measure,
)


class TestStripFrontmatter(unittest.TestCase):
    def test_normal_frontmatter(self):
        lines = ["---", "name: foo", "description: bar", "---", "body"]
        self.assertEqual(strip_frontmatter(lines), ["body"])

    def test_frontmatter_with_comment(self):
        lines = ["---", "# comment", "name: foo", "---", "body"]
        self.assertEqual(strip_frontmatter(lines), ["body"])

    def test_frontmatter_with_blank_lines(self):
        lines = ["---", "name: foo", "", "key: val", "---", "body"]
        self.assertEqual(strip_frontmatter(lines), ["body"])

    def test_unclosed_frontmatter_returns_all(self):
        lines = ["---", "name: foo", "body line"]
        self.assertEqual(strip_frontmatter(lines), lines)

    def test_no_frontmatter(self):
        lines = ["# heading", "body"]
        self.assertEqual(strip_frontmatter(lines), lines)

    def test_empty(self):
        self.assertEqual(strip_frontmatter([]), [])

    def test_leading_hr_not_frontmatter(self):
        """#148: 先頭の水平線を frontmatter とみなさない。"""
        lines = ["---", "日本語の本文がここにある。", "---", "More English prose."]
        self.assertEqual(strip_frontmatter(lines), lines)

    def test_leading_hr_single_prose(self):
        lines = ["---", "some prose", "---"]
        self.assertEqual(strip_frontmatter(lines), lines)

    def test_leading_hr_with_mixed_content(self):
        lines = ["---", "title but no colon", "name: looks like yaml", "---", "body"]
        self.assertEqual(strip_frontmatter(lines), lines)

    def test_real_frontmatter_with_quoted_values(self):
        lines = ["---", "name: 'my-skill'", "description: \"A skill\"", "---", "body"]
        self.assertEqual(strip_frontmatter(lines), ["body"])

    def test_frontmatter_only_blank_block(self):
        """空行だけのブロックは frontmatter として扱わない。"""
        lines = ["---", "", "", "---", "body"]
        self.assertEqual(strip_frontmatter(lines), lines)

    def test_yaml_list_values(self):
        """YAML リスト値を含む frontmatter を正しく認識する。"""
        lines = ["---", "dirty_files:", "  - src/foo.py", "  - src/bar.py", "---", "body"]
        self.assertEqual(strip_frontmatter(lines), ["body"])


class TestProseLines(unittest.TestCase):
    def test_basic(self):
        text = "# heading\n\nbody line\n"
        self.assertEqual(prose_lines(text), ["# heading", "body line"])

    def test_fenced_excluded(self):
        text = "before\n```\ncode\n```\nafter\n"
        self.assertEqual(prose_lines(text), ["before", "after"])

    def test_empty_lines_excluded(self):
        text = "a\n\n\nb\n"
        self.assertEqual(prose_lines(text), ["a", "b"])

    def test_frontmatter_excluded(self):
        text = "---\nname: x\n---\nbody\n"
        self.assertEqual(prose_lines(text), ["body"])

    def test_hr_excluded(self):
        text = "before\n---\nafter\n"
        self.assertEqual(prose_lines(text), ["before", "after"])

    def test_hr_variants_excluded(self):
        text = "a\n***\nb\n___\nc\n----\nd\n"
        self.assertEqual(prose_lines(text), ["a", "b", "c", "d"])

    def test_zero_prose(self):
        text = "```\ncode only\n```\n"
        self.assertEqual(prose_lines(text), [])


class TestUntranslated(unittest.TestCase):
    def test_japanese_line(self):
        self.assertTrue(untranslated("これは日本語です"))

    def test_english_line(self):
        self.assertFalse(untranslated("This is English"))

    def test_quoted_japanese_excluded(self):
        self.assertFalse(untranslated("Use the 「日本語」 format"))

    def test_japanese_outside_quotes(self):
        self.assertTrue(untranslated("「English」の外に日本語がある"))

    def test_double_quoted_excluded(self):
        self.assertFalse(untranslated("See 『日本語テスト』 here"))

    def test_empty_line(self):
        self.assertFalse(untranslated(""))


class TestMeasure(unittest.TestCase):
    def test_basic(self):
        text = "---\nname: x\n---\n日本語の本文。\nEnglish prose.\n"
        self.assertEqual(measure(text), (1, 2))

    def test_all_translated(self):
        text = "All English here.\nAnother line.\n"
        self.assertEqual(measure(text), (0, 2))

    def test_all_japanese(self):
        text = "日本語の行。\nもう一行。\n"
        self.assertEqual(measure(text), (2, 2))

    def test_zero_prose(self):
        text = "```\ncode\n```\n"
        self.assertEqual(measure(text), (0, 0))

    def test_issue_148_regression(self):
        """#148: 先頭水平線 + 日本語本文が消えて (0,1) になっていたバグ。"""
        text = "---\n日本語の本文がここにある。\n---\nMore English prose.\n"
        n, total = measure(text)
        self.assertEqual(n, 1, "日本語行が未翻訳として数えられるべき")
        self.assertEqual(total, 2, "散文は水平線を除いて 2 行")

    def test_hr_not_counted_as_prose(self):
        text = "before\n---\nafter\n"
        self.assertEqual(measure(text), (0, 2))


class TestRepoRegression(unittest.TestCase):
    """リポジトリ内の既存 md 全件で strip_frontmatter の判定が変わらないことを検証。"""

    _SKIP_DIRS = {".git", ".claude", ".agents", "node_modules"}

    @staticmethod
    def _naive_strip(lines):
        """修正前の strip_frontmatter（比較用）。"""
        if not lines or lines[0].strip() != "---":
            return lines
        for i, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                return lines[i + 1:]
        return lines

    def test_all_md_files_consistent(self):
        repo = pathlib.Path(__file__).resolve().parent.parent
        md_files = [
            p for p in sorted(repo.rglob("*.md"))
            if not any(part in self._SKIP_DIRS for part in p.relative_to(repo).parts)
        ]
        self.assertGreater(len(md_files), 100, f"md ファイルが少なすぎる: {len(md_files)}")
        diffs = []
        for p in md_files:
            try:
                lines = p.read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            old = self._naive_strip(lines)
            new = strip_frontmatter(lines)
            if old != new:
                diffs.append(str(p.relative_to(repo)))
        self.assertEqual(diffs, [], f"strip_frontmatter の判定が変わったファイル: {diffs}")


if __name__ == "__main__":
    unittest.main()
