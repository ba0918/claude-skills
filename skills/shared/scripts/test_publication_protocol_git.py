#!/usr/bin/env python3
"""publication-protocol.md の破壊的遷移を、正本プリミティブ経由で実行検証する回帰テスト。

surrogate 実装をテストしても本文とテストがドリトするだけなので、ここでは
cycle / iterate が実行するのと同じ publication_advance.py（advance / recover）を
使い捨て git リポジトリに対して起動し、機械的な不変条件を実測で固定する:

- happy path: prospective merge は main を動かさず、advance が構造検証（merge の形・
  CAS・ツリー安全）→ CAS → sync → durable marker（merge-intent staging）除去を
  単一実装で完了する
- 前提条件: dirty tree / 別 worktree に checkout された main は CAS 前に
  terminal failure（exit 3）で止まり、main は無傷
- CAS 競合: exit 4 で main・staging すべて無傷。stale を破棄して
  新 main から再作成すると retry が成功する
- crash 修復: durable marker（staging dir の SHA = main HEAD）だけから復旧し、
  phantom 状態の証明が成立するときのみ reset する。crash 後の本物のユーザー編集や
  untracked 衝突があるときは exit 6 で何も破壊しない。completion 途中の crash からも
  recover の再実行で収束する
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PRIMITIVE = ROOT / "skills/shared/scripts/publication_advance.py"
MARKER_NAME = "merge-intent.json"


def git(cwd, *args, check=True):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=check,
    )


class PublicationPrimitiveTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="pubproto-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.main = self.root / "main"
        self.main.mkdir()
        git(self.main, "init", "-q", "-b", "main")
        git(self.main, "config", "user.email", "test@example.com")
        git(self.main, "config", "user.name", "test")
        (self.main / ".gitignore").write_text(".agents/\n")
        (self.main / "a.txt").write_text("base\n")
        git(self.main, "add", ".")
        git(self.main, "commit", "-qm", "base")
        git(self.main, "branch", "satellite")
        sat = self.root / "sat"
        git(self.main, "worktree", "add", "-q", str(sat), "satellite")
        (sat / "b.txt").write_text("feature\n")
        git(sat, "add", ".")
        git(sat, "commit", "-qm", "feature")

    # -- protocol steps / primitive invocation --------------------------------

    def merge_cmd(self, suffix=""):
        return subprocess.run(
            [
                sys.executable, str(PRIMITIVE), "merge",
                "--repo-root", str(self.main),
                "--satellite-branch", "satellite",
                "--tmp-merge-root", str(self.root / f"tmp-merge{suffix}"),
            ],
            capture_output=True, text=True,
        )

    def prospective_merge(self, suffix=""):
        """Step 1 via the primitive: detached temp worktree + merge --no-ff."""
        result = self.merge_cmd(suffix)
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        return out["expected_main_sha"], out["post_merge_sha"], Path(out["tmp_merge_root"])

    def stage_marker(self, post, expected=None):
        """merge-intent durable marker を canonical staging へ書く（merge の再現）。"""
        staging = self.main / f".agents/artifacts/reviews/evidence-staging/{post}"
        staging.mkdir(parents=True, exist_ok=True)
        marker = {
            "schema_version": 1,
            "kind": "merge-intent",
            "post_merge_sha": post,
            "expected_main_sha": expected or "0" * 40,
            "branch": "main",
            "created_at": "2026-01-01T00:00:00Z",
        }
        (staging / MARKER_NAME).write_text(
            json.dumps(marker, ensure_ascii=False, indent=2) + "\n"
        )
        return staging

    def staging_path(self, sha):
        return self.main / f".agents/artifacts/reviews/evidence-staging/{sha}"

    def hold_lock(self):
        """workspace lock の claim を作り、holder 証明用の token を返す。"""
        claim = self.main / ".agents/runtime/workspace.claim"
        claim.parent.mkdir(parents=True, exist_ok=True)
        token = "test-lock-token"
        claim.write_text(json.dumps({"token": token, "pid": 1, "skill": "test"}))
        return token

    def advance(self, post, expected, token=None, staging=None):
        cmd = [
            sys.executable, str(PRIMITIVE), "advance",
            "--repo-root", str(self.main),
            "--post-merge-sha", post,
            "--expected-main-sha", expected,
        ]
        if token:
            cmd += ["--lock-token", token]
        if staging:
            cmd += ["--evidence-staging", str(staging)]
        return subprocess.run(cmd, capture_output=True, text=True).returncode

    def recover(self, token=None):
        cmd = [
            sys.executable, str(PRIMITIVE), "recover",
            "--repo-root", str(self.main),
        ]
        if token:
            cmd += ["--lock-token", token]
        return subprocess.run(cmd, capture_output=True, text=True).returncode

    def main_sha(self):
        return git(self.main, "rev-parse", "main").stdout.strip()

    def marker_exists(self, sha):
        return (self.staging_path(sha) / MARKER_NAME).exists()

    # -- merge -----------------------------------------------------------------

    def test_merge_conflict_is_terminal_and_leaves_main_untouched(self):
        (self.main / "a.txt").write_text("main side\n")
        git(self.main, "add", ".")
        git(self.main, "commit", "-qm", "main side")
        sat = self.root / "sat"
        (sat / "a.txt").write_text("satellite side\n")
        git(sat, "add", ".")
        git(sat, "commit", "-qm", "satellite side")
        before = self.main_sha()
        result = self.merge_cmd(suffix="-conflict")
        self.assertEqual(result.returncode, 3)
        self.assertEqual(self.main_sha(), before)
        self.assertFalse((self.root / "tmp-merge-conflict").exists())

    def test_merge_creates_merge_intent_marker(self):
        expected, post, _ = self.prospective_merge()
        self.assertEqual(self.main_sha(), expected)  # Step 1 must not advance main
        self.assertTrue(self.marker_exists(post))
        marker = json.loads(
            (self.staging_path(post) / MARKER_NAME).read_text(encoding="utf-8")
        )
        self.assertEqual(marker["kind"], "merge-intent")
        self.assertEqual(marker["post_merge_sha"], post)
        self.assertEqual(marker["expected_main_sha"], expected)

    # -- advance ---------------------------------------------------------------

    def test_advance_happy_path_syncs_and_clears_marker(self):
        expected, post, _ = self.prospective_merge()
        self.assertEqual(self.main_sha(), expected)  # Step 1 must not advance main
        self.assertTrue(self.marker_exists(post))    # merge intent recorded
        token = self.hold_lock()
        self.assertEqual(self.advance(post, expected, token), 0)
        self.assertEqual(self.main_sha(), post)
        self.assertTrue((self.main / "b.txt").exists())  # checkout synchronized
        self.assertFalse(self.marker_exists(post))       # durable marker cleared

    def test_advance_refuses_checked_out_main_without_lock_proof(self):
        # the lock requirement is enforced in code, not prose: a checked-out
        # main with no matching claim token stops before the CAS
        expected, post, _ = self.prospective_merge()
        self.assertEqual(self.advance(post, expected), 3)      # no token at all
        self.hold_lock()
        self.assertEqual(self.advance(post, expected, "wrong-token"), 3)
        self.assertEqual(self.main_sha(), expected)            # ref never moved

    def test_advance_refuses_dirty_main_tree(self):
        expected, post, _ = self.prospective_merge()
        (self.main / "a.txt").write_text("local edit\n")
        self.assertEqual(self.advance(post, expected, self.hold_lock()), 3)
        self.assertEqual(self.main_sha(), expected)  # main untouched
        self.assertEqual((self.main / "a.txt").read_text(), "local edit\n")

    def test_advance_refuses_main_checked_out_in_foreign_worktree(self):
        expected, post, _ = self.prospective_merge()
        # move the main checkout to a foreign worktree: repo-root switches away
        git(self.main, "checkout", "-q", "-b", "work")
        foreign = self.root / "foreign-main"
        git(self.main, "worktree", "add", "-q", str(foreign), "main")
        self.assertEqual(self.advance(post, expected), 3)
        self.assertEqual(self.main_sha(), expected)  # ref untouched
        self.assertFalse((foreign / "b.txt").exists())  # foreign checkout untouched

    def test_advance_cas_conflict_preserves_all_then_retry_succeeds(self):
        expected, post, tmp = self.prospective_merge()
        (self.main / "c.txt").write_text("concurrent\n")
        git(self.main, "add", ".")
        git(self.main, "commit", "-qm", "concurrent")
        moved = self.main_sha()
        token = self.hold_lock()
        self.assertEqual(self.advance(post, expected, token), 4)
        self.assertEqual(self.main_sha(), moved)             # main untouched
        self.assertTrue(self.marker_exists(post))            # durable marker preserved
        # CAS retry rule: discard the protocol's own intermediates, redo Steps 1-2
        git(self.main, "worktree", "remove", "--force", str(tmp))
        shutil.rmtree(self.staging_path(post))
        expected2, post2, _ = self.prospective_merge(suffix="-retry")
        self.assertEqual(expected2, moved)
        self.assertEqual(self.advance(post2, expected2, token), 0)
        self.assertEqual(self.main_sha(), post2)
        self.assertFalse(self.marker_exists(post2))

    # -- recover ---------------------------------------------------------------

    def crash_after_cas(self):
        """CAS 直後の crash 状態を作る: ref は前進、checkout は旧 tree のまま。"""
        expected, post, _ = self.prospective_merge()
        git(self.main, "update-ref", "refs/heads/main", post, expected)
        self.assertFalse((self.main / "b.txt").exists())
        return expected, post

    def test_recover_without_marker_reports_nothing_to_do(self):
        self.assertEqual(self.recover(), 5)

    def test_recover_phantom_state_from_durable_marker_alone(self):
        _, post = self.crash_after_cas()
        # a fresh process derives everything from disk: no SHAs are passed in
        self.assertEqual(self.recover(self.hold_lock()), 0)
        self.assertTrue((self.main / "b.txt").exists())
        self.assertFalse(self.marker_exists(post))
        self.assertEqual(self.recover(), 5)  # second run: nothing left to repair

    def test_recover_refuses_real_edits_after_crash(self):
        expected, post = self.crash_after_cas()
        (self.main / "a.txt").write_text("post-crash human edit\n")
        self.assertEqual(self.recover(self.hold_lock()), 6)
        # nothing destroyed: the edit survives, main ref stays at post
        self.assertEqual((self.main / "a.txt").read_text(), "post-crash human edit\n")
        self.assertEqual(self.main_sha(), post)
        self.assertTrue(self.marker_exists(post))

    def test_recover_refuses_untracked_collision_with_merged_tree(self):
        expected, post = self.crash_after_cas()
        (self.main / "b.txt").write_text("unrelated local file\n")  # merge adds b.txt
        self.assertEqual(self.recover(self.hold_lock()), 6)
        self.assertEqual((self.main / "b.txt").read_text(), "unrelated local file\n")
        self.assertTrue(self.marker_exists(post))

    def test_recover_with_other_branch_checked_out_clears_marker_without_reset(self):
        # git reset --hard moves whichever branch is checked out; recovery must
        # not run it when main is not the checked-out branch, or it would force
        # that branch's ref onto main's SHA. The lock is still required: marker
        # removal alone rewrites shared state
        _, post = self.crash_after_cas()
        git(self.main, "switch", "-q", "-c", "hotfix")
        hotfix_before = git(self.main, "rev-parse", "hotfix").stdout.strip()
        self.assertEqual(self.recover(), 6)  # marker removal without lock proof refused
        self.assertEqual(self.recover(self.hold_lock()), 0)
        self.assertEqual(
            git(self.main, "rev-parse", "hotfix").stdout.strip(), hotfix_before
        )
        self.assertEqual(self.main_sha(), post)      # main ref stays advanced
        self.assertFalse((self.main / "b.txt").exists())  # no reset ran
        self.assertFalse(self.marker_exists(post))        # marker still cleared

    def test_recover_requires_lock_proof_before_destructive_reset(self):
        _, post = self.crash_after_cas()
        self.assertEqual(self.recover(), 6)                 # no token
        self.hold_lock()
        self.assertEqual(self.recover("wrong-token"), 6)    # token mismatch
        self.assertFalse((self.main / "b.txt").exists())    # no reset ran

    def test_recover_detects_untracked_collision_with_spaced_pathname(self):
        # whitespace-split parsing of `diff --name-only` fragments a path like
        # "user notes.txt" and lets the collision through; -z parsing must not
        sat = self.root / "sat"
        (sat / "user notes.txt").write_text("satellite content\n")
        git(sat, "add", ".")
        git(sat, "commit", "-qm", "add spaced file")
        expected, post, _ = self.prospective_merge(suffix="-spaced")
        token = self.hold_lock()
        git(self.main, "update-ref", "refs/heads/main", post, expected)
        (self.main / "user notes.txt").write_text("local unrelated\n")
        self.assertEqual(self.recover(token), 6)
        self.assertEqual(
            (self.main / "user notes.txt").read_text(), "local unrelated\n"
        )

    def test_recover_converges_after_completion_interrupted(self):
        _, post = self.crash_after_cas()
        git(self.main, "reset", "-q", "--hard", "refs/heads/main")
        self.assertEqual(self.recover(self.hold_lock()), 0)  # rerun converges from intact marker
        self.assertFalse(self.marker_exists(post))

    # -- provenance / lock universality / post-commit-point failure -----------

    def test_advance_refuses_post_sha_not_derived_from_expected_main(self):
        # a stale or miswired caller must not move main to an unrelated commit
        # even when it carries a valid merge-intent marker
        expected, post, _ = self.prospective_merge()
        token = self.hold_lock()
        self.stage_marker(expected)
        # expected itself: no first parent relationship to itself → refused
        self.assertEqual(self.advance(expected, expected, token), 3)
        # satellite head: first parent matches but it is not a merge commit
        sat_sha = git(self.main, "rev-parse", "satellite").stdout.strip()
        self.stage_marker(sat_sha)
        self.assertEqual(self.advance(sat_sha, expected, token), 3)
        self.assertEqual(self.main_sha(), expected)  # ref never moved

    def test_advance_requires_lock_even_when_branch_not_checked_out(self):
        # ref advance + marker removal mutate shared state; the lock is
        # required even with no destructive checkout sync to run
        expected, post, _ = self.prospective_merge()
        git(self.main, "checkout", "-q", "-b", "work")  # main no longer checked out
        self.assertEqual(self.advance(post, expected), 3)
        self.assertEqual(self.main_sha(), expected)
        self.assertEqual(self.advance(post, expected, self.hold_lock()), 0)
        self.assertEqual(self.main_sha(), post)

    def test_advance_refuses_non_canonical_staging_paths(self):
        # marker removal deletes the staging directory on success; an arbitrary
        # --evidence-staging would let a miswired caller or compromised delegate
        # (holding the lock token) delete an unrelated directory after advancing
        expected, post, _ = self.prospective_merge()
        token = self.hold_lock()
        # victim directory even holds a merge-intent marker for the exact SHA
        victim = self.root / "victim"
        victim.mkdir()
        (victim / MARKER_NAME).write_text("not a marker\n")
        (victim / "unrelated.txt").write_text("do not delete\n")
        self.assertEqual(self.advance(post, expected, token, staging=victim), 3)
        self.assertTrue((victim / "unrelated.txt").exists())  # nothing deleted
        self.assertEqual(self.main_sha(), expected)           # main untouched
        # traversal spelling of an outside path is refused the same way
        dotted = self.main / ".agents/artifacts/reviews/evidence-staging" / ".." / ".." / ".." / ".." / "victim"
        self.assertEqual(self.advance(post, expected, token, staging=dotted), 3)
        self.assertTrue((victim / "unrelated.txt").exists())

    def test_advance_refuses_symlinked_canonical_staging(self):
        # a symlink planted at the canonical staging path must not redirect the
        # post-advance delete onto its target
        expected, post, _ = self.prospective_merge()
        token = self.hold_lock()
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / "unrelated.txt").write_text("do not delete\n")
        canonical = self.staging_path(post)
        shutil.rmtree(canonical, ignore_errors=True)  # merge pre-created the real dir
        canonical.parent.mkdir(parents=True, exist_ok=True)
        canonical.symlink_to(elsewhere)
        self.assertEqual(self.advance(post, expected, token), 3)
        self.assertTrue((elsewhere / "unrelated.txt").exists())  # target intact
        self.assertEqual(self.main_sha(), expected)

    def test_advance_marker_removal_failure_after_commit_point_exits_7_and_recovers(self):
        # inject a completion failure past the CAS: the staging parent becomes
        # read-only, so the merge-intent marker cannot be removed
        expected, post, _ = self.prospective_merge()
        staging_parent = self.staging_path(post).parent
        token = self.hold_lock()
        staging_parent.chmod(0o555)
        self.assertEqual(self.advance(post, expected, token), 7)
        self.assertEqual(self.main_sha(), post)          # commit point passed, no rollback
        self.assertTrue(self.staging_path(post).is_dir())   # durable marker preserved
        # repair the environment, then recover converges forward
        staging_parent.chmod(0o755)
        self.assertEqual(self.recover(token), 0)
        self.assertFalse(self.staging_path(post).exists())


if __name__ == "__main__":
    unittest.main()
