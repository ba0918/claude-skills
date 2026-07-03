# context-audit スキル新規作成

**Cycle ID:** `20260703190611`
**Started:** 2026-07-03 19:06:11
**Status:** 🟢 Complete

---

## 📝 What & Why

LLM 向け指示ファイル（CLAUDE.md / AGENTS.md / .claude/rules / プロジェクトメモリ）の老朽化・矛盾・有害指示・クロスツール乖離を監査する棚卸しスキル `context-audit` を新規作成する。長期運用で指示層が腐敗すると LLM の行動品質が劣化するが、既存の doc-check（docs⇔code）/ doc-audit（docs⇔docs）はこの「指示としての品質」を見ておらず、プロジェクトメモリはどのスキルの射程にも入っていない。

## 🎯 Goals

- **v1 = 純関数ルール中心の段階導入**: 機械検証可能なルール（参照実在 / frontmatter schema / ツール語彙混入 / カバレッジ差分 / unsafe 語彙）を Python 純関数 + unittest で実装し、LLM 判断（矛盾検出）は REPORT_ONLY に限定する
- **fix action 3値判定 + fail-safe**: AUTO_FIX（パス typo・実在ファイルへの置換・frontmatter 正規化のみ）/ NEEDS_JUDGMENT / REPORT_ONLY。**削除は絶対に自動でやらない**。迷ったら REPORT_ONLY に倒す。この 3値は **severity（BLOCK/WARN/INFO/PASS）とは直交する別軸の「fix action」** であり、taxonomy の出自は `doc-audit/references/checks.md`（詳細は Key Points 参照）
- **メモリ監査は cwd 対応プロジェクト限定**: `~/.claude/projects/{cwd-slug}/memory/` のみをデフォルト対象とし、全プロジェクト横断・グローバル設定（`~/.claude/CLAUDE.md` 等）は明示 opt-in フラグ（`--include-global`）指定時のみ。slug 解決は実 Claude Code 実装（`/` だけでなく `.`・`_` 等の非英数字も全て `-` に置換）に一致させ、reverse-verification + fail-safe skip を必須とする（Security 参照）
- **baseline suppression**: 意図的差分による誤検知を `.claude/context-audit-baseline.json` の suppression リストで抑制（v1 は finding ID ベースの単純リスト。finding ID の構成と stale 抑制リスクは baseline-format.md に明記。claim 正規化 hash + expiry は v2）。baseline はチーム共有目的で **commit 対象**（tmp とは別扱い）だが、**格納するのは opaque な finding ID のみ・検出値や本文は絶対に載せない**（v2 hash 形式でも不変）
- **skills-first**: command なし。Claude 版のみ（Codex 移植は v2 以降で判断。v1 は Claude 専用のため AGENTS.md 更新・codex-skills 同期は対象外 — validate_repo check 8 は codex-skills のみを対象とするため drift しない）

## 📐 Design

### アーキテクチャ（trigger-eval 踏襲）

「純関数は unittest で検証、エージェントは JSON の生成・受け渡しのみ」の構成。監査ロジックは Python スクリプトに集約し、SKILL.md はワークフロー制御・LLM 判断（contradiction の REPORT_ONLY 判定・NEEDS_JUDGMENT の提示）・AUTO_FIX の適用のみを担う。

### Files to Change

```
skills/context-audit/
  SKILL.md                          - メインワークフロー（Phase 0-4、下記参照）
  references/
    rule-catalog.md                 - CA-* ルール ID カタログ（全ルールの定義・severity・action・v1/v2 区分）
    memory-audit.md                 - メモリ監査の詳細（cwd-slug 解決 / type 別チェック / プライバシー制約）
    baseline-format.md              - baseline suppression の JSON schema と運用（--update-baseline）
  scripts/
    collect_targets.py              - 監査対象の発見・分類（path allowlist ベースの決定的分類、cwd→memory slug 解決 + reverse-verify）
    static_checks.py                - 純関数ルールエンジン（rule registry ディスパッチャ。各 CA-* ルールは pure fn として RULES に登録。findings JSON 出力。finding schema に fix_action(old→new) を含む）
    apply_fixes.py                  - AUTO_FIX 適用の純関数（findings + ファイル内容 → 新内容。パス置換 / frontmatter 正規化。body byte 不変・idempotent を保証）
    aggregate_report.py             - findings JSON + baseline → 最終レポート（suppression 適用 / severity 集計 / report skeleton 生成。action は static_checks.py 出力を尊重し再計算しない）
    secret_detect.py                - CA-M301 用。skill-improve の detect_secrets/mask_secrets/SECRET_PATTERNS を shared 化して再利用（新規正規表現をハンドロールしない）
    test_collect_targets.py         - unittest（scripts/ に co-locate。trigger-eval / skill-improve 慣習に一致）
    test_static_checks.py           - unittest
    test_apply_fixes.py             - unittest（AUTO_FIX 適用・idempotency・body 不変を検証）
    test_aggregate_report.py        - unittest
    test_catalog_sync.py            - unittest（rule-catalog.md の ID/severity/action と RULES registry の一致を検証、dual source of truth の drift 防止）

CLAUDE.md                           - 主要スキル表に context-audit を追加
README.md                           - スキル表・ファイル構成に追加
.gitignore                          - `.claude/tmp/context-audit/` は既存 `.claude/tmp` でカバー済み。baseline は commit するため追加しない（意図をコメントで明記）
skills/shared/references/           - fix-action taxonomy（AUTO_FIX/NEEDS_JUDGMENT/REPORT_ONLY）を doc-audit から抽出し共有化。secret 検出関数も shared 化
.claude-plugin/plugin.json          - バージョンバンプ（新スキル追加）
.claude-plugin/marketplace.json     - バージョン同期
CHANGELOG.md                        - エントリ追加
```

### SKILL.md ワークフロー（v1）

- **Phase 0: Discovery** — `collect_targets.py` で監査対象を **path allowlist（決定的・純関数）** で収集・分類。対象: リポジトリ内指示ファイル（root の CLAUDE.md / AGENTS.md、`.claude/rules/` / `rules/`、`.claude/review-rules.md`）+ cwd 対応プロジェクトメモリ。存在しない対象ディレクトリ（例: `.claude/rules/` 不在）は graceful-skip（エラーにしない）。ネストした CLAUDE.md/AGENTS.md（サブディレクトリ）は v1 対象外と明記。`docs/plans/`・`docs/ideas/`・`.claude/tmp/` 等の archival/一時領域は除外。各ファイルは `try/except` で個別読込し、非 UTF-8 / 読込失敗の 1 ファイルが監査全体を中断しないこと（errors='replace' or skip-and-report）。`--include-global` 指定時のみ `~/.claude/CLAUDE.md` 等を追加対象化。**baseline 不在を検知したら first-run フロー**（AskUserQuestion で「(a) 現状を baseline として確定し以降は新規 finding のみ提示 / (b) 重大度上位のみ triage / (c) フルレポート」を提示）で初回の overwhelm を回避
- **Phase 1: Static Checks** — `static_checks.py` の rule registry を一括実行し findings JSON を `.claude/tmp/context-audit/` に出力。**finding schema は全ルール共通で `id/severity/action/where(file:line)/what/why/how/fix_action(old→new)` を必須**とし、`secret_detect.py` の redaction を line-context に適用してから直列化（検出値・生 secret 行は JSON にも残さない — CA-M301 以外のルールの line-context も対象）
- **Phase 2: LLM Checks（REPORT_ONLY）** — contradiction 候補（同一 subject への禁止/許可の共起等、static_checks.py が抽出した candidate ペアのみ。抽出は **recall 優先の over-generation** で precision は問わない）を LLM が「矛盾 / 意図的差分 / 優先順位で解決済み / 不明」に分類。修正はしない。LLM に渡すのは **正規化済みの最小 claim テキストのみ**（生のメモリ行・PII を渡さない、redaction 済み）
- **Phase 3: Aggregate** — `aggregate_report.py` で baseline suppression を適用し、**summary-first の report skeleton**（トップ行に `N findings: X AUTO_FIX / Y NEEDS_JUDGMENT / Z REPORT_ONLY; M suppressed`、カテゴリ/ルール別グループ → severity 降順ソート、1 行 headline + file:line + 詳細）を決定的に生成。action は static_checks.py の出力を尊重し再計算しない
- **Phase 4: Apply & Report** — AUTO_FIX は `apply_fixes.py` で計算した差分を **unified diff で提示 → バッチ確認（「N 件の auto-fix を適用しますか？」）** の上で適用。NEEDS_JUDGMENT は **fix-type / rule ID でグルーピングしバッチ提示**（「12 件のパス typo 修正を一括適用 / 個別に確認 / スキップ」）、対話プロンプトは 1 回の run で上限 N 件に cap し残りはレポート送り（`--interactive` で再開可能）。REPORT_ONLY は what/why/how を含む actionable な構造化レポートで提示（contradiction は 2 箇所の location を併記）。verification-gate 契約準拠の evidence 出力

### v1 ルールセット（rule-catalog.md に定義）

| ID | カテゴリ | 内容 | 検証 | action |
|----|---------|------|------|--------|
| CA-S001 | stale | 存在しないファイル/ディレクトリへの参照 | 純関数 | AUTO_FIX（明白な typo）/ NEEDS_JUDGMENT |
| CA-S002 | stale | 存在しないスキル/コマンド名への言及 | 純関数 | NEEDS_JUDGMENT |
| CA-U001 | unsafe | 確認省略・破壊的操作を許可する語彙（regex ベース） | 純関数 | REPORT_ONLY |
| CA-D001 | drift | ツール語彙の混入（Claude 用 Edit/Write が AGENTS.md に等） | 純関数 | REPORT_ONLY |
| CA-D002 | drift | スキル一覧カバレッジ差分（実ディレクトリ vs 指示ファイル記載） | 純関数 | NEEDS_JUDGMENT |
| CA-C001 | contradiction | 同一 subject への禁止/許可衝突（candidate 抽出は純関数、判定は LLM） | 混成 | REPORT_ONLY |
| CA-M001 | memory | frontmatter schema 違反（必須キー欠落 / type 不正 / name と filename 乖離） | 純関数 | AUTO_FIX（正規化）/ NEEDS_JUDGMENT |
| CA-M101 | memory | メモリが参照するファイル/スキル/フラグの実在チェック | 純関数 | NEEDS_JUDGMENT |
| CA-M301 | memory | secret/credential 疑いのパターン検出 | 純関数（既存 detect_secrets 再利用） | REPORT_ONLY（自動マスク禁止） |

> **ID band 規約**（rule-catalog.md に明記）: 末尾 3桁は `0xx=schema/stale`、`1xx=reference 実在`、`3xx=security`、`2xx` は予約。将来ルールが恣意的な番号に落ちないよう band 意味論を固定。
> **実装ノート**: CA-D002 は set ベース lookup（skill ディレクトリ vs 記載名の集合差分、per-skill full-file scan 禁止）。CA-C001 candidate 抽出は subject key で bucket 化してから同一 bucket 内のみ pairing（全 pairs O(S²) を回避）。両者ともテストで実装形を lock する。

### Key Points

- **verdict taxonomy の正しい出自**: severity（BLOCK/WARN/INFO/PASS）は `severity-and-verdicts.md` に準拠。**fix action（AUTO_FIX/NEEDS_JUDGMENT/REPORT_ONLY）は `severity-and-verdicts.md` には存在せず、`doc-audit/references/checks.md` のローカル taxonomy が出自**。context-audit が 3 番目の consumer になるため、この fix-action taxonomy を `skills/shared/references/` に抽出し doc-audit と context-audit の双方が参照する（doc-check の `OK` と doc-audit の `REPORT_ONLY` の差異も併せて整理）。完了検証は `verification-gate.md`、description 執筆は `skill-authoring.md` に準拠
- **既存スキルとの境界（mechanical に deconflict）**: `CA-D002`（カバレッジ差分）は `scripts/validate_repo.py` を検出したリポジトリでは **自動スキップ**（prose の「補完扱い」ではなく機械的に抑制）。`CA-S001/S002`（実在しないファイル/スキル参照）は doc-check の structural check と重複するが、**context-audit は instruction-bearing ファイルを「指示品質」として所有、doc-check は任意 docs を「コード正確性」として所有**、という所有ルールを rule-catalog.md に明記
- **既存資産の再利用（reinvent 回避）**: secret 検出は skill-improve の `detect_secrets`/`mask_secrets`/`SECRET_PATTERNS`（`skills/skill-improve/scripts/collect.py`、テスト済み）を shared 化して再利用。frontmatter パースは `validate_repo.py` の regex ヘルパ方式を踏襲（PyYAML 依存を増やさない）
- **cwd→memory slug 解決**: 実 Claude Code の slug 化は `/` だけでなく `.`・`_` 等の非英数字も `-` に置換する（実測: `/x/.claude` → `-x--claude`）。これに正確に一致させ、**実ディレクトリ fixture に対する unittest** で検証。解決後は (1) 絶対パスが `~/.claude/projects/` 直下であること、(2) worktree/別プロジェクトとの collision でないことを reverse-verify し、曖昧なら fail-safe skip。監査した memory の解決済み絶対パスをレポートに明示（どのプロジェクトを読んだか可視化）
- **CA-M001 メモリ schema**: 観測されたフロントマター（`name`/`description`/`type`/`originSessionId`）は **Claude Code ランタイム慣習でありリポジトリ所有ではない**。memory-audit.md に「observed schema（repo 非所有）」として保守的に固定し、`type` の未知値は hard violation ではなく NEEDS_JUDGMENT に倒す（harness drift での偽陽性回避）
- **AUTO_FIX の境界**: パス置換は edit-distance ≤1 **かつ** 候補が一意のときのみ AUTO_FIX、複数候補や曖昧は NEEDS_JUDGMENT に降格。frontmatter 正規化はキーのみ変更し **body は byte 単位で不変**（`test_apply_fixes.py` で assert）。fix の置換文字列は `static_checks.py`/`apply_fixes.py` が純関数で計算し、LLM が SKILL.md 内で合成しない（決定性を glue に漏らさない）
- **rule registry と拡張性（Open-Closed）**: 各ルールは pure fn `check(target, ctx) -> list[Finding]` として `RULES` レジストリに登録、`static_checks.py` は薄いディスパッチャ。ルール追加 = 関数追加 + 登録 + テスト追加のみで既存に触れない。`test_catalog_sync.py` が rule-catalog.md（table）と RULES の ID/severity/action 一致を機械検証し、dual source of truth の drift を防ぐ
- **偽陽性優先の抑制**: 分類は path allowlist（決定的）で行い content 推論はしない。suppression 済み finding はレポートに件数のみ表示（silent truncation 禁止）
- **description のトリガー語**: 「context-audit」「指示ファイル監査」「CLAUDE.md 棚卸し」「メモリ棚卸し」「指示の腐敗」等を含め、validate_repo.py チェック11 に合格させる

## ✅ Tests

- [x] test_collect_targets.py — path allowlist 分類、除外パス、cwd→memory slug 解決（`.`/`_` 含む実パス fixture・collision detection・reverse-verify）、メモリ/rule ディレクトリ不在時の graceful skip、**非 UTF-8 / symlink / 空リポジトリ / CLAUDE.md 不在 / 巨大ファイルの edge case**、1 ファイル読込失敗が全体を中断しないこと
- [x] test_static_checks.py — CA-S001/S002（参照実在）、CA-U001（unsafe 語彙）、CA-D001（ツール語彙混入）、CA-D002（カバレッジ差分・validate_repo 検出時の auto-skip）、CA-C001 candidate 抽出（recall 優先・shape のみ検証）、CA-M001/M101/M301（メモリ系）の各正常系・偽陽性回避ケース。finding schema 必須フィールド（what/why/how/where/fix_action）の充足、secret redaction が全 finding の line-context に適用されること
- [x] test_apply_fixes.py — パス typo 置換、frontmatter 正規化（body byte 不変）、**idempotency（2 回目適用が no-op）**、複数候補時の AUTO_FIX 降格
- [x] test_aggregate_report.py — baseline suppression 適用、severity 集計、fix action 付与、suppression 件数の明示、report skeleton の決定性
- [x] test_catalog_sync.py — rule-catalog.md の ID/severity/action と RULES registry の一致
- [x] test_secret_detect.py — 共有化した detect_secrets/mask_secrets の回帰（再利用元テストの移設・維持）
- [x] `python3 scripts/validate_repo.py` 合格（description 品質・対応表・README カバレッジ）

## 🔒 Security

- [x] メモリ監査はデフォルトで cwd 対応プロジェクトのみ（プライバシー事故防止）。グローバル設定・全プロジェクト横断は明示 opt-in フラグ `--include-global`（デフォルト不在）でのみ有効化
- [x] slug 解決は実 Claude Code 実装に一致 + reverse-verify（解決先が `~/.claude/projects/` 直下・collision でないことを確認、曖昧なら fail-safe skip）。**別プロジェクトの memory を読む collision リスクを排除**し、読んだ絶対パスをレポートに明示
- [x] secret 疑い検出（CA-M301）は REPORT_ONLY。検出値そのものをレポート **にも中間 JSON にも** 転記せずパターン名と場所（file:line）のみ記載。redaction は finding schema の不変条件として **全ルールの line-context に適用**し `static_checks.py` で enforce（unittest）
- [x] Phase 2 の LLM / Phase 4 の AskUserQuestion には生のメモリ行・PII を渡さず、正規化済み最小 claim テキスト（redaction 済み）のみを渡す
- [x] 削除・本文書き換えの自動実行禁止（AUTO_FIX はパス修正・frontmatter 正規化に限定、path 置換は edit-distance ≤1 かつ一意候補のみ、body byte 不変）
- [x] レポート・中間 JSON は `.claude/tmp/context-audit/`（git-ignored）に出力。baseline `.claude/context-audit-baseline.json` は commit 対象だが **opaque finding ID のみ格納**（検出値・本文を絶対に載せない、v2 hash 形式でも不変）

## 📊 Progress

| Step | Status |
|------|--------|
| Tests | 🟢 |
| Implementation | 🟢 |
| Commit | 🟢 |

**Legend:** ⚪ Pending · 🟡 In Progress · 🟢 Done

---

## 📦 実装サマリー

- **スキル本体**: `skills/context-audit/`（SKILL.md + references 3種 + scripts 4種 + unittest 6種）
- **共有化**: `skills/shared/scripts/secret_detect.py`（skill-improve から抽出・再エクスポートで後方互換）、
  `skills/shared/references/fix-action-taxonomy.md`（doc-audit から抽出、doc-audit checks.md に参照追加）
- **テスト**: context-audit 93 件 + skill-improve 回帰 32 件 + trigger-eval 回帰 全パス。`validate_repo.py` 合格
- **レビュー**: 敵対的レビュー（BLOCK 1 / WARN 2 / INFO 4）を全件修正
  - B1: fix_action.path の redaction 破壊（AUTO_FIX silent no-op）→ path をマスク対象外に + 回帰テスト
  - W1: CA-C001 を計画通り bucket 化ペアリングに（shape lock テスト付き）
  - W2: CA-S001 backtick 参照の偽陽性 13→3 件（拡張子 + 親ディレクトリ実在の anchoring 条件）
  - I1: `--update-baseline` を aggregate_report.py に実装（LLM の手集め排除）
  - I2: CA-D002 語境界一致 / I3: CA-M301 credential=BLOCK・PII=WARN 分離 / I4: CRLF 耐性
- **バージョン**: v1.31.0（plugin.json / marketplace.json / CHANGELOG.md）

**Completed:** 2026-07-03
