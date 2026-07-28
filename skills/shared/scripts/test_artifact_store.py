import os
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from contextlib import redirect_stdout
import io

sys.path.insert(0, str(Path(__file__).parent))
from artifact_store import (  # noqa: E402
    ArtifactStoreError,
    finalize_migration,
    initialize,
    inspect,
    load_policy,
    migration_inventory,
    parse_policy,
    rebuild_index,
    require_writable,
    stage_migration,
    satellite_create,
    satellite_collect,
    satellite_publish,
    satellite_activate,
    satellite_transition,
    satellite_write,
    satellite_cleanup_transition,
    satellite_cleanup_allowed,
    satellite_revoke,
    satellite_rotate,
    satellite_reconcile,
    satellite_recovery_report,
    satellite_discard,
    satellite_format_diagnostic,
    satellite_authorize_write,
    recover_run,
    main,
)


class ArtifactStoreTest(unittest.TestCase):
    def repo(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        (root / ".gitignore").write_text("/.agents/artifacts/\n", encoding="utf-8")
        return root

    def write_policy(self, repo, **changes):
        policy = {
            "schema_version": 1,
            "root": ".agents/artifacts",
            "visibility": "local",
            "worktree_scope": "worktree",
        }
        policy.update(changes)
        path = repo / ".agents/artifacts.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(f"{k}: {v}\n" for k, v in policy.items()), encoding="utf-8")

    def test_satellite_facade_delegates_to_transport_api(self):
        with mock.patch("artifact_store.create_satellite_run", return_value="created") as create:
            self.assertEqual("created", satellite_create("/main", "/work", "run-1", "plans/p.md"))
            create.assert_called_once_with(Path("/main"), Path("/work"), "run-1", "plans/p.md")
        with mock.patch("artifact_store.collect_satellite", return_value="staged") as collect:
            self.assertEqual("staged", satellite_collect("/runtime", 2, "cap"))
            collect.assert_called_once_with(
                Path("/runtime"), expected_version=2, raw_capability="cap",
            )
        with mock.patch("artifact_store.publish_satellite", return_value="published") as publish:
            self.assertEqual("published", satellite_publish("/runtime", 3))
            publish.assert_called_once_with(Path("/runtime"), expected_version=3)

    def test_satellite_facade_exposes_complete_transport_workflow(self):
        with mock.patch("artifact_store.lifecycle_transition", return_value="active") as call:
            self.assertEqual("active", satellite_activate("/r", 0))
            call.assert_called_once_with(Path("/r"), "created", 0, "active")
        with mock.patch("artifact_store.lifecycle_transition", return_value="next") as call:
            self.assertEqual(
                "next", satellite_transition("/r", "active", 1, "harvesting",
                                             capability="cap", consume=True,
                                             expected_epoch=1),
            )
            call.assert_called_once_with(
                Path("/r"), "active", 1, "harvesting",
                capability="cap", consume=True, expected_epoch=1,
            )
        with mock.patch("artifact_store.durable_satellite_write", return_value=None) as call:
            satellite_write("/r", "cap", "plans/p.md", b"x")
            call.assert_called_once_with(Path("/r"), "cap", "plans/p.md", b"x")
        with mock.patch("artifact_store.transition_cleanup_allowed",
                        return_value="cleanup") as call:
            self.assertEqual("cleanup", satellite_cleanup_transition("/r", "published", 4))
            call.assert_called_once_with(Path("/r"), "published", 4)
        with mock.patch("artifact_store.discard_satellite_staging",
                        return_value="discarded") as call:
            self.assertEqual(
                "discarded",
                satellite_discard("/r", 3, actor="human", reason_code="REJECTED"),
            )
            call.assert_called_once_with(
                Path("/r"), 3, actor="human", reason_code="REJECTED",
            )
        with mock.patch("artifact_store.format_satellite_diagnostic",
                        return_value="diagnostic") as call:
            self.assertEqual(
                "diagnostic",
                satellite_format_diagnostic("DENIED", "/r", "reason"),
            )
            call.assert_called_once_with("DENIED", Path("/r"), "reason")
        with mock.patch("artifact_store.authorize_satellite_write",
                        return_value=None) as call:
            satellite_authorize_write("/r", "cap", "plans/p.md")
            call.assert_called_once_with(Path("/r"), "cap", "plans/p.md")
        delegates = (
            ("cleanup_allowed_satellite", satellite_cleanup_allowed, ("/r",)),
            ("revoke_satellite_capability", satellite_revoke, ("/r", 1)),
            ("rotate_satellite_capability", satellite_rotate, ("/r", 1, 2)),
            ("reconcile_satellite_owner", satellite_reconcile, ("/r",)),
            ("satellite_recovery", satellite_recovery_report, ("/r",)),
        )
        for target, facade, args in delegates:
            with self.subTest(target=target), mock.patch(
                f"artifact_store.{target}", return_value=target,
            ) as call:
                self.assertEqual(target, facade(*args))
                call.assert_called_once()

    def test_missing_policy_uses_safe_local_default(self):
        root = self.repo()
        policy, explicit = load_policy(root)
        self.assertFalse(explicit)
        self.assertEqual("local", policy["visibility"])
        self.assertEqual(".agents/artifacts", policy["root"])

    def test_fresh_init_creates_worktree_workspace_policy(self):
        root = self.repo()
        result = initialize(root)
        self.assertEqual(
            "isolation: worktree\n",
            (root / ".agents/workspace.yml").read_text(encoding="utf-8"),
        )
        self.assertTrue(result["workspace_policy_created"])
        self.assertIsNone(result["workspace_policy_opt_in"])

    def test_existing_or_partial_init_does_not_silently_create_workspace_policy(self):
        cases = ("artifact-policy", "empty-store", "legacy-store")
        for case in cases:
            with self.subTest(case=case):
                root = self.repo()
                if case == "artifact-policy":
                    self.write_policy(root)
                elif case == "empty-store":
                    (root / ".agents/artifacts").mkdir(parents=True)
                else:
                    (root / "docs/plans").mkdir(parents=True)
                    (root / "docs/plans/p.md").write_text("plan", encoding="utf-8")
                if case == "legacy-store":
                    with self.assertRaises(ArtifactStoreError):
                        initialize(root)
                else:
                    result = initialize(root)
                    self.assertFalse(result["workspace_policy_created"])
                    self.assertIn(".agents/workspace.yml", result["workspace_policy_opt_in"])
                self.assertFalse((root / ".agents/workspace.yml").exists())

    def test_repeated_init_preserves_workspace_policy(self):
        root = self.repo()
        initialize(root)
        policy = root / ".agents/workspace.yml"
        policy.write_text("isolation: inplace\n", encoding="utf-8")
        result = initialize(root)
        self.assertEqual("isolation: inplace\n", policy.read_text(encoding="utf-8"))
        self.assertFalse(result["workspace_policy_created"])

    def test_recover_run_reconciles_selected_main_runtime_and_reports(self):
        root = self.repo()
        runtime = root / ".agents/runtime/satellite-runs/run-42"
        runtime.mkdir(parents=True)
        with mock.patch(
            "artifact_store.recover_satellite", return_value={"run_id": "run-42"},
        ) as report:
            self.assertEqual({"run_id": "run-42"}, recover_run(root, "run-42"))
            report.assert_called_once_with(runtime)

    def test_recover_cli_requires_one_safe_run_id(self):
        root = self.repo()
        output = io.StringIO()
        with mock.patch("artifact_store.recover_run", return_value={"run_id": "run-42"}):
            with redirect_stdout(output):
                self.assertEqual(0, main(["recover", "--repo", str(root), "--run-id", "run-42"]))
        self.assertEqual("run-42", json.loads(output.getvalue())["run_id"])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(2, main(["recover", "--repo", str(root), "--run-id", "../escape"]))

    def test_recover_facade_and_cli_reconcile_a_deleted_worktree_from_main_runtime(self):
        root = self.repo()
        (root / ".agents/artifacts/plans").mkdir(parents=True)
        (root / ".agents/artifacts/plans/p.md").write_text("plan", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
             "commit", "-qm", "base"],
            cwd=root, check=True,
        )
        worktree = root.parent / f"{root.name}-deleted-worktree"
        subprocess.run(["git", "worktree", "add", "-q", str(worktree)], cwd=root, check=True)
        self.addCleanup(lambda: subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)],
            cwd=root, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ))
        record = satellite_create(root, worktree, "run-deleted", "plans/p.md")
        satellite_activate(record.runtime_dir, 0)
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree)],
            cwd=root, check=True,
        )

        facade = recover_run(root, "run-deleted")
        self.assertEqual("WORKTREE_MISSING", facade["state_code"])
        self.assertEqual("SATELLITE_PRESERVED", facade["reason_code"])

        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(
                0,
                main(["recover", "--repo", str(root), "--run-id", "run-deleted"]),
            )
        cli = json.loads(output.getvalue())
        self.assertEqual("failed_readonly", cli["lifecycle_state"])
        self.assertEqual("revoked", cli["capability_state"])
        self.assertEqual(6, len(cli["diagnostic"].splitlines()))

    def test_unknown_schema_and_key_fail_closed(self):
        root = self.repo()
        self.write_policy(root, schema_version=2)
        with self.assertRaisesRegex(ArtifactStoreError, "schema_version"):
            load_policy(root)
        (root / ".agents/artifacts.yml").write_text(
            "schema_version: 1\nroot: .agents/artifacts\nvisibility: local\n"
            "worktree_scope: worktree\nsecret: value\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ArtifactStoreError, "unknown policy keys"):
            load_policy(root)

    def test_noncanonical_and_absolute_roots_are_rejected(self):
        root = self.repo()
        self.write_policy(root, root="../outside")
        with self.assertRaisesRegex(ArtifactStoreError, "root"):
            load_policy(root)
        self.write_policy(root, root="/tmp/outside")
        with self.assertRaisesRegex(ArtifactStoreError, "root"):
            load_policy(root)

    def test_legacy_store_blocks_writes(self):
        root = self.repo()
        (root / "docs/plans").mkdir(parents=True)
        (root / "docs/plans/a.md").write_text("plan", encoding="utf-8")
        result = inspect(root)
        self.assertEqual("legacy", result["state"])
        with self.assertRaisesRegex(ArtifactStoreError, "migration"):
            require_writable(root)

    def test_split_brain_is_reported(self):
        root = self.repo()
        self.write_policy(root)
        (root / "docs/issues").mkdir(parents=True)
        (root / "docs/issues/a.md").write_text("issue", encoding="utf-8")
        (root / ".agents/artifacts/issues").mkdir(parents=True)
        (root / ".agents/artifacts/issues/b.md").write_text("issue", encoding="utf-8")
        result = inspect(root)
        self.assertEqual("split-brain", result["state"])
        self.assertFalse(result["writable"])

    def test_local_store_must_be_ignored_and_untracked(self):
        root = self.repo()
        self.write_policy(root)
        self.assertEqual([], inspect(root)["errors"])
        (root / ".gitignore").write_text("", encoding="utf-8")
        self.assertIn("local artifact store is not ignored by Git", inspect(root)["errors"])

    def test_public_store_must_not_be_ignored(self):
        root = self.repo()
        self.write_policy(root, visibility="public")
        self.assertIn("public artifact store is ignored by Git", inspect(root)["errors"])
        (root / ".gitignore").write_text("", encoding="utf-8")
        self.assertEqual([], inspect(root)["errors"])

    def test_policy_must_not_be_ignored(self):
        root = self.repo()
        self.write_policy(root)
        (root / ".gitignore").write_text("/.agents/\n", encoding="utf-8")
        self.assertIn("artifact policy is ignored by Git", inspect(root)["errors"])

    def test_symlink_root_is_rejected(self):
        root = self.repo()
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: outside.rmdir())
        (root / ".agents").mkdir()
        os.symlink(outside, root / ".agents/artifacts")
        with self.assertRaisesRegex(ArtifactStoreError, "symlink"):
            inspect(root, validate_git=False)

    def test_init_is_idempotent_and_refuses_legacy(self):
        root = self.repo()
        first = initialize(root)
        second = initialize(root)
        self.assertEqual(first["policy"], second["policy"])
        self.assertTrue((root / ".agents/artifacts/plans").is_dir())

        legacy = self.repo()
        (legacy / "docs/ideas").mkdir(parents=True)
        (legacy / "docs/ideas/a.md").write_text("idea", encoding="utf-8")
        with self.assertRaisesRegex(ArtifactStoreError, "migration"):
            initialize(legacy)

    def test_init_creates_handoff_kind_directory(self):
        root = self.repo()
        initialize(root)
        self.assertTrue((root / ".agents/artifacts/handoff").is_dir())

    def test_handoff_is_legacy_source_and_maps_to_handoff_kind(self):
        root = self.repo()
        (root / "docs/handoff").mkdir(parents=True)
        (root / "docs/handoff/20260701_100000_example.md").write_text(
            "handoff", encoding="utf-8"
        )
        result = inspect(root)
        self.assertEqual("legacy", result["state"])
        self.assertIn("docs/handoff", result["legacy_roots"])
        inventory = migration_inventory(root)
        entry = inventory["entries"][0]
        self.assertEqual("docs/handoff/20260701_100000_example.md", entry["source"])
        self.assertEqual(
            ".agents/artifacts/handoff/20260701_100000_example.md",
            entry["destination"],
        )

    def test_init_creates_reviews_kind_directory(self):
        root = self.repo()
        initialize(root)
        self.assertTrue((root / ".agents/artifacts/reviews").is_dir())

    def test_reviews_is_legacy_source_and_maps_to_reviews_kind(self):
        root = self.repo()
        (root / "docs/reviews").mkdir(parents=True)
        (root / "docs/reviews/review-20260719-1200.md").write_text(
            "review", encoding="utf-8"
        )
        result = inspect(root)
        self.assertEqual("legacy", result["state"])
        self.assertIn("docs/reviews", result["legacy_roots"])
        inventory = migration_inventory(root)
        entry = inventory["entries"][0]
        self.assertEqual("docs/reviews/review-20260719-1200.md", entry["source"])
        self.assertEqual(
            ".agents/artifacts/reviews/review-20260719-1200.md",
            entry["destination"],
        )

    def test_init_creates_decisions_kind_directory(self):
        root = self.repo()
        initialize(root)
        self.assertTrue((root / ".agents/artifacts/decisions").is_dir())

    def test_handoff_and_canonical_both_present_is_split_brain(self):
        root = self.repo()
        self.write_policy(root)
        (root / "docs/handoff").mkdir(parents=True)
        (root / "docs/handoff/a.md").write_text("old handoff", encoding="utf-8")
        (root / ".agents/artifacts/handoff").mkdir(parents=True)
        (root / ".agents/artifacts/handoff/b.md").write_text(
            "new handoff", encoding="utf-8"
        )
        result = inspect(root)
        self.assertEqual("split-brain", result["state"])
        self.assertFalse(result["writable"])

    def test_migration_requires_decisions_and_is_two_phase(self):
        root = self.repo()
        (root / "docs/plans").mkdir(parents=True)
        source = root / "docs/plans/a.md"
        source.write_text("plan", encoding="utf-8")
        inventory = migration_inventory(root)
        self.assertEqual("review", inventory["entries"][0]["action"])
        decisions = root / "decisions.json"
        decisions.write_text(__import__("json").dumps(inventory), encoding="utf-8")
        with self.assertRaisesRegex(ArtifactStoreError, "unresolved"):
            stage_migration(root, decisions)

        inventory["entries"][0]["action"] = "move"
        decisions.write_text(__import__("json").dumps(inventory), encoding="utf-8")
        staged = stage_migration(root, decisions)
        self.assertFalse(staged["source_removed"])
        self.assertTrue(source.exists())
        self.assertTrue((root / ".agents/artifacts/plans/a.md").exists())
        with self.assertRaisesRegex(ArtifactStoreError, "confirmations"):
            finalize_migration(root)
        finalized = finalize_migration(
            root, confirm_remove_source=True, confirm_public_history=True,
        )
        self.assertTrue(finalized["verified"])
        self.assertFalse(source.exists())


class RebuildIndexTest(unittest.TestCase):
    def repo(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        (root / ".gitignore").write_text("/.agents/artifacts/\n", encoding="utf-8")
        return root

    def write_idea(self, repo, slug, *, title=None, created="2026-07-01 10:00:00",
                   status="💡 Idea", tags="`a`, `b`", summary="Short summary.",
                   include_tags=True):
        title = title if title is not None else slug.split("_", 1)[-1]
        directory = repo / ".agents/artifacts/ideas"
        directory.mkdir(parents=True, exist_ok=True)
        tags_line = f"**Tags:** {tags}\n" if include_tags else ""
        (directory / f"{slug}.md").write_text(
            f"# {title}\n\n"
            f"**Created:** {created}\n"
            f"**Status:** {status}\n"
            f"{tags_line}"
            "\n---\n\n"
            f"## Summary\n\n{summary}\n\n"
            "## Key Discussion Points\n\n- point\n",
            encoding="utf-8",
        )

    def write_issue(self, repo, slug, *, title="An issue", status="open",
                    created="2026-07-01 10:00:00", tags="auth,bug",
                    source="", summary="Issue summary.", subdir=""):
        base = repo / ".agents/artifacts/issues"
        directory = base / subdir if subdir else base
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{slug}.md").write_text(
            "---\n"
            f"title: {title}\n"
            f"status: {status}\n"
            f"created: {created}\n"
            f"tags: {tags}\n"
            f"source: {source}\n"
            "---\n\n"
            f"## 概要\n\n{summary}\n\n"
            "## 備考\n\n(none)\n",
            encoding="utf-8",
        )

    def test_ideas_index_has_five_columns_and_is_deterministic(self):
        root = self.repo()
        self.write_idea(root, "20260701100000_alpha", title="alpha",
                        summary="First idea.")
        self.write_idea(root, "20260702100000_beta", title="beta",
                        summary="Second idea.")
        first = rebuild_index(root, "ideas")
        index_path = root / ".agents/artifacts/ideas/idea-status.md"
        self.assertEqual("ideas", first["kind"])
        self.assertEqual(2, first["entries"])
        content = index_path.read_bytes()
        header = index_path.read_text(encoding="utf-8")
        self.assertIn("# Idea Status", header)
        self.assertIn("| Idea | Tags | Created | Status | Summary |", header)
        self.assertIn("[alpha](20260701100000_alpha.md)", header)
        self.assertIn("First idea.", header)
        self.assertIn("💡 Idea", header)
        # 決定論性: 同一入力 → バイト同一
        rebuild_index(root, "ideas")
        self.assertEqual(content, index_path.read_bytes())

    def test_issues_index_has_four_columns_without_status(self):
        root = self.repo()
        self.write_issue(root, "20260701100000_login", title="Login bug",
                         tags="auth,bug", summary="Login times out.")
        result = rebuild_index(root, "issues")
        index_path = root / ".agents/artifacts/issues/issue-status.md"
        header = index_path.read_text(encoding="utf-8")
        self.assertEqual("issues", result["kind"])
        self.assertIn("# Issue Status", header)
        self.assertIn("| Issue | Tags | Created | Summary |", header)
        self.assertNotIn("Status |", header.splitlines()[4])  # header row has no Status col
        self.assertIn("[20260701100000_login](20260701100000_login.md)", header)
        self.assertIn("`auth,bug`", header)
        self.assertIn("Login times out.", header)

    def test_kind_column_schema_diverges(self):
        root = self.repo()
        self.write_idea(root, "20260701100000_i", title="i")
        self.write_issue(root, "20260701100000_j", title="j")
        rebuild_index(root, "ideas")
        rebuild_index(root, "issues")
        idea_header = (root / ".agents/artifacts/ideas/idea-status.md").read_text(
            encoding="utf-8")
        issue_header = (root / ".agents/artifacts/issues/issue-status.md").read_text(
            encoding="utf-8")
        self.assertIn("| Idea | Tags | Created | Status | Summary |", idea_header)
        self.assertIn("| Issue | Tags | Created | Summary |", issue_header)
        # issue index の列定義行には Status 列がない（title の "Issue Status" は別物）
        issue_col_row = [l for l in issue_header.splitlines()
                         if l.startswith("| Issue |")][0]
        self.assertNotIn("Status", issue_col_row)

    def test_archives_and_done_failed_are_excluded(self):
        root = self.repo()
        self.write_idea(root, "20260701100000_live", title="live")
        # ideas archive エントリは対象外
        arch = root / ".agents/artifacts/ideas/archives"
        arch.mkdir(parents=True, exist_ok=True)
        (arch / "20260601100000_gone.md").write_text(
            "# gone\n\n**Created:** 2026-06-01 10:00:00\n**Status:** 📋 Planned\n"
            "**Tags:** `x`\n\n---\n\n## Summary\n\narchived.\n", encoding="utf-8")
        rebuild_index(root, "ideas")
        idea_header = (root / ".agents/artifacts/ideas/idea-status.md").read_text(
            encoding="utf-8")
        self.assertIn("[live]", idea_header)
        self.assertNotIn("gone", idea_header)

        self.write_issue(root, "20260701100000_open_one", title="open one")
        self.write_issue(root, "20260601100000_done_one", title="done one",
                         status="closed", subdir="done")
        self.write_issue(root, "20260601100000_failed_one", title="failed one",
                         subdir="failed/permanent")
        self.write_issue(root, "20260601100000_arch_one", title="arch one",
                         subdir="archives")
        rebuild_index(root, "issues")
        issue_header = (root / ".agents/artifacts/issues/issue-status.md").read_text(
            encoding="utf-8")
        self.assertIn("open_one", issue_header)
        self.assertNotIn("done_one", issue_header)
        self.assertNotIn("failed_one", issue_header)
        self.assertNotIn("arch_one", issue_header)

    def test_missing_fields_do_not_crash(self):
        root = self.repo()
        self.write_idea(root, "20260701100000_notags", title="notags",
                        include_tags=False)
        result = rebuild_index(root, "ideas")
        self.assertEqual(1, result["entries"])
        header = (root / ".agents/artifacts/ideas/idea-status.md").read_text(
            encoding="utf-8")
        # Tags 欠損でも行は生成され、Tags セルは空
        row = [l for l in header.splitlines() if "[notags]" in l][0]
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        self.assertEqual("notags", cells[0].split("]")[0].lstrip("["))
        self.assertEqual("", cells[1])  # Tags empty

    def test_pipe_and_newline_in_body_are_escaped(self):
        root = self.repo()
        self.write_idea(root, "20260701100000_evil", title="evil",
                        summary="a | b\nsecond line")
        rebuild_index(root, "ideas")
        header = (root / ".agents/artifacts/ideas/idea-status.md").read_text(
            encoding="utf-8")
        row = [l for l in header.splitlines() if "[evil]" in l][0]
        # 生の `|` はエスケープされ、改行はセル内に残らない（1 行に収まる）
        self.assertIn("a \\| b", row)
        self.assertIn("second line", row)
        # テーブル構造: 5 列（区切り 6 本の `|`）を維持
        self.assertEqual(6, row.count("|") - row.count("\\|"))

    def test_pipe_in_slug_filename_is_escaped(self):
        root = self.repo()
        directory = root / ".agents/artifacts/ideas"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "20260701100000_a|b.md").write_text(
            "# a|b\n\n**Created:** 2026-07-01 10:00:00\n**Status:** 💡 Idea\n"
            "**Tags:** `x`\n\n---\n\n## Summary\n\nok\n", encoding="utf-8")
        rebuild_index(root, "ideas")
        header = (root / ".agents/artifacts/ideas/idea-status.md").read_text(
            encoding="utf-8")
        row = [l for l in header.splitlines() if "20260701100000_a" in l][0]
        # ファイル名由来の | もエスケープされ、5 列構造（生の | は 6 本）を維持
        self.assertEqual(6, row.count("|") - row.count("\\|"))

    def test_non_utf8_entry_raises_store_error(self):
        root = self.repo()
        directory = root / ".agents/artifacts/ideas"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "20260701100000_bin.md").write_bytes(b"\xff\xfe\x00bad")
        with self.assertRaisesRegex(ArtifactStoreError, "utf-8"):
            rebuild_index(root, "ideas")
        self.assertFalse(
            (root / ".agents/artifacts/ideas/idea-status.md").exists())

    def test_legacy_store_refuses_to_write(self):
        root = self.repo()
        (root / "docs/ideas").mkdir(parents=True)
        (root / "docs/ideas/legacy.md").write_text("# legacy\n", encoding="utf-8")
        with self.assertRaisesRegex(ArtifactStoreError, "migration"):
            rebuild_index(root, "ideas")
        self.assertFalse(
            (root / ".agents/artifacts/ideas/idea-status.md").exists())

    def test_split_brain_refuses_to_write(self):
        root = self.repo()
        (root / "docs/ideas").mkdir(parents=True)
        (root / "docs/ideas/legacy.md").write_text("# legacy\n", encoding="utf-8")
        self.write_idea(root, "20260701100000_canon", title="canon")
        with self.assertRaises(ArtifactStoreError):
            rebuild_index(root, "ideas")
        self.assertFalse(
            (root / ".agents/artifacts/ideas/idea-status.md").exists())

    def test_unknown_kind_is_rejected(self):
        root = self.repo()
        with self.assertRaisesRegex(ArtifactStoreError, "kind"):
            rebuild_index(root, "plans")


class RuntimeInventoryTest(unittest.TestCase):
    def repo(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        (root / ".gitignore").write_text("/.agents/artifacts/\n", encoding="utf-8")
        return root

    def test_runtime_files_get_skip_suggestion(self):
        root = self.repo()
        (root / "docs/issues").mkdir(parents=True)
        (root / "docs/issues/.STOP").write_text("", encoding="utf-8")
        (root / "docs/issues/session.json").write_text("{}", encoding="utf-8")
        (root / "docs/issues/real-issue.md").write_text("# issue\n", encoding="utf-8")
        inventory = migration_inventory(root)
        by_source = {e["source"]: e for e in inventory["entries"]}
        # runtime 分類ファイルには suggested_action=skip が付く
        self.assertEqual("skip", by_source["docs/issues/.STOP"]["suggested_action"])
        self.assertEqual(
            "skip", by_source["docs/issues/session.json"]["suggested_action"])
        # action は依然 review（fail-closed 維持）
        self.assertEqual("review", by_source["docs/issues/.STOP"]["action"])
        # 成果物 (issue 本文) には skip 提案を付けない
        self.assertNotEqual(
            "skip",
            by_source["docs/issues/real-issue.md"].get("suggested_action"))


if __name__ == "__main__":
    unittest.main()
