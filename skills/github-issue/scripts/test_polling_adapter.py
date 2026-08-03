"""polling_adapter の契約テスト。"""

import json
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest import mock

import polling_adapter as adapter


class ParsingTests(unittest.TestCase):
    def test_verdict_five_cases(self):
        cases = [
            ("## 自走可否\n判定: 自走可", "ALLOWED"),
            ("## 自走可否\n判定: 自走不可", "FORBIDDEN"),
            ("## 自走可否\n判定: 部分的に自走可", "AMBIGUOUS"),
            ("## 自走可否\n説明のみ", "MISSING"),
            ("本文だけ", "MISSING"),
        ]
        for body, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(adapter.parse_self_drive_verdict(body), expected)

    def test_verdict_ignores_fenced_and_rejects_conflict(self):
        body = "```\n## 自走可否\n判定: 自走不可\n```\n## 自走可否\n判定: 自走可"
        self.assertEqual(adapter.parse_self_drive_verdict(body), "ALLOWED")
        self.assertEqual(adapter.parse_self_drive_verdict(
            "## 自走可否\n判定: 自走可\n判定: 自走不可"), "AMBIGUOUS")

    def test_verdict_does_not_close_fence_with_different_delimiter(self):
        body = "```python\n## 自走可否\n判定: 自走不可\n~~~\n判定: 自走可\n```"
        self.assertEqual(adapter.parse_self_drive_verdict(body), adapter.MISSING)

    def test_verdict_ignores_backtick_fence_with_backtick_in_info_string(self):
        body = "```bad`info\n## 自走可否\n判定: 自走可\n"
        self.assertEqual(adapter.parse_self_drive_verdict(body), "ALLOWED")

    def test_verdict_does_not_close_long_fence_with_short_fence(self):
        body = "````\n## 自走可否\n判定: 自走不可\n```\n判定: 自走可\n````"
        self.assertEqual(adapter.parse_self_drive_verdict(body), adapter.MISSING)

    def test_change_targets_annotations_dedupe_and_backticks(self):
        body = "## 変更対象\n- `a/b.md`\n- a/b.md:170 — 注釈\n* c.py\n- a/b.md\n## 次"
        self.assertEqual(adapter.parse_change_targets(body), ["a/b.md", "c.py"])

    def test_change_targets_hostile_rejects_whole_section(self):
        for path in ("../secret", "/etc/passwd", "a/../b"):
            with self.subTest(path=path):
                self.assertEqual(adapter.parse_change_targets(f"## 変更対象\n- good.py\n- {path}"), adapter.MISSING)

    def test_change_targets_skips_invalid_annotated_item(self):
        body = "## 変更対象\n- good.py\n- ../secret:1 — note\n- also/good.md"
        self.assertEqual(adapter.parse_change_targets(body), ["good.py", "also/good.md"])


class GateTests(unittest.TestCase):
    def test_forbidden_path(self):
        runner = mock.Mock(side_effect=AssertionError("oracle must not run"))
        result = adapter.gate_0_decision(
            ["skills/shared/x.py"],
            {"forbidden_path_globs": ["skills/shared/**"], "impact_command": "oracle {files}"},
            runner,
        )
        self.assertEqual(result["reason"], "forbidden_path")
        runner.assert_not_called()

    def test_no_oracle(self):
        self.assertEqual(adapter.gate_0_decision(["x.py"], {})["impact_units"], adapter.NO_ORACLE)

    def test_oracle_failure_is_reject(self):
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 1, "", "bad"))
        result = adapter.gate_0_decision(["x.py"], {"impact_command": "oracle {files}"}, runner)
        self.assertEqual(result, {"decision": "REJECT", "reason": "impact_oracle_failed"})

    def test_impact_too_wide(self):
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, "one\ntwo\n", ""))
        result = adapter.gate_0_decision(["x.py"], {"impact_command": "oracle {files}", "max_impacted_units": 1}, runner)
        self.assertEqual(result["reason"], "impact_too_wide")


class LabelsAndValidationTests(unittest.TestCase):
    def test_failure_precedence_and_legacy(self):
        with mock.patch.object(adapter, "warn") as warning:
            self.assertEqual(adapter.state_of_failure(
                ["claude-failed-transient", "claude-failed-permanent"]), "permanent")
            warning.assert_called_once()
        self.assertEqual(adapter.state_of_failure(["claude-failed"]), "permanent")
        self.assertEqual(adapter.state_of_failure(["claude-failed-transient", "claude-failed"]), "transient")

    def test_normalize_git_url(self):
        cases = {
            "git@GitHub.com:Owner/Repo.git": "https://github.com/owner/repo",
            "ssh://git@github.com/Owner/Repo.git/": "https://github.com/owner/repo",
            "https://github.com/Owner/Repo.git/": "https://github.com/owner/repo",
        }
        for raw, expected in cases.items():
            self.assertEqual(adapter.normalize_git_url(raw), expected)
        for raw in ("https://github.com/a b", "https://github.com/a/../b", "x\\y", "x;$y"):
            with self.assertRaises(adapter.FailClosed):
                adapter.normalize_git_url(raw)

    def test_validate_slug_rejections(self):
        self.assertEqual(adapter.validate_slug("issue-7"), 7)
        for slug in ("issue-007", "issue-0", "issue--1", "issue-nope"):
            with self.subTest(slug=slug), self.assertRaises(adapter.FailClosed):
                adapter.validate_slug(slug)


class FileStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_retry_missing_and_validation(self):
        self.assertEqual(adapter.retry_state(1, self.root)["retry_count"], 0)
        retry = self.root / "retry" / "1.json"
        retry.write_text(json.dumps({"retry_count": 10000, "last_failed_at": "bad", "run_id": "not-v4"}))
        state = adapter.retry_state(1, self.root)
        self.assertEqual(state, {"retry_count": 0, "last_failed_at": None, "run_id": None})

    def test_retry_fields_are_validated_independently(self):
        retry = self.root / "retry" / "1.json"
        retry.parent.mkdir()
        valid_time = "2026-08-03T00:00:00Z"
        retry.write_text(json.dumps({"retry_count": 7, "last_failed_at": valid_time,
                                     "run_id": "not-v4"}))
        self.assertEqual(adapter.retry_state(1, self.root)["retry_count"], 7)
        retry.write_text(json.dumps({"retry_count": 8, "last_failed_at": "bad",
                                     "run_id": "550e8400-e29b-41d4-a716-446655440000"}))
        self.assertEqual(adapter.retry_state(1, self.root)["retry_count"], 8)

    def test_retry_count_boundaries_and_bool(self):
        retry = self.root / "retry" / "1.json"
        retry.parent.mkdir()
        for value, expected in ((-1, 0), (True, 0), (9999, 9999), (10000, 0)):
            with self.subTest(value=value):
                retry.write_text(json.dumps({"retry_count": value}))
                self.assertEqual(adapter.retry_state(1, self.root)["retry_count"], expected)

    def test_retry_corrupt_quarantine_and_second_failure(self):
        retry = self.root / "retry"
        retry.mkdir()
        path = retry / "2.json"
        path.write_text("{")
        self.assertEqual(adapter.retry_state(2, self.root)["retry_count"], 0)
        self.assertEqual(len(list(retry.glob("2.json.corrupt.*"))), 1)
        path.write_text("{")
        with self.assertRaisesRegex(adapter.FailClosed, "retry state corruption"):
            adapter.retry_state(2, self.root)

    def test_increment_requires_strict_uuid4(self):
        with self.assertRaises(adapter.FailClosed):
            adapter.increment_retry(3, self.root, "550e8400-e29b-11d4-a716-446655440000")
        value = adapter.increment_retry(3, self.root, "550e8400-e29b-41d4-a716-446655440000")
        self.assertEqual(value["retry_count"], 1)

    def test_write_atomic_replaces_and_permissions(self):
        path = self.root / "nested" / "state.json"
        adapter.write_atomic(path, "one")
        adapter.write_atomic(path, "two")
        self.assertEqual(path.read_text(), "two")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertFalse(list(path.parent.glob("*.tmp.*")))

    def test_write_atomic_syscall_order_and_exclusive_create(self):
        path = self.root / "state.json"
        events = []
        real_open, real_fsync, real_replace = os.open, os.fsync, os.replace

        def recording_open(target, flags, *args):
            if ".tmp." in str(target):
                self.assertTrue(flags & os.O_EXCL)
                events.append("open_tmp")
            return real_open(target, flags, *args)

        def recording_fsync(fd):
            events.append("fsync_parent" if os.path.isdir(f"/proc/self/fd/{fd}") else "fsync_data")
            return real_fsync(fd)

        def recording_replace(src, dst):
            events.append("rename")
            return real_replace(src, dst)

        with mock.patch.object(adapter.os, "open", side_effect=recording_open), \
             mock.patch.object(adapter.os, "fsync", side_effect=recording_fsync), \
             mock.patch.object(adapter.os, "replace", side_effect=recording_replace):
            adapter.write_atomic(path, "data")
        self.assertLess(events.index("fsync_data"), events.index("rename"))
        self.assertLess(events.index("rename"), events.index("fsync_parent"))

    def test_claim_lock_acquire_busy_and_stale_reacquire(self):
        me = os.getpid()
        result = adapter.claim_lock(4, self.root, me)
        self.assertEqual(result["status"], "claimed")
        with mock.patch.object(adapter, "_pid_alive", return_value=True):
            with self.assertRaises(adapter.LockBusy):
                adapter.claim_lock(4, self.root, me + 1)
        lock = self.root / "claim" / "4.lock"
        old = time.time() - 301
        os.utime(lock, (old, old))
        with mock.patch.object(adapter, "_pid_alive", return_value=False):
            self.assertEqual(adapter.claim_lock(4, self.root, me + 1)["owner_pid"], me + 1)

    def test_claim_lock_live_old_and_dead_recent_are_busy(self):
        me = os.getpid()
        adapter.claim_lock(4, self.root, me)
        lock = self.root / "claim" / "4.lock"
        old = time.time() - 301
        os.utime(lock, (old, old))
        with mock.patch.object(adapter, "_pid_alive", return_value=True), \
             self.assertRaises(adapter.LockBusy):
            adapter.claim_lock(4, self.root, me + 1)
        os.utime(lock, None)
        with mock.patch.object(adapter, "_pid_alive", return_value=False), \
             self.assertRaises(adapter.LockBusy):
            adapter.claim_lock(4, self.root, me + 1)

    def test_release_lock_checks_owner_or_dead_pid(self):
        me = os.getpid()
        adapter.claim_lock(5, self.root, me)
        with mock.patch.object(adapter, "_pid_alive", return_value=True), \
             mock.patch.object(adapter, "warn") as warning:
            self.assertFalse(adapter.release_lock(5, self.root, me + 1)["released"])
            warning.assert_called_once()
        self.assertTrue(adapter.release_lock(5, self.root, me)["released"])
        adapter.claim_lock(5, self.root, me)
        with mock.patch.object(adapter, "_pid_alive", return_value=False):
            self.assertTrue(adapter.release_lock(5, self.root, me + 1)["released"])

    def test_recovery_marker_ttl(self):
        adapter.recovery_marker("add", self.root, 8)
        marker = self.root / "recovery" / "8"
        old = time.time() - 7 * 86400
        os.utime(marker, (old, old))
        listed = adapter.recovery_marker("list", self.root, now=time.time())
        self.assertTrue(listed[0]["expired"])

    def test_kill_files_hard_first(self):
        (self.root / ".STOP").touch()
        files = adapter.kill_files(self.root)
        self.assertEqual([Path(item["path"]).name for item in files], [".STOP.hard", ".STOP"])
        self.assertEqual([item["exists"] for item in files], [False, True])

    def test_state_root_fs_getter_is_injectable(self):
        with mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.root)}):
            result = adapter.resolve_state_root("Owner/Repo", "git@github.com:Owner/Repo.git",
                                                fs_type_getter=lambda _: "ext4")
        self.assertEqual(result["filesystem"], "ext4")
        self.assertEqual(Path(result["state_root"]).stat().st_mode & 0o777, 0o700)

    def test_state_root_xdg_unset_and_empty_use_home_fallback(self):
        for environment in ({}, {"XDG_STATE_HOME": ""}):
            with self.subTest(environment=environment), \
                 mock.patch.dict(os.environ, environment, clear=True), \
                 mock.patch.object(adapter.Path, "expanduser", autospec=True,
                                   side_effect=lambda path: self.root / "fallback") as expanduser:
                result = adapter.resolve_state_root("Owner/Repo", "https://github.com/owner/repo",
                                                    fs_type_getter=lambda _: "ext4")
                self.assertIn(str(self.root / "fallback"), result["state_root"])
                self.assertEqual(str(expanduser.call_args.args[0]), "~/.local/state")

    def test_state_root_clone_id_is_sha1_prefix(self):
        url = "https://github.com/owner/repo"
        with mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.root)}):
            result = adapter.resolve_state_root("Owner/Repo", url, fs_type_getter=lambda _: "ext4")
        expected = hashlib.sha1(url.encode()).hexdigest()[:16]
        self.assertTrue(Path(result["state_root"]).name.endswith(expected))

    def test_state_root_clone_marker_symlink_fails_closed(self):
        url = "https://github.com/owner/repo"
        clone_id = hashlib.sha1(url.encode()).hexdigest()[:16]
        target = self.root / "claude-skills" / "github-issue" / f"Owner_Repo-{clone_id}"
        target.mkdir(parents=True)
        outside = self.root / "outside"
        outside.write_text(url)
        (target / ".clone_url").symlink_to(outside)
        with mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.root)}), \
             self.assertRaisesRegex(adapter.FailClosed, "unsafe state_root clone marker"):
            adapter.resolve_state_root("Owner/Repo", url, fs_type_getter=lambda _: "ext4")

    def test_state_root_collision_unsupported_fs_and_symlink_fail_closed(self):
        url = "https://github.com/owner/repo"
        with mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.root)}):
            result = adapter.resolve_state_root("Owner/Repo", url, fs_type_getter=lambda _: "ext4")
            Path(result["state_root"], ".clone_url").write_text("different")
            with self.assertRaisesRegex(adapter.FailClosed, "collision"):
                adapter.resolve_state_root("Owner/Repo", url, fs_type_getter=lambda _: "ext4")
            Path(result["state_root"], ".clone_url").write_text(url)
            with self.assertRaisesRegex(adapter.FailClosed, "unsupported filesystem"):
                adapter.resolve_state_root("Owner/Repo", url, fs_type_getter=lambda _: "nfs4")

        symlink_base = self.root / "symlink-base" / "claude-skills" / "github-issue"
        symlink_base.mkdir(parents=True)
        target_name = Path(result["state_root"]).name
        real = self.root / "real"
        real.mkdir()
        (symlink_base / target_name).symlink_to(real, target_is_directory=True)
        with mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.root / "symlink-base")}):
            with self.assertRaisesRegex(adapter.FailClosed, "symlink"):
                adapter.resolve_state_root("Owner/Repo", url, fs_type_getter=lambda _: "ext4")


class FilterTests(unittest.TestCase):
    def test_filter_ready_checks_every_issue(self):
        allowed = "## 自走可否\n判定: 自走可\n## 変更対象\n- src/x.py"
        issues = [
            {"number": 1, "labels": [], "authorAssociation": "OWNER", "body": allowed},
            {"number": 2, "labels": ["claude-running"], "authorAssociation": "OWNER", "body": allowed},
            {"number": 3, "labels": [], "authorAssociation": "NONE", "body": allowed},
        ]
        result = adapter.filter_ready(issues, {"require_author_association": ["OWNER"]})
        self.assertEqual(result["slugs"], ["issue-1"])
        self.assertEqual([item["number"] for item in result["excluded"]], [2, 3])

    def test_filter_ready_exclusion_reasons_and_oracle_short_circuit(self):
        allowed = "## 自走可否\n判定: 自走可\n## 変更対象\n- src/x.py"
        issues = [
            {"number": 1, "labels": ["claude-review"], "authorAssociation": "OWNER", "body": allowed},
            {"number": 2, "labels": ["claude-failed"], "authorAssociation": "OWNER", "body": allowed},
            {"number": 3, "labels": [], "authorAssociation": "OWNER", "body": "## 自走可否\n判定: 自走不可"},
            {"number": 4, "labels": [], "authorAssociation": "OWNER", "body": "## 自走可否\n判定: 自走可"},
        ]
        with mock.patch.object(adapter, "impact_units", side_effect=AssertionError("oracle must not run")):
            result = adapter.filter_ready(issues, {"impact_command": "oracle {files}"})
        self.assertEqual(result["excluded"], [
            {"number": 1, "reason": "review"},
            {"number": 2, "reason": "failed"},
            {"number": 3, "reason": "gate1_forbidden"},
            {"number": 4, "reason": "gate0_missing_targets"},
        ])


if __name__ == "__main__":
    unittest.main()
