# Loop Engineering — Shared Contract（センサー → トリアージ → キュー投入）

> **⚠️ Warning:** 本契約は「リポジトリの問題を自律的に発見し、既存の polling ループに作業として供給する」
> 閉ループの中枢仕様である。変更は sensor / triage 実装（`skills/loop-triage/` 等）と
> [polling-pattern.md](polling-pattern.md) の全 adapter に影響しうる。スキーマ・admission 表・
> ゲート規則を変更する場合は、参照スキルの references と SKILL.md を同一 PR で同期更新すること。

---

## 1. Overview — 5 層の責務境界

Osmani 型の自走ループ（discover → delegate → verify → learn）を、本リポジトリの既存契約の**上流**に接続する。

| Layer | 責務 | 実装 |
|---|---|---|
| Sensor | リポジトリの問題を検出し、§2 Finding Schema の JSON を吐く | validate_repo.py / ledger --check / context-audit 等（§7） |
| Triage | identity 付与 → 冪等化 → admission 分類 → 投入/降格 | `skills/loop-triage/`（純関数 + 薄い orchestrator） |
| Queue | 作業の永続キュー | `.agents/artifacts/issues/ready/`（[polling-pattern.md](polling-pattern.md) FS adapter） |
| Executor | キュー消化・実装 | issue polling → parallel-cycle（既存） |
| Verifier | 変更の検証 | validate_repo CI + skill-regression ledger + trigger-eval（既存） |

**Triage は編集をしない**。issue ファイルの生成と inbox / digest への追記のみを行い、
コードや docs の修正は常に Executor（cycle）の仕事である。

---

## 2. Finding Schema

Sensor が出力する 1 件の finding。フィールド集合は不変（追加は本契約の改訂を要する）。

```
Finding {
  sensor:          str            # センサー識別子（例: "validate-repo", "context-audit", "ledger-check"）
  rule:            str            # センサー内のルール ID（例: "CA-D001", "sync", "stale"）
  severity:        BLOCK | WARN | INFO           # severity-and-verdicts.md の定義に従う
  fix_action:      AUTO_FIX | NEEDS_JUDGMENT | REPORT_ONLY   # fix-action-taxonomy.md の定義に従う
  where:           { path: str, line?: int }     # 検出位置。identity には path のみ使う（§3）
  what:            str            # 何が問題か（1 行、secret redaction 済みであること）
  why?:            str            # なぜ問題か（任意）
  suggested_title: str            # issue 化する場合のタイトル案
  affected_paths:  [str]          # 修正が触れると想定されるファイル（自己修飾ゲート §5 の入力）
}
```

- severity / fix_action の意味論は定義元（[severity-and-verdicts.md](severity-and-verdicts.md) /
  [fix-action-taxonomy.md](fix-action-taxonomy.md)）に従い、本契約で再定義しない
- `what` に secret・PII を含めてはならない（sensor 側の責務。`skills/shared/scripts/secret_detect.py` を利用可）
- fix_action 不明・欠落の finding は **REPORT_ONLY に正規化**する（fail-safe）

---

## 3. Finding Identity & 冪等化

センサーは毎回同じ finding を再検出する。冪等化がなければループは同じ issue を毎朝積む。

### 3.1 Stable Finding ID

```
finding_id = sha256(f"{sensor}|{rule}|{where.path}|{what}")[:16]
```

- **行番号を含めない**（行移動で ID が変わる context-audit baseline v1 の既知の限界への対策。
  同一ファイル内の同種 finding は `what` の差で区別される）
- `what` は redaction 済みかつ hash 化されるため、ID は opaque（baseline に commit しても機密が漏れない）

### 3.2 二重投入防止（queue dedup）

- enqueue する issue の frontmatter に `finding_id: <hex16>` を必ず記録する
- Triage は投入前に `.agents/artifacts/issues/` 配下（`ready/` `running/` `failed/**` および `*.md` 直下）を走査し、
  同一 `finding_id` を持つ open issue が存在すれば **duplicate として投入しない**（件数のみ報告）
- `archives/` は照合対象に**含めない**（解決済みの問題が再発したなら新 issue が正しい）

### 3.3 Baseline suppression（意図的差分）

- `.claude/loop-baseline.json` に suppress する finding_id を格納する（**opaque ID のみ、検出値・本文は絶対に載せない**。
  形式・運用は [context-audit の baseline](../../context-audit/references/baseline-format.md) と同一思想、スキーマも同じ `{version, suppressions[]}`）
- suppress された finding は**件数のみ報告**する（silent truncation 禁止）

---

## 4. Admission Policy（fix_action × severity → route）

finding をどこへ流すかは以下の**純関数ルーティング**で決める。LLM の裁量を挟まない。

| fix_action \ severity | BLOCK | WARN | INFO |
|---|---|---|---|
| `AUTO_FIX` | enqueue | enqueue | digest |
| `NEEDS_JUDGMENT` | inbox | inbox | digest |
| `REPORT_ONLY` | digest | digest | digest |

| Route | 意味 |
|---|---|
| `enqueue` | `.agents/artifacts/issues/ready/` に issue を生成し、polling ループの消化対象にする |
| `inbox` | `.agents/artifacts/loop/inbox.md` に追記し、人間の判断を待つ（自動では絶対に進めない） |
| `digest` | 実行レポートに記載するのみ |
| `duplicate` / `suppressed` | 投入せず件数のみ報告（§3） |

**不変条件:**

1. `REPORT_ONLY` はいかなる条件でも enqueue しない（削除・本文書き換え・secret 対応の非自動化を
   fix-action-taxonomy から継承する）
2. ルーティングに使う fix_action / severity は **sensor の申告値**であり、Triage が昇格させてはならない
   （降格 = 安全側への変更のみ許可。§5 のゲート降格が唯一の変更点）
3. 1 回の triage 実行で enqueue できる件数は `max_enqueue_per_run`（default **5**）まで。
   超過分は inbox に降格し、超過があった事実を必ず報告する（silent cap 禁止）

---

## 5. Self-Modification Gate（自己修飾ゲート）

このループの Executor（cycle）は、ループ自身を定義するファイル（SKILL.md・共有契約・validate スクリプト）を
編集できる。無条件に許すと「調律済みの挙動」が無検証で書き換わっていく。

### 5.1 loop-defining ファイル

以下の glob に一致するファイルは **loop-defining** とする:

```
skills/*/SKILL.md
skills/*/references/**
skills/shared/**
commands/**
scripts/validate_repo.py
.claude/review-rules.md
```

### 5.2 ゲート規則（enqueue 時の降格）

`affected_paths` に loop-defining ファイルを含む finding は、enqueue する前に
[skill-regression](../../skill-regression/SKILL.md) の依存グラフ（`dep_graph.py`）で影響スキルを逆引きし:

- 影響スキルの**すべて**が fixture（`fixtures.json`）を持つ → enqueue 可。
  issue frontmatter に `gate: skill-regression` を付与する
- 影響スキルに fixture 非保有のものが 1 つでもある → **AUTO_FIX でも inbox に降格**する。
  降格理由（fixture 非保有スキル名）を inbox エントリに明記する

> 原則: **回帰の安全網が張られている範囲でだけ自己修飾を自動化する**。網のない場所は人間が判断する。
> 自動化を広げる正攻法はゲートを緩めることではなく fixture カバレッジを増やすことである。

### 5.3 下流の機械的強制

ゲートは prose の約束ではなく既存 CI で強制される:

- `gate: skill-regression` 付き issue の cycle が挙動面を変更すると、`ledger.py --check` が
  CI で fail する（[skill-regression](../../skill-regression/SKILL.md) の既存ゲート）。
  cycle は完了前に run → `--update`（または理由付き `--accept`）を済ませなければ main に入れない
- description を変更した場合は trigger-eval の再計測を推奨する（発火面の回帰は ledger では捕捉されない）

---

## 6. Safety

- Triage 自体の自走化（定期実行）は [polling-pattern.md](polling-pattern.md) の安全ブレーキ
  （kill file / max_iter / max_wallclock / failed_streak、cron 運用は §6.5 Tick Session）に従う。
  ブレーキのない自律ループはこのリポジトリに追加しない（[orchestration-patterns.md](orchestration-patterns.md) 支配原則 3）
- Triage の出力はすべて追記・生成のみ（issue 生成 / inbox 追記 / digest）。**既存ファイルの削除・
  書き換えを行わない**（唯一の例外は issue-status.md への行追加）
- inbox・digest に secret を書かない（sensor の redaction を信頼せず、Triage 側でも
  `secret_detect.py` を通してから書き出す）

---

## 7. Sensor Adapter 契約

sensor は「§2 の Finding JSON 配列を stdout または指定ファイルに吐ける」ものなら何でもよい。

| Sensor 種別 | 例 | 備考 |
|---|---|---|
| 機械センサー（決定的・LLM 不使用） | validate_repo.py の違反、`ledger.py --check` の stale、`static_collisions.py` の衝突ペア | 変換 adapter（`sensors/*.py`）が出力を Finding JSON に正規化する |
| LLM センサー | context-audit / doc-check / doc-audit / skill-improve | 各スキルの findings JSON を Finding Schema へ写像する。fix_action は各スキルの申告値をそのまま使う |

- sensor は**検出のみ**を行い、修正しない（Triage の不変条件と同じ）
- 新しい sensor の追加は adapter script の追加のみで済むこと（Open-Closed。Triage 本体・admission 表は不変）

---

## 8. 参照

- [polling-pattern.md](polling-pattern.md) — Queue / Executor 層の契約
- [fix-action-taxonomy.md](fix-action-taxonomy.md) / [severity-and-verdicts.md](severity-and-verdicts.md) — 分類軸の定義元
- [orchestration-patterns.md](orchestration-patterns.md) — 自律ループの安全ブレーキ原則
- [verification-gate.md](verification-gate.md) — Executor 側の完了前検証
- `skills/skill-regression/` — 自己修飾ゲートの依存グラフと CI 強制
