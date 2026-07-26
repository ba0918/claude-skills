"""check_translation_parity の単体テスト。

この sensor は fixture 未保有スキルにとって唯一の劣化検出手段なので、
「壊れているものを検出できる」ことと同じ重みで「正しい翻訳を止めない」ことを
検証する。後者が崩れるとゲートが常時赤になり、無効化されて検出力が 0 になる。
"""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check_translation_parity import (  # noqa: E402
    compare,
    fingerprint,
    is_translation,
    report,
    resolve_baseline,
    scan,
)

FRONTMATTER = "---\nname: demo\ndescription: Demo skill. Use when demoing.\n---\n"


def doc(body, frontmatter=FRONTMATTER):
    return frontmatter + body


JA_BODY = """# 見出し

この節は日本語で書かれている。
`ledger.py --check` を実行する。
詳細は [契約](../shared/references/fix-action-taxonomy.md) を参照する。

## 手順

1. 最初の手順
2. 次の手順

- 箇条書きの一つ目
- 箇条書きの二つ目

| 列 | 意味 |
|----|------|
| a | あ |

---

分類は AUTO_FIX / NEEDS_JUDGMENT / REPORT_ONLY のいずれかである。

```
完了メッセージ: 「{count} 件を処理したよ」
記録欄: 未記入
```
"""

EN_BODY = """# Heading

This section is written in English.
Run `ledger.py --check`.
See [the contract](../shared/references/fix-action-taxonomy.md) for details.

## Steps

1. First step
2. Next step

- First bullet
- Second bullet

| Column | Meaning |
|--------|---------|
| a | A |

---

The classification is one of AUTO_FIX / NEEDS_JUDGMENT / REPORT_ONLY.

```
完了メッセージ: 「{count} 件を処理したよ」
記録欄: 未記入
```
"""


class TestFingerprint(unittest.TestCase):
    def test_counts_structure_outside_fences(self):
        fp = fingerprint(doc(JA_BODY))
        self.assertEqual([1, 2], fp["headings"])
        self.assertEqual(1, fp["fences"])
        self.assertEqual(2, fp["ordered"])
        self.assertEqual(2, fp["bullets"])
        self.assertEqual(3, fp["table_rows"])
        self.assertEqual(1, fp["hrs"])

    def test_horizontal_rule_is_not_counted_as_bullet(self):
        fp = fingerprint(doc("- item\n\n---\n"))
        self.assertEqual(1, fp["bullets"])
        self.assertEqual(1, fp["hrs"])

    def test_frontmatter_is_kept_verbatim_and_excluded_from_body(self):
        fp = fingerprint(doc("# Heading\n"))
        self.assertIn("description: Demo skill.", fp["frontmatter"])
        self.assertEqual([1], fp["headings"])

    def test_identifiers_include_inline_code_and_link_targets(self):
        fp = fingerprint(doc(JA_BODY))
        self.assertIn("ledger.py --check", fp["identifiers"])
        self.assertIn("../shared/references/fix-action-taxonomy.md", fp["identifiers"])

    def test_contract_vocabulary_is_detected(self):
        fp = fingerprint(doc(JA_BODY))
        self.assertEqual({"AUTO_FIX", "NEEDS_JUDGMENT", "REPORT_ONLY"}, fp["vocab"])


class TestTranslationDetection(unittest.TestCase):
    def test_crossing_the_threshold_counts_as_translation(self):
        self.assertTrue(is_translation(doc(JA_BODY), doc(EN_BODY)))

    def test_editing_a_japanese_file_in_japanese_is_not_a_translation(self):
        edited = JA_BODY.replace("## 手順", "## 手順\n\n追記した段落。")
        self.assertFalse(is_translation(doc(JA_BODY), doc(edited)))

    def test_editing_an_already_english_file_is_not_a_translation(self):
        edited = EN_BODY.replace("## Steps", "## Steps\n\nAn added paragraph.")
        self.assertFalse(is_translation(doc(EN_BODY), doc(edited)))


class TestFaithfulTranslation(unittest.TestCase):
    """正しい翻訳を止めないこと（既知の正しい翻訳 5 本で校正済みの性質）。"""

    def test_structure_preserving_translation_reports_nothing(self):
        self.assertEqual([], compare("SKILL.md", doc(JA_BODY), doc(EN_BODY)))

    def test_emphasis_quote_in_prose_may_be_translated(self):
        before = doc("# H\n\n「ついでに」直すのは禁止する。\n")
        after = doc("# H\n\nFixing things while you are at it is prohibited.\n")
        self.assertEqual([], compare("SKILL.md", before, after))


class TestStructureParity(unittest.TestCase):
    def _rules(self, findings, rule):
        return [f for f in findings if f["rule"] == rule]

    def test_lost_heading_is_blocked(self):
        after = EN_BODY.replace("## Steps\n\n", "")
        findings = self._rules(compare("SKILL.md", doc(JA_BODY), doc(after)),
                               "structure_parity")
        self.assertTrue(findings)
        self.assertEqual("BLOCK", findings[0]["severity"])
        self.assertIn("見出しの件数: 2 → 1", findings[0]["detail"])

    def test_heading_level_reorder_at_equal_count_is_blocked(self):
        after = EN_BODY.replace("## Steps", "### Steps")
        details = [f["detail"] for f
                   in self._rules(compare("SKILL.md", doc(JA_BODY), doc(after)),
                                  "structure_parity")]
        self.assertTrue(any("見出しレベルの並び" in d for d in details))

    def test_dropped_table_row_is_blocked(self):
        after = EN_BODY.replace("| a | A |\n", "")
        details = [f["detail"] for f
                   in self._rules(compare("SKILL.md", doc(JA_BODY), doc(after)),
                                  "structure_parity")]
        self.assertTrue(any("表の行数: 3 → 2" in d for d in details))

    def test_dropped_fence_is_blocked(self):
        after = EN_BODY.split("```")[0]
        details = [f["detail"] for f
                   in self._rules(compare("SKILL.md", doc(JA_BODY), doc(after)),
                                  "structure_parity")]
        self.assertTrue(any("コードフェンスの件数: 1 → 0" in d for d in details))

    def test_dropped_numbered_step_is_blocked(self):
        after = EN_BODY.replace("2. Next step\n", "")
        details = [f["detail"] for f
                   in self._rules(compare("SKILL.md", doc(JA_BODY), doc(after)),
                                  "structure_parity")]
        self.assertTrue(any("番号ステップの件数: 2 → 1" in d for d in details))


class TestIdentifierPreservation(unittest.TestCase):
    def test_lost_inline_identifier_is_named_in_the_finding(self):
        after = EN_BODY.replace("Run `ledger.py --check`.", "Run the ledger check.")
        findings = [f for f in compare("SKILL.md", doc(JA_BODY), doc(after))
                    if f["rule"] == "identifier_preservation"]
        self.assertTrue(findings)
        self.assertEqual("BLOCK", findings[0]["severity"])
        self.assertIn("ledger.py --check", findings[0]["detail"])

    def test_lost_link_target_is_blocked(self):
        after = EN_BODY.replace("../shared/references/fix-action-taxonomy.md",
                                "../shared/references/severity-and-verdicts.md")
        rules = {f["rule"] for f in compare("SKILL.md", doc(JA_BODY), doc(after))}
        self.assertIn("identifier_preservation", rules)

    def test_placeholder_containing_japanese_may_be_translated(self):
        before = doc("# H\n\n`{観点}` を指定する。\n")
        after = doc("# H\n\nSpecify `{aspect}`.\n")
        self.assertEqual([], compare("SKILL.md", before, after))

    def test_shell_operator_is_not_treated_as_an_identifier(self):
        before = doc("# H\n\n`>` でリダイレクトする。出力は `report.md` に書く。\n")
        after = doc("# H\n\nRedirect the output into `report.md`.\n")
        self.assertEqual([], compare("SKILL.md", before, after))

    def test_regrouped_inline_code_is_not_a_loss(self):
        """`(none)` → `branch: (none)` のような括り直しは消失ではない。"""
        before = doc("# H\n\nbranch には `(none)` を入れる。\n")
        after = doc("# H\n\nSet `branch: (none)` in the frontmatter.\n")
        self.assertEqual([], compare("SKILL.md", before, after))

    def test_lost_contract_vocabulary_is_blocked(self):
        after = EN_BODY.replace(
            "one of AUTO_FIX / NEEDS_JUDGMENT / REPORT_ONLY", "one of three values")
        findings = [f for f in compare("SKILL.md", doc(JA_BODY), doc(after))
                    if "契約語彙" in f["detail"]]
        self.assertTrue(findings)
        self.assertEqual("BLOCK", findings[0]["severity"])


class TestFrontmatterImmutability(unittest.TestCase):
    def test_changed_description_is_blocked(self):
        after = doc(EN_BODY, frontmatter=FRONTMATTER.replace("Demo skill.", "Demo!"))
        findings = [f for f in compare("SKILL.md", doc(JA_BODY), after)
                    if f["rule"] == "frontmatter_immutability"]
        self.assertEqual(1, len(findings))
        self.assertEqual("BLOCK", findings[0]["severity"])


class TestUserFacingTemplates(unittest.TestCase):
    def test_translated_fence_content_is_warned_not_blocked(self):
        after = EN_BODY.replace("完了メッセージ: 「{count} 件を処理したよ」",
                                "Done message: \"Processed {count} items\"")
        findings = [f for f in compare("SKILL.md", doc(JA_BODY), doc(after))
                    if f["rule"] == "user_facing_template_preservation"]
        self.assertTrue(findings)
        self.assertEqual({"WARN"}, {f["severity"] for f in findings})

    def test_lost_placeholder_template_quote_is_warned(self):
        before = doc("# H\n\n「{X} が原因だ」の形式で書く。\n")
        after = doc("# H\n\nWrite it in the form: X is the cause.\n")
        findings = [f for f in compare("SKILL.md", before, after)
                    if f["rule"] == "user_facing_template_preservation"]
        self.assertTrue(findings)
        self.assertIn("{X} が原因だ", findings[0]["detail"])


class TestFixAction(unittest.TestCase):
    def test_every_finding_is_needs_judgment(self):
        after = EN_BODY.replace("## Steps\n\n", "").replace(
            "Run `ledger.py --check`.", "Run it.")
        findings = compare("SKILL.md", doc(JA_BODY), doc(after))
        self.assertTrue(findings)
        self.assertEqual({"NEEDS_JUDGMENT"}, {f["fix_action"] for f in findings})


class TestExitCode(unittest.TestCase):
    def _finding(self, severity):
        return {"file": "a.md", "sensor": "s", "rule": "r",
                "severity": severity, "fix_action": "NEEDS_JUDGMENT", "detail": "d"}

    def _report(self, findings, strict):
        with contextlib.redirect_stdout(io.StringIO()):
            return report(findings, 1, 0, strict)

    def test_block_fails(self):
        self.assertEqual(1, self._report([self._finding("BLOCK")], strict=False))

    def test_warn_alone_passes_by_default(self):
        self.assertEqual(0, self._report([self._finding("WARN")], strict=False))

    def test_warn_fails_under_strict(self):
        self.assertEqual(1, self._report([self._finding("WARN")], strict=True))

    def test_clean_passes(self):
        self.assertEqual(0, self._report([], strict=True))


class TestGitIntegration(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = temp.name
        # git hook 経由では GIT_DIR 等が環境に置かれており、引き継ぐと
        # この init が呼び出し元のリポジトリを操作してしまう。
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self._git("init", "-q")
        self._git("config", "user.email", "test@example.com")
        self._git("config", "user.name", "test")

    def _git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, env=self.env,
                              check=True, capture_output=True, text=True).stdout

    def _write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def _commit(self, message):
        self._git("add", "-A")
        self._git("commit", "-q", "-m", message)

    def test_translated_file_in_the_working_tree_is_checked(self):
        self._write("skills/demo/SKILL.md", doc(JA_BODY))
        self._commit("add japanese skill")
        broken = EN_BODY.replace("## Steps\n\n", "")
        self._write("skills/demo/SKILL.md", doc(broken))
        findings, checked, skipped = scan(self.root, "HEAD", [])
        self.assertEqual((1, 0), (checked, skipped))
        self.assertEqual({"structure_parity"}, {f["rule"] for f in findings})
        self.assertEqual("skills/demo/SKILL.md", findings[0]["file"])

    def test_japanese_edit_is_skipped_so_ordinary_work_is_not_gated(self):
        self._write("skills/demo/SKILL.md", doc(JA_BODY))
        self._commit("add japanese skill")
        self._write("skills/demo/SKILL.md",
                    doc(JA_BODY.replace("## 手順", "## 追記\n\n段落。\n\n## 手順")))
        findings, checked, skipped = scan(self.root, "HEAD", [])
        self.assertEqual(([], 0, 1), (findings, checked, skipped))

    def test_force_checks_even_without_a_translation_transition(self):
        self._write("skills/demo/SKILL.md", doc(JA_BODY))
        self._commit("add japanese skill")
        self._write("skills/demo/SKILL.md",
                    doc(JA_BODY.replace("## 手順", "## 追記\n\n段落。\n\n## 手順")))
        findings, checked, _ = scan(self.root, "HEAD", [], force=True)
        self.assertEqual(1, checked)
        self.assertTrue(findings)

    def test_new_file_without_a_baseline_is_skipped(self):
        self._write("README.md", "# readme\n")
        self._commit("init")
        self._write("skills/demo/SKILL.md", doc(EN_BODY))
        self.assertEqual(([], 0, 0), scan(self.root, "HEAD", []))

    def test_deleted_file_is_skipped(self):
        self._write("skills/demo/SKILL.md", doc(JA_BODY))
        self._commit("add japanese skill")
        os.remove(os.path.join(self.root, "skills/demo/SKILL.md"))
        self.assertEqual(([], 0, 0), scan(self.root, "HEAD", []))

    def test_paths_narrow_the_scan(self):
        self._write("skills/a/SKILL.md", doc(JA_BODY))
        self._write("skills/b/SKILL.md", doc(JA_BODY))
        self._commit("add two skills")
        broken = doc(EN_BODY.replace("## Steps\n\n", ""))
        self._write("skills/a/SKILL.md", broken)
        self._write("skills/b/SKILL.md", broken)
        _, checked, _ = scan(self.root, "HEAD", ["skills/a"])
        self.assertEqual(1, checked)

    def test_explicit_baseline_wins_over_the_candidate_chain(self):
        self._write("README.md", "# readme\n")
        self._commit("init")
        head = self._git("rev-parse", "HEAD").strip()
        self.assertEqual(head, resolve_baseline(self.root, "HEAD"))

    def test_unresolvable_baseline_returns_none(self):
        self._write("README.md", "# readme\n")
        self._commit("init")
        # origin/main も main も無い状態（既定ブランチ名に依存しないよう明示的に改名）
        self._git("branch", "-m", "detached-work")
        self.assertIsNone(resolve_baseline(self.root, "no-such-rev"))


if __name__ == "__main__":
    unittest.main()
