---
title: status.md の Session History が肥大化する問題
status: open
created: 2026-03-14
tags: improvement
source: docs/cycles/20260314204522_issue-management.md
---

## 概要

cycle を回すたびに Session History に履歴が蓄積され、LLM がコンテキストを消費する。issue-status.md と同様のアーカイブパターンの導入を検討すべき。

## 備考

issue-status.md では archives/ ディレクトリに完了済み issue を移動して肥大化を防ぐ設計にした。status.md にも同様のパターン（完了済みセッションのアーカイブ）を適用することで、コンテキスト消費を抑えられる。

---

> **注意:** センシティブな情報（パスワード、トークン、個人情報等）をこのファイルに記載しないでください。
