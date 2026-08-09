#!/usr/bin/env python3
"""publication-protocol.md の破壊的状態遷移（Exit 0 / Recovery）の正本プリミティブ。

プロトコル本文は自然言語であり、本文を読む agent とテストが別々に手順を再実装すると
互いにドリフトする。main の ref 前進・checkout 同期・crash 修復という破壊的遷移は
すべて本スクリプトの 1 実装に集約し、cycle / iterate / 回帰テストの全員が同じ
コードパスを実行する。

evidence 記帳層の解体（#308）に伴い、staging ディレクトリは検証済み証跡の置き場で
はなく「この merge は意図された」という記録（merge-intent marker）の durable marker
として機能する。品質ゲートの内容検査は除去され、品質は呼び出し元のレビューが担う。
compare-and-swap・ロック保持・merge の形・作業ツリーの安全という構造チェックは
すべて存続する。

サブコマンド:
  merge    prospective merge の作成（一時 detached worktree + --no-ff。main は不動）。
           成功時は expected/post SHA・worktree・staging パスを JSON で stdout に出力し、
           staging に merge-intent marker を書く
  advance  前提条件の証明 → CAS → checkout 同期 → durable marker の除去
  recover  durable marker（staging/{sha} = main HEAD）から未完了 publication を
           検出し、破壊的修復の安全性を証明できた場合のみ completion steps を再開する

exit codes:
  0  成功（merge: 作成完了 / advance: 前進+marker 除去完了 / recover: 修復完了）
  2  実行不能（commit point 前の引数・環境エラー。main は無傷）
  3  terminal publish failure（前提条件不成立。main は無傷）
  4  CAS conflict（main が動いた。main・staging は無傷）
  5  recover: 未完了 publication なし（durable marker 不在）
  6  recover: 破壊的修復の安全性を証明できない — 何も変更せず手動復旧を要求
  7  commit point 通過後の completion 失敗（main は前進済み。staging = durable marker を
     保存。publish failure ではない — recover で前方修復する。rollback はしない）
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

STAGING_RELROOT = os.path.join(".agents", "artifacts", "reviews", "evidence-staging")
CLAIM_REL = os.path.join(".agents", "runtime", "workspace.claim")
MARKER_NAME = "merge-intent.json"


def git(repo, *args, check=True):
    return subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True, check=check,
    )


def fail(code, message):
    print(f"publication_advance: {message}", file=sys.stderr)
    return code


def lock_held(repo, token):
    """caller が workspace lock（workspace-lock.md）を保持している証明。

    証明 = 渡された token が live claim（.agents/runtime/workspace.claim）の
    token と一致すること。散文で lock 保持を要求するだけでは保証にならない
    ため、破壊的経路はコード側でこの証明を要求する。
    """
    if not token:
        return False
    try:
        with open(os.path.join(repo, CLAIM_REL), encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, ValueError):
        return False
    return record.get("token") == token


def branch_checkouts(repo, branch):
    """branch が checkout されている worktree の実パス一覧。"""
    out = git(repo, "worktree", "list", "--porcelain").stdout
    paths, current = [], None
    for line in out.splitlines():
        if line.startswith("worktree "):
            current = line[len("worktree "):]
        elif line == f"branch refs/heads/{branch}" and current:
            paths.append(os.path.realpath(current))
    return paths


def tree_clean(repo):
    return git(repo, "status", "--porcelain").stdout == ""


def write_marker(staging, post, expected, branch):
    """merge-intent marker を staging へ書く。staging の存在自体が durable marker で、
    中身は「この merge は意図された」ことを記録する（証跡ではない）。"""
    marker = {
        "schema_version": 1,
        "kind": "merge-intent",
        "post_merge_sha": post,
        "expected_main_sha": expected,
        "branch": branch,
        "created_at": (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        ),
    }
    with open(os.path.join(staging, MARKER_NAME), "w", encoding="utf-8") as handle:
        json.dump(marker, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def marker_readable(staging):
    """未完了 publication の証明 = merge-intent record が読めること。

    staging ディレクトリの存在だけでは証明にならない: 空ディレクトリや書き損じを
    未完了 publication と見なすと、advance がそれを前進の許可として受け取り、
    recover が「回復成功」を報告して無関係なディレクトリを削除してしまう。
    """
    try:
        with open(os.path.join(staging, MARKER_NAME), encoding="utf-8") as handle:
            json.load(handle)
    except (OSError, ValueError):
        return False
    return True


def clear_marker(staging):
    """durable marker（staging dir）を除去する。冪等でない: 存在しない dir は呼び出し側の責務。"""
    shutil.rmtree(staging)


def cmd_merge(args):
    repo = os.path.realpath(args.repo_root)
    branch = args.branch
    expected = git(repo, "rev-parse", f"refs/heads/{branch}").stdout.strip()
    tmp = args.tmp_merge_root or f"{repo}-pubmerge-{expected[:12]}"
    if os.path.exists(tmp):
        return fail(2, f"temporary merge worktree already exists: {tmp} (discard stale state first)")
    git(repo, "worktree", "add", "--detach", "-q", tmp, expected)
    merge = git(
        tmp, "merge", "--no-ff", "-q",
        "-m", f"merge {args.satellite_branch}",
        args.satellite_branch, check=False,
    )
    if merge.returncode != 0:
        git(tmp, "merge", "--abort", check=False)
        git(repo, "worktree", "remove", "--force", tmp, check=False)
        return fail(3, "terminal: merge conflict with the satellite branch; main untouched")
    post = git(tmp, "rev-parse", "HEAD").stdout.strip()
    staging = os.path.join(repo, STAGING_RELROOT, post)
    try:
        os.makedirs(staging, exist_ok=True)
        write_marker(staging, post, expected, branch)
    except OSError as exc:
        # marker を書けないまま tmp worktree を残すと、次回起動が
        # 「temporary merge worktree already exists」で詰まる
        shutil.rmtree(staging, ignore_errors=True)
        git(repo, "worktree", "remove", "--force", tmp, check=False)
        return fail(2, f"cannot record the merge intent under {staging}: {exc}")
    print(json.dumps({
        "expected_main_sha": expected,
        "post_merge_sha": post,
        "tmp_merge_root": tmp,
        "evidence_staging": staging,
    }))
    return 0


def cmd_advance(args):
    repo = os.path.realpath(args.repo_root)
    branch = args.branch
    post, expected = args.post_merge_sha, args.expected_main_sha
    staging = args.evidence_staging or os.path.join(repo, STAGING_RELROOT, post)

    if not lock_held(repo, args.lock_token):
        return fail(3, "terminal: workspace lock not proven (--lock-token missing or not "
                       "matching the claim); ref advance and durable-marker removal mutate "
                       "shared state and require exclusion")
    parent = git(repo, "rev-parse", f"{post}^1", check=False)
    if parent.returncode != 0 or parent.stdout.strip() != expected:
        return fail(3, f"terminal: post-merge SHA is not derived from the expected {branch} "
                       "SHA (first parent mismatch); a stale or miswired caller must not "
                       "move the ref")
    if git(repo, "rev-parse", f"{post}^2", check=False).returncode != 0:
        return fail(3, "terminal: post-merge SHA is not a merge commit; only prospective "
                       "merges produced by the merge subcommand may advance the ref")
    checkouts = branch_checkouts(repo, branch)
    foreign = [p for p in checkouts if p != repo]
    if foreign:
        return fail(3, f"terminal: {branch} is checked out outside the main tree: {foreign[0]}")
    checked_out_here = repo in checkouts
    if checked_out_here and not tree_clean(repo):
        return fail(3, "terminal: main tree is dirty; advancing would entangle local edits")
    # marker 除去時に staging を rmtree するため、呼び出し側の任意パスをそのまま
    # 受けると誤配線・侵害された delegate が無関係ディレクトリを削除できてしまう。
    # --evidence-staging は正規の evidence-staging/{post_sha} との完全一致証明としてのみ受ける
    canonical = os.path.join(repo, STAGING_RELROOT, post)
    if os.path.islink(staging) or os.path.realpath(staging) != os.path.realpath(canonical):
        return fail(3, "terminal: evidence staging must be the canonical "
                       f"evidence-staging/{{post_merge_sha}} directory ({canonical}); "
                       "arbitrary staging paths are refused because marker removal deletes "
                       "the staging directory")
    if not marker_readable(staging):
        return fail(3, "terminal: durable marker missing or unreadable "
                       f"({os.path.join(staging, MARKER_NAME)}); only a recorded merge "
                       "intent may advance the ref")

    cas = git(repo, "update-ref", f"refs/heads/{branch}", post, expected, check=False)
    if cas.returncode != 0:
        return fail(4, f"cas-conflict: {branch} moved away from {expected[:12]}")

    # commit point 通過。以降の失敗は publish failure ではなく未完了 completion であり、
    # rollback せず exit 7（durable marker 保存）で recover に委ねる
    try:
        if checked_out_here:
            git(repo, "reset", "-q", "--hard", f"refs/heads/{branch}")
        clear_marker(staging)
    except (subprocess.CalledProcessError, OSError) as exc:
        return fail(7, "completion interrupted after the commit point "
                       f"(staging preserved; run recover): {exc}")
    print(f"advanced {branch} to {post[:12]} and cleared the merge-intent marker")
    return 0


def cmd_recover(args):
    repo = os.path.realpath(args.repo_root)
    branch = args.branch
    head = git(repo, "rev-parse", f"refs/heads/{branch}").stdout.strip()
    staging = os.path.join(repo, STAGING_RELROOT, head)
    if not marker_readable(staging):
        return fail(5, "no durable marker: no unfinished publication for the current HEAD")

    checkouts = branch_checkouts(repo, branch)
    foreign = [p for p in checkouts if p != repo]
    if foreign:
        return fail(6, f"manual recovery required: {branch} is checked out outside the main tree: {foreign[0]}")

    # 修復は checkout と公開 singleton の両方を変異させうるため、reset の有無に
    # かかわらず lock 証明を要求する（marker 除去だけでも共有状態の書換え）
    if not lock_held(repo, args.lock_token):
        return fail(6, "manual recovery required: workspace lock not proven "
                       "(--lock-token missing or not matching the claim); repair mutates "
                       "the checkout and the published state and requires exclusion")

    try:
        if repo in checkouts:
            synced = (
                git(repo, "diff", "--quiet", head, check=False).returncode == 0
                and git(repo, "diff", "--cached", "--quiet", head, check=False).returncode == 0
            )
            if not synced:
                # 安全性の証明 2: index と worktree が pre-CAS tree（{head}^1）そのままで
                # あること。それ以外の差分は crash 後の本物の編集かもしれず、破壊できない
                parent = git(repo, "rev-parse", f"{head}^1", check=False)
                if parent.returncode != 0:
                    return fail(6, "manual recovery required: HEAD has no first parent to compare against")
                expected = parent.stdout.strip()
                if git(repo, "diff", "--quiet", expected, check=False).returncode != 0:
                    return fail(6, "manual recovery required: worktree differs from the pre-CAS tree (possible post-crash edits)")
                if git(repo, "diff", "--cached", "--quiet", expected, check=False).returncode != 0:
                    return fail(6, "manual recovery required: index differs from the pre-CAS tree (possible post-crash staging)")
                # 安全性の証明 3: merge が新規に持ち込むパスが untracked として存在しないこと
                # -z: NUL 区切り + quotePath 無効。空白や非 ASCII を含むパス名を
                # 空白 split で分解すると衝突検知が素通りし reset がファイルを壊す
                added = git(
                    repo, "diff", "--name-only", "--diff-filter=A", "-z", expected, head
                ).stdout.split("\0")
                for path in filter(None, added):
                    if os.path.lexists(os.path.join(repo, path)):
                        return fail(6, f"manual recovery required: untracked file collides with the merged tree: {path}")
                git(repo, "reset", "-q", "--hard", f"refs/heads/{branch}")

        clear_marker(staging)
    except (subprocess.CalledProcessError, OSError) as exc:
        return fail(7, "completion interrupted during repair "
                       f"(staging preserved; rerun recover): {exc}")
    print(f"recovered publication of {head[:12]} (checkout synced, marker cleared)")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo-root", required=True)
    common.add_argument("--branch", default="main")
    common.add_argument("--lock-token", default=None,
                        help="workspace lock token proving the caller holds the claim; "
                             "required for every mutating path (ref advance, checkout "
                             "sync, durable-marker removal)")

    merge = sub.add_parser("merge", parents=[common])
    merge.add_argument("--satellite-branch", required=True)
    merge.add_argument("--tmp-merge-root", default=None,
                       help="temp worktree path (default: <repo-root>-pubmerge-<sha12>)")

    advance = sub.add_parser("advance", parents=[common])
    advance.add_argument("--post-merge-sha", required=True)
    advance.add_argument("--expected-main-sha", required=True)
    advance.add_argument("--evidence-staging", default=None,
                         help="staging dir (default: <repo-root>/.agents/artifacts/reviews/evidence-staging/<post-merge-sha>)")

    sub.add_parser("recover", parents=[common])

    args = parser.parse_args()
    try:
        if args.command == "merge":
            return cmd_merge(args)
        if args.command == "advance":
            return cmd_advance(args)
        return cmd_recover(args)
    except subprocess.CalledProcessError as exc:
        return fail(2, f"git failure: {exc.stderr or exc}")


if __name__ == "__main__":
    sys.exit(main())
