# Superpowers スキル統合

**Cycle ID:** `20260411040706`
**Started:** 2026-04-11 04:07:06
**Status:** 🟢 Complete

---

## 📝 What & Why

superpowers / superpowers-skills / Anthropic official skills から良い要素を取り込み、既存スキルセットの品質・堅牢性を強化する。特に design-principles.md で「テスタビリティが最高原則」と宣言しているにもかかわらず、TDD を強制するスキルが存在しない矛盾を解消する。

## 🎯 Goals

- TDD（RED-GREEN-REFACTOR）を cycle/iterate の実装フェーズで強制する仕組みを導入する
- 構造化デバッグスキルで「根本原因を見つけるまで修正するな」を実践レベルに落とし込む
- 「証拠なしに完了を主張するな」の verification gate を既存ワークフローに統合する
- 問題解決の思考ツールを brainstorm と連携可能な形で提供する
- testing anti-patterns をルールファイルとして全プロジェクトに適用する

## 📐 Design

### Phase 1: 基盤整備（共有リソース + ルール）

```
rules/
  testing-anti-patterns.md              — NEW: テストアンチパターン集（全プロジェクト適用）

skills/shared/references/
  tdd-contract.md                       — NEW: TDD 共通契約（cycle/iterate が参照）
  verification-gate.md                  — NEW: 完了前検証ゲート共通契約
```

#### Task 1.1: rules/testing-anti-patterns.md を作成

superpowers-skills の testing-anti-patterns を基に、プロジェクト横断のルールファイルを作成。

**含むべき内容:**
- Anti-Pattern 1: モックの振る舞いをテストするな（モックの存在を assert しない）
- Anti-Pattern 2: テスト専用メソッドをプロダクションに入れるな（test-utils に分離）
- Anti-Pattern 3: 依存関係を理解せずにモックするな（副作用の把握が先）
- Anti-Pattern 4: 不完全なモック（実 API のスキーマを完全再現）
- Anti-Pattern 5: テスト後付け（TDD で防止）
- 各パターンに Gate Function（「このモックを追加する前に自問する」チェック）を含める
- design-principles.md のテスタビリティ原則との関連を明記

#### Task 1.2: skills/shared/references/tdd-contract.md を作成

TDD スキルと cycle/iterate が共有する契約。

**含むべき内容:**
- RED-GREEN-REFACTOR サイクルの定義
- Iron Law: `NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST`
- 合理化テーブル（言い訳とその反論）の抜粋（上位5つ）
- Red Flags（TDD 違反の兆候）リスト
- cycle/iterate の実装フェーズからの参照パス

#### Task 1.3: skills/shared/references/verification-gate.md を作成

完了前検証の共通契約。cycle/iterate/commit が参照。

**含むべき内容:**
- Iron Law: `NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE`
- Gate Function: IDENTIFY → RUN → READ → VERIFY → CLAIM
- 禁止表現（"should", "probably", "seems to", 検証前の "Done!", "Perfect!"）
- 検証パターン表（テスト/ビルド/リンター/要件/エージェント委譲 × 必要なエビデンス）
- commit スキルへの統合指針（コミット前にテスト実行を必須化）

### Phase 2: 新規スキル作成

```
skills/
  test-driven-development/
    SKILL.md                            — NEW: TDD 強制スキル
  systematic-debugging/
    SKILL.md                            — NEW: 構造化デバッグスキル
    references/
      root-cause-tracing.md             — NEW: 後方トレース手法
  problem-solving/
    SKILL.md                            — NEW: 思考ツール集（5サブワークフロー）

commands/
  tdd.md                                — NEW
  debug.md                              — NEW
  problem-solving.md                    — NEW
```

#### Task 2.1: test-driven-development スキルを作成

RED-GREEN-REFACTOR サイクルの強制スキル。

**ワークフロー:**
- デフォルト → **Guide Workflow**: 現在の実装タスクに対して TDD サイクルをガイド
  1. ユーザーのタスクを把握（$ARGUMENTS or AskUserQuestion）
  2. RED: テストを書かせる → 失敗を確認（Bash でテスト実行）
  3. GREEN: 最小限のコードを書かせる → パスを確認
  4. REFACTOR: リファクタリング → テストが緑のままか確認
  5. 次のサイクルへ or 完了

**絶対的な制約:**
- テスト実行結果を Bash で確認するまで GREEN フェーズに進めない
- テストがパスするまで REFACTOR フェーズに進めない
- verification-gate.md を参照し、各フェーズで証拠を要求

**エラーハンドリング:**
- テストフレームワーク検出失敗時: AskUserQuestion で「テスト実行コマンドを教えてください（例: `npm test`, `pytest`, `cargo test`）」を表示。ユーザーが「なし」と回答した場合、「TDD にはテストフレームワークが必要です。先にテスト環境をセットアップしてください」と表示して終了
- テスト実行タイムアウト時（60秒以上）: テストを中断し「テスト実行がタイムアウトしました。テストコマンドが正しいか確認してください」と表示。AskUserQuestion で「1. テストコマンドを変更する 2. タイムアウトを無視して続行 3. セッションを中断する」を提示
- テスト実行でランタイムエラー（テストフレームワーク自体のエラー）: エラーメッセージを表示し、「テスト環境に問題がある可能性があります」と警告

**参照:**
- [../shared/references/tdd-contract.md](../shared/references/tdd-contract.md)
- [../shared/references/verification-gate.md](../shared/references/verification-gate.md)
- testing-anti-patterns ルール（rules/testing-anti-patterns.md）

**コマンド:** `commands/tdd.md` → `skills/test-driven-development/SKILL.md`

#### Task 2.2: systematic-debugging スキルを作成

4 フェーズ構造化デバッグスキル。investigate の補完（investigate=読み取り専用調査、systematic-debugging=修正まで含む）。

**ワークフロー:**
1. **Phase 1: Root Cause Investigation** — エラーメッセージ精読、再現、最近の変更確認、データフロートレース
2. **Phase 2: Pattern Analysis** — 動作する類似コードとの比較、差分の特定
3. **Phase 3: Hypothesis & Testing** — 仮説を1つ立てて最小限の変更でテスト
4. **Phase 4: Implementation** — 失敗テスト作成 → 修正 → 検証（TDD サイクル参照）

**3回修正失敗ルール:**
- 3回以上修正を試みて失敗 → アーキテクチャの問題を疑う
- ユーザーに AskUserQuestion で相談（自動修正続行しない）:
  ```
  ⚠️ 3回の修正試行が失敗しました。根本的な設計の問題の可能性があります。
  
  これまでの試行:
  1. {試行1の概要} → {失敗理由}
  2. {試行2の概要} → {失敗理由}
  3. {試行3の概要} → {失敗理由}
  
  選択肢:
  1. アーキテクチャの問題を一緒に検討する（推奨）
  2. 別のアプローチで修正を試す
  3. 調査結果をレポートとして出力し中断する
  ```

**investigate との連携:**
- Phase 1 で investigate スキルの出力を入力として受け付ける
- investigate → systematic-debugging の導線を提供

**references/root-cause-tracing.md:**
- バグを後方にトレースする手法（症状 → 直接原因 → さらに上流 → 根本原因）
- 多層システムでの診断インストルメンテーション追加パターン

**コマンド:** `commands/debug.md` → `skills/systematic-debugging/SKILL.md`

#### Task 2.3: problem-solving スキルを作成

行き詰まった時の思考ツール集。brainstorm セッション中からも呼び出し可能。

**ワークフロー選択（$ARGUMENTS キーワード）:**
- `simplify` → **Simplification Cascades**: 「全ては〇〇の特殊ケース」を見つけて複雑性を劇的に削減
- `collide` → **Collision-Zone Thinking**: 無関係な概念を強制衝突させて創発的性質を発見
- `invert` → **Inversion Exercise**: 前提を反転させて隠れた制約と代替アプローチを発見
- `scale` → **Scale Game**: 極端なスケール（1000倍大きい/小さい）でテストして本質を露出
- `pattern` → **Meta-Pattern Recognition**: 3+ドメインに現れるパターンから普遍原則を抽出
- (なし) → **Dispatch**: 行き詰まりの種類を AskUserQuestion で特定し、適切な手法に誘導:
  ```
  どのような行き詰まりですか？
  1. 問題が複雑すぎて分解できない → simplify を提案
  2. 新しいアイデアが出ない → collide を提案
  3. 前提や制約が正しいか疑問 → invert を提案
  4. スケールしたときの問題が見えない → scale を提案
  5. 似たパターンを他で見た気がする → pattern を提案
  ```

**各サブワークフローの共通構造:**
1. 問題の定義（AskUserQuestion で確認）
2. 手法の適用（具体的なステップ）
3. 発見の整理（要約を表示）
4. 次のアクション提案（brainstorm に戻る / plan 作成 / 別の手法を試す）

**絶対的な制約:**
- brainstorm と同じく Edit/Write/NotebookEdit 禁止（思考ツールなので）
- コード生成禁止（概念レベルの議論に集中）

**コマンド:** `commands/problem-solving.md` → `skills/problem-solving/SKILL.md`

### Phase 3: 既存スキル統合

```
commands/
  cycle.md                              — MODIFY: TDD + verification gate 統合
skills/
  iterate/SKILL.md                      — MODIFY: verification gate 統合
  commit/SKILL.md                       — MODIFY: verification gate 統合（テスト実行必須化）
  brainstorm/SKILL.md                   — MODIFY: problem-solving 連携追加
  skill-improve/SKILL.md               — MODIFY: プレッシャーテスト手法追加
```

#### Task 3.1: cycle の plan-implement フェーズに TDD 強制を組み込む

`commands/cycle.md` を修正。

**変更内容:**
- Phase 2（Implement）の Agent プロンプトに TDD 契約を注入
  - 「実装時は tdd-contract.md に従い、テストファースト（RED → GREEN → REFACTOR）で進めること」
  - 「テスト実行結果を各ステップで確認し、パスしてから次に進むこと」
- Phase 3 の完了チェックに verification gate を追加
  - 「テスト全パスのエビデンス（コマンド出力）を結果ファイルに含めること」

#### Task 3.2: iterate の Phase 4 レビューに verification gate を組み込む

`skills/iterate/SKILL.md` を修正。

**変更内容:**
- Phase 4（Review）の完了条件に verification gate を追加
  - レビューエージェントに「verification-gate.md の Gate Function を適用し、テスト実行結果のエビデンスなしに PASS を出さないこと」を指示
- Phase 3（Implementation）の Agent プロンプトに TDD 契約参照を追加

#### Task 3.3: commit スキルに verification gate を組み込む

`skills/commit/SKILL.md` を修正。

**変更内容:**
- コミット前にテストスイートの実行を試みる（テストフレームワークが検出できた場合）
  - package.json の `test` スクリプト / Cargo test / go test / pytest 等を自動検出
  - テスト失敗時: 警告メッセージをコミットメッセージの body に含めてコミットを続行する（commit スキルの Core Principle「No confirmation — Never prompt the user for confirmation」を遵守し、AskUserQuestion は使わない）
    - コミットメッセージ body に `⚠️ Tests failing: {failure_summary}` を追記
  - テストフレームワークが不明な場合: スキップ（従来通り即コミット）
  - **注意**: verification gate の「テスト実行必須化」は commit スキルでは「ベストエフォート」として適用する。commit は高速・無確認が最優先であり、テスト失敗でブロックしない

#### Task 3.4: brainstorm に problem-solving 連携を追加

`skills/brainstorm/SKILL.md` を修正。

**変更内容:**
- Session Workflow の壁打ち中に行き詰まりを検出するロジック追加
- **検出方式**: ユーザー発言の部分一致（大文字小文字無視）で以下のトリガーキーワードを判定:
  - 日本語: 「行き詰ま」「わからない」「どうすれば」「手詰まり」「煮詰ま」「堂々巡り」「進まない」
  - 英語: "stuck", "no idea", "don't know", "dead end", "going in circles"
- キーワード検出時、problem-solving スキルの手法を提案（1セッションにつき最大1回表示、2回目以降は抑制）:
  ```
  💡 行き詰まった時は `/claude-skills:problem-solving` で思考ツールを試せます:
  - `simplify` — 「全ては〇〇の特殊ケース」を見つける
  - `invert` — 前提を反転させてみる
  - `collide` — 無関係な概念を衝突させる
  - `scale` — 極端なスケールでテストする
  - `pattern` — 他ドメインのパターンから学ぶ
  ```

#### Task 3.5: skill-improve にプレッシャーテスト手法を追加

`skills/skill-improve/SKILL.md` を修正。

**変更内容:**
- Phase 2 のフリクション分析に「プレッシャーテスト」観点を追加
  - superpowers の writing-skills/testing-skills-with-subagents の手法を参考
  - 「このスキルの制約はプレッシャー下で合理化されうるか？」を分析観点に追加
  - プレッシャータイプ: 時間圧、サンクコスト、権威、経済性、疲労、社会的、プラグマティック
- Phase 3 の改善仮説に「ガードレール強化」カテゴリを追加

### Phase 4: プラグイン + ドキュメント更新

```
.claude-plugin/plugin.json              — MODIFY: version bump
CLAUDE.md                               — MODIFY: 新スキル情報追加
```

#### Task 4.1: plugin.json を更新

- version: 1.16.0 → 1.17.0
- releaseNotes に追加

#### Task 4.2: CLAUDE.md を更新

- コマンド→スキルマッピングに追加:
  - `commands/tdd.md → skills/test-driven-development/SKILL.md`
  - `commands/debug.md → skills/systematic-debugging/SKILL.md`
  - `commands/problem-solving.md → skills/problem-solving/SKILL.md`
- 主要スキルテーブルに追加
- 共有リソースセクションに tdd-contract.md, verification-gate.md を追加

### Key Points

- **TDD 契約は共有リソース**: cycle/iterate/commit が独立に参照する。スキル本体（test-driven-development）はユーザーが直接使う対話型ワークフロー、共有契約は Agent プロンプトに注入するルール
- **verification gate は非破壊的**: テスト失敗でコミットを「ブロック」するのではなく「警告」する。headless 実行（cycle）では自動パスだが、結果ファイルにエビデンスを記録
- **problem-solving は brainstorm の拡張**: 単独でも使えるし、brainstorm セッション中から呼び出しもできる
- **systematic-debugging は investigate の補完**: investigate（調査のみ）→ systematic-debugging（修正まで）の導線。両方存在する意味がある
- **Anti-patterns は rules/ に配置**: プロジェクト横断で適用。特定スキルに依存しない。ただし Plugin フォーマットでは `rules/` が自動配置されないため（CLAUDE.md 記載の制約）、Plugin 経由ユーザーは `~/.claude/rules/` への手動コピーが必要。この制約を README / releaseNotes で明記する
- **codex-skills/ 対応は後続 issue**: 今回のスコープでは Claude Code Plugin 版（skills/ + commands/）のみ実装する。Codex CLI 版（codex-skills/）は後続 issue として別途対応する。理由: (1) 新規スキルの設計をまず確定させ、安定してから移植する方が手戻りが少ない (2) codex-skills は Claude Code 版の references をシンボリックリンクで共有する構造のため、SKILL.md 確定後に移植するのが効率的

## ✅ Tests

- [ ] TDD スキルが RED → GREEN → REFACTOR の各フェーズで Bash テスト実行を要求するか
- [ ] systematic-debugging が Phase 1 完了前に修正提案をブロックするか
- [ ] verification-gate が「証拠なしの完了主張」を検出して警告するか
- [ ] cycle の Plan-Implement フェーズで TDD 契約が Agent プロンプトに含まれるか
- [ ] commit スキルがテストフレームワーク検出 → テスト実行 → 警告の流れで動作するか
- [ ] problem-solving の各サブワークフローが Edit/Write を使用しないか
- [ ] brainstorm が「行き詰まり」検出時に problem-solving を提案するか

## 📊 Progress

| Step | Status |
|------|--------|
| Phase 1: 基盤整備 | 🟢 |
| Phase 2: 新規スキル作成 | 🟢 |
| Phase 3: 既存スキル統合 | 🟢 |
| Phase 4: プラグイン更新 | 🟢 |

**Legend:** ⚪ Pending · 🟡 In Progress · 🟢 Done

---

**Next:** `/claude-skills:plan-review` でレビュー → `/claude-skills:cycle` で自動実装 🚀
