---
title: Polling Pattern Unification (local issue + github-issue)
created: 2026-04-08 15:04:18
tags: [polling, refactor, shared-pattern, ralph-loop]
status: 💡 Idea
---

# Polling Pattern Unification

## Summary

local `issue` スキルに polling 機構を追加して self-driving 化し、同時に既存の `github-issue` も同じ polling パターンに揃える。両者の共通契約を `skills/shared/references/polling-pattern.md` として確立し、各スキルは state adapter として実装する。

本質はラルフループ (https://github.com/snarktank/ralph) — 単一プロセスが kill されるまで延々 issue を消化し続けるパターン。`bypass-permissions` モードでの夜間/離席運用を主用途とする。

## Background / Motivation

- `github-issue` で得た atomic claim / lockfile / cleanup の知見を local issue にも流用したい
- 現状 local issue は「記録」までで自動消化フローがない
- ユーザーは離席時・夜間に溜まった issue を自動消化したい
- github-issue と local issue が drift しないよう、共通契約を先に固めるべき

## Design Decisions

### A. State 管理: ディレクトリベース (LLMファースト)

```
docs/issues/
  ready/                 ← 新規・リトライ待ち
  running/               ← claim 済み（実行中）
  done/                  ← 成功（月次で archives へ）
  failed/
    transient/           ← 環境要因、自動リトライ対象
    permanent/           ← 要人間判断
  archives/YYYY-MM/      ← 完了アーカイブ
  .STOP                  ← kill file
```

理由: `ls` 一発で状態が見える、POSIX rename が原子的、frontmatter パース不要、Bash と LLM が同じ語彙で扱える。

### B. 並列実行: parallel-cycle に委譲

polling 自身は worktree を管理しない。claim 済み issue リストを `claude-skills:parallel-cycle` に渡し、worktree 切り出しと並列実行はそちらに任せる。責務分離。

### C. ハイブリッドモード: --once / --loop

```
issue-polling --once        # 1 tick 実行して終了（/loop と組み合わせ）
issue-polling --loop        # 内蔵 while ループ（ラルフモード）
```

両モード共通の「1 tick 純関数」を内部実装として持ち、外側のループ戦略だけ切り替える。design-principles §1 (Compose) / §5 (DI) に整合。

### D. 安全ブレーキ（全部入れる）

- `.STOP` kill file（存在で即終了）
- `--max-iter`（デフォルト 50）
- `--max-wallclock`（デフォルト 8h）
- `--failed-streak`（連続失敗 N 回で自動停止、デフォルト 3）
- `--dry-run`（処理予定だけ表示、実行しない）
- SIGINT/SIGTERM trap → running を ready に戻す

### E. failed の二分

- **transient**: network / timeout / lock 競合 / rate limit → 自動リトライ可
- **permanent**: test fail / compile error / 矛盾 → 隔離、人間待ち

判定は cycle の終了コードと subprocess エラーパターンで自動分類。transient は frontmatter or 末尾追記でリトライ回数カウンタ管理、N 回超で permanent 昇格。

### F. done の月次アーカイブ

`docs/issues/archives/YYYY-MM/` に月次で move。polling 開始時に月跨ぎチェック。既存 issue スキルの archives 規約に整合。

### G. パラメータデフォルト

- `--max-parallel: 4`（複数プロジェクト並行運用前提、CPU 食いすぎず）
- `--max-iter: 50`
- `--max-wallclock: 8h`
- `--failed-streak: 3`

### H. github-issue 側の改修

共通契約に揃えるためのリファクタ:

1. フラグ統一: `--once`/`--loop`/`--max-*`/`--dry-run` を追加（現在 loop 前提）
2. failed 分類: `claude-failed` を `claude-failed-transient` / `claude-failed-permanent` に分割
3. SIGINT trap: claim 解放処理を共通仕様に合わせる
4. kill switch: ローカル `.STOP` ファイル参照を追加

## Architecture

```
shared/references/polling-pattern.md   ← 共通契約（NEW）
  ├─ フラグ仕様
  ├─ 状態機械の抽象（ready→running→done/failed/{transient,permanent}）
  ├─ 安全ブレーキ仕様
  ├─ tick 純関数のシグネチャ
  └─ SIGINT/SIGTERM ハンドラ仕様

skills/issue/                          ← state adapter: ファイルシステム（NEW polling）
  ├─ SKILL.md（polling workflow 追加）
  └─ references/polling-state.md（FS adapter 仕様）

skills/github-issue/                   ← state adapter: GitHub label（リファクタ）
  ├─ SKILL.md（共通仕様参照に変更）
  ├─ references/label-spec.md（既存）
  └─ references/polling-adapter.md（label adapter 仕様）

commands/issue-polling.md              ← NEW
commands/github-issue-polling.md       ← 既存、フラグ追加
```

design-principles 適合:
- §1 Compose: tick 純関数 + state adapter
- §4 Pure functions: tick / state transition
- §5 DI: state backend を差し替え可能
- §6 Open-Closed: 将来 Linear/Jira adapter 追加だけで対応

## Open Questions

- shared/polling-pattern.md は markdown 仕様書 + 擬似コードで十分か、それとも参考実装スクリプトも置くか
- transient リトライの間隔設計（exponential backoff? 固定?）
- 並列実行中に kill file が出現したらどうする（実行中分は走らせて新規 claim だけ止める? 即 kill?）

## References

- https://github.com/snarktank/ralph （ラルフループの元ネタ）
- skills/github-issue/SKILL.md（既存 polling 実装）
- skills/parallel-cycle/SKILL.md（worktree 並列実行基盤）
- skills/issue/SKILL.md（既存 local issue 管理）
- rules/design-principles.md
