"""markdown 相対リンクの抽出と推移的クロージャ算出（共有純関数）。

scripts/validate_repo.py のリンク抽出と同じ判定規則を持つ:
アンカーは除去し、URL / 絶対パス / `{var}`・`*` プレースホルダ /
タイムスタンプ始まりの例示ファイル名はチェック対象外とする。

利用側は skills/shared/scripts/secret_detect.py と同様に
`sys.path.insert` でこのディレクトリを追加して import する。
"""
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


def closure(root, start_rel):
    """start_rel から相対 .md リンクで到達できる実在ファイルの推移的クロージャ。

    root 外へ抜けるリンクと実在しないターゲットは辿らない。
    戻り値は root 相対の POSIX パスをソートしたリスト。start が無ければ空。
    """
    root = os.path.abspath(root)
    start = os.path.normpath(os.path.join(root, start_rel))
    if not os.path.isfile(start):
        return []
    seen = set()
    queue = [start]
    while queue:
        path = queue.pop()
        if path in seen:
            continue
        seen.add(path)
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
                queue.append(target)
    return sorted(
        os.path.relpath(p, root).replace(os.sep, "/") for p in seen
    )
