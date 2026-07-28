"""md_fence の回帰テスト。

3 スキャナが独立したフェンス走査を持っていた時代の不具合を再現し、
共有モジュールで修正されたことを保証する:

- ``~~~`` フェンスの開閉
- ```````` + 内側 ````` の入れ子
- 混合フェンス（`` ` `` と ``~``）
- インデント付きフェンス
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from md_fence import classify_lines, is_fence_line, iter_outside_fence  # noqa: E402


class TestIsFenceLine(unittest.TestCase):
    def test_triple_backtick(self):
        self.assertEqual(("`", 3), is_fence_line("```"))

    def test_quad_backtick(self):
        self.assertEqual(("`", 4), is_fence_line("````"))

    def test_triple_tilde(self):
        self.assertEqual(("~", 3), is_fence_line("~~~"))

    def test_quad_tilde(self):
        self.assertEqual(("~", 4), is_fence_line("~~~~"))

    def test_indented_backtick(self):
        self.assertEqual(("`", 3), is_fence_line("  ```"))

    def test_indented_tilde(self):
        self.assertEqual(("~", 3), is_fence_line("  ~~~"))

    def test_backtick_with_language(self):
        self.assertEqual(("`", 3), is_fence_line("```python"))

    def test_tilde_with_language(self):
        self.assertEqual(("~", 3), is_fence_line("~~~bash"))

    def test_not_a_fence_too_short(self):
        self.assertIsNone(is_fence_line("``"))

    def test_not_a_fence_plain_text(self):
        self.assertIsNone(is_fence_line("hello world"))

    def test_not_a_fence_inline_code(self):
        self.assertIsNone(is_fence_line("use `code` here"))

    def test_empty_line(self):
        self.assertIsNone(is_fence_line(""))

    def test_five_backticks(self):
        self.assertEqual(("`", 5), is_fence_line("`````"))


class TestIterOutsideFence(unittest.TestCase):
    def test_basic_fence(self):
        lines = ["before", "```", "inside", "```", "after"]
        self.assertEqual(["before", "after"], list(iter_outside_fence(lines)))

    def test_tilde_fence(self):
        lines = ["before", "~~~", "inside", "~~~", "after"]
        self.assertEqual(["before", "after"], list(iter_outside_fence(lines)))

    def test_nested_backtick_fence(self):
        """4 連バッククォートの内側の 3 連は閉じとみなさない。"""
        lines = [
            "before",
            "````",
            "inner start",
            "```",
            "still inside",
            "```",
            "still inside too",
            "````",
            "after",
        ]
        self.assertEqual(["before", "after"], list(iter_outside_fence(lines)))

    def test_nested_backtick_odd_inner(self):
        """内側に奇数個の 3 連があっても状態が狂わない。"""
        lines = [
            "before",
            "````",
            "```",
            "```",
            "```",
            "````",
            "after",
        ]
        self.assertEqual(["before", "after"], list(iter_outside_fence(lines)))

    def test_tilde_does_not_close_backtick(self):
        """種類が違うフェンスは閉じない。"""
        lines = ["before", "```", "~~~", "inside", "```", "after"]
        self.assertEqual(["before", "after"], list(iter_outside_fence(lines)))

    def test_backtick_does_not_close_tilde(self):
        lines = ["before", "~~~", "```", "inside", "~~~", "after"]
        self.assertEqual(["before", "after"], list(iter_outside_fence(lines)))

    def test_indented_fence(self):
        lines = ["before", "  ```", "inside", "  ```", "after"]
        self.assertEqual(["before", "after"], list(iter_outside_fence(lines)))

    def test_longer_closer_is_accepted(self):
        """閉じ側が長い場合も正しく閉じる。"""
        lines = ["before", "```", "inside", "````", "after"]
        self.assertEqual(["before", "after"], list(iter_outside_fence(lines)))

    def test_shorter_closer_is_rejected(self):
        """閉じ側が短い場合は閉じない。"""
        lines = ["before", "````", "inside", "```", "still inside", "````", "after"]
        self.assertEqual(["before", "after"], list(iter_outside_fence(lines)))

    def test_no_fence(self):
        lines = ["line1", "line2", "line3"]
        self.assertEqual(lines, list(iter_outside_fence(lines)))

    def test_empty_input(self):
        self.assertEqual([], list(iter_outside_fence([])))

    def test_unclosed_fence_hides_remaining_lines(self):
        lines = ["before", "```", "inside", "more inside"]
        self.assertEqual(["before"], list(iter_outside_fence(lines)))

    def test_multiple_fences(self):
        lines = ["a", "```", "b", "```", "c", "~~~", "d", "~~~", "e"]
        self.assertEqual(["a", "c", "e"], list(iter_outside_fence(lines)))

    def test_fence_with_language_tag(self):
        lines = ["before", "```python", "code", "```", "after"]
        self.assertEqual(["before", "after"], list(iter_outside_fence(lines)))

    def test_real_world_quad_backtick_with_inner_triple(self):
        """report-template.md のパターン: 4 連で囲んだ中に 3 連が複数。"""
        lines = [
            "prose before",
            "````markdown",
            "# Template",
            "```python",
            "print('hello')",
            "```",
            "more template",
            "```bash",
            "echo hi",
            "```",
            "end template",
            "````",
            "prose after",
        ]
        self.assertEqual(["prose before", "prose after"],
                         list(iter_outside_fence(lines)))


class TestClassifyLines(unittest.TestCase):
    def test_basic_classification(self):
        lines = ["before", "```", "inside", "```", "after"]
        result = list(classify_lines(lines))
        self.assertEqual([
            ("prose", "before"),
            ("fence_marker", "```"),
            ("fenced", "inside"),
            ("fence_marker", "```"),
            ("prose", "after"),
        ], result)

    def test_nested_fence_classification(self):
        lines = ["a", "````", "```", "b", "```", "````", "c"]
        result = list(classify_lines(lines))
        self.assertEqual([
            ("prose", "a"),
            ("fence_marker", "````"),
            ("fenced", "```"),
            ("fenced", "b"),
            ("fenced", "```"),
            ("fence_marker", "````"),
            ("prose", "c"),
        ], result)

    def test_mixed_fence_types(self):
        lines = ["a", "~~~", "b", "~~~", "c"]
        result = list(classify_lines(lines))
        self.assertEqual([
            ("prose", "a"),
            ("fence_marker", "~~~"),
            ("fenced", "b"),
            ("fence_marker", "~~~"),
            ("prose", "c"),
        ], result)


if __name__ == "__main__":
    unittest.main()
