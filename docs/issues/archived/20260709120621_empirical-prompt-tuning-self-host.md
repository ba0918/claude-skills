---
title: empirical-prompt-tuning をリポジトリ内に自炊してメタスキル群の自己完結性を回復する
status: closed
closed: 2026-07-09 14:10:00
resolution: implemented
created: 2026-07-09 12:06:21
tags: meta-skill,self-contained,license
source: brainstorm session 2026-07-09（自己完結性と配布戦略）
---

## 概要

このリポジトリのメタスキル群のうち `empirical-prompt-tuning` だけがリポジトリ外（`~/.claude/skills/`、ユーザーグローバル）に存在し、`codex-sync` / `trigger-eval` が「大規模移植後の実機チューニングに推奨」「姉妹スキル」として**外部スキルを参照**している。能動テスト系のペア（本文層 = empirical / 選択層 = trigger-eval）のうち trigger-eval だけがリポジトリ内にあり対称性が崩れている。これをリポジトリ内で完結させる。

## 壁打ちで固まった方針

**方向性: MIT クレジット付き自炊（正本移管）+ 計測系統合でオリジナリティ**

### 1. ライセンス（確認済み）
- 出典: https://github.com/mizchi/skills の `meta/empirical-prompt-tuning/`（SKILL.md 189行 + SKILL-ja.md + README.md、**スクリプト依存なし**）
- `meta/empirical-prompt-tuning/` に LICENSE.txt は**無い**。リポジトリ全体も SPDX license = none
- リポジトリ方針: 「明示ライセンスが無ければ MIT（オーナー裁量）」→ **実質 MIT 扱い**。コピー・改変・派生・再配布 OK、条件は著作権表示 + ライセンス文の保持（クレジット）
- ⚠️ 「at the owner's discretion」という含みがあるため、完璧を期すなら作者 mizchi に MIT 確認の一言を入れる選択肢あり（必須ではない）

### 2. 取り込み方（正本移管）
- リポジトリ内 `skills/empirical-prompt-tuning/` に配置し、**リポジトリ版を唯一の正本**にする
- グローバル版（`~/.claude/skills/empirical-prompt-tuning`）は削除 or リポジトリ版への symlink 化して**二重管理を終わらせる**
- SKILL.md は「説明書であると同時に実行エントリーポイント」なので、能動的なスキル入口を維持する（reference 格下げは禁止）

### 3. オリジナリティの出し方（単なるコピーにしない）
- **measurement spine への配線**: `measurement-identity.md`（5計測系統合）に empirical の結果を流す
- **skill-regression の fixture 生産手段として位置づけ**: CLAUDE.md に既にある「fixture の生産手段（empirical tuning / plan 受け入れ条件 / 手動設計）」思想を実配線する
- **trigger-eval（選択層）と empirical（本文層）を明示的に姉妹配置**して対称性を回復
- クレジット（出典 + MIT）を SKILL.md か LICENSE ファイルに明記

## 棲み分け（自炊時の設計注意）

| スキル | 測る対象 | 手法 | 時間軸 |
|--------|----------|------|--------|
| empirical-prompt-tuning | 本文実行の質 | 実行者に動かして両面評価・反復 | forward（能動テスト） |
| trigger-eval | 選択層（description→発火） | 判定 subagent で発火精度実測 | forward（能動テスト） |
| skill-improve | セッション摩擦 | 過去 JSONL から検出 | backward（受動分析） |

- skill-improve への吸収（案2）は役割が違う（受動分析 vs 能動テスト）ため不採用。無理に吸収すると skill-improve が単一責任を崩して肥大化する。
- Codex セカンドオピニオンも「自炊＝正本移管」を支持（reference 格下げ案は撤回済み）。

## 受け入れ条件（実装時）

- `skills/empirical-prompt-tuning/` として配置、クレジット（出典 + MIT）を明記
- グローバル版を削除 or symlink 化して正本を一本化
- `codex-sync` / `trigger-eval` の外部参照をリポジトリ内参照へ更新
- 計測系統合・fixture 生産手段としての配線を最低1つ実配線（単なるコピーで終わらせない）
- `python3 scripts/validate_repo.py` が合格
- README.md / CLAUDE.md のスキル表に追加

## 備考

- 実装コストは激安（189行、スクリプトなし）。技術的障壁はほぼゼロで、論点は棲み分けとオリジナリティの出し方だった。
- Codex 版への移植要否は別途判断（trigger-eval 同様に初版 Claude 版のみでも可）。

---

> **Note:** Do not include sensitive information (passwords, tokens, personal data, etc.) in this file.
