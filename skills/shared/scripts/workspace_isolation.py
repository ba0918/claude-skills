#!/usr/bin/env python3
"""Workspace-isolation policy and Git workspace identity primitives."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import subprocess


POLICY_REL = Path(".agents/workspace.yml")
MODES = frozenset({"inplace", "worktree"})


class WorkspaceIsolationError(ValueError):
    """Workspace policy or identity violates the isolation contract."""


@dataclass(frozen=True)
class WorkspaceIdentity:
    main_tree_path: Path
    worktree_path: Path
    git_common_dir: Path
    git_dir: Path
    worktree_id: str
    is_linked_worktree: bool
    is_submodule: bool


def _parse_policy(text: str) -> str:
    values = {}
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if raw[:1].isspace() or ":" not in line:
            raise WorkspaceIsolationError(f"invalid workspace policy at line {number}")
        key, value = (part.strip() for part in line.split(":", 1))
        if key in values:
            raise WorkspaceIsolationError(f"duplicate workspace policy key: {key}")
        values[key] = value.strip("'\"")
    if set(values) != {"isolation"}:
        raise WorkspaceIsolationError("workspace policy must contain exactly isolation")
    if values["isolation"] not in MODES:
        raise WorkspaceIsolationError("isolation must be worktree or inplace")
    return values["isolation"]


def resolve_isolation(repo_path: str | Path = ".", *, override: str | None = None) -> str:
    """Resolve one-shot override, tracked policy, then the compatible default."""
    if override is not None:
        if override not in MODES:
            raise WorkspaceIsolationError("invalid isolation override")
        return override
    policy = Path(repo_path).resolve() / POLICY_REL
    if not policy.exists() and not policy.is_symlink():
        return "inplace"
    if policy.is_symlink() or not policy.is_file():
        raise WorkspaceIsolationError("workspace policy must be a regular file")
    return _parse_policy(policy.read_text(encoding="utf-8"))


def _git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=path, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False,
    )
    if result.returncode:
        raise WorkspaceIsolationError(result.stderr.strip() or "not a Git workspace")
    return result.stdout.strip()


def _resolve_git_path(worktree: Path, value: str) -> Path:
    candidate = Path(value)
    return (candidate if candidate.is_absolute() else worktree / candidate).resolve()


def identify_workspace(
    path: str | Path = ".", *, require_linked: bool = False,
) -> WorkspaceIdentity:
    """Identify a checkout via Git's common-dir metadata, excluding submodules."""
    worktree = Path(_git(Path(path).resolve(), "rev-parse", "--show-toplevel")).resolve()
    common = _resolve_git_path(worktree, _git(worktree, "rev-parse", "--git-common-dir"))
    git_dir = _resolve_git_path(worktree, _git(worktree, "rev-parse", "--git-dir"))
    is_submodule = "modules" in common.parts and common.name != ".git"
    is_linked = git_dir != common and not is_submodule
    main = common.parent if common.name == ".git" else worktree
    if require_linked and is_submodule:
        raise WorkspaceIsolationError("submodule workspaces are excluded")
    if require_linked and not is_linked:
        raise WorkspaceIsolationError("workspace is not a linked worktree")
    identity_material = f"{common}\0{git_dir}".encode()
    return WorkspaceIdentity(
        main_tree_path=main.resolve(),
        worktree_path=worktree,
        git_common_dir=common,
        git_dir=git_dir,
        worktree_id=hashlib.sha256(identity_material).hexdigest(),
        is_linked_worktree=is_linked,
        is_submodule=is_submodule,
    )
