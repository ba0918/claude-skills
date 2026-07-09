# Goal Decomposition — Shared Contract（大枠ゴール → Loop Readiness Dossier の翻訳層）

> **⚠️ Warning:** 本契約は既存の閉ループ 4 契約
> （[loop-engineering.md](loop-engineering.md) 供給 / [convergence-pattern.md](convergence-pattern.md) 収束 /
> [polling-pattern.md](polling-pattern.md) 消化 / [measurement-identity.md](measurement-identity.md) 計測）の
> **上流「翻訳層」**である。既存契約を再定義せず、dossier の各フィールドを既存契約の語彙に**写像**する
> （§7 写像表）。独自語彙を増やさない。Dossier Schema / 決定木 / rule 表を変更する場合は
> `skills/goal-decomposition/` の SKILL.md・`scripts/dossier_lint.py`・`references/dossier-template.md` を
> 同一 PR で同期更新すること。

分類軸の定義元: [fix-action-taxonomy.md](fix-action-taxonomy.md)（AUTO_FIX / NEEDS_JUDGMENT / REPORT_ONLY） /
[severity-and-verdicts.md](severity-and-verdicts.md)。

---

## 1. 目的と非目的

**目的**: 自然言語の大枠ゴール（例:「コードベース全体を精査してリファクタリング完遂」）を、機械検証可能な
**Loop Readiness Dossier**（自走可能性の型検査結果）にコンパイルする。主成果は「**自走してはいけない断片を
機械的に説明して止めること**」— 願望を願望のまま自動化に流さない。

**非目的（v1 スコープ外）:**

- 配線の**実行**（goal-loop 起動 / sensor adapter 生成 / inbox 自動起票）はしない。dossier は「型検査結果」であり
  実行権限を与えない（§6）。特に inbox は loop-triage の route 結果であり、writer を増やさない
- dossier をイベント化して `docs/loop/events.jsonl` に載せることはしない（measurement-identity 契約の
  閉 enum 改訂が必要なため v1 スコープ外）

---

## 2. Dossier Schema v1（契約・テスト・lint の単一ソース）

契約・fixture・lint 実装の 3 者が暗黙スキーマでドリフトしないよう、canonical キー階層をここで固定する。
**未知フィールドは無視**（前方互換）。dossier は **JSON canonical + md レポートの 2 層**で、lint は JSON のみを
対象とし、md はビュー（生成物）扱い。置き場は `docs/loop/dossiers/{timestamp}_{slug}.json` + 同名 `.md`。

```jsonc
{
  "schema_version": 1,               // int 必須
  "status": "draft",                 // enum: draft | approved | superseded | rejected
  "superseded_by": null,             // status: superseded のとき必須（後継 dossier ファイル名）
  "goal": {
    "statement": "…",
    "non_goals": ["…"],              // 空なら GD302 warn
    "ssot": "…"                      // SSOT 宣言（何が正の情報源か）
  },
  "oracles": [{
    "id": "oracle:slug",             // id は全ブロック横断で一意（GD006）
    "type": "true",                  // enum: true | proxy
    "command": "…",                  // 判定コマンド（convergence-pattern の oracle に写像）
    "oracle_files": ["docs/x.md"],   // repo 相対の明示列挙（空/glob のみ → GD301 warn、絶対パス/secret → GD203 error）
    "owner": "…",                    // 所有権
    "proxy": {                       // type: proxy のとき必須（§5 → GD201）
      "gap_from_true_goal": "…",     // 真の完了条件との差分
      "failure_modes": "…",          // 破れるケース
      "human_limit_approved": false, // 人間の限界承認
      "hash_lock": true,             // ハッシュロック可能
      "post_completion_human_check": true,
      "judge_type": "mechanical"     // "llm_subjective" は GD201 error
    }
  }],
  "fragments": [{
    "id": "frag:slug",
    "wire_to": "goal-loop",          // enum: goal-loop | loop-triage | inbox | plan | reject
    "exit_to": "ci_gate",            // enum: ci_gate | resident_sensor | dissolve
    "routing_proof": "1行の根拠",     // approved で欠落 → GD102 error
    "auto_fix_allowed": false,
    "why_not_auto_fix": "…",         // auto_fix_allowed: false のとき必須（§4 → GD102）
    "self_modification_risk": "low", // enum: low | high。high × auto_fix_allowed=true → GD202 error
    "blocked_by": ["inbox:q1"]       // 参照整合は GD005
  }],
  "sensors": [{
    "id": "sensor:slug",
    "rules": ["…"],                  // 採用 rule 群の明示（責任範囲の無限化を防ぐ）
    "findings_policy": {
      "fix_action": "REPORT_ONLY",   // enum: AUTO_FIX | NEEDS_JUDGMENT | REPORT_ONLY（fix-action-taxonomy に写像）
      "enqueue": false               // fix_action: REPORT_ONLY かつ enqueue: true → GD101 error
    }
  }],
  "inbox": [{
    "id": "inbox:q1",
    "question": "…",
    "reclassify_when": "…"           // 再分類条件（この問いをいつ oracle/sensor に格上げできるか）
  }],
  "measurement": {
    "metrics": ["…"],                // 既存計測値の名前で書く（measurement-identity に写像）
    "stop_conditions": ["…"]
  }
}
```

必須ブロックは **`goal` / `oracles` / `sensors` / `inbox` / `measurement` の 5 種 + `schema_version`**（GD001）。

---

## 3. 第一問決定木（各断片の配線先の導出）

大枠ゴールを**断片**に割り、各断片に**最初にこう問う**:

```
Q1. この断片は「完了条件」か / 「未達検出器」か / 「人間判断」か？
    ├─ 完了条件（真になれば達成と言える）
    │     → Q2. 機械検証可能な oracle にできるか？
    │            ├─ できる            → wire_to: goal-loop（convergence-pattern の oracle）
    │            └─ oracle が大きすぎて作業単位に割れない（decomposition gap）
    │                                 → wire_to: plan（中間 oracle にも割れず、人手の plan/cycle 直行）
    ├─ 未達検出器（「まだ達成していない」を検出し続けるもの）
    │     → Q3. Finding Schema（loop-engineering §2）に適合するか？
    │            ├─ 適合            → wire_to: loop-triage（sensor として供給）
    │            └─ 適合しない       → wire_to: inbox（人間が検出方法を設計するまで保留）
    └─ 人間判断（自動化できない / してはいけない）
          → Q4. 自動化して**よい**判断か？
                 ├─ よい（保留すれば後で機械化できる）→ wire_to: inbox（reclassify_when 付き）
                 └─ 自動化に流してはいけない          → wire_to: reject（non-goals 行き）
```

**自動修正可否（AUTO_FIX 等）は finding の属性であって断片の属性ではない**。第一問で配線を決めた**後**、
断片の `auto_fix_allowed` / `self_modification_risk` を評価する（§4）。oracle-first（観測可能か?）から
始めると sensor 化できる断片を捨てるため、必ず「完了条件 / 未達検出器 / 人間判断」から問う。

`wire_to` の 5 値の導出:

| 値 | 決定木の出口 | 意味 |
|----|-------------|------|
| `goal-loop` | Q2 = できる | 完了条件を機械検証可能 oracle にして goal-loop で収束させる |
| `loop-triage` | Q3 = 適合 | 未達検出器を Finding Schema 準拠の sensor として loop-triage に供給 |
| `inbox` | Q3 = 不適合 / Q4 = よい | 人間の判断・設計を待つ（reclassify_when で後の格上げ条件を明示） |
| `plan` | Q2 = decomposition gap | oracle が大きすぎ中間 oracle にも割れない → 人手の plan/cycle 直行 |
| `reject` | Q4 = 流してはいけない | non-goals 行き。自動化に載せない断片 |

> **フィールド名の注意**: 断片の配線先は `wire_to` と命名する。loop-engineering §4 の `route`
> （finding の行き先 enum: enqueue/inbox/digest/…）とは**別物**。`wire_to` は goal 断片 → サブシステム選択、
> `route` は finding → キュー選択。名前衝突を避けるため `route` は使わない。

---

## 4. 5 軸 routing proof

各断片は 5 軸で評価し、**スコア表ではなく 1 行の routing proof** を持つ:

| 軸 | dossier フィールド | 用途 |
|----|-------------------|------|
| 機械検証可能性 | oracle の `command` / `type` | 決定木 Q2 |
| finding 化可能性 | sensor の `rules` / `findings_policy` | 決定木 Q3 |
| 自動修正許容度 | `auto_fix_allowed` + `why_not_auto_fix` | admission（loop-engineering §4） |
| 自己修飾リスク | `self_modification_risk` | 危険組み合わせ検査（GD202） |
| 計測可能性 | `measurement.metrics` | stop condition の観測 |

- `routing_proof` は各断片 1 行で「なぜこの `wire_to` か」を書く（`status: approved` では必須 = GD102）
- **非 AUTO_FIX 断片には「なぜ AUTO_FIX でないか」を必須**にする（`auto_fix_allowed: false` → `why_not_auto_fix`
  必須 = GD102）。「安全のため保留」を明文化させ、暗黙の保留を禁じる
- **危険組み合わせ**（5 軸検査の機械化）: `self_modification_risk: high` かつ `auto_fix_allowed: true` は
  GD202 error。回帰網のない自己修飾を自動修正に載せない（loop-engineering §5 自己修飾ゲートの前段）

### 4.1 wire_to × exit_to compatibility matrix（GD103）

`exit_to`（断片が最終的にどう「卒業」するか）は `wire_to` と整合しなければならない。**✓ のみ許可**:

| wire_to \ exit_to | ci_gate | resident_sensor | dissolve |
|-------------------|:-------:|:---------------:|:--------:|
| `goal-loop`       |    ✓    |        ✗        |    ✓     |
| `loop-triage`     |    ✓    |        ✓        |    ✗     |
| `inbox`           |    ✗    |        ✗        |    ✓     |
| `plan`            |    ✗    |        ✗        |    ✓     |
| `reject`          |    ✗    |        ✗        |    ✓     |

導出根拠:

- `goal-loop`（完了条件）は達成後に **ci_gate**（恒久的な回帰ゲートへ移管）か **dissolve**（一度きりの達成で
  維持不要なら解散）になる。resident_sensor は sensor 用の出口であり完了条件には不適合
- `loop-triage`（未達検出器）は **resident_sensor**（常駐 polling）か **ci_gate**（CI ゲートへ昇格）になる。
  検出器が dissolve する（=検出をやめる）のは矛盾
- `inbox` / `plan` / `reject` は下流サブシステムに常駐しない一時的断片なので **dissolve** のみ。特に
  `inbox × ci_gate` や `reject` への非 dissolve 出口は決定木と矛盾する配線として GD103 で止める

> matrix はこの表を single source of truth とし、`dossier_lint.py` の `_COMPAT` と `test_dossier_lint.py` の
> catalog-sync テストで一致を保証する。

---

## 5. status ライフサイクルと proxy oracle 許容条件

### 5.1 status ライフサイクル（人間ゲートは状態で止める）

dossier は `status`（`draft` / `approved` / `superseded` / `rejected`）を持つ。**ユーザー確認の必須箇所を
広げない**（headless 互換）。承認は人間が dossier を直接編集して `draft → approved` に遷移させる。

- **compile の出力は常に `draft`**（compile が approved を出すことは絶対にない）
- lint は状態不変条件を強制する: `approved` なのに `routing_proof` 欠落（GD102）/ `approved` なのに
  未解決 `blocked_by` 残存（GD104）/ `superseded` なのに `superseded_by` 欠落（GD104）/
  status = `rejected` の dossier の fragment に `exit_to` 配線が残存（GD104）
- **approved は実行を承認しない**（§6）

### 5.2 proxy oracle 許容条件

proxy oracle（`type: proxy`）は「**安全な前進の下限ゲート**」としてのみ可。以下を**すべて**満たすこと（GD201）:

1. `human_limit_approved: true` — 人間が「これは真の完了条件ではないが下限として承認する」と限界承認済み
2. `hash_lock: true` — ハッシュロック可能（oracle-gaming を convergence-pattern の hash-lock で遮断できる）
3. `post_completion_human_check: true` — 達成後に人間判断へ接続する
4. `judge_type: "mechanical"` — 機械判定。**`"llm_subjective"`（LLM judge の主観評価）は禁止**（GD201 error）
5. `gap_from_true_goal` / `failure_modes` を必須欄として明示（「本当の完了条件との差分」「破れるケース」）

Goodhart（proxy を満たすが真のゴールを満たさない）時の損害が限定的であることを `failure_modes` に書く。

---

## 6. approved は実行権限を与えない（信頼境界）

**v1 では `status: approved` はいかなる実行権限も与えない**。配線実行（goal-loop 起動 / sensor 生成 /
issue 起票）は将来の別ゲートの仕事であり、cycle 等が approved 遷移に executor を無言で接続してはならない。
lint は読み取り専用、writer は compile のみ。

### 6.1 コピペブロックの信頼境界 fence 規約

dossier 内のコピペブロック（他システムに貼る用の manifest / sensor spec / issue seed）は**用途別に fence を
分けて信頼境界を明示**する。fence トークンは以下:

| 用途 | fence トークン |
|------|---------------|
| oracle manifest 用 | ` ```oracle-manifest ` |
| sensor spec 用 | ` ```sensor-spec ` |
| issue seed 用 | `<untrusted_user_content>` … `</untrusted_user_content>` |

- issue seed は消費側（issue polling）が `<untrusted_user_content>` で wrap する前提。**wrap は消費側境界で行う**
- fence 内容に閉じデリミタ（`</untrusted_user_content>` 等）が含まれる場合は escape または reject する
  （prompt injection による境界破りの遮断）

---

## 7. 既存 4 契約への写像表

非ネイティブな全フィールドを既存契約の語彙に 1 行ずつ写像する（独自語彙の増殖を防ぐ）:

| dossier フィールド | 写像先 | 備考 |
|-------------------|--------|------|
| `oracles[].command` / `type` | [convergence-pattern.md](convergence-pattern.md) の Oracle 定義 | goal-loop の判定コマンドに写像 |
| `oracles[].oracle_files` | convergence-pattern の oracle_files（hash-lock 対象） | §8 の書き方規約に従う |
| `fragments[].exit_to = ci_gate` | validate_repo CI gate（[loop-engineering.md](loop-engineering.md) Verifier 層） | 回帰ゲートへ移管 |
| `fragments[].exit_to = resident_sensor` | [loop-engineering.md](loop-engineering.md) §7 Sensor Adapter 契約 | 常駐 sensor として登録 |
| `sensors[].findings_policy.fix_action` | [fix-action-taxonomy.md](fix-action-taxonomy.md)（AUTO_FIX / NEEDS_JUDGMENT / REPORT_ONLY） | admission の入力 |
| `sensors[].findings_policy.enqueue` | [loop-engineering.md](loop-engineering.md) §4 admission の route = enqueue | REPORT_ONLY は絶対に enqueue しない（不変条件） |
| `measurement.metrics` | [measurement-identity.md](measurement-identity.md) の計測系名 | 既存計測値の名前で書く |
| `fragments[].wire_to` | **（新規）** — finding.route とは別物（§3 注記） | goal 断片 → サブシステム選択 |
| `status`（ライフサイクル） | **intentionally-new** | dossier 固有の人間ゲート。既存契約に対応語なし |
| `exit_to = dissolve` | **intentionally-new** | 「下流に常駐せず解散」を表す dossier 固有の終端 |

---

## 8. oracle_files の書き方規約

「ディレクトリ全体をロックしたから新規追加も検出される」とは書かない。`goal_loop.py verify` CLI は
**manifest 記録済みパス中心**という実装限界があり、glob やディレクトリ指定では新規ファイル追加を取りこぼす。

- dossier の `oracle_files` には**ロック対象を明示的なファイル列挙**で書く（`docs/x.md` の列挙。`docs/**` は不可）
- 空配列 / glob のみは GD301 warn（明示列挙を促す）
- 絶対パス（`/home/…` 等）や secret 混入は GD203 error（§9）

---

## 9. secret redaction と GD203 多重防御

dossier 書き出し前に `skills/shared/scripts/secret_detect.py` を通す（loop-triage と同じ運用）。適用は 2 段構え:

1. **自由文フィールド**（`goal.statement` / `inbox[].question` / `routing_proof` 等）は `mask_secrets` でマスク
2. **構造フィールド**（`oracle_files` / hash 値 / 各 `id`）は `detect_secrets` で**検出したら compile を中止**
   （マスクによる無言破壊をしない。hash 値が `generic_long_key` に、絶対パスが `home_path` に誤爆して
   安全ゲート自体を壊すのを防ぐ。`oracle_files` を repo 相対必須にするのはこの誤爆回避も兼ねる）

compile 層の detect-and-abort は手書き dossier の直 commit で迂回できるため、**同じ検査を GD203 として
強制ゲート（lint → CI）側にも持つ**（多重防御）。GD203 は `oracle_files` / `command` / 各 `id` に
絶対パスまたは `detect_secrets` ヒットがあれば error。

md ビューは redaction 済み JSON からの一方向生成 + JSON の sha256 marker を末尾に持つ（md 単独で secret が
入る経路を閉じる）。hash marker は v1 では tamper-evident（改竄検知の手掛かり）であり機械検証はしない
（marker 再計算の CI 検査は v1.1 候補）。

---

## 10. supply gap 3 分類 playbook

ループが停滞したとき、既存計測値（oracle 真偽 × ready 件数 × inbox 件数 × finding_id 再発）で
故障種別を判定する。判定式は既存計測値で書けるため supply gap 検出自体もセンサー化できる。

| # | 分類 | 判定式 | 対応 |
|---|------|--------|------|
| ① | sensor coverage gap | oracle 偽 **かつ** ready 空 **かつ** inbox 空 | sensor を追加する（検出器が無く前進していない） |
| ② | 人間判断の滞留 | inbox に山（inbox 件数 >> 0）**かつ** ready 消化は進行 | **ループの故障ではない**。人間が inbox を捌く |
| ③ | decomposition gap | oracle 偽が長期継続 **かつ** 同一 finding_id が再発 **かつ** oracle が大きすぎ作業単位に割れない | **oracle を弱めない**。中間 oracle を足す（`wire_to: plan` へ） |

> ③ で oracle を弱めて合格させるのは oracle-gaming（convergence-pattern の `oracle_tampered` halt が
> 遮断する対象）。中間 oracle を足すのが正攻法。

---

## 11. Dossier Lint Rule Catalog（GD*）

`scripts/dossier_lint.py` の `RULES` レジストリと**この表が dual source of truth**であり、
`scripts/test_dossier_lint.py` の catalog-sync テストが ID / Severity の一致を機械検証する（drift 防止）。

**ID band 規約**: `GD0xx` = 構造/スキーマ、`GD1xx` = routing/proof、`GD2xx` = proxy/安全、`GD3xx` = 助言（warn）。

| Rule ID | Severity | 検査内容 |
|---------|----------|---------|
| GD001 | error | 必須ブロック 5 種（goal / oracles / sensors / inbox / measurement）+ `schema_version` の存在・型 |
| GD002 | error | `status` が enum（draft/approved/superseded/rejected）内。欠落・型違いも error |
| GD003 | error | 各 fragment の `wire_to` が enum（goal-loop/loop-triage/inbox/plan/reject）内。欠落・型違いも error |
| GD004 | error | 各 fragment の `exit_to` が enum（ci_gate/resident_sensor/dissolve）内。欠落・型違いも error |
| GD005 | error | `blocked_by` の参照整合（指す先の fragment/inbox id が dossier 内に実在） |
| GD006 | error | id の一意性（oracles/fragments/sensors/inbox 横断で重複禁止） |
| GD101 | error | REPORT_ONLY 配線違反: `findings_policy.fix_action == "REPORT_ONLY"` なのに `enqueue: true` |
| GD102 | error | `status: approved` なのに `routing_proof` 欠落 / `auto_fix_allowed: false` の断片に `why_not_auto_fix` 欠落 |
| GD103 | error | `wire_to` × `exit_to` の非互換組み合わせ（§4.1 compatibility matrix 違反） |
| GD104 | error | 状態不変条件: `approved` なのに未解決 `blocked_by` 残存 / `superseded` なのに `superseded_by` 欠落 / status `rejected` の fragment に `exit_to` 配線残存 |
| GD201 | error | proxy oracle の必須 6 欄欠落（§5.2）または `judge_type: "llm_subjective"` |
| GD202 | error | 危険組み合わせ: `self_modification_risk: high` かつ `auto_fix_allowed: true` |
| GD203 | error | 構造フィールド（`oracle_files` / `command` / 各 `id`）に絶対パスまたは secret 混入 |
| GD301 | warn | `oracle_files` が空配列 / glob のみ（明示列挙なし） |
| GD302 | warn | `goal.non_goals` が空（願望の無限拡張リスク） |

**finding schema**（1 件あたり）: `{rule, severity, file, locator, message, fix}`。`locator` は fragment/oracle/inbox の
id か JSON パス（例: `fragments[2].why_not_auto_fix`）。`message` は what/why、`fix` は具体的修正案。

**終了コード**: `0` = pass（**warn のみは 0**）/ `1` = error 級 finding あり / `2` = 前提不成立
（JSON parse 失敗・重複キー・パス不正・ファイル不在・サイズ超過）。

---

## 12. 参照

- [convergence-pattern.md](convergence-pattern.md) — Oracle / hash-lock / oracle-gaming 遮断
- [loop-engineering.md](loop-engineering.md) — Finding Schema / admission / Sensor Adapter / 自己修飾ゲート
- [polling-pattern.md](polling-pattern.md) — Queue / Executor 消化
- [measurement-identity.md](measurement-identity.md) — 計測系
- [fix-action-taxonomy.md](fix-action-taxonomy.md) / [severity-and-verdicts.md](severity-and-verdicts.md) — 分類軸
