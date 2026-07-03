---
name: trigger-eval
description: スキルセットの description 発火精度（recall / precision / stability / 80-way confusion matrix）を、description-only の判定 subagent で機械的に実測し、衝突ペアを特定して description 改稿→再評価ループを収束まで回すメタスキル。実測エビデンス（メトリクス差分・holdout ゲート・Tier1↔Tier2 乖離率）で改善を証明する。「trigger-eval」「発火精度」「スキル発火の計測」「トリガー評価」「description 改稿」「confusion matrix でスキル衝突を見たい」で起動。`empirical-prompt-tuning`（本文実行の質）に対し選択層（description→発火）を測る姉妹スキル。対象は本リポジトリの `skills/`、`--dir PATH`、`--user-scope`（~/.claude/skills）。`--no-e2e` で Tier 2 実発火検証をスキップ。Tier 1 は selection / autonomous の 2 モードで計測し `--selection-only` で selection のみに絞れる。v1 はプラグインキャッシュのハッシュ付きネスト構造を対象外とする。
---

# trigger-eval

スキル数増加で劣化した「自然言語指示からの自発的スキル発火」を、description の品質として実測・改善するメタスキル。判定エージェントに **description 一覧しか渡さない**（実発火時のモデルの視界を再現）ことで、recall / precision / stability / confusion matrix を機械的に計測し、改稿→再評価を収束まで回す。

**位置づけ**: `empirical-prompt-tuning` が「本文実行の質」を測るのに対し、trigger-eval は「選択層（description → 発火）」を測る。`validate_repo.py` チェック11（トリガー語の静的存在チェック）とは静的/動的の補完関係。

## 最小実行レシピ

```
trigger-eval                # 本リポジトリの skills/ を対象に Phase 0→6
trigger-eval --dir PATH     # 任意のフラットなスキルディレクトリ
trigger-eval --user-scope   # ~/.claude/skills
trigger-eval --no-e2e       # Tier 2 実発火検証をスキップ（デフォルトは実行）
trigger-eval --selection-only  # Tier 1 を selection モードのみ計測（デフォルトは selection + autonomous）
```

command は作らない（skills-first 方針。single-workflow のため名前付き入口も不要）。

## アーキテクチャ: 静的プレパス + 2 層評価

| 層 | 方式 | コスト |
|----|------|--------|
| Phase 1.5 静的衝突プレパス | description の語彙 Jaccard で全ペア衝突候補を決定的に算出（`static_collisions.py`、LLM 不使用） | ほぼゼロ |
| Tier 1 選択シミュレーション | バイアス排除 subagent に description 一覧 + 架空指示バッチだけを渡し、使うスキル(or none)を JSON で選ばせる | 低（sonnet、1 呼び出し ≤20 ケース、並行 dispatch） |
| Tier 2 E2E 実発火検証 | `claude -p` に架空指示を素で渡し stream-json から Skill tool_use を検出。**使い捨て git worktree で実行** | 高（合計 6 セッション上限を駆動側 Bash ループで強制） |

判定・集計の詳細契約は参照資料に分離する（Progressive disclosure）:

- 判定エージェント契約: [references/judge-protocol.md](references/judge-protocol.md)
- ケース設計指針: [references/testcase-design.md](references/testcase-design.md)
- メトリクス厳密定義: [references/metrics-spec.md](references/metrics-spec.md)

バイアス対策の一般則は `skills/shared/references/codex-integration.md`、Agent 呼び出しのモデル階層は `skills/shared/references/orchestration-patterns.md` を参照（再記述しない）。

## ワークフロー

### Phase 0: 対象収集

```bash
python3 skills/trigger-eval/scripts/collect_descriptions.py --dir skills \
  --output .claude/tmp/trigger-eval-{ts}/skills.json
```

- `{name, description}` 一覧を JSON 化。引数省略時はカレントリポジトリの `skills/*/SKILL.md`。`--user-scope` / `--dir PATH` で汎用適用。
- **スキル名は plugin prefix を除いた bare name に正規化**し、以後 cases の正解ラベル・判定選択肢・集計で同一 namespace を使う。
- **bare name 重複は fail-fast**（v1 は重複 namespace 非対応）。
- **v1 スコープ外**: プラグインキャッシュのハッシュ付きネスト構造（`~/.claude/plugins/cache/<mp>/<plugin>/<hash>/skills/`）。必要になったら glob を追加する。

### Phase 1: 実データ種採取（任意）

```bash
python3 skills/skill-improve/scripts/collect.py --capture-prompts --days N \
  --output .claude/tmp/trigger-eval-{ts}/prompts.jsonl
```

- 発火実績と発火漏れ候補（`correction_after_skill` シグナル + マスク済み `user_text_masked`）を採取。出力は `.claude/tmp/trigger-eval-{ts}/` のみ。
- collect.py 側が**書き込み前に `git check-ignore --quiet <解決済み実出力パス>` で ignore 済みを検証し、非 0 なら拒否**（fail-closed。root .gitignore の文字列走査は使わない）。
- **マスキングは denylist であり完全ではない**ため、採取済み本文ファイルは「マスク後も機微」として扱う（Phase 6 で削除）。

### Phase 1.5: 静的衝突プレパス

```bash
python3 skills/trigger-eval/scripts/static_collisions.py \
  .claude/tmp/trigger-eval-{ts}/skills.json --top-n 30 \
  --output .claude/tmp/trigger-eval-{ts}/collisions.json
```

上位ペアは (a) hard-negative 生成の「隣接スキル」定義、(b) 改稿優先度、(c) 判定不要の自明な統合候補、に使う。

### Phase 2: テストケース生成・事前固定

**生成者は改稿担当と分離した専用 subagent（model: sonnet）**。[testcase-design.md](references/testcase-design.md) に従う:

- positive 2 / hard-negative 1–2 / none 全体の 25% 以上。単一正解ラベル。
- 1 呼び出し ≤10 スキル、**出力ケース数 == 期待数を検証**。
- **`cases.json`（train）と `cases_holdout.json`（holdout 20%、両側 none 25% 以上の層化分割）に固定**。以後差し替え禁止。holdout は改稿ループに見せない。
- **固定前に匿名化三重ゲート**（masker 再適用 / raw seed 近似一致棄却 / 高エントロピートークン screen）を適用。

### Phase 3: 判定ラウンド

判定エージェント（Agent ツール、**model: sonnet 明示**、新規 subagent）に description 一覧 + ケースバッチを渡し JSON 回答を回収する。[judge-protocol.md](references/judge-protocol.md) に従う:

- **判定は 2 モードで実施する**（`judge-protocol.md` の selection / autonomous）。**デフォルトは selection + autonomous の両方を計測**し、`--selection-only` で従来動作（selection のみ）に戻す。入出力スキーマは共通で、フレーミングだけが異なる。モードごとに `judged-{mode}-iterN.json` を別々に生成する（混合禁止）。
- 入力の配布は **インライン渡し、または `skills.json` + バッチファイルの 2 ファイルのみ Read 許可**のいずれか（`judge-protocol.md`「入力の配布方法」）。
- バッチ ≤20 ケース、並行 dispatch（最大 4）。ケース順シャッフル。
- 回収時に**「判定数 == ケース数」を検証**。バッチ不正は 1 回だけ再判定 → なお不正なら `INVALID` 実体化。
- stability のため同一ケースを独立に 2 判定（イテレーション 2 回目以降は固定サンプル 20–30 ケースに縮約、`--full-stability` で全数）。
- 判定プロンプトで「ツールは一切使うな・与えられた入力のみで判定せよ」を明示（soft guarantee）。ファイル渡し時は許可した 2 ファイル以外を読まないことも明示。

### Phase 4: 集計

```bash
# モードごとに同じスクリプトを別々に通す（aggregate_metrics.py は無改修）
python3 skills/trigger-eval/scripts/aggregate_metrics.py \
  .claude/tmp/trigger-eval-{ts}/judged-selection-iterN.json \
  --output .claude/tmp/trigger-eval-{ts}/metrics-selection-iterN.json
# --selection-only でない限り autonomous も同様に集計
python3 skills/trigger-eval/scripts/aggregate_metrics.py \
  .claude/tmp/trigger-eval-{ts}/judged-autonomous-iterN.json \
  --output .claude/tmp/trigger-eval-{ts}/metrics-autonomous-iterN.json
```

`metrics-spec.md` の式で recall / precision / specificity / stability / confusion matrix / invalid_rate を算出。**2 モードの結果は混合せず**、収束・悪化ガードは selection を正・autonomous は参考系列（`metrics-spec.md`「モード軸」）。

### Phase 5: 改稿

- ワースト（confusion 上位ペア or recall 最低スキル）に絞って description を改稿（**1 イテレーション 1 テーマ**）。
- `skill-authoring.md` の frontmatter 契約（トリガー語必須・1024 字上限・ワークフロー要約禁止）に準拠し、**`validate_repo.py` 合格を改稿の完了条件**にする。
- **改稿時は SKILL.md 本文との整合を目視確認**（発火率のために本文の能力を超える約束を書かない）。
- **改稿は 1 スキル = 1 git 単位**。再評価で悪化・validate 不合格なら該当 description を改稿前に revert（ロールバックパス）。

### Phase 6: 再評価 → 収束判定

Phase 3–5 を反復。停止条件の判定は **selection モードの系列を正とする**（autonomous は参考系列・キャリブレーション信号であり、収束・悪化判定に混ぜない。metrics-spec.md のモード軸を参照）。停止条件は次のいずれか:

1. **収束**: 連続 2 イテレーションで macro recall / precision の改善が +1pt 未満。
2. **ハードキャップ**: `max_iterations = 5`。
3. **悪化ガード**: いずれかのスキルの recall / precision、もしくは specificity / invalid_rate が前イテレーション比 **5pt 超悪化** → 直前改稿を revert して停止（precision の defined↔undefined 遷移は non-comparison、metrics-spec.md 参照）。

停止後:

- (a) **holdout 判定（必須・採用ゲート）**: holdout の macro recall / precision がループ開始前 baseline 比で**非劣化でなければ、最後に採用した改稿を revert し「holdout FAIL」としてレポートに明記**。
- (b) **Tier 2 実発火検証**（層化固定 6 セッション、駆動側 Bash ループで上限強制、**デフォルト実行**、`--no-e2e` でスキップ可）。Tier1↔Tier2 乖離率を記録。

**Tier 2 の層化配分（固定）**: 改稿対象 positive 2 / 未改稿ワースト positive 1 / none 1 / hard-negative 1 / 全ケースからランダム 1。**採用改稿が無い場合（即収束 / holdout FAIL で全 revert）は改稿対象枠を recall ワースト positive に振り替える**。乖離率レポートには「層化小標本であり全体推定ではない」注記を必ず付す。

### レポート

`.claude/tmp/trigger-eval-{ts}/report.md` に出力:

- メトリクス推移 / confusion 上位（**全行列ダンプではなく非ゼロセル・上位 N ペアのみ**、raw と正規化率 `confusion(A,B)/related_cases(A,B)` を併記）
- **selection / autonomous のモード別併記**（`--selection-only` 時は selection のみ）。selection を主指標、autonomous を参考系列として並べ、両者の乖離を salience 信号として記す。**混合値は出さない**
- 改稿差分 / Tier1↔Tier2 乖離率 / holdout 判定
- **統合 / 棲み分け再設計候補ペア**（静的プレパス上位 + 改稿 2 回で confusion が解消しないペア）
- 実行メタデータ（判定モデル / 日付 / `cases.json` と `cases_holdout.json` の sha256 / stability サンプル台帳）

**保持するのは report.md / cases.json / cases_holdout.json / 各イテレーションのメトリクス JSON**（再現・run 間比較のアンカー）。**raw プロンプト本文を含む採取ファイル（--capture-prompts 出力）は削除**。過去の `trigger-eval-*` ディレクトリは 30 日超で削除を促す。report.md に載せる失敗例は**匿名化検査済みケースのみ**（raw seed 転記禁止）。

## リソース上限の四点セット

無制限な次元を残さない:

1. 判定バッチ ≤20 ケース/呼び出し + 判定数==ケース数検証
2. ケース生成 ≤10 スキル/呼び出し + 件数検証
3. 改稿ループ `max_iterations = 5` ハードキャップ + 悪化ガード
4. JSONL は mtime 事前フィルタ + 行単位ストリーミング、Tier 2 は 6 セッション × (`--max-turns 2` + 180s timeout)

## 合理化防止

| 言い訳 | 現実 |
|--------|------|
| 「description を盛れば直る」 | 1024 字上限・トリガー語規約・本文整合チェックが上限。validate_repo.py 合格が完了条件 |
| 「ケースを後から差し替えたい」 | 事前固定原則違反。holdout ゲートで過適合が検出される |
| 「Tier 2 は高いから常にスキップ」 | デフォルト実行。スキップは `--no-e2e` の明示指定のみ |
| 「収束しないからもう 1 周」 | max_iterations=5 のハードキャップ |
| 「悪化したが平均は改善している」 | per-skill recall/precision + specificity/invalid_rate の 5pt 悪化ガードで revert |
| 「holdout が悪いが train は良いので採用」 | holdout は採用ゲート。FAIL なら revert |
| 「本文を判定に見せれば精度が上がる」 | 実発火時のモデルの視界と乖離し false positive を生む。description-only は仕様 |

## Red Flags（trigger-eval 違反の兆候）

- 判定エージェントに SKILL.md 本文を渡している
- cases を固定後に編集している / holdout を改稿ループに見せている
- 悪化ガード・holdout ゲートを「レポートに書いたから」で revert せず採用している
- `--capture-prompts` 出力を保持成果物に残している
- Tier 2 を理由なく常にスキップしている
- 改稿 description が SKILL.md 本文の能力を超える約束をしている
