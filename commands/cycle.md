---
description: "計画の refine → implement を全自動で回す（寝てる間に完了するやつ）"
---

実装計画に対して refine → auto-implement の全サイクルを自律実行する。
各フェーズは Agent で委譲し、メインコンテキストには進捗サマリーのみ保持する。

## パラメータ

- `$ARGUMENTS` の最初の引数: 計画ファイルパス（省略時は `docs/cycles/` 内の最新を自動選択）
- `$ARGUMENTS` に数値があれば refine の最大イテレーション数（デフォルト: 4）

## Phase 0: 準備

1. 計画ファイルを特定する
   - 引数にパスがあればそれを使用
   - なければ: `ls -t docs/cycles/*.md 2>/dev/null | head -1`
1.5. パスを検証する
   - 計画ファイルのパスが `docs/cycles/` 配下であることを確認する
   - パスが `docs/cycles/*.md` に一致しない場合:
     ```
     ⛔ CYCLE ABORTED: Plan file is not in docs/cycles/
     Found: {actual_path}
     Expected: docs/cycles/*.md

     Plan files must be located in docs/cycles/.
     If the file was created in the wrong location, move it first:
       mv {actual_path} docs/cycles/
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
   - プロンプト: 「Skill ツールで `plan-refine` を実行してください。対象: {plan_file_path}。最大イテレーション: {max_iterations}。全観点 PASS になるまでループしてください。完了したら最終的な各観点のスコアと判定を報告してください。」
2. 結果を受け取る
3. **判定**:
   - 全 PASS → Phase 2 へ
   - BLOCK が残存 → サイクル中断。残存 BLOCK 一覧を表示して終了
   - WARN のみ残存 → 警告を表示し Phase 2 へ進む

表示:
```
── Phase 1: Refine ── {PASS|WARN|BLOCK}
Iterations: {N}
{各観点のスコアサマリー（1行ずつ）}
```

## Phase 2: Implement（自動実装）

1. Agent ツール（general-purpose）で実装エージェントを起動する:
   - プロンプト: 「Skill ツールで `plan-implement` を実行してください。計画ファイル {plan_file_path} の全ステップを実装してください。各ステップ完了ごとにコミットし、ステータスを更新してください。完了したら実装サマリー（変更ファイル数、テスト数、コミット数）を報告してください。」
2. 結果を受け取る

表示:
```
── Phase 2: Implement ── DONE
Files changed: {N}
Tests added: {N}
Commits: {N}
```

## Phase 3: サマリー生成

1. `git log` で Phase 2 のコミット一覧を取得する
2. サマリーファイルを生成: `docs/cycles/results/{plan_basename}_result.md` に出力（ディレクトリがなければ `mkdir -p` で作成）

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

4. **Issue 自動 close**: 計画ファイルを読み、`**Issue:**` 行が存在するか確認する
   - `**Issue:**` 行がある場合: issue slug を抽出し、Skill ツールで `issue` を `close {slug}` 引数で実行する
     - close が失敗した場合は警告メッセージを表示するのみで、cycle 自体は成功扱いとする（close 失敗で実装結果を巻き戻さない）
   - `**Issue:**` 行がない場合: このステップをスキップする

5. 最終表示:
```
══════════════════════════════════════
CYCLE COMPLETE
Feature: {feature_name}
Refine: {verdict} ({iterations} rounds)
Implement: {steps_done}/{steps_total} steps
Commits: {N}
Result: {result_file_path}
══════════════════════════════════════
```

## エラーハンドリング

- **Phase 1 で BLOCK 残存**: サイクルを中断し、BLOCK 一覧を表示して終了。
- **Phase 2 で実装エージェントがエラー**: エラー内容を表示し、どのステップまで完了したかを記録してサイクルを中断する。

## 重要なルール

- **各フェーズは Agent に委譲する**。メインコンテキストにはサマリーのみ保持する。
- **Phase 1 の BLOCK は絶対に無視しない**。BLOCK が残っていたら実装に進まない。
- **ユーザーへの確認プロンプトは出さない**（ヘッドレス実行対応）。
