# Friction Schema

collect.py の出力 JSON スキーマと friction-report.md のスキーマ定義。

## collect.py 出力 JSON スキーマ

```json
{
  "summary": {
    "project_filter": "string",
    "days": "integer",
    "sessions_found": "integer",
    "total_skill_invocations": "integer",
    "unique_skills_used": ["string"],
    "collection_timestamp": "ISO 8601 string"
  },
  "sessions": [
    {
      "file": "string (filepath)",
      "session_start": "ISO 8601 string | null",
      "session_end": "ISO 8601 string | null",
      "total_turns": "integer",
      "skill_count": "integer"
    }
  ],
  "skill_invocations": [
    {
      "skill": "string",
      "turn": "integer",
      "timestamp": "ISO 8601 string (optional)"
    }
  ],
  "friction_signals": {
    "{skill_name}": {
      "retry_count": "integer — 同一スキルの連続呼び出し回数",
      "correction_turns": "integer — スキル実行後の修正指示ターン数",
      "session_abandoned_count": "integer — セッション離脱回数",
      "tool_error_count": "integer — ツール実行エラー回数",
      "total_turns_to_completion": "integer — スキル完了までの総ターン数",
      "invocation_count": "integer — 呼び出し回数"
    }
  },
  "secret_warnings": [
    {
      "type": "string (aws_key | private_key | jwt | generic_secret | generic_long_key)",
      "masked": "string"
    }
  ]
}
```

## friction-report.md スキーマ

friction-report.md は以下のセクションを含む Markdown ドキュメント。

**重要: 生テキスト（セッション内容の原文）を含めてはならない。数値・分類・スコアのみ許可。**

```markdown
# Friction Report: {project}

**Generated:** {ISO 8601 timestamp}
**Period:** {days} days
**Sessions:** {count}

## Executive Summary
{1-3行の定量的要約。生テキスト禁止}

## Skill Rankings (摩擦スコア順)
| Rank | Skill | Friction Score | Invocations | Top Issue | Recommendation |
|------|-------|---------------|-------------|-----------|---------------|

## Detailed Findings

### {skill_name}
- **Friction Score:** {0-10 の数値}
- **Invocations:** {count}
- **Retry Rate:** {retry_count / invocation_count}
- **Correction Rate:** {correction_turns / invocation_count}
- **Abandonment Rate:** {session_abandoned_count / invocation_count}
- **Error Rate:** {tool_error_count / total_turns}
- **Issues:**
  - {issue_description — 定量的記述のみ}
- **Recommendations:**
  - {recommendation}

## Improvement Hypotheses

### Hypothesis {A/B/C}: {title}
- **Target:** {skill_name}
- **Change:** {変更内容の記述}
- **Expected Impact:** {定量的な期待効果}
- **Size:** Small / Large
- **Confidence:** High / Medium / Low
```

## 禁止フィールド

以下のフィールドは friction-report.md に **含めてはならない**:

- ユーザーのメッセージ原文
- アシスタントの応答原文
- セッション ID
- ファイルパスに含まれるユーザー名以外の個人情報
- シークレット（マスク済みであっても friction-report には含めない）
