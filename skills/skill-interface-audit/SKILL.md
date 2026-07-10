---
name: skill-interface-audit
description: 各 SKILL.md を API 仕様として静的に監査し、契約の欠落・構造違反を検出するスキル。skill-authoring.md の執筆原則を正本とし、SI-* ルール体系で機械検証する。純関数 static + LLM 意味判断の混成モデル。パッチ候補を含む finding を出力し、動的検証は既存メタスキルへ橋渡しする。「skill-interface-audit」「インターフェース監査」「スキル契約チェック」「SKILL.md 監査」「API仕様チェック」で起動。
---

# skill-interface-audit

[skill-authoring.md](../shared/references/skill-authoring.md) の執筆原則を正本とし、各 SKILL.md を「API 仕様」として静的に監査する。
既存メタスキルが動的実測と常駐指示の品質を所有するのに対し、本スキルは **skills/\*/SKILL.md の契約完備性** を所有する（[位置づけ詳細](references/positioning.md)）。

## 位置づけとアーキテクチャ

メタスキル群の中で「契約層」を所有し、context-audit とは対象ファイル集合で排他的に切る。純関数 static + LLM 意味判断の混成モデル。詳細は [references/positioning.md](references/positioning.md)。

参照資料（Progressive disclosure）:

- 位置づけ・アーキテクチャ: [references/positioning.md](references/positioning.md)
- ルール定義: [references/rule-catalog.md](references/rule-catalog.md)
- fix-action 3 値の定義: [../shared/references/fix-action-taxonomy.md](../shared/references/fix-action-taxonomy.md)
- severity の定義: [../shared/references/severity-and-verdicts.md](../shared/references/severity-and-verdicts.md)
- 執筆原則の正本: [../shared/references/skill-authoring.md](../shared/references/skill-authoring.md)
- 完了検証: [../shared/references/verification-gate.md](../shared/references/verification-gate.md)

## 引数

- 引数なし: skills/ 配下の全スキルを監査。
- スキル名（1 つ以上）: 指定スキルのみ監査。例: `skill-interface-audit refactor commit`
- `--update-baseline`: 現在の finding を baseline に確定（以降は新規 finding のみ提示）。
- `--bridge`: 動的検証への橋渡し出力を生成（empirical-prompt-tuning のシナリオ候補 + skill-regression の fixture 候補）。

command は作らない（skills-first 方針。single-workflow のため名前付き入口も不要）。

## 実行契約

- **スクリプトのパス解決**: `{skill_dir}` はこのスキルの配置ディレクトリ（絶対パス）。`{project_root}` はユーザーのプロジェクトルート（cwd）。
- **非対話フォールバック**: headless / subagent 実行時は状態を変更しない安全側に倒す。baseline は書き込まず、フルレポートを出力する。
- `{ts}` は `date +%Y%m%d-%H%M%S` で採番し、フェーズ間で同一値を使い回す。
- **出力先**: `.claude/tmp/skill-interface-audit/`（git-ignored）。

## ワークフロー

### Phase 0: Discovery

1. `skills/*/SKILL.md` を収集し対象リストを生成する。引数でスキル名が指定されていれば絞り込む
2. 各スキルの `references/` 配下のファイルも副対象として収集する
3. baseline ファイル（`.claude/skill-interface-audit-baseline.json`）の有無を確認する
4. baseline の扱い:
   - **全スキル監査 + baseline 不在**: first-run フローを提示 — (a) 現状を baseline として確定し以降は新規 finding のみ / (b) フルレポートのみ（baseline は書き込まない）
   - **単一スキル指定**: baseline の first-run フローは提示しない。フルレポートを出力する。`--update-baseline` 明示時のみ baseline に書き込む

### Phase 1: Static Checks（純関数）

SI-S\* ルールを一括実行し findings JSON を出力する。

対象ルール: SI-S001〜SI-S004（詳細は [rule-catalog.md](references/rule-catalog.md)）。
いずれも skill-authoring.md の機械検証可能な原則に対応し、決定的に判定できる。

finding schema は context-audit と共通:
`id / severity / action / where(skill:file:line) / what / why / how / fix_draft(null | suggested text)`

### Phase 2: Contract Assessment（LLM, REPORT\_ONLY）

SI-C\* ルールを LLM が評価する。Phase 1 とは明確に分離する。

1. 各スキルの SKILL.md を読み、SI-C001〜SI-C006 の契約要素を評価する
2. **「該当なし」は正当な状態**: 読み取り専用スキル（investigate）に副作用宣言は不要、単一ワークフロースキルに委譲条件は不要。「このスキルの性質上、この契約要素は不要」と判断できれば PASS
3. 判定基準は「セクションが存在するか」ではなく「**LLM がこの点で誤解して事故を起こしうるか**」
4. 全 finding は REPORT\_ONLY。パッチ候補（具体的な追記文面のドラフト）を `fix_draft` に含める
5. パッチ候補は NEEDS\_JUDGMENT が上限であり、**自動適用しない**（[fix-action-taxonomy.md](../shared/references/fix-action-taxonomy.md): 本文の意味的書き換えは AUTO\_FIX 禁止）

### Phase 3: Aggregate & Bridge

1. Phase 1 + Phase 2 の findings を統合する
2. baseline suppression を適用し、新規 finding のみ提示する（suppressed 件数は明示、silent truncation 禁止）
3. summary-first レポートを生成:
   ```
   N findings: X NEEDS_JUDGMENT / Y REPORT_ONLY; M suppressed
   ── Phase 1 (structural) ──
   [findings grouped by rule, severity descending]
   ── Phase 2 (contract) ──
   [findings grouped by rule, severity descending]
   ```
4. `--bridge` 指定時、動的検証への橋渡し出力を生成:
   - SI-C\* finding の曖昧箇所 → empirical-prompt-tuning のシナリオ候補（friction-taxonomy カテゴリにマッピング）
   - パッチ候補適用後の差分 → skill-regression の fixture 候補
5. [verification-gate.md](../shared/references/verification-gate.md) 契約に準拠し、エビデンスを伴って完了を報告する

### friction-taxonomy マッピング（bridge 出力用）

SI-C\* finding を empirical-prompt-tuning の固定タクソノミにマッピングし、語彙の二重化を防ぐ:

| SI-C ルール | friction category | 根拠 |
|---|---|---|
| SI-C001 副作用 | rationalization\_hook | 未宣言の副作用は合理化で回避される |
| SI-C002 完了条件 | ambiguous\_term / missing\_premise | 曖昧な完了条件は複数解釈を生む |
| SI-C003 失敗時 | missing\_premise | 失敗シナリオの暗黙前提 |
| SI-C004 入力 | missing\_premise / ambiguous\_term | 引数の暗黙前提 |
| SI-C005 出力 | ambiguous\_term | 成果物の曖昧な定義 |
| SI-C006 委譲 | self\_containment\_gap | 他スキルへの暗黙的依存 |

## 重要なルール

- **SKILL.md を変更しない**: 本スキルの出力は全て REPORT\_ONLY または NEEDS\_JUDGMENT。パッチ候補は提案であり、適用はユーザーが判断する
- **テンプレート強制にしない**: 「全スキルに N セクション追加せよ」という圧にしない。判定基準は「LLM がこの点で誤解しうるか」であり、形式の統一ではない
- **validate\_repo.py と重複しない**: frontmatter・description・リンク実在・共有契約語彙は CI 管轄。本スキルはそれ以外を所有する
- **severity の根拠を経験に接地する**: Tier の「事故直結」は経験的主張。skill-improve の friction データや empirical の実測に紐付けられないものは INFO に留める
- **基準を新規発明しない**: SI-\* ルールは skill-authoring.md の原則を監査するものであり、独自の品質基準を作らない（[skill-authoring.md](../shared/references/skill-authoring.md) #5）

## 合理化防止

| 言い訳 | 現実 |
|--------|------|
| 「このスキルはシンプルだから副作用宣言は不要」 | シンプルなスキルほど LLM が勝手に拡張する |
| 「完了条件は文脈から自明」 | 自明と推測は区別できない。明示するか N/A と判断する |
| 「全スキルに finding が出るから意味がない」 | baseline で抑制し、新規 finding だけ見る |
| 「パッチ候補をそのまま適用すればいい」 | パッチは NEEDS\_JUDGMENT。文脈を確認してから判断する |

## 副作用

- `.claude/tmp/skill-interface-audit/` 配下にレポート・findings JSON を生成する
- `--update-baseline` 指定時のみ `.claude/skill-interface-audit-baseline.json` を書き込む
- skills/\*/SKILL.md は**一切変更しない**

## 完了条件

- 対象スキル全件の Phase 1 + Phase 2 が完了している
- summary-first レポートが生成されている
- baseline 更新が要求された場合、baseline ファイルが書き込まれている
- [verification-gate.md](../shared/references/verification-gate.md) のエビデンス要件を満たしている

## 失敗時の扱い

- Phase 1 スクリプトの実行失敗: エラー内容を報告し、Phase 2 に進む（部分結果は破棄しない）
- Phase 2 の LLM 評価が特定スキルで失敗: そのスキルをスキップし、残りを継続する
- 全フェーズ失敗: 収集できた情報を含むエラーレポートを出力する

## 前提条件

- Python 3 が利用可能であること
- `skills/` ディレクトリが存在すること（本リポジトリ、または skill-authoring.md 準拠のスキル集リポジトリ）

## 委譲条件

| 状況 | 委譲先 |
|------|--------|
| description の発火精度を計測したい | trigger-eval |
| スキル本文の実行品質を評価したい | empirical-prompt-tuning |
| スキル変更後の回帰を検証したい | skill-regression |
| 実運用の摩擦を検出したい | skill-improve |
| CLAUDE.md / AGENTS.md / rules を監査したい | context-audit |
| スキル内のコード⇔ドキュメント整合性 | doc-check |
