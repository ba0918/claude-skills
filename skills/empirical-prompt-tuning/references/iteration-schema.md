# Iteration Record Schema

`.claude/tmp/empirical/{ts}/iterations.jsonl` に 1 行 1 レコードで append する。
構造化フィールドのみ。自由文禁止。

## Schema

```json
{
  "iteration": 1,
  "prompt_bytes": 4200,
  "checklist_sha256": "abc123...",
  "instruction_fingerprint": "def456...",
  "eval_strategy": "task_scenario | compliance_probe",
  "k_runs": 1,
  "scenarios": [
    {
      "id": "A",
      "title": "中央値シナリオ",
      "success": true,
      "precision": 0.9,
      "steps": 4,
      "duration_ms": 20000,
      "retries": 0,
      "friction": [
        {
          "category": "ambiguous_term | missing_premise | contradictory | over_specified | rationalization_hook | self_containment_gap | uncategorized",
          "detail": "自由記述（補足）",
          "checklist_item_index": null
        }
      ],
      "checker_grades": [
        { "requirement_index": 0, "result": "pass | fail | partial", "evidence": "..." }
      ]
    }
  ],
  "exit_verdict": "continue | converged | diverged | bloat_advisory | halt",
  "halt_reason": null
}
```

## フィールド定義

| フィールド | 必須 | 意味 |
|-----------|------|------|
| `iteration` | yes | 0-origin。Iteration 0 は description/body 整合チェック（静的） |
| `prompt_bytes` | yes | 対象プロンプトのバイト数。肥大化検出に使用 |
| `checklist_sha256` | yes | baseline 確定時のチェックリスト sha256。改変検出に使用 |
| `instruction_fingerprint` | yes | 対象ファイル群の内容 sha256。instruction バージョンの追跡 |
| `eval_strategy` | yes | `task_scenario`（能動的ワークフロー）or `compliance_probe`（受動的制約） |
| `k_runs` | yes | 同一シナリオの並列実行回数（デフォルト 1） |
| `scenarios[].success` | yes | `[critical]` 要件が全 pass |
| `scenarios[].precision` | yes | 要件達成率（0.0〜1.0） |
| `scenarios[].steps` | yes | 実行者の tool_uses 数 |
| `scenarios[].duration_ms` | yes | 実行者の duration_ms |
| `scenarios[].friction` | yes | 摩擦報告（空配列可）。category は固定タクソノミ |
| `scenarios[].checker_grades` | yes | checker の採点結果 |
| `exit_verdict` | yes | `convergence.py` の `resolve_exit_verdict()` が返す値 |
| `halt_reason` | no | halt 時のみ: `max_iter` / `max_wallclock` / `kill_file` / `checklist_tampered` |

## 可搬 fixture への変換

収束完了時（`exit_verdict == "converged"`）、最終 iteration のシナリオ + チェックリストを
`fixture.json` として出力する。フォーマットは SKILL.md §E を参照。
