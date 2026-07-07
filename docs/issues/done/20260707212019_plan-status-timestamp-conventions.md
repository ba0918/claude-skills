---
title: plan: Completed 日時の出所と abandoned 行の日付粒度を明文化
status: open
created: 2026-07-07 21:20:19
tags: docs,loop-rehearsal
source: fixture 実行者レポート（skillreg capture セッション）
---

## 概要

回帰 fixture の白紙実行者（pl-002 / pl-003）が報告した曖昧点 2 件を skills/plan/SKILL.md に明文化する。

1. **Completed 日時の出所**: Status Update Workflow で Completed とする日時は「更新を実行した時点の現在時刻（`date` コマンド取得）」であると明記する（ユーザーの完了申告時刻を推定しない）
2. **abandoned アーカイブ行の日付粒度**: 未完了 Current Session を abandoned アーカイブする際の Started / Completed 列は、session-history.md の既存慣習（`YYYY-MM-DD`、時刻なし）に合わせると明記する

## 備考

受け入れ条件:
- Status Update Workflow と「Handling an unfinished Current Session」の該当箇所に上記 2 点が追記されている
- `python3 scripts/validate_repo.py` が合格する
- 編集対象は skills/plan/SKILL.md のみ

---

> **Note:** Do not include sensitive information (passwords, tokens, personal data, etc.) in this file.
