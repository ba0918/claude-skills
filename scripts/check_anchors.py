"""md リンクのアンカー飛び先が実在する見出しを指すか検証する。

validate_repo.py のリンク検証はパス部分しか見ず `#` 以降を捨てる。そのため
見出しを改名して参照側を取りこぼしても CI は緑のままで、リンクだけが静かに
壊れる。ja→en の一括変換では見出しを大量に書き換えるので、この取りこぼしが
最も起きやすい。本スクリプトがその機械検証を担う。

検証するのはリポジトリ内の md へ向いた相対リンクのみ。外部 URL、md 以外の
拡張子、存在しないパス（validate_repo.py のリンク検証の管轄）は対象外。

アンカーの生成規則は GitHub 準拠:
  1. インラインコードとリンク記法を中身へ展開する
  2. lowercase 化する
  3. 単語構成文字・空白・ハイフン以外を除去する
  4. 空白 1 個をハイフン 1 個へ写す（連続空白は連続ハイフンになる）
"""
import argparse
import glob
import os
import re
import sys

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")
FENCE = re.compile(r"^\s*(?:```|~~~)")


def slugify(text):
    """見出しテキストを GitHub 準拠のアンカーへ変換する。"""
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[^\w\s\-]", "", text.lower(), flags=re.UNICODE)
    # 空白 1 個 = ハイフン 1 個。連続空白を畳むと、記号除去で生まれた
    # `spec_lint / trace_matrix` 由来の `--` を取りこぼす。
    return re.sub(r"\s", "-", text.strip())


def anchors(path):
    """ファイル内の見出しから生成されるアンカーの集合を返す。"""
    found = set()
    in_fence = False
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            matched = HEADING.match(line.rstrip("\n"))
            if matched:
                found.add(slugify(matched.group(1)))
    return found


def scan(roots):
    """壊れたアンカー参照を (参照元, リンク先) の列で返す。"""
    cache = {}
    broken = []
    for root in roots:
        for path in sorted(glob.glob(f"{root}/**/*.md", recursive=True)):
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            for target in LINK.findall(text):
                if target.startswith(("http://", "https://")) or "#" not in target:
                    continue
                rel, _, anchor = target.partition("#")
                if not anchor:
                    continue
                dest = path if not rel else os.path.normpath(
                    os.path.join(os.path.dirname(path), rel))
                if not dest.endswith(".md") or not os.path.exists(dest):
                    continue
                if dest not in cache:
                    cache[dest] = anchors(dest)
                if anchor not in cache[dest]:
                    broken.append((path, target))
    return broken


def report(broken):
    for src, target in broken:
        print(f"✗ {src} -> {target}")
    if broken:
        print(f"✗ {len(broken)} 件のアンカー参照が飛び先を失っている")
        return 1
    print("✓ アンカー参照: 飛び先の欠落なし")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="md アンカー参照の飛び先を検証する")
    parser.add_argument("roots", nargs="*", default=["skills"],
                        help="走査するディレクトリ（既定: skills）")
    args = parser.parse_args(argv)
    return report(scan(args.roots or ["skills"]))


if __name__ == "__main__":
    sys.exit(main())
