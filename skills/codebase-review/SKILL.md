---
name: codebase-review
description: コードベース全体を4つの専門エージェント（セキュリティ/機密情報、パフォーマンス/メモリ、実装品質/論理整合性、コード衛生/改善点）で並行レビューし、100点満点でスコアリングする。「コードベースレビュー」「全体レビュー」「codebase review」「コード品質チェック」「プロジェクト全体を分析」で起動。CLAUDE.mdがあればプロジェクト固有ルールも自動で考慮する。
---

# Codebase Review

コードベース全体を4つの専門エージェントで並行レビューし、統合スコアレポートを生成する。

**コンテキスト節約設計**: 全エージェントの分析結果はファイル経由で受け渡し、メインコンテキストにはサマリーのみ流入させる。

## Progress Checklist

```
codebase-review Progress:
- [ ] 対象範囲決定
- [ ] プロジェクト構造分析・作業ディレクトリ準備
- [ ] 4レビューエージェント並行起動
- [ ] 全エージェント完了待ち合わせ
- [ ] 統合エージェント起動
- [ ] サマリー表示・レポート配置
```

## Workflow

### Step 1: 対象範囲決定

引数に応じて対象範囲を決定:

| 引数 | 対象 |
|------|------|
| なし | コードベース全体（src/配下） |
| `差分のみ` `--diff` | `git diff HEAD`の変更ファイルのみ |
| ディレクトリ名 | 特定ディレクトリ |

対象ファイル: `*.ts`, `*.tsx`, `*.js`, `*.jsx`, `*.py`, `*.go`, `*.rs`, `*.java`, `*.php` 等のソースコード。
除外: `node_modules/`, `dist/`, `build/`, `.git/`, `*.test.*`, `*.spec.*`, `*.d.ts`, lockファイル。

### Step 2: プロジェクト構造分析・作業ディレクトリ準備

1. CLAUDE.md（プロジェクトルート＋`.claude/`配下）を読み、プロジェクト固有ルールを把握
2. ディレクトリ構造を把握（`ls` or `find`）
3. 主要設定ファイルを確認（`package.json`, `deno.json`, `tsconfig.json`, `Cargo.toml`等）
4. **作業ディレクトリを作成**:
   ```bash
   mkdir -p /tmp/codebase-review-{YYYYMMDD-HHMM}/
   ```
5. **context.jsonを書き出す**（Writeツールで作成）:
   ```json
   {
     "project_name": "プロジェクト名",
     "scope": "対象範囲の説明",
     "target_files": ["対象ファイルパス一覧"],
     "file_count": ファイル数,
     "claude_md_rules": "CLAUDE.mdの内容（あれば）",
     "work_dir": "/tmp/codebase-review-{YYYYMMDD-HHMM}",
     "datetime": "YYYY-MM-DD HH:MM"
   }
   ```

### Step 3: 4レビューエージェント並行起動

Taskツールで4つのエージェントを**並行**起動する（全て `run_in_background: true`）。

各エージェントに渡すコンテキスト:
- context.jsonのファイルパス
- レビュー観点の詳細（[references/review-criteria.md](references/review-criteria.md) の該当セクション）
- **出力先JSONファイルパス**

```
エージェント1: security-auditor       # セキュリティ + 機密情報 (合算35%)
エージェント2: performance-analyzer   # パフォーマンス + メモリ効率 (合算20%)
エージェント3: quality-inspector      # 実装品質 + 論理的整合性 (合算30%)
エージェント4: codebase-hygiene       # コード重複 + その他改善点 (合算15%)
```

各エージェントのsubagent_type: `general-purpose`

#### レビューエージェント プロンプトテンプレート

```
あなたは「{観点名}」の専門レビューアーです。
以下のコードベースを徹底的に分析してください。

## コンテキスト読み込み
まず {work_dir}/context.json を読み込み、プロジェクト情報と対象ファイル一覧を取得してください。

## プロジェクト固有ルール
context.json内の claude_md_rules を参照し、プロジェクト固有のルールに従ってレビューしてください。

## レビュー観点
{references/review-criteria.md から該当セクションの内容}

## 分析手順
1. context.jsonからtarget_filesを取得
2. 各ファイルを読み込み、上記チェック項目に基づいて分析
3. サブカテゴリごとに個別スコアとissuesを記録

## 結果出力（厳守）
分析結果を以下のJSON形式で **{work_dir}/agent-{N}-{category}.json** にWriteツールで書き出してください:

```json
{
  "agent": "{エージェント名}",
  "subcategories": [
    {
      "name": "{サブカテゴリ名}",
      "key": "{サブカテゴリキー}",
      "weight": 重み(数値),
      "score": 0-100,
      "issues": [
        {
          "severity": "critical|major|minor|info",
          "message": "問題の詳細説明",
          "file": "ファイルパス",
          "line": 行番号（不明なら0）,
          "suggestion": "具体的な修正提案",
          "effort": "low|medium|high"
        }
      ],
      "good_practices": ["良い点1", "良い点2"]
    }
  ],
  "summary": "総評（2-3文）"
}
```

スコア基準:
- 90-100: 優秀。重大な問題なし
- 70-89: 良好。軽微な改善余地あり
- 50-69: 要改善。対処すべき問題あり
- 30-49: 問題多数。早急な対応推奨
- 0-29: 危険。即座の対応が必要

## 出力制約（最重要）
あなたの分析結果は全て上記JSONファイルに書き出してください。
あなたの最終応答（Taskのresultとして返される部分）は、以下の1行のみとしてください:

DONE: {category}

これ以外のテキストを最終応答に含めないでください。長い分析結果や説明は全てJSONファイルに書き出し済みのはずです。
```

### Step 4: 統合エージェント起動

**4つ全てのレビューエージェントの完了を確認してから**、統合エージェントをTaskツールで起動する（`run_in_background: true`）。

統合エージェントのsubagent_type: `general-purpose`

#### 統合エージェント プロンプトテンプレート

```
あなたはコードベースレビューの統合レポートアナリストです。
4つのレビューエージェントの分析結果を統合し、最終レポートを生成してください。

## 入力ファイル
作業ディレクトリ: {work_dir}

以下のファイルを全て読み込んでください:
- {work_dir}/context.json（プロジェクト情報）
- {work_dir}/agent-1-security.json
- {work_dir}/agent-2-performance.json
- {work_dir}/agent-3-quality.json
- {work_dir}/agent-4-hygiene.json

## 処理手順

### 1. 各サブカテゴリのスコア収集
各JSONのsubcategories配列から、8つのサブカテゴリ個別スコアを取得。

### 2. 重み付け総合スコア算出
総合スコア = Σ(サブカテゴリスコア × 重み / 100)

重み: security=20, secrets=15, performance=12, memory=8,
      quality=15, logic=15, duplication=8, improvements=7

### 3. 全issueの統合・ソート
全エージェントのissuesを集約し、severity順にソート（critical→major→minor→info）。

### 4. 総合ランク決定
90-100=S, 80-89=A, 70-79=B, 60-69=C, 50-59=D, 0-49=F

### 5. 出力ファイル生成

**出力1: {work_dir}/summary.txt**

以下のフォーマットで正確に出力:

```
════════════════════════════════════════════════════════════════════════
  CODEBASE REVIEW REPORT
  Project: {project_name}
  Date: {datetime}
  Scope: {scope}
════════════════════════════════════════════════════════════════════════

  Overall Score: {total_score}/100  Rank: {rank}

  ┌─────────────────────────┬───────┬────────────┐
  │ Category                │ Score │ Status     │
  ├─────────────────────────┼───────┼────────────┤
  │ Security                │  XX   │ XXXXXXXXXX │
  │ Secrets                 │  XX   │ XXXXXXXXXX │
  │ Performance             │  XX   │ XXXXXXXXXX │
  │ Memory                  │  XX   │ XXXXXXXXXX │
  │ Quality                 │  XX   │ XXXXXXXXXX │
  │ Logic                   │  XX   │ XXXXXXXXXX │
  │ Duplication             │  XX   │ XXXXXXXXXX │
  │ Improvements            │  XX   │ XXXXXXXXXX │
  └─────────────────────────┴───────┴────────────┘

  Critical Issues: {N}件
  Major Issues: {N}件
  Minor Issues: {N}件

  Top 5 Critical/Major Issues:
  1. [{severity}] {message} ({file}:{line})
  2. ...

  Full report: docs/reviews/review-{YYYYMMDD-HHMM}.md
════════════════════════════════════════════════════════════════════════
```

Status: 90+→EXCELLENT, 70+→GOOD, 50+→NEEDS WORK, <50→CRITICAL

**出力2: {work_dir}/report.md**

レポートテンプレート（references/report-template.mdの構造）に従い詳細レポートを生成。
内容:
- エグゼクティブサマリー（総合スコア、ランク、概要）
- Critical/Major Issues一覧
- カテゴリ別詳細（8サブカテゴリ × スコア・issues・良い点）
- 改善ロードマップ（優先度順、推定工数付き）
- 付録（スコア算出式、対象ファイル一覧）

## 出力制約（最重要）
分析結果は全て上記2ファイル（summary.txt, report.md）に書き出してください。
あなたの最終応答は以下の1行のみとしてください:

DONE: integration

これ以外のテキストを最終応答に含めないでください。
```

### Step 5: サマリー表示・レポート配置

統合エージェントの完了を確認後:

1. **Readツール**で `{work_dir}/summary.txt` を読み込み、そのままコンソールに表示
2. **Bashツール**で `cp {work_dir}/report.md docs/reviews/review-{YYYYMMDD-HHMM}.md`
3. 完了メッセージ（レポートファイルパスを含む）を表示

**注意**: summary.txt以外のファイル（agent-*.json, report.md）をメインコンテキストに読み込まないこと。

## Reference

- レビュー基準詳細: [references/review-criteria.md](references/review-criteria.md)
- レポートテンプレート: [references/report-template.md](references/report-template.md)
