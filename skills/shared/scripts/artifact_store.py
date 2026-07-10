#!/usr/bin/env python3
"""Resolve and validate the provider-independent Agent Artifact Store."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from frontmatter import parse_frontmatter_fields  # noqa: E402


CONFIG_REL = Path(".agents/artifacts.yml")
DEFAULT_ROOT_REL = Path(".agents/artifacts")
LEGACY_RELS = (
    Path("docs/plans"),
    Path("docs/issues"),
    Path("docs/ideas"),
    Path("docs/loop"),
)
LEGACY_FILES = {
    Path("docs/status.md"): DEFAULT_ROOT_REL / "status.md",
    Path("docs/session-history.md"): DEFAULT_ROOT_REL / "session-history.md",
}
VISIBILITIES = {"local", "shared-private", "public"}
DEFAULT_POLICY = {
    "schema_version": 1,
    "root": DEFAULT_ROOT_REL.as_posix(),
    "visibility": "local",
    "worktree_scope": "worktree",
}
IGNORE_RULE = "/.agents/artifacts/"
ARTIFACT_KINDS = ("plans", "issues", "ideas", "loop")

# Runtime area (machine-specific, never shared, never migrated). See the
# "Runtime area" section of skills/shared/references/artifact-store.md. Files
# matching these patterns are runtime state, not artifacts; migration classifies
# them as suggested_action "skip".
RUNTIME_BASENAMES = frozenset({
    ".STOP",
    ".STOP.hard",
    ".polling-initialized",
    ".last_archive_month",
    "session.json",
})
_RUNTIME_TMP_PREFIXES = ("session.json.tmp.", "session.json.corrupt.")

# Derived indexes: regenerated deterministically from the entries, never merged.
# See the "Derived indexes" section of the Artifact Store contract. Only
# top-level *.md entry files are indexed: every subdirectory (archives/, and for
# issues done/, failed/, but also queue-state dirs like ready/ or running/) is
# excluded — the index covers open flat entries, nothing below them.
INDEX_FILENAMES = {"ideas": "idea-status.md", "issues": "issue-status.md"}
INDEX_TITLES = {"ideas": "Idea Status", "issues": "Issue Status"}
_SLUG_TS_RE = re.compile(r"^(\d{14})")


def _is_runtime_source(source_rel: str) -> bool:
    """True if a legacy path is machine-specific runtime state, not an artifact."""
    parts = PurePosixPath(source_rel).parts
    name = parts[-1] if parts else ""
    if name in RUNTIME_BASENAMES:
        return True
    if any(name.startswith(prefix) for prefix in _RUNTIME_TMP_PREFIXES):
        return True
    # loop event log and its monthly archives are runtime; loop dossiers are not.
    if "loop" in parts:
        if name == "events.jsonl":
            return True
        if name.endswith(".jsonl") and "archives" in parts:
            return True
    return False


class ArtifactStoreError(ValueError):
    """Policy or store violates the Artifact Store contract."""


def _parse_scalar(value: str):
    value = value.strip()
    if not value:
        raise ArtifactStoreError("empty configuration value")
    if value.isdigit():
        return int(value)
    if value[0:1] in {"'", '"'}:
        if len(value) < 2 or value[-1] != value[0]:
            raise ArtifactStoreError("unterminated quoted configuration value")
        return value[1:-1]
    return value


def parse_policy(text: str) -> dict:
    """Parse the intentionally flat v1 YAML subset without external dependencies."""
    result = {}
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if raw[:1].isspace() or ":" not in line:
            raise ArtifactStoreError(f"unsupported policy syntax at line {number}")
        key, value = line.split(":", 1)
        key = key.strip()
        if key in result:
            raise ArtifactStoreError(f"duplicate policy key: {key}")
        result[key] = _parse_scalar(value)
    return result


def load_policy(repo: Path) -> tuple[dict, bool]:
    config = repo / CONFIG_REL
    if not config.exists():
        return dict(DEFAULT_POLICY), False
    if config.is_symlink() or not config.is_file():
        raise ArtifactStoreError(f"policy must be a regular file: {CONFIG_REL}")
    policy = parse_policy(config.read_text(encoding="utf-8"))
    unknown = set(policy) - set(DEFAULT_POLICY)
    missing = set(DEFAULT_POLICY) - set(policy)
    if unknown:
        raise ArtifactStoreError(f"unknown policy keys: {', '.join(sorted(unknown))}")
    if missing:
        raise ArtifactStoreError(f"missing policy keys: {', '.join(sorted(missing))}")
    if policy["schema_version"] != 1:
        raise ArtifactStoreError("unsupported schema_version")
    if policy["root"] != DEFAULT_ROOT_REL.as_posix():
        raise ArtifactStoreError("v1 root must be .agents/artifacts")
    if policy["visibility"] not in VISIBILITIES:
        raise ArtifactStoreError("invalid visibility")
    if policy["worktree_scope"] != "worktree":
        raise ArtifactStoreError("v1 worktree_scope must be worktree")
    return policy, True


def _contains_files(path: Path) -> bool:
    if not path.is_dir():
        return False
    return any(item.is_file() or item.is_symlink() for item in path.rglob("*"))


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False,
    )


def _validate_containment(repo: Path, root: Path) -> None:
    repo_real = repo.resolve()
    candidate = root
    while candidate != repo and candidate != candidate.parent:
        if candidate.is_symlink():
            raise ArtifactStoreError(f"artifact root path contains symlink: {candidate}")
        candidate = candidate.parent
    root_real = root.resolve(strict=False)
    try:
        root_real.relative_to(repo_real)
    except ValueError as exc:
        raise ArtifactStoreError("artifact root escapes repository") from exc


def inspect(repo_path: str | os.PathLike = ".", validate_git: bool = True) -> dict:
    repo = Path(repo_path).resolve()
    policy, explicit = load_policy(repo)
    root = repo / policy["root"]
    _validate_containment(repo, root)

    legacy = [p.as_posix() for p in LEGACY_RELS if _contains_files(repo / p)]
    legacy.extend(p.as_posix() for p in LEGACY_FILES if (repo / p).is_file())
    canonical_has_files = _contains_files(root)
    state = "split-brain" if legacy and canonical_has_files else (
        "legacy" if legacy else ("canonical" if canonical_has_files else "empty")
    )
    errors = []

    if not explicit and policy["visibility"] != "local":
        errors.append("implicit policy may only use local visibility")
    if validate_git:
        if explicit and _run_git(repo, "check-ignore", "-q", CONFIG_REL.as_posix()).returncode == 0:
            errors.append("artifact policy is ignored by Git")
        ignore = _run_git(repo, "check-ignore", "-q", policy["root"] + "/.probe")
        if policy["visibility"] in {"local", "shared-private"}:
            tracked = _run_git(repo, "ls-files", "--", policy["root"]).stdout.splitlines()
            if tracked:
                errors.append(f"{policy['visibility']} artifact store contains Git-tracked files")
            if ignore.returncode != 0:
                errors.append(f"{policy['visibility']} artifact store is not ignored by Git")
        elif policy["visibility"] == "public" and ignore.returncode == 0:
            errors.append("public artifact store is ignored by Git")
    if state == "split-brain":
        errors.append("legacy and canonical stores both contain artifacts")

    return {
        "repo": str(repo),
        "config": CONFIG_REL.as_posix(),
        "explicit_policy": explicit,
        "policy": policy,
        "root": str(root),
        "state": state,
        "legacy_roots": legacy,
        "errors": errors,
        "writable": not errors and state != "legacy",
    }


def require_writable(repo_path: str | os.PathLike = ".") -> dict:
    result = inspect(repo_path)
    if result["state"] == "legacy":
        raise ArtifactStoreError("legacy artifacts require migration before writing")
    if result["errors"]:
        raise ArtifactStoreError("; ".join(result["errors"]))
    return result


def initialize(repo_path: str | os.PathLike = ".") -> dict:
    """Create an idempotent safe local store, refusing legacy state."""
    repo = Path(repo_path).resolve()
    before = inspect(repo, validate_git=False)
    if before["legacy_roots"]:
        raise ArtifactStoreError("legacy artifacts require migration before initialization")
    config = repo / CONFIG_REL
    if not config.exists():
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(
            "schema_version: 1\nroot: .agents/artifacts\n"
            "visibility: local\nworktree_scope: worktree\n",
            encoding="utf-8",
        )
    policy, _ = load_policy(repo)
    if policy["visibility"] == "local":
        ignore = repo / ".gitignore"
        text = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
        if IGNORE_RULE not in {line.strip() for line in text.splitlines()}:
            suffix = "" if not text or text.endswith("\n") else "\n"
            ignore.write_text(text + suffix + "\n# Agent Artifact Store\n" + IGNORE_RULE + "\n", encoding="utf-8")
    root = repo / policy["root"]
    root.mkdir(parents=True, exist_ok=True)
    for kind in ARTIFACT_KINDS:
        (root / kind).mkdir(exist_ok=True)
    result = inspect(repo)
    if result["errors"]:
        raise ArtifactStoreError("; ".join(result["errors"]))
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def migration_inventory(repo_path: str | os.PathLike = ".") -> dict:
    """Return a read-only inventory with every entry requiring a human decision."""
    repo = Path(repo_path).resolve()
    entries = []
    for legacy in LEGACY_RELS:
        base = repo / legacy
        if not base.is_dir():
            continue
        kind = legacy.name
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            source_rel = path.relative_to(repo).as_posix()
            entries.append({
                "source": source_rel,
                "destination": (DEFAULT_ROOT_REL / kind / path.relative_to(base)).as_posix(),
                "sha256": _sha256(path),
                "action": "review",
                "suggested_action": "skip" if _is_runtime_source(source_rel) else "review",
            })
    for source_rel, destination_rel in LEGACY_FILES.items():
        path = repo / source_rel
        if path.is_file() and not path.is_symlink():
            entries.append({
                "source": source_rel.as_posix(),
                "destination": destination_rel.as_posix(),
                "sha256": _sha256(path),
                "action": "review",
                "suggested_action": (
                    "skip" if _is_runtime_source(source_rel.as_posix()) else "review"
                ),
            })
    return {
        "schema_version": 1,
        "history_warning": "Moving tracked files does not remove them from Git history, forks, or caches.",
        "allowed_actions": ["move", "copy", "keep", "skip"],
        "entries": entries,
    }


def stage_migration(repo_path: str | os.PathLike, decisions_path: str | os.PathLike) -> dict:
    """Copy approved move/copy entries and write a verification marker; never delete."""
    repo = Path(repo_path).resolve()
    decisions = json.loads(Path(decisions_path).read_text(encoding="utf-8"))
    entries = decisions.get("entries")
    if decisions.get("schema_version") != 1 or not isinstance(entries, list):
        raise ArtifactStoreError("invalid migration decision file")
    unresolved = [e.get("source", "<unknown>") for e in entries if e.get("action") == "review"]
    if unresolved:
        raise ArtifactStoreError(f"unresolved migration entries: {len(unresolved)}")
    allowed = {"move", "copy", "keep", "skip"}
    staged = []
    for entry in entries:
        if entry.get("action") not in allowed:
            raise ArtifactStoreError(f"invalid migration action: {entry.get('action')}")
        source = repo / entry["source"]
        expected = entry["sha256"]
        if not source.is_file() or source.is_symlink() or _sha256(source) != expected:
            raise ArtifactStoreError(f"source changed since inventory: {entry['source']}")
        if entry["action"] not in {"move", "copy"}:
            continue
        destination = repo / entry["destination"]
        _validate_containment(repo, destination)
        if destination.exists() and _sha256(destination) != expected:
            raise ArtifactStoreError(f"destination conflict: {entry['destination']}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(source, destination)
        staged.append(entry["destination"])
    marker = repo / DEFAULT_ROOT_REL / ".migration-state.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(decisions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"staged": staged, "marker": marker.relative_to(repo).as_posix(), "source_removed": False}


def finalize_migration(
    repo_path: str | os.PathLike = ".",
    *,
    confirm_remove_source: bool = False,
    confirm_public_history: bool = False,
) -> dict:
    """Verify staged files, then remove only entries explicitly classified as move."""
    if not confirm_remove_source or not confirm_public_history:
        raise ArtifactStoreError("finalize requires both source-removal and public-history confirmations")
    repo = Path(repo_path).resolve()
    marker = repo / DEFAULT_ROOT_REL / ".migration-state.json"
    if not marker.is_file() or marker.is_symlink():
        raise ArtifactStoreError("staged migration marker not found")
    decisions = json.loads(marker.read_text(encoding="utf-8"))
    removed = []
    for entry in decisions.get("entries", []):
        if entry.get("action") not in {"move", "copy"}:
            continue
        destination = repo / entry["destination"]
        if not destination.is_file() or _sha256(destination) != entry["sha256"]:
            raise ArtifactStoreError(f"staged destination failed verification: {entry['destination']}")
        if entry["action"] == "move":
            source = repo / entry["source"]
            if source.is_file() and _sha256(source) == entry["sha256"]:
                source.unlink()
                removed.append(entry["source"])
    for legacy in LEGACY_RELS:
        base = repo / legacy
        if base.is_dir():
            for directory in sorted((p for p in base.rglob("*") if p.is_dir()), reverse=True):
                try:
                    directory.rmdir()
                except OSError:
                    pass
            try:
                base.rmdir()
            except OSError:
                pass
    marker.unlink()
    return {"removed": removed, "verified": True}


def _cell(text: str) -> str:
    """Make arbitrary entry text safe inside a Markdown table cell.

    Escapes literal pipes and collapses any whitespace (including newlines) so a
    single entry can never break the table's row/column structure.
    """
    return " ".join(text.replace("|", "\\|").split())


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _bold_label(text: str, label: str) -> str:
    pattern = re.compile(r"^\*\*" + re.escape(label) + r":\*\*\s*(.*)$")
    for raw in text.splitlines():
        match = pattern.match(raw.strip())
        if match:
            return match.group(1).strip()
    return ""


def _section_body(text: str, heading: str) -> str:
    collecting = False
    body = []
    for line in text.splitlines():
        if line.strip() == heading:
            collecting = True
            continue
        if collecting and line.startswith("## "):
            break
        if collecting:
            body.append(line)
    return "\n".join(body).strip()


def _slug_timestamp(slug: str) -> str:
    match = _SLUG_TS_RE.match(slug)
    if not match:
        return ""
    digits = match.group(1)
    return (
        f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]} "
        f"{digits[8:10]}:{digits[10:12]}:{digits[12:14]}"
    )


def _parse_idea_entry(slug: str, text: str) -> dict:
    return {
        "slug": slug,
        "title": _first_heading(text) or slug,
        "created": _bold_label(text, "Created"),
        "status": _bold_label(text, "Status"),
        "tags": _bold_label(text, "Tags"),
        "summary": _section_body(text, "## Summary"),
    }


def _parse_issue_entry(slug: str, text: str) -> dict:
    fields = parse_frontmatter_fields(text)
    return {
        "slug": slug,
        "created": fields.get("created", ""),
        "tags": fields.get("tags", ""),
        "summary": _section_body(text, "## 概要"),
    }


def _collect_index_entries(kind_dir: Path, kind: str) -> list:
    """Parse top-level entries only; every subdirectory is excluded (see contract)."""
    if not kind_dir.is_dir():
        return []
    index_name = INDEX_FILENAMES[kind]
    parse = _parse_idea_entry if kind == "ideas" else _parse_issue_entry
    entries = []
    for path in sorted(kind_dir.glob("*.md")):
        if not path.is_file() or path.is_symlink():
            continue
        if path.name == index_name:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ArtifactStoreError(
                f"entry is not valid utf-8: {path.name} ({exc.reason})"
            ) from exc
        entries.append(parse(path.stem, text))
    return sorted(entries, key=lambda entry: entry["slug"])


def _render_index(kind: str, entries: list) -> str:
    last_updated = max((_slug_timestamp(e["slug"]) for e in entries), default="")
    lines = [f"# {INDEX_TITLES[kind]}", "", f"**Last Updated:** {last_updated}", ""]
    if kind == "ideas":
        lines.append("| Idea | Tags | Created | Status | Summary |")
        lines.append("|------|------|---------|--------|---------|")
        for entry in entries:
            # slug はファイル名由来だがテーブル入力としては信用しない（| を含みうる）
            lines.append(
                f"| [{_cell(entry['title'])}]({_cell(entry['slug'])}.md) "
                f"| {_cell(entry['tags'])} | {_cell(entry['created'])} "
                f"| {_cell(entry['status'])} | {_cell(entry['summary'])} |"
            )
    else:
        lines.append("| Issue | Tags | Created | Summary |")
        lines.append("|-------|------|---------|---------|")
        for entry in entries:
            lines.append(
                f"| [{_cell(entry['slug'])}]({_cell(entry['slug'])}.md) "
                f"| `{_cell(entry['tags'])}` | {_cell(entry['created'])} "
                f"| {_cell(entry['summary'])} |"
            )
    return "\n".join(lines) + "\n"


def rebuild_index(repo_path: str | os.PathLike = ".", kind: str = "ideas") -> dict:
    """Deterministically regenerate a derived index from its entries.

    The index is a derived cache: the output is a pure function of the top-level
    entry files (byte-identical for identical input) and is never merged with the
    previous index. Refuses to write when the store is not writable
    (legacy / split-brain), so it never resurrects state in a broken store.
    """
    if kind not in INDEX_FILENAMES:
        raise ArtifactStoreError(f"unknown index kind: {kind}")
    result = require_writable(repo_path)
    repo = Path(repo_path).resolve()
    root = Path(result["root"])
    kind_dir = root / kind
    index_path = kind_dir / INDEX_FILENAMES[kind]
    _validate_containment(repo, index_path)
    entries = _collect_index_entries(kind_dir, kind)
    kind_dir.mkdir(parents=True, exist_ok=True)
    index_path.write_text(_render_index(kind, entries), encoding="utf-8")
    return {
        "kind": kind,
        "index": index_path.relative_to(repo).as_posix(),
        "entries": len(entries),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "resolve", "status", "init", "rebuild-index",
            "migrate-check", "migrate-stage", "migrate-finalize",
        ),
    )
    parser.add_argument("--repo", default=".")
    parser.add_argument("--require-writable", action="store_true")
    parser.add_argument("--kind", choices=tuple(INDEX_FILENAMES))
    parser.add_argument("--decisions")
    parser.add_argument("--output")
    parser.add_argument("--confirm-remove-source", action="store_true")
    parser.add_argument("--confirm-public-history", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            result = initialize(args.repo)
        elif args.command == "rebuild-index":
            if not args.kind:
                raise ArtifactStoreError("rebuild-index requires --kind (ideas|issues)")
            result = rebuild_index(args.repo, args.kind)
        elif args.command == "migrate-check":
            result = migration_inventory(args.repo)
        elif args.command == "migrate-stage":
            if not args.decisions:
                raise ArtifactStoreError("migrate-stage requires --decisions")
            result = stage_migration(args.repo, args.decisions)
        elif args.command == "migrate-finalize":
            result = finalize_migration(
                args.repo,
                confirm_remove_source=args.confirm_remove_source,
                confirm_public_history=args.confirm_public_history,
            )
        else:
            result = require_writable(args.repo) if args.require_writable else inspect(args.repo)
    except ArtifactStoreError as exc:
        print(f"artifact-store: {exc}", file=sys.stderr)
        return 2
    if args.command == "resolve":
        print(result["root"])
    else:
        rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.output:
            Path(args.output).write_text(rendered, encoding="utf-8")
        else:
            print(rendered, end="")
    return 0 if not result.get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
