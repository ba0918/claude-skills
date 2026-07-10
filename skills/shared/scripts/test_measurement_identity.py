"""measurement_identity.py の unittest。

skills/shared/references/measurement-identity.md の Event Record 契約（§3）を
検証する純関数群（validate_event / make_event / parse_events /
aggregate_by_surface / surface_delta / format_report）と、
skill-regression の ledger.py を再利用する current_surface_sha256 を検証する。
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measurement_identity as mi  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))

_SURFACE_A = "a" * 64
_SURFACE_B = "b" * 64


def _event(**overrides):
    base = {
        "ts": "2026-07-01T00:00:00+00:00",
        "system": "polling-fs",
        "event": "tick",
        "skill": "issue",
        "surface_sha256": _SURFACE_A,
        "run_id": None,
        "outcome": {"claimed": 1, "done": 1, "failed_transient": 0,
                     "failed_permanent": 0},
    }
    base.update(overrides)
    return base


class TestValidateEvent(unittest.TestCase):
    def test_valid_event_has_no_errors(self):
        self.assertEqual(mi.validate_event(_event()), [])

    def test_valid_event_with_uuid_run_id(self):
        event = _event(run_id="123e4567-e89b-12d3-a456-426614174000")
        self.assertEqual(mi.validate_event(event), [])

    def test_invalid_system_is_reported(self):
        errors = mi.validate_event(_event(system="not-a-system"))
        self.assertTrue(errors)

    def test_invalid_event_kind_is_reported(self):
        errors = mi.validate_event(_event(event="not-an-event"))
        self.assertTrue(errors)

    def test_bad_surface_length_is_reported(self):
        errors = mi.validate_event(_event(surface_sha256="abc123"))
        self.assertTrue(errors)

    def test_nested_dict_in_outcome_is_reported(self):
        errors = mi.validate_event(_event(outcome={"nested": {"x": 1}}))
        self.assertTrue(errors)

    def test_nested_list_in_outcome_is_reported(self):
        errors = mi.validate_event(_event(outcome={"nested": [1, 2]}))
        self.assertTrue(errors)

    def test_run_id_null_is_allowed(self):
        self.assertEqual(mi.validate_event(_event(run_id=None)), [])

    def test_run_id_garbage_is_reported(self):
        errors = mi.validate_event(_event(run_id="not-a-uuid"))
        self.assertTrue(errors)

    def test_empty_skill_is_reported(self):
        errors = mi.validate_event(_event(skill=""))
        self.assertTrue(errors)

    def test_outcome_scalar_values_are_allowed(self):
        event = _event(outcome={"recall": 0.9, "note": "ok", "n": None})
        self.assertEqual(mi.validate_event(event), [])


class TestMakeEvent(unittest.TestCase):
    def test_returns_dict_for_valid_input(self):
        result = mi.make_event(
            ts="2026-07-01T00:00:00+00:00", system="polling-fs", event="tick",
            skill="issue", surface_sha256=_SURFACE_A, run_id=None,
            outcome={"claimed": 1, "done": 1},
        )
        self.assertEqual(result["skill"], "issue")
        self.assertEqual(mi.validate_event(result), [])

    def test_raises_value_error_for_invalid_input(self):
        with self.assertRaises(ValueError):
            mi.make_event(
                ts="2026-07-01T00:00:00+00:00", system="bogus", event="tick",
                skill="issue", surface_sha256=_SURFACE_A, run_id=None,
                outcome={},
            )


class TestParseEvents(unittest.TestCase):
    def test_skips_broken_lines_and_reports_them(self):
        text = "\n".join([
            json.dumps(_event()),
            "{not valid json",
            json.dumps(_event(surface_sha256=_SURFACE_B)),
        ])
        events, errors = mi.parse_events(text)
        self.assertEqual(len(events), 2)
        self.assertEqual(len(errors), 1)

    def test_skips_blank_lines(self):
        text = json.dumps(_event()) + "\n\n"
        events, errors = mi.parse_events(text)
        self.assertEqual(len(events), 1)
        self.assertEqual(errors, [])

    def test_reports_schema_invalid_lines(self):
        text = json.dumps(_event(system="bogus"))
        events, errors = mi.parse_events(text)
        self.assertEqual(events, [])
        self.assertEqual(len(errors), 1)


class TestAggregateBySurface(unittest.TestCase):
    def test_aggregates_ticks_by_surface_with_success_rate(self):
        events = [
            _event(surface_sha256=_SURFACE_A, ts="2026-07-01T00:00:00+00:00",
                   outcome={"claimed": 1, "done": 1, "failed_transient": 0,
                             "failed_permanent": 0}),
            _event(surface_sha256=_SURFACE_A, ts="2026-07-01T01:00:00+00:00",
                   outcome={"claimed": 1, "done": 0, "failed_transient": 1,
                             "failed_permanent": 0}),
            _event(surface_sha256=_SURFACE_B, ts="2026-07-02T00:00:00+00:00",
                   outcome={"claimed": 1, "done": 1, "failed_transient": 0,
                             "failed_permanent": 0}),
        ]
        agg = mi.aggregate_by_surface(events, "issue")
        self.assertEqual(len(agg), 2)
        first, second = agg
        self.assertEqual(first["surface_sha256"], _SURFACE_A)
        self.assertEqual(first["ticks"], 2)
        self.assertEqual(first["claimed"], 2)
        self.assertEqual(first["done"], 1)
        self.assertEqual(first["failed"], 1)
        self.assertAlmostEqual(first["success_rate"], 0.5)
        self.assertEqual(first["first_ts"], "2026-07-01T00:00:00+00:00")
        self.assertEqual(first["last_ts"], "2026-07-01T01:00:00+00:00")
        self.assertEqual(second["surface_sha256"], _SURFACE_B)
        self.assertEqual(second["ticks"], 1)

    def test_orders_by_first_ts_ascending_regardless_of_input_order(self):
        events = [
            _event(surface_sha256=_SURFACE_B, ts="2026-07-02T00:00:00+00:00"),
            _event(surface_sha256=_SURFACE_A, ts="2026-07-01T00:00:00+00:00"),
        ]
        agg = mi.aggregate_by_surface(events, "issue")
        self.assertEqual([g["surface_sha256"] for g in agg],
                          [_SURFACE_A, _SURFACE_B])

    def test_filters_by_skill(self):
        events = [
            _event(skill="issue"),
            _event(skill="github-issue"),
        ]
        agg = mi.aggregate_by_surface(events, "issue")
        self.assertEqual(len(agg), 1)

    def test_ignores_non_tick_events(self):
        events = [_event(event="verification")]
        agg = mi.aggregate_by_surface(events, "issue")
        self.assertEqual(agg, [])

    def test_missing_outcome_keys_treated_as_zero(self):
        events = [_event(outcome={})]
        agg = mi.aggregate_by_surface(events, "issue")
        self.assertEqual(agg[0]["done"], 0)
        self.assertEqual(agg[0]["failed"], 0)
        self.assertIsNone(agg[0]["success_rate"])

    def test_systems_filter(self):
        events = [
            _event(system="polling-fs", surface_sha256=_SURFACE_A),
            _event(system="polling-label", surface_sha256=_SURFACE_B),
        ]
        agg = mi.aggregate_by_surface(events, "issue", systems={"polling-fs"})
        self.assertEqual(len(agg), 1)
        self.assertEqual(agg[0]["surface_sha256"], _SURFACE_A)


class TestSurfaceDelta(unittest.TestCase):
    def test_returns_none_when_fewer_than_two_surfaces(self):
        agg = [{"surface_sha256": _SURFACE_A, "success_rate": 0.5}]
        self.assertIsNone(mi.surface_delta(agg))
        self.assertIsNone(mi.surface_delta([]))

    def test_computes_rate_delta_between_last_two_surfaces(self):
        agg = [
            {"surface_sha256": _SURFACE_A, "success_rate": 0.5},
            {"surface_sha256": _SURFACE_B, "success_rate": 0.8},
        ]
        delta = mi.surface_delta(agg)
        self.assertEqual(delta["prev"]["surface_sha256"], _SURFACE_A)
        self.assertEqual(delta["curr"]["surface_sha256"], _SURFACE_B)
        self.assertAlmostEqual(delta["rate_delta"], 0.3)

    def test_rate_delta_is_none_when_either_rate_is_none(self):
        agg = [
            {"surface_sha256": _SURFACE_A, "success_rate": None},
            {"surface_sha256": _SURFACE_B, "success_rate": 0.8},
        ]
        delta = mi.surface_delta(agg)
        self.assertIsNone(delta["rate_delta"])


class TestCurrentSurfaceSha256(unittest.TestCase):
    def test_matches_ledger_direct_call_for_issue_skill(self):
        sr_scripts = os.path.join(REPO_ROOT, "skills", "skill-regression",
                                   "scripts")
        sys.path.insert(0, sr_scripts)
        import ledger  # noqa: E402

        expected = ledger.fingerprint(REPO_ROOT,
                                       ledger.skill_surface(REPO_ROOT, "issue"))
        actual = mi.current_surface_sha256(REPO_ROOT, "issue")
        self.assertRegex(actual, r"^[0-9a-f]{64}$")
        self.assertEqual(actual, expected)


class TestDefaultEventsPath(unittest.TestCase):
    def test_default_events_path_is_under_runtime(self):
        self.assertEqual(
            os.path.join(".agents", "runtime", "loop", "events.jsonl"),
            mi._DEFAULT_EVENTS_REL,
        )

    def test_no_warning_when_old_path_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(mi.old_events_path_warning(tmp))

    def test_warning_is_actionable_when_old_path_has_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_dir = os.path.join(tmp, ".agents", "artifacts", "loop")
            os.makedirs(old_dir)
            with open(os.path.join(old_dir, "events.jsonl"), "w") as f:
                f.write("{}\n")
            warning = mi.old_events_path_warning(tmp)
            self.assertIsNotNone(warning)
            # 何が: 旧パス / どう直す: 新パスへの mv コマンド
            self.assertIn(".agents/artifacts/loop/events.jsonl", warning)
            self.assertIn(".agents/runtime/loop/events.jsonl", warning)
            self.assertIn("mv", warning)


class TestRuntimeContainment(unittest.TestCase):
    def test_events_path_inside_repo_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".agents", "runtime", "loop", "events.jsonl")
            self.assertIsNone(mi.runtime_containment_error(tmp, path))

    def test_symlinked_runtime_dir_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, \
                tempfile.TemporaryDirectory() as outside:
            agents = os.path.join(tmp, ".agents")
            os.makedirs(agents)
            os.symlink(outside, os.path.join(agents, "runtime"))
            path = os.path.join(tmp, ".agents", "runtime", "loop", "events.jsonl")
            error = mi.runtime_containment_error(tmp, path)
            self.assertIsNotNone(error)
            self.assertIn("symlink", error)

    def test_emit_refuses_symlinked_default_runtime(self):
        with tempfile.TemporaryDirectory() as tmp, \
                tempfile.TemporaryDirectory() as outside:
            agents = os.path.join(tmp, ".agents")
            os.makedirs(agents)
            os.symlink(outside, os.path.join(agents, "runtime"))
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                rc = mi.main([
                    "emit", "--system", "skill-regression",
                    "--event", "verification", "--skill", "issue",
                    "--repo-root", tmp,
                    "--outcome", json.dumps({"result": "pass"}),
                ])
            self.assertNotEqual(rc, 0)
            self.assertIn("symlink", err.getvalue())
            # 何も書き込まれていない（symlink 先へのエスケープなし）
            self.assertEqual([], os.listdir(outside))


class TestFormatReport(unittest.TestCase):
    def test_shortens_surface_and_includes_delta_line(self):
        agg = [
            {"surface_sha256": _SURFACE_A, "ticks": 3, "claimed": 3,
             "done": 2, "failed": 1, "success_rate": 2 / 3,
             "first_ts": "2026-07-01T00:00:00+00:00",
             "last_ts": "2026-07-01T02:00:00+00:00"},
            {"surface_sha256": _SURFACE_B, "ticks": 2, "claimed": 2,
             "done": 2, "failed": 0, "success_rate": 1.0,
             "first_ts": "2026-07-02T00:00:00+00:00",
             "last_ts": "2026-07-02T01:00:00+00:00"},
        ]
        delta = mi.surface_delta(agg)
        report = mi.format_report(agg, delta, "issue")
        self.assertIn(_SURFACE_A[:12], report)
        self.assertNotIn(_SURFACE_A, report)
        self.assertIn("issue", report)
        self.assertIn("直近の改稿効果", report)

    def test_no_delta_line_when_delta_is_none(self):
        agg = [{"surface_sha256": _SURFACE_A, "ticks": 1, "claimed": 1,
                "done": 1, "failed": 0, "success_rate": 1.0,
                "first_ts": "2026-07-01T00:00:00+00:00",
                "last_ts": "2026-07-01T00:00:00+00:00"}]
        report = mi.format_report(agg, None, "issue")
        self.assertNotIn("直近の改稿効果", report)

    def test_empty_agg_does_not_crash(self):
        report = mi.format_report([], None, "issue")
        self.assertIsInstance(report, str)


class TestCli(unittest.TestCase):
    def test_emit_then_report_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            events_path = os.path.join(tmp, "events.jsonl")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = mi.main([
                    "emit", "--system", "polling-fs", "--event", "tick",
                    "--skill", "issue", "--repo-root", REPO_ROOT,
                    "--outcome", json.dumps({"claimed": 1, "done": 1,
                                              "failed_transient": 0,
                                              "failed_permanent": 0}),
                    "--events", events_path,
                ])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.isfile(events_path))
            with open(events_path, encoding="utf-8") as f:
                lines = [line for line in f.read().splitlines() if line]
            self.assertEqual(len(lines), 1)
            emitted = json.loads(lines[0])
            self.assertEqual(mi.validate_event(emitted), [])

            out2 = io.StringIO()
            with contextlib.redirect_stdout(out2):
                rc2 = mi.main([
                    "report", "--skill", "issue", "--events", events_path,
                ])
            self.assertEqual(rc2, 0)
            report_text = out2.getvalue()
            self.assertIn("issue", report_text)
            self.assertIn(emitted["surface_sha256"][:12], report_text)

    def test_report_skips_missing_events_file(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = mi.main([
                "report", "--skill", "issue",
                "--events", "/nonexistent/does-not-exist.jsonl",
            ])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
