---
name: cycle
description: 実装計画に対して refine（計画品質ゲート）と implement（TDD 自動実装）をサブエージェント委譲で自律実行し、最後にメインコンテキストでサマリー生成・ステータス更新・コミットまで行う。ユーザー確認なしのヘッドレス実行に対応。「cycle」「サイクル回して」「計画を自動実装して」「全自動で実装」で起動。
---

# Cycle

Artifact paths follow the [Agent Artifact Store contract](../shared/references/artifact-store.md). Resolve and validate the store before reading or writing artifacts.

実装計画に対して refine → auto-implement の全サイクルを自律実行する。
各フェーズはサブエージェントに委譲し、メインコンテキストには進捗サマリーのみ保持する。

サブエージェントや他スキルを起動できない環境では、各フェーズの内容を自分がインラインで実行してよい。
その場合、refine は plan-refine の手順に、実装は plan-implement の手順に従う（それぞれのフォールバック規定を含む）。

## パラメータ

- 引数の最初のパス: 計画ファイルパス（省略時は `.agents/artifacts/plans/` 内の最新を自動選択）
- 引数に数値があれば refine の最大イテレーション数（デフォルト: 4）

## Phase 0: 準備

1. 計画ファイルを特定する
   - 引数にパスがあればそれを使用
   - なければ自動選択する: `.agents/artifacts/plans/` 直下の `*.md` をファイル名のタイムスタンプ降順で並べ、先頭から順に見て **未完了の計画**（Status が ✅/Completed でないもの）を選ぶ。mtime（`ls -t`）は使わない — ファイル名タイムスタンプが正で、mtime は編集で入れ替わるため
   - 未完了の計画が 1 つもない場合: 「実装対象の計画がない」と表示してサイクルを中断する（完了済み計画で no-op サイクルを回さない）
1.5. パスを検証する
   - 計画ファイルが `.agents/artifacts/plans/` **直下**の `.md` ファイルであることを確認する（サブディレクトリは対象外）
   - 一致しない場合:
     ```
     ⛔ CYCLE ABORTED: Plan file is not in .agents/artifacts/plans/
     Found: {actual_path}
     Expected: .agents/artifacts/plans/*.md

     Plan files must be located in .agents/artifacts/plans/.
     If the file was created in the wrong location, move it first:
       mv {actual_path} .agents/artifacts/plans/
     ```
     サイクルを中断する。mv はユーザーに提示する案内であり、**実行者自身がファイルを移動して続行してはならない**。
     なお `docs/plans/` 等のレガシー配置からの移行は [Agent Artifact Store contract](../shared/references/artifact-store.md) の migration 手順の対象になりうるため、単純 mv の案内は「新規作成ファイルの置き場違い」を想定した簡易復旧である旨を添えてよい
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

## 委譲結果の受渡し（Phase 1 / 1.5 / 2 共通）

Phase 1 / 1.5 / 2 のサブエージェント委譲は [orchestration-patterns.md](../shared/references/orchestration-patterns.md) の
「委譲結果のファイル受渡し（delegation result relay）」に従う。完了報告メッセージの配達は非決定的で、
委譲先が作業を完遂したのに報告が届かず待機通知だけが来る停滞が実測されているため、**結果の正本は
ファイル、報告メッセージは通知**として扱う。要点:

- **`{run_id}`**: 本サイクルの識別子。計画ファイル冒頭の Cycle ID（なければ計画ファイル名の
  タイムスタンプ）を使う。オーケストレーターと委譲先が同じパスを導出できることが要件
- **委譲プロンプトに結果ファイルパスを必ず含める**: 委譲先は完了報告を送る**前に**結果全文を
  `.agents/runtime/delegation/{run_id}_{role}.md` へ書く（`{role}` は各 Phase で指定）。報告は
  「書いた」ことの通知にすぎない
- **受信手順**: (a) 委譲先の完了報告 (b) 委譲先の停止・待機通知 のどちらをトリガーにしても結果
  ファイルを読む。待機通知だけが来て報告が来ない場合も、即座に結果ファイルを検分する
- **フォールバック（必須）**: 結果ファイルが欠落・不完全なときは成果物（コミット履歴・変更ファイル・
  テスト結果・計画の Progress）を直接検分して完了・欠落を判定する。判定不能のときに限りリトライする
- **掃除**: 読了後に結果ファイルを削除する

## Phase 1: Refine（計画品質ゲート）

1. サブエージェント（高性能モデル）で refine エージェントを起動する:
   - プロンプト: 「スキル `claude-skills:plan-refine` を実行してください。対象: {plan_file_path}。最大イテレーション: {max_iterations}。全観点 PASS になるまでループしてください。**完了報告を送る前に**、最終的な各観点のスコアと判定・各イテレーションの総合スコア（累積停滞検知に使用）を含む結果全文を `.agents/runtime/delegation/{run_id}_refine.md` へ書き出してください。報告メッセージはそのファイルを書いた通知にすぎません。」
2. 結果を受け取る（上記「委譲結果の受渡し」に従う）
   - refine の完了報告 **または** 停止・待機通知のどちらかを受信したら、`.agents/runtime/delegation/{run_id}_refine.md` を読んで各観点のスコア・判定・累積スコアを取得する
   - 結果ファイルが欠落・不完全な場合: 計画ファイル本文（refine が編集する対象）と Git 差分を直接検分し、PASS/WARN/BLOCK を判定する
   - **サブエージェントがエラーを返した、または結果ファイルも成果物検分も判定不能な場合**: 1回だけ自動リトライする。リトライも失敗した場合はサイクルを中断する
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
2. サブエージェント（高性能モデル）で修正エージェントを起動する:
   - プロンプト: 「計画ファイル {plan_file_path} に対するレビューで以下の BLOCK が指摘されました。計画ファイルを修正して BLOCK を解消してください。**修正内容のサマリーは、完了報告を送る前に `.agents/runtime/delegation/{run_id}_refine-fix.md` へ書き出してください**（報告はそのファイルを書いた通知にすぎません）。\n\n残存 BLOCK:\n{block_list}」
3. 修正結果を受け取る（上記「委譲結果の受渡し」に従う）
   - 完了報告 **または** 停止・待機通知を受信したら `.agents/runtime/delegation/{run_id}_refine-fix.md` を読む。欠落・不完全なら計画ファイルの当該 BLOCK 箇所と Git 差分を直接検分して修正の有無を確認する
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

1. サブエージェント（高性能モデル）で実装エージェントを起動する:
   - プロンプト: 「スキル `claude-skills:plan-implement` を実行してください。計画ファイル {plan_file_path} の全ステップを実装してください。実装時は `skills/shared/references/tdd-contract.md` に従いテストファースト（RED → GREEN → REFACTOR）で進めること。完了前は `skills/shared/references/verification-gate.md` の Gate Function を適用すること。**完了報告を送る前に**、実装サマリー（変更ファイル数、テスト数、コミット数、ステップごとの完了状況）とテスト実行結果のエビデンスを含む結果全文を結果ファイル `.agents/runtime/delegation/{run_id}_implement.md` へ書き出してください（報告はそのファイルを書いた通知にすぎません）。各ステップ完了ごとにコミットし、ステータスを更新してください。」
2. 結果を受け取る（上記「委譲結果の受渡し」に従う）
   - 完了報告 **または** 停止・待機通知のどちらかを受信したら、`.agents/runtime/delegation/{run_id}_implement.md` を読んで実装サマリー・テストエビデンス・ステップ完了状況を取得する
   - 結果ファイルが欠落・不完全な場合: `git log` のコミット履歴・変更ファイル・計画ファイルの Progress を直接検分し、どのステップまで完了したかを判定する
   - **サブエージェントがエラーを返した、または結果ファイルも成果物検分も判定不能な場合**: 1回だけ自動リトライする。リトライも失敗した場合はエラー内容を表示し、どのステップまで完了したかを記録してサイクルを中断する
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

`Files changed` はプロダクションコードとテストの変更ファイル数（計画・status 等のメタ更新は含めない）。

## Phase 3: サマリー生成

**Phase 3 の実行主体**: メインコンテキストで直接実行する。Phase 1 / 1.5 / 2 と異なり **サブエージェントには委譲しない**（成果物生成・status 管理・commit はメインが一貫して責任を持つため）。

**Phase 3 の各ステップは独立して実行し、個別のステップが失敗しても残りのステップを続行する。** 失敗したステップは `phase3_failures` リストに記録し、最終表示に含める。

**Failure 判定の一般ルール**: ガード条件（スキップ許容）に該当せず、かつステップが完遂できない状態（例: 必要なファイル / セクションが見つからない、parse 不能、ツールが予期せぬエラーを返した）は全て failure として `phase3_failures` に記録する。ユーザーへの確認や cycle 全体の中断は行わない。

1. `git log` で Phase 2 のコミット一覧を取得する
2. サマリーファイルを生成: `.agents/artifacts/plans/results/{plan_basename}_result.md` に出力（ディレクトリがなければ `mkdir -p` で作成）
   - **失敗時**: `phase3_failures` に `"result file generation"` を追加し、次のステップへ進む

サマリーファイルの内容:
```markdown
# Cycle Result: {feature_name}

Artifact paths follow the Agent Artifact Store contract.

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
- Commits: {N}（Phase 2 の実装コミット数。Phase 3 の成果物コミットは含まない）

## Commits
{git log --oneline のコミット一覧}

## Notes
{特記事項があれば}
```

3. status.md を完了状態に更新する:
   - **Step 3a: Pre-check（failure 判定の先行チェック）**: `.agents/artifacts/status.md` を Read し、Current Session セクションが存在するかを確認する
     - Current Session 見出し自体が存在しない、またはテーブル構造が parse 不能
       → `phase3_failures` に `"status.md update"` を追加して次のステップへ進む（**ガードではなく失敗として扱う**。セッション管理をしていない旧フォーマットの status.md もここに含む — 修復や書き換えはせず、記録だけして続行する）
     - Current Session セクションが存在する → Step 3b へ
   - **Step 3b: ガード条件（いずれかに該当すればスキップ）**:
     - Current Session 本文が `_No active session` で始まる（セクションはあるが未初期化）
     - Current Session テーブルの Status が `Completed`
     - 上記いずれかに該当すれば、何もせず次のステップへ進む（失敗ではない）
   - **Step 3c: 通常処理（ガードに該当しない場合）**: [status-update-guide.md](../plan/references/status-update-guide.md) の **Case 2（In Progress → Completed）** の手順に従う:
     - Step 2a: session-history.md にアーカイブ
     - Step 2b: Session History セクションをクリア
     - Step 2c: Current Session をクリア
   - **Step 3c 実行中の失敗時**（Edit 失敗、ファイル書き込み失敗など）: `phase3_failures` に `"status.md update"` を追加し、次のステップへ進む

4. **サイクル成果物をコミット**: Phase 2 完了後に作業ディレクトリへ残っている全ての uncommitted changes をまとめてコミットする
   - 典型的な対象: Step 2 で新規作成した result ファイル / Step 3 で更新した `.agents/artifacts/status.md` / `.agents/artifacts/session-history.md` / Phase 2 agent が commit し損ねた計画ファイルの更新など
   - スキル `claude-skills:commit` を **引数なし** で実行する（commit skill が `git status` / `git diff` から対象を自動検出してコミット単位を分割する）
   - Step 3 が失敗した場合、status.md / session-history.md は更新されていないため自然と commit 対象には入らない（result ファイルだけがコミットされる想定）
   - 対象なしの場合、commit skill 側でスキップ判定する
   - **失敗時**: `phase3_failures` に `"commit"` を追加し、次のステップへ進む

5. **Issue 自動 close**: 計画ファイルを読み、`**Issue:**` 行が存在するか確認する
   - `**Issue:**` 行がある場合: issue slug を抽出し、スキル `claude-skills:issue` を `close {slug}` 引数で実行する
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
Commits: {N}（サイクル全体で作成したコミット数。Phase 3 の成果物コミットを含む）
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
- **Phase 1/Phase 2 でサブエージェントがエラー**: 1回自動リトライする。リトライも失敗した場合はサイクルを中断する。
- **Phase 1/Phase 2 で委譲先が報告なしで停止した場合**（作業完遂 + 完了報告なし + 待機通知のみ、が最頻の停滞パターン）: エラー扱いで即リトライせず、まず `.agents/runtime/delegation/{run_id}_{role}.md` を読む → 欠落・不完全なら成果物（コミット履歴・変更ファイル・テスト結果・計画の Progress）を直接検分してフェーズの完了・欠落を判定する → 判定不能のときに限りリトライ（1回）する。結果ファイルまたは成果物で完了が確認できれば、報告未達でもそのまま次フェーズへ進む。
- **Phase 3 の各ステップでエラー**: 失敗ステップを `phase3_failures` リストに記録し、残りのステップを続行する。Phase 3 のエラーで cycle 全体を失敗にしない。

## Codex セカンドオピニオン

Phase 1（Refine）で使用される plan-reviewer には Codex セカンドオピニオンが自動的に含まれます。
Claude の 7 次元レビューに加え、Codex による包括的な第三者視点が並行で取得されます。
Codex が利用不可能な場合は既存の 7 次元レビューのみで続行します（graceful degradation）。

## 重要なルール

- **各フェーズはサブエージェントに委譲する**。メインコンテキストにはサマリーのみ保持する。
- **サブエージェント起動時は高性能モデルを明示する**。セッションが最上位モデルでも配下は高性能モデルで実行し、コスト暴発を防ぐ（[orchestration-patterns.md](../shared/references/orchestration-patterns.md) のモデル階層に準拠）。
- **Phase 1 の BLOCK は絶対に無視しない**。BLOCK が残っていたら Phase 1.5 でフォールバックを試み、それでも解消しなければ実装に進まない。
- **ユーザーへの確認プロンプトは出さない**（ヘッドレス実行対応）。
- **サブエージェントエラー時は1回リトライする**。リトライ後も失敗なら中断する。2回以上のリトライは行わない。
- **Phase 3 は部分成功を許容する**。個別ステップの失敗がcycle全体を巻き戻さない。
- 問題の根本原因が不明な場合は、cycle 実行前に `/claude-skills:investigate` で読み取り専用の事前調査を推奨する。
