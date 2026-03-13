---
name: generate-review-rules
description: プロジェクトの CLAUDE.md、ドキュメント、コード構造を分析し、plan-reviewer およびコードレビュー用のプロジェクト固有レビュールール (.claude/review-rules.md) を自動生成する。「レビュールール生成」「generate review rules」「review-rules 作成」「レビュー設定」で起動。新しいプロジェクトでレビューを始める前のセットアップとして使用。
---

# Generate Review Rules

プロジェクトのドキュメントとコード構造を分析し、plan-reviewer およびコードレビューで使用するプロジェクト固有レビュールールを `.claude/review-rules.md` に生成する。

## Workflow

### Step 1: 情報収集

以下のソースを順に読み込む（存在するもののみ）:

1. `CLAUDE.md`（プロジェクトルート）— Design Principles、Tech Stack、Architecture セクションを重点的に
2. `docs/ARCHITECTURE.md` or `docs/architecture.md`
3. `docs/SECURITY.md` or `docs/security.md`
4. `docs/status.md` — プロジェクトの現在の状態把握

### Step 2: プロジェクト特性の検出

ビルドファイルからプロジェクトの言語・FW を特定:

| ファイル | 言語/FW |
|---------|---------|
| `Cargo.toml` | Rust |
| `package.json` | Node.js / TypeScript |
| `go.mod` | Go |
| `pyproject.toml` / `requirements.txt` | Python |
| `build.gradle` / `pom.xml` | Java/Kotlin |

Glob で上記ファイルを探す。複数ヒットした場合はモノレポの可能性あり。

### Step 3: ルール生成

収集した情報から `.claude/review-rules.md` を生成する。

出力テンプレート: [references/output-template.md](references/output-template.md)

**生成ルール:**
- CLAUDE.md に明記された設計原則は **そのまま引用**（解釈で変質させない）
- 言語/FW 固有の典型的な落とし穴を Language/Framework Specific セクションに追加
- プロジェクトに存在しない観点のセクションは省略（無理に埋めない）
- 各ルールは具体的・検証可能に書く（「良い設計にする」のような曖昧表現は禁止）

### Step 4: 確認と出力

1. `.claude/review-rules.md` が既に存在する場合はユーザーに上書き確認
2. 生成内容をユーザーに提示し、調整の機会を与える
3. 承認後にファイルを書き出す
