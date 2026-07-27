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
import unittest.mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check_translation_parity import (  # noqa: E402
    baseline_lead,
    compare,
    fingerprint,
    is_translation,
    main,
    report,
    resolve_baseline,
    scan,
)

FRONTMATTER = "---\nname: demo\ndescription: Demo skill. Use when demoing.\n---\n"


def doc(body, frontmatter=FRONTMATTER):
    return frontmatter + body


def mixed_body(japanese, english, heading="# Heading"):
    """日本語 N 行 + 英語 M 行の本文。部分翻訳ファイルを組み立てるための素材。"""
    lines = [heading, ""]
    lines += [f"日本語で書かれた {i} 行目である。" for i in range(japanese)]
    lines += [f"English line {i}." for i in range(english)]
    return "\n".join(lines) + "\n"


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

    def test_skill_name_is_extracted_and_frontmatter_excluded_from_body(self):
        fp = fingerprint(doc("# Heading\n"))
        self.assertEqual("demo", fp["name"])
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

    def test_partial_translation_below_the_threshold_is_detected(self):
        """元から大半が英語のファイルは閾値を跨がない。減少側の経路で拾う。"""
        base = doc(mixed_body(japanese=3, english=25))
        self.assertLess(3 / 29, 0.15, "前提: baseline は既に閾値未満である")
        self.assertTrue(is_translation(base, doc(mixed_body(japanese=0, english=28))))

    def test_deleting_a_japanese_section_is_not_a_translation(self):
        """節の削除は散文行そのものを減らす。翻訳と数えるとゲートが常時赤になる。"""
        base = doc(mixed_body(japanese=4, english=30))
        self.assertFalse(is_translation(base, doc(mixed_body(japanese=0, english=27))))

    def test_a_one_line_touch_up_is_not_a_translation(self):
        base = doc(mixed_body(japanese=3, english=25))
        self.assertFalse(is_translation(base, doc(mixed_body(japanese=2, english=26))))

    def test_adding_english_without_touching_japanese_is_not_a_translation(self):
        base = doc(mixed_body(japanese=3, english=25))
        self.assertFalse(is_translation(base, doc(mixed_body(japanese=3, english=35))))


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
    def test_changed_skill_name_is_blocked(self):
        after = doc(EN_BODY, frontmatter=FRONTMATTER.replace("name: demo", "name: demo2"))
        findings = [f for f in compare("SKILL.md", doc(JA_BODY), after)
                    if f["rule"] == "frontmatter_immutability"]
        self.assertEqual(1, len(findings))
        self.assertEqual("BLOCK", findings[0]["severity"])

    def test_translated_description_is_allowed(self):
        after = doc(EN_BODY, frontmatter=FRONTMATTER.replace(
            "Demo skill. Use when demoing.", "デモ用スキル。デモのときに使う。"))
        findings = [f for f in compare("SKILL.md", doc(JA_BODY), after)
                    if f["rule"] == "frontmatter_immutability"]
        self.assertEqual([], findings)


class TestTranslatedUserFacingTextIsNotFlagged(unittest.TestCase):
    def test_translated_fence_content_raises_no_finding(self):
        after = EN_BODY.replace("完了メッセージ: 「{count} 件を処理したよ」",
                                "Done message: \"Processed {count} items\"")
        self.assertEqual([], compare("SKILL.md", doc(JA_BODY), doc(after)))

    def test_translated_placeholder_template_quote_raises_no_finding(self):
        before = doc("# H\n\n「{X} が原因だ」の形式で書く。\n")
        after = doc("# H\n\nWrite it in the form: `{X}` is the cause.\n")
        self.assertEqual([], compare("SKILL.md", before, after))


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
            return report(findings, 1, 0, [], strict)

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
        findings, checked, skipped, unverified = scan(self.root, "HEAD", [])
        self.assertEqual((1, 0, []), (checked, skipped, unverified))
        self.assertEqual({"structure_parity"}, {f["rule"] for f in findings})
        self.assertEqual("skills/demo/SKILL.md", findings[0]["file"])

    def test_japanese_edit_is_skipped_so_ordinary_work_is_not_gated(self):
        self._write("skills/demo/SKILL.md", doc(JA_BODY))
        self._commit("add japanese skill")
        self._write("skills/demo/SKILL.md",
                    doc(JA_BODY.replace("## 手順", "## 追記\n\n段落。\n\n## 手順")))
        findings, checked, skipped, unverified = scan(self.root, "HEAD", [])
        self.assertEqual(([], 0, 1, []), (findings, checked, skipped, unverified))

    def test_force_checks_even_without_a_translation_transition(self):
        self._write("skills/demo/SKILL.md", doc(JA_BODY))
        self._commit("add japanese skill")
        self._write("skills/demo/SKILL.md",
                    doc(JA_BODY.replace("## 手順", "## 追記\n\n段落。\n\n## 手順")))
        findings, checked, _, _ = scan(self.root, "HEAD", [], force=True)
        self.assertEqual(1, checked)
        self.assertTrue(findings)

    def test_new_file_without_a_baseline_is_skipped(self):
        self._write("README.md", "# readme\n")
        self._commit("init")
        self._write("skills/demo/SKILL.md", doc(EN_BODY))
        self.assertEqual(([], 0, 0, []), scan(self.root, "HEAD", []))

    def test_deleted_file_is_skipped(self):
        self._write("skills/demo/SKILL.md", doc(JA_BODY))
        self._commit("add japanese skill")
        os.remove(os.path.join(self.root, "skills/demo/SKILL.md"))
        self.assertEqual(([], 0, 0, []), scan(self.root, "HEAD", []))

    def test_paths_narrow_the_scan(self):
        self._write("skills/a/SKILL.md", doc(JA_BODY))
        self._write("skills/b/SKILL.md", doc(JA_BODY))
        self._commit("add two skills")
        broken = doc(EN_BODY.replace("## Steps\n\n", ""))
        self._write("skills/a/SKILL.md", broken)
        self._write("skills/b/SKILL.md", broken)
        _, checked, _, _ = scan(self.root, "HEAD", ["skills/a"])
        self.assertEqual(1, checked)

    def test_partial_translation_damage_is_caught_end_to_end(self):
        """#65 の死角。閾値を跨がない部分翻訳ファイルで見出しを落としたケース。"""
        self._write("skills/demo/SKILL.md", doc(mixed_body(japanese=3, english=25)))
        self._commit("add a partially translated skill")
        translated = mixed_body(japanese=0, english=28).replace("# Heading\n", "")
        self._write("skills/demo/SKILL.md", doc(translated))
        findings, checked, _, _ = scan(self.root, "HEAD", [])
        self.assertEqual(1, checked)
        self.assertEqual({"structure_parity"}, {f["rule"] for f in findings})

    def test_untranslated_loss_outside_the_gate_is_listed_as_unverified(self):
        """翻訳判定に載らないが日本語が減ったファイルは、黙って落とさず列挙する。"""
        self._write("skills/demo/SKILL.md", doc(mixed_body(japanese=3, english=25)))
        self._commit("add a partially translated skill")
        self._write("skills/demo/SKILL.md", doc(mixed_body(japanese=2, english=26)))
        _, checked, skipped, unverified = scan(self.root, "HEAD", [])
        self.assertEqual((0, 1), (checked, skipped))
        self.assertEqual([("skills/demo/SKILL.md", 3, 2)], unverified)

    def test_unverified_files_are_named_in_the_report(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = report([], 0, 1, [("skills/demo/SKILL.md", 3, 2)], strict=False)
        out = buf.getvalue()
        self.assertEqual(0, code, "可視化であって新たなゲートではない")
        self.assertIn("未検証 1 ファイル", out)
        self.assertIn("skills/demo/SKILL.md", out)

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


class TestBaselineFreshness(unittest.TestCase):
    """古い remote-tracking ref を比較元にすると偽 BLOCK が出る（#88）。

    ゲートが理由なく赤くなると `--baseline` で握りつぶす運用が定着し、
    fixture 未保有 26 スキルの唯一の劣化検出手段が実質的に無効化される。
    比較が成立しないときは、赤にせず skip を明示出力する。
    """

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = temp.name
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self._git("init", "-q")
        self._git("config", "user.email", "test@example.com")
        self._git("config", "user.name", "test")
        # 既定ブランチ名は環境依存なので、候補連鎖が拾う `main` を明示的に作る。
        self._git("checkout", "-q", "-B", "main")
        self._write("skills/demo/SKILL.md", doc(JA_BODY))
        self._commit("add japanese skill")
        self._git("checkout", "-q", "-b", "work")
        for i in range(2):
            self._write(f"docs/note{i}.md", f"# note {i}\n")
            self._commit(f"unrelated commit {i}")
        # 作業ツリーには見出しを 1 つ落とした翻訳を置く（本来なら BLOCK）。
        self._write("skills/demo/SKILL.md", doc(EN_BODY.replace("## Steps\n\n", "")))

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

    def _run(self, *extra):
        argv = ["check_translation_parity.py", "--repo", self.root, *extra]
        clean = {k: v for k, v in os.environ.items()
                 if k not in ("GITHUB_BASE_REF", "TRANSLATION_PARITY_BASELINE")}
        buf = io.StringIO()
        with unittest.mock.patch.object(sys, "argv", argv), \
                unittest.mock.patch.dict(os.environ, clean, clear=True), \
                contextlib.redirect_stdout(buf):
            code = main()
        return code, buf.getvalue()

    def test_baseline_lead_counts_commits_ahead_of_the_baseline(self):
        base = self._git("rev-parse", "main").strip()
        self.assertEqual(2, baseline_lead(self.root, base))

    def test_a_fresh_baseline_still_reports_the_damage(self):
        code, out = self._run("--max-baseline-lead", "5")
        self.assertEqual(1, code)
        self.assertIn("structure_parity", out)

    def test_a_stale_baseline_skips_instead_of_reporting_false_findings(self):
        code, out = self._run("--max-baseline-lead", "1")
        self.assertEqual(0, code, "偽 BLOCK で赤にせず、成立しないことを申告する")
        self.assertIn("baseline が古すぎるため skip", out)
        self.assertIn("git fetch origin main", out)
        self.assertNotIn("structure_parity", out)

    def test_an_explicit_baseline_is_exempt_from_the_freshness_guard(self):
        """明示指定は利用者の判断。鮮度を理由に握り潰さない。"""
        code, out = self._run("--baseline", "main", "--max-baseline-lead", "1")
        self.assertEqual(1, code)
        self.assertIn("structure_parity", out)


if __name__ == "__main__":
    unittest.main()
