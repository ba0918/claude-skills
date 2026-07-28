"""md コードフェンスの共有モジュール。

3 つの md スキャナ（check_language_coverage, check_translation_parity,
check_anchors）が独立にフェンス正規表現とトグル走査を持っていたのを一箇所に
まとめた。フェンス走査は CommonMark 寄りの状態機械で、素朴な ``not in_fence``
トグルの 2 つの欠陥を修正する:

1. ``~~~`` を認識する（check_language_coverage が見落としていた）
2. 開始記号の文字種と長さを記憶し、**同種・同長以上** の行でのみ閉じる。
   これにより ```````` 内の ````` は「長さが足りない」ので閉じとみなさない。
   ``~~~`` 内の ````` も「種類が違う」ので閉じない。
"""

import re

# 開始・終了ともにマッチする正規表現。グループ 1 がフェンス文字の連なり。
FENCE = re.compile(r"^(\s*)((`{3,})|(~{3,}))")


def is_fence_line(line: str) -> tuple[str, int] | None:
    """フェンス行なら (文字種, 長さ) を返す。そうでなければ None。

    文字種は ``"`"`` または ``"~"``。長さはフェンス文字の連続数。
    """
    m = FENCE.match(line)
    if m is None:
        return None
    # グループ 3 がバッククォート、グループ 4 がチルダ
    if m.group(3):
        return ("`", len(m.group(3)))
    return ("~", len(m.group(4)))


def iter_outside_fence(lines: list[str]):
    """フェンス外の行だけを yield する。

    フェンスの開始行・終了行自体は yield しない。

    >>> list(iter_outside_fence(["a", "```", "b", "```", "c"]))
    ['a', 'c']
    """
    fence_char = None
    fence_len = 0
    for line in lines:
        info = is_fence_line(line)
        if fence_char is None:
            # フェンスの外
            if info is not None:
                fence_char, fence_len = info
            else:
                yield line
        else:
            # フェンスの中 — 同種・同長以上で閉じる
            if info is not None and info[0] == fence_char and info[1] >= fence_len:
                fence_char = None
                fence_len = 0
            # フェンス中の行は yield しない


def classify_lines(lines: list[str]):
    """各行を ``"prose"`` / ``"fence_marker"`` / ``"fenced"`` に分類して yield する。

    戻り値は ``(tag, line)`` のペア。

    - ``"prose"``: フェンスの外にある通常行
    - ``"fence_marker"``: フェンスの開始行または終了行
    - ``"fenced"``: フェンスの内側にある行
    """
    fence_char = None
    fence_len = 0
    for line in lines:
        info = is_fence_line(line)
        if fence_char is None:
            if info is not None:
                fence_char, fence_len = info
                yield ("fence_marker", line)
            else:
                yield ("prose", line)
        else:
            if info is not None and info[0] == fence_char and info[1] >= fence_len:
                fence_char = None
                fence_len = 0
                yield ("fence_marker", line)
            else:
                yield ("fenced", line)
