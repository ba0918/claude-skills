# goal-decomposition — 大枠ゴールをループ可能状態にコンパイルする入口スキル

**Created:** 2026-07-07 22:23:56
**Status:** 📋 Planned
**Tags:** loop-engineering, meta-skill, goal-loop, loop-triage

---

## Summary

大枠ゴール（例:「コードベース全体を精査してリファクタリング完遂」）を Loop Readiness Dossier（自走可能性の型検査結果）にコンパイルし、goal-loop / loop-triage / inbox / 計測に配線する入口スキルの設計。主成果は「自走してはいけない断片を機械的に止めること」— 願望を願望のまま自動化に流さない。

## Key Discussion Points

- **課題の正体**: 閉ループ基盤（goal-loop / loop-triage / polling / measurement spine）は部品が揃っているのに「どのゴールをどの部品にどう配線するか」を決める入口がなく、翻訳作業が毎回 LLM の裁量任せ。「運用が分かりづらい」= 入口の発見可能性の問題
- **体系化の形**: ゴールを類型に振り分ける表ではなく「1 つの大枠ゴールを断片に分解して既存部品に配線するプロセス」。goal-decomposition は実行スキルではなく **compiler**（自然言語ゴール → oracle spec / sensor spec / issue seed / inbox question / measurement hook の束）
- **第一問**: 「この断片は完了条件か / 未達検出器か / 人間判断か」。oracle-first（観測可能か?）から始めると sensor 化できる断片を捨てる。自動修正可否（AUTO_FIX 等）は finding の属性であってゴール断片の属性ではないので最後に見る
- **5 軸**（機械検証可能性 / finding 化可能性 / 自動修正許容度 / 自己修飾リスク / 計測可能性）は routing 決定木だけでなく危険な組み合わせ検査（AUTO_FIX × 自己修飾リスク高など）にも使う。スコア表ではなく各断片への 1 行 routing proof（「なぜ AUTO_FIX でないか」必須欄付き）
- **supply gap は 3 種類**: ①sensor coverage gap（oracle 偽・queue 空・inbox 空 → sensor 追加）②人間判断の滞留（inbox に山 → ループの故障ではない）③decomposition gap（oracle が大きすぎて作業単位に割れない → oracle を弱めず中間 oracle を足す）。判定式は既存計測値で書けるため supply gap 検出自体をセンサー化できる
- **proxy oracle は条件付きで可**: 「安全な前進の下限ゲート」としてのみ（人間が限界を承認済み / ハッシュロック可能 / 達成後に人間判断へ接続）。LLM judge の主観評価は問答無用でアウト
- **具体例検証**（「ドキュメント品質を上げて維持する」）で見つかった穴: SSOT 宣言の欠落 / sensor の採用 rule 群まで明示しないと責任範囲が無限化 / 人間が作る対象リスト自体が drift する（meta-sensor が要る）/ CI ゲート移管後も除外リストのハッシュロックは続く / 「維持する」は断片ではなく出口戦略（regression gate で足りる場合は常駐 polling を選ばない — 常駐はコスト）

## Decisions & Conclusions

- **Dossier スキーマ**: 5 ブロック — Goal（non-goals + SSOT 宣言込み）/ Completion Oracles（oracle_files 所有権込み）/ Sensors & Findings（採用 rule 群明示）/ Human Judgment Inbox（再分類条件込み）/ Measurement & Stop Conditions。各断片に routing proof + `exit_to: ci_gate|sensor常駐|解散` + `blocked_by: inbox:<id>`（局所フィールド。DAG 全体設計はしない）
- **ファイル形式**: JSON canonical + md レポートの 2 層（lint は構造検査中心のため。md はビュー扱い）。置き場は `docs/loop/dossiers/{timestamp}_{slug}.json` + `.md`。events.jsonl には混ぜない
- **スキル構成**: 共有契約 `skills/shared/references/goal-decomposition-pattern.md`（既存 4 契約の上流「翻訳層」、独自語彙を増やさず既存契約のフィールド名に写像）+ `skills/goal-decomposition/`（薄い orchestrator、command なし、compile / validate の 2 ワークフロー）+ `scripts/dossier_lint.py`（validate_repo.py から呼ぶところまで v1 に含める — 任意運用の lint は儀式化する）
- **人間ゲートは状態で止める**: AskUserQuestion 必須を広げると headless と相性が悪い。dossier に status（draft / approved / superseded / rejected）のライフサイクルを持たせ「未承認 fragment は exit_to 実行不可」とする
- **v1 スコープ**: compile + lint + draft/approved まで。配線実行（goal-loop 起動 / sensor adapter 生成 / inbox 自動起票）はしない — inbox は loop-triage の route 結果であり writer を増やすと形式ドリフト。コピペブロックは用途別に fence を分けて信頼境界を明示（`<untrusted_user_content>` 契約との整合）
- **v1 の成功条件**: 「下流を起動できること」ではなく「自走してはいけない断片が機械的に説明されて止まること」。「回帰網がある範囲だけ自動化」の思想と一貫
- dossier 書き出し前に secret redaction（`secret_detect.py` 再利用）/ Codex 版は作らず Claude 版のみ / README・CLAUDE.md 更新は command なしでも必須
- **却下した代替案**: 「スキルではなく contract + linter だけで十分（plan / brainstorm から dossier を作らせる）」— 元の課題が入口の発見可能性である以上、description で発火する薄い入口スキルは必要

## Open Questions

- 発動条件の境界: いつこのメタプロセスを使い、いつ plan / cycle 直行でいいのか（儀式化防止の線引き。「大枠・長期・自走させたい」が仮の基準）
- sensor adapter の一般化: ゴール類型ごとの sensor 定義方法が未解決（現状の sensors.py は validate / ledger 等の本リポジトリ専用）
- oracle_files の実装限界: `goal_loop.py verify` CLI は manifest 記録済みパス中心で新規追加検出に限界。dossier での書き方規約が要る
- dossier 作成履歴を計測に乗せるか（乗せるなら measurement-identity 契約の閉 enum 改訂が必要）
- 名称: goal-decomposition / goal-intake / loop-design / admission package のどれに寄せるか

## Next Steps

- plan 化して実装に進む場合: `/claude-skills:brainstorm-plan` で本メモを plan に変換（共有契約 → dossier_lint.py + unittest → SKILL.md → validate_repo 統合 → 具体例 1 本で E2E 検証、の順が自然）
- 実装前に「テスト品質向上」（oracle_files 自体が改善対象 = oracle_tampered 禁止と正面衝突する最難関ケース）で机上 stress test をもう 1 周すると契約の穴が減る
