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
  python3 ledger.py --remove SKILL [root]
  python3 ledger.py --impact FILE... [root]    # 変更ファイル → 影響スキル
  python3 ledger.py --status [root]
"""
import datetime
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dep_graph  # noqa: E402
import md_structure  # noqa: E402

LEDGER_REL = os.path.join("skills", "skill-regression", "ledger.json")
_MISSING = "MISSING"


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
RESULT_ACCEPTED_WITHOUT_RUN = "accepted-without-run"


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


def make_entry(root, surface, result, verified_date, note=None):
    """台帳エントリを作る。

    result は "pass"（実走して全シナリオ合格）| "accepted-addition"（実走せず承認。
    面への追加のみであることを hash 比較で機械確認済み）| "accepted-prose"
    （実走せず承認。既存 md の散文のみの変更であることを構造フィンガープリントで
    機械確認済み）| "accepted-without-run"（実走せず承認。上記いずれにも機械分類
    できない変更を含む、または比較基準が無い）。

    structural_sha256 は次回照合時の散文のみ判定の比較基準（md のみ）。これを
    持たない旧エントリの変更は常に contract-change へ倒れる。

    note は素の pass だけでは次に回す者へ伝わらない run の性質を残すための欄
    （executor-contract が要求する照会回数、実行者が選んだ経路など）。
    合否には影響しない。
    """
    entry = {
        "surface": surface,
        "file_sha256": file_hashes(root, surface),
        "structural_sha256": structural_hashes(root, surface),
        "surface_sha256": fingerprint(root, surface),
        "result": result,
        "verified": verified_date,
    }
    if note:
        entry["note"] = note
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


def coverage(root, exempt=None):
    """fixture 保有状況を {covered, exempt, uncovered, total} で返す。

    `--check` は fixture を持つスキルだけを見る opt-in ゲートなので、全件合格しても
    「検証されていない領域がどれだけあるか」は表せない。covered と uncovered を
    構造的に区別するのは coverage-ledger 契約と同じ考え方
    （skills/shared/references/coverage-ledger.md）。
    """
    exempt = COVERAGE_EXEMPT if exempt is None else exempt
    skills = _all_skills(root)
    with_fixtures = _fixtures_skills(root)
    covered = skills & with_fixtures
    exempted = {s: exempt[s] for s in sorted(skills & set(exempt)) if s not in covered}
    return {
        "covered": sorted(covered),
        "exempt": exempted,
        "uncovered": sorted(skills - covered - set(exempted)),
        "total": len(skills),
    }


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
        issues.append(("stale", skill, f"[{severity}] " + ", ".join(changed)))
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


def main(argv):
    args = list(argv)

    def _root(rest):
        return rest[0] if rest else os.getcwd()

    if "--check" in args:
        args.remove("--check")
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
        # Red flag の accepted-without-run 偏重チェックが鈍る
        counts = {
            RESULT_PASS: 0,
            RESULT_ACCEPTED_ADDITION: 0,
            RESULT_ACCEPTED_PROSE: 0,
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
            f" / 対象外 {len(cov['exempt'])} / 未保有 {len(cov['uncovered'])} "
            f"/ 全 {cov['total']}）"
        )
        return 0

    if "--coverage" in args:
        args.remove("--coverage")
        strict = "--strict" in args
        if strict:
            args.remove("--strict")
        root = _root(args)
        cov = coverage(root)
        for skill in cov["covered"]:
            print(f"{skill}\tcovered")
        for skill, reason in cov["exempt"].items():
            print(f"{skill}\texempt\t{reason}")
        for skill in cov["uncovered"]:
            print(f"{skill}\tuncovered")
        print(
            f"covered {len(cov['covered'])} / exempt {len(cov['exempt'])} "
            f"/ uncovered {len(cov['uncovered'])} / total {cov['total']}"
        )
        if strict and cov["uncovered"]:
            print(
                f"✗ fixture 未保有 {len(cov['uncovered'])} 件。capture ワークフローで"
                f"資産化するか、COVERAGE_EXEMPT に理由付きで登録すること"
            )
            return 1
        return 0

    if "--update" in args or "--remove" in args:
        mode = "--update" if "--update" in args else "--remove"
        idx = args.index(mode)
        skill = args[idx + 1]
        rest = args[idx + 2:]
        accept = "--accept" in rest
        rest = [a for a in rest if a != "--accept"]
        note = None
        if "--note" in rest:
            note_idx = rest.index("--note")
            note = rest[note_idx + 1]
            rest = rest[:note_idx] + rest[note_idx + 2:]
        root = _root(rest)
        entries = load(root)
        if mode == "--remove":
            if entries.pop(skill, None) is None:
                print(f"✗ 台帳にエントリがない: {skill}")
                return 1
        else:
            if skill not in _fixtures_skills(root):
                print(f"✗ skills/{skill}/fixtures.json が存在しない")
                return 1
            surface = skill_surface(root, skill)
            result = RESULT_PASS
            if accept:
                fixtures_rel = f"skills/{skill}/fixtures.json"
                prev_entry = entries.get(skill, {})
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
            entries[skill] = make_entry(
                root, surface, result,
                datetime.date.today().isoformat(), note=note,
            )
        save(root, entries)
        print(f"✓ ledger 更新: {skill} ({mode})")
        return 0

    if "--impact" in args:
        return dep_graph.main(args)

    if "--status" in args:
        args.remove("--status")
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
