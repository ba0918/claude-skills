#!/usr/bin/env python3
"""md の構造フィンガープリント算出（純関数）。

散文のみ変更（prose-only）の機械判定に使う。md テキストから機械パーストークンを
出現順に抽出し、その列の sha256 をフィンガープリントとする。2 版のフィンガー
プリントが一致すれば、変わったのは散文だけだと言える。

誤判定の向きは非対称で、抽出しすぎ（散文をトークン扱い）は重い側
（contract-change）へ倒れるだけだが、抽出漏れは挙動変更を散文と誤認させ
軽量承認レールに乗せてしまう。そこで構文の deny-list（トークン構文を列挙し
残りを散文とみなす）ではなく **allow-list** を採る: 散文と認めるのはプレーンな
地の文の行だけで、構造構文の兆候（行頭マーカー・インデント・バッククォート・
角括弧・パイプ・HTML タグ風・setext 下線）を 1 つでも含む行は行全体を
トークン化する。未知の・変種の md 構文はデフォルトで構造側に落ちるため、
個別構文の抽出漏れが起きない（PR #224 の敵対レビューで deny-list 実装に
リスト項目・setext 見出し・先頭パイプなし表・タブインデント・HTML・
多重バッククォート・4 連フェンスの偽陰性が実証されたことによる設計反転）。
"""
import hashlib
import re

# 行内にあれば地の文と認めない兆候: インラインコード、リンク・参照（角括弧全般。
# shortcut reference はプレーン角括弧と区別できないため両方拾う）、表セル区切り、
# HTML タグ・コメント風（< の直後が英字 / '/' / '!' のときだけ。比較演算の
# 「a < b」は空白が挟まるため拾わない）
_INLINE_STRUCTURE_RE = re.compile(r"`|\[|\||<[A-Za-z!/]")

# 行頭のリストマーカー（ordered / unordered）。リスト項目は指示そのものが
# 書かれる場所なので散文と認めない
_LIST_RE = re.compile(r"^ {0,3}(?:[-*+]|\d{1,9}[.)])(?:\s|$)")

# setext 見出しの下線 / thematic break。= か - だけの行
_SETEXT_RE = re.compile(r"^ {0,3}(=+|-+)\s*$")

# コードフェンスの開始。CommonMark に合わせ 3 連以上の ` または ~
_FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def _is_prose(line):
    """プレーンな地の文の行か。True の行だけがフィンガープリントに影響しない。"""
    if line.startswith("\t") or line.startswith("    "):
        return False  # インデントコード相当
    stripped = line.strip()
    if not stripped:
        return True  # 空行は段落区切りで、構造情報を持たない
    if stripped[0] in "#>|":
        return False  # ATX 見出し / blockquote / 表
    if _LIST_RE.match(line) or _SETEXT_RE.match(line):
        return False
    if _INLINE_STRUCTURE_RE.search(line):
        return False
    return True


def structural_tokens(text):
    """機械パーストークンを (kind, value) の列で返す。出現順を保持する。"""
    tokens = []
    lines = text.split("\n")
    i = 0

    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                tokens.append(("frontmatter", "\n".join(lines[: j + 1])))
                i = j + 1
                break

    fence_char = None
    fence_len = 0
    fence_buf = []
    prev_prose = None  # 直前の非空散文行（setext 見出しのテキスト候補）
    for ln in lines[i:]:
        if fence_char is not None:
            fence_buf.append(ln)
            stripped = ln.strip()
            # closer は opener と同じ文字種で opener 以上の run 長のみ
            # （内側の短い ``` を closer と誤認すると以降の内容が指紋から漏れる）
            if stripped and set(stripped) == {fence_char} \
                    and len(stripped) >= fence_len:
                tokens.append(("fence", "\n".join(fence_buf)))
                fence_buf = []
                fence_char = None
            continue
        m = _FENCE_OPEN_RE.match(ln)
        if m:
            fence_char = m.group(1)[0]
            fence_len = len(m.group(1))
            fence_buf = [ln]
            prev_prose = None
            continue
        # setext 下線は直前の散文行を見出しテキストとして道連れにする
        # （下線だけをトークン化すると見出し名の変更を散文と誤認する）
        if _SETEXT_RE.match(ln) and prev_prose is not None:
            tokens.append(("heading", prev_prose + "\n" + ln.strip()))
            prev_prose = None
            continue
        if _is_prose(ln):
            prev_prose = ln if ln.strip() else None
            continue
        tokens.append(("line", ln))
        prev_prose = None
    if fence_char is not None:
        # 閉じられていないフェンスは残り全文をコード扱い（重い側）
        tokens.append(("fence", "\n".join(fence_buf)))
    return tokens


def structural_fingerprint(text):
    """構造トークン列の sha256 hex。一致 = 散文のみの差分。"""
    h = hashlib.sha256()
    for kind, value in structural_tokens(text):
        h.update(f"{kind}\x1f{value}\x1e".encode("utf-8"))
    return h.hexdigest()
