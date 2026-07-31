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

タグやブランチで固定する場合:

```json
{
  "plugin": ["claude-skills@git+https://github.com/ba0918/claude-skills.git#v1.72.0"]
}
```

Claude Code / Codex とは別経路のインストールになる。併用する場合は各エージェントでそれぞれ入れる。

## 動作確認

OpenCode の `skill` ツールで一覧を出し、`cycle` や `brainstorm` などが見えること。

## 使い方

- スキルの一覧・読込は OpenCode ネイティブの `skill` ツール（名前に plugin 接頭辞は付けない）
- スラッシュコマンド（`commands/`）は本 plugin では自動登録しない。必要なら `.opencode/command/` に薄いラッパーを置く
- 常駐の skill-routing 表と quality-gate ポインタは、セッション最初の user メッセージへ自動注入される（Claude Code の SessionStart hook 相当）

## 更新

git 経由の plugin は OpenCode / Bun の cache や lock に解決結果が残ることがある。再起動だけでは最新にならない場合は、OpenCode の package cache を消すか plugin 行を付け直して再インストールする。

## 仕組み

`.opencode/plugins/claude-skills.js` が次を行う:

1. **`config` hook** — パッケージ内 `skills/` を `skills.paths` に追加（symlink 不要。`shared/` も同じツリー）
2. **`experimental.chat.messages.transform`** — `rules/skill-routing.md` 全文と quality-gate 契約のパスポインタを、各セッション最初の user メッセージへ 1 回注入

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
