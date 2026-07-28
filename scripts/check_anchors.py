"""md リンクと散文節参照が実在する見出しを指すか検証する。

validate_repo.py のリンク検証はパス部分しか見ず `#` 以降を捨てる。そのため
見出しを改名して参照側を取りこぼしても CI は緑のままで、リンクだけが静かに
壊れる。ja→en の一括変換では見出しを大量に書き換えるので、この取りこぼしが
最も起きやすい。本スクリプトがその機械検証を担う。

検証するのはリポジトリ内の md へ向いた相対リンクと、同一行または直前の
非空行に対象 md リンクを持つ ``§節名`` / ``"節名" section`` 形式。外部 URL、
md 以外の拡張子、存在しないパス（validate_repo.py のリンク検証の管轄）は
対象外。散文節参照の対象ファイルを解決できない場合は警告のみとする。

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

from md_fence import iter_outside_fence

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")
SECTION_REFERENCE = re.compile(
    r'§\s*"([^"\n]+)"'
    r'|§\s*([^§\n]+?)(?=\s+(?:from|in|of)\s+\[|[.;。；)|:]|$)'
    r'|"([^"\n]+)"\s+section\b')


def slugify(text):
    """見出しテキストを GitHub 準拠のアンカーへ変換する。"""
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[^\w\s\-]", "", text.lower(), flags=re.UNICODE)
    # 空白 1 個 = ハイフン 1 個。連続空白を畳むと、記号除去で生まれた
    # `spec_lint / trace_matrix` 由来の `--` を取りこぼす。
    return re.sub(r"\s", "-", text.strip())


def anchors(path):
    """ファイル内の見出しから生成されるアンカーの集合を返す。

    アンカー生成規則は GitHub 準拠:
      1. インラインコードとリンク記法を中身へ展開する
      2. lowercase 化する
      3. 単語構成文字・空白・ハイフン以外を除去する
      4. 空白 1 個をハイフン 1 個へ写す（連続空白は連続ハイフンになる）
      5. 同一スラグが複数回出現したら 2 つ目以降に ``-1``, ``-2`` を付ける
    """
    found = set()
    slug_counts: dict[str, int] = {}
    with open(path, encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    for line in iter_outside_fence(lines):
        matched = HEADING.match(line.rstrip("\n"))
        if matched:
            slug = slugify(matched.group(1))
            count = slug_counts.get(slug, 0)
            if count == 0:
                found.add(slug)
            else:
                found.add(f"{slug}-{count}")
            slug_counts[slug] = count + 1
    return found


def _markdown_target(line, reference_start, previous_line):
    """同一行、次いで直前の非空行から参照先 md を解決する。"""
    matches = list(LINK.finditer(line))
    if matches:
        nearest = min(
            matches,
            key=lambda match: min(
                abs(reference_start - match.start()),
                abs(reference_start - match.end()),
            ),
        )
        return nearest.group(1)
    previous = list(LINK.finditer(previous_line or ""))
    if len(previous) == 1:
        return previous[0].group(1)
    return None


def _inside_markdown_link(line, position):
    return any(match.start() <= position < match.end()
               for match in LINK.finditer(line))


def _section_exists(section, available):
    """完全な節名または一意な見出し接頭辞なら参照可能とみなす。"""
    requested = slugify(section)
    if requested in available:
        return True
    return sum(anchor.startswith(requested) for anchor in available) == 1


def scan_details(roots):
    """壊れた参照と、参照先を解決できない散文節参照を返す。

    フェンス内のリンクは走査対象から除外する（anchors() と対称にする）。
    散文節参照の対象ファイルは同一行の最寄り md リンク、または直前の
    非空行にある単一の md リンクから解決する。解決不能は警告に留める。
    """
    cache = {}
    broken = []
    warnings = []
    for root in roots:
        for path in sorted(glob.glob(f"{root}/**/*.md", recursive=True)):
            with open(path, encoding="utf-8") as handle:
                lines = handle.read().splitlines()
            prose_lines = list(iter_outside_fence(lines))
            prose_text = "\n".join(prose_lines)
            for target in LINK.findall(prose_text):
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
            previous_nonempty = None
            for line in prose_lines:
                for matched in SECTION_REFERENCE.finditer(line):
                    if _inside_markdown_link(line, matched.start()):
                        continue
                    section = next(
                        group for group in matched.groups() if group is not None
                    ).strip()
                    if not section or re.match(r"^\d", section):
                        continue
                    current_cell = line[:matched.start()].rsplit("|", 1)[-1]
                    if re.search(r"\bthis file\s*,?\s*$", current_cell,
                                 flags=re.IGNORECASE):
                        target = os.path.basename(path)
                    else:
                        target = _markdown_target(
                            line, matched.start(), previous_nonempty)
                    reference = matched.group(0).strip()
                    if not target:
                        if path not in cache:
                            cache[path] = anchors(path)
                        if _section_exists(section, cache[path]):
                            continue
                        warnings.append((path, reference))
                        continue
                    rel, _, _ = target.partition("#")
                    if target.startswith(("http://", "https://")) or not rel:
                        warnings.append((path, reference))
                        continue
                    dest = os.path.normpath(
                        os.path.join(os.path.dirname(path), rel))
                    if not dest.endswith(".md") or not os.path.exists(dest):
                        warnings.append((path, reference))
                        continue
                    if dest not in cache:
                        cache[dest] = anchors(dest)
                    anchor = slugify(section)
                    if not _section_exists(section, cache[dest]):
                        broken.append((path, f"{rel}#{anchor}"))
                if line.strip():
                    previous_nonempty = line
    return broken, warnings


def scan(roots):
    """壊れた参照を (参照元, リンク先) の列で返す。"""
    broken, _ = scan_details(roots)
    return broken


def report(broken, warnings=None):
    for src, reference in warnings or []:
        print(f"⚠ {src} -> 参照先を解決できない散文節参照: {reference}")
    for src, target in broken:
        print(f"✗ {src} -> {target}")
    if broken:
        print(f"✗ {len(broken)} 件のアンカー参照が飛び先を失っている")
        return 1
    print("✓ アンカー参照: 飛び先の欠落なし")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="md アンカー参照の飛び先を検証する")
    parser.add_argument("roots", nargs="*", default=["."],
                        help="走査するディレクトリ（既定: .）")
    args = parser.parse_args(argv)
    broken, warnings = scan_details(args.roots or ["."])
    return report(broken, warnings)


if __name__ == "__main__":
    sys.exit(main())
