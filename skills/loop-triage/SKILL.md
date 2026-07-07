---
name: loop-triage
description: リポジトリの問題をセンサー（validate_repo / ledger --check / context-audit 等）で検出し、finding を冪等化・admission 分類して docs/issues/ready/ キューに自動投入するループ中枢スキル。AUTO_FIX 級のみ enqueue し、ループ定義ファイルに触れる変更は fixture 非保有なら inbox に降格する自己修飾ゲートを持つ。「loop-triage」「ループトリアージ」「センサー実行して issue 化」「finding をキューに積んで」「ループ中枢」「自己修飾ゲート」で起動。issue polling（消化側）の上流に位置する供給側。本リポジトリ専用。
---

# Loop Triage

センサーが検出した finding を、人手を介さず安全に polling キューへ供給する。
**共通契約（必読・直リンク）:** [../shared/references/loop-engineering.md](../shared/references/loop-engineering.md)

- Finding Schema / Identity / Admission 表 / 自己修飾ゲートの定義はすべて契約側にある。
  本 SKILL.md は薄い orchestrator であり、契約の複製を書かない
- 分類軸の定義元: [fix-action-taxonomy.md](../shared/references/fix-action-taxonomy.md) /
  [severity-and-verdicts.md](../shared/references/severity-and-verdicts.md)
- キューの消化側は [issue polling](../issue/SKILL.md)（[polling-pattern.md](../shared/references/polling-pattern.md) 準拠）

## 不変条件（契約 §1 / §6）

1. **Triage は修正しない**。生成するのは issue ファイル / inbox 追記 / digest のみ
2. `REPORT_ONLY` はいかなる条件でも enqueue しない
3. 1 実行の enqueue は `--max-enqueue`（default 5）まで。超過は inbox 降格 + 明示報告（silent cap 禁止）
4. ルーティングは純関数（`admission.py`）の判定に従う。LLM の裁量で昇格しない

## 実行契約

- スクリプトは絶対パスで呼ぶ: `python3 {skill_dir}/scripts/<name>.py`。`{skill_dir}` は本 SKILL.md のディレクトリ、`{repo_root}` はリポジトリ root（通常 cwd）
- 中間 JSON は `.claude/tmp/loop-triage/{datetime}/` に置く（git-ignored）
- baseline は `.claude/loop-baseline.json`（commit 対象、opaque ID のみ。契約 §3.3）

## ワークフロー選択

| 入力 | ワークフロー |
|------|-------------|
| 「トリアージして」「センサー回して」（引数なし / `run`） | run |
| `--dry-run` | run（Step 5 以降をスキップし decisions のみ提示） |
| `baseline`（「現状を意図的差分として確定して」） | baseline |
| `status`（「inbox 見せて」「キュー状況は」） | status |

## run — センサー → トリアージ → 投入

### Step 1: 準備

```bash
TS=$(date +%Y%m%d%H%M%S)
OUT=.claude/tmp/loop-triage/$TS
mkdir -p $OUT
```

### Step 2: 機械センサー実行

```bash
python3 {skill_dir}/scripts/sensors.py --repo-root {repo_root} --out $OUT/findings-mech.json
```

LLM センサーの取り込み（opt-in）: `--context-audit PATH` が指定された場合、context-audit の
findings JSON を `sensors.py` の `map_context_audit` で写像して結合する。**loop-triage が
context-audit 等を自動起動することはない**（センサーの実行タイミングは人間または各スキルの運用に従う）。

### Step 3: トリアージ判定

```bash
python3 {skill_dir}/scripts/triage.py $OUT/findings-*.json \
  --repo-root {repo_root} --baseline .claude/loop-baseline.json \
  --out $OUT/decisions.json [--max-enqueue 5]
```

`triage.py` は薄い合成層で、判定はすべて純関数（`finding_identity.py` / `admission.py`）が行う。
自己修飾ゲートの影響スキル解決は `skills/skill-regression/scripts/ledger.py --impact` に委譲される。

### Step 4: decisions の確認

`decisions.json` の各エントリ: `{finding, finding_id, route, reason?, gate?, affected_skills?, missing_fixtures?}`。
`--dry-run` の場合はここで route 別サマリを提示して終了する。

### Step 5: enqueue（route = "enqueue" のみ）

各 enqueue 対象について [issue の Slug 定義](../issue/SKILL.md#slug-definition)に従い issue を生成する:

1. slug: `{yyyymmddhhmmss}_{suggested_title の英語 kebab 化}`（非 ASCII は意味ベース英訳）
2. `docs/issues/ready/{slug}.md` を [issue-template](../issue/references/issue-template.md) 準拠で作成し、
   frontmatter に以下を**追加**する:
   ```yaml
   finding_id: {finding_id}
   tags: loop-triage,{sensor}
   gate: skill-regression   # decisions に gate がある場合のみ
   ```
   本文の概要 = what + why、備考 = 受け入れ条件（finding の解消を機械的に確認する方法。例: 該当センサーの再実行で当該 finding_id が消えること）
3. `docs/issues/issue-status.md` に行を追加（存在しなければ issue スキルのテンプレで新規作成。
   Summary のパイプ・改行エスケープ規則は [issue SKILL.md](../issue/SKILL.md) Create Workflow Step 7 に従う）

書き出す前に全文を `python3 skills/shared/scripts/secret_detect.py` 相当のチェックに通し、
検出があればその finding を enqueue せず inbox に降格する（理由: "secret-suspect"）。

### Step 6: inbox（route = "inbox"）

`docs/loop/inbox.md` に追記する（無ければ見出し `# Loop Inbox` で新規作成）:

```markdown
## {YYYY-MM-DD HH:MM} {finding_id} [{sensor}/{rule}] {suggested_title}
- severity: {severity} / fix_action: {fix_action} / 降格理由: {reason または "-"}
- where: {where.path}
- what: {what}
- 対応方法: 人間が判断 → 対応するなら `/claude-skills:issue-create` で issue 化、意図的差分なら loop-triage baseline へ
```

### Step 7: 報告（summary-first）

```
## Loop Triage 結果
| route | 件数 |
|-------|------|
| enqueue（ready/ へ投入） | N |
| inbox（人間判断待ち） | N |
| digest | N |
| duplicate / suppressed | N / N |

- enqueue した issue: {slug のリスト（gate 付きは明示）}
- budget 超過による降格: {あれば件数}
- 次の一手: enqueue 分は issue polling が消化する（/claude-skills:issue-polling）
```

## baseline — 意図的差分の確定

現在の findings を suppress リストに確定する（契約 §3.3。opaque ID のみ・first-run 時の一括受け入れ用途）:

```bash
python3 {skill_dir}/scripts/triage.py $OUT/findings-*.json \
  --repo-root {repo_root} --update-baseline .claude/loop-baseline.json
```

実行前に AskUserQuestion で「何件を baseline 化するか」の確認を必ず取る（自走文脈では baseline 化しない）。

## status — 棚卸し

- `docs/loop/inbox.md` の未処理エントリ数と、`docs/issues/ready|running|failed` の件数を提示する
- `finding_id` 付き issue（loop-triage 由来）とそれ以外を区別して数える

## 合理化防止

| 言い訳 | 現実 |
|--------|------|
| 「この finding は明らかに直せるから NEEDS_JUDGMENT でも enqueue しよう」 | 昇格は禁止（契約 §4 不変条件 2）。判断が要るなら inbox が正しい置き場 |
| 「fixture が無いスキルだけど軽微な変更だから通そう」 | ゲート降格は網の有無で機械判定する。軽微かどうかの判断こそ人間の仕事 |
| 「digest ばかりで成果が無いから閾値を緩めよう」 | 成果はキュー投入数ではなく偽陽性ゼロの供給。緩めるなら契約改訂として明示的に行う |
| 「重複っぽいが微妙に違うので投入しよう」 | finding_id が違えば投入される。同 ID は duplicate — 迷う余地はない |

## Codex 版

なし（本リポジトリ専用の Claude 版のみ）。
