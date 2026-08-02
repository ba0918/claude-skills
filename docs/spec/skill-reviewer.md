# skill-reviewer

## 位置づけ

スキル成果物（`skills/*/SKILL.md` / `skills/*/references/**` / `skills/*/fixtures.json` / `skills/*/scripts/**` / `skills/shared/references/**` / `commands/*.md`）専用のレビュースキル。マージ可否を決めるゲートではなく**診断器**である。機械ゲートは既存の run_checks + regression ledger が担い、skill-reviewer は新しい強制を一切追加しない。

## 出力の 2 チャネル分離

出力は 2 チャネルに分かれ、cycle が制御判断に使えるのは `control_candidates` チャネルのみ。この分離は申し合わせではなく、スキーマ検証可能な不変条件として consumer 側の分岐でも強制する。

- **`control_candidates` チャネル**: BLOCK は「既に存在する機械的証拠を指せる指摘」（落ちるテスト・validate_repo 違反・本文だけで反証が完結する契約矛盾）のみ。この BLOCK には qualification_reason が必須で、欠くものはスキーマ検証で拒否される（WARN への強制はない — 必須化は BLOCK のみ）。WARN は記録して続行し、自動修正されるのは fix_action: AUTO_FIX が明示された指摘だけ。停止・修正の最終判断の所有者は cycle であり、レビュアーの verdict は停止命令ではない。
- **`diagnostics` チャネル**（WARN / OPPORTUNITY / INFO）: cycle の状態遷移に一切影響しない。自動修正・再レビュー・headless 停止のいずれにも使われず、表示と記録のみ。

## verdict 語彙

表面は BLOCK / WARN / OPPORTUNITY / INFO の 4 段。共有契約 severity-and-verdicts へは OPPORTUNITY の 1 行と skill-reviewer 方言節（BLOCK には機械的証拠が要る）のみを追加し、impact × evidence の二軸分類は skill-reviewer の内部規則に留める。

## 実走と証拠

skill-reviewer 自身は LLM 実走センサー（skill-regression 実走・trigger-eval 動的評価・empirical-prompt-tuning）を回さない。自走するのは決定的で安い検証（静的チェック・scripts のユニットテスト）のみ。実走証拠は regression ledger 等の既存記録を読み、current_pass / accepted_without_run / stale / uncovered / invalid の 5 状態で分類する。accepted_without_run を「実走証拠あり」として表示してはならない。

実走証拠の欠如・陳腐化は「推奨」止まりで、gate には決して入れない。証拠なしは finding ではなく coverage 状態（unsupported / uncovered）として申告し、該当領域の PASS を主張しない。推奨には影響面の広さと概算コストを添え、実測をいつ払うかは人間が決める。

## OPPORTUNITY の扱い

OPPORTUNITY は diagnostics 専属。WARN への自動昇格は禁止、issue 化は人間の明示操作。fixture capture 候補の昇格は、観測可能な受入条件・再現可能な重要シナリオ・回帰資産価値が揃うときに限り、材料がなければ INFO に留める。

## 非証拠宣言

すべての出力ヘッダに assurance_role: diagnostic_only / quality_gate_evidence: false / dynamic_sensors_executed: [] を固定し、品質ゲート証拠との誤認経路を構造的に潰す。

## 決定表の二層構成

①変更種別 → 参照する証拠・自走する静的チェックのルーティング層、②主張種別 → 言えること/言えないことの coverage 意味論層。実走要否をレビュアー裁量にしないため、レビューコストは変更種別から予測できる。
