# Issue Polling — Pure Function Specifications

> **本ファイルの位置づけ:** `skills/shared/references/polling-pattern.md` §4 で宣言された純関数の、issue adapter 側での実装仕様（全網羅 match 表含む）。

共通契約: [../../shared/references/polling-pattern.md](../../shared/references/polling-pattern.md)

---

## 1. `transition(state, event) -> NextState | InvalidTransition`

**純関数。** 副作用なし。共通契約 §2 の Transition Table と完全一致する match を返す。

### Full Match Table

| Input (state, event) | Output |
|---|---|
| (`ready`, `claim`) | `running` |
| (`running`, `cycle_success`) | `done` |
| (`running`, `cycle_fail_transient`) | `failed/transient` |
| (`running`, `cycle_fail_permanent`) | `failed/permanent` |
| (`running`, `sigint`) | `ready` |
| (`done`, `month_boundary`) | `archives` |
| (`failed/transient`, `retry_under_limit`) | `ready` |
| (`failed/transient`, `retry_over_limit`) | `failed/permanent` |
| **Any other (state, event)** | `InvalidTransition{state, event}` |

### Examples

- `transition(ready, claim)` → `running`
- `transition(done, claim)` → `InvalidTransition`（done は claim 対象外）
- `transition(failed/permanent, retry_under_limit)` → `InvalidTransition`（permanent は retry しない、契約 §8）

---

## 2. `classify_failure(error_kind) -> Transient | Permanent`

**純関数。** エラー種別の文字列を受け取り 2 分類する。

| `error_kind` | Classification |
|---|---|
| `network_error` | `Transient` |
| `timeout` | `Transient` |
| `file_lock` | `Transient` |
| `rate_limit` | `Transient` (backoff は exponential、契約 §8) |
| `test_failure` | `Permanent` |
| `compile_error` | `Permanent` |
| `cycle_abort` | `Permanent` |
| `invalid_input` | `Permanent` |
| **Unknown** | `Permanent` (fail-closed) |

Unknown を **`Permanent` に倒す** のは fail-closed 原則（暴走より停止を優先）。

---

## 3. `should_promote_to_permanent(retry_count, limit) -> bool`

**純関数。** 純粋な比較のみ。

```
should_promote_to_permanent(retry_count, limit) = (retry_count >= limit)
```

### Boundary Examples

| retry_count | limit | Result |
|---|---|---|
| 0 | 3 | `false` |
| 2 | 3 | `false` |
| 3 | 3 | `true` (境界) |
| 5 | 3 | `true` |

---

## 4. `month_boundary_crossed(now, last_check) -> bool`

**純関数。** `now` と `last_check` の `YYYY-MM` が異なれば true。

```
month_boundary_crossed(now, last_check) = (now.year_month != last_check.year_month)
```

### Examples

| now | last_check | Result |
|---|---|---|
| 2026-04-08 | 2026-04-01 | `false` |
| 2026-05-01 | 2026-04-30 | `true` |
| 2026-04-08 | `""` (unset) | `true` (初回は跨いだ扱い) |

時刻・タイムゾーンは呼び出し側で正規化して渡す契約（純関数はローカル時刻取得を行わない）。

---

## 5. 純関数の性質（verification checklist）

- [ ] `now` / `random` / ファイル I/O / ネットワーク I/O を一切呼ばない
- [ ] 同じ入力に対し常に同じ出力を返す
- [ ] 例外ではなく Result / Union 型で失敗を表現（`InvalidTransition` 等）
- [ ] `tick` は本リストに含まれない（orchestrator であり I/O を行う、契約 §1 / §5 参照）

---

## 6. 参照

- 共通契約 §2 Transition Table（本ファイルの `transition` は §2 表と完全一致する）
- 共通契約 §4 Pure Function Signatures
- FS adapter 実装: [./polling-state.md](./polling-state.md)
