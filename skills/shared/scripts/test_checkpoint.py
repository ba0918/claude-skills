#!/usr/bin/env python3
"""Unit tests for checkpoint.py (rolling-checkpoint session-state restore).

Security enforcement (path containment / secret masking / strict parse /
execution ban) is proven here — the contract (checkpoint-pattern.md) states
these rules but this file is what makes them mechanically true.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import checkpoint  # noqa: E402
from checkpoint import (  # noqa: E402
    ParseError,
    compute_fingerprint,
    parse_porcelain,
    dirty_paths,
    parse_checkpoint,
    classify,
    build_skeleton,
    verdict_exit_code,
    check_containment,
    checkpoint_path,
    atomic_write,
    ContainmentError,
)


# --------------------------------------------------------------------------
# compute_fingerprint
# --------------------------------------------------------------------------
class TestComputeFingerprint(unittest.TestCase):
    def test_same_input_same_hash(self):
        pz = b"M  a.py\x00A  b.py\x00"
        h1 = compute_fingerprint(pz, "diff-a", {})
        h2 = compute_fingerprint(pz, "diff-a", {})
        self.assertEqual(h1, h2)
        self.assertTrue(h1.startswith("sha256:"))

    def test_entry_order_swap_same_hash(self):
        a = b"M  a.py\x00A  b.py\x00"
        b = b"A  b.py\x00M  a.py\x00"
        self.assertEqual(
            compute_fingerprint(a, "d", {}), compute_fingerprint(b, "d", {})
        )

    def test_checkpoints_dir_excluded(self):
        with_ckpt = b"M  a.py\x00M  docs/plans/checkpoints/20260708012132.md\x00"
        without = b"M  a.py\x00"
        self.assertEqual(
            compute_fingerprint(with_ckpt, "d", {}),
            compute_fingerprint(without, "d", {}),
        )

    def test_empty_porcelain_is_empty_dirty(self):
        # empty porcelain -> deterministic hash, distinct from a non-empty set
        empty = compute_fingerprint(b"", "", {})
        nonempty = compute_fingerprint(b"M  a.py\x00", "d", {})
        self.assertTrue(empty.startswith("sha256:"))
        self.assertNotEqual(empty, nonempty)

    def test_same_stat_different_diff_different_hash(self):
        # Identical porcelain (same stat) but different diff body must differ.
        pz = b"M  a.py\x00"
        h1 = compute_fingerprint(pz, "@@ -1 +1 @@\n-old\n+new", {})
        h2 = compute_fingerprint(pz, "@@ -1 +1 @@\n-old\n+other", {})
        self.assertNotEqual(h1, h2)

    def test_untracked_content_change_different_hash(self):
        pz = b"?? new.txt\x00"
        h1 = compute_fingerprint(pz, "", {"new.txt": "aaa"})
        h2 = compute_fingerprint(pz, "", {"new.txt": "bbb"})
        self.assertNotEqual(h1, h2)


# --------------------------------------------------------------------------
# porcelain=v1 -z parsing
# --------------------------------------------------------------------------
class TestParsePorcelain(unittest.TestCase):
    def test_rename_two_path_form(self):
        # -z rename: "R  new\0old\0"
        pz = b"R  new.py\x00old.py\x00"
        entries = parse_porcelain(pz)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["xy"], "R ")
        self.assertEqual(entries[0]["path"], "new.py")
        self.assertEqual(entries[0]["orig"], "old.py")

    def test_path_with_space_unicode_newline(self):
        # -z does not quote; spaces/unicode/newline are literal in the path bytes.
        pz = "M  a b/日本語\nx.py\x00".encode("utf-8")
        entries = parse_porcelain(pz)
        self.assertEqual(entries[0]["path"], "a b/日本語\nx.py")

    def test_untracked_and_deleted(self):
        pz = b"?? u.txt\x00 D gone.py\x00"
        paths = dirty_paths(parse_porcelain(pz))
        self.assertEqual(paths, ["gone.py", "u.txt"])

    def test_dirty_paths_excludes_checkpoints(self):
        pz = b"M  a.py\x00M  docs/plans/checkpoints/x.md\x00"
        self.assertEqual(dirty_paths(parse_porcelain(pz)), ["a.py"])


# --------------------------------------------------------------------------
# parse_checkpoint (strict)
# --------------------------------------------------------------------------
VALID_FM = """---
cycle_id: "20260708012132"
owner: manual-session
mode: normal
written_at: 2026-07-08T01:30:00+09:00
base_head: abc1234deadbeef
dirty_fingerprint: sha256:{fp}
dirty_files:
  - a.py
verify_on_restore:
  - cmd: python3
    args: ["-m", "unittest", "test_checkpoint.py"]
---
## decision
none

## evidence
Observed 01:25: python3 -m unittest exited 0

## next
finish step 3
""".format(fp="0" * 64)


class TestParseCheckpoint(unittest.TestCase):
    def test_valid_parses(self):
        meta = parse_checkpoint(VALID_FM, "20260708012132")
        self.assertEqual(meta.cycle_id, "20260708012132")
        self.assertEqual(meta.owner, "manual-session")
        self.assertEqual(meta.mode, "normal")
        self.assertEqual(meta.dirty_files, ["a.py"])
        self.assertEqual(meta.verify_on_restore[0]["cmd"], "python3")
        self.assertEqual(
            meta.verify_on_restore[0]["args"], ["-m", "unittest", "test_checkpoint.py"]
        )

    def test_missing_required_key(self):
        txt = VALID_FM.replace("base_head: abc1234deadbeef\n", "")
        with self.assertRaises(ParseError):
            parse_checkpoint(txt, "20260708012132")

    def test_duplicate_key(self):
        txt = VALID_FM.replace(
            "owner: manual-session\n", "owner: manual-session\nowner: precompact\n"
        )
        with self.assertRaises(ParseError):
            parse_checkpoint(txt, "20260708012132")

    def test_malformed_delimiter(self):
        txt = VALID_FM.replace("---\ncycle_id", "cycle_id")  # no opening delimiter
        with self.assertRaises(ParseError):
            parse_checkpoint(txt, "20260708012132")

    def test_unknown_owner(self):
        txt = VALID_FM.replace("owner: manual-session", "owner: attacker")
        with self.assertRaises(ParseError):
            parse_checkpoint(txt, "20260708012132")

    def test_owner_mode_mismatch(self):
        # precompact must pair with degraded; here it is paired with normal.
        txt = VALID_FM.replace("owner: manual-session", "owner: precompact")
        with self.assertRaises(ParseError):
            parse_checkpoint(txt, "20260708012132")

    def test_filename_cycle_id_mismatch(self):
        with self.assertRaises(ParseError):
            parse_checkpoint(VALID_FM, "20260101000000")

    def test_malformed_hash(self):
        txt = VALID_FM.replace("sha256:" + "0" * 64, "notahash")
        with self.assertRaises(ParseError):
            parse_checkpoint(txt, "20260708012132")

    def test_inline_empty_verify_list(self):
        txt = VALID_FM.replace(
            '  - cmd: python3\n    args: ["-m", "unittest", "test_checkpoint.py"]',
            "",
        ).replace("verify_on_restore:\n", "verify_on_restore: []\n")
        meta = parse_checkpoint(txt, "20260708012132")
        self.assertEqual(meta.verify_on_restore, [])

    def test_inline_empty_dirty_files_list(self):
        txt = VALID_FM.replace("dirty_files:\n  - a.py", "dirty_files: []")
        meta = parse_checkpoint(txt, "20260708012132")
        self.assertEqual(meta.dirty_files, [])

    def test_precompact_degraded_valid(self):
        txt = VALID_FM.replace("owner: manual-session", "owner: precompact").replace(
            "mode: normal", "mode: degraded"
        )
        meta = parse_checkpoint(txt, "20260708012132")
        self.assertEqual(meta.owner, "precompact")
        self.assertEqual(meta.mode, "degraded")


# --------------------------------------------------------------------------
# Security enforcement
# --------------------------------------------------------------------------
class TestSecurity(unittest.TestCase):
    def test_cycle_id_traversal_rejected(self):
        # cycle_id must be exactly [0-9]{14}; traversal strings are rejected.
        txt = VALID_FM.replace('"20260708012132"', '"../../etc/passwd"')
        with self.assertRaises(ParseError):
            parse_checkpoint(txt, "../../etc/passwd")

    def test_cycle_id_reserved_suffix_rejected_in_v1(self):
        # Reserved checkpoint_id grammar allows a -suffix, but v1 rejects it.
        txt = VALID_FM.replace('"20260708012132"', '"20260708012132-branch"')
        with self.assertRaises(ParseError):
            parse_checkpoint(txt, "20260708012132-branch")

    def test_yaml_tag_payload_inert_and_rejected(self):
        # A YAML tag payload must NOT be interpreted (no PyYAML) and must be
        # rejected by strict enum validation.
        txt = VALID_FM.replace(
            "owner: manual-session",
            "owner: !!python/object/apply:os.system ['echo pwned']",
        )
        with self.assertRaises(ParseError):
            parse_checkpoint(txt, "20260708012132")

    def test_verify_on_restore_freeform_shell_rejected(self):
        # Free-form shell string element (not {cmd, args}) must be a ParseError.
        txt = VALID_FM.replace(
            '  - cmd: python3\n    args: ["-m", "unittest", "test_checkpoint.py"]',
            '  - "python3 -m unittest && rm -rf /"',
        )
        with self.assertRaises(ParseError):
            parse_checkpoint(txt, "20260708012132")

    def test_build_skeleton_masks_secrets_in_paths(self):
        # A home path in a dirty file must be masked in the skeleton output.
        pz = "M  /home/alice/secret/a.py\x00".encode("utf-8")
        out = build_skeleton(
            pz, "abc1234", "sha256:" + "0" * 64, "manual-session",
            "20260708012132", "2026-07-08T01:30:00+09:00",
        )
        self.assertNotIn("/home/alice", out)
        self.assertIn("[REDACTED:home_path]", out)

    def test_containment_rejects_outside_path(self):
        with tempfile.TemporaryDirectory() as d:
            ckdir = os.path.join(d, "docs", "plans", "checkpoints")
            os.makedirs(ckdir)
            outside = os.path.join(d, "evil.md")
            with open(outside, "w") as f:
                f.write("x")
            with self.assertRaises(ContainmentError):
                check_containment(outside, ckdir)

    def test_containment_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            ckdir = os.path.join(d, "docs", "plans", "checkpoints")
            os.makedirs(ckdir)
            target = os.path.join(d, "target.md")
            with open(target, "w") as f:
                f.write("x")
            link = os.path.join(ckdir, "20260708012132.md")
            os.symlink(target, link)
            with self.assertRaises(ContainmentError):
                check_containment(link, ckdir)

    def test_containment_accepts_inside_path(self):
        with tempfile.TemporaryDirectory() as d:
            ckdir = os.path.join(d, "docs", "plans", "checkpoints")
            os.makedirs(ckdir)
            inside = os.path.join(ckdir, "20260708012132.md")
            with open(inside, "w") as f:
                f.write("x")
            self.assertEqual(check_containment(inside, ckdir), inside)

    def test_checkpoint_path_rejects_bad_cycle_id(self):
        with tempfile.TemporaryDirectory() as d:
            ckdir = os.path.join(d, "docs", "plans", "checkpoints")
            os.makedirs(ckdir)
            with self.assertRaises(ParseError):
                checkpoint_path(ckdir, "../evil")


# --------------------------------------------------------------------------
# classify — 5-verdict matrix + priority
# --------------------------------------------------------------------------
def _meta(owner="manual-session", mode="normal", base_head="headA",
          fp="sha256:" + "1" * 64, dirty_files=None):
    return checkpoint.CheckpointMeta(
        cycle_id="20260708012132",
        owner=owner,
        mode=mode,
        written_at="2026-07-08T01:30:00+09:00",
        base_head=base_head,
        dirty_fingerprint=fp,
        dirty_files=dirty_files or ["a.py"],
        verify_on_restore=[],
    )


class TestClassify(unittest.TestCase):
    def test_valid(self):
        m = _meta()
        v = classify(m, "headA", "sha256:" + "1" * 64)
        self.assertEqual(v.verdict, "valid")

    def test_stale_fingerprint_mismatch(self):
        m = _meta()
        v = classify(m, "headA", "sha256:" + "2" * 64)
        self.assertEqual(v.verdict, "stale")

    def test_superseded_head_moved(self):
        m = _meta(base_head="headOLD")
        v = classify(m, "headNEW", "sha256:" + "9" * 64)
        self.assertEqual(v.verdict, "superseded")

    def test_superseded_wins_over_fingerprint_mismatch(self):
        # HEAD moved AND fingerprint differs -> superseded (not stale).
        m = _meta(base_head="headOLD")
        v = classify(m, "headNEW", "sha256:" + "2" * 64)
        self.assertEqual(v.verdict, "superseded")

    def test_superseded_reports_dirty_overlap(self):
        m = _meta(base_head="headOLD", dirty_files=["a.py", "b.py"])
        v = classify(m, "headNEW", "sha256:" + "2" * 64,
                     current_dirty_files=["b.py", "c.py"])
        self.assertEqual(v.verdict, "superseded")
        self.assertEqual(v.dirty_overlap, ["b.py"])

    def test_degraded_precompact_head_match(self):
        m = _meta(owner="precompact", mode="degraded")
        v = classify(m, "headA", "sha256:" + "1" * 64)
        self.assertEqual(v.verdict, "degraded")

    def test_conflict_marker_beats_degraded(self):
        m = _meta(owner="precompact", mode="degraded")
        v = classify(m, "headA", "sha256:" + "1" * 64, conflict_marker=True)
        self.assertEqual(v.verdict, "conflict")

    def test_superseded_beats_conflict_marker(self):
        m = _meta(base_head="headOLD")
        v = classify(m, "headNEW", "sha256:" + "1" * 64, conflict_marker=True)
        self.assertEqual(v.verdict, "superseded")

    def test_empty_porcelain_head_match_stale(self):
        # current dirty set empty (worktree cleaned differently) but fingerprint
        # differs from the recorded one -> stale.
        m = _meta()
        v = classify(m, "headA", compute_fingerprint(b"", "", {}))
        self.assertEqual(v.verdict, "stale")


# --------------------------------------------------------------------------
# build_skeleton
# --------------------------------------------------------------------------
class TestBuildSkeleton(unittest.TestCase):
    def test_manual_session_skeleton(self):
        pz = b"M  a.py\x00A  b.py\x00"
        out = build_skeleton(
            pz, "abc1234", "sha256:" + "0" * 64, "manual-session",
            "20260708012132", "2026-07-08T01:30:00+09:00",
        )
        self.assertIn("owner: manual-session", out)
        self.assertIn("mode: normal", out)
        self.assertIn("- a.py", out)
        self.assertIn("- b.py", out)
        self.assertIn("## decision", out)
        self.assertIn("## evidence", out)
        self.assertIn("## next", out)
        # round-trips through the strict parser
        parse_checkpoint(out, "20260708012132")

    def test_degraded_skeleton_markers(self):
        pz = b"M  a.py\x00"
        out = build_skeleton(
            pz, "abc1234", "sha256:" + "0" * 64, "precompact",
            "20260708012132", "2026-07-08T01:30:00+09:00",
        )
        self.assertIn("mode: degraded", out)
        self.assertIn("unknown", out)
        self.assertIn("reconstruct_from_diff", out)

    def test_skeleton_excludes_checkpoints_dir(self):
        pz = b"M  a.py\x00M  docs/plans/checkpoints/20260708012132.md\x00"
        out = build_skeleton(
            pz, "abc1234", "sha256:" + "0" * 64, "manual-session",
            "20260708012132", "2026-07-08T01:30:00+09:00",
        )
        self.assertIn("- a.py", out)
        self.assertNotIn("checkpoints/20260708012132.md", out)

    def test_skeleton_empty_verify_roundtrips_to_empty_list(self):
        pz = b"M  a.py\x00"
        out = build_skeleton(
            pz, "abc1234", "sha256:" + "0" * 64, "manual-session",
            "20260708012132", "2026-07-08T01:30:00+09:00",
        )
        meta = parse_checkpoint(out, "20260708012132")
        self.assertEqual(meta.verify_on_restore, [])

    def test_atomic_write_creates_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sub", "dir", "out.md")
            atomic_write(path, "hello")
            with open(path) as f:
                self.assertEqual(f.read(), "hello")
            atomic_write(path, "world")
            with open(path) as f:
                self.assertEqual(f.read(), "world")


# --------------------------------------------------------------------------
# CLI exit codes
# --------------------------------------------------------------------------
class TestExitCodes(unittest.TestCase):
    def test_distinct_codes_per_verdict(self):
        codes = {
            v: verdict_exit_code(v)
            for v in ("valid", "stale", "superseded", "degraded", "conflict")
        }
        self.assertEqual(codes["valid"], 0)
        # every verdict maps to a distinct code
        self.assertEqual(len(set(codes.values())), len(codes))

    def test_unknown_verdict_raises(self):
        with self.assertRaises(ValueError):
            verdict_exit_code("bogus")


if __name__ == "__main__":
    unittest.main()
