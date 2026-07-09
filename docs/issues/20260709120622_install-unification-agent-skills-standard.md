---
title: インストール方法を Agent Skills 標準準拠に寄せ、gh skill を主導線に配布統一する
status: open
created: 2026-07-09 12:06:22
tags: distribution,agent-skills-standard,research
source: brainstorm session 2026-07-09（自己完結性と配布戦略）
---

## 概要

現状のインストールは Claude Code = plugin marketplace（`claude plugin install`）、Codex = 独自 `install.sh`（`~/.codex/skills` へ symlink）の**2系統に割れている**。「どの LLM でも同じ方法でインストール」を目指し、2026年に確立した Agent Skills オープン標準 + 統一インストーラに寄せる。

## 壁打ちで固まった前提整理（最重要）

**「統一」は2種類あり、混同すると堂々巡りになる:**

- ❌ **変換ゼロ統一**（1ソースが変換なしでどこでも動く）= **不可能**。Agent Skills 標準が統一したのは「パッケージ形式（発見・読み込み）」だけで「実行意味論」は各ツール固有のまま。このリポジトリの request_user_input バグ修正（Codex では Plan mode 限定）が実証。
- ✅ **変換の自動化**（手動 dual 同期 → 生成 dual）= **可能、これが本命**。既存 `codex-sync` が半自動変換器（3層ルール: 機械的置換 / 構造的変換 / 要判断）。第1層（配置）・第2層（ツール名）は全自動化可能、第3層（意味判断: request_user_input→会話ターン等）だけ override / 手書きで残す。

## 2026年エコシステム状況（web リサーチ済み）

- **Agent Skills オープン標準**（Anthropic 2025/12/18 発表）: SKILL.md 形式が 30+ プラットフォーム共通（Claude Code / Codex / Gemini CLI / Copilot / Cursor / VS Code / Roo Code / Goose 等）
- 統一インストーラ4種:
  | ツール | 出自 | 特徴 |
  |--------|------|------|
  | **gh skill** | **GitHub 公式**（2026/4/16, CLI v2.90.0） | discover/install/manage/publish。`gh skill preview` で事前検査。awesome-copilot が公式マーケット。**このリポジトリは GitHub ホストなので最相性** |
  | npx skills | vercel-labs（2026/1〜） | 先行普及・68 agents 自動検出・skills.sh 中央ディレクトリ |
  | apm | microsoft | 依存管理厳格（apm.yml + lock）。外部依存ほぼ無い本リポジトリには過剰設計 |
  | openskills | numman-ali | universal loader（`npm i -g openskills`） |

## 壁打ちで固まった方針

**本質は「インストーラ選択」ではなく「Agent Skills 標準レイアウト準拠」**。準拠すれば4インストーラ全部から入れる（利用者が好きなものを使う）。

- **dual 構造は維持**: `skills/`↔`codex-skills/` は重複ではなく Claude/Codex 向けバックエンド実装。一本化すると差異が条件分岐 or 曖昧な自然言語に押し込まれるだけ。
- **主導線 = gh skill**（公式・GitHub ホストと最相性、`gh skill install ba0918/claude-skills`）、npx skills を併記。
- **apm は見送り**（外部依存ほぼ無しで lockfile/監査は過剰）。
- **将来の single source 化**を追うなら「ビルド時生成（共通ソース + target override）が1位」（Codex 評価）。実行時 shim は最不向き（意味差を吸収できない）。

## 次アクション（実行可能タスク）

1. **代表3スキルで実証 + 変換自動化率を実測**: 単純スキル / 対話含むスキル / sub-agent 使うスキルを選び、
   - gh skill（+ npx skills）で Claude版/Codex版を明示選択して配置・起動・更新・削除・誤 variant 混入を検証
   - `codex-sync` の変換で「機械変換できた割合 vs 手書きが残った第3層の割合」を測る
   - **判定基準**: 第3層 override が 1〜2割なら生成が勝つ（統一する価値大）／半分超えるなら手動 dual の方がマシ
2. 実証結果で「配布層だけ統一（dual 維持）」か「ビルド時生成で single source 化」かを全体展開前に判定する

## 見落としリスク（Codex 指摘）

- 最低共通分母化（Claude 固有の hooks / fork 能力が使いにくくなる）
- 導線を増やすほどサポート面積が線形膨張（skill本体/生成物/installer/loader の切り分け）→ **CI で全導入経路を検証できないまま「対応済み」表示にしない**
- 名前衝突（Claude版/Codex版を同名公開で中央キャッシュが誤 variant 選択）
- 標準の寿命・ベンダーロックイン（形式はオープンでも lockfile/registry/検出規則は実装固有）

## 受け入れ条件（この issue のゴール）

- 次アクション1の実証を代表3スキルで実施し、変換自動化率を数値で出す
- 「配布層統一 vs ビルド時生成」の判定を下す
- 判定に基づき README のインストール節を更新（gh skill 主導線 + Agent Skills 標準準拠の明記）

## 備考

- ② `empirical-prompt-tuning` の出典 mizchi/skills は apm エコシステムにいる（apm-usage スキル配布）。②と③は「外部スキルエコシステムとの接続」という点で関連。
- Codex セカンドオピニオン2回取得済み（前提への反論 / dual 維持+配布層統一の妥当性 / 破綻条件）。

---

> **Note:** Do not include sensitive information (passwords, tokens, personal data, etc.) in this file.
