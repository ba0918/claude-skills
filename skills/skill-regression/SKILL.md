---
name: skill-regression
description: スキルの「調律済みの挙動」を fixture（シナリオ + 要件チェックリスト）として資産化し、SKILL.md や共有契約の変更時に影響スキルだけへ回帰評価を回すハーネス。empirical tuning で実測した合格基準を使い捨てず、再実行可能な回帰資産に変換する。共有契約 1 ファイルの編集が参照スキル十数個の挙動を無検証で変える問題を、依存グラフ逆引き + 検証台帳 + CI ゲートで機械的に防ぐ。「skill-regression」「回帰評価」「フィクスチャ資産化」「retune」「共有契約の影響確認」「スキルのリグレッション」で起動。本リポジトリ（スキル集リポジトリ）専用。
---

# Skill Regression

スキルは prose で書かれたプログラムであり、SKILL.md・references・共有契約の編集はすべて「挙動変更」である。
しかし empirical tuning で確立した合格基準はセッションと共に消え、次の編集が調律済みの挙動を
壊しても誰も気づけない。本スキルはその合格基準を **fixture として資産化**し、
挙動面が変わったスキルだけに回帰評価を回して台帳に記録する。

- **trigger-eval** が守るのは「正しく発火するか」。本スキルが守るのは「発火した後、正しく実行されるか」
- fixture の生産手段は問わない（empirical tuning の実測・plan 文書の受け入れ条件・手動設計のいずれでも良い）。
  本スキルは fixture を **消費（再実行）** する側で、特定の生産スキルには依存しない

## 用語

| 用語 | 定義 |
|------|------|
| 挙動面 (behavior surface) | スキルの実行時挙動に影響しうるファイル集合。`skills/<name>/` 配下全部（test_*.py / __pycache__ 除く）+ SKILL.md から相対 .md リンクで到達できる推移閉包（共有契約を含む） |
| fixture | `skills/<name>/fixtures.json`。シナリオ + [critical] 付き要件チェックリストの集合。スキーマは [references/fixture-schema.md](references/fixture-schema.md) |
| 台帳 (ledger) | `skills/skill-regression/ledger.json`。「この挙動面のときに全シナリオ合格した」という検証イベントの記録。commit する |

## 実行契約

- スクリプトは常に絶対パスで呼ぶ: `python3 {skill_dir}/scripts/ledger.py <mode> {repo_root}`。
  `{skill_dir}` は本 SKILL.md のあるディレクトリ、`{repo_root}` はスキル集リポジトリの root（通常 cwd）
- fixture を持つスキルだけが追跡対象（opt-in）。fixture のないスキルは check 対象外
- 台帳の更新（`--update`）は **全シナリオ合格のエビデンスを得た後のみ**。
  [verification-gate.md](../shared/references/verification-gate.md) 準拠 — 証拠なしの「合格したはず」で台帳を進めない
- 実行せず「この変更は挙動に影響しない」と判断する場合は `--update <skill> --accept` を使う。
  台帳に `accepted-without-run` と明示記録され、判断の痕跡が残る（黙殺と区別される）

## ワークフロー選択

| 入力 | ワークフロー |
|------|-------------|
| 「fixture 化して」「資産化して」（tuning 直後・plan 完了後） | capture |
| 「回帰評価して」「この変更の影響を確認して」（契約・SKILL.md 編集後） | run |
| 「状況見せて」「どれが stale？」 | status |
| CI が `[stale]` / `[unverified]` で fail した | run（対象は fail メッセージのスキル） |

## capture — 合格基準の資産化

1. **素材の特定**: 対象スキルの合格基準の出どころを確認する。優先順:
   (a) 直近の empirical tuning セッションのシナリオ + 要件チェックリスト（実測済みで最良）
   (b) `docs/plans/` の該当 plan の受け入れ条件
   (c) どちらも無ければ [references/fixture-schema.md](references/fixture-schema.md) の設計指針に従い新規設計
2. **fixtures.json の作成**: スキーマに従い `skills/<skill>/fixtures.json` を書く。
   シナリオは 2〜3 本（中央値 1 + edge 1〜2）、要件は各 3〜7 項目、`critical: true` を最低 1 つ
3. **初回実行**: run ワークフローで全シナリオを実行し、全合格を確認する。
   落ちる fixture をそのまま資産化しない（後続の回帰評価が常に赤くなり、台帳が意味を失う）
4. **台帳記録**: `python3 {skill_dir}/scripts/ledger.py --update <skill> {repo_root}`

## run — 回帰評価

1. **対象の決定**:
   - スキル名の指定があればそれ。無ければ変更ファイルから逆引きする:
     `git diff --name-only HEAD`（未 commit 変更）または指定 commit 範囲を取り、
     `python3 {skill_dir}/scripts/ledger.py --impact <changed>... {repo_root}` で影響スキルを得る
   - 影響スキルのうち fixture を持つものだけが評価対象。持たないものは対象外として報告に列挙する
2. **実行**: 対象スキルの `fixtures.json` を読み、シナリオごとに白紙実行者 subagent を
   [references/executor-contract.md](references/executor-contract.md) の契約で起動する。
   - 同一メッセージ内で複数 Agent 呼び出しを並べて並行実行（[orchestration-patterns.md](../shared/references/orchestration-patterns.md) 準拠）
   - 実行者の model は `sonnet` を明示（機械的なシナリオ実行。判断の重いスキルで精度が出ない場合のみ `opus` に上げ、fixture の `executor_model` に記録して固定する）
   - ファイルを生成・編集するシナリオは使い捨て git worktree で隔離し、終了後に破棄する
3. **判定**: executor-contract の判定規則で各シナリオを ○/× 判定する。
   スキル単位の合格 = 全シナリオで `[critical]` 要件が全て ○
4. **報告**: シナリオ別の結果表（合格/不合格・落ちた critical 項目・実行者の不明瞭点自己申告）を提示する
5. **台帳更新**: 全合格したスキルのみ `--update <skill>`。不合格のスキルは台帳を進めず、
   原因（スキル側の回帰 or fixture の陳腐化）を切り分けて報告する。
   fixture の陳腐化と判断した場合は fixture を修正して capture からやり直す —
   ただし**シナリオを楽にする方向の修正は禁止**（回帰を隠すだけ）

## status — 棚卸し

- `python3 {skill_dir}/scripts/ledger.py --status {repo_root}` で全追跡スキルの
  verified / stale / unverified / orphan を表示する
- `--check` は CI と同一判定（issue があれば exit 1）。orphan は `--remove <skill>` で掃除する

## CI ゲート

`.github/workflows/validate.yml` が `ledger.py --check` を実行する。fixture を持つスキルの
挙動面（共有契約を含む）が前回検証時から変わっていると CI が fail し、
再評価（run → `--update`）または明示的な不要判断（`--update --accept`）を要求する。
sync-manifest と同じ思想: ドリフトを止めるのではなく、**黙殺だけを不可能にする**。

## 合理化防止

| 言い訳 | 現実 |
|--------|------|
| 「コメント修正だから挙動に影響ない、check は無視」 | 影響しないなら `--update --accept` で判断を記録する。無視は次の実変更で混ざって追えなくなる |
| 「全シナリオ回すのは重いから 1 本だけ」 | 1 本合格は合格ではない。台帳は全シナリオ合格の記録。重いなら fixture のシナリオ数を capture 時点で絞る |
| 「落ちたのは fixture が古いだけ」 | 切り分けのエビデンスなしにそう断定しない。シナリオを楽にして通すのは回帰の隠蔽 |
| 「実行者に前回の結果を渡せば速い」 | 白紙実行者でなくなり評価が汚染される。毎回新規 dispatch |
| 「自分で SKILL.md を読んで大丈夫と判断した」 | 自己再読はバイアスの塊。判断するなら `--accept` で痕跡を残す |

## Red Flags

- 台帳の `result` が `accepted-without-run` ばかりになっている（run が形骸化している兆候）
- 同一スキルの fixture が短期間に繰り返し「陳腐化」扱いで書き換えられている
- run の報告に落ちた critical 項目の明示がない
- CI の `[stale]` を PR 内で解消せず main に積んでいる

## 関連

- [fixture-schema.md](references/fixture-schema.md) — fixtures.json のスキーマと設計指針
- [executor-contract.md](references/executor-contract.md) — 白紙実行者の起動契約と判定規則
- [orchestration-patterns.md](../shared/references/orchestration-patterns.md) / [verification-gate.md](../shared/references/verification-gate.md)
