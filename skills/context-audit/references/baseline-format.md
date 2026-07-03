# Baseline Format（意図的差分の suppression）

意図的な差分による誤検知を抑制するための baseline。`.claude/context-audit-baseline.json` に置く。

## なぜ commit するのか / tmp と別扱い

baseline は**チーム共有目的**（「この finding は我々のプロジェクトでは意図的」という合意）なので
`.claude/tmp/`（git-ignored）ではなく**リポジトリに commit する**。中間 JSON・レポートは
`.claude/tmp/context-audit/`（git-ignored）に出力するが、baseline だけは追跡対象。

## 格納するのは opaque finding ID のみ

**検出値・本文・行の内容は絶対に載せない**。格納するのは opaque な finding ID（hash）だけ。
これにより commit された baseline から機密が漏れることはない（v2 の hash 形式でも不変条件）。

### finding ID の構成（v1）

`aggregate_report.finding_id` が算出する:

```
finding_id = sha256(f"{id}|{where}|{what}")[:16]
```

- `what` は secret redaction 済み、かつ hash 化されるため opaque。
- `id`（CA-* rule ID）+ `where`（file:line）+ `what` の組で 1 finding を一意に識別。

## スキーマ

```json
{
  "version": 1,
  "suppressions": [
    "3f2a1b0c9d8e7f60",
    "a1b2c3d4e5f60718"
  ]
}
```

- `version`: baseline フォーマットのバージョン（v1 = 単純 ID リスト）。
- `suppressions`: suppress する finding ID の配列。

## 運用（--update-baseline）

- 初回実行時に baseline が不在なら first-run フロー（現状を baseline 化 / triage / フルレポート）を提示。
- `--update-baseline` で現在の finding を baseline に確定（以降は新規 finding のみ提示）。実装は
  `aggregate_report.py --update-baseline PATH`（`build_baseline` 純関数、opaque ID のみ書き出し）:

  ```bash
  python3 skills/context-audit/scripts/aggregate_report.py \
    .claude/tmp/context-audit/findings-{ts}.json \
    --update-baseline .claude/context-audit-baseline.json
  ```
- suppress された finding は**レポートに件数のみ表示**（`M suppressed`）。silent truncation は禁止。

## stale 抑制リスク（v1 の既知の限界）

v1 の finding ID は `where`（file:line）を含むため、**行が動くと ID が変わり suppression が外れる**
（＝再び表示される。安全側の挙動）。逆に、別の finding がたまたま同じ ID になる衝突は
sha256 により実質ゼロ。

- **v2 候補**: claim 正規化 hash（行番号非依存）+ expiry（一定期間で自動失効）。
  行移動に強い suppression と、陳腐化した suppression の自動掃除を提供する。v1 は単純さを優先。
