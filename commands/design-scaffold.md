---
description: "DESIGN.md → tokens.json + tokens.css + lint設定を scaffold 生成"
---

`design-scaffold` スキルを実行する。ステージ引数（`tokens` / `catalog` / `layout`）で単一ステージを指名でき、引数なしなら Stage A から順にステージ境界ごとに継続確認する。

## 手順

1. Skillツールで `claude-skills:design-scaffold` を起動する
2. ユーザーの引数 `$ARGUMENTS` をそのまま渡す
