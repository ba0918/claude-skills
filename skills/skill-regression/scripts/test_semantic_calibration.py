"""semantic_calibration.py の unittest。

較正は判定器へ権限を与える前に「判定器自身の当てにならなさ」を測る工程で、
その結果だけが自動記録のゲートを開ける。採点が甘い方向へ壊れると、誤り率を
測っていないモデルの判定が台帳へ入る経路が開くので、偽陰性の計上と
「材料が欠けたら書かない」規則を重点的に固定する。
"""
import json
import os
import tempfile
import unittest

import ledger
import semantic_calibration


def _write(root, rel, content=""):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def _case(case_id, expected, **overrides):
    case = {
        "id": case_id,
        "expected": expected,
        "before": "手順 A を実行する。",
        "after": "手順 A を実施する。",
        "requirements": ["手順 A を実行したことが報告に含まれる"],
    }
    case.update(overrides)
    return case


class _CorpusHarness(unittest.TestCase):
    def _corpus(self, root, cases):
        for case in cases:
            side = "must_flag" if case["expected"] == "must-flag" else "must_pass"
            _write(root,
                   f"skills/skill-regression/calibration/{side}/{case['id']}.json",
                   json.dumps(case, ensure_ascii=False))

    def _run(self, argv):
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = semantic_calibration.main(argv)
        return rc, buf.getvalue()

    def _results(self, root, model, results):
        path = os.path.join(root, "results.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"model": model, "results": results}, f,
                      ensure_ascii=False)
        return path


class TestCorpusSchema(_CorpusHarness):
    """schema 違反は例外ではなく拒否メッセージにする（材料が壊れたら書かない）。"""

    def test_a_well_formed_corpus_has_no_errors(self):
        with tempfile.TemporaryDirectory() as root:
            self._corpus(root, [_case("f1", "must-flag"),
                                _case("p1", "must-pass")])
            self.assertEqual(
                semantic_calibration.validate_corpus(root, min_cases=1), [])

    def test_each_required_field_is_mandatory(self):
        for field in ("id", "expected", "before", "after", "requirements"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as root:
                case = _case("f1", "must-flag")
                del case[field]
                _write(root,
                       "skills/skill-regression/calibration/must_flag/f1.json",
                       json.dumps(case, ensure_ascii=False))
                errors = semantic_calibration.validate_corpus(root, min_cases=0)
                self.assertTrue(errors)
                self.assertTrue(any(field in e for e in errors))

    def test_an_unknown_expected_value_is_refused(self):
        with tempfile.TemporaryDirectory() as root:
            self._corpus(root, [_case("f1", "must-flag")])
            _write(root, "skills/skill-regression/calibration/must_flag/f1.json",
                   json.dumps(_case("f1", "probably-flag"), ensure_ascii=False))
            errors = semantic_calibration.validate_corpus(root, min_cases=0)
            self.assertTrue(any("expected" in e for e in errors))

    def test_a_case_filed_on_the_wrong_side_is_refused(self):
        # ディレクトリと expected が食い違うと、採点の向きが静かに反転する
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/skill-regression/calibration/must_pass/f1.json",
                   json.dumps(_case("f1", "must-flag"), ensure_ascii=False))
            errors = semantic_calibration.validate_corpus(root, min_cases=0)
            self.assertTrue(errors)

    def test_an_unchanged_case_is_refused(self):
        # before == after は「編集」ではない。判定器を測る材料にならない
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/skill-regression/calibration/must_flag/f1.json",
                   json.dumps(_case("f1", "must-flag", before="x", after="x"),
                              ensure_ascii=False))
            errors = semantic_calibration.validate_corpus(root, min_cases=0)
            self.assertTrue(errors)

    def test_empty_requirements_are_refused(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/skill-regression/calibration/must_flag/f1.json",
                   json.dumps(_case("f1", "must-flag", requirements=[]),
                              ensure_ascii=False))
            errors = semantic_calibration.validate_corpus(root, min_cases=0)
            self.assertTrue(any("requirements" in e for e in errors))

    def test_a_duplicate_id_is_refused(self):
        # id は採点の突き合わせキー。重複すると片方の判定が黙って捨てられる
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/skill-regression/calibration/must_flag/a.json",
                   json.dumps(_case("dup", "must-flag"), ensure_ascii=False))
            _write(root, "skills/skill-regression/calibration/must_pass/b.json",
                   json.dumps(_case("dup", "must-pass"), ensure_ascii=False))
            errors = semantic_calibration.validate_corpus(root, min_cases=0)
            self.assertTrue(any("dup" in e for e in errors))

    def test_a_broken_json_file_is_refused(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/skill-regression/calibration/must_flag/f1.json",
                   "{ broken")
            errors = semantic_calibration.validate_corpus(root, min_cases=0)
            self.assertTrue(any("f1.json" in e for e in errors))

    def test_the_case_count_guard_reports_a_thin_side(self):
        with tempfile.TemporaryDirectory() as root:
            self._corpus(root, [_case("f1", "must-flag"),
                                _case("p1", "must-pass")])
            errors = semantic_calibration.validate_corpus(root, min_cases=20)
            self.assertEqual(len(errors), 2)  # 両側とも不足


class TestScoring(_CorpusHarness):
    """偽陰性（must-flag を unaffected と言った）が解禁ラインの唯一の門。"""

    CASES = {
        "f1": _case("f1", "must-flag"),
        "f2": _case("f2", "must-flag"),
        "p1": _case("p1", "must-pass"),
        "p2": _case("p2", "must-pass"),
    }

    def _score(self, results):
        return semantic_calibration.score(self.CASES, results)

    def test_a_perfect_run_scores_zero_on_both_sides(self):
        scored, errors = self._score({
            "f1": "affected", "f2": "affected",
            "p1": "unaffected", "p2": "unaffected"})
        self.assertEqual(errors, [])
        self.assertEqual(scored["must_flag_fn"], 0)
        self.assertEqual(scored["must_pass_fp"], 0)

    def test_an_unaffected_verdict_on_a_must_flag_case_is_a_false_negative(self):
        scored, _ = self._score({
            "f1": "unaffected", "f2": "affected",
            "p1": "unaffected", "p2": "unaffected"})
        self.assertEqual(scored["must_flag_fn"], 1)
        self.assertEqual(scored["false_negatives"], ["f1"])

    def test_unclear_on_a_must_flag_case_is_not_a_false_negative(self):
        # unclear は「言い切れない」= 人間へ回る。危険な取りこぼしではない
        scored, _ = self._score({
            "f1": "unclear", "f2": "affected",
            "p1": "unaffected", "p2": "unaffected"})
        self.assertEqual(scored["must_flag_fn"], 0)

    def test_anything_but_unaffected_on_a_must_pass_case_costs_the_saving(self):
        # affected も unclear も安価な記録には至らない。節約効果の目減りは同じ
        for verdict in ("affected", "unclear"):
            with self.subTest(verdict=verdict):
                scored, _ = self._score({
                    "f1": "affected", "f2": "affected",
                    "p1": verdict, "p2": "unaffected"})
                self.assertEqual(scored["must_pass_fp"], 1)
                self.assertEqual(scored["false_positives"], ["p1"])

    def test_a_missing_verdict_is_an_error_not_a_pass(self):
        # 未判定を黙って除外すると、1 件だけ判定して満点の較正を作れてしまう
        _, errors = self._score({"f1": "affected"})
        self.assertTrue(errors)
        self.assertTrue(any("f2" in e for e in errors))

    def test_an_unknown_case_id_is_an_error(self):
        _, errors = self._score({
            "f1": "affected", "f2": "affected",
            "p1": "unaffected", "p2": "unaffected", "ghost": "unaffected"})
        self.assertTrue(any("ghost" in e for e in errors))

    def test_a_verdict_outside_the_three_values_is_an_error(self):
        _, errors = self._score({
            "f1": "probably", "f2": "affected",
            "p1": "unaffected", "p2": "unaffected"})
        self.assertTrue(any("f1" in e for e in errors))


class TestCalibrationRecord(_CorpusHarness):
    """採点結果は calibration.json へ。ゲートが開くかは ledger 側が判定する。"""

    def _corpus_and_results(self, root, flag_verdict="affected"):
        self._corpus(root, [_case("f1", "must-flag"), _case("p1", "must-pass")])
        return self._results(root, "judge-model-1",
                             {"f1": flag_verdict, "p1": "unaffected"})

    def _full_corpus_and_results(self, root):
        """ゲートの件数下限を満たすコーパスと、その全件正解の判定結果。"""
        cases = ([_case(f"f{i}", "must-flag") for i in range(ledger.MIN_CASES)]
                 + [_case(f"p{i}", "must-pass")
                    for i in range(ledger.MIN_CASES)])
        self._corpus(root, cases)
        return self._results(root, "judge-model-1", {
            case["id"]: ("affected" if case["expected"] == "must-flag"
                         else "unaffected")
            for case in cases})

    def test_a_clean_run_on_a_full_corpus_opens_the_ledger_gate(self):
        with tempfile.TemporaryDirectory() as root:
            path = self._full_corpus_and_results(root)
            rc, _ = self._run(["--score", path, root])
            self.assertEqual(rc, 0)
            self.assertIsNone(ledger.calibration_reason(
                "judge-model-1", ledger.load_calibration(root)))

    def test_lowering_the_min_cases_check_does_not_open_the_gate(self):
        # 書き込み側の下限は --min-cases で下げられる。下げた検査を通った痩せた
        # コーパスの満点でゲートが開くなら、母数の要件は散文の約束でしかない
        with tempfile.TemporaryDirectory() as root:
            path = self._corpus_and_results(root)
            rc, _ = self._run(["--score", path, "--min-cases", "1", root])
            self.assertEqual(rc, 0)
            reason = ledger.calibration_reason(
                "judge-model-1", ledger.load_calibration(root))
            self.assertIsNotNone(reason)
            self.assertIn(str(ledger.MIN_CASES), reason)

    def test_the_record_keeps_the_case_count_it_was_measured_on(self):
        # 偽陰性 0 の重みは母数で決まる。件数が記録に残らないと、その較正が
        # 48 件で測られたのか 2 件だったのかを後から検証できない
        with tempfile.TemporaryDirectory() as root:
            path = self._corpus_and_results(root)
            self._run(["--score", path, "--min-cases", "1", root])
            entry = ledger.load_calibration(root).entries["judge-model-1"]
            self.assertEqual(entry["must_flag_cases"], 1)
            self.assertEqual(entry["must_pass_cases"], 1)

    def test_a_false_negative_leaves_the_ledger_gate_shut(self):
        # 記録そのものは正直に残す（測った値を隠さない）。門は ledger 側が閉じる
        with tempfile.TemporaryDirectory() as root:
            path = self._corpus_and_results(root, flag_verdict="unaffected")
            rc, _ = self._run(["--score", path, "--min-cases", "1", root])
            self.assertEqual(rc, 0)
            entry = ledger.load_calibration(root).entries["judge-model-1"]
            self.assertEqual(entry["must_flag_fn"], 1)
            self.assertIsNotNone(ledger.calibration_reason(
                "judge-model-1", ledger.load_calibration(root)))

    def test_the_record_binds_to_the_corpus_it_was_measured_on(self):
        with tempfile.TemporaryDirectory() as root:
            path = self._corpus_and_results(root)
            self._run(["--score", path, "--min-cases", "1", root])
            entry = ledger.load_calibration(root).entries["judge-model-1"]
            self.assertEqual(entry["corpus_sha256"], ledger.corpus_sha256(root))
            self.assertTrue(entry["verified"])

    def test_a_second_model_does_not_erase_the_first(self):
        with tempfile.TemporaryDirectory() as root:
            path = self._corpus_and_results(root)
            self._run(["--score", path, "--min-cases", "1", root])
            other = self._results(root, "judge-model-2",
                                  {"f1": "affected", "p1": "unaffected"})
            self._run(["--score", other, "--min-cases", "1", root])
            entries = ledger.load_calibration(root).entries
            self.assertEqual(sorted(entries), ["judge-model-1", "judge-model-2"])

    def test_a_scoring_error_writes_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            self._corpus(root, [_case("f1", "must-flag"),
                                _case("p1", "must-pass")])
            path = self._results(root, "judge-model-1", {"f1": "affected"})
            rc, out = self._run(["--score", path, "--min-cases", "1", root])
            self.assertEqual(rc, 1)
            self.assertIn("p1", out)
            self.assertEqual(ledger.load_calibration(root).entries, {})

    def test_a_corpus_error_blocks_scoring(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/skill-regression/calibration/must_flag/f1.json",
                   "{ broken")
            path = self._results(root, "judge-model-1", {"f1": "affected"})
            rc, _ = self._run(["--score", path, "--min-cases", "1", root])
            self.assertEqual(rc, 1)
            self.assertEqual(ledger.load_calibration(root).entries, {})

    def test_a_results_file_without_a_model_is_refused(self):
        with tempfile.TemporaryDirectory() as root:
            self._corpus(root, [_case("f1", "must-flag"),
                                _case("p1", "must-pass")])
            path = os.path.join(root, "results.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"results": {"f1": "affected", "p1": "unaffected"}}, f)
            rc, out = self._run(["--score", path, "--min-cases", "1", root])
            self.assertEqual(rc, 1)
            self.assertIn("model", out)

    def test_a_missing_results_file_is_refused(self):
        with tempfile.TemporaryDirectory() as root:
            rc, out = self._run(
                ["--score", os.path.join(root, "absent.json"), root])
            self.assertEqual(rc, 1)
            self.assertIn("absent.json", out)


class TestCli(_CorpusHarness):
    def test_validate_reports_a_clean_corpus(self):
        with tempfile.TemporaryDirectory() as root:
            self._corpus(root, [_case("f1", "must-flag"),
                                _case("p1", "must-pass")])
            rc, out = self._run(["--validate", "--min-cases", "1", root])
            self.assertEqual(rc, 0)
            self.assertIn("✓", out)

    def test_validate_fails_on_a_broken_corpus(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/skill-regression/calibration/must_flag/f1.json",
                   "{ broken")
            rc, _ = self._run(["--validate", "--min-cases", "1", root])
            self.assertEqual(rc, 1)

    def test_no_mode_prints_usage(self):
        rc, _ = self._run([])
        self.assertEqual(rc, 2)

    def test_score_without_a_value_is_refused(self):
        rc, out = self._run(["--score"])
        self.assertEqual(rc, 2)
        self.assertIn("--score", out)


class TestShippedCorpus(unittest.TestCase):
    """出荷するコーパス自身への要件（両側 20 件以上・schema 適合）。

    件数が痩せると較正が「たまたま当たった」を見抜けなくなる。仕様の
    暫定ライン（must-flag 偽陰性 0）は母数があって初めて意味を持つ。
    """

    ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "..", "..")

    def test_the_shipped_corpus_passes_its_own_schema(self):
        self.assertEqual(semantic_calibration.validate_corpus(self.ROOT), [])

    def test_each_side_has_at_least_twenty_cases(self):
        cases, _ = semantic_calibration.load_corpus(self.ROOT)
        for side, expected in (("must_flag", "must-flag"),
                               ("must_pass", "must-pass")):
            with self.subTest(side=side):
                count = sum(1 for c in cases.values()
                            if c["expected"] == expected)
                self.assertGreaterEqual(count, 20)

    def test_the_gray_zone_adjudications_are_labelled_and_on_the_pass_side(self):
        # 判断が分かれる編集は維持者の裁定でラベル付けし、その裁定を判定基準文へ
        # 反映する（仕様「グレー帯」）。無印のまま混ぜると再現性を測れない
        cases, _ = semantic_calibration.load_corpus(self.ROOT)
        gray = [c for c in cases.values() if c.get("label") == "gray-zone"]
        self.assertTrue(gray)
        for case in gray:
            self.assertEqual(case["expected"], "must-pass")
            self.assertTrue(case.get("notes"))

    def test_the_must_flag_side_covers_every_mutation_kind(self):
        # 1 種類の変異に偏ると、その種類しか見抜けない判定器が満点を取る
        cases, _ = semantic_calibration.load_corpus(self.ROOT)
        kinds = {c.get("mutation") for c in cases.values()
                 if c["expected"] == "must-flag"}
        self.assertEqual(
            kinds, {"negation", "numeric", "reorder", "deletion"})


if __name__ == "__main__":
    unittest.main()
