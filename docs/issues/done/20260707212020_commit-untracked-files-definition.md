---
title: commit: untracked ファイルの「変更」定義への包含を明文化
status: open
created: 2026-07-07 21:20:20
tags: docs,loop-rehearsal
source: fixture 実行者レポート（skillreg capture セッション）
---

## 概要

回帰 fixture の白紙実行者（cm-003）が報告した曖昧点: Phase 2 の abort 条件「No changes: Neither staged nor unstaged changes exist」が untracked ファイルを含むのか読み取れない。

skills/commit/SKILL.md に次を明文化する:
1. Phase 2 の No changes 判定における「変更」は staged + unstaged + **untracked** をすべて含む（untracked のみ存在する場合は abort しない）
2. Phase 3 の分類対象にも untracked ファイルを含む
3. ただし untracked ファイルが明らかにユーザーの作業成果物でないと判断できる場合（検証ハーネスの副産物・一時ファイル等）はコミット対象から除外してよく、その場合は除外した事実と理由を報告に含める

## 備考

受け入れ条件:
- Phase 2 / Phase 3 の該当箇所に上記が追記されている
- `python3 scripts/validate_repo.py` が合格する
- 編集対象は skills/commit/SKILL.md のみ

---

> **Note:** Do not include sensitive information (passwords, tokens, personal data, etc.) in this file.
