# Cycle Result: goal-loop verify の追加ファイル検出漏れ修正（oracle-gaming 抜け道の封鎖）

**Plan:** docs/plans/20260708215304_goal-loop-verify-added-file-detection.md
**Executed:** 2026-07-08 22:34:06
**Issue:** 20260708202143_goal-loop-verify-add-detection-gap

## Refine
- Iterations: 4/4
- Final verdict: PASS（全観点 PASS、停滞・振動なし）
- スコア推移: 72 → 60 → 52 → 15（単調減少で収束）
- 主要改善: 旧形式フォールバック廃止 → v2-only + fail-closed 化 / 型検証を純関数 `parse_manifest_envelope` に切り出し / hidden 除外を lock root 相対パスで評価（空 manifest 回帰防止）/ 列挙・再ハッシュ両フェーズの OSError を fail-closed(exit 2) 統一

## Implementation
- Steps completed: 3/3（Tests → Implementation → Commit）
- Files changed: 2（`skills/goal-loop/scripts/goal_loop.py` +146 / `test_goal_loop.py` +295）
- Tests: 77 全パス（新規約20: `TestParseManifestEnvelope` 10 + `TestIsExcluded` 8 + CLI end-to-end 追加検出/削除/fail-closed 系）
- validate_repo.py: ✓ 全チェック合格

### 実装サマリー
- manifest を v2 形式 `{version:2, roots:[...], files:{path:hash}}` で出力（`cmd_lock`）
- 新純関数 `parse_manifest_envelope(raw) -> (roots, files)`: `isinstance(raw, dict)` ガード + version==2 / roots is list of str / files is dict を厳密検証、不一致は ValueError
- `cmd_verify`: read_text の OSError と json/parse の ValueError をまとめて exit 2（invalid manifest）にマップ。旧形式フォールバックなし（fail-closed）。roots を `_collect_paths` で再走査して current を再構築 → 追加ファイルを oracle_tampered(exit 2) で検出
- 列挙フェーズ・再ハッシュフェーズ両方を try/except OSError で fail-closed（列挙 OSError → exit 2、read_bytes OSError → current 除外して削除検出に倒す）
- `_is_build_artifact` を `_is_excluded(rel: Path)` へ昇格（module-level 純関数）。hidden（`.`始まり）除外を追加、判定は lock root 相対パス要素で実施（絶対パス祖先の hidden 要素による空 manifest 回帰を防止）
- docstring の「非対称性の明記」ブロックを是正（verify が追加も検出する旨へ）

### Codex 版への反映
- `codex-skills/goal-loop/scripts/{goal_loop.py,test_goal_loop.py}` は symlink 共有のため自動反映（追加作業不要）
- SKILL.md 非改変（CLI 引数サーフェス不変）→ sync-manifest 更新不要。validate_repo.py が「未同期」で fail しないことで裏取り済み

### 敵対レビュー確認
- 実装 Agent が spawn した re-review で BLOCK B1 CLOSED / W1・W2・I1・I2 対応済み / 77テスト再現OK / merge-ready を確認

## Commits
{Phase 3 で claude-skills:commit により作成。下記「最終コミット」参照}

## Notes
- 純関数 `oracle_manifest` / `verify_oracle_integrity` は無改変（issue 明記どおり既に正しい）
- Known Limitations: hidden ディレクトリ内 gaming ファイルは除外され得る（低実効性）/ 追加検出はディレクトリ形式 root のみ（ファイル列挙 lock は追加を捕捉できない — glob 展開の性質）。SKILL.md 側の注記追記は別 issue 候補として保留
