#!/usr/bin/env python3
"""リポジトリ整合性バリデータ。

このリポジトリの「コード」は markdown のスキル定義なので、
壊れやすいのはリンク・対応表・バージョン同期といったドキュメント間の整合性。
それらを機械的に検証する。CI（GitHub Actions）とローカルの両方から実行できる。

実行: python3 scripts/validate_repo.py [repo_root]
終了コード: 0 = 全チェック合格 / 1 = 違反あり

チェック項目:
  1. 壊れた symlink が存在しない
  2. skills/ / codex-skills/ の各スキルディレクトリに SKILL.md がある
  3. SKILL.md frontmatter に name / description がある
  4. commands/*.md frontmatter に description がある
  5. SKILL.md / commands/*.md 内の相対 .md リンクが実在する
  6. CLAUDE.md のコマンド対応表 ⇔ commands/ 実ファイルが一致する
  7. README.md が全スキル名に言及している（ドリフト検出）
  8. AGENTS.md が全 codex-skills 名に言及している（ドリフト検出）
  9. plugin.json と marketplace.json のバージョンが一致する
"""
import json
import os
import re
import sys

EXCLUDED_DIRS = {".git", ".claude", ".codex", "node_modules", "__pycache__"}

# 例示用プレースホルダと判定するパターン: {var} 含み / URL / アンカー /
# タイムスタンプ始まりのファイル名（docs 生成物の例示）
_TIMESTAMP_EXAMPLE = re.compile(r"^\d{8,}")
_LINK_RE = re.compile(r"\]\(([^)\s]+)\)")
_COMMAND_REF_RE = re.compile(r"commands/[a-z0-9-]+\.md")


def extract_md_links(text):
    """markdown テキストから .md へのリンクターゲットを抽出する（アンカーは除去）。"""
    links = []
    for target in _LINK_RE.findall(text):
        target = target.split("#", 1)[0]
        if target.endswith(".md"):
            links.append(target)
    return links


def is_checkable_link(link):
    """実在チェックすべき相対 .md リンクなら True。プレースホルダ・URL・例示は除外。"""
    if not link.endswith(".md"):
        return False
    if link.startswith(("http://", "https://", "mailto:", "#", "/")):
        return False
    if "{" in link or "*" in link:
        return False
    if _TIMESTAMP_EXAMPLE.match(os.path.basename(link)):
        return False
    return True


def parse_frontmatter_fields(text):
    """YAML frontmatter のトップレベル `key: value` を dict で返す。なければ空 dict。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        m = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if m:
            fields[m.group(1)] = m.group(2).strip()
    return {}  # 閉じデリミタなし = frontmatter 不成立


def extract_command_refs(text):
    """テキスト中の `commands/<name>.md` 参照を set で返す。"""
    return set(_COMMAND_REF_RE.findall(text))


def find_broken_symlinks(root):
    """リンク先が存在しない symlink のパス一覧を返す。EXCLUDED_DIRS は走査しない。"""
    broken = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for name in filenames + [d for d in dirnames if os.path.islink(os.path.join(dirpath, d))]:
            path = os.path.join(dirpath, name)
            if os.path.islink(path) and not os.path.exists(path):
                broken.append(path)
    return sorted(broken)


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _skill_dirs(root, subdir):
    base = os.path.join(root, subdir)
    if not os.path.isdir(base):
        return []
    return sorted(
        d for d in os.listdir(base)
        if os.path.isdir(os.path.join(base, d)) and d != "shared"
    )


def run_checks(root):
    """全チェックを実行し、違反メッセージの一覧を返す（空なら合格）。"""
    errors = []

    # 1. 壊れた symlink
    for path in find_broken_symlinks(root):
        errors.append(f"[symlink] 壊れた symlink: {os.path.relpath(path, root)}")

    # 2-3. スキルディレクトリと SKILL.md frontmatter
    for subdir in ("skills", "codex-skills"):
        for skill in _skill_dirs(root, subdir):
            skill_md = os.path.join(root, subdir, skill, "SKILL.md")
            if not os.path.isfile(skill_md):
                errors.append(f"[skill] SKILL.md がない: {subdir}/{skill}/")
                continue
            fields = parse_frontmatter_fields(_read(skill_md))
            for key in ("name", "description"):
                if not fields.get(key):
                    errors.append(f"[frontmatter] {key} がない: {subdir}/{skill}/SKILL.md")

    # 4. commands frontmatter
    commands_dir = os.path.join(root, "commands")
    command_files = sorted(
        f for f in os.listdir(commands_dir) if f.endswith(".md")
    ) if os.path.isdir(commands_dir) else []
    for name in command_files:
        fields = parse_frontmatter_fields(_read(os.path.join(commands_dir, name)))
        if not fields.get("description"):
            errors.append(f"[frontmatter] description がない: commands/{name}")

    # 5. 相対 .md リンクの実在
    link_sources = []
    for subdir in ("skills", "codex-skills"):
        for skill in _skill_dirs(root, subdir):
            path = os.path.join(root, subdir, skill, "SKILL.md")
            if os.path.isfile(path):
                link_sources.append(path)
    link_sources += [os.path.join(commands_dir, n) for n in command_files]
    for src in link_sources:
        src_dir = os.path.dirname(src)
        for link in extract_md_links(_read(src)):
            if not is_checkable_link(link):
                continue
            if not os.path.isfile(os.path.normpath(os.path.join(src_dir, link))):
                errors.append(
                    f"[link] リンク切れ: {os.path.relpath(src, root)} -> {link}"
                )

    # 6. CLAUDE.md 対応表 ⇔ commands/ 実ファイル
    claude_md = os.path.join(root, "CLAUDE.md")
    if os.path.isfile(claude_md):
        mapped = extract_command_refs(_read(claude_md))
        actual = {f"commands/{n}" for n in command_files}
        for missing in sorted(actual - mapped):
            errors.append(f"[map] CLAUDE.md の対応表に載っていない: {missing}")
        for stale in sorted(mapped - actual):
            errors.append(f"[map] CLAUDE.md が実在しないコマンドを参照: {stale}")

    # 7-8. README / AGENTS.md のスキル名カバレッジ（ドリフト検出）
    readme = _read(os.path.join(root, "README.md")) if os.path.isfile(os.path.join(root, "README.md")) else ""
    agents = _read(os.path.join(root, "AGENTS.md")) if os.path.isfile(os.path.join(root, "AGENTS.md")) else ""
    for skill in _skill_dirs(root, "skills"):
        if skill not in readme:
            errors.append(f"[drift] README.md がスキルに言及していない: {skill}")
    for skill in _skill_dirs(root, "codex-skills"):
        if skill not in agents:
            errors.append(f"[drift] AGENTS.md が codex スキルに言及していない: {skill}")

    # 9. plugin.json ⇔ marketplace.json バージョン同期
    plugin_path = os.path.join(root, ".claude-plugin", "plugin.json")
    market_path = os.path.join(root, ".claude-plugin", "marketplace.json")
    if os.path.isfile(plugin_path) and os.path.isfile(market_path):
        plugin_ver = json.loads(_read(plugin_path)).get("version")
        market = json.loads(_read(market_path))
        for entry in market.get("plugins", []):
            if entry.get("version") != plugin_ver:
                errors.append(
                    f"[version] plugin.json ({plugin_ver}) と marketplace.json "
                    f"({entry.get('version')}) のバージョン不一致"
                )

    return errors


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    errors = run_checks(root)
    if errors:
        print(f"✗ {len(errors)} 件の違反:")
        for e in errors:
            print(f"  {e}")
        return 1
    print("✓ 全チェック合格")
    return 0


if __name__ == "__main__":
    sys.exit(main())
