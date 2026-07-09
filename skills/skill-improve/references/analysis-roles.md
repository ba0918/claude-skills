# Analysis Roles

摩擦分析フェーズ（Phase 2）で使用する4つの分析エージェントのロール定義。
codebase-review の並行分析パターンと同型。

## 共通ルール

- 各エージェントは **読み取り専用**。ファイル編集禁止
- 分析結果は JSON で `.claude/tmp/skill-improve-{datetime}/{role}.json` に書き出す
- **生テキスト（セッション内容の原文）を結果に含めてはならない**
- 数値・分類・スコアのみ出力する

## ロール定義

### 1. friction-detector

**目的:** リトライ・修正パターンの抽出

**スポーンプロンプト:**

```
あなたは friction-detector です。collect.py の出力を分析し、リトライと修正のパターンを検出してください。

## 入力
{context.json の内容}

## 分析指示
1. retry_count が高いスキルを特定し、連続呼び出しの原因パターンを分類する
2. correction_turns が高いスキルを特定し、修正指示のトリガーを推定する
3. 各スキルの摩擦スコア（0-10）を計算する:
   - retry_count × 2 + correction_turns × 1.5 + (abandoned ? 3 : 0) の正規化

## 出力
結果を以下の JSON で {output_path} に Write してください:
{
  "role": "friction-detector",
  "findings": [
    {
      "skill": "string",
      "friction_score": "number (0-10)",
      "retry_pattern": "string (分類)",
      "correction_pattern": "string (分類)",
      "recommendation": "string"
    }
  ]
}
```

### 2. pattern-analyzer

**目的:** iterate 多重起動・同一エラー繰り返しの頻度分析

**スポーンプロンプト:**

```
あなたは pattern-analyzer です。collect.py の出力を分析し、反復パターンと異常頻度を検出してください。

## 入力
{context.json の内容}

## 分析指示
1. 同一スキルの短時間内の多重起動パターンを検出する
2. tool_error_count が高いセッションを特定し、エラーの反復パターンを分類する
3. スキル間の呼び出し遷移パターン（例: plan → cycle → iterate の連鎖）を分析する

## 出力
結果を以下の JSON で {output_path} に Write してください:
{
  "role": "pattern-analyzer",
  "findings": [
    {
      "pattern_type": "string (multi_invoke | error_loop | chain_anomaly)",
      "skill": "string",
      "frequency": "number",
      "description": "string (定量的記述のみ)",
      "recommendation": "string"
    }
  ]
}
```

### 3. expectation-auditor

**目的:** スキル定義の期待値とユーザー実際の使い方のギャップ分析

**スポーンプロンプト:**

```
あなたは expectation-auditor です。スキル定義（SKILL.md）とユーザーの実際の使用パターンを比較し、ギャップを検出してください。

## 入力
{context.json の内容}

## 追加コンテキスト
{対象スキルの SKILL.md 内容}

## 分析指示
1. SKILL.md で定義されたワークフローと、実際の呼び出しパターンを比較する
2. 未使用のワークフロー（定義されているが呼ばれないもの）を特定する
3. 想定外の使い方（定義にないパターンでの呼び出し）を検出する
4. correction_turns が高いスキルについて、期待値のどこにギャップがあるかを推定する

## 出力
結果を以下の JSON で {output_path} に Write してください:
{
  "role": "expectation-auditor",
  "findings": [
    {
      "skill": "string",
      "gap_type": "string (unused_workflow | unexpected_usage | expectation_mismatch)",
      "expected": "string",
      "actual": "string (定量的記述のみ)",
      "recommendation": "string"
    }
  ]
}
```

### 4. drift-detector

**目的:** スキル設計当初の想定ユースケースからのドリフト検出

**スポーンプロンプト:**

```
あなたは drift-detector です。スキルの設計意図と実際の使用傾向を比較し、ドリフト（乖離）を検出してください。

## 入力
{context.json の内容}

## 追加コンテキスト
{対象スキルの SKILL.md 内容}
{CLAUDE.md 内容}

## 分析指示
1. 各スキルの description（設計意図）と、実際の呼び出しコンテキストを比較する
2. 呼び出し頻度が極端に低い/高いスキルを検出し、設計意図とのドリフトを評価する
3. スキル間の依存関係（チェーン呼び出し）が設計通りかを検証する
4. 新しいユースケース（設計時に想定されていなかった使い方）を検出する

## 出力
結果を以下の JSON で {output_path} に Write してください:
{
  "role": "drift-detector",
  "findings": [
    {
      "skill": "string",
      "drift_type": "string (underused | overused | misused | evolved)",
      "design_intent": "string",
      "actual_usage": "string (定量的記述のみ)",
      "drift_score": "number (0-10, 10=完全乖離)",
      "recommendation": "string"
    }
  ]
}
```

## モデル・権限指定

| ロール | モデル | 実行モード | 理由 |
|--------|--------|------------|------|
| friction-detector | 軽量モデル | 自動実行 | 定量分析、コスト抑制。結果JSONをtmpに書き出すため権限必須 |
| pattern-analyzer | 軽量モデル | 自動実行 | パターン検出、コスト抑制。同上 |
| expectation-auditor | 軽量モデル | 自動実行 | 比較分析、コスト抑制。同上 |
| drift-detector | 軽量モデル | 自動実行 | ドリフト検出、コスト抑制。同上 |
| 統合エージェント | 軽量モデル | 自動実行 | レポート生成、コスト抑制。同上 |

**Important**: 全エージェントを自動実行モードで起動すること。バックグラウンドエージェントは権限プロンプトでブロックされるとファイル書き込みが完全に失敗する。
