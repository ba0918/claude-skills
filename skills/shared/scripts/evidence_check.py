#!/usr/bin/env python3
"""quality-gate-contract §2 の縦切り検証: verified(対象SHA, 契約版) → publishable.

証跡レコード（machine_verified.json / semantic_reviewed.json）が「現在の対象 SHA と
公開済み契約版」に束縛された有効な証跡かを機械判定し、publishable 可否を exit code で返す。
schema と exit code 契約の正本は skills/shared/references/evidence-format.md。

exit 0 = publishable / exit 1 = not publishable（欠落・失効・無効） / exit 2 = 検査自体が実行不能。
証跡不在は skip ではなく否定判定（exit 1）に落ちる。fail-closed であり vacuous pass は構造的に無い。
"""

import argparse
import json
import os
import re
import subprocess
import sys

CONTRACT_NAME = "quality-gate-contract"
CONTRACT_RELPATH = os.path.join("skills", "shared", "references", "quality-gate-contract.md")
DEFAULT_EVIDENCE_RELPATH = os.path.join(".agents", "artifacts", "reviews", "evidence")
STATES = ("machine_verified", "semantic_reviewed")

# §Contract Identity の宣言行から公開版を読む。散文の変化に強いよう、識別子+版の連なりだけを見る
_VERSION_DECL = re.compile(r"`quality-gate-contract\s+(\d+\.\d+\.\d+)`")
_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


class CheckBroken(Exception):
    """検査の前提が満たせない（exit 2）。証跡への否定判定（exit 1）とは区別する。"""


def read_published_version(contract_path):
    try:
        text = open(contract_path, encoding="utf-8").read()
    except OSError as exc:
        raise CheckBroken(f"contract file unreadable: {contract_path} ({exc})")
    found = _VERSION_DECL.findall(text)
    if not found:
        raise CheckBroken(f"contract file declares no version: {contract_path}")
    if len(set(found)) > 1:
        raise CheckBroken(f"contract file declares conflicting versions {sorted(set(found))}: {contract_path}")
    return found[0]


def resolve_head_sha(repo_root):
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root, capture_output=True, text=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CheckBroken(f"cannot resolve target SHA via git rev-parse HEAD: {exc}")
    sha = proc.stdout.strip()
    if not _FULL_SHA.match(sha):
        raise CheckBroken(f"git rev-parse HEAD returned a non-SHA value: {sha!r}")
    return sha


def judge_state(evidence_dir, state, target_sha, published_version):
    """1 状態の証跡を判定する。返り値: (valid: bool, reason: str)。

    欠落・失効・無効はすべて否定判定として理由文字列で区別する（契約 §2:
    expired / invalid は absent と同一に扱い、遷移をブロックする）。
    """
    path = os.path.join(evidence_dir, f"{state}.json")
    if not os.path.isfile(path):
        return False, "absent (no evidence record)"
    try:
        record = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return False, f"invalid (unreadable record: {exc})"
    if not isinstance(record, dict):
        return False, "invalid (record is not an object)"
    if record.get("schema_version") != 1:
        return False, f"invalid (unknown schema_version: {record.get('schema_version')!r})"
    if record.get("state") != state:
        return False, f"invalid (state field {record.get('state')!r} does not match file {state})"
    if record.get("contract") != CONTRACT_NAME:
        return False, f"invalid (contract {record.get('contract')!r} is not {CONTRACT_NAME})"
    recorded_sha = record.get("target_sha")
    if not isinstance(recorded_sha, str) or not _FULL_SHA.match(recorded_sha):
        return False, f"invalid (target_sha is not a full 40-hex id: {recorded_sha!r})"
    grounds = record.get("grounds")
    if not isinstance(grounds, str) or not grounds.strip():
        return False, "invalid (grounds is empty — evidence must name what produced it)"
    if record.get("contract_version") != published_version:
        return False, (
            f"invalid (contract_version {record.get('contract_version')!r} does not resolve "
            f"to the published version {published_version})"
        )
    if recorded_sha != target_sha:
        return False, f"expired (bound to {recorded_sha[:12]}, target is {target_sha[:12]})"
    return True, "valid"


def run(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", default=".", help="repository root (default: cwd)")
    parser.add_argument("--evidence-dir", default=None,
                        help=f"evidence directory (default: <repo-root>/{DEFAULT_EVIDENCE_RELPATH})")
    parser.add_argument("--target-sha", default=None,
                        help="full 40-hex target SHA (default: git rev-parse HEAD)")
    parser.add_argument("--contract", default=None,
                        help=f"contract file path (default: <repo-root>/{CONTRACT_RELPATH})")
    args = parser.parse_args(argv)

    contract_path = args.contract or os.path.join(args.repo_root, CONTRACT_RELPATH)
    evidence_dir = args.evidence_dir or os.path.join(args.repo_root, DEFAULT_EVIDENCE_RELPATH)

    published_version = read_published_version(contract_path)
    if args.target_sha is not None:
        if not _FULL_SHA.match(args.target_sha):
            raise CheckBroken(f"--target-sha must be a full 40-hex id, got: {args.target_sha!r}")
        target_sha = args.target_sha
    else:
        target_sha = resolve_head_sha(args.repo_root)

    print(f"target: {target_sha}")
    print(f"contract: {CONTRACT_NAME} {published_version}")
    if not os.path.isdir(evidence_dir):
        print(f"evidence dir: {evidence_dir} (missing)")
    else:
        print(f"evidence dir: {evidence_dir}")

    all_valid = True
    for state in STATES:
        valid, reason = judge_state(evidence_dir, state, target_sha, published_version)
        mark = "✓" if valid else "✗"
        print(f"{mark} {state}: {reason}")
        all_valid = all_valid and valid

    if all_valid:
        print("publishable: yes")
        return 0
    print("publishable: no")
    return 1


def main():
    try:
        sys.exit(run())
    except CheckBroken as exc:
        print(f"check broken: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
