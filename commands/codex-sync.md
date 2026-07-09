---
description: "Claude 版スキルを Codex 版へ自動移植・差分同期する（port / sync / 未同期スキャン）"
---

`claude-skills:codex-sync` スキルを使用して、Claude 版スキルの Codex 版への移植・同期を実行する。

## 手順

1. スキル `claude-skills:codex-sync` を起動する
2. ユーザーの引数 `$ARGUMENTS` をそのまま渡す
   - スキル名（Codex 版なし）: 新規移植（port）
   - スキル名（Codex 版あり）: 前回同期時点からの差分同期（sync）
   - 引数なし: validate の `[sync]` エラーから未同期ペアを検出して全て同期（scan）
3. 変換ルール（3層）適用 → validate → 同期台帳更新まで自動実行される
4. 第3層（設計判断が必要な箇所）は自動変換されず、要判断リストとして報告される
