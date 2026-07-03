---
name: context-audit
description: LLM 向け指示ファイル（CLAUDE.md / AGENTS.md / .claude/rules / プロジェクトメモリ）の老朽化・矛盾・有害指示・クロスツール乖離を監査する棚卸しスキル。純関数ルールエンジン（CA-* ルール体系）で機械検証し、AUTO_FIX / NEEDS_JUDGMENT / REPORT_ONLY の 3 値で扱い、削除は絶対に自動化しない。「context-audit」「指示ファイル監査」「CLAUDE.md 棚卸し」「AGENTS.md 監査」「メモリ棚卸し」「指示の腐敗」「指示の陳腐化をチェック」で起動。doc-check（code⇔docs）/ doc-audit（docs⇔docs）が見ない「指示としての品質」を所有する。メモリ監査はデフォルトで cwd 対応プロジェクトのみ、グローバルは `--include-global` で opt-in。baseline suppression 対応。skills-first のため command なし、Claude 版のみ。
---

# context-audit

LLM の行動品質は指示層（CLAUDE.md / AGENTS.md / rules / メモリ）の健全性に依存する。
長期運用でこの層が腐敗（陳腐化した参照・矛盾・破壊的許可・クロスツール乖離）すると LLM の挙動が劣化するが、
既存の doc-check（docs⇔code）/ doc-audit（docs⇔docs）はこの「**指示としての品質**」を見ておらず、
プロジェクトメモリはどのスキルの射程にも入っていない。context-audit はこの棚卸しを担う。

**位置づけ**: doc-check がコード正確性、doc-audit がドキュメント間整合性を所有するのに対し、
context-audit は instruction-bearing ファイルを「指示品質」として所有する。

## アーキテクチャ: 純関数ルール中心

trigger-eval / skill-improve と同じ「**純関数は unittest で検証、エージェントは JSON の生成・受け渡しのみ**」の構成。
監査ロジックは Python スクリプトに集約し、SKILL.md はワークフロー制御・LLM 判断（CA-C001 矛盾の REPORT_ONLY 分類・
NEEDS_JUDGMENT の提示）・AUTO_FIX の適用のみを担う。決定性は glue（SKILL.md 本文）に漏らさない。

| スクリプト | 役割 |
|-----------|------|
| `scripts/collect_targets.py` | 監査対象を path allowlist（決定的）で収集・分類。cwd→memory slug 解決 + reverse-verify |
| `scripts/static_checks.py` | 純関数ルールエンジン（`RULES` レジストリ・ディスパッチャ）。findings JSON を出力 |
| `scripts/apply_fixes.py` | AUTO_FIX 適用の純関数（findings + 内容 → 新内容。body byte 不変・idempotent） |
| `scripts/aggregate_report.py` | findings + baseline → summary-first レポート（suppression 適用・severity 集計） |
| `scripts/secret_detect.py` の実体 | `skills/shared/scripts/secret_detect.py`（skill-improve と共有、再利用） |

参照資料（Progressive disclosure）:

- ルール定義: [references/rule-catalog.md](references/rule-catalog.md)
- メモリ監査の詳細・プライバシー制約: [references/memory-audit.md](references/memory-audit.md)
- baseline suppression の schema と運用: [references/baseline-format.md](references/baseline-format.md)
- fix-action 3 値の定義: [../shared/references/fix-action-taxonomy.md](../shared/references/fix-action-taxonomy.md)
- severity の定義: [../shared/references/severity-and-verdicts.md](../shared/references/severity-and-verdicts.md)
- 完了検証: [../shared/references/verification-gate.md](../shared/references/verification-gate.md)

## 引数

- 引数なし: カレントリポジトリの指示ファイル + cwd 対応プロジェクトメモリを監査。
- `--include-global`: `~/.claude/CLAUDE.md` と `~/.claude/rules/*.md` を追加対象化（プライバシー opt-in）。
- `--update-baseline`: 現在の finding を baseline に確定（以降は新規 finding のみ提示）。実装は `aggregate_report.py --update-baseline PATH`（LLM が ID を手集めしない）。
- `--interactive`: NEEDS_JUDGMENT の対話プロンプトを再開（1 run の上限を超えた分の続き）。

command は作らない（skills-first 方針。single-workflow のため名前付き入口も不要）。

## ワークフロー

出力先はすべて `.claude/tmp/context-audit/`（git-ignored）。`{ts}` は実行時刻。

### Phase 0: Discovery

```bash
python3 skills/context-audit/scripts/collect_targets.py . \
  --output .claude/tmp/context-audit/targets-{ts}.json
```

- **path allowlist（決定的・純関数）** で対象を収集。対象: root の `CLAUDE.md` / `AGENTS.md`、
  `.claude/rules/*.md` / `rules/*.md`、`.claude/review-rules.md` + cwd 対応プロジェクトメモリ。
- 存在しない対象（例: `.claude/rules/` 不在）は graceful-skip（`skipped` に記録、エラーにしない）。
- ネストしたサブディレクトリの CLAUDE.md/AGENTS.md、`docs/plans/`・`docs/ideas/`・`.claude/tmp/` 等の
  archival/一時領域は allowlist に含めない（＝除外）。
- 非 UTF-8 / 読込失敗の 1 ファイルが監査全体を中断しない（`errors='replace'` / skip-and-report）。
- `--include-global` 指定時のみグローバル設定を追加。
- **baseline 不在を検知したら first-run フロー**を AskUserQuestion で提示: 「(a) 現状を baseline
  として確定し以降は新規 finding のみ / (b) 重大度上位のみ triage / (c) フルレポート」。初回の overwhelm を回避。
- レポートに `memory_dir`（解決済み絶対パス）を明示し、どのプロジェクトを読んだか可視化する。

### Phase 1: Static Checks

```bash
python3 skills/context-audit/scripts/static_checks.py \
  .claude/tmp/context-audit/targets-{ts}.json --root . \
  --output .claude/tmp/context-audit/findings-{ts}.json
```

- `RULES` レジストリを一括実行し findings JSON を出力。
- finding schema は全ルール共通で `id / severity / action / where(file:line) / what / why / how /
  fix_action(old→new|null)` を必須とする。
- **secret redaction を全 finding の line-context に適用してから直列化**（`finalize_findings`）。
  検出値・生 secret 行は JSON にも残さない。

### Phase 2: LLM Checks（REPORT_ONLY）

- `static_checks.py` が抽出した CA-C001 の contradiction candidate（recall 優先の over-generation）を、
  LLM が「矛盾 / 意図的差分 / 優先順位で解決済み / 不明」に分類する。**修正はしない**。
- LLM に渡すのは **redaction 済みの正規化最小 claim テキストのみ**（生のメモリ行・PII を渡さない）。

### Phase 3: Aggregate

```bash
python3 skills/context-audit/scripts/aggregate_report.py \
  .claude/tmp/context-audit/findings-{ts}.json \
  --baseline .claude/context-audit-baseline.json \
  --output .claude/tmp/context-audit/report-{ts}.json
```

- baseline suppression を適用し、**summary-first の report skeleton** を決定的に生成
  （トップ行 `N findings: X AUTO_FIX / Y NEEDS_JUDGMENT / Z REPORT_ONLY; M suppressed`、
  rule 別グループ → severity 降順ソート）。
- **action は static_checks.py の出力を尊重し再計算しない**。
- suppress された finding は件数のみ表示（silent truncation 禁止）。

### Phase 4: Apply & Report

- **AUTO_FIX**: `apply_fixes.py` で計算した差分を **unified diff で提示 → バッチ確認**
  （「N 件の auto-fix を適用しますか？」）の上で適用。
  ```bash
  python3 skills/context-audit/scripts/apply_fixes.py \
    .claude/tmp/context-audit/findings-{ts}.json --write
  ```
- **NEEDS_JUDGMENT**: fix-type / rule ID でグルーピングしてバッチ提示（「12 件のパス typo 修正を
  一括適用 / 個別に確認 / スキップ」）。対話プロンプトは 1 run で上限 N 件に cap し、残りはレポート送り
  （`--interactive` で再開）。
- **REPORT_ONLY**: what / why / how を含む actionable な構造化レポートで提示
  （contradiction は 2 箇所の location を併記）。
- `verification-gate.md` 契約に準拠し、**テスト実行結果のエビデンス**を伴って完了を報告する。

## 重要なルール

- **削除・本文の意味的書き換えは絶対に自動化しない**。AUTO_FIX はパス修正（edit-distance ≤1 かつ
  一意候補のみ）と frontmatter 整形正規化（body byte 不変）に限定。迷ったら REPORT_ONLY / NEEDS_JUDGMENT に倒す。
- **メモリ監査はデフォルト cwd 対応プロジェクトのみ**。グローバル・横断は `--include-global` opt-in。
  slug 解決は実 Claude Code に一致 + reverse-verify、曖昧なら fail-safe skip。
- **secret は値を転記せずパターン名 + file:line のみ**。redaction は全 line-context の不変条件。
- **baseline は commit するが opaque finding ID のみ格納**（検出値・本文を絶対に載せない）。
- **CA-D002 は `validate_repo.py` 検出時に自動スキップ**（機械的 deconflict、prose 判断に頼らない）。

## テスト

純関数は `scripts/test_*.py` の unittest で検証する:

```bash
for t in skills/context-audit/scripts/test_*.py; do python3 "$t"; done
```

- `test_collect_targets.py` / `test_static_checks.py` / `test_apply_fixes.py` /
  `test_aggregate_report.py` / `test_catalog_sync.py`（catalog⇔registry drift 防止）/
  `test_secret_detect.py`（共有 secret 検出の回帰）。
