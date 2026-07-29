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
  12. plugin.json の version と CHANGELOG.md の双方向同期
      （対応エントリが存在する / 未配布の先行エントリが残っていない）
  13. frontmatter のクォートなし値が strict YAML と互換（`: ` / 末尾コロン / ` #` 禁止）
  14. ヒューマンリーダブル要約契約の横展開ガード
  15. 配布 manifest の整合性（3 manifest の name / version、リポジトリ slug、LICENSE 実在）
  16. 名前が対応しない command が description で起動先スキルを名指ししている
  17. skills/*/fixtures.json が回帰 fixture の契約に適合する
  18. デザイントークンの authoring 層 ⇔ 配布層同期
  19. agent 生成物の置き場に `.claude/` を使っていないか
  20. リネーム許可表（scripts/rename-allowlist.json）の失効エントリ検出
  21. plugin hooks の整合性（hooks.json のパース / command パスの実在と実行ビット /
      hook スクリプトが参照する rules/skill-routing.md の実在）

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
import shlex
import subprocess
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
from workspace_isolation import (  # noqa: E402
    WorkspaceIsolationError,
    resolve_isolation,
)

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
    # workspace lock。語彙は意図的に固有名にしてある。polling-pattern が既に使う
    # `ClaimFailed` や汎用語の `claim` / `lock` を採ると、coverage-ledger の
    # reviewed / skipped で起きたのと同じ偽陽性を招く。
    ("skills/shared/references/workspace-lock.md",
     ("workspace.claim", "LOCK_HELD", "STALE_RECLAIMED"), 2),
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
HUMAN_READABLE_SUMMARY_LABEL = "📝 In short:"
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
    # ドットディレクトリはスキルではない。エージェントがリポジトリ本体を cwd にして
    # 動くと skills/.claude/ のようなセッション用スキャフォールドが現れ、
    # 「SKILL.md がない」という無関係な理由でチェックが落ちる
    return sorted(
        d for d in os.listdir(base)
        if os.path.isdir(os.path.join(base, d))
        and d != "shared" and not d.startswith(".")
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


def collect_doc_link_sources(root):
    """リンク実在チェックだけの追加対象: root 直下の md と rules/*.md。

    check_portable_resource_refs には含めない（README/CHANGELOG が
    rules/ を参照するのは正当）。
    """
    sources = []
    for name in sorted(os.listdir(root)):
        if name.endswith(".md") and os.path.isfile(os.path.join(root, name)):
            sources.append(os.path.join(root, name))
    rules_dir = os.path.join(root, "rules")
    if os.path.isdir(rules_dir):
        sources += [os.path.join(rules_dir, n)
                    for n in sorted(os.listdir(rules_dir))
                    if n.endswith(".md") and os.path.isfile(os.path.join(rules_dir, n))]
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


def check_workspace_policy(root):
    """Tracked workspace policy must parse when present; absence stays valid."""
    policy = os.path.join(root, ".agents", "workspace.yml")
    if not os.path.lexists(policy):
        return []
    try:
        resolve_isolation(root)
        return []
    except WorkspaceIsolationError as exc:
        return [f"[workspace-policy] .agents/workspace.yml: {exc}"]


DESIGN_TOKEN_LAYERS = [
    (
        os.path.join(".design", "tokens.css"),
        os.path.join("skills", "brief", "assets", "tokens.css"),
    ),
]


LEGACY_CLAUDE_PATH = re.compile(
    r"\.claude/(tmp|review-rules|[a-z][a-z0-9-]*-baseline\.json)"
)
# `source`（fixture をどこで捕獲したか）と `note`（その検証イベントがどういう性質だったか）は
# **過去の記録** であり、現在の書き込み先ではない。史実を書き換えると存在しなかった場所を
# 指すことになるうえ、「旧パスから移行した」と述べる記録そのものが違反として検出される。
# ガードの対象外にするが、除外していること自体をここに明示する。
#
# 除外は行単位ではなく **値単位** で行う。行単位にすると `{ "source": "...", "x": "..." }`
# のように 1 行へ複数キーが並んだとき、同じ行の別キーまで一緒に見逃す。JSON の整形は
# ファイルごとに違うので、整形に依存しない切り出し方を採る。
LEGACY_CLAUDE_EXEMPT_VALUE = re.compile(r'"(?:source|note)"\s*:\s*"(?:[^"\\]|\\.)*"')


def check_legacy_claude_paths(root):
    """チェック19: agent 生成物の置き場として `.claude/` 配下を参照していないか。

    共有契約は `.agents/tmp/`（ephemeral）と `.agents/config/`（tracked config）を
    定義しており、provider 名入りのパスを agent 生成物の置き場に使うことを禁じている
    （artifact-store.md「The namespace is provider-independent」）。移行後にガードが
    無いと、次に書かれた 1 行から静かに逆戻りする。

    Claude Code の実体パス（`~/.claude/projects/`, `.claude/rules`, `.claude/skills`,
    `.claude/plugins/`, `.claude/settings*`）は監査対象・入力ソース・配置先であって
    `.claude/` のままが正しい。検出パターンを移行済みの 3 種に限定することで、
    それらを誤検出しない。
    """
    errors = []
    skills_root = os.path.join(root, "skills")
    for dirpath, dirnames, filenames in os.walk(skills_root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in sorted(filenames):
            if not name.endswith((".md", ".py", ".json")):
                continue
            path = os.path.join(dirpath, name)
            try:
                text = _read(path)
            except (UnicodeDecodeError, OSError):
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                hit = LEGACY_CLAUDE_PATH.search(
                    LEGACY_CLAUDE_EXEMPT_VALUE.sub('""', line))
                if hit:
                    rel = os.path.relpath(path, root)
                    errors.append(
                        f"[legacy-path] agent 生成物の置き場に `.claude/` を参照している: "
                        f"{rel}:{lineno} `{hit.group(0)}`"
                        "（`.agents/tmp/` か `.agents/config/` を使う — "
                        "skills/shared/references/artifact-store.md）"
                    )
    return errors


RENAME_ALLOWLIST_REL = os.path.join("scripts", "rename-allowlist.json")


def _resolve_rename_baseline(root):
    """リネーム許可表の失効判定に使う baseline ref を解決する。

    check_translation_parity.py の baseline 候補連鎖と同じ方向で探す。
    origin/main → main の順に試し、どちらも無ければ None（skip）。
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    for candidate in ("origin/main", "main"):
        try:
            r = subprocess.run(
                ["git", "rev-parse", "--verify", "--quiet",
                 f"{candidate}^{{commit}}"],
                cwd=root, capture_output=True, text=True, env=env,
            )
            if r.returncode == 0:
                return candidate
        except (OSError, subprocess.SubprocessError):
            pass
    return None


def check_rename_allowlist_staleness(root):
    """チェック20: リネーム許可表の失効エントリを検出する。

    check_translation_parity.py の identifier_preservation は、許可表に申告された
    リネーム（old → new）を消失から除外する。しかしリネームが完了して baseline から
    old が消えた後もエントリが残ると、「消えた識別子を無条件で許す穴」が恒久化する。

    baseline（比較元）の skills/ 配下に old が存在しないエントリを失効として報告する。
    baseline が解決できない環境（remote なし・shallow clone 等）では skip して pass する。
    """
    path = os.path.join(root, RENAME_ALLOWLIST_REL)
    if not os.path.isfile(path):
        return []
    try:
        allowlist = json.loads(_read(path))
    except json.JSONDecodeError as exc:
        return [f"[rename-allowlist] JSON として読めない: "
                f"{RENAME_ALLOWLIST_REL} ({exc})"]
    if not allowlist:
        return []

    ref = _resolve_rename_baseline(root)
    if ref is None:
        return []

    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    errors = []
    for entry in allowlist:
        old = entry.get("old", "")
        if not old:
            continue
        try:
            r = subprocess.run(
                ["git", "grep", "-q", "-F", old, ref, "--", "skills/"],
                cwd=root, capture_output=True, text=True, env=env,
            )
            found = r.returncode == 0
        except (OSError, subprocess.SubprocessError):
            continue
        if not found:
            errors.append(
                f"[rename-allowlist] 失効エントリ: old={old!r} が baseline ({ref})"
                f" の skills/ 配下に存在しない"
                f"（リネーム完了後は許可表から削除する）"
            )
    return errors


def check_design_token_sync(root):
    """チェック18: authoring 層のデザイントークンと配布層の同一性を照合する。

    `.design/` は design-scaffold / design-lint がリポジトリルート固定で参照する
    authoring 層だが、プラグインとして配布された先にルートの `.design/` は存在せず、
    レンダラが実行時に解決できるのはスキルディレクトリ配下だけである。そのため
    トークンの実体をスキルへ同梱する 2 層構造を採っている。

    乖離すると「lint は通るのに配布物は古い配色」という、どちらの検査にも
    引っかからない状態が生まれる。ここで両者のバイト同一性を要求して塞ぐ。
    """
    errors = []
    for authored_rel, distributed_rel in DESIGN_TOKEN_LAYERS:
        authored = os.path.join(root, authored_rel)
        distributed = os.path.join(root, distributed_rel)
        if not os.path.isfile(authored) or not os.path.isfile(distributed):
            continue
        if _read(authored) != _read(distributed):
            errors.append(
                f"[design-tokens] {authored_rel} と {distributed_rel} が乖離している。"
                f"`cp {authored_rel} {distributed_rel}` で配布層を再生成する"
            )
    return errors


_HOOKS_JSON_REL = os.path.join("hooks", "hooks.json")
# hook スクリプト → そのスクリプトが読む正本。スクリプトが存在するときだけ正本の
# 実在を検査する（条件出力の補助正本はここに載せない — 欠落時はスクリプト側が沈黙する）
_HOOK_CANONICAL_SOURCES = {
    os.path.join("hooks", "inject-skill-routing.sh"): os.path.join(
        "rules", "skill-routing.md"
    ),
    os.path.join("hooks", "inject-quality-gate.sh"): os.path.join(
        "skills", "shared", "references", "quality-gate-contract.md"
    ),
}


def check_plugin_hooks(root):
    """チェック21: plugin hooks の整合性を検証する。

    SessionStart hook はスキル発火の想起を支える配送機構だが、壊れても CI も
    ローカルも緑のまま、コンテキスト注入だけが黙って止まる。ここで
    hooks.json のパース可否・command パスの実在と実行ビット・hook スクリプトが
    参照する正本（_HOOK_CANONICAL_SOURCES）の実在を機械検証して塞ぐ。

    hooks/hooks.json が存在しないリポジトリでは no-op で pass する。
    """
    hooks_path = os.path.join(root, _HOOKS_JSON_REL)
    if not os.path.isfile(hooks_path):
        return []
    try:
        config = json.loads(_read(hooks_path))
    except json.JSONDecodeError as exc:
        return [f"[hooks] JSON として読めない: {_HOOKS_JSON_REL} ({exc})"]
    if not isinstance(config, dict):
        return [f"[hooks] トップレベルが object でない: {_HOOKS_JSON_REL}"]

    hooks_map = config.get("hooks")
    if not isinstance(hooks_map, dict):
        return [f"[hooks] hooks キーが object でない: {_HOOKS_JSON_REL}"]

    errors = []
    for event, entries in hooks_map.items():
        if not isinstance(entries, list):
            errors.append(
                f"[hooks] {event} のエントリが配列でない: {_HOOKS_JSON_REL}"
            )
            continue
        for entry in entries:
            hook_list = entry.get("hooks", []) if isinstance(entry, dict) else None
            if not isinstance(hook_list, list):
                errors.append(
                    f"[hooks] {event} のエントリ構造が不正: {_HOOKS_JSON_REL}"
                )
                continue
            for hook in hook_list:
                command = hook.get("command", "") if isinstance(hook, dict) else ""
                if not isinstance(command, str) or not command.strip():
                    errors.append(
                        f"[hooks] {event} の hook に command がない: {_HOOKS_JSON_REL}"
                    )
                    continue
                # "${CLAUDE_PLUGIN_ROOT}"/path 形式のクォートは shell 規則で解き、
                # 引数付き command を許すため先頭トークンだけ検査する
                try:
                    tokens = shlex.split(command)
                except ValueError as exc:
                    errors.append(
                        f"[hooks] command をシェル語彙として解釈できない: "
                        f"{command!r}（{event}, {exc}）"
                    )
                    continue
                if not tokens:
                    errors.append(
                        f"[hooks] {event} の hook に command がない: {_HOOKS_JSON_REL}"
                    )
                    continue
                script = tokens[0].replace("${CLAUDE_PLUGIN_ROOT}", root)
                rel = os.path.relpath(script, root)
                if not os.path.isfile(script):
                    errors.append(
                        f"[hooks] command の実体が存在しない: {rel}（{event}）"
                    )
                elif not os.access(script, os.X_OK):
                    errors.append(
                        f"[hooks] command に実行ビットがない: {rel}（{event}）"
                        f"（`chmod +x {rel}` で付与する）"
                    )

    # hook スクリプトが読む正本の実在（2 本目のスクリプトが現れたためマッピング化）
    for script_rel, source_rel in _HOOK_CANONICAL_SOURCES.items():
        script_path = os.path.join(root, script_rel)
        if os.path.isfile(script_path):
            source_path = os.path.join(root, source_rel)
            if not os.path.isfile(source_path):
                errors.append(
                    f"[hooks] {script_rel} が参照する正本が存在しない: "
                    f"{source_rel}"
                )
    return errors


_VERSION_HEADING_RE = re.compile(r"^##\s+(\d+(?:\.\d+)*)(?:\s.*)?$", re.M)


def parse_version(text):
    """`1.65.0` → (1, 65, 0)。数値以外を含むものは None（比較対象外）。"""
    if not text:
        return None
    parts = text.split(".")
    if not all(p.isdigit() for p in parts):
        return None
    return tuple(int(p) for p in parts)


_UNRELEASED_CANON = "Unreleased"
_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)


def _is_unreleased_label(text):
    """`[Unreleased]` / `unreleased` などの表記ゆれも未配布セクションとして拾う。"""
    return text.strip().strip("[]").casefold() == _UNRELEASED_CANON.casefold()


def check_unreleased_section(changelog):
    """チェック12b: `## Unreleased` の表記・個数・位置を検証する。

    PR ごとに version を bump すると、並走する PR が全て同じ番号を名乗り、マージ順に
    依存した manifest 衝突が必ず起きる（実例: 同時に開いた 6 PR が揃って 1.66.0）。
    起票は `## Unreleased` へ集約し、bump はリリース時に一度だけ行う運用を正とする。

    この節が表記ゆれで増殖したり配布済みエントリの下に埋もれると、リリース時にどれを
    番号へ昇格させるか機械的に決められなくなる。単一・先頭・正規表記を要求して、
    昇格対象が常に一意に定まる状態を保つ。
    """
    errors = []
    unreleased = [
        (m.start(), m.group(1))
        for m in _HEADING_RE.finditer(changelog)
        if _is_unreleased_label(m.group(1))
    ]
    if not unreleased:
        return errors
    for _, label in unreleased:
        if label != _UNRELEASED_CANON:
            errors.append(
                f"[changelog] 未配布セクションの見出しは「## {_UNRELEASED_CANON}」に"
                f"統一する（検出: 「## {label}」）"
            )
    if len(unreleased) > 1:
        errors.append(
            f"[changelog] 「## {_UNRELEASED_CANON}」が {len(unreleased)} 個ある"
            f"（未配布の起票先は 1 つに集約する）"
        )
    first_version = next(_VERSION_HEADING_RE.finditer(changelog), None)
    if first_version is not None and unreleased[0][0] > first_version.start():
        errors.append(
            f"[changelog] 「## {_UNRELEASED_CANON}」が配布済みエントリ"
            f"「## {first_version.group(1)}」より下にある"
            f"（未配布の起票先は最新版より上に置く）"
        )
    return errors


def check_changelog_sync(root):
    """チェック12: plugin.json の version と CHANGELOG.md の見出しを双方向で照合する。

    順方向（version → 見出しが存在する）: マーケットプレイスがスキル変更を認識するのは
    version bump 時のみで、CHANGELOG はその bump の唯一の変更記録。bump だけして起票を
    忘れると履歴が永久に欠落する（実例: 1.45.1〜1.46.1）。

    逆方向（見出し ≤ version）: 起票だけ先に済ませて bump を保留する / bump を revert する
    と、CHANGELOG に「配布されていないバージョン」の記述が残る。読者は配布物に入っていない
    変更を入っていると誤読するため、先行エントリも違反として扱う。順方向だけを見ていた
    ため実際にすり抜けた（1.66.0 / 1.67.0 の起票と bump 延期）。

    未配布の変更は番号付き見出しではなく `## Unreleased` へ起票する。逆方向チェックが
    禁じているのは「配布済みに見える番号」であって未配布の記録そのものではなく、
    Unreleased は誤読が原理的に起きないため許可する（書式は check_unreleased_section）。
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
    changelog = _read(changelog_path)
    errors = []
    # 見出し直後は空白か行末のみ許可（1.46.1 が 1.46.10 に誤マッチしないように）
    heading = re.compile(rf"^##\s+{re.escape(version)}(?:\s.*)?$", re.M)
    if not heading.search(changelog):
        errors.append(
            f"[changelog] plugin.json の version {version} に対応する "
            f"「## {version}」エントリが CHANGELOG.md にない"
        )
    current = parse_version(version)
    if current is not None:
        ahead = sorted(
            {
                found for found in _VERSION_HEADING_RE.findall(changelog)
                if (parsed := parse_version(found)) is not None and parsed > current
            },
            key=parse_version,
        )
        for found in ahead:
            errors.append(
                f"[changelog] 未配布バージョンのエントリが残っている: 「## {found}」 > "
                f"plugin.json の version {version}"
                f"（bump するか、「## {_UNRELEASED_CANON}」へ移す）"
            )
    errors += check_unreleased_section(changelog)
    return errors


# チェック15: 配布 manifest 群。3 つの manifest が別々に手編集されるため、
# 一致していなければならない項目が黙ってドリフトする。実際に .claude-plugin/plugin.json の
# repository が実在しない owner を指したまま配布されていた。
_MANIFEST_RELS = (
    os.path.join(".claude-plugin", "plugin.json"),
    os.path.join(".claude-plugin", "marketplace.json"),
    os.path.join(".codex-plugin", "plugin.json"),
)
_REPO_URL_RE = re.compile(r"github\.com[:/]([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")


def _manifest_versions(manifest):
    """manifest 内の version 値をすべて拾う（marketplace は plugins[] 側に持つ）。"""
    versions = []
    if manifest.get("version"):
        versions.append(manifest["version"])
    for entry in manifest.get("plugins", []) or []:
        if isinstance(entry, dict) and entry.get("version"):
            versions.append(entry["version"])
    return versions


# チェック16: command 名がスキル名と対応しないとき、利用者から見て二重の名前空間になる
# （`/debug` がどのスキルの入口か `/` 補完の説明文から分からない）。名前が対応しない
# command は description で対応スキル名を名指しすることを要求する。改名・削除はしない
# 方針（既存ユーザーの呼び出しを壊さない）なので、説明文側で解決する。
_SKILL_INVOCATION_RE = re.compile(r"claude-skills:([a-z0-9-]+)")


def check_command_skill_mapping(root):
    """チェック16: 名前が対応しない command が description で対応スキルを名指しするか。"""
    commands_dir = os.path.join(root, "commands")
    if not os.path.isdir(commands_dir):
        return []
    skills = set(_skill_dirs(root, "skills"))
    errors = []
    for name in sorted(os.listdir(commands_dir)):
        if not name.endswith(".md"):
            continue
        command = name[: -len(".md")]
        text = _read(os.path.join(commands_dir, name))
        targets = [s for s in _SKILL_INVOCATION_RE.findall(text) if s in skills]
        if not targets:
            continue
        target = targets[0]
        # command 名がスキル名そのもの、またはスキル名 + workflow 接尾辞なら自明
        if command == target or command.startswith(f"{target}-"):
            continue
        desc = extract_description(text) or ""
        if target not in desc:
            errors.append(
                f"[command] commands/{name} は {target} スキルを起動するが、"
                f"description が対応スキル名を含まない"
                f"（`/` 補完で入口が分からない。description に「{target} スキルの入口」"
                f"のように明記する）"
            )
    return errors


_FIXTURE_SETUP_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "skills", "skill-regression", "scripts")


def check_fixtures(root):
    """チェック17: skills/*/fixtures.json が回帰 fixture の契約に適合するか。

    fixture は commit される回帰資産だが、長らく機械検証がなく、critical 要件の
    欠落や setup の未知キーが黙って通っていた。fixture_setup.validate を
    in-process で適用する（dossier lint と同じ方式）。
    """
    skills_dir = os.path.join(root, "skills")
    if not os.path.isdir(skills_dir):
        return []
    if _FIXTURE_SETUP_DIR not in sys.path:
        sys.path.insert(0, _FIXTURE_SETUP_DIR)
    import fixture_setup  # noqa: E402

    errors = []
    for name in sorted(os.listdir(skills_dir)):
        path = os.path.join(skills_dir, name, "fixtures.json")
        if not os.path.isfile(path):
            continue
        rel = f"skills/{name}/fixtures.json"
        try:
            fixture = json.loads(_read(path))
        except json.JSONDecodeError as exc:
            errors.append(f"[fixture] {rel}: JSON として読めない ({exc})")
            continue
        errors += fixture_setup.validate(fixture, source=rel)
    return errors


def check_manifests(root):
    """チェック15: 配布 manifest の name / version / リポジトリ slug / LICENSE を照合する。"""
    errors = []
    manifests = {}
    for rel in _MANIFEST_RELS:
        path = os.path.join(root, rel)
        if not os.path.isfile(path):
            continue
        key = rel.replace(os.sep, "/")
        try:
            manifests[key] = json.loads(_read(path))
        except json.JSONDecodeError as exc:
            errors.append(f"[manifest] JSON として読めない: {key} ({exc})")
    if not manifests:
        return errors

    names = {rel: m.get("name") for rel, m in manifests.items() if m.get("name")}
    if len(set(names.values())) > 1:
        detail = ", ".join(f"{rel}={name}" for rel, name in sorted(names.items()))
        errors.append(f"[manifest] name が manifest 間で不一致: {detail}")

    versions = {
        rel: v for rel, m in manifests.items() for v in _manifest_versions(m)
    }
    if len(set(versions.values())) > 1:
        detail = ", ".join(f"{rel}={v}" for rel, v in sorted(versions.items()))
        errors.append(f"[manifest] version が manifest 間で不一致: {detail}")

    # LICENSE 宣言と実体。宣言だけあってファイルがないと配布物の利用条件が確定しない。
    declared = {rel: m["license"] for rel, m in manifests.items() if m.get("license")}
    if declared and not os.path.isfile(os.path.join(root, "LICENSE")):
        detail = ", ".join(f"{rel}={v}" for rel, v in sorted(declared.items()))
        errors.append(
            f"[manifest] license を宣言しているが LICENSE ファイルがない: {detail}"
        )

    # リポジトリ slug。README の install 手順と manifest の repository が違う owner を
    # 指していると、マーケットプレイス経由の利用者がリポジトリへ辿り着けない。
    repo_url = manifests.get(".claude-plugin/plugin.json", {}).get("repository")
    match = _REPO_URL_RE.search(repo_url or "")
    if match:
        owner, repo = match.groups()
        readme_path = os.path.join(root, "README.md")
        if os.path.isfile(readme_path):
            # 先頭に / や文字が続くものはファイルパス（`--plugin-dir /path/to/claude-skills`）
            # であって install slug ではない
            slug_re = re.compile(
                rf"(?<![A-Za-z0-9_./-])([A-Za-z0-9_.-]+)/{re.escape(repo)}"
                rf"(?![A-Za-z0-9_.-])"
            )
            found = {m.group(1) for m in slug_re.finditer(_read(readme_path))}
            for other in sorted(found - {owner}):
                errors.append(
                    f"[manifest] README.md の install 手順が別 owner を指している: "
                    f"{other}/{repo}（plugin.json の repository は {owner}/{repo}）"
                )
    elif repo_url:
        errors.append(
            f"[manifest] repository を github.com/<owner>/<repo> として解釈できない: "
            f"{repo_url}"
        )
    return errors


def check_relative_links(root, sources=None, exempt=None):
    """各ソース内の相対 .md リンクの実在を検証し、違反メッセージを返す。"""
    if sources is None:
        sources = collect_link_sources(root) + collect_doc_link_sources(root)
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

    # 11b. Workspace isolation policy（存在する場合のみ検証。不在は inplace 扱いで正）
    errors += check_workspace_policy(root)

    # 12. plugin.json version ⇔ CHANGELOG.md エントリ同期（双方向）
    errors += check_changelog_sync(root)

    # 13. frontmatter 値の strict YAML 互換
    errors += check_frontmatter_yaml_compat(root)

    # 14. ヒューマンリーダブル要約契約の横展開ガード
    errors += check_human_readable_summary(root)

    # 15. 配布 manifest の整合性
    errors += check_manifests(root)

    # 16. command 名 ⇔ 起動スキル名の対応（二重名前空間の可視化）
    errors += check_command_skill_mapping(root)

    # 17. 回帰 fixture の契約適合
    errors += check_fixtures(root)

    # 18. デザイントークンの authoring 層 ⇔ 配布層 同期
    errors += check_design_token_sync(root)

    # 19. agent 生成物の置き場に `.claude/` を使っていないか（移行後の再発防止）
    errors += check_legacy_claude_paths(root)

    # 20. リネーム許可表の失効エントリ（baseline に old が残っていないなら削除すべき）
    errors += check_rename_allowlist_staleness(root)

    # 21. plugin hooks の整合性（hooks.json / command 実在・実行ビット / 正本実在）
    errors += check_plugin_hooks(root)

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
