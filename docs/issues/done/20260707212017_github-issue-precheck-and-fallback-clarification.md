---
title: github-issue: Common Pre-checks と polling の関係 + gh repo view フォールバックの明文化
status: open
created: 2026-07-07 21:20:17
tags: docs,loop-rehearsal
source: fixture 実行者レポート（skillreg capture セッション）
---

## 概要

回帰 fixture の白紙実行者（gi-001）が報告した仕様曖昧点 2 件を skills/github-issue/SKILL.md（必要なら references/）に明文化する。

1. **Common Pre-checks 失敗と polling の関係**: `gh auth status` 等の pre-check 失敗時にワークフロー全体を terminate するのか曖昧。次の意味論で明文化する: 「Common Pre-checks の失敗は fail-closed であり polling tick を起動しない（`fail_closed` と同経路、error_kind は `tool_missing` 相当）。ただし GitHub アクセスを要しない確認（kill file 停止確認等）をユーザーが明示的に指示した場合に限り、pre-check 失敗を記録した上で該当確認のみ継続してよい」
2. **nameWithOwner 取得のフォールバック**: Common Pre-check step 3 の `gh repo view --json nameWithOwner` が失敗した場合、`fetch_git_remote_url()` と同順（`git remote get-url origin` を primary、gh を fallback）で取得してよいことを明記し、両経路の整合を保証する。

## 備考

受け入れ条件:
- 上記 2 点が skills/github-issue/SKILL.md の該当節に追記されている（references への複製はしない）
- 既存の fixture（gi-001）のシナリオ前提（「pre-check 失敗は記録の上で続行してよい」というユーザー明示）と矛盾しない
- `python3 scripts/validate_repo.py` が合格する
- 編集対象は skills/github-issue/ 配下のみ（他スキル・共有契約に触れない）

---

> **Note:** Do not include sensitive information (passwords, tokens, personal data, etc.) in this file.
