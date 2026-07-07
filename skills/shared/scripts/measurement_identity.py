#!/usr/bin/env python3
"""計測の結合キー統一（Event Record）の純関数 + 薄い CLI。

skills/shared/references/measurement-identity.md の Event Record 契約（§3）を
実装する。全 writer（polling 両 adapter / skill-regression / trigger-eval）は
このモジュールの make_event / validate_event を経由して docs/loop/events.jsonl
に append する。surface_sha256 は skill-regression/scripts/ledger.py の
fingerprint() を再利用する（再実装禁止、契約 §2）。

CLI:
  python3 measurement_identity.py report --skill NAME \
      [--events PATH ...] [--repo-root PATH]
  python3 measurement_identity.py emit --system S --event E --skill NAME \
      --repo-root PATH --outcome JSON [--run-id UUID] [--events PATH]
"""
import datetime
import json
import os
import re
import sys

SYSTEMS = {"polling-fs", "polling-label", "skill-regression", "trigger-eval"}
EVENTS = {"tick", "verification", "eval"}

_SURFACE_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_RUN_ID_RE = re.compile(r"^[0-9a-f-]{36}$")

_DEFAULT_EVENTS_REL = os.path.join("docs", "loop", "events.jsonl")


def validate_event(d):
    """契約 §3 の Event Record を検証する。エラーメッセージのリスト（空 = valid）。"""
    if not isinstance(d, dict):
        return ["record is not a dict"]

    errors = []

    ts = d.get("ts")
    if not isinstance(ts, str) or not ts.strip():
        errors.append("ts must be a non-empty string")

    system = d.get("system")
    if system not in SYSTEMS:
        errors.append(f"system must be one of {sorted(SYSTEMS)}, got {system!r}")

    event = d.get("event")
    if event not in EVENTS:
        errors.append(f"event must be one of {sorted(EVENTS)}, got {event!r}")

    skill = d.get("skill")
    if not isinstance(skill, str) or not skill.strip():
        errors.append("skill must be a non-empty string")

    surface = d.get("surface_sha256")
    if not isinstance(surface, str) or not _SURFACE_RE.match(surface):
        errors.append("surface_sha256 must be a 64-hex-digit string")

    run_id = d.get("run_id")
    if run_id is not None and (
        not isinstance(run_id, str) or not _RUN_ID_RE.match(run_id)
    ):
        errors.append("run_id must be null or a UUID-like string")

    outcome = d.get("outcome")
    if not isinstance(outcome, dict):
        errors.append("outcome must be a dict")
    else:
        for key, value in outcome.items():
            if value is not None and not isinstance(value, (int, float, str)):
                errors.append(
                    f"outcome[{key!r}] must be numeric, string, or null "
                    f"(got {type(value).__name__})"
                )

    return errors


def make_event(*, ts, system, event, skill, surface_sha256, run_id, outcome):
    """検証済み Event dict を返す。invalid なら ValueError(errors) を送出する。"""
    record = {
        "ts": ts,
        "system": system,
        "event": event,
        "skill": skill,
        "surface_sha256": surface_sha256,
        "run_id": run_id,
        "outcome": outcome,
    }
    errors = validate_event(record)
    if errors:
        raise ValueError(errors)
    return record


def parse_events(text):
    """JSONL テキスト → (valid events, エラー行の説明リスト)。壊れた行は skip する。"""
    events = []
    errors = []
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {lineno}: invalid JSON ({exc})")
            continue
        verrs = validate_event(record)
        if verrs:
            errors.append(f"line {lineno}: {'; '.join(verrs)}")
            continue
        events.append(record)
    return events, errors


def aggregate_by_surface(events, skill, systems=None):
    """event=="tick" かつ skill 一致のイベントを surface_sha256 別に集計する。"""
    groups = {}
    for e in events:
        if e.get("event") != "tick" or e.get("skill") != skill:
            continue
        if systems is not None and e.get("system") not in systems:
            continue
        surface = e.get("surface_sha256")
        ts = e.get("ts")
        outcome = e.get("outcome") or {}
        group = groups.get(surface)
        if group is None:
            group = {
                "surface_sha256": surface,
                "ticks": 0,
                "claimed": 0,
                "done": 0,
                "failed": 0,
                "first_ts": ts,
                "last_ts": ts,
            }
            groups[surface] = group
        group["ticks"] += 1
        group["claimed"] += outcome.get("claimed", 0) or 0
        group["done"] += outcome.get("done", 0) or 0
        group["failed"] += (
            (outcome.get("failed_transient", 0) or 0)
            + (outcome.get("failed_permanent", 0) or 0)
        )
        if ts < group["first_ts"]:
            group["first_ts"] = ts
        if ts > group["last_ts"]:
            group["last_ts"] = ts

    result = []
    for group in groups.values():
        denom = group["done"] + group["failed"]
        group["success_rate"] = group["done"] / denom if denom else None
        result.append(group)
    result.sort(key=lambda g: g["first_ts"])
    return result


def surface_delta(agg):
    """直近 2 surface の成功率差分を返す。2 未満なら None。"""
    if len(agg) < 2:
        return None
    prev, curr = agg[-2], agg[-1]
    prev_rate = prev.get("success_rate")
    curr_rate = curr.get("success_rate")
    rate_delta = (
        curr_rate - prev_rate
        if prev_rate is not None and curr_rate is not None
        else None
    )
    return {"prev": prev, "curr": curr, "rate_delta": rate_delta}


def current_surface_sha256(repo_root, skill):
    """skill-regression/scripts/ledger.py を再利用し現在の挙動面 fingerprint を返す。"""
    sr_scripts = os.path.join(repo_root, "skills", "skill-regression", "scripts")
    if sr_scripts not in sys.path:
        sys.path.insert(0, sr_scripts)
    import ledger  # noqa: E402  (repo_root 依存の動的 import)

    surface = ledger.skill_surface(repo_root, skill)
    return ledger.fingerprint(repo_root, surface)


def format_report(agg, delta, skill):
    """人間向け markdown テーブル（純関数）。"""
    lines = [f"# measurement identity report: {skill}", ""]
    if not agg:
        lines.append("(tick イベントなし)")
        return "\n".join(lines)

    lines.append(
        "| surface | ticks | claimed | done | failed | success_rate | "
        "first_ts | last_ts |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for g in agg:
        rate = g["success_rate"]
        rate_str = f"{rate:.1%}" if rate is not None else "-"
        lines.append(
            f"| {g['surface_sha256'][:12]} | {g['ticks']} | {g['claimed']} | "
            f"{g['done']} | {g['failed']} | {rate_str} | {g['first_ts']} | "
            f"{g['last_ts']} |"
        )

    if delta is not None:
        prev_rate = delta["prev"]["success_rate"]
        curr_rate = delta["curr"]["success_rate"]
        prev_str = f"{prev_rate:.1%}" if prev_rate is not None else "-"
        curr_str = f"{curr_rate:.1%}" if curr_rate is not None else "-"
        delta_str = (
            f"{delta['rate_delta']:+.1%}" if delta["rate_delta"] is not None else "-"
        )
        lines.append("")
        lines.append(f"直近の改稿効果: rate {prev_str} → {curr_str} (Δ {delta_str})")

    return "\n".join(lines)


def _parse_flags(rest, flag_names, multi=frozenset()):
    """`--flag value` 形式の引数を dict に集める（multi は list に累積）。"""
    values = {name: ([] if name in multi else None) for name in flag_names}
    i = 0
    while i < len(rest):
        token = rest[i]
        if token in flag_names and i + 1 < len(rest):
            if token in multi:
                values[token].append(rest[i + 1])
            else:
                values[token] = rest[i + 1]
            i += 2
        else:
            i += 1
    return values


def _cmd_report(rest):
    flags = _parse_flags(
        rest, {"--skill", "--events", "--repo-root"}, multi={"--events"}
    )
    skill = flags["--skill"]
    if not skill:
        print("✗ --skill is required", file=sys.stderr)
        return 2
    repo_root = flags["--repo-root"] or os.getcwd()
    events_paths = flags["--events"] or [
        os.path.join(repo_root, _DEFAULT_EVENTS_REL)
    ]

    events = []
    broken_total = 0
    for path in events_paths:
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        evs, errs = parse_events(text)
        events.extend(evs)
        broken_total += len(errs)

    agg = aggregate_by_surface(events, skill)
    delta = surface_delta(agg)
    print(format_report(agg, delta, skill))
    if broken_total:
        print(f"⚠ {broken_total} 件の壊れた行をスキップしました", file=sys.stderr)
    return 0


def _cmd_emit(rest):
    flags = _parse_flags(
        rest,
        {
            "--system", "--event", "--skill", "--repo-root", "--outcome",
            "--run-id", "--events",
        },
    )
    required = ["--system", "--event", "--skill", "--repo-root", "--outcome"]
    missing = [name for name in required if not flags[name]]
    if missing:
        print(f"✗ required flags missing: {', '.join(missing)}", file=sys.stderr)
        return 2

    repo_root = flags["--repo-root"]
    outcome = json.loads(flags["--outcome"])
    surface_sha256 = current_surface_sha256(repo_root, flags["--skill"])
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

    try:
        record = make_event(
            ts=ts,
            system=flags["--system"],
            event=flags["--event"],
            skill=flags["--skill"],
            surface_sha256=surface_sha256,
            run_id=flags["--run-id"],
            outcome=outcome,
        )
    except ValueError as exc:
        print(f"✗ invalid event: {exc}", file=sys.stderr)
        return 1

    events_path = flags["--events"] or os.path.join(repo_root, _DEFAULT_EVENTS_REL)
    parent = os.path.dirname(events_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(events_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"✓ event appended: {events_path}")
    return 0


def main(argv):
    args = list(argv)
    if not args:
        print(__doc__)
        return 2
    cmd, rest = args[0], args[1:]
    if cmd == "report":
        return _cmd_report(rest)
    if cmd == "emit":
        return _cmd_emit(rest)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
