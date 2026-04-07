#!/usr/bin/env python3
"""
skill-improve: Session data collector for friction signal analysis.

Reads JSONL session data from ~/.claude/projects/ and extracts structural
friction signals (no message body content) for skill usage analysis.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_ROOT = Path.home() / ".claude" / "projects"

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+")),
    ("generic_secret", re.compile(
        r"""(?:password|secret|token|api[_-]?key|credentials)"""
        r"""\s*[:=]\s*["'][^"']{8,}["']""",
        re.IGNORECASE,
    )),
    ("generic_long_key", re.compile(r"""["'][A-Za-z0-9_\-/+]{40,}["']""")),
]

# Generic slash command pattern: /<plugin>:<skill-name>
# Matches any plugin prefix without requiring a hardcoded whitelist.
SLASH_SKILL_RE = re.compile(r"/([a-z][a-z0-9-]*):([a-z][a-z0-9-]*)")

# Generic Skill tool input pattern: "<plugin>:<skill-name>" or bare "<skill-name>"
SKILL_INPUT_RE = re.compile(r"^(?:([a-z][a-z0-9-]*):)?([a-z][a-z0-9-]*)$")


# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------

def resolve_and_validate_path(path: Path) -> Path | None:
    """Resolve symlinks and verify the path is under ALLOWED_ROOT."""
    try:
        resolved = path.resolve(strict=True)
    except (OSError, ValueError):
        return None
    if not str(resolved).startswith(str(ALLOWED_ROOT.resolve())):
        return None
    return resolved


def detect_secrets(text: str) -> list[dict[str, str]]:
    """Detect potential secrets in text. Returns list of {type, masked}."""
    findings: list[dict[str, str]] = []
    for name, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group()
            masked = value[:4] + "****" + value[-4:] if len(value) > 12 else "****"
            findings.append({"type": name, "masked": masked})
    return findings


def mask_secrets(text: str) -> str:
    """Replace detected secrets with masked versions."""
    result = text
    for _name, pattern in SECRET_PATTERNS:
        def _mask(m: re.Match[str]) -> str:
            v = m.group()
            return v[:4] + "****" + v[-4:] if len(v) > 12 else "****"
        result = pattern.sub(_mask, result)
    return result


# ---------------------------------------------------------------------------
# JSONL session discovery
# ---------------------------------------------------------------------------

def discover_session_dirs(project_filter: str | None) -> list[Path]:
    """
    Find session directories under ALLOWED_ROOT.
    If project_filter is given, only return dirs whose path contains that name.
    """
    if not ALLOWED_ROOT.exists():
        return []

    dirs: list[Path] = []
    try:
        for project_dir in ALLOWED_ROOT.iterdir():
            if not project_dir.is_dir():
                continue
            resolved = resolve_and_validate_path(project_dir)
            if resolved is None:
                continue
            if project_filter and project_filter not in resolved.name:
                continue
            dirs.append(resolved)
    except PermissionError:
        pass
    return dirs


def find_jsonl_files(session_dirs: list[Path]) -> list[Path]:
    """Find all .jsonl files within session directories."""
    jsonl_files: list[Path] = []
    for d in session_dirs:
        try:
            for f in d.rglob("*.jsonl"):
                resolved = resolve_and_validate_path(f)
                if resolved is not None and os.access(resolved, os.R_OK):
                    jsonl_files.append(resolved)
        except PermissionError:
            continue
    return jsonl_files


# ---------------------------------------------------------------------------
# Streaming JSONL parser with friction signal extraction
# ---------------------------------------------------------------------------

def parse_timestamp(ts: Any) -> datetime | None:
    """Parse ISO timestamp string to datetime."""
    if not isinstance(ts, str):
        return None
    try:
        # Handle various ISO formats
        ts_clean = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts_clean)
    except (ValueError, TypeError):
        return None


def extract_skill_name(text: str) -> str | None:
    """Extract skill name from any slash command invocation.

    Matches the generic pattern /<plugin>:<skill-name> regardless of plugin prefix.
    Handles formats like:
    - /claude-skills:plan-create
    - /wiki:wiki-ingest
    - <command-name>/any-plugin:team-cycle</command-name>
    - `/foo:cycle`
    """
    if not isinstance(text, str):
        return None
    m = SLASH_SKILL_RE.search(text)
    if m:
        return m.group(2)
    return None


def is_skill_tool_call(msg: dict[str, Any]) -> tuple[bool, str | None]:
    """Check if message is a Skill tool invocation and extract skill name.

    JSONL structure: assistant messages have tool_use blocks inside
    msg["message"]["content"] as {type: "tool_use", name: "Skill", input: {skill: ...}}.

    Accepts any "<plugin>:<skill-name>" or bare "<skill-name>" value without
    requiring a plugin whitelist.
    """
    def _resolve_skill(skill_value: Any) -> str | None:
        """Strip any plugin prefix from skill_value and return the skill name."""
        if not isinstance(skill_value, str) or not skill_value:
            return None
        m = SKILL_INPUT_RE.match(skill_value)
        if m:
            return m.group(2)
        return None

    # Check nested message.content for tool_use blocks (actual JSONL structure)
    inner = msg.get("message", {})
    if isinstance(inner, dict):
        content = inner.get("content", [])
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") != "tool_use":
                    continue
                name = block.get("name", "")
                if name in ("Skill", "skill"):
                    tool_input = block.get("input", {})
                    if isinstance(tool_input, dict):
                        skill = tool_input.get("skill", "")
                        resolved = _resolve_skill(skill)
                        if resolved is not None:
                            return True, resolved
                    return True, None

    # Fallback: legacy flat structure (tool_name at top level)
    tool_name = msg.get("tool_name", "")
    if tool_name in ("Skill", "skill"):
        tool_input = msg.get("tool_input", {})
        if isinstance(tool_input, dict):
            skill = tool_input.get("skill", "")
            resolved = _resolve_skill(skill)
            if resolved is not None:
                return True, resolved
        return True, None
    return False, None


def is_tool_error(msg: dict[str, Any]) -> bool:
    """Check if message represents a tool error (structural signal, no body needed).

    JSONL structure: tool results appear as blocks inside msg["message"]["content"]
    as {type: "tool_result", ...} and optionally at msg["toolUseResult"].
    """
    # Check nested message.content for tool_result blocks with errors
    inner = msg.get("message", {})
    if isinstance(inner, dict):
        content = inner.get("content", [])
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_result" and block.get("is_error", False) is True:
                    return True

    # Check top-level toolUseResult for errors
    tool_result = msg.get("toolUseResult", {})
    if isinstance(tool_result, dict) and tool_result.get("is_error", False) is True:
        return True

    # Fallback: legacy flat structure
    if msg.get("type") == "tool_result":
        return msg.get("is_error", False) is True
    if msg.get("error") is not None:
        return True
    return False


def process_session_file(
    filepath: Path,
    cutoff: datetime,
) -> dict[str, Any]:
    """
    Stream-process a single JSONL session file.
    Extracts friction signals without holding all lines in memory.
    Returns session-level summary.
    """
    secret_warnings: list[dict[str, str]] = []
    skill_invocations: list[dict[str, Any]] = []
    tool_errors: int = 0
    total_turns: int = 0
    session_start: datetime | None = None
    session_end: datetime | None = None
    last_skill: str | None = None
    last_skill_turn: int = 0
    consecutive_skill_calls: dict[str, int] = {}
    correction_after_skill: dict[str, int] = {}
    turns_since_skill: int = 0
    abandoned = False

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line_num, raw_line in enumerate(f, 1):
                raw_line = raw_line.strip()
                if not raw_line:
                    continue

                # --- Secret detection (immediately after JSONL parse, before field extraction) ---
                secrets_found = detect_secrets(raw_line)
                if secrets_found:
                    secret_warnings.extend(secrets_found)
                    raw_line = mask_secrets(raw_line)

                # --- Parse JSON ---
                try:
                    msg = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                if not isinstance(msg, dict):
                    continue

                # --- Timestamp processing ---
                ts = parse_timestamp(
                    msg.get("timestamp") or msg.get("created_at") or msg.get("ts")
                )
                if ts is not None:
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    if ts < cutoff:
                        continue
                    if session_start is None or ts < session_start:
                        session_start = ts
                    if session_end is None or ts > session_end:
                        session_end = ts

                total_turns += 1

                # --- Tool error detection (structural signal) ---
                if is_tool_error(msg):
                    tool_errors += 1

                # --- Skill invocation detection ---
                # Check slash command in user messages
                # JSONL messages nest role/content under "message" key
                inner = msg.get("message", {})
                if isinstance(inner, dict):
                    role = inner.get("role", msg.get("role", ""))
                    content = inner.get("content", msg.get("content", ""))
                else:
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                skill_name = None

                if role == "human" or role == "user":
                    if isinstance(content, str):
                        skill_name = extract_skill_name(content)
                    elif isinstance(content, list):
                        for part in content:
                            if isinstance(part, dict) and isinstance(part.get("text"), str):
                                skill_name = extract_skill_name(part["text"])
                                if skill_name:
                                    break

                # Check Skill tool call
                if skill_name is None:
                    is_skill, sname = is_skill_tool_call(msg)
                    if is_skill:
                        skill_name = sname

                if skill_name:
                    # Track consecutive calls (retry detection)
                    if last_skill == skill_name and (total_turns - last_skill_turn) <= 3:
                        consecutive_skill_calls[skill_name] = (
                            consecutive_skill_calls.get(skill_name, 1) + 1
                        )
                    else:
                        # Record correction turns for previous skill
                        if last_skill and turns_since_skill > 0:
                            correction_after_skill[last_skill] = (
                                correction_after_skill.get(last_skill, 0) + turns_since_skill
                            )

                    last_skill = skill_name
                    last_skill_turn = total_turns
                    turns_since_skill = 0

                    invocation: dict[str, Any] = {
                        "skill": skill_name,
                        "turn": total_turns,
                    }
                    if ts is not None:
                        invocation["timestamp"] = ts.isoformat()
                    skill_invocations.append(invocation)

                elif last_skill and role in ("human", "user"):
                    turns_since_skill += 1

    except (OSError, PermissionError) as e:
        return {
            "file": str(filepath),
            "error": str(e),
            "skill_invocations": [],
            "friction_signals": {},
            "secret_warnings": [],
        }

    # Detect session abandonment: session ended without natural completion
    # Heuristic: if the last message was from the user (no assistant response)
    # or session has high tool errors relative to turns
    if total_turns > 0 and tool_errors > total_turns * 0.3:
        abandoned = True

    # Record correction for the last skill
    if last_skill and turns_since_skill > 0:
        correction_after_skill[last_skill] = (
            correction_after_skill.get(last_skill, 0) + turns_since_skill
        )

    # Build friction signals per skill
    friction_signals: dict[str, dict[str, Any]] = {}
    seen_skills = set()
    for inv in skill_invocations:
        sn = inv["skill"]
        if sn and sn not in seen_skills:
            seen_skills.add(sn)
            friction_signals[sn] = {
                "retry_count": consecutive_skill_calls.get(sn, 0),
                "correction_turns": correction_after_skill.get(sn, 0),
                "session_abandoned": abandoned,
                "tool_error_count": tool_errors,
                "turns_to_completion": total_turns,
            }

    return {
        "file": str(filepath),
        "session_start": session_start.isoformat() if session_start else None,
        "session_end": session_end.isoformat() if session_end else None,
        "total_turns": total_turns,
        "skill_invocations": skill_invocations,
        "friction_signals": friction_signals,
        "secret_warnings": secret_warnings,
    }


# ---------------------------------------------------------------------------
# Project name inference
# ---------------------------------------------------------------------------

def infer_project_name() -> str:
    """Infer project filter from current working directory."""
    cwd = Path.cwd()
    # Convert /home/user/develop/my-project → -home-user-develop-my-project
    # This matches the typical ~/.claude/projects/ directory naming
    return str(cwd).replace("/", "-").lstrip("-")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect session friction signals for skill-improve analysis"
    )
    parser.add_argument(
        "--days", type=int, default=30,
        help="Number of days to look back (default: 30)"
    )
    parser.add_argument(
        "--project", type=str, default=None,
        help="Project name filter (default: inferred from cwd)"
    )
    parser.add_argument(
        "--all-projects", action="store_true", default=False,
        help="Scan all projects (ignore --project filter)"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output file path (default: stdout)"
    )
    args = parser.parse_args()

    # Determine project filter
    if args.all_projects:
        project_filter = None
    else:
        project_filter = args.project if args.project else infer_project_name()

    # Calculate cutoff date
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=args.days)

    # Discover session directories
    session_dirs = discover_session_dirs(project_filter)
    projects_scanned = [d.name for d in session_dirs]
    if not session_dirs:
        result = {
            "summary": {
                "project_filter": project_filter,
                "all_projects": args.all_projects,
                "projects_scanned": [],
                "days": args.days,
                "sessions_found": 0,
                "total_skill_invocations": 0,
                "collection_timestamp": now.isoformat(),
            },
            "sessions": [],
            "skill_invocations": [],
            "friction_signals": {},
            "secret_warnings": [],
        }
        _output_result(result, args.output)
        return

    # Find JSONL files
    jsonl_files = find_jsonl_files(session_dirs)

    # Process each session file (streaming)
    sessions: list[dict[str, Any]] = []
    all_invocations: list[dict[str, Any]] = []
    all_friction: dict[str, dict[str, Any]] = {}
    all_secrets: list[dict[str, str]] = []

    for jf in jsonl_files:
        session_result = process_session_file(jf, cutoff)
        if session_result.get("error"):
            sessions.append(session_result)
            continue

        if session_result["skill_invocations"]:
            sessions.append(session_result)
            all_invocations.extend(session_result["skill_invocations"])

            # Merge friction signals (aggregate across sessions)
            for skill, signals in session_result["friction_signals"].items():
                if skill not in all_friction:
                    all_friction[skill] = {
                        "retry_count": 0,
                        "correction_turns": 0,
                        "session_abandoned_count": 0,
                        "tool_error_count": 0,
                        "total_turns_to_completion": 0,
                        "invocation_count": 0,
                    }
                agg = all_friction[skill]
                agg["retry_count"] += signals["retry_count"]
                agg["correction_turns"] += signals["correction_turns"]
                if signals["session_abandoned"]:
                    agg["session_abandoned_count"] += 1
                agg["tool_error_count"] += signals["tool_error_count"]
                agg["total_turns_to_completion"] += signals["turns_to_completion"]
                agg["invocation_count"] += 1

        all_secrets.extend(session_result.get("secret_warnings", []))

    # Build output
    result = {
        "summary": {
            "project_filter": project_filter,
            "all_projects": args.all_projects,
            "projects_scanned": projects_scanned,
            "days": args.days,
            "sessions_found": len(sessions),
            "total_skill_invocations": len(all_invocations),
            "unique_skills_used": list(all_friction.keys()),
            "collection_timestamp": now.isoformat(),
        },
        "sessions": [
            {
                "file": s["file"],
                "session_start": s.get("session_start"),
                "session_end": s.get("session_end"),
                "total_turns": s.get("total_turns", 0),
                "skill_count": len(s.get("skill_invocations", [])),
            }
            for s in sessions
            if not s.get("error")
        ],
        "skill_invocations": all_invocations,
        "friction_signals": all_friction,
        "secret_warnings": _deduplicate_secrets(all_secrets),
    }

    _output_result(result, args.output)


def _deduplicate_secrets(secrets: list[dict[str, str]]) -> list[dict[str, str]]:
    """Deduplicate secret warnings."""
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for s in secrets:
        key = f"{s['type']}:{s['masked']}"
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique


def _output_result(result: dict[str, Any], output_path: str | None) -> None:
    """Write result JSON to file or stdout."""
    json_str = json.dumps(result, indent=2, ensure_ascii=False)
    if output_path:
        tmp_path = output_path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(json_str)
                f.write("\n")
            os.replace(tmp_path, output_path)
        finally:
            # Ensure temp file is cleaned up on error
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass
    else:
        print(json_str)


if __name__ == "__main__":
    main()
