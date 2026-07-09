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

## クロスツール互換性の注意

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
