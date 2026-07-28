#!/usr/bin/env python3
"""スキルの「挙動面」(behavior surface) と依存グラフの算出（純関数 + 薄い CLI）。

挙動面 = スキルの実行時挙動に影響しうるファイル集合:
  - skills/<name>/ 配下の全ファイル（test_*.py / __pycache__ / *.pyc を除く）
  - そのスキル自身の .md から相対リンクで **1 ホップ**到達するファイル（共有契約を含む）

共有契約を 1 つ編集すると、それを参照する全スキルの挙動が変わりうる。
この逆引き（変更ファイル → 影響スキル）が回帰評価のトリガーになる。

**1 ホップに制限する理由**: 以前は無制限の推移閉包だった。しかし共有契約どうしの
「関連」リンクを辿り続けるため、実行経路が一切交わらないスキルが同じ面に載る。
実例として `issue` は issue → measurement-identity.md → loop-engineering.md →
skill-regression/SKILL.md の 3 ホップで skill-regression に依存し、後者の節を
追記しただけで stale 判定された。スキル境界の外に出た先からは辿らないことで、
skill-authoring の「参照は 1 階層まで」原則と挙動面の定義を一致させる
（skill-interface-audit の SI-S001 が同じ原則を静的に強制している）。

CLI:
  python3 dep_graph.py [root]                # 全スキルの挙動面を JSON で出力
  python3 dep_graph.py --impact FILE... [root]  # 影響スキル名を 1 行 1 件で出力
"""
import json
import os
import re
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


# 委譲プロンプトや手順文の中では、契約が md リンクではなく素のパスで書かれる
# （例: cycle の Phase 2 プロンプト内の `skills/shared/references/tdd-contract.md`、
#   plan の SKILL.md 内の `skills/shared/scripts/checkpoint.py`）。
# md リンクだけを見ると、これらの実依存が挙動面から落ちて偽陰性になる。
_BARE_PATH_RE = re.compile(r"[A-Za-z0-9_./-]+\.(?:md|py|sh)")


def _bare_path_refs(root, rel):
    """rel の本文に素のパスとして現れる実在ファイル(.md/.py/.sh)を root 相対で返す。

    repo root 起点とファイル位置起点の両方で解決を試みる（手順文は前者、
    相対リンク風の記述は後者で書かれる）。実在しないものは無視する。
    test_*.py は面に入れない（テストは挙動面ではない）。
    """
    # 手順文は成果物パス（.agents/artifacts/status.md 等）にも言及する。これらは
    # スキル定義ではなく実行時に書き換わるファイルなので、面に入れると恒久 stale になる。
    # 本スクリプトのスコープどおり skills/ 配下だけを依存として認める。
    abs_root = os.path.abspath(root)
    path = os.path.join(abs_root, rel)
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return set()
    base = os.path.dirname(path)
    found = set()
    for token in _BARE_PATH_RE.findall(text):
        if "{" in token or "*" in token:
            continue
        basename = os.path.basename(token)
        if basename.startswith("test_") and basename.endswith(".py"):
            continue
        for candidate in (os.path.join(abs_root, token), os.path.join(base, token)):
            resolved = os.path.normpath(candidate)
            if not os.path.isfile(resolved):
                continue
            if os.path.commonpath([abs_root, resolved]) != abs_root:
                continue
            found_rel = os.path.relpath(resolved, abs_root).replace(os.sep, "/")
            if found_rel.startswith("skills/"):
                found.add(found_rel)
    return found


def behavior_surface(root, skill):
    """スキル 1 つの挙動面をソート済みリストで返す。SKILL.md が無ければ空。

    起点はスキルディレクトリ内の全 .md（SKILL.md と references/**）。そこから
    1 ホップだけ辿る。スキル外のファイル（共有契約・他スキルの文書）は面に含めるが、
    その先のリンクは辿らない。
    """
    skill_md = os.path.join(root, "skills", skill, "SKILL.md")
    if not os.path.isfile(skill_md):
        return []
    own = _skill_dir_files(root, skill)
    own_md = [rel for rel in own if rel.endswith(".md")]
    surface = set(own)
    surface.update(md_links.closure(root, own_md, max_depth=1))
    for rel in own_md:
        surface.update(_bare_path_refs(root, rel))
    return sorted(rel for rel in surface if rel not in _EXCLUDED_RELS)


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


def normalize_path(path, root=None):
    """パスをリポジトリ相対 POSIX 形式へ正規化する。解決できなければ None。"""
    p = os.path.normpath(path)
    if root and os.path.isabs(p):
        abs_root = os.path.abspath(root)
        if os.path.commonpath([abs_root, p]) != abs_root:
            return None
        p = os.path.relpath(p, abs_root)
    else:
        p = os.path.relpath(p) if os.path.isabs(p) else p
        p = os.path.normpath(p)
    result = p.replace(os.sep, "/")
    if result.startswith("../"):
        return None
    return result


def impacted_skills(graph, changed_paths, root=None):
    """変更ファイル集合に挙動面が交差するスキル名をソートして返す。"""
    changed = set()
    unresolved = []
    for p in changed_paths:
        norm = normalize_path(p, root)
        if norm is None:
            unresolved.append(p)
        else:
            changed.add(norm)
    return sorted(
        skill for skill, surface in graph.items()
        if changed.intersection(surface)
    ), unresolved


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
        skills, unresolved = impacted_skills(graph, changed, root)
        for skill in skills:
            print(skill)
        for p in unresolved:
            print(f"warning: unresolvable path: {p}", file=sys.stderr)
        if unresolved:
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
