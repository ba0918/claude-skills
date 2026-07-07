# rolling-checkpoint — 長生きセッションの実行状態復元（自動 handoff の再設計）

**Cycle ID:** `20260708012132`
**Started:** 2026-07-08 01:21:32
**Status:** 🔵 Implementing

---

## 📝 What & Why

plan 再読込では埋まらない「実行状態の細部」（未コミット dirty 状態・plan からの逸脱判断・次の一手）を、plan サイドカーの最新 1 ブロック checkpoint で復元する仕組みを作る。書くのは dirty のまま作業を終える者だけ、消すのは HEAD の前進（自然失効）、restore は trust-but-verify の parse ゲート + 5 分類判定（valid / stale / superseded / degraded / conflict）。

checkpoint は **worktree 内容のバックアップではなく、現在の git 状態と照合して使う restore ガイド**である（この 1 文を契約の冒頭に置く）。

出典アイデア: `docs/ideas/archives/20260708011837_rolling-checkpoint-session-state.md`

## 🎯 Goals

- checkpoint フォーマット（YAML frontmatter + 固定キー短文）を共有契約として固定し、所有境界（4 項目のみ）と禁止事項を明文化する
- 照合スクリプト（fingerprint 生成・骨格生成・5 分類判定の純関数 + unittest）を `skills/shared/scripts/` に実装する。**セキュリティ規則（path containment / secret マスク / 実行禁止 / strict parse）は文書でなくコード + テストで強制する**
- plan resume / handoff restore に checkpoint 読込 + 判定を統合し、plan / handoff スキルの出口条件に「dirty のまま終わるなら checkpoint を書く」規律を追加する
- hook なし・スキル規律のみの v1 として完結させる（PreCompact / PostToolUse hook、plan 不在の `_workspace` fallback、parallel-cycle 対応、Codex 版展開は v2 送り）

## 📐 Design

### 中核となる設計判断（壁打ち済み・確定）

| 論点 | 決定 |
|------|------|
| 書く条件 | `git status --porcelain=v1` 非空のまま作業を終える時**だけ**。成功時（クリーンに commit して終わる）は書かない。intent の事前記録は却下 |
| 失効 | `base_head`（書いた時の HEAD sha）+ `dirty_fingerprint` を必須フィールドにし、restore 時に現在値と照合。hook による削除はしない（自然失効）。restore は checkpoint を**読むだけ**（read-only）— 削除は「clean commit 後」または「superseded 判定時のユーザー確認つき削除提案」のみ（handoff の読了後削除とはライフサイクルを分離） |
| fingerprint 入力 | `LC_ALL=C git status --porcelain=v1 -z`（NUL 区切り・quoting/locale 非依存）+ `LC_ALL=C git diff HEAD` **全文** + untracked ファイルの per-file content sha256。`--stat` は行数カウント衝突（同一 stat・異なる編集で false valid）のため hash 入力に使わない。**保存**フィールドはパスと stat のみ（diff 本文は保存しない）— 「diff 本文禁止」は保存の制約であり hash 入力の制約ではない |
| 生成 | ハイブリッド: 機械的フィールドはスクリプトが git から骨格生成、叙述（decision / next）だけ LLM が 1 文ずつ埋める。書き出しは `mkdir -p` + temp ファイル → atomic rename。**単一ホスト・単一 writer 前提**（polling-pattern と同じ宣言を契約に明記）。既存 checkpoint の `written_at` / fingerprint が「自分が読んだ時点」と異なる場合は上書きせず conflict 扱いで人間照会 |
| 所有境界 | checkpoint が持つのは 4 つのみ — ①未コミット dirty 状態 ②plan からの逸脱判断（1 文）③evidence（過去観測の事実）④next（次の一手 1 個）。plan Progress / status.md / result と重複させない |
| 禁止事項 | 完了済みステップ一覧・最終結果サマリー・長いテストログの転記を契約で明示禁止 |
| evidence 分離 | `evidence`（過去に観測した事実）と `verify_on_restore`（復元後に再実行必須のコマンド）を構造分離。evidence は**観測コマンド + タイムスタンプ必須**（例: `Observed 01:25: python3 -m unittest ... exited 0`）。restore 出力は再検証まで全 evidence を historical と明示ラベルする（verification-gate 違反を構造 + 書式で防ぐ） |
| 置き場 | `docs/plans/checkpoints/{cycle_id}.md`（plan 1 つに 1 ファイル、上書き運用）。checkpoint ファイル自身と同ディレクトリは dirty set / fingerprint 計算から除外（自己ノイズ防止）。v1 の cycle_id は `[0-9]{14}` のみ受理。契約は将来の parallel-cycle 用に `[0-9]{14}(-[a-z0-9-]+)?` の checkpoint_id 文法を**予約のみ**する（v1 では拒否） |
| owner | v1 enum は `manual-session` \| `precompact` の 2 値。`precompact` は verdict 意味論（degraded）が定義済みなので予約する（v1 で書くのは manual-session のみ・emit しない旨を契約に明記）。`cycle-phase2` は書き手と verdict 挙動が同時に入る v2 で追加（bare token の先行予約はしない）。未知 owner は parse 段階で conflict。`mode: degraded` ⇔ `owner: precompact` は一致必須、不一致は parse conflict |

### restore 判定 — parse ゲート + 5 分類（判定は純関数）

**Phase 0（parse ゲート、classify より先に必ず実行）**: `parse_checkpoint` が frontmatter 不成立 / 必須キー欠落・重複キー / 未知 owner・mode / owner⇔mode 不一致 / cycle_id 形式違反 / ファイル名⇔frontmatter の cycle_id 不一致 / hash 形式不正を検出したら、HEAD 状態に関わらず terminal **conflict**（semantic 分類に入らない）。`superseded > conflict` の優先順位は parse 済み checkpoint にのみ適用される — base_head が読めない checkpoint は superseded 判定できないため、この層分離は論理的必然。

| verdict | 条件 | restore の振る舞い |
|---------|------|-------------------|
| `superseded` | `base_head` ≠ 現在 HEAD（HEAD が前進） | checkpoint を破棄・削除提案（ユーザー確認つき、自動削除しない）。コミットが ground truth。ただし現 dirty set と `dirty_files` に重なりがある場合はその旨を併記して提示（amend / rebase / 無関係コミット直後でも文脈を黙って捨てない） |
| `conflict`（semantic） | 書き込み時の上書き競合痕（読んだ時点と異なる written_at / fingerprint）等、parse は通るが整合しない状態 | 自動判断せず人間照会（fail-safe） |
| `degraded` | `owner: precompact`（`mode: degraded`） | dirty set と HEAD 以外信用しない。`decision: unknown` / `next: reconstruct_from_diff` を明示。v1 では emit されない（分類器のみ実装し fixture で凍結） |
| `stale` | HEAD 一致 & `dirty_fingerprint` ≠ 現在値 | 叙述は参考扱い。現在の diff から状態を再構成 |
| `valid` | HEAD 一致 & fingerprint 一致 | 叙述を復元の起点にする。ただし fingerprint は**変更検知であり改竄検知ではない**（repo 書込権があれば再計算できる）ため、valid でも verification-gate はスキップしない。verify_on_restore は提示のみ（下記） |

判定優先順位（parse 済みに対して）: `superseded > conflict > degraded > stale > valid`。

**呼び出し側の非対称**: plan resume では checkpoint は補助情報 — parse conflict は「警告して無視・通常 resume 続行」（壊れた補助ファイルが正常な resume をブロックしない）。handoff restore fallback では checkpoint が唯一の情報源のため conflict は人間照会で停止。この非対称を契約に明記する。

### checkpoint フォーマット（契約に固定）

```markdown
---
cycle_id: "20260708012132"
owner: manual-session        # manual-session | precompact（v1 emit は manual-session のみ）
mode: normal                 # normal | degraded（owner: precompact と一致必須）
written_at: 2026-07-08T01:30:00+09:00
base_head: abc1234...        # 書いた時点の HEAD sha（full）
dirty_fingerprint: sha256:...  # porcelain=v1 -z + diff HEAD 全文 + untracked content hash
dirty_files:
  - path/to/file1.py         # porcelain から機械生成（secret_detect.mask_secrets 通過後）
verify_on_restore:           # 構造化配列のみ。restore 側は表示専用・自動実行禁止
  - cmd: python3
    args: ["-m", "unittest", "skills/shared/scripts/test_checkpoint.py"]
---
## decision
{plan からの逸脱判断を 1 文。逸脱なしなら "none"}

## evidence
{観測コマンド + タイムスタンプ必須。例: "Observed 01:25: python3 -m unittest ... exited 0"}

## next
{次の一手 1 個だけ}
```

- 自由文 md は stale 判定が機械化できないため不採用。固定キー + 短文のみ。機械判定は frontmatter のみに依存し、本文セクションは見出し（`## decision` 等）の存在チェックまで — 本文の意味解析には依存しない
- `verify_on_restore` は自由文シェル文字列を禁止し `{cmd, args}` 構造化フィールドのみ（command-injection-by-document 対策）。restore はいかなる verdict でも**自動実行しない**（表示 → ユーザーが自分で実行）。headless / bypassPermissions 環境（cycle / polling 系）では表示のみで確認プロンプトも出さない — 「確認してから実行」は無人環境で「実行」に縮退するため、実行自体を仕様から排除する
- degraded 版は `mode: degraded` / `decision` に `unknown` / `next` に `reconstruct_from_diff` を明示（git status の羅列が判断記録に見える誤読を遮断）

### checkpoint と handoff の境界（契約に独立節を設ける）

| 軸 | checkpoint | handoff |
|----|-----------|---------|
| トリガー | dirty のまま終わる時だけ（出口条件） | コンテキスト圧迫時の明示保存 |
| ライフサイクル | plan ごと 1 ファイル上書き・HEAD 前進で自然失効・restore は read-only | セッションごと複数・restore で読了後削除 |
| キー | cycle_id（plan サイドカー） | タイムスタンプ（セッション単位） |
| 検証 | fingerprint による機械的 staleness 判定あり | なし（叙述のみ） |

handoff restore の fallback で checkpoint を読む場合も checkpoint を削除しない（handoff の削除セマンティクスを checkpoint に波及させない）。将来「handoff frontmatter への統合」に倒す場合の判断材料として、この境界表を契約に残す。

### 代替案の却下記録（契約に 1 節）

- `git stash`（pop 型）: dirty を worktree から**動かしてしまう**ため不適 — 目的は dirty をそのまま残して文脈だけ足すこと
- `git notes` / WIP commit: dirty 時点ではコミットが存在しない / 履歴汚染が base_head 失効モデルと衝突するため v1 不採用（WIP commit は長時間リスク作業向けの optional 拡張として v2 検討に記録）
- `git stash create`（tree を動かさない dangling commit）: content-exact fingerprint の代替候補として将来検討可

### Files to Change

```
skills/shared/references/
  checkpoint-pattern.md            - 新規: 共有契約（冒頭に drift 警告ヘッダ + 「restore ガイドであってバックアップではない」宣言 /
                                     フォーマット / 純関数シグネチャ表と verdict 優先順位の正本 / 所有境界 / 禁止事項 /
                                     parse ゲート + 5 分類判定表 / 呼び出し側非対称 / checkpoint vs handoff 境界 /
                                     出口条件と v1 カバレッジ限界 / evidence 書式 / 代替案却下記録 / セキュリティ規約 / v2 スコープ）
skills/shared/scripts/
  checkpoint.py                    - 新規: 純関数群 + CLI（skeleton / classify サブコマンド）。strict frontmatter parser 内蔵
                                     （共有 frontmatter.py は重複キーを黙って上書きするため**使わない** — 理由をコード内コメントに明記）
  test_checkpoint.py               - 新規: unittest（fingerprint / classify / parse / skeleton / セキュリティ強制の全項目）
skills/plan/SKILL.md               - Resume Workflow に checkpoint 読込 + 判定を統合（active session なし / plan リンク欠落 /
                                     orphan checkpoint の分岐を含む）、Status Update Workflow の出口条件に dirty 判定 + checkpoint 書き出しを追加。
                                     verdict 表は契約への md リンクで参照（重複記載しない）
skills/plan/references/status-update-guide.md - checkpoint リンクは「存在時のみの派生的 1 行」と規定
                                     （維持義務のある状態フィールドにしない。resume は cycle_id からパスを計算できる）
skills/handoff/SKILL.md            - Save Phase 1 に dirty 時の checkpoint 書き出し（主トリガー）、
                                     Restore Phase 1 に「handoff なし → active plan の checkpoint」fallback を追加（read-only・削除しない）
CLAUDE.md                          - 共有リソース一覧に checkpoint-pattern.md を追記
README.md                          - shared/references の契約一覧に checkpoint-pattern.md を追記
                                     （validate_repo はスキル名カバレッジのみ検査するため、この一覧の欠落は CI に出ない — 明示的に含める）
codex-skills/sync-manifest.json    - skills/plan/SKILL.md と skills/handoff/SKILL.md は**両方とも** codex sync source。
                                     v1 は Codex 版見送りのため両ファイルの変更を「Claude-only・v2 で追随」と判断した上で
                                     --update-manifest 実行。CHANGELOG に Claude-only である旨と Codex follow-up を明記
skills/plan/fixtures.json          - resume シナリオに checkpoint 分岐の critical 要件 + 出口条件文言の存在アサーションを追加
skills/handoff/fixtures.json       - restore fallback（read-only）の critical 要件を追加
skills/skill-regression/ledger.json - plan / handoff の挙動面 sha 更新（fixture 再生 or --update --accept）
.claude-plugin/plugin.json / marketplace.json / CHANGELOG.md - バージョン bump + エントリ
```

### Key Points

- **checkpoint.py の純関数分離**: `compute_fingerprint(porcelain_z, diff_text, untracked_hashes) -> str` / `classify(checkpoint_meta, current_head, current_fingerprint, sibling_paths, current_dirty_files) -> Verdict` / `parse_checkpoint(text, filename_cycle_id) -> meta | ParseError`（strict parser: 重複キー・リスト構文・malformed delimiter を検出）/ `build_skeleton(porcelain_z, diffstat_text, head, owner, cycle_id) -> str`。git 呼び出しは CLI 層のみ、判定ロジックは文字列入力の純関数（DI 原則準拠）。シグネチャの正本は契約に置き、SKILL.md は参照のみ（契約が skill-regression の md リンク推移閉包に入り、dep_graph が plan / handoff への影響を検出できる）
- **CLI 層の実装規約**: git 呼び出しは `subprocess.run([...], capture_output=True, text=True, timeout=...)`（index lock ハング対策の timeout 必須）、ファイル I/O は `with open()`。sibling 収集は `docs/plans/checkpoints/` の **flat listing のみ**（`docs/plans/` 全体の再帰走査をしない）
- **fingerprint の正規化**: `LC_ALL=C` 固定・`-z` NUL 区切りで quoting / locale / git 幅調整の揺れを遮断。エントリを bytes ソートし、`docs/plans/checkpoints/` 配下を除外してから hash。rename（`R old -> new` 2 パス形式）・パス内空白 / Unicode / 改行は `-z` パースで正しく扱う。untracked は per-file content sha256 を入力に含める（untracked の内容変更も stale に落ちる）
- **plan resume 統合**: Resume Process Step 2 の後に「`docs/plans/checkpoints/{cycle_id}.md` が存在すれば `checkpoint.py classify` を実行し、verdict 別分岐で復元情報を提示」を挿入。分岐には active session なし / status.md に対応 cycle_id なし（orphan checkpoint → 警告 + stale 扱い提示）/ parse conflict（警告 + 無視して通常 resume）を含める。superseded なら削除を**提案**（自動削除しない）
- **handoff restore fallback**: Phase 1 で handoff ファイルが 0 件のとき、従来は即終了 → 「`docs/status.md` の Current Session に plan があれば、その checkpoint を classify して復元」に変更。checkpoint は削除しない。handoff ファイルが在る場合の挙動は不変
- **出口条件の置き場と v1 カバレッジ限界**: handoff save の冒頭（主トリガー）と plan スキルの Status Update Workflow（副トリガー）に「`git status --porcelain=v1` 非空なら checkpoint 骨格を生成し叙述 2 文を埋める」を追記。**明示ワークフローを通らず終わるセッション（突然の中断・/clear）では書かれない** — これは hook なし v1 の既知の限界として契約の v2 スコープに明記し、fixture で出口条件文言の存在を凍結する（v1 の強制は規律 + fixture、runtime 強制は v2 hook）
- **語彙チェック（validate_repo チェック12）への追加は見送り**: `superseded` を含む語彙タプルを登録すると goal-decomposition の dossier status 使用箇所に対する false positive を誘発するため、契約語彙の機械強制は行わず fixture（skill-regression）で守る。この判断と「verdict 語彙は意図的に未強制」の 1 行を checkpoint-pattern.md に明記
- **measurement-identity への `checkpoint_written` イベント追加は v1 見送り**（EVENTS が closed set で契約改訂が必要なため）。v2 スコープ節に「additive でない（契約改訂を要する）」区分で記録。hook 系は enum 予約で additive、parallel-cycle 多重 writer と measurement イベントは契約改訂級 — と拡張コストの区別を明記

## ✅ Tests

`python3 -m unittest skills/shared/scripts/test_checkpoint.py` で全て機械検証（TDD: RED → GREEN → REFACTOR）:

- [ ] `compute_fingerprint`: 同一入力 → 同一 hash / エントリ順入替 → 同一 hash / checkpoints/ 配下除外 / 空 porcelain → 空 dirty の扱い / **同一 stat・異なる diff 内容 → 異なる hash** / untracked 内容変更 → 異なる hash
- [ ] porcelain=v1 -z パース: rename（`R` 2 パス形式）/ パスに空白・Unicode・改行 / untracked `??` / deleted `D` の各ケースで dirty_files と hash が正しい
- [ ] `parse_checkpoint`（strict）: 必須キー欠落 / 重複キー / malformed delimiter / 未知 owner / owner⇔mode 不一致 / ファイル名⇔frontmatter cycle_id 不一致 → ParseError
- [ ] セキュリティ強制: `cycle_id` が `[0-9]{14}` 以外（`../` 含む traversal 文字列）→ 拒否 / YAML タグ・アンカー付き payload → 解釈されず拒否（PyYAML 不使用の strict parser で inert）/ `verify_on_restore` に自由文シェル文字列 → ParseError（`{cmd, args}` 構造のみ受理）/ dirty_files・叙述に秘密情報パターン → `secret_detect.mask_secrets` でマスクされて書き出される
- [ ] path containment: checkpoint パスと sibling glob が realpath 済み `docs/plans/checkpoints/` 内に限定・symlink 拒否（dossier_lint の containment 手法を踏襲）
- [ ] `classify`: parse ゲート → semantic 5 分類の全 verdict + 優先順位マトリクス（HEAD 前進 + fingerprint 不一致 → superseded / parse conflict は HEAD 前進でも conflict / precompact + HEAD 一致 → degraded / 上書き競合痕 + precompact → conflict / 空 porcelain・HEAD 一致 → stale / superseded 時の dirty_files 重なり検出）
- [ ] `build_skeleton`: porcelain から dirty_files 生成（マスク済み）/ degraded モードで decision=unknown・next=reconstruct_from_diff / `mkdir -p` + atomic rename 書き出し
- [ ] CLI 終了コード: classify の verdict 別コード（スキルが分岐に使う）
- [ ] E2E（手動）: dirty のままセッション中断 → 新セッションで plan resume → valid 判定と叙述復元を確認 / commit 後の resume → superseded 判定 + 削除提案（自動削除なしを確認）/ verify_on_restore が表示のみで自動実行されないことを確認
- [ ] `python3 scripts/validate_repo.py` 全チェック合格（相対リンク / CLAUDE.md 整合 / sync-manifest（plan・handoff 両方）/ ledger）

## 🔒 Security

方針: 以下は全て「契約に書く」だけでなく **checkpoint.py 内で強制し、上記テストで証明する**（design-principles §9: single canonical validator, reused everywhere）。

- [ ] **実行面**: `verify_on_restore` は `{cmd, args}` 構造化のみ・自由文シェル禁止（parse で拒否）。restore はどの verdict でも自動実行しない（表示のみ）。headless / bypassPermissions 環境では確認プロンプトすら出さず表示のみ — 「人間の確認」を前提にした緩和は無人ループで無効化されるため、実行自体を仕様から外す
- [ ] **parse 面**: PyYAML 不使用（`yaml.load` 系のデシリアライズ RCE を構造的に排除）。strict parser はタグ / アンカーを解釈しない。共有 frontmatter.py は重複キー黙認のため不使用
- [ ] **path 面**: `re.fullmatch(r"[0-9]{14}", cycle_id)` を parse 内で強制 + checkpoint パス / sibling glob を realpath containment（symlink 拒否）で `docs/plans/checkpoints/` に限定
- [ ] **秘密情報面**: `build_skeleton` と叙述書き出しは `secret_detect.mask_secrets` を通す（パス自体が秘密になり得る — home path / email パターン）。diff 本文は保存しない（hash 入力にのみ使用）
- [ ] **信頼モデル**: fingerprint / base_head は**変更検知であり改竄検知ではない**と契約に明記。valid でも叙述は「復元の起点」であって verification-gate の代替にしない

## 📋 Implementation Steps

1. **共有契約** `skills/shared/references/checkpoint-pattern.md` を作成（Files to Change 記載の全節 — シグネチャ正本 / parse ゲート + 判定表 / 境界表 / 却下記録 / セキュリティ規約 / v1 カバレッジ限界と v2 スコープ）
2. **照合スクリプト（TDD）** `test_checkpoint.py` を先に書き（セキュリティ強制テスト含む）、`checkpoint.py`（strict parser + 純関数 + skeleton / classify CLI）を実装
3. **plan スキル統合**: Resume Workflow の checkpoint 分岐（orphan / parse conflict 分岐含む）+ Status Update Workflow の出口条件 + status-update-guide の派生的リンク規則
4. **handoff スキル統合**: save 冒頭の dirty 時書き出し（主トリガー）+ restore の checkpoint fallback（read-only）
5. **E2E 検証**: 手動セッションで dirty 中断 → restore（valid）/ commit 後 restore（superseded・削除提案のみ）/ verify_on_restore 非自動実行を実際に確認
6. **回帰・整合**: plan / handoff の fixtures 更新（出口条件文言アサーション含む）+ ledger 更新、codex-skills 同期判断（plan・handoff 両方を Claude-only と記録）+ `--update-manifest`、CLAUDE.md / README.md 追記、validate_repo 全パス
7. **リリース**: plugin.json / marketplace.json バージョン bump + CHANGELOG エントリ（Claude-only / Codex follow-up 明記）

## 📊 Progress

| Step | Status |
|------|--------|
| 契約（checkpoint-pattern.md） | 🟢 |
| Tests（test_checkpoint.py） | 🟢 (46 ケース pass) |
| Implementation（checkpoint.py + スキル統合） | 🟢 |
| E2E 検証 | 🟢 (valid/stale/superseded + verify 非実行を確認) |
| 回帰・整合（ledger / manifest / validate） | 🟢 (validate 全チェック合格) |
| Commit | 🟢 |

**Legend:** ⚪ Pending · 🟡 In Progress · 🟢 Done

---

**Next:** Write tests → Implement → Commit with `claude-skills:commit` 🚀
