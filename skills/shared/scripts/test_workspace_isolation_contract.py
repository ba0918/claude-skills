"""Mechanical checks for the workspace-isolation and satellite-store contracts."""

from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
REFERENCES = REPO_ROOT / "skills" / "shared" / "references"
WORKSPACE_CONTRACT = REFERENCES / "workspace-isolation.md"
ARTIFACT_CONTRACT = REFERENCES / "artifact-store.md"
RECOVERY_COMMAND = "/claude-skills:artifacts recover --run-id {run_id}"
LIFECYCLE_EDGES = {
    "created": {"active", "failed_readonly"},
    "active": {"harvesting", "failed_readonly"},
    "harvesting": {"staged", "recovery_required"},
    "staged": {"published", "discarded", "recovery_required"},
    "published": {"cleanup_allowed", "recovery_required"},
    "discarded": {"cleanup_allowed", "recovery_required"},
    "failed_readonly": {"active", "harvesting", "recovery_required"},
    "recovery_required": {"harvesting", "staged"},
}


def lifecycle_edges(text):
    rows = re.findall(r"^\| `([^`]+)` \| ([^|]+) \|", text, re.MULTILINE)
    return {
        source: set(re.findall(r"`([^`]+)`", destinations))
        for source, destinations in rows
        if source in LIFECYCLE_EDGES
    }


def fenced_block_after(text, marker):
    tail = text.split(marker, 1)[1]
    return tail.split("```text", 1)[1].split("```", 1)[0].strip()


class TestWorkspaceIsolationContract(unittest.TestCase):
    def test_workspace_contract_defines_policy_and_resolution(self):
        text = WORKSPACE_CONTRACT.read_text(encoding="utf-8")
        for required in (
            ".agents/workspace.yml",
            "isolation: worktree",
            "isolation: inplace",
            "invocation override",
            "missing",
            "`inplace`",
            "invalid",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)

    def test_workspace_contract_defines_transactional_lifecycle(self):
        text = WORKSPACE_CONTRACT.read_text(encoding="utf-8")
        for required in (
            "created",
            "active",
            "harvesting",
            "staged",
            "published",
            "discarded",
            "cleanup_allowed",
            "failed_readonly",
            "recovery_required",
            "compare-and-swap",
            "expected prior state",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)
        self.assertIn("| `staged` | `published`, `discarded`", text)
        self.assertIn("| `discarded` | `cleanup_allowed`", text)

    def test_lifecycle_table_has_exact_edges_and_atomic_transition_binding(self):
        text = WORKSPACE_CONTRACT.read_text(encoding="utf-8")
        self.assertEqual(lifecycle_edges(text), LIFECYCLE_EDGES)
        normalized = " ".join(text.split())
        self.assertIn(
            "Every lifecycle edge in this table, including recovery edges, MUST be "
            "committed while holding `lifecycle.lock`",
            normalized,
        )
        self.assertIn(
            "single atomic compare-and-swap of both `lifecycle_state` and "
            "`lifecycle_version`",
            normalized,
        )
        self.assertIn("Transitions not listed in the table are forbidden", normalized)

    def test_workspace_contract_defines_recovery_entry_point(self):
        text = WORKSPACE_CONTRACT.read_text(encoding="utf-8")
        self.assertIn(RECOVERY_COMMAND, text)
        reason_codes = (
            "SATELLITE_WRITE_DENIED",
            "SATELLITE_PRESERVED",
            "HARVEST_CONFLICT",
            "HARVEST_INTERRUPTED",
        )
        for reason_code in reason_codes:
            with self.subTest(reason_code=reason_code):
                self.assertIn(f"`reason_code={reason_code}`", text)
        expected_fields = (
            "reason_code={reason_code}",
            "run_id={run_id}",
            "main_tree_path={main_tree_path}",
            "worktree_path={worktree_path_or_unavailable}",
            "reason={reason}",
            f"recovery_command={RECOVERY_COMMAND}",
        )
        template = fenced_block_after(text, "exact structured template")
        self.assertEqual(template.splitlines(), list(expected_fields))
        self.assertEqual(
            re.findall(r"^- `reason_code=([A-Z_]+)`$", text, re.MULTILINE),
            list(reason_codes),
        )
        self.assertIn("literal `unavailable`", text)
        self.assertIn("Diagnostics MUST NOT contain the raw capability", text)

    def test_closed_satellite_write_lifecycle_states_are_explicit(self):
        text = " ".join(ARTIFACT_CONTRACT.read_text(encoding="utf-8").split())
        self.assertIn(
            "The closed set of lifecycle states permitting a durable satellite write "
            "is exactly `active`",
            text,
        )

    def test_owner_identity_is_pid_reuse_safe(self):
        text = " ".join(ARTIFACT_CONTRACT.read_text(encoding="utf-8").split())
        self.assertIn("owner_pid_start_time", text)
        self.assertIn("PID reuse", text)
        self.assertIn("both `owner_pid` and `owner_pid_start_time`", text)

    def test_capability_has_one_canonical_authority_bound_to_lifecycle_cas(self):
        raw_text = ARTIFACT_CONTRACT.read_text(encoding="utf-8")
        text = " ".join(raw_text.split())
        self.assertIn(
            "`provenance.json` fields `capability_digest`, `capability_state`, and "
            "`capability_epoch` jointly form the canonical capability representation",
            text,
        )
        self.assertIn(
            "`capability_digest` is the single canonical capability authority",
            text,
        )
        self.assertNotIn("├── capability.sha256", raw_text)
        self.assertIn(
            "same locked provenance snapshot",
            text,
        )
        self.assertIn(
            "capability digest match and lifecycle compare-and-swap",
            text,
        )
        self.assertIn(
            "`capability_state` | `live`, `consumed`, or `revoked`",
            text,
        )
        self.assertIn(
            "`capability_epoch` | monotonic capability generation",
            text,
        )
        self.assertIn(
            "atomically compare-and-swap `capability_state: live` and the expected "
            "`capability_epoch` to `capability_state: consumed`",
            text,
        )
        self.assertIn(
            "atomically compare-and-swap `capability_state: live` and the expected "
            "`capability_epoch` to `capability_state: revoked`",
            text,
        )

    def test_recovery_must_recollect_before_publish(self):
        text = " ".join(WORKSPACE_CONTRACT.read_text(encoding="utf-8").split())
        self.assertNotIn(
            "| `recovery_required` | `harvesting`, `staged`, `published`",
            text,
        )
        self.assertIn(
            "Recovery MUST revalidate or collect the preserved bytes, transition "
            "through `harvesting` to `staged`, and only then retry publish",
            text,
        )

    def test_recovery_must_recollect_before_discard(self):
        text = " ".join(WORKSPACE_CONTRACT.read_text(encoding="utf-8").split())
        self.assertNotIn(
            "| `recovery_required` | `harvesting`, `staged`, `discarded`",
            text,
        )
        self.assertIn(
            "Recovery MUST transition through `harvesting` to `staged` before an "
            "authorized discard",
            text,
        )
        self.assertNotIn(
            "recovery_required` may transition directly to `discarded`",
            text,
        )

    def test_satellite_write_commit_is_inside_authorization_lock(self):
        text = " ".join(ARTIFACT_CONTRACT.read_text(encoding="utf-8").split())
        self.assertIn(
            "authorization and the durable write commit MUST occur while holding the "
            "same `lifecycle.lock`",
            text,
        )
        self.assertIn(
            "write a temporary file, `fsync` it when durability is requested, "
            "atomically rename it to the destination, and only then release the lock",
            text,
        )
        self.assertIn("revocation cannot race an authorized write commit", text)

    def test_discard_evidence_is_concrete_and_atomic(self):
        raw_text = ARTIFACT_CONTRACT.read_text(encoding="utf-8")
        text = " ".join(raw_text.split())
        self.assertIn(
            ".agents/runtime/satellite-runs/{run_id}/discard-evidence.json",
            raw_text,
        )
        for field in (
            "`run_id`",
            "`staging_manifest_digest`",
            "`partial_staging_inventory`",
            "`reason_code`",
            "`actor`",
            "`discarded_at`",
            "`preserved_satellite`",
            "`lifecycle_version`",
        ):
            with self.subTest(field=field):
                self.assertIn(field, text)
        self.assertIn(
            "atomically bind the evidence to the `staged` to `discarded` lifecycle "
            "compare-and-swap under `lifecycle.lock`",
            text,
        )
        self.assertIn(
            "Cleanup MUST compare the evidence `run_id`, staging manifest digest, and "
            "`lifecycle_version`",
            text,
        )

    def test_discard_never_claims_invalid_or_partial_staging_was_validated(self):
        text = " ".join(ARTIFACT_CONTRACT.read_text(encoding="utf-8").split())
        self.assertIn(
            "A partial or invalid staging set MUST NOT enter `staged` or use the "
            "`discarded` disposition",
            text,
        )
        self.assertIn(
            "record failure evidence that identifies the unvalidated staging set",
            text,
        )
        self.assertIn(
            "preserve the satellite and staging bytes for recovery",
            text,
        )
        self.assertIn(
            "`discarded` certifies only that a complete validated staging set",
            text,
        )

    def test_artifact_contract_defines_satellite_schemas_and_transport(self):
        text = ARTIFACT_CONTRACT.read_text(encoding="utf-8")
        for required in (
            "run_id",
            "main_tree_path",
            "worktree_id",
            "pinned_plan",
            "created_at",
            "ingress_manifest_digest",
            "lifecycle_state",
            "relative_path",
            "file_type",
            "content_hash",
            "capability_digest",
            "0600",
            "collect",
            "publish",
            "destination hash",
            "three-way",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)

    def test_three_way_classifier_defines_hash_and_absence_predicates(self):
        text = " ".join(ARTIFACT_CONTRACT.read_text(encoding="utf-8").split())
        for predicate in (
            "`unchanged`: `M == B and S == B`",
            "`satellite_only_change`: `S != B and M == B`",
            "`main_only_change`: `M != B and S == B`",
            "`identical_concurrent_change`: `M == S and M != B`",
            "`conflict`: `B`, `M`, and `S` are pairwise distinct",
            "`deletion`: `B != ABSENT` and exactly one of `M` or `S` is `ABSENT`",
            "`recreation`: `B == ABSENT`, `M != ABSENT`, `S != ABSENT`, and `M != S`",
        ):
            with self.subTest(predicate=predicate):
                self.assertIn(predicate, text)
        self.assertIn("`ABSENT` is a first-class value", text)
        self.assertIn("rename cannot be proven from per-path hashes alone", text)
        self.assertIn("MUST NOT call the per-path table exhaustive", text)

    def test_contracts_link_to_each_other(self):
        workspace = WORKSPACE_CONTRACT.read_text(encoding="utf-8")
        artifact = ARTIFACT_CONTRACT.read_text(encoding="utf-8")
        self.assertIn("[Agent Artifact Store](artifact-store.md)", workspace)
        self.assertIn("[Workspace Isolation](workspace-isolation.md)", artifact)

    def test_pinned_plan_path_basis_is_store_relative(self):
        artifact = ARTIFACT_CONTRACT.read_text(encoding="utf-8")
        workspace = WORKSPACE_CONTRACT.read_text(encoding="utf-8")
        self.assertIn("store-relative plan path", artifact)
        self.assertIn("store-relative pinned plan", workspace)
        self.assertNotIn("repository-relative plan path", artifact)
        self.assertNotIn("repository-relative pinned plan", workspace)

    def test_capability_consumption_edge_documented(self):
        workspace = WORKSPACE_CONTRACT.read_text(encoding="utf-8")
        self.assertIn("capability is consumed on this edge", workspace)

    def test_delegation_runtime_classified(self):
        artifact = ARTIFACT_CONTRACT.read_text(encoding="utf-8")
        self.assertIn("Delegation result files", artifact)
        self.assertIn(".agents/runtime/delegation/", artifact)


if __name__ == "__main__":
    unittest.main()
