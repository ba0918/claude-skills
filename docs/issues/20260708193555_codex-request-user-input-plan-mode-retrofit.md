---
title: 既存 Codex スキルの request_user_input を Plan mode 限定バグとして retrofit（会話ターン + headless 降格へ）
status: open
created: 2026-07-08 19:35:55
tags: codex,bug,corpus-wide
source: codex-sync パイロット中の Codex 敵対レビュー → 事実確認（codex-cli 0.142.4）で確定
---

## 概要

Codex CLI 0.142.4 で `request_user_input` ツールは **Plan mode 限定**（default / exec モードでは使用不可）であることが実測で確定した。根拠:

- `codex features list` → `default_mode_request_user_input … under development / false`
- ソース → `allows_request_user_input(self) -> bool { matches!(self, Self::Plan) }`
- tool schema → "This tool is only available in Plan mode."
- バイナリ文字列 → "request_user_input is not supported in exec mode"

しかし `codex-skills/shared/references/tool-mapping.md` が `AskUserQuestion → request_user_input` と規定していたため、既存 Codex スキルが default/exec 実行時に request_user_input 呼び出しで詰まる潜在バグを抱えている。

**契約（tool-mapping.md / porting-rules.md）と新規3スキル（refactor / sweep-fix / systematic-debugging）は修正済み。** 本 issue は既存スキルへの retrofit を追跡する。

## 対象（実測: `grep -rl request_user_input codex-skills/*/SKILL.md`）

SKILL.md（8件）:
- codex-skills/brainstorm/SKILL.md
- codex-skills/commit/SKILL.md
- codex-skills/plan-reviewer/SKILL.md
- codex-skills/handoff/SKILL.md
- codex-skills/issue/SKILL.md
- codex-skills/team-cycle/SKILL.md
- codex-skills/problem-solving/SKILL.md
- codex-skills/iterate/SKILL.md

references（2件、EXTRA_SYNC_PAIRS 追跡対象）:
- codex-skills/shared/references/team-config.md
- codex-skills/plan-reviewer/references/review-dimensions.md

## 修正パターン（新規3スキルで適用済みの正典）

`request_user_input` への依存を除去し、以下に置換する:

> ユーザ確認を伴う分岐は **会話ターンで平文の質問**（選択肢は列挙して番号/短文で回答を促す）として尋ねる。`request_user_input` は Plan mode 限定のため使わない。**headless/exec で応答不能なら安全側デフォルト**（no-op / report-only / UNCERTAIN / 中断）に降格する。

- 各スキルの「Codex CLI ツールの使い分け」節（または冒頭のツール列挙）の `request_user_input` エントリを「会話ターンでの確認」に書き換える
- 本文中の「`request_user_input` で確認する」等を「会話ターンで確認する」に置換する
- **注意**: problem-solving / brainstorm は対話が本質のスキル。会話ターンでの平文 Q&A は default mode で成立するため機能は保たれるが、「headless 化しない」等の既存注記と矛盾しないこと

## 受け入れ条件

- 上記8 SKILL.md + 2 references から request_user_input 依存が除去され、意図的な「Plan mode 限定のため使わない」注記以外に呼び出しが残らない
- 各スキルの headless 降格ルールが明記されている
- `python3 scripts/validate_repo.py --update-manifest` 後に `python3 scripts/validate_repo.py` が合格する
- 修正後の各スキルを Codex 敵対レビューにかけ、request_user_input 起因の指摘が解消されていること（任意だが推奨）

## 備考

- 契約修正済み: tool-mapping.md（AskUserQuestion 変換先）/ skills/codex-sync/references/porting-rules.md（第1層）
- この bug は codex-sync パイロット（refactor 移植）中に Codex 敵対レビューが掘り当てた。Codex 版スキルの品質検証に Codex 自身を使う手法が有効であることの実証例

---

> **Note:** Do not include sensitive information (passwords, tokens, personal data, etc.) in this file.
