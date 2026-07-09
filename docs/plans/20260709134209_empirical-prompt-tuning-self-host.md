# empirical-prompt-tuning をリポジトリ内に自炊し構造的改善を加える

**Cycle ID:** `20260709134209`
**Started:** 2026-07-09 13:42:09
**Status:** ✅ Done
**Issue:** 20260709120621_empirical-prompt-tuning-self-host

---

## 📝 What & Why

`empirical-prompt-tuning`（github.com/mizchi/skills 出典、MIT 相当）はエージェント向けテキスト指示の品質を「白紙の実行者に動かしてもらい、両面評価して反復改善する」メタスキル。現在はユーザーグローバル（`~/.claude/skills/`）に単体で存在し、本リポジトリの計測エコシステム（measurement-identity / skill-regression / trigger-eval）と接続されていない。能動テスト系のペア（本文層 = empirical / 選択層 = trigger-eval）のうち trigger-eval だけがリポジトリ内にあり対称性が崩れている。

**方針: 汎用スキルとして原本を明確に超える。** リポジトリ固有の計測統合は optional adapter 層に分離し、コアは任意のプロンプト（skill / task プロンプト / CLAUDE.md 節 / rules / コード生成プロンプト）に適用できる汎用評価エンジンとする。

### 原本の構造的弱点

原本の最大の弱点は **「規律をすべて散文の自己申告に頼っている」** こと（Fable 分析）:

1. **自己採点問題**: 実行者が要件達成 ○/× を自己採点する。指示が曖昧なほど実行者は甘く解釈するため、測りたい対象（曖昧さ）が採点者のバイアス源になる自己矛盾
2. **散文ベースの収束判定**: 閾値条件（+3pt / ±10% / ±15%）を LLM が目視判断。チューナー自身が「早く収束させたい」動機を持つため恣意的に通せる
3. **チェックリスト固定の強制なし**: 「事前に固定」と書いてあるだけで機械的に守れない
4. **n=1 のノイズ問題**: 各シナリオ 1 run で閾値判定。LLM 実行の分散とプロンプト改善の効果を区別できない
5. **受動的制約を評価できない**: skill も CLAUDE.md 節も同じ「タスク実行シナリオ」で評価。rules / CLAUDE.md 節のような「遵守すべき制約」に対する遵守率の評価手法がない
6. **摩擦の分類が自由記述**: 不明瞭点 / 裁量補完がイテレーション間で比較困難
7. **検証資産が使い捨て**: 収束後に残るのは改善済みプロンプトのみ。シナリオ + チェックリストは消える
8. **安全ブレーキが定性的**: max_iter / max_wallclock がない

### 差別化ストーリー

> 原本 = 手法の記述（規律は散文）
> 本スキル = 3 役分離で統計的に厳密、制約型指示も測れ、回帰資産を残す実装（規律は機械的強制）

## 🎯 Goals

### 必須（受け入れ条件準拠）

1. `skills/empirical-prompt-tuning/` として配置、MIT クレジット（出典 + ライセンス文）を明記
2. `codex-sync` / `trigger-eval` の外部参照をリポジトリ内参照へ更新
3. 汎用的なオリジナリティを最低 1 つ実配線（単なるコピーで終わらせない）
4. `python3 scripts/validate_repo.py` が合格
5. README.md / CLAUDE.md のスキル表に追加

### コア改善（汎用 — 任意のプロンプトに適用可能）

6. **3 役分離**: チューナー / 実行者 / 採点者の分離。実行者は成果物 + 摩擦報告のみ、採点は独立 checker subagent
7. **k-run 統計的採択ゲート**: 同一シナリオを k 並列実行し、改善がノイズ帯を超えたときのみ採択。デフォルト k=1（原本互換）、`--k-run 2` で厳密モード
8. **対象タイプ別 eval strategy**: 能動的ワークフロー（skill）はタスクシナリオ、受動的制約（CLAUDE.md 節 / rules）は遵守プローブ（違反誘惑シナリオで遵守率測定）
9. **摩擦の固定タクソノミ**: 自由記述 → 6 分類（曖昧語 / 前提欠落 / 矛盾指示 / 過剰指定 / 合理化フック / 自己完結性欠陥）+ 分類→修正パターン対応表。同一分類 3 回再発 → 構造書き直し判定
10. **検収 fixture の資産化**: 収束時にシナリオ + [critical] 要件 + instruction fingerprint を可搬 JSON として出力。再実行で回帰検出可能
11. **収束判定の純関数化**: iteration 記録を構造化 JSON に書き出し、収束・発散判定を `convergence.py`（unittest 付き）に委ねる。閾値パラメータ（precision_delta_eps / steps_tolerance_pct / duration_tolerance_pct）を関数シグネチャに明示
12. **チェックリストのハッシュロック**: baseline 確定時に scenarios + checklist の sha256 を記録、毎 iteration verify、改変で halt
13. **安全ブレーキ**: max_iter / max_wallclock / kill file を polling-pattern §6 流用で定義
14. **肥大化ラチェット**: prompt_bytes をメトリクスに追加。閾値超過時は advisory 警告（hard halt ではない — Codex レビュー W4 指摘を反映）
15. **出口述語の優先順位**: halt(safety) > diverged > stalled > bloat(advisory) > converged（Codex レビュー W6 指摘を反映）

### Adapter 層（本リポジトリ固有 — オプション）

16. **measurement-identity 配線**: 対象が repo skill の場合のみ、`measurement_identity.py` の enum 拡張 + tuning 集計関数 `aggregate_tuning_by_surface` を追加して events.jsonl に配線。対象が repo skill 以外の場合はスキップ（instruction fingerprint のみ iteration JSON に記録）
17. **skill-regression fixture 変換**: 収束した可搬 JSON → `fixtures.json` 形式への変換ガイドを `fixture-schema.md` に追記（自動変換は v2）
18. **trigger-eval 姉妹出口ゲート**: 収束後に description が変更された場合、`static_collisions.py` で衝突チェック（警告のみ）

### 将来拡張（v2 スコープ、本 plan では実装しない）

- loop-triage センサー化（挙動面変更時に inbox へ NEEDS_JUDGMENT 投入）
- fixture 自動変換パイプライン（可搬 JSON → fixtures.json の機械変換）
- k-run の strong/weak 混成モード（最弱実行者で成功を採択条件に）
- Codex 版移植

### 既知の限界（Codex レビュー W1 — plan に明記）

チェックリストのハッシュロックは iteration 中のドリフトを防ぐが、**ベースライン作者バイアス**（チューナーが緩いチェックリストを最初から書く）は防げない。これは「garbage-in-frozen」の限界であり、本質的にはチェックリストの品質はチューナーの誠実さに依存する。v2 でチェックリスト品質の自動評価（要件の具体性スコアリング等）を検討するが、v1 では限界として受容する。

## 📐 Design

### ディレクトリ構造

```
skills/empirical-prompt-tuning/
  SKILL.md                      # メインロジック（原本ベース + 構造的改善）
  LICENSE                       # MIT — 出典: github.com/mizchi/skills
  scripts/
    convergence.py              # 収束・発散判定 + ハッシュロック + 肥大化検出の純関数
    test_convergence.py         # unittest
  references/
    checker-protocol.md         # checker subagent の起動契約
    iteration-schema.md         # iteration JSON レコードの schema 定義
    friction-taxonomy.md        # 摩擦の 6 分類 + 修正パターン対応表
    compliance-probe.md         # 受動的制約の遵守プローブ設計指針
```

### Files to Change

```
skills/empirical-prompt-tuning/
  SKILL.md                      - 新規作成（原本ベース + 改善 A〜I）
  LICENSE                       - 新規作成（MIT、出典 github.com/mizchi/skills）
  scripts/convergence.py        - 新規作成（純関数: is_converged / is_diverged /
                                  verify_checklist_integrity / detect_bloat /
                                  compute_instruction_fingerprint /
                                  classify_friction / resolve_exit_verdict）
  scripts/test_convergence.py   - 新規作成（unittest）
  references/checker-protocol.md   - 新規作成（checker subagent 契約）
  references/iteration-schema.md   - 新規作成（JSON レコード schema）
  references/friction-taxonomy.md  - 新規作成（6 分類 + 修正パターン表）
  references/compliance-probe.md   - 新規作成（遵守プローブ設計指針）

skills/trigger-eval/SKILL.md        - 外部参照 → リポジトリ内参照へ更新
skills/codex-sync/SKILL.md          - 外部参照 → リポジトリ内参照へ更新
skills/codex-sync/references/porting-rules.md - 同上
skills/skill-regression/SKILL.md    - empirical 参照パスを更新
skills/skill-regression/references/fixture-schema.md
  - empirical 参照パスを更新
  - 可搬 JSON → fixtures.json 変換ガイドを追記

skills/shared/references/measurement-identity.md
  - §4 写像表に system="empirical" / event="tuning" を追加
  - 「対象が repo skill の場合のみ」のスコープ制約を明記
skills/shared/scripts/measurement_identity.py
  - SYSTEMS / EVENTS enum に "empirical" / "tuning" を追加
  - aggregate_tuning_by_surface() 集計関数を追加（tuning イベントの消費者）

CLAUDE.md                 - 主要スキル表に empirical-prompt-tuning を追加
README.md                 - スキル表・ファイル構成に追加
```

### SKILL.md の設計（原本からの主な変更点）

#### A. 3 役分離（原本 §3-4 の構造変更）

原本: 実行者が成果物 + 要件達成 ○/× を同時に返す（2 役: チューナー / 実行者）
改善: 3 役に分離

```
チューナー  — シナリオ + チェックリストを設計、プロンプトを修正
実行者      — 対象プロンプトに従いシナリオを実行、成果物 + 摩擦報告を返す
             （要件チェックリストは渡さない）
checker     — 成果物 + チェックリストのみ受け取り、各要件を ○/×/部分的 で採点
             （対象プロンプトは見せない — プロンプトへの甘い解釈を排除）
```

2 チャネル（checker の採点 × 実行者の摩擦報告）の融合ルール:
- **精度（定量）**: checker の採点結果から算出。改善判定のソース
- **修正方針（定性）**: 実行者の摩擦報告から抽出。次 iteration の修正ターゲットのソース
- チューナーは両方を突き合わせて「checker が × を付けた要件」と「実行者が詰まった箇所」の相関を見て修正を決める

checker の起動契約は `references/checker-protocol.md` に分離（Progressive disclosure）。

#### B. 対象タイプ別 eval strategy

対象プロンプトを 2 タイプに分類し、評価手法を切り替える:

| タイプ | 対象例 | 評価手法 |
|--------|--------|----------|
| **能動的ワークフロー** | skill / slash command / task プロンプト | タスクシナリオ実行（原本と同じ） |
| **受動的制約** | CLAUDE.md 節 / rules / コード生成ガイドライン | 遵守プローブ（違反誘惑シナリオ） |

遵守プローブの設計:
- 制約に**違反したくなる自然な誘惑**をシナリオに仕込む
- 実行者が制約を遵守したか否かを checker が採点
- 例: 「テストをスキップするな」という rule に対し、「時間がないので skip して」というユーザー発話シナリオ
- 詳細は `references/compliance-probe.md` に分離

#### C. k-run 統計的採択ゲート

```
デフォルト: k=1（原本互換、コスト最小）
厳密モード: --k-run 2（各シナリオ 2 並列実行）
```

- k≥2 の場合、各シナリオの precision を k 回測定し中央値を採用
- 改善判定: 前回中央値と今回中央値の差が noise_band（k=2 時は run 間差の半分）を超えたときのみ「改善」と認定
- k=1 時は原本同様の単純比較（noise_band=0）にフォールバック

#### D. 摩擦の固定タクソノミ（原本 §4 の不明瞭点・裁量補完を置換）

自由記述 → 6 分類:

| 分類 | 定義 | 典型的な修正パターン |
|------|------|---------------------|
| `ambiguous_term` | 複数解釈可能な語句 | 定義を追加 or 用語を限定 |
| `missing_premise` | 暗黙の前提知識が必要 | 前提を明示 or 最小完成例を追加 |
| `contradictory` | 指示間の矛盾 | 優先順位を明示 or 片方を削除 |
| `over_specified` | 不必要に厳密で判断余地がない | 制約を緩める or 「推奨」に降格 |
| `rationalization_hook` | 合理化で回避できる指示 | escape hatch を塞ぐ |
| `self_containment_gap` | 外部参照なしでは完結しない | inline 化 or 参照先を明示 |

- 実行者に分類ラベルを付けて報告させる（自由記述は補足として許容）
- 同一分類が 3 iteration 再発 → `is_diverged` の発散判定トリガー
- 詳細は `references/friction-taxonomy.md` に分離

#### E. 検収 fixture の資産化

収束完了時に `.claude/tmp/empirical/{ts}/fixture.json` を出力:

```json
{
  "source_skill": "sweep-fix",
  "instruction_fingerprint": "abc123...",
  "eval_strategy": "task_scenario",
  "scenarios": [
    {
      "id": "A",
      "title": "単一ファイル指摘からの横展開",
      "prompt": "...",
      "requirements": [
        { "text": "...", "critical": true },
        { "text": "...", "critical": false }
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

- 可搬フォーマット: skill-regression の fixtures.json とは独立した汎用形式
- 本リポジトリでは `fixture-schema.md` の変換ガイドに従い fixtures.json に手動移送（v2 で自動化）
- 外部プロジェクトでは fixture.json をそのまま回帰テスト資産として利用可能

#### F. 構造化 iteration レコード

各 iteration の結果を `.claude/tmp/empirical/{ts}/iterations.jsonl` に append:

```json
{
  "iteration": 1,
  "prompt_bytes": 4200,
  "checklist_sha256": "abc123...",
  "instruction_fingerprint": "def456...",
  "eval_strategy": "task_scenario",
  "k_runs": 1,
  "scenarios": [
    {
      "id": "A",
      "success": true,
      "precision": 0.9,
      "steps": 4,
      "duration_ms": 20000,
      "retries": 0,
      "friction": [
        { "category": "missing_premise", "detail": "..." }
      ]
    }
  ],
  "exit_verdict": "continue"
}
```

schema 詳細は `references/iteration-schema.md` に分離。

#### G. 収束判定の純関数化

```python
def is_converged(history: list[dict], *,
                 window: int = 2,
                 precision_delta_eps: float = 0.03,
                 steps_tolerance_pct: float = 0.10,
                 duration_tolerance_pct: float = 0.15) -> bool:
    """連続 window 回で新規摩擦ゼロ + メトリクス飽和"""

def is_diverged(history: list[dict], threshold: int = 3) -> bool:
    """threshold 回以上同一分類の摩擦が減らない"""

def verify_checklist_integrity(current_json: str, locked_sha256: str) -> bool:
    """チェックリストの改変検出"""

def detect_bloat(history: list[dict], max_growth_pct: float = 20.0) -> bool:
    """prompt_bytes の前回比超過（advisory）"""

def compute_instruction_fingerprint(files: list[str]) -> str:
    """対象ファイル群の内容 sha256（汎用版 surface_sha256）"""

def classify_friction(raw_points: list[dict]) -> list[dict]:
    """自由記述 → 6 分類に正規化"""

def resolve_exit_verdict(history: list[dict], *,
                         max_iter: int = 10,
                         elapsed_s: float = 0.0,
                         max_wallclock: float = 3600.0,
                         kill_file_exists: bool = False) -> str:
    """出口述語の優先順位で verdict を返す:
       halt > diverged > bloat(advisory) > converged > continue"""
```

#### H. チェックリストのハッシュロック

baseline 確定時（Iteration 0 完了後）:
1. scenarios + requirements を JSON 正規化して sha256 を記録
2. 毎 iteration 開始時に `verify_checklist_integrity(current, locked_hash)` で verify
3. hash 不一致 → `checklist_tampered` halt
4. 意図的変更は「baseline リセット」として iteration 0 からやり直し（明示的コスト）

#### I. 安全ブレーキ（polling-pattern §6 流用）

- `max_iter`: 10（デフォルト。重要度高は 15 まで引き上げ可）
- `max_wallclock`: 3600s（1 時間）
- Kill file: `.claude/tmp/empirical/{ts}/.STOP`
- いずれかに到達 → halt、最後の iteration レコードに `halt_reason` を記録

### Adapter 層の設計

#### measurement-identity adapter（対象が repo skill の場合のみ）

```
条件: 対象が skills/<name>/ 配下のスキルであること
      → ledger.py fingerprint() で surface_sha256 を算出可能
      
不可の場合: instruction_fingerprint（ファイル内容の sha256）のみ iteration JSON に記録
           events.jsonl への配線はスキップ
```

配線時は `measurement_identity.py` の enum 拡張 + `aggregate_tuning_by_surface()` 追加が必要（Codex レビュー B1 指摘への対応）。

#### skill-regression fixture adapter

fixture-schema.md の「素材別の変換ガイド」に empirical の可搬 JSON からの変換手順を追記。自動変換は v2。

#### trigger-eval 姉妹出口ゲート

収束後に description が変更された場合、static_collisions.py で衝突チェック（警告のみ、修正は trigger-eval を別途実行）。

### 棲み分け整理（CLAUDE.md 記載用）

| スキル | 測る対象 | 手法 | 時間軸 |
|--------|----------|------|--------|
| empirical-prompt-tuning | 本文実行の質 | 3 役分離の白紙実行+独立採点・反復 | forward（能動テスト） |
| trigger-eval | 選択層（description→発火） | 判定 subagent で発火精度実測 | forward（能動テスト） |
| skill-improve | セッション摩擦 | 過去 JSONL から検出 | backward（受動分析） |
| skill-regression | 回帰防止 | fixture 再生（empirical 成果を資産化） | guard（変更時検証） |

### Codex 反映

本 plan は Claude 版のみ。Codex 版移植は将来スコープ（v2）。trigger-eval 同様に初版は Claude 版のみで合格。

## ✅ Verification

- `python3 scripts/validate_repo.py` が合格
- `python3 skills/empirical-prompt-tuning/scripts/test_convergence.py` が全パス
- `skills/trigger-eval/SKILL.md` の empirical 参照がリポジトリ内パスを指している
- `skills/codex-sync/` の empirical 参照がリポジトリ内パスを指している
- `skills/shared/references/measurement-identity.md` §4 に `empirical` system が存在（スコープ制約付き）
- `skills/shared/scripts/measurement_identity.py` に `aggregate_tuning_by_surface` 関数が存在
- `grep -r "~/.claude/skills/empirical" skills/` が 0 件（外部参照の残留なし）
- CLAUDE.md / README.md のスキル表に `empirical-prompt-tuning` が存在

## 📋 Implementation Steps

### Step 1: ライセンス検証と骨格の配置
- 原本の取得（`~/.claude/skills/empirical-prompt-tuning/SKILL.md`）
- 上流リポジトリのライセンス状態を確認（MIT 相当の裏取り）
- `skills/empirical-prompt-tuning/LICENSE` を作成（MIT、出典明記）
- ディレクトリ構造を scaffold

### Step 2: 純関数 `convergence.py` + テスト（TDD）
- `test_convergence.py` を先に書く
- `convergence.py`: is_converged / is_diverged / verify_checklist_integrity / detect_bloat / compute_instruction_fingerprint / classify_friction / resolve_exit_verdict
- テスト全パス確認

### Step 3: references の作成
- `checker-protocol.md`（checker subagent 起動契約）
- `iteration-schema.md`（JSON レコード schema）
- `friction-taxonomy.md`（6 分類 + 修正パターン表）
- `compliance-probe.md`（遵守プローブ設計指針）

### Step 4: SKILL.md の作成
- 原本をベースに構造的改善（A〜I）を反映
- 原本の良い部分（評価軸・red flags・よくある失敗）は維持・拡張
- 対象タイプ判定 → eval strategy 選択のフローを冒頭に配置

### Step 5: 外部参照の更新
- trigger-eval / codex-sync / skill-regression の参照パスをリポジトリ内へ

### Step 6: measurement-identity adapter 配線
- `measurement-identity.md` §4 に system="empirical" を追加（スコープ制約明記）
- `measurement_identity.py`: SYSTEMS/EVENTS enum 拡張 + aggregate_tuning_by_surface() 追加
- テスト追加

### Step 7: fixture-schema.md に変換ガイド追記

### Step 8: ドキュメント更新
- CLAUDE.md 主要スキル表に追加
- README.md のスキル表・ファイル構成に追加
- ledger.py --update 手当て（dep_graph の挙動面変化への対応）

### Step 9: 検証
- `validate_repo.py` 実行
- 外部参照の残留チェック
- テスト全パス確認
- グローバル版の削除 or symlink 化
