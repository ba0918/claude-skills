#!/usr/bin/env python3
"""publication-protocol.md の破壊的状態遷移（Exit 0 / Recovery）の正本プリミティブ。

プロトコル本文は自然言語であり、本文を読む agent とテストが別々に手順を再実装すると
互いにドリフトする。main の ref 前進・checkout 同期・evidence promotion・crash 修復と
いう破壊的遷移はすべて本スクリプトの 1 実装に集約し、cycle / iterate / 回帰テストの
全員が同じコードパスを実行する。

サブコマンド:
  merge    prospective merge の作成（一時 detached worktree + --no-ff。main は不動）。
           成功時は expected/post SHA・worktree・staging パスを JSON で stdout に出力
  advance  前提条件の証明 → CAS → checkout 同期 → evidence promotion
  recover  durable marker（evidence-staging/{sha} = main HEAD）から未完了 publication を
           検出し、破壊的修復の安全性を証明できた場合のみ completion steps を再開する

exit codes:
  0  成功（merge: 作成完了 / advance: 前進+promotion 完了 / recover: 修復完了）
  2  実行不能（引数・環境・予期しない状態）
  3  terminal publish failure（前提条件不成立。main は無傷）
  4  CAS conflict（main が動いた。main・公開 evidence・staging は無傷）
  5  recover: 未完了 publication なし（durable marker 不在）
  6  recover: 破壊的修復の安全性を証明できない — 何も変更せず手動復旧を要求
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKER = os.path.join(HERE, "evidence_check.py")
STAGING_RELROOT = os.path.join(".agents", "artifacts", "reviews", "evidence-staging")
DEFAULT_RELDIR = os.path.join(".agents", "artifacts", "reviews", "evidence")


def git(repo, *args, check=True):
    return subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, text=True, check=check,
    )


def fail(code, message):
    print(f"publication_advance: {message}", file=sys.stderr)
    return code


def checker_passes(repo, evidence_dir, target_sha, contract):
    result = subprocess.run(
        [
            sys.executable, CHECKER,
            "--target-sha", target_sha,
            "--contract", contract,
            "--repo-root", repo,
            "--evidence-dir", evidence_dir,
        ],
        capture_output=True, text=True,
    )
    return result.returncode == 0


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


def promote(repo, staging, target_sha, contract):
    """copy → checker 検証 → staging 削除。冪等: 失敗時は staging を残す。"""
    default_dir = os.path.join(repo, DEFAULT_RELDIR)
    os.makedirs(default_dir, exist_ok=True)
    for name in sorted(os.listdir(staging)):
        if name.endswith(".json"):
            shutil.copyfile(
                os.path.join(staging, name), os.path.join(default_dir, name)
            )
    if not checker_passes(repo, default_dir, target_sha, contract):
        return False
    shutil.rmtree(staging)
    return True


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
    os.makedirs(staging, exist_ok=True)
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

    checkouts = branch_checkouts(repo, branch)
    foreign = [p for p in checkouts if p != repo]
    if foreign:
        return fail(3, f"terminal: {branch} is checked out outside the main tree: {foreign[0]}")
    checked_out_here = repo in checkouts
    if checked_out_here and not tree_clean(repo):
        return fail(3, "terminal: main tree is dirty; advancing would entangle local edits")
    if not os.path.isdir(staging):
        return fail(3, f"terminal: evidence staging missing: {staging}")
    if not checker_passes(repo, staging, post, args.contract):
        return fail(3, "terminal: staged evidence does not pass the checker")

    cas = git(repo, "update-ref", f"refs/heads/{branch}", post, expected, check=False)
    if cas.returncode != 0:
        return fail(4, f"cas-conflict: {branch} moved away from {expected[:12]}")

    if checked_out_here:
        git(repo, "reset", "-q", "--hard", f"refs/heads/{branch}")
    if not promote(repo, staging, post, args.contract):
        return fail(2, "promotion verification failed; staging preserved for repair")
    print(f"advanced {branch} to {post[:12]} and promoted evidence")
    return 0


def cmd_recover(args):
    repo = os.path.realpath(args.repo_root)
    branch = args.branch
    head = git(repo, "rev-parse", f"refs/heads/{branch}").stdout.strip()
    staging = os.path.join(repo, STAGING_RELROOT, head)
    if not os.path.isdir(staging):
        return fail(5, "no durable marker: no unfinished publication for the current HEAD")

    # 安全性の証明 1: staging evidence がいまも checker を通ること
    if not checker_passes(repo, staging, head, args.contract):
        return fail(6, "manual recovery required: staged evidence no longer passes the checker")

    checkouts = branch_checkouts(repo, branch)
    foreign = [p for p in checkouts if p != repo]
    if foreign:
        return fail(6, f"manual recovery required: {branch} is checked out outside the main tree: {foreign[0]}")

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
            added = git(
                repo, "diff", "--name-only", "--diff-filter=A", expected, head
            ).stdout.split()
            for path in added:
                if os.path.lexists(os.path.join(repo, path)):
                    return fail(6, f"manual recovery required: untracked file collides with the merged tree: {path}")
            git(repo, "reset", "-q", "--hard", f"refs/heads/{branch}")

    if not promote(repo, staging, head, args.contract):
        return fail(2, "promotion verification failed; staging preserved for repair")
    print(f"recovered publication of {head[:12]} (checkout synced, evidence promoted)")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo-root", required=True)
    common.add_argument("--branch", default="main")
    common.add_argument("--contract", default=None,
                        help="quality-gate contract path (default: <repo-root>/skills/shared/references/quality-gate-contract.md)")

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
    if args.contract is None:
        args.contract = os.path.join(
            args.repo_root, "skills", "shared", "references", "quality-gate-contract.md"
        )
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
