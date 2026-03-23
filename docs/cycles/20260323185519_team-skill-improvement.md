# Team Skill Improvement (team-plan / team-cycle)

**Cycle ID:** `20260323185519`
**Started:** 2026-03-23 18:55:19
**Status:** In Progress

---

## What & Why

team-plan / team-cycle スキルに対するユーザーフィードバック4点（議論のメタレビュー、途中経過の可視化、実装後コードレビュー、ユーザーコメント再議論）を反映し、チーム議論の品質・透明性・実装品質担保を向上させる。

## Goals

- 議論の途中経過をユーザーに可視化し「置いてけぼり感」を解消する
- 実装後のコードレビューフェーズを追加し、計画と実装のギャップを検出する
- 議論ラウンド数を増やし、より深い議論を可能にする
- ユーザーコメントによるチーム再議論をオプションとして提供する
- 判定基準・重大度定義を共通化し、フロー間の一貫性を担保する

## Design

### Step 1: 途中経過の可視化 + ラウンド数増加（工数: 小、効果: 大）

> **依存関係**: Step 2 の完了後に実装すること。早期収束条件が Step 2 の重大度定義（BLOCK/WARN/INFO）に依存するため。

#### Files to Change

```
skills/team-plan/SKILL.md - 各ラウンド終了時にサマリー出力する指示を追加
skills/team-plan/references/planning-flow.md - 最大ラウンド数を 2→3 に変更、早期収束条件追加、サマリー出力フォーマット追加
skills/team-cycle/SKILL.md - 各ラウンド終了時にサマリー出力する指示を追加
skills/team-cycle/references/review-flow.md - 最大ラウンド数を 2→3 に変更、早期収束条件追加、サマリー出力フォーマット追加
```

#### Key Points

- **サマリー出力フォーマット**: Lead が各ラウンド終了時にユーザー向けに以下を出力する
  ```
  ── Round {N}/{max} ──
  論点: {topic}
    Security: {stance_summary} [BLOCK/WARN/INFO/PASS]
    Performance: {stance_summary} [BLOCK/WARN/INFO/PASS]
    Architect: {stance_summary} [BLOCK/WARN/INFO/PASS]
    Pragmatist: {stance_summary} [BLOCK/WARN/INFO/PASS]
    Status: {resolved | ongoing}
  ```
- **早期収束条件**: ラウンド終了時に全論点が WARN 以下に収束していたら残りのラウンドをスキップ（重大度定義は severity-and-verdicts.md を参照）
- **ラウンド上限**: 最大3ラウンド（メタレビュー含めず）。4以上は収穫逓減でコスト対効果が悪い

### Step 2: 判定基準・重大度定義の共通化（工数: 小、効果: 中）

#### Files to Change

```
skills/shared/references/severity-and-verdicts.md - 新規作成: 重大度定義 + 判定基準
skills/shared/references/team-config.md - 共通原則（ラウンド制限、早期収束条件、Lead 最終判断）を追記
skills/team-cycle/references/review-flow.md - 判定基準の定義を severity-and-verdicts.md への参照に置き換え
skills/team-plan/references/planning-flow.md - 同上
```

#### Key Points

- **severity-and-verdicts.md の内容**:
  - 重大度: BLOCK（進行不可）/ WARN（要検討）/ INFO（参考情報）の定義と使い分け基準
  - 計画レビュー判定: APPROVED / APPROVED WITH CONCERNS / REJECTED
  - コードレビュー判定: PASS / PASS WITH NOTES / NEEDS FIX
  - 各判定に対応するアクション（次フェーズへ / 記録して続行 / 中断）
  - メタレビュー規則: 条件付き発火（BLOCK 存在時のみ）、最大1回、入力は差分のみ、対象メンバーは BLOCK/WARN 発行者のみ
- **team-config.md への共通原則追記**: ラウンド制限、早期収束条件、Lead が最終判断権を持つこと

### Step 3: 実装後コードレビュー（工数: 中、効果: 大）

#### Files to Change

```
skills/team-cycle/SKILL.md - Phase 2.5（コードレビュー）を追加
skills/team-cycle/references/code-review-flow.md - 新規作成: コードレビューフロー
skills/shared/references/team-config.md - Security と Architect のコードレビュー用フレーミング（検証者）+ スポーンプロンプトを追加
```

#### Key Points

- **実装方式**: Agent 2本並行（Security + Architect）。TeamCreate は使わない
  - Security: 脆弱性、認証情報漏洩、入力検証の実装漏れ、エラーハンドリングでの情報露出
  - Architect: レイヤー違反、依存方向の遵守、テスタビリティ
- **レビュー対象**: `git diff {base_commit}..HEAD` の変更差分のみ（`base_commit` は Phase 2 実装開始直前に `git rev-parse HEAD` でキャプチャ）。diff が500行を超える場合はファイル単位で分割して各 Agent に配分
- **code-review-flow.md の構成**: 独立レビュー → 論点整理 → 合意形成（議論ラウンドは最大1回）。計画レビューより軽量
- **判定基準**: PASS / PASS WITH NOTES / NEEDS FIX
- **NEEDS FIX 時**: 修正指示を Agent に渡して再実装 → 再レビュー（最大1回リトライ）
- **NEEDS FIX が headless モードで出た場合**: ユーザーにレビュー結果を出力し処理を中断（ユーザーが次のアクションを判断）
- **team-config.md のセクション構造変更**: 既存の「スポーンプロンプト（レビュー時）」を「スポーンプロンプト（計画レビュー時）」に改名し、「スポーンプロンプト（コードレビュー時）」を新規追加。ただし Security と Architect の2ロール分のみ（Performance と Pragmatist は YAGNI）
- **参照整合性の維持**: スポーンプロンプトのセクション名改名に伴い、team-cycle の review-flow.md および team-plan の planning-flow.md 内で team-config.md のスポーンプロンプトを参照している箇所を確認し、必要に応じて更新する
- **フレーミングテーブルを team-config.md に追加**:
  ```
  | コンテキスト | Security | Performance | Architect | Pragmatist |
  |-------------|----------|-------------|-----------|------------|
  | team-plan   | 助言者   | 助言者      | 助言者    | 助言者     |
  | team-cycle (計画レビュー) | 批判者 | 批判者 | 批判者 | 批判者 |
  | team-cycle (コードレビュー) | 検証者 | - | 検証者 | - |
  ```

### Step 4: メタレビュー（工数: 中、効果: 中）

#### Files to Change

```
skills/team-plan/references/planning-flow.md - Step 5（メタレビュー）を条件付きで追加
skills/team-cycle/references/review-flow.md - Step 5（メタレビュー）を条件付きで追加
```

#### Key Points

- **条件付き実行**: 議論の合意形成時に BLOCK が1つでもあった場合のみ自動発火。問題がなければスキップ
- **メタレビューは最大1回**: 無限ループ防止。メタレビューで新たな BLOCK が出ても Lead が最終判断
- **クロスカッティングリスクの検出**: 複数提案の組み合わせで発生するリスクを明示的にチェック（例: Performance の並列化提案が Security の入力検証をバイパスする経路を作る）
- **入力は差分のみ**: 合意結果の修正差分 + 合意サマリーを送信。計画全文の再送は禁止（トークン節約）
- **対象メンバー**: BLOCK/WARN を出したメンバーのみに修正確認を求める（全員に再送しない）
- **ロジックの重複回避**: planning-flow.md と review-flow.md の両方にメタレビュー手順を追加するが、メタレビューの条件判定・ラウンド制限・入力制限のルールは severity-and-verdicts.md の「メタレビュー規則」セクションに一元化し、各フローからは参照のみとする

### Step 5: ユーザーコメント → チーム再議論（工数: 大、効果: 中）

#### Files to Change

```
skills/team-cycle/SKILL.md - --interactive フラグと議論後のユーザーコメント受付フローを追加
skills/team-cycle/references/review-flow.md - ユーザーフィードバックポイントの手順を追加
commands/team-cycle.md - --interactive オプションの説明を追加
```

#### Key Points

- **デフォルト: headless**（既存動作を維持）。`--interactive` フラグでオプトイン
- **フィードバックポイント**: Phase 1 合意後（実装前）の1箇所のみ。実装後にも入れたくなるが、2箇所は複雑すぎる
- **TeamDelete タイミング**: `--interactive` 時は合意形成直後ではなく、ユーザーコメント受付後にずらす
- **ユーザー入力受付メカニズム**: レビュー結果を表示した後、ユーザーに直接質問する形で入力を求める（Claude Code の通常の対話フロー）。ユーザーが「続行」「OK」「問題なし」等と入力した場合は続行、それ以外のテキストはコメントとして扱う
- **ユーザーコメント受付フォーマット**:
  ```
  ══════════════════════════════════════
  TEAM REVIEW COMPLETE — Awaiting Your Input
  Verdict: {verdict}

  議論結果を確認してください。
  コメントがあれば入力してください（チームが再議論します）。
  問題なければ「続行」と入力してください。
  ══════════════════════════════════════
  ```
- **コメント時の再議論**: ユーザーコメントを全メンバーに SendMessage → 各メンバーが意見を Lead に報告 → Lead が合意更新。最大1ラウンド
- **Lead の判定ロジック**: コメント内容に応じて対応を分岐
  - 軽微（スタイル、命名等）: Lead が単独で計画修正（チーム不要）
  - 専門的（セキュリティ懸念等）: 該当1名のみに意見を求める
  - 根本的（設計変更）: フルメンバー再議論（最大1回）

## Tests

- [ ] 途中経過サマリーが各ラウンドで出力されることを手動確認
- [ ] 早期収束条件で不要なラウンドがスキップされることを確認
- [ ] コードレビューで Agent 2本が並行実行され、結果が統合されることを確認
- [ ] NEEDS FIX 判定時に再実装→再レビューのリトライが1回で止まることを確認
- [ ] headless モードで NEEDS FIX 時にユーザー通知＋処理中断されることを確認
- [ ] --interactive フラグでユーザーコメント受付が有効になることを確認
- [ ] メタレビューが BLOCK 発生時のみ発火することを確認
- [ ] severity-and-verdicts.md の判定基準が全フローで一貫していることを確認

## Security

- [ ] コードレビュー時に `git diff` 出力から認証情報・シークレットが検出されないこと
- [ ] `.claude/tmp/` 配下の一時ファイルが議論完了後にクリーンアップされること
- [ ] コードレビュー用 Security フレーミングに入力検証・エラーハンドリング・情報露出のチェック項目を含めること

## Progress

| Step | Status | 依存 |
|------|--------|------|
| Step 2: 判定基準・重大度定義の共通化 | Done | なし（最初に実装） |
| Step 1: 途中経過の可視化 + ラウンド数増加 | Pending | Step 2 |
| Step 3: 実装後コードレビュー | Pending | Step 2 |
| Step 4: メタレビュー | Pending | Step 2 |
| Step 5: ユーザーコメント → チーム再議論 | Pending | なし |

**Legend:** Pending / In Progress / Done

---

## Team Planning Results

**Planned:** 2026-03-23 18:55
**Team:** Security Advisor, Performance Advisor, Architect, Pragmatist

### Discussion Rounds: 2 (early convergence at Round 2)

### Key Agreements
- ラウンド数 2→3（早期収束条件付き）、可視化は Lead のサマリー出力で実現
- コードレビューは Agent 2本並行（Security + Architect）。TeamCreate 不要
- headless をデフォルト維持。`--interactive` でオプトイン
- 個別 flow.md を維持しつつ、判定基準・重大度定義のみ shared に切り出し
- team-config.md にコードレビュー用フレーミング（検証者）を追加（将来の TeamCreate 昇格の土台）
- フレーミングは Security + Architect の2ロールのみ追加（Performance/Pragmatist は YAGNI）

### Discussion Highlights
- **コードレビュー方式**: Architect が当初 TeamCreate を推奨 → 「コードレビューは計画レビューと性質が異なり、メンバー間議論より独立検証が重要」との他3名の論拠に転向
- **デフォルトモード**: Architect が interactive デフォルトを推奨 → 「既存動作の破壊は避けるべき（最小驚きの原則）」「Open-Closed Principle」の論拠で headless に転向
- **フロー共通化**: Architect がテンプレート新設を推奨 → 「LLM にとって自己完結ドキュメントの方が処理しやすい」「3フローの実際の共通部分が少ない」の論拠で、判定基準の切り出し + 共通原則追記の折衷案に合意

### Member Contributions
- **Security Advisor**: 実装後コードレビューの重要性を最優先に位置づけ。コードレビュー用チェック項目（認証情報漏洩、入力検証実装漏れ、情報露出）を具体化。判定基準・重大度定義の shared 切り出しを提案
- **Performance Advisor**: コンテキストコストの定量見積もり（Agent spawn: 3,000-5,000トークン/回、1ラウンド: 約4,000トークン）。team-config.md の肥大化リスクを指摘。共通原則の team-config.md 追記を提案
- **Architect**: フレーミングテーブル設計、code-review-flow.md の新設提案、TeamDelete タイミングの設計。議論フロー共通化を「設計ガイドライン」に縮小する修正案。severity-and-verdicts.md の具体的な構成案
- **Pragmatist**: YAGNI の視点で過剰設計を牽制（ラウンド4以上、全員コードレビュー、独立スキル化を却下）。コードレビュー用フレーミングは Security + Architect の2ロールのみで十分と指摘

---

**Next:** Write tests / Implement / Commit with `claude-skills:commit`
