# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

Claude Code / Codex CLI 共用の自作スキル集（デュアルプラグイン構造）。実装計画の作成→レビュー→自動実装までのワークフローを提供する。
Claude Code の Plugin として `claude plugin install` でインストールするか、`claude --plugin-dir` でローカルテストできる。
Codex CLI では `codex-skills/` 配下のスキルを `$skill-name` 形式で呼び出す。

## アーキテクチャ

### デュアルプラグイン構造

- **commands/** — Claude Code 用スラッシュコマンド（`/claude-skills:plan-create` 等）。ユーザーが直接呼び出すエントリーポイント。各 `.md` ファイルが1つのコマンドに対応。
- **skills/** — Claude Code 用スキル定義。各ディレクトリが `SKILL.md`（メインロジック）を持ち、必要に応じて `references/`（テンプレート・チェックリスト等の参照資料）を含む。
- **codex-skills/** — Codex CLI 用スキル定義。Claude Code 版と同じワークフローを Codex CLI ネイティブのツール（`spawn_agent`, `send_message`, `apply_patch`, `shell` 等）で再実装。references の共有は内容基準: 真にツール非依存なら `skills/` への symlink、ツール名・Codex 第二意見節を含むなら変換済み実体コピー（`EXTRA_SYNC_PAIRS` で台帳追跡）。判定基準は `codex-skills/shared/references/tool-mapping.md` の「共有契約の可搬性ポリシー」。

### 共有リソース

- **skills/shared/** — 複数スキルが共有するリソースの配置場所。`skills/shared/references/` にロール定義等の共有参照資料を含む。
  - `team-config.md`: team-plan、team-cycle、team-brainstorm が共有する AgenticTeam のロール定義
  - `severity-and-verdicts.md`: 重大度（BLOCK/WARN/INFO/PASS）・レビュー判定（APPROVED系 / PASS系）・文脈検証3値判定（CONFIRMED/FALSE_POSITIVE/UNCERTAIN のフレーム。検証述語は sweep-fix / refactor がスキルごとに特殊化）の定義元。team-plan / team-cycle / sweep-fix / refactor / iterate / plan-reviewer（スコアバンド方言として承認済み）等が参照。fix-action-taxonomy と直交・相互リンク
  - `codex-integration.md`: plan-reviewer、codebase-review、iterate、brainstorm が共有する Codex セカンドオピニオンの呼び出しパターン・バイアス制御（自分の結論を渡さない / 敵対的フレーミング / doubt theater 検出）・フォールバック・セキュリティルール
  - `polling-pattern.md`: FS adapter (`skills/issue/`) / Label adapter (`skills/github-issue/`) が共通参照する polling パターン契約（状態機械 / interface / 純関数 / 安全ブレーキ）。単一ホスト前提
  - `lang-detect.md`: attack-review（Claude / Codex 両版）、generate-review-rules が共有する言語・フレームワーク検出契約（ビルドファイルマッピング / フレームワーク検出 / role分類）。`codex-skills/shared/references/lang-detect.md` は `skills/shared/references/` への symlink で同一内容
  - `tdd-contract.md`: cycle、iterate、test-driven-development が共有する TDD (RED-GREEN-REFACTOR) 共通契約。Agent プロンプトに注入してテストファースト開発を強制
  - `verification-gate.md`: cycle、iterate、commit、test-driven-development が共有する完了前検証ゲート共通契約。証拠なしの完了主張を防止
  - `design-system-contract.md`: design-scaffold、design-lint、design-generate、design-validate、mockup-diff が共有するデザインシステム検証の共通契約（ファイル構造 / Token 参照 / CSS 命名規則 / 検証階層 / Lint ルール ID 体系 / Baseline 再承認トリガー / Adapter 契約）
  - `orchestration-patterns.md`: 複数エージェントを使うスキル・コマンドを設計するときの共通契約。endorsed パターン7種（Agent 委譲 / 並行ファンアウト+ファイルマージ / worktree 分離 / チーム議論 / セカンドオピニオン / polling ループ / リサーチ隔離）とアンチパターン・モデル階層（レビュー・統合・実装は `opus`、小規模実装や機械的作業は `sonnet`、上流判断はセッションモデル。Agent 呼び出しに model を明示して高額モデルの継承を防ぐ。attack-review の `fable` 禁止）・判断フロー・カタログ追加ゲートを定義
  - `convergence-pattern.md`: goal-loop が実装する条件収束型ループ（「oracle が検証可能に真になるまで回す」）の共通契約。polling-pattern（キュー消化型）の姉妹契約。Oracle 定義 / ハッシュロックによる oracle-gaming（Goodhart）遮断 / failure signature と stall・oscillation 検出の純関数 / 安全ブレーキ（polling-pattern §6 流用）を定義
  - `measurement-identity.md`: 5つの計測系（polling TickResult / skill-regression ledger / trigger-eval / skill-improve / cycle 結果）を `skill × surface_sha256（挙動面 fingerprint）× run_id` の identity triple で結合する共通契約。イベントは `docs/loop/events.jsonl` に append-only（構造化のみ・自由文禁止・改竄不能）で記録し、`skills/shared/scripts/measurement_identity.py report --skill X` が surface（= instruction バージョン）別の成功率と直近改稿の効果差分を1コマンドで出す。writer は polling 両 adapter（tick）/ skill-regression（verification 履歴）/ trigger-eval（eval メトリクス）。No new silos rule: 新しい計測は新ストアを作らず本スキーマを拡張する
  - `loop-engineering.md`: loop-triage が実装する「センサー → トリアージ → キュー投入」閉ループの共通契約。Finding Schema / 冪等化（stable finding_id + baseline suppression + queue dedup）/ Admission Policy（fix_action × severity の純関数ルーティング、REPORT_ONLY 絶対非投入）/ 自己修飾ゲート（loop-defining ファイルに触れる finding は skill-regression の fixture カバレッジがない限り inbox 降格）/ Sensor Adapter 契約を定義。polling-pattern（消化側）の上流に位置する供給側の契約
  - `skill-authoring.md`: スキル新規作成・大幅改訂時のフォーマット仕様（frontmatter 契約 / トリガー語 / commands の位置づけ（skills-first: 新規は command なしがデフォルト、multi-workflow の名前付き入口のみ許可）/ 執筆原則 / 合理化防止テーブルの書き方 / Codex 移植の注意 / 追加チェックリスト）。機械検証可能なルールは validate_repo.py のチェック11（description のトリガー語・1024字上限）が CI で強制する
  - `checkpoint-pattern.md`: plan resume / handoff restore が共有する「長生きセッションの実行状態復元」契約。checkpoint は worktree バックアップではなく現在の git 状態と照合して使う restore ガイド。フォーマット（YAML frontmatter + 固定キー短文）/ 純関数シグネチャ正本（`compute_fingerprint` / `parse_checkpoint` strict / `classify` / `build_skeleton`）/ parse ゲート + semantic 5 分類（valid/stale/superseded/degraded/conflict、優先順位 `superseded > conflict > degraded > stale > valid`）/ 所有境界（4 項目のみ）と禁止事項 / 呼び出し側非対称（plan resume は conflict 無視続行・handoff fallback は conflict 停止）/ checkpoint vs handoff 境界表 / セキュリティ規約（PyYAML 不使用 strict parser / cycle_id `[0-9]{14}` + realpath containment / secret マスク / verify_on_restore は `{cmd,args}` 構造のみで**自動実行禁止**）/ v1 カバレッジ限界と v2 スコープ（hook / parallel-cycle 多重 writer / measurement イベント / Codex 版）を定義。セキュリティは文書でなく `skills/shared/scripts/checkpoint.py` + `test_checkpoint.py` で強制。verdict 語彙は false positive 回避のため validate_repo チェック12に**意図的に未登録**、遵守は fixture で守る
  - `goal-decomposition-pattern.md`: goal-decomposition が実装する「大枠ゴール → Loop Readiness Dossier」翻訳層の共通契約。既存 4 契約（loop-engineering 供給 / convergence-pattern 収束 / polling-pattern 消化 / measurement-identity 計測）の**上流**に位置し、dossier の各フィールドを既存契約の語彙に写像する（独自語彙を増やさない）。Dossier Schema v1（canonical キー階層の単一ソース）/ 第一問決定木（完了条件 / 未達検出器 / 人間判断 → wire_to 5 値の導出）/ 5 軸 routing proof / status ライフサイクル（draft/approved/superseded/rejected、approved は実行権限を与えない）/ wire_to×exit_to compatibility matrix / proxy oracle 許容条件（LLM judge 主観評価は禁止）/ supply gap 3 分類 playbook / 信頼境界 fence 規約 / GD001-GD302 の lint rule catalog を定義。rule 表は `dossier_lint.py` の RULES と catalog-sync テストで一致保証

### コマンド→スキルの関係

コマンドは Skill ツール経由でスキルを呼び出す薄いラッパー。ロジックはスキル側に集約する。

**skills-first 方針**: skills はクロスツールの共通分母（Codex CLI / APM 等は commands 相当を非サポート）であり、Claude Code でもスキルは `/skill-name` で直接起動できる。そのため**新規スキルは command なしをデフォルト**とし、command を追加するのは multi-workflow スキルの名前付きエントリポイント（issue-* / brainstorm-* 等）が必要な場合のみ。既存 commands は互換性のため維持する（積極的に増やさず自然減）。詳細は `skills/shared/references/skill-authoring.md` の「Commands の位置づけ」を参照。

```
commands/plan-create.md  →  skills/plan/SKILL.md
commands/plan-review.md  →  skills/plan-reviewer/SKILL.md
commands/plan-refine.md  →  skills/plan-reviewer/SKILL.md (ループ実行)
commands/plan-implement.md → skills/plan/SKILL.md
commands/cycle.md        →  plan-refine + plan-implement を Agent で連鎖実行
commands/commit.md       →  skills/commit/SKILL.md
commands/iterate.md      →  skills/iterate/SKILL.md
commands/doc-check.md    →  skills/doc-check/SKILL.md
commands/issue-create.md →  skills/issue/SKILL.md (create ワークフロー)
commands/issue-list.md   →  skills/issue/SKILL.md (list ワークフロー)
commands/issue-plan.md   →  skills/issue/SKILL.md (plan ワークフロー)
commands/issue-cycle.md  →  skills/issue/SKILL.md (cycle ワークフロー)
commands/issue-close.md  →  skills/issue/SKILL.md (close ワークフロー)
commands/issue-team-cycle.md →  skills/issue/SKILL.md (cycle --team ワークフロー)
commands/issue-polling.md →  skills/issue/SKILL.md (polling ワークフロー)
commands/plan-resume.md  →  skills/plan/SKILL.md (セッション復帰)
commands/plan-status.md  →  skills/plan/SKILL.md (ステータス更新)
commands/parallel-cycle.md → skills/parallel-cycle/SKILL.md
commands/investigate.md  →  skills/investigate/SKILL.md
commands/brainstorm.md   →  skills/brainstorm/SKILL.md (session ワークフロー)
commands/brainstorm-wrap.md → skills/brainstorm/SKILL.md (wrap ワークフロー)
commands/brainstorm-list.md → skills/brainstorm/SKILL.md (list ワークフロー)
commands/brainstorm-plan.md → skills/brainstorm/SKILL.md (plan ワークフロー)
commands/brainstorm-cycle.md → skills/brainstorm/SKILL.md (plan --cycle ワークフロー)
commands/brainstorm-team-cycle.md → skills/brainstorm/SKILL.md (plan --team-cycle ワークフロー)
commands/brainstorm-resume.md → skills/brainstorm/SKILL.md (resume ワークフロー)
commands/doc-write.md    →  skills/doc-write/SKILL.md (write ワークフロー)
commands/doc-write-resume.md → skills/doc-write/SKILL.md (resume ワークフロー)
commands/team-cycle.md   →  skills/team-cycle/SKILL.md
commands/team-plan.md    →  skills/team-plan/SKILL.md
commands/team-brainstorm.md → skills/team-brainstorm/SKILL.md (session ワークフロー)
commands/team-brainstorm-wrap.md → skills/team-brainstorm/SKILL.md (wrap ワークフロー)
commands/skill-improve.md    →  skills/skill-improve/SKILL.md
commands/doc-audit.md    →  skills/doc-audit/SKILL.md
commands/migrate-cycles-to-plans.md → skills/migrate-cycles-to-plans/SKILL.md
commands/codebase-review.md → skills/codebase-review/SKILL.md
commands/attack-review.md → skills/attack-review/SKILL.md (full/auto ワークフロー)
commands/attack-review-server.md → skills/attack-review/SKILL.md (server ワークフロー)
commands/attack-review-client.md → skills/attack-review/SKILL.md (client ワークフロー)
commands/handoff-save.md →  skills/handoff/SKILL.md (save ワークフロー)
commands/handoff-restore.md → skills/handoff/SKILL.md (restore ワークフロー)
commands/github-issue-create.md → skills/github-issue/SKILL.md (create ワークフロー)
commands/github-issue-list.md → skills/github-issue/SKILL.md (list ワークフロー)
commands/github-issue-polling.md → skills/github-issue/SKILL.md (polling ワークフロー)
commands/github-issue-cycle.md → skills/github-issue/SKILL.md (cycle ワークフロー)
commands/design-guide.md     →  skills/design-guide/SKILL.md (session ワークフロー)
commands/design-guide-update.md → skills/design-guide/SKILL.md (update ワークフロー)
commands/design-guide-mockup.md → skills/design-guide/SKILL.md (mockup ワークフロー)
commands/design-scaffold.md    →  skills/design-scaffold/SKILL.md
commands/design-generate.md    →  skills/design-generate/SKILL.md
commands/design-validate.md    →  skills/design-validate/SKILL.md
commands/design-lint.md        →  skills/design-lint/SKILL.md
commands/mockup-diff.md        →  skills/mockup-diff/SKILL.md
commands/tdd.md              →  skills/test-driven-development/SKILL.md
commands/debug.md            →  skills/systematic-debugging/SKILL.md
commands/problem-solving.md  →  skills/problem-solving/SKILL.md
commands/codex-sync.md       →  skills/codex-sync/SKILL.md
```

> `generate-review-rules`、`sweep-fix`、`refactor`、`trigger-eval` はコマンドなし（Skill ツール直接呼び出し）。

### 主要スキル

| スキル | 役割 |
|--------|------|
| `plan` | 計画ファイル（`docs/plans/{timestamp}_{slug}.md`）、`docs/status.md`、`docs/session-history.md` の生成・管理 |
| `plan-reviewer` | 7観点並行レビュー + Codex セカンドオピニオン（Feasibility / Security / Performance / Architecture / Completeness / Alternatives / UI/UX 条件付き + Codex） |
| `codebase-review` | 4エージェント + Codex 並行によるコードベース全体レビュー。結果はJSON→統合エージェントが集約。Codex は独立セクション「Codex Perspective」として表示 |
| `generate-review-rules` | プロジェクト固有の `.claude/review-rules.md` を自動生成 |
| `commit` | 変更を分析し論理単位で自動コミット（確認なし即実行） |
| `iterate` | cycle 後の追加指示をサイズ適応型の軽量改善ループで実行。Phase 4 レビューに Codex セカンドオピニオンを並行取得 |
| `doc-check` | ドキュメントとコードベースの整合性を検証・自動修正。Codex 版は `codex-skills/doc-check/`（`shell` / `spawn_agent` / `apply_patch` に変換、検証対象に AGENTS.md も追加） |
| `issue` | plan 中に発見したスコープ外の問題を記録・管理し、plan → cycle に繋げる。polling ワークフローで `ready/` キューを self-driving 消化するラルフループも提供 |
| `parallel-cycle` | 自然言語の指示を複数 plan に分解し、worktree で並行 cycle 実行・自動マージ。Codex CLI 版は `codex-skills/parallel-cycle/`（`spawn_agent` / `wait_agent` / `$<skill>` / `git worktree` 直叩き、承認プロンプトは撤廃して完全 headless、ワークフロー自体は Claude 版と同一） |
| `investigate` | 問題を読み取り専用で調査し、構造化レポートを出力。ファイル編集は一切行わない |
| `sweep-fix` | ユーザ指定範囲の問題検出 → パターン化 → コードベース全体への横展開検索（Grep/ast-grep/LSP、存在確認 + Grep フォールバック付き）→ 文脈検証（CONFIRMED/FALSE_POSITIVE/UNCERTAIN の3値判定で偽陽性除去、fail-safe: 迷ったら直さない）→ CONFIRMED 箇所のみ一括修正する find-one-fix-all 型スキル。skills-first 方針により command なし。severity-and-verdicts / orchestration-patterns / verification-gate の共有契約に準拠。Codex 版は `codex-skills/sweep-fix/`（`shell` / `spawn_agent` / `apply_patch` に変換、LSP は symbol-ref shell 検索に代替、orchestration-patterns 参照は inline 化） |
| `trigger-eval` | スキルセットの description 発火精度（recall / precision / stability / confusion matrix）を description-only 判定 subagent で機械的に実測し、衝突ペアを特定して description 改稿→再評価ループを収束まで回すメタスキル。静的衝突プレパス（`static_collisions.py` の語彙 Jaccard、LLM 不使用）+ Tier 1 選択シミュレーション（sonnet 判定 subagent、バッチ ≤20・並行 dispatch。selection モード＝弁別性の上界と autonomous モード＝スキル起動を強制しない salience 近似の 2 モードを既定で併走計測し、`--selection-only` で従来動作。結果は混合せず selection を正・autonomous を参考系列とする）+ Tier 2 E2E 実発火検証（使い捨て git worktree・6 セッション上限）の静的プレパス + 2 層評価。純関数（`collect_descriptions.py` / `static_collisions.py` / `aggregate_metrics.py`）を unittest で検証し、エージェントは JSON 生成・受け渡しのみ。事前固定原則 + holdout 採用ゲート + 悪化ガードで過適合と description 盛りを機械的に防ぐ。プロンプト本文採取は `skill-improve/collect.py` の `--capture-prompts`（opt-in、git-ignored `.claude/tmp` 制限、`[REDACTED:kind]` 完全マスク）に一元化。`empirical-prompt-tuning`（本文実行の質）の姉妹スキル。skills-first 方針により command なし。初版は Claude 版のみ |
| `context-audit` | LLM 向け指示ファイル（root の CLAUDE.md / AGENTS.md、`.claude/rules` / `rules`、`.claude/review-rules.md`）+ cwd 対応プロジェクトメモリの老朽化・矛盾・有害指示・クロスツール乖離を監査する棚卸しスキル。trigger-eval 踏襲の「純関数は unittest で検証、エージェントは JSON 生成・受け渡しのみ」構成。監査ロジックは 4 スクリプト（`collect_targets.py` path allowlist 収集 + cwd→memory slug 解決/reverse-verify / `static_checks.py` CA-* rule registry ディスパッチャ / `apply_fixes.py` AUTO_FIX 適用純関数・body byte 不変・idempotent / `aggregate_report.py` baseline suppression + summary-first レポート）に集約し、secret 検出は `skills/shared/scripts/secret_detect.py`（skill-improve と共有）を再利用。finding は severity（BLOCK/WARN/INFO/PASS）と直交する fix-action 3値（AUTO_FIX / NEEDS_JUDGMENT / REPORT_ONLY、`skills/shared/references/fix-action-taxonomy.md` を doc-audit と共有）で扱い、**削除・本文書き換えは絶対に自動化しない**（迷ったら安全側に倒す）。メモリ監査はデフォルト cwd 対応プロジェクトのみ・グローバルは `--include-global` opt-in。baseline は commit するが opaque finding ID のみ格納（検出値・本文を絶対に載せない）。CA-D002 は validate_repo.py 検出時に機械的自動スキップ。doc-check（code⇔docs）/ doc-audit（docs⇔docs）が見ない「指示品質」を所有。純関数を unittest で検証（`test_*.py` 6種）。skills-first のため command なし。初版は Claude 版のみ |
| `skill-regression` | スキルの「調律済みの挙動」を fixture として資産化し、変更時に影響スキルだけへ回帰評価を回すハーネス。挙動面（`skills/<name>/` 配下 + SKILL.md からの md リンク推移閉包 = 共有契約含む）を `dep_graph.py` で算出し、変更ファイル → 影響スキルを逆引き。検証台帳 `ledger.json`（sync-manifest と同思想: 挙動面の sha256 が前回検証時から変わったのに台帳が古いままなら CI fail、`--update --accept` で「実行せず不要判断」を明示記録 = 黙殺だけを不可能にする）。fixture は `skills/<name>/fixtures.json`（opt-in、シナリオ 2〜3 本 + [critical] 付き要件 3〜7 項目、白紙実行者 subagent で再生し critical 全 ○ で合格）。trigger-eval が「正しく発火するか」を守るのに対し、本スキルは「発火後に正しく実行されるか」を守る。fixture の生産手段（empirical tuning / plan 受け入れ条件 / 手動設計）には依存しない。純関数（`md_links.py`（shared）/ `dep_graph.py` / `ledger.py`）を unittest で検証。skills-first のため command なし。本リポジトリ専用・Claude 版のみ |
| `refactor` | ユーザ指定スコープ（ファイル / ディレクトリ / クラス名 / 「直近Nコミット」）を完全理解（Chesterton's Fence + 検証手段の確保）し、**動作を完全に維持したまま**表現だけをリファクタ → 類似コードへ文脈検証つき横展開（similarity-ts/rs / ast-grep / Grep を役割別に使い分け、存在確認 + フォールバック）→ 3値判定（CONFIRMED/FALSE_POSITIVE/UNCERTAIN、fail-safe）→ origin は APPLY、スコープ外 sweep_candidates は opt-in。発見したバグは修正せず issue 化コマンド案として提示（自動作成なし・docs 変更ゼロ）。skills-first 方針により command なし。検証観点は refactor 固有の `references/behavior-preservation-checks.md`（sweep-fix の context-verification.md はバグ成立検証向けで意味が異なるため流用しない）。3値判定の定義は severity-and-verdicts に準拠、orchestration-patterns / verification-gate も参照。Codex 版は `codex-skills/refactor/`（`shell` / `spawn_agent` / `apply_patch` に変換。Codex 未移植の orchestration-patterns 参照と Claude ビルトイン simplify 比較行は `<!-- REVIEW -->` マークで要判断保留） |
| `brainstorm` | アイデアの壁打ちに特化。発散→収束→plan化の導線を提供。壁打ち中はファイル編集禁止。各ターンで Codex セカンドオピニオンを取得し多角的な視点を提供。Codex CLI 版は `codex-skills/brainstorm/`（Codex セカンドオピニオンは冗長なため除外、`request_user_input` ベースの対話ループ、wrap/plan のファイル生成は `apply_patch`） |
| `doc-write` | LLMとのやり取り・調査結果をリーダブルなドキュメントに昇華。Mermaid図付き。Codex 版は `codex-skills/doc-write/`（`apply_patch` に変換、references は symlink 共有。Web 調査機能は Codex 環境依存で第3層 REVIEW 保留中） |
| `team-cycle` | AgenticTeam によるチーム議論型レビュー + 自動実装サイクル。4専門レビュワーが議論して計画品質を向上 |
| `team-plan` | AgenticTeam によるチーム議論型の計画作成。4専門家が議論しながら多角的な実装計画を作成。Codex 版は `codex-skills/team-plan/`（spawn_agent グループに変換、CLAUDE_CODE_EXPERIMENTAL 環境チェック削除） |
| `team-brainstorm` | AgenticTeam によるチーム議論型ブレインストーミング。4思考スタイル（Challenger/Explorer/Connector/Grounded）で多角的にアイデアを発散。Codex 版は `codex-skills/team-brainstorm/`（spawn_agent グループに変換、環境チェック削除、モデル指定テーブル除去） |
| `skill-improve` | セッションデータからスキル使用時の摩擦を検出・分析し、データ駆動でスキル改善を実行するメタスキル |
| `doc-audit` | docs 内の全アーティファクトを横断スキャンし、不整合を検出・自動修復する |
| `handoff` | セッション間のコンテキスト引き継ぎ。save で現在のコンテキストを `docs/handoff/` に構造化保存、restore で次セッションが読込→自動削除。Codex CLI 版は `codex-skills/handoff/`（`apply_patch` ベース、`shell` リダイレクト禁止、ツール名のみ置換で同一ワークフロー） |
| `migrate-cycles-to-plans` | `docs/cycles/` → `docs/plans/` のマイグレーション。ディレクトリ移動 + 全参照の一括置換 |
| `attack-review` | 6エージェント + Codex 並行によるコードベース攻撃者視点レビュー。リスクマトリクス（Likelihood×Impact）で脅威を分類。server/client/full モード切替対応。言語検出共通契約に基づく言語別攻撃プロファイル注入。Codex CLI 版は `codex-skills/attack-review/`（6 エージェントのみ、Codex セカンドオピニオンは冗長なため除外。`spawn_agent` / `shell` heredoc ベース、`AGENTS.md` / `.codex/tmp/` を参照） |
| `github-issue` | GitHub issue を起点に polling → draft PR → Codex レビュー → auto merge まで自走するスキル。共通契約 `polling-pattern.md` に準拠した Label state adapter 実装。多重防御 atomic claim + fail-closed Codex ゲート + atomic dual-write ラベル + FS retry state + 7 日 hard cap rollback + 単一ホスト前提 |
| `goal-loop` | 機械検証可能な oracle（判定コマンド + oracle_files）が真になるまで「oracle 実行 → 失敗出力を implementer agent に渡して修正」を自律反復する条件収束型ループ。共有契約 `convergence-pattern.md`（polling-pattern の姉妹契約）の参照実装。oracle_files をハッシュロックして毎イテレーション verify し、テスト・検証定義を弱めて合格する oracle-gaming を `oracle_tampered` halt で機械的に遮断（ループ内 manifest 更新 API は存在させない）。failure signature（正規化 + hash）による stall（同一失敗3連続）/ oscillation（周期 2〜3 の往復）検出で failed_streak より細かく無限ループを止める。oracle 実行はコントローラのみ（implementer の自己申告不採用 = maker/checker 分離）。純関数（`goal_loop.py`）を unittest で検証。安全ブレーキは polling-pattern §6 を流用。skills-first のため command なし。汎用スキル。Codex 版は `codex-skills/goal-loop/`（`shell`（oracle 実行）/ `spawn_agent`（implementer 委譲）に変換、goal_loop.py は symlink、convergence-pattern は変換コピー・polling-pattern は symlink で配置） |
| `loop-triage` | センサー（validate_repo 違反 / `ledger.py --check` の stale / context-audit findings）を Finding Schema に正規化し、stable finding_id で冪等化（baseline suppression + queue dedup）→ fix_action × severity の純関数 admission でルーティング → AUTO_FIX 級のみ `docs/issues/ready/` に enqueue して issue polling に供給するループ中枢スキル。loop-defining ファイル（SKILL.md / 共有契約 / commands / validate_repo.py）に触れる finding は skill-regression の dep_graph 逆引きで影響スキルを特定し、fixture 非保有が 1 つでもあれば AUTO_FIX でも `docs/loop/inbox.md` に降格する自己修飾ゲートを持つ（回帰網がある範囲でだけ自動化）。NEEDS_JUDGMENT は inbox、REPORT_ONLY は digest のみ（絶対に enqueue しない）。純関数（`finding_identity.py` / `admission.py` / `sensors.py` / `triage.py` の `run_triage`）を unittest で検証し、エージェントは実行と issue/inbox の書き出しのみ。共有契約 `loop-engineering.md` の参照実装。skills-first のため command なし。本リポジトリ専用・Claude 版のみ |
| `goal-decomposition` | 大枠ゴール（例:「コードベース全体を精査してリファクタリング完遂」）を Loop Readiness Dossier（自走可能性の型検査結果、`docs/loop/dossiers/{ts}_{slug}.json` + `.md` の 2 層）にコンパイルし、既存の閉ループ基盤（goal-loop / loop-triage / issue polling / measurement spine）への配線先を第一問決定木（完了条件 / 未達検出器 / 人間判断 → `wire_to`）で機械決定する入口スキル。主成果は「自走してはいけない断片を機械的に説明して止めること」— 願望を願望のまま自動化に流さない。compile（自然言語ゴール → dossier draft・出力は常に draft で承認は人間が JSON 直接編集）/ validate（`dossier_lint.py` 検査）の 2 ワークフロー。`dossier_lint.py` は純関数 RULES registry（GD001-GD302、終了コード 0/1/2、重複キー検出 / path containment / secret マスク）で、`validate_repo.py` チェック13から in-process 呼び出しされ CI で強制。共有契約 `goal-decomposition-pattern.md` の参照実装。approved は v1 では実行権限を与えない（配線実行は将来の別ゲート）。純関数を unittest で検証（`test_dossier_lint.py` 60 ケース + catalog-sync）。skills-first のため command なし。本リポジトリ専用・Claude 版のみ |
| `design-guide` | 対話型ディスカバリーでプロジェクト用 DESIGN.md（Google Stitch フォーマット準拠）を生成。Session（新規作成）/ Update（部分修正）/ Mockup（schema ベース生成 + 自動 lint + Base Design 承認 → baseline 確定。フィードバックループで納得いくまでリテイク可能、承認後は全て機械的検証）の3ワークフロー。Codex 版は `codex-skills/design-guide/`（会話ターン + apply_patch に変換、Playwright スクショは shell、mockup 環境前提を注記） |
| `design-scaffold` | DESIGN.md から machine-readable なデザインシステム（`.design/tokens.json` + `tokens.css` + `lint-config.json` + React theme）を scaffold 生成。DESIGN.md の「値の辞書」を機械的検証可能な schema ベースのシステムに変換する。Codex 版は `codex-skills/design-scaffold/`（`apply_patch` 生成に変換、schema 5本は symlink 共有） |
| `design-generate` | ページ定義（`.design/pages/*.json`）+ コンポーネントカタログに基づいて制約付きページ生成。LLM の自由度をコンテンツのみに限定し再現性を保証。生成後に自動 lint 実行。Codex 版は `codex-skills/design-generate/`（`apply_patch` 生成に変換、design-system-contract は symlink 共有） |
| `design-validate` | Static Lint → Visual Regression (Playwright) → Rubric Judge (LLM) の多段階検証ゲート。weighted average (mechanical 60% / visual 22% / llm-judge 18%) で合否判定。verification-gate 契約準拠の evidence 出力。lint/visual/full/report モード切替。Codex 版は `codex-skills/design-validate/`（`spawn_agent`(judge) / `shell`(Playwright) に変換、visual ゲートは playwright 環境前提） |
| `design-lint` | プロジェクトのコードベースを `.design/tokens.json` に基づいて lint し、デザイントークン違反（DL001-006 トークン / DL101-103 コンポーネント / DL201-204 ページ構成）を機械的に検出。実体は実行スクリプト `skills/design-lint/scripts/design_lint.py`（標準ライブラリのみ・unittest 付き）で、エージェントは実行と結果解釈のみを担う。終了コード 0/1/2 でそのまま CI に組み込み可能。Codex 版は `codex-skills/design-lint/`（`shell` 実行に変換、design_lint.py は symlink 共有） |
| `mockup-diff` | 承認済みモックアップ HTML vs 実行中アプリのスクショ比較で実装差異を検出・修正。Phase 0: SETUP でプロジェクトを自動調査しテーラーメイドの比較スクリプトを生成。design-validate がトークン準拠の機械検証なのに対し、mockup-diff は spacing/font/layout の実装品質ラストワンマイルを担当。Codex 版は `codex-skills/mockup-diff/`（`apply_patch`(compare.mjs 生成) / `shell`(node/Playwright) に変換、環境前提を注記） |
| `test-driven-development` | TDD (RED-GREEN-REFACTOR) の対話型ガイド。各フェーズで Bash テスト実行を要求し、テストファースト開発を強制。共有契約 `tdd-contract.md` + `verification-gate.md` を参照。Codex 版は `codex-skills/test-driven-development/`（`shell` / `apply_patch` に変換） |
| `systematic-debugging` | 4フェーズ構造化デバッグ（Root Cause Investigation → Pattern Analysis → Hypothesis & Testing → Implementation）。investigate の補完として修正まで実行。3回失敗ルールでアーキテクチャ問題を検出。Codex 版は `codex-skills/systematic-debugging/`（`shell` / `apply_patch` に変換、reference は symlink 共有） |
| `problem-solving` | 行き詰まった時の思考ツール集。5サブワークフロー（simplify/collide/invert/scale/pattern）で多角的アプローチ。brainstorm セッションからも呼び出し可能。Edit/Write 禁止（概念レベルの議論に集中）。Codex CLI 版は `codex-skills/problem-solving/`（`request_user_input` ベース、apply_patch 禁止、思考手法の内容は Claude 版と同一） |
| `codex-sync` | Claude 版スキルを Codex 版へ自動移植・差分同期するメタスキル（本リポジトリ専用）。port（新規移植）/ sync（同期台帳の sha256 から前回同期時点を特定し差分のみ移植）/ scan（未同期ペアの一括処理）の3モード。3層変換ルール（機械的置換 / 構造的変換 / 要判断）を適用し、validate → `--update-manifest` まで一気通貫。第3層は自動変換せず人間の判断を仰ぐ |

### ワークフロー設計パターン

- **Agent 委譲**: `cycle` コマンドのように重い処理は Agent ツールに委譲し、メインコンテキストにはサマリーのみ保持する
- **ファイル経由の受け渡し**: `codebase-review` ではエージェント間のデータ受け渡しに `.claude/tmp/` 配下のJSONファイルを使い、コンテキストウィンドウを節約する
- **ヘッドレス対応**: `cycle` コマンドはユーザー確認プロンプトを出さずに全自動で動作する
- **セッション履歴アーカイブ**: Completed セッションは `docs/session-history.md` に自動アーカイブされ、`docs/status.md` の肥大化を防ぐ
- **Worktree 並行実行**: `parallel-cycle` では `EnterWorktree`/`ExitWorktree` で各 cycle を物理的に分離し、複数 Agent を並行起動する
- **ファイル直交性チェック**: 並行実行前に各 plan の影響ファイル集合の交差を判定し、コンフリクトが原理的に発生しないことを保証する
- **部分成功の許容**: 複数 cycle のうち一部が失敗しても、成功分のみマージし失敗ブランチは保持する
- **スクリプト経由データ収集**: `skill-improve` では Python スクリプト（collect.py）を Bash 経由で実行し、JSONL セッションデータを構造化 JSON に変換してエージェントに渡す
- **Polling パターン**: `issue polling` / `github-issue polling` に代表される self-driving ループ。共通契約 `skills/shared/references/polling-pattern.md` に state machine / interface / 純関数 / 安全ブレーキを集約し、state adapter を DI で差し替える 2 実装構成: FS adapter (`skills/issue/`) と Label adapter (`skills/github-issue/`)。両 adapter とも **単一ホスト前提**。Kill file 2 系統（`.STOP` graceful + `.STOP.hard` hard）・max_iter/max_wallclock/failed_streak の 3 重ガード・SIGINT trap + 5 段階 orphan recovery（worktree / stale lock / long running 7 日 hard cap / recovery marker / closed 残ラベル）の多重防御で bypass-permissions 環境での暴走を防ぐ。Label adapter 固有: atomic dual-write ラベル + verification + FS retry state (`<state_root>/retry/{N}.json`) + `error_kind = "lock"` は failed_streak 非カウント

## インストール・開発

### Plugin としてインストール

```bash
# マーケットプレイスからインストール
claude plugin install claude-skills@<marketplace>

# ローカル開発（変更を即テスト）
claude --plugin-dir /path/to/claude-skills
```

`--plugin-dir` でのローカルテスト中は `/reload-plugins` で変更を即反映できる。

### レガシーインストール（非推奨）

```bash
./install.sh    # ~/.claude/ にシンボリックリンクを作成（非推奨）
```

> **Note:** `rules/` ディレクトリは Plugin フォーマットでは自動配置されない。グローバル rules が必要な場合は手動で `~/.claude/rules/` にコピーすること。

## 編集時の注意

- スキルの `SKILL.md` 内で参照する `references/` のファイルは相対パスでリンクしている。パスを変更する場合はリンクも更新すること
- コマンドの frontmatter（`---` ブロック）の `description` フィールドがスキル一覧での表示に使われる
- `.skill` ファイルは `.gitignore` で除外されている（単体ファイル形式のスキルは使わない方針）
- 編集後は `python3 scripts/validate_repo.py` を実行すること。symlink 切れ / 相対リンク切れ / frontmatter 欠落 / CLAUDE.md 対応表とcommands/ の不一致 / README・AGENTS.md のスキル名カバレッジ / plugin.json⇔marketplace.json のバージョン同期 / Claude⇔Codex 同期台帳 / SKILL.md description の品質（トリガー語・1024字上限）/ 共有契約語彙の適合（チェック12: AUTO_FIX 系・CONFIRMED 系・polling ガード・codex:codex-rescue 等の識別語彙を使う skill / command は契約への md リンク必須。免除は `CONTRACT_VOCAB_EXEMPT` に理由付きで登録）を機械検証する。CI（`.github/workflows/validate.yml`）でも push / PR ごとに同じチェックが走る
- **Codex 版があるスキル（`codex-skills/` に同名ディレクトリが存在）の SKILL.md や `commands/cycle.md` を変更したら**、Codex 版への反映要否を判断すること。反映（または反映不要と判断）したら `python3 scripts/validate_repo.py --update-manifest` で同期台帳 `codex-skills/sync-manifest.json` を更新する。台帳が古いままだと CI が「未同期」で fail する（サイレントドリフト防止）
- スキルを追加したら README.md（コマンド表・スキル表・ファイル構成）、CLAUDE.md（対応表・主要スキル表）、codex 版があれば AGENTS.md も更新すること（怠ると CI のドリフト検出で fail する）
- バージョン bump 時は `.claude-plugin/plugin.json` と `.claude-plugin/marketplace.json` の両方を更新し、`CHANGELOG.md` にエントリを追加すること（リリースノートは plugin.json ではなく CHANGELOG.md に書く）
