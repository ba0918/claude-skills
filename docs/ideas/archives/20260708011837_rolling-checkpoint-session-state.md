# rolling-checkpoint — 長生きセッションの実行状態復元（自動 handoff の再設計）

**Created:** 2026-07-08 01:18:37
**Status:** 📋 Planned
**Tags:** checkpoint, handoff, plan, session-continuity, loop-engineering

---

## Summary

plan 再読込では埋まらない「実行状態の細部」を、plan サイドカーの最新 1 ブロック checkpoint（未コミット dirty 状態 + 逸脱判断 + 次の一手のみ所有）で復元する仕組み。書くのは dirty のまま終わる者だけ、消すのは HEAD の前進（自然失効）、restore は trust-but-verify の 5 分類判定。

## Key Discussion Points

- **痛点の正体**: plan 再読込は「意図と手順」を復元するが「実行状態の細部」（どこまでやったか・途中の判断・今どこにいるか）を復元できず、作業内容の全再投入コストが毎回発生する。状態が始点（plan）と終点（result）でしか記録されず「途中」が無いのが原因
- **ループ本体には不要**: polling `--stateless` / cycle の Agent 委譲は「状態はファイル、会話履歴に依存しない」設計で、キュー + 状態ファイルが handoff の上位互換。会話ベース handoff を足すのは退化。問題は長生きセッション（cycle オーケストレータ / 長い実装 agent / goal-loop コントローラ / 手動対話）に限定される
- **append-only journal 案は却下**: 末尾だけ読むと撤回・方針転換を見落とし、全部読むと再投入コストに逆戻り。痛点は履歴保存ではなく「現在地に戻るコスト」→ 最新 1 ブロックの rolling checkpoint が正解
- **checkpoint = 例外記録**: 成功時はコミットが完璧な記録（git log が ground truth の journal）。checkpoint が必要なのは「未コミットの仕掛かり」がある瞬間だけ。checkpoint の肥大化は「コミットをサボってる」ことのセンサーにもなる。理想状態では checkpoint はほぼ空
- **所有境界の厳格化**: checkpoint が所有するのは既存資産の誰も記録しない 4 つのみ — 未コミット dirty 状態 / plan からの逸脱判断（1 文）/ 検証エビデンス（過去観測）/ 次の一手（1 個）。工程ステータス（plan Progress）・セッション状態（status.md）・事後サマリー（result）とは重複させない。禁止事項（完了済みステップ一覧・最終結果・長いテストログ）を v1 から明文化
- **PreCompact hook 単独は遅い**: 圧迫時点で低劣化な状態は失われている。本命トリガーはフェーズ境界・コミット直前・検証直後（既存の規律ポイント）。PreCompact は「dirty set と HEAD を失わない」だけの degraded 保険に格下げ

## Decisions & Conclusions

- **書く責任は agent の善意ではなくワークフローの出口条件**: 「dirty（`git status --porcelain` 非空）のまま作業を終える時だけ」書く。ステップ開始時の intent 記録は却下（実 dirty とズレる）。成功時は書かない
- **ハイブリッド生成**: 機械的フィールド（dirty set・fingerprint）はスクリプトが git から骨格生成、叙述（decision / next）だけ LLM が 1 文ずつ埋める。checkpoint ファイル自身は dirty set から除外（自己ノイズ防止）
- **supersede は hook ではなく自然失効**: `base_head`（書いた時の HEAD）+ `dirty_fingerprint`（git status + diff --stat の hash）を必須フィールドにし、restore 時に現在値と照合して失効判定。goal-loop のハッシュロックと同思想
- **restore 5 分類を先に設計**（書き手より restore が本体）: valid（全一致・叙述も信用可）/ stale（dirty 変化 → diff から再構成）/ superseded（HEAD 前進 → 破棄）/ degraded（PreCompact 産 → dirty set と HEAD 以外信用しない）/ conflict（複数書き手 → 人間照会）
- **evidence と verify_on_restore を構造分離**: evidence = 過去に観測した事実、verify_on_restore = 再実行必須コマンド。古いテスト結果が復元後に成功証拠として誤用される verification-gate 違反を構造で防ぐ
- **フォーマット**: YAML frontmatter + 固定キー短文（自由文 md は stale 判定が機械化できない）。`owner: manual-session | cycle-phase2 | precompact` で復元時の信用度を変える
- **置き場**: `docs/plans/checkpoints/{cycle_id}.md`（plan 1 つに 1 ファイル、上書き運用）。status.md の Current Session からリンク（人間向け）+ plan resume / handoff restore が必ず読む（ワークフロー側の規律が本体）
- **v1 スコープ**: hook なし・スキル規律のみ — ①フォーマット固定 ②plan resume / handoff restore に checkpoint 読込 + 5 分類判定を統合 ③出口条件の dirty 判定を plan / handoff スキルに追加。PreCompact / PostToolUse hook・plan 不在の手動作業（_workspace fallback）・parallel-cycle 対応は全部 v2
- **degraded 版の構造**: `mode: degraded / decision: unknown / next: reconstruct_from_diff` を明示し、git status の羅列が判断記録に見える誤読を遮断

## Open Questions

- checkpoint 書き込みを計測に乗せるか（events.jsonl の event enum は tick/verification/eval に閉じており、`checkpoint_written` を足すには measurement-identity の契約改訂が必要）
- handoff スキルとの最終的な関係: restore のフォールバック統合（最新 handoff がなければ active plan の checkpoint を読む）の具体形
- cycle Phase 2 agent への組込方法: 失敗・中断時の checkpoint 書き出しを plan-implement 側とオーケストレータ側のどちらの責務にするか（Codex 推奨はオーケストレータが git ground truth から作る方）
- Codex 版スキルへの展開要否

## Next Steps

- plan 化する場合: `/claude-skills:brainstorm-plan` で変換（checkpoint フォーマット + 照合スクリプト（純関数 + unittest）→ plan / handoff スキルへの規律統合 → E2E（手動セッションで dirty 中断 → restore）の順が自然）
- 実装前に既存 handoff スキルの restore フローと plan resume フローの現行仕様を精読して統合点を確定する
