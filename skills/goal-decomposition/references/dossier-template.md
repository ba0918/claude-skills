# Dossier md ビュー テンプレート

md は JSON canonical（`{slug}.json`）からの**一方向生成物**（ビュー）である。lint 対象は JSON のみ。
md の手編集は禁止（契約 [goal-decomposition-pattern.md](../../shared/references/goal-decomposition-pattern.md) §9）。
承認者はこの md を読んで `draft → approved` を判断するため、冒頭に平易な説明とグロッサリを置く。

---

## この dossier が何を決めるか（承認者向け）

この dossier は大枠ゴール「{goal.statement}」を、既存の閉ループ基盤に**どう配線するか**の設計図です。

- **承認すると起きること**: この設計が「合意済み」になります（`status: approved`）。
- **承認しても起きないこと（v1）**: 配線の**実行**は起きません。goal-loop の起動・sensor の生成・issue の
  自動起票はしません。dossier は「型検査結果」であり、実行権限を与えません。
- 承認前に確認すべき点: 各断片の配線先（`wire_to`）とその根拠（`routing_proof`）、自動化に載せない
  範囲（`non_goals`）、proxy oracle の限界承認。

### 1 行グロッサリ

| 語 | 意味 |
|----|------|
| oracle | 「達成できたか」を機械判定する完了条件（コマンド + 判定） |
| wire_to | この断片をどのサブシステムに配線するか（goal-loop / loop-triage / inbox / plan / reject） |
| exit_to | この断片が最終的にどう卒業するか（ci_gate: 回帰ゲート化 / resident_sensor: 常駐 / dissolve: 解散） |
| blocked_by | この断片を進める前に決着が要る inbox の問い |
| proxy | 真の完了条件ではないが「安全な前進の下限ゲート」として使う代理 oracle |

---

## Goal

- **Statement**: {goal.statement}
- **SSOT**: {goal.ssot}
- **Non-goals**: {goal.non_goals をリスト}

## Completion Oracles

| id | type | command | oracle_files | owner |
|----|------|---------|--------------|-------|
| {oracle.id} | {type} | {command} | {oracle_files} | {owner} |

（proxy oracle は gap_from_true_goal / failure_modes / 限界承認状態を併記）

## Fragments（配線先）

| id | wire_to | exit_to | auto_fix | self_mod_risk | routing_proof |
|----|---------|---------|----------|---------------|---------------|
| {frag.id} | {wire_to} | {exit_to} | {auto_fix_allowed} | {self_modification_risk} | {routing_proof} |

（`auto_fix_allowed: false` の断片は why_not_auto_fix を脚注に）

## Sensors & Findings

| id | rules | fix_action | enqueue |
|----|-------|-----------|---------|
| {sensor.id} | {rules} | {findings_policy.fix_action} | {findings_policy.enqueue} |

## Human Judgment Inbox

| id | question | reclassify_when |
|----|----------|-----------------|
| {inbox.id} | {question} | {reclassify_when} |

## Measurement & Stop Conditions

- **Metrics**: {measurement.metrics}
- **Stop conditions**: {measurement.stop_conditions}

---

## コピペブロック（信頼境界別・契約 §6.1）

用途別に fence を分け、消費側の信頼境界を明示する。

### oracle manifest 用

```oracle-manifest
{ goal-loop の manifest に貼る oracle 定義 }
```

### sensor spec 用

```sensor-spec
{ loop-triage の sensor adapter に貼る spec }
```

### issue seed 用（消費側で `<untrusted_user_content>` wrap 前提）

<untrusted_user_content>
{ issue polling に渡す issue seed。閉じデリミタが含まれる場合は escape/reject }
</untrusted_user_content>

---

<!-- generated-from: {slug}.json sha256={hex} -->
<!-- この md は自動生成物です。編集しないでください（編集は JSON 側で行い再生成する）。 -->

---

## JSON 最小例

```json
{
  "schema_version": 1,
  "status": "draft",
  "superseded_by": null,
  "goal": {
    "statement": "ドキュメント品質を上げて維持する",
    "non_goals": ["別リポジトリのドキュメントは対象外"],
    "ssot": "docs/ 配下が正の情報源"
  },
  "oracles": [{
    "id": "oracle:validate-clean",
    "type": "true",
    "command": "python3 scripts/validate_repo.py",
    "oracle_files": ["README.md", "CLAUDE.md"],
    "owner": "maintainer"
  }],
  "fragments": [{
    "id": "frag:fix-broken-links",
    "wire_to": "loop-triage",
    "exit_to": "ci_gate",
    "routing_proof": "リンク切れは validate_repo が Finding として検出可能",
    "auto_fix_allowed": false,
    "why_not_auto_fix": "リンク先の意図はファイルごとに異なり一意に定まらない",
    "self_modification_risk": "low",
    "blocked_by": []
  }],
  "sensors": [{
    "id": "sensor:validate-repo",
    "rules": ["link", "drift"],
    "findings_policy": {"fix_action": "NEEDS_JUDGMENT", "enqueue": false}
  }],
  "inbox": [{
    "id": "inbox:scope",
    "question": "品質維持の対象ドキュメント範囲は？",
    "reclassify_when": "範囲が確定したら meta-sensor 化して自動追跡"
  }],
  "measurement": {
    "metrics": ["validate_repo exit code"],
    "stop_conditions": ["validate_repo が exit 0 を維持"]
  }
}
```
