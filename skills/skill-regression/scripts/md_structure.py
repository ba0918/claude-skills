#!/usr/bin/env python3
"""md の構造フィンガープリント算出（純関数）。

散文のみ変更（prose-only）の機械判定に使う。md テキストから機械パーストークン
（frontmatter・コードフェンス・インデントコード・インラインコード・リンク先・
表行・見出し行）を出現順に抽出し、その列の sha256 をフィンガープリントとする。
2 版のフィンガープリントが一致すれば、変わったのは散文だけだと言える。

誤判定の向きは非対称で、抽出しすぎ（散文をトークン扱い）は重い側
（contract-change）へ倒れるだけだが、抽出漏れは挙動変更を散文と誤認させる。
規則は広め（表はセル散文ごと丸ごと・見出し丸ごと・行頭 4 スペースはコード扱い）
に取り、迷ったらトークンに含める。
"""
import hashlib
import re

_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_LINK_TARGET_RE = re.compile(r"\]\(([^)]+)\)")
_REF_DEF_RE = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*(\S+)")


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

    fence_close = None
    fence_buf = []
    for ln in lines[i:]:
        stripped = ln.strip()
        if fence_close is not None:
            fence_buf.append(ln)
            if stripped.startswith(fence_close):
                tokens.append(("fence", "\n".join(fence_buf)))
                fence_buf = []
                fence_close = None
            continue
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fence_close = stripped[:3]
            fence_buf = [ln]
            continue
        if ln.startswith("    "):
            tokens.append(("indented-code", ln))
            continue
        if stripped.startswith("|"):
            tokens.append(("table", stripped))
            continue
        if stripped.startswith("#"):
            tokens.append(("heading", stripped))
            continue
        m = _REF_DEF_RE.match(ln)
        if m:
            tokens.append(("ref-def", m.group(1)))
            continue
        for m in _LINK_TARGET_RE.finditer(ln):
            tokens.append(("link", m.group(1)))
        for m in _INLINE_CODE_RE.finditer(ln):
            tokens.append(("code", m.group(1)))
    if fence_close is not None:
        # 閉じられていないフェンスは残り全文をコード扱い（重い側）
        tokens.append(("fence", "\n".join(fence_buf)))
    return tokens


def structural_fingerprint(text):
    """構造トークン列の sha256 hex。一致 = 散文のみの差分。"""
    h = hashlib.sha256()
    for kind, value in structural_tokens(text):
        h.update(f"{kind}\x1f{value}\x1e".encode("utf-8"))
    return h.hexdigest()
