"""スキル文書の英語化到達度を測る（skills/**/*.md）。

素朴に「日本語を含む行の割合」を数えると使い物にならない。翻訳スコープは本文の
指示・散文だけで、frontmatter・ユーザーへ提示される定型文・鉤括弧で引用した
ユーザー向け文字列は**原文のまま残すのが正しい**からである。それらを数に入れると、
英語化を完了したスキルほど「残存率が高い」と報告され、指標が完了判定に使えなくなる。

そこで測るのは **翻訳対象である散文のうち、まだ日本語のままの行の割合** とする:

- frontmatter は除外（description は発火判定の入力で trigger-eval の領分）
- fenced code block は除外（ユーザーへ提示する完了メッセージ・選択肢ブロックが入る）
- 残った散文からは鉤括弧で引用されたユーザー向け文字列を取り除いてから判定する

この定義でも、鉤括弧を使わずに地の文へユーザー向け文言を書いた箇所は日本語として
数えられる。これは指標の欠陥ではなく、そういう箇所は引用形に直すべきという設計上の
要求として扱う。
"""
import argparse
import json
import pathlib
import re
import sys

from md_fence import iter_outside_fence

JP = re.compile(r"[ぁ-んァ-ヴ一-龥]")
QUOTED = re.compile(r"[「『][^」』]*[」』]")
DEFAULT_THRESHOLD = 0.15


def strip_frontmatter(lines: list[str]) -> list[str]:
    """先頭の `---` で囲まれた frontmatter を落とす。無ければそのまま返す。"""
    if not lines or lines[0].strip() != "---":
        return lines
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return lines[i + 1:]
    return lines  # 閉じられていない frontmatter は本文として扱う


def prose_lines(text: str) -> list[str]:
    """判定対象の散文行だけを返す（frontmatter / コードブロック / 空行を除く）。"""
    return [line for line in iter_outside_fence(strip_frontmatter(text.splitlines()))
            if line.strip()]


def untranslated(line: str) -> bool:
    """引用されたユーザー向け文字列を除いてなお日本語が残るか。"""
    return bool(JP.search(QUOTED.sub("", line)))


def measure(text: str) -> tuple[int, int]:
    """(未翻訳行, 散文行) を返す。散文が 0 行なら (0, 0)。"""
    lines = prose_lines(text)
    return sum(1 for l in lines if untranslated(l)), len(lines)


def scan(paths: list[pathlib.Path], threshold: float) -> list[dict]:
    """各ファイルの測定結果を、比率の降順で返す。"""
    rows = []
    for p in paths:
        n, total = measure(p.read_text(encoding="utf-8"))
        ratio = n / total if total else 0.0
        rows.append({"file": str(p), "untranslated": n, "prose": total,
                     "ratio": round(ratio, 4), "over": ratio >= threshold})
    return sorted(rows, key=lambda r: (-r["ratio"], r["file"]))


def collect(roots: list[str]) -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for r in roots:
        p = pathlib.Path(r)
        if p.is_dir():
            out += sorted(p.rglob("*.md"))
        elif p.is_file():
            out.append(p)
        else:
            sys.exit(f"path not found: {r}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", default=["skills"])
    ap.add_argument("--max-jp-ratio", type=float, default=DEFAULT_THRESHOLD)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--limit", type=int, default=20, help="テキスト出力で並べる件数")
    args = ap.parse_args()

    files = collect(args.paths or ["skills"])
    if not files:
        print("no markdown files found", file=sys.stderr)
        return 2
    rows = scan(files, args.max_jp_ratio)
    over = [r for r in rows if r["over"]]
    done = len(rows) - len(over)

    if args.json:
        print(json.dumps({"threshold": args.max_jp_ratio, "total": len(rows),
                          "translated": done, "over": len(over), "files": rows},
                         ensure_ascii=False, indent=2))
    else:
        print(f"threshold={args.max_jp_ratio}  translated {done}/{len(rows)}  "
              f"remaining {len(over)}")
        for r in over[:args.limit]:
            print(f"  {r['ratio']*100:5.1f}%  {r['untranslated']:4}/{r['prose']:<4} {r['file']}")
        if len(over) > args.limit:
            print(f"  … and {len(over) - args.limit} more")
    return 1 if over else 0


if __name__ == "__main__":
    raise SystemExit(main())
