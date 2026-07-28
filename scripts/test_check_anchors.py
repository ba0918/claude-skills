"""check_anchors の単体テスト。

この検査は「見出しを改名して参照を取りこぼす」を捕まえるためにある。
偽陽性を出すと翻訳のたびに赤くなって無効化されるので、壊れているものを
検出できることと同じ重みで、正しい参照を止めないことを検証する。
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check_anchors import anchors, scan, slugify  # noqa: E402


class TestSlugify(unittest.TestCase):
    def test_spaces_become_hyphens_and_case_is_lowered(self):
        self.assertEqual("claim-3-layers-of-defense",
                         slugify("claim() 3 Layers of Defense"))

    def test_removed_symbol_leaves_a_double_hyphen(self):
        """記号除去で空白が 2 つ残る形。連続空白を畳むと取りこぼす。"""
        self.assertEqual("exit-code-shared-by-spec_lint--trace_matrix",
                         slugify("Exit code shared by spec_lint / trace_matrix"))

    def test_inline_code_is_unwrapped(self):
        self.assertEqual("mark_failedslug-kind", slugify("`mark_failed(slug, kind)`"))

    def test_underscores_survive_as_word_characters(self):
        self.assertEqual("state_root-resolution", slugify("state_root Resolution"))


class TestAnchors(unittest.TestCase):
    def _write(self, body):
        handle = tempfile.NamedTemporaryFile(
            "w", suffix=".md", delete=False, encoding="utf-8")
        handle.write(body)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def test_headings_inside_a_fence_are_ignored(self):
        path = self._write("# Real\n\n```\n# Fake\n```\n")
        self.assertEqual({"real"}, anchors(path))

    def test_every_heading_level_is_collected(self):
        path = self._write("# A\n\n### B C\n")
        self.assertEqual({"a", "b-c"}, anchors(path))

    def test_duplicate_headings_get_numbered_slugs(self):
        """同一見出しが複数回出現したら -1, -2 のスラグも生成される。"""
        path = self._write("# A\n\n## B\n\n## B\n\n## B\n")
        result = anchors(path)
        self.assertIn("b", result)
        self.assertIn("b-1", result)
        self.assertIn("b-2", result)
        self.assertEqual({"a", "b", "b-1", "b-2"}, result)

    def test_headings_inside_nested_fence_are_ignored(self):
        """4 連バッククォート内の 3 連を跨いで見出しが拾われてはならない。"""
        path = self._write("# Real\n\n````\n```\n# Fake\n```\n````\n")
        self.assertEqual({"real"}, anchors(path))

    def test_tilde_fence_hides_headings(self):
        path = self._write("# Real\n\n~~~\n# Fake\n~~~\n")
        self.assertEqual({"real"}, anchors(path))


class TestScan(unittest.TestCase):
    def _repo(self, files):
        root = tempfile.mkdtemp()
        self.addCleanup(lambda: None)
        for name, body in files.items():
            path = os.path.join(root, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(body)
        return root

    def test_a_live_anchor_is_not_reported(self):
        root = self._repo({
            "a.md": "# A\n\nSee [B](b.md#target-heading).\n",
            "b.md": "# B\n\n## Target Heading\n",
        })
        self.assertEqual([], scan([root]))

    def test_a_renamed_heading_breaks_the_reference(self):
        root = self._repo({
            "a.md": "# A\n\nSee [B](b.md#old-name).\n",
            "b.md": "# B\n\n## New Name\n",
        })
        broken = scan([root])
        self.assertEqual(1, len(broken))
        self.assertEqual("b.md#old-name", broken[0][1])

    def test_a_same_file_anchor_is_resolved(self):
        root = self._repo({"a.md": "# A\n\nJump to [X](#section-x).\n\n## Section X\n"})
        self.assertEqual([], scan([root]))

    def test_external_urls_and_anchorless_links_are_skipped(self):
        root = self._repo({
            "a.md": "[x](https://example.com#frag) [y](b.md) [z](../out.md#gone)\n",
            "b.md": "# B\n",
        })
        self.assertEqual([], scan([root]))

    def test_links_inside_fences_are_not_checked(self):
        """scan() がフェンス内のリンクを除外する（anchors() との対称性）。"""
        root = self._repo({
            "a.md": "# A\n\n```\n[link](b.md#nonexistent)\n```\n",
            "b.md": "# B\n",
        })
        self.assertEqual([], scan([root]))

    def test_duplicate_heading_anchor_is_reachable(self):
        """重複見出しの -1 スラグへのリンクが壊れたと報告されない。"""
        root = self._repo({
            "a.md": "# A\n\nSee [B](b.md#section) and [B2](b.md#section-1).\n",
            "b.md": "# B\n\n## Section\n\n## Section\n",
        })
        self.assertEqual([], scan([root]))

    def test_subdirectories_are_walked(self):
        """走査範囲が再帰的にサブディレクトリを含む。"""
        root = self._repo({
            "commands/a.md": "# A\n\nSee [B](../skills/b.md#gone).\n",
            "skills/b.md": "# B\n",
        })
        broken = scan([root])
        self.assertEqual(1, len(broken))
