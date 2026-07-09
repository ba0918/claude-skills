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

CLI:
  python3 ledger.py --check [root]             # CI 用。issue があれば exit 1
  python3 ledger.py --update SKILL [--accept] [root]
      fixtures 合格後に台帳を更新（--accept は「実行せず再評価不要と判断」を明示記録）
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


def make_entry(root, surface, result, verified_date):
    """台帳エントリを作る。result は "pass" | "accepted-without-run"。"""
    return {
        "surface": surface,
        "file_sha256": file_hashes(root, surface),
        "surface_sha256": fingerprint(root, surface),
        "result": result,
        "verified": verified_date,
    }


def _fixtures_skills(root):
    base = os.path.join(root, "skills")
    if not os.path.isdir(base):
        return set()
    return {
        name for name in os.listdir(base)
        if os.path.isfile(os.path.join(base, name, "fixtures.json"))
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
        if current == recorded:
            continue
        changed = sorted(
            set(k for k in current if current[k] != recorded.get(k))
            | (set(recorded) - set(current))
        )
        issues.append(("stale", skill, ", ".join(changed)))
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
        print("✓ regression ledger: 全スキル検証済み")
        return 0

    if "--update" in args or "--remove" in args:
        mode = "--update" if "--update" in args else "--remove"
        idx = args.index(mode)
        skill = args[idx + 1]
        rest = args[idx + 2:]
        accept = "--accept" in rest
        rest = [a for a in rest if a != "--accept"]
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
            result = "accepted-without-run" if accept else "pass"
            entries[skill] = make_entry(
                root, skill_surface(root, skill), result,
                datetime.date.today().isoformat(),
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
