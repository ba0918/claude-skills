#!/usr/bin/env python3
"""semantic triage の判定入力を組み立てる（git 履歴から変更前の内容を復元する）。

判定器に渡すのは「変更前後の差分」なので、前回検証時点の内容を持ってくる必要が
あり、そこだけは git 履歴に頼らざるを得ない。ledger.py は「git 履歴やコミット
範囲に依存せず、前回検証した内容そのものとの hash 比較で決まる」決定性を設計
判断として持っている（stale_severity の docstring）ので、git への依存はこの
スクリプトに隔離し、台帳側の性質を崩さない。

復元は**コミット位置ではなく内容ハッシュ**で行う。台帳は検証イベントを内容で
記録していてコミットとは紐づいていないため、「前回検証の頃のコミット」から
逆算すると、検証後に別経路で履歴が進んだ場合に誤った base を掴む。

復元できなかったファイルは skeleton の該当シナリオへ unclear を事前充填する。
diff を見せられないまま unaffected と言える経路を残すと、判定器の権限が
「見ていないものを安全と宣言する」まで広がってしまう。

CLI:
  python3 semantic_diff.py SKILL [--skeleton FILE] [root]
      判定入力（正準 diff ハッシュ・unified diff・判定ファイル skeleton）を
      標準出力へ出す。--skeleton は skeleton だけを JSON ファイルへも書く。
      判定手順と権限境界は references/semantic-triage.md
"""
import difflib
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ledger  # noqa: E402

# 1 ファイルあたり遡る最大リビジョン数。履歴全体を無制限に走査すると、長い
# 履歴を持つ人気契約で判定入力の組み立てだけが重くなる。上限に達して見つから
# なかった場合は復元不能（= unclear 事前充填）へ倒れるので、安全側で頭打ちする
MAX_REVISIONS = 200

UNRESTORABLE_RATIONALE = (
    "変更前の内容を git 履歴から復元できず、差分を確認できていない"
    "（見ていない差分を unaffected と判定してはならない）"
)


def _git(root, args):
    """git を引数リストで呼ぶ（shell を経由させない）。失敗時は None。"""
    try:
        proc = subprocess.run(
            ["git", "-C", root] + list(args),
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    except OSError:
        return None
    return proc.stdout if proc.returncode == 0 else None


def _revisions(root, rel, limit):
    """rel を触ったコミットを新しい順に（git が無い / repo でないなら空）。"""
    out = _git(root, ["rev-list", f"--max-count={limit}", "HEAD", "--", rel])
    return [] if out is None else out.decode("utf-8", "replace").split()


def restore_base(root, rel, recorded_sha, max_revisions=MAX_REVISIONS):
    """台帳が記録した内容と一致する版を git 履歴から復元する（無ければ None）。

    UTF-8 として読めない版も None を返す。判定器が読むのはテキストの差分で
    あり、読めない内容は「復元できなかった」のと機構上は同じ扱いでよい。
    """
    if recorded_sha == ledger._MISSING:
        return None
    for rev in _revisions(root, rel, max_revisions):
        blob = _git(root, ["show", f"{rev}:{rel}"])
        if blob is None or hashlib.sha256(blob).hexdigest() != recorded_sha:
            continue
        try:
            return blob.decode("utf-8")
        except UnicodeDecodeError:
            return None
    return None


def _current_text(root, rel, current_hashes):
    """変更後の内容（面から外れたファイルは空文字、読めなければ None）。

    after 側を「ディスクに実体があるか」ではなく**現在の面に属しているか**で
    決める。SKILL.md や中間 reference からリンクを外す編集では、ファイルは
    ディスクに残ったまま面から外れる。実体の有無で決めると、その差分は changed に
    名前が挙がるのに diff 本文が 1 バイトも出ず、判定器には「名前だけあって何も
    変わっていない」= unaffected と読める（偽陰性方向）。面から外れたファイルは
    もうスキルの挙動に寄与しないので、全文削除として描くのが正確でもある。

    current_hashes は ledger.file_hashes の出力（面のファイルのみを鍵に持ち、
    実体の無い参照先は MISSING）。面の外と壊れたリンクはどちらも空文字になる。
    """
    if current_hashes.get(rel, ledger._MISSING) == ledger._MISSING:
        return ""
    try:
        with open(os.path.join(root, rel), encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def unified_diff(rel, base, current):
    """1 ファイル分の unified diff（末尾は必ず改行で閉じる）。"""
    body = "".join(difflib.unified_diff(
        base.splitlines(keepends=True), current.splitlines(keepends=True),
        fromfile=f"a/{rel}", tofile=f"b/{rel}"))
    if body and not body.endswith("\n"):
        body += "\n"
    return body


def build_skeleton(skill, diff_sha256, scenario_ids, unclear_ids):
    """判定ファイルの skeleton。空欄の verdict は台帳側で必ず拒否される。

    復元不能分だけは空欄ではなく unclear を完成形で埋める。判定器に「空欄を
    埋める」作業として渡すと、埋める過程で unaffected へ書き換えられてしまう。
    """
    return {
        "skill": skill,
        "diff_sha256": diff_sha256,
        "model": "",
        "scenarios": {
            sid: (
                {"verdict": ledger.VERDICT_UNCLEAR,
                 "rationale": UNRESTORABLE_RATIONALE}
                if sid in unclear_ids
                else {"verdict": "", "rationale": ""}
            )
            for sid in scenario_ids
        },
    }


def build_input(root, skill, entry):
    """判定入力一式を組み立てる。

    差分ファイルの列挙と影響シナリオの解決は、どちらも ledger.py の規則を
    そのまま呼ぶ。判定入力が --check / --impact-scenarios と別の集合を見ると、
    「台帳が再走を要求している範囲」と「判定器が見た範囲」がずれる。
    """
    surface = ledger.skill_surface(root, skill)
    current = ledger.file_hashes(root, surface)
    recorded = entry.get("file_sha256", {})
    severity, changed = ledger.stale_severity(
        recorded, current,
        entry.get("structural_sha256", {}),
        ledger.structural_hashes(root, surface),
        own_prefix=f"skills/{skill}/")
    blocks, unrestorable = [], []
    for rel in changed:
        recorded_sha = recorded.get(rel, ledger._MISSING)
        # 前回の面に無かったファイルは「復元不能」ではない（変更前が存在しない）
        base = "" if recorded_sha == ledger._MISSING else restore_base(
            root, rel, recorded_sha)
        after = _current_text(root, rel, current)
        if base is None or after is None:
            unrestorable.append(rel)
            blocks.append(f"--- {rel}\n({UNRESTORABLE_RATIONALE})\n")
            continue
        blocks.append(unified_diff(rel, base, after))
    scenarios = ledger.load_scenarios(root, skill)
    recorded_scenarios = entry.get("scenarios")
    impacted = ledger.impacted_scenarios(
        skill, surface, scenarios, changed, recorded_scenarios)
    unclear = set(ledger.impacted_scenarios(
        skill, surface, scenarios, unrestorable, recorded_scenarios))
    diff_sha256 = ledger.semantic_diff_sha256(recorded, current)
    return {
        "severity": severity,
        "changed": changed,
        "diff": "".join(blocks),
        "unrestorable": unrestorable,
        "diff_sha256": diff_sha256,
        "scenarios": impacted,
        "total": len(scenarios),
        "skeleton": build_skeleton(skill, diff_sha256, impacted, unclear),
    }


def _usage(message):
    print(f"✗ {message}")
    print(__doc__)
    return 2


def main(argv):
    args = list(argv)
    skeleton_path = None
    if "--skeleton" in args:
        idx = args.index("--skeleton")
        skeleton_path = ledger._option_value(args, idx)
        if skeleton_path is None:
            return _usage("--skeleton に出力先ファイルパスがない")
        args = args[:idx] + args[idx + 2:]
    stray = [a for a in args if a.startswith("--")]
    if stray:
        return _usage(f"解釈できないオプションが残っている: {', '.join(stray)}")
    if not args:
        return _usage("スキル名がない")
    skill = args[0]
    root = args[1] if len(args) > 1 else os.getcwd()
    entry = ledger.load(root).get(skill)
    if entry is None:
        print(f"✗ 台帳にエントリがない: {skill}（semantic triage が見るのは"
              f"「前回検証した内容」との差分なので、比較基準が要る）")
        return 1
    # 比較基準が無い旧エントリでは、差分が「面が丸ごと新しい」に化ける。判定へ
    # 回しても per-scenario 記録が無い以上どのシナリオも記録には至らず、判定 1 回分の
    # 費用だけが出ていく（stale_severity が recorded 空を重い側へ倒すのと同じ理由）
    if not entry.get("file_sha256"):
        print(f"✗ {skill} のエントリに file_sha256 が無く、差分の比較基準が取れない。"
              f"先に run → --update で検証すること")
        return 1
    built = build_input(root, skill, entry)
    if built["severity"] is None:
        print(f"✗ {skill} の挙動面に差分がない（判定するものがない）")
        return 1
    if built["severity"] != ledger.SEVERITY_CHANGE:
        print(f"✗ {skill} の変更は [{built['severity']}] で semantic triage の"
              f"担当帯ではない。機械が安全と証明できる帯なので "
              f"--update {skill} --accept で安価に進めること")
        return 1
    print(f"# semantic triage input: {skill}")
    print(f"diff_sha256: {built['diff_sha256']}")
    print(f"changed files: {', '.join(built['changed'])}")
    print(f"impacted scenarios: {', '.join(built['scenarios'])} "
          f"({len(built['scenarios'])}/{built['total']})")
    if built["unrestorable"]:
        print(f"unrestorable base: {', '.join(built['unrestorable'])}")
    print()
    print("## diff")
    print(built["diff"])
    print("## judgment skeleton")
    print(json.dumps(built["skeleton"], ensure_ascii=False, indent=2))
    if skeleton_path:
        with open(skeleton_path, "w", encoding="utf-8") as f:
            json.dump(built["skeleton"], f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"\n✓ skeleton を書き出した: {skeleton_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
