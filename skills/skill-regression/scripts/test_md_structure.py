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

    def test_prose_around_structural_lines(self):
        # 構造行（フェンス・見出し）はそのままに、地の文の段落だけが変わる
        before = "# T\n\nOld explanation here.\n\n```sh\nrun\n```\n"
        after = "# T\n\nA better explanation.\n\n```sh\nrun\n```\n"
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


class TestAdversarialFalseNegatives(unittest.TestCase):
    """PR #224 敵対レビューで deny-list 実装に実証された偽陰性 5 種の固定。

    いずれも「挙動を変える編集なのにフィンガープリントが変わらない」collision
    だったもの。allow-list 反転後は必ず不一致になる。
    """

    def test_list_item_instruction_change(self):
        before = "1. Delete cache.\n"
        after = "1. Delete database.\n"
        self.assertNotEqual(_fp(before), _fp(after))

    def test_unordered_list_item_change(self):
        before = "- run the linter\n"
        after = "- skip the linter\n"
        self.assertNotEqual(_fp(before), _fp(after))

    def test_setext_heading_change(self):
        before = "Step One\n--------\n"
        after = "Step Two\n--------\n"
        self.assertNotEqual(_fp(before), _fp(after))

    def test_table_without_leading_pipe(self):
        before = "run | safe\n"
        after = "run | destructive\n"
        self.assertNotEqual(_fp(before), _fp(after))

    def test_tab_indented_code_change(self):
        before = "\tcommand old\n"
        after = "\tcommand new\n"
        self.assertNotEqual(_fp(before), _fp(after))

    def test_html_tag_content_change(self):
        before = "<agent-rule>allow</agent-rule>\n"
        after = "<agent-rule>deny</agent-rule>\n"
        self.assertNotEqual(_fp(before), _fp(after))

    def test_reference_link_label_change(self):
        # 両定義が残ったまま use 側のラベルを差し替える = 解決先の変更
        before = "see [policy][old]\n\n[old]: refs/a.md\n[new]: refs/b.md\n"
        after = "see [policy][new]\n\n[old]: refs/a.md\n[new]: refs/b.md\n"
        self.assertNotEqual(_fp(before), _fp(after))

    def test_link_destination_with_parentheses(self):
        before = "see [x](dir/(stable)old.md)\n"
        after = "see [x](dir/(stable)new.md)\n"
        self.assertNotEqual(_fp(before), _fp(after))

    def test_multi_backtick_inline_code_change(self):
        before = "use ``foo ` old`` now\n"
        after = "use ``foo ` new`` now\n"
        self.assertNotEqual(_fp(before), _fp(after))

    def test_inner_shorter_fence_is_not_a_closer(self):
        # 4 連フェンス内の ``` を closer と誤認すると以降の変更が指紋から漏れる
        before = "````md\n```\ninner old\n```\n````\n"
        after = "````md\n```\ninner new\n```\n````\n"
        self.assertNotEqual(_fp(before), _fp(after))

    def test_blockquote_change(self):
        before = "> do the safe thing\n"
        after = "> do the risky thing\n"
        self.assertNotEqual(_fp(before), _fp(after))

    def test_link_text_change_is_structural_by_fail_safe(self):
        # リンクテキストの言い換えは deny-list 時代は散文扱いだった。shortcut
        # reference（テキスト自体が解決先）と区別できないため、行ごと重い側へ倒す
        before = "See [the old label](refs/contract.md) for details.\n"
        after = "Read [a new label](refs/contract.md) instead.\n"
        self.assertNotEqual(_fp(before), _fp(after))

    def test_deeply_indented_fence_marker_is_not_a_closer(self):
        # closer のインデントは 3 以下（4 以上はフェンス内のコード行）
        before = "```\n    ```\ntail old\n```\n"
        after = "```\n    ```\ntail new\n```\n"
        self.assertNotEqual(_fp(before), _fp(after))

    def test_multiline_setext_heading_first_line_change(self):
        # setext 見出しは複数行を許す。先頭行の変更も見出しの変更
        before = "First old\nSecond\n------\n"
        after = "First new\nSecond\n------\n"
        self.assertNotEqual(_fp(before), _fp(after))

    def test_mixed_space_tab_indented_code_change(self):
        # スペース + タブの混合インデントもタブストップ展開で 4 カラムに達する
        before = " \tcommand old\n"
        after = " \tcommand new\n"
        self.assertNotEqual(_fp(before), _fp(after))

    def test_processing_instruction_html_change(self):
        before = "<?agent allow?>\n"
        after = "<?agent deny?>\n"
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
