#!/usr/bin/env python3
"""Model validation for the brief skill.

Whether the grouping is good is a judgement no script can make. Whether
anything silently fell out of the page is decidable, and that is what this
module decides. See ../references/brief-model.md for the contract.
"""

VIEWS = ("change", "document", "orientation", "discussion")

KINDS = {
    "change": ("feature", "fix", "refactor", "docs", "test", "chore"),
    "document": ("goal", "design", "constraint", "risk", "step", "acceptance"),
    "orientation": ("done", "inflight", "next", "blocked"),
    "discussion": ("topic", "decided", "undecided", "option"),
}

LEVELS = ("low", "medium", "high")

UNIVERSE_KEY = {
    "change": "hunks",
    "document": "sections",
    "orientation": "open_items",
}

TOP_LEVEL = ("metadata", "summary", "groups", "comprehension_questions")
METADATA_FIELDS = ("schema_version", "run_id", "view", "source_kind")
SUMMARY_FIELDS = ("one_liner", "purpose", "scope_note")
GROUP_FIELDS = (
    "id",
    "title",
    "kind",
    "intent",
    "plain_explanation",
    "risk",
    "confidence",
    "evidence_refs",
    "items",
)

QUESTION_COUNT = 3


def _filled(value):
    return isinstance(value, str) and value.strip() != ""


def _validate_structure(model):
    errors = []
    for key in TOP_LEVEL:
        if key not in model:
            errors.append("[structure] 必須キーがない: %s" % key)
    if errors:
        return errors

    metadata = model["metadata"]
    if not isinstance(metadata, dict):
        return ["[structure] metadata がオブジェクトでない"]
    for key in METADATA_FIELDS:
        if key not in metadata:
            errors.append("[metadata] 必須キーがない: %s" % key)
    view = metadata.get("view")
    if view not in VIEWS:
        errors.append("[metadata] view が不正: %r" % (view,))

    summary = model["summary"]
    if not isinstance(summary, dict):
        errors.append("[summary] オブジェクトでない")
    else:
        for key in SUMMARY_FIELDS:
            if not _filled(summary.get(key)):
                errors.append("[summary] 必須フィールドが空: %s" % key)

    if not isinstance(model["groups"], list) or not model["groups"]:
        errors.append("[groups] 1 件以上必要")

    return errors


def _validate_groups(model, view):
    errors = []
    seen = set()
    allowed_kinds = KINDS.get(view, ())

    for position, group in enumerate(model["groups"], start=1):
        label = "groups[%d]" % position
        if not isinstance(group, dict):
            errors.append("[%s] オブジェクトでない" % label)
            continue

        for key in GROUP_FIELDS:
            if key not in group:
                errors.append("[%s] 必須キーがない: %s" % (label, key))

        identifier = group.get("id")
        if identifier in seen:
            errors.append("[%s] id が重複: %s" % (label, identifier))
        elif identifier is not None:
            seen.add(identifier)

        if group.get("kind") not in allowed_kinds:
            errors.append(
                "[%s] view %s で使えない kind: %r" % (label, view, group.get("kind"))
            )
        if group.get("risk") not in LEVELS:
            errors.append("[%s] risk が不正: %r" % (label, group.get("risk")))
        if group.get("confidence") not in LEVELS:
            errors.append("[%s] confidence が不正: %r" % (label, group.get("confidence")))

        refs = group.get("evidence_refs")
        if not isinstance(refs, list) or not refs:
            errors.append("[%s] evidence_refs が空。根拠のない主張は本文に置けない" % label)
        if not isinstance(group.get("items"), list):
            errors.append("[%s] items が配列でない" % label)

    return errors


def _validate_deferred(model):
    errors = []
    for position, entry in enumerate(model.get("deferred") or [], start=1):
        label = "deferred[%d]" % position
        if not isinstance(entry, dict):
            errors.append("[%s] オブジェクトでない" % label)
            continue
        if not _filled(entry.get("ref")):
            errors.append("[%s] ref が空" % label)
        if not _filled(entry.get("reason")):
            errors.append("[%s] reason が空。件数だけ隠すことは許さない" % label)
    return errors


def _validate_questions(model):
    questions = model.get("comprehension_questions")
    if not isinstance(questions, list) or len(questions) != QUESTION_COUNT:
        count = len(questions) if isinstance(questions, list) else 0
        return ["[questions] ちょうど %d 件必要（現在 %d 件）" % (QUESTION_COUNT, count)]
    return [
        "[questions] %d 件目が空" % (index + 1)
        for index, question in enumerate(questions)
        if not _filled(question)
    ]


def _refs_by_group(model):
    """Return [(group id, [ref, ...]), ...] preserving each group's own list."""
    pairs = []
    for group in model["groups"]:
        if isinstance(group, dict) and isinstance(group.get("evidence_refs"), list):
            refs = [r for r in group["evidence_refs"] if isinstance(r, str)]
            pairs.append((group.get("id"), refs))
    return pairs


def _group_refs(model):
    refs = []
    for _, group_refs in _refs_by_group(model):
        refs += group_refs
    return refs


def _deferred_refs(model):
    return [
        entry["ref"]
        for entry in (model.get("deferred") or [])
        if isinstance(entry, dict) and isinstance(entry.get("ref"), str)
    ]


def _validate_attribution(model, view, universe):
    errors = []
    group_refs = _group_refs(model)
    deferred_refs = _deferred_refs(model)

    for ref in sorted(set(group_refs + deferred_refs) - set(universe)):
        errors.append("[evidence] 入力に存在しない参照: %s" % ref)

    if view == "change":
        # 「どこで重複したか」で原因も直し方も変わる。同一グループ内の書き損じを
        # 「複数のグループに属している」と報告すると、存在しない別グループを探させる。
        owners = {}
        for group_id, refs in _refs_by_group(model):
            for ref in sorted({r for r in refs if refs.count(r) > 1}):
                errors.append(
                    "[attribution/duplicate-in-group] 同じグループ内で重複している: "
                    "%s (%s)" % (ref, group_id)
                )
            for ref in set(refs):
                owners.setdefault(ref, []).append(group_id)
        for ref in sorted(r for r, gids in owners.items() if len(gids) > 1):
            errors.append(
                "[attribution/duplicate-across-groups] 複数のグループに属している: "
                "%s (%s)" % (ref, " / ".join(str(g) for g in owners[ref]))
            )
        for ref in sorted(set(universe) - set(group_refs)):
            errors.append("[attribution/unassigned] どのグループにも属していない: %s" % ref)
        # deferred is not an escape hatch for change: a hunk nobody grouped is
        # a hole in the page, not a detail worth hiding.
        for ref in sorted(set(deferred_refs) & set(universe)):
            errors.append("[attribution] change では deferred へ退避できない: %s" % ref)
        return errors

    covered = set(group_refs) | set(deferred_refs)
    for ref in sorted(set(universe) - covered):
        errors.append("[attribution] グループにも deferred にも現れない: %s" % ref)
    return errors


def _validate_discussion(model):
    errors = []
    kinds = [
        group.get("kind")
        for group in model["groups"]
        if isinstance(group, dict)
    ]
    if "undecided" not in kinds:
        errors.append(
            "[discussion] 未決事項のグループがない。会話の要約で最も落ちやすいのは"
            "「まだ決まっていないこと」なので、ここだけは構造的に守る"
        )
    for entry in model.get("deferred") or []:
        if isinstance(entry, dict) and entry.get("kind") == "undecided":
            errors.append(
                "[discussion] 未決事項を deferred へ退避している: %s" % entry.get("ref")
            )
    return errors


def validate_model(model, inputs=None):
    """Return every contract violation found in the model, empty when valid."""
    if not isinstance(model, dict):
        return ["[structure] モデルがオブジェクトでない"]

    errors = _validate_structure(model)
    if errors:
        return errors

    view = model["metadata"]["view"]
    errors += _validate_groups(model, view)
    errors += _validate_deferred(model)
    errors += _validate_questions(model)

    if view == "discussion":
        errors += _validate_discussion(model)
        return errors

    universe = (inputs or {}).get(UNIVERSE_KEY[view])
    if universe is None:
        errors.append(
            "[evidence] view %s には入力の識別子一覧が必要（帰属検査ができない）" % view
        )
        return errors

    errors += _validate_attribution(model, view, universe)
    return errors
