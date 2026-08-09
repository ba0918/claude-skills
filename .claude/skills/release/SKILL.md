---
name: release
description: このリポジトリのリリース（version bump）手続きを定型実行する。ユーザーが「bump して」「リリースして」「release して」と言ったとき、または未リリース変更をリリースしたいときに使う。CHANGELOG の Unreleased 事前検査 → トレイン規則での版番号判定 → ユーザー確認 → release.yml の workflow_dispatch → run 監視 → 失敗診断までを一式で行う。プロジェクトローカルスキル（配布物には含まれない）。
---

# Release

このリポジトリ専用のリリース手続き。正本仕様は [docs/spec/release.md](../../../docs/spec/release.md) —
判断規則（トレイン規則・品質ゲートの機械確認・非目標）はそちらが正で、本書は実行の具体だけを持つ。

## 前提

- リリースは `release.yml` の workflow_dispatch 全自動（CHANGELOG 確定・4 manifest 同期・タグ発行）。
  **手動での version bump・PR 内での bump は行わない**。
- 実行は main が最新であること（`git checkout main && git pull`）。

## 手順

### 1. 未リリース変更の確認

```bash
last_tag=$(gh release list --limit 1 --json tagName -q '.[0].tagName')
git log --oneline "$last_tag"..origin/main
```

- 変更ゼロ → 「リリースするものがない」と報告して**終了**。

### 2. CHANGELOG 事前検査（起動前の必須ゲート）

```bash
grep -c '^## Unreleased' CHANGELOG.md
```

- **ちょうど 1** → 続行。`## Unreleased` 節の内容が Step 1 の変更を代表しているかも目視確認する。
- **0** → **起動せず停止**。エントリの積み忘れ。作業ブランチ + PR で `## Unreleased` 節を
  追記してから（CHANGELOG 冒頭の規範に従い、利用者視点 1〜3 行 + PR 参照）、本手順を最初からやり直す。
  main へ直接コミットしない。
- **2 以上** → 起動せず停止。CHANGELOG の構造破損として原因を調べ、修正 PR を出す。

### 3. 版番号の判定（トレイン規則）

Step 1 の変更一覧を分類して提案を組み立てる:

- 挙動が変わらない変更のみ（typo・文言・ドキュメント整理） → **patch**
- 契約・出力・挙動の変更を含む（スキルの手順変更・新機能・共有契約の改定） → **minor**
- 互換性を壊す大改変が視野に入る → **major は基準未定義。必ずユーザーに聞く**
- patch / minor の判断が割れる場合もユーザーに聞く

現行 version は `.claude-plugin/plugin.json` の `version` を読む。

### 4. ユーザー確認（リリース承認ゲート）

提案（新 version・根拠となる変更分類・Unreleased 節の要約）を提示し、**明示の承認を得る**。

- 品質ゲート通過の保証は release.yml 内の機械確認（Unreleased → PR → merged + 全 check
  完了・失敗なし）が担う。ここでの承認はリリース実行の承認であり、品質ゲートの attestation ではない。
  **ユーザーの承認発話なしに起動してはならない**。承認が得られない・返答が曖昧な場合は起動しない。

### 5. 起動

```bash
gh workflow run release.yml -f version={X.Y.Z}
```

### 6. 監視

```bash
sleep 8
run_id=$(gh run list --workflow=release.yml --limit 1 --json databaseId -q '.[0].databaseId')
gh run watch "$run_id" --exit-status
gh release view v{X.Y.Z} --json tagName,publishedAt -q '.tagName + " " + .publishedAt'
```

成功したら、発行タグと「マーケットプレイスはこの bump でスキル変更を認識する」旨を報告する。

### 7. 失敗診断

```bash
gh run view "$run_id" --log-failed
```

- 原因を特定して報告し、復旧手順を提示する。復旧の変更も**通常規律（作業ブランチ + PR）**で行う。
- 既知の失敗形: `CHANGELOG.md has no ## Unreleased heading` = Step 2 の検査漏れ（エントリ追記 PR →
  マージ後に Step 1 から再実行）。
- 既知の失敗形（品質ゲート機械確認ステップ）:
  - `Could not resolve to a PullRequest` = エントリの `(#NNN)` が PR でなく issue を指している（#308 と同じ
    番号空間の罠）。エントリを PR 番号へ修正する PR を出してから再実行。
  - `PR #N は MERGED でない` = 参照 PR が未マージ。マージ後に再実行。
  - `PR #N に未完了または失敗した check がある` = check が未完または失敗。完了・修正後に再実行。
  - いずれも CHANGELOG エントリ修正 PR（通常規律）→ マージ → Step 1 から再実行。

## 禁止事項

- ユーザー確認なしの起動
- PR 内での version bump・manifest の手動編集
- 失敗復旧での main 直接コミット
