"""frontmatter.py の unittest。

3 つの再実装（scripts/validate_repo.py / skills/context-audit/scripts/
static_checks.py / skills/trigger-eval/scripts/collect_descriptions.py）の
既存挙動を統合後も維持することを保証する。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from frontmatter import (
    extract_description,
    parse_frontmatter_fields,
    parse_frontmatter_lines,
    parse_name_and_description,
)


class TestParseFrontmatterLines(unittest.TestCase):
    def test_basic_keys_with_raw_lines(self):
        text = "---\nname: note\ndescription: a note\n---\nbody"
        self.assertEqual(
            parse_frontmatter_lines(text),
            [
                ("name", "note", "name: note"),
                ("description", "a note", "description: a note"),
            ],
        )

    def test_preserves_raw_line_for_non_canonical_formatting(self):
        # CA-M001 の整形正規化チェックが raw 行を必要とする
        text = "---\nname:note\n---\nbody"
        self.assertEqual(
            parse_frontmatter_lines(text), [("name", "note", "name:note")]
        )

    def test_no_frontmatter_returns_none(self):
        self.assertIsNone(parse_frontmatter_lines("# タイトルだけ\n本文"))

    def test_unclosed_frontmatter_returns_none(self):
        self.assertIsNone(parse_frontmatter_lines("---\nname: a\n本文だけで閉じない"))

    def test_empty_text_returns_none(self):
        self.assertIsNone(parse_frontmatter_lines(""))

    def test_key_may_contain_digits_after_first_char(self):
        text = "---\nv2: yes\n---\n"
        self.assertEqual(parse_frontmatter_lines(text), [("v2", "yes", "v2: yes")])

    def test_key_may_not_start_with_digit_or_hyphen(self):
        # `- item:` のような YAML リスト行・数字始まりはトップレベルキーではない
        text = "---\nname: a\n2fast: x\n-item: y\n---\n"
        self.assertEqual(
            [k for k, _, _ in parse_frontmatter_lines(text)], ["name"]
        )

    def test_indented_lines_are_not_keys(self):
        text = "---\ndescription: >\n  折り返し行: これはキーではない\n---\n"
        self.assertEqual(
            [k for k, _, _ in parse_frontmatter_lines(text)], ["description"]
        )


class TestParseFrontmatterFields(unittest.TestCase):
    def test_parses_name_and_description(self):
        text = "---\nname: my-skill\ndescription: すごいスキル\n---\n\n# Body\n"
        fields = parse_frontmatter_fields(text)
        self.assertEqual(fields.get("name"), "my-skill")
        self.assertEqual(fields.get("description"), "すごいスキル")

    def test_no_frontmatter_returns_empty(self):
        self.assertEqual(parse_frontmatter_fields("# タイトルだけ\n本文"), {})

    def test_unclosed_frontmatter_returns_empty(self):
        self.assertEqual(parse_frontmatter_fields("---\nname: a\n閉じない"), {})

    def test_ignores_fields_after_closing_delimiter(self):
        text = "---\nname: a\n---\ndescription: 本文中の偽フィールド\n"
        fields = parse_frontmatter_fields(text)
        self.assertIn("name", fields)
        self.assertNotIn("description", fields)

    def test_value_is_stripped(self):
        text = "---\nname:   spaced   \n---\n"
        self.assertEqual(parse_frontmatter_fields(text), {"name": "spaced"})


class TestExtractDescription(unittest.TestCase):
    def test_single_line(self):
        text = "---\nname: a\ndescription: 一行の説明\n---\n"
        self.assertEqual(extract_description(text), "一行の説明")

    def test_block_scalar_folded(self):
        text = (
            "---\nname: a\ndescription: >\n"
            "  一行目の説明。\n"
            "  二行目の説明。\n"
            "---\n"
        )
        self.assertEqual(extract_description(text), "一行目の説明。 二行目の説明。")

    def test_block_scalar_literal_and_strip_variants(self):
        for marker in (">", "|", ">-", "|-"):
            text = f"---\ndescription: {marker}\n  aaa\n  bbb\n---\n"
            self.assertEqual(extract_description(text), "aaa bbb", marker)

    def test_multiline_stops_at_next_top_level_key(self):
        text = (
            "---\ndescription: >\n  説明文。\nlicense: MIT\n---\n"
        )
        self.assertEqual(extract_description(text), "説明文。")

    def test_blank_continuation_lines_are_dropped(self):
        text = "---\ndescription: >\n  aaa\n\n  bbb\n---\n"
        self.assertEqual(extract_description(text), "aaa bbb")

    def test_no_description_returns_none(self):
        self.assertIsNone(extract_description("---\nname: a\n---\n"))

    def test_no_frontmatter_returns_none(self):
        self.assertIsNone(extract_description("本文だけ\n"))

    def test_unclosed_frontmatter_returns_none(self):
        self.assertIsNone(extract_description("---\ndescription: x\n閉じない"))

    def test_body_description_is_ignored(self):
        text = "---\nname: a\n---\ndescription: 本文中の偽物\n"
        self.assertIsNone(extract_description(text))


class TestParseNameAndDescription(unittest.TestCase):
    def test_basic(self):
        text = "---\nname: my-skill\ndescription: 説明\n---\n"
        self.assertEqual(
            parse_name_and_description(text),
            {"name": "my-skill", "description": "説明"},
        )

    def test_multiline_description(self):
        text = "---\nname: s\ndescription: >\n  aaa\n  bbb\n---\n"
        self.assertEqual(
            parse_name_and_description(text),
            {"name": "s", "description": "aaa bbb"},
        )

    def test_missing_name_becomes_empty(self):
        text = "---\ndescription: d\n---\n"
        self.assertEqual(
            parse_name_and_description(text), {"name": "", "description": "d"}
        )

    def test_missing_description_becomes_empty(self):
        text = "---\nname: s\n---\n"
        self.assertEqual(
            parse_name_and_description(text), {"name": "s", "description": ""}
        )

    def test_no_frontmatter_returns_none(self):
        self.assertIsNone(parse_name_and_description("no frontmatter here\n"))

    def test_unclosed_returns_none(self):
        self.assertIsNone(parse_name_and_description("---\nname: s\n閉じない"))


if __name__ == "__main__":
    unittest.main()
