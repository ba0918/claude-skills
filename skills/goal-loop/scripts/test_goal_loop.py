#!/usr/bin/env python3
"""goal_loop.py の unittest。

契約: ../../shared/references/convergence-pattern.md §3（oracle integrity）/
§4（収束判定）/ §5（LoopResult）。純関数群は time / random / I/O を持たないため
入出力のみで検証する。CLI は薄い I/O ラッパーなので統合テスト 2 本のみ。
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from goal_loop import (
    detect_convergence_halt,
    failure_signature,
    make_loop_result,
    normalize_output,
    oracle_manifest,
    verify_oracle_integrity,
)

SCRIPT_DIR = Path(__file__).resolve().parent
GOAL_LOOP_PY = SCRIPT_DIR / "goal_loop.py"


class TestOracleManifest(unittest.TestCase):
    def test_single_file(self):
        import hashlib

        contents = {"a.txt": b"hello"}
        manifest = oracle_manifest(contents)
        self.assertEqual(manifest, {"a.txt": hashlib.sha256(b"hello").hexdigest()})

    def test_multiple_files(self):
        import hashlib

        contents = {"a.txt": b"hello", "b.txt": b"world"}
        manifest = oracle_manifest(contents)
        self.assertEqual(
            manifest,
            {
                "a.txt": hashlib.sha256(b"hello").hexdigest(),
                "b.txt": hashlib.sha256(b"world").hexdigest(),
            },
        )

    def test_empty(self):
        self.assertEqual(oracle_manifest({}), {})

    def test_hash_is_hex64(self):
        manifest = oracle_manifest({"a.txt": b"x"})
        digest = manifest["a.txt"]
        self.assertEqual(len(digest), 64)
        int(digest, 16)  # raises ValueError if not hex


class TestVerifyOracleIntegrity(unittest.TestCase):
    def test_match_is_ok(self):
        manifest = {"a.txt": "abc123"}
        current = {"a.txt": "abc123"}
        result = verify_oracle_integrity(manifest, current)
        self.assertEqual(result, {"ok": True, "tampered": []})

    def test_changed_file_is_tampered(self):
        manifest = {"a.txt": "abc123"}
        current = {"a.txt": "def456"}
        result = verify_oracle_integrity(manifest, current)
        self.assertFalse(result["ok"])
        self.assertEqual(result["tampered"], ["a.txt"])

    def test_deleted_file_is_tampered(self):
        manifest = {"a.txt": "abc123", "b.txt": "def456"}
        current = {"a.txt": "abc123"}
        result = verify_oracle_integrity(manifest, current)
        self.assertFalse(result["ok"])
        self.assertEqual(result["tampered"], ["b.txt"])

    def test_added_file_is_tampered(self):
        manifest = {"a.txt": "abc123"}
        current = {"a.txt": "abc123", "sneaky.txt": "def456"}
        result = verify_oracle_integrity(manifest, current)
        self.assertFalse(result["ok"])
        self.assertEqual(result["tampered"], ["sneaky.txt"])

    def test_combined_change_delete_add(self):
        manifest = {"changed.txt": "aaa", "deleted.txt": "bbb", "same.txt": "ccc"}
        current = {"changed.txt": "zzz", "same.txt": "ccc", "added.txt": "ddd"}
        result = verify_oracle_integrity(manifest, current)
        self.assertFalse(result["ok"])
        self.assertEqual(
            result["tampered"], ["added.txt", "changed.txt", "deleted.txt"]
        )

    def test_empty_manifest_and_current_is_ok(self):
        self.assertEqual(verify_oracle_integrity({}, {}), {"ok": True, "tampered": []})


class TestNormalizeOutput(unittest.TestCase):
    def test_strips_lines_and_drops_blank_lines(self):
        raw = "  line1  \n\n   \n  line2\n"
        self.assertEqual(normalize_output(raw), "line1\nline2")

    def test_replaces_iso_timestamp_with_t_separator(self):
        raw = "2024-01-01T12:00:00.123 something happened"
        normalized = normalize_output(raw)
        self.assertIn("<TS>", normalized)
        self.assertNotIn("2024-01-01", normalized)

    def test_replaces_timestamp_with_space_separator(self):
        raw = "2024-01-01 12:00:00 something happened"
        normalized = normalize_output(raw)
        self.assertIn("<TS>", normalized)
        self.assertNotIn("2024-01-01", normalized)

    def test_replaces_duration_with_in_prefix(self):
        raw = "test failed in 0.456s"
        normalized = normalize_output(raw)
        self.assertIn("<DUR>", normalized)
        self.assertNotIn("0.456s", normalized)

    def test_replaces_bare_duration(self):
        raw = "elapsed 1.234s total"
        normalized = normalize_output(raw)
        self.assertIn("<DUR>", normalized)
        self.assertNotIn("1.234s", normalized)

    def test_replaces_hex_address(self):
        raw = "segfault at 0xDEADBEEF in libc"
        normalized = normalize_output(raw)
        self.assertIn("<ADDR>", normalized)
        self.assertNotIn("0xDEADBEEF", normalized)

    def test_combined_normalization(self):
        raw = "  2024-01-01T12:00:00.123Z FAIL test_foo (0x1a2b) in 0.789s  \n\n"
        normalized = normalize_output(raw)
        self.assertNotIn("2024-01-01", normalized)
        self.assertNotIn("0.789s", normalized)
        self.assertNotIn("0x1a2b", normalized)
        self.assertNotIn("\n\n", normalized)


class TestFailureSignature(unittest.TestCase):
    def test_same_error_different_timestamp_same_signature(self):
        out1 = "Error at 2024-01-01T12:00:00.123: test_foo failed in 0.456s"
        out2 = "Error at 2024-06-15T08:30:22.789: test_foo failed in 0.789s"
        self.assertEqual(failure_signature(out1), failure_signature(out2))

    def test_different_error_different_signature(self):
        out1 = "AssertionError: expected 1 got 2"
        out2 = "AssertionError: expected 3 got 4"
        self.assertNotEqual(failure_signature(out1), failure_signature(out2))

    def test_signature_is_hex16(self):
        sig = failure_signature("some failure output")
        self.assertEqual(len(sig), 16)
        int(sig, 16)


class TestDetectConvergenceHalt(unittest.TestCase):
    def test_stall_on_three_identical(self):
        self.assertEqual(detect_convergence_halt(["A", "A", "A"]), "stall")

    def test_stall_only_checks_tail(self):
        self.assertEqual(detect_convergence_halt(["X", "A", "A", "A"]), "stall")

    def test_no_stall_when_tail_differs(self):
        self.assertIsNone(detect_convergence_halt(["A", "A", "B"]))

    def test_oscillation_period_2(self):
        history = ["A", "B", "A", "B", "A", "B"]
        self.assertEqual(detect_convergence_halt(history), "oscillation")

    def test_oscillation_period_3(self):
        history = ["A", "B", "C", "A", "B", "C"]
        self.assertEqual(detect_convergence_halt(history), "oscillation")

    def test_all_identical_window_is_stall_not_oscillation(self):
        history = ["A", "A", "A", "A", "A", "A"]
        self.assertEqual(detect_convergence_halt(history), "stall")

    def test_progress_all_different_is_none(self):
        history = ["A", "B", "C", "D", "E", "F"]
        self.assertIsNone(detect_convergence_halt(history))

    def test_insufficient_history_is_none(self):
        self.assertIsNone(detect_convergence_halt(["A", "B"]))

    def test_empty_history_is_none(self):
        self.assertIsNone(detect_convergence_halt([]))

    def test_stall_takes_priority_over_oscillation(self):
        # 末尾3個が同一 -> stall。同時に oscillation 的な繰り返しでもあり得るが
        # stall を優先して返す。
        history = ["A", "B", "A", "A", "A", "A"]
        self.assertEqual(detect_convergence_halt(history), "stall")

    def test_custom_stall_limit(self):
        self.assertEqual(
            detect_convergence_halt(["A", "A"], stall_limit=2), "stall"
        )
        self.assertIsNone(detect_convergence_halt(["A", "A"], stall_limit=3))

    def test_custom_window_and_max_period(self):
        history = ["A", "B", "A", "B"]
        self.assertEqual(
            detect_convergence_halt(history, window=4, max_period=2), "oscillation"
        )
        # デフォルト window=6 では履歴不足で None
        self.assertIsNone(detect_convergence_halt(history))

    def test_period_beyond_max_period_not_detected(self):
        # 周期4のパターンは max_period=3 の既定では検出しない
        history = ["A", "B", "C", "D", "A", "B", "C", "D"]
        self.assertIsNone(
            detect_convergence_halt(history, window=8, max_period=3)
        )
        self.assertEqual(
            detect_convergence_halt(history, window=8, max_period=4), "oscillation"
        )


class TestMakeLoopResult(unittest.TestCase):
    def test_minimal_success(self):
        result = make_loop_result(iterations=3, converged=True)
        self.assertEqual(result, {"iterations": 3, "converged": True})

    def test_halt_reason_included(self):
        result = make_loop_result(iterations=8, converged=False, halt_reason="stall")
        self.assertEqual(
            result, {"iterations": 8, "converged": False, "halt_reason": "stall"}
        )
        self.assertNotIn("tampered_paths", result)
        self.assertNotIn("final_signature", result)

    def test_tampered_paths_included(self):
        result = make_loop_result(
            iterations=2,
            converged=False,
            halt_reason="oracle_tampered",
            tampered_paths=["tests/test_foo.py"],
        )
        self.assertEqual(result["tampered_paths"], ["tests/test_foo.py"])

    def test_final_signature_included(self):
        result = make_loop_result(
            iterations=5,
            converged=False,
            halt_reason="stall",
            final_signature="0123456789abcdef",
        )
        self.assertEqual(result["final_signature"], "0123456789abcdef")

    def test_none_fields_omitted_entirely(self):
        result = make_loop_result(iterations=1, converged=True, halt_reason=None,
                                   tampered_paths=None, final_signature=None)
        self.assertEqual(set(result.keys()), {"iterations", "converged"})


class TestCLI(unittest.TestCase):
    def test_lock_verify_roundtrip_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            f1 = tdp / "test_a.py"
            f1.write_text("def test_a(): assert True\n")
            manifest_path = tdp / "manifest.json"

            r = subprocess.run(
                [sys.executable, str(GOAL_LOOP_PY), "lock", str(f1),
                 "--out", str(manifest_path)],
                capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(manifest_path.exists())

            r = subprocess.run(
                [sys.executable, str(GOAL_LOOP_PY), "verify", str(manifest_path)],
                capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)

            f1.write_text("def test_a(): assert False  # tampered\n")

            r = subprocess.run(
                [sys.executable, str(GOAL_LOOP_PY), "verify", str(manifest_path)],
                capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 2)
            self.assertIn(str(f1), r.stderr)

    def test_signature_cli_reads_stdin(self):
        r = subprocess.run(
            [sys.executable, str(GOAL_LOOP_PY), "signature"],
            input="Error: something failed\n",
            capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        sig = r.stdout.strip()
        self.assertEqual(len(sig), 16)
        int(sig, 16)


if __name__ == "__main__":
    unittest.main()
