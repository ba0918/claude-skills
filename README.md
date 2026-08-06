# claude-skills

AI コーディングエージェント向けのスキル集。
[Agent Skills](https://agentskills.io/) 標準に準拠しており、Claude Code、Codex、OpenCode、Copilot、Cursor、Gemini CLI 等で利用できる。

計画の作成からレビュー、自動実装、コミットまでのワークフローを中心に、セキュリティレビュー、デザインシステム、TDD ガイド、issue 自走ループなど 40 以上のスキルを提供する。

## インストール

### Claude Code Plugin（一括インストール・推奨）

全スキル、共有契約、コマンドをまとめて導入できるため、通常はこちらを推奨する。
常駐ルールとしても使いたい文書は、後述の手順で別途配置する。

```bash
claude plugin marketplace add ba0918/claude-skills
claude plugin install claude-skills@claude-skills
```

Plugin ではコマンドを `/claude-skills:plan-create` のように名前空間付きで呼び出せる。

### Codex CLI Plugin（一括インストール・推奨）

```bash
codex plugin marketplace add ba0918/claude-skills
codex plugin add claude-skills@claude-skills
```

スキル本文はプラットフォーム非依存の自然言語で記述されており、そのまま利用できる。

### OpenCode Plugin（一括インストール・推奨）

`opencode.json` の `plugin` に git 指定を 1 行足す:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "plugin": ["claude-skills@git+https://github.com/ba0918/claude-skills.git"]
}
```

OpenCode を再起動すると、plugin が `skills/` を登録し、using-workflow（幹の漏斗 + ルーティング規律）と quality-gate ポインタをセッションへ注入する。
詳細・更新・トラブルシュートは [docs/README.opencode.md](docs/README.opencode.md)。

### Claude Code rules（Plugin 利用者は手動コピー不要）

Plugin をインストールすると、SessionStart hook（`hooks/hooks.json`）がセッション開始時
（startup / resume / clear / compact / fork）に次の 2 本を常駐コンテキストへ自動注入する。
Plugin 利用者に手動コピーは不要である。

- `skills/using-workflow/SKILL.md` — 幹ワークフローの漏斗 + ルーティング規律（frontmatter を除く本文を注入。
  旧 `rules/skill-routing.md` の語彙×スキル対応表はこの漏斗に統合・簡略化した）
- 品質ゲート契約のポインタ（`hooks/inject-quality-gate.sh`）— 契約の存在・正本パス・事前条件の
  要旨のみ 4 行を注入し、契約本文（約 230 行）は複製しない

注入対象は上記 2 本のみ。常駐コンテキストの予算を使うのは、実測で必要性が確認されたものだけに
限るという意図的な選択で、`rules/` の文書（`information-placement.md` 等）は注入しない。
OpenCode は上記 git plugin が同等の注入を行う（[docs/README.opencode.md](docs/README.opencode.md)）。

自動注入があるのは Claude Code（SessionStart hook）と OpenCode（git plugin）の 2 環境のみ。
Codex CLI など session start の注入機構を持たないプラットフォームでは、
`skills/using-workflow/SKILL.md` の本文（frontmatter を除く）をプロジェクトの
`AGENTS.md`（相当ファイル）へ転記して常駐させる。

Plugin を使わず `rules/` の常駐文書も利用したい場合は、手動でコピーする:

```bash
mkdir -p ~/.claude/rules
cp rules/*.md ~/.claude/rules/
cp skills/shared/references/design-principles.md ~/.claude/rules/
cp skills/shared/references/testing-anti-patterns.md ~/.claude/rules/
```

### gh skill（個別インストール・実験的）

Agent Skills 標準の個別インストールに対応しているが、現時点では標準仕様上、複数スキルから参照される `shared/` 依存を bundle として宣言できない。
複数スキルを組み合わせて使う場合は Plugin を推奨する。

```bash
# 共有契約ライブラリ（他スキルが依存。最初にインストールする）
gh skill install ba0918/claude-skills shared --agent <your-agent>

# 個別スキルをインストール
gh skill install ba0918/claude-skills plan --agent claude-code

# 対話的に選択
gh skill install ba0918/claude-skills --agent claude-code
```

`--agent` には `claude-code` / `codex` / `github-copilot` / `cursor` / `gemini` 等を指定する。
`--scope user` を付けるとグローバルインストールになる。

## 基本ワークフロー

brainstorm（壁打ち）→ plan（計画）→ cycle（自動実装 + レビュー）→ doc-check branch（整合: ドキュメントへの書き戻し）→ commit（コミット）→ PR が幹の流れになる。

```
アイデアを壁打ちしたい           → brainstorm
計画を作りたい                   → plan-create
計画を自動実装したい             → cycle
追加修正したい                   → iterate
ドキュメントを実装に揃えたい     → doc-check branch
コミットしたい                   → commit
PR を出したい                    → 環境の手段で（gh 等。自走時は github-issue が代行）
```

brainstorm で人間と対話しながら仕様・設計を合意し、合意内容を plan / GitHub issue / docs/spec に振り分ける（ledger・clauses は意思決定の記録や機械検証を残したいときの支線）。
`cycle` は plan の自動実装をエージェントに委譲し、レビューまで含めて全自動で回す。
`iterate` は cycle 後の軽微な修正に使う。タスクの大きさを自動判定し、大きければ新しい plan の作成を提案する。
`doc-check branch` は幹の整合駅で、実装で生じたドキュメント（README・docs/spec 等）とのズレを PR 前に検証・修正する。
PR の作成はどのスキルも所有しないプル型の終端で、手動では gh 等の環境の手段を使い、自走経路では github-issue が代行する。

この流れへの道しるべ（漏斗）は `using-workflow` スキルが持つ。「作る・変える話の既定入口は brainstorm、例外は列挙された 3 カテゴリのみ」の 1 ルール + カテゴリ内の代表スキルで、数十行なので常駐できる。Plugin をインストールしていれば SessionStart hook が自動注入する（後述「Claude Code rules」節）。Plugin を使わない場合の hook 例（読み取り専用の注入のみ）:

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command", "command": "cat <スキル配置先>/skills/using-workflow/SKILL.md" } ] }
    ]
  }
}
```

## スキル一覧

スキル群は「発生順の 3 レイヤ」で整理する。このリポジトリは元来メンテナ個人の作業用として plan → implement → review の基本サイクルから始まり、実務で必要になった順にスキルが増えていった。その履歴を初見の利用者にも見えるようにするため、次の 3 段で提示する。

- **Core（幹）** — brainstorm → plan → cycle → doc-check（整合）→ commit を回すのに最小限必要なスキル。初めての利用者はここだけ見れば十分。
- **Extensions（枝）** — 実務で必要になったタイミングで後から追加されたスキル。用途別に整理する。必要になったら参照する。
- **Personal / Experimental（葉）** — 本リポジトリ自身のスキル開発サイクル・移行専用スキル・実験的スキル。外部利用者は基本的に無視してよい。

### Core（幹）— まずここから

brainstorm → plan → cycle → doc-check（整合）→ commit の基本ワークフローに必要な最小セット。

| スキル | 用途 |
|--------|------|
| `using-workflow` | 幹ワークフローの実行時漏斗（既定入口 = brainstorm、例外 3 カテゴリの列挙。常駐ロード向け） |
| `brainstorm` | 幹の既定入口。要件定義・仕様定義を対話で詰め切る重フェーズ（出口で plan / issue / docs/spec に振り分け） |
| `plan` | 合意済みの実装手順書の作成とステータス管理 |
| `plan-reviewer` | 実装成果物のレビュー（差し戻し判定付き） |
| `cycle` | plan の自動実装サイクル |
| `iterate` | cycle 後の軽量な追加修正 |
| `doc-check` | 幹の整合駅。ドキュメントとコードの整合性検証・修正（`branch` 引数で PR 前のブランチ差分を対象化） |
| `commit` | 変更の論理単位での自動コミット |
| `codebase-review` | コードベース全体の並行レビュー（100 点満点） |

### Extensions（枝）— 用途に応じて追加

Core を補強・拡張するスキル群。すべてを覚える必要はなく、直面する課題に応じて拾えばよい。

#### 計画と実装（cycle の内部を直接使いたい場合）

| スキル | 用途 |
|--------|------|
| `plan-implement` | 計画の TDD 自動実装ループ（cycle の実装フェーズ本体） |
| `parallel-cycle` | 複数の plan を worktree で並行実行 |

#### 調査とデバッグ

| スキル | 用途 |
|--------|------|
| `investigate` | 読み取り専用の問題調査（ファイル編集なし） |
| `systematic-debugging` | 根本原因の特定から修正までの構造化デバッグ |
| `problem-solving` | 行き詰まり打開の思考ツール集 |

#### レビュー

| スキル | 用途 |
|--------|------|
| `attack-review` | 攻撃者視点のセキュリティレビュー |
| `review-testing` | テスト品質の三層 focused レビュー（総合点なし） |
| `review-deps` | 依存ヘルスの focused レビュー（scanner 統合 + 相関分析） |
| `skill-reviewer` | スキル成果物（SKILL.md / references / fixtures / scripts）の診断（ゲートではない） |
| `generate-review-rules` | プロジェクト固有のレビュールール自動生成 |

##### Composite と Focused の使い分け

レビュー系は 2 群に分かれる。**Composite**（Core の `codebase-review` と本節の `attack-review`）は総合スコアで全体像を俯瞰し、**Focused**（`review-testing` / `review-deps`）はオンデマンドで特定観点を深掘りして findings + coverage ledger を返す（総合点は出さない）。

| 群 | スキル | 対象 | 観点 | 成果物 | コスト |
|----|--------|------|------|--------|--------|
| Composite | `codebase-review` | src/ 全体（`*.test.*`・lockfile は除外） | セキュリティ/性能/品質/衛生の 8 小観点 | 100 点満点スコア + レポート | 高（4+1 エージェント並行） |
| Composite | `attack-review` | 攻撃対象コード | 6 攻撃領域（server/client モード） | リスクマトリクス | 高（6+1 エージェント並行） |
| Focused | `review-testing` | テストコード + 対応 production | 欠陥検出力・契約検証・安全網の安定性 | findings + coverage ledger | 低〜中（必要時のみ） |
| Focused | `review-deps` | manifest / lockfile / 依存 diff | 既知脆弱性（scanner 正本）+ サプライチェーン相関 | findings + coverage ledger | 低〜中（必要時のみ） |

Focused レビューは [coverage ledger](skills/shared/references/coverage-ledger.md) を必ず出力し、「問題なし（reviewed）」と「見ていない（skipped / unsupported / inconclusive）」を構造的に区別する。Composite が構造的に除外する領域（テストコード・lockfile）を Focused が第一級入力として埋める関係にある。

##### レビュー対象による分担（plan-reviewer / skill-reviewer）

アプリケーションコードと一般の実装計画は `plan-reviewer`、スキル成果物（`skills/*/SKILL.md` / `skills/*/references/**` / `skills/*/fixtures.json` / `skills/shared/references/**` / `commands/*.md`）は `skill-reviewer` が見る。`skills/*/scripts/**` はコードなので cycle 内の管轄は plan-reviewer（skill-reviewer 直接起動時の診断対象としては in scope のまま — [docs/spec/skill-reviewer.md](docs/spec/skill-reviewer.md) の「管轄の境界」参照）。plan-reviewer は recall 最適化ゲートで、自然言語成果物に適用すると「散文の完全性」を無限に要求する構造になるため分けてある。skill-reviewer は**診断器でありマージゲートではない**。出力は control 候補チャネルと diagnostics チャネルに分かれ、後者は cycle の状態遷移に一切影響しない。cycle Phase 3 は変更ファイル種別で両者を自動的に振り分ける（Phase 4 final gate は振り分け対象外で全ファイルを見る）。

#### Issue 管理と自走ループ

| スキル | 用途 |
|--------|------|
| `issue` | ローカルファイルベースの issue 管理と polling ループ |
| `github-issue` | GitHub issue を起点とした自走ワークフロー |
| `goal-loop` | oracle が真になるまで修正を自律反復する収束ループ |
| `goal-decomposition` | 大枠ゴールを自走可能な単位に分解 |
| `loop-triage` | センサーの検出結果を issue キューに自動供給 |

#### ドキュメント

| スキル | 用途 |
|--------|------|
| `doc-write` | 調査結果を構造化ドキュメントに昇華 |
| `doc-audit` | docs 内のアーティファクト横断スキャン |
| `decision-journal` | 技術選定の意思決定を判例集方式で記録・聞き取り（着手前 1 行プロトコル / 選定会話の固化 / 判例聞き取り） |
| `handoff` | セッション間のコンテキスト引き継ぎ（揮発型） |
| `brief` | 変更・計画・引き継ぎ・進行中の会話を人間の判断順に再構成した自己完結 HTML として可視化（手動起動のみ・4 view 単一レンダラ・帰属完全性の機械検査） |

#### デザインシステム

| スキル | 用途 |
|--------|------|
| `design-guide` | 対話的に DESIGN.md を作成 |
| `design-scaffold` | DESIGN.md からトークンと lint 設定を生成 |
| `design-generate` | ページ定義に基づく制約付きページ生成 |
| `design-lint` | デザイントークン違反の機械検出 |
| `design-validate` | 多段階検証ゲート（lint → visual → judge） |
| `mockup-diff` | モックアップと実装の視覚差分を検出 |

#### コード改善

| スキル | 用途 |
|--------|------|
| `sweep-fix` | 問題を全体へ横展開検索し一括修正 |
| `refactor` | 動作を保持したままリファクタリング |
| `test-driven-development` | TDD サイクルのガイド |
| `spec-verify` | 検証可能な契約の正本化・PBT 生成・証拠ベースのドリフト機械検知 |
| `ledger` | 現在形の合意を状態付きで正本化する合意台帳（extract / session 対話ハイブリッド / status / orient・承認真正性 + batch + pending-vocabulary の機械検証・digest 込みの書き込み CLI ledger_write で verify-before-swap 記録） |

### Personal / Experimental（葉）— 本リポジトリ開発用・実験的

本スキル集自身の開発・チューニング・移行を支えるメタスキル群と、実験的スキル。外部利用者にとっては直接価値がないため、初見では読み飛ばして構わない。ただし「スキル集の運用ノウハウ自体を学びたい」場合は参考になる。

| スキル | 用途 |
|--------|------|
| `artifacts` | Agent Artifact Store の初期化・状態診断・移行（本スキル集を使うプロジェクトのセットアップ用） |
| `skill-improve` | セッションデータからスキルの摩擦を検出 |
| `trigger-eval` | description の発火精度を実測・改善 |
| `empirical-prompt-tuning` | テキスト指示の品質を実測・反復改善 |
| `context-audit` | 指示ファイルの老朽化を監査 |
| `skill-regression` | 共有契約の変更による回帰を検出（カバレッジは behavioral / static-only / exempt の宣言制。基準は [fixture-schema.md § Coverage tiers](skills/skill-regression/references/fixture-schema.md)） |
| `skill-interface-audit` | SKILL.md の API 契約完備性を静的監査 |
| `migrate-cycles-to-plans` | 旧 docs/cycles/ から .agents/artifacts/plans/ への移行（一回限りの移行専用） |

## 品質ゲート契約

「保護対象への状態遷移は、対象版に結びついた有効な検証証拠なしには成立しない」を中核性質とする、プラットフォーム非依存の保証条件契約。正本・強制・想起の 3 層で構成され、レビュー・検証系スキルの証跡と収束判定の共通基盤になる。先行 spike（issue #142）の実測に基づき、観点の精緻化よりも証跡・収束判定に重心を置いた設計である。

- 正本: [quality-gate-contract.md](skills/shared/references/quality-gate-contract.md) — 状態機械（machine_verified ⊥ semantic_reviewed → publishable）・証跡の失効規則・独立性の定義・収束条件
- 証跡: [evidence-format.md](skills/shared/references/evidence-format.md) + `skills/shared/scripts/evidence_check.py` — publishable 判定の機械検証（証跡不在は否定判定に倒す fail-closed）
- 適合プロファイル: [skill-repository-profile.md](skills/shared/references/skill-repository-profile.md) — 2026-08-03 発効（profile-aware verifier `evidence_check.py` が in-force 宣言を機械検証）
- 想起: SessionStart hook によるポインタ注入（インストール節を参照）

## プロンプト設計方針

Fable 5 世代モデルに沿って「短く柔らかい」を志向するが、無条件の削減は行わない。`empirical-prompt-tuning` による実測（plan / cycle スキルで 6 iteration 検証）に基づく判断基準を [skill-authoring.md § When Prompt Compression Works](skills/shared/references/skill-authoring.md) に集約している。

要約:

- **効くパターン**: inline 二重説明を契約参照に集約（3 条件下で friction -37%）／例示削減／禁止語削減（`over_specified` と `rationalization_hook` は完全消滅可能）
- **効かないパターン**: 契約側の rationale 削除／常時関与する情報の集約
- **削ってはいけない**: パス制約や auto mode 判別等の「規約」（compliance が破綻）
- **構造由来の摩擦** (テンプレ書式曖昧, プロジェクト情報欠落, template chase) は削減ではなく明示化で解く

スキル改訂時の指針として、上記条件を満たす箇所を優先的に対象にする。実測は `empirical-prompt-tuning` スキルで再現可能。

## 構成

```
skills/          スキル本体（SKILL.md + references/ + scripts/）
  shared/        複数スキルが参照する共有契約（設計・テスト原則を含む）とユーティリティ
commands/        スラッシュコマンド（スキルへの薄いラッパー）
rules/           Claude Code の初期プロンプトに配置する常駐専用ルール
scripts/         リポジトリ整合性バリデータ（CI で自動実行）
```

共有資産のうち、スキル経由ではなくコマンドラインから直接使うものもある。
[process-delegation.md](skills/shared/references/process-delegation.md) は、プロンプト単位の作業を
サブエージェントではなく別プロセスへ外注するための契約とランナー
（`skills/shared/scripts/process_runner.py`）である。セッション累計のサブエージェント起動上限を
消費せず、本体コンテキストも汚さずにワークキューを消化する。成果物ファイルの有無と妥当性だけで
合否を判定できるユニットにのみ適用する。

## 開発

```bash
# ローカルテスト
claude --plugin-dir /path/to/claude-skills

# 整合性チェック
python3 scripts/validate_repo.py
```

リポジトリ整合性チェックは GitHub Actions で push / PR ごとに実行される。
symlink の切れ、frontmatter の欠落、スキル名のドリフト、バージョン同期等を機械検証する。
