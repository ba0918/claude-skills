# 位置づけとアーキテクチャ

## 位置づけ

| 層 | スキル | 問い |
|---|---|---|
| 選択層 | trigger-eval | 正しく発火するか（動的実測） |
| **契約層** | **skill-interface-audit** | **仕様として完全か（静的）** |
| 実行層 | empirical-prompt-tuning | 実行品質は高いか（動的） |
| 回帰層 | skill-regression | 変更後も挙動を保つか（fixture） |
| 運用層 | skill-improve | 実運用で摩擦があるか（ログ実測） |

**context-audit との境界は対象ファイル集合で排他的に切る**:
- context-audit → 常駐指示（CLAUDE.md / AGENTS.md / rules / メモリ）
- skill-interface-audit → スキル本体（skills/\*/SKILL.md + references/）

**validate\_repo.py との関係**: frontmatter・description トリガー語・リンク実在・共有契約語彙は
既に CI で強制済みであり重複させない。逆に、監査で安定して機械判定できると証明されたルールは
validate\_repo.py に昇格させて CI 化する（出口戦略）。

## アーキテクチャ: 混成モデル

context-audit の CA-\* パターンを踏襲し、**決定的判定は純関数、LLM は意味判断のみ**の混成モデルを採る。
「純粋静的」ではない——SI-C\* の契約完備性判断は LLM が担い、全て REPORT\_ONLY に留める。

| フェーズ | 判定主体 | 対象ルール | fix action 上限 |
|---------|---------|-----------|----------------|
| Phase 1 | 純関数（スクリプト） | SI-S\* | NEEDS\_JUDGMENT |
| Phase 2 | LLM | SI-C\* | NEEDS\_JUDGMENT（finding 自体は REPORT\_ONLY、パッチ適用判断のみ NEEDS\_JUDGMENT） |
