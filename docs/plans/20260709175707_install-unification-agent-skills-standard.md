# インストール方法を Agent Skills 標準準拠に寄せ、gh skill を主導線に配布統一する

**Cycle ID:** `20260709175707`
**Started:** 2026-07-09 17:57:07
**Status:** 🟡 Planning
**Issue:** 20260709120622_install-unification-agent-skills-standard

---

## 📝 What & Why

現状のインストールは Claude Code = plugin marketplace（`claude plugin install`）、Codex = 独自 `install.sh`（`~/.codex/skills` へ symlink）の2系統に割れている。Agent Skills オープン標準（2025/12 Anthropic 発表、30+ プラットフォーム共通）に準拠し、`gh skill`（GitHub 公式 CLI v2.90.0）を主導線にすることで、どのツールからも同じリポジトリを参照できる配布統一を実現する。

**壁打ちで確定した前提:**
- 変換ゼロ統一は不可能（標準が統一したのはパッケージ形式のみ、実行意味論は各ツール固有）
- 変換の自動化が本命（既存 `codex-sync` の3層ルール活用）
- dual 構造（`skills/` ↔ `codex-skills/`）は維持
- 主導線 = `gh skill`（GitHub 公式、本リポジトリと最相性）、`npx skills` を併記
- `apm` は見送り（外部依存ほぼ無しで lockfile/監査は過剰）

## 🎯 Goals

- 代表3スキルで `gh skill` + `npx skills` の配置・起動・更新・削除・誤 variant 混入を実証する
- `codex-sync` の変換自動化率を数値で出す（第3層 override の割合を計測）
- 計測結果に基づき「配布層統一（dual 維持）」vs「ビルド時生成（single source）」を判定する
- 判定に基づき README のインストール節を更新する

## 📐 Design

### Phase 1: 代表3スキルの選定と gh skill 互換性検証

Agent Skills 標準が要求するレイアウト（SKILL.md ベース）と現リポジトリ構造の差分を調査し、3つの代表スキルを選定して `gh skill` での配置・起動を実証する。

**代表3スキルの選定基準:**

| カテゴリ | 選定候補 | 選定理由 |
|---------|---------|---------|
| 単純スキル | `commit` | references なし、sub-agent なし、最もシンプル |
| 対話含むスキル | `brainstorm` | AskUserQuestion 多用、Codex セカンドオピニオン、ファイル編集禁止制約 |
| Sub-agent 使うスキル | `codebase-review` | 4エージェント並行 + Codex、JSON ファイル経由データ受け渡し、最も複雑 |

**検証項目:**
- [ ] `gh skill install ba0918/claude-skills` で Claude 版スキルが正しく配置されるか
- [ ] `gh skill install ba0918/claude-skills --variant codex` 等で Codex 版を明示選択できるか
- [ ] `gh skill preview` で事前検査が通るか
- [ ] `npx skills install ba0918/claude-skills` でも動作するか
- [ ] 誤 variant 混入テスト: Claude 環境に Codex 版が入らないか、逆も
- [ ] `gh skill update` / `gh skill remove` が正常動作するか

### Phase 2: codex-sync 変換自動化率の実測

代表3スキルそれぞれについて `codex-sync` の3層変換を分析し、各層の割合を計測する。

**3層ルール:**
- **第1層（機械的置換）**: パス配置、import 変換 → 全自動化可能
- **第2層（構造的変換）**: ツール名置換（Agent→spawn_agent 等）→ パターンマッチで自動化可能
- **第3層（要判断）**: 意味的差異（AskUserQuestion→Plan mode 限定の会話ターン化等）→ override/手書き

**計測方法:**
1. 各スキルの SKILL.md + references の総行数を base とする
2. codex-sync の変換ログから各層で処理された行数を集計
3. 第3層の割合 = 手動介入が必要な割合を算出

**判定基準（issue で確定済み）:**
- 第3層 override が 1〜2割 → 生成が勝つ（ビルド時生成で single source 化の価値大）
- 第3層 override が半分超え → 手動 dual 維持の方がマシ

### Phase 3: 判定と README 更新

Phase 1・2 の結果を総合して判定を下し、README のインストール節を更新する。

### Files to Change

```
README.md                    - インストール節を gh skill 主導線に更新
.claude-plugin/plugin.json   - Agent Skills 標準準拠のメタデータ追加（必要に応じて）
install.sh                   - 非推奨の明記 or gh skill へのリダイレクト案内追加
CLAUDE.md                    - インストール節の更新（plugin.json → gh skill 追記）
```

### Key Points

- **Agent Skills 標準はレイアウト標準**: SKILL.md 形式は既に準拠済み。配布メカニズムの統一が焦点
- **dual 構造は設計判断**: `skills/` と `codex-skills/` は重複ではなく Claude/Codex 向けバックエンド実装。一本化すると差異が条件分岐に押し込まれる
- **CI 検証なき「対応済み」にしない**: 全導入経路のテストを CI に組み込むか、少なくとも手動検証手順を文書化する
- **名前衝突リスク**: Claude版/Codex版を同名公開した場合の中央キャッシュ誤選択を検証する

## 🔬 Research & Verification Steps

### Step 1: gh skill の仕様調査

- [ ] `gh skill` の最新ドキュメントを確認（CLI v2.90.0+）
- [ ] Agent Skills 標準のレイアウト要件を確認（SKILL.md 以外に必要なファイルがあるか）
- [ ] `gh skill` がマルチスキルリポジトリ（1リポジトリに複数スキル）をどう扱うか確認
- [ ] variant 指定（Claude版/Codex版の明示選択）の仕組みを確認

### Step 2: 代表3スキルで gh skill 実証

- [ ] `commit`（単純）: gh skill install → 起動 → 更新 → 削除
- [ ] `brainstorm`（対話）: gh skill install → 起動 → 更新 → 削除
- [ ] `codebase-review`（複合）: gh skill install → 起動 → 更新 → 削除
- [ ] 各スキルで `npx skills` でも動作確認
- [ ] 誤 variant 混入テスト（Claude/Codex クロス）

### Step 3: codex-sync 変換自動化率の計測

- [ ] `commit` の変換分析（層別行数比率）
- [ ] `brainstorm` の変換分析（層別行数比率）
- [ ] `codebase-review` の変換分析（層別行数比率）
- [ ] 3スキルの加重平均で全体自動化率を推定

### Step 4: 判定と文書更新

- [ ] 計測結果に基づく「配布層統一 vs ビルド時生成」判定
- [ ] README のインストール節更新
- [ ] install.sh の非推奨化または更新
- [ ] CLAUDE.md の対応箇所更新

## ⚠️ Risks & Mitigations

| リスク | 影響 | 対策 |
|--------|------|------|
| 最低共通分母化 | Claude 固有の hooks/fork 能力が使いにくくなる | dual 構造維持で回避済み。標準はレイアウトのみ制約 |
| サポート面積膨張 | 導線増 → 問い合わせ・バグ報告が分散 | README で主導線（gh skill）を明記し、他は「も使える」程度に |
| 名前衝突 | 中央キャッシュが誤 variant 選択 | Phase 1 で実証テスト。必要なら namespace 分離 |
| 標準の寿命 | 形式はオープンでも registry/検出規則は実装固有 | SKILL.md 形式は既に広く採用（30+）。ロックインリスクは低い |
| gh skill が variant を未サポート | Claude/Codex の明示選択ができない | npx skills 等の代替手段を調査。最悪 README で手動案内 |

## 🔒 Security

- [ ] `gh skill install` 時にリポジトリの integrity 検証が行われるか確認
- [ ] `.env` や credential ファイルがスキルパッケージに含まれないことを確認（.gitignore で既に除外済みだが二重確認）

## 📊 Progress

| Step | Status |
|------|--------|
| gh skill 仕様調査 | ⚪ |
| 代表3スキル実証 | ⚪ |
| 変換自動化率計測 | ⚪ |
| 判定 & 文書更新 | ⚪ |
| Commit | ⚪ |

**Legend:** ⚪ Pending · 🟡 In Progress · 🟢 Done

---

**Next:** Write tests → Implement → Commit with `claude-skills:commit` 🚀
