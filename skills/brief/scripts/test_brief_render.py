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
        "deferred": [{"ref": "s2", "reason": "実装手順の詳細のため初期表示から外した"}],
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
        self.assertTrue(any("h002" in e for e in errors))

    def test_does_not_let_deferred_absorb_an_unassigned_hunk(self):
        model = change_model()
        model["groups"][1]["evidence_refs"] = ["h002"]
        model["deferred"] = [{"ref": "h003", "reason": "些細な変更のため"}]
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
        model["deferred"] = [{"ref": "i2", "reason": "前回完了済みのため"}]
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
            {"ref": "turn-18", "reason": "話が長いため", "kind": "undecided"}
        ]
        self.assertTrue(validate_model(model))

    def test_does_not_require_input_identifiers(self):
        self.assertEqual(validate_model(discussion_model(), None), [])


if __name__ == "__main__":
    unittest.main()
