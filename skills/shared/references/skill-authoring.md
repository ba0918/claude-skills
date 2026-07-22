# Skill Authoring 共通仕様

本リポジトリでスキルを新規作成・大幅改訂するときのフォーマット仕様と執筆原則。
skill-improve などのメタスキルの判断基準としても参照する。
ここに書かれた機械検証可能なルールは `scripts/validate_repo.py` が CI で強制する。

## ディレクトリ構成

```
skills/<skill-name>/
  SKILL.md          # 必須: メインロジック
  references/       # 任意: テンプレート・チェックリスト等（SKILL.md から相対リンク）
  scripts/          # 任意: 実行ヘルパー（skill-improve の collect.py 等）
commands/<command>.md  # 任意: スキルを呼び出す薄いラッパー（skills-first 方針により新規はデフォルト不要）
```

- スキル名はケバブケース。`.skill` 単体ファイル形式は使わない
- `references/` は本当に使うファイルだけ置く。他スキルの構成を真似た空ディレクトリを作らない
- 複数スキルで共有する契約・定義は `skills/shared/references/` に置き、各スキルからリンクする

## Commands の位置づけ（skills-first）

ロジックは常に skills に集約し、commands は Claude Code ローカル専用のオプショナルな糖衣とする。
skills はクロスツールの共通分母（Codex CLI / APM 等のエコシステムは commands 相当を非サポート）であり、
Claude Code 上でもスキルは `/skill-name` で直接起動できるため、command がなくても発見性は description で確保できる。

- **新規スキルは command なしをデフォルトにする**。SKILL.md の description にトリガー語と引数の使い方を書くことで起動導線を担保する
- command を追加してよいのは **multi-workflow スキルの名前付きエントリポイント**が必要な場合のみ（例: `issue` スキルに対する issue-create / issue-list / issue-plan。1スキル複数ワークフローの各入口を `/` 補完に個別の説明付きで並べたい場合）
- command を作る場合もロジックは書かない。Skill ツール呼び出し + `$ARGUMENTS` の受け渡しのみの薄いラッパーに徹する
- **既存 commands は互換性のため維持する**。1行ラッパーで維持コストはほぼゼロであり、削除は既存ユーザーの `/claude-skills:*` 呼び出しを壊す。積極的に増やさず自然減に任せる

## Frontmatter 契約（validate_repo.py が強制）

```yaml
---
name: skill-name        # ディレクトリ名と一致
description: <何をするか>。<いつ使うか（トリガー語）>。
---
```

- **name / description は必須**（チェック3）
- **description は 1024 字以内**（チェック10）
- **description はトリガー語を含む**（チェック10）: 日本語スキルは「『◯◯』『◯◯』で起動」、英語スキルは "Use when …"。スキル発火はモデルが description を読んで判断するため、トリガー語の欠落は発火漏れに直結する
- description に**ワークフローの要約を書かない**。手順を description に書くと、モデルが本文を読まずに要約だけで動く事故が起きる
- 免除が必要な場合は frontmatter ではなく `validate_repo.py` の `DESCRIPTION_TRIGGER_EXEMPT` に理由付きで登録する（スキルファイルの編集だけで検証を迂回させない）

## 執筆原則

1. **Process over prose** — スキルは参照ドキュメントではなくワークフロー。フェーズ・ステップ・遷移条件で書く。知識の羅列になりそうなら `references/` に逃がす
2. **Specific over general** — 「テストを確認する」ではなく「`npm test` を実行し 0 failures を確認する」
3. **Evidence over assumption** — 完了条件は必ずエビデンス要求とセットにする（[verification-gate.md](verification-gate.md) 準拠）
4. **Progressive disclosure** — SKILL.md はエントリーポイントに徹する。詳細資料はワークフローが到達した時点で読む `references/` に置く。参照は SKILL.md から1階層まで（参照の参照をチェーンしない）
5. **共有契約を再発明しない** — TDD / 検証ゲート / Codex 連携 / polling / 言語検出 / オーケストレーション設計は既存の shared references を参照する。重複記述はドリフトの温床

## 合理化防止テーブルと Red Flags

エージェントがステップをサボる時の「言い訳」と反論を表で明記する。
省略されやすいステップ（検証・テスト・確認）を持つスキルには入れることを推奨する。

```markdown
## 合理化防止

| 言い訳 | 現実 |
|--------|------|
| 「今回だけスキップ」 | 例外なし。それは合理化 |
| 「もう正しいとわかっている」 | 自信はエビデンスではない |
```

- 書き方の実例: [verification-gate.md](verification-gate.md) の合理化防止、[tdd-contract.md](tdd-contract.md) の合理化テーブル
- **Red Flags** は「スキルが守られていない兆候」の観測可能なリスト。レビュー時・自己監視に使う。判定可能な形で書く（「テスト実行せずに GREEN を宣言している」）

## プロンプト圧縮の効果条件（empirical-prompt-tuning 実測に基づく）

Fable 5 世代モデルでも「短くすれば良くなる」わけではない。`empirical-prompt-tuning` で plan / cycle スキルを 6 iteration 計測した結果、以下が観測された。

### 効くパターン

- **inline 二重説明を契約参照に集約**: SKILL.md 内に inline された共通契約（checkpoint 復元手順 / delegation relay 等）を、契約側正本への短い参照に置き換える。次 3 条件が揃うと顕著に効く（実測で friction -37%）:
  1. inline 節が長い（数十行以上）
  2. inline 節が全シナリオに関係するわけではない（例: 新規 plan 作成では checkpoint 節は不要）
  3. 契約側で完全にカバー済み
- **例示・enum の削減**: 有能モデルには「URL slug の作り方」等の一般定義は不要。1 例のみ残すか完全に削る
- **禁止語（`絶対に` / `してはならない`）を減らす**: `over_specified` と `rationalization_hook` の主原因。柔らかい表現でも compliance は落ちない（実測: 4 iter で両カテゴリ完全消滅）

### 効かない / 削るべきでないパターン

- **契約側の rationale / 却下記録 / v2 ロードマップ削除**: 保守負債軽減にはなるが実行時信号は弱い（friction ほぼ変化なし）
- **パス制約や auto mode 判別等の「規約」の緩和**: compliance が破綻する
- **常時関与する情報の集約**: inline 節が全シナリオで必要な場合、集約しても執行者が読む情報量は同じで効果が薄い（cycle の delegation relay 圧縮で実証）

### 構造由来の摩擦は prose 削減では解けない

`ambiguous_term` / `missing_premise` / `self_containment_gap` は削減方向ではなく **明示化・例示追加** で解く。テンプレ書式の曖昧さ、プロジェクト情報の欠落、template chase 構造そのものが原因のため、Fable 論調とは逆方向のアプローチが必要になる。

### 横展開バッチ1（commit / plan-reviewer、2026-07-22）での追加知見

- **既にリーンなスキル（~150-200 行級）はサイズ削減より摩擦削減が主効果**: commit は行数 -9% に対し摩擦 -83%（6→1、precision 100% 維持）。明示化の追記でバイト数はむしろ増えうるが、それで良い（「高信号トークンの選別」が正）
- **圧縮テーマと明示化テーマは iteration を分けて回す**: 圧縮で消える摩擦（二重説明由来）と、明示化でしか消えない摩擦（既定値欠落・未定義分岐）が分離して観測できる
- **`is_diverged` はカテゴリ単位の粗い判定**: 詳細レベルで毎回別項目・総数漸減でも ambiguous_term が 3 回連続すると diverged になる。残存が (a) 本質的判断領域 (b) 契約参照設計そのもの (c) 評価ハーネス起因なら、prose 追加は over-specification に転ぶため打ち切りが正しい

### 収束履歴の資産化

`empirical-prompt-tuning` の fixture として plan スキルの 4 iteration 収束履歴が `.claude/tmp/empirical/plan-*/fixture.json` に記録される。横展開バッチ1 の計測は `.claude/tmp/empirical/20260722-lean-rollout/`（summary.md + iterations.jsonl）。カテゴリ推移・削減量・学びの全文はそこを参照。再チューニング時のベースライン比較・回帰検出資産として使う。

## クロスツール互換性の注意

- **SKILL.md 本文の言語は 1 スキル内で統一する（本文は英語を推奨）**: 英日混在は可読性を損なう（2026-07-22 ユーザー裁定）。トークン効率も英語が有利 — o200k 実測で同内容の日本語版は約 +30%（commit: 英 1,607 vs 日 2,091 tokens）、英日混在だった plan-reviewer は英語統一だけで 3,758→3,025 tokens（-19.5%）。frontmatter `description` はユーザーの発話語彙（日本語トリガー）を含める必要があるため日本語のままでよい。日本語契約ファイルの見出し名や照合語彙（例: "ユーザー確認"）の引用は混在に数えない
- スキル本文は `skills/` を単一の正本とし、Claude Code / Codex CLI / Cursor / Gemini CLI などで読める自然言語に保つ
- `SKILL.md` と `references/` では、特定プラットフォームのツール API 名やモデル名に依存しない表現を使う
- プラットフォーム差が必要な場合は、本文を分岐コピーせず [tool-mapping.md](tool-mapping.md) に共通語彙と対応方針を集約する

## 新規スキル追加チェックリスト

- [ ] command の要否を skills-first 方針で判断した（デフォルトは command なし。multi-workflow の名前付き入口が必要な場合のみ薄いラッパーを追加）
- [ ] AGENTS.md / README.md の主要スキル表を必要に応じて更新した（CLAUDE.md は薄い wrapper のままにする）
- [ ] README.md（コマンド表・スキル表・ファイル構成）を更新した
- [ ] plugin manifest への反映が必要な変更なら `.claude-plugin/` / `.codex-plugin/` を更新した
- [ ] 複数エージェントを使う場合は [orchestration-patterns.md](orchestration-patterns.md) の判断フローを通し、Agent 呼び出しに model 指定（モデル階層準拠）を明示した
- [ ] `python3 scripts/validate_repo.py` が全チェック合格
- [ ] バージョン bump 時は plugin.json / marketplace.json / CHANGELOG.md を更新した
