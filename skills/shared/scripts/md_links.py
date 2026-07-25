"""markdown 相対リンクの抽出と推移的クロージャ算出（共有純関数）。

scripts/validate_repo.py のリンク抽出と同じ判定規則を持つ:
アンカーは除去し、URL / 絶対パス / `{var}`・`*` プレースホルダ /
タイムスタンプ始まりの例示ファイル名はチェック対象外とする。

利用側は skills/shared/scripts/secret_detect.py と同様に
`sys.path.insert` でこのディレクトリを追加して import する。
"""
import collections
import os
import re

_LINK_RE = re.compile(r"\]\(([^)\s]+)\)")
_TIMESTAMP_EXAMPLE = re.compile(r"^\d{8,}")


def extract_md_links(text):
    """markdown テキストから .md リンクターゲットを抽出する（アンカー除去）。"""
    links = []
    for target in _LINK_RE.findall(text):
        target = target.split("#", 1)[0]
        if target.endswith(".md"):
            links.append(target)
    return links


def is_checkable_link(link):
    """実在チェックすべき相対 .md リンクなら True。"""
    if not link.endswith(".md"):
        return False
    if link.startswith(("http://", "https://", "mailto:", "#", "/")):
        return False
    if "{" in link or "*" in link:
        return False
    if _TIMESTAMP_EXAMPLE.match(os.path.basename(link)):
        return False
    return True


def closure(root, start_rel, max_depth=None):
    """start から相対 .md リンクで到達できる実在ファイルのクロージャ。

    start_rel は 1 パスでも、パスの iterable でもよい（複数 start は同時に深さ 0）。
    max_depth は start から辿るホップ数の上限（None なら無制限、1 なら直接リンクまで）。
    root 外へ抜けるリンクと実在しないターゲットは辿らない。
    戻り値は root 相対の POSIX パスをソートしたリスト。start が 1 つも無ければ空。

    深さ制限が要るのは、無制限クロージャが「リンクで繋がってさえいれば挙動依存」
    と見なすため。共有契約から他スキルへの関連リンク 1 本で、実行経路が交わらない
    スキル同士が同じ面に載ってしまう（skill-authoring の「参照は 1 階層まで」原則と
    実装が食い違っていた）。深さは幅優先で数えるので、初到達が最短ホップになる。
    """
    root = os.path.abspath(root)
    starts = [start_rel] if isinstance(start_rel, str) else list(start_rel)
    queue = collections.deque()
    seen = set()
    for rel in starts:
        path = os.path.normpath(os.path.join(root, rel))
        if os.path.isfile(path) and path not in seen:
            seen.add(path)
            queue.append((path, 0))
    while queue:
        path, depth = queue.popleft()
        if max_depth is not None and depth >= max_depth:
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        base = os.path.dirname(path)
        for link in extract_md_links(text):
            if not is_checkable_link(link):
                continue
            target = os.path.normpath(os.path.join(base, link))
            if os.path.commonpath([root, target]) != root:
                continue  # root 外へのリンクは対象外
            if os.path.isfile(target) and target not in seen:
                seen.add(target)
                queue.append((target, depth + 1))
    return sorted(
        os.path.relpath(p, root).replace(os.sep, "/") for p in seen
    )
