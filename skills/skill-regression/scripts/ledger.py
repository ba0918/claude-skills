#!/usr/bin/env python3
"""回帰評価台帳（regression ledger）の照合・更新（純関数 + 薄い CLI）。

台帳 skills/skill-regression/ledger.json は「このスキルの挙動面が
この内容だった時点で、fixtures.json の全シナリオが合格した（または
明示的に再評価不要と判断した）」という検証イベントを記録する。

挙動面が変わったのに台帳が古いままなら CI を落とし、「共有契約を直したら
参照スキルの再検証を忘れる」サイレント回帰を防ぐ。fixtures.json を持つ
スキルだけが対象（opt-in）。

check() が返す issue の種別:
  unverified  fixtures.json はあるが台帳に検証記録がない
  stale       挙動面が前回検証時から変化した（再評価が必要）
  orphan      台帳に記録があるが fixtures.json が消えた（--remove で掃除）

stale には severity が付く。自スキル配下からの面へのファイル追加だけなら
contract-addition、既存 md の変更がすべて散文のみ（構造フィンガープリント一致）
なら prose-change、機械で安全と確認できない変更はすべて contract-change
（迷ったら contract-change 側）。

CLI:
  python3 ledger.py --check [root]             # CI 用。issue があれば exit 1
  python3 ledger.py --coverage [--strict] [root]
      fixture 保有率を covered / exempt / uncovered で計上（--strict で uncovered を exit 1）
  python3 ledger.py --update SKILL [--accept] [--note TEXT] [root]
      fixtures 合格後に台帳を更新（--accept は「実行せず再評価不要と判断」を明示記録。
      severity が contract-addition / prose-change で前回が実走 pass なら
      accepted-addition / accepted-prose として自動で区別記録する。
      --note は run の性質（照会回数・実行者が通った経路など）の申し送り）
  python3 ledger.py --update SKILL --partial [--scenario ID]... [--note TEXT]
                    [--semantic JUDGMENT.json] [root]
      部分再走。--scenario で指名した id を「今回実走して合格」として記録し、
      残りは前回結果の持ち越しを試みる。持ち越せないものがあれば更新ごと拒否
      して列挙する（= それらも再走が必要）。詳細は references/partial-rerun.md
      --semantic は semantic triage の判定ファイル。影響ありシナリオのうち
      unaffected 判定の分を accepted-semantic として記録する（形式・diff ハッシュ
      束縛・較正ゲートを全件検査し、1 つでも欠ければ記録ごと拒否）。
      詳細は references/semantic-triage.md
  python3 ledger.py --seed-scenarios SKILL [root]
      移行用ワンショット。stale でないエントリへ per-scenario 記録を埋める
  python3 ledger.py --remove SKILL [root]
  python3 ledger.py --impact FILE... [root]    # 変更ファイル → 影響スキル
  python3 ledger.py --impact-scenarios FILE... [root]
      変更ファイル → 影響シナリオ（skill<TAB>scenario_id）。fixture の exercises
      宣言を使って再走をシナリオ単位へ絞る。宣言なしのシナリオは常に影響側
  python3 ledger.py --status [root]
"""
import collections
import datetime
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dep_graph  # noqa: E402
import fixture_setup  # noqa: E402
import md_structure  # noqa: E402

LEDGER_REL = os.path.join("skills", "skill-regression", "ledger.json")
_MISSING = "MISSING"

# シナリオ内容ハッシュの正本は fixture_setup 側。ここで再実装すると、rerun ガードと
# 持ち越し判定が別々の規則で動き「台帳は持ち越せると言うのに rerun は再構築を
# 要求する」食い違いが生まれる
scenario_sha256 = fixture_setup.scenario_sha256


def _file_sha256(root, rel):
    path = os.path.join(root, rel)
    if not os.path.isfile(path):
        return _MISSING
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def file_hashes(root, files):
    """{root 相対パス: sha256 hex}（実在しないファイルは MISSING 番兵）。"""
    return {rel: _file_sha256(root, rel) for rel in files}


def fingerprint(root, files):
    """ファイル集合の内容フィンガープリント。順序非依存・決定的。"""
    hashes = file_hashes(root, files)
    h = hashlib.sha256()
    for rel in sorted(hashes):
        h.update(f"{rel}\n{hashes[rel]}\n".encode("utf-8"))
    return h.hexdigest()


def skill_surface(root, skill):
    """スキルの挙動面（fixtures.json 自身も skills/<skill>/ 配下として含む）。"""
    return dep_graph.behavior_surface(root, skill)


SEVERITY_CHANGE = "contract-change"
SEVERITY_ADDITION = "contract-addition"
SEVERITY_PROSE = "prose-change"

RESULT_PASS = "pass"
RESULT_ACCEPTED_ADDITION = "accepted-addition"
RESULT_ACCEPTED_PROSE = "accepted-prose"
RESULT_ACCEPTED_SEMANTIC = "accepted-semantic"
RESULT_ACCEPTED_WITHOUT_RUN = "accepted-without-run"

# accepted-semantic を積める土台。実走 pass か、実走 pass まで遡れる
# accepted-semantic の連鎖だけを認める（semantic_block_reason に理由）
SEMANTIC_FOUNDATION_RESULTS = frozenset(
    {RESULT_PASS, RESULT_ACCEPTED_SEMANTIC})

# semantic triage（docs/spec/semantic-triage.md）の 3 値判定。連続スコアを採らない
# 理由は仕様側にある。ここで確率的な中間値を持たせないことが、較正対象を
# 「unaffected 判定の誤り率」1 点に絞れる土台になっている。
VERDICT_UNAFFECTED = "unaffected"
VERDICT_UNCLEAR = "unclear"
VERDICT_AFFECTED = "affected"
VERDICTS = (VERDICT_UNAFFECTED, VERDICT_UNCLEAR, VERDICT_AFFECTED)

CALIBRATION_REL = os.path.join("skills", "skill-regression", "calibration.json")
CALIBRATION_CORPUS_REL = os.path.join("skills", "skill-regression", "calibration")
CALIBRATION_SIDES = ("must_flag", "must_pass")

# 片側あたりの最低 case 数。痩せたコーパスでは「たまたま当たった」を見抜けず、
# 偽陰性 0 という解禁ラインが母数の裏付けを失う。書き込み側（semantic_calibration.py
# の --min-cases）は運用の都合で下げられるので、ゲートの側にも同じ下限を持たせて
# おかないと「2 件で測った満点」が記録経路を開けてしまう
MIN_CASES = 20

# 較正ゲートの判定材料。「登録済みの較正記録」と「今のコーパスの内容・件数」が
# 揃って初めてゲートを開けられる。一部だけを引数で運ぶと、コーパスを差し替えた
# まま古い較正で記録を通す経路や、母数を検査しないまま通す経路が開く
CalibrationGate = collections.namedtuple(
    "CalibrationGate", ["entries", "corpus_sha256", "corpus_counts"])


def structural_hashes(root, files):
    """md ファイルの構造フィンガープリント {root 相対パス: sha256 hex}。

    散文のみ変更（prose-change）判定の比較基準。非 md には散文の概念が無いので
    対象外（記録が無い = 判定不能 = 重い側、が stale_severity 側の規則）。
    読めないファイル（不在・非 UTF-8）も同じ理由で黙って外す。
    """
    out = {}
    for rel in files:
        if not rel.endswith(".md"):
            continue
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except UnicodeDecodeError:
            continue
        out[rel] = md_structure.structural_fingerprint(text)
    return out


def stale_severity(recorded, current, recorded_struct=None, current_struct=None,
                   own_prefix=None):
    """stale の重さを (severity, 差分ファイル一覧) で返す。差分なしなら (None, [])。

    recorded / current はどちらも {root 相対パス: sha256（不在は MISSING）}。
    recorded_struct / current_struct は md の構造フィンガープリント
    （structural_hashes の出力）、own_prefix は自スキルのパス接頭辞
    （例 "skills/a/"）。3 つとも省略可で、省略はその判定材料が無いことを意味し、
    常に重い側へ倒れる。

    分類は 3 値。面にファイルが増えただけなら contract-addition、既存 md の変更が
    すべて散文のみ（構造フィンガープリント一致）なら prose-change、それ以外は
    contract-change。迷ったら重い側という fail-safe を全経路で効かせる:
    追加ファイルの hash が MISSING（実体のない参照先＝壊れたリンク）、recorded が
    空（file_sha256 を持たない旧エントリ＝比較基準が無い）、own_prefix 指定時の
    自スキル外からの追加（素パス参照の実体が後から作られて面へ入る未検証新規内容 —
    #182 で Why not 見送り、#222 で導入）、構造記録の無いファイルの変更、は
    いずれも contract-change として扱う。

    判定材料を hash 差分だけに閉じているのは、git 履歴やコミット範囲に依存せず
    「前回検証した内容そのもの」との比較で決まる決定性を優先したため。
    """
    added = sorted(set(current) - set(recorded))
    removed = sorted(set(recorded) - set(current))
    modified = sorted(
        rel for rel in set(recorded) & set(current)
        if recorded[rel] != current[rel]
    )
    changed = sorted(added + removed + modified)
    if not changed:
        return None, []
    dangling = [rel for rel in added if current[rel] == _MISSING]
    foreign = [] if own_prefix is None else [
        rel for rel in added if not rel.startswith(own_prefix)
    ]
    if not recorded or removed or dangling or foreign:
        return SEVERITY_CHANGE, changed
    if modified:
        recorded_struct = recorded_struct or {}
        current_struct = current_struct or {}
        prose_only = all(
            rel in recorded_struct and rel in current_struct
            and recorded_struct[rel] == current_struct[rel]
            for rel in modified
        )
        if prose_only:
            return SEVERITY_PROSE, changed
        return SEVERITY_CHANGE, changed
    return SEVERITY_ADDITION, changed


def accept_result(recorded, current, prev_result, recorded_struct=None,
                  current_struct=None, own_prefix=None):
    """--accept で記録する result を、severity と前回 result の両方から決める。

    addition-only または prose-only と機械的に確認でき、**かつ前回が実走 pass** の
    承認だけを "accepted-addition" / "accepted-prose" にする。前回が accepted-* の
    台帳に軽量承認を積めてしまうと、一度も実走しないまま accepted-without-run の
    計上から恒久的に逃げ続けられ、Red flag が用をなさなくなる。どちらの分類も
    「直前に実走で確かめた内容からの安全な差分」を意味するので、土台が実走で
    なければ成立しない。

    比較基準の無いエントリを弾く判断は stale_severity に持たせてあり、ここでは
    再実装しない（--check の表示と記録値が別々の規則で動くと食い違うため）。
    """
    # 差分ゼロ（severity is None）も "accepted-without-run" 側へ落ちる。何も追加して
    # いない承認が軽量分類を名乗るのは意味論的に嘘であり、stale ですらない
    # エントリへの --accept は運用上ほぼ通らない経路なので、重い側で据え置く
    severity, _ = stale_severity(
        recorded, current, recorded_struct, current_struct, own_prefix)
    if prev_result == RESULT_PASS:
        if severity == SEVERITY_ADDITION:
            return RESULT_ACCEPTED_ADDITION
        if severity == SEVERITY_PROSE:
            return RESULT_ACCEPTED_PROSE
    return RESULT_ACCEPTED_WITHOUT_RUN


def semantic_diff_sha256(recorded_hashes, current_hashes):
    """判定対象の差分を指す正準ハッシュ。順序非依存・決定的で git に依存しない。

    recorded / current はどちらも {root 相対パス: sha256（不在は MISSING）}。
    変わったファイルだけを sorted して `rel\\n{recorded}\\n{current}\\n` を連結する。
    無変更のファイルを含めないのは、判定に無関係な面の増減でハッシュが動くと
    「同じ diff を見て出した判定」が別物として拒否されるため。

    台帳エントリと現在のファイル状態だけから決まるので、判定を発行する側
    （semantic_diff.py）と検証する側（ここ）が git 履歴の解釈を共有せずに
    同じ値へ到達できる。ledger.py が git を呼ばない設計の要でもある。
    """
    h = hashlib.sha256()
    for rel in sorted(set(recorded_hashes) | set(current_hashes)):
        before = recorded_hashes.get(rel, _MISSING)
        after = current_hashes.get(rel, _MISSING)
        if before == after:
            continue
        h.update(f"{rel}\n{before}\n{after}\n".encode("utf-8"))
    return h.hexdigest()


def corpus_files(root):
    """較正コーパスの case ファイル（root 相対パス）。"""
    out = []
    for side in CALIBRATION_SIDES:
        directory = os.path.join(root, CALIBRATION_CORPUS_REL, side)
        if not os.path.isdir(directory):
            continue
        out += [
            os.path.join(CALIBRATION_CORPUS_REL, side, name)
            for name in os.listdir(directory) if name.endswith(".json")
        ]
    return sorted(out)


def corpus_sha256(root):
    """較正コーパス全体の内容フィンガープリント（コーパス改訂の検知に使う）。"""
    return fingerprint(root, corpus_files(root))


def corpus_counts(root):
    """較正コーパスの case ファイル数を {side: 件数} で返す。"""
    counts = {side: 0 for side in CALIBRATION_SIDES}
    for rel in corpus_files(root):
        side = os.path.basename(os.path.dirname(rel))
        if side in counts:
            counts[side] += 1
    return counts


def load_calibration(root):
    """calibration.json の記録と、現在のコーパスのフィンガープリントを読む。

    読めない・壊れている・不在は「一度も較正していない」（entries 空）へ倒す。
    較正の不在が意味するのは advisor 止まりであって検査系の停止ではないので、
    例外で --check ごと落とす経路にはしない。
    """
    path = os.path.join(root, CALIBRATION_REL)
    entries = {}
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                loaded = json.load(f)
        except (json.JSONDecodeError, OSError):
            loaded = None
        if isinstance(loaded, dict):
            entries = loaded
    return CalibrationGate(entries=entries, corpus_sha256=corpus_sha256(root),
                           corpus_counts=corpus_counts(root))


def calibration_reason(model, calibration):
    """判定モデルが較正ゲートを通せない理由（通せるなら None）。

    段階 3 の解禁・モデル変更 = 再較正・コーパス改訂 = 再較正・母数の確保の
    4 つを、散文の約束ではなくこの 1 か所の機械検査で守る（A7, A8）。危険なのは
    偽陰性方向なので、誤り率の通過条件は must_flag_fn == 0 だけに置き、偽陽性
    （must_pass_fp）は記録するが門にはしない — 安全側の誤りで節約効果が減るだけ。

    件数を今のコーパスで数えるのは、記録された件数の自己申告より確かだから。
    corpus_sha256 の一致は「較正時とコーパスが同一」を意味し、採点側は全 case の
    判定を要求する（semantic_calibration.score）ので、今の件数が下限を満たせば
    その較正が下限以上の母数で測られたことも同時に決まる。
    """
    entry = (calibration.entries or {}).get(model)
    if not isinstance(entry, dict):
        return (f"判定モデル {model} の較正記録がない — advisor 止まり"
                f"（semantic_calibration.py で較正すること）")
    fn = entry.get("must_flag_fn")
    if isinstance(fn, bool) or not isinstance(fn, int):
        return f"判定モデル {model} の較正記録の must_flag_fn が整数でない"
    if fn != 0:
        return f"判定モデル {model} は較正未達（must_flag_fn {fn} > 0）— advisor 止まり"
    if entry.get("corpus_sha256") != calibration.corpus_sha256:
        return (f"判定モデル {model} の較正は別版の corpus に対するもの — "
                f"コーパスが改訂されている。再較正すること")
    # 件数の検査は corpus の同一性を確かめた後に置く。先に置くと、較正が
    # 一度も無い状態でも「コーパスが薄い」と報告してしまい、advisor 止まりの
    # 本当の理由（未較正）が operator から見えなくなる
    counts = calibration.corpus_counts or {}
    thin = [f"{side} {counts.get(side, 0)} 件"
            for side in CALIBRATION_SIDES if counts.get(side, 0) < MIN_CASES]
    if thin:
        return (f"較正コーパスが片側 {MIN_CASES} 件に満たない"
                f"（{' / '.join(thin)}）— 母数が薄いと偽陰性 0 を偶然と"
                f"区別できない。case を足して再較正すること")
    return None


_JUDGMENT_FIELDS = ("skill", "diff_sha256", "model", "scenarios")


def validate_judgment(judgment, skill, recorded_hashes, current_hashes,
                      calibration, known_ids=None):
    """判定ファイルを検証し、拒否理由（人間が読める 1 行）を返す。合格なら None。

    検査は全件で、1 つでも欠ければ記録ごと拒否する（C1, C2）。判定の中身
    （どの verdict か）は見ない — ここは「この判定ファイルを台帳の材料として
    信用してよいか」だけを決め、どの verdict なら記録できるかは partial_update
    側の規則（unaffected のみ）が持つ。

    diff ハッシュの一致要求が塞ぐのは、別の変更に対して出した古い判定を
    使い回す事故である。較正ゲートが塞ぐのは、誤り率を測っていないモデルの
    判定が記録経路へ入ることである。

    型の検査を「必須フィールドがある」で済ませないのは、判定ファイルが人手でも
    書けるため。model が対応表や配列だと較正記録の参照が TypeError の traceback
    になり、拒否理由の 1 行という idiom（load_judgment に理由）から外れる。

    known_ids は fixtures.json に実在するシナリオ id の集合。実在しない id への
    判定を黙って捨てると、typo が「semantic 判定がない」という別の欠落として
    しか現れず、operator に打ち間違いの手がかりが残らない（同じ理由で
    semantic_calibration.score もコーパスに無い case id を拒否している）。
    None は照合材料を持たない呼び出し（判定入力の形だけを見る検査）専用で、
    台帳を書く経路は必ず現在の fixtures.json の id を渡す。
    """
    if not isinstance(judgment, dict):
        return "判定ファイルが JSON オブジェクトでない"
    missing = [field for field in _JUDGMENT_FIELDS if field not in judgment]
    if missing:
        return "判定ファイルに必須フィールドがない: " + ", ".join(missing)
    if judgment["skill"] != skill:
        return (f"判定ファイルの skill が対象と違う: {judgment['skill']}"
                f"（対象は {skill}）")
    if judgment["diff_sha256"] != semantic_diff_sha256(
            recorded_hashes, current_hashes):
        return ("判定ファイルの diff_sha256 が現在の差分と一致しない"
                "（別の変更に対する判定の使い回し）")
    model = judgment["model"]
    if not isinstance(model, str) or not model.strip():
        return ("判定ファイルの model が空でない文字列でない"
                "（較正はモデルに固有で、識別子なしでは記録できない）")
    scenarios = judgment["scenarios"]
    if not isinstance(scenarios, dict):
        return "判定ファイルの scenarios が「シナリオ id → 判定」の対応表でない"
    if known_ids is not None:
        unknown = sorted(set(scenarios) - set(known_ids))
        if unknown:
            return ("fixtures.json に無いシナリオ id の判定がある: "
                    + ", ".join(unknown))
    for sid in sorted(scenarios):
        verdict = scenarios[sid]
        if not isinstance(verdict, dict):
            return f"{sid}: 判定が verdict / rationale を持つ対応表でない"
        if verdict.get("verdict") not in VERDICTS:
            return (f"{sid}: verdict が 3 値でない: {verdict.get('verdict')!r}"
                    f"（{' / '.join(VERDICTS)} のみ）")
        rationale = verdict.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            return f"{sid}: rationale が空（根拠のない判定は監査できない）"
    return calibration_reason(model, calibration)


def carryover_dependencies(skill, scenario, surface):
    """持ち越し判定でハッシュ一致を要求するファイル集合。

    fixtures.json はここに含めない。含めると他シナリオの編集や exercises 宣言の
    追加だけで全シナリオの持ち越しが壊れ、シナリオ差分で見る impact 側の規則と
    食い違う。シナリオ定義の変化は scenario_sha256 の比較が受け持つ。
    """
    fixtures_rel = f"skills/{skill}/fixtures.json"
    deps = declared_dependencies(scenario, set(surface))
    if deps is None:
        return set(surface) - {fixtures_rel}
    return deps | {f"skills/{skill}/SKILL.md"}


def carryover_reason(skill, scenario, surface, recorded_hashes, current_hashes,
                     recorded_scenarios):
    """前回の合格を持ち越せない理由を返す（持ち越せるなら None）。

    有効性は直前エントリとの**帰納**で決まる。直前エントリでこのシナリオは
    有効だった（実走したか、同じ規則で有効性を機械確認して持ち越した）ので、
    シナリオ定義が不変で、依存ファイルが 1 バイトも動いていなければ、その
    合格は今も有効である。per-scenario にファイルハッシュを保存しなくても
    これが成り立つのが本設計の要。

    材料が欠けるケースはすべて持ち越し不可（安全側）。前回エントリに記録が
    無い、前回時点で依存の実体が無かった（MISSING = 壊れた参照）、依存が
    前回の面に無かった、のいずれも帰納の土台にならない。
    """
    recorded = (recorded_scenarios or {}).get(scenario["id"])
    if not recorded:
        return "前回エントリに per-scenario 記録がない（--seed-scenarios で移行）"
    if recorded.get("scenario_sha256") != scenario_sha256(scenario):
        return "シナリオ定義が前回検証時から変わった"
    unbacked, drifted = [], []
    for rel in sorted(carryover_dependencies(skill, scenario, surface)):
        previous = recorded_hashes.get(rel)
        if previous is None or previous == _MISSING:
            unbacked.append(rel)
        elif previous != current_hashes.get(rel):
            drifted.append(rel)
    if unbacked:
        return "前回検証時に実体の無い依存がある: " + ", ".join(unbacked)
    if drifted:
        return "依存ファイルが変わった: " + ", ".join(drifted)
    return None


def full_scenarios_record(root, skill, result, verified_date):
    """現在の fixtures.json の全シナリオを同一の result / 検証日で記録する。"""
    return {
        scenario["id"]: {
            "scenario_sha256": scenario_sha256(scenario),
            "result": result,
            "verified": verified_date,
        }
        for scenario in load_scenarios(root, skill)
    }


def accepted_scenarios_record(root, skill, result, prev_entry, today):
    """--accept 用の per-scenario 記録。result は承認値、検証日は据え置く。

    per-scenario の verified は「そのシナリオを最後に実走で確かめた日」であり、
    references/partial-rerun.md は run の新しさをここから読めと指示している
    （持ち越したシナリオが古い日付を保つのはそのため）。1 本も走らせていない
    --accept が今日で塗り替えると、実走記録と承認記録が日付から区別できなくなる。

    前回記録が無いシナリオは前回エントリの skill レベル検証日へ、それも無ければ
    today へ落とす。材料が無いときに古い日付を捏造しないための fail-honest な段階。
    """
    previous = (prev_entry or {}).get("scenarios") or {}
    fallback = (prev_entry or {}).get("verified") or today
    return {
        scenario["id"]: {
            "scenario_sha256": scenario_sha256(scenario),
            "result": result,
            "verified": previous.get(scenario["id"], {}).get("verified") or fallback,
        }
        for scenario in load_scenarios(root, skill)
    }


def carried_note(prev_entry, note):
    """新エントリが引き継ぐ申し送り（スロットは 1 つ）。

    直前の note があればそれを、無ければ直前が引き継いでいた分をそのまま次へ渡す。
    エントリを作り直す更新はすべてこれを通す — 部分更新だけが申し送りを守ると、
    定例の --accept 1 回で実走証拠の由来が台帳から消える。
    """
    prev_entry = prev_entry or {}
    carried = prev_entry.get("note") or prev_entry.get("carried_note")
    return None if carried == note else carried


def skill_result(scenario_records):
    """per-scenario 記録から skill レベルの result を決める。

    実走していないシナリオが 1 つでも混ざる限り pass を名乗らせない。全件が
    実走 pass（持ち越しはその有効性を機械確認したもの）のときだけ pass。

    実走 pass と accepted-semantic だけで構成されるなら accepted-semantic。
    判定器の確度（較正済みの確率的判断）は機械の形状証明より下・人間の目視
    accept より上でも下でもなく**別種**なので、他の accepted と畳まずに独立の
    段を持たせる。判定器より確度の説明が付かない記録が 1 つでも混ざれば、
    従来どおり accepted-without-run まで落ちる。
    """
    results = {rec.get("result") for rec in scenario_records.values()}
    if results == {RESULT_PASS}:
        return RESULT_PASS
    if results and results <= {RESULT_PASS, RESULT_ACCEPTED_SEMANTIC}:
        return RESULT_ACCEPTED_SEMANTIC
    return RESULT_ACCEPTED_WITHOUT_RUN


def semantic_block_reason(verdict, recorded, scenario):
    """影響ありシナリオを accepted-semantic として記録できない理由（可なら None）。

    記録を許すのは unaffected 判定だけで（C3）、かつシナリオ定義が前回検証時から
    不変であることを要求する。合否基準そのものが動いたシナリオは判定器の管轄外
    — 判定器が見ているのは「この差分が要件の充足を変えうるか」であって、
    要件自体が別物になったかどうかは実走でしか確かめられない。

    加えて前回記録の result が実走 pass か accepted-semantic であることを要求する
    （accept_result が軽量承認へ課しているのと同じ「土台は実走」の要求）。判定器の
    言い分は「前回確かめた振る舞いをこの差分は変えない」であって、前回に何も
    確かめていなければ引き継ぐ土台が存在しない。

    記録そのものが無いケースは scenario_sha256 の比較より先に見る。空の記録を
    比較へ流すと必ず不一致になり、「シナリオ定義が変わった = 実走が必要」という
    高価な処方が出るが、実際の欠落は per-scenario 記録であって処方は無料の
    --seed-scenarios 移行である。同じ更新の中で carryover_reason は正しい文言を
    出しているので、順序を揃えないと 1 回の実行が 2 つの診断を並べることになる。
    """
    value = (verdict or {}).get("verdict")
    if value is None:
        return "semantic 判定がない"
    if value != VERDICT_UNAFFECTED:
        return (f"semantic 判定は {value}（記録できるのは {VERDICT_UNAFFECTED} "
                f"のみ。実走するか人間が判断すること）")
    if not recorded:
        return "前回エントリに per-scenario 記録がない（--seed-scenarios で移行）"
    if (recorded or {}).get("scenario_sha256") != scenario_sha256(scenario):
        return "シナリオ定義が前回検証時から変わった（合否基準の変更は実走でのみ確かめられる）"
    prev_result = (recorded or {}).get("result")
    # accepted-addition / accepted-prose を土台に許さないのは、skill_result が
    # その 2 つを含む記録集合を accepted-without-run へ落としているため。判定を
    # 重ねて accepted-semantic へ書き換えられると、機械が下げた段を判定器が
    # 無条件に押し戻す洗浄経路になる。accepted-without-run は一度も実走して
    # いない記録そのもので、判定の前提（前回確かめた振る舞い）が存在しない。
    if prev_result not in SEMANTIC_FOUNDATION_RESULTS:
        return (f"前回記録が {prev_result or '無い'}（accepted-semantic を積めるのは "
                f"{' / '.join(sorted(SEMANTIC_FOUNDATION_RESULTS))} の上だけ。"
                f"実走して土台を作ること）")
    return None


def load_judgment(path):
    """判定ファイルを読む。(判定, エラー理由) のどちらか一方だけが埋まる。

    読めない judgment を例外で落とすと、利用者には traceback だけが見えて
    「何を直せば通るのか」が読めない。拒否理由の idiom（✗ 1 行）へ揃える。
    """
    if not os.path.isfile(path):
        return None, f"判定ファイルが無い: {path}"
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f), None
    except json.JSONDecodeError as exc:
        return None, f"判定ファイルが JSON として読めない: {path}（{exc}）"
    except OSError as exc:
        return None, f"判定ファイルを開けない: {path}（{exc}）"


def make_entry(root, surface, result, verified_date, note=None, scenarios=None,
               carried_note=None):
    """台帳エントリを作る。

    result は "pass"（実走して全シナリオ合格）| "accepted-addition"（実走せず承認。
    面への追加のみであることを hash 比較で機械確認済み）| "accepted-prose"
    （実走せず承認。既存 md の散文のみの変更であることを構造フィンガープリントで
    機械確認済み）| "accepted-without-run"（実走せず承認。上記いずれにも機械分類
    できない変更を含む、または比較基準が無い）。

    structural_sha256 は次回照合時の散文のみ判定の比較基準（md のみ）。これを
    持たない旧エントリの変更は常に contract-change へ倒れる。

    scenarios は per-scenario の {scenario_sha256, result, verified}。部分再走
    （--partial）の持ち越し判定がこれを土台に帰納する。省略時はキーごと落とす
    ので、記録を持たない旧エントリと同じ扱いになる（= 全シナリオ再走が必要）。

    note は素の pass だけでは次に回す者へ伝わらない run の性質を残すための欄
    （executor-contract が要求する照会回数、実行者が選んだ経路など）。
    合否には影響しない。

    carried_note は直前エントリの note を引き継ぐ欄。エントリを作り直す更新で
    前任の申し送りを黙って捨てると、実走証拠の性質（誰がどの経路を通ったか）が
    台帳から消え、持ち越し記録だけが残って由来が読めなくなる。スロットは 1 つ
    だけで、直近 1 世代の note しか保たない（連鎖して伸び続けさせない）。

    accepted-semantic 記録の由来（どのモデルが何を根拠に）は、エントリではなく
    scenarios の各記録が持つ。理由は partial_update の該当箇所に書いた。
    """
    entry = {
        "surface": surface,
        "file_sha256": file_hashes(root, surface),
        "structural_sha256": structural_hashes(root, surface),
        "surface_sha256": fingerprint(root, surface),
        "result": result,
        "verified": verified_date,
    }
    if scenarios:
        entry["scenarios"] = scenarios
    if note:
        entry["note"] = note
    if carried_note:
        entry["carried_note"] = carried_note
    return entry


# fixture による挙動検証の対象外。理由必須。免除はスキル側ではなくここに置く
# （スキルディレクトリを触るだけで計上から消せないようにするため — validate_repo.py の
# 各 EXEMPT と同じ idiom）。「まだ書いていない」は免除理由ではなく uncovered である。
COVERAGE_EXEMPT = {
    "shared": "スキルではなく共有契約ライブラリ。単独で起動される挙動を持たない",
    "migrate-cycles-to-plans":
        "旧レイアウトからの一回限りの移行スキル。移行完了後に削除する予定で、"
        "資産化しても再実行されない",
}

# 意図的に static 検証（skill-interface-audit + structural sha + trigger-eval）へ
# 留めるスキル（#244 裁定）。exempt（挙動検証の概念が無い）とも uncovered
# （まだ書いていない）とも別の階層で、理由必須。fixture を得たら behavioral 昇格 =
# ここから外す（取り残しはテストが機械検出する）。behavioral 予定のまま未着手の
# スキル（parallel-cycle）はここに載せず uncovered に残す — 「意図的」の看板で
# 欠落を隠さないため。
COVERAGE_STATIC_ONLY = {
    "artifacts": "store 管理の薄い入口。機構は artifact_store 実装側が担う",
    "attack-review": "read-only 分析。出力が自由形式の報告で fixture 判定に馴染まない",
    "codebase-review": "read-only 分析。出力が自由形式の報告で fixture 判定に馴染まない",
    "design-generate": "デザイン系。成果物検証は design-validate ゲート側が担う",
    "design-lint": "デザイン系。機械判定は lint 側にあり本文は入口の分岐のみ",
    "design-scaffold": "デザイン系。生成物の整合は design-validate ゲート側が担う",
    "design-validate": "検証ゲート自身。判定は機械 lint と rubric 側にある",
    "doc-audit": "docs 整合スキル。判定は機械チェッカ側にある",
    "doc-check": "docs 整合スキル。判定は機械チェッカ側にある",
    "empirical-prompt-tuning": "メタ評価ハーネス。挙動は計測運用そのもので検証される",
    "generate-review-rules": "read-only 分析。出力が自由形式で fixture 判定に馴染まない",
    "goal-decomposition": "ループ配線の型検査スキル。static 検証で担保",
    "goal-loop": "収束ループ機構。長時間実走が前提で fixture 実走の経済性に合わない",
    "ledger": "人間との裁定セッションが本体で、非対話 fixture では構造的に測れない",
    "loop-triage": "ループ配線の型検査スキル。static 検証で担保",
    "mockup-diff": "デザイン系。視覚差分の検証は視覚テスト側が担う",
    "review-deps": "read-only 分析。出力が自由形式の報告で fixture 判定に馴染まない",
    "review-testing": "read-only 分析。出力が自由形式の報告で fixture 判定に馴染まない",
    "skill-improve": "メタ評価ハーネス。挙動は計測運用そのもので検証される",
    "skill-interface-audit": "static 検証の実施側。自身を fixture で測る循環になる",
    "skill-regression": "回帰基盤自身。機構は scripts の unit テストで固定済み",
    "spec-verify": "契約抽出・PBT 生成系。機構は clause lint と PBT 側で固定される",
    "trigger-eval": "メタ評価ハーネス。挙動は計測運用そのもので検証される",
}


def _all_skills(root):
    """skills/ 配下の全スキル名（SKILL.md を持つディレクトリ）。"""
    base = os.path.join(root, "skills")
    if not os.path.isdir(base):
        return set()
    return {
        name for name in os.listdir(base)
        if os.path.isfile(os.path.join(base, name, "SKILL.md"))
    }


def _fixtures_skills(root):
    base = os.path.join(root, "skills")
    if not os.path.isdir(base):
        return set()
    return {
        name for name in os.listdir(base)
        if os.path.isfile(os.path.join(base, name, "fixtures.json"))
    }


def coverage(root, exempt=None, static_only=None):
    """fixture 保有状況を {covered, exempt, static_only, uncovered, total} で返す。

    `--check` は fixture を持つスキルだけを見る opt-in ゲートなので、全件合格しても
    「検証されていない領域がどれだけあるか」は表せない。covered と uncovered を
    構造的に区別するのは coverage-ledger 契約と同じ考え方
    （skills/shared/references/coverage-ledger.md）。static_only は「意図的に
    static 検証へ留める」宣言で、uncovered（まだ書いていない）と区別して計上する。
    """
    exempt = COVERAGE_EXEMPT if exempt is None else exempt
    static_only = COVERAGE_STATIC_ONLY if static_only is None else static_only
    skills = _all_skills(root)
    with_fixtures = _fixtures_skills(root)
    covered = skills & with_fixtures
    exempted = {s: exempt[s] for s in sorted(skills & set(exempt)) if s not in covered}
    static = {
        s: static_only[s] for s in sorted(skills & set(static_only))
        if s not in covered and s not in exempted
    }
    return {
        "covered": sorted(covered),
        "exempt": exempted,
        "static_only": static,
        "uncovered": sorted(skills - covered - set(exempted) - set(static)),
        "total": len(skills),
    }


def load_scenarios(root, skill):
    """skills/<skill>/fixtures.json の scenarios を返す（読めなければ空）。"""
    path = os.path.join(root, "skills", skill, "fixtures.json")
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            fixture = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    scenarios = fixture.get("scenarios")
    if not isinstance(scenarios, list):
        return []
    return [s for s in scenarios if isinstance(s, dict) and s.get("id")]


def declared_dependencies(scenario, surface):
    """シナリオが踏むと主張するファイル集合。宣言なし・宣言不正なら None。

    None は「主張が無い＝どの変更でも影響しうる」という安全側の意味。宣言は
    完全主張（ここに挙げたファイルと SKILL.md 以外は踏まない）なので、面に
    実在しないパスが 1 つでも混ざれば主張全体を信用しない — typo や参照先の
    移動が「踏まないから再走不要」という誤った持ち越しを生むのを防ぐ。
    """
    declared = scenario.get("exercises")
    if not isinstance(declared, list):
        return None
    if any(path not in surface for path in declared):
        return None
    return set(declared)


def changed_scenarios(scenarios, recorded_scenarios):
    """fixtures.json の変更のうち、内容が動いた（または新規の）シナリオ id。"""
    if not recorded_scenarios:
        # 突き合わせ基準が無い（per-scenario 記録を持たない旧エントリ）。
        # 「変わっていない」と断じる根拠もないので全件
        return {s["id"] for s in scenarios}
    return {
        s["id"] for s in scenarios
        if recorded_scenarios.get(s["id"], {}).get("scenario_sha256")
        != scenario_sha256(s)
    }


def impacted_scenarios(skill, surface, scenarios, changed,
                       recorded_scenarios=None):
    """変更ファイル集合 → 影響を受けるシナリオ id（ソート済み）。

    `changed` はこのスキルに関係すると呼び出し側が判断済みの root 相対パス。
    判定規則はすべて安全側優先で、材料が足りない場合は必ず全シナリオへ倒す:

    - `skills/<skill>/SKILL.md` は全シナリオが必ず読む暗黙の依存 → 全件
    - 現在の面に無いパス（＝面から消えたファイル）は現在の宣言と突き合わせ
      ようがない → 全件
    - `skills/<skill>/fixtures.json` はシナリオ差分（内容ハッシュ比較）
    - それ以外の面ファイル f は、f を宣言するシナリオと、宣言を持たない
      （または宣言が不正な）シナリオ
    """
    surface = set(surface)
    changed = set(changed)
    ids = sorted(s["id"] for s in scenarios)
    if not changed:
        return []
    skill_md = f"skills/{skill}/SKILL.md"
    fixtures_rel = f"skills/{skill}/fixtures.json"
    others = changed - {skill_md, fixtures_rel}
    if skill_md in changed or (others - surface):
        return ids
    impacted = set()
    if others:
        for scenario in scenarios:
            deps = declared_dependencies(scenario, surface)
            if deps is None or (others & deps):
                impacted.add(scenario["id"])
    if fixtures_rel in changed:
        impacted |= changed_scenarios(scenarios, recorded_scenarios)
    return sorted(impacted)


def check(root, entries):
    """台帳を照合し (kind, skill, detail) の一覧を返す。空なら合格。"""
    issues = []
    with_fixtures = _fixtures_skills(root)
    for skill in sorted(with_fixtures - set(entries)):
        issues.append((
            "unverified", skill,
            "fixtures.json はあるが検証記録がない（skill-regression run 後に --update）",
        ))
    for skill in sorted(entries):
        entry = entries[skill]
        if skill not in with_fixtures:
            issues.append((
                "orphan", skill,
                "fixtures.json が存在しない（--remove で台帳から削除）",
            ))
            continue
        current_surface = skill_surface(root, skill)
        current = file_hashes(root, current_surface)
        recorded = entry.get("file_sha256", {})
        severity, changed = stale_severity(
            recorded, current,
            entry.get("structural_sha256", {}),
            structural_hashes(root, current_surface),
            own_prefix=f"skills/{skill}/",
        )
        if severity is None:
            continue
        detail = f"[{severity}] " + ", ".join(changed)
        # 再走の規模を stale 行そのものに出す。合否判定は不変（stale は update
        # されるまで stale）で、これは「何本払えば済むか」を示す triage 情報
        scenarios = load_scenarios(root, skill)
        if scenarios:
            hit = impacted_scenarios(
                skill, current_surface, scenarios, changed,
                entry.get("scenarios"))
            label = ("all" if len(hit) == len(scenarios)
                     else ",".join(hit) or "none")
            detail += f" → scenarios: {label} ({len(hit)}/{len(scenarios)})"
        issues.append(("stale", skill, detail))
    return issues


def load(root):
    path = os.path.join(root, LEDGER_REL)
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(root, entries):
    path = os.path.join(root, LEDGER_REL)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def _summarize_changed(changed, limit=3):
    """拒否理由へ添える変更ファイル名（先頭 limit 件 + 残数）。

    「面の変更が影響する」だけでは、どのファイルが再走を呼んだのかを見るのに
    --impact-scenarios を別途叩き直す必要がある。原因を理由行に同梱する。
    """
    names = sorted(changed)
    if not names:
        return "（変更ファイル不明）"
    head = ", ".join(names[:limit])
    return head if len(names) <= limit else f"{head} … ほか {len(names) - limit} 件"


def partial_update(root, entries, skill, ran_ids, note=None, today=None,
                   judgment=None):
    """実走したシナリオを記録し、残りを持ち越して台帳を進める。

    持ち越せないシナリオが 1 つでもあれば更新ごと拒否して列挙する。部分的に
    書き込むと「台帳のどこまでが今も有効か」が読めなくなり、台帳が保証する
    ものが「全シナリオ合格」から曖昧になるため。

    影響側の規則（impacted_scenarios）を先に通し、影響ありと出たシナリオが
    ran_ids に無ければ持ち越し判定を待たずに拒否する。持ち越し規則だけで
    判定すると、依存集合の走査が**現在の面**を起点にしているため、面から
    消えたファイルはどのシナリオの依存にも現れず全件が持ち越されてしまう
    （check() は同じ状態を「scenarios: all」と報告する）。影響と持ち越しを
    別々の材料で動かさず、partial_update を影響規則の消費者にすることで
    「片方が全件再走を要求する状態で、もう片方が実走ゼロの更新を通す」
    食い違いを構造的に閉じる。

    judgment（--semantic）は semantic triage の判定ファイル。影響ありシナリオの
    うち unaffected 判定の分だけを accepted-semantic として記録する第 3 の経路
    で、ここでも同じ消費者の位置に置く。判定器が持つ権限はこの記録 1 点だけで、
    unclear / affected は従来どおり block へ落ちる（実走か人間判断）。
    """
    scenarios = load_scenarios(root, skill)
    if not scenarios:
        print(f"✗ skills/{skill}/fixtures.json にシナリオがない")
        return 1
    unknown = sorted(set(ran_ids) - {s["id"] for s in scenarios})
    if unknown:
        print(f"✗ fixtures.json に無いシナリオ id: {', '.join(unknown)}")
        return 1
    today = today or datetime.date.today().isoformat()
    entry = entries.get(skill, {})
    surface = skill_surface(root, skill)
    current = file_hashes(root, surface)
    recorded_scenarios = entry.get("scenarios") or {}
    _, changed = stale_severity(
        entry.get("file_sha256", {}), current,
        entry.get("structural_sha256", {}), structural_hashes(root, surface),
        own_prefix=f"skills/{skill}/")
    impacted = set(impacted_scenarios(
        skill, surface, scenarios, changed, recorded_scenarios))
    verdicts = {}
    if judgment is not None:
        # severity が contract-change 帯かどうかはここでは見ない。帯のゲートは
        # 判定入力を組む semantic_diff.py 側にあり、二重化すると「実走した分＋
        # 判定で進める分」を混ぜた部分更新が prose-change 帯で丸ごと拒否され、
        # 実走記録を捨てて --accept へ倒すしかなくなる。手書きの判定ファイルで
        # 軽い帯を判定経路へ通せてしまうが、誤用の向きは安全側 — 機械が形状で
        # 証明する accepted-prose / accepted-addition より弱い accepted-semantic が
        # 付くだけで、実走を要求される範囲は広がりこそすれ狭まらない。
        reason = validate_judgment(
            judgment, skill, entry.get("file_sha256", {}), current,
            load_calibration(root), {s["id"] for s in scenarios})
        if reason:
            print(f"✗ {reason}")
            return 1
        verdicts = judgment["scenarios"]
    # 今回の判定で進めた分。持ち越された過去の accepted-semantic とは区別する
    # （集計行が「今回いくら値切れたか」を示すため）
    records, blocked, semantic_ids = {}, [], []
    for scenario in scenarios:
        sid = scenario["id"]
        if sid in ran_ids:
            records[sid] = {
                "scenario_sha256": scenario_sha256(scenario),
                "result": RESULT_PASS,
                "verified": today,
            }
            continue
        if sid in impacted:
            recorded = recorded_scenarios.get(sid) or {}
            gap = semantic_block_reason(verdicts.get(sid), recorded, scenario)
            if judgment is not None and gap is None:
                records[sid] = {
                    "scenario_sha256": scenario_sha256(scenario),
                    "result": RESULT_ACCEPTED_SEMANTIC,
                    # 実走していないので検証日は据え置く。accepted_scenarios_record
                    # と同じ fail-honest 規則で、判定で進めた記録が実走記録と
                    # 日付から区別できなくなるのを防ぐ
                    "verified": (recorded.get("verified")
                                 or entry.get("verified") or today),
                    # 由来はエントリ単位ではなく記録単位で持つ。判定で進めた記録は
                    # 次の更新で持ち越されうるが、そのときエントリには「今回の判定」が
                    # 存在しない。エントリ単位に置くと、持ち越しのたびに由来が
                    # 落ちるか、無い判定から欄を埋めることになる（dict のコピーで
                    # 運ばれる記録側に置けば、持ち越しは何もしなくても由来を保つ）
                    "semantic": {
                        "model": judgment["model"],
                        "diff_sha256": judgment["diff_sha256"],
                        "verdict": VERDICT_UNAFFECTED,
                        "rationale": verdicts[sid]["rationale"],
                    },
                }
                semantic_ids.append(sid)
                continue
            reason = ("面の変更が影響する（--check / --impact-scenarios と同じ規則）: "
                      + _summarize_changed(changed))
            if judgment is not None:
                reason += f" / {gap}"
        else:
            reason = carryover_reason(
                skill, scenario, surface, entry.get("file_sha256", {}), current,
                recorded_scenarios)
        if reason:
            blocked.append((sid, reason))
        else:
            records[sid] = dict(recorded_scenarios[sid])
    if blocked:
        for sid, reason in blocked:
            print(f"✗ {sid}: {reason}")
        print(f"✗ {len(blocked)} 件は持ち越せない。実走して --scenario で指名するか、"
              f"--partial を外して全シナリオ実走の --update にすること")
        return 1
    entries[skill] = make_entry(
        root, surface, skill_result(records), today, note=note,
        scenarios=records, carried_note=carried_note(entry, note))
    save(root, entries)
    summary = (f"実走 {len(ran_ids)} / "
               f"持ち越し {len(records) - len(ran_ids) - len(semantic_ids)}")
    if semantic_ids:
        summary += f" / semantic {len(semantic_ids)}"
    print(f"✓ ledger 更新: {skill} (--partial: {summary})")
    return 0


def seed_scenarios(root, entries, skill):
    """記録を持たない旧エントリへ per-scenario 記録を埋める移行用ワンショット。

    skill レベルのエントリが「この面で全シナリオ合格（または明示的な承認）」を
    保証しているので、面が前回検証時と一致している限り、その保証を各シナリオへ
    分配するのは健全。検証イベントではないので検証日は動かさない。
    """
    entry = entries.get(skill)
    if entry is None:
        print(f"✗ 台帳にエントリがない: {skill}")
        return 1
    if entry.get("scenarios"):
        print(f"✗ {skill} には既に per-scenario 記録がある。--seed-scenarios は"
              f"記録を持たない旧エントリ専用で、上書きを許すと実走していない"
              f"シナリオ記録を skill レベルの result で塗り替えられる")
        return 1
    scenarios = load_scenarios(root, skill)
    if not scenarios:
        print(f"✗ skills/{skill}/fixtures.json にシナリオがない")
        return 1
    surface = skill_surface(root, skill)
    severity, changed = stale_severity(
        entry.get("file_sha256", {}), file_hashes(root, surface),
        entry.get("structural_sha256", {}), structural_hashes(root, surface),
        own_prefix=f"skills/{skill}/")
    if severity is not None:
        print(f"✗ {skill} は stale [{severity}]: {', '.join(changed)}")
        print("  シードの前提は「面が前回検証時のまま」であること。"
              "先に run → --update で検証すること")
        return 1
    entry["scenarios"] = full_scenarios_record(
        root, skill, entry.get("result", RESULT_ACCEPTED_WITHOUT_RUN),
        entry.get("verified", ""))
    save(root, entries)
    print(f"✓ per-scenario 記録をシード: {skill}"
          f"（{len(entry['scenarios'])} シナリオ / 検証日は据え置き）")
    return 0


def impact_scenarios_cli(root, changed_paths):
    """変更ファイル → `skill<TAB>scenario_id` 行。"""
    graph = dep_graph.build_graph(root)
    skills, unresolved = dep_graph.impacted_skills(graph, changed_paths, root)
    normalized = {dep_graph.normalize_path(p, root) for p in changed_paths}
    normalized.discard(None)
    entries = load(root)
    with_fixtures = _fixtures_skills(root)
    # 依存グラフは**現在の**面しか知らないので、削除されたファイルはどのスキルも
    # 選ばない。台帳が記録した前回の面からも引き当てないと、削除が影響ゼロに
    # 見えたまま rc 0 で何も出力されない（check() は同じ状態を全件再走と報告する）
    recorded_hits = {
        skill for skill, entry in entries.items()
        if skill in with_fixtures and normalized & set(entry.get("file_sha256", {}))
    }
    for skill in sorted(set(skills) | recorded_hits):
        if skill not in with_fixtures:
            print(f"note: {skill} は fixtures.json を持たない（再走の対象外）",
                  file=sys.stderr)
            continue
        entry = entries.get(skill, {})
        surface = graph.get(skill, [])
        # 面から消えたファイルも「このスキルに関係する変更」として渡す。
        # 落とすと削除が影響ゼロに見える（impacted_scenarios 側で全件へ倒る）
        relevant = normalized & (
            set(surface) | set(entry.get("file_sha256", {})))
        for sid in impacted_scenarios(
                skill, surface, load_scenarios(root, skill), relevant,
                entry.get("scenarios")):
            print(f"{skill}\t{sid}")
    for p in unresolved:
        print(f"warning: unresolvable path: {p}", file=sys.stderr)
    return 2 if unresolved else 0


def _usage(message):
    """引数の欠落を usage 付きで報告する（exit 2 = 引数エラー）。

    値を伴うオプションの取りこぼしを素の IndexError で落とすと、利用者には
    traceback だけが見えてどの引数が足りないのか読めない。
    """
    print(f"✗ {message}")
    print(__doc__)
    return 2


def _option_value(args, idx):
    """args[idx] のオプションが取る値。欠落（末尾・次も別オプション）なら None。"""
    if idx + 1 >= len(args):
        return None
    value = args[idx + 1]
    return None if value.startswith("--") else value


def _stray_options(tokens):
    """モードが読み終えた後に残った `--` 始まりトークン（root パスは残ってよい）。

    オプションは位置依存で読むので、モード指定より前に置かれた既知フラグは
    黙って捨てられる。捨てられた --partial / --scenario は「全シナリオを実走して
    合格した」という偽の per-scenario 記録を書き込み、以後の持ち越し帰納が
    その上に積まれる。未知トークン（typo）が root 解決で落ちるのと同じ扱いにする。
    """
    return [t for t in tokens if t.startswith("--")]


def main(argv):
    args = list(argv)

    def _root(rest):
        return rest[0] if rest else os.getcwd()

    def _stray(tokens, mode):
        stray = _stray_options(tokens)
        if not stray:
            return None
        return _usage(
            f"解釈できないオプションが残っている: {', '.join(stray)}\n"
            f"  オプションは対象指定（{mode} …）より後ろに書くこと。"
            f"前に置くと黙って捨てられる"
        )

    if "--check" in args:
        args.remove("--check")
        rc = _stray(args, "--check")
        if rc is not None:
            return rc
        root = _root(args)
        issues = check(root, load(root))
        for kind, skill, detail in issues:
            print(f"[{kind}] {skill}: {detail}")
        if issues:
            hint = "skills/skill-regression/SKILL.md の run ワークフローで再評価"
            print(f"✗ {len(issues)} 件。{hint}してから ledger.py --update すること")
            return 1
        # 合格表示に必ず母数を添える。fixture を持つスキルだけを見るゲートなので、
        # 「全スキル検証済み」と書くと未検証領域が検証済みに見える（実際に誤読を招いた）。
        cov = coverage(root)
        entries = load(root)
        # accepted-addition を別建てで数える。畳んで表示すると「機械が安全側と
        # 確認した承認」が「人間が重い変更を承知で通した承認」に紛れ、
        # Red flag の accepted-without-run 偏重チェックが鈍る。
        # accepted-semantic も同じ理由で独立カウント（C4）— こちらは
        # 「判定器に寄りかかりすぎている」という別種の危険信号を運ぶ
        counts = {
            RESULT_PASS: 0,
            RESULT_ACCEPTED_ADDITION: 0,
            RESULT_ACCEPTED_PROSE: 0,
            RESULT_ACCEPTED_SEMANTIC: 0,
            RESULT_ACCEPTED_WITHOUT_RUN: 0,
        }
        for entry in entries.values():
            result = entry.get("result")
            if result in counts:
                counts[result] += 1
        breakdown = " / ".join(f"{name} {n}" for name, n in counts.items())
        print(
            f"✓ regression ledger: fixture 保有 {len(cov['covered'])} スキルすべて検証済み"
            f"（{breakdown}"
            f" / 対象外 {len(cov['exempt'])} / static-only {len(cov['static_only'])}"
            f" / 未保有 {len(cov['uncovered'])} "
            f"/ 全 {cov['total']}）"
        )
        return 0

    if "--coverage" in args:
        args.remove("--coverage")
        strict = "--strict" in args
        if strict:
            args.remove("--strict")
        rc = _stray(args, "--coverage")
        if rc is not None:
            return rc
        root = _root(args)
        cov = coverage(root)
        for skill in cov["covered"]:
            print(f"{skill}\tcovered")
        for skill, reason in cov["exempt"].items():
            print(f"{skill}\texempt\t{reason}")
        for skill, reason in cov["static_only"].items():
            print(f"{skill}\tstatic-only\t{reason}")
        for skill in cov["uncovered"]:
            print(f"{skill}\tuncovered")
        print(
            f"covered {len(cov['covered'])} / exempt {len(cov['exempt'])} "
            f"/ static-only {len(cov['static_only'])} "
            f"/ uncovered {len(cov['uncovered'])} / total {cov['total']}"
        )
        if strict and cov["uncovered"]:
            print(
                f"✗ fixture 未保有 {len(cov['uncovered'])} 件。capture ワークフローで"
                f"資産化するか、COVERAGE_STATIC_ONLY / COVERAGE_EXEMPT に理由付きで"
                f"登録すること"
            )
            return 1
        return 0

    if "--seed-scenarios" in args:
        idx = args.index("--seed-scenarios")
        skill = _option_value(args, idx)
        if skill is None:
            return _usage("--seed-scenarios にスキル名がない")
        rest = args[:idx] + args[idx + 2:]
        rc = _stray(rest, "--seed-scenarios SKILL")
        if rc is not None:
            return rc
        root = _root(args[idx + 2:])
        return seed_scenarios(root, load(root), skill)

    if "--update" in args or "--remove" in args:
        mode = "--update" if "--update" in args else "--remove"
        idx = args.index(mode)
        skill = _option_value(args, idx)
        if skill is None:
            return _usage(f"{mode} にスキル名がない")
        rest = args[idx + 2:]
        accept = "--accept" in rest
        partial = "--partial" in rest
        rest = [a for a in rest if a not in ("--accept", "--partial")]
        ran_ids = set()
        while "--scenario" in rest:
            sidx = rest.index("--scenario")
            value = _option_value(rest, sidx)
            if value is None:
                return _usage("--scenario にシナリオ id がない")
            ran_ids.add(value)
            rest = rest[:sidx] + rest[sidx + 2:]
        note = None
        if "--note" in rest:
            note_idx = rest.index("--note")
            note = _option_value(rest, note_idx)
            if note is None:
                return _usage("--note に本文がない")
            rest = rest[:note_idx] + rest[note_idx + 2:]
        semantic_path = None
        if "--semantic" in rest:
            sem_idx = rest.index("--semantic")
            semantic_path = _option_value(rest, sem_idx)
            if semantic_path is None:
                return _usage("--semantic に判定ファイルのパスがない")
            rest = rest[:sem_idx] + rest[sem_idx + 2:]
        rc = _stray(args[:idx] + rest, f"{mode} SKILL")
        if rc is not None:
            return rc
        root = _root(rest)
        entries = load(root)
        if semantic_path is not None:
            if mode == "--remove":
                print("✗ --semantic は --update --partial 専用で、--remove では"
                      "指定できない（判定は記録を進めるための材料で、"
                      "エントリの削除には使わない）")
                return 1
            if accept:
                print("✗ --semantic は --update --partial 専用で、--accept とは"
                      "併用できない（判定器による記録と人間の承認が混ざると "
                      "result の意味が読めなくなる）")
                return 1
            if not partial:
                print("✗ --semantic は --partial と併せて指定すること"
                      "（記録できるのは影響ありシナリオのうち unaffected 判定の分だけ）")
                return 1
        if partial:
            if mode == "--remove" or accept:
                print("✗ --partial は --update 専用で、--accept とは併用できない"
                      "（承認と実走記録が混ざると result の意味が読めなくなる）")
                return 1
            if skill not in _fixtures_skills(root):
                print(f"✗ skills/{skill}/fixtures.json が存在しない")
                return 1
            judgment = None
            if semantic_path is not None:
                judgment, error = load_judgment(semantic_path)
                if error:
                    print(f"✗ {error}")
                    return 1
            return partial_update(root, entries, skill, ran_ids, note=note,
                                  judgment=judgment)
        if ran_ids:
            print("✗ --scenario は --partial と併せて指定すること")
            return 1
        if mode == "--remove":
            if entries.pop(skill, None) is None:
                print(f"✗ 台帳にエントリがない: {skill}")
                return 1
        else:
            if skill not in _fixtures_skills(root):
                print(f"✗ skills/{skill}/fixtures.json が存在しない")
                return 1
            surface = skill_surface(root, skill)
            prev_entry = entries.get(skill, {})
            result = RESULT_PASS
            if accept:
                fixtures_rel = f"skills/{skill}/fixtures.json"
                prev = prev_entry.get("file_sha256", {})
                prev_hash = prev.get(fixtures_rel)
                curr_hash = _file_sha256(root, fixtures_rel)
                if prev_hash is not None and prev_hash != curr_hash:
                    print(
                        f"✗ skills/{skill}/fixtures.json が前回検証時から変更されている。"
                        f"合否基準の変更は実走で検証すること（--accept を外して run → --update）"
                    )
                    return 1
                result = accept_result(
                    prev, file_hashes(root, surface), prev_entry.get("result"),
                    prev_entry.get("structural_sha256", {}),
                    structural_hashes(root, surface),
                    own_prefix=f"skills/{skill}/")
            today = datetime.date.today().isoformat()
            scenarios = (
                accepted_scenarios_record(root, skill, result, prev_entry, today)
                if accept
                else full_scenarios_record(root, skill, result, today)
            )
            entries[skill] = make_entry(
                root, surface, result, today, note=note, scenarios=scenarios,
                carried_note=carried_note(prev_entry, note),
            )
        save(root, entries)
        print(f"✓ ledger 更新: {skill} ({mode})")
        return 0

    if "--impact-scenarios" in args:
        idx = args.index("--impact-scenarios")
        rest = args[idx + 1:]
        root = os.getcwd()
        if rest and os.path.isdir(rest[-1]) and not rest[-1].endswith(".md"):
            root, rest = rest[-1], rest[:-1]
        # 変更ファイル 0 件で黙って rc 0 を返すと、「再走すべきシナリオが無い」と
        # 区別が付かない。呼び出し側の引数組み立てミスが影響ゼロに化ける
        if not rest:
            return _usage("--impact-scenarios に変更ファイルが 1 つも無い")
        # フラグ風トークンを変更ファイルとして消費すると、誤配置フラグが
        # 「影響ゼロ」の顔で rc 0 になる（他モードの誤配置ガードと同じ穴）
        rc = _stray(rest, "--impact-scenarios FILE...")
        if rc is not None:
            return rc
        return impact_scenarios_cli(root, rest)

    if "--impact" in args:
        return dep_graph.main(args)

    if "--status" in args:
        args.remove("--status")
        rc = _stray(args, "--status")
        if rc is not None:
            return rc
        root = _root(args)
        entries = load(root)
        issues = {s: k for k, s, _ in check(root, entries)}
        tracked = sorted(_fixtures_skills(root) | set(entries))
        if not tracked:
            print("追跡対象なし（fixtures.json を持つスキルがない）")
            return 0
        for skill in tracked:
            state = issues.get(skill, "verified")
            entry = entries.get(skill, {})
            when = entry.get("verified", "-")
            result = entry.get("result", "-")
            print(f"{skill}\t{state}\t{result}\t{when}")
        return 0

    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
