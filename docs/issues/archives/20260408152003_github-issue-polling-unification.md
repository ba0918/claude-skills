---
title: github-issue を共通 polling 契約に揃えるリファクタ
status: open
created: 2026-04-08 15:20:03
tags: refactor, polling-pattern, github-issue
source: docs/plans/20260408150529_polling-pattern-unification.md
---

## 概要

`docs/plans/20260408150529_polling-pattern-unification.md` の Phase A（local issue 側の polling + 共通契約策定）から切り出された Phase B スコープ。

Phase A で確立した `skills/shared/references/polling-pattern.md` の共通契約に `skills/github-issue/` を準拠させるリファクタを行う。本 issue は team review (APPROVED WITH CONCERNS) における Pragmatist の BLOCK を解消するために、元 plan からスコープを切り出したもの。

## 備考

### Phase B のスコープ

1. **`skills/github-issue/SKILL.md` の共通契約参照化**
   - 重複する状態機械 / 安全ブレーキ / tick 仕様を共通契約 `skills/shared/references/polling-pattern.md` への直リンクに置換
   - 固有部分（label adapter / Codex gate / fail-closed merge）のみ残す
   - drift 防止規約（契約 §11）に準拠

2. **Label 二分割**
   - 既存 `claude-failed` を `claude-failed-transient` / `claude-failed-permanent` に分割
   - `classify_failure` 純関数との整合を取る
   - 既存ラベル付き issue に対する後方互換戦略（マイグレーション or 手動移行）を決定

3. **`skills/github-issue/references/` 整理**
   - `label-spec.md`: failed ラベル二分割を反映
   - `codex-review-loop.md`: failed 分類ロジックに合わせた更新
   - `cleanup-spec.md`: `.STOP` / SIGINT trap の共通仕様部分を削除し共通契約参照へ。`sanitize_repo_slug()` / Partial Claim Rollback は固有として残す
   - `polling-adapter.md` [NEW]: Label adapter として Interface Table の実装を記述

4. **`commands/github-issue-polling.md` フラグ統合**
   - `--once` / `--loop` / `--max-*` / `--dry-run` を issue-polling と揃える

5. **Interface Table 一致の検証**
   - FS adapter（Phase A）と Label adapter（Phase B）が同じ Interface Table を満たすことを目視確認

### 前提

- Phase A の共通契約 `skills/shared/references/polling-pattern.md` が既に確立済み
- Phase A の純関数仕様（`transition` / `classify_failure` / `should_promote_to_permanent` / `month_boundary_crossed`）をそのまま利用

### 想定される困難

- 既存 `github-issue` 利用者への後方互換: ラベル rename は破壊的変更のため、移行手順と plugin.json major/minor bump 方針の決定が必要
- `bypass-permissions` でのラルフループ運用検証は、FS adapter と Label adapter が揃ってから別途実施

### Acceptance Criteria

- [ ] `skills/github-issue/SKILL.md` が共通契約 §2 / §3 / §4 / §6 / §7 を直リンク参照のみで表現している
- [ ] `label-spec.md` の failed ラベルが `transient` / `permanent` に分割されている
- [ ] `cleanup-spec.md` から `.STOP` / SIGINT trap 共通仕様の重複が削除されている
- [ ] `polling-adapter.md` [NEW] が Interface Table の Label 実装を網羅している
- [ ] `commands/github-issue-polling.md` のフラグが issue-polling と一致している
- [ ] Phase A の純関数仕様を Label adapter が正しく呼ぶように記述されている
- [ ] **後方互換戦略**: 旧 `claude-failed` ラベルを `claude-failed-permanent` への alias として一定期間（最低 1 minor リリース）維持し、読み込み時は新旧両方のラベル名を許容する
- [ ] **dual-write 戦略**: migration window 中は書き込み時に `claude-failed` と `claude-failed-permanent` の両方を付与する（one-way 互換では旧 reader が新 failure を silently miss するリスクを回避）。alias 維持期間終了後に別 cycle で dual-write を廃止し新ラベル単独書き込みに移行する
- [ ] **plugin.json bump 方針**: ラベル alias による後方互換を維持するため **minor bump で可**（major bump は alias 廃止時に行う）。alias 廃止のタイミングは別途 issue で告知

---

> **Note:** Do not include sensitive information (passwords, tokens, personal data, etc.) in this file.
