---
description: "デザインシステム準拠の多段階検証ゲート（lint + visual test + rubric judge）"
---

`design-validate` スキルの **Validate** ワークフローを実行する。

## 手順

1. Skillツールで `claude-skills:design-validate` を起動する
2. ユーザーの引数 `$ARGUMENTS` をそのまま渡す（lint / visual / full / report）
