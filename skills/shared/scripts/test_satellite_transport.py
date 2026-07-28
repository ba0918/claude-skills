import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))
from satellite_transport import (  # noqa: E402
    ABSENT,
    TransportError,
    authorize_write,
    canonical_json,
    classify_three_way,
    collect,
    create_ingress_manifest,
    create_run,
    discard_staging,
    durable_write,
    format_diagnostic,
    lifecycle_transition,
    publish,
    reconcile_owner,
    recovery_report,
    revoke_capability,
    rotate_capability,
    sweep_store,
    cleanup_allowed,
    transition_cleanup_allowed,
)


class SatelliteTransportTest(unittest.TestCase):
    def roots(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        main = base / "main"
        worktree = base / "worktree"
        (main / ".agents/artifacts/plans").mkdir(parents=True)
        subprocess = __import__("subprocess")
        subprocess.run(["git", "init", "-q"], cwd=main, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=main, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=main, check=True)
        (main / "tracked").write_text("x")
        subprocess.run(["git", "add", "tracked"], cwd=main, check=True)
        subprocess.run(["git", "commit", "-qm", "initial"], cwd=main, check=True)
        subprocess.run(["git", "worktree", "add", "-q", str(worktree)], cwd=main, check=True)
        (worktree / ".agents/artifacts/plans").mkdir(parents=True)
        return main, worktree

    def active_run(self):
        main, worktree = self.roots()
        plan = Path("plans/p.md")
        (main / ".agents/artifacts" / plan).write_bytes(b"base")
        record = create_run(main, worktree, "run-1", plan)
        lifecycle_transition(record.runtime_dir, "created", 0, "active")
        return main, worktree, record

    def test_canonical_manifest_is_sorted_and_digest_bound(self):
        main, _, _ = self.active_run()
        root = main / ".agents/artifacts"
        (root / "issues").mkdir()
        (root / "issues/z.md").write_bytes(b"z")
        manifest, digest = create_ingress_manifest(root, "run-1", ["issues/z.md", "plans/p.md"])
        self.assertEqual(["issues/z.md", "plans/p.md"], [e["relative_path"] for e in manifest["entries"]])
        self.assertEqual(hashlib.sha256(canonical_json(manifest)).hexdigest(), digest)

    def test_capability_is_random_mode_0600_and_only_digest_is_authoritative(self):
        _, _, record = self.active_run()
        self.assertGreaterEqual(len(record.capability), 32)
        self.assertEqual(0o600, record.capability_path.stat().st_mode & 0o777)
        provenance = json.loads((record.runtime_dir / "provenance.json").read_text())
        self.assertNotIn(record.capability, json.dumps(provenance))
        self.assertEqual(hashlib.sha256(record.capability.encode()).hexdigest(),
                         provenance["capability_digest"])

    def test_duplicate_run_id_fails_before_mutating_satellite(self):
        main, worktree, record = self.active_run()
        plan = worktree / ".agents/artifacts/plans/p.md"
        plan.write_bytes(b"delegate work")
        with self.assertRaises(FileExistsError):
            create_run(main, worktree, "run-1", "plans/p.md")
        self.assertEqual(b"delegate work", plan.read_bytes())
        self.assertEqual(record.capability, record.capability_path.read_text())

    def test_authorization_requires_active_live_matching_capability_and_path(self):
        _, _, record = self.active_run()
        authorize_write(record.runtime_dir, record.capability, "plans/p.md")
        for capability, path in (("wrong", "plans/p.md"), (record.capability, "status.md"),
                                 (record.capability, ".runtime/x")):
            with self.subTest(capability=capability, path=path), self.assertRaises(TransportError):
                authorize_write(record.runtime_dir, capability, path)
        lifecycle_transition(record.runtime_dir, "active", 1, "harvesting",
                             capability=record.capability, consume=True, expected_epoch=1)
        with self.assertRaises(TransportError):
            authorize_write(record.runtime_dir, record.capability, "plans/p.md")

    def test_durable_write_commits_only_when_locked_authorization_succeeds(self):
        _, worktree, record = self.active_run()
        destination = worktree / ".agents/artifacts/plans/p.md"
        durable_write(record.runtime_dir, record.capability, "plans/p.md", b"updated")
        self.assertEqual(b"updated", destination.read_bytes())
        with self.assertRaises(TransportError):
            durable_write(record.runtime_dir, "wrong", "plans/p.md", b"forbidden")
        self.assertEqual(b"updated", destination.read_bytes())

    def test_denial_diagnostic_has_closed_shape_and_never_capability(self):
        _, _, record = self.active_run()
        text = format_diagnostic("SATELLITE_WRITE_DENIED", record.runtime_dir, "denied")
        self.assertEqual(6, len(text.splitlines()))
        self.assertIn("run_id=run-1", text)
        self.assertIn("recovery_command=/claude-skills:artifacts recover --run-id run-1", text)
        self.assertNotIn(record.capability, text)

    def test_three_way_classifier_covers_absence_and_hash_cases(self):
        cases = [
            (ABSENT, "m", "s", "recreation"),
            ("b", ABSENT, "b", "deletion"),
            ("b", "b", ABSENT, "deletion"),
            ("b", "b", "b", "unchanged"),
            ("b", "b", "s", "satellite_only_change"),
            ("b", "m", "b", "main_only_change"),
            ("b", "x", "x", "identical_concurrent_change"),
            ("b", "m", "s", "conflict"),
        ]
        for base, main, satellite, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(expected, classify_three_way(base, main, satellite))

    def test_sweep_is_whole_store_and_rejects_excluded_or_unsafe_entries(self):
        _, worktree, _ = self.active_run()
        store = worktree / ".agents/artifacts"
        (store / "future-kind").mkdir()
        (store / "future-kind/item.md").write_text("ok", encoding="utf-8")
        self.assertIn("future-kind/item.md", sweep_store(store))
        for relative in ("status.md", "session-history.md"):
            path = store / relative
            path.write_text("excluded", encoding="utf-8")
            self.assertNotIn(relative, sweep_store(store))
            path.unlink()
        for relative in (".secret", "plans/.tmp"):
            path = store / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("bad", encoding="utf-8")
            with self.subTest(relative=relative), self.assertRaises(TransportError):
                sweep_store(store)
            path.unlink()
        target = store / "plans/link"
        target.symlink_to(store / "plans/p.md")
        with self.assertRaises(TransportError):
            sweep_store(store)

    def test_collect_rejects_raw_capability_and_preserves_for_recovery(self):
        _, worktree, record = self.active_run()
        leaked = worktree / ".agents/artifacts/issues/leak.md"
        leaked.parent.mkdir(parents=True)
        leaked.write_text(f"secret={record.capability}", encoding="utf-8")
        lifecycle_transition(record.runtime_dir, "active", 1, "harvesting",
                             capability=record.capability, consume=True, expected_epoch=1)
        with self.assertRaisesRegex(TransportError, "capability"):
            collect(record.runtime_dir, expected_version=2, raw_capability=record.capability)
        provenance = json.loads((record.runtime_dir / "provenance.json").read_text())
        self.assertEqual("recovery_required", provenance["lifecycle_state"])

    def test_collect_rejects_wrong_capability_before_scanning_store(self):
        _, _, record = self.active_run()
        lifecycle_transition(record.runtime_dir, "active", 1, "harvesting",
                             capability=record.capability, consume=True, expected_epoch=1)
        with mock.patch("satellite_transport.sweep_store") as sweep:
            with self.assertRaisesRegex(TransportError, "capability mismatch"):
                collect(record.runtime_dir, expected_version=2, raw_capability="wrong")
            sweep.assert_not_called()

    def test_collect_is_immutable_and_publish_uses_destination_cas(self):
        main, worktree, record = self.active_run()
        satellite_plan = worktree / ".agents/artifacts/plans/p.md"
        satellite_plan.write_bytes(b"satellite")
        lifecycle_transition(record.runtime_dir, "active", 1, "harvesting",
                             capability=record.capability, consume=True, expected_epoch=1)
        result = collect(
            record.runtime_dir, expected_version=2, raw_capability=record.capability,
        )
        self.assertEqual("staged", result["state"])
        self.assertEqual(b"base", (main / ".agents/artifacts/plans/p.md").read_bytes())
        staged = record.runtime_dir / "staging/files/plans/p.md"
        self.assertEqual(b"satellite", staged.read_bytes())
        (main / ".agents/artifacts/plans/p.md").write_bytes(b"raced")
        with self.assertRaisesRegex(TransportError, "destination"):
            publish(record.runtime_dir, expected_version=3)
        self.assertEqual(b"raced", (main / ".agents/artifacts/plans/p.md").read_bytes())

    def test_publish_is_atomic_preflight_and_idempotent(self):
        main, worktree, record = self.active_run()
        (worktree / ".agents/artifacts/plans/p.md").write_bytes(b"satellite")
        lifecycle_transition(record.runtime_dir, "active", 1, "harvesting",
                             capability=record.capability, consume=True, expected_epoch=1)
        collect(record.runtime_dir, expected_version=2, raw_capability=record.capability)
        publish(record.runtime_dir, expected_version=3)
        self.assertEqual(b"satellite", (main / ".agents/artifacts/plans/p.md").read_bytes())
        self.assertEqual("published", json.loads(
            (record.runtime_dir / "provenance.json").read_text())["lifecycle_state"])
        with self.assertRaises(TransportError):
            publish(record.runtime_dir, expected_version=3)

    def test_conflicted_collect_enters_recovery_and_preserves_inventory(self):
        main, worktree, record = self.active_run()
        (main / ".agents/artifacts/plans/p.md").write_bytes(b"main")
        (worktree / ".agents/artifacts/plans/p.md").write_bytes(b"satellite")
        lifecycle_transition(record.runtime_dir, "active", 1, "harvesting",
                             capability=record.capability, consume=True, expected_epoch=1)
        with self.assertRaisesRegex(TransportError, "conflict"):
            collect(record.runtime_dir, expected_version=2, raw_capability=record.capability)
        provenance = json.loads((record.runtime_dir / "provenance.json").read_text())
        self.assertEqual("recovery_required", provenance["lifecycle_state"])
        evidence = json.loads((record.runtime_dir / "discard-evidence.json").read_text())
        self.assertIsNone(evidence["staging_manifest_digest"])
        self.assertTrue(evidence["partial_staging_inventory"])

    def test_discard_requires_validated_staging_and_binds_evidence(self):
        _, worktree, record = self.active_run()
        (worktree / ".agents/artifacts/plans/p.md").write_bytes(b"satellite")
        with self.assertRaises(TransportError):
            discard_staging(record.runtime_dir, 1, actor="human", reason_code="REJECTED")
        lifecycle_transition(record.runtime_dir, "active", 1, "harvesting",
                             capability=record.capability, consume=True, expected_epoch=1)
        collect(record.runtime_dir, expected_version=2, raw_capability=record.capability)
        result = discard_staging(
            record.runtime_dir, 3, actor="human", reason_code="REJECTED",
        )
        self.assertEqual("discarded", result["lifecycle_state"])
        evidence = json.loads((record.runtime_dir / "discard-evidence.json").read_text())
        self.assertEqual(4, evidence["lifecycle_version"])
        self.assertIsNone(evidence["partial_staging_inventory"])

    def test_lifecycle_cas_rejects_stale_and_illegal_transitions(self):
        _, _, record = self.active_run()
        with self.assertRaises(TransportError):
            lifecycle_transition(record.runtime_dir, "active", 0, "harvesting")
        with self.assertRaises(TransportError):
            lifecycle_transition(record.runtime_dir, "active", 1, "published")
        provenance = json.loads((record.runtime_dir / "provenance.json").read_text())
        self.assertEqual(("active", 1),
                         (provenance["lifecycle_state"], provenance["lifecycle_version"]))

    def test_revoke_rotate_and_dead_owner_reconciliation(self):
        _, _, record = self.active_run()
        revoke_capability(record.runtime_dir, 1)
        with self.assertRaises(TransportError):
            authorize_write(record.runtime_dir, record.capability, "plans/p.md")
        provenance_path = record.runtime_dir / "provenance.json"
        provenance = json.loads(provenance_path.read_text())
        provenance["owner_pid"] = 99999999
        provenance_path.write_bytes(canonical_json(provenance))
        result = reconcile_owner(record.runtime_dir)
        provenance = json.loads(provenance_path.read_text())
        provenance["lifecycle_state"] = "failed_readonly"
        provenance_path.write_bytes(canonical_json(provenance))
        new_capability = rotate_capability(
            record.runtime_dir, expected_epoch=1,
            expected_version=provenance["lifecycle_version"],
        )
        self.assertNotEqual(record.capability, new_capability)
        self.assertEqual("live", json.loads(provenance_path.read_text())["capability_state"])
        self.assertEqual("active", json.loads(provenance_path.read_text())["lifecycle_state"])
        report = recovery_report(record.runtime_dir)
        self.assertEqual("run-1", report["run_id"])
        self.assertEqual("active", report["lifecycle_state"])
        self.assertTrue(report["preserved_worktree"])

    def test_run_id_is_strict_and_cannot_escape_runtime(self):
        main, worktree, _ = self.active_run()
        for value in ("../escape", "a/b", "", "."):
            with self.subTest(value=value), self.assertRaises(TransportError):
                create_run(main, worktree, value, "plans/p.md")

    def test_git_identity_is_derived_and_revalidated_before_write(self):
        _, worktree, record = self.active_run()
        provenance_path = record.runtime_dir / "provenance.json"
        provenance = json.loads(provenance_path.read_text())
        provenance["worktree_id"] = "caller-lie"
        provenance_path.write_bytes(canonical_json(provenance))
        with self.assertRaisesRegex(TransportError, "identity"):
            durable_write(record.runtime_dir, record.capability, "plans/p.md", b"x")
        self.assertNotEqual(b"x", (worktree / ".agents/artifacts/plans/p.md").read_bytes())

    def test_nested_singletons_derived_and_control_are_excluded(self):
        _, worktree, _ = self.active_run()
        store = worktree / ".agents/artifacts"
        allowed = store / "future-kind/nested/item.md"
        allowed.parent.mkdir(parents=True)
        allowed.write_text("ok")
        self.assertIn("future-kind/nested/item.md", sweep_store(store))
        for relative in ("plans/status.md", "ideas/idea-status.md",
                         "issues/issue-status.md", "loop/events.jsonl",
                         "issues/archives/old.md", "issues/done/old.md"):
            path = store / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("excluded")
            self.assertNotIn(relative, sweep_store(store))

    def test_collect_any_exception_enters_retryable_recovery_with_evidence(self):
        _, worktree, record = self.active_run()
        (worktree / ".agents/artifacts/plans/p.md").write_bytes(b"satellite")
        lifecycle_transition(record.runtime_dir, "active", 1, "harvesting",
                             capability=record.capability, consume=True, expected_epoch=1)
        (record.runtime_dir / "ingress-manifest.json").write_text("{bad")
        with self.assertRaises(Exception):
            collect(record.runtime_dir, expected_version=2, raw_capability=record.capability)
        provenance = json.loads((record.runtime_dir / "provenance.json").read_text())
        self.assertEqual("recovery_required", provenance["lifecycle_state"])
        self.assertTrue((record.runtime_dir / "discard-evidence.json").is_file())
        lifecycle_transition(record.runtime_dir, "recovery_required",
                             provenance["lifecycle_version"], "harvesting")

    def test_publish_rolls_back_all_files_when_commit_is_interrupted(self):
        main, worktree, record = self.active_run()
        second = worktree / ".agents/artifacts/issues/two.md"
        second.parent.mkdir(parents=True)
        second.write_bytes(b"two")
        (worktree / ".agents/artifacts/plans/p.md").write_bytes(b"satellite")
        lifecycle_transition(record.runtime_dir, "active", 1, "harvesting",
                             capability=record.capability, consume=True, expected_epoch=1)
        collect(record.runtime_dir, expected_version=2, raw_capability=record.capability)
        real_replace = os.replace
        count = 0
        def flaky(src, dst):
            nonlocal count
            if "publish-transaction" in str(src):
                count += 1
                if count == 2:
                    raise OSError("injected")
            return real_replace(src, dst)
        with mock.patch("satellite_transport.os.replace", side_effect=flaky):
            with self.assertRaises(TransportError):
                publish(record.runtime_dir, expected_version=3)
        self.assertEqual(b"base", (main / ".agents/artifacts/plans/p.md").read_bytes())
        self.assertFalse((main / ".agents/artifacts/issues/two.md").exists())

    def test_reconcile_rolls_back_durable_publish_journal_after_crash_boundaries(self):
        for crash_at in (1, 2):
            with self.subTest(crash_at=crash_at):
                main, worktree, record = self.active_run()
                second = worktree / ".agents/artifacts/issues/two.md"
                second.parent.mkdir(parents=True)
                second.write_bytes(b"two")
                (worktree / ".agents/artifacts/plans/p.md").write_bytes(b"satellite")
                lifecycle_transition(record.runtime_dir, "active", 1, "harvesting",
                                     capability=record.capability, consume=True, expected_epoch=1)
                collect(record.runtime_dir, expected_version=2,
                        raw_capability=record.capability)
                real_replace = os.replace
                replacements = 0
                def crash(src, dst):
                    nonlocal replacements
                    if "publish-transaction/prepared" in str(src):
                        replacements += 1
                        if replacements == crash_at:
                            real_replace(src, dst)
                            raise KeyboardInterrupt("simulated crash")
                    return real_replace(src, dst)
                with mock.patch("satellite_transport.os.replace", side_effect=crash):
                    with self.assertRaises(KeyboardInterrupt):
                        publish(record.runtime_dir, expected_version=3)
                journal = record.runtime_dir / "publish-transaction/journal.json"
                self.assertTrue(journal.is_file())
                reconcile_owner(record.runtime_dir, pid_start_reader=lambda _: "unavailable")
                self.assertEqual(b"base",
                                 (main / ".agents/artifacts/plans/p.md").read_bytes())
                self.assertFalse((main / ".agents/artifacts/issues/two.md").exists())
                self.assertFalse(journal.exists())
                state = json.loads((record.runtime_dir / "provenance.json").read_text())
                self.assertEqual("recovery_required", state["lifecycle_state"])

    def test_rotate_requires_exact_recovery_cas(self):
        _, _, record = self.active_run()
        with self.assertRaises(TransportError):
            rotate_capability(record.runtime_dir, expected_epoch=1,
                              expected_version=1)

    def test_cleanup_requires_terminal_evidence(self):
        _, worktree, record = self.active_run()
        self.assertFalse(cleanup_allowed(record.runtime_dir))
        lifecycle_transition(record.runtime_dir, "active", 1, "harvesting",
                             capability=record.capability, consume=True, expected_epoch=1)
        collect(record.runtime_dir, expected_version=2, raw_capability=record.capability)
        publish(record.runtime_dir, expected_version=3)
        self.assertFalse(cleanup_allowed(record.runtime_dir))
        transitioned = transition_cleanup_allowed(
            record.runtime_dir, "published", 4,
        )
        self.assertEqual("cleanup_allowed", transitioned["lifecycle_state"])
        self.assertTrue(cleanup_allowed(record.runtime_dir))
        (record.runtime_dir / "publish-evidence.json").write_text("{}")
        self.assertFalse(cleanup_allowed(record.runtime_dir))

    def test_cleanup_transition_requires_nonlive_capability_and_valid_evidence(self):
        _, worktree, record = self.active_run()
        (worktree / ".agents/artifacts/plans/p.md").write_bytes(b"satellite")
        lifecycle_transition(record.runtime_dir, "active", 1, "harvesting",
                             capability=record.capability, consume=True, expected_epoch=1)
        collect(record.runtime_dir, expected_version=2, raw_capability=record.capability)
        publish(record.runtime_dir, expected_version=3)
        provenance = json.loads((record.runtime_dir / "provenance.json").read_text())
        provenance["capability_state"] = "live"
        (record.runtime_dir / "provenance.json").write_bytes(canonical_json(provenance))
        with self.assertRaisesRegex(TransportError, "capability"):
            transition_cleanup_allowed(record.runtime_dir, "published", 4)

    def test_cleanup_rejects_tampered_manifest_digest_and_required_evidence_fields(self):
        for disposition in ("published", "discarded"):
            with self.subTest(disposition=disposition):
                _, worktree, record = self.active_run()
                (worktree / ".agents/artifacts/plans/p.md").write_bytes(b"satellite")
                lifecycle_transition(
                    record.runtime_dir, "active", 1, "harvesting",
                    capability=record.capability, consume=True, expected_epoch=1,
                )
                collect(record.runtime_dir, expected_version=2,
                        raw_capability=record.capability)
                if disposition == "published":
                    publish(record.runtime_dir, expected_version=3)
                    evidence_path = record.runtime_dir / "publish-evidence.json"
                else:
                    discard_staging(
                        record.runtime_dir, 3, actor="human", reason_code="REJECTED",
                    )
                    evidence_path = record.runtime_dir / "discard-evidence.json"
                original = json.loads(evidence_path.read_text())
                mutations = [
                    lambda value: value.update(staging_manifest_digest="0" * 64),
                    lambda value: value.pop("schema_version", None),
                    lambda value: value.update(schema_version=2),
                    lambda value: value.pop("run_id", None),
                    lambda value: value.pop("lifecycle_version", None),
                ]
                if disposition == "published":
                    mutations.append(lambda value: value.pop("published_at", None))
                else:
                    mutations.extend((
                        lambda value: value.pop("reason_code", None),
                        lambda value: value.pop("actor", None),
                        lambda value: value.pop("discarded_at", None),
                        lambda value: value.pop("preserved_satellite", None),
                        lambda value: value.update(partial_staging_inventory=[]),
                    ))
                for mutation in mutations:
                    evidence = dict(original)
                    mutation(evidence)
                    evidence_path.write_bytes(canonical_json(evidence))
                    with self.assertRaises(TransportError):
                        transition_cleanup_allowed(
                            record.runtime_dir, disposition, 4,
                        )
                evidence_path.write_bytes(canonical_json(original))

    def test_cleanup_allowed_revalidates_manifest_digest_after_transition(self):
        _, worktree, record = self.active_run()
        (worktree / ".agents/artifacts/plans/p.md").write_bytes(b"satellite")
        lifecycle_transition(
            record.runtime_dir, "active", 1, "harvesting",
            capability=record.capability, consume=True, expected_epoch=1,
        )
        collect(record.runtime_dir, expected_version=2,
                raw_capability=record.capability)
        publish(record.runtime_dir, expected_version=3)
        transition_cleanup_allowed(record.runtime_dir, "published", 4)
        manifest_path = record.runtime_dir / "staging/manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["entries"][0]["content_hash"] = "0" * 64
        manifest_path.write_bytes(canonical_json(manifest))
        self.assertFalse(cleanup_allowed(record.runtime_dir))

    def test_reconcile_rejects_main_store_parent_symlink_swap_without_outside_write(self):
        main, worktree, record = self.active_run()
        (worktree / ".agents/artifacts/plans/p.md").write_bytes(b"satellite")
        lifecycle_transition(
            record.runtime_dir, "active", 1, "harvesting",
            capability=record.capability, consume=True, expected_epoch=1,
        )
        collect(record.runtime_dir, expected_version=2,
                raw_capability=record.capability)
        real_replace = os.replace

        def crash(src, dst):
            if "publish-transaction/prepared" in str(src):
                real_replace(src, dst)
                raise KeyboardInterrupt("simulated crash")
            return real_replace(src, dst)

        with mock.patch("satellite_transport.os.replace", side_effect=crash):
            with self.assertRaises(KeyboardInterrupt):
                publish(record.runtime_dir, expected_version=3)
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(outside))
        artifacts = main / ".agents/artifacts"
        moved = main / ".agents/artifacts-real"
        artifacts.rename(moved)
        artifacts.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(TransportError, "symlink"):
            reconcile_owner(record.runtime_dir, pid_start_reader=lambda _: "unavailable")
        self.assertEqual([], list(outside.rglob("*")))

    def test_reconcile_derives_backup_path_and_rejects_journal_escape(self):
        main, worktree, record = self.active_run()
        (worktree / ".agents/artifacts/plans/p.md").write_bytes(b"satellite")
        lifecycle_transition(
            record.runtime_dir, "active", 1, "harvesting",
            capability=record.capability, consume=True, expected_epoch=1,
        )
        collect(record.runtime_dir, expected_version=2,
                raw_capability=record.capability)
        real_replace = os.replace

        def crash(src, dst):
            if "publish-transaction/prepared" in str(src):
                real_replace(src, dst)
                raise KeyboardInterrupt("simulated crash")
            return real_replace(src, dst)

        with mock.patch("satellite_transport.os.replace", side_effect=crash):
            with self.assertRaises(KeyboardInterrupt):
                publish(record.runtime_dir, expected_version=3)
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(outside))
        sentinel = outside / "sentinel"
        sentinel.write_bytes(b"outside")
        journal_path = record.runtime_dir / "publish-transaction/journal.json"
        journal = json.loads(journal_path.read_text())
        journal["entries"][0]["backup_path"] = str(sentinel)
        journal_path.write_bytes(canonical_json(journal))
        with self.assertRaisesRegex(TransportError, "backup path"):
            reconcile_owner(record.runtime_dir, pid_start_reader=lambda _: "unavailable")
        self.assertEqual(b"outside", sentinel.read_bytes())

    def test_create_rejects_symlink_in_control_path_before_mutation(self):
        main, worktree = self.roots()
        plan = Path("plans/p.md")
        (main / ".agents/artifacts" / plan).write_bytes(b"base")
        (worktree / ".agents/runtime").parent.mkdir(parents=True, exist_ok=True)
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(outside))
        (worktree / ".agents/runtime").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(TransportError, "symlink"):
            create_run(main, worktree, "unsafe", plan)
        self.assertFalse((main / ".agents/runtime/satellite-runs/unsafe").exists())

    def test_pid_stat_parser_handles_spaces_and_parentheses(self):
        from satellite_transport import pid_start_time
        stat = "12 (worker name (x)) S " + " ".join(str(i) for i in range(1, 30))
        self.assertEqual("19", pid_start_time(12, reader=lambda _: stat))


if __name__ == "__main__":
    unittest.main()
