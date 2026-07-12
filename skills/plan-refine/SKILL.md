---
name: plan-refine
description: 実装計画を plan-reviewer による review → fix ループで改善する計画品質ゲート。全観点 PASS か最大イテレーション数到達で終了する。cycle の Phase 1 としても単体でも使える。「plan-refine」「計画を磨いて」「計画をレビューして直して」「refine」で起動。
---

# Plan Refine

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md). Resolve and validate the store before reading or writing artifacts.

実装計画を `claude-skills:plan-reviewer` スキルでレビューし、検出された問題に対して
計画ファイルを直接編集して改善する。これを全観点 PASS になるか、
最大イテレーション数に達するまでループする。

判定の語彙は [plan-reviewer](../plan-reviewer/SKILL.md) の定義に従う。要点: 各観点は 0-100 のスコア
（最も重い指摘の重さ）を持ち、0-49 = PASS / 50-79 = WARN / 80-100 = BLOCK。
本スキルでの終了条件「全観点 PASS」は「WARN / BLOCK が 1 件も残っていない」ことと同義。

plan-reviewer をスキルとして起動できない環境では、plan-reviewer の **SKILL.md 本体と references の両方**
（観点定義・UI/UX の条件付きトリガー判定・フォールバック規定・出力形式を含む）を読み、
同じ観点・同じ判定基準で自分がインラインでレビューを実施する。
インライン代行ではレビュアーと修正者が同一になるため、次の 2 点でバイアスを抑える:
- レビュー時は自分の直前の編集を前提とせず、計画本文だけを読み直して採点する
- 修正後の再レビューで判定を引き上げる場合、解消の根拠（該当する変更箇所の引用）を添える。根拠なく PASS にしない

## パラメータ

- 引数の最初の数値: 最大イテレーション数（デフォルト: 3）
- 引数のファイルパス: 対象計画ファイル。省略時は `.agents/artifacts/plans/` 直下の `*.md` を
  **ファイル名のタイムスタンプ降順**で並べた先頭を選ぶ（mtime は編集で入れ替わるため使わない）

## フロー

### Iteration 1（フルレビュー）

1. スキル `claude-skills:plan-reviewer` を起動（7観点フルレビュー、UI/UX は条件付き）
   - 対象ファイルは引数で指定。省略時は `.agents/artifacts/plans/` 内の最新を自動選択
   - 対象ファイルのパスを記憶しておく（以降のイテレーションで再利用）
2. 結果が全て PASS → 終了（完了報告へ）
3. WARN/BLOCK がある場合:
   a. 各指摘を検討し、計画ファイルを直接編集して改善
   b. **そのイテレーションで改善した箇所**の diff（変更ハンクまたはその要約）を表示する。
      全イテレーション分をまとめた累積 stat 1 回だけで済ませるのは不可。
      変更追跡ができないファイルでは変更前後の要約で代替する
   c. 次のイテレーションへ

### Iteration 2+（差分レビュー）

1. 前回 WARN/BLOCK だった観点のみ再レビューする
   - `claude-skills:plan-reviewer` へ対象観点を明示して依頼する。観点の部分指定を受け付けない場合は
     フルレビューを依頼し、**前回 WARN/BLOCK だった観点の結果のみ**を判定に使う
   - 同じ対象ファイルを引数で明示的に渡す（自動選択に頼らない）
   - PASS だった観点はスキップ（コンテキスト消費を抑える）
2. 結果が全て PASS → 終了
3. まだ WARN/BLOCK がある場合 → 改善して次へ

### 終了条件

- 全観点 PASS
- 最大イテレーション数に到達 → 残りの WARN/BLOCK を一覧表示して終了

### 完了報告

ユーザーに以下を提示:

- 実行したイテレーション数（レビュー 1 回＝1 イテレーションと数える。修正の有無は問わず、最終のレビューのみの回も含む）
- 各イテレーションで改善した項目のサマリー
- 最終的な各観点のスコアと判定
- 残存する WARN/BLOCK があればその一覧
