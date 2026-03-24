# UI/UXデザイナーレビューの導入検討

**Created:** 2026-03-24 21:02:03
**Status:** 💡 Idea
**Tags:** `review` `ui-ux` `team-cycle` `plan-reviewer`
**Mode:** Team Brainstorm
**Rounds:** 1（Phase 1 発散 + Phase 3 深掘り）

---

## Summary

レビュースキル（plan-reviewer / team-cycle / team-plan / codebase-review）にUI/UX観点を導入する方法を5ロール（Challenger / Explorer / Connector / Grounded / Domain Expert: UI/UXデザイン）で多角的に議論。25以上のアイデアを発散させ、3つの主要論点（常時vs条件付き、専任vs責務拡張、型分類レジストリ）を深掘り。「条件付き動的ロール追加（偽陽性許容・ユーザーオーバーライド付き）」と「段階的導入（チェックリスト→キーワード検出→専任ロール）」が合意方向として収束。

## Key Discussion Points

- 現在のレビューシステム（Security / Performance / Architect / Pragmatist）にはUI/UXの視点が一切含まれていない
- CLIツールであってもUI/UXレビューは重要（ターミナル出力・対話フロー・エラーメッセージ等のUX設計）
- 全実装に常時UI/UXレビューを入れるのはコスト過剰 → 条件付き（UI要素検出時のみ）が最適
- チェックリストだけでは専門家視点の問題（認知負荷の蓄積、スキル間一貫性、非ハッピーパス設計）の約4割を見落とす

## Dispute Memory

### Accepted

全ロールが「面白い」と認めた案。

| # | Idea | Proposed By | Why Accepted |
|---|------|-------------|--------------|
| 1 | 条件付き動的ロール追加（偽陽性許容 + ユーザーオーバーライド） | Explorer, Challenger, Connector, Grounded | 全員が「UIが含まれる場合のみ追加」方向で合流。偽陰性より偽陽性を許容する設計 |
| 2 | UI/UXチェックリストの具体化（5観点） | Domain Expert | CLI出力品質・対話フロー評価・ドキュメント可読性・マイクロインタラクション・エラーリカバリーUX |
| 3 | review-dimensions.md へのUI/UXセクション追記 | Grounded | 30分で検証可能なクイックウィン。Markdownのみ、コード変更なし |
| 4 | team-config.md への UX Advisor ロール追加 | Grounded | 既存テンプレートに沿えば比較的容易。4→5ロール化 |
| 5 | plan-reviewer → team-cycle のシグナル共有 | Connector | plan時点の判定をcycleに引き継ぎ、二重レビュー防止＋漏れ防止 |
| 6 | optional specialist パターンの汎用化 | Connector | Domain Expert のパターンを team-cycle/team-plan にも展開。将来の a11y/i18n にも対応 |
| 7 | skill-improve フィードバックループ | Explorer, Connector | UI/UXレビュー導入後の効果測定→改善サイクル |
| 8 | 段階的導入アプローチ | Grounded, Domain Expert | Step1: チェックリスト(30分) → Step2: キーワード検出(1-2h) → Step3: 専任ロール(必要時) |

### Controversial

ロール間で意見が分かれている案。対立構造を明記する。

| # | Idea | For | Against | Core Tension |
|---|------|-----|---------|--------------|
| 1 | 型分類レジストリ vs シグナルベース判定 | Explorer/Connector: タイプ分類で体系的管理、ハブ&スポーク構造 | Challenger: 保守コスト・境界問題・ブラックボックス化のリスク。シグナル検出で十分 | 体系的管理の利点 vs 保守コストの現実 |
| 2 | チェックリストの4割見落とし問題 | Domain Expert: 専門家でなければ見抜けない問題が存在（認知負荷蓄積、専門用語漏れ、キャンセルフロー設計漏れ、スキル間一貫性、情報優先度の誤り） | Challenger: CLIツール中心のプロジェクトで常時専任は過剰投資 | レビュー品質 vs コスト効率 |
| 3 | Step3（専任ロール追加）への到達タイミング | Domain Expert: 新スキル追加時のみ専任レビューが最適 | Grounded: Step1-2で不足を感じてから判断 | プロアクティブ vs リアクティブ |

### Frontier

実装方法は不明だが革新的な可能性がある案。

| # | Idea | Proposed By | Potential | Unknown |
|---|------|-------------|-----------|---------|
| 1 | 非同期フィードバックトラック | Explorer | UI/UXレビューを同期レビューから分離し別ファイルで非同期出力。同期レビューのコストを上げずにUX視点を残せる | 非同期レビューが実際に参照されるか。品質担保の仕組みが不明 |
| 2 | CLIデザインシステム | Domain Expert(派生) | 出力フォーマット・用語・対話パターンをスキル横断で統一。学習コスト低減と一貫性向上 | 定義と維持のコスト。強制力の仕組みが未定義 |

## Round History

### Round 1

**Phase 1 (Independent Divergence):**
- Challenger: 5案（自動検出+条件付き、全レビュー組込み、常時追加、frontmatterフラグ、plan時スキャン）— 各案のリスク・破綻シナリオを詳細に分析
- Explorer: 5案（コンテキスト感知型注入、ルーブリック外在化、型分類レジストリ、非同期フィードバック、skill-improve統合）— Open-Closed原則に沿った構造的アプローチ
- Connector: 5案（動的注入連動、Domain Expert統合、シグナル共有、自己申告フラグ、skill-improveループ）— 既存システム間の接続点を重視
- Grounded: 5案（review-dimensions追記、team-config追加、条件分岐注入、キーワード検出、条件付きサブエージェント）— 具体的な実装ステップとクイックウィンを提示
- Domain Expert: 5案（CLI出力品質、対話フロー評価、ドキュメント可読性、マイクロインタラクション、エラーリカバリーUX）— CLIツール特有のUX制約とニールセンの原則を適用

**Phase 2 (Classification):**
- Accepted: 7 ideas
- Controversial: 4 ideas
- Frontier: 3 ideas

**Phase 3 (User Feedback + Deep Dive):**
- User feedback: 3論点（常時vs条件付き、専任vs責務拡張、型分類レジストリ）の深掘りを要求
- Team response:
  - 常時vs条件付き → 「条件付き（偽陽性許容＋ユーザーオーバーライド）」で収束。Acceptedに昇格
  - 専任vs責務拡張 → 段階的導入で方向合意。ただしStep3タイミングは未決
  - 型分類レジストリ → MVP具体化（工数2.5h）。ただしシグナルベースとの対立あり

## Decisions & Conclusions

- **最初の一歩**: review-dimensions.md にUI/UXセクションを追記する（30分、コード変更なし）
- **条件付き追加が最適**: 偽陰性より偽陽性を許容する設計。`.claude/review-rules.md` でユーザーがオーバーライド可能にする
- **CLI特有のUI/UXトリガー基準**: 「ターミナル表示が1文字でも変わるか？」がYESならUI/UXレビュー対象
- **チェックリストだけでは6割しかカバーできない**: 認知負荷・スキル間一貫性・非ハッピーパスの設計は専門家視点が必要

## Open Questions

- 型分類レジストリ vs シグナルベース判定、どちらが長期的に優れるか？
- Step3（専任ロール追加）はどのタイミングで実施すべきか？
- 非同期フィードバックトラックは実用的か？
- CLIデザインシステム（出力・用語・対話パターンの統一）は別途取り組むべきか？
- plan-reviewer の6→7観点化で、他の観点とのバランスは崩れないか？

## Next Steps

- `/claude-skills:brainstorm-plan` でこのアイデアを plan に変換（Step1: review-dimensions.md 追記から着手）
- 必要に応じて `/claude-skills:brainstorm-resume` で議論を再開（Controversial の解決）
