#!/usr/bin/env python3
"""GitHub Issue polling adapter の純関数・ローカル状態操作・薄い JSON CLI。"""

from __future__ import annotations

import argparse
import datetime as dt
import errno
import fcntl
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import uuid


class FailClosed(ValueError):
    """安全側に停止すべき入力・状態異常。"""


class LockBusy(RuntimeError):
    """別 owner が claim を保持している。"""


MISSING = "MISSING"
NO_ORACLE = "NO_ORACLE"
UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
TRANSIENT = {"network", "rate_limit", "timeout", "lock"}
PERMANENT = {
    "test", "compile", "abort", "lgtm_parse_fail", "sanitize_failed",
    "security", "not_found", "tool_missing", "unknown",
}
UNSUPPORTED_FS = {"nfs", "nfs4", "cifs", "smb", "smbfs", "tmpfs", "9p", "drvfs"}


def warn(message):
    print(f"warn: {message}", file=sys.stderr)


def _unfenced_lines(text):
    fenced = False
    result = []
    for line in (text or "").splitlines():
        if re.match(r"^\s*(```|~~~)", line):
            fenced = not fenced
            continue
        if not fenced:
            result.append(line)
    return result


def _section(text, heading):
    lines = _unfenced_lines(text)
    start = None
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start = index + 1
            break
    if start is None:
        return None
    end = len(lines)
    for index in range(start, len(lines)):
        if re.match(r"^#{1,2}\s+", lines[index]):
            end = index
            break
    return lines[start:end]


def parse_self_drive_verdict(body):
    """自走可否節を厳密に解釈する。"""
    section = _section(body, "## 自走可否")
    if section is None:
        return "MISSING"
    verdict_lines = [line for line in section if line.startswith("判定:")]
    if not verdict_lines:
        return "MISSING"
    matches = [re.fullmatch(r"判定:\s*(\S+)\s*", line) for line in verdict_lines]
    if any(match is None for match in matches):
        return "AMBIGUOUS"
    values = [match.group(1) for match in matches]
    if len(set(values)) != 1:
        return "AMBIGUOUS"
    return {"自走可": "ALLOWED", "自走不可": "FORBIDDEN"}.get(values[0], "AMBIGUOUS")


def parse_change_targets(body):
    """変更対象節から安全な相対パスを順序維持で抽出する。"""
    section = _section(body, "## 変更対象")
    if section is None:
        return MISSING
    paths = []
    for line in section:
        match = re.match(r"^\s*[-*]\s+(.+?)\s*$", line)
        if not match:
            continue
        value = match.group(1).strip()
        if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
            value = value[1:-1].strip()
        if not re.fullmatch(r"[A-Za-z0-9._\-/]+", value):
            continue
        if ".." in value or value.startswith("/"):
            return MISSING
        if value not in paths:
            paths.append(value)
    return paths or MISSING


def impact_units(paths, config, runner=subprocess.run):
    """外部 oracle を実行し、影響単位を返す。"""
    command = config.get("impact_command")
    if not command:
        return NO_ORACLE
    if command.count("{files}") != 1:
        raise FailClosed("impact_oracle_failed")
    expanded = command.replace("{files}", " ".join(shlex.quote(path) for path in paths))
    try:
        result = runner(expanded, shell=True, text=True, capture_output=True)
    except OSError as exc:
        raise FailClosed("impact_oracle_failed") from exc
    if result.returncode != 0:
        raise FailClosed("impact_oracle_failed")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def gate_0_decision(paths, config, runner=subprocess.run):
    """Gate 0 の許可または拒否理由を返す。"""
    globs = config.get("forbidden_path_globs", [])
    if isinstance(globs, str):
        globs = [item.strip() for item in globs.split(",") if item.strip()]
    if any(fnmatch.fnmatchcase(path, glob) for path in paths for glob in globs):
        return {"decision": "REJECT", "reason": "forbidden_path"}
    try:
        units = impact_units(paths, config, runner)
    except FailClosed as exc:
        return {"decision": "REJECT", "reason": str(exc)}
    if units == NO_ORACLE:
        return {"decision": "ALLOW", "impact_units": NO_ORACLE}
    if len(units) > int(config.get("max_impacted_units", 1)):
        return {"decision": "REJECT", "reason": "impact_too_wide", "impact_units": units}
    return {"decision": "ALLOW", "impact_units": units}


def state_of_failure(labels):
    """failure label の優先規則を適用する。"""
    labels = set(labels)
    if {"claude-failed-transient", "claude-failed-permanent"} <= labels:
        warn("invalid state: both failure labels present")
        return "permanent"
    if "claude-failed-transient" in labels:
        return "transient"
    if "claude-failed-permanent" in labels or "claude-failed" in labels:
        return "permanent"
    return None


def validate_slug(slug):
    """issue-N の raw N を正規化せず検証する。"""
    match = re.fullmatch(r"issue-([1-9][0-9]*)", slug)
    if not match:
        raise FailClosed("invalid issue_number")
    return int(match.group(1))


def classify_failure(kind):
    kind = kind if kind in TRANSIENT | PERMANENT else "unknown"
    return {"kind": kind, "classification": "transient" if kind in TRANSIENT else "permanent",
            "counts_failed_streak": kind != "lock"}


def mark_failed_labels(kind):
    if kind not in {"transient", "permanent"}:
        raise FailClosed("invalid failure kind")
    return [f"claude-failed-{kind}", "claude-failed"]


def sanitize_repo_slug(value):
    value = re.sub(r"[^a-zA-Z0-9._-]", "_", value)
    while ".." in value:
        value = value.replace("..", "__")
    return value


def normalize_git_url(url):
    """git remote URL を clone identity 用に正規化する。"""
    if not isinstance(url, str) or not re.fullmatch(r"[a-zA-Z0-9._\-/:@]+", url):
        raise FailClosed(f"invalid git remote url character set: {url!r}")
    if ".." in url:
        raise FailClosed(f"git remote url contains path traversal: {url!r}")
    value = url.lower().rstrip("/")
    match = re.fullmatch(r"git@([^:]+):(.+?)(?:\.git)?", value)
    if match:
        return f"https://{match.group(1)}/{match.group(2)}"
    if value.startswith("ssh://"):
        value = re.sub(r"^ssh://(?:git@)?", "https://", value)
    value = re.sub(r"\.git$", "", value).rstrip("/")
    return value


def write_atomic(path, content):
    """O_EXCL tmp、fsync、rename、親 fsync で永続化する。"""
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        data = content.encode("utf-8") if isinstance(content, str) else content
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(data)
            stream.flush()
        os.fsync(fd)
    finally:
        os.close(fd)
    try:
        os.replace(tmp, path)
        parent_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        if tmp.exists():
            tmp.unlink()


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _issue_number(value):
    value = str(value)
    if not re.fullmatch(r"[1-9][0-9]*", value):
        raise FailClosed("invalid issue_number")
    return int(value)


def _state_subdir(root, name):
    path = Path(root) / name
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def _valid_iso8601(value):
    if not isinstance(value, str):
        return False
    try:
        dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def retry_state(number, state_root):
    """retry state を検証し、破損時は隔離する。"""
    number = _issue_number(number)
    directory = _state_subdir(state_root, "retry")
    path = directory / f"{number}.json"
    streak = directory / f".{number}.corrupt-streak"
    empty = {"retry_count": 0, "last_failed_at": None, "run_id": None}
    if not path.exists():
        return empty
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise json.JSONDecodeError("object required", "", 0)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        warn(f"corrupt retry state: {path}: {exc}")
        consecutive = streak.exists()
        quarantine = directory / f"{number}.json.corrupt.{int(time.time())}"
        suffix = 0
        while quarantine.exists():
            suffix += 1
            quarantine = directory / f"{number}.json.corrupt.{int(time.time())}.{suffix}"
        os.replace(path, quarantine)
        if consecutive:
            raise FailClosed("retry state corruption")
        write_atomic(streak, b"1")
        return empty
    if streak.exists():
        streak.unlink()
    count = value.get("retry_count", 0)
    if type(count) is not int or not 0 <= count < 10000:
        warn("invalid retry_count; reset to 0")
        count = 0
    failed_at = value.get("last_failed_at")
    if failed_at is not None and not _valid_iso8601(failed_at):
        warn("invalid last_failed_at; ignored")
        failed_at = None
    run_id = value.get("run_id")
    # polling-adapter.md is intentionally stricter than error-kinds.md: UUID v4 only.
    if run_id is not None and (not isinstance(run_id, str) or not UUID4_RE.fullmatch(run_id)):
        warn("invalid run_id; ignored")
        run_id = None
    return {"retry_count": count, "last_failed_at": failed_at, "run_id": run_id}


def increment_retry(number, state_root, run_id):
    if not UUID4_RE.fullmatch(run_id or ""):
        raise FailClosed("invalid run_id")
    number = _issue_number(number)
    directory = _state_subdir(state_root, "retry")
    lock_path = directory / f"{number}.flock"
    with open(lock_path, "a+", encoding="utf-8") as lock:
        os.chmod(lock_path, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = retry_state(number, state_root)
        value = {"retry_count": current["retry_count"] + 1,
                 "last_failed_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
                 "run_id": run_id}
        write_atomic(directory / f"{number}.json", json.dumps(value, ensure_ascii=False) + "\n")
    return value


def claim_lock(number, state_root, owner_pid, now=None):
    """短命 CLI 向けに flock を RMW ガードとして claim owner を記録する。"""
    number, owner_pid = _issue_number(number), int(owner_pid)
    if owner_pid <= 0:
        raise FailClosed("invalid owner pid")
    directory = _state_subdir(state_root, "claim")
    path = directory / f"{number}.lock"
    # Why not hold flock until process exit: each subcommand exits immediately, so it
    # cannot represent the long-lived owner. The persisted live PID is the lease.
    with open(path, "a+", encoding="utf-8") as stream:
        os.chmod(path, 0o600)
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise LockBusy("LockBusy") from exc
        stream.seek(0)
        raw = stream.read().strip()
        try:
            existing = int(raw)
        except ValueError:
            existing = None
        age = (time.time() if now is None else now) - path.stat().st_mtime
        if existing and existing != owner_pid and _pid_alive(existing):
            raise LockBusy("LockBusy")
        if existing and existing != owner_pid and age < 300:
            raise LockBusy("LockBusy")
        if raw and existing is None and age < 300:
            raise LockBusy("LockBusy")
        stream.seek(0)
        stream.truncate()
        stream.write(str(owner_pid))
        stream.flush()
        os.fsync(stream.fileno())
    return {"status": "claimed", "number": number, "owner_pid": owner_pid, "path": str(path)}


def release_lock(number, state_root):
    path = Path(state_root) / "claim" / f"{_issue_number(number)}.lock"
    existed = path.exists()
    if existed:
        path.unlink()
    return {"released": existed, "path": str(path)}


def stale_locks(state_root, now=None):
    directory = _state_subdir(state_root, "claim")
    now = time.time() if now is None else now
    removed = []
    for path in sorted(directory.glob("*.lock")):
        try:
            pid = int(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            pid = None
        if now - path.stat().st_mtime >= 300 and (pid is None or not _pid_alive(pid)):
            path.unlink()
            removed.append({"number": int(path.stem), "path": str(path), "owner_pid": pid})
    return removed


def recovery_marker(action, state_root, number=None, now=None):
    directory = _state_subdir(state_root, "recovery")
    if action == "add":
        path = directory / str(_issue_number(number))
        write_atomic(path, b"")
        return {"added": True, "path": str(path)}
    if action == "delete":
        path = directory / str(_issue_number(number))
        existed = path.exists()
        if existed:
            path.unlink()
        return {"deleted": existed, "path": str(path)}
    now = time.time() if now is None else now
    result = []
    for path in sorted(directory.iterdir(), key=lambda item: int(item.name) if item.name.isdigit() else 10**30):
        if not re.fullmatch(r"[1-9][0-9]*", path.name) or not path.is_file():
            continue
        mtime = path.stat().st_mtime
        result.append({"number": int(path.name), "path": str(path), "mtime": mtime,
                       "expired": now - mtime >= 7 * 24 * 60 * 60})
    return result


def kill_files(state_root):
    root = Path(state_root).resolve()
    paths = [root / ".STOP.hard", root / ".STOP"]
    return [{"path": str(path), "exists": path.exists()} for path in paths]


def session_load(state_root):
    path = Path(state_root) / "session.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        warn(f"corrupt session state: {exc}")
        os.replace(path, path.with_name(f"session.json.corrupt.{int(time.time())}"))
        return None


def session_save(state_root, value):
    path = Path(state_root) / "session.json"
    write_atomic(path, json.dumps(value, ensure_ascii=False) + "\n")
    return value


def filesystem_type(path):
    """マウント表から最長一致するファイルシステム種別を得る（モック可能）。"""
    resolved = str(Path(path).resolve())
    if sys.platform.startswith("linux"):
        candidates = []
        with open("/proc/self/mounts", encoding="utf-8") as mounts:
            for line in mounts:
                fields = line.split()
                if len(fields) < 3:
                    continue
                mountpoint = fields[1].replace("\\040", " ")
                if resolved == mountpoint or resolved.startswith(mountpoint.rstrip("/") + "/"):
                    candidates.append((len(mountpoint), fields[2].lower()))
        if candidates:
            return max(candidates)[1]
    elif sys.platform == "darwin":
        result = subprocess.run(["mount"], text=True, capture_output=True)
        candidates = []
        for line in result.stdout.splitlines():
            match = re.match(r".+ on (.+) \(([^, )]+)", line)
            if match and (resolved == match.group(1) or resolved.startswith(match.group(1).rstrip("/") + "/")):
                candidates.append((len(match.group(1)), match.group(2).lower()))
        if candidates:
            return max(candidates)[1]
    raise FailClosed("cannot determine filesystem type")


def resolve_state_root(name_with_owner, remote_url=None, fs_type_getter=filesystem_type):
    if remote_url is None:
        try:
            result = subprocess.run(["git", "remote", "get-url", "origin"], text=True,
                                    capture_output=True, check=True)
            remote_url = result.stdout.strip()
        except (OSError, subprocess.CalledProcessError) as exc:
            raise FailClosed("cannot resolve git remote URL") from exc
    normalized = normalize_git_url(remote_url)
    repo_slug = sanitize_repo_slug(name_with_owner)
    clone_id = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]
    base = Path(os.environ.get("XDG_STATE_HOME", "~/.local/state")).expanduser()
    target = base / "claude-skills" / "github-issue" / f"{repo_slug}-{clone_id}"
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(target, 0o700)
    clone_file = target / ".clone_url"
    try:
        fd = os.open(clone_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, normalized.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        parent_fd = os.open(target, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except FileExistsError:
        if clone_file.read_text(encoding="utf-8") != normalized:
            raise FailClosed(f"state_root clone_id collision: {target}")
    if target.stat().st_uid != os.getuid():
        raise FailClosed(f"state_root ownership mismatch: {target}")
    kind = fs_type_getter(target).lower()
    if kind in UNSUPPORTED_FS or kind.startswith("nfs") or kind.startswith("cifs") or kind.startswith("smb"):
        raise FailClosed(f"unsupported filesystem: {kind}")
    return {"state_root": str(target), "normalized_url": normalized, "filesystem": kind}


def filter_ready(issues, config):
    """全 issue を契約順に判定し ready slug と skip 理由を返す。"""
    required = config.get("require_author_association", ["OWNER", "MEMBER", "COLLABORATOR"])
    if isinstance(required, str):
        required = [item.strip() for item in required.split(",") if item.strip()]
    slugs, excluded = [], []
    for issue in issues:
        labels = issue.get("labels", [])
        labels = [item.get("name") if isinstance(item, dict) else item for item in labels]
        reason = None
        if "claude-running" in labels:
            reason = "running"
        elif "claude-review" in labels:
            reason = "review"
        elif state_of_failure(labels) is not None:
            reason = "failed"
        elif issue.get("authorAssociation") not in required:
            reason = "author_association"
        else:
            verdict = parse_self_drive_verdict(issue.get("body") or "")
            if verdict != "ALLOWED":
                reason = f"gate1_{verdict.lower()}"
            else:
                paths = parse_change_targets(issue.get("body") or "")
                if paths == MISSING:
                    reason = "gate0_missing_targets"
                else:
                    decision = gate_0_decision(paths, config)
                    if decision["decision"] == "REJECT":
                        reason = f"gate0_{decision['reason']}"
        if reason:
            excluded.append({"number": issue.get("number"), "reason": reason})
        else:
            slugs.append(f"issue-{issue['number']}")
    return {"slugs": slugs, "excluded": excluded}


def _load_json(path):
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    def command(name):
        return sub.add_parser(name)
    p = command("state-root"); p.add_argument("--name-with-owner", required=True); p.add_argument("--remote-url")
    p = command("filter-ready"); p.add_argument("--issues-json", required=True); p.add_argument("--config-json", required=True)
    for name in ("verdict", "change-targets"):
        p = command(name); p.add_argument("--body-file", required=True)
    p = command("gate0"); p.add_argument("--paths-json", required=True); p.add_argument("--config-json", required=True)
    p = command("state-of-failure"); p.add_argument("--labels", default="")
    p = command("validate-slug"); p.add_argument("slug")
    p = command("classify"); p.add_argument("kind")
    p = command("mark-failed-labels"); p.add_argument("--kind", choices=("transient", "permanent"), required=True)
    for name in ("retry-count",):
        p = command(name); p.add_argument("number"); p.add_argument("--state-root", required=True)
    p = command("increment-retry"); p.add_argument("number"); p.add_argument("--state-root", required=True); p.add_argument("--run-id", required=True)
    p = command("kill-files"); p.add_argument("--state-root", required=True)
    p = command("session-load"); p.add_argument("--state-root", required=True)
    p = command("session-save"); p.add_argument("--state-root", required=True); p.add_argument("--json", required=True)
    p = command("claim-lock"); p.add_argument("number"); p.add_argument("--state-root", required=True); p.add_argument("--owner-pid", required=True, type=int)
    p = command("release-lock"); p.add_argument("number"); p.add_argument("--state-root", required=True)
    p = command("recovery-marker"); p.add_argument("action", choices=("add", "list", "delete")); p.add_argument("number", nargs="?"); p.add_argument("--state-root", required=True)
    p = command("stale-locks"); p.add_argument("--state-root", required=True)
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    c = args.command
    if c == "state-root": result = resolve_state_root(args.name_with_owner, args.remote_url)
    elif c == "filter-ready": result = filter_ready(_load_json(args.issues_json), _load_json(args.config_json))
    elif c == "verdict": result = {"verdict": parse_self_drive_verdict(Path(args.body_file).read_text(encoding="utf-8"))}
    elif c == "change-targets": result = {"paths": parse_change_targets(Path(args.body_file).read_text(encoding="utf-8"))}
    elif c == "gate0": result = gate_0_decision(_load_json(args.paths_json), _load_json(args.config_json))
    elif c == "state-of-failure": result = {"state": state_of_failure([x for x in args.labels.split(",") if x])}
    elif c == "validate-slug": result = {"number": validate_slug(args.slug)}
    elif c == "classify": result = classify_failure(args.kind)
    elif c == "mark-failed-labels": result = {"add": mark_failed_labels(args.kind)}
    elif c == "retry-count": result = retry_state(args.number, args.state_root)
    elif c == "increment-retry": result = increment_retry(args.number, args.state_root, args.run_id)
    elif c == "kill-files": result = {"files": kill_files(args.state_root)}
    elif c == "session-load": result = {"session": session_load(args.state_root)}
    elif c == "session-save": result = {"session": session_save(args.state_root, _load_json(args.json))}
    elif c == "claim-lock": result = claim_lock(args.number, args.state_root, args.owner_pid)
    elif c == "release-lock": result = release_lock(args.number, args.state_root)
    elif c == "recovery-marker": result = {"markers": recovery_marker(args.action, args.state_root, args.number)}
    elif c == "stale-locks": result = {"removed": stale_locks(args.state_root)}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LockBusy as exc:
        print(f"fail_closed: {exc}", file=sys.stderr)
        raise SystemExit(2)
    except (FailClosed, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"fail_closed: {exc}", file=sys.stderr)
        raise SystemExit(2)
