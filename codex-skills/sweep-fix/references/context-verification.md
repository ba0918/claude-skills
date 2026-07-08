# Context Verification — 文脈検証チェックリスト

sweep-fix Phase 3 で使用する判定基準。横展開検索（Phase 2）が拾った候補箇所に対し、
「同じ問題が本当に成立するか」を文脈で検証する。

## 判定の定義

| 判定 | 定義 | 成立条件 |
|------|------|---------|
| **CONFIRMED** | 同じ問題が同じ理由で成立する | 下記チェックリストの全項目で「問題が成立する」側に倒れ、根拠を 1-2 文で書ける |
| **FALSE_POSITIVE** | 字面は似ているが文脈的に問題ない | チェックリストのいずれかで「成立しない」ことが確認できた。除外理由を必ず記録 |
| **UNCERTAIN** | 判断に必要な文脈が不足 | どちらとも確認できない。修正せずユーザに委ねる |

> フレーム（3値・Iron Law・fail-safe）の定義元は共通契約
> [severity-and-verdicts.md](../../shared/references/severity-and-verdicts.md) の
> 「文脈検証の3値判定」。本ファイルは sweep-fix 固有の検証述語（バグ成立）を特殊化する。

## The Iron Law

```
根拠を書けない CONFIRMED は存在しない。
書けなければ UNCERTAIN に降格する。
```

## チェックリスト

候補箇所ごとに、該当ファイルを **shell（`cat` 等）で実際に読んで**（excerpt だけで判定しない）以下を確認する:

### 1. 前提条件の同一性

元の問題が成立した前提（入力の出所、実行タイミング、並行性の有無）が候補箇所でも同じか。

- 例: 元箇所は「ユーザ入力を未検証で使う」問題でも、候補箇所の入力元が定数や内部生成値なら **FALSE_POSITIVE**

### 2. ガードの有無

候補箇所の上流（呼び出し元・早期 return・型制約）に、問題を無効化するガードが既に存在しないか。

- 例: null 参照の候補でも、呼び出し元で null チェック済み / 型が non-nullable なら **FALSE_POSITIVE**
- ガードは候補行の周辺だけでなく、**関数の入口と呼び出し元まで**遡って確認する

### 3. 意図的な違いの兆候

その書き方が意図的であることを示す証拠がないか。

- コメントで理由が説明されている（`// 意図的に〜` / `// NOTE:` / lint 抑制コメント）
- その挙動を固定するテストが存在する
- 該当すれば **FALSE_POSITIVE**（意図的な設計）または **UNCERTAIN**（意図は読めるが問題の可能性も残る場合）

### 4. 影響の実在性

問題が成立するとして、その箇所で実害に到達するパスがあるか。

- 例: 到達不能コード、テスト専用コード、デッドパスなら影響なし → **FALSE_POSITIVE**（ただしデッドコード自体は INFO としてレポートに記載してよい)

### 5. 修正の安全性

Phase 1 の修正案をこの箇所に適用したとき、既存の挙動を壊さないと言えるか。

- 修正案がこの箇所の文脈に適合しない（同じ問題だが直し方が異なる）場合は **CONFIRMED としたうえで修正案を箇所別に調整**する
- 修正による挙動変更が仕様変更に相当する可能性がある場合は **UNCERTAIN**

## Fail-safe 原則

- **UNCERTAIN → CONFIRMED への昇格は禁止**。追加の文脈（ユーザ回答・ドキュメント）が得られた場合のみ再判定できる
- **CONFIRMED → UNCERTAIN への降格は常に許可**（保守的な方向は自由）
- 誤修正（偽陽性を直してしまう）のコストは、保留（真陽性を見送る）のコストより大きい。迷ったら直さない

## 判定例

**元の問題**: `JSON.parse(userInput)` を try-catch なしで呼んでおり、不正 JSON でクラッシュする（P1。重大度ラベルは例示であり、境界事例の倒し方は SKILL.md Phase 1 の規定に従う）

| 候補 | 文脈 | 判定 | 根拠 |
|------|------|------|------|
| `api/handler.ts:88` の `JSON.parse(req.body)` | 外部入力・ガードなし | CONFIRMED | 元箇所と同じ外部入力を未保護でパースしている |
| `config/loader.ts:12` の `JSON.parse(fs.readFileSync(...))` | 自リポジトリ内の設定ファイル。起動時に一度だけ実行 | UNCERTAIN | 入力は内部ファイルだが破損時の挙動（即クラッシュ）が意図か不明。fail-fast 設計の可能性がある |
| `test/fixtures.ts:30` の `JSON.parse(FIXTURE)` | 定数リテラルのパース | FALSE_POSITIVE | 入力が定数であり不正 JSON になり得ない。前提条件（外部入力）が異なる |
| `worker/job.ts:51` の `JSON.parse(msg)` | 直前に `isValidJson(msg)` ガードあり | FALSE_POSITIVE | 上流ガードが問題を無効化している（チェック2） |

## 記録フォーマット

`.codex/tmp/sweep-fix/verdicts.json`:

```json
{
  "problem_id": "P1",
  "verdicts": [
    {
      "file": "api/handler.ts",
      "line": 88,
      "verdict": "CONFIRMED",
      "reason": "元箇所と同じ外部入力（req.body）を未保護でパースしている"
    },
    {
      "file": "test/fixtures.ts",
      "line": 30,
      "verdict": "FALSE_POSITIVE",
      "reason": "入力が定数リテラルであり前提条件（外部入力）が異なる"
    }
  ]
}
```

`reason` は必須。空の reason を持つ verdict は不正データとして扱い、その候補を UNCERTAIN で再判定する。
