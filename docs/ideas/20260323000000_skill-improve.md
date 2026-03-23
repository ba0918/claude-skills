# skill-improve: スキル自己改善メタスキル

**Created:** 2026-03-23
**Status:** 📋 Planned
**Tags:** `meta-skill`, `data-analysis`, `friction-detection`, `self-improvement`
**Mode:** Team Brainstorm
**Rounds:** 2

---

## Summary

Claude Code のセッションデータ・session-history・git 履歴など複数データソースからスキル使用状況をプロジェクト横断で収集・分析し、「摩擦」（ユーザーとスキルの間のギャップ）を可視化した上で、AgenticTeam で改善方法を議論してスキル改善を実行するメタスキル。

核心的な発見: 本当の問題は session-history.md のサマリーだけでは分からない。実際のLLMとユーザーのやり取りにおける摩擦（リトライ、修正指示、セッション離脱等）を構造的シグナルとして検出することが価値の源泉。

## Key Discussion Points

- データ収集はスクリプト経由（Python）が必須 — サブエージェントから ~/.claude/ への直接アクセスはサンドボックスで制限される
- メッセージ本文は収集しない — 構造的シグナル（retry_count, correction_turns, session_abandoned等）のみで摩擦を検出
- 既存スキル（investigate, codebase-review, iterate, team-cycle）のパターンを最大限再利用
- フル自動改善は禁止 — Dry-run + 人間レビューゲート必須
- 参考実装: tokoroten/prompt-review の collect.py パターン

## Dispute Memory

### Accepted

全ロールが「面白い」と認めた案。

| # | Idea | Proposed By | Why Accepted |
|---|------|-------------|--------------|
| 1 | session-history.md ベースの使用頻度分析（MVP） | Grounded + Data Analyst | 両者とも「まず session-history.md から始める」で一致 |
| 2 | git log × スキル使用の時系列クロス分析 | Connector + Data Analyst + Grounded | 3ロールが git log との連携を挙げた |
| 3 | データ収集の最小化原則 + プライバシー保護 | Challenger + Data Analyst | 「JSONL を生で読むな」「機密情報を扱うな」で完全一致 |
| 4 | 既存スキルの再利用パターン | Connector + Grounded | 新インフラ不要、既存パターンに乗せる方針で一致 |
| 5 | 改善適用前の安全ゲート（ロールバック保証） | Challenger | 自走実行でスキル定義が壊れた場合の「詰み状態」回避 |
| 6 | plan-reviewer の6観点をスキル評価に転用 | Connector | 既存の強力なレビュー基盤をそのまま活かせる |
| 7 | SKILL.md 静的メトリクス収集 | Grounded | 副作用ゼロで即実装可能（行数・セクション数・references数） |
| 8 | JSONL は読む、ただし抽象化レイヤー必須 | Challenger | SessionParser → SessionEvent → FrictionAnalyzer の3層設計 |
| 9 | 摩擦の3次元モデル | Data Analyst | 修正コスト × 意図乖離度 × 完了遅延で指標化 |
| 10 | ハイブリッド摩擦検出パイプライン | Data Analyst | パターンマッチで候補絞り→LLMセマンティック判定 |
| 11 | codebase-review の4エージェント並行を session-review に転用 | Connector | friction-detector / pattern-analyzer / expectation-auditor / drift-detector |
| 12 | investigate パターンで摩擦レポートを構造化 | Connector | 読み取り専用制約を引き継ぎ、分析と改善実装を完全分離 |
| 13 | collect スクリプトは構造的シグナルのみ収集 | Data Analyst + Challenger | retry_count, correction_turns, session_abandoned 等。メッセージ本文不要 |
| 14 | シンボリックリンク攻撃対策 | Challenger | パス正規化 + プレフィックスチェック必須 |
| 15 | シークレット検出→マスク→テキスト切り捨ての順序保証 | Challenger | 順序逆転バグは容易に発生 |
| 16 | デフォルトスコープ: 現在プロジェクト + 直近30日 | Challenger + Connector | --all や --days で明示的に拡張する設計 |
| 17 | 4フェーズ統合パイプライン | Connector | collect → friction-analyze → hypothesis → implement。新規実装はcollectスクリプト+4エージェント定義のみ |
| 18 | iterate のサイズ判定を改善自走度の制御弁に転用 | Connector | 摩擦スコア低→提案のみ / 中→iterate Small / 高→team-cycle フルレビュー |
| 19 | Dry-run モード必須 | Data Analyst + Challenger | False Positive がコード劣化に直結するリスク回避 |
| 20 | スキルバージョンタグ付け（git blame 日時） | Data Analyst | 改善前後の比較に必須 |

### Controversial

ロール間で意見が分かれている案。対立構造を明記する。

| # | Idea | For | Against | Core Tension |
|---|------|-----|---------|--------------|
| 1 | 摩擦ゼロ＝良いとは限らない | Data Analyst: 期待値が低すぎるサイン / Connector: 良い摩擦と悪い摩擦は区別可能 | Challenger: 完全な判定は困難、invocation_count < 5 は別管理 | 摩擦の不在が「品質の高さ」なのか「無関心」なのか判別困難 |

### Frontier

実装方法は不明だが革新的な可能性がある案。

| # | Idea | Proposed By | Potential | Unknown |
|---|------|-------------|-----------|---------|
| 1 | 加重線形スコアリングの重み最適化 | Data Analyst | データ蓄積後にスコアリング精度を向上 | 初期重みの妥当性、十分なデータ量の確保 |

## Round History

### Round 1

**Phase 1 (Independent Divergence):**
- Challenger: JSONL直接読み取り禁止/ロールバック保証/横断収集の境界問題/AgenticTeam即実装の危険性/収集データ最小化原則
- Explorer: (Bash権限待ちで固まり、報告なし)
- Connector: investigate×codebase-review融合/plan-reviewer観点転用/session-history×git logクロス分析/iterateサイズ適応転用/team-brainstormロール再利用
- Grounded: session-historyスキャナーMVP/git logヒートマップ/SKILL.md静的メトリクス/docs/cycles差分分析/AgenticTeam最小プロト
- Data Analyst: 使用頻度ヒートマップ/エラーパターンクラスタリング/完了率・離脱ポイント/git revert相関/コンテキスト消費効率ROI

**Phase 2 (Classification):**
- Accepted: 12 ideas
- Controversial: 4 ideas
- Frontier: 3 ideas

**Phase 3 (User Feedback + Deep Dive):**
- User feedback: 「本当の問題はsession-historyだけ見ても分からない。実際のLLMとユーザのやり取りの摩擦を分析するのが重要」
- Team response: Challenger→JSONL安全読み取り3層設計、Data Analyst→摩擦の3次元モデル+ハイブリッド検出、Connector→既存スキル接続の具体設計

### Round 2

**Phase 1 (Divergence with Context):**
- 新コンテキスト: tokoroten/prompt-review の collect.py パターン発見 + サブエージェントの ~/.claude/ アクセス制限判明
- Challenger: スクリプト自体の攻撃面/500文字制限の機密漏洩/横断はオプトイン+正規化/摩擦原因の3分類/フル自動禁止+承認コスト最小化
- Connector: collectをBaseCollectorとして継承設計/iterateサイズ判定で自走度制御/2モード引数設計/完全パイプライン統合/良い摩擦vs悪い摩擦の分類
- Data Analyst: skill_invocationsフィールド設計/摩擦分析用JSON拡張スキーマ/プロジェクト横断バイアス対策(層化+下限フィルタ+z-score)/摩擦スコアリングアルゴリズム

**Phase 2 (Classification):**
- Accepted: 20 ideas (累計)
- Controversial: 1 idea (摩擦ゼロ問題 — pragmatic着地)
- Frontier: 1 idea

## Decisions & Conclusions

- **データ収集方式**: Python スクリプト経由（Bash実行→JSON標準出力）。参考: tokoroten/prompt-review の collect.py
- **収集データ**: メッセージ本文は不要。構造的シグナル（retry_count, correction_turns, session_abandoned, negation_words_count等）のみ
- **スコープ**: デフォルトは現在プロジェクト+直近30日。横断は --all でオプトイン
- **セキュリティ**: シークレット検出+マスク必須、シンボリックリンク対策、パス正規化
- **改善実行**: Dry-run 必須。iterate サイズ判定で自走度を制御（低→提案のみ / 中→iterate / 高→team-cycle）
- **アーキテクチャ**: 4フェーズパイプライン（collect → friction-analyze → hypothesis → implement）。既存スキルパターンを最大限再利用

## Open Questions

- collect スクリプトを Python にするか Bash+jq にするか（Python の方が参考実装あり+拡張性高い）
- JSONL のフォーマット変更時の graceful degradation の具体実装
- 摩擦スコアリングの初期閾値の妥当性（データ蓄積後に調整が必要）
- 「良い摩擦」と「悪い摩擦」の自動判定の精度
- 複数プロジェクトでのテスト運用の進め方

## Next Steps

- `/claude-skills:plan-create` で実装計画に落とす
- Phase 1（collect スクリプト + 基本的な摩擦シグナル検出）を MVP として実装
- 実際のセッションデータで動作確認後、Phase 2 以降を段階的に拡張
