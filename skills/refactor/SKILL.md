---
name: refactor
description: 実装完了後のコードを動作を完全に維持したままリファクタリングし、類似コードへ文脈検証つきで横展開するスキル。ユーザ指定スコープ（ファイル / ディレクトリ / クラス名 / 「直近Nコミット」）を完全理解したうえで表現だけを改善し、発見したバグは修正せず issue 化案を提示する。「リファクタリング」「リファクタして」「refactor」「きれいにして」「シンプルにして」「可読性を上げて」「類似コードも直して」で起動。バグ修正・不具合対応・脆弱性修正が目的の場合は本スキルではなく sweep-fix を使う（本スキルは動作保持が前提）。
---

# Refactor

指定スコープのコードを完全に理解したうえで、**動作を完全に維持したまま**表現を改善し、
コードベース全体の類似コードへ文脈検証つきで横展開する。
**理解 → 改善候補の抽出 → 横展開検索 → 文脈検証 → 動作保持リファクタ → 報告** のワークフロー。

sweep-fix が「問題（バグ）起点の find-one-fix-all」なのに対し、refactor は
「動作保持の表現改善」起点。発見したバグは**修正せず** issue 化コマンド案を提示してユーザに委ねる。

## Iron Laws

```
1. 動作を完全に維持する — 変えるのは表現だけ。入出力・副作用・エラー挙動・順序は同一
2. 理解していないコードをリファクタするな — Chesterton's Fence
3. バグを見つけても直すな — issue 化コマンド案を提示してユーザに委ねる（diff に混ぜない・自動作成もしない）
4. 既にきれいなら何もするな — no-op は正当な結果
5. 迷ったら直すな — UNCERTAIN はユーザに委ねる。証明手段（テスト/型検査/probe）がない箇所は APPLY しない
```

## 他スキルとの差別化

- **sweep-fix**: 問題（バグ・アンチパターン）起点の find-one-fix-all で、**挙動を変える**前提。refactor は**動作保持**が前提で、改善カタログも検証観点も別物（バグ成立検証 vs 動作保持検証）。correctness / security 起因の候補は refactor では扱わず sweep-fix / issue に送る
- **iterate**: ユーザが修正指示を持ち込む cycle 後の改善ループ。refactor はスコープ指定分析から改善候補の発見自体を行う
- **investigate**: 読み取り専用の分析のみ。refactor は Phase 5 で改善実施まで行う
- **systematic-debugging**: バグの根本原因特定と修正が目的。refactor はバグに手を出さない
- **simplify（Claude Code ビルトイン）**: 直近の変更 diff に対する quality-only の整理。refactor はユーザ指定スコープ（既存コード全般）を対象とし、横展開・3値判定・issue 化提案まで行う
- **codebase-review**: 全体固定スキャンのレポート止まり。refactor はユーザ指定スコープ起点で修正まで行う

## 共有契約への準拠

- [severity-and-verdicts.md](../shared/references/severity-and-verdicts.md): 3値判定（CONFIRMED / FALSE_POSITIVE / UNCERTAIN）の**定義のみ**参照する。severity（BLOCK / WARN / INFO）は refactor では使わない
- [verification-gate.md](../shared/references/verification-gate.md): 完了前検証・証拠要求（Phase 1 の検証手段確保 Gate と Phase 5 のテスト証拠の根拠）
- [orchestration-patterns.md](../shared/references/orchestration-patterns.md): read-only フェーズの Agent 委譲閾値の根拠（パターン7: リサーチ隔離）

> **検証観点は自前で持つ**: sweep-fix の `context-verification.md` はバグ成立検証向けの質問リストで、動作保持検証とは問いが異なる。また兄弟スキルの private reference への横依存は結合を生むため参照しない。refactor 固有の [references/behavior-preservation-checks.md](references/behavior-preservation-checks.md) を使う。3値判定の**定義**は共有契約 severity-and-verdicts.md に準拠する。

## フロー

```
Phase 0: SCOPE      — スコープ解釈と対象確定（安全上限つき）
Phase 1: UNDERSTAND — 対象コードの完全理解（Chesterton's Fence + 検証手段の確保）
Phase 2: IDENTIFY   — 改善候補の洗い出し・分類と Gate 判定
Phase 3: SWEEP      — 類似コードの横展開検索（読み取り専用・範囲限定）
Phase 4: VERIFY     — 文脈検証・3値判定 ★品質の要
Phase 5: APPLY      — 1改善ずつの動作保持リファクタ + テスト（スコープ外は opt-in）
Phase 6: REPORT     — 結果報告 + 発見バグの issue 化コマンド案提示
```

## Phase 0: SCOPE — スコープ解釈と対象確定

1. `$ARGUMENTS` からスコープを解釈する:
   - ファイルパス / ディレクトリ / glob / クラス名・関数名
   - git 期間表現（「直近5コミット」「今週の変更」→ `git log --since=...` / `git diff HEAD~N --name-only` で対象ファイル集合に展開）
2. **引用の徹底**: パス・引数に空白やシェルメタ文字が含まれる場合は、コマンド組み立て時に必ず引用符で囲む（`git diff HEAD~5 --name-only -- "src/my dir"`）
3. **引数なしの場合**: 直近コミットの変更ファイル（`git diff HEAD~1 --name-only`）をデフォルトスコープとして提示し確認する
4. **存在確認**: 展開後の対象パスの存在を `ls` / Glob で確認する。存在しなければ即エラーで中断
5. **安全上限**: 展開後の対象が **50 ファイルを超える**場合は、そのまま進めずスコープの分割案を提示してユーザに確認する（スコープ総量の暴走防止。Phase 5 の Rule of 500 は1改善あたりのサイズ制御で別レイヤ）
6. **Gate: 一時コード判定** — プロトタイプ・使い捨てスクリプト・削除予定コード（`TODO: remove` / `experimental` / `scratch` 等のシグナル + ユーザへの確認）は**改善対象から除外**して報告する（一時コードに労力を割くのは時間の無駄）。一時に見えて仕様化しているコード（migration shim 等）があるため、**削除・統合系の変換は初版の対象外**とし、命名整理・抽出・重複解消など可逆性の高い変換に限定する

## Phase 1: UNDERSTAND — 対象コードの完全理解

**Chesterton's Fence: なぜこう書かれたかを理解するまで壊さない。**

1. 対象コードの責務・入出力・副作用・エラー挙動・エッジケースを読み取る
2. 呼び出し元・呼び出し先を Grep / LSP で確認する（挙動契約の把握）
3. `git log --follow` / `git blame` で経緯を確認する（「なぜこう書かれたか」— パフォーマンス対策・プラットフォーム制約・過去のバグ修正の可能性）
4. **Gate: 理解不足** — 答えられない箇所は改善対象から除外し、除外理由を `unknown_reason` として記録する:
   `no_history` / `dynamic_dispatch` / `public_api` / `generated_or_vendor` / `unclear_tests` / `semantic_dependency`。**理解していないコードを単純化しない**
5. **Gate: 検証手段の確保（動作保持の証明可能性）** — 既存テストの有無と範囲を確認する:
   - テストが存在しない場合は characterization test（現挙動の固定テスト）の追加を提案し、ユーザ合意が得られれば作成・実行してから進む
   - **headless 実行では合意が取れないため characterization test を勝手に生成せず、該当箇所は UNCERTAIN / no-op に落とす**
   - 既存テスト・ビルド・型検査・lint・実行可能な characterization probe の**いずれも用意できない箇所は APPLY 対象にしない**（UNCERTAIN または no-op に落とす）。証明手段なしの「動作完全維持」主張は verification-gate 契約違反
   - Phase 1 で作成した characterization test / probe は以降 **immutable**（Phase 5 の「テストを修正しない」規則の対象に含める）
6. **委譲判定**: スコープが **10 ファイルを超える**場合、UNDERSTAND の読み取り調査は read-only の Explore Agent に委譲する（orchestration-patterns.md パターン7: リサーチ隔離。メインコンテキスト肥大の防止）

## Phase 2: IDENTIFY — 改善候補の洗い出しと分類

1. [references/refactoring-catalog.md](references/refactoring-catalog.md) のパターン表（深いネスト / 長大関数 / ネストした三項演算子 / boolean フラグ引数 / 汎用名 / what コメント / 重複ロジック / デッドコード / 無価値ラッパー等）に照らして候補をリストアップする
2. 各候補を **4値に分類**する:

   | 分類 | 意味 | 扱い |
   |------|------|------|
   | `REFACTOR_CANDIDATE` | 動作保持で表現を改善できる | Phase 3 以降の対象 |
   | `BUG_FOUND` | correctness / security / data loss / behavior mismatch を理由とする | Phase 6 で issue 化案として提示（**改善候補に入れない**） |
   | `OUT_OF_SCOPE` | 一時コード・理解不足・スコープ外 | 除外して報告 |
   | `ALREADY_CLEAN` | 既にシンプルで可読性が高い | 何もしない |

3. **sweep-fix との境界規則**: 候補の改善価値が correctness / security / data loss / behavior mismatch を理由とする場合、それは refactor 候補ではなく `BUG_FOUND`。バグ修正が目的なら sweep-fix を使う
4. 各 `REFACTOR_CANDIDATE` に「**新しいチームメンバーが元より速く理解できるか？**」テストを適用する
5. **Gate: already-clean** — 改善候補ゼロまたは全候補が「効果薄」→ **no-op で終了**する。「既にシンプルで可読性が高い」ことを正当な結果として報告する（無理に適用しない）。この場合、変更が発生しないため検証ゲート（テスト実行）は不要で、簡略版レポートを会話上に出力する
6. **Gate: パフォーマンスクリティカル** — ホットパス・ベンチマーク対象・計測コメントのある箇所は、「シンプルな版」が遅くなる可能性を明記し、計測なしに書き換えない。**ホットパスかどうか不明な場合も UNCERTAIN に倒す**（fail-safe の完結）

## Phase 3: SWEEP — 類似コードの横展開検索

**読み取り専用・範囲限定。一切修正しない。**

1. Phase 2 の各 `REFACTOR_CANDIDATE` をパターン化し、類似事例を検索する。各改善は `improvement_id` を持ち、`origin`（Phase 0 スコープ内の元箇所）と `sweep_candidates`（スコープ外の類似箇所）を区別して記録する
2. **検索範囲の限定**: Phase 0 スコープと**同一言語・関連ディレクトリに限定**する（巨大 monorepo での similarity-* 全体走査は重い。「コードベース全体」を無条件に走査しない）
3. **検出ツールの使い分け**（詳細は [references/similarity-detection.md](references/similarity-detection.md)）。ツールは役割が異なるため、候補の性質と言語で選ぶ（純粋な段階フォールバックではない）:
   - `similarity-ts` / `similarity-rs`（`which` で存在確認）: 重複ブロック・コードクローンの構造的検出。**TS/JS/Rust のみ**
   - `ast-grep`（`which` で存在確認）: 既知の構文パターンの全インスタンス列挙
   - `Grep`（常に利用可能）: 広めの字面検索。上記が使えない場合のフォールバック
4. **言語カバレッジの非対称性**: similarity-* 非対応言語（Python / Go / PHP / Dart 等）では字面検索に落ちるため偽陽性リスクが上がる。非対応言語では横展開を保守的に運用する。使用ツールと `fallback_reason` を記録して REPORT に載せる
5. 検索は広く（偽陰性防止）、修正判断は Phase 4 に委ねる（検索と検証の責務分離）
6. **委譲判定**: スコープが **10 ファイルを超える**場合、SWEEP は read-only Agent に委譲する（`model: opus` 明示）

## Phase 4: VERIFY — 文脈検証・3値判定

**このスキルの品質を決める Phase。スキップ・簡略化は禁止。**

判定値の定義は共有契約 [severity-and-verdicts.md](../shared/references/severity-and-verdicts.md)（CONFIRMED / FALSE_POSITIVE / UNCERTAIN）に準拠する。
検証観点は refactor 固有の [references/behavior-preservation-checks.md](references/behavior-preservation-checks.md) の質問リストを使う。

1. `origin` / `sweep_candidates` の**両方**を検証に通す。候補ごとに該当ファイルの周辺コンテキストを **Read で実際に読む**（excerpt だけで判定しない）
2. behavior-preservation-checks.md の質問で判定する:
   - 「同じ変換をこの箇所に**動作を保持したまま**安全に適用できるか」
   - 「挙動契約（入出力・副作用・エラー挙動・順序）は同一に保てるか」
   - 「呼び出し文脈は origin と同質か」
   - 「意図的な差異の痕跡（コメント・履歴・将来分岐予定）はないか」
   - 「ホットパスの可能性はないか（不明なら UNCERTAIN）」
3. 3値判定を下す:

   | 判定 | 意味 | 扱い |
   |------|------|------|
   | **CONFIRMED** | 動作を保持したまま同じ変換を安全に適用できる | APPLY 候補 |
   | **FALSE_POSITIVE** | 表面上似ているが文脈が違う（適用不可・不要） | 除外。**除外理由を必ず記録** |
   | **UNCERTAIN** | 判断に必要な文脈が不足、または適用可否が文脈依存 | 修正しない。判断材料付きでレポート |

4. **判定には根拠を必ず添える**。根拠を書けない CONFIRMED は UNCERTAIN に降格する
5. **fail-safe: 迷ったら直さない**。「表面上同じに見えるが文脈が違う」（例: 同形の重複コードだが片方は将来分岐予定でコメントあり / 片方はホットパス）を FALSE_POSITIVE または UNCERTAIN に落とす。**UNCERTAIN → CONFIRMED への昇格は禁止**（逆の降格は常に許可）
6. **委譲判定**: 候補が **20 件を超える**場合は VERIFY を Agent に委譲する（`model: opus` 明示。判定基準は behavior-preservation-checks.md を Agent プロンプトに注入する）

## Phase 5: APPLY — 動作保持リファクタ（スコープ外は opt-in）

1. **適用ポリシー**:
   - `origin`（Phase 0 スコープ内）の CONFIRMED は APPLY する
   - `sweep_candidates`（スコープ外の横展開候補）は CONFIRMED でも**デフォルトは report-only** とし、件数・対象・変換内容を提示してユーザの **opt-in 確認**を得てから適用する
   - **headless 実行（cycle 経由等、確認が取れない文脈）では report-only 固定**。「このファイルをきれいにして」が「似た20箇所も書き換えて」を意味するとは限らない
2. **1改善（improvement_id）ずつ**適用 → テスト実行 → パスしたら次へ（失敗したら revert して再考）。複数候補を並列に直さない。**1回の実行で APPLY する改善は最大 10 件**とし、残りはレポートに回す（この 10 は適用バッチ上限。Phase 1/3 の「10 ファイル」委譲閾値とは別軸）
3. **動作維持の検証**: 既存テスト（および Phase 1 で作った characterization test / probe）を**修正せず**全パスさせる。テストの修正が必要になった時点で behavior change の疑い → **revert**
4. **テスト実行の最適化（任意）**: 各変更では対象モジュールの targeted test、全改善の適用完了後に全スイートを1回、という構成を許容する（大規模スイートでの N×全実行を回避）
5. **検証ゲート**（[verification-gate.md](../shared/references/verification-gate.md) 準拠）: テスト実行コマンドと結果を証拠として記録する。証拠なしの完了主張禁止
6. **Rule of 500**: 1改善の diff が **500 行（`git diff --stat` で実測）を超える**場合、手作業 Edit を禁止し機械的変換を使う:
   - 第一選択は **ast-grep rewrite**（構文単位で安全）
   - `sed` は字面置換で文字列リテラル・コメント内の同形テキストも書き換えるため**最終手段**とし、使う場合は **(a) 変換前に revert 点（コミットまたは stash）を確保 (b) 変換後に diff 全件確認 (c) テスト全パス** の3条件を必須とする

## Phase 6: REPORT — 結果報告 + issue 化コマンド案

以下の構造で会話上にレポートを出力する:

```
══════════════════════════════════════
REFACTOR REPORT
══════════════════════════════════════

## 1. 実施した改善（スコープ: {scope}）

| improvement_id | 対象 | before/after 要旨 | テスト結果 |
|----------------|------|-------------------|-----------|

## 2. 横展開の結果

| improvement_id | 検出ツール | origin | sweep 候補数 | CONFIRMED | FALSE_POSITIVE | UNCERTAIN | fallback_reason |
|----------------|-----------|--------|-------------|-----------|----------------|-----------|-----------------|

## 3. no-op / スキップ / 除外

{OUT_OF_SCOPE / ALREADY_CLEAN の一覧と unknown_reason }

## 4. 判断保留（UNCERTAIN）

{file:line と、ユーザが判断するために必要な材料}

## 5. report-only に留めた sweep_candidates（スコープ外・要 opt-in）

{file:line と変換内容。ユーザ確認待ち}

## 6. 発見したバグ（BUG_FOUND）— 修正していません

各バグにつき issue 化コマンド案を提示する（実行はユーザ判断）:

  /claude-skills:issue-create "{タイトル案}"
  本文案: {症状 / 該当箇所 file:line / 再現条件の下書き}

## 7. 検証エビデンス

- テスト: {実行コマンドと結果。未実行なら理由を明記}
- diff: {git diff --stat の要約}
```

**重要**: refactor 実行中に `docs/issues` 等のリポジトリ文書を作成・編集しない。issue 化はコマンド案の提示のみ（自動 issue 作成はしない）。リファクタ diff にも issue ファイルにも手を出さない。

## 合理化防止

| 言い訳 | 現実 |
|--------|------|
| 「行数が減ったからシンプルになった」 | 簡潔さの基準は理解速度であって行数ではない。1行のネスト三項は5行の if/else より複雑 |
| 「ついでにこのバグも直しておこう」 | behavior change。リファクタ diff が汚染されレビュー不能になる。issue 化案の提示が正しい経路 |
| 「テストをちょっと直せば通る」 | テスト修正が必要 = 挙動が変わった証拠。revert する |
| 「テストがないけど見れば分かる変更だ」 | 証明手段なしの動作保持主張は verification-gate 違反。probe を作るか no-op に落とす |
| 「このヘルパーは無駄だからインライン化」 | 概念に名前を与える抽象・テスタビリティのための抽象は複雑性ではない |
| 「似てるから同じ修正でいいでしょ」 | 字面の類似は文脈の同一を意味しない。Phase 4 の検証を通過するまで修正対象ではない |
| 「横展開で見つけたから全部直そう」 | スコープ外の適用はユーザ opt-in。指定範囲外の大量 diff はユーザを驚かせレビュー不能にする |
| 「動いてるコードだし理解は後でいい」 | 理解なきリファクタは劣化。Phase 1 に戻る |
| 「プロジェクトの慣例よりこの書き方がベター」 | 慣例を壊す「簡素化」は churn。周辺コードとの一貫性が優先 |

## Red Flags — スキルが守られていない兆候

- テストを修正して GREEN にしている
- リファクタ diff にロジック変更（条件の追加・削除、戻り値の変化）が混ざっている
- Phase 1 の理解チェックに答えられないままファイルを編集している
- テスト・型検査・probe のいずれもないコードに APPLY している
- UNCERTAIN 判定の箇所を修正している
- スコープ外の `sweep_candidates` をユーザ確認なしに APPLY している
- refactor 実行中に docs/issues 配下のファイルを作成・編集している
- エラーハンドリングを「きれいにするため」に削除している
- no-op 判定を避けるために効果の薄い改善を無理に列挙している
