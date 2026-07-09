---
title: 統合前の Codex 移植バックログの棚卸し
status: closed
created: 2026-07-09 11:28:22
closed: 2026-07-10 01:56:27
tags: codex,port,backlog,superseded
source: session 2026-07-08 マージ後の棚卸し
---

## 結論

この issue は、スキル本文を単一の `skills/` 正本として Claude Code / Codex CLI / 他エージェントから読む方針に統合したため close する。

旧来の「ランタイム別に別スキルを移植する」前提は廃止済み。今後の作業は移植バックログではなく、`SKILL.md` と `references/` をプラットフォーム非依存の自然言語に保つこと、および必要なランタイム差を `skills/shared/references/tool-mapping.md` に集約することとして扱う。

## 反映済み

- スキル本文の「別版なし」節を削除
- 共有 authoring 契約を単一 `skills/` 正本前提へ更新
- 旧移植コマンドの入口を削除
- `python3 scripts/validate_repo.py` 合格を確認

---

> **Note:** Do not include sensitive information (passwords, tokens, personal data, etc.) in this file.
