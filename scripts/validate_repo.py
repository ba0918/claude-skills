#!/usr/bin/env python3
"""リポジトリ整合性バリデータ。

このリポジトリの「コード」は markdown のスキル定義なので、
壊れやすいのはリンク・対応表・バージョン同期といったドキュメント間の整合性。
それらを機械的に検証する。CI（GitHub Actions）とローカルの両方から実行できる。

実行: python3 scripts/validate_repo.py [repo_root]
終了コード: 0 = 全チェック合格 / 1 = 違反あり

チェック項目:
  1. 壊れた symlink が存在しない
  2. skills/ の各スキルディレクトリに SKILL.md がある
  3. SKILL.md frontmatter に name / description がある
  4. commands/*.md frontmatter に description がある
  5. SKILL.md / commands/*.md / references/**/*.md 内の相対 .md リンクが実在する
  6. README.md が全スキル名に言及している（ドリフト検出）
  7. plugin.json と marketplace.json のバージョンが一致する
  8. SKILL.md description の品質（トリガー語を含む / 1024 字以内）
  9. 共有契約語彙の適合（契約の識別語彙を使う skill / command は契約を md リンクする）
  10. .agents/artifacts/loop/dossiers/*.json の dossier lint（error 級のみ CI fail）
  11. .agents/artifacts.yml と local store の Git 安全性
  12. plugin.json の version に対応するエントリが CHANGELOG.md に存在する
  13. frontmatter のクォートなし値が strict YAML と互換（`: ` / 末尾コロン / ` #` 禁止）

チェック 10・11 と store 実在性:
  チェック 10（dossier lint）は local store が ignore されている環境では対象ファイルが
  存在せず no-op で pass する。すなわち CI（fresh checkout）では store 内容を検査できない
  ため、dossier の内容ゲートは store が実在する writer 環境（pre-push hook / ローカル実行）
  で担保する。CI の green を「dossier 内容も検証済み」と読んではならない
  （artifact-store.md「Quality gates」節が正本）。
  チェック 11 は store 内容ではなく tracked policy（.agents/artifacts.yml）と Git 安全性を
  検証するため、store が空の CI でも有効に機能する（policy が無ければ skip）。
"""
import json
import os
import re
import sys

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "skills", "shared", "scripts",
    ),
)
from frontmatter import (  # noqa: E402,F401
    extract_description,
    parse_frontmatter_fields,
    parse_frontmatter_lines,
)
from artifact_store import ArtifactStoreError, inspect as inspect_artifact_store  # noqa: E402

EXCLUDED_DIRS = {".git", ".claude", ".codex", "node_modules", "__pycache__"}

# 例示用プレースホルダと判定するパターン: {var} 含み / URL / アンカー /
# タイムスタンプ始まりのファイル名（docs 生成物の例示）
_TIMESTAMP_EXAMPLE = re.compile(r"^\d{8,}")
_LINK_RE = re.compile(r"\]\(([^)\s]+)\)")
_ROOT_RULE_REF_RE = re.compile(r"(?<![.\w/])rules/([A-Za-z0-9._-]+\.md)")



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


# frontmatter パーサは skills/shared/scripts/frontmatter.py に共有化した
# （context-audit / trigger-eval と同一実装。冒頭の import を参照）。


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


# チェック9: 共有契約の識別語彙。unit（skills/<name>/ 全体 or commands/<file>.md 単体）が
# min_distinct 種類以上の語彙を含むなら、その unit 内のどこかで契約への md リンクを要求する。
# 「宣言だけ共有・実体はインライン再発明」のドリフトを機械的に止めるのが目的。
# BLOCK / WARN 単体のような汎用語は偽陽性が多いため対象にしない — 契約を一意に識別する
# 複合語彙のみ登録する。
CONTRACT_VOCAB = [
    ("skills/shared/references/fix-action-taxonomy.md",
     ("AUTO_FIX", "NEEDS_JUDGMENT", "REPORT_ONLY"), 2),
    ("skills/shared/references/severity-and-verdicts.md",
     ("CONFIRMED", "FALSE_POSITIVE", "UNCERTAIN"), 2),
    ("skills/shared/references/severity-and-verdicts.md",
     ("PASS WITH NOTES", "APPROVED WITH CONCERNS"), 1),
    ("skills/shared/references/polling-pattern.md",
     (".STOP.hard", "failed_streak", "max_wallclock"), 2),
    ("skills/shared/references/codex-integration.md",
     ("codex:codex-rescue",), 1),
    ("skills/shared/references/goal-decomposition-pattern.md",
     ("ci_gate", "resident_sensor", "dissolve"), 2),
    ("skills/shared/references/artifact-store.md",
     (".agents/artifacts",), 1),
    # coverage ledger（評価範囲台帳）。reviewed/skipped は汎用語で偽陽性を招くため、
    # 4 値中 3 値の共起でのみ契約リンクを要求する（min_distinct=3）。
    ("skills/shared/references/coverage-ledger.md",
     ("reviewed", "skipped", "unsupported", "inconclusive"), 3),
]

# チェック9の免除リスト。免除はスキル側ではなくここに置く（迂回防止）。理由必須。
CONTRACT_VOCAB_EXEMPT = {
    # "skills/<name>" または "commands/<file>.md": "理由",
}


def check_description_quality(root, trigger_exempt=None):
    """チェック8: SKILL.md description のトリガー語含有と長さを検証する。"""
    if trigger_exempt is None:
        trigger_exempt = DESCRIPTION_TRIGGER_EXEMPT
    errors = []
    for skill in _skill_dirs(root, "skills"):
        skill_md = os.path.join(root, "skills", skill, "SKILL.md")
        if not os.path.isfile(skill_md):
            continue
        desc = extract_description(_read(skill_md))
        if not desc:
            continue
        rel = f"skills/{skill}"
        if len(desc) > DESCRIPTION_MAX_LEN:
            errors.append(
                f"[description] {DESCRIPTION_MAX_LEN} 字を超過（{len(desc)} 字）: "
                f"{rel}/SKILL.md"
            )
        if rel not in trigger_exempt and not DESCRIPTION_TRIGGER.search(desc):
            errors.append(
                f"[description] トリガー語がない（「〜で起動」/ \"Use when\" 等）: "
                f"{rel}/SKILL.md"
            )
    return errors


# チェック13: 本リポジトリや一部エージェント実装の行ベースパーサは寛容に読めるが、
# strict YAML 実装（PyYAML / Go yaml 等を使う他プラットフォームのツール）では
# クォートなしのプレーンスカラーが別の意味になるパターン。マルチプラットフォーム
# 配布でスキルが読めなくなる互換事故を機械的に止める。
_YAML_PLAIN_UNSAFE = (
    ("mapping と誤認される ': '（parse error になる）", lambda v: ": " in v),
    ("mapping と誤認される末尾コロン（parse error になる）", lambda v: v.endswith(":")),
    ("コメント開始と解釈される ' #'（以降が黙って捨てられる）", lambda v: " #" in v),
)


def check_frontmatter_yaml_compat(root):
    """チェック13: frontmatter のクォートなし値が strict YAML でも同じ意味で読めるか検証する。"""
    errors = []
    targets = [
        os.path.join(root, "skills", skill, "SKILL.md")
        for skill in _skill_dirs(root, "skills")
    ]
    commands_dir = os.path.join(root, "commands")
    if os.path.isdir(commands_dir):
        targets += [
            os.path.join(commands_dir, name)
            for name in sorted(os.listdir(commands_dir))
            if name.endswith(".md")
        ]
    for path in targets:
        if not os.path.isfile(path):
            continue
        fm = parse_frontmatter_lines(_read(path))
        if not fm:
            continue
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        for key, value, _ in fm:
            if not value or value[0] in "\"'>|[{":
                continue
            for reason, hits in _YAML_PLAIN_UNSAFE:
                if hits(value):
                    errors.append(f"[frontmatter-yaml] {reason}: {rel} ({key})")
    return errors


# チェック14: ヒューマンリーダブル要約契約の横展開ガード。
# 対象 5 スキルの完了表示が「契約への md リンク + 固定要約ラベル」を持つことを
# テキストレベルで機械検証し、「要約が出力される」ことを grep レベルで担保する。
# fixtures を持たない 3 スキル（brainstorm / doc-write / design-guide）
# の要約"挙動"は behavior テストできないため、この統一テキストガードが最低ガードになる。
# 要約"内容の質"はいずれのスキルも機械検証不能であることを受容した上での設計。
HUMAN_READABLE_SUMMARY_CONTRACT = "skills/shared/references/human-readable-summary.md"
HUMAN_READABLE_SUMMARY_LABEL = "📝 つまり:"
HUMAN_READABLE_SUMMARY_SKILLS = (
    "brainstorm",
    "issue",
    "handoff",
    "doc-write",
    "design-guide",
)


def check_human_readable_summary(root):
    """チェック14を実行し、違反メッセージ一覧を返す。"""
    errors = []
    contract_path = os.path.join(root, HUMAN_READABLE_SUMMARY_CONTRACT)
    if not os.path.isfile(contract_path):
        errors.append(f"[summary] 契約ファイルがない: {HUMAN_READABLE_SUMMARY_CONTRACT}")
        return errors
    contract_low = _read(contract_path).lower()
    if "before" not in contract_low or "after" not in contract_low:
        errors.append(
            f"[summary] 契約に before/after ワークト例がない: "
            f"{HUMAN_READABLE_SUMMARY_CONTRACT}"
        )
    for skill in HUMAN_READABLE_SUMMARY_SKILLS:
        skill_md = os.path.join(root, "skills", skill, "SKILL.md")
        if not os.path.isfile(skill_md):
            errors.append(f"[summary] SKILL.md がない: skills/{skill}/SKILL.md")
            continue
        text = _read(skill_md)
        if "human-readable-summary.md" not in text:
            errors.append(
                f"[summary] {skill}: 契約への md リンクがない: skills/{skill}/SKILL.md"
            )
        if HUMAN_READABLE_SUMMARY_LABEL not in text:
            errors.append(
                f"[summary] {skill}: 要約ラベル「{HUMAN_READABLE_SUMMARY_LABEL}」が"
                f"ない: skills/{skill}/SKILL.md"
            )
    return errors


def _conformance_units(root):
    """チェック9の unit（識別子 → md ファイル一覧）を返す。"""
    units = {}
    for skill in _skill_dirs(root, "skills"):
        base = os.path.join(root, "skills", skill)
        files = []
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
            files += [
                os.path.join(dirpath, n) for n in sorted(filenames)
                if n.endswith(".md")
            ]
        units[f"skills/{skill}"] = files
    commands_dir = os.path.join(root, "commands")
    if os.path.isdir(commands_dir):
        for name in sorted(os.listdir(commands_dir)):
            if name.endswith(".md"):
                units[f"commands/{name}"] = [os.path.join(commands_dir, name)]
    return units


def check_contract_conformance(root, vocab=None, exempt=None):
    """チェック9を実行し、違反メッセージ一覧を返す。"""
    vocab = CONTRACT_VOCAB if vocab is None else vocab
    exempt = CONTRACT_VOCAB_EXEMPT if exempt is None else exempt
    errors = []
    for unit, files in sorted(_conformance_units(root).items()):
        if unit in exempt:
            continue
        texts = []
        linked = set()
        for path in files:
            text = _read(path)
            texts.append(text)
            for link in extract_md_links(text):
                if not is_checkable_link(link):
                    continue
                target = os.path.normpath(
                    os.path.join(os.path.dirname(path), link))
                linked.add(os.path.relpath(target, root).replace(os.sep, "/"))
        for contract_rel, tokens, min_distinct in vocab:
            used = sorted(t for t in tokens if any(t in x for x in texts))
            if len(used) < min_distinct or contract_rel in linked:
                continue
            errors.append(
                f"[contract] {unit} が契約語彙 {'/'.join(used)} を使用しているが "
                f"{contract_rel} への md リンクがない（参照を張るか、意図的な別体系なら "
                f"validate_repo.py の CONTRACT_VOCAB_EXEMPT に理由付きで登録）"
            )
    return errors


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


def mentions_name(text, name):
    """text がスキル名 name に word-boundary で言及しているか。

    bare substring だと issue ⊂ github-issue / plan ⊂ team-plan が
    誤合格するため、英数字とハイフンの連続を1語として境界判定する。
    """
    pattern = rf"(?<![A-Za-z0-9-]){re.escape(name)}(?![A-Za-z0-9-])"
    return re.search(pattern, text) is not None


def collect_link_sources(root):
    """チェック5の対象ファイルを集める。

    SKILL.md / commands/*.md に加えて、skills 配下の
    references/**/*.md（shared 含む — 共有契約こそリンク切れの影響が大きい）。
    """
    sources = []
    base = os.path.join(root, "skills")
    if os.path.isdir(base):
        for entry in sorted(os.listdir(base)):
            skill_dir = os.path.join(base, entry)
            if not os.path.isdir(skill_dir):
                continue
            skill_md = os.path.join(skill_dir, "SKILL.md")
            if os.path.isfile(skill_md):
                sources.append(skill_md)
            refs = os.path.join(skill_dir, "references")
            if os.path.isdir(refs):
                for dirpath, _, files in os.walk(refs):
                    for name in sorted(files):
                        if name.endswith(".md"):
                            sources.append(os.path.join(dirpath, name))
    commands_dir = os.path.join(root, "commands")
    if os.path.isdir(commands_dir):
        sources += [
            os.path.join(commands_dir, n)
            for n in sorted(os.listdir(commands_dir)) if n.endswith(".md")
        ]
    return sources


# リンク検査の免除リスト。免除はファイル側ではなくここに置く
# （ファイル編集だけで検証を迂回できないようにするため）。必ず理由を書くこと。
LINK_CHECK_EXEMPT = {
    # テンプレート本文のリンクは「生成先プロジェクトの docs/ 構造」を指す例示
    # であり、このリポジトリ内には存在しない
    "skills/plan/references/status-template.md": "生成先 docs/ の例示リンク",
    "skills/plan/references/status-update-guide.md": "生成先 docs/ の例示リンク",
}


_DOSSIER_LINT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "skills", "goal-decomposition", "scripts")


def check_dossiers(root):
    """チェック10: .agents/artifacts/loop/dossiers/*.json を dossier_lint で in-process 検査する。

    error 級 finding のみを `[dossier] <file>: GDxxx <message>` 形式で返す
    （warn は CI fail させない）。1 つの壊れた dossier で validate_repo 全体が
    traceback で落ちないよう、各ファイルは dossier_lint の例外集合で包まれた
    `_lint_one` を通す（parse-error は errors エントリに変換される）。
    """
    ddir = os.path.join(root, ".agents", "artifacts", "loop", "dossiers")
    if not os.path.isdir(ddir):
        return []
    if _DOSSIER_LINT_DIR not in sys.path:
        sys.path.insert(0, _DOSSIER_LINT_DIR)
    import dossier_lint  # noqa: E402

    errors = []
    for name in sorted(os.listdir(ddir)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(ddir, name)
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        findings, err = dossier_lint._lint_one(path, ddir)
        if err is not None:
            errors.append(f"[dossier] {rel}: parse-error {err}")
            continue
        for f in findings:
            if f.get("severity") == "error":
                errors.append(f"[dossier] {rel}: {f['rule']} {f['message']}")
    return errors


def check_artifact_store(root):
    """Agent Artifact Store policy and Git safety errors."""
    artifact_policy = os.path.join(root, ".agents", "artifacts.yml")
    if not os.path.isfile(artifact_policy):
        return []
    try:
        status = inspect_artifact_store(root)
        return [f"[artifact-store] {error}" for error in status["errors"]]
    except ArtifactStoreError as exc:
        return [f"[artifact-store] {exc}"]


def check_changelog_sync(root):
    """チェック12: plugin.json の version に対応する `## <version>` 見出しが CHANGELOG.md にあるか。

    マーケットプレイスがスキル変更を認識するのは version bump 時のみで、
    CHANGELOG はその bump の唯一の変更記録。bump だけして起票を忘れると
    履歴が永久に欠落する（実例: 1.45.1〜1.46.1）ため機械検証する。
    """
    plugin_path = os.path.join(root, ".claude-plugin", "plugin.json")
    if not os.path.isfile(plugin_path):
        return []
    version = json.loads(_read(plugin_path)).get("version")
    if not version:
        return []
    changelog_path = os.path.join(root, "CHANGELOG.md")
    if not os.path.isfile(changelog_path):
        return [
            f"[changelog] CHANGELOG.md がない"
            f"（plugin version {version} のエントリを起票できない）"
        ]
    # 見出し直後は空白か行末のみ許可（1.46.1 が 1.46.10 に誤マッチしないように）
    heading = re.compile(rf"^##\s+{re.escape(version)}(?:\s.*)?$", re.M)
    if not heading.search(_read(changelog_path)):
        return [
            f"[changelog] plugin.json の version {version} に対応する "
            f"「## {version}」エントリが CHANGELOG.md にない"
        ]
    return []


def check_relative_links(root, sources=None, exempt=None):
    """各ソース内の相対 .md リンクの実在を検証し、違反メッセージを返す。"""
    if sources is None:
        sources = collect_link_sources(root)
    if exempt is None:
        exempt = LINK_CHECK_EXEMPT
    errors = []
    for src in sources:
        rel = os.path.relpath(src, root).replace(os.sep, "/")
        if rel in exempt:
            continue
        src_dir = os.path.dirname(src)
        for link in extract_md_links(_read(src)):
            if not is_checkable_link(link):
                continue
            if not os.path.isfile(os.path.normpath(os.path.join(src_dir, link))):
                errors.append(
                    f"[link] リンク切れ: {os.path.relpath(src, root)} -> {link}"
                )
    return errors


def check_portable_resource_refs(root, sources=None):
    """skill 文書が常駐専用の root rules/ をリソース参照しないことを検証する。"""
    if sources is None:
        sources = collect_link_sources(root)
    errors = []
    for src in sources:
        text = _read(src)
        for match in _ROOT_RULE_REF_RE.finditer(text):
            legacy = f"rules/{match.group(1)}"
            errors.append(
                f"[resource] rules/ への非可搬参照: "
                f"{os.path.relpath(src, root)} -> {legacy}"
            )
    return errors


def run_checks(root):
    """全チェックを実行し、違反メッセージの一覧を返す（空なら合格）。"""
    errors = []

    # 1. 壊れた symlink
    for path in find_broken_symlinks(root):
        errors.append(f"[symlink] 壊れた symlink: {os.path.relpath(path, root)}")

    # 2-3. スキルディレクトリと SKILL.md frontmatter
    for skill in _skill_dirs(root, "skills"):
        skill_md = os.path.join(root, "skills", skill, "SKILL.md")
        if not os.path.isfile(skill_md):
            errors.append(f"[skill] SKILL.md がない: skills/{skill}/")
            continue
        fields = parse_frontmatter_fields(_read(skill_md))
        for key in ("name", "description"):
            if not fields.get(key):
                errors.append(f"[frontmatter] {key} がない: skills/{skill}/SKILL.md")

    # 4. commands frontmatter
    commands_dir = os.path.join(root, "commands")
    command_files = sorted(
        f for f in os.listdir(commands_dir) if f.endswith(".md")
    ) if os.path.isdir(commands_dir) else []
    for name in command_files:
        fields = parse_frontmatter_fields(_read(os.path.join(commands_dir, name)))
        if not fields.get("description"):
            errors.append(f"[frontmatter] description がない: commands/{name}")

    # 5. 相対 .md リンクの実在（SKILL.md / commands / references）と
    #    rules/ から shared へ移した共有契約の非可搬参照
    errors += check_relative_links(root)
    errors += check_portable_resource_refs(root)

    # 6. README.md のスキル名カバレッジ（ドリフト検出）
    readme = _read(os.path.join(root, "README.md")) if os.path.isfile(os.path.join(root, "README.md")) else ""
    for skill in _skill_dirs(root, "skills"):
        if not mentions_name(readme, skill):
            errors.append(f"[drift] README.md がスキルに言及していない: {skill}")

    # 7. plugin.json ⇔ marketplace.json バージョン同期
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

    # 8. description の品質（トリガー語 / 長さ上限）
    errors += check_description_quality(root)

    # 9. 共有契約語彙の適合
    errors += check_contract_conformance(root)

    # 10. dossier lint（.agents/artifacts/loop/dossiers/*.json）
    errors += check_dossiers(root)

    # 11. Agent Artifact Store policy / Git safety
    errors += check_artifact_store(root)

    # 12. plugin.json version ⇔ CHANGELOG.md エントリ同期
    errors += check_changelog_sync(root)

    # 13. frontmatter 値の strict YAML 互換
    errors += check_frontmatter_yaml_compat(root)

    # 14. ヒューマンリーダブル要約契約の横展開ガード
    errors += check_human_readable_summary(root)

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
