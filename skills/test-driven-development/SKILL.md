---
name: test-driven-development
description: TDD (RED-GREEN-REFACTOR) サイクルをガイドするスキル。テストファースト開発を強制し、各フェーズでシェルコマンドによるテスト実行結果を証拠として要求する。「tdd」「テスト駆動」「テストファースト」で起動。
---

# Test-Driven Development

RED-GREEN-REFACTOR サイクルの対話型ガイドスキル。ユーザーのタスクに対して TDD を強制し、各フェーズでテスト実行結果のエビデンスを要求する。

### 他スキルとの差別化

- **cycle / iterate との違い**: cycle/iterate はサブエージェントのプロンプトに TDD 契約を注入して自動実行する。本スキルはユーザーと対話しながら 1 サイクルずつ丁寧にガイドする教育的ツール
- **commit との違い**: commit はコミット前のベストエフォート検証。本スキルは実装プロセス全体を TDD で制御する

## 絶対的な制約

### Iron Law

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

テストが失敗することをシェルコマンドで確認するまで、GREEN フェーズに進めない。
テストが全パスすることをシェルコマンドで確認するまで、REFACTOR フェーズに進めない。

### verification-gate 適用

各フェーズの遷移条件として [../shared/references/verification-gate.md](../shared/references/verification-gate.md) の Gate Function を適用する。
「通るはず」「自信がある」等の推測による遷移は禁止。

## Workflow: Guide（デフォルト）

### Phase 0: コンテキスト取得

1. ユーザーのタスクを `$ARGUMENTS` から取得する
   - `$ARGUMENTS` が空の場合: ユーザーに確認して「TDD で実装したいタスクを教えてください」と尋ねる
2. テストフレームワークを自動検出する:
   - `package.json` → `npm test` / `npx vitest` / `npx jest`
   - `Cargo.toml` → `cargo test`
   - `go.mod` → `go test ./...`
   - `pyproject.toml` / `pytest.ini` → `pytest`
   - `Makefile` (test ターゲット) → `make test`
3. **テストフレームワーク検出失敗時**:
   - ユーザーに確認: 「テスト実行コマンドを教えてください（例: `npm test`, `pytest`, `cargo test`）」
   - ユーザーが「なし」と回答 → 「TDD にはテストフレームワークが必要です。先にテスト環境をセットアップしてください」と表示して終了
4. テストコマンドを `$TEST_CMD` として保持

表示:
```
══════════════════════════════════════
TDD SESSION
Task: {task_description}
Test command: {TEST_CMD}
══════════════════════════════════════
```

### Phase 1: RED — 失敗するテストを書く

1. ユーザーのタスクから、最初にテストすべき振る舞いを特定する
2. テストを 1 つ書く:
   - 1 つの振る舞いに対して 1 つのテスト
   - 明確なテスト名（何をテストしているかが名前でわかる）
   - 可能な限り実コードを使う（モックは最小限）
   - [testing-anti-patterns.md](../shared/references/testing-anti-patterns.md) に準拠
3. **シェルでテストを実行する**:
   ```bash
   {TEST_CMD}
   ```
4. **テスト結果を確認する**:
   - ✅ テストが**失敗**した → RED 成功。GREEN へ進む
   - ❌ テストが**通った** → 既存の振る舞いをテストしている。テストを修正する
   - ❌ テストが**エラー**（テストフレームワーク自体のエラー）→ エラーを修正して再実行
   - ❌ **タイムアウト**（60秒以上）→ テストを中断し、ユーザーに確認して対応を確認:
     ```
     ⚠️ テスト実行がタイムアウトしました。
     1. テストコマンドを変更する
     2. タイムアウトを無視して続行する
     3. セッションを中断する
     ```

表示:
```
── RED ──
Test: {test_name}
Result: FAIL ✅ (expected)
Failure: {failure_message}
→ Proceeding to GREEN
```

### Phase 2: GREEN — 最小限の実装

1. テストを通すための**最小限のコード**を書く:
   - 過剰な抽象化、先回り実装はしない
   - YAGNI — テストが要求しないコードは書かない
2. **シェルでテストを実行する**:
   ```bash
   {TEST_CMD}
   ```
3. **テスト結果を確認する**:
   - ✅ テストが**全パス** → GREEN 成功。REFACTOR へ進む
   - ❌ テストが**失敗** → 実装を修正して再実行（RED には戻らない）
   - ❌ **既存テストが壊れた** → 既存テストの修正を優先する

表示:
```
── GREEN ──
Tests: {pass_count}/{total_count} passed
Result: ALL PASS ✅
→ Proceeding to REFACTOR
```

### Phase 3: REFACTOR — 整理する

1. テストが通った状態でコードを整理する:
   - 重複の排除
   - 命名の改善
   - ヘルパーの抽出
   - **新しい振る舞いの追加は禁止**
2. **シェルでテストを実行する**:
   ```bash
   {TEST_CMD}
   ```
3. **テスト結果を確認する**:
   - ✅ テストが**全パス** → REFACTOR 成功。次のサイクルへ
   - ❌ テストが**失敗** → リファクタリングで壊した箇所を修正して再実行

表示:
```
── REFACTOR ──
Changes: {refactoring_summary}
Tests: {pass_count}/{total_count} passed
Result: ALL PASS ✅
```

### Phase 4: 次のサイクルまたは完了

1. タスクの残りの振る舞いを確認する
2. ユーザーに確認して次のアクションを確認する:
   ```
   🔄 TDD サイクル完了！
   
   実装済み: {implemented_behaviors}
   
   次のアクション:
   1. 次の振る舞いをテストする (→ RED に戻る)
   2. TDD セッションを終了する
   ```
3. 「次の振る舞い」選択 → Phase 1 (RED) に戻る
4. 「終了」選択 → 完了表示:
   ```
   ══════════════════════════════════════
   TDD SESSION COMPLETE
   Cycles: {cycle_count}
   Tests added: {test_count}
   All tests passing: ✅
   ══════════════════════════════════════
   ```

## エラーハンドリング

### テストフレームワーク検出失敗

ユーザーに確認してテストコマンドを確認する。「なし」の場合はセッション終了。

### テスト実行タイムアウト（60秒以上）

テストを中断し、ユーザーに確認して 3 択を提示する:
1. テストコマンドを変更する
2. タイムアウトを無視して続行する
3. セッションを中断する

### テスト実行でランタイムエラー

エラーメッセージを表示し「テスト環境に問題がある可能性があります」と警告。修正を試みてからテストを再実行する。

## 参照

- [../shared/references/tdd-contract.md](../shared/references/tdd-contract.md) — TDD 共通契約
- [../shared/references/verification-gate.md](../shared/references/verification-gate.md) — 完了前検証ゲート
- [testing-anti-patterns.md](../shared/references/testing-anti-patterns.md) — テストアンチパターン集
