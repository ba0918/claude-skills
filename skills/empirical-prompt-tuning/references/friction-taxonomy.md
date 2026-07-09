# Friction Taxonomy

実行者の摩擦報告を分類する固定タクソノミ。
自由記述をイテレーション間で比較可能にし、発散判定を精密化する。

## 6 分類

| カテゴリ | 定義 | 典型的な実行者の発言 |
|---------|------|---------------------|
| `ambiguous_term` | 複数解釈可能な語句 | 「"適切に" がどの水準か分からない」 |
| `missing_premise` | 暗黙の前提知識が必要 | 「この API のバージョンが不明」 |
| `contradictory` | 指示間の矛盾 | 「A 節と B 節で逆のことを言っている」 |
| `over_specified` | 不必要に厳密で判断余地がない | 「変数名まで指定されていて実態と合わない」 |
| `rationalization_hook` | 合理化で回避できる指示 | 「"必要に応じて" と書いてあるので省略した」 |
| `self_containment_gap` | 外部参照なしでは完結しない | 「references/X.md を読まないと何をすべきか分からない」 |

`uncategorized` は上記に当てはまらない場合のフォールバック。

## 分類 → 修正パターン対応表

| カテゴリ | 推奨修正パターン |
|---------|----------------|
| `ambiguous_term` | 定義を追加 or 用語を限定する（例: 「適切に」→「RFC 7231 準拠で」） |
| `missing_premise` | 前提を明示 or 最小完成例を inline に追加 |
| `contradictory` | 優先順位を明示 or 片方を削除 |
| `over_specified` | 制約を緩める or 「推奨」に降格 |
| `rationalization_hook` | escape hatch を塞ぐ（「必要に応じて」→ 具体条件を列挙） |
| `self_containment_gap` | 必要な情報を inline 化 or 参照先と読むタイミングを明示 |

## 発散判定への接続

同一カテゴリが `threshold`（デフォルト 3）回連続で出現した場合、
`convergence.py` の `is_diverged()` が発散と判定する。
これは「同じ種類の問題をパッチで直せていない → 構造を書き直すべき」のシグナル。

## 実行者への指示

実行者の摩擦報告テンプレートに以下を含める:

```
## 摩擦報告
指示で詰まった箇所を以下の分類で報告してください:
- ambiguous_term: 複数解釈可能な語句
- missing_premise: 暗黙の前提知識が必要
- contradictory: 指示間の矛盾
- over_specified: 不必要に厳密
- rationalization_hook: 合理化で回避できる指示
- self_containment_gap: 外部参照なしでは完結しない

形式: { "category": "<分類>", "detail": "<詳細>" }
該当なしの場合は空配列 [] を返してください。
```
