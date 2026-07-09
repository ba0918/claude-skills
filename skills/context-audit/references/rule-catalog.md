# CA-* Rule Catalog

context-audit の全ルールの定義。`scripts/static_checks.py` の `RULES` レジストリと
**この表が dual source of truth** であり、`scripts/test_catalog_sync.py` が
ID / Category / Severity / Action の一致を機械検証する（drift 防止）。

- **Severity**（BLOCK / WARN / INFO / PASS）は問題の重大度。定義は
  [../../shared/references/severity-and-verdicts.md](../../shared/references/severity-and-verdicts.md) に準拠。
- **Action**（AUTO_FIX / NEEDS_JUDGMENT / REPORT_ONLY）は修正の自動化可否。severity と直交する別軸で、
  定義は [../../shared/references/fix-action-taxonomy.md](../../shared/references/fix-action-taxonomy.md) に準拠。
- v1 の判定は「純関数（決定的）」が中心。CA-C001 のみ candidate 抽出が純関数で、矛盾/意図的差分の判定は LLM（Phase 2, REPORT_ONLY）。

## ID band 規約

末尾 3 桁で band を固定し、将来ルールが恣意的な番号に落ちないようにする:

| band | 意味 |
|------|------|
| `0xx` | schema / stale（構造・陳腐化） |
| `1xx` | reference 実在（参照先の存在チェック） |
| `2xx` | 予約（未使用） |
| `3xx` | security（secret / 資格情報） |

Category prefix: `S`=stale, `U`=unsafe, `D`=drift, `C`=contradiction, `M`=memory。

## ルール一覧

| ID | Category | Severity | Action | 検証 | 内容 |
|----|----------|----------|--------|------|------|
| CA-S001 | stale | WARN | AUTO_FIX / NEEDS_JUDGMENT | 純関数 | 存在しないファイル/ディレクトリへの参照。抽出対象は `/` を含むパス表記のみ（裸のファイル名は precision のため対象外）。edit-distance ≤1 かつ一意候補のみ AUTO_FIX、それ以外は NEEDS_JUDGMENT |
| CA-S002 | stale | WARN | NEEDS_JUDGMENT | 純関数 | 存在しない `skills/<name>/` `codex-skills/<name>/` ディレクトリ参照 |
| CA-U001 | unsafe | WARN | REPORT_ONLY | 純関数 | 確認省略・破壊的操作を許可する語彙（regex ベース） |
| CA-D001 | drift | INFO | REPORT_ONLY | 純関数 | AGENTS.md への Claude 専用ツール語彙（Edit/Write 等、日本語「〜ツール」表記含む）の混入。行単位で finding 化し、1 行に複数語彙があっても代表 1 語で報告 |
| CA-D002 | drift | WARN | NEEDS_JUDGMENT | 純関数 | スキル一覧カバレッジ差分（実ディレクトリ vs 指示ファイル記載）。`validate_repo.py` 検出時は自動スキップ |
| CA-C001 | contradiction | WARN | REPORT_ONLY | 混成 | 同一 subject への禁止/許可衝突。candidate 抽出は純関数（recall 優先）、判定は LLM |
| CA-M001 | memory | WARN | AUTO_FIX / NEEDS_JUDGMENT | 純関数 | メモリ frontmatter schema。整形の揺れは AUTO_FIX（正規化・body 不変）、必須キー欠落/未知 type は NEEDS_JUDGMENT |
| CA-M101 | memory | WARN | NEEDS_JUDGMENT | 純関数 | メモリが参照するファイル/スキルの実在チェック |
| CA-M301 | memory | BLOCK / WARN | REPORT_ONLY | 純関数（既存 detect_secrets 再利用） | secret/credential 疑いのパターン検出（credential=BLOCK / PII（email・home_path）=WARN）。値は転記せず自動マスクもしない |

## 所有ルール（既存スキルとの境界）

- **CA-S001 / CA-S002** は doc-check の structural check と表面的に重複するが、所有領域が異なる:
  - **context-audit**: instruction-bearing ファイル（CLAUDE.md / AGENTS.md / rules / memory）を「指示品質」として所有。
  - **doc-check**: 任意の docs を「コード正確性（code ⇔ docs）」として所有。
- **CA-D002** は `scripts/validate_repo.py` を検出したリポジトリでは自動スキップ（prose の「補完扱い」ではなく機械的に抑制）。validate_repo のチェック6がカバレッジを所有する。

## 実装ノート

- **CA-D002** は set ベース lookup（skill ディレクトリ集合 vs 指示ファイル記載の集合差分）。per-skill full-file scan はしない。
- **CA-C001** candidate 抽出は subject token で bucket 化してから同一主題ペアのみ pairing（Jaccard ≥ 0.5、opposite polarity）。全 pairs O(S²) の素朴走査を避ける。
- 各ルールは pure fn `check(targets, ctx) -> list[Finding]` として `RULES` に登録。ルール追加 = 関数追加 + 登録 + テスト追加のみ（Open-Closed）。
- 全 finding は `id / severity / action / where(file:line) / what / why / how / fix_action(old→new|null)` を持ち、直列化前に secret redaction を全 line-context に適用する。

## v2 候補（v1 対象外）

- ネストしたサブディレクトリの CLAUDE.md / AGENTS.md。
- baseline の claim 正規化 hash + expiry（v1 は opaque finding ID の単純リスト）。
- `2xx` band（drift の追加系）。
- Codex 版移植。
