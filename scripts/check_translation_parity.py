"""翻訳による構造劣化を検出する（dossier の `sensor:translation-damage` の実装）。

ja→en の一括変換では、fixture を持たない 26 スキルについて非劣化 A/B が原理的に
走らせられない。dossier `frag:translation-damage-sensor` が「fixture 未保有スキルを
構造検証のみで訳す方針を採ったため、この sensor が唯一の劣化検出手段になる断片が
存在する」と判定しているのはそのためで、本スクリプトがその機械検証を担う。

測るのは **翻訳の前後で不変であるべき構造** だけであり、訳文の品質は測らない。
比較は git の baseline リビジョン ⇔ 作業ツリーで行う。

## 対象ファイルの選別

翻訳されたファイルを 2 つの経路で拾う。**閾値の跨ぎ**（日本語行比率が閾値以上から
閾値未満へ遷移した = 元が日本語主体だったファイル）と、**日本語行の実質的な減少**
（元から本文の一部が英語だった部分翻訳ファイル）である。

跨ぎだけを条件にすると、部分翻訳ファイルは閾値を跨がないため一切検証されない。
それでいて出力は「劣化なし」と読めるため、緑の意味が「検証して問題なし」から
「検証していない」へ静かに反転する。英語化が進むほど残る作業は部分翻訳ファイルに
寄るので、スイープの後半ほど網が粗くなる。

減少側の条件には縮み幅の上限を置く。翻訳は行を置き換えるが、節の削除は散文行そのものを
減らす。縮んだファイルまで翻訳として扱うと、日本語のまま節を消す通常の編集が
すべて構造差分で赤くなり、ゲートが常時赤になって使い物にならない。

どちらの経路にも載らなかったファイルのうち、日本語が減っているものは
`report()` が **未検証** として明示列挙する。素通しと検証済みを出力で区別する。

閾値と日本語判定は check_language_coverage と共有する（2 つの日本語検出器が
別々に育つと、指標と劣化検出が食い違う）。

## baseline の鮮度

remote-tracking ref は fetch するまで更新されない。pre-push hook は push の **前** に
走るため、「しばらく fetch していない作業ディレクトリから push する」経路では
古い `origin/main` が baseline に採用される。するとマージ済みの翻訳が
「これから入る翻訳」として再検出され、数十件の偽 BLOCK でゲートが赤くなる。

対策は 2 つある。pre-push hook は push ネゴシエーションで得た **remote の現在地**
（stdin の remote sha）を `$TRANSLATION_PARITY_BASELINE` で渡す。これは fetch なしに
得られる正確な比較元である。それが使えない経路のために、baseline から HEAD までの
コミット数が `--max-baseline-lead` を超えたら比較を成立させず skip を明示出力する。

`git fetch` をスクリプトから打つことはしない。副作用が大きく、検証の実行が
リポジトリの状態を変えるのは sensor の役割から外れる。

## rule と severity

| rule | severity | 見るもの |
|------|----------|----------|
| structure_parity | BLOCK | 見出し / フェンス / リンク / 番号 / 箇条書き / 表の行 / 水平線の件数 |
| identifier_preservation | BLOCK | インラインコード・リンク先・契約語彙の消失 |
| frontmatter_immutability | BLOCK | frontmatter の `name`（スキル識別子）の不変 |

`--strict` を使うと WARN も exit code に含める（現時点で WARN を出す rule は無い）。

fix action は全 rule で NEEDS_JUDGMENT（dossier の findings_policy に従う）。
消失した識別子を機械的に戻すと訳文の構文を壊しうるため AUTO_FIX にしない。
分類の定義は skills/shared/references/fix-action-taxonomy.md を参照。
"""
import argparse
import json
import os
import re
import subprocess
import sys

from check_language_coverage import (
    DEFAULT_THRESHOLD,
    JP,
    measure,
    strip_frontmatter,
)
from md_fence import classify_lines
from validate_repo import CONTRACT_VOCAB

SENSOR = "sensor:translation-damage"
FIX_ACTION = "NEEDS_JUDGMENT"

HEADING = re.compile(r"^(#{1,6})\s")
ORDERED = re.compile(r"^\s*\d+\.\s")
BULLET = re.compile(r"^\s*[-*+]\s")
TABLE_ROW = re.compile(r"^\s*\|")
HR = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)")
INLINE_CODE = re.compile(r"`([^`\n]+)`")
FM_NAME = re.compile(r"^name:\s*(.+?)\s*$", re.MULTILINE)

# baseline リビジョンの解決順。ローカル（pre-push）と CI（PR）の両方で、
# ネットワークアクセスなしにローカル ref だけで解決できる候補を並べる。
BASELINE_ENV = "TRANSLATION_PARITY_BASELINE"

# baseline から HEAD までのコミット数の上限。これを超えたら比較を成立させない。
# 実測の根拠: 本リポジトリの feature ブランチは 1〜2 コミットで、偽 BLOCK 68 件を
# 出した事例では古い remote-tracking ref が 195 コミット先行していた。日数を条件に
# しないのは、その事例の ref が 4 日前のリリースのもので、活発なリポジトリでは
# 「古さ」が日数に現れないため。先行コミット数は fetch 漏れの量を直接映す。
DEFAULT_MAX_BASELINE_LEAD = 100

# 翻訳と認めるのに必要な日本語行の最小減少。1〜2 行の手直しを翻訳と数えない。
MIN_TRANSLATED_LINES = 3

# 翻訳として許容する散文行の縮み幅。これを超えて縮んだものは削除とみなす。
MAX_PROSE_SHRINK = 0.10

# 契約語彙は validate_repo のチェック9 と同一の表を使う。あちらは「語彙があるなら
# 契約へのリンクを要求する」検査で、語彙が消えた場合は要求そのものが消えて
# 検出できない。消失側は本 sensor が持つ。
VOCAB_TERMS = sorted({term for _, terms, _ in CONTRACT_VOCAB for term in terms})

RENAME_ALLOWLIST_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "rename-allowlist.json")


def load_rename_allowlist(path=None):
    """リネーム許可表を読み込む。ファイルが無ければ空リスト。"""
    path = path or RENAME_ALLOWLIST_PATH
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def split_frontmatter(text):
    """(frontmatter の生テキスト, 本文行) に分ける。frontmatter が無ければ ("", 全行)。"""
    lines = text.splitlines()
    body = strip_frontmatter(lines)
    return "\n".join(lines[: len(lines) - len(body)]), body


def is_identifier(token):
    """保持を要求する識別子か。過去の翻訳 41 ペアの実測で決めた 2 つの除外を持つ。

    - **日本語を含むものは除く**。`{観点}` `{checkpoint.py のパス}`
      `#1-feasibility---実現可能性` のようなプレースホルダ・アンカーは、訳文では
      中身も一緒に訳されるのが正しい。これが最大の偽陽性源だった。
    - **英数字を含まないものは除く**。`>` `>>` のようなシェル演算子は、
      消えても劣化ではない断片としてノイズになる。
    """
    return bool(re.search(r"[0-9A-Za-z]", token)) and not JP.search(token)


def fingerprint(text):
    """翻訳前後で不変であるべき構造の指紋を返す。"""
    frontmatter, body = split_frontmatter(text)
    prose, fence_lines, fences = [], 0, 0
    prev_tag = "prose"
    for tag, line in classify_lines(body):
        if tag == "fence_marker" and prev_tag != "fenced":
            fences += 1  # 開始マーカーだけを数える
        elif tag == "fenced":
            fence_lines += 1
        elif tag == "prose":
            prose.append(line)
        prev_tag = tag

    prose_text = "\n".join(prose)
    body_text = "\n".join(body)
    links = LINK.findall(prose_text)
    # 識別子はフェンス内も含めて集める。ユーザー提示テンプレート内のパスや
    # コマンド名が消えるのも劣化であり、フェンスの外だけでは取り逃がす。
    identifiers = {t.strip() for t in INLINE_CODE.findall(body_text)
                   if is_identifier(t.strip())}
    name = FM_NAME.search(frontmatter)
    return {
        "name": name.group(1) if name else "",
        "headings": [len(m.group(1)) for m in map(HEADING.match, prose) if m],
        "fences": fences,
        "fence_lines": fence_lines,
        "links": sorted(links),
        "ordered": sum(1 for l in prose if ORDERED.match(l)),
        "bullets": sum(1 for l in prose if BULLET.match(l)),
        "table_rows": sum(1 for l in prose if TABLE_ROW.match(l)),
        "hrs": sum(1 for l in prose if HR.match(l)),
        "identifiers": identifiers | {l for l in links if is_identifier(l)},
        "text": body_text,
        "vocab": {t for t in VOCAB_TERMS if t in body_text},
    }


def japanese_lines(base_text, cur_text):
    """(baseline の未翻訳行, 現在版の未翻訳行, baseline の散文行, 現在版の散文行)。"""
    base_n, base_total = measure(base_text)
    cur_n, cur_total = measure(cur_text)
    return base_n, cur_n, base_total, cur_total


def is_translation(base_text, cur_text, threshold=DEFAULT_THRESHOLD):
    """このファイルは今回訳されたか。

    閾値の跨ぎと、日本語行の実質的な減少の 2 経路で判定する（詳細は module docstring）。
    """
    base_n, cur_n, base_total, cur_total = japanese_lines(base_text, cur_text)
    base_ratio = base_n / base_total if base_total else 0.0
    cur_ratio = cur_n / cur_total if cur_total else 0.0
    if base_ratio >= threshold > cur_ratio:
        return True
    return (base_n - cur_n >= MIN_TRANSLATED_LINES
            and cur_ratio < base_ratio
            and cur_total >= base_total * (1 - MAX_PROSE_SHRINK))


def _finding(path, rule, severity, detail):
    return {"file": path, "sensor": SENSOR, "rule": rule,
            "severity": severity, "fix_action": FIX_ACTION, "detail": detail}


# structure_parity で件数一致を要求する次元。(指紋キー, 表示名, 値の整形)
COUNT_DIMENSIONS = [
    ("headings", "見出しの件数", len),
    ("fences", "コードフェンスの件数", int),
    ("fence_lines", "フェンス内の行数", int),
    ("links", "md リンクの件数", len),
    ("ordered", "番号ステップの件数", int),
    ("bullets", "箇条書きの件数", int),
    ("table_rows", "表の行数", int),
    ("hrs", "水平線の件数", int),
]


def _lost(base_set, cur_set, limit=8):
    """baseline にあって現在版で消えた要素を、表示用に整形して返す。"""
    lost = sorted(base_set - cur_set)
    shown = ", ".join(lost[:limit])
    if len(lost) > limit:
        shown += f", … +{len(lost) - limit}"
    return lost, shown


def compare(path, base_text, cur_text, rename_allowlist=None):
    """翻訳前後の指紋を突き合わせ、finding のリストを返す。"""
    if rename_allowlist is None:
        rename_allowlist = load_rename_allowlist()
    base, cur = fingerprint(base_text), fingerprint(cur_text)
    findings = []

    if base["name"] != cur["name"]:
        findings.append(_finding(
            path, "frontmatter_immutability", "BLOCK",
            f"frontmatter の name が変化している: {base['name']} → {cur['name']}"
            "（スキル識別子は command / README / manifest から参照される）"))

    for key, label, norm in COUNT_DIMENSIONS:
        before, after = norm(base[key]), norm(cur[key])
        if before != after:
            findings.append(_finding(path, "structure_parity", "BLOCK",
                                     f"{label}: {before} → {after}"))
    if base["headings"] != cur["headings"] and len(base["headings"]) == len(cur["headings"]):
        findings.append(_finding(path, "structure_parity", "BLOCK",
                                 "見出しレベルの並びが変化している: "
                                 f"{base['headings']} → {cur['headings']}"))

    # 消失判定は「現在版の本文のどこにも文字列として現れない」で行う。識別子の集合
    # 差分で見ると、`(none)` → `branch: (none)` のようにインラインコードの括り方が
    # 変わっただけで消失と報告される（過去 41 ペアの実測で確認した偽陽性）。
    for key, label in (("identifiers", "識別子"), ("vocab", "契約語彙")):
        survived = {t for t in base[key] if t in cur["text"]}
        # 許可表に申告済みのリネーム: old が消え new が存在するなら消失扱いしない
        for entry in rename_allowlist:
            old = entry.get("old", "")
            new = entry.get("new", "")
            if old in base[key] and old not in survived and new in cur["text"]:
                survived.add(old)
        lost, shown = _lost(base[key], survived)
        if lost:
            findings.append(_finding(
                path, "identifier_preservation", "BLOCK",
                f"{label} {len(lost)} 種が消失: {shown}"))

    return findings


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def git(args, repo, check=True):
    """GIT_* を継承しない git 呼び出し。hook 経由だと GIT_DIR が本体を指すため。"""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    proc = subprocess.run(["git", *args], cwd=repo, env=env,
                          capture_output=True, text=True)
    if check and proc.returncode != 0:
        return None
    return proc.stdout


def resolve_baseline(repo, explicit=None):
    """比較元リビジョンを解決する。見つからなければ None。"""
    base_ref = os.environ.get("GITHUB_BASE_REF")
    candidates = [explicit, os.environ.get(BASELINE_ENV),
                  f"origin/{base_ref}" if base_ref else None, "origin/main", "main"]
    for rev in [c for c in candidates if c]:
        if git(["rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}"], repo) is None:
            continue
        # fork point を使う。baseline の tip を直接使うと、main 側が同じファイルを
        # 触っていた場合にこちらの変更でない差分まで拾う。
        merged = git(["merge-base", "HEAD", rev], repo)
        return merged.strip() if merged else rev
    return None


def baseline_lead(repo, baseline):
    """baseline から HEAD までのコミット数。数えられなければ None。"""
    out = git(["rev-list", "--count", f"{baseline}..HEAD"], repo)
    if out is None or not out.strip().isdigit():
        return None
    return int(out.strip())


def changed_md(repo, baseline, paths):
    """baseline ⇔ 作業ツリーで変化した .md のリポジトリ相対パス。"""
    out = git(["diff", "--name-only", baseline, "--", *(paths or ["."])], repo)
    if out is None:
        return []
    return [p for p in out.splitlines() if p.endswith(".md")]


def baseline_text(repo, baseline, path):
    """baseline 側の内容。新規ファイル等で存在しなければ None。"""
    return git(["show", f"{baseline}:{path}"], repo)


def scan(repo, baseline, paths, force=False):
    """(findings, 検証したファイル数, 対象外のファイル数, 未検証の明細)。

    未検証の明細は `[(path, baseline の未翻訳行, 現在版の未翻訳行), ...]`。
    翻訳判定に載らなかったファイルのうち、日本語が減っているものだけを挙げる。
    「対象外」に埋めると素通しと検証済みが出力で区別できない。
    """
    findings, checked, skipped, unverified = [], 0, 0, []
    rename_allowlist = load_rename_allowlist()
    for rel in changed_md(repo, baseline, paths):
        full = os.path.join(repo, rel)
        if not os.path.isfile(full):
            continue  # 削除されたファイルは比較対象にしない
        base = baseline_text(repo, baseline, rel)
        if base is None:
            continue  # baseline に存在しない = 新規追加
        cur = read(full)
        if not force and not is_translation(base, cur):
            skipped += 1
            base_n, cur_n, _, _ = japanese_lines(base, cur)
            if base_n > cur_n:
                unverified.append((rel, base_n, cur_n))
            continue
        checked += 1
        findings += compare(rel, base, cur, rename_allowlist=rename_allowlist)
    return findings, checked, skipped, unverified


def _print_unverified(unverified, limit=10):
    """未検証ファイルを列挙する。緑を「検証済み」と読ませないための出力。"""
    if not unverified:
        return
    print(f"  ! 未検証 {len(unverified)} ファイル: 日本語は減っているが翻訳判定に"
          "載らないため、構造は検証していない")
    for rel, base_n, cur_n in unverified[:limit]:
        print(f"      {rel}（未翻訳行 {base_n} → {cur_n}）")
    if len(unverified) > limit:
        print(f"      … +{len(unverified) - limit}")
    print("      翻訳したファイルなら --force で検証できる")


def report(findings, checked, skipped, unverified, strict):
    blocks = [f for f in findings if f["severity"] == "BLOCK"]
    warns = [f for f in findings if f["severity"] == "WARN"]
    if not findings:
        print(f"✓ {SENSOR}: 翻訳 {checked} ファイルに劣化なし"
              f"（翻訳判定に載らず対象外 {skipped}）")
        _print_unverified(unverified)
        return 0
    print(f"✗ {SENSOR}: {len(findings)} 件（BLOCK {len(blocks)} / WARN {len(warns)}）"
          f"  検証 {checked} ファイル / 対象外 {skipped}")
    for f in blocks + warns:
        print(f"  {f['severity']:<5} {f['file']} [{f['rule']}] {f['detail']}")
    print(f"  fix action: {FIX_ACTION}（機械的な復元は訳文の構文を壊すため行わない）")
    _print_unverified(unverified)
    return 1 if blocks or (strict and warns) else 0


def main():
    ap = argparse.ArgumentParser(description="翻訳による構造劣化を検出する")
    ap.add_argument("paths", nargs="*", help="対象を絞る pathspec（既定はリポジトリ全体）")
    ap.add_argument("--repo", default=".", help="リポジトリルート")
    ap.add_argument("--baseline", help=f"比較元リビジョン（既定: ${BASELINE_ENV} → "
                                       "origin/$GITHUB_BASE_REF → origin/main → main）")
    ap.add_argument("--pair", nargs=2, metavar=("BEFORE", "AFTER"),
                    help="2 ファイルを直接比較する（git を使わず、遷移判定も省く）")
    ap.add_argument("--force", action="store_true",
                    help="翻訳遷移の判定を省き、変化した .md すべてを検証する")
    ap.add_argument("--strict", action="store_true", help="WARN も exit 1 に含める")
    ap.add_argument("--max-baseline-lead", type=int, default=DEFAULT_MAX_BASELINE_LEAD,
                    help="baseline から HEAD までのコミット数の上限。超えたら比較を "
                         f"成立させず skip する（既定 {DEFAULT_MAX_BASELINE_LEAD}）。"
                         "明示指定した baseline には適用しない")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    unverified = []
    if args.pair:
        before, after = args.pair
        findings = compare(after, read(before), read(after))
        checked, skipped = 1, 0
    else:
        baseline = resolve_baseline(args.repo, args.baseline)
        if baseline is None:
            # 黙って無効化されると「劣化なし」と誤読されるため必ず出力する。
            print(f"- {SENSOR}: baseline リビジョンを解決できないため skip"
                  f"（--baseline か ${BASELINE_ENV} で指定できる）")
            return 0
        # 明示指定は利用者の判断なので鮮度を問わない。候補の連鎖から自動で
        # 拾った ref だけを検査する。
        explicit = args.baseline or os.environ.get(BASELINE_ENV)
        lead = None if explicit else baseline_lead(args.repo, baseline)
        if lead is not None and lead > args.max_baseline_lead:
            print(f"- {SENSOR}: baseline が古すぎるため skip")
            print(f"    {baseline[:12]} から HEAD まで {lead} コミット"
                  f"（上限 {args.max_baseline_lead}）")
            print("    remote-tracking ref が fetch されておらず、マージ済みの翻訳を"
                  "「これから入る翻訳」として再検出する状態にある")
            print("    `git fetch origin main` の後に再実行するか、--baseline で明示する")
            return 0
        findings, checked, skipped, unverified = scan(
            args.repo, baseline, args.paths, args.force)

    if args.json:
        print(json.dumps({"sensor": SENSOR, "checked": checked, "skipped": skipped,
                          "unverified": [{"file": f, "baseline_untranslated": b,
                                          "current_untranslated": c}
                                         for f, b, c in unverified],
                          "findings": findings}, ensure_ascii=False, indent=2))
        return 1 if any(f["severity"] == "BLOCK" for f in findings) else 0
    return report(findings, checked, skipped, unverified, args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
