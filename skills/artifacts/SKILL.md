---
name: artifacts
description: Agent Artifact Store の初期化・状態診断・旧 docs 成果物の安全な移行を行う。「artifacts init」「artifact status」「成果物を .agents へ移行」「artifact migrate」「保存先設定を確認」で起動。
---

# Artifacts

Agent-generated working state を `.agents/artifacts/` で LLM 非依存に管理する。全 workflow で先に
[Artifact Store contract](../shared/references/artifact-store.md) を読み、配布位置基準の
`../shared/scripts/artifact_store.py` を使う。手作業で設定解決や移行を再実装しない。

## Workflow selection

先頭引数で workflow を選ぶ。

- `init` → safe local store を初期化
- `status` または引数なし → 設定と store を読み取り専用で診断
- `migrate` → legacy `docs/{plans,issues,ideas,loop}` を inventory・分類・段階移行

`{artifact_store.py}` はこのスキルディレクトリから
`../shared/scripts/artifact_store.py` を解決したパスとする。

## Status workflow

1. 次を実行する。

   ```bash
   python3 {artifact_store.py} status --repo .
   ```

2. `policy`、`root`、`state`、`legacy_roots`、`errors`、`writable` を表示する。
3. `legacy` なら migrate、`split-brain` なら新規書き込み停止を案内する。
4. status 中はファイルを変更しない。

## Init workflow

1. status を実行する。
2. legacy root があれば初期化を中止し、migrate へ誘導する。空の新 store を作らない。
3. legacy root がなければ次を実行する。

   ```bash
   python3 {artifact_store.py} init --repo .
   ```

4. `.agents/artifacts.yml`、`.gitignore`、標準サブディレクトリを確認する。
5. status を再実行し、`errors: []` かつ `writable: true` を完了条件とする。

`public` または `shared-private` は init で暗黙選択しない。管理者の明示的な
policy 変更と検査なしに visibility を広げない。

## Migrate workflow

### 1. Inventory

必ず最初に dry-run report を作る。リポジトリ内に report を保存しない。

```bash
python3 {artifact_store.py} migrate-check --repo . --output {temporary_decisions_json}
```

report の各 `entries[].action` は初期値 `review` である。各 entry を文脈で確認し、次のいずれかへ変更する。

- `move`: canonical store へ移し、finalize で legacy source を除去
- `copy`: canonical store へ複製し、legacy source も残す
- `keep`: reader-facing 公開文書として legacy 側だけに残す
- `skip`: この store の管理対象外

`review` が1件でも残っていれば次へ進まない。公開文書をカテゴリ単位で
一括 `move` しない。

### 2. Stage

分類完了後に次を実行する。

```bash
python3 {artifact_store.py} migrate-stage --repo . --decisions {temporary_decisions_json}
```

stage は `move/copy` 対象を複製して hash を検査するが、source を削除しない。

### 3. Verify

1. stage 出力と `.agents/artifacts/.migration-state.json` を確認する。
2. 件数、hash、相対リンク、producer/consumer の新 root 対応を検査する。
3. 検証中は legacy source を削除しない。

### 4. Finalize

source 削除と公開履歴の残存をユーザーが明示承認した場合のみ、次を実行する。

```bash
python3 {artifact_store.py} migrate-finalize --repo . \
  --confirm-remove-source --confirm-public-history
```

finalize 後に status を再実行する。`copy/keep/skip` で legacy root が残る場合は、
canonical writer との split-brain ではないことを人間が確認するまで書き込みを再開しない。

## Blocking conditions

次の場合は自動修復や別 root への fallback を行わず停止する。

- unknown schema、policy parse error、未知の設定キー
- root 逸脱または symlink
- local store の Git 追跡・ignore 不整合
- legacy/canonical split-brain
- inventory 後の source hash 変化
- stage destination の衝突
- unresolved `review`

停止時は status とエラーを表示し、どのファイルも削除しない。
