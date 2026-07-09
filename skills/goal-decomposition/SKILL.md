---
name: goal-decomposition
description: 大枠ゴール（例「コードベース全体を精査してリファクタリング完遂」）を Loop Readiness Dossier（自走可能性の型検査結果）にコンパイルし、既存の閉ループ基盤（goal-loop / loop-triage / issue polling / measurement spine）への配線先を機械的に決める入口スキル。主成果は「自走してはいけない断片を機械的に説明して止めること」。「goal-decomposition」「大枠ゴール」「ループに乗せたい」「自走できる状態にして」「dossier」「ゴールを分解して配線」「loop readiness」「このゴールを自動化できるか」で起動。compile（自然言語ゴール → dossier draft 生成）と validate（dossier を dossier_lint で検査）の 2 ワークフロー。出力は常に status: draft で、承認は人間が dossier を直接編集する。配線の実行はしない（型検査のみ）。本リポジトリ専用・Claude 版のみ。
---

# Goal Decomposition

自然言語の大枠ゴールを、機械検証可能な **Loop Readiness Dossier** にコンパイルする入口。

**共通契約（必読・直リンク）:** [../shared/references/goal-decomposition-pattern.md](../shared/references/goal-decomposition-pattern.md)

- Dossier Schema / 第一問決定木 / 5 軸 routing proof / status ライフサイクル /
  wire_to×exit_to matrix / proxy 許容条件 / supply gap playbook / 写像表はすべて契約側にある。
  本 SKILL.md は薄い orchestrator であり、契約の複製を書かない
- 分類軸の定義元: [fix-action-taxonomy.md](../shared/references/fix-action-taxonomy.md)（AUTO_FIX / NEEDS_JUDGMENT / REPORT_ONLY）
- 下流の消化側は [issue polling](../issue/SKILL.md) / [loop-triage](../loop-triage/SKILL.md) / [goal-loop](../goal-loop/SKILL.md)

## 不変条件（契約 §1 / §6）

1. **compile は配線を実行しない**。生成するのは `docs/loop/dossiers/{ts}_{slug}.json` + `.md` のみ
2. **compile の出力は常に `status: draft`**。approved は人間が dossier を直接編集して遷移させる
3. **approved は実行権限を与えない**（v1 は型検査のみ・lint は読み取り専用）
4. 観察できていない断片は confidence を盛らず inbox + `blocked_by` に落とす

## 実行契約

- スクリプトは絶対パスで呼ぶ: `python3 {skill_dir}/scripts/dossier_lint.py`。`{skill_dir}` は本 SKILL.md のディレクトリ、`{repo_root}` はリポジトリ root（通常 cwd）
- dossier 置き場: `docs/loop/dossiers/{timestamp}_{slug}.json`（canonical）+ 同名 `.md`（ビュー）
- secret_detect は CLI を持たない import-only モジュール（`detect_secrets` / `mask_secrets` を **import して使う**。「スクリプトを実行」とは書かない）

## ワークフロー選択

| 入力 | ワークフロー |
|------|-------------|
| 自然言語の大枠ゴール（「〜をループに乗せたい」「自走できる状態にして」） | compile |
| 既存 dossier の検査（「dossier を lint して」「validate」） | validate |

## compile — ゴール → dossier draft

### Step 1: 調査（スコープ限定）

goal と oracle_files 候補に関連するパスに調査を限定する。**full-tree scan はしない**。
コードベースで埋められるもの（既存センサー・oracle コマンド候補・SSOT）/ 契約から推定できるもの
（決定木の出口・写像先）は自分で埋める。

### Step 2: 断片分解と配線（決定木）

大枠ゴールを断片に割り、各断片に契約 §3 の第一問（完了条件か / 未達検出器か / 人間判断か）を適用して
`wire_to`（goal-loop / loop-triage / inbox / plan / reject）を決める。配線後に §4 の 5 軸で
`auto_fix_allowed` / `self_modification_risk` / `exit_to` を埋め、各断片 1 行の `routing_proof` を書く
（非 AUTO_FIX 断片は `why_not_auto_fix` 必須）。

- **proxy の扱い**（決定木に明示リーフはない）: 完了条件だが真の oracle を機械化できない断片は、
  §5.2 / §10 ③ の proxy / 中間 oracle を検討し、`human_limit_approved: false` + inbox 承認待ちで
  goal-loop に blocked 配線してよい。headless でも proxy **採用判断**は compile が下してよい
  （人間担保は承認ゲート = GD104 が持つ）
- **oracle.command は実在しなくてよい**（dossier は設計図であり実行しない）。未実装のコマンドは
  routing_proof か oracle 側に aspirational である旨を 1 語添える
- **oracle_files は verifier をロックする** — 「oracle の意味を定義する側」（検証スクリプト・テスト・
  期待値。[convergence-pattern §2](../shared/references/convergence-pattern.md) と同義）を列挙する。
  修正対象のターゲット文書はロック対象ではない（ターゲットが検証定義を兼ねる場合のみ含める）
- **exit_to の使い分け**（matrix 上どちらも合法なとき）: 常駐検出は `resident_sensor` を既定とし、
  恒久ブロックへ昇格させる意図が明確なときだけ `ci_gate` を選ぶ
- **measurement.metrics**: 未接続の新規計測は `proposed:` プレフィックスで明示し、既存計測名
  （events.jsonl / ledger 等）と区別して書く

### Step 3: 人間への 3 質問（headless 時はスキップ）

質問攻めにしない。人間には以下の 3 つだけ聞く（文言固定）:

1. **non-goals の確認**: 「このゴールに含めない範囲（自動化に載せない断片）は？ 例: {推定した non-goals}」
2. **proxy 限界承認**: proxy oracle を使う場合のみ「{oracle} は真の完了条件ではなく下限ゲートです。
   差分『{gap}』を承知で下限として承認しますか？」
3. **routing proof の差分承認**: 「{断片} を {wire_to} に配線しました（根拠: {proof}）。この配線でよいですか？」

**headless 時はユーザーへの確認をスキップして draft を出し**、未解決の承認事項を inbox エントリ +
`blocked_by` に記録する（状態ゲートが人間承認を担保するので compile が対話をブロックしない）。

### Step 4: secret redaction（契約 §9・import ベース）

書き出しパイプライン順序: **JSON 生成 → secret チェック → 検出時は中止 → 合格時のみ md 生成**。
実務手順: JSON はまず `.claude/tmp/goal-decomposition/` に一時ファイルとして書き、そこで検査する。
合格したら `docs/loop/dossiers/` へ配置し、検出したら一時ファイルを削除して中止する
（dossiers ディレクトリに検査前のファイルを置かない・検出時に残骸を残さない）。

- **自由文フィールド**（`goal.statement` / `inbox[].question` / `routing_proof` 等）は `mask_secrets` でマスク
- **構造フィールド**（`oracle_files` / hash 値 / `id`）は `detect_secrets` で**検出したら compile を中止**
  （マスクによる無言破壊をしない）

### Step 5: 書き出しと lint

1. `docs/loop/dossiers/{timestamp}_{slug}.json` を書く（`status: "draft"`）
2. md ビューを [dossier-template.md](references/dossier-template.md) 準拠で生成する。md は redaction 済み JSON からの
   **一方向生成** + 末尾に生成元 JSON の sha256 marker（tamper-evident）。md の手編集は禁止
3. `python3 {skill_dir}/scripts/dossier_lint.py docs/loop/dossiers/{timestamp}_{slug}.json` で検査する

### Step 6: 報告（summary-first）

```
## Goal Decomposition 結果: {slug}
| wire_to | 件数 |
|---------|------|
| goal-loop | N |
| loop-triage | N |
| inbox | N |
| plan / reject | N / N |

- inbox / blocked_by: {件数}
- secret チェック: {pass / 中止（該当フィールド）}
- lint: {全チェック合格 / error N・warn N}
- status: draft
- 次の一手: md（docs/loop/dossiers/{slug}.md）を読んで、承認するなら JSON を直接編集して status を approved に上げる
```

## validate — dossier の検査

```bash
python3 {skill_dir}/scripts/dossier_lint.py [docs/loop/dossiers/{slug}.json ...]
```

- 引数なしなら `docs/loop/dossiers/` 直下の全 `*.json` を検査する。特定 dossier の検査を頼まれたら
  そのパスだけを引数指定する（無関係な dossier を巻き込まない）
- 終了コード: `0` = pass（warn のみも 0）/ `1` = error 級 finding / `2` = 前提不成立
- error 級があれば finding を提示し、契約 §11 の rule 表を参照して修正案を出す（lint は修正しない）。
  検査結果はテキスト報告のみ — validate はファイルを一切書かない（writer は compile だけ）

## 合理化防止

| 言い訳 | 現実 |
|--------|------|
| 「この断片は明らかに自動化できるから approved で出そう」 | compile は draft しか出さない（不変条件 2）。承認は人間の仕事 |
| 「oracle が大きいけど proxy にして LLM judge で通そう」 | LLM judge の主観評価は GD201 で禁止。中間 oracle を足す（契約 §10 ③） |
| 「oracle_files は docs/** でまとめて楽したい」 | goal_loop verify は manifest 記録パス中心。明示列挙する（契約 §8・GD301） |
| 「secret っぽいけど構造フィールドだしマスクすれば通る」 | 構造フィールドはマスクせず compile 中止（契約 §9）。無言破壊を作らない |

## Codex 版

なし（本リポジトリ専用の Claude 版のみ）。
