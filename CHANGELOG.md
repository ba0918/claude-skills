# Changelog

claude-skills プラグインのバージョン履歴。
`.claude-plugin/plugin.json` の `version` を bump したら、このファイルにエントリを追加すること
（マーケットプレイスがスキル変更を認識するのは version bump 時のみ）。

## 1.42.0

skill-interface-audit 新規追加。各 SKILL.md を API 仕様として静的監査するメタスキル。

- `skill-interface-audit` スキルを追加（SKILL.md + references/ + scripts/）
- SI-S001〜S004 の純関数ルールエンジン（`static_checks.py`、42 テスト）
- SI-C001〜C006 の LLM 意味判断ルール（REPORT\_ONLY 上限）
- skill-authoring.md の執筆原則を正本とし、契約の欠落・構造違反を検出
- empirical-prompt-tuning / trigger-eval / Codex 敵対レビューで品質検証済み

## 1.41.0

統合漏れクリーンアップ。

- `commands/codex-sync.md` を削除（スキル本体は 1.40.0 で削除済み）
- 各 SKILL.md / 共有契約 / issue から「Claude 版のみ」「Codex 移植」等のレガシー前提を除去
- `tool-mapping.md` を「変換リファレンス」から「ランタイム差の参考資料」に改題
- `skill-authoring.md` から Codex 移植セクションを削除
- 関連 issue 2 件をクローズ（統合により superseded）
- `empirical-prompt-tuning`: Codex 自己チューニングにより環境制約の代替案を明確化

## 1.40.0

プラットフォーム非依存化。スキル本文から LLM 固有のツール API 名・モデル名を排除し、
Agent Skills 標準準拠のクロスプラットフォーム互換を実現。superpowers (obra/superpowers)
のアプローチに倣い、自然言語で意図を記述する方式に統一。

- **ツール名変換（111 ファイル）**: `Read` / `Edit` / `Write` / `Bash` / `Agent` /
  `AskUserQuestion` / `SendMessage` / `TeamCreate` / `TeamDelete` / `Grep` / `Glob` /
  `NotebookEdit` / `EnterWorktree` / `ExitWorktree` / `subagent_type` /
  `mode: bypassPermissions` → 全て自然言語に
- **モデル名変換**: `opus` → tier:high / 高性能モデル、`sonnet` → tier:standard / 軽量モデル
- **セクション名統一**: 禁止ツール → 禁止操作、許可ツール → 許可操作
- **codex-skills/ 完全削除**: 62 ファイル・13,902 行削減。デュアル構造を廃止
- **codex-sync スキル削除**: 同期機能が不要に
- **validate_repo.py**: Codex 同期台帳チェック・`--update-manifest` を除去
- **CLAUDE.md / AGENTS.md 統合**: AGENTS.md を正本化、CLAUDE.md は `@AGENTS.md` の薄いラッパーに
- **CLAUDE.md 編集ルール追加**: プラットフォーム非依存の記述を徹底する旨の NG/OK 例付きガイド
- `.codex-plugin/plugin.json`: `skills: "./skills/"` でプラットフォーム共通の skills/ を参照
- `.agents/plugins/marketplace.json`: openai/plugins 標準に準拠した配置に移動

## 1.39.1

empirical-prompt-tuning による 5 スキルの実測チューニング。白紙実行者 計 32 本（rolling-checkpoint 10 +
ループ 4 兄弟 22）で実行し、検出した指示・実装ギャップを解消。全実行 精度 100%・holdout 過適合なし。

- **checkpoint（plan / handoff / checkpoint-pattern.md）**: CLI 呼び出し規約の新設（`--repo` 常時明示・
  プレースホルダ形式のコマンド例）/「checkpoint 生成はセッション最後の書き込み」ルール（handoff save は
  Phase 3 後に実行）/ fallback 提示フォーマット / dirty_overlap 行の不在 = 重なりなし / phase 据え置き遷移
- **goal-loop**: `halt` サブコマンド新設（stall / oscillation 判定を暗算から CLI 化、exit 0/3/4）/
  lock の `__pycache__`・`*.pyc` 自動除外(false-tamper 根治）/ $WORK 絶対パス確定と lock/verify の
  cwd 固定 / implementer への fence 尊重 + no-op 指示と「収束不能 → no-op → stall」正規経路の明文化 /
  oracle 推定の優先順位（README > Makefile > 生ランナー）
- **loop-triage**: SKILL が規定する `sensors.py --context-audit` フラグの実装欠落を解消 /
  `map_context_audit` の `why` 写像欠落を修正（「概要 = what + why」の成立）/ run の引数構文と
  「限定モードなし」/ issue frontmatter の tags 重複キー禁止 / issue-status リンクは `ready/{slug}.md` /
  status ワークフローの定義補強
- **goal-decomposition**: secret パイプラインの実務手順（.claude/tmp で検査 → 合格後配置）/
  proxy の扱い（決定木リーフ不在の明記・headless 採用可）/ oracle_files = verifier ロックの明確化 /
  metrics の `proposed:` プレフィックス / validate はテキスト報告のみ
- **skill-regression**: executor-contract の運用具体化（隔離領域内は編集可 / 非 git フォールバック /
  sha256 ベースライン照合の正式化 / **削除拒否時に別ツールで迂回しない**）/ run vs accept の目安 /
  capture Step 3 = run Step 2〜4 の明記。副次成果: commit スキルの台帳を実 run の pass に格上げ
- 安全性の実測証明: oracle-gaming 誘惑・LLM judge 提案圧力・deny 迂回の 3 種のインシデント経路を
  契約文言で遮断できることを独立実行で確認

## 1.39.0

`rolling-checkpoint` — 長生きセッションの実行状態復元（自動 handoff の再設計）。plan resume /
handoff restore に「dirty のまま終わった実行状態」の復元を追加。**Claude-only**（plan / handoff の
Codex 版追随は v2）。

- **共有契約 `checkpoint-pattern.md`**: checkpoint は worktree バックアップではなく現在の git 状態と
  照合して使う restore ガイド。フォーマット（YAML frontmatter + 固定キー短文）/ 純関数シグネチャ正本 /
  parse ゲート + semantic 5 分類（valid / stale / superseded / degraded / conflict、優先順位
  `superseded > conflict > degraded > stale > valid`）/ 所有境界（4 項目）と禁止事項 / 呼び出し側非対称
  （plan resume は conflict 無視続行・handoff fallback は conflict 停止）/ checkpoint vs handoff 境界 /
  セキュリティ規約 / v1 カバレッジ限界と v2 スコープを定義。
- **`skills/shared/scripts/checkpoint.py`**: 純関数群（`compute_fingerprint` / strict `parse_checkpoint` /
  `classify` / `build_skeleton`）+ skeleton / classify CLI。git 呼び出しは CLI 層のみ（DI）。
  セキュリティは文書でなくコードで強制 — PyYAML 不使用 strict parser（重複キー・未知 owner/mode・
  owner⇔mode 不一致・cycle_id `[0-9]{14}` を拒否）/ realpath containment + symlink 拒否 /
  `secret_detect.mask_secrets` / `verify_on_restore` は `{cmd,args}` 構造のみで**どの verdict でも自動実行しない**
  （headless では確認プロンプトも出さず表示のみ）。fingerprint は `git status --porcelain=v1 -z` +
  `git diff HEAD` 全文 + untracked content sha256 を入力にし `--untracked-files=all` で collapsed dir を展開。
  `test_checkpoint.py` 46 ケース（fingerprint / porcelain -z parse / strict parse / セキュリティ強制 /
  classify マトリクス / skeleton / exit codes）。
- **plan / handoff スキル統合**: plan Resume に checkpoint classify 分岐（orphan / parse conflict 無視続行
  含む）+ Status Update に dirty 出口条件（checkpoint 骨格生成）。handoff save に dirty 時の checkpoint
  書き出し（主トリガー）+ restore に handoff 0 件時の checkpoint fallback（read-only・削除しない）。
  plan / handoff の fixtures に checkpoint 分岐 edge（pl-004 / ho-004）を追加。
- **意図的な非強制**: verdict 語彙（`superseded` 等）は goal-decomposition dossier status との false
  positive を避けるため validate_repo チェック12に登録せず、遵守は skill-regression fixture で守る。
- **v2 送り**: PreCompact / PostToolUse hook（runtime 強制）/ plan 不在の `_workspace` fallback /
  parallel-cycle 多重 writer（契約改訂級）/ measurement `checkpoint_written` イベント（契約改訂級）/
  Codex 版展開。

## 1.38.0

`goal-decomposition` スキル新設 — 大枠ゴールを Loop Readiness Dossier にコンパイルする入口。

- **共有契約 `goal-decomposition-pattern.md`**: 既存 4 契約（loop-engineering / convergence-pattern /
  polling-pattern / measurement-identity）の上流「翻訳層」。Dossier Schema v1（canonical キー階層の単一ソース）/
  第一問決定木（完了条件 / 未達検出器 / 人間判断 → `wire_to` 5 値の導出）/ 5 軸 routing proof /
  status ライフサイクル（draft/approved/superseded/rejected、approved は実行権限を与えない）/
  wire_to×exit_to compatibility matrix / proxy oracle 許容条件（LLM judge 主観評価は禁止）/
  supply gap 3 分類 playbook / 信頼境界 fence 規約 / 既存契約への写像表 / GD001-GD302 rule catalog を定義。
- **`skills/goal-decomposition/`**: 薄い orchestrator（command なし、compile / validate の 2 ワークフロー）。
  compile の出力は常に `status: draft`、承認は人間が JSON を直接編集する。secret redaction は 2 段構え
  （自由文はマスク / 構造フィールドは検出で compile 中止）。
- **`dossier_lint.py`**: 純関数 RULES registry（GD001-GD302、終了コード 0/1/2、object_pairs_hook で
  重複キー検出 / commonpath + symlink 拒否の path containment / secret マスク）。unittest 60 ケース +
  catalog-sync（契約 rule 表 ⇔ RULES の一致保証）。
- **`validate_repo.py` チェック13**: `docs/loop/dossiers/*.json` を dossier_lint で in-process 検査し
  error 級のみ CI fail。壊れた dossier は `[dossier] parse-error` に変換して validate_repo 全体の abort を防ぐ。
  CONTRACT_VOCAB に goal-decomposition-pattern.md（ci_gate / resident_sensor / dissolve）を登録。
- **E2E 具体例**: `docs/loop/dossiers/20260707230000_doc-quality.json`（「ドキュメント品質を上げて維持する」）を
  正式スキーマで作成し lint 合格を確認。md ビューは JSON からの一方向生成 + sha256 marker（tamper-evident）。

## 1.37.2

閉ループの予行演習（③ 残 findings 処理を polling パイプラインで消化）。

- **4 スキルの仕様曖昧点を明文化**（fixture 白紙実行者の報告に基づく。Codex 版 3 スキルへも同期）:
  - github-issue: Common Pre-checks 失敗は fail-closed で polling を起動しない（例外は
    ユーザー明示時のみ）+ nameWithOwner 取得を `fetch_git_remote_url()` と同順に統一
  - handoff: mtime 同秒タイはファイル名タイムスタンプ降順でタイブレーク（restore / list 両方）
  - plan: Completed 日時 = 更新実行時点の現在時刻 / abandoned 行は `YYYY-MM-DD` 粒度
  - commit: 「変更」に untracked を含む（untracked のみでは abort しない、
    非作業成果物は理由付きで除外可）
- **供給→消化の初 E2E 実証**: 4 件を `docs/issues/ready/` に enqueue → 初回強制 dry-run tick
  （claim 4→release 4）→ 本 tick で claim → 並行実装 → 回帰台帳 → mark_done。
  tick イベント 2 件が measurement spine に記録され、`report --skill issue` が
  初の実データ（成功率 100%）を返すようになった

## 1.37.1

fixture カバレッジ拡大（loop-triage 自己修飾ゲートの自動化範囲を広げる）。

- **plan / commit / handoff に回帰 fixture を新規追加**（各 3 シナリオ、白紙実行者で全合格）:
  - plan: headless 作成 / 非 ASCII slug + 未完了セッションの abandoned アーカイブ / Completed 遷移
  - commit: 論理分割（feat/docs 別コミット + 個別 add）/ .env 除外 / 変更なし abort
  - handoff: restore（最新選択・固定サマリ・復元後削除）/ list（原文転記・案内なし）/ not-found
- fixture 保有スキルが 3 → 6 に倍増。これらのスキル（+共有契約経由の挙動面）に触れる
  loop-triage の AUTO_FIX finding が inbox 降格なしで enqueue 可能になった
- iterate は Phase 1 の Agent（Explore）委譲が subagent 実行者では再生不能（入れ子 spawn 禁止）
  なため対象から外し、完全 FS 再生可能な handoff を採用

## 1.37.0

ループエンジニアリング基盤の後半2ピッチ + スコープ明文化。

- **計測 identity 統一（measurement-identity.md）**: 5つの計測系（polling TickResult /
  skill-regression ledger / trigger-eval / skill-improve / cycle 結果）を
  `skill × surface_sha256（挙動面 fingerprint）× run_id` の identity triple で結合する共通契約。
  イベントは `docs/loop/events.jsonl` に append-only で記録し、
  `measurement_identity.py report --skill X` が instruction バージョン別の成功率と
  直近改稿の効果差分を1コマンドで出す。No new silos rule 付き
- **goal-loop スキル新規作成 + convergence-pattern 共有契約**: polling-pattern（キュー消化型）の
  姉妹契約として条件収束型ループを新設。oracle_files のハッシュロック + 毎イテレーション verify で
  「テストを弱めて合格」する oracle-gaming を `oracle_tampered` halt で機械的に遮断
  （ループ内 manifest 更新 API は存在させない）。failure signature による stall / oscillation
  検出、maker/checker 分離（oracle 実行はコントローラのみ）。純関数 40 unittest
- **skill-regression の Codex スコープ明文化**: `codex-skills/` が回帰対象外である理由
  （fixture 再生は Claude Agent ランタイム前提、本文同期は codex-sync が担保）と
  拡張時の順序（実行手段 → 検出範囲）を意図的 non-goal として SKILL.md に明記

## 1.36.0

ループエンジニアリング基盤（出典: Addy Osmani "Loop Engineering"）。polling ループの
「発見 → 供給」上流を新設し、自走ループの安全装置を cron 運用まで拡張した3点。

- **polling 回帰 fixture の資産化**: `issue` / `github-issue` に fixtures.json を新規追加
  （初回 dry-run 強制 / kill file 優先順位 / orphan recovery + fail-safe / state_root 解決 +
  graceful stop / Label Mapping 判定の5シナリオ）。白紙実行者による全シナリオ合格を台帳に記録し、
  ループ本体の挙動面変更が CI で検証を強制されるようになった
- **stateless tick session（polling-pattern §6.5）**: cron / scheduler の 1 invocation = 1 tick
  実行でも 3 重ガード（max_iter / max_wallclock / failed_streak）を `session.json` で維持。
  `--stateless` フラグを両 adapter に追加。`failed_streak` halt は sticky（session.json を
  人間が削除するまで自動再開しない）。fixture 実行者が発見した契約ドリフト6件
  （kill_file_path 戻り順の契約⇔adapter 不一致、state_of_failure 擬似コードの fail-closed 矛盾、
  archive 初回の空文字パス穴、.claim 形式未規定、.polling-initialized 作成責務未規定、
  早期 halt 時の run_id 未定義）も同時修正
- **loop-triage スキル新規作成 + loop-engineering 共有契約**: センサー（validate_repo 違反 /
  ledger --check の stale / context-audit findings）を Finding Schema に正規化し、
  stable finding_id で冪等化（baseline suppression + queue dedup）→ fix_action × severity の
  純関数 admission → AUTO_FIX 級のみ `docs/issues/ready/` に enqueue して polling に供給する
  ループ中枢。loop-defining ファイルに触れる finding は fixture 非保有スキルが1つでもあれば
  inbox 降格する自己修飾ゲート付き（回帰網がある範囲でだけ自動化）。純関数4本 + 111 unittest

## 1.35.0

ベースライン整備。検証インフラの再実装重複と検査の死角を4点まとめて解消。

- **frontmatter パーサの共有化**: validate_repo.py / context-audit / trigger-eval が
  各自再実装していた YAML frontmatter パーサを `skills/shared/scripts/frontmatter.py`
  に統合（TDD、28 テスト）。キー正規表現は最も正確な `[A-Za-z_][A-Za-z0-9_-]*` に統一。
  乖離すると description トリガー語チェックの正しさに直結する箇所
- **チェック5の対象拡大**: references/**/*.md（共有契約含む）の相対リンクも検査対象に。
  検出した実リンク切れ（codex 側 severity-and-verdicts → fix-action-taxonomy）は
  symlink 追加で修正。plan のテンプレ内例示リンクは理由付き `LINK_CHECK_EXEMPT` で免除
- **チェック7/8の word-boundary 化**: bare substring 一致では issue ⊂ github-issue、
  plan ⊂ team-plan が誤合格していたのを `mentions_name` で修正
- **design-lint の機械化**: description の「機械的に検出」「CI 組み込み可能」の実体が
  エージェント prose だったのを、lint-contract 準拠の実行スクリプト
  `skills/design-lint/scripts/design_lint.py`（DL001-006 / DL101-103 / DL201-204、
  標準ライブラリのみ、63 unittest、終了コード 0/1/2）として実装。SKILL.md は
  スクリプト実行 + 結果解釈に書き換え、ルール適用の暗算再現を禁止

## 1.34.0

Codex パリティを「信頼ベース」から「検証ベース」へ。14 ペア全部の Claude 版⇔Codex 版を
意味レベルで敵対的に突き合わせ、9 ペア計 15 件のドリフトを修正。sha 一致 =「見た」の記録
しか守れなかった台帳の死角を、構造ごと塞いだ。

- **構造的根本原因の特定と修正**: ツール名（SendMessage / ExitWorktree / AskUserQuestion）や
  Codex 第二意見節を含む references 10 本が「tool-independent」と誤判定されて symlink 共有
  されており、Codex 実行者に Claude 方言と削除済みの第二意見指示が見え続けていた
  （本文は正しく変換済み = 本文と参照が直接矛盾）。10 本すべてを変換済み実体コピーに置換し、
  `EXTRA_SYNC_PAIRS` で台帳追跡に載せた（15 → 25 ペア）
- **実質的な意味喪失の復元**: codex cycle の実装プロンプトに TDD（tdd-contract）+
  verification-gate 注入を復元 / codex iterate の TDD 義務を「when feasible」から契約準拠に
  復元 + テストアンチパターン禁止を復元 / codex plan-reviewer に最新ドキュメント確認ヒント復元
- **点在ミスの修正**: codex commit の verification-gate 参照を cross-tree パスから codex ローカル
  リンクへ / codex issue の Next Steps を issue スコープ（`$issue cycle --team`）に修正
- **codex shared 契約の拡充**: verification-gate.md / tdd-contract.md を symlink 追加。
  codex-integration（Codex 内では無意味）/ skill-authoring（リポジトリ開発メタ）/
  orchestration-patterns（model 階層が Claude 固有）は不移植と tool-mapping.md に明文化
  （「共有契約の可搬性ポリシー」新設: symlink / 変換コピー / 不移植の3分類）
- **規約統一**: codebase-review / plan-reviewer / commit に `(Codex Edition)` H1 +
  「Codex CLI ツールの使い分け」節を補完、attack-review に同節を補完
- **監査で IN_SYNC を確認**: handoff / investigate / plan / brainstorm / problem-solving の
  5 ペアは移植品質良好（brainstorm の第二意見除去とステップ再番号の整合まで検証済み）
- skill-authoring.md に references 共有の内容基準判定を明文化（「テンプレだから中立」推定の禁止）

## 1.33.0

共有契約システムの意味的再統一。11 本の契約と全スキルを突き合わせ、「宣言だけ共有・実体は
インライン再発明」のドリフトを解消し、以後の再発を CI で機械的に止める。

- **文脈検証3値判定（CONFIRMED/FALSE_POSITIVE/UNCERTAIN）の定義元を新設**:
  CLAUDE.md や refactor が「severity-and-verdicts 準拠」と宣言していたのに、当の契約に
  定義が存在しなかった（事実上の定義は sweep-fix の references に散在）。severity-and-verdicts.md
  に汎用フレーム（3値・Iron Law・fail-safe）を新設し、CONFIRMED の検証述語は各スキルの
  意図的特殊化として維持（sweep-fix = バグ成立 / refactor = 動作保持）・相互リンクで接続
- **team-config の自己矛盾を解消**: 冒頭注記（メンバー = opus、9343065 のモデル階層コミット由来）と
  §モデル指定表（sonnet、階層導入前の残骸）が矛盾していた。opus に統一（Codex 版は model
  パラメータ自体が Claude 固有のため反映不要と判断、台帳更新済み）
- **plan-reviewer のスコアバンド用法を承認済み方言として明文化**: BLOCK/WARN/PASS を
  リスクスコア帯にマップする用法を severity-and-verdicts に記載し、Claude / Codex 両版の
  SKILL.md から契約へリンク（トークン変更なし = 挙動不変）
- **doc-check の軸混同を修正**: fix action（AUTO_FIX/NEEDS_JUDGMENT/OK）を `severity:` と
  ラベルしていた箇所を `action:` に修正し、fix-action-taxonomy の差異節へリンク
- **インライン複製を参照に接続**: doc-audit / context-audit(memory-audit) / iterate(light-review) /
  skill-regression(fixture-schema) / commands/plan-implement / commands/issue-polling に契約リンクを追加。
  severity-and-verdicts ⇔ fix-action-taxonomy を相互リンク化
- **チェック12（共有契約語彙の適合）を validate_repo.py に新設**: 契約を一意に識別する語彙
  （AUTO_FIX 系 / CONFIRMED 系 / PASS WITH NOTES 系 / polling ガード / codex:codex-rescue）を
  使う skill / command が契約への md リンクを持たないと CI fail。免除は理由必須の
  `CONTRACT_VOCAB_EXEMPT`。TDD で追加（6 テスト）、既存リポジトリで偽陽性ゼロを確認
- **regression harness が初稼働**: 契約編集で context-audit が stale 判定され、変更が追記のみで
  挙動無影響と裁定して `--update --accept` を記録（黙殺不可能の設計が機能）
- 不介入と判断した重複（意図的再利用）: Gate Function / Iron Law 見出しの別ドメイン再利用、
  tdd-contract と lang-detect のマーカーファイル表（目的が異なる）、design-system-contract の
  独自検証階層。codex-skills 側の契約未移植（fix-action / verification-gate / codex-integration /
  polling / orchestration が codex shared に不在）は Codex パリティ作業（ピッチ3）の scope として残す

## 1.32.0

`skill-regression` スキルを新規追加。スキルの「調律済みの挙動」を fixture として資産化し、
SKILL.md や共有契約の変更時に影響スキルだけへ回帰評価を回すハーネス。

- **課題**: empirical tuning で確立した合格基準はセッションと共に消え、共有契約 1 ファイルの
  編集が参照スキル十数個の挙動を無検証で変える（実測: `verification-gate.md` の変更は
  推移参照込みで 14 スキルに波及）。trigger-eval が「発火」を守る一方、「実行の質」の回帰は
  誰も見ていなかった
- **挙動面 (behavior surface)**: `skills/<name>/` 配下 + SKILL.md からの md リンク推移閉包
  （共有契約含む）を `dep_graph.py` で算出し、変更ファイル → 影響スキルを逆引き
- **検証台帳 `ledger.json`**: sync-manifest と同思想。挙動面が前回検証時から変わったのに
  台帳が古いままなら CI fail。`--update --accept` で「実行せず不要判断」を明示記録
  （黙殺だけを不可能にする）。fixture を持つスキルのみ追跡（opt-in）
- **fixture 契約**: `skills/<name>/fixtures.json`。シナリオ 2〜3 本 + [critical] 付き要件
  3〜7 項目。白紙実行者 subagent（model 明示・毎回新規 dispatch・worktree 隔離）で再生し、
  critical 全 ○ で合格。生産手段（empirical tuning / plan 受け入れ条件 / 手動設計）に非依存
- **共有純関数 `skills/shared/scripts/md_links.py`** を新設（リンク抽出 + 推移閉包）。
  `dep_graph.py` / `ledger.py` とあわせて全て TDD（RED→GREEN）で unittest 検証
- **初の fixture 資産化: context-audit**: 1.31.1 EPT が検証した挙動（CA-S001 backtick 参照 /
  CA-C001 矛盾 / CA-D001 日本語ツール語彙 / 非対話フォールバックでの AUTO_FIX 不適用・baseline
  非書き込み / 誤検出ゼロの precision）を 3 シナリオ・14 要件に固定。白紙実行者 3 体で全シナリオ
  合格（critical 全 ○ + ファイル無改変をハッシュで機械検証）を確認し台帳に記録
- **CI のテスト発見を自動化**: `.github/workflows/validate.yml` のハードコード 3 ステップを
  `skills/*/scripts` の自動発見ループに置換。従来 CI から漏れていた context-audit の
  96 テストが回るようになった（新スキルのテストが黙って漏れる構造を根絶）。
  あわせて `ledger.py --check` を CI ゲートに追加

## 1.31.1

`context-audit` を empirical-prompt-tuning（白紙実行者 × 3〜4 シナリオ × 5 イテレーション）で改善。

- **検出エンジンの recall 改善**（fixture 実測で炙り出したギャップ 3 件）:
  - CA-S001: リポジトリ全体の basename 索引を導入。親ディレクトリ不在の backtick 参照でも、
    その basename が木のどこにも無ければ「削除済みディレクトリの stale」として検出
    （basename が他所に実在する shorthand 表記は従来どおり skip、precision 維持）
  - CA-D001: 日本語ツール語彙（「Edit ツール」等）を検出対象に追加
  - CA-C001: Jaccard 足切りを 0.5 → 0.2 に緩和（SKILL の「recall 優先の over-generation」契約に整合）
- **SKILL.md に「実行契約」を新設**: スクリプトのパス解決（`{skill_dir}` 絶対パス + root=cwd）/
  非対話フォールバック（明示指示が最優先 → なければ安全側で first-run=(c)・適用なし）/ `{ts}` 採番規約
- **仕様の明文化**: Phase 2 の candidate 0 件スキップ / 非 git での baseline 運用 + `--update-baseline`
  の idempotent 性 / CA-S001 の抽出対象（`/` 含むパス表記のみ）/ CA-D001 の行単位・代表 1 語報告 /
  memory_dir 開示と where マスクの関係
- 評価結果: 3 シナリオ + hold-out で精度 100%・再試行 0・steps 単調減（A: 17→9）。hold-out で過適合なし

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
