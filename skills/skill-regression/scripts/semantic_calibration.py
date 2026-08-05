#!/usr/bin/env python3
"""semantic triage の判定器を較正する（コーパス検証・採点・記録）。

「影響は解釈次第で機械には測れない」と言った当のものを LLM に判定させる以上、
判定器自身の当てにならなさを先に測る。危険なのは偽陰性（「影響なし」と言ったが
実際は影響があった）方向で、must-flag 側の偽陰性 0 件が自動記録解禁の暫定ライン
である（docs/spec/semantic-triage.md「較正」）。

較正コーパスは両面で作る:

  calibration/must_flag/*.json  挙動が変わることに争いのない編集（偽陰性を測る）
  calibration/must_pass/*.json  影響しないことに争いのない編集（偽陽性を測る）

case schema: {id, expected, before, after, requirements[], mutation?, label?, notes?}

このスクリプトは外部プロセスを起動する API を一切 import しない。判定器はどの
方向にも実行を発火しないという権限境界（仕様「権限の境界」）を、散文の約束では
なく依存関係の不在で守るため。test_ledger.py の canary がソースを走査して退行を
検出するので、名指しの禁止語はこの文でも書かない（canary 自身に引っかかる）。

CLI:
  python3 semantic_calibration.py --validate [--min-cases N] [root]
      コーパスの schema と件数を検査する
  python3 semantic_calibration.py --score RESULTS.json [--min-cases N] [root]
      判定結果を採点し calibration.json へ記録する。
      RESULTS.json は {"model": "<判定モデル識別子>", "results": {case_id: verdict}}
      採点値は正直に記録するだけで、ゲートを開けるかどうかは ledger.py が
      判定する（must_flag_fn == 0 / corpus_sha256 一致 / 片側の件数が下限以上）
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ledger  # noqa: E402

# 片側あたりの最低件数。下限の正本は ledger 側に置く。ゲート（記録を通すか）と
# 検査（コーパスが検査を通るか）が別々の数を持つと、--min-cases で下げた検査を
# 通ったコーパスがゲートでは弾かれる／その逆が起きる
MIN_CASES = ledger.MIN_CASES

CASE_FIELDS = ("id", "expected", "before", "after", "requirements")
EXPECTED_BY_SIDE = {"must_flag": "must-flag", "must_pass": "must-pass"}


def _case_errors(case, side):
    """1 case の schema 違反（無ければ空）。"""
    if not isinstance(case, dict):
        return ["case が JSON オブジェクトでない"]
    missing = [f"必須フィールドがない: {f}" for f in CASE_FIELDS if f not in case]
    if missing:
        return missing
    if case["expected"] not in EXPECTED_BY_SIDE.values():
        return [f"expected が must-flag / must-pass でない: {case['expected']!r}"]
    # ディレクトリと expected の食い違いを通すと、採点の向きが静かに反転する
    if case["expected"] != EXPECTED_BY_SIDE[side]:
        return [f"expected がディレクトリと食い違う: "
                f"{case['expected']}（{side}/ の下に置かれている）"]
    problems = []
    for field in ("id", "before", "after"):
        if not isinstance(case[field], str) or not case[field].strip():
            problems.append(f"{field} が空")
    if case["before"] == case["after"]:
        problems.append("before と after が同一（編集になっていない）")
    requirements = case["requirements"]
    if (not isinstance(requirements, list) or not requirements
            or not all(isinstance(r, str) and r.strip() for r in requirements)):
        problems.append("requirements が非空の文字列リストでない")
    return problems


def load_corpus(root):
    """較正コーパスを ({id: case}, errors) で返す。壊れた case は落とす。"""
    cases, errors, seen = {}, [], {}
    for side in ledger.CALIBRATION_SIDES:
        directory = os.path.join(root, ledger.CALIBRATION_CORPUS_REL, side)
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if not name.endswith(".json"):
                continue
            try:
                with open(os.path.join(directory, name), encoding="utf-8") as f:
                    case = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                errors.append(f"{side}/{name}: JSON として読めない（{exc}）")
                continue
            problems = _case_errors(case, side)
            if problems:
                errors += [f"{side}/{name}: {p}" for p in problems]
                continue
            # id は採点の突き合わせキー。重複すると片方の判定が黙って捨てられる
            if case["id"] in seen:
                errors.append(f"{side}/{name}: id が重複している: "
                              f"{case['id']}（既出: {seen[case['id']]}）")
                continue
            seen[case["id"]] = f"{side}/{name}"
            cases[case["id"]] = case
    return cases, errors


def validate_corpus(root, min_cases=MIN_CASES):
    """schema 違反と件数不足をまとめて返す（合格なら空）。"""
    cases, errors = load_corpus(root)
    for side, expected in EXPECTED_BY_SIDE.items():
        count = sum(1 for case in cases.values() if case["expected"] == expected)
        if count < min_cases:
            errors.append(f"{side}: case が {count} 件しかない"
                          f"（{min_cases} 件以上必要）")
    return errors


def score(cases, results):
    """判定結果を採点して (集計, errors) を返す。

    must-flag 側で unaffected と答えたものだけを偽陰性に数える。unclear は
    「言い切れない」= 人間へ回るので、危険な取りこぼしではない。
    must-pass 側は unaffected 以外すべてを偽陽性に数える — affected でも
    unclear でも安価な記録には至らず、節約効果の目減りとしては同じだから。

    判定の欠落を黙って除外しないのは、1 件だけ判定して満点の較正を作れる
    抜け道を塞ぐため。
    """
    errors = []
    unknown = sorted(set(results) - set(cases))
    if unknown:
        errors.append("コーパスに無い case id の判定がある: " + ", ".join(unknown))
    absent = sorted(set(cases) - set(results))
    if absent:
        errors.append("判定が無い case がある: " + ", ".join(absent))
    false_negatives, false_positives = [], []
    for case_id in sorted(cases):
        verdict = results.get(case_id)
        if verdict is None:
            continue
        if verdict not in ledger.VERDICTS:
            errors.append(f"{case_id}: verdict が 3 値でない: {verdict!r}")
            continue
        if cases[case_id]["expected"] == "must-flag":
            if verdict == ledger.VERDICT_UNAFFECTED:
                false_negatives.append(case_id)
        elif verdict != ledger.VERDICT_UNAFFECTED:
            false_positives.append(case_id)
    scored = {
        "must_flag_fn": len(false_negatives),
        "must_pass_fp": len(false_positives),
        "false_negatives": false_negatives,
        "false_positives": false_positives,
        "cases": len(cases),
    }
    for side, expected in EXPECTED_BY_SIDE.items():
        scored[f"{side}_cases"] = sum(
            1 for case in cases.values() if case["expected"] == expected)
    return scored, errors


def record_calibration(root, model, scored, today=None):
    """採点値を calibration.json へ書く（他モデルの記録は保つ）。

    測った値をそのまま残し、ゲートを開けるかどうかの判断は持たない。
    「合格した較正だけを書く」設計にすると、不合格の測定が台帳から消えて
    「まだ測っていない」と区別が付かなくなる。

    誤り数だけでなく片側ごとの case 数も残す。偽陰性 0 の重みは母数で決まる
    ので、「何件で測った 0 か」が記録に無いと、後から較正の強さを検証できない。
    """
    entries = dict(ledger.load_calibration(root).entries)
    entries[model] = {
        "must_flag_cases": scored["must_flag_cases"],
        "must_flag_fn": scored["must_flag_fn"],
        "must_pass_cases": scored["must_pass_cases"],
        "must_pass_fp": scored["must_pass_fp"],
        "corpus_sha256": ledger.corpus_sha256(root),
        "verified": today or datetime.date.today().isoformat(),
    }
    path = os.path.join(root, ledger.CALIBRATION_REL)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    return entries[model]


def _load_results(path):
    """判定結果ファイルを (model, results) で返す。読めなければ (None, 理由)。"""
    if not os.path.isfile(path):
        return None, f"判定結果ファイルが無い: {path}"
    try:
        with open(path, encoding="utf-8") as f:
            loaded = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        return None, f"判定結果ファイルが読めない: {path}（{exc}）"
    if not isinstance(loaded, dict):
        return None, f"判定結果ファイルが JSON オブジェクトでない: {path}"
    model = loaded.get("model")
    if not isinstance(model, str) or not model.strip():
        return None, ("判定結果ファイルに model がない"
                      "（較正はモデルに固有で、識別子なしでは記録できない）")
    results = loaded.get("results")
    if not isinstance(results, dict):
        return None, "判定結果ファイルの results が case id → verdict の対応表でない"
    return (model, results), None


def _usage(message):
    print(f"✗ {message}")
    print(__doc__)
    return 2


def _stray(tokens):
    return [t for t in tokens if t.startswith("--")]


def main(argv):
    args = list(argv)
    min_cases = MIN_CASES
    if "--min-cases" in args:
        idx = args.index("--min-cases")
        value = ledger._option_value(args, idx)
        if value is None or not value.isdigit():
            return _usage("--min-cases に件数（整数）がない")
        min_cases = int(value)
        args = args[:idx] + args[idx + 2:]

    if "--validate" in args:
        args.remove("--validate")
        stray = _stray(args)
        if stray:
            return _usage(f"解釈できないオプション: {', '.join(stray)}")
        root = args[0] if args else os.getcwd()
        errors = validate_corpus(root, min_cases)
        for error in errors:
            print(f"✗ {error}")
        if errors:
            return 1
        cases, _ = load_corpus(root)
        print(f"✓ 較正コーパス: {len(cases)} case（schema・件数とも適合）")
        return 0

    if "--score" in args:
        idx = args.index("--score")
        results_path = ledger._option_value(args, idx)
        if results_path is None:
            return _usage("--score に判定結果ファイルのパスがない")
        rest = args[:idx] + args[idx + 2:]
        stray = _stray(rest)
        if stray:
            return _usage(f"解釈できないオプション: {', '.join(stray)}")
        root = rest[0] if rest else os.getcwd()
        loaded, error = _load_results(results_path)
        if error:
            print(f"✗ {error}")
            return 1
        model, results = loaded
        errors = validate_corpus(root, min_cases)
        if errors:
            for error in errors:
                print(f"✗ {error}")
            print("✗ コーパスが検査を通らない。較正を記録しない")
            return 1
        cases, _ = load_corpus(root)
        scored, errors = score(cases, results)
        if errors:
            for error in errors:
                print(f"✗ {error}")
            print("✗ 採点の材料が揃わない。較正を記録しない")
            return 1
        entry = record_calibration(root, model, scored)
        print(f"✓ 較正を記録: {model}（{scored['cases']} case / "
              f"must_flag {scored['must_flag_cases']} 件 → fn "
              f"{scored['must_flag_fn']} / must_pass "
              f"{scored['must_pass_cases']} 件 → fp {scored['must_pass_fp']}）")
        if scored["false_negatives"]:
            print(f"  偽陰性: {', '.join(scored['false_negatives'])}")
            print("  must_flag_fn > 0 の間、台帳側は accepted-semantic の記録を"
                  "拒否する（advisor 止まり）")
        if scored["false_positives"]:
            print(f"  偽陽性: {', '.join(scored['false_positives'])}"
                  "（安全側の誤り。節約効果は目減りする）")
        print(f"  corpus_sha256: {entry['corpus_sha256']}")
        return 0

    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
