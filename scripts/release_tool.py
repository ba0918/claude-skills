#!/usr/bin/env python3
"""手動 release workflow の同期・notes 抽出を行う。"""

import argparse
import json
import os
import re
import sys


MANIFEST_RELPATHS = (
    os.path.join(".claude-plugin", "plugin.json"),
    os.path.join(".claude-plugin", "marketplace.json"),
    os.path.join(".codex-plugin", "plugin.json"),
    "package.json",
)

_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_UNRELEASED_HEADING_RE = re.compile(r"^## Unreleased[ \t]*$", re.MULTILINE)


class ReleaseError(Exception):
    """release 入力またはリポジトリ状態が安全な更新条件を満たさない。"""


def parse_version(version):
    """X.Y.Z を数値 tuple へ変換する。不正形式は ReleaseError。"""
    if not _VERSION_RE.fullmatch(version):
        raise ReleaseError(
            f"version must match X.Y.Z with numeric components: {version!r}"
        )
    return tuple(int(part) for part in version.split("."))


def manifest_versions(documents):
    """4 manifest の version 値を path と共に列挙する。"""
    found = []
    for relpath in MANIFEST_RELPATHS:
        document = documents[relpath]
        if relpath.endswith("marketplace.json"):
            plugins = document.get("plugins") if isinstance(document, dict) else None
            if not isinstance(plugins, list) or not plugins:
                raise ReleaseError(f"{relpath} must contain a non-empty plugins array")
            for index, plugin in enumerate(plugins):
                version = plugin.get("version") if isinstance(plugin, dict) else None
                if not isinstance(version, str):
                    raise ReleaseError(
                        f"{relpath} plugins[{index}].version must be a string"
                    )
                found.append((f"{relpath}:plugins[{index}]", version))
        else:
            version = document.get("version") if isinstance(document, dict) else None
            if not isinstance(version, str):
                raise ReleaseError(f"{relpath} version must be a string")
            found.append((relpath, version))
    return found


def update_manifest_documents(documents, version):
    """manifest document のコピーを version 同期して返す。"""
    updated = json.loads(json.dumps(documents))
    for relpath in MANIFEST_RELPATHS:
        document = updated[relpath]
        if relpath.endswith("marketplace.json"):
            for plugin in document["plugins"]:
                plugin["version"] = version
        else:
            document["version"] = version
    return updated


def plan_sync(changelog, documents, version):
    """同期可否を判定し、書き込み対象と結果 JSON を返す純関数。"""
    requested = parse_version(version)
    found = manifest_versions(documents)
    distinct = sorted({current for _, current in found})
    if len(distinct) != 1:
        detail = ", ".join(f"{path}={current}" for path, current in found)
        raise ReleaseError(f"manifest version drift detected: {detail}")

    current = distinct[0]
    current_tuple = parse_version(current)
    version_heading = re.compile(
        rf"^## {re.escape(version)}[ \t]*$", re.MULTILINE
    )
    has_version_heading = version_heading.search(changelog) is not None
    has_unreleased = _UNRELEASED_HEADING_RE.search(changelog) is not None

    if current == version and has_version_heading and not has_unreleased:
        return None, None, {
            "changed": False,
            "previous_version": current,
            "version": version,
        }
    if requested <= current_tuple:
        raise ReleaseError(
            f"new version {version} must be greater than current version {current}"
        )
    if not has_unreleased:
        raise ReleaseError(
            "CHANGELOG.md has no ## Unreleased heading in a non-idempotent state"
        )
    if has_version_heading:
        raise ReleaseError(
            f"CHANGELOG.md already contains ## {version} while ## Unreleased remains"
        )
    if len(_UNRELEASED_HEADING_RE.findall(changelog)) != 1:
        raise ReleaseError("CHANGELOG.md must contain exactly one ## Unreleased heading")

    updated_changelog = _UNRELEASED_HEADING_RE.sub(
        f"## {version}", changelog, count=1
    )
    updated_documents = update_manifest_documents(documents, version)
    return updated_changelog, updated_documents, {
        "changed": True,
        "previous_version": current,
        "version": version,
    }


def extract_notes(changelog, version):
    """指定 version の CHANGELOG 節を次の level-2 見出し手前まで抜き出す。"""
    parse_version(version)
    heading = re.compile(rf"^## {re.escape(version)}[ \t]*$", re.MULTILINE)
    match = heading.search(changelog)
    if match is None:
        raise ReleaseError(f"CHANGELOG.md has no ## {version} heading")
    next_heading = re.search(r"^## .+$", changelog[match.end():], re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(changelog)
    return changelog[match.start():end].strip() + "\n"


def _read_text(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except OSError as exc:
        raise ReleaseError(f"cannot read {path}: {exc}")


def _read_json(path):
    try:
        return json.loads(_read_text(path))
    except json.JSONDecodeError as exc:
        raise ReleaseError(f"invalid JSON in {path}: {exc}")


def _write_text(path, text):
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
    except OSError as exc:
        raise ReleaseError(f"cannot write {path}: {exc}")


def _write_json(path, document):
    _write_text(path, json.dumps(document, ensure_ascii=False, indent=2) + "\n")


def sync_release(repo_root, version):
    """CHANGELOG と 4 manifest を検証後に同期する。"""
    changelog_path = os.path.join(repo_root, "CHANGELOG.md")
    changelog = _read_text(changelog_path)
    documents = {
        relpath: _read_json(os.path.join(repo_root, relpath))
        for relpath in MANIFEST_RELPATHS
    }
    updated_changelog, updated_documents, result = plan_sync(
        changelog, documents, version
    )
    if not result["changed"]:
        return result

    _write_text(changelog_path, updated_changelog)
    for relpath in MANIFEST_RELPATHS:
        _write_json(os.path.join(repo_root, relpath), updated_documents[relpath])
    return result


def run(argv=None):
    """CLI を実行して終了コードを返す。"""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync", help="release version を同期する")
    sync_parser.add_argument("--version", required=True)
    sync_parser.add_argument("--repo-root", default=".")

    notes_parser = subparsers.add_parser("notes", help="CHANGELOG の release notes を抽出する")
    notes_parser.add_argument("--version", required=True)
    notes_parser.add_argument("--repo-root", default=".")

    args = parser.parse_args(argv)
    if args.command == "sync":
        print(json.dumps(sync_release(args.repo_root, args.version), ensure_ascii=False))
    else:
        changelog = _read_text(os.path.join(args.repo_root, "CHANGELOG.md"))
        sys.stdout.write(extract_notes(changelog, args.version))
    return 0


def main():
    try:
        sys.exit(run())
    except ReleaseError as exc:
        print(f"release error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
