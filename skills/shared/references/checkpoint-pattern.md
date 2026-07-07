# Checkpoint Pattern — 共通契約

> ⚠️ **DRIFT WARNING**: この契約は plan resume / handoff restore の両スキルと `checkpoint.py`
> が共有する正本である。純関数シグネチャ・verdict 優先順位・parse ゲート・所有境界を変更したら、
> 参照スキル（plan / handoff）の再検証（skill-regression）とテスト（`test_checkpoint.py`）を必ず回すこと。
> セキュリティ規約（path containment / secret マスク / 実行禁止 / strict parse）は**文書ではなくコード + テストで強制**する。

## 冒頭宣言（最重要）

**checkpoint は worktree 内容のバックアップではない。現在の git 状態と照合して使う restore ガイドである。**

checkpoint が復元するのは「plan 再読込では埋まらない実行状態の細部」— 未コミット dirty 状態の意味、
plan からの逸脱判断、次の一手。dirty なファイル本文そのものは worktree に既にある（checkpoint は複製しない）。

## スコープと前提

- **単一ホスト・単一 writer 前提**（polling-pattern と同じ宣言）。複数プロセスが同一 checkpoint を
  同時に書く状況は v1 の対象外。書き込みは `mkdir -p` + temp ファイル → atomic rename で行う。
- **hook なし・スキル規律のみの v1**。明示ワークフロー（handoff save / plan status update）を通らずに
  終わるセッション（突然の中断・/clear）では checkpoint は書かれない。これは既知の限界（下記 v2 スコープ）。
- v1 で実際に emit するのは `owner: manual-session` のみ。`precompact` は分類器のみ実装し fixture で凍結。

## 置き場と ID 文法

- パス: `docs/plans/checkpoints/{cycle_id}.md`（plan 1 つに 1 ファイル、上書き運用）。
- checkpoint ファイル自身と `docs/plans/checkpoints/` 配下は dirty set / fingerprint 計算から**除外**（自己ノイズ防止）。
- v1 の `cycle_id` は `[0-9]{14}` のみ受理（`re.fullmatch`）。
- 契約は将来の parallel-cycle 用に `checkpoint_id` 文法 `[0-9]{14}(-[a-z0-9-]+)?` を**予約のみ**する。
  v1 では suffix 付き（`-branch` 等）は拒否する。

## フォーマット（契約に固定）

```markdown
---
cycle_id: "20260708012132"
owner: manual-session        # manual-session | precompact（v1 emit は manual-session のみ）
mode: normal                 # normal | degraded（owner: precompact と一致必須）
written_at: 2026-07-08T01:30:00+09:00
base_head: abc1234...        # 書いた時点の HEAD sha（hex）
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

- 自由文 md は stale 判定が機械化できないため不採用。固定キー + 短文のみ。
- **機械判定は frontmatter のみに依存**。本文セクションは見出し（`## decision` 等）の存在チェックまで —
  本文の意味解析には依存しない。
- degraded 版は `mode: degraded` / `decision: unknown` / `next: reconstruct_from_diff` を明示
  （git status の羅列が判断記録に見える誤読を遮断）。

## 純関数シグネチャ（正本 — SKILL.md は参照のみ）

`checkpoint.py` の判定ロジックは全て文字列/bytes 入力の純関数。git 呼び出しは CLI 層のみ（DI 原則準拠）。

| 関数 | シグネチャ | 役割 |
|------|-----------|------|
| `compute_fingerprint` | `(porcelain_z: bytes, diff_text: str, untracked_hashes: dict[str,str]) -> str` | `sha256:...` を返す。`docs/plans/checkpoints/` 配下を除外・エントリソートで順序非依存 |
| `parse_checkpoint` | `(text: str, filename_cycle_id: str) -> CheckpointMeta`（strict） | 重複キー・リスト構文・malformed delimiter・未知 owner/mode・不一致・cycle_id 形式違反を検出し `ParseError` |
| `classify` | `(meta, current_head, current_fingerprint, *, current_dirty_files=None, conflict_marker=False) -> Verdict` | parse 済み meta に対する semantic 5 分類。`conflict_marker` は上書き競合痕の入力（v1 では呼び出し側が設定しない — 下記 §信頼モデル） |
| `build_skeleton` | `(porcelain_z, head, fingerprint, owner, cycle_id, written_at) -> str` | 機械フィールドの骨格生成（dirty_files はマスク済み）。叙述は LLM が後埋め |
| `verdict_exit_code` | `(verdict: str) -> int` | CLI がスキルに返す verdict 別終了コード |

- git 呼び出しは CLI 層のみ・`subprocess.run([...], capture_output=True, timeout=...)`
  （index lock ハング対策の timeout 必須）。出力は **bytes のまま受け取り `surrogateescape` で decode** する
  （`text=True` にしない — `-z` の NUL 区切り・非 UTF-8 パスを壊さないため）。ファイル I/O は `with open()`。
- sibling 収集は `docs/plans/checkpoints/` の **flat listing のみ**（`docs/plans/` 全体の再帰走査をしない）。

### CLI 呼び出し規約（スキル側の作法）

- **`--repo` を常に明示する**（`--repo .` を含む）。cwd = 対象プロジェクトを暗黙仮定しない —
  スクリプト実体はスキル配布位置（本リポジトリでは `skills/shared/scripts/checkpoint.py`、
  plugin 利用時は plugin キャッシュ）にあり、対象プロジェクトと同居しているとは限らない。
- 対象プロジェクトが cwd と異なる場合は、スクリプトを**絶対パス**で起動し
  `--repo {対象プロジェクトルート}` を渡す。`--file` のパスも対象プロジェクト側を指すこと。
- **checkpoint 生成はセッション最後の書き込み**: skeleton 実行は他の全ファイル書き込み
  （status.md / handoff 本体等、tracked / untracked を問わず）を確定させた後に行う。
  生成後にファイルを書くと fingerprint が即 stale になる（除外は `docs/plans/checkpoints/` 配下のみ）。
- classify の `dirty_overlap:` 行は overlap があるときだけ出力される（行が無ければ重なりなし）。

## fingerprint の正規化（契約）

- 入力: `LC_ALL=C git status --porcelain=v1 -z`（NUL 区切り・quoting/locale 非依存）
  + `LC_ALL=C git diff HEAD` **全文** + untracked ファイルの per-file content sha256。
- `--stat` は行数カウント衝突（同一 stat・異なる編集で false valid）のため hash 入力に使わない。
- **保存**フィールドはパスと stat のみ（diff 本文は保存しない）。「diff 本文禁止」は保存の制約であり
  hash 入力の制約ではない。
- rename（`R old -> new` の -z 2 パス形式）・パス内空白 / Unicode / 改行は `-z` パースで正しく扱う。
- untracked は per-file content sha256 を入力に含める（untracked の内容変更も stale に落ちる）。
- エントリをソートし `docs/plans/checkpoints/` 配下を除外してから hash（順序非依存）。

## restore 判定 — parse ゲート + 5 分類

### Phase 0（parse ゲート、classify より先に必ず実行）

`parse_checkpoint` が以下を検出したら、HEAD 状態に関わらず terminal **conflict**（semantic 分類に入らない）:
frontmatter 不成立 / 必須キー欠落・重複キー / 未知 owner・mode / owner⇔mode 不一致 /
cycle_id 形式違反 / ファイル名⇔frontmatter の cycle_id 不一致 / hash 形式不正 /
`verify_on_restore` が `{cmd, args}` 構造でない（自由文シェル文字列）。

`superseded > conflict` の優先順位は parse 済み checkpoint にのみ適用される — `base_head` が読めない
checkpoint は superseded 判定できないため、この層分離は論理的必然。

### Phase 1（semantic 5 分類、parse 済みに対して）

| verdict | 条件 | restore の振る舞い |
|---------|------|-------------------|
| `superseded` | `base_head` ≠ 現在 HEAD（HEAD が前進） | checkpoint を破棄・削除**提案**（ユーザー確認つき、自動削除しない）。コミットが ground truth。ただし現 dirty set と `dirty_files` に重なりがある場合はその旨を併記（amend / rebase / 無関係コミット直後でも文脈を黙って捨てない） |
| `conflict`（semantic） | 上書き競合痕（読んだ時点と異なる written_at / fingerprint）等、parse は通るが整合しない状態 | 自動判断せず人間照会（fail-safe） |
| `degraded` | `owner: precompact`（`mode: degraded`） | dirty set と HEAD 以外信用しない。`decision: unknown` / `next: reconstruct_from_diff` を明示。v1 では emit されない（分類器のみ実装し fixture で凍結） |
| `stale` | HEAD 一致 & `dirty_fingerprint` ≠ 現在値 | 叙述は参考扱い。現在の diff から状態を再構成 |
| `valid` | HEAD 一致 & fingerprint 一致 | 叙述を復元の起点にする。ただし fingerprint は**変更検知であり改竄検知ではない**（repo 書込権があれば再計算できる）ため、valid でも verification-gate はスキップしない。verify_on_restore は提示のみ |

**判定優先順位（parse 済みに対して）**: `superseded > conflict > degraded > stale > valid`。

### 呼び出し側の非対称（契約）

- **plan resume**: checkpoint は補助情報 — parse conflict は「警告して無視・通常 resume 続行」
  （壊れた補助ファイルが正常な resume をブロックしない）。
- **handoff restore fallback**: checkpoint が唯一の情報源のため conflict は人間照会で停止。

この非対称を破ってはならない。

## checkpoint と handoff の境界

| 軸 | checkpoint | handoff |
|----|-----------|---------|
| トリガー | dirty のまま終わる時だけ（出口条件） | コンテキスト圧迫時の明示保存 |
| ライフサイクル | plan ごと 1 ファイル上書き・HEAD 前進で自然失効・restore は read-only | セッションごと複数・restore で読了後削除 |
| キー | cycle_id（plan サイドカー） | タイムスタンプ（セッション単位） |
| 検証 | fingerprint による機械的 staleness 判定あり | なし（叙述のみ） |

handoff restore の fallback で checkpoint を読む場合も checkpoint を**削除しない**（handoff の削除
セマンティクスを checkpoint に波及させない）。将来「handoff frontmatter への統合」に倒す場合の判断材料として
この境界表を残す。

## 所有境界（4 項目のみ）

checkpoint が持つのは 4 つのみ:

1. 未コミット dirty 状態（機械生成 `dirty_files` + `dirty_fingerprint`）
2. plan からの逸脱判断（`decision`、1 文）
3. evidence（過去観測の事実 — 観測コマンド + タイムスタンプ必須）
4. next（次の一手 1 個）

plan Progress / status.md / result と**重複させない**。

### 禁止事項（契約で明示）

- 完了済みステップ一覧の転記
- 最終結果サマリー
- 長いテストログの転記
- diff 本文の保存（hash 入力にのみ使用）

### evidence と verify_on_restore の分離

- `evidence`（過去に観測した事実）は**観測コマンド + タイムスタンプ必須**
  （例: `Observed 01:25: python3 -m unittest ... exited 0`）。
- `verify_on_restore`（復元後に再実行必須のコマンド）は構造化配列（`{cmd, args}`）。
- restore 出力は再検証まで全 evidence を **historical** と明示ラベルする（verification-gate 違反を構造 + 書式で防ぐ）。

## セキュリティ規約（コードで強制、テストで証明）

design-principles §9（single canonical validator, reused everywhere）に従い、以下は `checkpoint.py`
内で強制し `test_checkpoint.py` で証明する:

- **実行面**: `verify_on_restore` は `{cmd, args}` 構造化のみ・自由文シェル禁止（parse で拒否）。
  restore はどの verdict でも**自動実行しない**（表示のみ）。headless / bypassPermissions 環境
  （cycle / polling 系）では確認プロンプトすら出さず表示のみ — 「人間の確認」を前提にした緩和は
  無人ループで無効化されるため、**実行自体を仕様から外す**。
- **parse 面**: PyYAML 不使用（`yaml.load` 系のデシリアライズ RCE を構造的に排除）。strict parser は
  タグ / アンカーを解釈しない（全フィールドが enum / regex で strict 検証されるため payload は inert かつ拒否）。
  共有 `frontmatter.py` は重複キーを黙って上書きするため**使わない**。
- **path 面**: `re.fullmatch(r"[0-9]{14}", cycle_id)` を parse 内で強制 + checkpoint パス / sibling glob を
  realpath containment（symlink 拒否）で `docs/plans/checkpoints/` に限定（dossier_lint の containment 手法を踏襲）。
- **秘密情報面**: `build_skeleton` が生成する**機械フィールド `dirty_files` は `secret_detect.mask_secrets`
  を必ず通す**（パス自体が秘密になり得る — home path / email パターン）。これはコードで強制。
  一方、`decision` / `next` / `evidence` の**叙述本文は LLM が骨格生成後に直接編集して書く**ため、
  叙述のマスクは**コード強制ではなくスキル規律**（SKILL.md で mask を指示）である点を正直に区別する
  （骨格が masking するのは機械フィールドとプレースホルダのみ）。diff 本文は保存しない。
- **上書き競合（overwrite-race）**: 「既存 checkpoint の written_at / fingerprint が自分の読んだ時点と
  異なれば上書きせず conflict」という anti-overwrite 規律は、v1 では**単一 writer・単一ホスト前提に依存した
  スキル規律であってコード強制ではない**（`build_skeleton --output` は既存を無条件に atomic rename する）。
  `classify` の `conflict_marker` はこの検出を将来コード化するための v2 wire point で、v1 では呼び出し側が
  設定しない（分類器の優先順位を凍結するため unittest のみが行使する）。多重 writer への拡張は契約改訂級（v2）。
- **信頼モデル**: fingerprint / base_head は**変更検知であり改竄検知ではない**。valid でも叙述は
  「復元の起点」であって verification-gate の代替にしない。

## owner enum（契約）

- v1 enum は `manual-session` | `precompact` の 2 値。
- `precompact` は verdict 意味論（degraded）が定義済みなので予約する（v1 で書くのは manual-session のみ・emit しない）。
- `cycle-phase2` は書き手と verdict 挙動が同時に入る v2 で追加（bare token の先行予約はしない）。
- 未知 owner は parse 段階で conflict。`mode: degraded` ⇔ `owner: precompact` は一致必須、不一致は parse conflict。

## 語彙強制の意図的不採用（契約）

verdict 語彙（`superseded` 等）を validate_repo チェック12の CONTRACT_VOCAB に登録すると
goal-decomposition の dossier status 使用箇所に対する false positive を誘発するため、**契約語彙の
機械強制は行わない**。checkpoint 契約の遵守は fixture（skill-regression）で守る。この判断と
「verdict 語彙は意図的に未強制」をここに明記する。

## 代替案の却下記録

- `git stash`（pop 型）: dirty を worktree から**動かしてしまう**ため不適 — 目的は dirty をそのまま残して文脈だけ足すこと。
- `git notes` / WIP commit: dirty 時点ではコミットが存在しない / 履歴汚染が base_head 失効モデルと衝突するため v1 不採用
  （WIP commit は長時間リスク作業向けの optional 拡張として v2 検討に記録）。
- `git stash create`（tree を動かさない dangling commit）: content-exact fingerprint の代替候補として将来検討可。

## v1 カバレッジ限界と v2 スコープ

- **runtime 強制は v2**: 明示ワークフローを通らず終わるセッションでは書かれない。v1 の強制は規律 + fixture
  （出口条件文言の存在を凍結）、runtime 強制は v2 hook（PreCompact / PostToolUse）。
  hook 系は owner enum 予約で **additive**（契約改訂不要）。
- **PreCompact / PostToolUse hook** — v2。
- **plan 不在の `_workspace` fallback** — v2。
- **parallel-cycle 対応（多重 writer）** — v2、**契約改訂級**（単一 writer 前提を緩める）。
  `checkpoint_id` 文法は予約済み。
- **measurement-identity への `checkpoint_written` イベント** — v2、**契約改訂級**
  （measurement-identity の EVENTS は closed set で契約改訂が必要）。additive でない。
- **Codex 版展開** — v2。v1 は plan / handoff とも Claude-only（sync-manifest に Claude-only と記録）。

拡張コストの区別: **enum 予約 = additive**（hook 系）、**多重 writer / measurement イベント = 契約改訂級**。
