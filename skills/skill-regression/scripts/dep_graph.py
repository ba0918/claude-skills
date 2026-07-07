#!/usr/bin/env python3
"""スキルの「挙動面」(behavior surface) と依存グラフの算出（純関数 + 薄い CLI）。

挙動面 = スキルの実行時挙動に影響しうるファイル集合:
  - skills/<name>/ 配下の全ファイル（test_*.py / __pycache__ / *.pyc を除く）
  - SKILL.md から相対 .md リンクで到達できる推移閉包（共有契約を含む）

共有契約を 1 つ編集すると、それを参照する全スキルの挙動が変わりうる。
この逆引き（変更ファイル → 影響スキル）が回帰評価のトリガーになる。

CLI:
  python3 dep_graph.py [root]                # 全スキルの挙動面を JSON で出力
  python3 dep_graph.py --impact FILE... [root]  # 影響スキル名を 1 行 1 件で出力
"""
import json
import os
import sys

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "..", "..", "shared", "scripts"),
)
import md_links  # noqa: E402

_EXCLUDED_DIR_NAMES = {"__pycache__"}

# 台帳は「検証の記録」であって挙動ではない。挙動面に含めると
# --update のたびに skill-regression 自身の挙動面が変わり stale が
# 自己再生産される（記録→stale→再検証→記録…のループ）ため除外する。
_EXCLUDED_RELS = {"skills/skill-regression/ledger.json"}


def _skill_dir_files(root, skill):
    """skills/<skill>/ 配下の挙動面ファイル（root 相対 POSIX パス）を列挙する。"""
    base = os.path.join(root, "skills", skill)
    files = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in _EXCLUDED_DIR_NAMES]
        for name in filenames:
            if name.startswith("test_") and name.endswith(".py"):
                continue
            if name.endswith(".pyc"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), root)
            rel = rel.replace(os.sep, "/")
            if rel in _EXCLUDED_RELS:
                continue
            files.append(rel)
    return files


def behavior_surface(root, skill):
    """スキル 1 つの挙動面をソート済みリストで返す。SKILL.md が無ければ空。"""
    skill_md = os.path.join(root, "skills", skill, "SKILL.md")
    if not os.path.isfile(skill_md):
        return []
    surface = set(_skill_dir_files(root, skill))
    surface.update(md_links.closure(root, f"skills/{skill}/SKILL.md"))
    return sorted(surface)


def build_graph(root):
    """{スキル名: 挙動面} を全スキル（shared を除く）について返す。"""
    base = os.path.join(root, "skills")
    graph = {}
    for name in sorted(os.listdir(base)):
        if name == "shared" or not os.path.isdir(os.path.join(base, name)):
            continue
        surface = behavior_surface(root, name)
        if surface:
            graph[name] = surface
    return graph


def impacted_skills(graph, changed_paths):
    """変更ファイル集合に挙動面が交差するスキル名をソートして返す。"""
    changed = {p.replace(os.sep, "/") for p in changed_paths}
    return sorted(
        skill for skill, surface in graph.items()
        if changed.intersection(surface)
    )


def main(argv):
    args = list(argv)
    changed = None
    if "--impact" in args:
        idx = args.index("--impact")
        rest = args[idx + 1:]
        args = args[:idx]
        # 末尾要素が実在ディレクトリなら root、それ以外は変更ファイル
        if rest and os.path.isdir(rest[-1]) and not rest[-1].endswith(".md"):
            args.append(rest[-1])
            rest = rest[:-1]
        changed = rest
    root = args[0] if args else os.getcwd()
    graph = build_graph(root)
    if changed is None:
        print(json.dumps(graph, ensure_ascii=False, indent=2))
    else:
        for skill in impacted_skills(graph, changed):
            print(skill)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
