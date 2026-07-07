# Measurement Identity — Shared Contract（計測の結合キー統一）

> **⚠️ Warning:** 本契約は「ループは良くなっているか」に答えるための計測結合キーを定義する。
> スキーマ・enum・写像表の変更は全 writer（polling 両 adapter / skill-regression / trigger-eval）と
> 全 reader（skill-improve 等）に影響する。変更時は参照スキルを同一 PR で同期更新すること。

---

## 1. 問題 — 計測系のサイロ化

本リポジトリには 5 つの計測系があるが、互いに結合キーを持たない:

| 系 | 計るもの | 既存ストア | 限界 |
|---|---|---|---|
| polling TickResult | tick の成否カウンタ | なし（揮発） | tick が終わると消える |
| skill-regression | 挙動面の検証イベント | `ledger.json` | 最新 1 件のみ（履歴なし） |
| trigger-eval | 発火精度メトリクス | なし（レポートのみ） | 実行間比較ができない |
| skill-improve | セッション摩擦 | session JSONL（読み取り） | 逸話単位、instruction 版と未結合 |
| cycle 結果 | plan 実行の成果 | `docs/plans/results` | 自由文、機械集計不能 |

このままでは「SKILL.md のこの改稿は成功率を上げたのか」に原理的に答えられない。
**新しいサイロを足すことは解決ではない** — 結合キーの統一が解決である。

---

## 2. Identity Triple

すべての計測イベントは以下の 3 キーで識別する:

| キー | 定義 | SSOT |
|---|---|---|
| `skill` | その実行の挙動を司ったスキル名（ディレクトリ名） | `skills/<name>/` |
| `surface_sha256` | 実行時点の挙動面 fingerprint | `skills/skill-regression/scripts/dep_graph.py` の挙動面定義 + `ledger.py fingerprint()`（**再実装禁止**、必ず同一実装を呼ぶ） |
| `run_id` | 実行イベントの UUID | [polling-pattern.md §7](polling-pattern.md#7-tick-result-schema) の `run_id` と同一系（失敗 issue frontmatter とも相関可能） |

`surface_sha256` が **instruction のバージョン番号**として機能する。改稿前後の比較は
「hash A の期間の成績 vs hash B の期間の成績」の比較である。

---

## 3. Event Record Schema

`docs/loop/events.jsonl` に 1 行 1 イベントで append する（commit 対象。単一ホスト前提は
polling と同じ）。**構造化フィールドのみ・自由文禁止・secret 禁止**（TickResult §7 の哲学を継承）。

```
Event {
  ts:             ISO8601
  system:         "polling-fs" | "polling-label" | "skill-regression" | "trigger-eval"
  event:          "tick" | "verification" | "eval"
  skill:          str
  surface_sha256: hex64
  run_id:         UUID | null
  outcome:        object   # system 別（§4）。数値・enum のみ
}
```

- `system` / `event` は閉じた enum。追加は本契約の改訂として行う（**No new silos rule**:
  新しい計測を追加するときは新ストアを作らず本スキーマを拡張する）
- append は atomic write でなくてよい（追記 1 行、単一ホスト・単一プロセス前提）

---

## 4. 既存系の写像表

| system | event | outcome フィールド | append タイミング |
|---|---|---|---|
| `polling-fs` / `polling-label` | `tick` | `{claimed, done, failed_transient, failed_permanent, halt_reason?}`（TickResult §7 と同一） | tick の TickResult 出力直後（各 SKILL.md の最終 Step）。`skill` = issue / github-issue、`surface_sha256` は tick 開始時に算出 |
| `skill-regression` | `verification` | `{result: "pass" \| "accepted-without-run", scenarios?: int}` | `ledger.py --update` 実行直後（ledger.json は最新のみ・events は履歴） |
| `trigger-eval` | `eval` | `{recall, precision, stability}`（対象スキル別に 1 行ずつ） | Tier 1/2 計測完了時（推奨） |

読み取り専用の系:

- **skill-improve**: writer ではなく reader。session JSONL の摩擦と events を `run_id` /
  `skill` × `surface_sha256` で相関させ、「どの instruction 版で摩擦が増えたか」を分析できる
- **cycle（手動実行）**: v1 対象外。polling 経由の cycle 成否は `tick` イベントが捕捉している。
  手動 cycle の計測は将来拡張（本契約の改訂として行う）

---

## 5. 結合クエリ（1 コマンド）

```bash
python3 skills/shared/scripts/measurement_identity.py report --skill issue \
  [--events docs/loop/events.jsonl]
```

- surface_sha256 別に `{ticks, done, failed, success_rate, first_ts, last_ts}` を集計し、
  時系列順のテーブルで表示する
- 直近 2 つの surface の成功率差分（= 最後の改稿の効果）を明示する
- 集計は純関数（`aggregate_by_surface` / `surface_delta`）で行い、unittest で検証する

---

## 6. 運用

- `docs/loop/events.jsonl` は肥大化したら `docs/loop/archives/YYYY-MM.jsonl` へ月次で移動してよい
  （polling の archive パターンと同じ。report は `--events` 複数指定で跨げる）
- イベントの**削除・書き換えは禁止**（append-only。誤記録はそのまま残し、次の正しいイベントで上書きせず補正もしない — 計測の改竄可能性を構造的に排除する）
- writer の追加・変更は本契約の写像表（§4）の更新とセットで行う

## 7. 参照

- [polling-pattern.md](polling-pattern.md) — run_id / TickResult の定義元
- [loop-engineering.md](loop-engineering.md) — 供給側ループ（finding_id は別軸の identity。混同しない: finding_id は「問題」の同一性、本契約は「実行」の同一性）
- `skills/skill-regression/` — 挙動面と fingerprint の SSOT
