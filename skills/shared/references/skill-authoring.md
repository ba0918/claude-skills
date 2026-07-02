# Skill Authoring 共通仕様

本リポジトリでスキルを新規作成・大幅改訂するときのフォーマット仕様と執筆原則。
skill-improve / codex-sync の判断基準としても参照する。
ここに書かれた機械検証可能なルールは `scripts/validate_repo.py` が CI で強制する。

## ディレクトリ構成

```
skills/<skill-name>/
  SKILL.md          # 必須: メインロジック
  references/       # 任意: テンプレート・チェックリスト等（SKILL.md から相対リンク）
  scripts/          # 任意: 実行ヘルパー（skill-improve の collect.py 等）
commands/<command>.md  # スキルを呼び出す薄いラッパー。ロジックはスキル側に集約
```

- スキル名はケバブケース。`.skill` 単体ファイル形式は使わない
- `references/` は本当に使うファイルだけ置く。他スキルの構成を真似た空ディレクトリを作らない
- 複数スキルで共有する契約・定義は `skills/shared/references/` に置き、各スキルからリンクする

## Frontmatter 契約（validate_repo.py が強制）

```yaml
---
name: skill-name        # ディレクトリ名と一致
description: <何をするか>。<いつ使うか（トリガー語）>。
---
```

- **name / description は必須**（チェック3）
- **description は 1024 字以内**（チェック11）
- **description はトリガー語を含む**（チェック11）: 日本語スキルは「『◯◯』『◯◯』で起動」、英語スキルは "Use when …"。スキル発火はモデルが description を読んで判断するため、トリガー語の欠落は発火漏れに直結する
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

## Codex 版を持つスキルの注意

- Claude 版 SKILL.md（cycle のみ `commands/cycle.md`）を変更したら、Codex 版への反映要否を判断し、`python3 scripts/validate_repo.py --update-manifest` で同期台帳を更新する（怠ると CI が fail）
- 移植は codex-sync スキルの3層変換ルール（機械的置換 / 構造的変換 / 要判断）に従う
- ツール非依存の references は複製せず `skills/` への symlink で共有する

## 新規スキル追加チェックリスト

- [ ] `commands/<name>.md`（薄いラッパー）を追加した（コマンド不要なスキルは除く）
- [ ] CLAUDE.md のコマンド対応表・主要スキル表を更新した
- [ ] README.md（コマンド表・スキル表・ファイル構成）を更新した
- [ ] Codex 版を作った場合は AGENTS.md を更新し、同期台帳を更新した
- [ ] 複数エージェントを使う場合は [orchestration-patterns.md](orchestration-patterns.md) の判断フローを通した
- [ ] `python3 scripts/validate_repo.py` が全チェック合格
- [ ] バージョン bump 時は plugin.json / marketplace.json / CHANGELOG.md を更新した
