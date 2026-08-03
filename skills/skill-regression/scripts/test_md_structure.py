"""md_structure.py の unittest。

散文のみ変更（prose-only）の判定材料になる構造フィンガープリントを検証する。
誤判定の向きが非対称であることに注意: 散文の変化を構造変化と誤判定しても
contract-change（重い側）に倒れるだけで安全だが、構造変化を散文と誤判定すると
未検証の挙動変更が軽量承認レールに乗る。テストは後者の穴を塞ぐ方向を厚くする。
"""
import unittest

import md_structure


def _fp(text):
    return md_structure.structural_fingerprint(text)


class TestProseOnlyChangesKeepFingerprint(unittest.TestCase):
    """散文だけの編集ではフィンガープリントが変わらない。"""

    def test_prose_rewording(self):
        before = "# Title\n\nThis is the old wording of the paragraph.\n"
        after = "# Title\n\nThis paragraph was reworded entirely.\n"
        self.assertEqual(_fp(before), _fp(after))

    def test_prose_added_outside_fence(self):
        before = "# Title\n\n```sh\nrun me\n```\n"
        after = "# Title\n\nA new explanatory sentence.\n\n```sh\nrun me\n```\n"
        self.assertEqual(_fp(before), _fp(after))

    def test_link_text_rewording_keeps_target(self):
        before = "See [the old label](refs/contract.md) for details.\n"
        after = "Read [a new label](refs/contract.md) instead.\n"
        self.assertEqual(_fp(before), _fp(after))


class TestStructuralChangesBreakFingerprint(unittest.TestCase):
    """機械パーストークンが 1 つでも変わればフィンガープリントが変わる。"""

    def test_frontmatter_change(self):
        before = "---\nname: a\n---\nbody\n"
        after = "---\nname: b\n---\nbody\n"
        self.assertNotEqual(_fp(before), _fp(after))

    def test_fence_content_change(self):
        before = "intro\n\n```sh\necho one\n```\n"
        after = "intro\n\n```sh\necho two\n```\n"
        self.assertNotEqual(_fp(before), _fp(after))

    def test_fence_added(self):
        before = "intro\n"
        after = "intro\n\n```sh\necho new\n```\n"
        self.assertNotEqual(_fp(before), _fp(after))

    def test_tilde_fence_content_change(self):
        before = "~~~\nold\n~~~\n"
        after = "~~~\nnew\n~~~\n"
        self.assertNotEqual(_fp(before), _fp(after))

    def test_inline_code_change(self):
        before = "run `ledger.py --check` first\n"
        after = "run `ledger.py --status` first\n"
        self.assertNotEqual(_fp(before), _fp(after))

    def test_link_target_change(self):
        before = "see [label](refs/old.md)\n"
        after = "see [label](refs/new.md)\n"
        self.assertNotEqual(_fp(before), _fp(after))

    def test_reference_definition_change(self):
        before = "[contract]: refs/old.md\n"
        after = "[contract]: refs/new.md\n"
        self.assertNotEqual(_fp(before), _fp(after))

    def test_table_row_change(self):
        # セル内の散文も含め表は丸ごとトークン（fail-safe: 重い側）
        before = "| a | old cell |\n|---|---|\n"
        after = "| a | new cell |\n|---|---|\n"
        self.assertNotEqual(_fp(before), _fp(after))

    def test_heading_change(self):
        # 見出しはワークフローの step 名として参照されるためトークン扱い
        before = "## Step 1: Gather\n\nprose\n"
        after = "## Step 1: Collect\n\nprose\n"
        self.assertNotEqual(_fp(before), _fp(after))

    def test_indented_code_block_change(self):
        before = "para\n\n    old command\n"
        after = "para\n\n    new command\n"
        self.assertNotEqual(_fp(before), _fp(after))

    def test_token_reorder(self):
        # 同じトークン集合でも並びが変われば別物（順序保持）
        before = "```sh\none\n```\n\n```sh\ntwo\n```\n"
        after = "```sh\ntwo\n```\n\n```sh\none\n```\n"
        self.assertNotEqual(_fp(before), _fp(after))


class TestFenceInteriorIsOpaque(unittest.TestCase):
    """フェンス内はコードとして丸ごと扱い、他の規則を適用しない。"""

    def test_prose_like_line_inside_fence_is_code(self):
        before = "```\njust words here\n```\n"
        after = "```\ndifferent words here\n```\n"
        self.assertNotEqual(_fp(before), _fp(after))

    def test_unclosed_fence_swallows_rest(self):
        # 閉じられていないフェンスは残り全文をコード扱い（重い側）
        before = "```\ntail one\n"
        after = "```\ntail two\n"
        self.assertNotEqual(_fp(before), _fp(after))


class TestFingerprintShape(unittest.TestCase):
    def test_deterministic_hex(self):
        text = "# t\n\nprose\n"
        self.assertEqual(_fp(text), _fp(text))
        self.assertEqual(len(_fp(text)), 64)


if __name__ == "__main__":
    unittest.main()
