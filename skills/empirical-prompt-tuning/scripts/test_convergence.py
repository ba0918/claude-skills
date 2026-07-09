"""Tests for convergence.py — empirical-prompt-tuning pure functions."""

import hashlib
import json
import unittest

from convergence import (
    classify_friction,
    compute_instruction_fingerprint,
    detect_bloat,
    is_converged,
    is_diverged,
    resolve_exit_verdict,
    verify_checklist_integrity,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_iter(iteration, precision=0.9, steps=4, duration_ms=20000,
               friction=None, prompt_bytes=1000):
    return {
        "iteration": iteration,
        "prompt_bytes": prompt_bytes,
        "scenarios": [
            {
                "id": "A",
                "success": True,
                "precision": precision,
                "steps": steps,
                "duration_ms": duration_ms,
                "retries": 0,
                "friction": friction or [],
            }
        ],
    }


def _checklist_hash(checklist):
    return hashlib.sha256(
        json.dumps(checklist, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


# ===========================================================================
# is_converged
# ===========================================================================

class TestIsConverged(unittest.TestCase):

    def test_converged_after_two_clear_iterations(self):
        h = [
            _make_iter(1, precision=0.87, friction=[{"category": "ambiguous_term"}]),
            _make_iter(2, precision=0.88),
            _make_iter(3, precision=0.89),
        ]
        self.assertTrue(is_converged(h, window=2))

    def test_not_converged_with_friction_in_last(self):
        h = [
            _make_iter(1, precision=0.85),
            _make_iter(2, precision=0.88),
            _make_iter(3, precision=0.89,
                       friction=[{"category": "missing_premise"}]),
        ]
        self.assertFalse(is_converged(h, window=2))

    def test_not_converged_with_large_precision_jump(self):
        h = [
            _make_iter(1, precision=0.50),
            _make_iter(2, precision=0.85),
            _make_iter(3, precision=0.95),
        ]
        self.assertFalse(is_converged(h, window=2))

    def test_not_converged_insufficient_history(self):
        h = [_make_iter(1, precision=0.90)]
        self.assertFalse(is_converged(h, window=2))

    def test_converged_with_custom_eps(self):
        h = [
            _make_iter(1, precision=0.84),
            _make_iter(2, precision=0.85),
            _make_iter(3, precision=0.86),
        ]
        self.assertFalse(is_converged(h, window=2, precision_delta_eps=0.005))
        self.assertTrue(is_converged(h, window=2, precision_delta_eps=0.02))

    def test_steps_variance_prevents_convergence(self):
        h = [
            _make_iter(1, steps=10),
            _make_iter(2, steps=10),
            _make_iter(3, steps=15),  # +50%
        ]
        self.assertFalse(is_converged(h, window=2))


# ===========================================================================
# is_diverged
# ===========================================================================

class TestIsDiverged(unittest.TestCase):

    def test_diverged_same_category_persists(self):
        friction = [{"category": "ambiguous_term"}]
        h = [
            _make_iter(1, friction=friction),
            _make_iter(2, friction=friction),
            _make_iter(3, friction=friction),
        ]
        self.assertTrue(is_diverged(h, threshold=3))

    def test_not_diverged_when_friction_clears(self):
        h = [
            _make_iter(1, friction=[{"category": "ambiguous_term"}]),
            _make_iter(2, friction=[{"category": "ambiguous_term"}]),
            _make_iter(3),
        ]
        self.assertFalse(is_diverged(h, threshold=3))

    def test_not_diverged_insufficient_history(self):
        friction = [{"category": "ambiguous_term"}]
        h = [_make_iter(1, friction=friction), _make_iter(2, friction=friction)]
        self.assertFalse(is_diverged(h, threshold=3))

    def test_diverged_different_categories_not_counted(self):
        h = [
            _make_iter(1, friction=[{"category": "ambiguous_term"}]),
            _make_iter(2, friction=[{"category": "missing_premise"}]),
            _make_iter(3, friction=[{"category": "contradictory"}]),
        ]
        self.assertFalse(is_diverged(h, threshold=3))


# ===========================================================================
# verify_checklist_integrity
# ===========================================================================

class TestVerifyChecklistIntegrity(unittest.TestCase):

    def test_integrity_ok(self):
        cl = [{"text": "does X", "critical": True}]
        h = _checklist_hash(cl)
        self.assertTrue(verify_checklist_integrity(cl, h))

    def test_integrity_tampered(self):
        cl = [{"text": "does X", "critical": True}]
        h = _checklist_hash(cl)
        cl[0]["critical"] = False
        self.assertFalse(verify_checklist_integrity(cl, h))

    def test_integrity_order_independent(self):
        cl = [
            {"text": "A", "critical": True},
            {"text": "B", "critical": False},
        ]
        h = _checklist_hash(cl)
        self.assertTrue(verify_checklist_integrity(cl, h))


# ===========================================================================
# detect_bloat
# ===========================================================================

class TestDetectBloat(unittest.TestCase):

    def test_no_bloat(self):
        h = [_make_iter(1, prompt_bytes=1000), _make_iter(2, prompt_bytes=1050)]
        self.assertFalse(detect_bloat(h, max_growth_pct=20.0))

    def test_bloat_detected(self):
        h = [_make_iter(1, prompt_bytes=1000), _make_iter(2, prompt_bytes=1300)]
        self.assertTrue(detect_bloat(h, max_growth_pct=20.0))

    def test_single_iteration_no_bloat(self):
        h = [_make_iter(1, prompt_bytes=5000)]
        self.assertFalse(detect_bloat(h))

    def test_shrink_is_not_bloat(self):
        h = [_make_iter(1, prompt_bytes=2000), _make_iter(2, prompt_bytes=1500)]
        self.assertFalse(detect_bloat(h))


# ===========================================================================
# compute_instruction_fingerprint
# ===========================================================================

class TestComputeInstructionFingerprint(unittest.TestCase):

    def test_same_content_same_hash(self):
        fp1 = compute_instruction_fingerprint({"a.md": "hello"})
        fp2 = compute_instruction_fingerprint({"a.md": "hello"})
        self.assertEqual(fp1, fp2)

    def test_different_content_different_hash(self):
        fp1 = compute_instruction_fingerprint({"a.md": "hello"})
        fp2 = compute_instruction_fingerprint({"a.md": "world"})
        self.assertNotEqual(fp1, fp2)

    def test_order_independent(self):
        fp1 = compute_instruction_fingerprint({"a.md": "x", "b.md": "y"})
        fp2 = compute_instruction_fingerprint({"b.md": "y", "a.md": "x"})
        self.assertEqual(fp1, fp2)


# ===========================================================================
# classify_friction
# ===========================================================================

VALID_CATEGORIES = {
    "ambiguous_term", "missing_premise", "contradictory",
    "over_specified", "rationalization_hook", "self_containment_gap",
}

class TestClassifyFriction(unittest.TestCase):

    def test_valid_category_passes_through(self):
        raw = [{"category": "ambiguous_term", "detail": "x"}]
        result = classify_friction(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["category"], "ambiguous_term")

    def test_invalid_category_becomes_uncategorized(self):
        raw = [{"category": "totally_made_up", "detail": "x"}]
        result = classify_friction(raw)
        self.assertEqual(result[0]["category"], "uncategorized")

    def test_missing_category_becomes_uncategorized(self):
        raw = [{"detail": "something unclear"}]
        result = classify_friction(raw)
        self.assertEqual(result[0]["category"], "uncategorized")

    def test_empty_list(self):
        self.assertEqual(classify_friction([]), [])


# ===========================================================================
# resolve_exit_verdict
# ===========================================================================

class TestResolveExitVerdict(unittest.TestCase):

    def test_halt_on_max_iter(self):
        h = [_make_iter(i) for i in range(1, 11)]
        v = resolve_exit_verdict(h, max_iter=10)
        self.assertEqual(v, "halt")

    def test_halt_on_kill_file(self):
        h = [_make_iter(1)]
        v = resolve_exit_verdict(h, kill_file_exists=True)
        self.assertEqual(v, "halt")

    def test_halt_on_wallclock(self):
        h = [_make_iter(1)]
        v = resolve_exit_verdict(h, elapsed_s=4000.0, max_wallclock=3600.0)
        self.assertEqual(v, "halt")

    def test_diverged_takes_priority_over_converged(self):
        friction = [{"category": "ambiguous_term"}]
        h = [_make_iter(i, friction=friction) for i in range(1, 5)]
        v = resolve_exit_verdict(h, max_iter=100)
        self.assertEqual(v, "diverged")

    def test_converged(self):
        h = [
            _make_iter(1, precision=0.88, friction=[{"category": "ambiguous_term"}]),
            _make_iter(2, precision=0.90),
            _make_iter(3, precision=0.91),
        ]
        v = resolve_exit_verdict(h, max_iter=100)
        self.assertEqual(v, "converged")

    def test_continue_when_nothing_triggered(self):
        h = [
            _make_iter(1, friction=[{"category": "ambiguous_term"}]),
            _make_iter(2),
        ]
        v = resolve_exit_verdict(h, max_iter=100)
        self.assertEqual(v, "continue")

    def test_halt_priority_over_diverged(self):
        friction = [{"category": "ambiguous_term"}]
        h = [_make_iter(i, friction=friction) for i in range(1, 11)]
        v = resolve_exit_verdict(h, max_iter=10)
        self.assertEqual(v, "halt")

    def test_bloat_advisory_returned(self):
        h = [_make_iter(1, prompt_bytes=1000), _make_iter(2, prompt_bytes=1500)]
        v = resolve_exit_verdict(h, max_iter=100)
        self.assertEqual(v, "bloat_advisory")


if __name__ == "__main__":
    unittest.main()
