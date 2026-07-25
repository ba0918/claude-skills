#!/usr/bin/env python3
"""Validation and rendering for the brief skill.

Whether the grouping is good is a judgement no script can make. Whether
anything silently fell out of the page is decidable, and that is what this
module decides. See ../references/brief-model.md for the contract.

The renderer is the other half: a language model writes the model JSON and
never writes markup, so the page looks the same on every run. Colours and
dimensions come from ../assets/, never from this file.
"""

import argparse
import html
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

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


MARKERS = ("+", "-", " ")


def _validate_excerpts(model):
    """Excerpts are optional, but a malformed one would render as a broken page."""
    errors = []
    for position, group in enumerate(model["groups"], start=1):
        if not isinstance(group, dict) or "excerpts" not in group:
            continue
        excerpts = group["excerpts"]
        if not isinstance(excerpts, list):
            errors.append("[groups[%d]] excerpts が配列でない" % position)
            continue
        for index, excerpt in enumerate(excerpts, start=1):
            label = "groups[%d].excerpts[%d]" % (position, index)
            if not isinstance(excerpt, dict):
                errors.append("[%s] オブジェクトでない" % label)
                continue
            if not _filled(excerpt.get("path")):
                errors.append("[%s] path が空" % label)
            lines = excerpt.get("lines")
            if not isinstance(lines, list) or not lines:
                errors.append("[%s] lines が空" % label)
                continue
            for number, line in enumerate(lines, start=1):
                if not isinstance(line, dict):
                    errors.append("[%s] lines[%d] がオブジェクトでない" % (label, number))
                    continue
                if not isinstance(line.get("text"), str):
                    errors.append("[%s] lines[%d] の text が文字列でない" % (label, number))
                if line.get("marker", " ") not in MARKERS:
                    errors.append(
                        "[%s] lines[%d] の marker が不正: %r"
                        % (label, number, line.get("marker"))
                    )
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
    errors += _validate_excerpts(model)
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


# ---------------------------------------------------------------------------
# Reader-facing vocabulary
#
# Internal words (view, evidence, deferred, attribution) must never reach the
# page. Every label a reader sees is looked up here, so there is exactly one
# place to check that promise.
# ---------------------------------------------------------------------------

VIEW_LABEL = {
    "change": "差分",
    "document": "文書",
    "orientation": "状況",
    "discussion": "会話",
}

VIEW_TITLE = {
    "change": "作業内容",
    "document": "文書",
    "orientation": "いまの状況",
    "discussion": "今の会話",
}

SOURCE_LABEL = {
    "unstaged": "未ステージ差分",
    "staged": "ステージ済み差分",
    "branch": "ブランチ差分",
    "commits": "コミット範囲",
    "plan": "実装計画",
    "handoff": "引き継ぎ",
    "session": "このセッション",
}

SCALE_UNIT = {
    "change": "変更",
    "document": "節",
    "orientation": "項目",
    "discussion": "論点",
}

INDEX_HEADING = {
    "change": "%d つの意図に分かれている",
    "document": "%d つのまとまりに分かれている",
    "orientation": "いま押さえるのは %d つ",
    "discussion": "話したことは %d つ",
}

LEDE_LABELS = {
    "change": ("なぜ", "どこまで"),
    "document": ("なぜ", "どこまで"),
    "orientation": ("なぜ", "どこまで"),
    "discussion": ("この会話の目的", "まだやっていないこと"),
}

# kind -> (badge text, rail class, badge modifier, heading above the item list)
KIND_STYLE = {
    "change": {
        "feature": ("新機能", "rail-primary", "", "やったこと"),
        "fix": ("修正", "rail-warning", "badge--warning", "直したこと"),
        "refactor": ("整理", "", "", "整理したこと"),
        "docs": ("文書", "", "", "書いたこと"),
        "test": ("テスト", "", "", "足したテスト"),
        "chore": ("雑務", "", "", "やったこと"),
    },
    "document": {
        "goal": ("ねらい", "rail-primary", "", "中身"),
        "design": ("設計", "rail-primary", "", "決めたこと"),
        "constraint": ("制約", "", "", "守ること"),
        "risk": ("危ないところ", "rail-warning", "badge--warning", "心配な点"),
        "step": ("手順", "", "", "やること"),
        "acceptance": ("できた条件", "rail-success", "badge--success", "満たすこと"),
    },
    "orientation": {
        "done": ("終わった", "rail-success", "badge--success", "済んだこと"),
        "inflight": ("進行中", "rail-primary", "", "やりかけ"),
        "next": ("次", "", "", "次にやること"),
        "blocked": ("止まってる", "rail-warning", "badge--warning", "詰まっていること"),
    },
    "discussion": {
        "topic": ("論点", "rail-primary", "", "出た話"),
        "decided": ("決定", "rail-success", "badge--success", "合意した内容"),
        "undecided": ("未決", "rail-warning", "badge--warning", "持ち越し"),
        "option": ("選択肢", "", "", "外した案"),
    },
}

# The header carries exactly two boxes. When more gets counted the numbers
# join an existing box; the box count never grows.
ATTENTION = {
    "change": ("要注意", None),
    "document": ("要注意", None),
    "orientation": ("詰まり", "blocked"),
    "discussion": ("未決", "undecided"),
}

RISK_LABEL = {"low": "低リスク", "medium": "中リスク", "high": "高リスク"}
CONFIDENCE_LABEL = {"low": "確度 低", "medium": "確度 中"}

MARKER_GLYPH = {"+": "+", "-": "−", " ": " "}
MARKER_CLASS = {"+": " add", "-": " del", " ": ""}

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SHARED_SCRIPTS = Path(__file__).resolve().parents[2] / "shared" / "scripts"

CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
    "base-uri 'none'; form-action 'none'"
)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _esc(value):
    """The single escaping choke point. Nothing reaches the page around it."""
    return html.escape("" if value is None else str(value), quote=True)


def _read_asset(name):
    return (ASSETS / name).read_text(encoding="utf-8")


def _extension_tokens():
    """The brief-only custom properties, emitted after the shared tokens."""
    data = json.loads(_read_asset("tokens.brief.json"))
    lines = ["  %s: %s;" % (name, value) for name, value in data["tokens"].items()]
    return ":root {\n" + "\n".join(lines) + "\n}"


def _kind_style(view, kind):
    return KIND_STYLE.get(view, {}).get(kind, (kind or "", "", "", "内容"))


def _attention_count(model, view):
    label, kind = ATTENTION.get(view, ("要注意", None))
    groups = [g for g in model["groups"] if isinstance(g, dict)]
    if kind is None:
        return label, sum(1 for g in groups if g.get("risk") == "high")
    return label, sum(
        len(g.get("items") or []) for g in groups if g.get("kind") == kind
    )


def _concern_count(model):
    return sum(
        len(g.get("concerns") or [])
        for g in model["groups"]
        if isinstance(g, dict)
    )


def _source_line(metadata):
    label = SOURCE_LABEL.get(metadata.get("source_kind"), metadata.get("source_kind"))
    parts = [label]
    if _filled(metadata.get("source_ref")):
        parts.append(metadata["source_ref"])
    if _filled(metadata.get("perspective")):
        parts.append(metadata["perspective"])
    return " — ".join(str(p) for p in parts if p)


def _render_bar(model, view):
    metadata = model["metadata"]
    groups = model["groups"]
    deferred = model.get("deferred") or []

    scale = "%d %s" % (len(groups), SCALE_UNIT.get(view, "件"))
    if deferred:
        scale += " · 除外 %d" % len(deferred)

    label, attention = _attention_count(model, view)
    flags = []
    if attention:
        flags.append("%s %d" % (label, attention))
    concerns = _concern_count(model)
    if concerns:
        flags.append("気になる点 %d" % concerns)

    out = [
        '<div class="bar">',
        '  <div class="bar-inner">',
        '    <span class="bar-id">brief / %s</span>' % _esc(VIEW_LABEL.get(view, view)),
        '    <span class="bar-target">%s</span>' % _esc(_source_line(metadata)),
        '    <span class="chips">',
        '      <span class="chipset scale" title="この画面の規模">%s</span>' % _esc(scale),
    ]
    if flags:
        out.append(
            '      <span class="chipset todo" title="注意して見るもの">'
            '<span class="flag">%s</span></span>' % _esc(" · ".join(flags))
        )
    out += [
        '      <button class="toggle-all" id="toggleAll" type="button"'
        ' data-state="open">すべて閉じる</button>',
        "    </span>",
        "  </div>",
        "</div>",
    ]
    return out


def _render_lede(model, view):
    summary = model["summary"]
    why_label, scope_label = LEDE_LABELS.get(view, ("なぜ", "どこまで"))
    return [
        '  <header class="lede">',
        '    <p class="eyebrow">つまり</p>',
        '    <h1 class="one-liner">%s</h1>' % _esc(summary["one_liner"]),
        '    <p class="meta"><b>%s</b> %s</p>'
        % (_esc(why_label), _esc(summary["purpose"])),
        '    <p class="meta"><b>%s</b> %s</p>'
        % (_esc(scope_label), _esc(summary["scope_note"])),
        "  </header>",
    ]


def _render_excerpt(excerpt):
    out = ['        <div class="diff">', '          <div class="diff-file">']
    out.append('            <span class="path">%s</span>' % _esc(excerpt["path"]))
    stat = []
    if excerpt.get("added") is not None:
        stat.append('<span class="plus">+%s</span>' % _esc(excerpt["added"]))
    if excerpt.get("removed") is not None:
        stat.append('<span class="minus">−%s</span>' % _esc(excerpt["removed"]))
    if stat:
        out.append('            <span class="stat">%s</span>' % " ".join(stat))
    out += ["          </div>", '          <div class="diff-body">']
    if _filled(excerpt.get("hunk_header")):
        out.append(
            '            <div class="diff-hunk">%s</div>' % _esc(excerpt["hunk_header"])
        )
    for line in excerpt["lines"]:
        marker = line.get("marker", " ")
        out.append(
            '            <div class="row%s">'
            '<span class="ln">%s</span><span class="ln">%s</span>'
            '<span class="mk">%s</span><span class="tx">%s</span></div>'
            % (
                MARKER_CLASS[marker],
                _esc(line.get("old") if line.get("old") is not None else ""),
                _esc(line.get("new") if line.get("new") is not None else ""),
                _esc(MARKER_GLYPH[marker]),
                _esc(line.get("text", "")),
            )
        )
    out += ["          </div>", "        </div>"]
    return out


def _render_group(group, position, view):
    badge, rail, modifier, items_heading = _kind_style(view, group.get("kind"))
    number = "%02d" % position
    classes = "card" + ((" " + rail) if rail else "")

    tags = ['<span class="badge">%s</span>' % _esc(badge)]
    risk = group.get("risk")
    tags.append(
        '<span class="badge%s">%s</span>'
        % (
            " badge--warning" if risk == "high" else "",
            _esc(RISK_LABEL.get(risk, risk)),
        )
    )
    if group.get("confidence") in CONFIDENCE_LABEL:
        tags.append(
            '<span class="badge%s">%s</span>'
            % (
                " badge--warning" if group["confidence"] == "low" else "",
                _esc(CONFIDENCE_LABEL[group["confidence"]]),
            )
        )
    items = group.get("items") or []
    if items:
        tags.append('<span class="count">%d 件</span>' % len(items))

    out = [
        '  <article class="group">',
        '    <div class="num">%s</div>' % _esc(number),
        '    <details class="%s" open>' % classes,
        "      <summary>",
        '        <span class="chevron">›</span>',
        '        <span class="head-row"><span class="title">'
        '<span class="num-inline">%s</span>%s</span>' % (_esc(number), _esc(group["title"])),
        '          <span class="tags">%s</span></span>' % "".join(tags),
        '        <span class="summary-line">%s</span>' % _esc(group["intent"]),
        "      </summary>",
        '      <div class="body">',
        "        <h4>どういうこと</h4>",
        "        <p>%s</p>" % _esc(group["plain_explanation"]),
    ]

    if items:
        out.append("        <h4>%s</h4>" % _esc(items_heading))
        out.append("        <ul>")
        out += ["          <li>%s</li>" % _esc(item) for item in items]
        out.append("        </ul>")

    excerpts = group.get("excerpts") or []
    if excerpts:
        out.append("        <h4>実際の差分</h4>")
        for excerpt in excerpts:
            out += _render_excerpt(excerpt)

    concerns = group.get("concerns") or []
    if concerns:
        out.append("        <h4>気になっている点</h4>")
        out += ['        <p class="concern">%s</p>' % _esc(c) for c in concerns]

    refs = group.get("evidence_refs") or []
    out += [
        "        <h4>根拠</h4>",
        '        <p class="evidence">%s</p>' % _esc(" / ".join(str(r) for r in refs)),
        "      </div>",
        "    </details>",
        "  </article>",
    ]
    return out


def _render_hidden_note(model, view):
    deferred = model.get("deferred") or []
    unit = SCALE_UNIT.get(view, "件")
    out = ['  <div class="hidden-note">']
    if not deferred:
        if view == "change":
            out.append(
                "    <p>このページに出していない変更はありません"
                "（差分では折りたたみへの退避を許していないため、集めた変更は"
                "すべて上のいずれかに含まれています）。</p>"
            )
        else:
            out.append("    <p>この画面に出していない%sはありません。</p>" % _esc(unit))
        out.append("  </div>")
        return out

    out.append(
        "    <p>この画面に出していない%sが %d 件あります。</p>" % (_esc(unit), len(deferred))
    )
    out.append("    <ul>")
    out += [
        "      <li>%s — %s</li>" % (_esc(entry["ref"]), _esc(entry["reason"]))
        for entry in deferred
    ]
    out += ["    </ul>", "  </div>"]
    return out


def render_html(model):
    """Render the model into one self-contained page. Deterministic by design."""
    view = model["metadata"]["view"]
    groups = model["groups"]

    out = [
        "<!DOCTYPE html>",
        '<html lang="ja">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" content="%s">' % CSP,
        "<title>brief — %s</title>" % _esc(VIEW_TITLE.get(view, view)),
        "<style>",
        _read_asset("tokens.css").rstrip("\n"),
        _extension_tokens(),
        _read_asset("brief.css").rstrip("\n"),
        "</style>",
        "</head>",
        "<body>",
        "",
    ]
    out += _render_bar(model, view)
    out += ["", '<main class="page">', ""]
    out += _render_lede(model, view)
    out += ["", '  <hr class="rule">', ""]
    out.append(
        '  <h2 class="section-label">%s</h2>'
        % _esc(INDEX_HEADING.get(view, "%d 件") % len(groups))
    )
    out.append("")
    for position, group in enumerate(groups, start=1):
        out += _render_group(group, position, view)
        out.append("")
    out += _render_hidden_note(model, view)
    out += ["", '  <hr class="rule">', ""]
    out += [
        '  <section class="questions">',
        '    <h2 class="section-label">読み終えたら</h2>',
        '    <p class="note">答え合わせはしません。'
        "答えられないことに気づくためだけの 3 問です。</p>",
        "    <ol>",
    ]
    out += [
        "      <li>%s</li>" % _esc(question)
        for question in model["comprehension_questions"]
    ]
    out += [
        "    </ol>",
        "  </section>",
        "",
        '  <p class="foot">brief / %s / %s</p>'
        % (_esc(view), _esc(model["metadata"]["run_id"])),
        "",
        "</main>",
        "",
        "<script>",
        _read_asset("brief.js").rstrip("\n"),
        "</script>",
        "</body>",
        "</html>",
        "",
    ]
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Secrets, opening, CLI
# ---------------------------------------------------------------------------


def _walk_strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _walk_strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_strings(value)


def scan_secrets(model):
    """Findings from the shared detector, or None when it cannot be loaded."""
    if str(SHARED_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SHARED_SCRIPTS))
    try:
        from secret_detect import detect_secrets
    except ImportError:
        return None
    findings = []
    for text in _walk_strings(model):
        findings += detect_secrets(text)
    return findings


def _is_wsl():
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        release = Path("/proc/sys/kernel/osrelease").read_text(encoding="utf-8")
    except OSError:
        return False
    return "microsoft" in release.lower()


def _opener_commands():
    system = platform.system()
    if system == "Darwin":
        return [["open"]]
    if system == "Windows":
        return [["cmd", "/c", "start", ""]]
    if _is_wsl():
        # Only wslview, deliberately. The browser lives on the Windows side, and
        # the Linux desktop openers cannot reach it — `gio open` in particular
        # exits 0 without opening anything, which would report a success that
        # never happened and send the reader to a page nobody displayed.
        return [["wslview"]]
    return [["xdg-open"], ["gio", "open"]]


def open_in_browser(path):
    """Return the opener that worked, or None. Never raises: a page that was
    written but not opened is still a success, and the caller prints the path."""
    for command in _opener_commands():
        binary = shutil.which(command[0])
        if not binary:
            continue
        try:
            subprocess.run(
                [binary] + command[1:] + [str(path)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
            )
        except (subprocess.SubprocessError, OSError):
            continue
        return command[0]
    return None


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _report(errors):
    print("✗ %d 件の違反:" % len(errors))
    for error in errors:
        print("  %s" % error)


def main(argv=None):
    parser = argparse.ArgumentParser(description="brief model validation and rendering")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("validate", help="check a model against the contract")
    check.add_argument("--model", required=True)
    check.add_argument("--inputs", help="JSON with the collected input identifiers")

    draw = sub.add_parser("render", help="render a validated model to HTML")
    draw.add_argument("--model", required=True)
    draw.add_argument("--inputs")
    draw.add_argument("--out", required=True)
    draw.add_argument("--open", action="store_true", dest="open_after")
    draw.add_argument(
        "--allow-secrets",
        action="store_true",
        help="render even though the input looks like it carries a credential",
    )

    args = parser.parse_args(argv)
    model = _load(args.model)
    inputs = _load(args.inputs) if args.inputs else None

    errors = validate_model(model, inputs)
    if errors:
        _report(errors)
        return 1
    if args.command == "validate":
        print("✓ モデルは契約を満たしている")
        return 0

    findings = scan_secrets(model)
    if findings and not args.allow_secrets:
        kinds = sorted({f["type"] for f in findings})
        print("✗ 秘密情報らしき文字列を %d 件検出: %s" % (len(findings), ", ".join(kinds)))
        print("  中身を確認し、問題なければ --allow-secrets を付けて再実行する")
        return 2

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(model), encoding="utf-8")
    print("生成した: %s" % out)

    if args.open_after:
        opener = open_in_browser(out.resolve())
        if opener:
            print("開いた: %s" % opener)
        else:
            print("自動で開けなかった。次のパスを手で開く: %s" % out.resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
