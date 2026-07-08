# Codex 既存スキルの request_user_input を Plan mode 限定バグとして retrofit（会話ターン + headless 降格へ）

**Cycle ID:** `20260708225136`
**Started:** 2026-07-08 22:51:36
**Status:** 🟢 Complete
**Issue:** 20260708193555_codex-request-user-input-plan-mode-retrofit

---

## 📝 What & Why

Codex CLI 0.142.4 で `request_user_input` は **Plan mode 限定**（default/exec モードでは使用不可）であることが実測確定している（`allows_request_user_input` は `Self::Plan` のみ true、"not supported in exec mode"）。しかし契約修正前に移植された既存 Codex スキルが `AskUserQuestion → request_user_input` 変換を引きずり、default/exec 実行時に `request_user_input` 呼び出しで詰まる潜在バグを抱える。契約（tool-mapping.md）と後発スキル群は既に正典パターンへ移行済みなので、残る既存スキルを会話ターン確認 + headless 降格へ retrofit する。

## 🎯 Goals

- **カテゴリA の 7 SKILL.md**（brainstorm / problem-solving / commit / handoff / iterate / issue / team-cycle）から `request_user_input` への**依存（ツール呼び出し指示）**を除去し、会話ターンでの平文質問へ置換する。ただし commit L182・handoff L195 は「禁止事項リスト内の否定的言及」なので**変換ではなく言及除去**（下記 negative-mention サブパターン）
- カテゴリA の各スキルに **headless/exec で応答不能なときの安全側デフォルト降格ルール**を明記する（対話本質スキル brainstorm / problem-solving の降格の意味は下記で別定義）
- レビュー次元・キーワードとして `request_user_input` を参照している箇所（カテゴリB。plan-reviewer/SKILL.md はツール呼び出し依存ではなく keyword list + レビュー観点なので依存除去の対象外）を Codex 文脈に合う「会話ターンでの選択肢提示」概念へ更新する
- 編集対象の SKILL.md は合計 8 個（カテゴリA 7 + カテゴリB の plan-reviewer 1）＋ 2 references（team-config.md / review-dimensions.md）
- **既に正典パターン（「Plan mode 限定のため使わない」注記）を持つ12スキルを一切変更しない**（過剰修正の防止）
- 契約 tool-mapping.md L14（正典定義そのもの）は触らない
- `python3 scripts/validate_repo.py`（引数なし）が合格する（Codex 側のみの変更のため `--update-manifest` は本タスクでは no-op。詳細は下記「sync-manifest への影響」）

## 📐 Design

### 分類フレーム（最重要 — 実装はこの分類に厳密に従う）

実測（`grep -n request_user_input codex-skills/**`）に基づく3カテゴリ + 保護対象:

**カテゴリA — 実使用（会話ターンへ変換 + headless 降格ルール追記）:**
| ファイル | 該当行（実測） | 備考 |
|---|---|---|
| `codex-skills/brainstorm/SKILL.md` | L15,47（ツール列挙）,51,72,99,127,151,195 | 対話が本質。会話ターン Q&A ループを維持（default mode で成立）。「headless 化しない」注記と矛盾させない |
| `codex-skills/problem-solving/SKILL.md` | L13,37（ツール列挙）,54,73,93,122,151,180,210,229 | 同上（対話本質スキル） |
| `codex-skills/commit/SKILL.md` | L182 | **negative-mention サブパターン**。L182 は「Prohibited Actions」内の項目 `Prompting the user for confirmation (using request_user_input)`＝commit は確認しない方針の否定的言及。**会話ターン確認を追加しない**。`(using request_user_input)` を削除し `Prompting the user for confirmation` のまま禁止事項として残す（commit の確認なし即実行方針を維持） |
| `codex-skills/handoff/SKILL.md` | L195 | **negative-mention サブパターン**。L195 も「Prohibited Actions」内で「save / restore / list 全て headless で完走」の趣旨。`（\`request_user_input\`）` の括弧言及を除去し「確認プロンプトを出さず headless 完走」に整理（会話ターン確認を追加しない） |
| `codex-skills/iterate/SKILL.md` | L74,100,213 **+ L216, および「Do not block on Large judgment」Important Rule** | Large 警告・続行判断を会話ターンへ。**L216 の既存 headless ルール `Do not prompt ... except for user choice on Large judgment and halt escalations` は、Large 判断を headless 例外として prompt する現行仕様なので retrofit と矛盾する → 併せて更新**。interactive では Large 選択肢を会話ターンで提示。**headless/exec（応答なし）では Large を自動続行せず halt（$plan 誘導して中断）＝ Security 節と一致**。「Do not block on Large judgment — Always present options」の Important Rule も「interactive では options 提示 / headless では安全側 halt」に明確化 |
| `codex-skills/issue/SKILL.md` | L58,128,129,171,175,198,202 | preview確認・issue選択・intakeを会話ターンへ。**headless での安全側は「自動選択しない」**: issue 選択（L128 の 1 件確認 / L129 の 2+ 件選択 / L198・L202 の close）は slug が引数で明示されていない限り**中断**（任意 issue に plan→cycle を走らせてコードを書き換える経路を作らない）。intake（L171 空 Notes）・close 未指定は非破壊なので Skip 相当のデフォルト続行可だが、create preview（L58）は重複検出結果を無視した自動作成を避け、重複ヒット時は中断する |
| `codex-skills/team-cycle/SKILL.md` | L240 | 「`request_user_input` でユーザー入力を待つ」→会話ターンで待つ。**headless（issue-team-cycle 等の自動フロー）では、既にチームがレビュー合意済みの計画に対するコメント募集ゲートなので、応答なし時はデフォルト「続行」で Phase 2 へ進む**（team-cycle は「チームレビュー → 実装」が確定フローであり、この続行はチーム合意の実行であって未レビュー変更の強行ではない。この点を1文明記する） |

**カテゴリB — レビュー次元・キーワード言及（概念を Codex 文脈へ更新）:**
| ファイル | 該当行 | 対応 |
|---|---|---|
| `codex-skills/plan-reviewer/SKILL.md` | L67（UI keyword list）, L144（"request_user_input option design"） | UI/UX 検出シグナル・レビュー観点。`request_user_input` を「会話ターンでの選択肢提示（Q&A 確認）」へ置換。Hick's Law（≤4選択肢・明確ラベル・妥当デフォルト）の評価概念は平文選択肢提示に対して有効なので保持 |
| `codex-skills/team-cycle/SKILL.md` | L101（UI keyword list） | plan-reviewer と同一の keyword list。同じ置換 |
| `codex-skills/shared/references/team-config.md` | L330 | 「request_user_input の選択肢が Hick's 法則に従うか」→「会話ターンで提示する選択肢が Hick's 法則に従うか」 |
| `codex-skills/plan-reviewer/references/review-dimensions.md` | L198 | 同上（英語チェックリスト項目） |

**カテゴリC — 触らない（契約の正典定義）:**
- `codex-skills/shared/references/tool-mapping.md` L14 — `AskUserQuestion → 会話ターン` マッピングの定義元。`request_user_input は使わない`と明記する正典。**変更禁止**。

**保護対象 — 変更禁止の12スキル（既に「Plan mode 限定のため使わない」注記済み。誤って"修正"しない）:**
team-plan / doc-check / doc-write / refactor / design-generate / design-guide / design-scaffold / sweep-fix / goal-loop / systematic-debugging / test-driven-development / team-brainstorm

### 置換パターン（カテゴリA の正典 — 後発スキルで確立済み）

各スキルの「Codex CLI ツールの使い分け」節（冒頭のツール列挙）の `request_user_input` エントリを次の定型へ:

> **会話ターンでの確認** — ユーザ確認を伴う分岐は会話ターンで平文の質問（選択肢を列挙して番号/短文で回答を促す）として尋ねる。**Codex の `request_user_input` は Plan mode 限定（default/exec 不可）のため使わない。** 応答が得られない headless/exec 文脈では安全側（{スキル固有のデフォルト: no-op / report-only / 中断}）に降格する。

> **降格先の選び方（重要）**: 安全側デフォルトに「対象を勝手に選んで破壊的操作へ進む（自動選択）」を含めてはならない。破壊的操作（コード書き換え・ファイル生成・issue 選択実行）を伴う分岐は headless では**中断**を既定とする。非破壊の分岐（出力先の慣例値・追加コンテキストの Skip 等）に限り既定値での続行を許す。team-cycle L240 のように「cycle ファミリーが headless-by-design で、既にレビュー合意済みの計画を実行する」ことが明示されている場合のみ「続行」を安全側として採用してよい（各スキルの備考で個別に正当化する）。

本文中の「`request_user_input` で確認する / 選択する / 待つ」等はすべて「会話ターンで確認する / 選択する」へ置換。対話本質スキル（brainstorm / problem-solving）は Q&A ループ自体を保持し、実現手段だけを会話ターンへ置換する（機能は default mode で保たれる）。

**対話本質スキルの「headless 降格」の意味**: brainstorm / problem-solving は対話（会話ターン Q&A）が機能そのものなので、応答チャネルが無い文脈では**降格して安全側デフォルトを勝手に確定するのではなく、対話不能を報告して終了する**（ファイル生成・破壊的操作は無いため安全側デフォルトの必要がない = 勝手に答えを捏造して進めない）。テンプレートの「安全側デフォルトに降格」節は、これらのスキルでは「default mode の会話ターンで成立。応答が得られない headless では対話を進められない旨を報告して中断（no-op）」と表現し、「headless 化しない」注記と一貫させる。

### negative-mention サブパターン（commit L182 / handoff L195 の正典）

「Prohibited Actions」等の**否定的リスト内で `request_user_input` に言及している行**は、ツール呼び出し依存ではなく「このスキルは確認プロンプトを出さない」という否定的言及である。**会話ターン確認を追加してはならない**（それはスキルの確認なし方針を反転させる誤修正になる）。対応は「`request_user_input` の語のみを除去し、否定的言及（＝確認しない方針）はそのまま残す」。headless 降格ルールの追記も不要（元々確認しないため）。

### Files to Change

```
codex-skills/
  brainstorm/SKILL.md          - カテゴリA（対話ループ維持しつつ会話ターン化）
  problem-solving/SKILL.md     - カテゴリA（同上）
  commit/SKILL.md              - カテゴリA / negative-mention（L182、語のみ除去・確認追加なし）
  handoff/SKILL.md             - カテゴリA / negative-mention（L195、括弧言及除去・確認追加なし）
  iterate/SKILL.md             - カテゴリA（L74,100,213 + L216 headless 規定 + 「Do not block on Large」Important Rule）
  issue/SKILL.md               - カテゴリA（L58ほか7箇所、headless は自動選択せず中断）
  team-cycle/SKILL.md          - カテゴリA（L240）+ カテゴリB（L101 keyword）
  plan-reviewer/SKILL.md       - カテゴリB（L67,144）
  shared/references/team-config.md              - カテゴリB（L330）
  plan-reviewer/references/review-dimensions.md - カテゴリB（L198）
```

### sync-manifest への影響

- **機構の実測**: `sync-manifest.json` は各エントリに `source_sha256`＝**Claude 側ソース**（例 `skills/issue/SKILL.md`）の sha256 を記録し、`check_sync_manifest` は「記録 sha ≠ 現在の Claude 側 sha」のときだけ「Claude 版が変更されたが Codex 版が未同期」で fail する（validate_repo.py L360-362 で実測確認）。本タスクは **Codex 側のみ**を変更し Claude 側は不変（Claude 版は AskUserQuestion を使い `request_user_input` を持たない）なので、記録 sha は動かず **`validate_repo.py`（引数なし）はそのまま合格する**。編集対象 8 SKILL.md + 2 references はいずれも manifest 追跡対象（Codex→Claude ペア）であることを確認済み。
- **`--update-manifest` の扱いを訂正**: 上記より、本タスクで `--update-manifest` は Claude 側 sha を書き換えないため **no-op（sync-manifest.json に diff が出ない）**。よって受け入れ条件は「`--update-manifest` を必須実行」ではなく「**引数なし `validate_repo.py` が合格すること**」を正とする。`--update-manifest` を走らせる場合は、無関係な既存ドリフト（他タスクで Claude 側が変わったが未同期のペア）を巻き込んで暗黙に承認するリスクがあるため、**先に引数なし `validate_repo.py` で既存ドリフトが無いことを確認してからのみ**実行し、実行後は `git diff codex-skills/sync-manifest.json` が空であることを確認する。

## ✅ Tests

> 本タスクはドキュメント（SKILL.md / references）の retrofit でありユニットテスト対象コードは無い。検証は機械的 grep + validate_repo.py で行う。

- [ ] **canonical-note 5ファイル**（brainstorm / problem-solving / iterate / issue / team-cycle）: ツール呼び出しとしての `request_user_input` 使用が残らない。`grep -n "request_user_input" <file>` の残存は「Plan mode 限定のため使わない」注記行のみ
- [ ] **negative-mention 2ファイル**（commit L182 / handoff L195）: 語 `request_user_input` を除去し**残存ゼロ**（`grep -c request_user_input` = 0）。否定的言及（確認しない方針）の文言自体は保持し、会話ターン確認を追加していない
- [ ] **mechanical assertion**: カテゴリA 7ファイルに対し「`request_user_input` を含む行が canonical-note パターン（`Plan mode 限定.*使わない`）にマッチしない行がゼロ」を grep で機械確認（例: `grep -n request_user_input <file> | grep -v 'Plan mode 限定'` が空。commit/handoff は全ヒットが空になる）
- [ ] **iterate L216 と「Do not block on Large」Important Rule** が headless で Large を自動続行しない方針へ更新され、L74/100/213 と矛盾しない
- [ ] カテゴリB 4ファイルの `request_user_input` 言及が「会話ターンでの選択肢提示」概念へ更新されている（plan-reviewer L67 keyword list / team-cycle L101 keyword list は検出シグナル語なので UI/UX 検出が壊れない形で置換）
- [ ] カテゴリA の各スキルに headless/exec 降格ルールが1文以上明記されている（対話本質 brainstorm / problem-solving は「対話不能を報告して中断」の形で明記）
- [ ] **issue の headless 安全性**: plan / cycle / close が slug 未指定時に自動選択せず中断する旨が明記されている
- [ ] 保護対象12スキルの diff がゼロ（`git diff --stat` で対象外であることを確認）
- [ ] tool-mapping.md L14 が無変更
- [ ] **`python3 scripts/validate_repo.py`（引数なし）が「✓ 全チェック合格」**（Codex 側のみの変更なので sync 検査は Claude 側 sha を見て合格する。`--update-manifest` は本タスクでは no-op のため必須ではない。実行する場合は事前に引数なし検査で既存ドリフト無しを確認し、実行後 `git diff codex-skills/sync-manifest.json` が空であること）
- [ ] （推奨・任意）修正後の代表スキルを Codex 敵対レビューにかけ request_user_input 起因の指摘が解消されていること

## 🔒 Security (if applicable)

- [ ] headless/exec 降格の既定は必ず**安全側**（no-op / report-only / UNCERTAIN / 中断）。ユーザ確認が取れないまま破壊的操作へ進む経路を作らない
- [ ] **issue**: headless で issue を自動選択しない。plan / cycle / close は slug が引数で明示されない限り中断（任意 issue に plan→cycle を走らせてコードを書き換える経路を封じる）。create は重複検出ヒット時に中断
- [ ] **iterate**: headless で Large を自動続行しない。Large 判定・累積警告（N≥3）・Small→Large 昇格・halt escalation は、応答なし時に options をテキスト提示して**実装に進まず中断**（$plan 誘導）。L216 の既存 headless 例外規定と Important Rule「Do not block on Large」も同方針へ更新し矛盾を残さない
- [ ] **team-cycle との非対称性を意図的に区別**: team-cycle L240 のレビューコメントゲートは cycle ファミリー（headless-by-design、CLAUDE.md「cycle は確認プロンプトを出さず全自動」）の一部であり、チーム合意済み計画の実行なので headless デフォルト「続行」でよい。iterate/issue の「破壊的操作への未確認エスカレーション」とは性質が異なる点を実装時に取り違えない

## 📊 Progress

| Step | Status |
|------|--------|
| Tests (機械検証: grep + validate_repo.py) | 🟢 |
| Implementation | 🟢 |
| Commit | 🟢 |

**Legend:** ⚪ Pending · 🟡 In Progress · 🟢 Done

---

**Next:** Write tests → Implement → Commit with `claude-skills:commit` 🚀
