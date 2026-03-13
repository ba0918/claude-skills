# Output Template - generate-review-rules

`.claude/review-rules.md` の出力テンプレート。全セクションが必須ではない。プロジェクトに該当する観点のみ出力する。

---

```markdown
# Project Review Rules

plan-reviewer および コードレビュー でこのプロジェクトをレビューする際に適用するプロジェクト固有ルール。
（generate-review-rules スキルにより自動生成。手動で調整可能）

## Architecture

{CLAUDE.md の Design Principles / Architecture セクションから抽出}

- レイヤー構造と依存方向
- 責務分離のルール
- モジュール分割の基準

## Security

{プロジェクト固有のセキュリティ観点}

- 入力検証のルール
- 機密データの取り扱い
- 認証・認可の要件

## Performance

{言語・FW固有のパフォーマンス観点}

- リソース管理のルール
- 計算量の制約
- I/O最適化の方針

## Language/Framework Specific

{検出した言語・FWに応じた固有ルール}

- 言語固有のアンチパターン
- FW固有の制約やベストプラクティス
- ビルド・依存管理のルール

## Testing

{テスト方針・テストフレームワーク固有のルール}

- テストの配置規約
- カバレッジの基準
- テスト記述のスタイル
```
