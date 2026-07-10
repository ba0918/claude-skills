# SI-* Rule Catalog

skill-interface-audit の全ルールの定義。
[skill-authoring.md](../../shared/references/skill-authoring.md) の執筆原則を正本とし、
その遵守を機械的に監査する。

- **Severity**（BLOCK / WARN / INFO / PASS）は問題の重大度。定義は
  [severity-and-verdicts.md](../../shared/references/severity-and-verdicts.md) に準拠。
- **Action**（AUTO\_FIX / NEEDS\_JUDGMENT / REPORT\_ONLY）は修正の自動化可否。severity と直交する別軸で、
  定義は [fix-action-taxonomy.md](../../shared/references/fix-action-taxonomy.md) に準拠。
- Phase 1（SI-S\*）は純関数で決定的に判定する。Phase 2（SI-C\*）は LLM が意味判断し、全て REPORT\_ONLY。

## ID band 規約

| prefix | band | 意味 |
|--------|------|------|
| `S` | `0xx` | structural — 構造・形式の機械検証 |
| `C` | `1xx` | contract — API 契約要素の意味的完備性 |

v2 で band を追加する場合はこの表を更新する。

## Finding ID 採番規則

同一ルールで複数箇所にマッチした場合、finding ID にサフィックスを付与する:
- 単一マッチ: `SI-S004`
- 複数マッチ: `SI-S004-1`, `SI-S004-2`, ...（検出順）

レポート内では `where` フィールド（`skill:file:line`）で一意に識別できるため、
サフィックスは可読性のための補助であり、baseline での照合には `where` を使う。

## Phase 1: Structural Rules（純関数）

validate\_repo.py が既に CI で強制しているチェック（frontmatter・description トリガー語・リンク実在・
共有契約語彙）とは重複しない。本フェーズは validate\_repo.py が見ない構造的品質を所有する。

| ID | Severity | Action | 正本 | 検証 | 内容 |
|----|----------|--------|------|------|------|
| SI-S001 | WARN | REPORT\_ONLY | skill-authoring #4 | 純関数 | **参照チェーン深度超過**: SKILL.md → references/ 内ファイル → さらに別ファイルへの md リンク（depth > 1）。Progressive disclosure は1階層まで |
| SI-S002 | WARN | REPORT\_ONLY | skill-authoring frontmatter | 純関数 | **description にワークフロー要約が混入**: 番号付きリスト・フェーズキーワード（Phase/Step/まず/次に）・手順記述パターンを検出。description は「何をするか + いつ使うか」に留める |
| SI-S003 | INFO | REPORT\_ONLY | skill-authoring #1 | 純関数 | **prose 肥大**: SKILL.md 内に `Workflow` / `Phase` / `Step` 系見出しを持たないセクションが全体の 60% 超。Process over prose 原則の逸脱指標 |
| SI-S004 | WARN | NEEDS\_JUDGMENT | AGENTS.md 編集ルール | 純関数 | **プラットフォーム固有ツール語彙の混入**: SKILL.md または references/ に特定プラットフォームのツール API 名（`Edit`, `Write`, `Read`, `Bash`, `Agent`, `Workflow` 等）やモデル固有名が含まれる。コードブロック・引用内は除外 |

### SI-S001 詳細: 参照チェーン深度

検出方法:
1. SKILL.md 内の相対 md リンクを抽出し、references/ 配下へのリンクを一次参照とする
2. 一次参照先ファイル内の相対 md リンクを抽出する
3. 一次参照先から shared/references/ 以外への md リンクがあれば finding（shared は共有契約なので許可）

### SI-S002 詳細: description ワークフロー要約

検出パターン（regex ベース）:
- `\d+[.)]\s` — 番号付きリスト
- `Phase\s*\d` / `Step\s*\d` — フェーズ・ステップ番号
- `まず.*次に` / `最初に.*その後` — 手順接続詞の連鎖
- `→` が 2 つ以上 — フロー矢印の連鎖

### SI-S003 詳細: prose 肥大判定

ヒューリスティック:
1. SKILL.md の `##` 見出しを分類: workflow 系（`Workflow` / `Phase` / `Step` / フロー / ワークフロー）vs prose 系（それ以外）。`###` 以下の小見出しは親 `##` の分類に従う。親 `##` を持たない独立 `###` は prose 系に分類する
2. 分母は **frontmatter を除く SKILL.md の総行数**（空行を含む）。prose 系セクションの総行数 / 分母 > 0.6 なら finding
3. 知識の羅列は references/ に逃がすべき（skill-authoring #1 + #4）

### SI-S004 詳細: プラットフォーム固有語彙

検出対象語彙（context-audit CA-D001 と同じリスト、対象ファイルが異なる）:
- ツール API 名: `Edit`, `Write`, `Read`, `Bash`, `Agent`, `Workflow`, `WebFetch`, `WebSearch`, `Grep`, `Glob`, `LSP`, `NotebookEdit`
- 日本語「〜ツール」表記: `Edit ツール`, `Bash ツール` 等
- モデル固有名: `claude-opus-*`, `claude-sonnet-*`, `claude-haiku-*`, `gpt-*`, `o1-*`

**大文字小文字の判定規則（英語 SKILL.md での誤検知防止）**:
- PascalCase のツール名（`Edit`, `Read`, `Write` 等）は**文頭以外**で単独出現した場合のみ検出する
- 文頭（行頭・ピリオド直後）の大文字は英語の通常表記であり除外する
- 小文字の `edit`, `read`, `write` 等は一般動詞として除外する（Unix コマンドとしても使われるため）
- `LSP` は業界標準プロトコル名としても使われるため、「`LSP` ツール」「`LSP` を使う」等のツール用法のみ検出し、プロトコル名としての言及（「`LSP` 準拠」「`LSP` サポート」等）は除外する

除外条件:
- コードブロック（`` ``` `` / `` ` `` 内）
- 引用ブロック（`> ` 行）
- ファイルパス中の語（`scripts/test_*.py` 等）
- 文頭（行頭・ピリオド直後）の大文字語
- Markdown 見出し内の語（`## Workflow` 等。見出しは行頭 `#` で始まるため文頭除外にも該当するが、明示的に除外する）
- 番号付きリスト直後の語（`3. Write ...` の `Write` 等。`N. ` のピリオドは文末ピリオドではないが、文頭相当として除外する）

## Phase 2: Contract Rules（LLM 意味判断）

全ルールの fix action は **REPORT\_ONLY**（上限は NEEDS\_JUDGMENT。AUTO\_FIX 禁止）。
finding にはパッチ候補（`fix_draft`: 追記すべき文面のドラフト）を含める。

**「該当なし」は正当な状態**: スキルの性質上、特定の契約要素が不要な場合がある。
LLM はスキルの目的・ワークフローを読んだ上で、「この要素が欠落すると
LLM が誤解して事故を起こしうるか」で判定する。不要と判断すれば PASS。

| ID | Severity | 正本 | 内容 | N/A となる典型例 |
|----|----------|------|------|----------------|
| SI-C001 | WARN | skill-authoring #2, #3 | **副作用未宣言**: ファイル生成・変更・削除、外部通信、状態変更が明示されていない。欠落すると LLM が「ついでに」副作用を追加する | 読み取り専用スキル（investigate 等）で「変更しない」と明記済み |
| SI-C002 | WARN | verification-gate.md | **完了条件の欠落/非検証可能**: 何をもって完了とするかが不明、または検証不可能な形で書かれている | 対話型スキル（brainstorm 等）でユーザーが終了を判断する |
| SI-C003 | WARN | skill-authoring #2 | **失敗時の扱い未定義**: エラー・中断時にどう振る舞うかが書かれていない。LLM は失敗を握りつぶして完了報告する | 失敗パスが存在しないスキル（problem-solving 等の思考ツール） |
| SI-C004 | INFO | — | **入力/引数契約の欠落**: 引数の一覧・デフォルト・引数なし時の動作が不明 | 引数を取らないスキル |
| SI-C005 | INFO | skill-authoring #2 | **出力/成果物の未定義**: 何を生成するか（ファイル・レポート・差分）が不明 | 対話のみで完結するスキル |
| SI-C006 | INFO | — | **委譲条件の未文書化**: 類似スキルとの境界・使い分けが書かれていない | 唯一の目的を持ち他スキルと混同しようがないスキル |

### Severity の根拠規律

SI-C001〜C003 が WARN、SI-C004〜C006 が INFO である根拠:

- **WARN（C001〜C003）**: 欠落時の LLM 事故モードが skill-improve の friction データおよび
  empirical-prompt-tuning の実測で観測されている（副作用の暴走、完了の誤判定、失敗の握りつぶし）。
  エビデンスが蓄積され次第、severity を昇格または降格する
- **INFO（C004〜C006）**: 欠落しても文脈から補われやすく、事故に直結した実測データがまだない。
  skill-improve のログで事故相関が確認されれば WARN に昇格する

## v2 候補（v1 対象外）

- SI-C007: 冪等性/再入可能性 — 中断後の再実行安全性
- SI-C008: 非対話フォールバック — headless 実行時の振る舞い
- SI-C009: 前提条件 — 実行環境の要件
- SI-S005: 合理化防止テーブルの欠落 — ファイル変更を伴うスキルでの推奨
- baseline の claim 正規化 hash + expiry
- SI-S\* の安定ルールの validate\_repo.py への昇格
