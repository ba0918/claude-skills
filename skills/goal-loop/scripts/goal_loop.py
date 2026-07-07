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
      ファイル群を読んで oracle_manifest を JSON 保存する。
      glob 展開は shell に任せる。ディレクトリを渡すと再帰的に
      配下の全ファイルを対象にする。

  verify MANIFEST.json
      現在のファイル状態を再ハッシュして verify_oracle_integrity を行う。
      ok なら exit 0。tampered なら該当パスを 1 行ずつ stderr に出し exit 2。

      **非対称性の明記**: 純関数 verify_oracle_integrity は
      manifest/current の両方向の差分（変更・削除・追加）を検出できるが、
      この CLI の `current` は manifest に記録されたパスのみを再ハッシュして
      構築する。そのため、manifest 記録パスの親ディレクトリ配下に
      "新規追加" されたファイル（lock 後に置かれた新しいファイル）は
      current 集合に現れず検出されない。lock 時にディレクトリ指定で
      列挙された「追加」検出は、oracle_manifest/verify_oracle_integrity を
      直接呼ぶ側（unittest 等）でのみ保証される契約であり、CLI verify は
      「manifest に載っているものが変更・消失していないか」のみを見る。

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


def _collect_paths(args: list[str]) -> list[Path]:
    """引数（ファイル or ディレクトリ）を実ファイルパスの一覧に展開する。

    ディレクトリは再帰的に配下の全ファイルを対象にする。glob 展開自体は
    shell に任せる想定（このリストは既に個別パスとして渡ってくる）。
    """
    def _is_build_artifact(p: Path) -> bool:
        # oracle 実行自体が生成・更新するビルド生成物（bytecode キャッシュ）は
        # oracle の意味を定義しないため lock から除外する。含めると oracle 実行の
        # たびに hash が揺れて oracle_tampered の誤検出になる。
        return p.suffix == ".pyc" or "__pycache__" in p.parts

    paths: list[Path] = []
    for arg in args:
        p = Path(arg)
        if p.is_dir():
            for sub in sorted(p.rglob("*")):
                if sub.is_file() and not _is_build_artifact(sub):
                    paths.append(sub)
        elif not _is_build_artifact(p):
            paths.append(p)
    return paths


def cmd_lock(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="goal_loop.py lock")
    parser.add_argument("files", nargs="+", help="oracle_files（ファイル or ディレクトリ）")
    parser.add_argument("--out", required=True, help="manifest JSON の出力先")
    ns = parser.parse_args(argv)

    paths = _collect_paths(ns.files)
    contents = {str(p): p.read_bytes() for p in paths}
    manifest = oracle_manifest(contents)

    out_path = Path(ns.out)
    out_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return 0


def cmd_verify(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="goal_loop.py verify")
    parser.add_argument("manifest", help="lock で生成した manifest JSON")
    ns = parser.parse_args(argv)

    manifest: dict[str, str] = json.loads(Path(ns.manifest).read_text())

    current: dict[str, str] = {}
    for path in manifest:
        p = Path(path)
        if p.exists():
            current[path] = hashlib.sha256(p.read_bytes()).hexdigest()
        # 存在しない場合は current に含めない -> verify_oracle_integrity が
        # "manifest にあるが current にない" = 削除として検出する。

    result = verify_oracle_integrity(manifest, current)
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
        print("usage: goal_loop.py {lock,verify,signature} ...", file=sys.stderr)
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
