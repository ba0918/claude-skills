#!/usr/bin/env python3
"""Transactional transport primitives for worktree satellite artifact stores."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import shutil
import stat
import tempfile

from workspace_isolation import WorkspaceIsolationError, identify_workspace


ABSENT = "ABSENT"
STORE_REL = Path(".agents/artifacts")
RUNS_REL = Path(".agents/runtime/satellite-runs")
CAPABILITY_REL = Path(".agents/runtime/satellite-capability")
SINGLETONS = frozenset({"status.md", "session-history.md"})
DERIVED = frozenset({"idea-status.md", "issue-status.md"})
EXCLUDED_PARTS = frozenset({"archives", "done", "failed", "ready", "running"})
RUN_ID_RE = __import__("re").compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
DISCARD_REASON_CODES = frozenset({
    "REJECTED",
    "USER_REJECTED",
    "MERGE_REVERTED",
    "VERIFICATION_FAILED",
    "SUPERSEDED",
})
ALLOWED_EDGES = {
    "created": {"active", "failed_readonly"},
    "active": {"harvesting", "failed_readonly"},
    "harvesting": {"staged", "recovery_required"},
    "staged": {"published", "discarded", "recovery_required"},
    "published": {"cleanup_allowed", "recovery_required"},
    "discarded": {"cleanup_allowed", "recovery_required"},
    "failed_readonly": {"active", "harvesting", "recovery_required"},
    "recovery_required": {"harvesting", "staged"},
}


class TransportError(RuntimeError):
    """Satellite transport failed closed."""


@dataclass(frozen=True)
class RunRecord:
    runtime_dir: Path
    capability: str
    capability_path: Path


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")


def derive_satellite_run_id(batch_run_id: str, plan_id: str) -> str:
    """Return the collision-free lifecycle identity for one plan in a batch."""
    if not RUN_ID_RE.fullmatch(batch_run_id):
        raise TransportError("invalid batch run id")
    if not RUN_ID_RE.fullmatch(plan_id):
        raise TransportError("invalid plan id")
    satellite_run_id = f"{batch_run_id}-{plan_id}"
    if not RUN_ID_RE.fullmatch(satellite_run_id):
        raise TransportError("derived satellite run id is too long")
    return satellite_run_id


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_utc_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00").tzinfo == timezone.utc
    except ValueError:
        return False


def _atomic_bytes(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def _locked(runtime_dir: Path):
    lock_path = runtime_dir / "lifecycle.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def _load(runtime_dir: Path) -> dict:
    try:
        return json.loads((runtime_dir / "provenance.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TransportError("invalid or missing canonical provenance") from exc


def _save(runtime_dir: Path, provenance: dict) -> None:
    _atomic_bytes(runtime_dir / "provenance.json", canonical_json(provenance))


def _safe_relative(value: str | Path) -> str:
    raw = Path(value).as_posix()
    path = PurePosixPath(raw)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise TransportError("artifact path is not a normalized relative path")
    return path.as_posix()


def _strict_run_id(run_id: str) -> str:
    if not isinstance(run_id, str) or not RUN_ID_RE.fullmatch(run_id):
        raise TransportError("run_id must be a single safe identifier")
    return run_id


def _hash_path(path: Path) -> str:
    return _digest(path.read_bytes()) if path.is_file() and not path.is_symlink() else ABSENT


def create_ingress_manifest(
    store: Path, run_id: str, relative_paths: list[str | Path],
) -> tuple[dict, str]:
    entries = []
    for relative in sorted({_safe_relative(item) for item in relative_paths}):
        source = store / relative
        if source.is_symlink() or not source.is_file():
            raise TransportError(f"ingress source is not a regular file: {relative}")
        entries.append({
            "relative_path": relative,
            "file_type": "regular",
            "content_hash": _hash_path(source),
        })
    manifest = {
        "schema_version": 1, "run_id": run_id, "created_at": _now(), "entries": entries,
    }
    return manifest, _digest(canonical_json(manifest))


def pid_start_time(pid: int, *, reader=None) -> str:
    reader = reader or (lambda path: Path(path).read_text(encoding="utf-8"))
    try:
        stat = reader(f"/proc/{pid}/stat")
        tail = stat[stat.rindex(")") + 1:].split()
        return tail[19]
    except (OSError, ValueError, IndexError):
        return "unavailable"


def _pid_start_time(pid: int) -> str:
    return pid_start_time(pid)


def _reject_control_symlinks(root: Path, relatives: tuple[Path, ...]) -> None:
    if root.is_symlink():
        raise TransportError(f"control path contains symlink: {root}")
    for relative in relatives:
        cursor = root
        for part in relative.parts:
            cursor /= part
            if cursor.is_symlink():
                raise TransportError(f"control path contains symlink: {cursor}")


def create_run(
    main_tree: Path,
    worktree: Path,
    run_id: str,
    pinned_plan: str | Path,
) -> RunRecord:
    main_tree, worktree = Path(main_tree), Path(worktree)
    _reject_control_symlinks(worktree, (Path(".agents"), STORE_REL, Path(".agents/runtime")))
    _reject_control_symlinks(main_tree, (Path(".agents"), RUNS_REL))
    main_tree, worktree = main_tree.resolve(), worktree.resolve()
    run_id = _strict_run_id(run_id)
    try:
        identity = identify_workspace(worktree, require_linked=True)
    except WorkspaceIsolationError as exc:
        raise TransportError(f"invalid Git workspace identity: {exc}") from exc
    if identity.main_tree_path != main_tree:
        raise TransportError("worktree does not belong to main tree")
    plan = _safe_relative(pinned_plan)
    _validate_identity_and_destination({
        "main_tree_path": str(main_tree),
        "worktree_path": str(worktree),
        "worktree_id": identity.worktree_id,
    }, plan)
    runtime_dir = main_tree / RUNS_REL / run_id
    runtime_dir.mkdir(parents=True, exist_ok=False)
    manifest, manifest_digest = create_ingress_manifest(main_tree / STORE_REL, run_id, [plan])
    destination = worktree / STORE_REL / plan
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(main_tree / STORE_REL / plan, destination)
    capability = secrets.token_urlsafe(32)
    capability_path = worktree / CAPABILITY_REL
    _atomic_bytes(capability_path, capability.encode())
    _atomic_bytes(runtime_dir / "ingress-manifest.json", canonical_json(manifest))
    provenance = {
        "schema_version": 1, "run_id": run_id, "main_tree_path": str(main_tree),
        "worktree_path": str(worktree), "worktree_id": identity.worktree_id, "pinned_plan": plan,
        "created_at": _now(), "owner_pid": os.getpid(),
        "owner_pid_start_time": _pid_start_time(os.getpid()),
        "ingress_manifest_digest": manifest_digest,
        "capability_digest": _digest(capability.encode()), "capability_state": "live",
        "capability_epoch": 1, "lifecycle_state": "created", "lifecycle_version": 0,
        "staging_disposition": "pending",
    }
    _save(runtime_dir, provenance)
    return RunRecord(runtime_dir, capability, capability_path)


def _validate_destination(relative: str) -> None:
    relative = _safe_relative(relative)
    path = PurePosixPath(relative)
    if (path.name in SINGLETONS or path.name in DERIVED
            or path.name == "events.jsonl" or any(part in EXCLUDED_PARTS for part in path.parts)
            or any(part.startswith(".") for part in path.parts)):
        raise TransportError("destination is not mergeable satellite state")


def _validate_identity_and_destination(provenance: dict, relative: str | None = None) -> Path:
    try:
        identity = identify_workspace(provenance["worktree_path"], require_linked=True)
    except (WorkspaceIsolationError, KeyError) as exc:
        raise TransportError(f"Git workspace identity unavailable: {exc}") from exc
    if (str(identity.main_tree_path) != provenance.get("main_tree_path")
            or str(identity.worktree_path) != provenance.get("worktree_path")
            or identity.worktree_id != provenance.get("worktree_id")):
        raise TransportError("Git workspace identity changed")
    _reject_control_symlinks(
        identity.worktree_path, (Path(".agents"), STORE_REL, Path(".agents/runtime")),
    )
    _reject_control_symlinks(
        identity.main_tree_path, (Path(".agents"), RUNS_REL),
    )
    store = identity.worktree_path / STORE_REL
    if store.is_symlink():
        raise TransportError("satellite store must not be a symlink")
    if relative is not None:
        candidate = store / relative
        cursor = candidate.parent
        while cursor != store:
            if cursor.is_symlink():
                raise TransportError("destination path contains symlink")
            cursor = cursor.parent
        try:
            candidate.resolve(strict=False).relative_to(store.resolve())
        except ValueError as exc:
            raise TransportError("destination escapes satellite store") from exc
    return store


def authorize_write(runtime_dir: Path, capability: str, relative_path: str | Path) -> None:
    """Validate a prospective write only; this is never durable authorization."""
    relative = _safe_relative(relative_path)
    _validate_destination(relative)
    with _locked(runtime_dir):
        provenance = _load(runtime_dir)
        if provenance["lifecycle_state"] != "active":
            raise TransportError("satellite write requires active lifecycle")
        if provenance["capability_state"] != "live":
            raise TransportError("satellite capability is not live")
        if not secrets.compare_digest(provenance["capability_digest"],
                                      _digest(capability.encode())):
            raise TransportError("satellite capability mismatch")
        _validate_identity_and_destination(provenance, relative)


def durable_write(
    runtime_dir: Path, capability: str, relative_path: str | Path, data: bytes,
) -> None:
    """Authorize and atomically commit one mergeable write under one lifecycle lock."""
    relative = _safe_relative(relative_path)
    _validate_destination(relative)
    with _locked(runtime_dir):
        provenance = _load(runtime_dir)
        if provenance["lifecycle_state"] != "active":
            raise TransportError("satellite write requires active lifecycle")
        if provenance["capability_state"] != "live" or not secrets.compare_digest(
            provenance["capability_digest"], _digest(capability.encode()),
        ):
            raise TransportError("satellite capability denied")
        store = _validate_identity_and_destination(provenance, relative)
        destination = store / relative
        _atomic_bytes(destination, data)


def lifecycle_transition(
    runtime_dir: Path, expected_state: str, expected_version: int, target_state: str,
    *, capability: str | None = None, consume: bool = False,
    expected_epoch: int | None = None,
) -> dict:
    with _locked(runtime_dir):
        provenance = _load(runtime_dir)
        _validate_identity_and_destination(provenance)
        if (provenance["lifecycle_state"], provenance["lifecycle_version"]) != (
            expected_state, expected_version,
        ):
            raise TransportError("stale lifecycle compare-and-swap")
        if target_state not in ALLOWED_EDGES.get(expected_state, set()):
            raise TransportError("illegal lifecycle transition")
        if consume:
            if expected_epoch != provenance["capability_epoch"]:
                raise TransportError("stale capability epoch")
            if provenance["capability_state"] != "live" or capability is None or not (
                secrets.compare_digest(provenance["capability_digest"], _digest(capability.encode()))
            ):
                raise TransportError("capability consumption failed")
            provenance["capability_state"] = "consumed"
            Path(provenance["worktree_path"]).joinpath(CAPABILITY_REL).unlink(missing_ok=True)
        provenance["lifecycle_state"] = target_state
        provenance["lifecycle_version"] += 1
        _save(runtime_dir, provenance)
        return provenance


def revoke_capability(runtime_dir: Path, expected_epoch: int) -> dict:
    with _locked(runtime_dir):
        provenance = _load(runtime_dir)
        _validate_identity_and_destination(provenance)
        if provenance["capability_epoch"] != expected_epoch:
            raise TransportError("stale capability epoch")
        if provenance["capability_state"] == "consumed":
            return provenance
        if provenance["capability_state"] != "live":
            raise TransportError("capability is not live")
        provenance["capability_state"] = "revoked"
        Path(provenance["worktree_path"]).joinpath(CAPABILITY_REL).unlink(missing_ok=True)
        _save(runtime_dir, provenance)
        return provenance


def rotate_capability(
    runtime_dir: Path, *, expected_epoch: int, expected_version: int,
) -> str:
    with _locked(runtime_dir):
        provenance = _load(runtime_dir)
        if (provenance["lifecycle_state"], provenance["lifecycle_version"],
                provenance["capability_epoch"]) != (
                "failed_readonly", expected_version, expected_epoch):
            raise TransportError("capability rotation requires exact failed-readonly CAS")
        if provenance["capability_state"] not in {"revoked", "consumed"}:
            raise TransportError("live capability cannot be rotated")
        capability = secrets.token_urlsafe(32)
        _validate_identity_and_destination(provenance)
        provenance["capability_digest"] = _digest(capability.encode())
        provenance["capability_state"] = "live"
        provenance["capability_epoch"] += 1
        provenance["lifecycle_state"] = "active"
        provenance["lifecycle_version"] += 1
        capability_path = Path(provenance["worktree_path"]) / CAPABILITY_REL
        _atomic_bytes(capability_path, capability.encode())
        _save(runtime_dir, provenance)
        return capability


def classify_three_way(base: str, main: str, satellite: str) -> str:
    if base != ABSENT and ((main == ABSENT) != (satellite == ABSENT)):
        return "deletion"
    if base == ABSENT and main != ABSENT and satellite != ABSENT and main != satellite:
        return "recreation"
    if main == base and satellite == base:
        return "unchanged"
    if satellite != base and main == base:
        return "satellite_only_change"
    if main != base and satellite == base:
        return "main_only_change"
    if main == satellite and main != base:
        return "identical_concurrent_change"
    return "conflict"


def sweep_store(store: Path) -> list[str]:
    if store.is_symlink() or not store.is_dir():
        raise TransportError("satellite store must be a real directory")
    entries = []
    for path in sorted(store.rglob("*")):
        relative = path.relative_to(store).as_posix()
        if path.is_symlink():
            raise TransportError(f"symlink rejected: {relative}")
        if path.is_dir():
            if path.name.startswith("."):
                raise TransportError(f"control directory rejected: {relative}")
            continue
        if not path.is_file():
            raise TransportError(f"non-regular entry rejected: {relative}")
        if any(part.startswith(".") for part in PurePosixPath(relative).parts):
            raise TransportError(f"control entry rejected: {relative}")
        try:
            _validate_destination(relative)
        except TransportError:
            continue
        entries.append(relative)
    return entries


def _record_collection_failure(
    runtime_dir: Path, provenance: dict, inventory: list[dict], reason_code: str,
) -> None:
    provenance["lifecycle_state"] = "recovery_required"
    provenance["lifecycle_version"] += 1
    evidence = {
        "schema_version": 1,
        "run_id": provenance["run_id"], "staging_manifest_digest": None,
        "partial_staging_inventory": inventory, "reason_code": reason_code,
        "actor": "system", "recorded_at": _now(), "preserved_satellite": True,
        "lifecycle_version": provenance["lifecycle_version"],
    }
    _atomic_bytes(runtime_dir / "recovery-evidence.json", canonical_json(evidence))
    _save(runtime_dir, provenance)


def collect(
    runtime_dir: Path, *, expected_version: int, raw_capability: str,
) -> dict:
    with _locked(runtime_dir):
        provenance = _load(runtime_dir)
        if (provenance["lifecycle_state"], provenance["lifecycle_version"]) != (
            "harvesting", expected_version,
        ):
            raise TransportError("stale collect compare-and-swap")
        if not secrets.compare_digest(
            provenance["capability_digest"], _digest(raw_capability.encode()),
        ):
            raise TransportError("raw capability mismatch")
        rows = []
        ambiguous = []
        try:
            main_store = Path(provenance["main_tree_path"]) / STORE_REL
            satellite_store = _validate_identity_and_destination(provenance)
            ingress = json.loads((runtime_dir / "ingress-manifest.json").read_text(encoding="utf-8"))
            if _digest(canonical_json(ingress)) != provenance["ingress_manifest_digest"]:
                raise TransportError("ingress manifest digest mismatch")
            baseline = {entry["relative_path"]: entry["content_hash"] for entry in ingress["entries"]}
            staging = runtime_dir / "staging"
            if staging.exists():
                shutil.rmtree(staging)
            files = staging / "files"
            files.mkdir(parents=True)
            satellite_entries = sweep_store(satellite_store)
            capability_bytes = raw_capability.encode()
            for relative in satellite_entries:
                if capability_bytes in (satellite_store / relative).read_bytes():
                    raise TransportError(f"raw capability occurrence rejected: {relative}")
            for relative in sorted(set(satellite_entries) | set(baseline)):
                base_hash = baseline.get(relative, ABSENT)
                main_hash = _hash_path(main_store / relative)
                satellite_hash = _hash_path(satellite_store / relative)
                classification = classify_three_way(base_hash, main_hash, satellite_hash)
                row = {
                    "relative_path": relative, "content_hash": satellite_hash,
                    "classification": classification,
                    "destination_hash": None if main_hash == ABSENT else main_hash,
                }
                if classification in {"deletion", "recreation", "conflict"}:
                    ambiguous.append(row)
                elif classification == "satellite_only_change":
                    destination = files / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(satellite_store / relative, destination)
                    rows.append(row)
            manifest = {"schema_version": 1, "run_id": provenance["run_id"], "entries": rows}
            _atomic_bytes(staging / "manifest.json", canonical_json(manifest))
            if ambiguous:
                raise TransportError(
                    "harvest conflict: " + ", ".join(row["relative_path"] for row in ambiguous)
                )
        except Exception as exc:
            _record_collection_failure(
                runtime_dir, provenance, ambiguous or rows, (
                    "HARVEST_CONFLICT" if ambiguous else "HARVEST_INTERRUPTED"
                ),
            )
            if isinstance(exc, TransportError):
                raise
            raise TransportError(f"harvest interrupted: {type(exc).__name__}") from exc
        provenance["lifecycle_state"] = "staged"
        provenance["lifecycle_version"] += 1
        _save(runtime_dir, provenance)
        return {
            "state": "staged", "manifest_digest": _digest(canonical_json(manifest)),
            "entries": rows,
        }


def discard_staging(
    runtime_dir: Path, expected_version: int, *, actor: str, reason_code: str,
) -> dict:
    if reason_code not in DISCARD_REASON_CODES:
        raise TransportError("discard reason_code is outside the closed set")
    with _locked(runtime_dir):
        provenance = _load(runtime_dir)
        _validate_identity_and_destination(provenance)
        if (provenance["lifecycle_state"], provenance["lifecycle_version"]) != (
            "staged", expected_version,
        ):
            raise TransportError("discard requires validated staged state")
        manifest_bytes = (runtime_dir / "staging/manifest.json").read_bytes()
        target_version = expected_version + 1
        evidence = {
            "schema_version": 1, "run_id": provenance["run_id"],
            "staging_manifest_digest": _digest(canonical_json(
                json.loads(manifest_bytes),
            )),
            "partial_staging_inventory": None, "reason_code": reason_code,
            "actor": actor, "discarded_at": _now(), "preserved_satellite": True,
            "lifecycle_version": target_version,
        }
        _atomic_bytes(runtime_dir / "discard-evidence.json", canonical_json(evidence))
        provenance["lifecycle_state"] = "discarded"
        provenance["lifecycle_version"] = target_version
        provenance["staging_disposition"] = "discarded"
        _save(runtime_dir, provenance)
        return provenance


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _durable_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as reader, destination.open("wb") as writer:
        shutil.copyfileobj(reader, writer)
        writer.flush()
        os.fsync(writer.fileno())
    _fsync_directory(destination.parent)


def _rollback_publish_transaction(runtime_dir: Path, provenance: dict) -> bool:
    transaction = runtime_dir / "publish-transaction"
    journal_path = transaction / "journal.json"
    if not journal_path.is_file():
        return False
    try:
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        main_store = Path(provenance["main_tree_path"]) / STORE_REL
        _reject_control_symlinks(
            Path(provenance["main_tree_path"]), (Path(".agents"), STORE_REL),
        )
        for entry in reversed(journal["entries"]):
            relative = _safe_relative(entry["relative_path"])
            _validate_destination(relative)
            destination = main_store / relative
            _reject_destination_symlinks(main_store, destination)
            current = _hash_path(destination)
            if current not in {entry["old_hash"], entry["new_hash"]}:
                raise TransportError(
                    f"publish recovery found unrecognized destination: {relative}"
                )
            expected_backup_path = (Path("backups") / relative).as_posix()
            if entry.get("backup_path") != expected_backup_path:
                raise TransportError(
                    f"publish recovery backup path mismatch: {relative}"
                )
            backup = transaction / expected_backup_path
            _reject_destination_symlinks(transaction, backup)
            if entry["old_hash"] == ABSENT:
                _reject_destination_symlinks(main_store, destination)
                destination.unlink(missing_ok=True)
            else:
                if _hash_path(backup) != entry["old_hash"]:
                    raise TransportError(f"publish recovery backup mismatch: {relative}")
                _reject_destination_symlinks(main_store, destination)
                destination.parent.mkdir(parents=True, exist_ok=True)
                _reject_destination_symlinks(main_store, destination)
                os.replace(backup, destination)
                _fsync_directory(destination.parent)
        journal_path.unlink()
        _fsync_directory(transaction)
        return True
    except (OSError, ValueError, KeyError) as exc:
        raise TransportError("invalid durable publish transaction journal") from exc


def publish(runtime_dir: Path, *, expected_version: int) -> dict:
    with _locked(runtime_dir):
        provenance = _load(runtime_dir)
        if (provenance["lifecycle_state"], provenance["lifecycle_version"]) != (
            "staged", expected_version,
        ):
            raise TransportError("stale publish compare-and-swap")
        manifest = json.loads((runtime_dir / "staging/manifest.json").read_text(encoding="utf-8"))
        _validate_identity_and_destination(provenance)
        main_store = Path(provenance["main_tree_path"]) / STORE_REL
        if main_store.is_symlink():
            raise TransportError("main artifact store must not be a symlink")
        for entry in manifest["entries"]:
            current = _hash_path(main_store / entry["relative_path"])
            observed = entry["destination_hash"] if entry["destination_hash"] is not None else ABSENT
            if current != observed:
                provenance["lifecycle_state"] = "recovery_required"
                provenance["lifecycle_version"] += 1
                _save(runtime_dir, provenance)
                raise TransportError("destination changed after collection")
        transaction = runtime_dir / "publish-transaction"
        if transaction.exists():
            shutil.rmtree(transaction)
        backups = transaction / "backups"
        prepared = transaction / "prepared"
        applied = []
        try:
            journal_entries = []
            for entry in manifest["entries"]:
                relative = entry["relative_path"]
                _validate_destination(relative)
                destination = main_store / relative
                cursor = destination
                while cursor != main_store:
                    if cursor.is_symlink():
                        raise TransportError("publish destination path contains symlink")
                    cursor = cursor.parent
                backup = backups / relative
                if destination.exists():
                    _durable_copy(destination, backup)
                staged = prepared / relative
                _durable_copy(runtime_dir / "staging/files" / relative, staged)
                journal_entries.append({
                    "relative_path": relative,
                    "old_hash": _hash_path(destination),
                    "new_hash": _hash_path(staged),
                    "backup_path": (Path("backups") / relative).as_posix(),
                })
            journal = {
                "schema_version": 1, "run_id": provenance["run_id"],
                "lifecycle_version": expected_version, "entries": journal_entries,
            }
            _atomic_bytes(transaction / "journal.json", canonical_json(journal))
            _fsync_directory(transaction)
            for entry in manifest["entries"]:
                relative = entry["relative_path"]
                destination = main_store / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(prepared / relative, destination)
                _fsync_directory(destination.parent)
                applied.append(relative)
        except Exception as exc:
            _rollback_publish_transaction(runtime_dir, provenance)
            provenance["lifecycle_state"] = "recovery_required"
            provenance["lifecycle_version"] += 1
            _save(runtime_dir, provenance)
            raise TransportError("atomic publish failed and was rolled back") from exc
        provenance["lifecycle_state"] = "published"
        provenance["lifecycle_version"] += 1
        provenance["staging_disposition"] = "published"
        evidence = {
            "schema_version": 1, "run_id": provenance["run_id"],
            "staging_manifest_digest": _digest(canonical_json(manifest)),
            "lifecycle_version": provenance["lifecycle_version"],
            "published_at": _now(),
        }
        _atomic_bytes(runtime_dir / "publish-evidence.json", canonical_json(evidence))
        _save(runtime_dir, provenance)
        (transaction / "journal.json").unlink(missing_ok=True)
        _fsync_directory(transaction)
        return provenance


def format_diagnostic(reason_code: str, runtime_dir: Path, reason: str) -> str:
    if reason_code not in {
        "SATELLITE_WRITE_DENIED", "SATELLITE_PRESERVED",
        "HARVEST_CONFLICT", "HARVEST_INTERRUPTED",
    }:
        raise TransportError("unknown reason code")
    provenance = _load(runtime_dir)
    run_id = provenance["run_id"]
    return "\n".join((
        f"reason_code={reason_code}", f"run_id={run_id}",
        f"main_tree_path={provenance['main_tree_path']}",
        f"worktree_path={provenance.get('worktree_path') or 'unavailable'}",
        f"reason={reason}",
        f"recovery_command=/claude-skills:artifacts recover --run-id {run_id}",
    ))


def _recorded_worktree_is_directory(provenance: dict) -> bool:
    """Check the recorded path without following a symlink outside the main runtime."""
    try:
        mode = os.lstat(provenance["worktree_path"]).st_mode
    except (OSError, KeyError, TypeError):
        return False
    return stat.S_ISDIR(mode)


def _validate_canonical_runtime(runtime_dir: Path, provenance: dict) -> None:
    """Bind recovery mutations to the recorded canonical main-tree runtime."""
    try:
        run_id = _strict_run_id(provenance["run_id"])
        main_tree = Path(provenance["main_tree_path"]).resolve(strict=True)
        expected = main_tree / RUNS_REL / run_id
    except (KeyError, OSError, TypeError) as exc:
        raise TransportError("canonical main runtime identity unavailable") from exc
    if runtime_dir.resolve() != expected.resolve():
        raise TransportError("recovery must use the canonical main runtime")
    _reject_control_symlinks(main_tree, (Path(".agents"), RUNS_REL))


def _reconcile_unavailable_owner_state(provenance: dict) -> None:
    """Apply only lifecycle edges allowed when the recorded owner is unavailable."""
    if provenance["capability_state"] == "live":
        provenance["capability_state"] = "revoked"
    state = provenance["lifecycle_state"]
    if state in {"created", "active"}:
        provenance["lifecycle_state"] = "failed_readonly"
        provenance["lifecycle_version"] += 1
    elif state in {"harvesting", "staged"}:
        provenance["lifecycle_state"] = "recovery_required"
        provenance["lifecycle_version"] += 1


def reconcile_owner(runtime_dir: Path, *, pid_start_reader=_pid_start_time) -> dict:
    with _locked(runtime_dir):
        provenance = _load(runtime_dir)
        _validate_canonical_runtime(runtime_dir, provenance)
        if not _recorded_worktree_is_directory(provenance):
            _reconcile_unavailable_owner_state(provenance)
            _save(runtime_dir, provenance)
            return provenance
        _validate_identity_and_destination(provenance)
        if _rollback_publish_transaction(runtime_dir, provenance):
            if provenance["capability_state"] == "live":
                provenance["capability_state"] = "revoked"
                Path(provenance["worktree_path"]).joinpath(CAPABILITY_REL).unlink(missing_ok=True)
            provenance["lifecycle_state"] = "recovery_required"
            provenance["lifecycle_version"] += 1
            _save(runtime_dir, provenance)
            return provenance
        current_start = pid_start_reader(provenance["owner_pid"])
        owner_alive = (
            current_start not in {None, "unavailable"}
            and current_start == provenance["owner_pid_start_time"]
        )
        if owner_alive:
            return provenance
        if provenance["capability_state"] == "live":
            Path(provenance["worktree_path"]).joinpath(CAPABILITY_REL).unlink(missing_ok=True)
        _reconcile_unavailable_owner_state(provenance)
        _save(runtime_dir, provenance)
        return provenance


def recovery_report(runtime_dir: Path) -> dict:
    """Return read-only facts for the single main-tree recovery workflow."""
    provenance = _load(runtime_dir)
    staging_manifest = runtime_dir / "staging/manifest.json"
    worktree = Path(provenance["worktree_path"])
    entries = []
    conflicts = []
    if staging_manifest.is_file():
        try:
            entries = json.loads(staging_manifest.read_text(encoding="utf-8")).get(
                "entries", [],
            )
        except (OSError, ValueError):
            entries = []
    recovery_evidence = runtime_dir / "recovery-evidence.json"
    if recovery_evidence.is_file():
        try:
            inventory = json.loads(
                recovery_evidence.read_text(encoding="utf-8"),
            ).get("partial_staging_inventory", [])
            conflicts = [
                row for row in inventory
                if row.get("classification") in {"deletion", "recreation", "conflict"}
            ]
            if not entries:
                entries = inventory
        except (OSError, ValueError):
            pass
    preserved = _recorded_worktree_is_directory(provenance)
    state = provenance["lifecycle_state"]
    if not preserved:
        state_code = "WORKTREE_MISSING"
        reason_code = "SATELLITE_PRESERVED"
        reason = "recorded worktree is missing; satellite bytes cannot be collected"
        next_action = (
            "satellite bytes cannot be collected: recover them outside this command, or "
            "explicitly close the run after human review; publish remains a separate "
            "authorized action"
        )
    elif state == "staged":
        state_code = "STAGED_REVIEW_REQUIRED"
        reason_code = "SATELLITE_PRESERVED"
        reason = "validated staging is preserved for explicit review"
        next_action = (
            "review every staged entry; publish separately only with explicit approval "
            "and mechanically checked preconditions, or request an authorized human discard"
        )
    elif state == "recovery_required" and conflicts:
        state_code = "HARVEST_CONFLICT"
        reason_code = "HARVEST_CONFLICT"
        reason = "harvest conflicts require human judgment; all bytes are preserved"
        next_action = (
            "resolve conflicts in the preserved worktree without deleting either version; "
            "then rerun recovery"
        )
    elif state == "recovery_required":
        state_code = "RECOVERY_PRECONDITIONS_UNPROVEN"
        reason_code = "SATELLITE_PRESERVED"
        reason = "recovery preconditions are not mechanically proven; all bytes are preserved"
        next_action = (
            "inspect recovery evidence and retry collection only after identity and "
            "compare-and-swap preconditions are mechanically proven"
        )
    elif state == "failed_readonly":
        state_code = "FAILED_READONLY"
        reason_code = "SATELLITE_WRITE_DENIED"
        reason = "satellite is read-only until a new run-scoped capability is issued"
        next_action = "invoke recovery to rotate a file-backed capability and resume the inner run"
    else:
        state_code = "LIFECYCLE_STATE_REPORT"
        reason_code = "SATELLITE_PRESERVED"
        reason = f"satellite lifecycle state is {state}"
        next_action = "follow the lifecycle action for the reported state"
    diagnostic = format_diagnostic(reason_code, runtime_dir, reason)
    return {
        "run_id": provenance["run_id"],
        "lifecycle_state": state,
        "capability_state": provenance["capability_state"],
        "staging_present": staging_manifest.is_file(),
        "preserved_worktree": preserved,
        "worktree_path": str(worktree),
        "entries": entries,
        "conflicts": conflicts,
        "state_code": state_code,
        "reason_code": reason_code,
        "diagnostic": diagnostic,
        "next_safe_action": next_action,
        "recovery_command": (
            f"/claude-skills:artifacts recover --run-id {provenance['run_id']}"
        ),
    }


def recover(runtime_dir: Path, *, pid_start_reader=_pid_start_time) -> dict:
    """Execute only state-specific recovery actions that are mechanically safe."""
    reconcile_owner(runtime_dir, pid_start_reader=pid_start_reader)
    provenance = _load(runtime_dir)
    if (
        provenance["lifecycle_state"] == "failed_readonly"
        and _recorded_worktree_is_directory(provenance)
    ):
        rotate_capability(
            runtime_dir,
            expected_epoch=provenance["capability_epoch"],
            expected_version=provenance["lifecycle_version"],
        )
        report = recovery_report(runtime_dir)
        report["capability_file_path"] = str(
            Path(provenance["worktree_path"]) / CAPABILITY_REL
        )
        report["resolved_context"] = {
            "pinned_plan": provenance["pinned_plan"],
            "resolved_isolation": "worktree",
            "satellite_run_id": provenance["run_id"],
            "satellite_capability_file": report["capability_file_path"],
        }
        report["next_safe_action"] = "resume the inner run with resolved_context"
        return report
    return recovery_report(runtime_dir)


def cleanup_allowed(runtime_dir: Path) -> bool:
    provenance = _load(runtime_dir)
    _validate_identity_and_destination(provenance)
    if (
        provenance["lifecycle_state"] != "cleanup_allowed"
        or provenance["capability_state"] == "live"
        or provenance.get("cleanup_evidence_validated") is not True
    ):
        return False
    evidence_name = provenance.get("cleanup_evidence_file")
    try:
        evidence = json.loads((runtime_dir / evidence_name).read_text(encoding="utf-8"))
    except (TypeError, OSError, ValueError):
        return False
    try:
        _validate_cleanup_evidence(
            runtime_dir, provenance, evidence,
            provenance["cleanup_terminal_version"],
        )
    except TransportError:
        return False
    return True


def _validate_cleanup_evidence(
    runtime_dir: Path, provenance: dict, evidence: dict, terminal_version: int,
) -> None:
    if (
        evidence.get("schema_version") != 1
        or evidence.get("run_id") != provenance["run_id"]
        or evidence.get("lifecycle_version") != terminal_version
    ):
        raise TransportError("cleanup evidence does not bind terminal state")
    try:
        manifest = json.loads(
            (runtime_dir / "staging/manifest.json").read_text(encoding="utf-8"),
        )
    except (OSError, ValueError) as exc:
        raise TransportError("canonical staging manifest is missing or invalid") from exc
    expected_digest = _digest(canonical_json(manifest))
    if evidence.get("staging_manifest_digest") != expected_digest:
        raise TransportError("cleanup evidence staging manifest digest mismatch")
    disposition = provenance.get("staging_disposition")
    if disposition == "published":
        if not isinstance(evidence.get("published_at"), str) or not evidence["published_at"]:
            raise TransportError("publish evidence is incomplete")
    elif disposition == "discarded":
        if (
            evidence.get("reason_code") not in DISCARD_REASON_CODES
            or not isinstance(evidence.get("actor"), str)
            or not evidence["actor"]
            or not _is_utc_timestamp(evidence.get("discarded_at"))
            or evidence.get("preserved_satellite") is not True
            or evidence.get("partial_staging_inventory") is not None
        ):
            raise TransportError("discard evidence is incomplete")
    else:
        raise TransportError("cleanup evidence has unknown disposition")


def _reject_destination_symlinks(root: Path, destination: Path) -> None:
    """Reject a root or any existing component before a filesystem mutation."""
    if root.is_symlink():
        raise TransportError(f"destination path contains symlink: {root}")
    cursor = root
    try:
        parts = destination.relative_to(root).parts
    except ValueError as exc:
        raise TransportError("destination escapes validated root") from exc
    for part in parts:
        cursor /= part
        if cursor.is_symlink():
            raise TransportError(f"destination path contains symlink: {cursor}")


def transition_cleanup_allowed(
    runtime_dir: Path, expected_state: str, expected_version: int,
) -> dict:
    with _locked(runtime_dir):
        provenance = _load(runtime_dir)
        _validate_identity_and_destination(provenance)
        if (provenance["lifecycle_state"], provenance["lifecycle_version"]) != (
            expected_state, expected_version,
        ):
            raise TransportError("stale cleanup compare-and-swap")
        if expected_state not in {"published", "discarded"}:
            raise TransportError("cleanup requires terminal disposition")
        if provenance["capability_state"] == "live":
            raise TransportError("cleanup requires non-live capability")
        evidence_name = (
            "publish-evidence.json" if expected_state == "published"
            else "discard-evidence.json"
        )
        try:
            evidence = json.loads((runtime_dir / evidence_name).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise TransportError("cleanup evidence is missing or invalid") from exc
        _validate_cleanup_evidence(
            runtime_dir, provenance, evidence, expected_version,
        )
        provenance["lifecycle_state"] = "cleanup_allowed"
        provenance["lifecycle_version"] += 1
        provenance["cleanup_evidence_validated"] = True
        provenance["cleanup_evidence_file"] = evidence_name
        provenance["cleanup_terminal_version"] = expected_version
        _save(runtime_dir, provenance)
        return provenance
