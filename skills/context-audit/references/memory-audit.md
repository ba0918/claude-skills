# Memory Audit（メモリ監査の詳細）

> 本ファイルの AUTO_FIX / NEEDS_JUDGMENT / REPORT_ONLY は共通契約
> [fix-action-taxonomy.md](../../shared/references/fix-action-taxonomy.md) に従う。

プロジェクトメモリ（`~/.claude/projects/{cwd-slug}/memory/*.md`）は、長期運用で腐敗しても
既存のどのスキルの射程にも入っていない。context-audit はこれを監査対象に含めるが、
**プライバシー事故を防ぐため対象範囲を厳格に絞る**。

## 対象範囲（デフォルト = cwd 対応プロジェクトのみ）

- **デフォルト**: `~/.claude/projects/{slugify(cwd)}/memory/` の `*.md` のみ。
- **`--include-global` 指定時のみ**: `~/.claude/CLAUDE.md` と `~/.claude/rules/*.md` を追加。
- 全プロジェクト横断は**サポートしない**（別プロジェクトの memory を読むのは事故）。

## cwd → memory slug 解決

実 Claude Code の slug 化は「**すべての非英数字を `-` に置換**」する（`/` だけではない）。

```
slugify("/home/mizumi/develop/claude-skills") == "-home-mizumi-develop-claude-skills"
slugify("/x/.claude")                          == "-x--claude"   # '.' も '-' になる
```

実装は `collect_targets.slugify_cwd`（`re.sub(r"[^A-Za-z0-9]", "-", path)`）。
実ディレクトリ fixture に対する unittest（`test_collect_targets.py`）で検証している。

### reverse-verify + fail-safe skip

解決した memory ディレクトリは、以下を満たさなければ**読まずにスキップ**する（`resolve_memory_dir`）:

1. ディレクトリが実在する（`is_dir()`）。
2. symlink を解決した実体が `~/.claude/projects/<slug>/memory` に**ちょうど 2 階層**で収まる
   （symlink 脱出を排除。なお異なる cwd が同一 slug に潰れる真の collision は構造上検出不能であり、
   その場合も読み込み先の絶対パスをレポートに明示することで可視化する）。

曖昧なら `None` を返してスキップ。監査した memory の**解決済み絶対パスをレポートに明示**し、
「どのプロジェクトを読んだか」を可視化する。

## type 別チェック（CA-M001 / M101 / M301）

### CA-M001: frontmatter schema

観測された frontmatter（`name` / `description` / `type` / `originSessionId`）は
**Claude Code ランタイム慣習でありリポジトリ所有ではない**。harness drift による偽陽性を避けるため保守的に扱う:

- 必須キー（`name` / `description`）欠落 → **NEEDS_JUDGMENT**（自動補完しない）。
- `type` の未知値 → **NEEDS_JUDGMENT**（hard violation にしない）。観測済み既知値:
  `user` / `feedback` / `reference` / `project` / `session`。
- frontmatter キーの整形揺れ（`name:note` → `name: note`）→ **AUTO_FIX**。ただし
  **frontmatter ブロック内のみ**を書き換え、`---` 以降の body は byte 単位で不変
  （`test_apply_fixes.py` の `test_body_bytes_unchanged` で保証）。

### CA-M101: 参照実在

メモリ本文が参照する repo 相対パス（markdown link / backtick）が実在するかチェック。
実在しなければ **NEEDS_JUDGMENT**（メモリは絶対に自動書き換えしない）。

### CA-M301: secret 検出

`skills/shared/scripts/secret_detect.py`（skill-improve 由来・テスト済み）を再利用して
行単位で secret/credential 疑いを検出。**REPORT_ONLY / severity=BLOCK**。

## プライバシー制約（不変条件）

- 検出した secret 値は**レポートにも中間 JSON にも転記しない**。パターン名と `file:line` のみ。
  redaction は `static_checks.finalize_findings` で全 finding の全 line-context に適用（`mask_secrets`）。
- Phase 2 の LLM / Phase 4 の AskUserQuestion には**生のメモリ行・PII を渡さない**。
  正規化済み最小 claim テキスト（redaction 済み）のみを渡す。
- メモリに対する AUTO_FIX は frontmatter 整形正規化のみ。**削除・本文の意味的書き換えは禁止**。
