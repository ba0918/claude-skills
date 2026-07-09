"""Pure functions for empirical-prompt-tuning convergence logic.

All judgment calls (converged / diverged / halt / bloat) are made here,
not by the LLM tuner.  Each function is deterministic and unit-tested.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter

# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------

FRICTION_CATEGORIES = frozenset({
    "ambiguous_term",
    "missing_premise",
    "contradictory",
    "over_specified",
    "rationalization_hook",
    "self_containment_gap",
})

# ---------------------------------------------------------------------------
# Convergence
# ---------------------------------------------------------------------------

def is_converged(
    history: list[dict],
    *,
    window: int = 2,
    precision_delta_eps: float = 0.03,
    steps_tolerance_pct: float = 0.10,
    duration_tolerance_pct: float = 0.15,
) -> bool:
    if len(history) < window + 1:
        return False
    tail = history[-(window + 1):]
    for rec in tail[-window:]:
        if _has_friction(rec):
            return False
    for i in range(1, len(tail)):
        prev, cur = tail[i - 1], tail[i]
        if not _metrics_saturated(prev, cur, precision_delta_eps,
                                  steps_tolerance_pct, duration_tolerance_pct):
            return False
    return True


def _has_friction(rec: dict) -> bool:
    for sc in rec.get("scenarios", []):
        if sc.get("friction"):
            return True
    return False


def _metrics_saturated(
    prev: dict, cur: dict,
    precision_eps: float, steps_pct: float, duration_pct: float,
) -> bool:
    for sp, sc in zip(prev.get("scenarios", []), cur.get("scenarios", [])):
        if abs(sc.get("precision", 0) - sp.get("precision", 0)) > precision_eps:
            return False
        prev_steps = sp.get("steps", 1) or 1
        if abs(sc.get("steps", 0) - prev_steps) / prev_steps > steps_pct:
            return False
        prev_dur = sp.get("duration_ms", 1) or 1
        if abs(sc.get("duration_ms", 0) - prev_dur) / prev_dur > duration_pct:
            return False
    return True


# ---------------------------------------------------------------------------
# Divergence
# ---------------------------------------------------------------------------

def is_diverged(history: list[dict], threshold: int = 3) -> bool:
    if len(history) < threshold:
        return False
    tail = history[-threshold:]
    category_sets = []
    for rec in tail:
        cats: set[str] = set()
        for sc in rec.get("scenarios", []):
            for f in sc.get("friction", []):
                cats.add(f.get("category", "uncategorized"))
        category_sets.append(cats)
    if not category_sets or not category_sets[0]:
        return False
    common = category_sets[0]
    for cs in category_sets[1:]:
        common = common & cs
    return len(common) > 0


# ---------------------------------------------------------------------------
# Checklist integrity (hash-lock)
# ---------------------------------------------------------------------------

def verify_checklist_integrity(checklist: list[dict], locked_sha256: str) -> bool:
    current = hashlib.sha256(
        json.dumps(checklist, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    return current == locked_sha256


# ---------------------------------------------------------------------------
# Bloat detection
# ---------------------------------------------------------------------------

def detect_bloat(history: list[dict], max_growth_pct: float = 20.0) -> bool:
    if len(history) < 2:
        return False
    prev_bytes = history[-2].get("prompt_bytes", 0) or 1
    cur_bytes = history[-1].get("prompt_bytes", 0)
    growth = (cur_bytes - prev_bytes) / prev_bytes * 100
    return growth > max_growth_pct


# ---------------------------------------------------------------------------
# Instruction fingerprint
# ---------------------------------------------------------------------------

def compute_instruction_fingerprint(file_contents: dict[str, str]) -> str:
    h = hashlib.sha256()
    for path in sorted(file_contents.keys()):
        h.update(path.encode())
        h.update(b"\x00")
        h.update(file_contents[path].encode())
        h.update(b"\x00")
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Friction classification
# ---------------------------------------------------------------------------

def classify_friction(raw_points: list[dict]) -> list[dict]:
    result = []
    for pt in raw_points:
        cat = pt.get("category", "")
        if cat not in FRICTION_CATEGORIES:
            cat = "uncategorized"
        result.append({**pt, "category": cat})
    return result


# ---------------------------------------------------------------------------
# Exit verdict
# ---------------------------------------------------------------------------

def resolve_exit_verdict(
    history: list[dict],
    *,
    max_iter: int = 10,
    elapsed_s: float = 0.0,
    max_wallclock: float = 3600.0,
    kill_file_exists: bool = False,
) -> str:
    if kill_file_exists or len(history) >= max_iter or elapsed_s >= max_wallclock:
        return "halt"
    if is_diverged(history):
        return "diverged"
    if detect_bloat(history):
        return "bloat_advisory"
    if is_converged(history):
        return "converged"
    return "continue"
