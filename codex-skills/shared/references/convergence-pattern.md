# Convergence Pattern — Shared Contract（条件収束型ループ）

> **⚠️ Warning:** 本契約は [polling-pattern.md](polling-pattern.md)（キュー消化型）の姉妹契約であり、
> 「機械検証可能な条件が真になるまで回す」ループ族の共通仕様を定義する。oracle 整合・収束判定・
> 安全ブレーキの変更は全実装スキル（`skills/goal-loop/` 等）に影響する。同一 PR で同期更新すること。

---

## 1. Overview — 2 つのループ族

| 族 | 契約 | 停止条件 | 例 |
|---|---|---|---|
| キュー消化型 | polling-pattern.md | キューが空 / kill / brake | issue polling / github-issue polling |
| **条件収束型** | 本契約 | **oracle が検証可能に真** / kill / brake / 収束不能検出 | goal-loop（「全テスト green まで回す」） |

条件収束型の最大の脅威は **oracle-gaming（Goodhart の法則）**: 目標が計測になった瞬間、
「テストを直す」より「テストを弱める」方が常に安い。自律圧力下の implementer は
悪意なしにこの経路へ滑り落ちる。本契約はこれを**機械的に**遮断する。

---

## 2. Oracle

```
Oracle {
  command:       str        # 判定コマンド（例: "python3 -m unittest discover"）
  expected_exit: int = 0    # 成功とみなす exit code
  oracle_files:  [str]      # oracle の意味を定義するファイル群（テスト・検証スクリプト・期待値）
}
```

- `command` は**機械実行可能**でなければならない。「〜が良くなったら」のような LLM 判定を
  oracle にしない（判定者が動かせる目標は目標ではない）
- `oracle_files` はループ開始時に確定する。テストディレクトリ全体を含めるのが既定
  （狭くするほど gaming の抜け道が増える）

---

## 3. Oracle Integrity（ハッシュロック — Goodhart 遮断の中核）

1. **Lock**: ループ開始時に `oracle_files` の各ファイル sha256 を manifest として記録する
2. **Verify**: **毎イテレーションの oracle 実行直前**に manifest を再検証する
3. 不一致（変更・削除・oracle_files 内への新規テスト skip 追加を含む書き換え）を検出したら、
   即 `halt_reason="oracle_tampered"` で停止し、改変されたパスを報告する。**実装の巻き戻しはしない**
   （何が起きたかを人間が見るため。改変が implementer の暴走か正当な仕様変更かは人間が判断する）

**不変条件:**

- implementer には oracle_files を**編集する権限がない**ことをプロンプトで明示し、
  かつ編集されても Verify が検出する（пронプト規律に依存しない二重防御）
- 正当な oracle 変更（仕様変更・テスト追加）は**ループ外**で人間が行い、ループを最初から再開始する。
  ループ内での manifest 更新 API は**存在させない**（あれば必ず使われる）
- oracle の**実行**はループコントローラが行う。implementer の「テスト通りました」という
  自己申告は採らない（maker/checker 分離。[verification-gate.md](verification-gate.md) 準拠）

---

## 4. 収束判定（failed_streak より細かい停止条件）

失敗し続けても**違う失敗**なら前進かもしれない。同じ失敗の反復と往復だけを止める。

### 4.1 Failure Signature

oracle 失敗出力を正規化（行トリム / タイムスタンプ・実行時間・16進アドレスの除去）して
sha256 先頭 16 hex を取る。イテレーションごとに履歴に積む。

### 4.2 純関数

| Function | Signature | 判定 |
|---|---|---|
| `oracle_manifest(contents)` | `(dict[path, bytes]) -> dict[path, hex64]` | lock 用 manifest 生成 |
| `verify_oracle_integrity(manifest, current)` | `(dict, dict) -> Ok \| Tampered{paths}` | 変更・削除・追加をすべて検出 |
| `failure_signature(output)` | `(str) -> hex16` | §4.1 の正規化 + hash |
| `detect_convergence_halt(history, config)` | `(list[hex16], Config) -> None \| "stall" \| "oscillation"` | stall: 末尾 `stall_limit` 個が同一シグネチャ。oscillation: 末尾 `window` 個が周期 2〜`max_period` の繰り返しパターン |

全て副作用なし・time / random / I/O 不使用。実装スキルは unittest で検証すること。

---

## 5. Iteration Loop

```
goal_loop(oracle, config) -> LoopResult:
    manifest = lock(oracle.oracle_files)                     # §3
    history = []
    for i in 1..config.max_iter:
        if kill_file_exists(): return halt("stop.graceful" | "stop.hard")   # polling-pattern §6.1
        if wallclock_exceeded(): return halt("max_wallclock")
        if verify_oracle_integrity(manifest, rehash()) is Tampered:
            return halt("oracle_tampered", paths)            # §3
        result = run(oracle.command)                         # コントローラが実行
        if result.exit == oracle.expected_exit:
            return success(i, evidence=result.output_tail)   # verification-gate 準拠の証拠
        sig = failure_signature(result.output)
        history.append(sig)
        if (h := detect_convergence_halt(history, config)):
            return halt(h)                                   # stall / oscillation
        implementer_fix(result.output)                       # maker: 失敗出力を渡して修正させる
    return halt("max_iter")
```

- 安全ブレーキ（kill file 2 系統 / max_iter / max_wallclock）は polling-pattern §6 の値と
  意味論を流用する。**ブレーキのない自律ループはこのリポジトリに追加しない**（自律ループの支配原則）
- IterationResult / LoopResult は構造化フィールドのみ（自由文禁止、polling-pattern §7 の哲学）:
  `LoopResult {iterations, converged: bool, halt_reason?, tampered_paths?, final_signature?}`

---

## 6. Default Config

```yaml
max_iter: 8
max_wallclock: 30m
stall_limit: 3        # 同一シグネチャ 3 連続で stall
window: 6             # oscillation 検出の観測窓
max_period: 3         # 検出する往復周期の上限
```

## 7. 使い分け

| スキル | ループ | 向き |
|---|---|---|
| test-driven-development | 人間対話型 RED-GREEN-REFACTOR | 新規実装 |
| iterate | 指示駆動の 1 パス改善 | cycle 後の追加修正 |
| **goal-loop（本契約）** | oracle 収束まで自律反復 | 「全テスト green まで」「lint ゼロまで」型の明確な条件 |
| issue polling | キュー消化 | 作業の量を捌く |

## 8. 参照

- [polling-pattern.md](polling-pattern.md) — 安全ブレーキ / kill file / 構造化結果の定義元
- [verification-gate.md](verification-gate.md) — 証拠なし完了主張の防止（oracle 実行ログが証拠）
