#!/usr/bin/env python3
"""
context-audit: findings + baseline -> deterministic summary-first report.

Applies baseline suppression (opaque finding-ID list), aggregates severity/action
counts, and emits a stable report skeleton. The fix `action` is taken verbatim
from static_checks.py output — never recomputed here (single source of truth).

The baseline stores ONLY opaque finding IDs (sha256 of id|where|what). No detected
value or body text is stored, so the committed baseline never leaks content.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ACTIONS = ("AUTO_FIX", "NEEDS_JUDGMENT", "REPORT_ONLY")
_SEVERITY_RANK = {"BLOCK": 0, "WARN": 1, "INFO": 2, "PASS": 3}


def finding_id(finding: dict) -> str:
    """Opaque, stable per-finding ID. Hashed so no content leaks into baseline."""
    key = f"{finding.get('id')}|{finding.get('where')}|{finding.get('what')}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def apply_suppression(findings: list[dict], baseline: dict | None) -> tuple[list[dict], int]:
    """Drop findings whose opaque ID is in the baseline. Returns (kept, count)."""
    if not baseline:
        return list(findings), 0
    suppressed_ids = set(baseline.get("suppressions", []))
    if not suppressed_ids:
        return list(findings), 0
    kept, count = [], 0
    for f in findings:
        if finding_id(f) in suppressed_ids:
            count += 1
        else:
            kept.append(f)
    return kept, count


def build_baseline(findings: list[dict]) -> dict:
    """Baseline JSON from current findings. Stores ONLY opaque finding IDs
    (sorted, deduped) — never detected values or body text."""
    return {
        "version": 1,
        "suppressions": sorted({finding_id(f) for f in findings}),
    }


def summarize(findings: list[dict]) -> dict:
    """Count findings by action and by severity."""
    by_action = {a: 0 for a in ACTIONS}
    by_severity: dict[str, int] = {}
    for f in findings:
        a = f.get("action")
        if a in by_action:
            by_action[a] += 1
        sev = f.get("severity", "INFO")
        by_severity[sev] = by_severity.get(sev, 0) + 1
    return {**by_action, "total": len(findings), "by_severity": by_severity}


def _sort_key(f: dict) -> tuple:
    return (_SEVERITY_RANK.get(f.get("severity"), 9), f.get("id", ""), f.get("where", ""))


def build_report(findings: list[dict], baseline: dict | None) -> dict:
    """Deterministic summary-first report skeleton."""
    kept, suppressed = apply_suppression(findings, baseline)
    kept_sorted = sorted(kept, key=_sort_key)
    for f in kept_sorted:
        f["finding_id"] = finding_id(f)

    s = summarize(kept_sorted)
    summary = {
        "total": s["total"],
        "AUTO_FIX": s["AUTO_FIX"],
        "NEEDS_JUDGMENT": s["NEEDS_JUDGMENT"],
        "REPORT_ONLY": s["REPORT_ONLY"],
        "suppressed": suppressed,
    }

    groups: dict[str, list[dict]] = {}
    for f in kept_sorted:
        groups.setdefault(f.get("id", "?"), []).append(f)
    grouped = [
        {"rule_id": rid, "count": len(fs), "findings": fs}
        for rid, fs in sorted(groups.items())
    ]

    return {
        "summary": summary,
        "by_severity": s["by_severity"],
        "groups": grouped,
        "findings": kept_sorted,
    }


def render_markdown(report: dict) -> str:
    s = report["summary"]
    head = (f"{s['total']} findings: {s['AUTO_FIX']} AUTO_FIX / "
            f"{s['NEEDS_JUDGMENT']} NEEDS_JUDGMENT / {s['REPORT_ONLY']} REPORT_ONLY; "
            f"{s['suppressed']} suppressed")
    lines = ["# context-audit report", "", head, ""]
    for f in report["findings"]:
        lines.append(f"- [{f['severity']}/{f['action']}] {f['id']} {f['where']}")
        lines.append(f"  - {f['what']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate context-audit findings")
    parser.add_argument("findings_json", help="static_checks.py output (path or '-')")
    parser.add_argument("--baseline", default=None, help="baseline JSON path")
    parser.add_argument("--output", default=None)
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--update-baseline", default=None, metavar="PATH",
                        help="Write current findings as the new baseline "
                             "(opaque IDs only) to PATH and exit")
    args = parser.parse_args()

    raw = sys.stdin.read() if args.findings_json == "-" else Path(args.findings_json).read_text(encoding="utf-8")
    data = json.loads(raw)
    findings = data["findings"] if isinstance(data, dict) else data

    if args.update_baseline:
        baseline_doc = build_baseline(findings)
        Path(args.update_baseline).write_text(
            json.dumps(baseline_doc, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"baseline_written": args.update_baseline,
                          "suppression_count": len(baseline_doc["suppressions"])}))
        return 0

    baseline = None
    if args.baseline and Path(args.baseline).is_file():
        baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))

    report = build_report(findings, baseline)
    out = render_markdown(report) if args.markdown else json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(out + ("" if out.endswith("\n") else "\n"), encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
