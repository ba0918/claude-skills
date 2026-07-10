"""loop-triage 駆動層 — 純関数（finding_identity / admission）の薄い合成。

判定ロジックは admission.py / finding_identity.py に集約されており、本モジュールは
入出力の合成と決定的な処理順序（severity 順）だけを持つ。
契約: skills/shared/references/loop-engineering.md
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import admission as adm  # noqa: E402
import finding_identity as fi  # noqa: E402

_SEVERITY_ORDER = {"BLOCK": 0, "WARN": 1, "INFO": 2}


def order_findings(findings):
    """決定的な処理順: severity（BLOCK 優先）→ sensor → rule → what。

    budget（max_enqueue_per_run）の消費順を再現可能にする。純関数。
    """
    return sorted(
        findings,
        key=lambda f: (
            _SEVERITY_ORDER.get(f.get("severity"), 3),
            f.get("sensor", ""),
            f.get("rule", ""),
            f.get("what", ""),
        ),
    )


def run_triage(findings, *, baseline, queue_ids, skills_with_fixtures,
               impact_resolver, max_enqueue=5):
    """findings 全体をルーティングして decisions を返す。

    impact_resolver: Callable[[str], list[str]] — path → 影響スキル名（DI。テストでは stub、
    本番は ledger.py --impact への subprocess）。それ以外の入力はすべて値なので、
    resolver を純粋にすればこの関数も純粋になる。
    """
    decisions = []
    enqueue_used = 0
    for raw in order_findings(findings):
        errors = fi.validate_finding(raw)
        if errors:
            decisions.append({"finding": raw, "finding_id": None,
                              "route": "digest", "reason": "invalid-schema",
                              "errors": errors})
            continue
        f = fi.normalize_finding(raw)
        fid = fi.finding_id(f["sensor"], f["rule"], f["where"]["path"], f["what"])
        d = adm.route(
            f,
            queue_ids=queue_ids,
            baseline=baseline,
            fid=fid,
            path_to_skills=impact_resolver,
            skills_with_fixtures=skills_with_fixtures,
            enqueue_used=enqueue_used,
            max_enqueue_per_run=max_enqueue,
        )
        if d.get("route") == "enqueue":
            enqueue_used += 1
        decisions.append({"finding": f, "finding_id": fid, **d})
    return decisions


def _impact_resolver_factory(repo_root):
    ledger = Path(repo_root) / "skills" / "skill-regression" / "scripts" / "ledger.py"
    cache = {}

    def resolve(path):
        if path not in cache:
            r = subprocess.run(
                [sys.executable, str(ledger), "--impact", path, str(repo_root)],
                capture_output=True, text=True,
            )
            cache[path] = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
        return cache[path]

    return resolve


def _load_findings(paths):
    findings = []
    for p in paths:
        findings.extend(json.loads(Path(p).read_text()))
    return findings


def main(argv=None):
    ap = argparse.ArgumentParser(description="loop-triage: findings -> decisions")
    ap.add_argument("findings", nargs="+", help="Finding JSON 配列ファイル")
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--baseline", default=".claude/loop-baseline.json")
    ap.add_argument("--out", help="decisions.json の出力先")
    ap.add_argument("--max-enqueue", type=int, default=5)
    ap.add_argument("--update-baseline", metavar="PATH",
                    help="現在の findings の ID を baseline に確定して終了する")
    args = ap.parse_args(argv)

    root = Path(args.repo_root)
    findings = _load_findings(args.findings)

    if args.update_baseline:
        fids = [
            fi.finding_id(f["sensor"], f["rule"], f["where"]["path"], f["what"])
            for f in (fi.normalize_finding(x) for x in findings)
            if not fi.validate_finding(f)
        ]
        Path(args.update_baseline).write_text(
            json.dumps(fi.build_baseline(fids), indent=2) + "\n")
        print(f"baseline updated: {len(set(fids))} suppressions -> {args.update_baseline}")
        return 0

    baseline_path = Path(args.baseline)
    baseline = fi.load_baseline(
        baseline_path.read_text() if baseline_path.exists() else "")
    queue_ids = fi.collect_queue_ids(str(root / ".agents" / "artifacts" / "issues"))
    skills_with_fixtures = {
        p.parent.name for p in (root / "skills").glob("*/fixtures.json")}

    decisions = run_triage(
        findings,
        baseline=baseline,
        queue_ids=queue_ids,
        skills_with_fixtures=skills_with_fixtures,
        impact_resolver=_impact_resolver_factory(root),
        max_enqueue=args.max_enqueue,
    )

    counts = {}
    for d in decisions:
        counts[d["route"]] = counts.get(d["route"], 0) + 1
    out = json.dumps(decisions, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(out + "\n")
    else:
        print(out)
    print(f"routes: {json.dumps(counts, ensure_ascii=False)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
