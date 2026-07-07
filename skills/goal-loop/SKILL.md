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

1. `--oracle` があればそれ。無ければ goal 記述とプロジェクト構成から判定コマンドを推定する。
   推定はプロジェクトが**公式に案内する入口を優先**する（README 記載のコマンド >
   Makefile / package.json scripts の test ターゲット > 生のテストランナー直叩き）
2. `--oracle-files` があればそれ。無ければ oracle が読む検証定義（テストディレクトリ全体・
   lint 設定・検証スクリプト）を列挙する。**狭めない** — テストディレクトリは全体を含めるのが既定（契約 §2）。
   oracle コマンドを**定義する**ファイル（Makefile の test ターゲット等）も含めるのを推奨
   （コマンド書き換えによる gaming も遮断できる）。ただし implementer が正当に触り得る
   ファイル（package.json 全体等）は誤 halt の元なので判断して除外してよい。
   ビルド生成物（`__pycache__` / `*.pyc`）は lock がスクリプト側で自動除外する
3. AskUserQuestion で oracle（コマンド + files + expected_exit）を 1 度だけ確認する。
   ヘッドレス文脈（cycle 内等）では推定値をそのまま採用し、報告に明記する

### Step 2: Lock

```bash
TS=$(date +%Y%m%d%H%M%S); WORK=$(pwd)/.claude/tmp/goal-loop/$TS; mkdir -p $WORK
python3 {skill_dir}/scripts/goal_loop.py lock {oracle_files...} --out $WORK/manifest.json
```

`$WORK` は**絶対パスで確定させ、以降の全ステップで同じ値を使い続ける**（Bash 呼び出しは
ステートレスなので、確定した WORK の絶対パスを自分のコンテキストに控えておく。
再取得の仕組みは作らない — TS を跨いで解決しようとするとロック対象がずれる）。

manifest のパスは **lock 実行時の cwd 相対**で記録・解決される。lock / verify は必ず
**プロジェクトルート（同じ cwd）**で実行すること — 別ディレクトリから verify を叩くと
ファイルが見つからず偽 tamper（exit 2）になる。

### Step 3: Iteration Loop（契約 §5 の擬似コードに準拠）

各イテレーション i = 1..max_iter で:

1. **Kill file check**: `$WORK/.STOP`（graceful）/ `$WORK/.STOP.hard` を確認、存在で即 halt。
   kill file の基準ディレクトリは**絶対パスの $WORK**（polling-pattern §6 の「絶対パス解決」は
   これで満たす — 相対パスで別の場所を見ない）
2. **Wallclock check**: 開始からの経過が max_wallclock（既定 30m）を超えていたら
   `halt_reason="max_wallclock"` で終了
3. **Integrity verify**: `python3 {skill_dir}/scripts/goal_loop.py verify $WORK/manifest.json`
   - exit 2 なら `halt_reason="oracle_tampered"`。改変パスを報告して**即終了**（修正もロールバックもしない）
4. **Oracle 実行**: oracle command を Bash で実行し、出力を `$WORK/iter-{i}.log` に保存
   - `expected_exit` と一致 → **収束**。Step 4 へ（収束した iter の signature は積まない）
5. **Signature 記録と収束不能判定**（両方 CLI で機械実行 — 暗算・目視判定をしない）:
   ```bash
   python3 {skill_dir}/scripts/goal_loop.py signature < $WORK/iter-{i}.log >> $WORK/history.txt
   python3 {skill_dir}/scripts/goal_loop.py halt $WORK/history.txt
   ```
   halt の exit code: 0 = 継続 / 3 = stall / 4 = oscillation。3 か 4 なら halt_reason に
   そのまま採用して終了
6. **Implementer 委譲**: Agent（model: `sonnet`、大きな修正のみ `opus`）に以下を渡して修正させる。
   委譲は**同期的に扱う** — implementer の結果を受け取るまでコントローラのターンを終えない
   （結果待ちのままターンを終えるとループが迷子になる）。implementer が no-op で戻っても、
   oracle 再実行・signature 記録・halt 判定は**毎イテレーション実行**する（stall 検出の反復を
   成立させるため。no-op を理由にループを手動で打ち切らない）:
   - oracle の失敗出力（当該 iter のログ）
   - 「**oracle_files（{列挙}）の編集は禁止**。テスト・検証定義を変更して通すのは失敗と同義」という明示指示
   - 「コード内に明示された承認ゲート・制約（『変更には承認が必要』等のコメント / fence）を
     無断で越えない。**越えなければ修正不能なら何も変更せず、その旨を報告して戻る（no-op）**」という明示指示
   - 修正対象はプロダクションコードのみ
7. 次のイテレーションへ

> **収束不能の設計意図**: テスト期待値とプロダクション制約（承認ゲート）が衝突して自律修正が
> 原理的に不可能な場合、専用の halt_reason は発明しない。implementer が no-op で戻る →
> 同一失敗が反復 → **stall として機械停止**するのが正規経路。報告にはループ外で人間が
> 決めるべき選択肢（承認を得て変更 / oracle を定義し直して再 lock・再開始）を申し送りとして含める。

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
