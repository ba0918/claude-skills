#!/usr/bin/env python3
"""リポジトリ整合性バリデータ。

このリポジトリの「コード」は markdown のスキル定義なので、
壊れやすいのはリンク・対応表・バージョン同期といったドキュメント間の整合性。
それらを機械的に検証する。CI（GitHub Actions）とローカルの両方から実行できる。

実行: python3 scripts/validate_repo.py [repo_root]
      python3 scripts/validate_repo.py --update-manifest [repo_root]
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
  10. Claude 版 ⇔ Codex 版スキルの同期台帳（codex-skills/sync-manifest.json）
  11. SKILL.md description の品質（トリガー語を含む / 1024 字以内）

同期台帳の仕組み:
  codex-skills/ の各スキルは skills/ の対応スキル（cycle のみ commands/cycle.md）を
  ソースとする移植版。両者は意図的に内容が異なるため diff 比較はできないが、
  「ソースだけ更新して移植版を忘れる」サイレントドリフトは防ぎたい。
  そこで sync 時点のソースファイルの sha256 を台帳に記録し、ソースが変わったのに
  台帳が古いままなら CI を落とす。Codex 版へ反映（または反映不要と判断）したら
  `--update-manifest` で台帳を更新して合意を記録する。
"""
import hashlib
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


def extract_description(text):
    """frontmatter から description の全文を返す（複数行ブロックスカラー対応）。

    parse_frontmatter_fields は単一行の値しか取れないため、`description: >` 形式の
    複数行 description はこちらで結合して返す。なければ None。
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    body = []
    closed = False
    for line in lines[1:]:
        if line.strip() == "---":
            closed = True
            break
        body.append(line)
    if not closed:
        return None
    desc_lines = []
    in_desc = False
    for line in body:
        if re.match(r"^description:", line):
            in_desc = True
            desc_lines.append(re.sub(r"^description:\s*", "", line).strip())
            continue
        if in_desc:
            if re.match(r"^[A-Za-z_-]+:", line):  # 次のトップレベルキー
                break
            desc_lines.append(line.strip())
    if not in_desc:
        return None
    if desc_lines and desc_lines[0] in (">", "|", ">-", "|-"):
        desc_lines = desc_lines[1:]
    return " ".join(l for l in desc_lines if l).strip()


# description は「何をするか」に加えて「いつ起動するか」を含まなければならない。
# スキル発火はモデルが description を読んで判断するため、トリガー語の欠落は
# 発火漏れに直結する。日本語スキルは「〜で起動」、英語スキルは "Use when" 等。
DESCRIPTION_TRIGGER = re.compile(r"で起動|で使用|use when|triggers?:", re.IGNORECASE)
DESCRIPTION_MAX_LEN = 1024

# トリガー語チェックの免除リスト。免除はスキル側の frontmatter ではなく
# ここに置く（スキルファイルの編集だけで検証を迂回できないようにするため）。
# 追加する場合は必ず理由を書くこと。
DESCRIPTION_TRIGGER_EXEMPT = {
    # "skills/<name>": "理由",
}


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


SYNC_MANIFEST_PATH = os.path.join("codex-skills", "sync-manifest.json")

# codex スキル名 → Claude 側ソースの特例。デフォルトは skills/<name>/SKILL.md
CODEX_SOURCE_OVERRIDES = {
    "cycle": "commands/cycle.md",  # Claude 側は commands のみ（スキル実体なし）
}

# skills/*/SKILL.md 対応以外で同期追跡したい実ファイルペア (codex側, ソース)
EXTRA_SYNC_PAIRS = [
    (
        "codex-skills/shared/references/team-config.md",
        "skills/shared/references/team-config.md",
    ),
]


def resolve_codex_source(codex_skill_name):
    """codex スキル名から Claude 側ソースのリポジトリ相対パスを返す。"""
    return CODEX_SOURCE_OVERRIDES.get(
        codex_skill_name, f"skills/{codex_skill_name}/SKILL.md"
    )


def collect_sync_pairs(root):
    """同期追跡対象の (codex相対パス, ソース相対パス) 一覧を返す。

    symlink は物理的に同一内容なのでドリフトし得ず、対象外。
    """
    pairs = []
    for skill in _skill_dirs(root, "codex-skills"):
        codex_rel = f"codex-skills/{skill}/SKILL.md"
        path = os.path.join(root, codex_rel)
        if os.path.isfile(path) and not os.path.islink(path):
            pairs.append((codex_rel, resolve_codex_source(skill)))
    for codex_rel, source_rel in EXTRA_SYNC_PAIRS:
        path = os.path.join(root, codex_rel)
        if os.path.isfile(path) and not os.path.islink(path):
            pairs.append((codex_rel, source_rel))
    return pairs


def check_sync_manifest(pairs, manifest, source_hashes):
    """同期台帳を検証し、違反メッセージ一覧を返す。

    pairs: (codex相対パス, ソース相対パス) の一覧
    manifest: {codex相対パス: {"source": ..., "source_sha256": ...}}
    source_hashes: {ソース相対パス: sha256 hex}（存在しないソースはキーなし）
    """
    errors = []
    hint = "python3 scripts/validate_repo.py --update-manifest"
    for codex_rel, source_rel in pairs:
        source_hash = source_hashes.get(source_rel)
        if source_hash is None:
            errors.append(
                f"[sync] 対応する Claude 版ソースが存在しない: {codex_rel} -> {source_rel}"
            )
            continue
        entry = manifest.get(codex_rel)
        if not entry:
            errors.append(f"[sync] sync-manifest に未登録: {codex_rel}（{hint} で登録）")
        elif entry.get("source") != source_rel:
            errors.append(
                f"[sync] sync-manifest の source が不一致: {codex_rel} "
                f"(台帳: {entry.get('source')} / 期待: {source_rel})"
            )
        elif entry.get("source_sha256") != source_hash:
            errors.append(
                f"[sync] Claude 版が変更されたが Codex 版が未同期: {source_rel} -> {codex_rel}"
                f"（内容を同期・または反映不要と判断してから {hint}）"
            )
    pair_keys = {codex_rel for codex_rel, _ in pairs}
    for stale in sorted(set(manifest) - pair_keys):
        errors.append(f"[sync] sync-manifest に実在しないエントリ: {stale}（{hint} で掃除）")
    return errors


def _sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _collect_source_hashes(root, pairs):
    hashes = {}
    for _, source_rel in pairs:
        path = os.path.join(root, source_rel)
        if os.path.isfile(path):
            hashes[source_rel] = _sha256_file(path)
    return hashes


def _load_manifest(root):
    path = os.path.join(root, SYNC_MANIFEST_PATH)
    if not os.path.isfile(path):
        return {}
    return json.loads(_read(path))


def update_manifest(root):
    """現在のソースハッシュで同期台帳を再生成して書き込む。"""
    pairs = collect_sync_pairs(root)
    hashes = _collect_source_hashes(root, pairs)
    manifest = {
        codex_rel: {"source": source_rel, "source_sha256": hashes[source_rel]}
        for codex_rel, source_rel in sorted(pairs)
        if source_rel in hashes
    }
    path = os.path.join(root, SYNC_MANIFEST_PATH)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return manifest


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

    # 10. Claude 版 ⇔ Codex 版の同期台帳
    pairs = collect_sync_pairs(root)
    errors += check_sync_manifest(
        pairs, _load_manifest(root), _collect_source_hashes(root, pairs)
    )

    # 11. description の品質（トリガー語 / 長さ上限）
    for subdir in ("skills", "codex-skills"):
        for skill in _skill_dirs(root, subdir):
            skill_md = os.path.join(root, subdir, skill, "SKILL.md")
            if not os.path.isfile(skill_md):
                continue  # 欠落はチェック2で報告済み
            desc = extract_description(_read(skill_md))
            if not desc:
                continue  # 欠落はチェック3で報告済み
            rel = f"{subdir}/{skill}"
            if len(desc) > DESCRIPTION_MAX_LEN:
                errors.append(
                    f"[description] {DESCRIPTION_MAX_LEN} 字を超過（{len(desc)} 字）: "
                    f"{rel}/SKILL.md"
                )
            if rel not in DESCRIPTION_TRIGGER_EXEMPT and not DESCRIPTION_TRIGGER.search(desc):
                errors.append(
                    f"[description] トリガー語がない（「〜で起動」/ \"Use when\" 等）: "
                    f"{rel}/SKILL.md"
                )

    return errors


def main():
    args = [a for a in sys.argv[1:] if a != "--update-manifest"]
    root = args[0] if args else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if "--update-manifest" in sys.argv[1:]:
        manifest = update_manifest(root)
        print(f"✓ {SYNC_MANIFEST_PATH} を更新（{len(manifest)} ペア）")
        return 0
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
