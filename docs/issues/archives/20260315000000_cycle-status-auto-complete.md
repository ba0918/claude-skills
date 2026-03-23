---
title: cycle 完了時に status.md を自動で Completed にする
status: open
created: 2026-03-15
tags: cycle, status, automation
source: docs/cycles/20260315193813_status-auto-migration.md
---

## 概要

cycle コマンドの Phase 3（サマリー生成）完了時に、status.md の Current Session を Completed に更新し session-history.md にアーカイブする処理が含まれていない。現状ではサマリーファイルの生成のみ行い、status.md は Planning のまま放置される。

cycle コマンドの Phase 3 に以下を追加すべき:
1. status.md の Current Session を `🟢 Completed` に更新
2. session-history.md にエントリーを追加
3. Current Session を `_No active session. Create a new plan to start._` にクリア

## 備考

cycle は plan-implement に委譲しているが、plan-implement 側でも status 更新が不十分な可能性がある。cycle コマンド自体の Phase 3 で確実に status 更新を行うのが安全。

---

> **Note:** Do not include sensitive information (passwords, tokens, personal data, etc.) in this file.
