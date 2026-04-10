# Root Cause Tracing

バグを後方にトレースし、症状ではなく根本原因を見つける手法。

## Core Principle

```
症状を修正するな。根本原因を見つけてから修正しろ。
```

## トレースプロセス

### 1. 症状を観察する

エラーメッセージ、スタックトレース、異常な出力を正確に記録する。

```
Error: git init failed in /Users/user/project/packages/core
```

### 2. 直接原因を特定する

このエラーを直接引き起こしたコードは何か？

```typescript
await execFileAsync('git', ['init'], { cwd: projectDir });
```

### 3. さらに上流をたどる

「何がこの関数をこの引数で呼んだか？」を繰り返す。

```
WorktreeManager.createSessionWorktree(projectDir, sessionId)
  → Session.initializeWorkspace()
    → Session.create()
      → test: Project.create()
```

### 4. 上流をたどり続ける

各レイヤーで渡された値を検証する:

- `projectDir = ''` (空文字列！)
- 空文字列の `cwd` → `process.cwd()` に解決される
- つまりソースコードディレクトリ内で git init が実行された

### 5. 根本原因を発見する

```typescript
const context = setupCoreTest(); // { tempDir: '' } を返す
Project.create('name', context.tempDir); // beforeEach の前にアクセス！
```

根本原因: トップレベルの変数初期化が空値にアクセスしている。

## 多層システムでの診断インストルメンテーション

システムが複数コンポーネントから構成される場合、各コンポーネント境界にログを追加して、**どこで壊れるか**を特定する。

### パターン

```
各コンポーネント境界で:
  - 入力データをログ
  - 出力データをログ
  - 環境・設定の伝播を検証
  - 各レイヤーの状態を確認

1回実行してエビデンスを収集
→ どの境界で壊れているかを分析
→ その特定コンポーネントを調査
```

### 具体例

```bash
# Layer 1: ワークフロー
echo "=== Secrets available: ==="
echo "API_KEY: ${API_KEY:+SET}${API_KEY:-UNSET}"

# Layer 2: ビルドスクリプト
echo "=== Env vars in build: ==="
env | grep API_KEY || echo "API_KEY not in environment"

# Layer 3: アプリケーション
echo "=== Config loaded: ==="
cat config.json | jq '.apiKey'
```

## スタックトレースの追加

手動でトレースできない場合、インストルメンテーションを追加する:

```typescript
async function riskyOperation(directory: string) {
  const stack = new Error().stack;
  console.error('DEBUG riskyOperation:', {
    directory,
    cwd: process.cwd(),
    nodeEnv: process.env.NODE_ENV,
    stack,
  });
  // 本来の処理
}
```

**テスト中は `console.error()` を使う**（ロガーはテストで抑制されることがある）。

## Defense-in-Depth

根本原因を修正した後、各レイヤーにバリデーションを追加して同じバグが再発不可能にする:

1. **Layer 1**: 入力バリデーション（空文字列チェック等）
2. **Layer 2**: 環境ガード（テスト環境なら tmpdir 外での操作を拒否等）
3. **Layer 3**: ログ追加（危険な操作の前にログを出力）
4. **Layer 4**: 回帰テスト（この特定のバグを再現するテストを追加）

## Key Principle

```
直接原因を見つけた → 1つ上のレイヤーをたどれるか？
  たどれる → さらに上流へ
  たどれない → ここが根本原因
    → 根本原因を修正
    → 各レイヤーにバリデーションを追加
    → バグが構造的に再発不可能になる
```
