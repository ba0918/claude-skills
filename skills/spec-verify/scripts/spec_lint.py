#!/usr/bin/env python3
"""spec-verify: hand-rolled structural linter for clause files (schema v1).

The vocabulary source of truth is references/clause-schema.md; the constants
below mirror its tables and are kept in sync by test_spec_lint (three-way:
md tables <-> these constants <-> references/spec-clause.schema.json). The
schema.json projection is NOT read at runtime — stdlib has no jsonschema, so
validation is hand-rolled (dossier_lint.py precedent).

Finding schema (every finding): {where, what, why, how, check}
  where = "<file>#<clause id>" / what = violation / why = rationale /
  how = fix instruction / check = machine slug (fixtures/README.md 違反種別).

Exit codes (contract table in clause-schema.md):
  0 = run succeeded (report-only default: even with findings; zero targets too)
  1 = findings present, --strict only
  2 = input corruption / usage error (mode-independent; diagnostics-only
      output marked valid: false — partial results are never published as
      authoritative)
"""

import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "..", "..", "shared", "scripts"))
import secret_detect  # noqa: E402

# ---------------------------------------------------------------------------
# Schema constants (single source: references/clause-schema.md)
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1
MAX_SIZE = 1_000_000   # bytes; real clause files are a few KB
MAX_CLAUSES = 10_000   # per file; expected real scale is hundreds
MAX_DEPTH = 16         # valid schema depth is 6; anything deeper is hostile

ID_PATTERN = r"^[A-Z][A-Z0-9]*(-[A-Z0-9]+)*-[0-9]{3,}$"
_ID_RE = re.compile(ID_PATTERN)

KINDS = ("invariant", "pre_post", "transition", "authorization")
EFFECT_VALUES = ("allow", "deny")

# {field: (type token, required)} — tokens fixed by the md parse contract.
TOPLEVEL_FIELDS = {
    "schema_version": ("integer", True),
    "clauses": ("array[object]", True),
}

ENVELOPE_FIELDS = {
    "id": ("string", True),
    "revision": ("integer", True),
    "kind": ("string", True),
    "statement": ("string", True),
    "payload": ("object", True),
    "rationale": ("string", False),
    "examples": ("array[string]", False),
    "counterexamples": ("array[string]", False),
    "refs": ("array[string]", False),
    "superseded_by": ("array[string]", False),
    "predicates": ("array[string]", False),
}

PAYLOAD_FIELDS = {
    "invariant": {
        "target": ("string", True),
        "condition": ("string", True),
    },
    "pre_post": {
        "input_domain": ("string", True),
        "precondition": ("string", True),
        "operation": ("string", True),
        "postcondition": ("string", True),
    },
    "transition": {
        "states": ("array[string]", True),
        "events": ("array[string]", True),
        "transitions": ("array[object]", True),
        "forbidden": ("array[object]", False),
    },
    "authorization": {
        "subject": ("string", True),
        "action": ("string", True),
        "resource": ("string", True),
        "context": ("string", False),
        "effect": ("string", True),
    },
}

TRANSITION_RULE_FIELDS = {
    "from": ("string", True),
    "event": ("string", True),
    "to": ("string", True),
    "guard": ("string", False),
}
FORBIDDEN_RULE_FIELDS = {
    "from": ("string", True),
    "event": ("string", True),
}
_NESTED_RULE_FIELDS = {
    "transitions": TRANSITION_RULE_FIELDS,
    "forbidden": FORBIDDEN_RULE_FIELDS,
}

MIN_ITEMS = {"states": 1, "events": 1}

# Free-text fields under the 機密情報の規約 (synthetic/anonymous data only).
_SECRET_SCAN_STRINGS = ("statement", "rationale")
_SECRET_SCAN_ARRAYS = ("examples", "counterexamples")

_CTRL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")


class SpecLintError(Exception):
    """Input corruption / usage error (maps to exit 2)."""

    def __init__(self, category, message):
        super().__init__(message)
        self.category = category
        self.message = message


# ---------------------------------------------------------------------------
# Fail-closed loading
# ---------------------------------------------------------------------------

class _DuplicateKeyError(ValueError):
    pass


def _reject_duplicate_keys(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise _DuplicateKeyError(f"重複 JSON key: {key}")
        seen[key] = value
    return seen


def _check_depth(data):
    stack = [(data, 1)]
    while stack:
        node, depth = stack.pop()
        if depth > MAX_DEPTH:
            raise SpecLintError(
                "too-deep", f"ネスト深さが上限 {MAX_DEPTH} を超過")
        if isinstance(node, dict):
            stack.extend((v, depth + 1) for v in node.values())
        elif isinstance(node, list):
            stack.extend((v, depth + 1) for v in node)


def load_clause_file(path):
    """Parse one clause file fail-closed. Raise SpecLintError on corruption
    (size / broken JSON / duplicate key / nesting depth); no traceback leaks."""
    try:
        if os.stat(path).st_size > MAX_SIZE:
            raise SpecLintError(
                "file-too-large", f"ファイルサイズが上限 {MAX_SIZE}B を超過")
    except OSError as e:
        raise SpecLintError("unreadable", f"読み取り不能 ({type(e).__name__})")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.loads(f.read(),
                              object_pairs_hook=_reject_duplicate_keys)
    except _DuplicateKeyError as e:
        raise SpecLintError("duplicate-json-key", str(e))
    except (json.JSONDecodeError, RecursionError, UnicodeDecodeError,
            ValueError, OSError) as e:
        raise SpecLintError(
            "invalid-json", f"JSON として parse できない ({type(e).__name__})")
    _check_depth(data)
    return data


def validate_toplevel(data, name):
    """Return (clauses, toplevel findings). Raise SpecLintError for file
    structure corruption per clause-schema.md ファイル構造節 (exit 2 class)."""
    if not isinstance(data, dict):
        raise SpecLintError("not-an-object", "トップレベルが object でない")
    missing = [k for k, (_t, req) in TOPLEVEL_FIELDS.items()
               if req and k not in data]
    if missing:
        raise SpecLintError(
            "missing-toplevel-key",
            f"トップレベル必須キーが欠落: {', '.join(missing)}")
    version = data["schema_version"]
    if isinstance(version, bool) or not isinstance(version, int) \
            or version != SCHEMA_VERSION:
        raise SpecLintError(
            "unknown-schema-version",
            f"schema_version が未知（v1 は {SCHEMA_VERSION} 固定）")
    clauses = data["clauses"]
    if not isinstance(clauses, list):
        raise SpecLintError("clauses-not-array", "clauses が配列でない")
    if len(clauses) > MAX_CLAUSES:
        raise SpecLintError(
            "too-many-clauses", f"条項数が上限 {MAX_CLAUSES} を超過")
    findings = []
    for key in sorted(set(data) - set(TOPLEVEL_FIELDS)):
        findings.append(_finding(
            f"{name}#(file)", "unknown-key",
            f"トップレベルに未知キー {key!r}",
            "未知キーは fail-closed（typo がサイレントに無視される事故防止）",
            "キーを削除するか、schema_version / clauses に修正する"))
    return clauses, findings


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

def _finding(where, check, what, why, how):
    return {"where": where, "check": check, "what": what, "why": why,
            "how": how}


def _finalize(findings):
    """Mask secrets in free-text diagnostic fields (never in where — it holds
    file paths and clause IDs that masking would destroy), strip control
    characters everywhere, and sort deterministically."""
    out = []
    for f in findings:
        g = dict(f)
        for key in ("what", "why", "how"):
            g[key] = secret_detect.mask_secrets(g[key])
        for key in ("where", "what", "why", "how"):
            g[key] = _CTRL_RE.sub("", g[key])
        out.append(g)
    out.sort(key=lambda f: (f["where"], f["check"], f["what"]))
    return out


# ---------------------------------------------------------------------------
# Value validators
# ---------------------------------------------------------------------------

def _check_string(findings, where, field, value, required):
    if not isinstance(value, str):
        findings.append(_finding(
            where, "invalid-type",
            f"{field} が string でない（{type(value).__name__}）",
            "型が契約と異なると生成テストと digest が壊れる",
            f"{field} を非空の string にする"))
        return
    if not value:
        check = "empty-required-string" if required else "empty-string"
        findings.append(_finding(
            where, check, f"{field} が空文字列",
            "「値なし」は空文字列でなくキー省略で表現する規則（任意フィールドのみ可）",
            f"{field} に内容を書くか、任意フィールドならキーごと削除する"))


def _check_string_array(findings, where, field, value):
    if not isinstance(value, list):
        findings.append(_finding(
            where, "invalid-type",
            f"{field} が配列でない（{type(value).__name__}）",
            "型が契約と異なると機械検証が成立しない",
            f"{field} を string の配列にする"))
        return False
    for i, item in enumerate(value):
        if not isinstance(item, str):
            findings.append(_finding(
                where, "invalid-type",
                f"{field}[{i}] が string でない（{type(item).__name__}）",
                "array[string] の要素は非空 string のみ",
                f"{field}[{i}] を string にする"))
        elif not item:
            findings.append(_finding(
                where, "empty-string", f"{field}[{i}] が空文字列",
                "array[string] の要素は非空が必須（検証の共通規則）",
                f"{field}[{i}] に内容を書くか要素を削除する"))
    return True


def _check_revision(findings, where, value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        findings.append(_finding(
            where, "invalid-revision",
            f"revision が正整数でない: {value!r}",
            "revision は 1 以上の単調増加カウンタ（意味変更ごとに +1）",
            "revision を 1 以上の整数にする"))


def _check_rule_object(findings, where, field, index, rule, rule_fields):
    if not isinstance(rule, dict):
        findings.append(_finding(
            where, "invalid-type",
            f"{field}[{index}] が object でない（{type(rule).__name__}）",
            f"{field} の各要素は from/event 等を持つ object",
            f"{field}[{index}] を object にする"))
        return
    for key in sorted(set(rule) - set(rule_fields)):
        findings.append(_finding(
            where, "unknown-key",
            f"{field}[{index}] に未知キー {key!r}",
            "未知キーは fail-closed（書いたつもりの契約が消える事故防止）",
            f"{field}[{index}] のキーを {'/'.join(rule_fields)} に限定する"))
    for name, (_token, required) in rule_fields.items():
        if name not in rule:
            if required:
                findings.append(_finding(
                    where, "missing-required",
                    f"{field}[{index}] に必須キー {name} が欠落",
                    "遷移規則は from/event（/to）が揃って初めて検証可能になる",
                    f"{field}[{index}] に {name} を追加する"))
            continue
        _check_string(findings, where, f"{field}[{index}].{name}",
                      rule[name], required)


def _check_payload(findings, where, kind, payload):
    spec = PAYLOAD_FIELDS[kind]
    for key in sorted(set(payload) - set(spec)):
        findings.append(_finding(
            where, "unknown-key",
            f"payload に未知キー {key!r}（kind: {kind}）",
            "未知キーは fail-closed（typo がサイレントに無視される事故防止）",
            f"payload のキーを {'/'.join(spec)} に限定する"))
    for field, (token, required) in spec.items():
        if field not in payload:
            if required:
                findings.append(_finding(
                    where, "payload-missing-required",
                    f"payload に必須キー {field} が欠落（kind: {kind}）",
                    "kind 別 payload が揃わないとテスト生成と digest 算出ができない",
                    f"payload に {field} を追加する"))
            continue
        value = payload[field]
        if token == "string":
            _check_string(findings, where, f"payload.{field}", value, required)
            if field == "effect" and isinstance(value, str) and value \
                    and value not in EFFECT_VALUES:
                findings.append(_finding(
                    where, "invalid-enum",
                    f"effect が enum 外: {value!r}",
                    f"effect は {'/'.join(EFFECT_VALUES)} のみ（deny 優先の意味論）",
                    f"effect を {'/'.join(EFFECT_VALUES)} のいずれかにする"))
        elif token == "array[string]":
            ok = _check_string_array(findings, where, f"payload.{field}", value)
            if ok and field in MIN_ITEMS and len(value) < MIN_ITEMS[field]:
                findings.append(_finding(
                    where, "min-items",
                    f"payload.{field} が空（{MIN_ITEMS[field]} 要素以上が必須）",
                    "状態機械は状態・イベント集合が空だと定義できない",
                    f"payload.{field} に {MIN_ITEMS[field]} 要素以上を列挙する"))
        elif token == "array[object]":
            if not isinstance(value, list):
                findings.append(_finding(
                    where, "invalid-type",
                    f"payload.{field} が配列でない（{type(value).__name__}）",
                    "型が契約と異なると機械検証が成立しない",
                    f"payload.{field} を object の配列にする"))
                continue
            for i, rule in enumerate(value):
                _check_rule_object(findings, where, f"payload.{field}", i,
                                   rule, _NESTED_RULE_FIELDS[field])


def _scan_secrets(findings, where, clause):
    hits = []
    for field in _SECRET_SCAN_STRINGS:
        value = clause.get(field)
        if isinstance(value, str) and secret_detect.detect_secrets(value):
            hits.append(field)
    for field in _SECRET_SCAN_ARRAYS:
        value = clause.get(field)
        if isinstance(value, list) and any(
                isinstance(v, str) and secret_detect.detect_secrets(v)
                for v in value):
            hits.append(field)
    for field in hits:
        # 検出のみ（値は再掲しない）。黙って書き換えない — 仕様正本の
        # 無断改変はドリフトそのものだから（clause-schema.md 機密情報の規約）。
        findings.append(_finding(
            where, "secret-in-free-text",
            f"{field} に credential らしき文字列を検出",
            "自由文フィールドは合成・匿名データ限定（機密情報の規約）",
            f"{field} から実在の credential・個人情報を除去し合成データに差し替える"))


def _check_clause(findings, name, index, clause):
    """Validate one clause envelope + payload. Return (id, superseded_by);
    id is None unless it matches ID_PATTERN (invalid ids never become where
    labels or known ids — see the cid_valid comment below)."""
    if not isinstance(clause, dict):
        findings.append(_finding(
            f"{name}#clauses[{index}]", "invalid-type",
            f"条項が object でない（{type(clause).__name__}）",
            "条項は envelope フィールドを持つ object",
            "条項を id/revision/kind/statement/payload を持つ object にする"))
        return None, []
    cid = clause.get("id")
    # パターン不一致の id は where ラベルにも既知 ID 登録にも使わない —
    # where は mask_secrets の対象外（ファイルパス・条項 ID を破壊しないため）
    # なので、生の不正値（credential の可能性がある）が where 経由で露出する。
    cid_valid = isinstance(cid, str) and bool(cid) \
        and _ID_RE.fullmatch(cid) is not None
    label = cid if cid_valid else f"clauses[{index}]"
    where = f"{name}#{label}"

    for key in sorted(set(clause) - set(ENVELOPE_FIELDS)):
        findings.append(_finding(
            where, "unknown-key",
            f"envelope に未知キー {key!r}",
            "未知キーは fail-closed（typo がサイレントに無視される事故防止）",
            f"キーを削除するか envelope のフィールド名（{'/'.join(ENVELOPE_FIELDS)}）に修正する"))

    for field, (token, required) in ENVELOPE_FIELDS.items():
        if field not in clause:
            if required:
                findings.append(_finding(
                    where, "missing-required",
                    f"必須フィールド {field} が欠落",
                    "envelope 必須フィールドが揃わない条項は契約として不完全",
                    f"{field} を追加する"))
            continue
        value = clause[field]
        if field == "revision":
            _check_revision(findings, where, value)
        elif token == "string":
            _check_string(findings, where, field, value, required)
        elif token == "object":
            if not isinstance(value, dict):
                findings.append(_finding(
                    where, "invalid-type",
                    f"{field} が object でない（{type(value).__name__}）",
                    "payload は kind 別の必須キーを持つ object",
                    f"{field} を object にする"))
        elif token == "array[string]":
            _check_string_array(findings, where, field, value)

    if isinstance(cid, str) and cid and not cid_valid:
        findings.append(_finding(
            where, "invalid-id",
            f"id がパターン {ID_PATTERN} に合わない: {cid!r}",
            "ID は namespace 付き ASCII 識別子（例: LIB-INV-001）に固定されている",
            "id を大文字英数セグメント + 3 桁以上の連番の形式にする"))

    kind = clause.get("kind")
    if isinstance(kind, str) and kind and kind not in KINDS:
        findings.append(_finding(
            where, "unknown-kind",
            f"kind が enum 外: {kind!r}",
            f"v1 の検証意味論は {'/'.join(KINDS)} の 4 種のみ",
            f"kind を {'/'.join(KINDS)} のいずれかにする"))

    payload = clause.get("payload")
    if kind in KINDS and isinstance(payload, dict):
        _check_payload(findings, where, kind, payload)

    successors = clause.get("superseded_by")
    if isinstance(successors, list):
        for i, succ in enumerate(successors):
            if isinstance(succ, str) and succ and not _ID_RE.fullmatch(succ):
                findings.append(_finding(
                    where, "invalid-id",
                    f"superseded_by[{i}] が ID パターンに合わない: {succ!r}",
                    "後継参照も条項 ID パターンに従う",
                    f"superseded_by[{i}] を正しい条項 ID にする"))
        successors = [s for s in successors if isinstance(s, str) and s]
    else:
        successors = []

    _scan_secrets(findings, where, clause)
    return (cid if cid_valid else None), successors


# ---------------------------------------------------------------------------
# Reference integrity (superseded_by graph across all files of the run)
# ---------------------------------------------------------------------------

def _nontrivial_sccs(graph):
    """Iterative Tarjan; return SCCs with >1 node (self-loops are reported
    separately as self-superseded-by, so they are excluded from the graph)."""
    index, low, onstack, stack, sccs = {}, {}, set(), [], []
    counter = [0]
    for start in sorted(graph):
        if start in index:
            continue
        index[start] = low[start] = counter[0]
        counter[0] += 1
        stack.append(start)
        onstack.add(start)
        work = [(start, iter(sorted(graph[start])))]
        while work:
            node, it = work[-1]
            pushed = False
            for succ in it:
                if succ not in index:
                    index[succ] = low[succ] = counter[0]
                    counter[0] += 1
                    stack.append(succ)
                    onstack.add(succ)
                    work.append((succ, iter(sorted(graph[succ]))))
                    pushed = True
                    break
                if succ in onstack:
                    low[node] = min(low[node], index[succ])
            if pushed:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                component = []
                while True:
                    member = stack.pop()
                    onstack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                if len(component) > 1:
                    sccs.append(sorted(component))
    return sccs


def _check_references(findings, tombstones, known_ids, file_of):
    graph = {}
    for name, cid, successors in tombstones:
        where = f"{name}#{cid}"
        for succ in successors:
            if succ == cid:
                findings.append(_finding(
                    where, "self-superseded-by",
                    "superseded_by が自分自身を参照",
                    "自己参照はライフサイクル（分割・統合・廃止）を表現しない",
                    "後継 ID を実在する別条項にするか、後継なし廃止は空配列にする"))
            elif succ not in known_ids:
                findings.append(_finding(
                    where, "dangling-superseded-by",
                    f"superseded_by が存在しない条項 ID を参照: {succ}",
                    "実在しない後継への参照は履歴の断絶（tombstone 削除の兆候）",
                    f"後継条項 {succ} を追加するか参照を実在 ID に直す"))
            else:
                graph.setdefault(cid, set()).add(succ)
    for node in list(graph):
        for succ in graph[node]:
            graph.setdefault(succ, set())
    for component in _nontrivial_sccs(graph):
        head = component[0]
        findings.append(_finding(
            f"{file_of[head]}#{head}", "cycle-superseded-by",
            f"superseded_by が循環: {' -> '.join(component)}",
            "循環する後継参照はどれが現役条項か決定できない",
            "循環を断ち、現役条項には superseded_by を付けない"))


# ---------------------------------------------------------------------------
# Core lint
# ---------------------------------------------------------------------------

def lint_data(named_files):
    """Lint parsed clause files [(name, data), ...]. Never raises: file
    structure corruption becomes a diagnostic (exit-2 class), clause-level
    violations become findings (exit-1 class under --strict)."""
    findings = []
    diagnostics = []
    clause_total = 0
    tombstone_total = 0
    known_ids = set()
    tombstones = []
    file_of = {}
    per_file_ids = []

    for name, data in named_files:
        try:
            clauses, top_findings = validate_toplevel(data, name)
        except SpecLintError as e:
            diagnostics.append({"file": name, "category": e.category,
                                "message": secret_detect.mask_secrets(e.message)})
            continue
        findings.extend(top_findings)
        clause_total += len(clauses)
        ids_here = {}
        for index, clause in enumerate(clauses):
            cid, successors = _check_clause(findings, name, index, clause)
            if isinstance(clause, dict) and "superseded_by" in clause:
                tombstone_total += 1
            if cid is None:
                continue
            ids_here[cid] = ids_here.get(cid, 0) + 1
            known_ids.add(cid)
            file_of.setdefault(cid, name)
            if successors:
                tombstones.append((name, cid, successors))
        per_file_ids.append((name, ids_here))

    for name, ids_here in per_file_ids:
        for cid, count in sorted(ids_here.items()):
            if count > 1:
                findings.append(_finding(
                    f"{name}#{cid}", "duplicate-id",
                    f"id がファイル内で重複（{count} 回出現）",
                    "同一ファイル内の ID 重複は禁止（どちらが正か決定できない）",
                    "片方の条項に新しい ID を採番する（既存 ID の再利用は禁止）"))

    _check_references(findings, tombstones, known_ids, file_of)

    findings = _finalize(findings)
    by_check = {}
    for f in findings:
        by_check[f["check"]] = by_check.get(f["check"], 0) + 1
    return {
        "findings": findings,
        "diagnostics": diagnostics,
        "corrupt": bool(diagnostics),
        "findings_present": bool(findings),
        "summary": {
            "files": len(named_files),
            "corrupt_files": len(diagnostics),
            "clauses": clause_total,
            "tombstones": tombstone_total,
            "findings": len(findings),
            "by_check": by_check,
            "truncated": False,
        },
    }


def _merge_diagnostics(result, extra_diagnostics, total_files):
    """Prepend pre-lint diagnostics (load / containment failures) and restate
    the file counters over the full target set, keeping the corrupt flag and
    summary consistent with the merged view."""
    result["diagnostics"] = extra_diagnostics + result["diagnostics"]
    result["corrupt"] = bool(result["diagnostics"])
    result["summary"]["files"] = total_files
    result["summary"]["corrupt_files"] = len(result["diagnostics"])
    return result


def lint_paths(paths, names=None):
    """Load + lint clause files. Load failures join the diagnostics (the run
    still collects findings from healthy files, but exits 2 overall)."""
    display = list(names) if names is not None else list(paths)
    entries = []
    load_diagnostics = []
    for path, name in zip(paths, display):
        try:
            entries.append((name, load_clause_file(path)))
        except SpecLintError as e:
            load_diagnostics.append({
                "file": name, "category": e.category,
                "message": secret_detect.mask_secrets(e.message)})
    return _merge_diagnostics(lint_data(entries), load_diagnostics,
                              len(display))


# ---------------------------------------------------------------------------
# Path containment
# ---------------------------------------------------------------------------

def check_containment(path, root):
    """Reject any target outside root. Symlinks are checked on every existing
    component BEFORE canonicalization, then realpath() + commonpath() confirms
    canonical containment (context-audit/collect_targets.py の検査順序を踏襲)。"""
    root_abs = os.path.abspath(root)
    path_abs = os.path.abspath(path)
    try:
        rel = os.path.relpath(path_abs, root_abs)
    except ValueError:
        raise SpecLintError("path-escape", f"対象が root 外: {path}")
    if rel == ".." or rel.startswith(".." + os.sep) or os.path.isabs(rel):
        raise SpecLintError("path-escape", f"対象が root 外: {path}")
    current = root_abs
    for part in rel.split(os.sep):
        current = os.path.join(current, part)
        if os.path.islink(current):
            raise SpecLintError(
                "path-escape", f"symlink を含むパスは拒否: {path}")
    resolved = os.path.realpath(path_abs)
    root_resolved = os.path.realpath(root_abs)
    if os.path.commonpath([resolved, root_resolved]) != root_resolved:
        raise SpecLintError("path-escape", f"対象が root 外に解決される: {path}")
    return resolved


# ---------------------------------------------------------------------------
# Output (summary-first, stable order; JSON is json.dumps only)
# ---------------------------------------------------------------------------

def _sanitize_line(line):
    return _CTRL_RE.sub("", line)


def render_text(result):
    s = result["summary"]
    lines = [
        f"spec_lint summary: files={s['files']} corrupt={s['corrupt_files']} "
        f"clauses={s['clauses']} tombstones={s['tombstones']} "
        f"findings={s['findings']}"
        + (" (表示は --max-errors で打ち切り)" if s["truncated"] else "")]
    if s["files"] == 0:
        lines.append("対象 0 件: 条項ファイルが見つからない（specs/clauses/*.json）")
    for d in result["diagnostics"]:
        lines.append(f"[{d['file']}] input-corruption({d['category']}): "
                     f"{d['message']}")
    for f in result["findings"]:
        lines.append(f"[{f['where']}] {f['check']}: {f['what']} | "
                     f"why: {f['why']} | fix: {f['how']}")
    if not result["diagnostics"] and not result["findings"] and s["files"]:
        lines.append("違反なし: 全条項ファイルが schema v1 に適合")
    return "\n".join(_sanitize_line(line) for line in lines)


def render_json(result):
    return json.dumps({
        "valid": not result["corrupt"],
        "findings_present": result["findings_present"],
        "summary": result["summary"],
        "diagnostics": result["diagnostics"],
        "findings": result["findings"],
    }, indent=2, ensure_ascii=False)


def exit_code(result, strict):
    if result["corrupt"]:
        return 2
    if strict and result["findings_present"]:
        return 1
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="spec-verify 条項ファイルの構造 lint（schema v1）")
    parser.add_argument("paths", nargs="*",
                        help="条項ファイル（省略時は <root>/specs/clauses/*.json）")
    parser.add_argument("--root", required=True,
                        help="対象プロジェクトルート（containment 境界）")
    parser.add_argument("--strict", action="store_true",
                        help="検出ありを exit 1 にする（既定は report-only）")
    parser.add_argument("--json", action="store_true", help="JSON で出力する")
    parser.add_argument("--max-errors", type=int, default=200,
                        help="findings の表示上限（サマリーは全件を数える）")
    args = parser.parse_args(argv)

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"usage-error: root がディレクトリでない: {args.root}",
              file=sys.stderr)
        return 2

    paths = args.paths or sorted(
        glob.glob(os.path.join(root, "specs", "clauses", "*.json")))

    contained = []
    containment_diagnostics = []
    for path in paths:
        try:
            resolved = check_containment(path, root)
        except SpecLintError as e:
            # mask_secrets は適用しない: containment 診断の message はパスのみで、
            # マスク（home_path 等）はパス情報を破壊し原因特定を不能にする。
            containment_diagnostics.append({
                "file": path, "category": e.category, "message": e.message})
            continue
        contained.append((resolved, os.path.relpath(resolved, root)))

    result = lint_paths([p for p, _n in contained],
                        names=[n for _p, n in contained])
    result = _merge_diagnostics(result, containment_diagnostics, len(paths))

    if args.max_errors >= 0 and len(result["findings"]) > args.max_errors:
        result["findings"] = result["findings"][:args.max_errors]
        result["summary"]["truncated"] = True

    print(render_json(result) if args.json else render_text(result))
    return exit_code(result, args.strict)


if __name__ == "__main__":
    sys.exit(main())
