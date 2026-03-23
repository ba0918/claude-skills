---
name: skill-improve
description: セッションデータからスキル使用時の摩擦を検出・分析し、データ駆動でスキル改善を実行するメタスキル。「skill-improve」「スキル改善」「摩擦分析」で起動。
---

# Skill Improve

セッションデータから摩擦シグナルを収集・分析し、スキルの自己改善を実行するメタスキル。

## Flow Overview

```
skill-improve コマンド
  │
  ├─ Phase 1: データ収集（collect.py → context.json）
  │
  ├─ Phase 2: 摩擦分析（4エージェント並行）
  │    ├─ friction-detector / pattern-analyzer
  │    ├─ expectation-auditor / drift-detector
  │    └─ → friction-report.md
  │
  ├─ Phase 3: 改善仮説生成（investigate パターン）
  │    └─ → 改善仮説 A/B/C + 自走度判定
  │
  └─ Phase 4: 改善実装（improve モード時のみ）
       ├─ Small → iterate
       └─ Large → team-cycle に委譲
```

## パラメータ

- `$ARGUMENTS` の最初の引数: ワークフロー選択
  - `analyze`（デフォルト）: Phase 1-3 を実行し friction-report.md を生成
  - `report`: Phase 1 のみ実行し、収集データの JSON を出力
  - `improve`: Phase 1-4 を実行し、改善まで自動実行（Dry-run 必須）
- `--days N`: 分析対象期間（デフォルト: 30日）
- `--project NAME`: プロジェクトフィルタ（デフォルト: cwd から推定）

## Phase 1: データ収集

### Step 1.1: collect.py 実行

```bash
python3 skills/skill-improve/scripts/collect.py \
  --days {days} \
  --project {project} \
  --output .claude/tmp/skill-improve-{datetime}/context.json
```

### Step 1.2: 結果確認

context.json を読み込み、サマリーを表示:

```
── Phase 1: Data Collection ──
Project: {project_filter}
Period: {days} days
Sessions: {sessions_found}
Skill invocations: {total_skill_invocations}
Unique skills: {unique_skills_used}
Secret warnings: {count}
```

`report` モードの場合はここで終了。JSON 内容を表示して完了。

スキル呼び出しが 0 件の場合:

```
⚠️ No skill invocations found in the last {days} days.
Try increasing the period with --days or checking the project filter.
```

Phase 2 には進まず終了。

## Phase 2: 摩擦分析（4エージェント並行）

### Step 2.1: エージェント spawn

4つの分析エージェントを **並行で** Agent ツール（model: sonnet）で起動する。
各エージェントのプロンプトは [references/analysis-roles.md](references/analysis-roles.md) を参照。

各エージェントに渡すコンテキスト:
1. context.json の内容
2. 対象スキルの SKILL.md（Glob で取得）
3. ロール固有の分析指示

各エージェントは分析結果を JSON で `.claude/tmp/skill-improve-{datetime}/{role}.json` に書き出す。

### Step 2.2: 結果統合

統合エージェント（Agent ツール、model: sonnet）を起動し、4つの分析結果を統合して
`.claude/tmp/skill-improve-{datetime}/friction-report.md` を生成する。

統合エージェントのプロンプト:
```
.claude/tmp/skill-improve-{datetime}/ 配下の 4つの JSON ファイルを読み込み、
摩擦レポートを friction-report.md として書き出してください。

フォーマット:
# Friction Report: {project}

## Executive Summary
{1-3行の要約}

## Skill Rankings (摩擦スコア順)
| Skill | Score | Top Issue | Recommendation |

## Detailed Findings
### {skill_name}
- Friction Score: {score}
- Issues: ...
- Recommendations: ...

## Improvement Hypotheses
### Hypothesis A: {title}
- Target: {skill}
- Change: {description}
- Expected Impact: {impact}
- Size: Small / Large
```

表示:

```
── Phase 2: Friction Analysis ──
Agents: 4/4
Skills analyzed: {N}
Top friction skill: {name} (score: {score})
Report: .claude/tmp/skill-improve-{datetime}/friction-report.md
```

## Phase 3: 改善仮説と自走度判定

### Step 3.1: friction-report.md を読み込む

### Step 3.2: 自走度判定

[references/scoring-guide.md](references/scoring-guide.md) の基準に従い、改善の規模を判定:

| 摩擦スコア | 判定 | アクション |
|-----------|------|-----------|
| 0-2 | レポートのみ | friction-report.md を表示して終了 |
| 3-5 | Small | iterate で SKILL.md を直接修正 |
| 6+ | Large | team-cycle に委譲 |

`analyze` モードの場合はここで終了。friction-report.md の内容と改善仮説を表示。

表示:

```
── Phase 3: Improvement Hypotheses ──
Hypotheses: {N}
Recommended action: {Report only / iterate / team-cycle}
Top hypothesis: {title} (target: {skill}, size: {size})
```

## Phase 4: 改善実装（improve モード時のみ）

**重要: 全レベルで Dry-run を必ず実行する。**

### Step 4.1: Dry-run 表示

改善対象のスキルファイルと変更内容の概要を表示:

```
══════════════════════════════════════
SKILL-IMPROVE DRY-RUN
Target skill: {skill_name}
Files to modify: {file_list}
Change summary: {summary}

Proceeding with implementation...
══════════════════════════════════════
```

### Step 4.2: 実装委譲

| サイズ | 委譲先 | 方法 |
|--------|--------|------|
| Small | iterate | Skill ツールで `claude-skills:iterate` を実行。friction-report の改善仮説を引数として渡す |
| Large | team-cycle | 改善仮説から plan を作成し、`claude-skills:team-cycle` に委譲 |

### Step 4.3: 完了表示

```
══════════════════════════════════════
SKILL-IMPROVE COMPLETE
Mode: {improve}
Skills analyzed: {N}
Improvements applied: {N}
Report: {friction_report_path}
══════════════════════════════════════
```

## 一時ファイルのクリーンアップ

Phase 完了時（正常終了・エラー問わず）に `.claude/tmp/skill-improve-{datetime}/` を削除する。
ただし `friction-report.md` は保持する（ユーザーが後で参照できるように）。

## エラーハンドリング

### Phase 1 のエラー

- **Python 未インストール**: エラーメッセージを表示して中断
- **collect.py 実行失敗**: stderr を表示して中断
- **セッションデータなし**: 警告を表示して中断

### Phase 2 のエラー

- **エージェント spawn 失敗（2名以上成功）**: 成功したエージェントの結果のみで続行
- **エージェント spawn 失敗（1名以下）**: 中断

### Phase 4 のエラー

- **iterate/team-cycle 失敗**: エラー内容を表示。friction-report.md は保持

## References

- 摩擦分析エージェントロール: [references/analysis-roles.md](references/analysis-roles.md)
- 摩擦スキーマ定義: [references/friction-schema.md](references/friction-schema.md)
- スコアリング基準: [references/scoring-guide.md](references/scoring-guide.md)
