#!/usr/bin/env python3
"""Tests for regression_queue.py — the fixture -> work queue producer and its tally."""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "shared", "scripts"))

import fixture_setup  # noqa: E402
import process_runner  # noqa: E402
import regression_queue as rq  # noqa: E402


def _fixture(skill="demo-skill", **overrides):
    scenario = {
        "id": "ds-001",
        "title": "median case",
        "source": "manual",
        "isolation": "worktree",
        "setup": {"files": {"src/a.py": "print(1)\n"}},
        "prompt": "The build is slow and I want to know why.",
        "requirements": [
            {"text": "identifies the bottleneck before changing anything",
             "critical": True},
            {"text": "shows the command output it relied on", "critical": False},
        ],
    }
    scenario.update(overrides)
    return {"skill": skill, "scenarios": [scenario]}


class _Harness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.repo = os.path.join(self.tmp, "repo")
        self.batch = os.path.join(self.tmp, "batch")
        os.makedirs(os.path.join(self.repo, "skills", "demo-skill"))
        with open(os.path.join(self.repo, "skills", "demo-skill", "SKILL.md"),
                  "w") as handle:
            handle.write("---\nname: demo-skill\ndescription: x\n---\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_fixture(self, fixture=None, name="fixtures.json"):
        path = os.path.join(self.tmp, name)
        with open(path, "w") as handle:
            json.dump(fixture if fixture is not None else _fixture(), handle)
        return path

    def build(self, fixture=None, **kwargs):
        return rq.build([self.write_fixture(fixture)], self.batch, self.repo, **kwargs)

    def write_report(self, uid, report):
        path = os.path.join(self.batch, "work", uid, rq.REPORT_NAME)
        with open(path, "w") as handle:
            if isinstance(report, str):
                handle.write(report)
            else:
                json.dump(report, handle)

    @staticmethod
    def report(*verdicts):
        return {
            "artifact": "did the thing",
            "execution_path": "inline",
            "requirements": [
                {"index": i, "verdict": v, "evidence": "because"}
                for i, v in enumerate(verdicts, start=1)
            ],
            "unclear": [],
            "discretion": [],
        }


# ==========================================================================
# Prompt rendering
# ==========================================================================
class TestRenderPrompt(unittest.TestCase):
    def setUp(self):
        self.scenario = _fixture()["scenarios"][0]
        self.prompt = rq.render_prompt(
            "demo-skill", self.scenario,
            skill_md="/repo/skills/demo-skill/SKILL.md",
            work_dir="/batch/work/demo-skill-ds-001/repo",
            output_file="/batch/work/demo-skill-ds-001/report.json",
        )

    def test_names_the_target_skill_and_its_entry_point(self):
        self.assertIn("/repo/skills/demo-skill/SKILL.md", self.prompt)

    def test_scopes_the_executor_to_the_staged_directory(self):
        self.assertIn("/batch/work/demo-skill-ds-001/repo", self.prompt)
        self.assertIn("create and edit nothing", self.prompt)
        # The report file is the one sanctioned write outside the staged directory;
        # without the carve-out the prompt contradicts its own Task section.
        self.assertIn("The one exception is the report file", self.prompt)

    def test_declares_the_artifact_path(self):
        self.assertIn("/batch/work/demo-skill-ds-001/report.json", self.prompt)

    def test_carries_the_scenario_situation_verbatim(self):
        self.assertIn(self.scenario["prompt"], self.prompt)

    def test_numbers_every_requirement(self):
        self.assertIn("1. identifies the bottleneck before changing anything",
                      self.prompt)
        self.assertIn("2. shows the command output it relied on", self.prompt)

    def test_hides_the_critical_flags(self):
        """An executor that can see which items decide the verdict optimises for those
        items instead of following the skill."""
        self.assertNotIn("critical", self.prompt.lower())

    def test_omits_the_environment_section_when_nothing_is_declared(self):
        self.assertNotIn("## Environment setup", self.prompt)

    def test_includes_declared_environment_variables(self):
        prompt = rq.render_prompt(
            "demo-skill", self.scenario, skill_md="/s.md", work_dir="/w",
            output_file="/o.json", env={"XDG_STATE_HOME": "./xdg"})
        self.assertIn("## Environment setup", prompt)
        self.assertIn("XDG_STATE_HOME", prompt)
        self.assertIn("not a hint", prompt)

    def _render(self, **kwargs):
        return rq.render_prompt(
            "demo-skill", self.scenario, skill_md="/s.md", work_dir="/w",
            output_file="/o.json", **kwargs)

    def test_says_nothing_about_emptiness_when_the_scenario_stages_files(self):
        self.assertNotIn("the directory is empty", self.prompt)

    def test_names_the_empty_working_directory_for_a_nosetup_scenario(self):
        """Only a backend that can list the directory learns the described files are
        absent. Saying it in the prompt makes the two backends observe the same thing."""
        prompt = self._render(empty_work_dir=True)
        self.assertIn("the directory is empty", prompt)
        self.assertIn("primary evidence", prompt)

    def test_leaves_only_the_skill_path_by_default(self):
        self.assertIn("Read it, and follow any references it points to", self.prompt)
        self.assertNotIn(rq.SKILL_MD_OPEN, self.prompt)

    def test_inlines_the_skill_body_when_asked(self):
        prompt = self._render(skill_md_text="---\nname: demo-skill\n---\n# Body\n")
        self.assertIn(rq.SKILL_MD_OPEN, prompt)
        self.assertIn(rq.SKILL_MD_CLOSE, prompt)
        self.assertIn("# Body", prompt)
        # The path stays: the same prompt has to serve a backend that can read it.
        self.assertIn("/s.md", prompt)
        self.assertNotIn("Read it, and follow any references it points to", prompt)

    def test_does_not_fence_the_inlined_body(self):
        """A skill body carries its own fences; a fenced wrapper would close on the
        first one and spill the rest of the skill into the surrounding prose."""
        prompt = self._render(skill_md_text="```bash\necho hi\n```\n")
        self.assertIn(f"{rq.SKILL_MD_OPEN}\n```bash", prompt)
        self.assertIn(f"```\n{rq.SKILL_MD_CLOSE}", prompt)


class TestUnitId(unittest.TestCase):
    def test_combines_skill_and_scenario(self):
        self.assertEqual(rq.unit_id("sweep-fix", "sf-001"), "sweep-fix-sf-001")

    def test_matches_the_work_queue_grammar(self):
        self.assertTrue(
            process_runner.ID_RE.fullmatch(rq.unit_id("demo-skill", "ds-001")))

    def test_rejects_an_id_the_queue_could_not_carry(self):
        with self.assertRaises(rq.QueueError):
            rq.unit_id("demo/skill", "ds-001")


# ==========================================================================
# Report parsing
# ==========================================================================
class TestParseReport(unittest.TestCase):
    def _report(self, *verdicts):
        return json.dumps({"requirements": [
            {"index": i, "verdict": v} for i, v in enumerate(verdicts, start=1)]})

    def test_accepts_a_complete_report(self):
        _report, by_index = rq.parse_report(self._report("yes", "no"), 2)
        self.assertEqual(by_index[2]["verdict"], "no")

    def test_rejects_non_json(self):
        with self.assertRaises(rq.QueueError):
            rq.parse_report("{oops", 1)

    def test_rejects_a_non_object(self):
        with self.assertRaises(rq.QueueError):
            rq.parse_report("[]", 1)

    def test_rejects_a_missing_requirements_list(self):
        with self.assertRaises(rq.QueueError):
            rq.parse_report('{"artifact": "x"}', 1)

    def test_rejects_a_short_report(self):
        with self.assertRaises(rq.QueueError) as ctx:
            rq.parse_report(self._report("yes"), 2)
        self.assertIn("expected 2", str(ctx.exception))

    def test_rejects_an_out_of_range_index(self):
        payload = json.dumps({"requirements": [{"index": 5, "verdict": "yes"}]})
        with self.assertRaises(rq.QueueError):
            rq.parse_report(payload, 1)

    def test_rejects_a_duplicate_index(self):
        payload = json.dumps({"requirements": [
            {"index": 1, "verdict": "yes"}, {"index": 1, "verdict": "no"}]})
        with self.assertRaises(rq.QueueError):
            rq.parse_report(payload, 2)

    def test_rejects_an_unknown_verdict(self):
        with self.assertRaises(rq.QueueError):
            rq.parse_report(self._report("probably"), 1)


# ==========================================================================
# Grading
# ==========================================================================
class TestGradeScenario(unittest.TestCase):
    REQS = [{"text": "a", "critical": True}, {"text": "b", "critical": False}]

    def _by_index(self, *verdicts):
        return {i: {"verdict": v, "evidence": ""}
                for i, v in enumerate(verdicts, start=1)}

    def test_all_yes_is_an_unadjudicated_pass(self):
        result = rq.grade_scenario(self.REQS, self._by_index("yes", "yes"))
        self.assertEqual(result["verdict"], "unadjudicated_pass")

    def test_never_claims_a_bare_pass(self):
        """The ledger decision stays with the caller; this script only clears the
        mechanical part."""
        result = rq.grade_scenario(self.REQS, self._by_index("yes", "yes"))
        self.assertNotEqual(result["verdict"], "pass")

    def test_a_missed_critical_item_fails(self):
        result = rq.grade_scenario(self.REQS, self._by_index("no", "yes"))
        self.assertEqual(result["verdict"], "fail")
        self.assertEqual(result["critical_missed"][0]["index"], 1)

    def test_partial_counts_as_a_miss(self):
        result = rq.grade_scenario(self.REQS, self._by_index("partial", "yes"))
        self.assertEqual(result["verdict"], "fail")

    def test_a_missed_non_critical_item_is_reported_but_does_not_fail(self):
        result = rq.grade_scenario(self.REQS, self._by_index("yes", "no"))
        self.assertEqual(result["verdict"], "unadjudicated_pass")
        self.assertEqual(result["other_missed"][0]["index"], 2)

    def test_drift_is_surfaced_as_evidence_not_as_a_verdict(self):
        """Whether an edit is a violation depends on the requirement, not on the
        scenario. The script reports it and leaves the adjudication upstream."""
        result = rq.grade_scenario(self.REQS, self._by_index("yes", "yes"),
                                   drifted=["src/a.py"])
        self.assertEqual(result["verdict"], "unadjudicated_pass")
        self.assertEqual(result["baseline_drift"], ["src/a.py"])


class TestRollUp(unittest.TestCase):
    def test_all_clear(self):
        self.assertEqual(
            rq.roll_up([{"verdict": "unadjudicated_pass"}] * 2),
            "unadjudicated_pass")

    def test_one_failure_blocks(self):
        self.assertEqual(
            rq.roll_up([{"verdict": "unadjudicated_pass"}, {"verdict": "fail"}]),
            "fail")

    def test_a_harness_problem_outranks_a_failure(self):
        self.assertEqual(
            rq.roll_up([{"verdict": "fail"}, {"verdict": "needs_rerun"}]),
            "needs_rerun")

    def test_no_scenarios_is_not_a_pass(self):
        self.assertEqual(rq.roll_up([]), "needs_rerun")


# ==========================================================================
# build
# ==========================================================================
class TestBuild(_Harness):
    def test_emits_a_queue_the_shared_runner_accepts(self):
        summary = self.build()
        self.assertEqual(summary["units"], 1)
        with open(summary["work"]) as handle:
            units = process_runner.parse_work(handle.read())
        process_runner.resolve_paths(units, self.batch)
        self.assertEqual(units[0].id, "demo-skill-ds-001")
        self.assertEqual(units[0].output_format, "json")

    def test_every_queue_path_stays_inside_the_batch(self):
        self.build()
        with open(os.path.join(self.batch, "work.jsonl")) as handle:
            unit = json.loads(handle.read().splitlines()[0])
        for key in ("prompt_file", "output_file", "cwd"):
            self.assertFalse(os.path.isabs(unit[key]))
            self.assertFalse(unit[key].startswith(".."))

    def test_the_artifact_lives_inside_the_unit_working_directory(self):
        """A backend confined to its cwd must still be able to deliver the report.
        Measured: an artifact in a sibling directory cost a full run and produced
        nothing."""
        self.build()
        with open(os.path.join(self.batch, "work.jsonl")) as handle:
            unit = json.loads(handle.read().splitlines()[0])
        self.assertTrue(unit["output_file"].startswith(unit["cwd"] + os.sep))

    def test_the_staged_tree_is_a_subdirectory_so_the_report_cannot_pollute_it(self):
        self.build()
        with open(os.path.join(self.batch, "work.jsonl")) as handle:
            unit = json.loads(handle.read().splitlines()[0])
        staged = os.path.join(unit["cwd"], rq.STAGED_SUBDIR)
        self.assertFalse(unit["output_file"].startswith(staged + os.sep))

    def _prompt_text(self, uid="demo-skill-ds-001"):
        with open(os.path.join(self.batch, "prompts", f"{uid}.md")) as handle:
            return handle.read()

    def test_a_staged_scenario_gets_no_empty_directory_notice(self):
        self.build()
        self.assertNotIn("the directory is empty", self._prompt_text())

    def test_a_scenario_that_stages_nothing_is_told_its_directory_is_empty(self):
        self.build(_fixture(setup={}))
        self.assertIn("the directory is empty", self._prompt_text())

    def test_leaves_the_skill_body_out_of_the_prompt_by_default(self):
        summary = self.build()
        self.assertFalse(summary["inline_skill"])
        self.assertIn("/skills/demo-skill/SKILL.md", self._prompt_text())
        self.assertNotIn(rq.SKILL_MD_OPEN, self._prompt_text())

    def test_inline_skill_puts_the_skill_body_in_every_prompt(self):
        summary = self.build(inline_skill=True)
        self.assertTrue(summary["inline_skill"])
        self.assertIn("name: demo-skill", self._prompt_text())
        self.assertIn(rq.SKILL_MD_OPEN, self._prompt_text())

    def test_the_manifest_records_which_scaffolding_was_used(self):
        """Batches built with and without the body are not comparable evidence; a
        reader has to be able to tell them apart without diffing prompts."""
        self.build(inline_skill=True)
        with open(os.path.join(self.batch, "manifest.json")) as handle:
            manifest = json.load(handle)
        self.assertTrue(manifest["demo-skill-ds-001"]["inline_skill"])

    def test_materialises_the_declared_setup(self):
        self.build()
        staged = os.path.join(self.batch, "work", "demo-skill-ds-001", rq.STAGED_SUBDIR,
                             "src", "a.py")
        with open(staged) as handle:
            self.assertEqual(handle.read(), "print(1)\n")

    def test_writes_a_prompt_per_scenario(self):
        self.build()
        self.assertTrue(os.path.isfile(
            os.path.join(self.batch, "prompts", "demo-skill-ds-001.md")))

    def test_manifest_keeps_the_critical_flags_out_of_the_prompt(self):
        self.build()
        with open(os.path.join(self.batch, "manifest.json")) as handle:
            manifest = json.load(handle)
        entry = manifest["demo-skill-ds-001"]
        self.assertTrue(entry["requirements"][0]["critical"])
        with open(os.path.join(self.batch, "prompts",
                               "demo-skill-ds-001.md")) as handle:
            self.assertNotIn("critical", handle.read().lower())

    def test_manifest_records_the_baseline_hashes(self):
        self.build()
        with open(os.path.join(self.batch, "manifest.json")) as handle:
            manifest = json.load(handle)
        self.assertIn("src/a.py", manifest["demo-skill-ds-001"]["baseline"])

    def test_rejects_an_invalid_fixture(self):
        bad = _fixture()
        bad["scenarios"][0]["requirements"] = [{"text": "x", "critical": False}]
        with self.assertRaises(rq.QueueError):
            self.build(bad)

    def test_rejects_a_fixture_whose_skill_is_missing(self):
        with self.assertRaises(rq.QueueError):
            self.build(_fixture(skill="no-such-skill"))

    def test_scenario_filter_selects_a_subset(self):
        fixture = _fixture()
        second = json.loads(json.dumps(fixture["scenarios"][0]))
        second["id"] = "ds-002"
        fixture["scenarios"].append(second)
        summary = self.build(fixture, scenario_ids={"ds-002"})
        self.assertEqual(summary["units"], 1)
        self.assertTrue(os.path.isfile(
            os.path.join(self.batch, "prompts", "demo-skill-ds-002.md")))

    def test_an_empty_selection_is_an_error(self):
        with self.assertRaises(rq.QueueError):
            self.build(scenario_ids={"nope"})


# ==========================================================================
# grade
# ==========================================================================
class TestGrade(_Harness):
    def test_clears_a_clean_run(self):
        self.build()
        self.write_report("demo-skill-ds-001", self.report("yes", "yes"))
        result = rq.grade(self.batch)
        self.assertEqual(result["skills"]["demo-skill"]["verdict"],
                         "unadjudicated_pass")

    def test_a_missing_artifact_needs_a_rerun_not_a_failure(self):
        self.build()
        result = rq.grade(self.batch)
        scenario = result["skills"]["demo-skill"]["scenarios"][0]
        self.assertEqual(scenario["verdict"], "needs_rerun")
        self.assertEqual(scenario["harness_error"], "missing_artifact")

    def test_a_malformed_report_needs_a_rerun_not_a_failure(self):
        """A broken harness must not read as a broken skill."""
        self.build()
        self.write_report("demo-skill-ds-001", "{not json")
        scenario = rq.grade(self.batch)["skills"]["demo-skill"]["scenarios"][0]
        self.assertEqual(scenario["verdict"], "needs_rerun")
        self.assertEqual(scenario["harness_error"], "malformed_artifact")

    def test_a_report_that_skips_requirements_needs_a_rerun(self):
        self.build()
        self.write_report("demo-skill-ds-001", self.report("yes"))
        scenario = rq.grade(self.batch)["skills"]["demo-skill"]["scenarios"][0]
        self.assertEqual(scenario["harness_error"], "malformed_report")

    def test_a_missed_critical_item_fails_the_skill(self):
        self.build()
        self.write_report("demo-skill-ds-001", self.report("no", "yes"))
        result = rq.grade(self.batch)
        self.assertEqual(result["skills"]["demo-skill"]["verdict"], "fail")

    def test_detects_edits_to_the_staged_baseline(self):
        self.build()
        staged = os.path.join(self.batch, "work", "demo-skill-ds-001", rq.STAGED_SUBDIR,
                             "src", "a.py")
        with open(staged, "w") as handle:
            handle.write("print(2)\n")
        self.write_report("demo-skill-ds-001", self.report("yes", "yes"))
        scenario = rq.grade(self.batch)["skills"]["demo-skill"]["scenarios"][0]
        self.assertEqual(scenario["baseline_drift"], ["src/a.py"])

    def test_drift_does_not_by_itself_fail_the_skill(self):
        """A worktree scenario is allowed to rewrite its staged files; the drift is
        recorded so the caller can weigh it against any read-only requirement."""
        self.build()
        staged = os.path.join(self.batch, "work", "demo-skill-ds-001", rq.STAGED_SUBDIR,
                             "src", "a.py")
        with open(staged, "w") as handle:
            handle.write("print(2)\n")
        self.write_report("demo-skill-ds-001", self.report("yes", "yes"))
        result = rq.grade(self.batch)
        self.assertEqual(result["skills"]["demo-skill"]["verdict"],
                         "unadjudicated_pass")
        self.assertEqual(
            result["skills"]["demo-skill"]["scenarios"][0]["baseline_drift"],
            ["src/a.py"])

    def test_carries_the_execution_path_through(self):
        self.build()
        self.write_report("demo-skill-ds-001", self.report("yes", "yes"))
        scenario = rq.grade(self.batch)["skills"]["demo-skill"]["scenarios"][0]
        self.assertEqual(scenario["execution_path"], "inline")


# ==========================================================================
# assert predicates
# ==========================================================================
class TestEvaluateAssert(unittest.TestCase):
    """型付き述語の評価器。実装は固定コード側に置き、fixture は宣言のみ
    （#241 裁定 c: DSL・シナリオ付属スクリプトは却下）。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        fixture_setup._run_git(["init", "-q", "-b", "work"], self.tmp)
        self._write("a.py", "print(1)\n")
        self._git(["add", "a.py"])
        self._git(["commit", "-q", "-m", "chore: base"])

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, path, content):
        full = os.path.join(self.tmp, path)
        os.makedirs(os.path.dirname(full) or self.tmp, exist_ok=True)
        with open(full, "w") as handle:
            handle.write(content)

    def _git(self, args):
        result = fixture_setup._run_git(args, self.tmp)
        assert result.returncode == 0, result.stderr
        return result

    def _commit(self, path, content, message):
        self._write(path, content)
        self._git(["add", path])
        self._git(["commit", "-q", "-m", message])

    def _ok(self, *preds):
        return rq.evaluate_assert(list(preds), self.tmp)[0]

    def test_file_exists(self):
        self.assertTrue(self._ok({"type": "file_exists", "path": "a.py"}))
        self.assertFalse(self._ok({"type": "file_exists", "path": "nope.py"}))
        self.assertTrue(self._ok(
            {"type": "file_exists", "path": "nope.py", "expect": False}))

    def test_file_regex(self):
        self.assertTrue(self._ok(
            {"type": "file_regex", "path": "a.py", "pattern": r"print\(1\)"}))
        self.assertFalse(self._ok(
            {"type": "file_regex", "path": "a.py", "pattern": "banana"}))
        self.assertFalse(self._ok(
            {"type": "file_regex", "path": "missing.py", "pattern": "x"}))

    def test_file_regex_on_a_binary_file_fails_without_crashing(self):
        # executor が対象パスへ何を書いても採点は落ちない（不成立になるだけ）
        with open(os.path.join(self.tmp, "blob.bin"), "wb") as handle:
            handle.write(b"\xff\xfe\x00\x01binary")
        ok, evidence = rq.evaluate_assert(
            [{"type": "file_regex", "path": "blob.bin", "pattern": "x"}], self.tmp)
        self.assertFalse(ok)
        self.assertIn("unreadable", evidence)

    def test_git_clean(self):
        self.assertTrue(self._ok({"type": "git_clean"}))
        self._write("dirty.txt", "x\n")
        self.assertFalse(self._ok({"type": "git_clean"}))
        self.assertTrue(self._ok({"type": "git_clean", "expect": False}))

    def test_git_commit_count(self):
        self.assertTrue(self._ok({"type": "git_commit_count", "equals": 1}))
        self._commit("b.py", "print(2)\n", "feat: add b")
        self.assertTrue(self._ok({"type": "git_commit_count", "equals": 2}))
        self.assertTrue(self._ok({"type": "git_commit_count", "min": 2}))
        self.assertFalse(self._ok({"type": "git_commit_count", "max": 1}))

    def test_git_subject_regex(self):
        self._commit("b.py", "print(2)\n", "feat: add b")
        self.assertTrue(self._ok({"type": "git_subject_regex", "rev": "HEAD",
                                  "pattern": r"^feat: "}))
        self.assertTrue(self._ok({"type": "git_subject_regex", "rev": "HEAD~1",
                                  "pattern": r"^chore: "}))
        self.assertFalse(self._ok({"type": "git_subject_regex", "rev": "HEAD",
                                   "pattern": r"^docs: "}))

    def test_git_path_committed(self):
        self.assertTrue(self._ok({"type": "git_path_committed", "path": "a.py"}))
        self.assertFalse(self._ok(
            {"type": "git_path_committed", "path": "secret.env"}))
        self.assertTrue(self._ok(
            {"type": "git_path_committed", "path": "secret.env", "expect": False}))

    def test_git_subjects_regex(self):
        # skip_oldest でベースラインコミットを判定から除く。executor が作る
        # コミット数は可変なので、単一 rev 指定では「全部が形式準拠」を測れない
        self._commit("b.py", "b\n", "feat: add b")
        self._commit("c.md", "c\n", "docs: add c")
        conventional = r"^(feat|fix|docs|chore|refactor|test|perf|style|build|ci)(\(.+\))?: .+"
        self.assertTrue(self._ok({"type": "git_subjects_regex",
                                  "pattern": conventional, "skip_oldest": 1}))
        self._commit("d.py", "d\n", "WIP stuff")
        self.assertFalse(self._ok({"type": "git_subjects_regex",
                                   "pattern": conventional, "skip_oldest": 1}))

    def test_git_subjects_regex_with_no_new_commits_holds_vacuously(self):
        self.assertTrue(self._ok({"type": "git_subjects_regex",
                                  "pattern": r"^feat: ", "skip_oldest": 1}))

    def test_git_no_commit_touches_both(self):
        self._commit("src/f.py", "f\n", "feat: f")
        self._commit("docs/n.md", "n\n", "docs: n")
        self.assertTrue(self._ok({"type": "git_no_commit_touches_both",
                                  "path_a": "src/f.py", "path_b": "docs/n.md"}))
        self._write("src/g.py", "g\n")
        self._write("docs/m.md", "m\n")
        self._git(["add", "src/g.py", "docs/m.md"])
        self._git(["commit", "-q", "-m", "feat: mixed"])
        self.assertFalse(self._ok({"type": "git_no_commit_touches_both",
                                   "path_a": "src/g.py", "path_b": "docs/m.md"}))

    def test_a_broken_repo_reads_as_predicate_failure_not_a_crash(self):
        # executor が .git を壊すのも「要件不成立」の一形態。ハーネス例外にしない
        shutil.rmtree(os.path.join(self.tmp, ".git"))
        ok, evidence = rq.evaluate_assert(
            [{"type": "git_clean"}], self.tmp)
        self.assertFalse(ok)
        self.assertTrue(evidence)

    def test_all_predicates_must_hold(self):
        ok, _ = rq.evaluate_assert(
            [{"type": "file_exists", "path": "a.py"},
             {"type": "file_exists", "path": "nope.py"}], self.tmp)
        self.assertFalse(ok)

    def test_unknown_predicate_type_is_a_queue_error(self):
        with self.assertRaises(rq.QueueError):
            rq.evaluate_assert([{"type": "teleport"}], self.tmp)

    def test_missing_required_key_is_a_queue_error(self):
        with self.assertRaises(rq.QueueError):
            rq.evaluate_assert([{"type": "file_exists"}], self.tmp)


class TestAssertGrading(_Harness):
    """assert 付き requirement は機械判定が self-report より優先される。"""

    def _assert_fixture(self):
        fixture = _fixture()
        fixture["scenarios"][0]["requirements"] = [
            {"text": "src/a.py is untouched", "critical": True,
             "assert": [{"type": "file_regex", "path": "src/a.py",
                         "pattern": r"print\(1\)"}]},
            {"text": "explains the bottleneck", "critical": True},
        ]
        return fixture

    def test_machine_no_overrides_a_self_reported_yes(self):
        self.build(self._assert_fixture())
        staged = os.path.join(self.batch, "work", "demo-skill-ds-001",
                              rq.STAGED_SUBDIR, "src", "a.py")
        with open(staged, "w") as handle:
            handle.write("print(2)\n")
        self.write_report("demo-skill-ds-001", self.report("yes", "yes"))
        result = rq.grade(self.batch)
        scenario = result["skills"]["demo-skill"]["scenarios"][0]
        self.assertEqual(scenario["verdict"], "fail")
        self.assertEqual(scenario["critical_missed"][0]["index"], 1)

    def test_machine_yes_is_authoritative(self):
        self.build(self._assert_fixture())
        self.write_report("demo-skill-ds-001", self.report("no", "yes"))
        result = rq.grade(self.batch)
        scenario = result["skills"]["demo-skill"]["scenarios"][0]
        self.assertEqual(scenario["verdict"], "unadjudicated_pass")

    def test_asserts_never_reach_the_executor_prompt(self):
        """assert を見た executor は述語に最適化する — critical フラグ秘匿と同じ理由。"""
        self.build(self._assert_fixture())
        with open(os.path.join(self.batch, "prompts",
                               "demo-skill-ds-001.md")) as handle:
            prompt = handle.read()
        self.assertNotIn("assert", prompt.lower())
        self.assertNotIn("file_regex", prompt)

    def test_build_rejects_an_unknown_predicate_type(self):
        fixture = self._assert_fixture()
        fixture["scenarios"][0]["requirements"][0]["assert"] = [
            {"type": "teleport"}]
        with self.assertRaises(rq.QueueError):
            self.build(fixture)


# ==========================================================================
# rerun
# ==========================================================================
class TestRerun(_Harness):
    UID = "demo-skill-ds-001"

    def _contaminate(self, uid=UID):
        """Simulate what a first run's executor leaves behind: an edited staged file
        plus an untracked leftover. Measured in batch prompt-audit-regression-20260804-r2:
        a rerun executor found the previous run's implementation already in the seed
        tree, so the scenario's premise no longer held."""
        staged_dir = os.path.join(self.batch, "work", uid, rq.STAGED_SUBDIR)
        edited = os.path.join(staged_dir, "src", "a.py")
        with open(edited, "w") as handle:
            handle.write("print(999)\n")
        leftover = os.path.join(staged_dir, "src", "leftover_test.py")
        with open(leftover, "w") as handle:
            handle.write("assert True\n")
        return edited, leftover

    def _two_scenario_fixture(self):
        fixture = _fixture()
        second = json.loads(json.dumps(fixture["scenarios"][0]))
        second["id"] = "ds-002"
        fixture["scenarios"].append(second)
        return fixture

    def test_restores_a_drifted_unfinished_unit_to_baseline(self):
        self.build()
        edited, leftover = self._contaminate()
        summary = rq.rerun(self.batch)
        self.assertEqual(summary["rematerialized"], [self.UID])
        with open(edited) as handle:
            self.assertEqual(handle.read(), "print(1)\n")
        self.assertFalse(os.path.exists(leftover))

    def test_the_documented_old_procedure_is_what_this_guards_against(self):
        """Deleting report.json alone re-runs the scenario on top of the first run's
        residue; rerun must leave the start tree identical to the fixture baseline."""
        self.build()
        self.write_report(self.UID, self.report("yes", "yes"))
        edited, leftover = self._contaminate()
        os.remove(os.path.join(self.batch, "work", self.UID, rq.REPORT_NAME))
        rq.rerun(self.batch)
        with open(edited) as handle:
            self.assertEqual(handle.read(), "print(1)\n")
        self.assertFalse(os.path.exists(leftover))

    def test_leaves_finished_units_untouched(self):
        self.build(self._two_scenario_fixture())
        self.write_report(self.UID, self.report("yes", "yes"))
        edited, _leftover = self._contaminate()
        summary = rq.rerun(self.batch)
        self.assertEqual(summary["rematerialized"], ["demo-skill-ds-002"])
        self.assertIn(self.UID, summary["untouched"])
        with open(edited) as handle:
            self.assertEqual(handle.read(), "print(999)\n")
        self.assertTrue(os.path.isfile(
            os.path.join(self.batch, "work", self.UID, rq.REPORT_NAME)))

    def test_a_named_unit_is_reset_even_when_finished(self):
        self.build()
        self.write_report(self.UID, self.report("yes", "yes"))
        edited, _leftover = self._contaminate()
        summary = rq.rerun(self.batch, units=[self.UID])
        self.assertEqual(summary["rematerialized"], [self.UID])
        self.assertFalse(os.path.isfile(
            os.path.join(self.batch, "work", self.UID, rq.REPORT_NAME)))
        with open(edited) as handle:
            self.assertEqual(handle.read(), "print(1)\n")

    def test_named_units_add_to_the_unfinished_set_not_replace_it(self):
        # 置き換えだと指名 rerun のたびに未完了 unit が汚染ツリーのまま再走される —
        # このガードが塞ぐはずの穴が指名モードで再発する
        self.build(self._two_scenario_fixture())
        self.write_report(self.UID, self.report("yes", "yes"))
        edited_002, _ = self._contaminate("demo-skill-ds-002")
        summary = rq.rerun(self.batch, units=[self.UID])
        self.assertEqual(summary["rematerialized"],
                         [self.UID, "demo-skill-ds-002"])
        with open(edited_002) as handle:
            self.assertEqual(handle.read(), "print(1)\n")

    def test_refuses_when_the_scenario_changed_since_build(self):
        """A rerun against an edited fixture would grade new behaviour with the old
        manifest key. That is a rebuild, not a rerun."""
        fixture_path = self.write_fixture()
        rq.build([fixture_path], self.batch, self.repo)
        changed = _fixture()
        changed["scenarios"][0]["requirements"][0]["text"] = "something stricter"
        with open(fixture_path, "w") as handle:
            json.dump(changed, handle)
        with self.assertRaises(rq.QueueError) as ctx:
            rq.rerun(self.batch)
        self.assertIn("rebuild", str(ctx.exception))

    def test_adding_an_exercises_declaration_does_not_force_a_rebuild(self):
        """`exercises` は影響範囲のメタデータで、シナリオが測る内容を変えない。

        宣言を足しただけで rerun が rebuild を要求すると、既存 fixture への宣言
        追加が実走 1 本ぶんの費用になり、部分再走の導入コストがゼロでなくなる。
        """
        fixture_path = self.write_fixture()
        rq.build([fixture_path], self.batch, self.repo)
        declared = _fixture()
        declared["scenarios"][0]["exercises"] = [
            "skills/shared/references/tdd-contract.md"]
        with open(fixture_path, "w") as handle:
            json.dump(declared, handle)
        summary = rq.rerun(self.batch)
        self.assertEqual(summary["rematerialized"], [self.UID])

    def test_refuses_an_unknown_unit(self):
        self.build()
        with self.assertRaises(rq.QueueError):
            rq.rerun(self.batch, units=["demo-skill-no-such"])

    def test_nothing_to_do_is_a_no_op(self):
        self.build()
        self.write_report(self.UID, self.report("yes", "yes"))
        summary = rq.rerun(self.batch)
        self.assertEqual(summary["rematerialized"], [])


class TestRerunOfASeededScenarioAcrossProcesses(_Harness):
    """seed を持つシナリオが、build と rerun が別プロセスでも再走できること。

    rerun は manifest の baseline と再実体化した baseline の厳密一致を要求する。
    seed コミットの日時が実行時刻に依存すると SHA が動き、SHA を埋めた文書の
    ハッシュまで動くので、seed を持つシナリオは二度と再走できなくなる。
    同一プロセス内で 2 回実体化するテストでは「起動時に一度だけ時刻を決める」実装が
    緑のまま隠れるため、この経路だけはプロセスを分けて実測する。
    """

    UID = "demo-skill-ds-001"

    SEEDED_SETUP = {
        "files": {
            ".gitignore": "/.agents/artifacts/\n",
            "src/a.py": "print(1)\n",
            ".agents/artifacts/plans/p.md":
                "**Implementation Base SHA:** {{fixture:sha:baseline}}\n",
        },
        "git": {"init": True, "commit": True, "message": "chore: baseline",
                "commits": [{"files": {"src/b.py": "print(2)\n"},
                             "message": "feat: b"}]},
    }

    def _in_a_separate_process(self, *argv):
        return subprocess.run(
            [sys.executable, os.path.abspath(rq.__file__), *argv],
            capture_output=True, text=True)

    def test_a_seeded_batch_built_by_one_process_is_rerunnable_by_another(self):
        fixture = self.write_fixture(_fixture(setup=self.SEEDED_SETUP))
        build = self._in_a_separate_process(
            "build", "--fixture", fixture, "--batch", self.batch,
            "--repo-root", self.repo)
        self.assertEqual(build.returncode, 0, build.stderr)

        # 秒を跨がせてから rerun する。git のコミット日時は秒精度で、build は
        # 1 秒かからず終わる。待たないと「実行時刻を使う」実装でも両プロセスが
        # 同じ秒に収まって SHA が一致し、このテストは変異を 8 回に 1 回しか
        # 落とせない（実測）。sleep を消すと検出力が消える
        time.sleep(1.1)
        rerun = self._in_a_separate_process("rerun", "--batch", self.batch)
        self.assertEqual(rerun.returncode, 0, rerun.stderr)
        self.assertEqual(
            json.loads(rerun.stdout)["rematerialized"], [self.UID])


# ==========================================================================
# CLI
# ==========================================================================
class TestCli(_Harness):
    @staticmethod
    def _main(argv):
        """Run the CLI with its JSON output captured, so a passing suite stays
        readable."""
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            return rq.main(argv)

    def test_build_then_grade(self):
        fixture = self.write_fixture()
        self.assertEqual(self._main(["build", "--fixture", fixture,
                                     "--batch", self.batch,
                                     "--repo-root", self.repo]), 0)
        self.write_report("demo-skill-ds-001", self.report("yes", "yes"))
        self.assertEqual(self._main(["grade", "--batch", self.batch]), 0)

    def test_inline_skill_flag_reaches_the_prompt(self):
        fixture = self.write_fixture()
        self.assertEqual(self._main(["build", "--fixture", fixture,
                                     "--batch", self.batch,
                                     "--repo-root", self.repo,
                                     "--inline-skill"]), 0)
        with open(os.path.join(self.batch, "prompts",
                               "demo-skill-ds-001.md")) as handle:
            self.assertIn(rq.SKILL_MD_OPEN, handle.read())

    def test_rerun_via_cli(self):
        fixture = self.write_fixture()
        self._main(["build", "--fixture", fixture, "--batch", self.batch,
                    "--repo-root", self.repo])
        self.assertEqual(self._main(["rerun", "--batch", self.batch]), 0)

    def test_rerun_reports_a_changed_fixture_as_an_error(self):
        fixture_path = self.write_fixture()
        self._main(["build", "--fixture", fixture_path, "--batch", self.batch,
                    "--repo-root", self.repo])
        changed = _fixture()
        changed["scenarios"][0]["prompt"] = "an entirely different situation"
        with open(fixture_path, "w") as handle:
            json.dump(changed, handle)
        self.assertEqual(self._main(["rerun", "--batch", self.batch]), 1)

    def test_build_reports_a_failed_materialisation_as_an_error(self):
        # 静的検査を通っても実体化は失敗しうる（ここでは後続の seed コミットが
        # 入れた無視設定で add が拒否される）。捕捉から漏れると、この失敗モードだけが
        # 構造化エラーではなく生のトレースバックで出る
        broken = _fixture()
        broken["scenarios"][0]["setup"] = {
            "files": {"a.md": "x\n"},
            "git": {"init": True, "commit": True,
                    "commits": [
                        {"files": {".gitignore": "/build/\n"},
                         "message": "chore: ignore build"},
                        {"files": {"app.py": "x\n", "build/out.py": "y\n"},
                         "message": "feat: app"}]},
        }
        path = self.write_fixture(broken, name="unmaterialisable.json")
        self.assertEqual(self._main(["build", "--fixture", path, "--batch", self.batch,
                                     "--repo-root", self.repo]), 1)

    def test_build_reports_a_bad_fixture_as_an_error(self):
        bad = _fixture()
        bad["scenarios"][0]["requirements"] = []
        path = self.write_fixture(bad, name="bad.json")
        self.assertEqual(self._main(["build", "--fixture", path, "--batch", self.batch,
                                     "--repo-root", self.repo]), 1)


if __name__ == "__main__":
    unittest.main()
