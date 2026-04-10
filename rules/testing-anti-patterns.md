# Testing Anti-Patterns

テストは実際の振る舞いを検証するもの。モックの振る舞いを検証するものではない。
TDD (Red → Green → Refactor) を遵守すれば、これらのアンチパターンの大部分は未然に防げる。

**design-principles.md との関連**: テスタビリティが最高原則である以上、テスト自体の品質も最高水準でなければならない。壊れたテストは壊れた安全ネットと同じ。

## The Iron Laws

```
1. モックの振る舞いをテストするな
2. テスト専用メソッドをプロダクションコードに入れるな
3. 依存関係を理解せずにモックするな
4. 不完全なモックを作るな
5. テストを後付けするな
```

## Anti-Pattern 1: モックの振る舞いをテストしている

**違反例:**
```typescript
// BAD: モックの存在を assert している
test('renders sidebar', () => {
  render(<Page />);
  expect(screen.getByTestId('sidebar-mock')).toBeInTheDocument();
});
```

**なぜ問題か:**
- モックが動作することを検証しているだけで、コンポーネントの実際の振る舞いは検証していない
- テストが通ってもコードが正しい保証がない

**修正:**
```typescript
// GOOD: 実コンポーネントの振る舞いをテストする
test('renders sidebar', () => {
  render(<Page />);
  expect(screen.getByRole('navigation')).toBeInTheDocument();
});
```

### Gate Function

```
モック要素に対して assert する前に自問する:
  「実際のコンポーネントの振る舞いをテストしているか、それともモックの存在を確認しているだけか？」

  モックの存在確認 → STOP — assert を削除するかモックをやめる
```

## Anti-Pattern 2: テスト専用メソッドをプロダクションに入れている

**違反例:**
```typescript
// BAD: destroy() はテストでしか呼ばれない
class Session {
  async destroy() {
    await this._workspaceManager?.destroyWorkspace(this.id);
  }
}
```

**なぜ問題か:**
- プロダクションコードがテスト用コードで汚染される
- 誤って本番で呼ばれるリスク
- 責務の混在 (design-principles #2 違反)

**修正:**
```typescript
// GOOD: テストユーティリティに分離する
// test-utils/session-cleanup.ts
export async function cleanupSession(session: Session) {
  const workspace = session.getWorkspaceInfo();
  if (workspace) {
    await workspaceManager.destroyWorkspace(workspace.id);
  }
}
```

### Gate Function

```
プロダクションクラスにメソッドを追加する前に自問する:
  「このメソッドはテストでしか使わないのではないか？」

  テスト専用 → STOP — テストユーティリティに置く
  「このクラスはこのリソースのライフサイクルを所有しているか？」
  所有していない → STOP — 別の場所に置く
```

## Anti-Pattern 3: 依存関係を理解せずにモックしている

**違反例:**
```typescript
// BAD: テストが依存している副作用ごとモックしてしまう
test('detects duplicate', () => {
  vi.mock('ToolCatalog', () => ({
    discoverAndCacheTools: vi.fn().mockResolvedValue(undefined)
  }));
  await addItem(config);
  await addItem(config); // 本来は throw すべきだが、モックが副作用を消している
});
```

**なぜ問題か:**
- モック対象の副作用にテストが依存していた
- 「安全のために」過剰にモックすると実際の振る舞いが壊れる
- テストが間違った理由で通るか、不可解に失敗する

**修正:**
```typescript
// GOOD: 正しいレベルでモックする
test('detects duplicate', () => {
  vi.mock('SlowExternalService'); // 遅い外部通信だけモック
  await addItem(config);  // 設定ファイル書き込みは実行される
  await addItem(config);  // 重複検出が正しく動く
});
```

### Gate Function

```
メソッドをモックする前に:
  1. 「実メソッドにはどんな副作用があるか？」
  2. 「このテストはそれらの副作用に依存しているか？」
  3. 「なぜモックが必要なのか完全に理解しているか？」

  副作用に依存 → より低レベル（実際に遅い/外部の操作）でモックする
  理解不十分 → まず実装で動かして、何が必要かを観察してからモックする

  レッドフラグ:
    - 「安全のためにモックしておこう」
    - 「遅いかもしれないからモックしておこう」
    - 依存チェーンを理解せずにモックしている
```

## Anti-Pattern 4: 不完全なモック

**違反例:**
```typescript
// BAD: 自分が知っているフィールドだけモック
const mockResponse = {
  status: 'success',
  data: { userId: '123', name: 'Alice' }
  // metadata が欠落 → 下流で response.metadata.requestId にアクセスして壊れる
};
```

**なぜ問題か:**
- 部分的なモックは構造的な前提を隠す
- テストは通るが統合で壊れる
- 偽の安心感

**修正:**
```typescript
// GOOD: 実 API レスポンスの完全な構造を再現する
const mockResponse = {
  status: 'success',
  data: { userId: '123', name: 'Alice' },
  metadata: { requestId: 'req-789', timestamp: 1234567890 }
};
```

### Gate Function

```
モックレスポンスを作成する前に:
  「実 API レスポンスにはどんなフィールドがあるか？」

  1. 実際の API ドキュメントまたはサンプルレスポンスを確認する
  2. 下流のコードが消費する可能性のある全フィールドを含める
  3. モックが実レスポンススキーマと完全に一致することを検証する

  不確実 → ドキュメントに記載された全フィールドを含める
```

## Anti-Pattern 5: テストの後付け

**違反例:**
```
✅ 実装完了
❌ テスト未作成
「テスト用意できたら追加します」
```

**なぜ問題か:**
- テストは実装の一部であり、オプションの追加作業ではない
- TDD で書けばこのパターンは発生しない
- テストなしで「完了」を主張するのは検証なしに品質を保証するのと同じ

**修正:**
```
TDD サイクル:
1. 失敗するテストを書く (RED)
2. テストを通す最小の実装を書く (GREEN)
3. リファクタリングする (REFACTOR)
4. ここで初めて「完了」と言える
```

### Gate Function

```
「完了」を宣言する前に:
  「このコードにはテストがあるか？」
  「テストはコードより先に書かれたか？」

  テストなし → STOP — テストを書くまで完了ではない
  テスト後付け → 次回から TDD で進める
```

## Quick Reference

| アンチパターン | 修正方法 |
|--------------|---------|
| モック要素を assert | 実コンポーネントをテストするかモックをやめる |
| テスト専用メソッド | テストユーティリティに移動 |
| 理解せずにモック | 依存関係を理解してから最小限にモック |
| 不完全なモック | 実 API の完全なスキーマを再現 |
| テスト後付け | TDD — テストを先に書く |
| 過度に複雑なモック | 統合テストを検討 |

## Red Flags

- `*-mock` テスト ID に対する assertion
- テストファイルからしか呼ばれないメソッド
- モックのセットアップがテストの50%以上
- モックを外すとテストが壊れる（実装が壊れるのではなく）
- モックが必要な理由を説明できない
- 「安全のために」モックしている
