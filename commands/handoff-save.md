---
description: 現在のセッションコンテキストを構造化テキストとして .agents/artifacts/handoff/ に保存する（次セッションへの引き継ぎ用）
allowed-tools: Bash, Glob, Grep, Read, Write
---

Artifact paths follow the [Artifact Store consumer contract](../skills/shared/references/artifact-paths.md).

$ARGUMENTS を考慮した上で、スキル `claude-skills:handoff` スキルを `save` モードで実行してください。
