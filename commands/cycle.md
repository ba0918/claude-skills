---
description: "計画の refine → implement を全自動で回す（寝てる間に完了するやつ）"
---

実装計画に対して refine → auto-implement の全サイクルを自律実行する。
各フェーズは Agent で委譲し、メインコンテキストには進捗サマリーのみ保持する。

## パラメータ

- `$ARGUMENTS` の最初の引数: 計画ファイルパス（省略時は `docs/plans/` 内の最新を自動選択）
- `$ARGUMENTS` に数値があれば refine の最大イテレーション数（デフォルト: 4）

## Phase 0: 準備

1. 計画ファイルを特定する
   - 引数にパスがあればそれを使用
   - なければ: `ls -t docs/plans/*.md 2>/dev/null | head -1`
1.5. パスを検証する
   - 計画ファイルのパスが `docs/plans/` 配下であることを確認する
   - パスが `docs/plans/*.md` に一致しない場合:
     ```
     ⛔ CYCLE ABORTED: Plan file is not in docs/plans/
     Found: {actual_path}
     Expected: docs/plans/*.md

     Plan files must be located in docs/plans/.
     If the file was created in the wrong location, move it first:
       mv {actual_path} docs/plans/
     ```
     サイクルを中断する
2. 計画ファイルを読み込み、概要を把握する（Feature名、ステップ数、現在の進捗）
3. サイクル開始を表示:
   ```
   ══════════════════════════════════════
   CYCLE START
   Plan: {plan_file_path}
   Feature: {feature_name}
   Steps: {step_count}
   ══════════════════════════════════════
   ```

## Phase 1: Refine（計画品質ゲート）

1. Agent ツール（general-purpose）で refine エージェントを起動する:
   - プロンプト: 「Skill ツールで `claude-skills:plan-refine` を実行してください。対象: {plan_file_path}。最大イテレーション: {max_iterations}。全観点 PASS になるまでループしてください。完了したら最終的な各観点のスコアと判定を報告してください。**各イテレーションの総合スコアも報告してください（累積停滞検知に使用）。**」
2. 結果を受け取る
   - **Agent がエラーを返した場合**: 1回だけ自動リトライする。リトライも失敗した場合はサイクルを中断する
     ```
     ⚠️ Phase 1 agent failed — retrying (1/1)...
     ```
3. **判定**:
   - 全 PASS → Phase 2 へ
   - BLOCK が残存 → **Phase 1.5（フォールバック）** へ
   - WARN のみ残存 → 警告を表示し Phase 2 へ進む

表示:
```
── Phase 1: Refine ── {PASS|WARN|BLOCK}
Iterations: {N}
{各観点のスコアサマリー（1行ずつ）}
```

## Phase 1.5: BLOCK フォールバック（自動修正）

**Phase 1 で BLOCK が残存した場合のみ実行する。このフェーズは最大1回のみ。**

1. 残存 BLOCK の内容を分析する
2. Agent ツール（general-purpose）で修正エージェントを起動する:
   - プロンプト: 「計画ファイル {plan_file_path} に対するレビューで以下の BLOCK が指摘されました。計画ファイルを修正して BLOCK を解消してください。修正後、修正内容のサマリーを報告してください。\n\n残存 BLOCK:\n{block_list}」
3. 修正結果を受け取る
4. **再 refine**: Phase 1 と同じ手順で refine エージェントを再起動する（イテレーション数は残り回数 or 2 の小さい方）
5. **再判定**:
   - 全 PASS or WARN のみ → Phase 2 へ
   - BLOCK が依然として残存 → サイクル中断。残存 BLOCK 一覧を表示して終了

表示:
```
── Phase 1.5: Fallback ── {RESOLVED|UNRESOLVED}
BLOCKs addressed: {N}/{total}
{RESOLVED の場合: Proceeding to Phase 2}
{UNRESOLVED の場合: Cycle aborted — remaining BLOCKs listed above}
```

## Phase 2: Implement（自動実装）

1. Agent ツール（general-purpose）で実装エージェントを起動する:
   - プロンプト: 「Skill ツールで `claude-skills:plan-implement` を実行してください。計画ファイル {plan_file_path} の全ステップを実装してください。実装時は `skills/shared/references/tdd-contract.md` に従いテストファースト（RED → GREEN → REFACTOR）で進めること。完了前は `skills/shared/references/verification-gate.md` の Gate Function を適用し、テスト実行結果のエビデンスを結果ファイルに含めること。各ステップ完了ごとにコミットし、ステータスを更新してください。完了したら実装サマリー（変更ファイル数、テスト数、コミット数）を報告してください。」
2. 結果を受け取る
   - **Agent がエラーを返した場合**: 1回だけ自動リトライする。リトライも失敗した場合はエラー内容を表示し、どのステップまで完了したかを記録してサイクルを中断する
     ```
     ⚠️ Phase 2 agent failed — retrying (1/1)...
     ```

表示:
```
── Phase 2: Implement ── DONE
Files changed: {N}
Tests added: {N}
Commits: {N}
```

## Phase 3: サマリー生成

**Phase 3 の各ステップは独立して実行し、個別のステップが失敗しても残りのステップを続行する。** 失敗したステップは `phase3_failures` リストに記録し、最終表示に含める。

1. `git log` で Phase 2 のコミット一覧を取得する
2. サマリーファイルを生成: `docs/plans/results/{plan_basename}_result.md` に出力（ディレクトリがなければ `mkdir -p` で作成）
   - **失敗時**: `phase3_failures` に `"result file generation"` を追加し、次のステップへ進む

サマリーファイルの内容:
```markdown
# Cycle Result: {feature_name}

**Plan:** {plan_file_path}
**Executed:** {datetime}

## Refine
- Iterations: {N}
- Final verdict: {PASS|WARN}
- {残存 WARN があれば一覧}

## Implementation
- Steps completed: {N}/{total}
- Files changed: {N}
- Tests added: {N}
- Commits: {N}

## Commits
{git log --oneline のコミット一覧}

## Notes
{特記事項があれば}
```

3. status.md を完了状態に更新する:
   - **ガード条件**: `docs/status.md` の Current Session が既に空（`_No active session`）または Completed の場合はこのステップをスキップする
   - `skills/plan/references/status-update-guide.md` の **Case 2（In Progress → Completed）** の手順に従う:
     - Step 2a: session-history.md にアーカイブ
     - Step 2b: Session History セクションをクリア
     - Step 2c: Current Session をクリア
   - **失敗時**: `phase3_failures` に `"status.md update"` を追加し、次のステップへ進む

4. **サイクル成果物をコミット**: result ファイル・status.md・session-history.md・計画ファイルなど、Phase 3 で更新されたファイルをまとめてコミットする
   - Skill ツールで `claude-skills:commit` を実行する
   - コミット対象がなければスキップする
   - **失敗時**: `phase3_failures` に `"commit"` を追加し、次のステップへ進む

5. **Issue 自動 close**: 計画ファイルを読み、`**Issue:**` 行が存在するか確認する
   - `**Issue:**` 行がある場合: issue slug を抽出し、Skill ツールで `claude-skills:issue` を `close {slug}` 引数で実行する
     - close が失敗した場合は警告メッセージを表示するのみで、cycle 自体は成功扱いとする（close 失敗で実装結果を巻き戻さない）
     - **close の成否を記録しておき、Step 6 の最終表示に含める**
   - `**Issue:**` 行がない場合: このステップをスキップする

6. 最終表示:
```
══════════════════════════════════════
CYCLE COMPLETE
Feature: {feature_name}
Refine: {verdict} ({iterations} rounds)
Implement: {steps_done}/{steps_total} steps
Commits: {N}
Result: {result_file_path}
Issue: {closed ✅ / ⚠️ close failed: {slug} — manual close required / (none)}
{phase3_failures が空でない場合:}
⚠️ Phase 3 partial failures: {phase3_failures をカンマ区切りで表示}
──────────────────────────────────────
💡 Need tweaks? Use /iterate for quick fixes and polish.
══════════════════════════════════════
```

## エラーハンドリング

- **Phase 1 で BLOCK 残存**: Phase 1.5（フォールバック）を1回試行する。フォールバック後もBLOCK残存ならサイクルを中断し、BLOCK 一覧を表示して終了。
- **Phase 1/Phase 2 で Agent がエラー**: 1回自動リトライする。リトライも失敗した場合はサイクルを中断する。
- **Phase 3 の各ステップでエラー**: 失敗ステップを `phase3_failures` リストに記録し、残りのステップを続行する。Phase 3 のエラーで cycle 全体を失敗にしない。

## Codex セカンドオピニオン

Phase 1（Refine）で使用される plan-reviewer には Codex セカンドオピニオンが自動的に含まれます。
Claude の 7 次元レビューに加え、Codex による包括的な第三者視点が並行で取得されます。
Codex が利用不可能な場合は既存の 7 次元レビューのみで続行します（graceful degradation）。

## 重要なルール

- **各フェーズは Agent に委譲する**。メインコンテキストにはサマリーのみ保持する。
- **Phase 1 の BLOCK は絶対に無視しない**。BLOCK が残っていたら Phase 1.5 でフォールバックを試み、それでも解消しなければ実装に進まない。
- **ユーザーへの確認プロンプトは出さない**（ヘッドレス実行対応）。
- **Agent エラー時は1回リトライする**。リトライ後も失敗なら中断する。2回以上のリトライは行わない。
- **Phase 3 は部分成功を許容する**。個別ステップの失敗がcycle全体を巻き戻さない。
- 問題の根本原因が不明な場合は、cycle 実行前に `/claude-skills:investigate` で読み取り専用の事前調査を推奨する。
