# goal-loop verify の追加ファイル検出漏れ修正（oracle-gaming 抜け道の封鎖）

**Cycle ID:** `20260708215304`
**Started:** 2026-07-08 21:53:04
**Status:** 🔵 Implementing
**Issue:** 20260708202143_goal-loop-verify-add-detection-gap

---

## 📝 What & Why

`skills/goal-loop/scripts/goal_loop.py` の CLI `verify`（`cmd_verify`）が、lock 後に oracle ディレクトリへ**新規追加されたファイルを検出しない**。純関数 `verify_oracle_integrity` は追加を検出できるのに、CLI が `current` を manifest のキーからのみ再構築するため、追加ファイル（manifest に無いキー）が純関数に渡らない。これは共有契約 `convergence-pattern.md` の「変更・削除・**追加**をすべて検出」宣言と矛盾し、lock 後に `conftest.py`（失敗握りつぶし fixture）等を仕込む oracle-gaming の抜け道を残す。maker/checker 分離とハッシュロックの安全性が破れるため、これを封鎖する。

本修正により、SKILL.md L117 の合理化防止表「skip の追加は oracle_files の改変。検出されて halt する」および契約 §3.3・§4.2 の「追加をすべて検出」が、**ディレクトリ形式で lock された oracle_files について**初めて CLI 実装で真になる（現状これらは純関数レベルの宣言に留まり CLI では偽）。すなわち本修正は既存ドキュメント／契約の主張を実装に一致させる作業でもある。

## 🎯 Goals

- `cmd_verify` が oracle の入力 root（ディレクトリ形式）を再走査して `current` 集合を再構築し、追加ファイルを `oracle_tampered`（exit 2）として検出する
- 除外ルールを oracle 実行の一時生成物（bytecode + hidden ディレクトリ／ファイル）へ拡張し、verify を lock と一致させて iteration≥2 の誤検出（false oracle_tampered）を防ぐ
- 旧形式・不正 manifest を fail-closed（exit 2）で拒否し、弱挙動へのサイレント downgrade 経路を作らない
- `convergence-pattern.md` の宣言（追加検出）と CLI 実装を一致させる（現在コードの docstring は「非対称は仕様」と正当化しているが、これを是正）
- CLI レベルの追加検出 end-to-end テスト + `parse_manifest_envelope` 純関数テストを追加し、回帰を防ぐ

## 📐 Design

### Files to Change

```
skills/goal-loop/scripts/
  goal_loop.py       - manifest を v2 形式 {version,roots,files} で出力（cmd_lock）。
                       純関数 parse_manifest_envelope を新設して v2 を型検証（fail-closed）。
                       cmd_verify が roots を再走査して current を再構築。
                       除外ルールを oracle 実行生成物へ拡張。docstring 是正。
  test_goal_loop.py  - parse_manifest_envelope の単体テスト（純関数）+ CLI end-to-end
                       追加検出/削除/変更/cache 誤検出なし/不正 manifest fail-closed。
                       既存 test_lock_excludes_pycache_and_pyc を manifest["files"] 参照へ更新。
```

> **Codex 反映**: `codex-skills/goal-loop/scripts/{goal_loop.py,test_goal_loop.py}` は Claude 側の symlink 共有のため**自動反映**（追加作業不要）。本修正は SKILL.md を**変更しない**（CLI 引数サーフェス `lock {files} --out M` / `verify M` は不変）。`codex-skills/goal-loop/SKILL.md` は sync-manifest 追跡の実体コピーだが、Claude 版 SKILL.md 無変更のため **sync-manifest 更新は不要**。この判断は実装後に `validate_repo.py` が「未同期」で fail しないことで裏取りする。
>
> SKILL.md を触らない代わりに、SKILL.md 側で対処すべき 2 点（追加検出のディレクトリ粒度限界の明記 / implementer への manifest 編集禁止の追記）は本計画の «Known Limitations & Follow-up» に整理し、別 issue の候補として残す（スコープを CLI 層に閉じる）。

### Key Points

- **manifest フォーマットの拡張（v2）**: `cmd_lock` が「入力 root（`lock` に渡された生の引数列 = `ns.files`）」と「解決済みファイルハッシュ」の両方を保存する。新構造:
  ```json
  {
    "version": 2,
    "roots": ["tests", "check.sh"],
    "files": { "tests/a.py": "sha256...", ... }
  }
  ```
  純関数 `oracle_manifest` / `verify_oracle_integrity` は**変更しない**（issue 明記のとおり純関数側は正しい）。フォーマット拡張は CLI 層に閉じる。

- **エンベロープ検証を純関数へ切り出す（テスタビリティ）**: v2 の型検証・(roots, files) 抽出を CLI に直書きせず、副作用のない純関数
  ```
  parse_manifest_envelope(raw: dict) -> tuple[list[str], dict[str, str]]
  ```
  に切り出す。判定は**型まで厳密に**行う: まず `isinstance(raw, dict)` を確認し（**この dict ガードは必須** — manifest は KL#2 のとおり implementer 書込可能で、`null` / `[]` / `"s"` / 数値をトップレベルに書くと `json.loads` は成功し、続く `raw.get(...)` が `AttributeError → 未捕捉 → exit 1 fail-open` になる。これは「不正形式 manifest → exit 2」の明示約束の抜けになるため dict でなければ即 `ValueError`）、続いて `raw.get("version") == 2 and isinstance(raw.get("roots"), list) and isinstance(raw.get("files"), dict)` を満たさなければ `ValueError`（呼び出し側 `cmd_verify` が exit 2 に変換）。
  - **`json.loads` / `read_text` の配置**: `cmd_verify` では `Path(ns.manifest).read_text()` の `OSError`（manifest 欠落・読取不能）と `json.loads(...)` / `parse_manifest_envelope(...)` の `ValueError` を**まとめて exit 2 + stderr（invalid manifest）にマップ**する（`json.JSONDecodeError` は `ValueError` サブクラス。read_text の OSError は現行 L195 から存在する pre-existing な exit 1 経路だが、列挙フェーズと同じ fail-closed 方針でここも exit 2 へ揃える）。これで「manifest 欠落/読取不能」「壊れた JSON」「非 dict」「v2 型不正」がすべて fail-closed（exit 2）に統一され、exit 1 の取りこぼしを残さない。
  - これで「純関数は unittest で検証、CLI は薄い I/O」という本リポジトリの構成（`goal_loop.py` の他純関数群と同じ）を保つ。`cmd_verify` はこの関数を呼んで `(roots, files)` を得るだけに保ち、業務ロジックを glue に置かない（design-principles #2）。

- **v2-only + fail-closed（旧フラット形式フォールバックは廃止）**: manifest は 1 ループ実行内で `cmd_lock` 生成 → `cmd_verify` 消費される**揮発物**で、lock/verify は常に同一コード版で走る。よって旧フラット形式の manifest が verify に届く経路は原理的に存在しない。「旧挙動（追加検出なし）へのサイレント fallback」は (1) 死にコードであり、(2) implementer 作業ツリー内（`$WORK/.claude/tmp/...`）の manifest から `version`/`files` ラッパーを剥がすだけで verify を弱挙動へ **downgrade** できる攻撃面になる（本 issue の趣旨と逆行 = fail-open）。したがって**旧形式・不正形式は fail-closed（exit 2 + stderr で invalid manifest を明示）で拒否**し、legacy fallback は作らない。version フィールドは「読まれない装飾」ではなく `parse_manifest_envelope` の判定に実際に使う。

- **`cmd_verify` の current 再構築**: `parse_manifest_envelope` で得た `roots` を `_collect_paths(roots)` に渡して**ファイルシステムを再走査**し（lock と同じ除外ルールが自動適用される）、各ファイルを再ハッシュして `current` を構築、`files` と `verify_oracle_integrity` で突き合わせる。これにより：
  - 追加（current にあるが files に無い）→ 検出される（**本修正の主眼**）
  - 削除（files にあるが current に無い）→ 従来どおり検出
  - 変更（両方にあるがハッシュ相違）→ 従来どおり検出

- **削除・読取失敗・走査失敗の fail-closed 維持（列挙フェーズも含む）**: `_collect_paths` の**ファイル引数分岐は存在確認をしない**（`elif not _is_build_artifact(p): paths.append(p)`）。「ファイルを直接 lock → そのファイルを削除 → verify」経路では削除済みパスが返り、素朴に `read_bytes()` すると `FileNotFoundError` で exit 1（＝ oracle_tampered=2 でも ok=0 でもない中間状態）になり、SKILL.md L70 の「exit 2 = oracle_tampered」運用から外れる。対処は**2 フェーズとも**包む:
  - **再ハッシュフェーズ**: 各パスの `read_bytes()` を `try/except OSError` で包み、**読めなかったパスは `current` から除外**する（→ manifest にあって current にない = 削除として `verify_oracle_integrity` が exit 2 で検出）。削除・権限エラー・列挙後の race がここで tampered 側に倒れる。
  - **列挙フェーズ**: `_collect_paths(roots)` 呼び出し自体も `try/except OSError` で包む。`sorted(p.rglob("*"))` はジェネレータを即時実体化するため、symlink ループ・サブディレクトリ権限エラー由来の OSError は**再ハッシュ try の外＝列挙フェーズ**で送出され、放置すると cmd_verify→main を突き抜けて **exit 1 = fail-open**（implementer が oracle dir に symlink ループを仕込み、追加 symlink 報告前に verify をクラッシュさせて握りつぶす経路になる）。列挙で OSError が出たら **exit 2（走査不能 = tampered 相当）+ stderr で理由を明示**して fail-closed に倒す。

  ディレクトリ root は `rglob` が削除済みファイルを列挙しないので従来どおり自然に削除検出される。これで削除・権限・race・symlink ループ由来の例外がすべて fail-closed に統一される（計画が掲げる「例外は非 tampered と誤解させない」を実装配置と一致させる）。

- **除外ルールを oracle 実行生成物へ拡張（誤検出防止 — 必須）**: verify は**毎イテレーション oracle 実行の直前**に走る（SKILL.md Step 3 → Step 4）。iteration 1 の oracle 実行が locked root 配下に `.pytest_cache/` 等を生成すると、iteration 2 の verify（＝再走査）がそれを「追加ファイル」と見なし **false `oracle_tampered`（exit 2）でループを誤停止**する。現行 `_is_build_artifact` は `*.pyc` / `__pycache__` のみ除外で不足。追加検出を有効化する以上、除外を oracle 実行の一時生成物へ広げるのは必須。
  - **既定案（言語非依存 heuristic）**: 既存の bytecode 除外に加え、**hidden（`.` 始まり）ディレクトリ／ファイルを除外**する（`.pytest_cache` / `.mypy_cache` / `.ruff_cache` / `.hypothesis` / `.coverage` / `.git` 等をまとめてカバー）。テストランナーが hidden ディレクトリ配下を test/conftest として自動探索することは通常ないため、主脅威（`tests/conftest.py` = 非 hidden の `.py`）は依然検出される。
  - **判定は lock root からの相対パスで行う（重要 — 誤除外/空 manifest 回帰の防止）**: hidden 判定を `p.parts`（絶対パス全体の要素）に適用すると、lock root が絶対パスで解決され祖先に hidden 要素（`~/.config` / `~/.cache` / `~/.claude` / 一時ディレクトリ等）があると locked 配下の**正当ファイルまで全除外され manifest が空化**する（＝ verify が常に ok=True の無防備・fail-open 回帰）。既存 `_is_build_artifact` の `"__pycache__" in p.parts` は祖先にその literal が現れないため顕在化していないが、hidden 要素は日常的に祖先に現れるため衝突確率が桁違いに高い。よって hidden 除外は **lock root からの相対パス要素**（ディレクトリ root: `sub.relative_to(root).parts` / ファイル root: `basename` のみ）で評価する。bytecode 除外も同様に相対評価へ揃える（`.pyc` suffix 判定は絶対/相対不問なので不変）。
  - **残存リスク**: hidden ディレクトリ内に gaming ファイルを仕込む経路は除外され得る（低実効性のため Known Limitations に記載）。より堅牢な代替として `.gitignore` 尊重（oracle 生成物は概ね gitignored / gaming source は非 gitignore）があるが、stdlib に gitignore matcher が無く実装コストが高いため v1 は heuristic を採る。
  - lock と verify は同一 `_collect_paths` を共有するので、除外ルールの変更は**片方だけ拡張しても自動一致**する（DRY）。

- **docstring 是正**: モジュール docstring の「非対称性の明記」ブロック（現行 L27-35）を、「verify は roots を再走査して追加も検出する（ディレクトリ形式 root の場合）」内容に書き換える。契約と乖離した「非対称は仕様」正当化コメントを残さない。

- **path policy（cwd 前提の維持、正規化は追加しない）**: `roots` は lock の生引数を `str(Path(arg))` で**そのまま**記録する（相対はそのまま／絶対はそのまま。既存の `files` キーが `str(p)` で保存されるのと同一挙動で、既存 CLI テストが tempfile の絶対パスを lock し tamper stderr に絶対パスを期待する挙動を壊さない）。新たな cwd 正規化は導入しない。SKILL.md の「lock / verify は同じ cwd（プロジェクトルート）で実行」前提を踏襲する（別 cwd からの verify は従来どおり相対 root 解決がずれる — これは既存制約で本修正のスコープ外）。

## ✅ Tests

**純関数（`parse_manifest_envelope`）— unittest で直接検証:**
- [ ] 正常 v2（`{version:2, roots:[...], files:{...}}`）→ `(roots, files)` を返す
- [ ] `version != 2` / `version` 欠落 → `ValueError`
- [ ] `roots` が list でない・`files` が dict でない → `ValueError`
- [ ] 旧フラット形式（パス→hex のみ、`version`/`roots` 無し）→ `ValueError`（fallback せず fail-closed）
- [ ] 非 dict トップレベル（`null` / `[]` / `"s"` / 数値）→ `ValueError`（`isinstance(raw, dict)` ガード。AttributeError で exit 1 に落ちない）
- [ ] `files` という名の oracle ファイルを含む旧 manifest が来ても型判定で誤分類しない（`version` が無ければ弾く）

**CLI（end-to-end、subprocess）:**
- [ ] **追加検出**: ディレクトリを lock → 配下に新規 `.py` 追加 → `verify` exit 2 かつ stderr に追加パス（現状 `test_added_file_is_tampered` は純関数のみ担保。CLI 経路を新規にカバー）
- [ ] **空ディレクトリからの追加**: ファイル 0 個のディレクトリを lock（`files` 空 / `roots` あり）→ 1 本追加 → `verify` exit 2（本修正の効果が最大のケース）
- [ ] **変更検出（回帰）**: 既存 `test_lock_verify_roundtrip_and_tamper_detection` が v2 フォーマットでも合格する（構造非依存のため無改変で緑を確認）
- [ ] **削除検出（ディレクトリ root、回帰）**: ディレクトリ lock 後にファイル削除 → `verify` exit 2 で削除パスを列挙
- [ ] **削除検出（ファイル root）**: ファイルを直接 lock → そのファイルを削除 → `verify` が exit 1 でクラッシュせず exit 2 で削除として検出（`try/except OSError` で fail-closed）
- [ ] **oracle 生成物の誤検出なし**: ディレクトリ lock 後に `__pycache__/*.pyc` と `.pytest_cache/`（hidden ディレクトリ配下ファイル）が生成されても `verify` exit 0（拡張除外ルールが再走査でも効く）
- [ ] **hidden 祖先パスで空 manifest 回帰しない**: 祖先に hidden 要素を含む絶対パス（例: `<tmp>/.hidden/tests/`）配下を lock → 配下の非 hidden ファイルが `files` に載る（相対パス評価により祖先 hidden で全除外されない）→ 追加検出も効く
- [ ] **列挙フェーズの走査失敗も fail-closed**: locked ディレクトリ配下に symlink ループ（`tests/loop -> tests`）等を仕込み `rglob` が OSError を投げる状況で、`verify` が exit 1 でクラッシュせず exit 2 + stderr（走査不能）で halt する（環境依存で symlink ループ再現が難しい場合は、列挙を担う内部関数へ OSError を注入する単体テストで代替可）
- [ ] **不正 manifest は fail-closed**: 旧フラット形式 / `roots` 欠落 / 型不正 / 壊れた JSON / 非 dict トップレベルの manifest を `verify` に渡すと exit 2 + stderr で invalid を明示（exit 1 クラッシュもサイレント弱挙動 fallback もしない）
- [ ] **既存テスト更新**: `test_lock_excludes_pycache_and_pyc` を、トップレベルキー（v2 では `version/roots/files`）ではなく `manifest["files"]` を検査するよう更新（更新しないと v2 化で必ず FAIL）

**回帰確認:**
- [ ] 純関数テスト（`test_added_file_is_tampered` / `test_combined_change_delete_add` 等）は無改変で全て緑のまま
- [ ] `python3 -m unittest` 一式が緑

## 🔒 Security (if applicable)

- [ ] oracle-gaming（テスト・検証定義を弱めて合格する）の抜け道封鎖が本 issue の主題。追加ファイル経路での握りつぶしを CLI で確実に検出する（**ディレクトリ形式で lock された root に限る** — 下記 Known Limitations 参照）
- [ ] 旧形式・不正 manifest は fail-closed（exit 2）で拒否。弱挙動へのサイレント downgrade 経路を作らない（本節の最重要項目 — legacy fallback 廃止で達成）
- [ ] 除外ルールの拡張は「oracle 実行が生成する一時生成物（hidden ディレクトリ・bytecode）」に限定し、主脅威の非 hidden `.py`（`conftest.py` 等）は検出対象に残す。新たな信頼境界の緩和を導入しない
- [ ] `verify` の**列挙（`_collect_paths`）と読取（`read_bytes`）の両フェーズ**を `try/except OSError` で fail-closed（exit 2）にする。symlink ループ由来の rglob 例外を exit 1 で握りつぶす fail-open 経路を塞ぐ
- [ ] 契約 §3「ループ内で manifest を更新する API を存在させない」不変条件を維持（`cmd_lock` はループ開始時 1 回・コントローラ実行。ループ内 manifest 更新 API は新設しない）
- [ ] manifest の `roots` はパスのみ（機密情報を含めない）

## ⚠️ Known Limitations & Follow-up（本修正のスコープ境界）

本修正は CLI 層に閉じるため、以下は封鎖しきれない残存事項として明記する（誤った安心を与えないため）。SKILL.md／契約側の対処は別 issue の候補とする。

1. **追加検出はディレクトリ粒度の root にのみ有効**: `roots` は lock の生引数。`lock tests/` のようにディレクトリを渡せば `tests/conftest.py` の新規追加を検出できるが、shell glob で `tests/*.py` が個別ファイル列に展開されて渡ると `roots` はファイル列となり、兄弟 `conftest.py` の追加は検出できない。SKILL.md Step 1.2 は既に「テストディレクトリは全体を含めるのが既定」と推奨しており主経路は守れるが、**「追加検出はディレクトリ形式 root 限定」を SKILL.md／docstring に明記する**のは follow-up（本 PR は docstring に 1 行残す程度に留め、SKILL.md 本体は触らない = Codex sync を発生させない）。

2. **manifest 自体の完全性は本修正の射程外（pre-existing）**: manifest は `$WORK`（implementer 作業ツリー内）に置かれ、CLI は manifest を信頼して読む。これは v2 で `roots` を足したことで「roots を surgical に個別ファイル列へ書き換えて走査範囲を縮小する」レバーが1つ増えるが、**「manifest が implementer 書込可能」という信頼前提は v1 フラット形式（記録済み hash を書き換えられる）から既に存在する**。根本対処は manifest を controller 専有ディレクトリへ退避 or implementer プロンプト（SKILL.md Step 3.6）に `.claude/tmp/**`／manifest 編集禁止を追記すること。いずれも SKILL.md／アーキテクチャに関わるため **follow-up issue** とし、本 PR では fail-closed 化（残存レバーの一部を塞ぐ）に留める。

3. **除外ルールの gaming 残存（hidden 配下 / bare .pyc）**: (a) hidden ディレクトリ配下に置かれた gaming ファイルは除外され得る（テストランナーが hidden 配下を自動探索しないため実効性は低い）。(b) `_is_build_artifact` は `__pycache__` 外の bare `.pyc` も除外し続けるため、bare `.pyc` を sourceless import させる gaming 経路も理論上残る（Python 3 で bare `.pyc` を conftest 等として自動 import させるのは困難で実効性は低い）。除外を `__pycache__/*.pyc` に限定して bare `.pyc` を検出対象へ戻す選択肢もあるが、既存テスト（`stray.pyc` 除外を仕様化）との兼ね合いで v1 は現行踏襲とし残存を開示する。より堅牢な `.gitignore` 尊重（denylist より広く、gaming source は非 gitignore で検出可）は stdlib に matcher が無く実装コストのため v2 スコープ外。除外方式の候補は「hidden heuristic（採用・1ルールで全 cache ツールを DRY にカバー）／既知 cache ディレクトリ名の明示 denylist（より narrow だが列挙保守が必要）／`.gitignore` 尊重（最も堅牢だが高コスト）」の3案で、v1 は DRY 性を優先して hidden heuristic を採る。

4. **非 hidden の oracle 生成物による誤停止 / 隠し oracle ファイルの検出漏れ（追加検出の原理的トレードオフ）**: 追加検出は「re-scan で manifest 外を tampered 扱い」する以上、locked ディレクトリ配下に oracle 実行が**非 hidden**の生成物（`tests/report.html` / `coverage.xml` を dir root 直下に出力する類）を書くと iteration≥2 で false `oracle_tampered`（exit 2）= ループ誤停止になる。hidden + bytecode 除外は `.pytest_cache` 等の主要ケースを潰すが網羅ではない。運用上は「locked ディレクトリは出力物を持たない構成を推奨」または「該当ケースはファイル粒度 lock（ただし追加検出は失う）」で回避する。逆に、正規の隠し oracle ファイル（テストが読む `.config` 等）への**変更**も hidden 除外で検出対象外になる副作用がある（稀）。いずれも「正当な生成 vs gaming の構造的区別が heuristic 依存」という追加検出機能に内在する限界。

## 📊 Progress

| Step | Status |
|------|--------|
| Tests | 🟢 |
| Implementation | 🟢 |
| Commit | 🟡 |

**Legend:** ⚪ Pending · 🟡 In Progress · 🟢 Done

---

**Next:** Write tests（純関数 `parse_manifest_envelope` → CLI end-to-end）→ Implement → `python3 -m unittest`（goal_loop テスト一式が緑）→ `python3 scripts/validate_repo.py`（symlink 自動反映・SKILL.md 無変更ゆえ未同期 fail が出ないことを確認）→ Commit with `claude-skills:commit` 🚀
