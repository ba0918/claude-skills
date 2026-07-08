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

import goal_loop
from goal_loop import (
    _is_excluded,
    cmd_verify,
    detect_convergence_halt,
    failure_signature,
    make_loop_result,
    normalize_output,
    oracle_manifest,
    parse_manifest_envelope,
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


class TestParseManifestEnvelope(unittest.TestCase):
    def test_valid_v2_returns_roots_and_files(self):
        raw = {"version": 2, "roots": ["tests"], "files": {"tests/a.py": "abc"}}
        roots, files = parse_manifest_envelope(raw)
        self.assertEqual(roots, ["tests"])
        self.assertEqual(files, {"tests/a.py": "abc"})

    def test_valid_v2_empty_roots_and_files(self):
        roots, files = parse_manifest_envelope({"version": 2, "roots": [], "files": {}})
        self.assertEqual(roots, [])
        self.assertEqual(files, {})

    def test_version_not_2_raises(self):
        with self.assertRaises(ValueError):
            parse_manifest_envelope({"version": 1, "roots": [], "files": {}})

    def test_version_missing_raises(self):
        with self.assertRaises(ValueError):
            parse_manifest_envelope({"roots": [], "files": {}})

    def test_roots_not_list_raises(self):
        with self.assertRaises(ValueError):
            parse_manifest_envelope({"version": 2, "roots": "tests", "files": {}})

    def test_files_not_dict_raises(self):
        with self.assertRaises(ValueError):
            parse_manifest_envelope({"version": 2, "roots": [], "files": []})

    def test_roots_with_non_string_element_raises(self):
        # roots は list だが要素が str でない場合、後段の Path(arg) が TypeError を
        # 送出し、except OSError に捕まらず exit 1（fail-open）になる。純関数側で
        # 要素型まで検証して ValueError（-> exit 2）に倒す。
        for bad in ([123], [None], [[]], ["ok", 5], [{"a": 1}]):
            with self.assertRaises(ValueError):
                parse_manifest_envelope({"version": 2, "roots": bad, "files": {}})

    def test_legacy_flat_format_raises(self):
        # 旧フラット形式（パス -> hex のみ、version/roots 無し）は fail-closed で拒否
        with self.assertRaises(ValueError):
            parse_manifest_envelope({"tests/a.py": "abc123", "tests/b.py": "def456"})

    def test_non_dict_toplevel_raises(self):
        # null / [] / str / number をトップレベルに書いても AttributeError で
        # exit 1 に落ちず、ValueError にマップされること
        for raw in (None, [], "s", 42, 3.14, True):
            with self.assertRaises(ValueError):
                parse_manifest_envelope(raw)

    def test_legacy_manifest_with_files_key_but_no_version_raises(self):
        # "files" という名の oracle ファイルを含む旧 manifest でも version が無ければ弾く
        raw = {"files": "somehash", "tests/a.py": "abc"}
        with self.assertRaises(ValueError):
            parse_manifest_envelope(raw)


class TestIsExcluded(unittest.TestCase):
    """除外述語は lock root からの **相対パス** で評価する（絶対パス全体で評価すると
    祖先の hidden 要素で正当ファイルまで全除外され manifest 空化 = fail-open 回帰）。
    セキュリティ上重要なため純関数として直接検証する。"""

    def test_plain_file_not_excluded(self):
        self.assertFalse(_is_excluded(Path("test_a.py")))

    def test_nested_plain_file_not_excluded(self):
        self.assertFalse(_is_excluded(Path("sub/dir/test_b.py")))

    def test_pyc_excluded_at_any_depth(self):
        self.assertTrue(_is_excluded(Path("a.pyc")))
        self.assertTrue(_is_excluded(Path("sub/a.pyc")))

    def test_pycache_dir_component_excluded(self):
        self.assertTrue(_is_excluded(Path("__pycache__/a.txt")))
        self.assertTrue(_is_excluded(Path("pkg/__pycache__/mod.pyc")))

    def test_hidden_leaf_file_excluded(self):
        self.assertTrue(_is_excluded(Path(".coverage")))

    def test_hidden_dir_component_excluded(self):
        self.assertTrue(_is_excluded(Path(".pytest_cache/v/cache/lastfailed")))
        self.assertTrue(_is_excluded(Path("tests/.mypy_cache/x")))

    def test_git_dir_excluded(self):
        self.assertTrue(_is_excluded(Path(".git/config")))

    def test_non_hidden_conftest_not_excluded(self):
        # 主脅威（非 hidden の conftest.py）は除外されないこと
        self.assertFalse(_is_excluded(Path("conftest.py")))
        self.assertFalse(_is_excluded(Path("tests/conftest.py")))


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

    def _run_halt(self, lines, extra_args=()):
        with tempfile.TemporaryDirectory() as td:
            hist = Path(td) / "history.txt"
            hist.write_text("".join(line + "\n" for line in lines))
            return subprocess.run(
                [sys.executable, str(GOAL_LOOP_PY), "halt", str(hist),
                 *extra_args],
                capture_output=True, text=True,
            )

    def test_halt_cli_none_exits_0(self):
        r = self._run_halt(["aaaa", "bbbb"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "none")

    def test_halt_cli_stall_exits_3(self):
        r = self._run_halt(["aaaa", "aaaa", "aaaa"])
        self.assertEqual(r.returncode, 3, r.stderr)
        self.assertEqual(r.stdout.strip(), "stall")

    def test_halt_cli_oscillation_exits_4(self):
        r = self._run_halt(["aa", "bb", "aa", "bb", "aa", "bb"])
        self.assertEqual(r.returncode, 4, r.stderr)
        self.assertEqual(r.stdout.strip(), "oscillation")

    def test_halt_cli_ignores_blank_lines_and_whitespace(self):
        r = self._run_halt(["aaaa", "", "  aaaa  ", "aaaa"])
        self.assertEqual(r.returncode, 3, r.stderr)

    def test_halt_cli_empty_history_is_none(self):
        r = self._run_halt([])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "none")

    def test_halt_cli_custom_stall_limit(self):
        r = self._run_halt(["aaaa", "aaaa"], extra_args=["--stall-limit", "2"])
        self.assertEqual(r.returncode, 3, r.stderr)

    def test_halt_cli_missing_file_exits_2(self):
        r = subprocess.run(
            [sys.executable, str(GOAL_LOOP_PY), "halt", "/nonexistent/hist.txt"],
            capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 2)

    def test_lock_excludes_pycache_and_pyc(self):
        # oracle 実行自体が生む bytecode キャッシュを lock に含めると
        # false tamper（oracle_tampered 誤検出）になるため、自動除外する。
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            tests = tdp / "tests"
            (tests / "__pycache__").mkdir(parents=True)
            (tests / "test_a.py").write_text("def test_a(): assert True\n")
            (tests / "__pycache__" / "test_a.cpython-312.pyc").write_bytes(b"\x00fake")
            (tests / "stray.pyc").write_bytes(b"\x00stray")
            manifest_path = tdp / "manifest.json"

            r = subprocess.run(
                [sys.executable, str(GOAL_LOOP_PY), "lock", str(tests),
                 "--out", str(manifest_path)],
                capture_output=True, text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            import json as _json
            manifest = _json.loads(manifest_path.read_text())
            # v2 形式: 除外は files キーに対して検査する
            keys = "\n".join(manifest["files"])
            self.assertIn("test_a.py", keys)
            self.assertNotIn("__pycache__", keys)
            self.assertNotIn(".pyc", keys)

    def _lock(self, roots, manifest_path):
        return subprocess.run(
            [sys.executable, str(GOAL_LOOP_PY), "lock", *roots,
             "--out", str(manifest_path)],
            capture_output=True, text=True,
        )

    def _verify(self, manifest_path):
        return subprocess.run(
            [sys.executable, str(GOAL_LOOP_PY), "verify", str(manifest_path)],
            capture_output=True, text=True,
        )

    def test_lock_outputs_v2_envelope(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            tests = tdp / "tests"
            tests.mkdir()
            (tests / "test_a.py").write_text("def test_a(): assert True\n")
            manifest_path = tdp / "manifest.json"
            r = self._lock([str(tests)], manifest_path)
            self.assertEqual(r.returncode, 0, r.stderr)
            import json as _json
            m = _json.loads(manifest_path.read_text())
            self.assertEqual(m["version"], 2)
            self.assertEqual(m["roots"], [str(tests)])
            self.assertIn(str(tests / "test_a.py"), m["files"])

    def test_added_file_in_dir_is_tampered_cli(self):
        # ディレクトリを lock -> 配下に新規 .py 追加 -> verify exit 2 + stderr にパス
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            tests = tdp / "tests"
            tests.mkdir()
            (tests / "test_a.py").write_text("def test_a(): assert True\n")
            manifest_path = tdp / "manifest.json"
            self.assertEqual(self._lock([str(tests)], manifest_path).returncode, 0)
            self.assertEqual(self._verify(manifest_path).returncode, 0)

            sneaky = tests / "conftest.py"
            sneaky.write_text("def pytest_collectstart(): pass\n")
            r = self._verify(manifest_path)
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn(str(sneaky), r.stderr)

    def test_added_file_to_empty_dir_cli(self):
        # ファイル 0 個のディレクトリを lock -> 1 本追加 -> verify exit 2
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            tests = tdp / "tests"
            tests.mkdir()
            manifest_path = tdp / "manifest.json"
            self.assertEqual(self._lock([str(tests)], manifest_path).returncode, 0)
            import json as _json
            m = _json.loads(manifest_path.read_text())
            self.assertEqual(m["files"], {})
            self.assertEqual(m["roots"], [str(tests)])
            self.assertEqual(self._verify(manifest_path).returncode, 0)

            added = tests / "test_new.py"
            added.write_text("def test_new(): assert True\n")
            r = self._verify(manifest_path)
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn(str(added), r.stderr)

    def test_delete_in_dir_root_cli(self):
        # ディレクトリ lock 後にファイル削除 -> verify exit 2 で削除パスを列挙
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            tests = tdp / "tests"
            tests.mkdir()
            fa = tests / "test_a.py"
            fa.write_text("def test_a(): assert True\n")
            (tests / "test_b.py").write_text("def test_b(): assert True\n")
            manifest_path = tdp / "manifest.json"
            self.assertEqual(self._lock([str(tests)], manifest_path).returncode, 0)
            self.assertEqual(self._verify(manifest_path).returncode, 0)

            fa.unlink()
            r = self._verify(manifest_path)
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn(str(fa), r.stderr)

    def test_delete_file_root_no_crash_cli(self):
        # ファイルを直接 lock -> そのファイル削除 -> exit 1 でクラッシュせず exit 2
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            fa = tdp / "test_a.py"
            fa.write_text("def test_a(): assert True\n")
            manifest_path = tdp / "manifest.json"
            self.assertEqual(self._lock([str(fa)], manifest_path).returncode, 0)
            self.assertEqual(self._verify(manifest_path).returncode, 0)

            fa.unlink()
            r = self._verify(manifest_path)
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn(str(fa), r.stderr)

    def test_oracle_artifacts_no_false_positive_cli(self):
        # __pycache__/*.pyc と .pytest_cache/（hidden dir）が生成されても verify exit 0
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            tests = tdp / "tests"
            tests.mkdir()
            (tests / "test_a.py").write_text("def test_a(): assert True\n")
            manifest_path = tdp / "manifest.json"
            self.assertEqual(self._lock([str(tests)], manifest_path).returncode, 0)

            # oracle 実行が生成する類の生成物を後から作る
            (tests / "__pycache__").mkdir()
            (tests / "__pycache__" / "test_a.cpython-312.pyc").write_bytes(b"\x00fake")
            pytest_cache = tests / ".pytest_cache" / "v" / "cache"
            pytest_cache.mkdir(parents=True)
            (pytest_cache / "lastfailed").write_text("{}\n")
            (tests / ".coverage").write_bytes(b"\x00cov")

            r = self._verify(manifest_path)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_hidden_ancestor_no_empty_manifest_cli(self):
        # 祖先に hidden 要素を含む絶対パス配下を lock -> 非 hidden ファイルが files に載る
        # （相対パス評価により祖先 hidden で全除外されない）+ 追加検出も効く
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            tests = tdp / ".hidden" / "tests"
            tests.mkdir(parents=True)
            (tests / "test_a.py").write_text("def test_a(): assert True\n")
            manifest_path = tdp / "manifest.json"
            self.assertEqual(self._lock([str(tests)], manifest_path).returncode, 0)
            import json as _json
            m = _json.loads(manifest_path.read_text())
            self.assertIn(str(tests / "test_a.py"), m["files"])
            self.assertEqual(self._verify(manifest_path).returncode, 0)

            added = tests / "conftest.py"
            added.write_text("x = 1\n")
            r = self._verify(manifest_path)
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn(str(added), r.stderr)

    def test_invalid_manifest_fail_closed_cli(self):
        # 旧フラット / roots 欠落 / 壊れた JSON / 非 dict を verify に渡すと exit 2
        cases = [
            '{"tests/a.py": "abc123"}',            # 旧フラット形式
            '{"version": 2, "files": {}}',          # roots 欠落
            '{"version": 1, "roots": [], "files": {}}',  # version 不正
            'not valid json {{{',                   # 壊れた JSON
            'null',                                 # 非 dict トップレベル
            '[]',                                   # 非 dict トップレベル
        ]
        with tempfile.TemporaryDirectory() as td:
            for i, body in enumerate(cases):
                manifest_path = Path(td) / f"m{i}.json"
                manifest_path.write_text(body)
                r = self._verify(manifest_path)
                self.assertEqual(r.returncode, 2, f"case={body!r} stderr={r.stderr}")
                self.assertIn("invalid manifest", r.stderr, f"case={body!r}")

    def test_non_string_roots_element_fail_closed_cli(self):
        # roots 要素が非 str の manifest を verify に渡すと exit 1 クラッシュせず exit 2
        import json as _json
        with tempfile.TemporaryDirectory() as td:
            for i, bad in enumerate(([123], [None], [[]])):
                manifest_path = Path(td) / f"m{i}.json"
                manifest_path.write_text(
                    _json.dumps({"version": 2, "roots": bad, "files": {}})
                )
                r = self._verify(manifest_path)
                self.assertEqual(r.returncode, 2, f"bad={bad!r} stderr={r.stderr}")
                self.assertIn("invalid manifest", r.stderr, f"bad={bad!r}")

    def test_missing_manifest_file_fail_closed_cli(self):
        r = subprocess.run(
            [sys.executable, str(GOAL_LOOP_PY), "verify", "/nonexistent/m.json"],
            capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("invalid manifest", r.stderr)

    def test_enumeration_oserror_fail_closed(self):
        # 列挙フェーズ（_collect_paths）の OSError が exit 1 に漏れず exit 2 に倒れる。
        # symlink ループの再現は環境依存なので、列挙関数へ OSError を注入して代替する。
        import json as _json
        with tempfile.TemporaryDirectory() as td:
            manifest_path = Path(td) / "manifest.json"
            manifest_path.write_text(_json.dumps(
                {"version": 2, "roots": ["tests"], "files": {"tests/a.py": "abc"}}
            ))
            original = goal_loop._collect_paths
            try:
                def _boom(_roots):
                    raise OSError("too many symbolic links encountered")
                goal_loop._collect_paths = _boom
                rc = cmd_verify([str(manifest_path)])
            finally:
                goal_loop._collect_paths = original
            self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
