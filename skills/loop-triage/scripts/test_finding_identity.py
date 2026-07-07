"""finding_identity.py の unittest。

契約: skills/shared/references/loop-engineering.md
  - §2 Finding Schema (validate_finding / normalize_finding)
  - §3 Finding Identity & 冪等化 (finding_id / build_baseline / load_baseline /
    parse_frontmatter_finding_id / collect_queue_ids)

標準ライブラリのみ使用。
"""

import json
import os
import tempfile
import unittest

from finding_identity import (
    FIX_ACTIONS,
    SEVERITIES,
    build_baseline,
    collect_queue_ids,
    finding_id,
    load_baseline,
    normalize_finding,
    parse_frontmatter_finding_id,
    validate_finding,
)


def _valid_finding(**overrides):
    base = {
        "sensor": "validate-repo",
        "rule": "CA-D001",
        "severity": "WARN",
        "fix_action": "AUTO_FIX",
        "where": {"path": "skills/foo/SKILL.md", "line": 12},
        "what": "frontmatter missing description",
        "suggested_title": "SKILL.md に description を追加",
        "affected_paths": ["skills/foo/SKILL.md"],
    }
    base.update(overrides)
    return base


class TestConstants(unittest.TestCase):
    def test_severities(self):
        self.assertEqual(SEVERITIES, {"BLOCK", "WARN", "INFO"})

    def test_fix_actions(self):
        self.assertEqual(FIX_ACTIONS, {"AUTO_FIX", "NEEDS_JUDGMENT", "REPORT_ONLY"})


class TestFindingId(unittest.TestCase):
    def test_snapshot_value(self):
        # sha256("s|r|p|w").hexdigest()[:16] を独立に python3 -c で計算した既知値
        self.assertEqual(finding_id("s", "r", "p", "w"), "f0d9ad214727d52b")

    def test_length_is_16(self):
        result = finding_id("sensor", "rule", "path/to/file", "something is wrong")
        self.assertEqual(len(result), 16)
        # hex 文字のみで構成される
        int(result, 16)

    def test_line_number_not_part_of_signature(self):
        # 関数シグネチャに line 引数が存在しない = 呼び出し不能であることを
        # inspect で確認する（契約: 行番号を含めない）
        import inspect

        sig = inspect.signature(finding_id)
        self.assertNotIn("line", sig.parameters)
        self.assertEqual(list(sig.parameters), ["sensor", "rule", "path", "what"])

    def test_differs_on_input_change(self):
        base = finding_id("sensor", "rule", "path", "what")
        self.assertNotEqual(base, finding_id("other-sensor", "rule", "path", "what"))
        self.assertNotEqual(base, finding_id("sensor", "other-rule", "path", "what"))
        self.assertNotEqual(base, finding_id("sensor", "rule", "other-path", "what"))
        self.assertNotEqual(base, finding_id("sensor", "rule", "path", "other-what"))

    def test_deterministic(self):
        self.assertEqual(
            finding_id("sensor", "rule", "path", "what"),
            finding_id("sensor", "rule", "path", "what"),
        )


class TestValidateFinding(unittest.TestCase):
    def test_valid_finding_has_no_errors(self):
        self.assertEqual(validate_finding(_valid_finding()), [])

    def test_valid_finding_without_fix_action_has_no_errors(self):
        d = _valid_finding()
        del d["fix_action"]
        self.assertEqual(validate_finding(d), [])

    def test_valid_finding_without_line_has_no_errors(self):
        d = _valid_finding()
        d["where"] = {"path": "skills/foo/SKILL.md"}
        self.assertEqual(validate_finding(d), [])

    def test_missing_sensor(self):
        d = _valid_finding()
        del d["sensor"]
        self.assertTrue(validate_finding(d))

    def test_empty_sensor(self):
        d = _valid_finding(sensor="")
        self.assertTrue(validate_finding(d))

    def test_non_str_sensor(self):
        d = _valid_finding(sensor=123)
        self.assertTrue(validate_finding(d))

    def test_missing_rule(self):
        d = _valid_finding()
        del d["rule"]
        self.assertTrue(validate_finding(d))

    def test_empty_rule(self):
        d = _valid_finding(rule="")
        self.assertTrue(validate_finding(d))

    def test_missing_severity(self):
        d = _valid_finding()
        del d["severity"]
        self.assertTrue(validate_finding(d))

    def test_invalid_severity(self):
        d = _valid_finding(severity="CRITICAL")
        self.assertTrue(validate_finding(d))

    def test_missing_where(self):
        d = _valid_finding()
        del d["where"]
        self.assertTrue(validate_finding(d))

    def test_where_not_dict(self):
        d = _valid_finding(where="skills/foo/SKILL.md")
        self.assertTrue(validate_finding(d))

    def test_where_missing_path(self):
        d = _valid_finding(where={"line": 1})
        self.assertTrue(validate_finding(d))

    def test_where_empty_path(self):
        d = _valid_finding(where={"path": ""})
        self.assertTrue(validate_finding(d))

    def test_where_path_not_str(self):
        d = _valid_finding(where={"path": 123})
        self.assertTrue(validate_finding(d))

    def test_where_line_not_int(self):
        d = _valid_finding(where={"path": "a.md", "line": "12"})
        self.assertTrue(validate_finding(d))

    def test_missing_what(self):
        d = _valid_finding()
        del d["what"]
        self.assertTrue(validate_finding(d))

    def test_empty_what(self):
        d = _valid_finding(what="")
        self.assertTrue(validate_finding(d))

    def test_missing_suggested_title(self):
        d = _valid_finding()
        del d["suggested_title"]
        self.assertTrue(validate_finding(d))

    def test_empty_suggested_title(self):
        d = _valid_finding(suggested_title="")
        self.assertTrue(validate_finding(d))

    def test_missing_affected_paths(self):
        d = _valid_finding()
        del d["affected_paths"]
        self.assertTrue(validate_finding(d))

    def test_affected_paths_not_list(self):
        d = _valid_finding(affected_paths="skills/foo/SKILL.md")
        self.assertTrue(validate_finding(d))

    def test_affected_paths_with_non_str_item(self):
        d = _valid_finding(affected_paths=["skills/foo/SKILL.md", 42])
        self.assertTrue(validate_finding(d))

    def test_fix_action_unknown_value_has_no_errors(self):
        # fix_action は欠落・未知でもエラーにしない（normalize_finding が正規化）
        d = _valid_finding(fix_action="SOMETHING_ELSE")
        self.assertEqual(validate_finding(d), [])

    def test_multiple_errors_reported(self):
        d = {}
        errors = validate_finding(d)
        self.assertGreater(len(errors), 1)


class TestNormalizeFinding(unittest.TestCase):
    def test_missing_fix_action_normalized_to_report_only(self):
        d = _valid_finding()
        del d["fix_action"]
        result = normalize_finding(d)
        self.assertEqual(result["fix_action"], "REPORT_ONLY")

    def test_unknown_fix_action_normalized_to_report_only(self):
        d = _valid_finding(fix_action="MAYBE_FIX")
        result = normalize_finding(d)
        self.assertEqual(result["fix_action"], "REPORT_ONLY")

    def test_known_fix_action_unchanged(self):
        d = _valid_finding(fix_action="NEEDS_JUDGMENT")
        result = normalize_finding(d)
        self.assertEqual(result["fix_action"], "NEEDS_JUDGMENT")

    def test_other_fields_unchanged(self):
        d = _valid_finding()
        result = normalize_finding(d)
        for key in ("sensor", "rule", "severity", "where", "what", "suggested_title", "affected_paths"):
            self.assertEqual(result[key], d[key])

    def test_does_not_mutate_input(self):
        d = _valid_finding()
        del d["fix_action"]
        original = json.loads(json.dumps(d))
        normalize_finding(d)
        self.assertEqual(d, original)

    def test_returns_new_dict(self):
        d = _valid_finding()
        result = normalize_finding(d)
        self.assertIsNot(result, d)


class TestBuildBaseline(unittest.TestCase):
    def test_basic_shape(self):
        result = build_baseline(["b", "a", "c"])
        self.assertEqual(result, {"version": 1, "suppressions": ["a", "b", "c"]})

    def test_dedups(self):
        result = build_baseline(["a", "a", "b"])
        self.assertEqual(result["suppressions"], ["a", "b"])

    def test_empty_list(self):
        result = build_baseline([])
        self.assertEqual(result, {"version": 1, "suppressions": []})


class TestLoadBaseline(unittest.TestCase):
    def test_valid_baseline(self):
        text = json.dumps({"version": 1, "suppressions": ["abc123", "def456"]})
        self.assertEqual(load_baseline(text), {"abc123", "def456"})

    def test_empty_string_returns_empty_set(self):
        self.assertEqual(load_baseline(""), set())

    def test_invalid_json_returns_empty_set(self):
        self.assertEqual(load_baseline("{not valid json"), set())

    def test_wrong_version_returns_empty_set(self):
        text = json.dumps({"version": 2, "suppressions": ["abc123"]})
        self.assertEqual(load_baseline(text), set())

    def test_missing_suppressions_key_returns_empty_set(self):
        text = json.dumps({"version": 1})
        self.assertEqual(load_baseline(text), set())


class TestParseFrontmatterFindingId(unittest.TestCase):
    def test_extracts_finding_id(self):
        text = "---\nfinding_id: abc123def456\ntitle: foo\n---\n\nbody text\n"
        self.assertEqual(parse_frontmatter_finding_id(text), "abc123def456")

    def test_no_frontmatter_returns_none(self):
        text = "# just a doc\n\nno frontmatter here\n"
        self.assertIsNone(parse_frontmatter_finding_id(text))

    def test_frontmatter_without_finding_id_returns_none(self):
        text = "---\ntitle: foo\n---\n\nbody\n"
        self.assertIsNone(parse_frontmatter_finding_id(text))

    def test_unterminated_frontmatter_returns_none(self):
        text = "---\nfinding_id: abc123\ntitle: foo\n\nbody without closing marker\n"
        self.assertIsNone(parse_frontmatter_finding_id(text))


class TestCollectQueueIds(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.root = self.tmpdir.name

    def _write(self, rel_path, content):
        full = os.path.join(self.root, rel_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)

    def _fm(self, finding_id_value):
        return f"---\nfinding_id: {finding_id_value}\n---\n\nbody\n"

    def test_collects_from_all_open_locations(self):
        self._write("top-level.md", self._fm("id-top"))
        self._write("ready/r1.md", self._fm("id-ready"))
        self._write("running/task1/issue.md", self._fm("id-running"))
        self._write("failed/transient/t1.md", self._fm("id-transient"))
        self._write("failed/permanent/p1.md", self._fm("id-permanent"))

        result = collect_queue_ids(self.root)
        self.assertEqual(
            result,
            {"id-top", "id-ready", "id-running", "id-transient", "id-permanent"},
        )

    def test_ignores_archives(self):
        self._write("ready/r1.md", self._fm("id-ready"))
        self._write("archives/old.md", self._fm("id-archived"))

        result = collect_queue_ids(self.root)
        self.assertIn("id-ready", result)
        self.assertNotIn("id-archived", result)

    def test_missing_subdirectories_are_skipped(self):
        self._write("ready/r1.md", self._fm("id-ready"))
        # running/, failed/, archives/ は存在しない
        result = collect_queue_ids(self.root)
        self.assertEqual(result, {"id-ready"})

    def test_files_without_finding_id_are_skipped(self):
        self._write("ready/no-id.md", "---\ntitle: foo\n---\n\nbody\n")
        self._write("ready/has-id.md", self._fm("id-has"))
        result = collect_queue_ids(self.root)
        self.assertEqual(result, {"id-has"})

    def test_nonexistent_root_returns_empty_set(self):
        result = collect_queue_ids(os.path.join(self.root, "does-not-exist"))
        self.assertEqual(result, set())


if __name__ == "__main__":
    unittest.main()
