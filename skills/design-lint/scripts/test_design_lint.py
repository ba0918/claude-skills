"""design_lint.py の unittest。

references/lint-contract.md（DL001-006 / DL101-103 / DL201-204）と
shared/references/design-system-contract.md（CSS 変数命名規則）を正とする。
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import design_lint as dl


TOKENS = {
    "colors": {
        "primary": "#2563EB",
        "primaryHover": "#1D4ED8",
        "error": "#DC2626",
        "textPrimary": "#111827",
    },
    "colorsDark": {"background": "#0B1120"},
    "typography": {
        "headingFont": "'Outfit', sans-serif",
        "bodyFont": "Inter, sans-serif",
        "codeFont": "'JetBrains Mono', monospace",
        "scale": {},
    },
    "spacing": {"scale": [0, 4, 8, 16, 24]},
    "components": {
        "buttons": {"borderRadius": 8},
        "cards": {"borderRadius": 12},
        "inputs": {"borderRadius": 8},
    },
    "depth": {
        "flat": {"shadow": "none"},
        "raised": {"shadow": "0 1px 3px rgba(0,0,0,0.12)"},
    },
}


def ctx(**over):
    base = {
        "tokens": TOKENS,
        "config": dl.merge_config(None),
        "catalog": None,
        "pages": {},
        "layout_rules": None,
    }
    base.update(over)
    return dl.build_context(**base)


def rules_of(violations):
    return [v["rule"] for v in violations]


class TestMergeConfig(unittest.TestCase):
    def test_defaults_when_none(self):
        cfg = dl.merge_config(None)
        self.assertEqual(cfg["rules"]["DL001"], "error")
        self.assertEqual(cfg["rules"]["DL003"], "warn")
        self.assertIn("transparent", cfg["allowRawValues"]["colors"])

    def test_user_overrides_are_merged(self):
        cfg = dl.merge_config({"rules": {"DL001": "off"}})
        self.assertEqual(cfg["rules"]["DL001"], "off")
        self.assertEqual(cfg["rules"]["DL002"], "error")  # 既定は保持


class TestStripComments(unittest.TestCase):
    def test_block_and_line_comments_removed(self):
        text = "a /* #FF0000 */ b\n// #00FF00\nc\n"
        out = dl.strip_comments(text)
        self.assertNotIn("#FF0000", out)
        self.assertNotIn("#00FF00", out)
        self.assertEqual(len(out.splitlines()), 3)  # 行番号を保存

    def test_url_scheme_is_not_a_comment(self):
        out = dl.strip_comments("background: url(https://x.test/a.png);\n")
        self.assertIn("https://x.test", out)


class TestDL001Color(unittest.TestCase):
    def test_unknown_hex_is_flagged(self):
        v = dl.lint_text("src/a.css", ".x { color: #FF6B6B; }", ctx())
        self.assertIn("DL001", rules_of(v))
        hit = [x for x in v if x["rule"] == "DL001"][0]
        self.assertEqual(hit["value"], "#FF6B6B")
        self.assertEqual(hit["line"], 1)
        self.assertIn("suggestion", hit)  # 最も近いトークンを提案

    def test_token_hex_is_not_dl001(self):
        v = dl.lint_text("src/a.css", ".x { color: #2563EB; }", ctx())
        self.assertNotIn("DL001", rules_of(v))

    def test_dark_token_hex_is_allowed(self):
        v = dl.lint_text("src/a.css", ".x { color: #0B1120; }", ctx())
        self.assertNotIn("DL001", rules_of(v))

    def test_short_hex_is_normalized(self):
        # #fff は許可リストになければ違反（3桁→6桁展開で照合）
        v = dl.lint_text("src/a.css", ".x { color: #fff; }", ctx())
        self.assertIn("DL001", rules_of(v))

    def test_unknown_rgba_is_flagged(self):
        v = dl.lint_text("src/a.css", ".x { color: rgba(1,2,3,0.5); }", ctx())
        self.assertIn("DL001", rules_of(v))

    def test_rgba_inside_allowed_shadow_is_not_flagged(self):
        # トークン定義済み shadow 内の rgba は DL001 を発火させない
        v = dl.lint_text(
            "src/a.css",
            ".x { box-shadow: 0 1px 3px rgba(0,0,0,0.12); }", ctx())
        self.assertNotIn("DL001", rules_of(v))

    def test_comment_and_url_are_ignored(self):
        text = "/* #FF6B6B */\n.x { background: url(#grad4); }"
        v = dl.lint_text("src/a.css", text, ctx())
        self.assertNotIn("DL001", rules_of(v))


class TestDL002Font(unittest.TestCase):
    def test_unknown_font_is_flagged(self):
        v = dl.lint_text(
            "src/a.css", ".x { font-family: 'Comic Sans MS', cursive; }", ctx())
        self.assertIn("DL002", rules_of(v))

    def test_token_font_and_generics_pass(self):
        v = dl.lint_text(
            "src/a.css", ".x { font-family: 'Outfit', sans-serif; }", ctx())
        self.assertNotIn("DL002", rules_of(v))

    def test_system_stack_passes(self):
        v = dl.lint_text(
            "src/a.css",
            ".x { font-family: -apple-system, BlinkMacSystemFont, system-ui, sans-serif; }",
            ctx())
        self.assertNotIn("DL002", rules_of(v))

    def test_css_in_js_font_family(self):
        v = dl.lint_text(
            "src/a.tsx", "const s = { fontFamily: 'Papyrus' };", ctx())
        self.assertIn("DL002", rules_of(v))

    def test_var_reference_passes(self):
        v = dl.lint_text(
            "src/a.css", ".x { font-family: var(--font-body); }", ctx())
        self.assertNotIn("DL002", rules_of(v))


class TestDL003Spacing(unittest.TestCase):
    def test_off_scale_px_is_flagged(self):
        v = dl.lint_text("src/a.css", ".x { padding: 13px; }", ctx())
        self.assertIn("DL003", rules_of(v))

    def test_scale_px_is_not_dl003(self):
        v = dl.lint_text("src/a.css", ".x { padding: 16px; }", ctx())
        self.assertNotIn("DL003", rules_of(v))

    def test_shorthand_checks_each_value(self):
        v = dl.lint_text("src/a.css", ".x { margin: 8px 13px; }", ctx())
        hits = [x for x in v if x["rule"] == "DL003"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["value"], "13px")

    def test_relative_units_are_allowed(self):
        v = dl.lint_text(
            "src/a.css", ".x { margin: 5%; padding: 2rem; gap: 1em; }", ctx())
        self.assertNotIn("DL003", rules_of(v))

    def test_non_spacing_property_px_is_ignored(self):
        v = dl.lint_text("src/a.css", ".x { width: 13px; }", ctx())
        self.assertNotIn("DL003", rules_of(v))


class TestDL004Radius(unittest.TestCase):
    def test_unknown_radius_is_flagged(self):
        v = dl.lint_text("src/a.css", ".x { border-radius: 5px; }", ctx())
        self.assertIn("DL004", rules_of(v))

    def test_component_radius_is_not_dl004(self):
        v = dl.lint_text("src/a.css", ".x { border-radius: 12px; }", ctx())
        self.assertNotIn("DL004", rules_of(v))

    def test_allow_raw_values_pass(self):
        v = dl.lint_text(
            "src/a.css", ".x { border-radius: 50%; } .y { border-radius: 9999px; }",
            ctx())
        self.assertNotIn("DL004", rules_of(v))


class TestDL005Shadow(unittest.TestCase):
    def test_unknown_shadow_is_flagged(self):
        v = dl.lint_text(
            "src/a.css", ".x { box-shadow: 0 0 40px rgba(9,9,9,0.9); }", ctx())
        self.assertIn("DL005", rules_of(v))

    def test_token_shadow_is_not_dl005(self):
        v = dl.lint_text(
            "src/a.css", ".x { box-shadow: 0 1px 3px rgba(0,0,0,0.12); }", ctx())
        self.assertNotIn("DL005", rules_of(v))

    def test_none_is_allowed(self):
        v = dl.lint_text("src/a.css", ".x { box-shadow: none; }", ctx())
        self.assertNotIn("DL005", rules_of(v))


class TestDL006CssVar(unittest.TestCase):
    def test_token_color_raw_usage_suggests_var(self):
        v = dl.lint_text("src/a.css", ".x { color: #2563EB; }", ctx())
        hits = [x for x in v if x["rule"] == "DL006"]
        self.assertEqual(len(hits), 1)
        self.assertIn("var(--color-primary)", hits[0]["message"])

    def test_camel_case_token_maps_to_kebab_var(self):
        v = dl.lint_text("src/a.css", ".x { color: #1D4ED8; }", ctx())
        hits = [x for x in v if x["rule"] == "DL006"]
        self.assertIn("var(--color-primary-hover)", hits[0]["message"])

    def test_token_shadow_raw_usage_suggests_var(self):
        v = dl.lint_text(
            "src/a.css", ".x { box-shadow: 0 1px 3px rgba(0,0,0,0.12); }", ctx())
        hits = [x for x in v if x["rule"] == "DL006"]
        self.assertEqual(len(hits), 1)
        self.assertIn("var(--shadow-raised)", hits[0]["message"])

    def test_scale_spacing_raw_usage_suggests_var(self):
        v = dl.lint_text("src/a.css", ".x { padding: 16px; }", ctx())
        hits = [x for x in v if x["rule"] == "DL006"]
        self.assertEqual(len(hits), 1)
        self.assertIn("var(--spacing-3)", hits[0]["message"])  # scale[3] = 16

    def test_var_usage_is_clean(self):
        v = dl.lint_text(
            "src/a.css",
            ".x { color: var(--color-primary); padding: var(--spacing-3); }",
            ctx())
        self.assertEqual(v, [])


class TestDL101Component(unittest.TestCase):
    CATALOG = {"components": [
        {"name": "Button", "variants": [
            {"name": "primary"}, {"name": "ghost"}]},
        {"name": "Card", "variants": []},
    ]}

    def test_unregistered_component_is_flagged(self):
        v = dl.lint_text(
            "src/a.tsx", "<CustomAlert msg='x' />", ctx(catalog=self.CATALOG))
        hits = [x for x in v if x["rule"] == "DL101"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["value"], "CustomAlert")

    def test_catalog_and_react_standard_pass(self):
        text = "<Fragment><Button variant='primary' /><Card /></Fragment>"
        v = dl.lint_text("src/a.tsx", text, ctx(catalog=self.CATALOG))
        self.assertNotIn("DL101", rules_of(v))

    def test_skipped_without_catalog(self):
        v = dl.lint_text("src/a.tsx", "<CustomAlert />", ctx(catalog=None))
        self.assertNotIn("DL101", rules_of(v))

    def test_html_elements_pass(self):
        v = dl.lint_text(
            "src/a.tsx", "<div><span>x</span></div>", ctx(catalog=self.CATALOG))
        self.assertNotIn("DL101", rules_of(v))


class TestDL102Variant(unittest.TestCase):
    CATALOG = TestDL101Component.CATALOG

    def test_unknown_variant_is_flagged(self):
        v = dl.lint_text(
            "src/a.tsx", "<Button variant='danger' />", ctx(catalog=self.CATALOG))
        hits = [x for x in v if x["rule"] == "DL102"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["value"], "danger")

    def test_known_variant_passes(self):
        v = dl.lint_text(
            "src/a.tsx", '<Button variant="ghost" />', ctx(catalog=self.CATALOG))
        self.assertNotIn("DL102", rules_of(v))

    def test_jsx_expression_form(self):
        v = dl.lint_text(
            "src/a.tsx", "<Button variant={'danger'} />", ctx(catalog=self.CATALOG))
        self.assertIn("DL102", rules_of(v))


class TestDL103InlineStyle(unittest.TestCase):
    CATALOG = TestDL101Component.CATALOG

    def test_token_property_override_is_flagged(self):
        v = dl.lint_text(
            "src/a.tsx",
            "<Button style={{ color: 'red', display: 'flex' }} />",
            ctx(catalog=self.CATALOG))
        hits = [x for x in v if x["rule"] == "DL103"]
        self.assertEqual(len(hits), 1)
        self.assertIn("color", hits[0]["value"])

    def test_layout_only_style_passes(self):
        v = dl.lint_text(
            "src/a.tsx",
            "<Card style={{ display: 'grid', zIndex: 5 }} />",
            ctx(catalog=self.CATALOG))
        self.assertNotIn("DL103", rules_of(v))

    def test_non_catalog_component_style_is_ignored(self):
        v = dl.lint_text(
            "src/a.tsx", "<Widget style={{ color: 'red' }} />",
            ctx(catalog=self.CATALOG))
        self.assertNotIn("DL103", rules_of(v))


class TestDL201PageDef(unittest.TestCase):
    def test_route_without_page_def_is_flagged(self):
        c = ctx(pages={"dashboard": {}})
        v = dl.lint_text(
            "src/App.tsx", '<Route path="/settings" element={<S/>} />', c)
        hits = [x for x in v if x["rule"] == "DL201"]
        self.assertEqual(len(hits), 1)
        self.assertIn("settings", hits[0]["value"])

    def test_route_with_page_def_passes(self):
        c = ctx(pages={"dashboard": {}})
        v = dl.lint_text(
            "src/App.tsx", '<Route path="/dashboard" element={<D/>} />', c)
        self.assertNotIn("DL201", rules_of(v))

    def test_skipped_without_pages(self):
        v = dl.lint_text(
            "src/App.tsx", '<Route path="/settings" />', ctx(pages={}))
        self.assertNotIn("DL201", rules_of(v))


class TestDL202AllowedComponents(unittest.TestCase):
    PAGES = {"dashboard": {"allowedComponents": ["Card", "Button"]}}

    def test_disallowed_component_in_page_file_is_flagged(self):
        v = dl.lint_text(
            "src/pages/Dashboard.tsx", "<Card /><Chart />",
            ctx(pages=self.PAGES))
        hits = [x for x in v if x["rule"] == "DL202"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["value"], "Chart")

    def test_allowed_components_pass(self):
        v = dl.lint_text(
            "src/pages/Dashboard.tsx", "<Card /><Button />",
            ctx(pages=self.PAGES))
        self.assertNotIn("DL202", rules_of(v))

    def test_non_page_file_is_ignored(self):
        v = dl.lint_text(
            "src/components/Chart.tsx", "<Chart />", ctx(pages=self.PAGES))
        self.assertNotIn("DL202", rules_of(v))


class TestDL203SectionOrder(unittest.TestCase):
    PAGES = {"home": {"sections": [
        {"id": "hero", "order": 1},
        {"id": "features", "order": 2},
        {"id": "footer-cta", "order": 3},
    ]}}

    def test_wrong_order_is_flagged(self):
        text = ('<div className="features" />\n'
                '<div className="hero" />\n')
        v = dl.lint_text("src/pages/Home.tsx", text, ctx(pages=self.PAGES))
        self.assertIn("DL203", rules_of(v))

    def test_correct_order_passes(self):
        text = ('<div className="hero" />\n'
                '<div className="features" />\n'
                '<div id="footer-cta" />\n')
        v = dl.lint_text("src/pages/Home.tsx", text, ctx(pages=self.PAGES))
        self.assertNotIn("DL203", rules_of(v))

    def test_missing_sections_are_not_order_violations(self):
        # 出現しないセクションは順序違反ではない（DL203 は順序のみを見る）
        v = dl.lint_text(
            "src/pages/Home.tsx", '<div className="hero" />',
            ctx(pages=self.PAGES))
        self.assertNotIn("DL203", rules_of(v))


class TestDL204LayoutRules(unittest.TestCase):
    RULES = {"constraints": [
        {"id": "LC003", "rule": "grid の列数 <= 3", "enforcement": "lint",
         "severity": "error",
         "checkPattern": r"grid-template-columns\s*:\s*repeat\(\s*([4-9]|\d{2,})"},
        {"id": "LC004", "rule": "手動チェック", "enforcement": "manual",
         "checkPattern": r"float\s*:"},
    ]}

    def test_lint_constraint_violation_is_flagged(self):
        v = dl.lint_text(
            "src/a.css", ".g { grid-template-columns: repeat(4, 1fr); }",
            ctx(layout_rules=self.RULES))
        hits = [x for x in v if x["rule"] == "DL204"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["severity"], "error")
        self.assertIn("LC003", hits[0]["message"])

    def test_manual_constraint_is_not_linted(self):
        v = dl.lint_text(
            "src/a.css", ".x { float: left; }", ctx(layout_rules=self.RULES))
        self.assertNotIn("DL204", rules_of(v))


class TestSeverityAndConfig(unittest.TestCase):
    def test_rule_off_suppresses_violations(self):
        cfg = dl.merge_config({"rules": {"DL001": "off"}})
        v = dl.lint_text("src/a.css", ".x { color: #FF6B6B; }",
                         ctx(config=cfg))
        self.assertNotIn("DL001", rules_of(v))

    def test_severity_override(self):
        cfg = dl.merge_config({"rules": {"DL003": "error"}})
        v = dl.lint_text("src/a.css", ".x { padding: 13px; }",
                         ctx(config=cfg))
        hits = [x for x in v if x["rule"] == "DL003"]
        self.assertEqual(hits[0]["severity"], "error")


class TestMatchPattern(unittest.TestCase):
    def test_double_star_matches_nested(self):
        self.assertTrue(dl.match_pattern("src/**/*.tsx", "src/a/b/C.tsx"))
        self.assertTrue(dl.match_pattern("src/**/*.tsx", "src/C.tsx"))
        self.assertFalse(dl.match_pattern("src/**/*.tsx", "lib/C.tsx"))

    def test_basename_pattern_matches_anywhere(self):
        self.assertTrue(dl.match_pattern("*.test.*", "src/a/b.test.tsx"))
        self.assertFalse(dl.match_pattern("*.test.*", "src/a/b.tsx"))

    def test_dir_prefix_pattern(self):
        self.assertTrue(dl.match_pattern("node_modules/**", "node_modules/x/y.js"))
        self.assertFalse(dl.match_pattern("node_modules/**", "src/y.js"))


class TestSummarize(unittest.TestCase):
    def test_fail_on_error(self):
        report = dl.summarize(
            [{"rule": "DL001", "severity": "error"},
             {"rule": "DL003", "severity": "warn"}], files_scanned=2)
        self.assertEqual(report["summary"]["result"], "FAIL")
        self.assertEqual(report["summary"]["errors"], 1)
        self.assertEqual(report["summary"]["warnings"], 1)

    def test_pass_with_warnings(self):
        report = dl.summarize(
            [{"rule": "DL003", "severity": "warn"}], files_scanned=1)
        self.assertEqual(report["summary"]["result"], "PASS")

    def test_pass_when_clean(self):
        report = dl.summarize([], files_scanned=3)
        self.assertEqual(report["summary"]["result"], "PASS")
        self.assertEqual(report["summary"]["totalViolations"], 0)


class TestRunEndToEnd(unittest.TestCase):
    def _setup(self, root):
        os.makedirs(os.path.join(root, ".design"))
        os.makedirs(os.path.join(root, "src"))
        os.makedirs(os.path.join(root, "node_modules", "lib"))
        with open(os.path.join(root, ".design", "tokens.json"), "w") as f:
            json.dump(TOKENS, f)
        with open(os.path.join(root, "src", "bad.css"), "w") as f:
            f.write(".x { color: #FF6B6B; }\n")
        with open(os.path.join(root, "src", "ok.css"), "w") as f:
            f.write(".x { color: var(--color-primary); }\n")
        with open(os.path.join(root, "node_modules", "lib", "v.css"), "w") as f:
            f.write(".x { color: #BAD123; }\n")

    def test_run_detects_and_excludes(self):
        with tempfile.TemporaryDirectory() as root:
            self._setup(root)
            report, exit_code = dl.run(root)
            self.assertEqual(exit_code, 1)
            files = {v["file"] for v in report["violations"]}
            self.assertEqual(files, {"src/bad.css"})
            self.assertEqual(report["summary"]["result"], "FAIL")

    def test_run_without_tokens_returns_precondition_error(self):
        with tempfile.TemporaryDirectory() as root:
            report, exit_code = dl.run(root)
            self.assertEqual(exit_code, 2)
            self.assertIsNone(report)


if __name__ == "__main__":
    unittest.main()
