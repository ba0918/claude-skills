#!/usr/bin/env python3
"""publication-protocol.md の破壊的遷移を、正本プリミティブ経由で実行検証する回帰テスト。

surrogate 実装をテストしても本文とテストがドリトするだけなので、ここでは
cycle / iterate が実行するのと同じ publication_advance.py（advance / recover）を
使い捨て git リポジトリに対して起動し、機械的な不変条件を実測で固定する:

- happy path: prospective merge は main を動かさず、advance が checker 検証 →
  CAS → sync → promotion（copy → checker → staging 削除）を単一実装で完了する
- 前提条件: dirty tree / 別 worktree に checkout された main は CAS 前に
  terminal failure（exit 3）で止まり、main は無傷
- CAS 競合: exit 4 で main・公開 evidence・staging すべて無傷。stale を破棄して
  新 main から再作成すると retry が成功する
- crash 修復: durable marker（staging dir の SHA = main HEAD）だけから復旧し、
  phantom 状態の証明が成立するときのみ reset する。crash 後の本物のユーザー編集や
  untracked 衝突があるときは exit 6 で何も破壊しない。promotion 途中の crash からも
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
CONTRACT = ROOT / "skills/shared/references/quality-gate-contract.md"
STATES = ("machine_verified", "semantic_reviewed")


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
        self.default_dir = self.main / ".agents/artifacts/reviews/evidence"

    # -- protocol steps / primitive invocation --------------------------------

    def merge_cmd(self, suffix=""):
        return subprocess.run(
            [
                sys.executable, str(PRIMITIVE), "merge",
                "--repo-root", str(self.main),
                "--satellite-branch", "satellite",
                "--tmp-merge-root", str(self.root / f"tmp-merge{suffix}"),
                "--contract", str(CONTRACT),
            ],
            capture_output=True, text=True,
        )

    def prospective_merge(self, suffix=""):
        """Step 1 via the primitive: detached temp worktree + merge --no-ff."""
        result = self.merge_cmd(suffix)
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        return out["expected_main_sha"], out["post_merge_sha"], Path(out["tmp_merge_root"])

    def record(self, state, sha):
        return json.dumps({
            "schema_version": 1,
            "state": state,
            "contract": "quality-gate-contract",
            "target_sha": sha,
            "contract_version": "1.0.0",
            "profile": None,
            "grounds": "test run of the publication primitive",
        })

    def stage_evidence(self, post):
        staging = self.main / f".agents/artifacts/reviews/evidence-staging/{post}"
        staging.mkdir(parents=True, exist_ok=True)
        for state in STATES:
            (staging / f"{state}.json").write_text(self.record(state, post))
        return staging

    def publish_old_evidence(self, sha):
        self.default_dir.mkdir(parents=True)
        for state in STATES:
            (self.default_dir / f"{state}.json").write_text(self.record(state, sha))

    def hold_lock(self):
        """workspace lock の claim を作り、holder 証明用の token を返す。"""
        claim = self.main / ".agents/runtime/workspace.claim"
        claim.parent.mkdir(parents=True, exist_ok=True)
        token = "test-lock-token"
        claim.write_text(json.dumps({"token": token, "pid": 1, "skill": "test"}))
        return token

    def advance(self, post, expected, token=None):
        cmd = [
            sys.executable, str(PRIMITIVE), "advance",
            "--repo-root", str(self.main),
            "--post-merge-sha", post,
            "--expected-main-sha", expected,
            "--contract", str(CONTRACT),
        ]
        if token:
            cmd += ["--lock-token", token]
        return subprocess.run(cmd, capture_output=True, text=True).returncode

    def recover(self, token=None):
        cmd = [
            sys.executable, str(PRIMITIVE), "recover",
            "--repo-root", str(self.main),
            "--contract", str(CONTRACT),
        ]
        if token:
            cmd += ["--lock-token", token]
        return subprocess.run(cmd, capture_output=True, text=True).returncode

    def published_sha(self):
        return json.loads(
            (self.default_dir / "machine_verified.json").read_text()
        )["target_sha"]

    def main_sha(self):
        return git(self.main, "rev-parse", "main").stdout.strip()

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

    # -- advance ---------------------------------------------------------------

    def test_advance_happy_path_syncs_and_promotes(self):
        expected, post, _ = self.prospective_merge()
        self.assertEqual(self.main_sha(), expected)  # Step 1 must not advance main
        self.publish_old_evidence(expected)
        staging = self.stage_evidence(post)
        self.assertEqual(self.published_sha(), expected)  # staging isolation
        token = self.hold_lock()
        self.assertEqual(self.advance(post, expected, token), 0)
        self.assertEqual(self.main_sha(), post)
        self.assertTrue((self.main / "b.txt").exists())  # checkout synchronized
        self.assertEqual(self.published_sha(), post)     # evidence promoted
        self.assertFalse(staging.exists())               # marker cleared

    def test_advance_refuses_checked_out_main_without_lock_proof(self):
        # the lock requirement is enforced in code, not prose: a checked-out
        # main with no matching claim token stops before the CAS
        expected, post, _ = self.prospective_merge()
        self.stage_evidence(post)
        self.assertEqual(self.advance(post, expected), 3)      # no token at all
        self.hold_lock()
        self.assertEqual(self.advance(post, expected, "wrong-token"), 3)
        self.assertEqual(self.main_sha(), expected)            # ref never moved

    def test_advance_refuses_dirty_main_tree(self):
        expected, post, _ = self.prospective_merge()
        self.stage_evidence(post)
        (self.main / "a.txt").write_text("local edit\n")
        self.assertEqual(self.advance(post, expected, self.hold_lock()), 3)
        self.assertEqual(self.main_sha(), expected)  # main untouched
        self.assertEqual((self.main / "a.txt").read_text(), "local edit\n")

    def test_advance_refuses_main_checked_out_in_foreign_worktree(self):
        expected, post, _ = self.prospective_merge()
        self.stage_evidence(post)
        # move the main checkout to a foreign worktree: repo-root switches away
        git(self.main, "checkout", "-q", "-b", "work")
        foreign = self.root / "foreign-main"
        git(self.main, "worktree", "add", "-q", str(foreign), "main")
        self.assertEqual(self.advance(post, expected), 3)
        self.assertEqual(self.main_sha(), expected)  # ref untouched
        self.assertFalse((foreign / "b.txt").exists())  # foreign checkout untouched

    def test_advance_cas_conflict_preserves_all_then_retry_succeeds(self):
        expected, post, tmp = self.prospective_merge()
        self.publish_old_evidence(expected)
        staging = self.stage_evidence(post)
        (self.main / "c.txt").write_text("concurrent\n")
        git(self.main, "add", ".")
        git(self.main, "commit", "-qm", "concurrent")
        moved = self.main_sha()
        token = self.hold_lock()
        self.assertEqual(self.advance(post, expected, token), 4)
        self.assertEqual(self.main_sha(), moved)             # main untouched
        self.assertEqual(self.published_sha(), expected)     # singleton untouched
        self.assertTrue((staging / "machine_verified.json").exists())
        # CAS retry rule: discard the protocol's own intermediates, redo Steps 1-2
        git(self.main, "worktree", "remove", "--force", str(tmp))
        shutil.rmtree(staging)
        expected2, post2, _ = self.prospective_merge(suffix="-retry")
        self.assertEqual(expected2, moved)
        self.stage_evidence(post2)
        self.assertEqual(self.advance(post2, expected2, token), 0)
        self.assertEqual(self.main_sha(), post2)
        self.assertEqual(self.published_sha(), post2)

    # -- recover ---------------------------------------------------------------

    def crash_after_cas(self):
        """CAS 直後の crash 状態を作る: ref は前進、checkout は旧 tree のまま。"""
        expected, post, _ = self.prospective_merge()
        self.publish_old_evidence(expected)
        self.stage_evidence(post)
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
        self.assertEqual(self.published_sha(), post)
        self.assertFalse(
            (self.main / f".agents/artifacts/reviews/evidence-staging/{post}").exists()
        )
        self.assertEqual(self.recover(), 5)  # second run: nothing left to repair

    def test_recover_refuses_real_edits_after_crash(self):
        expected, post = self.crash_after_cas()
        (self.main / "a.txt").write_text("post-crash human edit\n")
        self.assertEqual(self.recover(), 6)
        # nothing destroyed: the edit survives, evidence still describes old main
        self.assertEqual((self.main / "a.txt").read_text(), "post-crash human edit\n")
        self.assertEqual(self.published_sha(), expected)

    def test_recover_refuses_untracked_collision_with_merged_tree(self):
        expected, post = self.crash_after_cas()
        (self.main / "b.txt").write_text("unrelated local file\n")  # merge adds b.txt
        self.assertEqual(self.recover(), 6)
        self.assertEqual((self.main / "b.txt").read_text(), "unrelated local file\n")
        self.assertEqual(self.published_sha(), expected)

    def test_recover_with_other_branch_checked_out_promotes_without_reset(self):
        # git reset --hard moves whichever branch is checked out; recovery must
        # not run it when main is not the checked-out branch, or it would force
        # that branch's ref onto main's SHA
        _, post = self.crash_after_cas()
        git(self.main, "switch", "-q", "-c", "hotfix")
        hotfix_before = git(self.main, "rev-parse", "hotfix").stdout.strip()
        self.assertEqual(self.recover(), 0)
        self.assertEqual(
            git(self.main, "rev-parse", "hotfix").stdout.strip(), hotfix_before
        )
        self.assertEqual(self.main_sha(), post)      # main ref stays advanced
        self.assertFalse((self.main / "b.txt").exists())  # no reset ran
        self.assertEqual(self.published_sha(), post)      # promotion still done

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
        self.publish_old_evidence(expected)
        self.stage_evidence(post)
        token = self.hold_lock()
        git(self.main, "update-ref", "refs/heads/main", post, expected)
        (self.main / "user notes.txt").write_text("local unrelated\n")
        self.assertEqual(self.recover(token), 6)
        self.assertEqual(
            (self.main / "user notes.txt").read_text(), "local unrelated\n"
        )

    def test_recover_converges_after_promotion_interrupted_mid_copy(self):
        _, post = self.crash_after_cas()
        git(self.main, "reset", "-q", "--hard", "refs/heads/main")
        staging = self.main / f".agents/artifacts/reviews/evidence-staging/{post}"
        # crash after copying only ONE record: singleton is mixed old/new
        shutil.copyfile(
            staging / "machine_verified.json",
            self.default_dir / "machine_verified.json",
        )
        self.assertNotEqual(
            json.loads((self.default_dir / "semantic_reviewed.json").read_text())["target_sha"],
            post,
        )
        self.assertEqual(self.recover(), 0)  # rerun converges from intact staging
        self.assertEqual(self.published_sha(), post)
        self.assertFalse(staging.exists())


if __name__ == "__main__":
    unittest.main()
