---
name: codex-sync
description: Claude 版スキルを Codex CLI 版へ自動移植・差分同期するメタスキル。port（新規移植）と sync（差分同期）の2モードを持ち、変換ルール適用 → validate → 同期台帳更新まで一気通貫で実行する。「codex-sync」「Codex に移植」「Codex 版を作って」「Codex 版を同期」「未同期を解消」で起動。
---

# Codex Sync

Claude 版スキル（`skills/`）を単一ソースとして、Codex 版（`codex-skills/`）への
新規移植（port）と差分同期（sync）を自動実行するメタスキル。
「Claude 用に作って、後から Codex 用に真似して再現」という多重管理の編集コストを排除する。

**このスキルは claude-skills リポジトリ専用**（`codex-skills/sync-manifest.json` と
`scripts/validate_repo.py` の存在が前提）。

## Progress Checklist

```
codex-sync Progress:
- [ ] Step 0: モード判定（port / sync / scan）
- [ ] Step 1: 変換コンテキスト読み込み
- [ ] Step 2: 差分抽出（sync のみ）
- [ ] Step 3: 移植・変換の実行
- [ ] Step 4: 周辺ドキュメント更新（port のみ）
- [ ] Step 5: validate → 台帳更新 → 全チェック合格
- [ ] Step 6: 報告（第3層の要判断事項を列挙）
```

## Step 0: モード判定

| 引数 | モード | 動作 |
|------|--------|------|
| スキル名（`codex-skills/<name>/` が**存在しない**） | **port** | Codex 版を新規作成 |
| スキル名（`codex-skills/<name>/` が**存在する**） | **sync** | 前回同期時点からの差分を移植 |
| なし | **scan** | `python3 scripts/validate_repo.py` の `[sync]` エラーから未同期ペアを列挙し、各ペアを sync モードで順次処理。未同期ゼロなら「全ペア同期済み」と報告して終了 |

- スキル名指定時、`skills/<name>/SKILL.md` が存在しなければ中断:
  `⛔ CODEX-SYNC ABORTED: skills/<name>/SKILL.md が存在しない`
- port モードで対象がツール非依存（例: 参照資料のみのスキル）と判断される場合も
  中断せず進める — 変換箇所が少ないだけで手順は同じ

## Step 1: 変換コンテキスト読み込み

以下を読み込む:

1. [references/porting-rules.md](references/porting-rules.md) — 3層変換ルール（正典）
2. `codex-skills/shared/references/tool-mapping.md` — ツール対応表
3. **スタイル参照**: 既存の Codex 版から性質が近いものを1つ
   （エージェント並行系→ `codex-skills/codebase-review/SKILL.md`、
   単独ワークフロー系→ `codex-skills/commit/SKILL.md`、
   headless 系→ `codex-skills/parallel-cycle/SKILL.md`）

## Step 2: 差分抽出（sync モードのみ）

1. `codex-skills/sync-manifest.json` から対象ペアの `source_sha256` を取得
2. 前回同期時点のソース内容を git 履歴から特定する:
   ```bash
   for rev in $(git log --format=%H -- skills/<name>/SKILL.md); do
     if [ "$(git show $rev:skills/<name>/SKILL.md | sha256sum | cut -d' ' -f1)" = "<source_sha256>" ]; then
       echo "FOUND: $rev"; break
     fi
   done
   ```
3. 一致 rev が見つかったら移植対象差分を抽出:
   ```bash
   git diff <rev> HEAD -- skills/<name>/SKILL.md
   ```
4. **フォールバック**: 一致 rev が見つからない場合（squash / rebase / 台帳更新漏れ）は
   差分同期を諦め、Claude 版と Codex 版の全文を読み比べて意味レベルで欠落を特定する
   （その旨を報告書に明記する）

## Step 3: 移植・変換の実行

**Agent ツールに委譲**（`subagent_type: general-purpose`, `mode: bypassPermissions`）。
プロンプトには以下を**実内容でインライン展開**して渡す（プレースホルダのまま転送しない）:

- porting-rules.md の全文
- port モード: Claude 版 SKILL.md の全文 + スタイル参照の全文
- sync モード: Step 2 の差分 + 現在の Codex 版 SKILL.md の全文
- 指示: 第1〜2層ルールを機械的に適用し、第3層に該当する箇所は**変換せず**
  `<!-- REVIEW: 理由 -->` コメントを挿入した上で、要判断リストとして返答に含めること

Agent の出力で `codex-skills/<name>/SKILL.md` を作成（port）または更新（sync）する。

**references の処理**（port のみ）: ツール非依存の references は symlink を張る:

```bash
mkdir -p codex-skills/<name>/references
ln -s ../../../skills/<name>/references/<file> codex-skills/<name>/references/<file>
```

## Step 4: 周辺ドキュメント更新（port モードのみ）

CI のドリフト検出に合格するため、以下を**必ず**更新する:

1. **AGENTS.md** — codex-skills 構造ツリーに新スキルのエントリ追加 + 主要スキル表に行追加
   （AGENTS.md にスキル名が無いと `[drift]` で CI が fail する）
2. **README.md** — 「Codex CLI 用スキル」表に行追加
3. **CLAUDE.md** — 主要スキル表の該当スキル説明に Codex 版の存在を追記（慣例に従う）

## Step 5: Validate → 台帳更新

```bash
python3 scripts/validate_repo.py          # [sync] 未登録（port）/ 未同期（sync）以外のエラーが無いこと
python3 scripts/validate_repo.py --update-manifest
python3 scripts/validate_repo.py          # 全チェック合格の確認（このエビデンスを報告に含める）
```

**Verification Gate**: `skills/shared/references/verification-gate.md` に従い、
最終の「✓ 全チェック合格」出力を確認するまで完了を宣言しない。
合格しない場合はエラーを修正して再実行する（同じ修正の3回失敗で中断し人間へ報告）。

## Step 6: 報告

```
✅ codex-sync 完了: <name>（port / sync）

変更ファイル:
  - codex-skills/<name>/SKILL.md（新規 / 更新）
  - <その他の変更ファイル>

適用した変換:
  - 第1層: <適用した置換の要約>
  - 第2層: <適用した構造変換の要約>

⚠️ 要判断（第3層 — 人間のレビューが必要）:
  1. <箇所>: <なぜ自動変換しなかったか>
  （なければ「なし」）

検証: ✓ 全チェック合格（validate_repo.py）
推奨: <大規模移植の場合> [empirical-prompt-tuning](../empirical-prompt-tuning/SKILL.md) での実機チューニングを推奨
```

## 重要ルール

- **第3層を勝手に変換しない** — 安全設計・プラットフォーム設計判断・チューニング済み文言は
  `<!-- REVIEW -->` マーカーと報告で人間に委ねる
- **台帳更新は validate 合格とセット** — `--update-manifest` だけ実行して内容同期を怠るのは禁止
- **既存の Codex 版の独自改良を上書きしない**（sync モード） — 差分適用時に Codex 版固有の
  記述と衝突したら第3層扱いにする

## References

- 変換ルール（3層）: [references/porting-rules.md](references/porting-rules.md)
- ツール対応表: `codex-skills/shared/references/tool-mapping.md`
- 完了前検証: [../shared/references/verification-gate.md](../shared/references/verification-gate.md)
