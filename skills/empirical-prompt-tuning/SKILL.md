---
name: empirical-prompt-tuning
description: agent 向けテキスト指示（skill / slash command / task プロンプト / CLAUDE.md 節 / rules / コード生成プロンプト）を、バイアスを排した 3 役分離（チューナー / 実行者 / checker）で評価し、摩擦の固定タクソノミと統計的採択ゲートで反復改善する。収束した検証資産は可搬 fixture として資産化する。「empirical-prompt-tuning」「プロンプトチューニング」「指示の品質を測りたい」「skill を堅牢化したい」「このプロンプトが分かりにくい原因を知りたい」「rule が守られているか確認したい」で起動。`trigger-eval`（選択層 = description→発火の精度）の姉妹スキル（本文層 = 実行の質）。
---

# Empirical Prompt Tuning

プロンプトの品質は書いた本人には分からない。書き手が「明瞭だ」と思うものほど、別エージェントが読むと詰まる。**バイアスを排した 3 役分離で実際に動かし、固定タクソノミと純関数で評価して反復する** のが本 skill の核。改善が頭打ちになるまで止めない。
## いつ使うか

- skill / slash command / タスクプロンプトを新規作成・大幅改訂した直後
- エージェントが期待通り動かず、原因を指示側の曖昧さに求めたいとき
- 重要度の高い指示（頻繁に使う skill、自動化の中核プロンプト）を堅牢化したいとき
- CLAUDE.md 節 / rules が実際に守られているか確認したいとき

使わない場面:
- 一回限りの使い捨てプロンプト（評価コストが割に合わない）
- 成功率の改善が目的ではなく、書き手の主観的好みを反映したいだけのとき

## 対象タイプの判定（最初に行う）

| 対象の性質 | eval_strategy | 評価手法 |
|-----------|---------------|----------|
| 実行すると成果物が生まれる（skill / command / task） | `task_scenario` | タスクシナリオ実行 |
| 行動を制約する（rules / CLAUDE.md 節 / ガイドライン） | `compliance_probe` | 違反誘惑シナリオで遵守率測定 |

迷ったら `task_scenario`。詳細は [references/compliance-probe.md](references/compliance-probe.md)。

## ワークフロー

### Iteration 0 — description と body の整合チェック（静的、dispatch 不要）

- frontmatter `description` が謳う trigger / 用途と body がカバーする範囲を突合
- 乖離があれば iter 1 に進む前に description か body を合わせる
- これを飛ばすと実行者は description に合わせて body を「再解釈」し、false positive が出る

### Phase 1 — ベースライン準備

1. **対象プロンプトを確定**し、`compute_instruction_fingerprint()` で fingerprint を記録
2. **評価シナリオ** 2〜3 種を設計:
   - `task_scenario`: 中央値タスク 1 + edge 1〜2
   - `compliance_probe`: 違反誘惑シナリオ 1〜2 + 正常遵守 1（詳細は [compliance-probe.md](references/compliance-probe.md)）
3. **要件チェックリスト** を各シナリオに 3〜7 項目で設計:
   - `[critical]` を最低 1 つ含める（0 件だと成功判定が vacuous になる）
   - 要件は観測可能な形で書く（「正しく動く」ではなく具体的な検証条件）
   - **事前に固定し、以後動かさない**
4. シナリオ + チェックリストを JSON 正規化して **sha256 をロック**（`verify_checklist_integrity()`）

### Phase 2 — 実行（3 役分離）

**2a. 実行者 サブエージェント を dispatch**

新規サブエージェントを毎回作成する（前回の改善を学習したエージェントは再利用しない）。並列で複数シナリオを同時実行する場合は単一メッセージ内で複数サブエージェント呼び出しを並べる。

```
あなたは <対象プロンプト名> を白紙で読む実行者です。

## 対象プロンプト
<対象プロンプトの本文を全文貼る or ファイルパスを指定して読ませる>

## シナリオ
<シナリオの状況設定>

## タスク
1. 対象プロンプトに従ってシナリオを実行し、成果物を生成する。
2. 終了時に下記レポートを返す。

## 摩擦報告
指示で詰まった箇所を以下の分類で報告してください:
- ambiguous_term: 複数解釈可能な語句
- missing_premise: 暗黙の前提知識が必要
- contradictory: 指示間の矛盾
- over_specified: 不必要に厳密
- rationalization_hook: 合理化で回避できる指示
- self_containment_gap: 外部参照なしでは完結しない

## レポート構造
- 成果物: <生成物 or 実行結果サマリ>
- 摩擦: [{ "category": "<分類>", "detail": "<詳細>" }, ...]
- 裁量補完: 指示で決まっておらず自分の判断で埋めた箇所（箇条書き）
- 再試行: 同じ判断をやり直した回数とその理由
```

> **注意**: 要件チェックリストは実行者に渡さない。自己採点バイアスの排除。

**2b. Checker サブエージェント を dispatch**

実行者とは別の新規 サブエージェント。詳細は [references/checker-protocol.md](references/checker-protocol.md)。

```
あなたは独立した採点者です。成果物が要件チェックリストを満たしているかを判定します。

## 成果物
<実行者の成果物>

## 要件チェックリスト
<要件一覧>

## タスク
各要件を pass/fail/partial で採点し、根拠を 1 行添えて JSON で返してください。
```

> **注意**: 対象プロンプト本文は checker に渡さない。プロンプトへの甘い解釈を排除。

### Phase 3 — 両面評価

戻ってきた結果から以下を記録（`iterations.jsonl` に append）:

**checker の採点（定量）:**
- 成功/失敗: `[critical]` 要件が全 pass のとき成功
- 精度: `pass=1.0, partial=0.5, fail=0.0` で算出、要件数で割る
- 失敗時は「どの [critical] 要件が落ちたか」を記録

**実行者の自己申告（定性）:**
- 摩擦報告（固定タクソノミで分類済み。詳細は [friction-taxonomy.md](references/friction-taxonomy.md)）
- 裁量補完箇所
- 再試行回数

**実行メトリクス:**
- ステップ数（ツール使用回数 `tool_uses`）
- 所要時間（`duration_ms`）

**収束判定:**
- `convergence.py` の `resolve_exit_verdict()` を呼び、verdict を記録

**重み付け**: 摩擦報告（定性）を主、メトリクス（定量）を補助とする。時間短縮だけ追いかけるとプロンプトが痩せすぎる。

### Phase 4 — 差分適用

不明瞭点を潰す最小修正をプロンプトに入れる。1 イテレーション 1 テーマ（関連する複数修正は OK、無関係な修正は次回に回す）。

修正前に:
1. **この修正が要件チェックリストのどの項目に効くか**を明示する
2. **checklist の sha256 が変わっていないこと**を `verify_checklist_integrity()` で verify

### Phase 5 — 再評価

新しい サブエージェント で Phase 2〜4 を繰り返す。`exit_verdict` が `continue` 以外になるまで回す。

## k-run 統計的採択ゲート

デフォルトは k=1（原本互換、コスト最小）。精密な評価が必要な場合:

```
--k-run 2   # 各シナリオ 2 並列実行
```

- k≥2 の場合、各シナリオの precision を k 回測定し中央値を採用
- 改善判定: 前回中央値と今回中央値の差が noise_band（run 間差の半分）を超えたときのみ「改善」と認定
- 「運が良かった run」での誤採択を機械的に排除

## 収束判定（純関数 — `scripts/convergence.py`）

判定はすべて `convergence.py` の純関数で行う。チューナーの主観判断は介入しない。

| 判定 | 条件 | 優先順位 |
|------|------|----------|
| `halt` | max_iter / max_wallclock / kill_file / checklist_tampered | 最高 |
| `diverged` | 同一摩擦カテゴリが threshold 回連続 | 高 |
| `bloat_advisory` | prompt_bytes が前回比 max_growth_pct 超 | 中（advisory） |
| `converged` | 連続 window 回で新規摩擦ゼロ + メトリクス飽和 | 低 |
| `continue` | 上記いずれにも該当しない | 最低 |

パラメータ:
- `window`: 2（連続クリア判定回数。重要度高は 3）
- `precision_delta_eps`: 0.03（精度飽和の閾値）
- `steps_tolerance_pct`: 0.10（ステップ数飽和の許容幅）
- `duration_tolerance_pct`: 0.15（所要時間飽和の許容幅）
- `max_iter`: 10（デフォルト。重要度高は 15 まで引き上げ可）
- `max_wallclock`: 3600s（1 時間）

## チェックリストのハッシュロック

baseline 確定時に scenarios + requirements を JSON 正規化して sha256 を記録。毎 iteration 開始時に `verify_checklist_integrity()` で verify し、hash 不一致は `checklist_tampered` halt。

意図的にチェックリストを変更する場合は「baseline リセット」として iteration 0 からやり直す。これにより「修正が通らないからチェックリストを緩める」操作に明示的なコスト（全イテレーションの破棄）を課す。

## 検収 fixture の資産化

収束完了時（`exit_verdict == "converged"`）、最終 iteration のシナリオ + [critical] 要件 + instruction fingerprint を可搬 JSON として出力:

```json
{
  "source_skill": "<対象スキル名 or null>",
  "instruction_fingerprint": "abc123...",
  "eval_strategy": "task_scenario",
  "converged_at": "2026-07-09T13:42:00Z",
  "scenarios": [
    {
      "id": "A",
      "title": "...",
      "prompt": "...",
      "requirements": [
        { "text": "...", "critical": true }
      ]
    }
  ],
  "convergence_summary": {
    "iterations": 5,
    "final_precision": 0.93,
    "k_runs": 1
  }
}
```

出力先: `.claude/tmp/empirical/{ts}/fixture.json`

この fixture は:
- 将来プロンプトを編集したとき、再実行して回帰検出に使える
- 本リポジトリでは `skill-regression` の `fixtures.json` に手動移送可能（[fixture-schema.md](../skill-regression/references/fixture-schema.md) の変換ガイド参照）

## `tool_uses` の質的解釈

精度だけ見ると指示の構造的問題が隠れる。`tool_uses` を **シナリオ間の相対値** として使うと欠陥が見える:

- シナリオ間で他シナリオ比 **3-5 倍以上** なら、その指示は自己完結性が低いサイン
- 典型例: 全シナリオ `tool_uses` が 1-3 なのに 1 シナリオだけ 15+ → そのシナリオ用の recipe が inline にない
- 対処: iter 2 で「最小完成例 inline」や「いつ references を読むかの指針」を追加

精度 100% でも `tool_uses` の偏りがあれば iter 2 発動の根拠になる。

## 環境制約

新規サブエージェントを起動できない環境では本 skill は **適用しない**。
- 代替案 1: 親セッションのユーザーに別セッションを起動して依頼
- 代替案 2: 評価を諦め「empirical evaluation skipped: dispatch unavailable」と明示報告
- **NG**: 自己再読で代替する（バイアスが入るので評価結果を信じてはいけない）

**構造審査モード**: 実行ではなくテキスト整合性だけをチェックしたい場合は、サブエージェント への依頼に「構造審査モード: 実行ではなくテキスト整合性チェック」と明記する。構造審査は empirical の代替ではなく補助（収束クリア判定には使えない）。

## 提示フォーマット

```
## Iteration N

### 変更点（前回差分）
- <修正内容 1 行>

### 実行結果（シナリオ別）
| シナリオ | 成功 | 精度 | steps | duration | retries |
|---|---|---|---|---|---|
| A | ○ | 90% | 4 | 20s | 0 |
| B | × | 60% | 9 | 41s | 2 |

### 摩擦報告（今回新出）
- <シナリオ B>: [critical] 要件 N が × — <落ちた理由 1 行>
- <シナリオ B>: [missing_premise] <詳細>

### 裁量補完（今回新出）
- <シナリオ B>: <補完内容>

### 次の修正案
- <最小修正 1 行>
- 対象要件: #N

（exit_verdict: continue | 収束まであと X 回クリア必要）
```

## Red flags（合理化に注意）

| 出てくる合理化 | 実態 |
|---|---|
| 「自分で読み直せば同じ効果がある」 | 直前に書いた文章を客観視はできない。必ず新規サブエージェントを起動する |
| 「1 シナリオで充分」 | 1 シナリオは過適合する。最低 2、できれば 3 |
| 「不明瞭点ゼロが 1 回出たから終わり」 | 偶然なこともある。連続 2 回で確定判定（`is_converged` が制御） |
| 「複数の不明瞭点を一気に潰そう」 | 何が効いたか分からなくなる。1 イテレーション 1 テーマ |
| 「関連する微修正も純粋に 1 件ずつ別 iter に分けよう」 | 逆方向の罠。"1 テーマ" は意味単位。関連する 2-3 件の微修正は 1 iter にまとめて良い |
| 「メトリクスが良いから摩擦報告は無視」 | 時間短縮は痩せすぎのサインにもなる。定性を主に |
| 「書き直した方が早い」 | 3 回以上同一分類の摩擦が減らないなら正解（`is_diverged`）。それ以前は逃げ |
| 「同じサブエージェントを使い回そう」 | 前回の改善を学習している。毎回新規に起動する |
| 「チェックリストが厳しすぎるから緩めよう」 | baseline リセット（iteration 0 からやり直し）が必要。ハッシュロックが強制する |
| 「checker の採点が間違っている」 | checker に不服がある場合は要件の書き方を改善する（次 baseline で）。今の iteration では checker の判定が final |

## よくある失敗

- **シナリオが楽すぎる / 難しすぎる**: どちらもシグナルが出ない。中央値 1 + edge 1 が基本
- **メトリクスだけ見る**: 時間短縮しか追わないとプロンプトが痩せすぎる
- **イテレーションごとに変更多すぎ**: どの修正が効いたか追えなくなる。1 テーマ 1 iter
- **シナリオを修正に合わせてチューニング**: チェックリストの sha256 が変わって halt する（設計通り）
- **checker に対象プロンプトを見せる**: 甘い解釈バイアスが復活する。絶対に渡さない

## 関連

- [trigger-eval](../trigger-eval/SKILL.md) — 選択層（description→発火）の姉妹スキル。本スキルが本文実行の質を測るのに対し、trigger-eval は発火精度を測る
- [skill-regression](../skill-regression/SKILL.md) — 本スキルの収束成果（fixture.json）を回帰資産に変換可能
- [skill-improve](../skill-improve/SKILL.md) — 受動分析（過去 JSONL）。本スキルは能動テスト
- [references/checker-protocol.md](references/checker-protocol.md) — checker サブエージェント 起動契約
- [references/iteration-schema.md](references/iteration-schema.md) — iteration JSON レコード schema
- [references/friction-taxonomy.md](references/friction-taxonomy.md) — 摩擦の 6 分類
- [references/compliance-probe.md](references/compliance-probe.md) — 受動的制約の評価手法
