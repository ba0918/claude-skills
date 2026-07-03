# Similarity Detection — 検出ツールの役割別使い分け

refactor Phase 3（SWEEP）で使用する。Phase 2 の各 `REFACTOR_CANDIDATE` の類似事例を
コードベースから探すためのツール選択・存在確認・フォールバック手順。

## 設計方針: 役割で選ぶ（純粋な段階フォールバックではない）

ツールは目的が異なる。候補の**性質**と**言語**で選ぶ。
検索は広め（偽陰性防止）、絞り込みは Phase 4（文脈検証）の責務。

| ツール | 役割 | 対応言語 | 選ぶ場面 |
|--------|------|---------|---------|
| `similarity-ts` / `similarity-rs` | 重複ブロック・コードクローンの**構造的**検出 | TS/JS（ts）、Rust（rs）のみ | 重複ロジック（C7）・コピペブロックを構造で拾いたい |
| `ast-grep` | 既知の**構文パターン**の全インスタンス列挙 | 多言語（言語指定） | ネスト三項（C3）・boolean フラグ（C4）等の構文形が明確 |
| `Grep` | 広めの**字面**検索 | 全言語 | 上記が使えない、または字面トークンで十分 |

## 存在確認とフォールバック

外部 CLI を可用性の前提にしない。**`which` で存在確認 → なければフォールバック**を必ず行う。

```bash
which similarity-ts || echo "NOT_AVAILABLE"
which ast-grep || echo "NOT_AVAILABLE"
```

フォールバックの優先順位:

```
similarity-*（構造的クローン検出）
  └─ なし → ast-grep（構文パターン）
       └─ なし → Grep（字面）
```

- フォールバックが発生したら `fallback_reason` を記録し REPORT に載せる
  （例: `"tool": "grep", "fallback_reason": "similarity-ts not installed; ast-grep unavailable"`）

## 言語カバレッジの非対称性（重要）

| 言語 | similarity-* | ast-grep | 横展開の運用 |
|------|:---:|:---:|------|
| TS / JS | ✅ similarity-ts | ✅ | 構造検出が使えるため通常運用 |
| Rust | ✅ similarity-rs | ✅ | 同上 |
| Python / Go / PHP / Dart 等 | ❌ | ✅（言語対応時） | 字面 or 構文検索のみ。**偽陽性リスクが上がるため保守的に運用** |

**similarity-* 非対応言語では**:
- 構造的クローン検出が使えないため、Grep / ast-grep の結果は偽陽性を多く含む前提で扱う
- Phase 4 の検証をより慎重に行い、UNCERTAIN を厚めに出す（fail-safe）
- `fallback_reason` に「similarity-* 非対応言語のため字面検索」と明記する

## 検索範囲の限定

- **Phase 0 スコープと同一言語・関連ディレクトリに限定**する。「コードベース全体」を無条件に走査しない
  （巨大 monorepo での similarity-* 全体走査は重く、無関係言語の候補はノイズ）
- 除外: `.git/` / `node_modules/` / ビルド成果物 / ロックファイル / vendored コード
- テストコードは除外しない（テスト内の同種改善も候補価値がある）

## コマンド例（すべて読み取り専用）

```bash
# similarity-ts: 重複ブロック検出（--threshold で類似度、書き込みフラグは使わない）
similarity-ts --threshold 0.85 "src/services"

# ast-grep: 構文パターンの列挙（--pattern。rewrite 系フラグは Phase 3 では使わない）
ast-grep --pattern '$C ? $A : $B ? $D : $E' --lang ts "src"

# Grep: 字面フォールバック（固有部分は汎化）
# origin: doExport(true)  → フラグ引数呼び出しを広く拾う
grep -rEn 'doExport\((true|false)\)' src
```

> Phase 3 は**検出のみ**。`ast-grep` の `--rewrite` / `-U` 等の書き換えフラグはここでは使わない
> （機械的変換は Phase 5 の Rule of 500 で条件付き使用）。

## 候補リストの構造

```json
{
  "improvement_id": "R1",
  "pattern_used": "doExport\\((true|false)\\)",
  "tool": "grep",
  "fallback_reason": "similarity-ts not installed",
  "scope": "src/services（同一言語 TS に限定）",
  "origin": { "file": "src/services/order.ts", "line": 42 },
  "sweep_candidates": [
    { "file": "src/services/invoice.ts", "line": 88, "excerpt": "doExport(true)" }
  ]
}
```

`pattern_used` / `tool` / `fallback_reason` は必ず記録する — REPORT で検索の再現性と
カバレッジの限界（非対応言語での保守運用）をユーザが事後検証できるようにするため。
