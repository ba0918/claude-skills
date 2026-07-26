---
name: artifacts
description: Agent Artifact Store の初期化・状態診断・旧 docs 成果物の安全な移行を行う。「artifacts init」「artifact status」「成果物を .agents へ移行」「artifact migrate」「保存先設定を確認」で起動。
---

# Artifacts

Manage agent-generated working state under `.agents/artifacts/` in an LLM-independent way. In every workflow, first
read the [Artifact Store contract](../shared/references/artifact-store.md) and use
`../shared/scripts/artifact_store.py`, resolved relative to the distribution location. Never re-implement configuration
resolution or migration by hand.

## Workflow selection

Select the workflow with the leading argument.

- `init` → initialize a safe local store
- `status` or no argument → diagnose the configuration and the store, read-only
- `migrate` → inventory, classify, and incrementally migrate legacy `docs/{plans,issues,ideas,loop,handoff,reviews}`

`{artifact_store.py}` is the path obtained by resolving
`../shared/scripts/artifact_store.py` from this skill's directory.

## Status workflow

1. Run the following.

   ```bash
   python3 {artifact_store.py} status --repo .
   ```

2. Display `policy`, `root`, `state`, `legacy_roots`, `errors`, and `writable`.
3. On `legacy`, guide the user to migrate; on `split-brain`, guide them to stop new writes.
4. Change no files during status.

## Init workflow

1. Run status.
2. If a legacy root exists, abort the initialization and steer the user to migrate. Do not create an empty new store.
3. If no legacy root exists, run the following.

   ```bash
   python3 {artifact_store.py} init --repo .
   ```

4. Confirm `.agents/artifacts.yml`, `.gitignore`, and the standard subdirectories.
5. Re-run status and treat `errors: []` together with `writable: true` as the completion condition.

Never select `public` or `shared-private` implicitly during init. Do not widen visibility without an
administrator's explicit policy change and inspection.

## Migrate workflow

### 1. Inventory

Always produce a dry-run report first. Do not save the report inside the repository.

```bash
python3 {artifact_store.py} migrate-check --repo . --output {temporary_decisions_json}
```

Each `entries[].action` in the report starts at `review`. Check every entry in context and change it to one of the following.

- `move`: move it to the canonical store and remove the legacy source at finalize
- `copy`: duplicate it into the canonical store and keep the legacy source as well
- `keep`: leave it only on the legacy side as a reader-facing public document
- `skip`: not managed by this store

Do not proceed while even one `review` remains. Do not bulk-`move` public documents
by category.

### 2. Stage

Once classification is complete, run the following.

```bash
python3 {artifact_store.py} migrate-stage --repo . --decisions {temporary_decisions_json}
```

Stage duplicates the `move/copy` targets and checks their hashes, but does not delete the sources.

### 3. Verify

1. Check the stage output and `.agents/artifacts/.migration-state.json`.
2. Inspect the counts, the hashes, the relative links, and the producer/consumer correspondence to the new root.
3. Do not delete legacy sources during verification.

### 4. Finalize

Only when the user has explicitly approved both the source deletion and the retention of public history, run the following.

```bash
python3 {artifact_store.py} migrate-finalize --repo . \
  --confirm-remove-source --confirm-public-history
```

Re-run status after finalize. When a legacy root survives because of `copy/keep/skip`,
do not resume writes until a human has confirmed that this is not a split-brain against the canonical writer.

## Blocking conditions

In the following cases, stop without attempting automatic repair or falling back to a different root.

- Unknown schema, policy parse error, or an unknown configuration key
- Escaping the root, or a symlink
- Git tracking / ignore inconsistency for a local store
- A legacy/canonical split-brain
- A source hash change after inventory
- A collision at a stage destination
- An unresolved `review`

On stopping, display the status and the errors, and delete no files.
