#!/usr/bin/env python3
"""goal-loop: oracle 収束まで自律反復するループの純関数エンジン + 薄い CLI。

契約: ../../shared/references/convergence-pattern.md
  - §3 Oracle Integrity（ハッシュロック — Goodhart 遮断の中核）
  - §4 収束判定（stall / oscillation）
  - §5 Iteration Loop / LoopResult

本モジュールの中核関数（oracle_manifest / verify_oracle_integrity /
normalize_output / failure_signature / detect_convergence_halt /
make_loop_result）はすべて副作用なし（time / random / I/O 不使用）。
ループのコントロール自体（kill file 監視・oracle 実行・実装委譲）は
goal-loop スキルの Agent 側が契約 §5 の擬似コードに従って行う。
本スクリプトはそのための I/O プリミティブ（lock / verify / signature）を
CLI として提供する。

CLI:
  lock FILE... --out MANIFEST.json
      ファイル群を読んで v2 manifest（{version:2, roots:[...], files:{...}}）を
      JSON 保存する。roots は lock に渡した生引数列（走査 root）、files は
      解決済みの path -> sha256 マップ。glob 展開は shell に任せる。ディレクトリを
      渡すと再帰的に配下の全ファイルを対象にする。
      注意: manifest（--out）は **どの lock root の配下にも置かない**こと。root 配下に
      置くと verify の再走査がそれを「追加ファイル」と見なし常に oracle_tampered に
      なる（fail-closed だが誤停止する footgun）。SKILL の $WORK/.claude/tmp 慣習で回避。

  verify MANIFEST.json
      manifest の roots を **再走査**して current 集合を再構築し、各ファイルを
      再ハッシュして verify_oracle_integrity を行う。ok なら exit 0。tampered
      （変更・削除・**追加**）なら該当パスを 1 行ずつ stderr に出し exit 2。

      追加検出について: roots を _collect_paths で再走査するため、ディレクトリ
      形式で lock された root 配下に lock 後に置かれた新規ファイル（例: 失敗を
      握りつぶす conftest.py）も current に現れ、manifest に無いパスとして
      oracle_tampered（exit 2）で検出される。これは契約 convergence-pattern.md
      §3.3 / §4.2 の「追加をすべて検出」を CLI 層でも満たすためのもの。
      ただし追加検出はディレクトリ粒度の root にのみ有効（shell glob で個別
      ファイル列に展開して渡された場合、兄弟ファイルの追加は検出できない）。

      fail-closed: manifest 欠落・読取不能・壊れた JSON・非 dict・v2 型不正・
      roots 走査中の OSError（symlink ループ等）はすべて exit 2 + stderr で
      拒否する。旧フラット形式へのフォールバックや exit 1 の取りこぼしは作らない
      （弱挙動への downgrade 経路 = oracle-gaming の抜け道になるため）。

  signature
      stdin から failure_signature を計算して stdout に出力する。

  halt HISTORY.txt [--stall-limit N] [--window N] [--max-period N]
      signature を 1 行 1 個で追記した履歴ファイルを読み、
      detect_convergence_halt を実行する。none: exit 0 / stall: exit 3 /
      oscillation: exit 4。空行・前後空白は無視する。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 純関数（契約 §3 / §4）
# ---------------------------------------------------------------------------


def oracle_manifest(contents: dict[str, bytes]) -> dict[str, str]:
    """path -> sha256 hex64 の manifest（契約 §4.2 / §3.1 lock）。"""
    return {path: hashlib.sha256(data).hexdigest() for path, data in contents.items()}


def verify_oracle_integrity(manifest: dict[str, str], current: dict[str, str]) -> dict:
    """manifest と current を突き合わせ、変更・削除・追加をすべて検出する（契約 §3.2-3.3）。

    戻り値: {"ok": bool, "tampered": sorted list[str]}
    """
    tampered: set[str] = set()
    for path, digest in manifest.items():
        if path not in current or current[path] != digest:
            tampered.add(path)
    for path in current:
        if path not in manifest:
            tampered.add(path)
    return {"ok": not tampered, "tampered": sorted(tampered)}


def parse_manifest_envelope(raw: object) -> tuple[list[str], dict[str, str]]:
    """v2 manifest エンベロープを型検証し (roots, files) を返す（純関数・fail-closed）。

    manifest は implementer 作業ツリー内に置かれ書込可能なため、型まで厳密に検証する:
      - `isinstance(raw, dict)` ガード必須。null / [] / str / number を
        トップレベルに書くと json.loads は成功するが、後続の raw.get() が
        AttributeError → 未捕捉 exit 1（fail-open）になる。dict でなければ即 ValueError。
      - version == 2 かつ roots が list かつ files が dict でなければ ValueError。
      - roots の **各要素が str** であること。要素が非 str（int / null / list 等）だと
        後段の `Path(arg)` が TypeError を送出し、cmd_verify の except OSError に
        捕まらず exit 1（fail-open）に漏れる。要素型までここで検証し ValueError に倒す。

    旧フラット形式（version/roots 無し）へのフォールバックは作らない。verify を
    弱挙動へ downgrade する経路（= oracle-gaming の抜け道）を残さないため、
    不一致はすべて ValueError（呼び出し側が exit 2 に変換）で拒否する。
    """
    if not isinstance(raw, dict):
        raise ValueError("manifest must be a JSON object")
    if (
        raw.get("version") != 2
        or not isinstance(raw.get("roots"), list)
        or not isinstance(raw.get("files"), dict)
    ):
        raise ValueError("manifest must be v2 {version:2, roots:[...], files:{...}}")
    roots = raw["roots"]
    if not all(isinstance(r, str) for r in roots):
        raise ValueError("manifest roots must be a list of strings")
    return roots, raw["files"]


_TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[^\s]*")
_DUR_IN_RE = re.compile(r"in \d+\.\d+s")
_DUR_RE = re.compile(r"\b\d+\.\d+s\b")
_ADDR_RE = re.compile(r"0x[0-9a-fA-F]+")


def normalize_output(output: str) -> str:
    """failure signature 用の正規化（契約 §4.1）。

    タイムスタンプ・実行時間・16進アドレスをプレースホルダに置換し、
    各行を strip、空行を除去する。
    """
    text = _TS_RE.sub("<TS>", output)
    text = _DUR_IN_RE.sub("<DUR>", text)
    text = _DUR_RE.sub("<DUR>", text)
    text = _ADDR_RE.sub("<ADDR>", text)
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def failure_signature(output: str) -> str:
    """sha256(normalize_output(output)) の hex 先頭 16 文字（契約 §4.1）。"""
    normalized = normalize_output(output)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def detect_convergence_halt(
    history: list[str],
    *,
    stall_limit: int = 3,
    window: int = 6,
    max_period: int = 3,
) -> str | None:
    """stall / oscillation を検出する（契約 §4.2）。stall を oscillation より優先する。"""
    if len(history) >= stall_limit and len(set(history[-stall_limit:])) == 1:
        return "stall"

    if len(history) >= window:
        tail = history[-window:]
        for period in range(2, max_period + 1):
            if all(tail[i] == tail[i + period] for i in range(len(tail) - period)):
                if len(set(tail)) >= 2:
                    return "oscillation"

    return None


def make_loop_result(
    *,
    iterations: int,
    converged: bool,
    halt_reason: str | None = None,
    tampered_paths: list[str] | None = None,
    final_signature: str | None = None,
) -> dict:
    """契約 §5 の LoopResult。None のフィールドは省略する（構造化のみ・自由文禁止）。"""
    result: dict = {"iterations": iterations, "converged": converged}
    if halt_reason is not None:
        result["halt_reason"] = halt_reason
    if tampered_paths is not None:
        result["tampered_paths"] = tampered_paths
    if final_signature is not None:
        result["final_signature"] = final_signature
    return result


# ---------------------------------------------------------------------------
# CLI（薄い I/O）
# ---------------------------------------------------------------------------


def _is_excluded(rel: Path) -> bool:
    """oracle 実行の一時生成物か判定する（純関数・セキュリティ上重要）。

    oracle 実行自体が生成・更新する一時生成物は oracle の意味を定義しないため
    lock/verify から除外する。含めると oracle 実行のたびに（追加検出有効化後は
    特に）hash や集合が揺れて oracle_tampered の誤検出になる。
      - bytecode: *.pyc / __pycache__/
      - hidden: . 始まりのディレクトリ/ファイル（.pytest_cache / .mypy_cache /
        .ruff_cache / .hypothesis / .coverage / .git 等をまとめてカバー）

    引数 `rel` は **lock root からの相対パス**（ディレクトリ root: relative_to(root) /
    ファイル root: basename のみ）。絶対パス全体で hidden 判定すると、lock root の
    祖先に hidden 要素（~/.config, 一時ディレクトリ等）があると locked 配下の正当
    ファイルまで全除外され manifest が空化する（= verify が常に ok の無防備 fail-open
    回帰）ため、必ず相対パス要素で評価する。
    """
    if rel.suffix == ".pyc":
        return True
    return any(part == "__pycache__" or part.startswith(".") for part in rel.parts)


def _collect_paths(args: list[str]) -> list[Path]:
    """引数（ファイル or ディレクトリ）を実ファイルパスの一覧に展開する。

    ディレクトリは再帰的に配下の全ファイルを対象にする。glob 展開自体は
    shell に任せる想定（このリストは既に個別パスとして渡ってくる）。
    """
    paths: list[Path] = []
    for arg in args:
        p = Path(arg)
        if p.is_dir():
            for sub in sorted(p.rglob("*")):
                if sub.is_file() and not _is_excluded(sub.relative_to(p)):
                    paths.append(sub)
        elif not _is_excluded(Path(p.name)):
            # ファイル引数は存在確認をしない（削除済みでも append）。verify 側で
            # read_bytes の OSError を削除として fail-closed 扱いにするため。
            paths.append(p)
    return paths


def cmd_lock(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="goal_loop.py lock")
    parser.add_argument("files", nargs="+", help="oracle_files（ファイル or ディレクトリ）")
    parser.add_argument("--out", required=True, help="manifest JSON の出力先")
    ns = parser.parse_args(argv)

    paths = _collect_paths(ns.files)
    contents = {str(p): p.read_bytes() for p in paths}
    files = oracle_manifest(contents)

    # v2 manifest: roots（走査 root = lock の生引数）と files（解決済み hash）を
    # 両方保存する。roots を verify が再走査して追加ファイルを検出する。
    # roots は str(Path(arg)) で正規化（既存 files キーが str(p) 保存なのと同一挙動。
    # 相対はそのまま / 絶対はそのまま。新たな cwd 正規化は導入しない）。
    roots = [str(Path(arg)) for arg in ns.files]
    manifest = {"version": 2, "roots": roots, "files": files}

    out_path = Path(ns.out)
    out_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return 0


def cmd_verify(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="goal_loop.py verify")
    parser.add_argument("manifest", help="lock で生成した manifest JSON")
    ns = parser.parse_args(argv)

    # manifest 読取・パース・v2 型検証をまとめて fail-closed（exit 2）にマップする。
    # read_text の OSError（欠落・読取不能）/ json の ValueError（JSONDecodeError は
    # ValueError サブクラス）/ parse_manifest_envelope の ValueError（非 dict・型不正・
    # 旧形式）を区別せず invalid manifest として拒否。旧形式フォールバックは作らない。
    try:
        raw = json.loads(Path(ns.manifest).read_text())
        roots, files = parse_manifest_envelope(raw)
    except (OSError, ValueError) as exc:
        print(f"invalid manifest: {exc}", file=sys.stderr)
        return 2

    # 列挙フェーズ: roots を再走査。rglob はジェネレータを即時実体化するため
    # symlink ループ・サブディレクトリ権限エラー由来の OSError はここで送出される。
    # 放置すると exit 1（fail-open）で握りつぶされるため exit 2 に倒す。
    try:
        paths = _collect_paths(roots)
    except OSError as exc:
        print(f"oracle scan failed: {exc}", file=sys.stderr)
        return 2

    # 再ハッシュフェーズ: 各ファイルを再ハッシュして current を構築。read_bytes の
    # OSError（削除・権限・列挙後の race）は current から除外 -> manifest にあって
    # current にない = 削除として verify_oracle_integrity が exit 2 で検出する。
    current: dict[str, str] = {}
    for p in paths:
        try:
            current[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        except OSError:
            pass

    result = verify_oracle_integrity(files, current)
    if result["ok"]:
        return 0

    for path in result["tampered"]:
        print(path, file=sys.stderr)
    return 2


def cmd_signature(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="goal_loop.py signature")
    parser.parse_args(argv)
    output = sys.stdin.read()
    print(failure_signature(output))
    return 0


HALT_EXIT_CODES = {None: 0, "stall": 3, "oscillation": 4}


def cmd_halt(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="goal_loop.py halt")
    parser.add_argument("history", help="signature を 1 行 1 個で追記した履歴ファイル")
    parser.add_argument("--stall-limit", type=int, default=3)
    parser.add_argument("--window", type=int, default=6)
    parser.add_argument("--max-period", type=int, default=3)
    ns = parser.parse_args(argv)

    path = Path(ns.history)
    if not path.is_file():
        print(f"history が読めない: {path}", file=sys.stderr)
        return 2
    history = [line.strip() for line in path.read_text().splitlines() if line.strip()]

    verdict = detect_convergence_halt(
        history,
        stall_limit=ns.stall_limit,
        window=ns.window,
        max_period=ns.max_period,
    )
    print(verdict if verdict else "none")
    return HALT_EXIT_CODES[verdict]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("usage: goal_loop.py {lock,verify,signature,halt} ...", file=sys.stderr)
        return 2

    command, rest = argv[0], argv[1:]
    if command == "lock":
        return cmd_lock(rest)
    if command == "verify":
        return cmd_verify(rest)
    if command == "signature":
        return cmd_signature(rest)
    if command == "halt":
        return cmd_halt(rest)

    print(f"unknown command: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
