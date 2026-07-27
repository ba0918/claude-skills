"""workspace_lock の単体テスト。

このロックの価値は「取れること」ではなく **「生きている claim を絶対に奪わないこと」** と
**「取れない環境で処理を止めないこと」** にある。前者が崩れれば防ごうとした事故がそのまま
起き、後者が崩れればレガシー構成が動かなくなって無効化される。両方を同じ重みで固定する。
"""
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import workspace_lock as wl  # noqa: E402

DEAD_PID = 2 ** 22 - 1  # Linux の既定 pid_max を超える値。存在しえない


class WorkspaceLockTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name)

    def _record(self):
        return json.loads(wl.claim_path(self.repo).read_text(encoding="utf-8"))


class TestClaim(WorkspaceLockTest):
    def test_first_claim_acquires_and_records_the_holder(self):
        result = wl.claim(self.repo, "cycle", branch="feat/x")
        self.assertEqual(wl.ACQUIRED, result.outcome)
        self.assertTrue(result.ok)
        record = self._record()
        self.assertEqual("cycle", record["skill"])
        self.assertEqual("feat/x", record["branch"])
        self.assertEqual(os.getpid(), record["pid"])
        self.assertEqual(result.token, record["token"])
        self.assertTrue(record["started_at"])

    def test_second_claim_in_the_same_tree_is_lock_held(self):
        wl.claim(self.repo, "cycle")
        result = wl.claim(self.repo, "iterate")
        self.assertEqual(wl.LOCK_HELD, result.outcome)
        self.assertFalse(result.ok)
        self.assertEqual("cycle", result.holder["skill"])
        self.assertIsNone(result.token)

    def test_a_live_claim_is_never_taken_over(self):
        """生存中の claim を奪う経路が存在しないこと。"""
        first = wl.claim(self.repo, "cycle")
        for _ in range(3):
            self.assertEqual(wl.LOCK_HELD, wl.claim(self.repo, "plan-implement").outcome)
        self.assertEqual(first.token, self._record()["token"])

    def test_separate_trees_do_not_collide(self):
        """資源は作業ツリーのパス。別ツリーなら同一ブランチでも衝突しない。"""
        with tempfile.TemporaryDirectory() as other:
            self.assertEqual(wl.ACQUIRED, wl.claim(self.repo, "cycle", branch="main").outcome)
            self.assertEqual(wl.ACQUIRED, wl.claim(Path(other), "cycle", branch="main").outcome)

    def test_the_same_tree_collides_across_branches(self):
        """識別子はブランチではないので、同一チェックアウトなら別ブランチでも衝突する。"""
        wl.claim(self.repo, "cycle", branch="feat/a")
        self.assertEqual(wl.LOCK_HELD, wl.claim(self.repo, "cycle", branch="feat/b").outcome)

    def test_claim_file_is_created_0600(self):
        wl.claim(self.repo, "cycle")
        mode = stat.S_IMODE(os.stat(wl.claim_path(self.repo)).st_mode)
        self.assertEqual(0o600, mode)


class TestStaleReclaim(WorkspaceLockTest):
    def test_dead_holder_is_reclaimed(self):
        wl.claim(self.repo, "cycle")
        path = wl.claim_path(self.repo)
        record = json.loads(path.read_text(encoding="utf-8"))
        record["pid"] = DEAD_PID
        path.write_text(json.dumps(record), encoding="utf-8")

        result = wl.claim(self.repo, "iterate")
        self.assertEqual(wl.STALE_RECLAIMED, result.outcome)
        self.assertTrue(result.ok)
        self.assertEqual(DEAD_PID, result.holder["pid"])
        self.assertEqual(result.token, self._record()["token"])
        self.assertEqual("iterate", self._record()["skill"])

    def test_reclaimed_file_keeps_mode_0600(self):
        wl.claim(self.repo, "cycle", pid=DEAD_PID)
        wl.claim(self.repo, "iterate")
        self.assertEqual(0o600, stat.S_IMODE(os.stat(wl.claim_path(self.repo)).st_mode))

    def test_unreadable_record_is_treated_as_stale_with_a_warning(self):
        path = wl.claim_path(self.repo)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json at all", encoding="utf-8")
        result = wl.claim(self.repo, "cycle")
        self.assertEqual(wl.STALE_RECLAIMED, result.outcome)
        self.assertTrue(any("unreadable" in w for w in result.warnings))

    def test_pid_liveness_treats_permission_denied_as_alive(self):
        """別ユーザの pid を「死んでいる」と誤判定すると他人の claim を奪う。"""
        self.assertTrue(wl.pid_is_alive(os.getpid()))
        self.assertFalse(wl.pid_is_alive(DEAD_PID))
        self.assertFalse(wl.pid_is_alive(0))
        self.assertFalse(wl.pid_is_alive(-1))
        self.assertFalse(wl.pid_is_alive("1234"))


class TestRelease(WorkspaceLockTest):
    def test_holder_can_release_and_reclaim(self):
        first = wl.claim(self.repo, "cycle")
        self.assertTrue(wl.release(self.repo, first.token))
        self.assertFalse(wl.claim_path(self.repo).exists())
        self.assertEqual(wl.ACQUIRED, wl.claim(self.repo, "iterate").outcome)

    def test_a_wrong_token_cannot_release(self):
        wl.claim(self.repo, "cycle")
        self.assertFalse(wl.release(self.repo, "deadbeef"))
        self.assertTrue(wl.claim_path(self.repo).exists())

    def test_release_without_a_claim_is_not_an_error(self):
        """孤児回収が先に走った後の trap でも shutdown を落とさない。"""
        self.assertFalse(wl.release(self.repo, "anything"))

    def test_release_with_no_token_is_rejected(self):
        wl.claim(self.repo, "cycle")
        self.assertFalse(wl.release(self.repo, None))
        self.assertTrue(wl.claim_path(self.repo).exists())


class TestFailOpen(WorkspaceLockTest):
    def test_unwritable_runtime_area_warns_and_continues(self):
        """ロックできない環境で止めると、これまで動いていた構成が動かなくなる。"""
        agents = self.repo / ".agents"
        agents.mkdir()
        agents.chmod(0o500)
        self.addCleanup(agents.chmod, 0o700)
        result = wl.claim(self.repo, "cycle")
        self.assertEqual(wl.UNAVAILABLE, result.outcome)
        self.assertTrue(result.ok, "fail-open なので処理は続行する")
        self.assertTrue(any("without the workspace lock" in w for w in result.warnings))


class TestStatus(WorkspaceLockTest):
    def test_status_is_none_when_unclaimed(self):
        self.assertIsNone(wl.status(self.repo))

    def test_status_reports_the_holder_and_liveness(self):
        wl.claim(self.repo, "cycle", branch="main")
        state = wl.status(self.repo)
        self.assertEqual("cycle", state["skill"])
        self.assertTrue(state["alive"])

    def test_status_marks_a_dead_holder(self):
        wl.claim(self.repo, "cycle", pid=DEAD_PID)
        self.assertFalse(wl.status(self.repo)["alive"])


class TestDescribe(WorkspaceLockTest):
    def test_conflict_display_names_the_holder_and_offers_two_options(self):
        wl.claim(self.repo, "cycle", branch="feat/x")
        text = wl.describe(wl.claim(self.repo, "iterate"))
        for expected in ("LOCK_HELD", "cycle", "feat/x", "started_at",
                         ".agents/runtime/workspace.claim"):
            self.assertIn(expected, text)

    def test_no_force_option_is_offered(self):
        """自動で奪う経路を提示しない（実装にも表示にも存在させない）。"""
        wl.claim(self.repo, "cycle")
        text = wl.describe(wl.claim(self.repo, "iterate")).lower()
        for forbidden in ("force", "override", "steal", "--yes"):
            self.assertNotIn(forbidden, text)

    def test_describe_is_empty_for_a_successful_claim(self):
        self.assertEqual("", wl.describe(wl.claim(self.repo, "cycle")))



class TestCli(WorkspaceLockTest):
    """スキル本文から呼ぶ経路。CLI が無いと呼び出し側が各自で発明して食い違う。"""

    def _run(self, *argv):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = wl._cli(list(argv))
        return code, buf.getvalue()

    def test_claim_prints_the_outcome_and_exits_zero(self):
        code, out = self._run("claim", "--repo", str(self.repo), "--skill", "cycle")
        self.assertEqual(0, code)
        payload = json.loads(out.splitlines()[0])
        self.assertEqual(wl.ACQUIRED, payload["outcome"])
        self.assertTrue(payload["token"])

    def test_lock_held_is_the_only_non_zero_exit(self):
        self._run("claim", "--repo", str(self.repo), "--skill", "cycle")
        code, out = self._run("claim", "--repo", str(self.repo), "--skill", "iterate")
        self.assertEqual(1, code)
        self.assertIn("LOCK_HELD", out)
        self.assertIn("cycle", out)

    def test_unavailable_exits_zero_because_the_contract_is_fail_open(self):
        agents = self.repo / ".agents"
        agents.mkdir()
        agents.chmod(0o500)
        self.addCleanup(agents.chmod, 0o700)
        code, out = self._run("claim", "--repo", str(self.repo), "--skill", "cycle")
        self.assertEqual(0, code)
        self.assertEqual(wl.UNAVAILABLE, json.loads(out.splitlines()[0])["outcome"])

    def test_release_round_trip(self):
        _, out = self._run("claim", "--repo", str(self.repo), "--skill", "cycle")
        token = json.loads(out.splitlines()[0])["token"]
        code, out = self._run("release", "--repo", str(self.repo), "--token", token)
        self.assertEqual(0, code)
        self.assertTrue(json.loads(out)["released"])

    def test_status_reports_none_then_the_holder(self):
        _, out = self._run("status", "--repo", str(self.repo))
        self.assertIsNone(json.loads(out))
        self._run("claim", "--repo", str(self.repo), "--skill", "iterate")
        _, out = self._run("status", "--repo", str(self.repo))
        self.assertEqual("iterate", json.loads(out)["skill"])

if __name__ == "__main__":
    unittest.main()
