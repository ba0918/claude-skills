"""Finding Schema 検証・正規化・identity（冪等化）純関数。

契約: skills/shared/references/loop-engineering.md
  - §2 Finding Schema
  - §3 Finding Identity & 冪等化

標準ライブラリのみ使用。副作用（ファイル書き込み・削除）は一切行わない
（collect_queue_ids はファイル読み取りのみ）。
"""

import hashlib
import json
import os
import re

SEVERITIES = {"BLOCK", "WARN", "INFO"}
FIX_ACTIONS = {"AUTO_FIX", "NEEDS_JUDGMENT", "REPORT_ONLY"}

# collect_queue_ids が走査する open issue の相対サブディレクトリ名（archives/ は含めない。§3.2）
_READY_DIR = "ready"
_RUNNING_DIR = "running"
_FAILED_SUBDIRS = ("transient", "permanent")

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?\n)---\n", re.DOTALL)
_FINDING_ID_RE = re.compile(r"^finding_id:\s*(\S+)\s*$", re.MULTILINE)


def validate_finding(d):
    """Finding Schema (契約 §2) 準拠検証。エラーメッセージのリストを返す（空 = valid）。"""
    errors = []

    def _require_nonempty_str(key):
        value = d.get(key)
        if not isinstance(value, str) or value == "":
            errors.append(f"{key} must be a non-empty string")

    if not isinstance(d, dict):
        return ["finding must be a dict"]

    _require_nonempty_str("sensor")
    _require_nonempty_str("rule")

    severity = d.get("severity")
    if severity not in SEVERITIES:
        errors.append(f"severity must be one of {sorted(SEVERITIES)}")

    where = d.get("where")
    if not isinstance(where, dict):
        errors.append("where must be a dict")
    else:
        path = where.get("path")
        if not isinstance(path, str) or path == "":
            errors.append("where.path must be a non-empty string")
        if "line" in where and not isinstance(where.get("line"), int):
            errors.append("where.line must be an int when present")

    _require_nonempty_str("what")
    _require_nonempty_str("suggested_title")

    affected_paths = d.get("affected_paths")
    if not isinstance(affected_paths, list) or not all(
        isinstance(p, str) for p in affected_paths
    ):
        errors.append("affected_paths must be a list of strings")

    # fix_action は欠落・未知でもエラーにしない（normalize_finding が REPORT_ONLY に正規化する）

    return errors


def normalize_finding(d):
    """新しい dict を返す（入力を変異しない）。fix_action を fail-safe 正規化する。"""
    result = dict(d)
    if result.get("fix_action") not in FIX_ACTIONS:
        result["fix_action"] = "REPORT_ONLY"
    return result


def finding_id(sensor, rule, path, what):
    """sha256(f"{sensor}|{rule}|{path}|{what}") の hex 先頭 16 文字（契約 §3.1）。"""
    signature = f"{sensor}|{rule}|{path}|{what}"
    return hashlib.sha256(signature.encode("utf-8")).hexdigest()[:16]


def build_baseline(finding_ids):
    """{"version": 1, "suppressions": sorted(set(finding_ids))} を返す。"""
    return {"version": 1, "suppressions": sorted(set(finding_ids))}


def load_baseline(text):
    """baseline JSON 文字列 → suppressions の set。不正入力は空 set（fail-open）。"""
    if not text:
        return set()
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return set()
    if not isinstance(data, dict) or data.get("version") != 1:
        return set()
    suppressions = data.get("suppressions")
    if not isinstance(suppressions, list):
        return set()
    return set(suppressions)


def parse_frontmatter_finding_id(text):
    """issue ファイル本文の frontmatter から finding_id を抽出。無ければ None。"""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None
    frontmatter_body = match.group(1)
    id_match = _FINDING_ID_RE.search(frontmatter_body)
    if not id_match:
        return None
    return id_match.group(1)


def _read_finding_id(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None
    return parse_frontmatter_finding_id(text)


def _collect_md_files_in_dir(dir_path):
    if not os.path.isdir(dir_path):
        return []
    return [
        os.path.join(dir_path, name)
        for name in sorted(os.listdir(dir_path))
        if name.endswith(".md") and os.path.isfile(os.path.join(dir_path, name))
    ]


def collect_queue_ids(issues_root):
    """open issue（ready / running / failed/transient / failed/permanent / 直下）の finding_id を収集する。
    archives/ は走査しない（契約 §3.2）。存在しないサブディレクトリはスキップ。"""
    if not os.path.isdir(issues_root):
        return set()

    file_paths = []

    # 直下 *.md
    file_paths.extend(_collect_md_files_in_dir(issues_root))

    # ready/*.md
    file_paths.extend(_collect_md_files_in_dir(os.path.join(issues_root, _READY_DIR)))

    # running/*/issue.md
    running_dir = os.path.join(issues_root, _RUNNING_DIR)
    if os.path.isdir(running_dir):
        for name in sorted(os.listdir(running_dir)):
            task_dir = os.path.join(running_dir, name)
            issue_file = os.path.join(task_dir, "issue.md")
            if os.path.isdir(task_dir) and os.path.isfile(issue_file):
                file_paths.append(issue_file)

    # failed/transient/*.md, failed/permanent/*.md
    for subdir in _FAILED_SUBDIRS:
        file_paths.extend(
            _collect_md_files_in_dir(os.path.join(issues_root, "failed", subdir))
        )

    ids = set()
    for file_path in file_paths:
        fid = _read_finding_id(file_path)
        if fid is not None:
            ids.add(fid)
    return ids
