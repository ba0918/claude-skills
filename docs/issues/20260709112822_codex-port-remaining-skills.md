---
title: 未移植 Claude スキルの Codex 移植要否検討
status: open
created: 2026-07-09 11:28:22
tags: codex,port,backlog
source: session 2026-07-08 マージ後の棚卸し
---

## 概要

Claude 版のみで Codex 未移植のスキルが11個ある。移植要否を性質で分類した。

### 移植不要（8個）— メタ / 本リポジトリ専用 / レガシー移行

| スキル | 未移植の理由 |
|--------|------|
| `codex-sync` | Claude→Codex 移植メタスキルそのもの。Codex 版を作るのは自己矛盾 |
| `skill-improve` | セッションデータからスキル改善するメタスキル |
| `skill-regression` | スキル挙動の回帰ハーネス（本リポジトリ専用） |
| `loop-triage` | センサー→トリアージ→キュー投入（本リポジトリ専用） |
| `goal-decomposition` | ゴール→Dossier コンパイラ（本リポジトリ専用） |
| `trigger-eval` | description 発火精度の実測メタスキル |
| `context-audit` | 指示ファイル・メモリの棚卸し監査（初版 Claude 版のみ） |
| `migrate-cycles-to-plans` | レガシー移行。一回限りでほぼ不要 |

### 移植候補（3個）— 汎用スキル

| スキル | 役割 | 判断軸 |
|--------|------|--------|
| `doc-audit` | docs 内アーティファクトの横断監査 | Codex 側で docs 運用するか |
| `generate-review-rules` | プロジェクト固有レビュールール生成 | Codex 側でレビュー系を使うなら下地に |
| `github-issue` | GitHub issue polling→PR 自走 | Codex 側で GitHub issue 自走するか（issue の FS 版は移植済み） |

## 備考

- 判断基準: Codex 側でその運用（docs 監査 / レビュールール生成 / GitHub issue 自走）を行う予定があるかどうか。予定がなければ全てスルーで問題ない。
- 実施する場合は `codex-sync` スキル（Claude 版あり）で移植可能。移植後は Codex 敵対レビューで検証する運用が確立済み。
- 今すぐ着手する話ではなくバックログとして記録。移植要否を先に決めてから着手する。

---

> **Note:** Do not include sensitive information (passwords, tokens, personal data, etc.) in this file.
