# goal-decomposition-loop-intake

**Cycle ID:** `20260707222735`
**Started:** 2026-07-07 22:27:35
**Status:** 🔵 Implementing

---

## 📝 What & Why

大枠ゴール（例:「コードベース全体を精査してリファクタリング完遂」）を Loop Readiness Dossier（自走可能性の型検査結果）にコンパイルし、既存の閉ループ基盤（goal-loop / loop-triage / issue polling / measurement spine）に配線する入口スキル `goal-decomposition` を新設する。主成果は「自走してはいけない断片を機械的に説明して止めること」— 願望を願望のまま自動化に流さない。閉ループ基盤の部品は揃っているが「どのゴールをどの部品にどう配線するか」を決める入口がなく、翻訳作業が毎回 LLM の裁量任せになっている問題を解消する。

**出典**: `docs/ideas/archives/20260707222356_goal-decomposition-loop-intake.md`（brainstorm セッションの合意事項。本 plan の設計判断はすべてここで Codex セカンドオピニオン込みで検証済み）

## 🎯 Goals

- 共有契約 `goal-decomposition-pattern.md` を新設し、Dossier Schema / 第一問決定木 / 5 軸 routing proof / supply gap 3 分類 playbook / proxy oracle 許容条件を集約する（既存 4 契約の上流「翻訳層」。既存契約は再定義しない・独自語彙を増やさず既存契約のフィールド名に写像する）
- スキル `skills/goal-decomposition/`（薄い orchestrator、command なし、compile / validate の 2 ワークフロー）を新設する
- `dossier_lint.py`（純関数 + unittest）を実装し、`validate_repo.py` から呼ばれる CI チェックまで v1 に含める（任意運用の lint は儀式化するため）
- 具体例 1 本（「ドキュメント品質を上げて維持する」）の dossier を E2E で作成して lint を通し、スキーマの実用性を証明する

## 📐 Design

### 確定済み設計判断（brainstorm 合意。cycle の refine で覆さないこと）

1. **dossier = JSON canonical + md レポートの 2 層**。lint は JSON のみを対象とし、md はビュー（生成物）扱い。置き場は `docs/loop/dossiers/{timestamp}_{slug}.json` + 同名 `.md`。`docs/loop/events.jsonl` には混ぜない（イベント化は measurement-identity 契約の閉 enum 改訂が必要なため v1 スコープ外）
2. **第一問決定木**: 各断片に「完了条件か / 未達検出器か / 人間判断か」を最初に問う。完了条件 → oracle 可能性 → goal-loop、未達検出器 → Finding Schema 適合性 → loop-triage、人間判断 → inbox question。自動修正可否（AUTO_FIX 等）は finding の属性なので最後に評価する
3. **5 軸**（機械検証可能性 / finding 化可能性 / 自動修正許容度 / 自己修飾リスク / 計測可能性）は routing 決定木と危険組み合わせ検査（例: AUTO_FIX × 自己修飾リスク高）の両方に使う。スコア表ではなく各断片 1 行の routing proof（非 AUTO_FIX 断片には「なぜ AUTO_FIX でないか」必須）
4. **Dossier 5 ブロック**: Goal（non-goals + SSOT 宣言込み）/ Completion Oracles（oracle_files 所有権込み）/ Sensors & Findings（採用 rule 群明示）/ Human Judgment Inbox(再分類条件込み) / Measurement & Stop Conditions。断片の局所フィールドとして `exit_to`（enum: `ci_gate` | `resident_sensor` | `dissolve`）と `blocked_by`（例: `inbox:<id>`。DAG 全体設計はしない）
5. **人間ゲートは状態で止める**: dossier に `status`（`draft` / `approved` / `superseded` / `rejected`）ライフサイクルを持たせる。AskUserQuestion 必須を広げない（headless 互換）。lint は「approved なのに routing proof 欠落」等を fail にする
6. **v1 スコープ = compile + lint のみ**。配線実行（goal-loop 起動 / sensor adapter 生成 / inbox 自動起票）はしない。特に inbox は loop-triage の route 結果であり、writer を増やさない。dossier 内のコピペブロックは用途別（oracle manifest 用 / sensor spec 用 / issue seed 用）に fence を分けて信頼境界を明示する（issue polling の `<untrusted_user_content>` 契約との整合）
7. **supply gap 3 分類**を契約の playbook 節に定義: ①sensor coverage gap（oracle 偽・ready 空・inbox 空）②人間判断の滞留（inbox に山 — ループの故障ではない）③decomposition gap（oracle が大きすぎて作業単位に割れない — oracle を弱めず中間 oracle を足す）。判定式は既存計測値（oracle 真偽 × ready 件数 × inbox 件数 × finding_id 再発）で書く
8. **proxy oracle 許容条件**を契約に定義: 「安全な前進の下限ゲート」としてのみ可（人間が限界承認済み / ハッシュロック可能 / 達成後に人間判断へ接続 / Goodhart 時の損害が限定的）。LLM judge の主観評価は禁止。proxy には「本当の完了条件との差分」「破れるケース」を必須欄にする
9. **secret redaction**: dossier 書き出し前に `skills/shared/scripts/secret_detect.py` を通す（loop-triage と同じ運用）
10. **Codex 版は作らない**（goal-loop / loop-triage と同格の Claude 版のみ・本リポジトリの閉ループ基盤向けだが契約自体は汎用）
11. **oracle_files の書き方規約**: 「ディレクトリ全体をロックしたから新規追加も検出される」とは書かない（`goal_loop.py verify` CLI は manifest 記録済みパス中心という実装限界がある）。dossier にはロック対象を明示的なファイル列挙で書く

### Dossier JSON Schema v1（最小契約 — 契約・テスト・lint の単一ソース）

契約・fixture・lint 実装の 3 者が暗黙スキーマでドリフトしないよう、canonical キー階層をここで先に固定する（実装ステップ 1 でこのブロックを契約草案に転記してから RED テストを書く）。未知フィールドは無視（前方互換）。

```jsonc
{
  "schema_version": 1,               // int 必須
  "status": "draft",                 // enum: draft | approved | superseded | rejected
  "superseded_by": null,             // status: superseded のとき必須（後継 dossier ファイル名）
  "goal": {
    "statement": "…",
    "non_goals": ["…"],              // 空なら GD302 warn
    "ssot": "…"                      // SSOT 宣言（判断4）
  },
  "oracles": [{
    "id": "oracle:slug",             // id は全ブロック横断で一意（GD006）
    "type": "true",                  // enum: true | proxy
    "command": "…",                  // 判定コマンド（convergence-pattern の oracle に写像）
    "oracle_files": ["docs/x.md"],   // repo 相対の明示列挙（判断11。空/globのみ → GD301 warn、絶対パス/secret → GD203 error）
    "owner": "…",                    // 所有権（判断4）
    "proxy": {                       // type: proxy のとき必須（判断8 → GD201）
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
    "why_not_auto_fix": "…",         // auto_fix_allowed: false のとき必須（判断3 → GD102）
    "self_modification_risk": "low", // enum: low | high。high × auto_fix_allowed=true → GD202 error
    "blocked_by": ["inbox:q1"]       // 参照整合は GD005
  }],
  "sensors": [{
    "id": "sensor:slug",
    "rules": ["…"],                  // 採用 rule 群の明示（判断4）
    "findings_policy": {
      "fix_action": "REPORT_ONLY",   // enum: AUTO_FIX | NEEDS_JUDGMENT | REPORT_ONLY（fix-action-taxonomy に写像）
      "enqueue": false               // fix_action: REPORT_ONLY かつ enqueue: true → GD101 error
    }
  }],
  "inbox": [{
    "id": "inbox:q1",
    "question": "…",
    "reclassify_when": "…"           // 再分類条件（判断4）
  }],
  "measurement": {
    "metrics": ["…"],                // 既存計測値の名前で書く（measurement-identity に写像）
    "stop_conditions": ["…"]
  }
}
```

**フィールド名の注意**: 断片の配線先フィールドは `wire_to` と命名する（loop-engineering §4 の `route`（finding の行き先 enum: enqueue/inbox/…）と名前衝突するため `route` は使わない。契約の写像表に「`wire_to` は goal 断片→サブシステム選択であり finding.route とは別物」と明記する）。`wire_to` の 5 値のうち `goal-loop`/`loop-triage`/`inbox` は第一問決定木（判断2）の 3 出口、`plan`/`reject` は決定木の終端 2 種（`plan` = decomposition gap で中間 oracle にも割れず人手の plan/cycle に直行させる断片、`reject` = non-goals 行きで自動化に流さない断片）。契約の決定木節でこの 5 値の導出を定義する。

### dossier_lint.py の検査ルール（v1）

Rule ID は design-lint（DL0xx/1xx/2xx）と同様のバンド構造: **GD0xx = 構造/スキーマ、GD1xx = routing/proof、GD2xx = proxy/安全、GD3xx = 助言（warn）**。

| Rule ID | 検査内容 | severity |
|---------|---------|----------|
| GD001 | 必須ブロック 5 種（goal / oracles / sensors / inbox / measurement）+ `schema_version` の存在・型 | error |
| GD002 | `status` が enum（draft/approved/superseded/rejected）内。欠落・型違いも error | error |
| GD003 | 各 fragment の `wire_to` が enum（goal-loop/loop-triage/inbox/plan/reject）内。欠落・型違いも error | error |
| GD004 | `exit_to` が enum（ci_gate/resident_sensor/dissolve）内。欠落・型違いも error | error |
| GD005 | `blocked_by` の参照整合（指す先の fragment/inbox id が dossier 内に実在） | error |
| GD006 | id の一意性（oracles/fragments/sensors/inbox 横断で重複禁止。GD005 の前提） | error |
| GD101 | REPORT_ONLY 配線違反: `findings_policy.fix_action == "REPORT_ONLY"` なのに `enqueue: true`（REPORT_ONLY は絶対に enqueue しない — loop-engineering 契約の不変条件） | error |
| GD102 | `status: approved` なのに `routing_proof` 欠落 / `auto_fix_allowed: false` の断片に `why_not_auto_fix` 欠落 | error |
| GD103 | `wire_to` × `exit_to` の非互換組み合わせ（決定木対応の compatibility matrix 違反。例: `wire_to: inbox` × `exit_to: ci_gate`、`wire_to: reject` に exit_to 指定。matrix は契約に表で定義し catalog-sync テストで lint と一致を保証） | error |
| GD104 | 状態不変条件: `approved` なのに未解決 `blocked_by` が残存 / `superseded` なのに `superseded_by` 欠落 / `rejected` の fragment に `exit_to` 配線残存 | error |
| GD201 | proxy oracle（`type: proxy`）の必須欄欠落（gap_from_true_goal / failure_modes / human_limit_approved / hash_lock / post_completion_human_check / judge_type）または `judge_type: "llm_subjective"` | error |
| GD202 | 危険組み合わせ（判断3 の 5 軸検査の機械化）: `self_modification_risk: high` かつ `auto_fix_allowed: true` | error |
| GD203 | 構造フィールドの秘密・絶対パス混入: `oracle_files` / `command` / 各 `id` に絶対パス（`/home/…` 等）または `detect_secrets` ヒットがある（compile 層の detect-and-abort は手書き dossier の直 commit で迂回できるため、強制ゲート（lint→CI）側でも error として止める） | error |
| GD301 | `oracle_files` が空配列 / glob のみ（明示列挙なし） | warn |
| GD302 | `goal.non_goals` が空（願望の無限拡張リスク） | warn |

**実装パターン**: context-audit の `static_checks.py` と同じ **RULES registry**（`dict[rule_id → {severity, fn}]`、`run_checks()` は `sorted(RULES)` を走査、ルール追加 = 関数追加 + 登録のみで既存ルール無変更 = open-closed）+ `make_finding()` 相当の canonical finding schema + `finalize_findings()` 相当の secret masking（`skills/shared/scripts/secret_detect.py` を import して findings 出力自体もマスク）を踏襲する。ゼロから dispatch を発明しない。

**finding schema**（1 件あたり）: `{rule, severity, file, locator, message, fix}`。`locator` は JSON に行番号がないため fragment/oracle/inbox の id か JSON パス（例: `fragments[2].why_not_auto_fix`）。`message` は what/why、`fix` は具体的修正案を必ず持つ（design-lint の `_violation()` + `suggestion` と同水準）。

**終了コード**（design-lint の実際の規約に一致させる）: `0` = pass（**warn のみは 0**）/ `1` = error 級 finding あり / `2` = 前提不成立（JSON parse 失敗・重複キー・パス不正・ファイル不在）。~~warn=1/error=2~~ という独自規約は採らない。

**堅牢性・性能**:
- `json.load` は `object_pairs_hook` で**重複キーを検出したら exit 2**（`"status": "draft"` と `"status": "approved"` の二重定義で人間レビューを欺く review-bypass を遮断）
- `JSONDecodeError` だけでなく `RecursionError` / `ValueError` / `UnicodeDecodeError` も捕捉して exit 2（深いネストの crafted input が traceback で漏れない）
- parse 前に `os.stat` でサイズ上限（1MB）を検査し、超過は exit 2（in-process 実行時のメモリ暴走防止）
- path containment は `os.path.commonpath([realpath(arg), realpath(dossiers_dir)]) == realpath(dossiers_dir)` で判定（`startswith` の prefix-match footgun — `docs/loop/dossiers-evil/` 素通り — を避ける）。symlink エントリは拒否。対象は lint の読み取りパスと compile の書き出しパスの両方
- GD005/GD006 は事前に id set を 1 回構築して membership test（fragment ごとの全走査 O(n²) を書かない）

### Files to Change

```
skills/shared/references/
  goal-decomposition-pattern.md   - 新規: 共有契約（翻訳層）。Dossier Schema (JSON) / 第一問決定木
                                    （wire_to 5 値の導出込み）/ 5軸 routing proof / status ライフサイクル /
                                    wire_to×exit_to compatibility matrix / supply gap playbook /
                                    proxy oracle 許容条件 / 信頼境界 fence 規約（fence トークン定義 +
                                    閉じデリミタ検出・拒否ルール + wrap は消費側境界で行う旨）/
                                    「approved は実行権限を与えない（配線実行は将来の別ゲート）」条項 /
                                    既存4契約への写像表（非ネイティブ全フィールドに 1 行ずつ:
                                    exit_to.ci_gate → convergence-pattern Oracle、exit_to.resident_sensor →
                                    loop-engineering Sensor Adapter、findings_policy.fix_action →
                                    fix-action-taxonomy、measurement.metrics → measurement-identity、
                                    wire_to は finding.route と別物と明記。status / dissolve は
                                    intentionally-new として 1 行の理由付き）
skills/goal-decomposition/
  SKILL.md                        - 新規: 薄い orchestrator。compile / validate の 2 ワークフロー。
                                    frontmatter description にトリガー語（「goal-decomposition」「大枠ゴール」
                                    「ループに乗せたい」「dossier」「自走できる状態にして」等・1024字以内）。
                                    チェック12対応として fix-action-taxonomy.md への md リンク必須
                                    （新契約へのリンクだけでは check 12 を満たさない。loop-triage と同じ）
  scripts/dossier_lint.py         - 新規: 純関数 lint（標準ライブラリのみ・jsonschema 等の外部依存禁止）。
                                    RULES registry パターン。終了コード 0/1/2（上記規約）
  scripts/test_dossier_lint.py    - 新規: unittest（TDD で lint より先に書く）。catalog-sync テスト込み
  references/dossier-template.md  - 新規: md ビューのテンプレート + JSON 最小例
scripts/validate_repo.py          - 変更: チェック13として dossier lint を統合（in-process import。
                                    dossier ごとの subprocess 起動はしない）。docs/loop/dossiers/ が
                                    不在/空なら no-op。error 級 finding のみ errors へ
                                    `[dossier] <file>: GDxxx <message>` 形式で追加（warn は表示のみ・
                                    CI fail させない）。対象は dossiers/ 直下の *.json 全件（小規模 JSON の
                                    線形走査で CI 負荷は無視できる。将来 terminal 状態の蓄積が問題化したら
                                    archives/ 退避を別 plan で導入）。**チェック13は各 dossier を lint CLI と
                                    同一の例外集合（JSONDecodeError / RecursionError / ValueError /
                                    UnicodeDecodeError / 重複キー / サイズ超過）の try/except で包み、
                                    失敗は `[dossier] <file>: parse-error <理由>` の errors エントリに変換する
                                    （1 つの壊れた dossier が validate_repo 全体を traceback で落とさない）**。
                                    ヘッダ docstring のチェック項目一覧に 13 を追記。CONTRACT_VOCAB に
                                    goal-decomposition-pattern.md
                                    （識別語彙: ci_gate / resident_sensor / dissolve、閾値 2）を登録
scripts/test_validate_repo.py     - 変更: チェック13のケース追加（dossiers/ 不在で no-op /
                                    不正 dossier で fail / warn のみで pass / 壊れた JSON を置いても
                                    validate_repo が abort せず `[dossier] parse-error` として報告する）
docs/loop/dossiers/
  20260707230000_doc-quality.json - 新規: E2E 検証用の具体例 dossier（brainstorm で机上検証済みの
  20260707230000_doc-quality.md     「ドキュメント品質を上げて維持する」を正式スキーマで書き直す。status: draft）
README.md                         - 変更: スキル表 + ファイル構成ツリー（skills/goal-decomposition/ と
                                    shared/references/goal-decomposition-pattern.md）に追加
CLAUDE.md                         - 変更: 主要スキル表 + 共有リソース節に契約を追加
.claude-plugin/plugin.json        - 変更: バージョン bump（minor）
.claude-plugin/marketplace.json   - 変更: 同上
CHANGELOG.md                      - 変更: エントリ追加
```

### Key Points

- **契約は翻訳層**: loop-engineering（供給）/ convergence-pattern（収束）/ polling-pattern（消化）/ measurement-identity（計測）の上流。写像表（dossier フィールド → 既存契約の語彙）を契約内に持ち、独自語彙の増殖を防ぐ。SKILL.md は `AUTO_FIX`/`REPORT_ONLY` 語彙を使うため validate_repo チェック12の対象になる — **`fix-action-taxonomy.md` への md リンクを必ず張る**（新契約へのリンクでは代替できない）
- **SKILL.md は薄く**: schema 詳細・決定木・playbook は契約側に置き、SKILL.md は compile 手順と validate 手順のみ。loop-triage / goal-loop と同じ構造
- **compile の I/O 契約**: 入力は自然言語の大枠ゴール。**出力は常に `status: draft`**（approved は人間が dossier を直接編集して遷移させる。compile が approved を出すことは絶対にない）。人間判断が必要な断片は inbox エントリ + `blocked_by` に落とす。観察できていない断片は confidence を盛らず `blocked_by` に落とす。コードベース調査は goal と oracle_files 候補に関連するパスに限定し、full-tree scan はしない（SKILL.md に明記）
- **compile の対話設計**: 質問攻めにしない。コードベース調査で埋められるもの / 契約から推定できるものは埋め、人間には non-goals・proxy 限界承認・routing proof の差分承認の 3 つだけ聞く（質問文・選択肢の文言は SKILL.md に固定で書く）。**headless 時は AskUserQuestion をスキップして draft を出し、未解決の承認事項を inbox/blocked_by に記録する**（状態ゲートが人間承認を担保するので compile が対話をブロックしない）
- **secret redaction の適用境界**（判断9 の具体化）: `secret_detect.py` は CLI を持たない import-only モジュールなので、compile 手順では `detect_secrets` / `mask_secrets` を **import して使う**と SKILL.md に明記する。適用は 2 段構え — ①自由文フィールド（goal.statement / question / routing_proof 等）は `mask_secrets` でマスク、②構造フィールド（oracle_files / hash 値 / id）は `detect_secrets` で**検出したら compile を中止**（マスクによる無言破壊をしない。ハッシュロック値が `generic_long_key` に、絶対パスが `home_path` に誤爆して安全ゲート自体を壊すのを防ぐ）。oracle_files を repo 相対必須（GD203 error）にするのはこの誤爆回避も兼ねる。書き出しパイプライン順序: JSON 生成 → secret チェック → 検出時はファイル未作成で中止 → 合格時のみ md 生成。なお compile 層のこのチェックは手書き dossier の直 commit では迂回できるため、同じ検査を GD203 として強制ゲート（lint→CI）側にも持つ（多重防御）
- **md は JSON からの一方向生成物**: md ビューは redaction 済み JSON から生成し、生成元 JSON の sha256 と generated marker を md 末尾に記載する。md の手編集は禁止（契約に明記）。これで lint 対象外の md に secret や JSON との乖離が入る経路を閉じる
- **md ビューの人間可読性**: 承認者は md を読んで draft→approved を判断するため、dossier-template.md の冒頭に「この dossier が何を決め、承認すると何が起きる/起きないか」の平易な説明節と、oracle / wire_to / exit_to / blocked_by / proxy の 1 行グロッサリを置く（JSON は専門語彙のまま、md で人間に翻訳する）
- **compile の報告は summary-first**: 終了時に断片数（wire_to 別）/ inbox・blocked_by 件数 / secret チェック結果 / lint 結果 / status / 次の一手（「md を読んで approved に上げる」等）のテンプレを SKILL.md に置く（loop-triage Step 7 と同形式）
- **TDD**: test_dossier_lint.py → dossier_lint.py の順（RED → GREEN）。lint は純関数（JSON 入力 → findings リスト出力）に寄せ、I/O は main() に隔離する
- **契約⇔コードの drift 防止**: 契約の rule 表（ID/severity）と `RULES` registry の一致を assert する catalog-sync テストを test_dossier_lint.py に含める（context-audit の `test_catalog_sync.py` と同じパターン）

### 実装ステップ（この順で）

1. 本 plan の「Dossier JSON Schema v1」ブロックを契約 `goal-decomposition-pattern.md` の**草案**として先に固定する（schema 定義が fixture・lint・契約でドリフトしないよう単一ソースを最初に置く。写像表・playbook 等の本文は後述ステップ 4 で完成させる）
2. `test_dossier_lint.py` を書く（RED。詳細は Tests 節）
3. `dossier_lint.py` を実装して GREEN にする（RULES registry パターン）
4. 共有契約 `goal-decomposition-pattern.md` を完成させる（決定木 / 写像表 / compatibility matrix / playbook / proxy 条件 / fence 規約 / approved 非実行権限条項。rule 表は catalog-sync テストで lint と一致確認）
5. `SKILL.md` + `references/dossier-template.md` を書く（fix-action-taxonomy.md への md リンク・3 質問の文言・summary-first テンプレ・headless 挙動・調査スコープ上限を含む）
6. `validate_repo.py` にチェック13を統合（in-process import + `[dossier]` タグ形式 + ヘッダ docstring 更新 + CONTRACT_VOCAB 登録）し、`test_validate_repo.py` にケースを追加する
7. 具体例 dossier（doc-quality）を作成して lint を通す（E2E 検証）
8. README.md（スキル表 + ファイル構成）/ CLAUDE.md を更新し、ここで初めて `python3 scripts/validate_repo.py` の**全チェック合格**を確認する（ステップ 5 の時点では README 未更新のためチェック7 が fail する — 全 green 確認をステップ 5-7 に置かない）
9. バージョン bump + CHANGELOG → commit（論理単位分割・日本語）

## ✅ Tests

**error 系（各ルール fail / pass の両方向）:**
- [ ] GD001: ブロック欠落で fail / 5 ブロック + schema_version 揃いで pass。空 JSON `{}` で全欠落検出
- [ ] GD002-GD004: enum 外の値で fail / 有効値で pass / **フィールド欠落**で fail / **型違い**（例: status が list）で fail
- [ ] GD005: 存在しない id を指す `blocked_by` で fail / 実在 id で pass
- [ ] GD006: fragment と inbox の id 重複で fail / 全 id 一意で pass
- [ ] GD101: `fix_action: REPORT_ONLY` + `enqueue: true` で fail / `REPORT_ONLY` + `enqueue: false` で pass（**near-miss**: `AUTO_FIX` + `enqueue: true` は pass）
- [ ] GD102: approved + routing_proof 欠落で fail / **draft + routing_proof 欠落は pass**（near-miss）/ `auto_fix_allowed: true` に why_not_auto_fix 不要（near-miss）
- [ ] GD103: 非互換組み合わせ（inbox×ci_gate 等）で fail / matrix 内の組み合わせで pass
- [ ] GD104: approved + 未解決 blocked_by で fail / superseded + superseded_by 欠落で fail / rejected + exit_to 残存で fail
- [ ] GD201: proxy の必須 6 欄いずれか欠落で fail / `judge_type: llm_subjective` で fail / **`type: true` の oracle に proxy 欄不要**（near-miss）
- [ ] GD202: `self_modification_risk: high` × `auto_fix_allowed: true` で fail / high × false で pass
- [ ] GD203: `oracle_files` に絶対パス混入で fail / secret パターン（40 字超の鍵様文字列等）混入で fail / repo 相対の明示列挙で pass

**warn 系:**
- [ ] GD301: 空配列 / glob のみで warn。GD302: non_goals 空で warn
- [ ] **warn のみの dossier は終了コード 0**（design-lint の実規約に一致。error ありで 1）

**堅牢性（exit 2 系）:**
- [ ] 壊れた JSON / 重複キー（status 二重定義）/ サイズ超過 / dossiers/ 外のパス指定 → いずれも exit 2 で安全側終了
- [ ] status 遷移非依存: lint は単一 JSON のみで判定でき、履歴ファイルを要求しない

**正常系・統合:**
- [ ] 完全な **approved** dossier（proxy oracle + blocked_by 解消済み + why_not_auto_fix 完備）が findings 0 で通る（draft 偏重にしない）
- [ ] catalog-sync: 契約の rule 表と RULES registry の ID/severity 一致
- [ ] validate_repo 統合（test_validate_repo.py）: dossiers/ 不在・空で既存チェックが壊れない / error 級 dossier を置くと `[dossier]` タグで fail / **warn のみの dossier では fail しない** / 壊れた JSON でも validate_repo が abort せず `[dossier] parse-error` で報告
- [ ] E2E: doc-quality dossier（draft）が lint 合格する

## 🔒 Security

- [ ] secret redaction の 2 段適用（自由文 = mask / 構造フィールド = detect で compile 中止）を SKILL.md の compile 手順に明記。import ベースで呼ぶ（secret_detect.py は CLI を持たない — 「スクリプトを実行」とは書かない）
- [ ] md ビューは redaction 済み JSON からの一方向生成 + JSON hash marker（md 単独で secret が入る経路を閉じる）。lint findings 出力自体も finalize_findings 相当でマスク。hash marker は v1 では tamper-evident（改竄検知の手掛かり）であり機械検証はしない — marker 再計算の CI 検査は v1.1 候補として契約に既知の限界と明記
- [ ] compile 層の detect-and-abort（迂回可能）に加え、強制ゲート側にも GD203（構造フィールドの秘密・絶対パス検査、error 級）を置き、手書き dossier の直 commit でも CI が止める
- [ ] コピペブロックの信頼境界 fence 規約を契約に定義: fence トークンの定義 + 内容に閉じデリミタ（`</untrusted_user_content>` 等）が含まれる場合は escape/reject + wrap は消費側境界で行う（issue seed は `<untrusted_user_content>` wrap 前提）
- [ ] dossier_lint.py の path containment は `commonpath` 判定 + symlink 拒否（`startswith` prefix-match は使わない）。docs/loop/dossiers/ 配下のみ読む
- [ ] JSON parse: 重複キー検出（object_pairs_hook）で review-bypass 遮断 / RecursionError 等も捕捉。失敗はすべて exit 2（安全側）
- [ ] `status: approved` は v1 では**いかなる実行権限も与えない**（配線実行なし・lint は読み取り専用・writer は compile のみ）。契約に「approved は実行を承認しない。配線は将来の別ゲート」と明文化し、将来 cycle が approved 遷移に executor を無言で接続できないようにする

## 📊 Progress

| Step | Status |
|------|--------|
| Tests | ⚪ |
| Implementation | ⚪ |
| Commit | ⚪ |

**Legend:** ⚪ Pending · 🟡 In Progress · 🟢 Done

---

**Next:** Write tests → Implement → Commit with `claude-skills:commit` 🚀
