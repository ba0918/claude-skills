---
name: goal-loop
description: 機械検証可能な条件（oracle コマンド）が真になるまで「oracle 実行 → 失敗出力を implementer に渡して修正」を自律反復する条件収束型ループ。「全テスト green まで回して」「lint エラーゼロまで直して」「ビルドが通るまで」で起動。oracle ファイル群をハッシュロックし、テストを弱めて合格する oracle-gaming を機械的に遮断（oracle_tampered で即 halt）。同一失敗の stall・往復の oscillation を検出して無限ループを防ぐ。「goal-loop」「ゴールループ」「収束するまで」「〜が通るまで繰り返して」でも起動。
---

# Goal Loop

**共通契約（必読・直リンク）:** [../shared/references/convergence-pattern.md](../shared/references/convergence-pattern.md)

oracle（判定コマンド）が真になるまで修正を自律反復する。本 SKILL.md は薄い orchestrator であり、
oracle 整合・収束判定・安全ブレーキの仕様は契約側を参照する（複製しない）。

## 不変条件（契約 §3 / §5）

1. **oracle はコントローラ（あなた）が実行する**。implementer の「通りました」は採らない
2. **oracle_files はハッシュロック**し、毎イテレーションの oracle 実行直前に verify する。
   改変検出 = `oracle_tampered` で即 halt（実装の巻き戻しはせず、人間に報告）
3. ループ内で manifest を更新しない。oracle の変更はループ外で人間が行う
4. 安全ブレーキ（max_iter=8 / max_wallclock=30m / kill file 2 系統）なしで回さない。
   kill file の意味論（`.STOP` graceful / `.STOP.hard` hard、絶対パス解決）は
   [polling-pattern.md §6](../shared/references/polling-pattern.md#6-safety-brakes) に従う

## Argument Format

```
goal-loop "<goal の自然言語記述>" [--oracle "COMMAND"] [--oracle-files PATH...]
          [--max-iter N] [--max-wallclock DURATION]
```

## Steps

### Step 1: Oracle の確定

1. `--oracle` があればそれ。無ければ goal 記述とプロジェクト構成（package.json / Cargo.toml /
   pyproject.toml / Makefile 等）から判定コマンドを推定する
2. `--oracle-files` があればそれ。無ければ oracle が読む検証定義（テストディレクトリ全体・
   lint 設定・検証スクリプト）を列挙する。**狭めない** — テストディレクトリは全体を含めるのが既定（契約 §2）
3. AskUserQuestion で oracle（コマンド + files + expected_exit）を 1 度だけ確認する。
   ヘッドレス文脈（cycle 内等）では推定値をそのまま採用し、報告に明記する

### Step 2: Lock

```bash
TS=$(date +%Y%m%d%H%M%S); WORK=.claude/tmp/goal-loop/$TS; mkdir -p $WORK
python3 {skill_dir}/scripts/goal_loop.py lock {oracle_files...} --out $WORK/manifest.json
```

### Step 3: Iteration Loop（契約 §5 の擬似コードに準拠）

各イテレーション i = 1..max_iter で:

1. **Kill file check**: `.claude/tmp/goal-loop/$TS/.STOP`（graceful）/ `.STOP.hard` を確認、存在で即 halt
2. **Integrity verify**: `python3 {skill_dir}/scripts/goal_loop.py verify $WORK/manifest.json`
   - exit 2 なら `halt_reason="oracle_tampered"`。改変パスを報告して**即終了**（修正もロールバックもしない）
3. **Oracle 実行**: oracle command を Bash で実行し、出力を `$WORK/iter-{i}.log` に保存
   - `expected_exit` と一致 → **収束**。Step 4 へ
4. **Signature 記録**: `python3 {skill_dir}/scripts/goal_loop.py signature < $WORK/iter-{i}.log` を
   履歴に追加し、stall / oscillation を判定（`detect_convergence_halt`、契約 §4.2）。検出で halt
5. **Implementer 委譲**: Agent（model: `sonnet`、大きな修正のみ `opus`）に以下を渡して修正させる:
   - oracle の失敗出力（当該 iter のログ）
   - 「**oracle_files（{列挙}）の編集は禁止**。テスト・検証定義を変更して通すのは失敗と同義」という明示指示
   - 修正対象はプロダクションコードのみ
6. 次のイテレーションへ

### Step 4: 完了報告（verification-gate 準拠）

```
## Goal Loop 結果
- converged: true/false（halt_reason: ...）
- iterations: N / max N
- oracle: {command}（exit {code}）
- 証拠: 最終 oracle 実行出力の末尾（$WORK/iter-{last}.log）
- oracle integrity: 全イテレーションで verify 合格 / oracle_tampered（改変パス列挙）
```

`converged: true` は**最終 oracle 実行の実出力**を証拠として提示できる場合のみ
（[verification-gate.md](../shared/references/verification-gate.md) — 証拠なしの完了主張禁止）。

## 合理化防止

| 言い訳 | 現実 |
|--------|------|
| 「このテストは仕様と食い違っているから直した方が早い」 | それは oracle の変更であり、ループ外で人間が判断する仕事。ループ内では `oracle_tampered` = 失敗 |
| 「flaky なテストだけ skip すれば収束する」 | skip の追加は oracle_files の改変。検出されて halt する。flaky の除外は人間が oracle を定義し直してから |
| 「implementer がテスト通ったと言っている」 | 自己申告は採らない。コントローラが oracle を再実行した結果だけが真 |
| 「あと 1 回回せば通りそうだから max_iter を増やそう」 | stall / oscillation 検出は「回しても収束しない」の機械判定。増やすのは人間の明示指示があるときだけ |

## 使い分け

条件収束型（本スキル） vs 対話型 TDD vs 指示駆動 iterate vs キュー消化 polling —
[契約 §7 の使い分け表](../shared/references/convergence-pattern.md#7-使い分け) を参照。

## Codex 版

なし（初版は Claude 版のみ）。
