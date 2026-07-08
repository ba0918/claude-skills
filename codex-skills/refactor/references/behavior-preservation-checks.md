# Behavior Preservation Checks — 動作保持の文脈検証チェックリスト

refactor Phase 4（VERIFY）で使用する判定基準。横展開検索（Phase 3）が拾った候補
（`origin` / `sweep_candidates` の両方）に対し、
「**同じ変換を、動作を保持したまま、この箇所に安全に適用できるか**」を文脈で検証する。

> sweep-fix の `context-verification.md` は「同じ**バグ**が成立するか」を問う設計。
> 本チェックリストは「同じ**変換**を**動作保持**で適用できるか」を問う。問いが逆向きなので流用しない。
> 3値判定の**定義**は共有契約 severity-and-verdicts.md（SKILL.md からリンク済み）に準拠する。

## 判定の定義（refactor 文脈）

| 判定 | 定義 | 成立条件 |
|------|------|---------|
| **CONFIRMED** | 動作を保持したまま同じ変換を安全に適用できる | 下記チェックリスト全項目で「安全に適用できる」側に倒れ、根拠を 1-2 文で書ける |
| **FALSE_POSITIVE** | 表面上似ているが文脈が違う（適用不可・不要） | いずれかの項目で「適用できない/すべきでない」ことが確認できた。除外理由を必ず記録 |
| **UNCERTAIN** | 適用可否が文脈依存で判断材料が不足 | どちらとも確認できない。修正せずユーザに委ねる |

> フレーム（3値・Iron Law・fail-safe）の定義元は共通契約
> [severity-and-verdicts.md](../../shared/references/severity-and-verdicts.md) の
> 「文脈検証の3値判定」。本ファイルは refactor 固有の検証述語（動作保持）を特殊化する。

## The Iron Law

```
根拠を書けない CONFIRMED は存在しない。書けなければ UNCERTAIN に降格する。
UNCERTAIN → CONFIRMED への昇格は禁止（逆の降格は常に許可）。
```

## チェックリスト

候補箇所ごとに、該当ファイルを **shell（cat 等）で実際に読んで**（excerpt だけで判定しない）以下を確認する:

### 1. 挙動契約の同一性

変換後、入出力・副作用・エラー挙動・実行順序が**完全に同一**に保てるか。

- 戻り値・例外の型と条件が変わらないか
- 副作用（I/O・状態変更・ログ）の**回数と順序**が変わらないか
- 短絡評価・遅延評価の順序が保たれるか
- いずれか一つでも変わるなら **FALSE_POSITIVE**（それは refactor ではなく behavior change）

### 2. 呼び出し文脈の同質性（origin との比較）

sweep_candidate の呼び出し文脈が origin と同質か。

- 同じ変換（例: フラグ引数の分割）が呼び出し元全件に同じ意味で適用できるか
- 片方だけ公開 API・シリアライズ境界・リフレクション対象なら **FALSE_POSITIVE / UNCERTAIN**
- 呼び出し元は候補行の周辺だけでなく、**関数の入口と全呼び出し元まで**遡って確認する

### 3. 意図的な差異の痕跡

その書き方が意図的であることを示す証拠がないか。

- コメントで理由が説明されている（`// 意図的に〜` / `// NOTE:` / パフォーマンス注記）
- 将来分岐予定・後方互換のための冗長さ（migration shim 等）
- 挙動を固定するテストが「その形」を前提にしている
- 該当すれば **FALSE_POSITIVE**（意図的設計）または **UNCERTAIN**（意図は読めるが改善余地も残る）

### 4. 証明手段の有無（動作保持の検証可能性）

変換後に「動作が変わっていない」ことを**証明できる**か。

- 既存テスト・型検査・lint・実行可能な characterization probe のいずれかがこの箇所をカバーするか
- **いずれもカバーしない → UNCERTAIN**（証明手段なしの動作保持主張は verification-gate 違反）
- headless 実行で characterization test を新規生成できない箇所も **UNCERTAIN**

### 5. パフォーマンス感度

この箇所がホットパス・ベンチマーク対象・計測コメント付きでないか。

- 「シンプルな版」が遅くなる可能性があり、計測なしに書き換えられない → **UNCERTAIN**
- **ホットパスかどうか不明な場合も UNCERTAIN に倒す**（fail-safe の完結）

### 6. 慣例との整合

変換がプロジェクトの慣例（周辺コードのスタイル・イディオム）と整合するか。

- 慣例を壊す「簡素化」は churn。周辺との一貫性が優先 → 整合しないなら **FALSE_POSITIVE**

## Fail-safe 原則

- 誤変換（動作が変わる/文脈に合わない変換を適用してしまう）のコストは、保留（真の改善を見送る）のコストより大きい
- 迷ったら直さない。「表面上同じに見えるが文脈が違う」を FALSE_POSITIVE または UNCERTAIN に落とす

## 判定例

**改善（origin）**: `doExport(true)` という boolean フラグ引数を、意図が読める `doExportAsPdf()` / `doExportAsCsv()` の2関数に分割する（C4）

| 候補 | 文脈 | 判定 | 根拠 |
|------|------|------|------|
| `services/order.ts:42`（origin） | 内部呼び出し3件、全て意味が一意、テストあり | CONFIRMED | 呼び出し元全件が同じ意味で分割可能、既存テストが挙動を固定している |
| `services/invoice.ts:88` の `doExport(true)` | 同じユーティリティを内部で呼ぶ。テストあり | CONFIRMED | 呼び出し文脈が origin と同質、挙動契約を保てる |
| `api/public_export.ts:12` の `doExport(flag)` | `flag` は外部 API のクエリパラメータ由来 | UNCERTAIN | 引数が実行時の外部入力で、2関数分割が公開 API シグネチャ変更に波及しうる |
| `legacy/report.ts:30` の `doExport(true)` | 直前に `// TODO: remove after v2 migration` | FALSE_POSITIVE | 削除予定の一時コード。労力を割く対象外（Phase 0 一時コード除外に該当） |

## 記録フォーマット

```json
{
  "improvement_id": "R1",
  "verdicts": [
    { "file": "services/invoice.ts", "line": 88, "role": "sweep_candidate",
      "verdict": "CONFIRMED", "reason": "呼び出し文脈が origin と同質で挙動契約を保てる" },
    { "file": "api/public_export.ts", "line": 12, "role": "sweep_candidate",
      "verdict": "UNCERTAIN", "reason": "引数が外部入力で公開 API シグネチャ変更に波及しうる" }
  ]
}
```

`reason` は必須。空の reason を持つ verdict は不正データとして扱い、その候補を UNCERTAIN で再判定する。
