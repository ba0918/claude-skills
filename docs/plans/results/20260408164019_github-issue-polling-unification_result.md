# Cycle Result: github-issue Polling Contract Unification (Phase B)

**Plan:** [docs/plans/20260408164019_github-issue-polling-unification.md](../20260408164019_github-issue-polling-unification.md)
**Executed:** 2026-04-08
**Mode:** AgenticTeam Review (team-cycle)
**Issue:** 20260408152003_github-issue-polling-unification

## Team Review

- **Verdict:** APPROVED WITH CONCERNS
- **Reviewers:** 4/4 (Security / Performance / Architect / Pragmatist)
- **Discussion rounds:** 1 (early convergence — 全論点 WARN 以下)
- **Issues resolved:** 16 WARN/INFO (Round 4 修正 #33〜#48)
- **Remaining concerns:** 0

### Review Highlights

- BLOCK 指摘はゼロ。Round 1〜3 の精緻化が効いており、Round 4 は全論点 WARN 以下で早期収束
- **Security の主要指摘**: `normalize_git_url` パスインジェクション対策、`.clone_url` TOCTOU 回避、`rollback_orphans` 7 日 hard cap（updated_at ベース DoS 排除）
- **Architect の主要指摘**: Label Mapping SSOT を `polling-adapter.md` に一本化（plan archive 後の長期保守性確保）、`sanitize_*` 責務分離の DRY 遵守、`transition()` 擬似コード残存チェック追加
- **Performance の主要指摘**: `error_kind = "lock"` を `failed_streak` 非カウント（誤 brake 防止）、Corrupt retry JSON `.corrupt.{ts}` 隔離、Unsupported FS を warn → fail-closed 格上げ
- **Pragmatist の主要指摘**: `polling-adapter.md` 見出しレベル規約明示（H2/H3）、`cleanup-spec.md` / `config-defaults.md` 現状確認条件分岐追加

## Implementation

- **Steps completed:** 10/10
- **Files changed:** 9 (1 new + 8 modified)
  - **NEW**: `skills/github-issue/references/polling-adapter.md` (572 行、Label adapter 本体)
  - **Modified**: `skills/github-issue/SKILL.md`, `references/label-spec.md`, `references/cleanup-spec.md`, `references/codex-review-loop.md`, `references/config-defaults.md`, `commands/github-issue-polling.md`, `CLAUDE.md`, `.claude-plugin/plugin.json`
- **Tests added:** 20 grep-verified checklist items（machine-verifiable）
- **Commits:** 4

## Code Review

- **Verdict:** PASS WITH NOTES
- **Reviewers:** Security, Architect
- **Findings:** 0 BLOCK, 3 WARN, 7 INFO
- **Resolved:** Architect 3 WARN + Security/Architect 共通の `increment_retry` パス漏れ + INFO 4 件を追加修正コミットで解消
- **Deferred:** Security INFO 2 件（`UNSUPPORTED_FS` マジックナンバー値、fail_closed メッセージ redact）は実装フェーズでの考慮事項として記録

### Code Review 追加修正（Phase 2.5）

- SKILL.md Polling Step 11: `increment_retry` + `should_promote_to_permanent` 分岐を明示（共通契約 §5 準拠）
- SKILL.md Polling Step 12: TickResult に `run_id` / `tick_started_at` を追加（共通契約 §7 の 7 フィールド不変契約）
- SKILL.md Polling Step 8: `authorAssociation` フィルタ責務を `list_ready` に一元化
- `polling-adapter.md §list_ready`: early termination 要件（共通契約 §3）の充足根拠を明示
- `polling-adapter.md §retry_count`: `run_id` UUID v4 正規表現を厳密化、`retry_count` 型/範囲検証、`last_failed_at` ISO8601 検証追記
- `config-defaults.md`: `polling_interval` と `tick_interval_loop_mode` が別概念であることを明示

## Commits

```
1963f39 refactor(github-issue): address Phase 2.5 code review WARN/INFO
00cea7c chore(release): bump to 1.14.0 for github-issue Phase B
d2afd8c refactor(github-issue): rewrite SKILL Polling Workflow as thin adapter orchestrator
3408d50 refactor(github-issue): conform references to shared polling-pattern contract (Phase B)
```

## Notes

- **markdown-only リファクタ**: 仕様ドキュメントの再編成のみでコード実装はゼロ。TDD サイクルは不要で grep ベースの 20 項目検証で代替
- **Phase A invariant 完全遵守**: `skills/shared/references/polling-pattern.md` と `skills/issue/` は一切変更していない（Drift 防止 §11）
- **Plugin version**: 1.13.0 → 1.14.0 (minor bump)
- **Downgrade 非対応**: 1.14.0 以降から 1.13.x への downgrade は silent data loss リスクのため非対応（plugin.json release notes + label-spec.md に明記）
- **alias 廃止 exit strategy**: 1.14.0 導入 → 1.14.x 監視 → 1.15.0 告知 → 1.16.0 廃止の 4 段階
- **Label adapter として共通契約準拠**: FS adapter (Phase A `skills/issue/`) と Label adapter (Phase B `skills/github-issue/`) の 2 実装が共通契約 `polling-pattern.md` に準拠する構造が完成
