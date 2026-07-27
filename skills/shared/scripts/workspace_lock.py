"""Working-tree occupancy lock (the implementation of workspace-lock.md).

The core implementation loop (cycle -> plan-implement -> iterate) writes directly into a
shared checkout and never checks whether another session is already working there. Two
sessions in the same tree overwrite each other's edits, tests run against the other side's
half-finished state, and commits are cut across both. Every one of those is only visible
much later, and the cause is hard to recover.

This module is the occupancy check that is missing. It is deliberately **always on and not
configurable**: the cost is effectively zero, and a switch would leave the accident in
place exactly in the environments where the switch was thrown.

The lock lives at `.agents/runtime/workspace.claim`, which makes the granularity fall out
of the location itself — the runtime area is per working tree, so one working tree is one
lock. No hash, no key design. **The resource identity is the working-tree path, not the
branch**: the same checkout collides across branches, and separate worktrees never collide
even on the same branch.

The claim semantics (atomic claim, pid + started_at, mode 0600, trap plus orphan recovery)
are already defined by polling-pattern.md §6.3-6.4 and are **referenced, not reimplemented**.
What is new here is only which resource is locked and who locks it.
"""
from __future__ import annotations

import errno
import json
import os
import secrets
import subprocess
from pathlib import Path

CLAIM_REL = Path(".agents/runtime/workspace.claim")
CLAIM_MODE = 0o600

# claim() outcomes. Displayed verbatim, and named in workspace-lock.md.
ACQUIRED = "ACQUIRED"
STALE_RECLAIMED = "STALE_RECLAIMED"
LOCK_HELD = "LOCK_HELD"
UNAVAILABLE = "UNAVAILABLE"


class ClaimResult:
    """The outcome of a claim attempt.

    `ok` is what a caller branches on. It is True for UNAVAILABLE as well, because the
    contract is **fail-open**: a tree where the runtime area cannot be created is no less
    safe than it was before this lock existed, and stopping there would break setups that
    used to work.
    """

    def __init__(self, outcome, token=None, holder=None, warnings=None):
        self.outcome = outcome
        self.token = token
        self.holder = holder or {}
        self.warnings = warnings or []

    @property
    def ok(self):
        return self.outcome != LOCK_HELD

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"ClaimResult({self.outcome}, token={self.token!r})"


def claim_path(repo):
    return Path(repo) / CLAIM_REL


def pid_is_alive(pid):
    """Whether the process still exists.

    A PermissionError means the pid exists under another user — alive. Treating it as dead
    would let one user steal another user's claim, which the contract forbids outright.
    """
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def current_branch(repo):
    """The branch name, recorded for the conflict display. Never used for identity."""
    try:
        proc = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(repo), capture_output=True, text=True,
            env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
        )
    except (OSError, ValueError):
        return None
    name = proc.stdout.strip()
    return name or None


def read_claim(repo):
    """The claim record, or None when absent. An unreadable record returns None."""
    path = claim_path(repo)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_record(path, record, warnings):
    """Create the claim exclusively. Returns False when it already exists."""
    payload = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, CLAIM_MODE)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(payload)
    _verify_mode(path, warnings)
    return True


def _verify_mode(path, warnings):
    """0600 is best-effort: warn where the mode is not honored, never stop.

    Same posture as polling-pattern.md §6.4 — on a DrvFs / ACL-backed mount the mode does
    not stick, and refusing to run there would disable the lock precisely on the platforms
    this repository is used from.
    """
    try:
        mode = os.stat(path).st_mode & 0o777
    except OSError:
        return
    if mode != CLAIM_MODE:
        warnings.append(
            f"claim file mode is {mode:04o}, not {CLAIM_MODE:04o} "
            "(the filesystem does not honor it; continuing best-effort)"
        )


def status(repo):
    """The current holder plus a liveness flag, or None when unclaimed."""
    record = read_claim(repo)
    if record is None:
        return None
    return {**record, "alive": pid_is_alive(record.get("pid"))}


def claim(repo, skill, branch=None, pid=None, now=None, token=None):
    """Take the working tree, or report who holds it.

    A dead holder is reclaimed and reported as STALE_RECLAIMED so the operator can see that
    a crashed session was cleaned up rather than silently ignored. **A live holder is never
    taken over** — there is no force path in this module, by design.
    """
    repo = Path(repo)
    warnings = []
    path = claim_path(repo)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        # fail-open: the lock is an addition, so an environment that cannot host it keeps
        # its previous (unimproved, but not worsened) safety.
        warnings.append(
            f"cannot create {CLAIM_REL.parent} ({errno.errorcode.get(exc.errno, exc.errno)}); "
            "continuing without the workspace lock"
        )
        return ClaimResult(UNAVAILABLE, warnings=warnings)

    record = {
        "pid": os.getpid() if pid is None else pid,
        "started_at": now or _now(),
        "skill": skill,
        "branch": current_branch(repo) if branch is None else branch,
        "token": token or secrets.token_hex(16),
    }

    if _write_record(path, record, warnings):
        return ClaimResult(ACQUIRED, token=record["token"], warnings=warnings)

    holder = read_claim(repo)
    if holder is None:
        warnings.append("existing claim is unreadable; treating it as stale")
    elif pid_is_alive(holder.get("pid")):
        return ClaimResult(LOCK_HELD, holder=holder, warnings=warnings)

    # The holder is dead (or its record is unreadable). Replace it atomically, then confirm
    # the file really carries our token: two reclaimers racing here would otherwise both
    # believe they own the tree.
    tmp = path.with_name(path.name + f".tmp.{record['pid']}")
    try:
        fd = os.open(tmp, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, CLAIM_MODE)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        os.replace(tmp, path)
    except OSError as exc:
        _unlink(tmp)
        warnings.append(f"failed to reclaim the stale lock ({exc}); continuing without it")
        return ClaimResult(UNAVAILABLE, warnings=warnings)

    _verify_mode(path, warnings)
    winner = read_claim(repo)
    if not winner or winner.get("token") != record["token"]:
        return ClaimResult(LOCK_HELD, holder=winner or {}, warnings=warnings)
    return ClaimResult(STALE_RECLAIMED, token=record["token"],
                       holder=holder or {}, warnings=warnings)


def release(repo, token):
    """Drop the claim. Only the holder of `token` may release it.

    Returning False rather than raising keeps the trap path simple: a release that arrives
    after an orphan sweep already reclaimed the tree must not take down the shutdown path.
    """
    record = read_claim(repo)
    if record is None or not token or record.get("token") != token:
        return False
    try:
        claim_path(repo).unlink()
    except OSError:
        return False
    return True


def _unlink(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cli(argv=None):
    """CLI entry point.

    Skill prose says "take the working tree per the contract" and must not have to invent an
    invocation. Without this, every caller improvises its own `python3 -c "import ..."` line
    and the calls drift apart — measured: two independent executors each wrote a different one.

    Exit code is the branch a caller needs: non-zero **only** for `LOCK_HELD`. `UNAVAILABLE`
    exits 0 because the contract is fail-open.
    """
    import argparse

    ap = argparse.ArgumentParser(description="Working-tree occupancy lock")
    sub = ap.add_subparsers(dest="command", required=True)

    take = sub.add_parser("claim", help="take the working tree")
    take.add_argument("--repo", default=".")
    take.add_argument("--skill", required=True, help="the claiming skill's name")

    drop = sub.add_parser("release", help="drop a claim held by --token")
    drop.add_argument("--repo", default=".")
    drop.add_argument("--token", required=True)

    show = sub.add_parser("status", help="who holds the tree, and is that process alive")
    show.add_argument("--repo", default=".")

    args = ap.parse_args(argv)

    if args.command == "claim":
        result = claim(args.repo, args.skill)
        print(json.dumps({"outcome": result.outcome, "token": result.token,
                          "holder": result.holder, "warnings": result.warnings},
                         ensure_ascii=False))
        if result.outcome == LOCK_HELD:
            print(describe(result))
            return 1
        return 0

    if args.command == "release":
        released = release(args.repo, args.token)
        print(json.dumps({"released": released}, ensure_ascii=False))
        return 0

    print(json.dumps(status(args.repo), ensure_ascii=False))
    return 0


def describe(result):
    """The one-block conflict display named by workspace-lock.md §Conflict.

    Only two options are offered. There is deliberately no "take it anyway" — an automatic
    steal is the failure this lock exists to prevent.
    """
    if result.outcome != LOCK_HELD:
        return ""
    h = result.holder or {}
    return (
        "LOCK_HELD: another session is working in this tree\n"
        f"  skill      : {h.get('skill', '(unknown)')}\n"
        f"  pid        : {h.get('pid', '(unknown)')}\n"
        f"  branch     : {h.get('branch', '(unknown)')}\n"
        f"  started_at : {h.get('started_at', '(unknown)')}\n"
        "  options    : wait for that session to finish, or — after confirming it is "
        f"dead — delete {CLAIM_REL}"
    )


if __name__ == "__main__":
    raise SystemExit(_cli())
