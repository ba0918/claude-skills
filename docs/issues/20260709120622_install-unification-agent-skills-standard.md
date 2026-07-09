---
title: Agent Skills 標準準拠の配布統一
status: closed
created: 2026-07-09 12:06:22
closed: 2026-07-10 01:56:27
tags: distribution,agent-skills-standard,research,superseded
source: brainstorm session 2026-07-09（自己完結性と配布戦略）
---

## 結論

この issue は、配布方針を Agent Skills 標準の単一 `skills/` レイアウトへ寄せたため close する。

README は `gh skill` を主導線としつつ、Claude Code Plugin / Codex CLI Plugin も同じスキル本文を読む導線として案内している。今後はランタイム別のスキル本文を作らず、共通本文をプラットフォーム非依存に保つ。

## 残す運用

- `SKILL.md` と `references/` では固有ツール API 名やモデル名を避ける
- ランタイム差は `skills/shared/references/tool-mapping.md` に集約する
- 変更後は `python3 scripts/validate_repo.py` を実行する

## 反映済み

- 旧 dual 構造前提の本文を現行方針へ更新
- 旧移植コマンドの入口を削除
- 未移植バックログ issue を close
- `python3 scripts/validate_repo.py` 合格を確認

---

> **Note:** Do not include sensitive information (passwords, tokens, personal data, etc.) in this file.
