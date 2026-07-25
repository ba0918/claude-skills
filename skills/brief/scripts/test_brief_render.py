#!/usr/bin/env python3
"""Unit tests for brief_render.py model validation.

Grouping is a judgement call and cannot be checked mechanically. Whether
anything silently fell out of the page can be, and that is what these tests
pin down — plus the discussion-view rule that unsettled points may never be
the thing that disappears.
"""

import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from brief_render import validate_model  # noqa: E402

QUESTIONS = [
    "この変更で最もリスクが高いのはどこ？",
    "なぜ別の方法ではなくこの方法を選んだ？",
    "これが原因で壊れうるのはどこ？",
]


def change_model():
    return {
        "metadata": {
            "schema_version": 1,
            "run_id": "20260726011631",
            "view": "change",
            "source_kind": "unstaged",
            "source_ref": None,
            "perspective": "作業内容を教えて",
        },
        "summary": {
            "one_liner": "URL 生成を一箇所に集約した",
            "purpose": "deployment mode ごとに散っていた生成処理をまとめる",
            "scope_note": "認証まわりは対象外",
        },
        "groups": [
            {
                "id": "g1",
                "title": "URL 生成の共通基盤",
                "kind": "refactor",
                "intent": "散在した生成処理を一箇所へ寄せる",
                "plain_explanation": "同じ URL を作る処理が三箇所にあったのを一つにした",
                "risk": "medium",
                "confidence": "high",
                "evidence_refs": ["h001", "h002"],
                "items": ["src/url.py を新設", "呼び出し側を差し替え"],
                "concerns": [],
            },
            {
                "id": "g2",
                "title": "設計文書の更新",
                "kind": "docs",
                "intent": "集約後の構成に記述を合わせる",
                "plain_explanation": "図と説明を今の形に直した",
                "risk": "low",
                "confidence": "high",
                "evidence_refs": ["h003"],
                "items": ["docs/b.md を更新"],
            },
        ],
        "deferred": [],
        "comprehension_questions": list(QUESTIONS),
    }


def document_model():
    return {
        "metadata": {
            "schema_version": 1,
            "run_id": "r1",
            "view": "document",
            "source_kind": "plan",
            "source_ref": ".agents/artifacts/plans/p.md",
        },
        "summary": {
            "one_liner": "brief スキルを作る計画",
            "purpose": "承認の儀式化を止める",
            "scope_note": "既存ワークフローへの配線は対象外",
        },
        "groups": [
            {
                "id": "g1",
                "title": "作るもの",
                "kind": "goal",
                "intent": "何を達成するかを決める",
                "plain_explanation": "手動起動の解説画面を作る",
                "risk": "low",
                "confidence": "high",
                "evidence_refs": ["s1"],
                "items": ["4 つの view に対応する"],
            }
        ],
        "deferred": [{"ref": "s2", "label": "実装手順の細目", "reason": "実装手順の詳細のため初期表示から外した"}],
        "comprehension_questions": list(QUESTIONS),
    }


def discussion_model():
    return {
        "metadata": {
            "schema_version": 1,
            "run_id": "r2",
            "view": "discussion",
            "source_kind": "session",
        },
        "summary": {
            "one_liner": "解説画面を作るかどうかを詰めた",
            "purpose": "方針を固める",
            "scope_note": "実装の詳細は未着手",
        },
        "groups": [
            {
                "id": "g1",
                "title": "決まったこと",
                "kind": "decided",
                "intent": "合意した範囲を確認する",
                "plain_explanation": "手動起動の単体スキルとして作ることにした",
                "risk": "low",
                "confidence": "high",
                "evidence_refs": ["turn-12"],
                "items": ["既存フローには配線しない"],
            },
            {
                "id": "g2",
                "title": "まだ決まっていないこと",
                "kind": "undecided",
                "intent": "残った判断を見えるようにする",
                "plain_explanation": "レビュー対象をコミット前にするか PR 前にするか未定",
                "risk": "medium",
                "confidence": "low",
                "evidence_refs": ["turn-18"],
                "items": ["承認の副作用をどこに置くか"],
            },
        ],
        "deferred": [],
        "comprehension_questions": list(QUESTIONS),
    }


CHANGE_INPUTS = {"hunks": ["h001", "h002", "h003"]}
DOCUMENT_INPUTS = {"sections": ["s1", "s2"]}


class RequiredStructure(unittest.TestCase):
    def test_accepts_a_well_formed_change_model(self):
        self.assertEqual(validate_model(change_model(), CHANGE_INPUTS), [])

    def test_rejects_a_missing_top_level_key(self):
        model = change_model()
        del model["summary"]
        self.assertTrue(validate_model(model, CHANGE_INPUTS))

    def test_rejects_a_missing_summary_field(self):
        model = change_model()
        del model["summary"]["scope_note"]
        self.assertTrue(validate_model(model, CHANGE_INPUTS))

    def test_rejects_an_unknown_view(self):
        model = change_model()
        model["metadata"]["view"] = "timeline"
        self.assertTrue(validate_model(model, CHANGE_INPUTS))

    def test_rejects_a_model_without_groups(self):
        model = change_model()
        model["groups"] = []
        self.assertTrue(validate_model(model, CHANGE_INPUTS))

    def test_rejects_duplicate_group_identifiers(self):
        model = change_model()
        model["groups"][1]["id"] = "g1"
        self.assertTrue(validate_model(model, CHANGE_INPUTS))

    def test_rejects_an_out_of_range_risk_value(self):
        model = change_model()
        model["groups"][0]["risk"] = "critical"
        self.assertTrue(validate_model(model, CHANGE_INPUTS))

    def test_rejects_an_out_of_range_confidence_value(self):
        model = change_model()
        model["groups"][0]["confidence"] = "certain"
        self.assertTrue(validate_model(model, CHANGE_INPUTS))

    def test_rejects_a_kind_that_does_not_belong_to_the_view(self):
        model = change_model()
        model["groups"][0]["kind"] = "undecided"
        self.assertTrue(validate_model(model, CHANGE_INPUTS))


class ComprehensionQuestions(unittest.TestCase):
    def test_requires_exactly_three_questions(self):
        for count in (0, 2, 4):
            model = change_model()
            model["comprehension_questions"] = QUESTIONS[:1] * count
            with self.subTest(count=count):
                self.assertTrue(validate_model(model, CHANGE_INPUTS))

    def test_rejects_a_blank_question(self):
        model = change_model()
        model["comprehension_questions"][1] = "   "
        self.assertTrue(validate_model(model, CHANGE_INPUTS))


class Evidence(unittest.TestCase):
    def test_rejects_a_group_without_evidence(self):
        model = change_model()
        model["groups"][0]["evidence_refs"] = []
        self.assertTrue(validate_model(model, CHANGE_INPUTS))

    def test_rejects_a_reference_that_does_not_exist_in_the_input(self):
        model = change_model()
        model["groups"][1]["evidence_refs"] = ["h999"]
        self.assertTrue(validate_model(model, CHANGE_INPUTS))

    def test_rejects_a_deferred_entry_without_a_reason(self):
        model = document_model()
        model["deferred"][0].pop("reason")
        self.assertTrue(validate_model(model, DOCUMENT_INPUTS))


class ChangeAttribution(unittest.TestCase):
    def test_rejects_an_unassigned_hunk(self):
        model = change_model()
        model["groups"][1]["evidence_refs"] = ["h002"]
        errors = validate_model(model, CHANGE_INPUTS)
        self.assertTrue(any("h003" in e for e in errors))

    def test_rejects_a_hunk_assigned_to_two_groups(self):
        model = change_model()
        model["groups"][1]["evidence_refs"] = ["h002", "h003"]
        errors = validate_model(model, CHANGE_INPUTS)
        self.assertTrue(any("duplicate-across-groups" in e and "h002" in e for e in errors))

    def test_rejects_the_same_hunk_listed_twice_inside_one_group(self):
        model = change_model()
        model["groups"][0]["evidence_refs"] = ["h001", "h002", "h002"]
        model["groups"][1]["evidence_refs"] = ["h003"]
        errors = validate_model(model, CHANGE_INPUTS)
        self.assertTrue(any("duplicate-in-group" in e and "h002" in e for e in errors))

    def test_does_not_blame_a_second_group_for_a_duplicate_inside_one_group(self):
        model = change_model()
        model["groups"][0]["evidence_refs"] = ["h001", "h002", "h002"]
        model["groups"][1]["evidence_refs"] = ["h003"]
        errors = validate_model(model, CHANGE_INPUTS)
        self.assertFalse(any("duplicate-across-groups" in e for e in errors))

    def test_names_the_groups_that_share_a_hunk(self):
        model = change_model()
        model["groups"][1]["evidence_refs"] = ["h002", "h003"]
        errors = validate_model(model, CHANGE_INPUTS)
        shared = [e for e in errors if "duplicate-across-groups" in e]
        self.assertTrue(shared and "g1" in shared[0] and "g2" in shared[0])

    def test_does_not_let_deferred_absorb_an_unassigned_hunk(self):
        model = change_model()
        model["groups"][1]["evidence_refs"] = ["h002"]
        model["deferred"] = [{"ref": "h003", "label": "空行の調整", "reason": "些細な変更のため"}]
        self.assertTrue(validate_model(model, CHANGE_INPUTS))


class DocumentAttribution(unittest.TestCase):
    def test_accepts_a_section_covered_by_a_deferred_entry(self):
        self.assertEqual(validate_model(document_model(), DOCUMENT_INPUTS), [])

    def test_rejects_a_section_that_appears_nowhere(self):
        model = document_model()
        model["deferred"] = []
        errors = validate_model(model, DOCUMENT_INPUTS)
        self.assertTrue(any("s2" in e for e in errors))


class OrientationAttribution(unittest.TestCase):
    def base(self):
        model = copy.deepcopy(document_model())
        model["metadata"]["view"] = "orientation"
        model["metadata"]["source_kind"] = "handoff"
        model["groups"][0]["kind"] = "next"
        model["groups"][0]["evidence_refs"] = ["i1"]
        model["deferred"] = [{"ref": "i2", "label": "前回のタスク", "reason": "前回完了済みのため"}]
        return model

    def test_accepts_open_items_covered_by_groups_or_deferred(self):
        inputs = {"open_items": ["i1", "i2"]}
        self.assertEqual(validate_model(self.base(), inputs), [])

    def test_rejects_an_open_item_that_appears_nowhere(self):
        model = self.base()
        model["deferred"] = []
        errors = validate_model(model, {"open_items": ["i1", "i2"]})
        self.assertTrue(any("i2" in e for e in errors))


class DiscussionRules(unittest.TestCase):
    def test_accepts_a_model_that_keeps_an_undecided_group(self):
        self.assertEqual(validate_model(discussion_model()), [])

    def test_rejects_a_model_with_no_undecided_group(self):
        model = discussion_model()
        model["groups"][1]["kind"] = "topic"
        self.assertTrue(validate_model(model))

    def test_rejects_unsettled_material_pushed_into_deferred(self):
        model = discussion_model()
        model["groups"].pop()
        model["deferred"] = [
            {"ref": "turn-18", "label": "承認の副作用", "reason": "話が長いため", "kind": "undecided"}
        ]
        self.assertTrue(validate_model(model))

    def test_does_not_require_input_identifiers(self):
        self.assertEqual(validate_model(discussion_model(), None), [])


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

import json  # noqa: E402
import re  # noqa: E402
from pathlib import Path  # noqa: E402
from unittest import mock  # noqa: E402

import brief_render  # noqa: E402
from brief_render import (  # noqa: E402
    ASSETS,
    open_in_browser,
    render_html,
    scan_secrets,
)

ASSET_DIR = Path(ASSETS)


def excerpt_model():
    model = change_model()
    model["groups"][0]["excerpts"] = [
        {
            "path": "src/link.py",
            "added": 2,
            "removed": 1,
            "hunk_header": "@@ -1,3 +1,4 @@",
            "lines": [
                {"old": 1, "new": 1, "marker": " ", "text": "def build(a, b):"},
                {"old": 2, "new": None, "marker": "-", "text": "    return a & b"},
                {"old": None, "new": 2, "marker": "+", "text": "    return f'{a}<{b}>'"},
            ],
        }
    ]
    return model


def visible_text(page):
    """The page as a reader sees it: no style, no script, no tag names."""
    body = re.sub(r"<style>.*?</style>", " ", page, flags=re.S)
    body = re.sub(r"<script>.*?</script>", " ", body, flags=re.S)
    return re.sub(r"<[^>]+>", " ", body)


class ExcerptValidation(unittest.TestCase):
    def test_accepts_a_well_formed_excerpt(self):
        self.assertEqual(validate_model(excerpt_model(), CHANGE_INPUTS), [])

    def test_rejects_an_unknown_line_marker(self):
        model = excerpt_model()
        model["groups"][0]["excerpts"][0]["lines"][0]["marker"] = "*"
        self.assertTrue(
            any("marker が不正" in e for e in validate_model(model, CHANGE_INPUTS))
        )

    def test_rejects_an_excerpt_without_a_path(self):
        model = excerpt_model()
        model["groups"][0]["excerpts"][0]["path"] = ""
        self.assertTrue(
            any("path が空" in e for e in validate_model(model, CHANGE_INPUTS))
        )

    def test_rejects_an_excerpt_with_no_lines(self):
        model = excerpt_model()
        model["groups"][0]["excerpts"][0]["lines"] = []
        self.assertTrue(
            any("lines が空" in e for e in validate_model(model, CHANGE_INPUTS))
        )


class InitialOrder(unittest.TestCase):
    def test_the_page_opens_in_the_contracted_order(self):
        page = render_html(discussion_model())
        model = discussion_model()
        positions = [
            page.index(model["summary"]["one_liner"]),
            page.index(model["summary"]["purpose"]),
            page.index('class="section-label"'),
            page.index(model["groups"][0]["title"]),
            page.index("この画面に出していない"),
            page.index("読み終えたら"),
            page.index('class="foot"'),
        ]
        self.assertEqual(positions, sorted(positions))

    def test_a_group_reads_explanation_then_items_then_evidence(self):
        page = render_html(discussion_model())
        group = discussion_model()["groups"][0]
        self.assertLess(
            page.index(group["plain_explanation"]), page.index(group["items"][0])
        )
        self.assertLess(page.index(group["items"][0]), page.index("もとの箇所"))

    def test_the_intent_stays_visible_above_the_explanation(self):
        page = render_html(discussion_model())
        group = discussion_model()["groups"][0]
        self.assertLess(
            page.index(group["intent"]), page.index(group["plain_explanation"])
        )


class CollapsedState(unittest.TestCase):
    def test_a_closed_group_still_shows_its_count_and_one_line_summary(self):
        page = render_html(discussion_model())
        head = page[page.index("<summary>") : page.index("</summary>")]
        self.assertIn(discussion_model()["groups"][0]["intent"], head)
        self.assertIn('class="count"', head)

    def test_summary_holds_only_spans_so_the_fold_survives_html_correction(self):
        page = render_html(discussion_model())
        for head in re.findall(r"<summary>(.*?)</summary>", page, flags=re.S):
            self.assertEqual(re.findall(r"<(\w+)", head), ["span"] * len(re.findall(r"<(\w+)", head)))

    def test_items_render_one_per_line(self):
        page = render_html(discussion_model())
        for item in discussion_model()["groups"][0]["items"]:
            self.assertIn("<li>%s</li>" % item, page)


class DeferredVisibility(unittest.TestCase):
    def test_the_count_of_withheld_material_is_always_stated(self):
        model = discussion_model()
        model["deferred"] = [
            {"ref": "turn-30", "label": "見た目の細かい選択肢", "reason": "結論だけで足りる", "kind": "topic"}
        ]
        self.assertIn("出していない論点が 1 件", render_html(model))

    def test_an_empty_page_still_says_nothing_was_withheld(self):
        self.assertIn("出していない論点はありません", render_html(discussion_model()))


class Escaping(unittest.TestCase):
    def test_markup_in_the_model_never_reaches_the_dom(self):
        model = discussion_model()
        model["groups"][0]["title"] = "<script>alert('x')</script>"
        model["summary"]["one_liner"] = 'a "quoted" & <b>bold</b>'
        page = render_html(model)
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;alert", page)
        self.assertIn("&lt;b&gt;bold&lt;/b&gt;", page)

    def test_code_inside_an_excerpt_is_escaped(self):
        page = render_html(excerpt_model())
        self.assertNotIn("return a & b", page)
        self.assertIn("return a &amp; b", page)
        self.assertIn("f&#x27;{a}&lt;{b}&gt;&#x27;", page)


class SelfContained(unittest.TestCase):
    def test_the_page_reaches_nothing_outside_itself(self):
        page = render_html(excerpt_model())
        for forbidden in ("http://", "https://", "@import", "url(", "<img", "src="):
            self.assertNotIn(forbidden, page)

    def test_a_policy_blocks_network_access_from_inside_the_page(self):
        page = render_html(discussion_model())
        self.assertIn("Content-Security-Policy", page)
        self.assertIn("default-src 'none'", page)

    def test_the_stylesheet_and_script_are_inlined(self):
        page = render_html(discussion_model())
        self.assertIn("scrollbar-gutter: stable", page)
        self.assertIn("IntersectionObserver", page)


class TokenDiscipline(unittest.TestCase):
    def test_every_custom_property_the_stylesheet_uses_is_declared(self):
        declared = set(
            re.findall(r"^\s*(--[\w-]+):", (ASSET_DIR / "tokens.css").read_text(), re.M)
        )
        declared |= set(json.loads((ASSET_DIR / "tokens.brief.json").read_text())["tokens"])
        stylesheet = (ASSET_DIR / "brief.css").read_text()
        declared |= set(re.findall(r"(--[\w-]+):", stylesheet))
        used = set(re.findall(r"var\((--[\w-]+)\)", stylesheet))
        self.assertEqual(sorted(used - declared), [])

    def test_the_renderer_holds_no_colours_or_dimensions_of_its_own(self):
        source = Path(__file__).with_name("brief_render.py").read_text()
        self.assertEqual(re.findall(r"#[0-9A-Fa-f]{3,8}\b", source), [])
        self.assertEqual(re.findall(r"\b\d+(?:px|rem|em)\b", source), [])

    def test_the_distribution_tokens_match_the_authored_ones(self):
        authored = Path(__file__).resolve().parents[3] / ".design" / "tokens.css"
        if not authored.is_file():
            self.skipTest("authoring layer is absent in an installed plugin")
        self.assertEqual(
            authored.read_text(), (ASSET_DIR / "tokens.css").read_text()
        )


class ReaderFacingLanguage(unittest.TestCase):
    def test_internal_vocabulary_stays_out_of_what_a_reader_reads(self):
        page = render_html(discussion_model())
        text = visible_text(page[: page.index('class="foot"')])
        for word in ("evidence", "deferred", "attribution", "schema", "one_liner"):
            self.assertNotIn(word, text)

    def test_the_conversation_page_never_asks_for_approval(self):
        # The model's own words are the reader's material. What must never
        # appear is approval vocabulary the renderer adds by itself, so the
        # fixture is stripped of the word before the page is built.
        model = discussion_model()
        model["groups"][1]["items"] = ["残った判断をどこに置くか"]
        text = visible_text(render_html(model))
        for word in ("承認", "却下", "approve", "Approve", "レビュー済み"):
            self.assertNotIn(word, text)

    def test_local_japanese_fonts_are_named_and_banned_ones_are_not(self):
        page = render_html(discussion_model())
        self.assertIn("Hiragino Kaku Gothic ProN", page)
        self.assertIn("Noto Sans JP", page)
        for banned in ("Inter", "Poppins", "Montserrat", "Roboto"):
            self.assertIsNone(re.search(r"\b%s\b" % banned, page))


class Secrets(unittest.TestCase):
    def test_a_credential_in_the_model_is_reported_before_rendering(self):
        model = discussion_model()
        model["groups"][0]["items"].append('api_key = "sk-liveDEADBEEFcafe1234"')
        findings = scan_secrets(model)
        self.assertTrue(findings)

    def test_an_ordinary_model_reports_nothing(self):
        self.assertEqual(scan_secrets(discussion_model()), [])


class Opening(unittest.TestCase):
    def test_a_missing_opener_is_reported_rather_than_raised(self):
        with mock.patch("shutil.which", return_value=None):
            self.assertIsNone(open_in_browser("/tmp/brief.html"))

    def test_on_wsl_only_the_windows_opener_is_tried(self):
        # gio exits 0 on WSL without opening anything. Keeping it in the chain
        # would turn "nothing happened" into a reported success.
        with mock.patch("brief_render._is_wsl", return_value=True), \
             mock.patch("platform.system", return_value="Linux"):
            self.assertEqual(brief_render._opener_commands(), [["wslview"]])

    def test_off_wsl_the_desktop_openers_are_used(self):
        with mock.patch("brief_render._is_wsl", return_value=False), \
             mock.patch("platform.system", return_value="Linux"):
            self.assertEqual(
                brief_render._opener_commands(), [["xdg-open"], ["gio", "open"]]
            )


class WithheldMaterialNaming(unittest.TestCase):
    """`ref` anchors the attribution check; `label` is what a reader reads."""

    def _model(self, **overrides):
        model = discussion_model()
        entry = {"ref": "s001-b4", "label": "会議室の予約方法", "reason": "本題と関係ない"}
        entry.update(overrides)
        model["deferred"] = [entry]
        return model

    def test_the_reader_sees_the_label_and_never_the_identifier(self):
        page = render_html(self._model())
        note = page[page.index("この画面に出していない") :]
        self.assertIn("会議室の予約方法", note)
        self.assertNotIn("s001-b4", note)

    def test_an_entry_without_a_label_is_rejected(self):
        errors = validate_model(self._model(label=""))
        self.assertTrue(any("label が空" in e for e in errors))

    def test_an_entry_without_a_reference_is_still_rejected(self):
        errors = validate_model(self._model(ref=""))
        self.assertTrue(any("ref が空" in e for e in errors))


class EvidenceIsAnAnchorNotReadingMaterial(unittest.TestCase):
    """The count says the claim is backed; the token says nothing to a reader."""

    def test_the_page_states_how_many_places_back_a_group(self):
        page = render_html(discussion_model())
        self.assertIn("もとの箇所 1 件", page)

    def test_identifiers_never_reach_the_reading_flow(self):
        model = change_model()
        page = render_html(model)
        text = visible_text(page[: page.index('class="foot"')])
        for group in model["groups"]:
            for ref in group["evidence_refs"]:
                self.assertNotIn(ref, text)

    def test_identifiers_stay_available_for_tracing(self):
        page = render_html(change_model())
        self.assertIn('data-refs="h001 h002"', page)

    def test_this_holds_for_the_conversation_view_too(self):
        # discussion has no attribution check, and the absence of a check is
        # not permission to put tokens on the page.
        model = discussion_model()
        page = render_html(model)
        text = visible_text(page[: page.index('class="foot"')])
        self.assertNotIn("turn-12", text)


class StickyHeaderStaysShort(unittest.TestCase):
    """An open group's header rides down the screen. Keep it to what a reader
    still needs there, and never change its height on stuck — that oscillates."""

    def test_the_one_line_summary_is_dropped_once_the_group_is_open(self):
        css = (ASSET_DIR / "brief.css").read_text()
        self.assertIn("details.card[open] > summary .summary-line { display: none; }", css)

    def test_nothing_is_hidden_on_stuck(self):
        css = (ASSET_DIR / "brief.css").read_text()
        for rule in re.findall(r"[^}]*\.stuck[^{]*\{[^}]*\}", css):
            self.assertNotIn("display: none", rule)
            self.assertNotIn("height", rule)

    def test_the_item_count_is_dropped_once_the_group_is_open(self):
        css = (ASSET_DIR / "brief.css").read_text()
        self.assertIn("details.card[open] > summary .count { display: none; }", css)

    def test_the_labels_a_reader_reads_alongside_the_text_are_kept(self):
        # kind and risk are read with the body; only index affordances go.
        css = (ASSET_DIR / "brief.css").read_text()
        hidden = re.findall(r"details\.card\[open\] > summary \.(\w[\w-]*) \{ display: none", css)
        self.assertEqual(sorted(hidden), ["count", "summary-line"])

    def test_badges_never_take_a_line_of_their_own_at_reading_width(self):
        css = (ASSET_DIR / "brief.css").read_text()
        head = re.search(r"\.head-row \{[^}]*\}", css).group(0)
        self.assertIn("flex-wrap: nowrap", head)

    def test_the_same_sentence_leads_the_body_so_nothing_is_lost(self):
        model = discussion_model()
        page = render_html(model)
        intent = model["groups"][0]["intent"]
        self.assertEqual(page.count(intent), 2)
        self.assertIn('<p class="lead">%s</p>' % intent, page)


class SourceKindIsAClosedSet(unittest.TestCase):
    """The renderer turns it into a label; an unlisted value reaches the page raw."""

    def test_a_listed_value_passes(self):
        model = discussion_model()
        model["metadata"]["source_kind"] = "session"
        self.assertEqual(validate_model(model), [])

    def test_an_invented_value_is_rejected(self):
        model = discussion_model()
        model["metadata"]["source_kind"] = "打ち合わせメモ"
        self.assertTrue(any("source_kind" in e for e in validate_model(model)))


class ExcerptHeadingFollowsTheMaterial(unittest.TestCase):
    """Calling a quoted memo line a diff is what stopped anyone quoting one."""

    def test_a_diff_is_called_a_diff(self):
        self.assertIn("実際の差分", render_html(excerpt_model()))

    def test_a_document_quote_is_not(self):
        model = document_model()
        model["metadata"]["source_kind"] = "plan"
        model["groups"][0]["excerpts"] = [
            {"path": "notes.md", "lines": [{"text": "- 計測してから直す"}]}
        ]
        page = render_html(model)
        self.assertIn("もとの記述", page)
        self.assertNotIn("実際の差分", page)

    def test_a_conversation_quote_is_called_a_remark(self):
        model = discussion_model()
        model["groups"][0]["excerpts"] = [
            {"path": "conversation.md", "lines": [{"text": "A: 外部に寄せる"}]}
        ]
        self.assertIn("もとの発言", render_html(model))


class DocumentVocabularyCoversUnsettledAndProgress(unittest.TestCase):
    """Two runs reported having nowhere to put a carried-over item."""

    def test_an_unsettled_section_has_a_kind_of_its_own(self):
        model = document_model()
        model["groups"][0]["kind"] = "undecided"
        self.assertEqual(validate_model(model, DOCUMENT_INPUTS), [])

    def test_a_progress_section_has_a_kind_of_its_own(self):
        model = document_model()
        model["groups"][0]["kind"] = "progress"
        self.assertEqual(validate_model(model, DOCUMENT_INPUTS), [])

    def test_both_render_with_reader_facing_labels(self):
        model = document_model()
        model["groups"][0]["kind"] = "undecided"
        self.assertIn("決まっていないこと", render_html(model))
