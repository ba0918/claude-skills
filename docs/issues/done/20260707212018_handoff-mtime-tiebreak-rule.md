---
title: handoff: mtime 同秒タイ時のタイブレーク規則を明文化
status: open
created: 2026-07-07 21:20:18
tags: docs,loop-rehearsal
source: fixture 実行者レポート（skillreg capture セッション）
---

## 概要

回帰 fixture の白紙実行者（ho-001 / ho-002）が報告した曖昧点: docs/handoff/ 配下のファイルの mtime が同一（秒精度で判別不能）の場合、「最新」の判定が一意に決まらない。

skills/handoff/SKILL.md の Restore Workflow Phase 1（File Discovery）と List Workflow の両方に、次のタイブレーク規則を追記する: 「mtime で順序が決まらない場合は、ファイル名先頭のタイムスタンプ（YYYYMMDD_HHMMSS）の降順をタイブレークとして使う」。

## 備考

受け入れ条件:
- Restore Phase 1 と List Workflow の両節にタイブレーク規則が明記されている
- `python3 scripts/validate_repo.py` が合格する
- 編集対象は skills/handoff/SKILL.md のみ

---

> **Note:** Do not include sensitive information (passwords, tokens, personal data, etc.) in this file.
