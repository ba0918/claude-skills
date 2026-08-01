#!/usr/bin/env python3
"""publication-protocol.md の git 機構を実リポジトリで実行検証する回帰テスト。

プロトコル本文は自然言語であり、test_step4_skill_integration.py の文言・順序
アサーションだけでは「コマンド列が実際に不変条件を満たすか」を検証できない。
ここでは本文が規定するコマンド列そのものを使い捨て git リポジトリに対して実行し、
機械的な不変条件を実測で固定する:

- happy path: prospective merge は main を動かさず、CAS → sync → promotion
  （copy → checker 検証 → staging 削除）の後に ref・checkout・evidence singleton
  の三者が新 main に揃う。checker は本物の evidence_check.py を実行する
- CAS 競合: main が動いていたら update-ref が拒否し、main と公開済み evidence と
  staging のすべてが無傷で残る。stale を破棄して新 main から再作成すると 2 回目の
  CAS は成功する（retry 経路）
- commit point 後の中断: プロセス内変数を捨て、ディスク上の durable marker
  （staging dir の SHA = main HEAD）だけから中断を検出し、reset + promotion の
  再実行で収束する。promotion が 1 レコードだけ複製した時点の crash からも収束する
- staging 隔離: prospective evidence は promotion まで default evidence dir に
  一切触れない
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CHECKER = ROOT / "skills/shared/scripts/evidence_check.py"
CONTRACT = ROOT / "skills/shared/references/quality-gate-contract.md"
STATES = ("machine_verified", "semantic_reviewed")


def git(cwd, *args, check=True):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=check,
    )


def run_checker(repo_root, evidence_dir, target_sha):
    return subprocess.run(
        [
            sys.executable, str(CHECKER),
            "--target-sha", target_sha,
            "--contract", str(CONTRACT),
            "--repo-root", str(repo_root),
            "--evidence-dir", str(evidence_dir),
        ],
        capture_output=True, text=True,
    ).returncode


class PublicationProtocolGitTests(unittest.TestCase):
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

    # -- protocol steps as written ------------------------------------------

    def prospective_merge(self, suffix=""):
        """Step 1: detached temp worktree + merge --no-ff; main untouched."""
        expected = git(self.main, "rev-parse", "main").stdout.strip()
        tmp = self.root / f"tmp-merge{suffix}"
        git(self.main, "worktree", "add", "--detach", "-q", str(tmp), expected)
        git(tmp, "merge", "--no-ff", "-q", "-m", "merge satellite", "satellite")
        post = git(tmp, "rev-parse", "HEAD").stdout.strip()
        return expected, post, tmp

    def record(self, state, sha):
        return json.dumps({
            "schema_version": 1,
            "state": state,
            "contract": "quality-gate-contract",
            "target_sha": sha,
            "contract_version": "1.0.0",
            "profile": None,
            "grounds": "test run of the publication protocol command sequence",
        })

    def stage_evidence(self, post):
        """Step 2: schema-valid records in the run-scoped staging directory."""
        staging = self.main / f".agents/artifacts/reviews/evidence-staging/{post}"
        staging.mkdir(parents=True)
        for state in STATES:
            (staging / f"{state}.json").write_text(self.record(state, post))
        return staging

    def publish_old_evidence(self, sha):
        self.default_dir.mkdir(parents=True)
        for state in STATES:
            (self.default_dir / f"{state}.json").write_text(self.record(state, sha))

    def promote(self, staging, post):
        """Exit 0 step 5: copy -> verify with the real checker -> delete staging."""
        for src in staging.glob("*.json"):
            shutil.copyfile(src, self.default_dir / src.name)
        if run_checker(self.main, self.default_dir, post) == 0:
            shutil.rmtree(staging)
            return True
        return False

    def published_sha(self):
        return json.loads(
            (self.default_dir / "machine_verified.json").read_text()
        )["target_sha"]

    # -- tests ---------------------------------------------------------------

    def test_happy_path_checker_cas_sync_and_promotion(self):
        expected, post, _ = self.prospective_merge()
        self.assertEqual(git(self.main, "rev-parse", "main").stdout.strip(), expected)
        self.publish_old_evidence(expected)
        staging = self.stage_evidence(post)
        # Step 3: the real checker accepts the staged records for the prospective SHA
        self.assertEqual(run_checker(self.main, staging, post), 0)
        # staging isolation: the singleton still describes the old main
        self.assertEqual(self.published_sha(), expected)
        # Exit 0: locate/clean check -> CAS -> sync -> promotion
        self.assertEqual(git(self.main, "status", "--porcelain").stdout, "")
        git(self.main, "update-ref", "refs/heads/main", post, expected)
        git(self.main, "reset", "-q", "--hard", "refs/heads/main")
        self.assertTrue(self.promote(staging, post))
        self.assertEqual(git(self.main, "rev-parse", "main").stdout.strip(), post)
        self.assertTrue((self.main / "b.txt").exists())
        self.assertEqual(self.published_sha(), post)
        self.assertFalse(staging.exists())
        self.assertEqual(run_checker(self.main, self.default_dir, post), 0)

    def test_cas_conflict_preserves_everything_then_retry_succeeds(self):
        expected, post, tmp = self.prospective_merge()
        self.publish_old_evidence(expected)
        staging = self.stage_evidence(post)
        # main moves concurrently before the CAS
        (self.main / "c.txt").write_text("concurrent\n")
        git(self.main, "add", ".")
        git(self.main, "commit", "-qm", "concurrent")
        moved = git(self.main, "rev-parse", "main").stdout.strip()
        result = git(
            self.main, "update-ref", "refs/heads/main", post, expected, check=False
        )
        self.assertNotEqual(result.returncode, 0)
        # main, published evidence, and staging are all untouched
        self.assertEqual(git(self.main, "rev-parse", "main").stdout.strip(), moved)
        self.assertEqual(self.published_sha(), expected)
        self.assertTrue((staging / "machine_verified.json").exists())
        # the old evidence is now stale for the moved main — checker refuses it
        self.assertNotEqual(run_checker(self.main, self.default_dir, moved), 0)
        # CAS retry: discard the stale prospective merge + staging, redo Steps 1-2
        git(self.main, "worktree", "remove", "--force", str(tmp))
        shutil.rmtree(staging)
        expected2, post2, _ = self.prospective_merge(suffix="-retry")
        self.assertEqual(expected2, moved)
        staging2 = self.stage_evidence(post2)
        self.assertEqual(run_checker(self.main, staging2, post2), 0)
        git(self.main, "update-ref", "refs/heads/main", post2, expected2)
        git(self.main, "reset", "-q", "--hard", "refs/heads/main")
        self.assertTrue(self.promote(staging2, post2))
        self.assertEqual(git(self.main, "rev-parse", "main").stdout.strip(), post2)

    def test_restart_recovery_from_durable_marker_alone(self):
        expected, post, _ = self.prospective_merge()
        self.publish_old_evidence(expected)
        self.stage_evidence(post)
        git(self.main, "update-ref", "refs/heads/main", post, expected)
        # crash: ref advanced, checkout stale, promotion never started.
        # A fresh process derives everything from disk: main HEAD + staging dirs.
        del expected, post
        head = git(self.main, "rev-parse", "main").stdout.strip()
        staging_root = self.main / ".agents/artifacts/reviews/evidence-staging"
        markers = [d for d in staging_root.iterdir() if d.name == head]
        self.assertEqual(len(markers), 1, "durable marker must identify the interruption")
        staging = markers[0]
        # resume completion steps: reset (idempotent), then promotion
        git(self.main, "reset", "-q", "--hard", "refs/heads/main")
        git(self.main, "reset", "-q", "--hard", "refs/heads/main")
        self.assertTrue((self.main / "b.txt").exists())
        self.assertTrue(self.promote(staging, head))
        self.assertEqual(self.published_sha(), head)
        self.assertFalse(staging.exists())

    def test_promotion_interrupted_mid_copy_converges_on_rerun(self):
        expected, post, _ = self.prospective_merge()
        self.publish_old_evidence(expected)
        staging = self.stage_evidence(post)
        git(self.main, "update-ref", "refs/heads/main", post, expected)
        git(self.main, "reset", "-q", "--hard", "refs/heads/main")
        # crash after copying only ONE of the two records: singleton is mixed
        shutil.copyfile(
            staging / "machine_verified.json",
            self.default_dir / "machine_verified.json",
        )
        mixed_semantic = json.loads(
            (self.default_dir / "semantic_reviewed.json").read_text()
        )["target_sha"]
        self.assertNotEqual(mixed_semantic, post)  # the mixed state is real
        # the checker refuses the mixed singleton, so staging was NOT deleted
        self.assertNotEqual(run_checker(self.main, self.default_dir, post), 0)
        self.assertTrue((staging / "semantic_reviewed.json").exists())
        # re-running the promotion from the intact staging set converges
        self.assertTrue(self.promote(staging, post))
        self.assertEqual(self.published_sha(), post)
        self.assertEqual(run_checker(self.main, self.default_dir, post), 0)
        self.assertFalse(staging.exists())


if __name__ == "__main__":
    unittest.main()
