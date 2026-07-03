# judge-protocol — 判定エージェント契約

Tier 1 選択シミュレーションの判定エージェント（Agent ツール、**model: sonnet 明示**、新規 subagent）の入出力契約。バイアス対策の一般則（自分の結論を渡さない / 敵対的フレーミング等）は `skills/shared/references/codex-integration.md` の既存ドクトリンを参照し、ここでは再記述しない。

## 判定エージェントに渡すもの / 渡さないもの

- **渡す**: description 一覧（`{name, description}` の JSON）＋ 架空指示のケースバッチ（`{case_id, text}` の配列）。
- **渡さない**: SKILL.md 本文。本文を見せると実発火時のモデルの視界と乖離し false positive を生む（empirical-prompt-tuning Iteration 0 と同じ思想）。これは実発火時にモデルが description しか見ないことの再現。
- **ツール禁止**: プロンプトで「ツールは一切使うな・ファイルを読むな・与えられた一覧のみで判定せよ」を明示する。これは prompt-level の **soft guarantee** であり、ツールアクセスを機械的に剥奪するものではない（この限界を明記する）。

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
- 判定モデル（sonnet）は実運用のセッションモデルと異なる。
- したがって Tier 1 の recall/precision は **sonnet 選択器相対の指標**であり、Tier 2 実発火との**乖離率がキャリブレーション信号**になる。
- 「判定モデル」「Tier 2 の実行条件（`--max-turns` / timeout / worktree）」は knob である。
- 判定エージェントのツール禁止は prompt-level の **soft guarantee** である。
