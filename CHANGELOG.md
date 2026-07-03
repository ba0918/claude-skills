# Changelog

claude-skills プラグインのバージョン履歴。
`.claude-plugin/plugin.json` の `version` を bump したら、このファイルにエントリを追加すること
（マーケットプレイスがスキル変更を認識するのは version bump 時のみ）。

## 1.31.0

`context-audit` スキルを新規追加。LLM 向け指示ファイル（root の CLAUDE.md / AGENTS.md、
`.claude/rules` / `rules`、`.claude/review-rules.md`）+ cwd 対応プロジェクトメモリの
老朽化・矛盾・有害指示・クロスツール乖離を監査する棚卸しスキル。

- **純関数ルールエンジン（CA-* ルール体系）**: trigger-eval 踏襲の「純関数は unittest で検証、
  エージェントは JSON 生成・受け渡しのみ」構成。`collect_targets.py`（path allowlist 収集 +
  cwd→memory slug 解決/reverse-verify）/ `static_checks.py`（CA-* rule registry ディスパッチャ）/
  `apply_fixes.py`（AUTO_FIX 適用純関数・body byte 不変・idempotent）/ `aggregate_report.py`
  （baseline suppression + summary-first レポート）の 4 スクリプト。
- **v1 ルール**: CA-S001/S002（参照実在）/ CA-U001（unsafe 語彙）/ CA-D001（ツール語彙混入）/
  CA-D002（カバレッジ差分・validate_repo 検出時は機械的自動スキップ）/ CA-C001（矛盾候補・
  candidate 抽出は純関数、判定は LLM の REPORT_ONLY）/ CA-M001/M101/M301（メモリ系）。
- **fix-action 3値判定（severity と直交）**: AUTO_FIX / NEEDS_JUDGMENT / REPORT_ONLY。
  taxonomy を `skills/shared/references/fix-action-taxonomy.md` に抽出し doc-audit と共有。
  **削除・本文書き換えは絶対に自動化しない**（迷ったら安全側に倒す）。
- **プライバシー制約**: メモリ監査はデフォルト cwd 対応プロジェクトのみ、グローバルは
  `--include-global` opt-in。slug 解決は実 Claude Code 実装に一致 + reverse-verify + fail-safe skip。
  secret は値を転記せずパターン名 + file:line のみ（redaction を全 finding の line-context に適用）。
  secret 検出は `skills/shared/scripts/secret_detect.py`（skill-improve と共有化）を再利用。
- **baseline suppression**: `.claude/context-audit-baseline.json` は commit するが opaque finding ID のみ格納。
- 純関数を unittest で検証（`test_*.py` 6 種、93 テスト）。skills-first のため command なし、初版は Claude 版のみ。

## 1.30.0

`trigger-eval` スキルの v2 改善（発火計測の妥当性強化 + トークン化・fail-closed の堅牢化）。

- **Tier 1 に autonomous モードを追加**。従来の selection モード（「一覧から最適スキルを選べ」＝ description 弁別性の上界）に加え、
  「普通に応答するかスキルを起動するか自分で決めよ。起動する場合のみスキル名を返せ」＝スキル起動を強制しない
  autonomous モード（salience/想起の近似）を新設。デフォルトで両モードを併走計測し、`--selection-only` で従来動作。
  モードごとに `judged-{mode}-iterN.json` / `metrics-{mode}-iterN.json` を別々に生成し**混合禁止**。収束・悪化ガードは
  selection を正、autonomous は参考系列 + Tier1↔Tier2 乖離のキャリブレーション信号（`aggregate_metrics.py` は無改修）
- **判定エージェントへの入力配布方法を正式契約化**: インライン渡し、または `skills.json` + バッチファイルの 2 ファイルのみ
  Read 許可のファイル渡しのいずれか。それ以外のツール・ファイル読取は禁止（soft guarantee）
- **`static_collisions.py` の日本語トークン化を bigram 化**（TDD）。CJK 単字ユニグラムを廃止し、連続 CJK run の
  sliding bigram に変更（単字 run は除外、`計画` のような 2 字語は 1 bigram として保持）。共通助詞・かなでの誤衝突を低減
- **`skill-improve/collect.py` の `output_is_git_ignored` を fail-closed 改善**（TDD）。`git check-ignore` の exit 0/1/その他を
  区別し、undecidable（git 自体が実行不能）のとき stderr に `GIT_CONFIG_GLOBAL=/dev/null` 再実行を促すヒントを出す
  （fail-closed は維持）
- **testcase-design.md の高エントロピー screen を機械判定化**: `[A-Za-z0-9+/=_-]{20,}` かつ数字・英大文字・英小文字の
  3 種混在のトークンのみを高エントロピーとみなす（`migrate-cycles-to-plans` 等の小文字ハイフン長スキル名を誤検出しない）

## 1.29.0

`trigger-eval` スキルを新規追加。スキルセットの description 発火精度（recall / precision /
stability / 80-way confusion matrix）を description-only の判定 subagent で機械的に実測し、
衝突ペアを特定して description 改稿→再評価ループを収束まで回すメタスキル。`empirical-prompt-tuning`
（本文実行の質）に対し選択層（description→発火）を測る姉妹スキル。

- 静的衝突プレパス（`static_collisions.py` の語彙 Jaccard、LLM 不使用）+ Tier 1 選択シミュレーション
  （sonnet 判定 subagent、バッチ ≤20・並行 dispatch）+ Tier 2 E2E 実発火検証（使い捨て git worktree・
  6 セッション上限）の静的プレパス + 2 層評価
- 純関数 `collect_descriptions.py` / `static_collisions.py` / `aggregate_metrics.py` を unittest で検証
  （エージェントは JSON 生成・受け渡しのみ）。references に judge-protocol / testcase-design / metrics-spec
- 事前固定原則 + holdout 採用ゲート + 悪化ガード（max_iterations=5）で過適合と description 盛りを機械的に防ぐ
- `skill-improve/collect.py` に opt-in `--capture-prompts` を追加（マスク済みプロンプト本文を JSONL 出力。
  出力は git-ignored な `cwd/.claude/tmp` 配下に機械制限＝fail-closed）。秘匿マスクを `[REDACTED:kind]` の
  完全マスクに変更し、email / ホームパス / ghp_・github_pat_・xoxb-・sk-・sk-ant-・AIza 等の既知プレフィックス
  トークン（引用符の有無・sk-proj- 等のダッシュ入り・3-part JWT 署名も含む）を検出するよう強化
- CI（`validate.yml`）に trigger-eval / skill-improve scripts の unittest discover ステップを 2 つ追加
- skills-first 方針により command なし。初版は Claude 版のみ

## 1.28.1

`refactor` スキルの empirical prompt tuning（白紙実行者による4イテレーション評価、
3シナリオ + hold-out 1、全12+4ラン成功・精度100%維持）で検出した曖昧箇所を明文化。
挙動の変更なし、判定文言の精度向上のみ。

- `no_verification_means` を除外理由の語彙に追加（検証手段そのものが不在のケース）
- Phase 6 冒頭にレポート形式選択規則を明文化（簡略版は「変更ゼロ かつ 提示項目ゼロ」のときのみ）
- セクション帰属規則を追加（§5 は CONFIRMED + opt-in 待ち専用、複数理由該当は UNCERTAIN を §4 優先、
  重複掲載禁止）
- headless の定義を明文化（ユーザへの確認・質問に応答が得られない文脈全般）
- characterization test / probe は headless Gate で常に同じ扱いであることを明記
- no-op 時のテスト実行は必須ではない（読み取り目的の1回実行は妨げない）ことを明記
- Phase 0 にテストファイルの扱いを追加（スコープ展開に含まれても改善対象ではなく検証手段）
- refactoring-catalog: 兆候列の数値は目安であり足切り条件ではないことを明記

## 1.28.0

新スキル `refactor` を追加。実装完了後のコードを**動作を完全に維持したまま**リファクタリングし、
コードベース全体の類似コードへ文脈検証つきで横展開する。sweep-fix が「問題（バグ）起点の
find-one-fix-all」なのに対し、refactor は「動作保持の表現改善」起点。

- **7フェーズ構成**: SCOPE（スコープ解釈・安全上限 50 ファイル・一時コード除外）→
  UNDERSTAND（Chesterton's Fence + 検証手段の確保。テスト/型検査/probe のない箇所は APPLY しない）→
  IDENTIFY（4値分類 REFACTOR_CANDIDATE / BUG_FOUND / OUT_OF_SCOPE / ALREADY_CLEAN、no-op Gate、
  performance Gate）→ SWEEP（similarity-ts/rs / ast-grep / Grep を役割別に使い分け、存在確認 +
  フォールバック、範囲限定）→ VERIFY（3値判定 ★品質の要）→ APPLY（origin は APPLY、
  スコープ外 sweep_candidates は opt-in、1改善ずつ最大10件、Rule of 500）→ REPORT
- **Iron Laws**: 動作完全維持 / Chesterton's Fence / バグは直さず issue 化案を提示 /
  既にきれいなら no-op / 迷ったら直さない（証明手段なしは APPLY 不可）
- **検証観点は自前で持つ**: sweep-fix の context-verification.md は「同じ**バグ**が成立するか」を
  問う設計で、動作保持検証（「同じ**変換**を動作保持で適用できるか」）とは問いが逆向きのため流用せず、
  refactor 固有の `references/behavior-preservation-checks.md` を新設。3値判定の**定義**は
  共有契約 severity-and-verdicts.md に準拠
- **references**: `refactoring-catalog.md`（改善パターン C1-C12 + 過度な単純化の罠 +
  「新しいチームメンバー」テスト）、`similarity-detection.md`（ツール役割別使い分け +
  存在確認・言語カバレッジ非対称性・フォールバック）、`behavior-preservation-checks.md`
  （動作保持の6観点チェックリスト + 判定例）
- **バグ修正はしない**: 発見した `BUG_FOUND` は修正せず REPORT で `issue` スキルの起動コマンド案
  （タイトル・本文の下書き付き）として提示。refactor 実行中は docs/issues を書き換えない
- **skills-first 方針**: command なし（`/claude-skills:refactor` で直接起動）
- **初版は Claude 版のみ**: sweep-fix と同じ戦略で、Codex 版は需要を見てから codex-sync で移植予定
  （`codex-skills/` / `AGENTS.md` / `sync-manifest.json` は変更なし）

## 1.27.1

sweep-fix を empirical prompt tuning（白紙エージェント10実行 + hold-out 過適合チェック、
全実行で要件精度 100%）で検証し、実行者の申告に基づく曖昧箇所を明文化。

- **早期終了パスの仕様明文化**: 中間ディレクトリ `.claude/tmp/sweep-fix/` の作成を
  Phase 0 から「最初にファイルを保存する時点（Phase 1 の問題リスト保存）」に遅延。
  問題ゼロ終了時は中間ファイル未作成（作成済みなら削除）+ 簡略版レポート +
  「変更なしのため検証対象なし」（テスト実行不要）を明記
- **severity 境界の倒し方**: BLOCK/WARN の境界事例は高い方に倒して根拠を1行記録。
  重大度は修正フローを変えない（Phase 4 続行確認の発火条件のみ）ため境界判定に
  時間をかけない旨を Phase 1 に追記
- **判定例の注記**: context-verification.md の判定例の重大度ラベルが例示である旨を
  明記（境界の倒し方は SKILL.md Phase 1 の規定に従う）

## 1.27.0

新スキル `sweep-fix` を追加。指定範囲で見つけた問題をコードベース全体へ横展開して
一括修正する find-one-fix-all 型ワークフロー。

- **6フェーズ構成**: SCOPE（範囲確定）→ ANALYZE（問題検出、severity-and-verdicts 準拠）→
  SWEEP（パターン化 + 横展開検索。Grep / ast-grep / LSP を使い分け、存在確認 +
  Grep フォールバック付き。問題複数時は並行ファンアウト + `.claude/tmp/sweep-fix/` マージ、
  `model: opus` 明示）→ VERIFY（文脈検証）→ FIX（verification-gate 準拠）→ REPORT
- **偽陽性対策を独立フェーズとして強制**: 候補を CONFIRMED / FALSE_POSITIVE / UNCERTAIN の
  3値判定にし、判定根拠の記録を必須化。UNCERTAIN → CONFIRMED への昇格を禁止する
  fail-safe（迷ったら直さない）。「検索は広く、修正は狭く」で偽陰性対策（検索段階）と
  偽陽性対策（検証段階）の責務を分離
- **references**: `context-verification.md`（判定チェックリスト5項目 + 判定例）、
  `pattern-extraction.md`（問題→検索シグネチャ変換ガイド + アンチパターン）
- **skills-first 方針の初適用**: 新規スキルとして初めて command なしで追加
  （`/claude-skills:sweep-fix` で直接起動）。Codex 版は需要を見てから codex-sync で移植予定

## 1.26.0

サブエージェントのモデル階層（Model Tiering）を導入。高額モデル（Fable 等）の
セッションからスキルを起動しても、配下のエージェントが高額モデルを継承して
コストが暴発する事故を構造的に防止する。

- **共通契約**: `orchestration-patterns.md` に「モデル階層」セクションを新設。
  原則4つ（レバレッジ / 検証ゲートで守られたフェーズは安くできる / ゲートのない
  レビュー・発見系は安くしない / model 明示の第一目的は高額モデルの継承防止）と
  標準マッピング表を定義。fork は model 指定を無視する点、Codex エージェントは
  対象外である点も明記
- **model 指定の追加**: cycle（refine/修正/実装 = opus）、plan-reviewer（7観点 = opus）、
  codebase-review（4体+統合 = opus）、attack-review（6体+統合 = opus）、
  iterate（実装は Small=sonnet / Large=opus のサイズ連動、レビュー = opus）、
  parallel-cycle（分解 = セッションモデル、plan 生成 = sonnet、cycle 実行 = opus）、
  team-config（メンバー spawn = opus、Lead = セッションモデル）
- **attack-review の fable 禁止**: Fable のサイバーセキュリティ分類器は正当な防御
  目的のレビューでも refusal を返しうるため、コスト以前に成果物が壊れる旨を明記
- **Codex 版6ペア**: model パラメータは Claude の Agent tool 固有のため反映不要と
  判断し、同期台帳のみ更新

## 1.25.0

addyosmani/agent-skills の分析結果から良質なプラクティスを移植。

- **Codex バイアス制御**: `codex-integration.md` に「バイアス制御」セクションを新設。
  自分の結論・レビュー結果を Codex に渡さない（アンカリング防止）/ 敵対的フレーミング必須 /
  doubt theater 検出（2回連続全棄却・検証なし全採用の両方を Red Flag 化）。
  セキュリティ節の許可コンテキストから「レビュー結果」を外し、修正ループの再レビューのみ例外化
- **バリデータ強化（チェック11）**: SKILL.md description のトリガー語
  （「〜で起動」/ "Use when" 等）と 1024 字上限を CI で機械検証。複数行
  `description: >` 対応の `extract_description()` を追加。免除リストはバリデータ側に配置
  （スキルファイル編集による検証迂回を防止）
- **description 修正**: トリガー語がなかった commit（Claude/Codex）・parallel-cycle
  （Claude/Codex）・cycle（Codex）の5スキルにトリガー語を追加
- **共有契約 orchestration-patterns.md 新設**: endorsed パターン7種（Agent 委譲 /
  並行ファンアウト+ファイルマージ / worktree 分離 / チーム議論 / セカンドオピニオン /
  polling ループ / リサーチ隔離）+ アンチパターン5種 + 判断フロー + カタログ追加ゲート
- **共有契約 skill-authoring.md 新設**: frontmatter 契約 / 執筆原則 / 合理化防止テーブルの
  書き方 / Codex 移植の注意 / 新規スキル追加チェックリストを集約したスキル執筆仕様

## 1.24.0

codex-sync による brainstorm / problem-solving の Codex 版移植。

- **Codex 版 brainstorm 追加**: `codex-skills/brainstorm/`（codex-sync port）。Codex セカンドオピニオン
  機構は自己レビューで冗長なため丸ごと削除しステップ番号を再整合。`request_user_input` ベースの
  対話ループは維持（壁打ちが本質のため headless 化しない）。wrap / plan のファイル生成は
  `apply_patch`、idea-template.md は symlink で共有
- **Codex 版 problem-solving 追加**: `codex-skills/problem-solving/`（codex-sync port）。
  5つの思考手法（simplify/collide/invert/scale/pattern）の内容は Claude 版と一字一句同一、
  ツール参照のみ変換（`request_user_input` / `shell` 読み取り専用 / `apply_patch` 禁止）
- **brainstorm Codex 版の誘導先を解消**: 行き詰まり検出の誘導ブロックが未移植の problem-solving を
  指していた REVIEW を、problem-solving 移植完了に伴い `$problem-solving` へ置換
- **ソース修正**: `skills/problem-solving/SKILL.md` の Dispatch 選択肢に残っていた UTF-8 破損
  （U+FFFD ×2）を「新しいアイデアが出ない」に修正
- **同期台帳**: 15 ペアに更新。AGENTS.md / README / CLAUDE.md に両スキルの Codex 版を追記

## 1.23.0

リポジトリ自己検証基盤と Claude⇔Codex 一元管理の導入。

- **CI バリデータ新設**: `scripts/validate_repo.py` + GitHub Actions で symlink 切れ /
  相対リンク切れ / frontmatter 欠落 / CLAUDE.md 対応表⇔commands/ の双方向一致 /
  README・AGENTS.md のスキル名カバレッジ / plugin.json⇔marketplace.json のバージョン同期を
  push / PR ごとに機械検証（純関数はユニットテストでカバー、TDD で作成）
- **Claude⇔Codex 同期台帳**: `codex-skills/sync-manifest.json` に sync 時点のソース sha256 を
  記録し、ソースだけ更新して Codex 版を忘れるサイレントドリフトを CI で検出（13ペア）
- **新スキル codex-sync**: Claude 版スキルを Codex 版へ自動移植（port）・差分同期（sync）・
  未同期一括処理（scan）するメタスキル。3層変換ルール（機械的置換 / 構造的変換 / 要判断）を
  適用し、第3層は人間にエスカレーション。validate → 台帳更新まで一気通貫
- **ドリフト修正**: commit Codex 版に v1.17.0 の Phase 1.5 (Best-Effort Test Verification) を
  移植（反映漏れ）。tool-mapping.md を AGENTS.md が示す codex-skills/shared/references/ へ移動
- **ドキュメント追従**: README / AGENTS.md に未記載だった attack-review・design 系・
  mockup-diff・tdd・debug・problem-solving 等を追記。リリースノートを plugin.json から
  本ファイルに分離。marketplace.json のバージョン同期

## 1.22.0

brainstorm skill empirically tuned (4 iterations, dispatch-based evaluation). Session Workflow: step numbering fixed (a2 → b with cascaded rename of sub-steps b→c→d→e→f→g, loop-exit step 4→5), stuck-hint placement locked to response body head (hint → normal answer → Codex section order), Codex prompt `{summary}` first-turn handling specified (`（最初のターン、履歴なし）`), Codex failure conditions expanded (Agent tool unavailable / timeout / empty response all explicit). Plan Workflow: Title/Summary provenance declared (kebab-title from idea-status link text, Summary from `## Summary` section), plan-create output path documented (`docs/plans/{new_timestamp}_{kebab-title}.md`), Step 5/6 reordered to move-first then status-update in archives/, Step 4.5 Skip Step 7 made explicit (cycle produces own completion log). Resume Workflow cross-reference corrected (steps 2-3f → 4a-4g). Mojibake (U+FFFD replacement chars in simplify-invert bullet) removed.

## 1.21.0

Codex CLI edition of handoff skill added under codex-skills/handoff/. Same save/restore/list workflows as the Claude Code version, rewritten for Codex native tools (apply_patch for file creation, shell for cat/rm/date/git, send_message for user output). Headless end-to-end: no request_user_input, no shell redirects for file writes. Handoff skill itself was empirically tuned (3 iterations, dispatch-based evaluation) before porting: status vocabulary locked to 3 values, absolute-path example fixed, restore summary templated, list extraction rules specified, git-less fallback (branch: (none)) added. Both editions share identical frontmatter structure so handoff files are cross-compatible.

## 1.20.0

New mockup-diff skill: visual diff detection between approved mockup HTML and running app. Phase 0 SETUP auto-generates a tailored Playwright comparison script per project (Tauri, Next.js, Vite, etc.) instead of hardcoded framework-specific logic. Captures screenshots of both mockup and app, enables LLM-driven visual comparison, diff analysis, code fix, and verification loop. Complements design-validate (token compliance) as the last-mile implementation quality gate.

## 1.19.0

Mockup Workflow v2: schema-based mockup generation with auto-lint (DL001-204) and Base Design approval gate. Feedback loop for iterating tokens/catalog/page-schema until human approval, then all subsequent validation is mechanical. Baseline confirmed via approval.json + screenshots.

## 1.18.0

Design-guide v2: mechanical verification for design systems. 5 new skills: design-scaffold (DESIGN.md → tokens.json + tokens.css + catalog + pages + layout-rules + rubric), design-generate (constrained page generation from page-defs + catalog), design-validate (multi-stage gate: lint → visual regression → rubric judge with weighted scoring), design-lint (14 rules: DL001-006 tokens, DL101-103 components, DL201-204 pages). Human-in-the-Loop Once: single base design approval → all subsequent validation is mechanical. Shared design-system-contract.md.

## 1.17.0

New TDD, systematic-debugging, and problem-solving skills. TDD contract and verification gate shared references injected into cycle/iterate/commit. Testing anti-patterns rule for project-wide enforcement. Brainstorm now detects stuck keywords and suggests problem-solving tools. Skill-improve gains pressure-test analysis and guardrail-strengthening category.

## 1.16.0

New design-guide skill: interactive discovery-driven DESIGN.md generator. Binary-choice questions to structure vague design vision into concrete design tokens (Google Stitch format). Anti-pattern guardrails to avoid generic AI aesthetics. Session (create), Update (modify), and Mockup (token-strict HTML/React mockup generation) workflows.

## 1.15.0

New attack-review skill: attacker-perspective security review with 6 specialist agents + Codex. Risk-matrix-based threat classification (not scores). Server/client/full mode with auto-detection. Language-adaptive attack profiles (TS/JS, Python, Go, Rust, Dart, PHP, HTML/CSS). Shared language detection contract (lang-detect.md) for cross-skill reuse.

## 1.14.1

Phase 2.5 code review follow-ups for github-issue Polling Phase B: SKILL.md Polling Step 11 now explicitly references increment_retry + should_promote_to_permanent; TickResult schema lists all 7 fields per shared contract §7; list_ready early-termination guarantee documented; retry_count / last_failed_at / run_id validation spec tightened; polling_interval vs tick_interval_loop_mode clarified. README refreshed to cover github-issue / handoff / polling commands and workflow quirks.

## 1.14.0

github-issue Polling Contract Unification (Phase B): Label adapter refactor to conform with shared polling-pattern.md contract. Split `claude-failed` into `claude-failed-transient` / `claude-failed-permanent` with backward-compatible dual-write alias. Atomic dual-write + verification + recovery marker. FS retry state replaces GitHub comment state. WARNING: Downgrade to 1.13.x is NOT supported — issues tagged with the new labels become invisible to older readers, causing silent data loss. Alias `claude-failed` will be removed in 1.16.0 (advance notice in 1.15.0).

## 1.13.x 以前

記録なし（releaseNotes の運用開始は 1.14.0 から）。
