# claude-skills for OpenCode

[OpenCode](https://opencode.ai) 向けの導入手順。

## インストール

`opencode.json`（グローバル `~/.config/opencode/opencode.json` またはプロジェクト）の `plugin` に追加する:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": ["claude-skills@git+https://github.com/ba0918/claude-skills.git"]
}
```

OpenCode を再起動する。plugin manager が git から取得し、スキルを登録する。

特定の版に固定する場合は、[Releases](https://github.com/ba0918/claude-skills/releases) に
**実在する** `vX.Y.Z` タグだけを指定する（未発行タグは git ref を解決できない）:

```json
{
  "plugin": ["claude-skills@git+https://github.com/ba0918/claude-skills.git#vX.Y.Z"]
}
```

タグがまだ無い、または Releases に載っていないあいだは、上の unpinned 指定（デフォルトブランチ追従）を使う。
ルート `package.json` の `version` は Claude/Codex manifest と揃える内部番号であり、git タグそのものではない。

Claude Code / Codex とは別経路のインストールになる。併用する場合は各エージェントでそれぞれ入れる。

## 動作確認

OpenCode の `skill` ツールで一覧を出し、`cycle` や `brainstorm` などが見えること。

## 使い方

- スキルの一覧・読込は OpenCode ネイティブの `skill` ツール（名前に plugin 接頭辞は付けない）
- スラッシュコマンド（`commands/`）は本 plugin では自動登録しない。必要なら `.opencode/command/` に薄いラッパーを置く
- 常駐の using-workflow（幹の漏斗 + ルーティング規律）と quality-gate ポインタは、セッション最初の user メッセージへ自動注入される（Claude Code の SessionStart hook 相当）

## 更新

git 経由の plugin は OpenCode / Bun の cache や lock に解決結果が残ることがある。再起動だけでは最新にならない場合は、OpenCode の package cache を消すか plugin 行を付け直して再インストールする。

## 仕組み

`.opencode/plugins/claude-skills.js` が次を行う:

1. **`config` hook** — パッケージ内 `skills/` を `skills.paths` に追加（symlink 不要。`shared/` も同じツリー）
2. **`experimental.chat.messages.transform`** — `skills/using-workflow/SKILL.md` 本文（frontmatter 除く）と quality-gate 契約のパスポインタを、各セッション最初の user メッセージへ 1 回注入
3. **`tool.execute.before`** — bash ツールの git コマンドを実行前にワークフローゲート（`skills/shared/scripts/workflow_gate.py --decide`）で判定し、違反は例外送出で遮断する。escalate（人間確認）は理由文付きの遮断へ縮退する（正本: `skills/shared/references/workflow-gate.md`、環境別の強制力序列はルート README）。判定には `python3` が必要で、起動できない場合は遮断せず素通しになる（fail-open）

`package.json` の `main` がこの plugin を指す。

## トラブルシュート

### plugin が載らない

1. `opencode run --print-logs "hello" 2>&1 | grep -i claude-skills` でログを確認
2. `opencode.json` の `plugin` 行を確認
3. 最近の OpenCode を使う

### Windows で git+https が失敗する

system npm で入れてパス指定する:

```powershell
npm install claude-skills@git+https://github.com/ba0918/claude-skills.git --prefix "$HOME\.config\opencode"
```

```json
{
  "plugin": ["~/.config/opencode/node_modules/claude-skills"]
}
```

### スキルが見えない

1. `skill` ツールで一覧を確認
2. plugin がロードされているか上記ログで確認
3. 各スキルに `name` / `description` 付きの `SKILL.md` があること

### bootstrap が出ない

1. OpenCode が `experimental.chat.messages.transform` をサポートしていること
2. 設定変更後に OpenCode を再起動したこと

### git コマンドが遮断される

ワークフローゲートの判定（main 直コミット・証跡なし push・バイパスフラグの検出）による意図した遮断。遮断メッセージの理由文に対処（ブランチ作成・証跡の生成・恩赦の記録手順）が書かれているので、それに従う。詳細はルート README の「ワークフロー強制ゲート」節を参照。
