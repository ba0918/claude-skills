#!/usr/bin/env python3
"""Build a process-delegation work queue from fixtures, and grade what comes back.

This is the producer side that `skills/shared/references/process-delegation.md` §11
deliberately leaves out of the shared runner: turning `fixtures.json` into prompt files
plus a `work.jsonl`, then reducing the returned artifacts to a mechanical tally.

It exists so a regression batch can run without spending subagent launches. The dispatch
contract is otherwise the one in `references/executor-contract.md`, with two adaptations
that the process path forces and one that it removes:

- The executor writes its report as **JSON to a declared path**, because the artifact is
  what the runner grades. Prose bullets are not machine-checkable.
- The prompt still withholds the `critical` flags; they live only in the batch manifest,
  so grading stays on the caller's side of the fence.
- The "report channel" problem disappears. A subagent's completion message may never be
  delivered; a file either exists or does not.

`grade` never returns a bare pass. It collapses the mechanical part of the judgement and
names what still needs adjudication, because executor-contract requires the caller to
re-judge any self-report the artifacts do not corroborate.
"""

import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "shared", "scripts"))

import fixture_setup  # noqa: E402
import process_runner  # noqa: E402

VERDICTS = ("yes", "no", "partial")

# Each unit owns one directory, laid out so a backend that sandboxes writes to the
# process working directory can still deliver its report:
#
#   work/<unit>/          <- the unit's cwd, and the narrowest sandbox that works
#     repo/               <- the staged scenario; what the executor is told to work in
#     report.json         <- the artifact
#
# Measured: an agent CLI confined to its cwd could not write a report placed in a
# sibling results/ directory, burned a full run, and exited 0 with nothing to show.
# Keeping the artifact under the unit's cwd removes that failure mode, and keeps the
# report out of the staged tree so it cannot pollute a "clean working tree" requirement.
STAGED_SUBDIR = "repo"
REPORT_NAME = "report.json"
# A scenario is only ever `fail` or `unadjudicated_pass` here. `pass` is a word this
# script is not entitled to say (see module docstring).
SCENARIO_VERDICTS = ("fail", "unadjudicated_pass", "needs_rerun")

REPORT_SCHEMA = """{
  "artifact": "<one-paragraph summary of what you produced>",
  "execution_path": "<one line: which phases you delegated vs. did inline; \\"n/a\\" if single-step>",
  "requirements": [
    {"index": 1, "verdict": "yes|no|partial", "evidence": "<one line>"}
  ],
  "unclear": ["<points in the skill you had to interpret>"],
  "discretion": ["<choices the instructions did not determine>"]
}"""


class QueueError(Exception):
    """Malformed fixture, batch, or returned report."""


# ==========================================================================
# Prompt rendering (pure)
# ==========================================================================
def render_prompt(skill, scenario, *, skill_md, work_dir, output_file, env=None):
    """Render one executor prompt.

    Requirements are numbered and stripped of their `critical` flags: an executor that
    knows which items decide the verdict optimises for those items instead of following
    the skill, and the measurement stops being about the skill.
    """
    lines = [
        f"You are an executor reading the `{skill}` skill's SKILL.md for the first time.",
        "",
        "## Target skill",
        "",
        f"{skill_md}",
        "",
        "Read it, and follow any references it points to.",
        "",
        "## Working directory",
        "",
        f"{work_dir}",
        "",
        "Work only inside that directory. The one exception is the report file named "
        "in the Task section below; apart from that file, create and edit nothing "
        "outside it.",
        "",
    ]
    if env:
        lines += [
            "## Environment setup",
            "",
            "Treat the following as already true of your environment. This section is "
            "context, not a hint about how to solve the situation below.",
            "",
        ]
        lines += [f"- `{name}` = `{value}`" for name, value in sorted(env.items())]
        lines.append("")
    lines += [
        "## Situation",
        "",
        scenario["prompt"],
        "",
        "## Task",
        "",
        "1. Follow the target skill's instructions to handle the situation and produce "
        "whatever it calls for.",
        "2. Then write your report as a JSON file to exactly this path:",
        "",
        f"   {output_file}",
        "",
        "   That file is the only channel that reaches the caller. Anything you print is "
        "discarded, and a run that produces no file counts as a failure however well it "
        "went.",
        "",
        "## Report schema",
        "",
        "```json",
        REPORT_SCHEMA,
        "```",
        "",
        "Emit one `requirements` entry per numbered item below, using the same index. "
        "Assess honestly: `no` and `partial` are useful answers, and a report that "
        "disagrees with your own artifacts is worse than a low score.",
        "",
        "### Items to self-assess",
        "",
    ]
    lines += [
        f"{index}. {requirement['text']}"
        for index, requirement in enumerate(scenario["requirements"], start=1)
    ]
    lines.append("")
    return "\n".join(lines)


def unit_id(skill, scenario_id):
    """Batch-unique unit id. Must satisfy the work-queue id grammar."""
    candidate = f"{skill}-{scenario_id}"
    if not process_runner.ID_RE.fullmatch(candidate):
        raise QueueError(
            f"unit id {candidate!r} is not usable in a work queue "
            f"(allowed: [A-Za-z0-9._-]+)")
    return candidate


# ==========================================================================
# Grading (pure)
# ==========================================================================
def parse_report(text, expected_count):
    """Validate an executor report. Raises QueueError on any protocol violation.

    A malformed report is a *harness* failure, not evidence that the skill regressed —
    the same split empirical-prompt-tuning draws between protocol failure and candidate
    failure. Conflating them makes a broken batch look like a broken skill.
    """
    try:
        report = json.loads(text)
    except json.JSONDecodeError as exc:
        raise QueueError(f"report is not valid JSON: {exc}")
    if not isinstance(report, dict):
        raise QueueError("report is not a JSON object")
    entries = report.get("requirements")
    if not isinstance(entries, list):
        raise QueueError("report has no 'requirements' list")
    if len(entries) != expected_count:
        raise QueueError(
            f"report covers {len(entries)} requirement(s), expected {expected_count}")
    by_index = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise QueueError("a requirements entry is not an object")
        index = entry.get("index")
        if not isinstance(index, int) or not 1 <= index <= expected_count:
            raise QueueError(f"requirement index out of range: {index!r}")
        if index in by_index:
            raise QueueError(f"requirement index {index} appears twice")
        verdict = entry.get("verdict")
        if verdict not in VERDICTS:
            raise QueueError(
                f"requirement {index} has unknown verdict {verdict!r} "
                f"(allowed: {', '.join(VERDICTS)})")
        by_index[index] = entry
    return report, by_index


def grade_scenario(requirements, by_index, *, drifted=()):
    """Mechanical part of the scenario judgement.

    `partial` counts as a miss: executor-contract fails safe, because a lenient tally
    empties the ledger of meaning.

    `baseline_drift` is evidence, never a verdict. Whether an edit to a staged file is a
    violation depends on the requirement, not on the scenario's isolation mode — a
    worktree scenario may legitimately rewrite everything, and a read-only requirement
    inside one is contradicted by a single byte. The script surfaces the drift so the
    caller can hold a self-reported "yes" against it, per executor-contract's rule that
    read-only judgements rest on hash comparison rather than self-report.
    """
    critical_missed, other_missed = [], []
    for index, requirement in enumerate(requirements, start=1):
        verdict = by_index[index]["verdict"]
        if verdict == "yes":
            continue
        target = critical_missed if requirement.get("critical") else other_missed
        target.append({"index": index, "text": requirement["text"],
                       "verdict": verdict,
                       "evidence": by_index[index].get("evidence", "")})
    return {
        "verdict": "fail" if critical_missed else "unadjudicated_pass",
        "critical_missed": critical_missed,
        "other_missed": other_missed,
        "baseline_drift": sorted(drifted),
    }


def roll_up(scenarios):
    """Skill-level roll-up. Any non-pass scenario blocks the ledger."""
    verdicts = [s["verdict"] for s in scenarios]
    if not verdicts:
        return "needs_rerun"
    if "needs_rerun" in verdicts:
        return "needs_rerun"
    if "fail" in verdicts:
        return "fail"
    return "unadjudicated_pass"


# ==========================================================================
# Filesystem layer
# ==========================================================================
def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _sha256_file(path):
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return None


def build(fixture_paths, batch_dir, repo_root, *, scenario_ids=None):
    """Materialise every scenario and emit prompts, a work queue, and a manifest."""
    batch_dir = os.path.abspath(batch_dir)
    repo_root = os.path.abspath(repo_root)
    for sub in ("prompts", "work"):
        os.makedirs(os.path.join(batch_dir, sub), exist_ok=True)

    units, manifest = [], {}
    for fixture_path in fixture_paths:
        fixture = json.loads(_read(fixture_path))
        errors = fixture_setup.validate(fixture, source=fixture_path)
        if errors:
            raise QueueError("; ".join(errors))
        skill = fixture["skill"]
        skill_md = os.path.join(repo_root, "skills", skill, "SKILL.md")
        if not os.path.isfile(skill_md):
            raise QueueError(f"target skill has no SKILL.md: {skill_md}")

        for scenario in fixture["scenarios"]:
            if scenario_ids and scenario["id"] not in scenario_ids:
                continue
            uid = unit_id(skill, scenario["id"])
            unit_dir = os.path.join(batch_dir, "work", uid)
            staged = fixture_setup.materialize(
                scenario, os.path.join(unit_dir, STAGED_SUBDIR))
            output_file = os.path.join(unit_dir, REPORT_NAME)
            prompt = render_prompt(
                skill, scenario,
                skill_md=skill_md,
                work_dir=staged["dir"],
                output_file=output_file,
                env=staged["env"],
            )
            prompt_rel = os.path.join("prompts", f"{uid}.md")
            with open(os.path.join(batch_dir, prompt_rel), "w",
                      encoding="utf-8") as handle:
                handle.write(prompt)

            units.append({
                "id": uid,
                "prompt_file": prompt_rel,
                "output_file": os.path.join("work", uid, REPORT_NAME),
                "output_format": "json",
                "cwd": os.path.join("work", uid),
            })
            manifest[uid] = {
                "skill": skill,
                "scenario_id": scenario["id"],
                "title": scenario["title"],
                "isolation": scenario.get("isolation", "worktree"),
                "executor_tier": scenario.get("executor_tier", "standard"),
                "requirements": scenario["requirements"],
                "work_dir": staged["dir"],
                "baseline": staged["baseline"],
                "unmaterialized": staged["unmaterialized"],
            }

    if not units:
        raise QueueError("no scenarios selected")

    work_text = "".join(json.dumps(u, sort_keys=True) + "\n" for u in units)
    work_path = os.path.join(batch_dir, "work.jsonl")
    with open(work_path, "w", encoding="utf-8") as handle:
        handle.write(work_text)
    manifest_path = os.path.join(batch_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)

    # Dogfood the producer obligation in process-delegation.md §11: a batch that the
    # runner would reject must fail here, while it is still cheap to fix.
    process_runner.resolve_paths(process_runner.parse_work(work_text), batch_dir)

    unmaterialized = {
        uid: entry["unmaterialized"]
        for uid, entry in manifest.items() if entry["unmaterialized"]
    }
    return {
        "batch": batch_dir,
        "work": work_path,
        "manifest": manifest_path,
        "units": len(units),
        "unmaterialized": unmaterialized,
    }


def grade(batch_dir):
    """Reduce the returned artifacts to a per-skill mechanical tally."""
    batch_dir = os.path.abspath(batch_dir)
    manifest = json.loads(_read(os.path.join(batch_dir, "manifest.json")))

    by_skill = {}
    for uid in sorted(manifest):
        entry = manifest[uid]
        requirements = entry["requirements"]
        result = {"unit": uid, "scenario_id": entry["scenario_id"],
                  "title": entry["title"]}

        artifact = os.path.join(batch_dir, "work", uid, REPORT_NAME)
        state = process_runner.artifact_state(
            process_runner.read_text(artifact), "json")
        if state != "ok":
            result.update({"verdict": "needs_rerun",
                           "harness_error": f"{state}_artifact"})
        else:
            try:
                report, by_index = parse_report(_read(artifact), len(requirements))
            except QueueError as exc:
                result.update({"verdict": "needs_rerun",
                               "harness_error": "malformed_report",
                               "detail": str(exc)})
            else:
                drifted = [
                    path for path, digest in entry["baseline"].items()
                    if _sha256_file(os.path.join(entry["work_dir"], path)) != digest
                ]
                result.update(grade_scenario(
                    requirements, by_index, drifted=drifted))
                result["execution_path"] = report.get("execution_path", "")
                result["unclear"] = report.get("unclear", [])
        by_skill.setdefault(entry["skill"], []).append(result)

    return {
        "batch": batch_dir,
        "skills": {
            skill: {"verdict": roll_up(results), "scenarios": results}
            for skill, results in sorted(by_skill.items())
        },
    }


# ==========================================================================
# CLI
# ==========================================================================
def _cli_build(args):
    summary = build(args.fixture, args.batch, args.repo_root,
                    scenario_ids=set(args.scenario) if args.scenario else None)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _cli_grade(args):
    print(json.dumps(grade(args.batch), ensure_ascii=False, indent=2,
                     sort_keys=True))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Fixture -> process-delegation work queue -> mechanical tally.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    build_parser = sub.add_parser("build", help="materialise scenarios into a batch")
    build_parser.add_argument("--fixture", action="append", required=True,
                              help="path to a fixtures.json (repeatable)")
    build_parser.add_argument("--batch", required=True, help="batch directory to create")
    build_parser.add_argument("--repo-root", default=".")
    build_parser.add_argument("--scenario", action="append",
                              help="restrict to these scenario ids (repeatable)")
    build_parser.set_defaults(func=_cli_build)

    grade_parser = sub.add_parser("grade", help="tally the returned reports")
    grade_parser.add_argument("--batch", required=True)
    grade_parser.set_defaults(func=_cli_grade)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (QueueError, process_runner.ParseError,
            process_runner.ContainmentError, OSError) as exc:
        print(json.dumps({"error": type(exc).__name__, "detail": str(exc)},
                         ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
