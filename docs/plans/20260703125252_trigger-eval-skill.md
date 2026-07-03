# trigger-eval スキル新規作成（スキル発火精度の実測・改善メタスキル）

**Cycle ID:** `20260703125252`
**Started:** 2026-07-03 12:52:52
**Status:** 🟢 Complete

---

## 📝 What & Why

スキル数増加（80種以上）により自然言語指示からの自発的スキル発火が劣化している。30日分のセッション実測で、自然言語指示（スラッシュ明示起動を除く）でのスキル自発発火は 68 プロンプト中 11 件、うち大半が commit。同一指示「commit + bump + push」が 3 回発火・1 回スルーする不安定性も確認した。description の品質を「架空のユーザ指示で判定エージェントが正しくスキルを選べるか」で実測し、recall / precision / confusion matrix を根拠に description を改稿→再評価するメタスキル `trigger-eval` を新規作成する。

**位置づけ**: `empirical-prompt-tuning`（ユーザスコープ）が「本文実行の質」を測るのに対し、`trigger-eval` は「選択層（description → 発火）」を測る姉妹スキル。`validate_repo.py` チェック11（トリガー語の静的存在チェック）とは静的/動的の補完関係。

**先行技術との差分（skill-creator 調査結果）**: 公式 skill-creator の `run_eval.py`（`claude -p` + `--include-partial-messages` で単一スキルの発火有無を検出）・`improve_description.py`・`run_loop.py`（precision/recall 集計 + train/test holdout + 改稿ループ + history-blinding）は存在するが、いずれも**単一スキルの発火有無**を測る設計で、80種の競合下で「どのスキルに取られたか」（confusion 帰属）は記録しない。本スキルの独自価値は (a) 80-way confusion matrix と (b) stability 計測の 2 点に限定し、precision/recall/holdout/収束ループの設計は `run_loop.py` の実証済みパターンを踏襲する（run_loop.py はプラグインキャッシュ配下にのみ存在し package-relative import 前提のため import 再利用は不可。コードは Python 3 標準ライブラリのみで自己完結の別実装だが、設計判断は流用）。Tier 2 の stream 検出は `run_eval.py` の方式（`content_block_start` → tool_use 検出、`CLAUDECODE` env 除去、**permission-mode は付けず検出即終了のみで安全を担保**）を踏襲し、run_eval が boolean 検出なのに対し **Skill tool_use の input からスキル名を抽出して Phase 0 と同じ bare name に正規化する拡張**を加える（confusion 帰属のため）。

## 🎯 Goals

- スキルセットの description 一覧に対する発火精度（recall / precision / stability）を機械的に計測できる
- confusion matrix で「衝突しているスキルペア」を特定し、description 改稿では救えない統合・棲み分け候補をレポートできる
- 改稿→再評価ループを収束判定つきで回し、改善をエビデンス（メトリクス差分）で証明できる
- 実セッションデータから発火漏れ実例を採取し、テストケースの種にできる（データ駆動、プロンプト本文はコミットしない）
- 汎用設計: 本リポジトリ以外のフラットなスキルディレクトリ（`~/.claude/skills`、`--dir PATH`）にも適用できる。**v1 スコープ外**: プラグインキャッシュのハッシュ付きネスト構造（`~/.claude/plugins/cache/<mp>/<plugin>/<hash>/skills/`）は v1 では対象外と SKILL.md に明記（必要になったら glob を追加）

## 📐 Design

### 全体アーキテクチャ: 静的プレパス + 2層評価

| 層 | 方式 | 用途 | コスト |
|------|------|------|--------|
| **Phase 1.5: 静的衝突プレパス** | description のトリガー語・語彙の Jaccard 類似度で全ペアの衝突候補を決定的に算出（LLM 不使用、純関数） | 衝突候補ペアのランキング → hard-negative 生成の隣接定義 + 改稿優先度付け。自明な統合候補はこの時点でレポート可能 | ほぼゼロ |
| **Tier 1: 選択シミュレーション** | バイアス排除 subagent に「description 一覧 + 架空指示バッチ」だけを渡し、使うスキル（or none）を JSON で選ばせる。SKILL.md 本文は見せない（実発火時のモデルの視界を再現） | 全スキル横断のスクリーニング・confusion matrix・改稿ループの計測 | 低（sonnet、**1 呼び出し最大 20 ケース**にチャンク分割、バッチは並行 dispatch） |
| **Tier 2: E2E 実発火検証** | `claude -p` に架空指示を素で渡し、stream-json から Skill ツール呼び出しを検出（run_eval.py 方式: `--output-format stream-json --include-partial-messages`、**`CLAUDECODE` env を除去してネスト起動**、最初の Skill tool_use 検出で即プロセス終了 = 検出専用でワークフローは実行させない。**permission-mode は指定しない**（plan mode の system prompt が発火分布を変えキャリブレーションを汚染するため）。**副作用の封じ込めは「使い捨て git worktree」で行う**: Tier 2 の 6 セッションは専用の一時 worktree（実行後に破棄）を cwd にして起動する。スキルが発火せずモデルが指示を直接実行するパス（Bash/Write 等。ユーザの settings.json allow list があると headless でも auto-approve され得る）でも、変更は破棄対象の worktree に閉じる。ツールセットは変えないため発火分布への追加バイアスなし。**1 セッションあたり `--max-turns 2` + timeout 180 秒**） | Tier 1 シミュレーションの実環境キャリブレーション。**デフォルト実行**（`--no-e2e` で明示スキップ可）。Tier1↔Tier2 の乖離率自体をレポートメトリクスにする | 高（1 ケース = 1 セッション。**合計 6 セッション上限を駆動側の Bash ループで強制**、agent の裁量に委ねない） |

**Tier 1 の妥当性限界（明記事項）**: Tier 1 の判定エージェントは「選ぶこと」を指示された選択器であり、自律発火（何も発火せず直接回答する）とは分布が異なる。また判定モデル（sonnet）は実運用のセッションモデルと異なる。したがって Tier 1 の recall/precision は **sonnet 選択器相対の指標**であり、Tier 2 実発火との乖離率がキャリブレーション信号になる。この限界と「判定モデル・Tier 2 の実行条件は knob である」ことを `references/judge-protocol.md` に明記する。判定エージェントのツール禁止（後述）は prompt-level の **soft guarantee** であることも同所に明記する。

**Tier 2 のサンプル配分（層化固定）**: 6 セッションの内訳は固定配分「改稿対象スキルの positive 2 / 未改稿ワーストスキルの positive 1 / none 1 / hard-negative 1 / 全ケースからランダム 1」。**採用された改稿が存在しない場合（即収束 / holdout FAIL で全 revert）は改稿対象枠を recall ワーストスキルの positive に振り替える**。乖離率レポートには「層化小標本であり全体推定ではない」注記を必ず付す。

### Files to Change

```
skills/trigger-eval/
  SKILL.md                              # メインワークフロー（Phase 0-6）
  references/
    judge-protocol.md                   # 判定エージェント契約（入出力 JSON スキーマ / バッチ≤20 とチャンク分割 / 「判定数==ケース数」検証 / バッチ不正の正規化（INVALID の生成はここが所掌）/ バイアス対策は codex-integration.md を参照 / モデル指定と妥当性限界 / Tier 2 のスキル名抽出・正規化）
    testcase-design.md                  # テストケース設計指針（positive / hard-negative / none、件数比率、生成チャンクと件数検証、生成者分離、事前固定原則 + holdout の層化分割、実データ種の使い方）
    metrics-spec.md                     # メトリクス厳密定義（ラベル空間 / ケース JSON スキーマ / per-skill TP・FP・FN / macro・micro / none の specificity 扱い / INVALID の集計（カウント方法はここが所掌）/ confusion matrix の軸とペアランキング式 / 収束・悪化ガード / ゼロ除算規約）
  scripts/
    collect_descriptions.py             # スキルセットから frontmatter description を収集（skills/ ディレクトリ or ~/.claude/skills を引数指定、SKILL.md のみ対象・symlink 非追従、bare name 重複は fail-fast）
    static_collisions.py                # description ペアの語彙 Jaccard 類似度で衝突候補ランキング（純関数、LLM 不使用）
    aggregate_metrics.py                # 判定結果 JSON → recall / precision / stability / confusion matrix 集計（metrics-spec.md の式を実装する純関数）
    test_collect_descriptions.py        # 単体テスト
    test_static_collisions.py           # 単体テスト
    test_aggregate_metrics.py           # 単体テスト
skills/skill-improve/scripts/collect.py # 拡張: (1) --capture-prompts opt-in（マスク済み user_text を出力。このモードのときのみ --output を「git check-ignore で ignore 確認済みの cwd/.claude/tmp 配下」に機械的に制限。既存の body-free 出力の --output 挙動は無変更 = 後方互換維持）(2) SECRET_PATTERNS 強化（email / ホームパス / ghp_・github_pat_・xoxb-・sk-・sk-ant-・AIza 等の既知プレフィックストークンは引用符の有無を問わず検出。プレフィックスなしの汎用「引用符なし秘匿値」は誤爆過多のため対象外と明記）(3) マスク形式を [REDACTED:kind] の完全マスクに全面変更（first4+last4 の部分開示廃止。friction-schema の masked は opaque string なので契約は維持、dedup キーへの影響は test_collect.py で検証）(4) docstring に「--capture-prompts は trigger-eval が第二の消費者」と明記
skills/skill-improve/scripts/test_collect.py  # 新規: 秘匿クラスごとのマスキング検証 / capture-prompts 出力スキーマ / --output の制限（capture 時のみ）/ 空 JSONL・破損 JSONL 行の耐性 / mtime 事前フィルタ / 既存 body-free 出力のリグレッション
skills/skill-improve/SKILL.md           # collect.py の --capture-prompts（trigger-eval 用）と新 secret type の一行追記
skills/skill-improve/references/friction-schema.md  # secret type enum 追加 + masked 形式の注記
.github/workflows/validate.yml          # discover ステップを2つ追加（-s/-t を各ディレクトリに明示。既存の -s scripts ステップとは分離）
CLAUDE.md                               # 主要スキル表に trigger-eval を追記 + 「コマンドなしスキル」注記行（generate-review-rules、sweep-fix、refactor の並び）に trigger-eval を追加
README.md                               # スキル表・ファイル構成に追記
.claude-plugin/plugin.json              # v1.29.0
.claude-plugin/marketplace.json         # v1.29.0
CHANGELOG.md                            # v1.29.0 エントリ
```

**scan_misfires.py は作らない（重要な設計判断）**: セッション JSONL の走査（行単位ストリーミング）・秘匿マスキング・skill 名抽出（plugin prefix 除去）・パス検証（`resolve_and_validate_path`）・`--days` フィルタは `skills/skill-improve/scripts/collect.py` に全て実装済み。二重実装は秘匿マスキングパスのドリフト（片方だけパターン修正される）という保守性・セキュリティ問題を生むため、collect.py に **opt-in の `--capture-prompts`** を追加してシェルアウトで再利用する。`--days N` は JSONL 全読みの前に **ファイル mtime での事前フィルタ**を行い、行単位パースで全文をメモリに載せない（test_collect.py で担保）。trigger-eval 側に新設する純関数は「collect.py にない機能」（description 収集 / 静的衝突 / メトリクス集計）のみ。

**--capture-prompts の出力スキーマ（契約）**: JSONL 形式、1 行 = `{"ts": ISO8601, "project": str, "user_text_masked": str, "fired_skill": str|null, "signals": [str]}`。test_collect.py と Phase 2 の種消費側はこのスキーマを共通契約とする。**--output の検証は新設バリデータ**（出力ファイル自体は未存在なので **親ディレクトリを `resolve(strict=True)` で解決**し、`parent_resolved / name` の包含判定を **`Path.is_relative_to(base)` で行う**。生文字列 startswith は `.claude/tmp2` 等の sibling escape を許すため禁止。`.tmp` sibling write も同一検証。既存の `resolve_and_validate_path` は projects ルート用かつ既存パスの strict resolve 前提なので流用しない）。

**CI discovery の具体機構**: 現行 CI は `python3 -m unittest discover -s scripts -p 'test_*.py'` の単一ステップで、`discover -s` は start dir を1つしか取れない（かつ `trigger-eval` はハイフンを含み Python パッケージ名にできないため `-s .` の一括探索は不可）。次の **2 ステップを追加**する:

```yaml
- name: Unit tests (trigger-eval scripts)
  run: python3 -m unittest discover -s skills/trigger-eval/scripts -t skills/trigger-eval/scripts -p 'test_*.py' -v
- name: Unit tests (skill-improve scripts)
  run: python3 -m unittest discover -s skills/skill-improve/scripts -t skills/skill-improve/scripts -p 'test_*.py' -v
```

command は作らない（skills-first 方針。single-workflow のため名前付き入口も不要。SKILL.md に最小実行レシピ「`trigger-eval` / `trigger-eval --dir PATH` / `--no-e2e`」を明記して起動導線を担保）。Codex 版は初版では作らない（判定 subagent の並行 dispatch が Claude 依存。必要になったら codex-sync で移植判断）。

### SKILL.md ワークフロー（Phase 構成）

- **Phase 0: 対象収集** — `collect_descriptions.py` で対象スキルセットの `{name, description}` 一覧を JSON 化。引数省略時はカレントリポジトリの `skills/*/SKILL.md`。`--user-scope` / `--dir PATH` で汎用適用。**スキル名は plugin prefix を除いた bare name に正規化**し、以後 cases.json の正解ラベル・判定エージェントの選択肢・集計の全てで同一 namespace を使う。**bare name の重複を検出したら fail-fast**（v1 は重複 namespace 非対応と明記）
- **Phase 1: 実データ種採取（任意）** — `collect.py --capture-prompts --days N` をシェルアウトで実行し、発火実績と発火漏れ候補（correction_after_skill 等の既存シグナル + マスク済み user_text）を採取。出力は `.claude/tmp/trigger-eval-{ts}/` のみ。**書き込み前に `git check-ignore --quiet <解決済み実出力パス>` で ignore 済みであることを検証し、非 0（未 ignore / git なし / 判定不能）なら prompt 採取を拒否**（fail-safe。root .gitignore の文字列走査はアンカリング・`!` 否定・サブディレクトリ実行で偽陰性になるため使わない）。**マスキングは denylist であり完全ではないため、採取済み本文ファイルは「マスク後も機微」として扱う**（削除対象、後述）
- **Phase 1.5: 静的衝突プレパス** — `static_collisions.py` で description 全ペアの語彙 Jaccard 類似度を算出し衝突候補ペアをランキング。上位ペアは (a) hard-negative 生成の「隣接スキル」定義、(b) 改稿優先度、(c) 判定不要の自明な統合候補、に使う
- **Phase 2: テストケース生成・事前固定** — **生成者は改稿担当と分離した専用 subagent（model: sonnet）**。**1 呼び出し 10 スキル分までのチャンクに分割し、出力ケース数 == 期待数を検証**（判定バッチと対称の上限設計）。対象スキルごとに positive 2 / hard-negative 1-2（Phase 1.5 の上位衝突ペアのスキルを正解に持つ紛らわしい指示）を生成し、**none ケースは全体の 25% 以上**。曖昧な指示は生成段階で排除し、全ケースは単一の正解ラベル（skill 名 or `none`）を持つ（多義・ambiguous ケースの扱いは v1 スコープ外と testcase-design.md に明記）。**train 用 `cases.json` と holdout 用 `cases_holdout.json`（全体の 20%、none 比率 25% 以上を両側で維持する層化分割）の 2 ファイルに固定**（以後の差し替え禁止。holdout は改稿ループに見せない）。**固定前に (a) 全ケース文字列へ masker を再適用し、(b) 実データ raw seed との近似一致（正規化編集距離、閾値は testcase-design.md に固定値で明記）を検査して近すぎるケースは棄却し、(c) 20 文字以上の高エントロピートークン（プレフィックスなし秘匿値が言い換えを生き残るケース）を含むケースは redact または棄却**（LLM 言い換えの匿名化を機械検証する三重ゲート。永続化されるのは cases ファイルのみなのでここで止める）。実データ種があれば言い換えて匿名化した上で優先採用
- **Phase 3: 判定ラウンド** — 判定エージェント（Agent ツール、**model: sonnet 明示**、新規 subagent）に description 一覧 + ケースバッチを渡し JSON 回答を回収。**バッチは 1 呼び出し最大 20 ケースにチャンク分割し、複数バッチは並行 dispatch（最大 4 並行）**。回収時に**「判定数 == ケース数」を検証**。**バッチ応答全体がパース不能な場合はバッチ内全 case_id を 1 回だけ再判定し、それでも不正なら全 case_id を predicted=INVALID として実体化**（judge-protocol.md の所掌）。ケース順はシャッフル（位置バイアス対策）。stability 計測のため同一ケースを独立に 2 判定（**イテレーション 2 回目以降はデフォルトで固定サンプル 20-30 ケースに縮約**。サンプルは 1 回だけ決定的に選んで記録し全イテレーションで同一、`--full-stability` で全数に戻せる）。**判定プロンプトで「ツールは一切使うな・ファイルを読むな・与えられた一覧のみで判定せよ」を明示**（description-only の視界の soft guarantee）
- **Phase 4: 集計** — `aggregate_metrics.py` が `metrics-spec.md` の式で recall / precision / specificity / stability / confusion matrix / invalid_rate を算出
- **Phase 5: 改稿** — ワースト（confusion 上位ペア or recall 最低スキル）に絞って description を改稿（1 イテレーション 1 テーマ）。skill-authoring.md の frontmatter 契約（トリガー語必須・1024 字上限・ワークフロー要約禁止）に準拠し、`validate_repo.py` 合格を改稿の完了条件にする。**改稿時は SKILL.md 本文との整合を目視確認**（発火率のために本文の能力を超える約束を書かない）。**改稿は 1 スキル = 1 git 単位で行い、再評価で悪化した場合・validate が通せない場合は該当 description を改稿前に revert する**（ロールバックパス）
- **Phase 6: 再評価 → 収束判定** — Phase 3-5 を反復。停止条件は次のいずれか: (1) 収束「連続 2 イテレーションで macro recall / precision の改善が +1pt 未満」、(2) **ハードキャップ `max_iterations = 5`**、(3) **悪化ガード「いずれかのスキルの recall または precision、もしくは specificity / invalid_rate が前イテレーション比 5pt 超悪化」→ 直前改稿を revert して停止**（recall だけ守って precision・none 誤発火を犠牲にする改稿を機械的に拒否）。停止後、(a) **holdout 判定（必須・採用ゲート）: holdout の macro recall / precision がループ開始前 baseline 比で非劣化でなければ、最後に採用した改稿を revert し「holdout FAIL」としてレポートに明記**（過適合検出を報告で済ませない）、(b) Tier 2 実発火検証（層化固定 6 セッション、駆動側 Bash ループで上限強制、デフォルト実行、`--no-e2e` でスキップ可）を行い、Tier1↔Tier2 乖離率を記録
- **レポート** — `.claude/tmp/trigger-eval-{ts}/report.md` にメトリクス推移・confusion 上位（**全行列のダンプではなく非ゼロセル / 上位 N ペアのみ**。raw count と正規化率 `confusion(A,B)/related_cases(A,B)` を併記）・改稿差分・Tier1↔Tier2 乖離率・holdout 判定・**統合/棲み分け再設計候補ペア**（静的プレパス上位 + 改稿 2 回で confusion が解消しないペア）・実行メタデータ（判定モデル / 日付 / cases.json と cases_holdout.json の sha256 / stability サンプル台帳）を出力。**保持するのは report.md / cases.json / cases_holdout.json / 各イテレーションのメトリクス JSON**（再現・run 間比較のアンカー）。**raw プロンプト本文を含む採取ファイル（--capture-prompts 出力）は削除**。過去の `trigger-eval-*` ディレクトリは 30 日超で削除を促す（後始末）。report.md に載せる失敗例は匿名化検査済みケースのみ（raw seed の転記禁止）

### メトリクス厳密定義（metrics-spec.md の要点）

`aggregate_metrics.py` とその unittest はこの式を実装する（フィクスチャの期待値はこの式から手計算）:

- **ケース JSON スキーマ**: `{case_id, gold, judgments: [j1, j2?]}`。**メトリクス（TP/FN/FP・confusion・specificity・invalid_rate）は j1 のみを正とし、(j1, j2) のペアは stability 専用**。INVALID 正規化は判定単位で適用
- **ラベル空間**: 正規化済み bare skill name の集合 + `none` + `INVALID`（集計専用バケット）
- **判定の正規化**: 判定が (a) パース不能、(b) 一覧外のスキル名、(c) 複数スキル、のいずれかの場合は 1 回だけ再判定し、それでも不正なら `INVALID`（生成規則は judge-protocol.md 所掌、本書はカウント方法のみ所掌）
- **per-skill 集計**: スキル S について TP = (正解 S ∧ j1=S)、FN = (正解 S ∧ j1≠S)（none・他スキル・INVALID を含む）、FP = (正解 ≠S ∧ j1=S)（正解 none・正解他スキルの両方を含む）。recall(S) = TP/(TP+FN)、precision(S) = TP/(TP+FP)。**TP+FP=0 のとき precision(S) は undefined とし macro precision の平均から除外**（fixture に本ケースを含める）
- **全体集計**: ヘッドライン指標は **macro 平均**（recall: 正解ケースを 1 件以上持つスキルで平均 / precision: defined なスキルで平均）。参考として micro も併記
- **none の扱い**: none は recall/precision の行を持たず、**specificity = (正解 none ∧ j1=none) / (正解 none 全件)** として独立に報告。正解 none で j1=S の誤りは S の FP に帰属。正解 none で j1=INVALID は specificity の分母に含め分子に含めない
- **invalid_rate** = INVALID 判定数 / 全判定数（INVALID は正解スキルの FN に数え、どのスキルの FP にも数えない）
- **stability** = 同一ケース (j1, j2) の完全一致率。**イテレーション横断の推移系列は常に固定サンプル部分集合上で計算する**（全数 2 判定するイテレーション 1 も、系列用の値はサンプル部分集合に制限して算出 = 母集団が揃い系列比較可能。全数値は参考として別掲）。サンプル数は常に明記
- **confusion matrix**: 行 = 正解、列 = j1（none / INVALID 列を含む）。**ペアランキングは raw = count[正解A,j1=B] + count[正解B,j1=A] の降順を主とし、正規化率 raw / related_cases(A,B) を併記**（ケース投入数の偏りで上位が歪むのを防ぐ）。**related_cases(A,B) = 正解ラベルが A または B のケース総数**（fixture で手計算可能な定義）
- **悪化ガードの defined 遷移規約**: per-skill precision が defined ↔ undefined を跨いで遷移したイテレーションでは、そのスキルの precision 項は 5pt 悪化ガードの比較対象外（non-comparison）。recall・specificity・invalid_rate はケース集合固定のため常に比較可能

### Key Points

- **description-only 判定**: 判定エージェントには description 一覧しか渡さない。本文を見せると実発火時のモデルの視界と乖離し false positive を生む（empirical-prompt-tuning Iteration 0 と同じ思想）。バイアス対策の一般則（自分の結論を渡さない等）は `codex-integration.md` の既存ドクトリンを参照し再記述しない
- **事前固定原則 + holdout ゲート**: テストケースは Phase 2 で固定し、以後のイテレーションで動かさない。holdout 20% は層化分割で隠し、収束後の holdout 判定を**採用ゲート**にする（非劣化でなければ revert。報告のみで済ませない）
- **純関数分離**: 集計・抽出ロジックは scripts/ の純関数に置き unittest で検証（design-principles: Testability / collect.py の設計思想に準拠）。エージェントは JSON の生成と受け渡しのみ。判定は非決定的だが集計は判定結果 JSON に対して決定的なので、フィクスチャは手書きの判定結果 JSON とする
- **プライバシー**: プロンプト本文の採取は collect.py の `--capture-prompts`（opt-in）に一元化。マスキングパターンの実装・強化も collect.py 1 箇所のみ（二重実装によるドリフト排除）。denylist マスキングは完全ではない前提で、本文ファイルは削除対象・cases への転写は masker 再適用 + 近似一致棄却のゲートを通す
- **モデル階層**: 判定 = sonnet（機械的選択タスク）、ケース生成 = sonnet（改稿担当と分離した subagent）、改稿・レポート統合 = セッションモデル。orchestration-patterns.md に従い Agent 呼び出しへ model を明示
- **リソース上限の四点セット**: (1) 判定バッチ ≤ 20 ケース/呼び出し + 判定数==ケース数検証、(2) ケース生成 ≤ 10 スキル/呼び出し + 件数検証、(3) 改稿ループ `max_iterations = 5` ハードキャップ + 悪化ガード、(4) JSONL は mtime 事前フィルタ + 行単位ストリーミング、Tier 2 は 6 セッション × (`--max-turns 2` + 180s timeout)。無制限な次元を残さない
- **合理化防止テーブル**（SKILL.md に記載）: 「description を盛れば直る」→ 1024 字上限・トリガー語規約・本文整合チェックが上限 / 「ケースを後から差し替えたい」→ 事前固定原則違反、holdout ゲートで検出される / 「Tier 2 は高いから常にスキップ」→ デフォルト実行・スキップは `--no-e2e` の明示指定のみ / 「収束しないからもう 1 周」→ max_iterations=5 のハードキャップ / 「悪化したが平均は改善している」→ per-skill recall/precision + specificity/invalid_rate の 5pt 悪化ガードで revert / 「holdout が悪いが train は良いので採用」→ holdout は採用ゲート、FAIL なら revert

## ✅ Tests

- [ ] `collect_descriptions.py`: frontmatter から name/description を正しく抽出する（正常系 / description 欠落 / 非スキル md 除外 / plugin prefix の bare name 正規化 / bare name 重複の fail-fast / symlink 非追従）
- [ ] `static_collisions.py`: 既知の description ペアから Jaccard 類似度と衝突ランキングを正しく算出する（同一 / 無関係 / 部分重複）
- [ ] `aggregate_metrics.py`: metrics-spec.md の式どおりに recall / precision / specificity / stability / invalid_rate / confusion matrix を既知の判定結果フィクスチャから算出する（発火漏れ・誤発火・none 正解・wrong-skill 帰属・INVALID・precision 未定義（TP+FP=0）・j1/j2 分離・不一致ケースを含む）
- [ ] `collect.py` 拡張の `test_collect.py`: 秘匿クラスごと（AWS / JWT / PEM / email / ホームパス / ghp_ 等プレフィックストークンの引用符あり・なし両方）のマスキング検証 / `--capture-prompts` の出力スキーマ（JSONL 契約）/ capture 時の `--output` 制限（`.claude/tmp` 外・未 ignore パスの拒否）/ 既存 body-free 出力のリグレッション（--output 挙動不変）/ 空 JSONL・破損 JSONL 行の耐性 / mtime 事前フィルタ / [REDACTED:kind] 形式と dedup キーの検証
- [ ] CI: `.github/workflows/validate.yml` に追加した 2 つの discover ステップが新テストを拾い合格する（既存 `-s scripts` ステップは無変更で回帰なし）
- [ ] `python3 scripts/validate_repo.py` 全チェック合格（trigger-eval 自身の description がチェック11 を通る = セルフホスティング）
- [ ] 動作確認（実行証跡）: 本リポジトリのスキルセットに対し Phase 0→4 を 1 周回し、report.md にメトリクスと confusion 上位ペアが出力されること

## 🔒 Security

- [ ] セッション JSONL のプロンプト本文を含む出力は `--capture-prompts` 時のみ生成し、`git check-ignore --quiet <解決済み実出力パス>` の合格を書き込み前提条件にする（root .gitignore の文字列走査は使わない。git なし / 判定不能 / 未 ignore は全て拒否 = fail-closed）
- [ ] capture 時の `--output` は新設バリデータで cwd/`.claude/tmp` 配下に機械的に制限（親ディレクトリ `resolve(strict=True)` + `Path.is_relative_to` 包含判定。生文字列 startswith 禁止 = sibling escape 防止。`.tmp` sibling write も同一検証。既存 body-free 出力は無変更 = skill-improve 後方互換）
- [ ] マスキングは collect.py に一元化し強化（email / ホームパス / 既知プレフィックストークンの引用符有無両対応）。kept 成果物は `[REDACTED:kind]` の完全マスク。denylist の不完全性を前提に、本文ファイルは削除・cases 転写は masker 再適用 + raw seed 近似一致棄却 + 高エントロピートークン screen の三重ゲート。秘匿クラスごとに unittest で担保
- [ ] collect_descriptions.py のパス引数は resolve + 存在検証 + SKILL.md のみ対象 + symlink 非追従（パストラバーサル防止）
- [ ] Tier 2 の `claude -p` は検出専用（最初の Skill tool_use で即終了）+ `--max-turns 2` + 180 秒 timeout + `CLAUDECODE` env 除去 + 合計 6 セッション上限（駆動側 Bash ループで強制）+ **使い捨て git worktree 内で実行**（スキル不発火時にモデルが指示を直接実行しても変更が worktree に閉じる。settings.json の allow list による auto-approve を前提にした封じ込め。permission-mode は発火分布バイアス回避のため付けない。任意の追加硬化として worktree では `git remote remove` で push ベクターも遮断）
- [ ] report.md には匿名化検査済みケースのみ掲載（raw seed 転記禁止を SKILL.md に明記）。過去 run の `trigger-eval-*` ディレクトリは 30 日で後始末

## 📊 Progress

| Step | Status |
|------|--------|
| Tests | 🟢 |
| Implementation | 🟢 |
| Commit | 🟢 |

**実装エビデンス（{ts} 実測）:**
- trigger-eval scripts unittest: 50 tests OK（collect_descriptions 15 / static_collisions 13 / aggregate_metrics 22）
- skill-improve collect.py unittest: 30 tests OK（マスキング各クラス / capture スキーマ / --output 制限 / git-ignore gate / mtime / dedup / body-free 回帰）
- validator scripts unittest: 23 tests OK（回帰なし）
- `python3 scripts/validate_repo.py`: ✓ 全チェック合格（trigger-eval description がチェック11 通過 = セルフホスティング）
- E2E スクリプトチェーン（Phase 0→1.5→4）: 本リポジトリ 33 スキルに対し collect_descriptions → static_collisions → aggregate_metrics が正常動作。top collision = team-cycle↔team-plan (0.571)
- レビューエージェント指摘（sk-proj-/sk-svcacct- 未マスク・3-part JWT 署名漏れ・validate の `..` 許容）を修正しテスト追加

**Legend:** ⚪ Pending · 🟡 In Progress · 🟢 Done

---

**Next:** Write tests → Implement → Commit with `claude-skills:commit` 🚀
