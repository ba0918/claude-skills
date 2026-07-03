# judge-protocol — 判定エージェント契約

Tier 1 選択シミュレーションの判定エージェント（Agent ツール、**model: sonnet 明示**、新規 subagent）の入出力契約。バイアス対策の一般則（自分の結論を渡さない / 敵対的フレーミング等）は `skills/shared/references/codex-integration.md` の既存ドクトリンを参照し、ここでは再記述しない。

## 2 つの判定モード（selection / autonomous）

判定は 2 つの独立したモードで実施する。**入出力スキーマは共通**だが、判定エージェントに渡すフレーミングだけが異なる。

- **selection モード**（従来の既定挙動）: 「与えられた指示に最も適合するスキルを一覧から選べ。適合するものが無ければ `none` を返せ」= description 一覧の弁別性を測る。スキル起動を暗に前提とするフレーミング。
- **autonomous モード**（新設）: 「あなたは Claude Code アシスタントである。このユーザ指示に普通に応答するか、スキルを起動するか自分で決めよ。起動する場合のみスキル名を返し、普通に応答すべきなら `none` を返せ」= スキル起動を**強制しない**。実運用でモデルが「わざわざスキルを起動するに値するか」を自己判断する salience（想起）に近い分布を測る。

両モードとも同じ入力スキーマ・同じケースバッチを使い、**モードごとに独立した判定結果 JSON を生成する**（`judged-{mode}-iterN.json`）。結果を混合してはならない（下の妥当性限界を参照）。

## 判定エージェントに渡すもの / 渡さないもの

- **渡す**: description 一覧（`{name, description}` の JSON）＋ 架空指示のケースバッチ（`{case_id, text}` の配列）。
- **渡さない**: SKILL.md 本文。本文を見せると実発火時のモデルの視界と乖離し false positive を生む（empirical-prompt-tuning Iteration 0 と同じ思想）。これは実発火時にモデルが description しか見ないことの再現。
- **ツール禁止**: プロンプトで「ツールは一切使うな・与えられた入力のみで判定せよ」を明示する。これは prompt-level の **soft guarantee** であり、ツールアクセスを機械的に剥奪するものではない（この限界を明記する）。

### 入力の配布方法（正式契約）

判定エージェントへの入力は次の 2 通りのいずれかに限る:

1. **インライン渡し**: description 一覧とケースバッチをプロンプト本文に直接埋め込む。追加のファイル読取は発生しない。
2. **ファイル渡し**: `skills.json`（description 一覧）とケースバッチファイルの **2 ファイルのみ Read を許可**する。この 2 ファイル以外のツール・ファイル読取は禁止する。

いずれの場合も **SKILL.md 本文・その他ソースへのアクセスは禁止**（soft guarantee）。ファイル渡しでは「許可した 2 ファイル以外は読むな」をプロンプトに明示する。

## 入力スキーマ

```json
{
  "skills": [{"name": "commit", "description": "..."}, ...],
  "cases": [{"case_id": "c001", "text": "この変更をコミットして"}, ...]
}
```

- **バッチは 1 呼び出し最大 20 ケース**にチャンク分割する。複数バッチは並行 dispatch（最大 4 並行）。
- ケース順はシャッフルする（位置バイアス対策）。

## 出力スキーマ

判定エージェントは各ケースについて 1 つのラベルを返す:

```json
{"judgments": [{"case_id": "c001", "choice": "commit"}, {"case_id": "c002", "choice": "none"}, ...]}
```

- `choice` は description 一覧のいずれかの skill 名、または `none`（どのスキルも発火しないのが正しい）。
- **単一ラベルのみ**。複数スキルを挙げてはならない。

## 回収時の検証（駆動側の責務）

1. **「判定数 == ケース数」を検証**する。
2. `choice` の正規化（bare name 化）: plugin prefix が付いていたら除去し、Phase 0 と同じ namespace に揃える。
3. **INVALID の生成**（本書所掌）:
   - バッチ応答全体がパース不能 → **バッチ内全 case_id を 1 回だけ再判定**。それでも不正なら全 case_id を `predicted=INVALID` として実体化。
   - 個別 choice が (a) パース不能、(b) 一覧外のスキル名、(c) 複数スキル → その case を 1 回だけ再判定。それでも不正なら `INVALID`。
   - INVALID の**カウント方法**は `metrics-spec.md` 所掌（正解スキルの FN に数え、どの FP にも数えない）。

## stability 計測

同一ケースを独立に 2 判定する（j1, j2）。イテレーション 2 回目以降はデフォルトで**固定サンプル 20–30 ケースに縮約**する。サンプルは 1 回だけ決定的に選んで台帳に記録し、全イテレーションで同一のものを使う（`--full-stability` で全数に戻せる）。

## Tier 2（E2E 実発火）でのスキル名抽出・正規化

Tier 2 は `run_eval.py` 方式の stream 検出（`--output-format stream-json --include-partial-messages`、`content_block_start` → tool_use 検出、`CLAUDECODE` env 除去、最初の Skill tool_use 検出で即プロセス終了）。run_eval が boolean 検出なのに対し、本スキルは **Skill tool_use の `input` からスキル名を抽出して Phase 0 と同じ bare name に正規化する**（confusion 帰属のため）。**permission-mode は指定しない**（plan mode の system prompt が発火分布を変えキャリブレーションを汚染するため）。

## 妥当性限界（明記事項 / knob）

- Tier 1 の判定エージェントは「選ぶこと」を指示された**選択器**であり、自律発火（何も発火せず直接回答する）とは分布が異なる。
- **selection は弁別性の上界、autonomous は想起 (salience) の近似。両者の分布は異なるため結果を混合してはならない。** selection は「起動する前提でどれが最適か」を測るため recall/precision の上界を与え、autonomous は「そもそも起動に値するか」を含むため実運用の想起に近い。混合すると両者の異なる母集団を平均してしまい、どちらの信号も損なう。
- 判定モデル（sonnet）は実運用のセッションモデルと異なる。
- したがって Tier 1 の recall/precision は **sonnet 選択器相対の指標**であり、Tier 2 実発火との**乖離率がキャリブレーション信号**になる。
- 「判定モデル」「Tier 2 の実行条件（`--max-turns` / timeout / worktree）」は knob である。
- 判定エージェントのツール禁止は prompt-level の **soft guarantee** である。
