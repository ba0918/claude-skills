# Changelog

claude-skills プラグインのバージョン履歴。

変更は PR で `## Unreleased` へ追記する。**PR では version を bump しない** — 並走する PR が
揃って同じ番号を名乗り、マージ順に依存した manifest 衝突が必ず起きるため。リリース時に
`## Unreleased` を `## <version>` へ改名し、`.claude-plugin/plugin.json` /
`.claude-plugin/marketplace.json` / `.codex-plugin/plugin.json` の 3 manifest を揃えて bump する
（マーケットプレイスがスキル変更を認識するのは version bump 時のみ）。

## Unreleased

worktree 分離の共有契約と satellite artifact transport を導入した（issue #93 正本、#105 の
stale satellite ガード、#92 の parallel-cycle 適用。進捗の transport は #93 が #92 を上書き）。
tracked な `.agents/workspace.yml`（`isolation: worktree | inplace`、不在は `inplace`）で
workspace policy を店舗 policy から分離し、外側 orchestrator が ingress（pinned plan の複製と
run-scoped capability の発行）→ 委譲 → 全 terminal path での collect → merge・検証後のみ
publish → 証跡付き cleanup という transaction lifecycle を所有する。satellite からの durable
write は linked-worktree 判定と live capability の両方を要求して fail-closed にし、
singleton（status.md / session-history.md / derived index）の合成は main-tree orchestrator に
固定した。復旧の入口は `/claude-skills:artifacts recover --run-id {run_id}` に一本化し、
拒否・conflict・中断の診断は閉じた六行フォーマットへ統一した。`cycle` / `iterate` /
`parallel-cycle` / `github-issue` / `plan-implement` が同一の解決済み inner context を中継し、
入れ子の worktree 生成と policy 再解決を禁止する。`validate_repo` は存在する場合のみ
workspace policy を機械検証する（不在は正）。

- `skills/shared/references/workspace-isolation.md`（新規）
- `skills/shared/references/artifact-store.md`
- `skills/shared/scripts/workspace_isolation.py` / `test_workspace_isolation.py`（新規）
- `skills/shared/scripts/satellite_transport.py` / `test_satellite_transport.py`（新規）
- `skills/shared/scripts/artifact_store.py` / `test_artifact_store.py`
- `skills/artifacts/SKILL.md`（`recover` workflow / fresh-only policy 初期化）
- `skills/parallel-cycle/SKILL.md` / `references/merge-strategy.md`
- `skills/plan-implement/SKILL.md` / `fixtures.json`
- `skills/cycle/SKILL.md` / `fixtures.json`
- `skills/iterate/SKILL.md` / `fixtures.json`
- `skills/github-issue/SKILL.md` / `fixtures.json` / `references/worktree-cycle.md`
- `skills/brainstorm/fixtures.json`（bs-003 の git 前提を実体化）
- `scripts/validate_repo.py` / `test_validate_repo.py`

satellite transport 契約と実装の摩擦 5 点を修正した（issue #161）。`pinned_plan` のパス基準を
「repository-relative」から「store-relative」へ統一（7 箇所）、capability 消費エッジを lifecycle
表に明記、delegation result ファイルの worktree 所在を state 分類に追加、iterate 手順 7 の
「revoked」を「non-live (consumed or revoked)」へ修正、iterate Phase 5 に worktree モードの
衛星経由書き込みを明記した。相互参照テストを 3 件追加。

- `skills/shared/references/artifact-store.md`
- `skills/shared/references/workspace-isolation.md`
- `skills/iterate/SKILL.md`
- `skills/cycle/SKILL.md`
- `skills/plan-implement/SKILL.md`
- `skills/github-issue/references/worktree-cycle.md`
- `skills/shared/scripts/test_workspace_isolation_contract.py`

`github-issue` の GitHub 操作を `gh` CLI 固定から18個の意味的 transport operation へ分離した
（issue #123）。既定の `github_transport=auto` は `gh` がインストール済みなら従来経路を維持し、
`gh` 自体が存在しない場合だけ接続済み GitHub integration へフォールバックする。
`gh` の認証・権限エラーでは backend を切り替えず `security` として fail-closed し、明示指定した
transport または全 transport が利用不能な場合だけ `tool_missing` とする。Codex review、secret
scanner、ラベル状態機械、4条件の merge gate は transport の外側に維持した。

- `skills/github-issue/SKILL.md`
- `skills/github-issue/references/gh-commands.md`
- `skills/github-issue/references/polling-adapter.md`
- `skills/github-issue/references/config-defaults.md`
- `skills/github-issue/references/codex-review-loop.md`
- `skills/github-issue/references/secret-scanner.md`
- `skills/github-issue/fixtures.json`

## 1.70.0

品質ゲート契約 v1（issue #143 の 4 作業単位）と #86 の hooks 配送レールをまとめて配布する
リリース。README の rules 節を hook 2 本構成へ追随させ、品質ゲート契約の紹介節を追加した
（`README.md`）。

品質ゲート契約 v1 の想起層アダプタ第 1 号として、SessionStart hook
`hooks/inject-quality-gate.sh` を新設した（issue #143 の v1 作業単位 4/4）。#86 で敷いた
hooks 配送レールに 2 本目の command として後乗りし、契約の存在・3 正本のパス・「公開型の
状態遷移には対象 SHA × 発効契約版に束縛された検証証跡が要る」という事前条件の要旨だけを
注入する。skill-routing（正本 47 行を全文 cat）と違い契約は約 230 行あり、全文注入は常駐
コンテキスト予算を圧迫するため、本文を複製しないポインタ注入とした（アダプタの責務は
SessionStart = 語彙配布に限定。UserPromptSubmit の閾値判定・実行直前の機械検証は v1 対象外
— 2026-07-28 壁打ちの責務分割裁定どおり）。契約 md を含まない配布形態では沈黙して exit 0
し、セッション開始を壊さない。validate_repo チェック 21 の「hook スクリプトが参照する正本の
実在」検査は 2 本目の出現に伴いスクリプト→正本のマッピングへ一般化した。

- `hooks/inject-quality-gate.sh`（新設）
- `hooks/hooks.json`（SessionStart に 2 本目の command を追加）
- `scripts/validate_repo.py`（チェック 21 の正本実在検査をマッピング化）
- `scripts/test_validate_repo.py`（quality-gate 正本欠落 / スクリプト不在時スキップの 2 テスト追加、fixture を 2 hook 構成へ更新）

品質ゲート契約 v1 の適合プロファイル第 1 号 `skills/shared/references/skill-repository-profile.md`
を新設した（issue #143 の v1 作業単位 3/4）。汎用契約 §6 の 3 層設定の中間層で、自然言語スキル
リポジトリという 1 ドメインについて最低証拠・必須義務・弱体化禁止リストを確定する。汎用契約の
発火表を本ドメインの変更種別（スキル指示文書 / 共有契約 / バリデータ / 薄いコマンド / 配布
manifest）で具体化し、機械検査が既にカバーする義務を semantic review へ二重計上しない帰属規則、
および発火率・採用率のように運用測定でしか顕在化しない欠陥型を review 義務から外して運用センサー
へ回す routing を定めた（根拠は spike #142 実測）。semantic 側の比重が高いというドメイン特性は
汎用契約ではなく本プロファイルに置く（2026-07-28 壁打ちの裁定どおり）。証跡へのプロファイル束縛は
v1 verifier が profile 非 null を拒否する現行仕様と矛盾しないよう、v2 の profile 対応 verifier
までは定義のみの先行宣言であることを明記した。このリポジトリは本プロファイルの規範的リファレンス
ではなく適合標本の 1 つである。

- `skills/shared/references/skill-repository-profile.md`（新設）

品質ゲート契約 v1 の縦切り 1 本 `verified(対象SHA, 契約版) → publishable` を機械検証可能にした
（issue #143 の v1 作業単位 2/4）。証跡レコードの schema（状態ごと 1 JSON、対象 SHA × 公開済み
契約版へのバインド、grounds 必須）を `skills/shared/references/evidence-format.md` に定義し、
検査スクリプト `skills/shared/scripts/evidence_check.py` が publishable 可否を exit code で返す
（0 = publishable / 1 = 否定判定 / 2 = 検査自体が実行不能）。証跡不在・失効（SHA 不一致）・無効
（契約版が公開版に解決しない、record 破損）はすべて否定判定に落ちる fail-closed 設計で、
spike #142 の実測で 3 レビュアーが指摘した「対象 0 件で黙って緑になる」型の欠陥（vacuous pass）を
構造的に排除した。証跡の置き場所は artifact store の `reviews` 配下（Git 追跡外）——証跡をコミットに
含めると束縛先の SHA 自体が変わる鶏卵になるため、追跡外は要件である。

- `skills/shared/references/evidence-format.md`（新設）
- `skills/shared/scripts/evidence_check.py`（新設）
- `skills/shared/scripts/test_evidence_check.py`（新設）

品質ゲート契約 v1 の正本 `skills/shared/references/quality-gate-contract.md` を新設した
（issue #143 の v1 作業単位 1/4）。オーケストレーション運用で実測された「PR 前に品質ゲートを
通さない」失敗に対し、hook という機構ではなく保証条件を正本として標準化する 3 層構成
（正本 / 強制アダプタ / 想起アダプタ）の最上層にあたる。`machine_verified ⊥ semantic_reviewed
→ publishable` の状態機械、証跡の 対象版 × 契約版 バインドと失効規則、独立性の 4 性質分解、
プロファイル導出型のレビュー義務、状態機械式の収束条件を定義する。観点契約の精緻化を中程度で
止め「影響先集合の完全性」を弱体化禁止にした根拠、および運用実測でしか顕在化しない欠陥型を
静的レビューの義務から外した根拠は、spike #142 の実測（2026-07-28、素レビュー vs 契約駆動
レビューの検出力比較）にある。縦切り検証スクリプト・適合プロファイル・想起アダプタは後続の
作業単位として分離した。

- `skills/shared/references/quality-gate-contract.md`（新設）

`rules/skill-routing.md` が標準インストール経路のどれにも乗っておらず、Plugin 利用者に
想起ルーティング表が届かない状態だった（issue #86）。trigger-eval では 138 ケース全問正解の
弁別性がある一方、実セッション 30 日間の自発発火は 68 プロンプト中 11 件（16%）で、
差分は「会話として自然に返せる指示ではスキル照合が走らない」想起の問題である。SessionStart
hook（`hooks/hooks.json` + `hooks/inject-skill-routing.sh`）を追加し、startup / resume /
clear / compact / fork の各セッション開始時に正本をそのまま stdout 注入する（本文の複製なし）。
hook が壊れても CI が緑のまま注入だけ黙って止まる状態は、validate_repo.py のチェック 21
（hooks.json パース / command 実在・実行ビット / 正本実在）で塞いだ。issue は「チェック 18」
と指定していたが採番が 20 まで進んでいたため 21 として実装した。

cycle の Delegation result relay に、共有契約が明記を要求している role-specific values
（timeout minutes / redelegation limit / optional viewpoints）が書かれていなかった（issue #58）。
実害として、N=10 分の契約に対し約 1 分で委譲を見切って inline へ倒れ、委譲結果の着弾 1 秒前に
取りこぼした回帰評価がある。裁定（2026-07-28）に基づき共有契約の既定 N=10 分をそのまま採用し、
redelegation limit は pillar 2 の「1 視点 1 回」、optional viewpoints は無しと明記した。
cycle の実測が溜まって別値が正当化されたら改定する。

SI-S001（参照チェーン深度）が同一の参照エッジを SKILL.md 側のリンク出現回数だけ重複出力し、
finding が 4.1 倍（raw 329 / distinct 80）に膨らんでいた（issue #110）。重複分は `where` も `what` も
完全に同一で `id` だけが違い、読み手が区別できる情報を持たない。raw は issue 起票時の実測で 323、
#119 時点で 325、本修正の直前には 329 へ動いていた（#83 が同一 reference へのリンクを 2 本追加した
だけで +4）——リンクを足すたび findings が水増しされる、この欠陥の生きた実例である。一次参照の収集を resolved パスで
一意化し、同じ reference を何回リンクしても各エッジを 1 回だけ数えるようにした。rule-catalog の
SI-S001 detail にも同旨を明記。SI-S001 は 329 → 80 件（raw = distinct）、他ルールの増減なし。

github-issue の Cycle Workflow が主チェックアウトの HEAD から直接 `git switch -c` しており、
別セッションが feature ブランチで作業中に `cycle N` を起動すると無関係コミットが PR に混入する
状態だった（issue #83、実害未遂）。分岐起点を `origin/{default_branch}`（`gh repo view` で毎回解決、
`main` 決め打ち禁止）に固定し、ワークフロー全体を `gh-issue-{N}-{timestamp}` 命名の専用 worktree 内で
実行する契約に変更した。主チェックアウトの HEAD・ブランチ・インデックスには一切触れない。
worktree は成功・失敗の双方で撤去し、cleanup-spec の orphan 検知はクラッシュ時の安全網に位置づけ直した。
lockfile 相互排他と dirty チェックは採らない（片側しか参加しない排他は排他ではなく、分離後は
主チェックアウトの汚れが無関係になるため）。非既定ブランチ上から起動しても PR diff に無関係コミットが
混入しないことの検証手順を Step 4 に明記した。

SI-S003（prose 肥大）の見出し分類語彙に英語の `flow` が無く、`## Flow` を見出しに持つ
plan-refine が 85/85 行 (100%) という構造的に成立し得ない値で誤検出されていた（issue #119）。
skills/ 全文書の英語化で `## フロー` が `## Flow` になった際、検出器側の語彙が追従して
いなかった。`_WORKFLOW_KEYWORDS` へ `flow` を追加し、rule-catalog の SI-S003 detail の
語彙列挙を実装と同期した。SI-S003 は 11 → 10 件になり、消えるのは plan-refine の誤検出
1 件のみ。他ルール・他スキルの finding に増減は無い。

## 1.69.0

plan が 1 件のときだけ worktree 分離が失われていた（issue #84）。`parallel-cycle` は各 plan を
独立した worktree で実行するが、1 plan のときだけ `claude-skills:cycle` へ fallback し、呼び出し元の
作業ツリーで直接コミットしていた。**分離の有無が plan の件数という無関係な要因で決まる。**
polling 経路では、そのティックで ready だった issue がたまたま 1 件だったかどうかで分離が変わる。
1 plan でも通常経路（worktree 作成 → delegate → マージ）へ流す。

**Step 0.3 をスキップする挙動も併せて廃した。** 従来の本文は「downstream の cycle が必要なら plan を
作る」と書いていたが、`cycle` にその工程は無い。パスが無ければ最新の未完了 plan を自動選択し、
無ければ abort する。しかも worktree の artifact store は Git 無視で**空**なので、生の `$ARGUMENTS` を
渡す delegate は毎回 abort する。1 plan でも Step 0.3 で plan ファイルを生成し、そのパスを delegate へ
渡す。delegate は `plan-implement` ではなく `cycle` を呼ぶ（1 件でも refine ゲートを通すため）。

Phase 1 は引き続き飛ばす（1 件に交差は無い）が、Phase 1 でしか確定しない実行状態を明示的に引き継ぐ
ようにした。**Group 1 = `[A]` / `{N}` = 1 / `{M}` = 1 / 依存なし。** Phase 3 のマージ順と Phase 4 の
`Groups:` 行がこれを読むため、値が存在しないと表示が未定義になる。result の `Plan batch` は Step 0.3 の
`{timestamp}`、`Plan Files` は生成した 1 本のパスで、他の自然言語モード実行と同じになる。

表示挙動（DECOMPOSE RESULT 非表示・承認なし・headless）は従来どおり維持する。変えたのは実行の分離
だけである。

なお issue #84 の設計は「worktree 撤去は成功・失敗いずれの場合も行う」と書いていたが、これは
#104 で変更前の規定を指しているため、意図（1 plan を特別扱いしない）に従って現行の Step 3.4 と
同じ規則（マージ済みかつ post-merge test 通過のみ撤去、失敗時は保存）として実装した。

`parallel-cycle` の plan ファイル命名で、共有 timestamp が必須か個別可かが SKILL.md と
`decompose-guide.md` で食い違っていた（issue #111）。`{timestamp}` が「plan ファイルの一意化」と
「バッチの識別」という 2 つの役割を兼ねており、decompose-guide は前者だけを見て個別を許容し、
SKILL.md は後者を要求していた。共有を必須に統一し、両文書に理由を書いた。

**規定を強めた結果、それが守られない経路が 3 つ見つかった。**いずれも「規則は書いてあるが、
実際に書き込む委譲先には届いていない」という同じ形をしている。

- **plan ファイルが上書きし合う。** 命名は `{slug}` だけで区別する規定だったが、#104 で
  「2 つの plan が同じ slug を持ちうる」と明文化したばかりだった。同一バッチ内で slug が重なると
  同じパスへ解決し、並列生成なので上書きか同時書き込みになる。さらに Phase 1 が同じファイルを
  2 plan として読み、直交性判定を誤る。`{timestamp}_{plan_id}_{slug}.md` とし、一意性は
  `{plan_id}` が負う（#104 の worktree 命名と同じ語彙）
- **「timestamp を 1 回だけ取得する」が委譲先に伝わっていない。** Step 0.3 の委譲プロンプトには
  timestamp も出力パスも含まれておらず、呼ばれる `claude-skills:plan` は自分で時刻を取る。並列
  起動が秒境界をまたぐだけで分かれる。呼び出し側が解決済みのパスを渡す形へ変えた
- **`status.md` が並列に書き換えられる。** 抑止規定は Phase 2 の内側にあり対象も「individual
  cycles」だったため、Step 0.3 の plan 生成は素通りしていた。`plan` は read-modify-write で
  セッションの abandoned 退避まで行うので、3 並列で更新消失・多重退避・履歴破損が起こりうる
  （issue #114）。抑止を全 delegate 対象へ広げ、両委譲プロンプトに実際に書き込んだ

抑止規定には「規則はここに置くが、効くのは**委譲先に言われた場所**だけである」ことを明記した。
この節にだけ書かれた規則は、これから書き込もうとしている者には届かない。

Step 4.3 の result ファイル名を `{base_plan_name}` から `{run_id}_parallel_result.md` へ変えた。
`{base_plan_name}` はどこにも定義がなく、バッチは result 1 つに対し plan が複数なのでどの plan 名も
代表にならない。plan ファイル直指定モードでは共有する要素も無い。run 由来にすると、失敗を直して
再実行したときに 2 本目の result が書かれ、最初に何が落ちたかの記録が残る。result には
`Run ID` / `Plan batch` / `Plan Files` を追加した。`Plan batch` は自然言語モードのみで、plan ファイル
直指定モードでは `external` とする（引数は既存ファイルでバッチ timestamp を共有しない）。

秒精度の timestamp は同じ秒の別 plan 生成と prefix が衝突しうるため、「バッチを再構築できる」とは
主張しない。timestamp はグループ化するだけで membership を証明せず、正本は result の `Plan Files` である。

`plan` 側に caller-supplied path / status 更新抑止の正式契約が無い点は #115 として分離した。現状は
委譲プロンプトの自然言語指示で上書きしており、優先関係を明示してある。

失敗した cycle の worktree が撤去され、診断に必要な状態が失敗時にだけ失われていた（issue #104）。
`parallel-cycle` は `Merge what succeeds, preserve what fails` と宣言していたが、`preserve the
branch` が守るのはコミット済みの内容だけで、未コミットの編集・テスト出力・`.agents/` の状態は
撤去とともに消えていた。実装フェーズ途中で落ちた場合は空のブランチが残るだけになる。

**失敗時は worktree を保存する。** 撤去前に診断情報を主ツリーへ退避する案は却下した。#93 が確定
させた衛星 store の収穫と二重の輸送機構になるうえ、退避は「何を退避するか」の事前列挙を要求し、
診断に必要なものは失敗の性質で変わるので列挙は必ず漏れる。列挙しない設計が可能なときに列挙する
設計を選ぶ理由がない。なお #93 の規定 6 は「失敗時は worktree を保存する（`parallel-cycle` の
既存ルール）」と書いており、**存在しないルールを既存と誤認して確定設計を組んでいた**。本変更で
その前提が実際に成立する。

**撤去のトリガは人間の確認に置き、時間や個数で自動撤去しない。** 自動撤去を入れると、この修正が
潰そうとしている「診断したいときには既に無い」がそのまま再発する。「ブランチがマージ済み」も
撤去の許可として扱わない。マージが証明するのはコミット済み内容の保全だけで、保存 worktree の
存在意義は**コミットされなかったもの**にある。

確認の置き場所は入力モードで分ける。**Step 0.2 が実際に走るとき（自然言語モードで 2+ plans に
到達した場合）だけ**、既存の Phase 0 承認プロンプトへ相乗りする。plan ファイル直指定・0 plan
終了・1 plan の headless fallback・その他 headless 経路では一覧を報告するだけで撤去しない。
掃除のためだけのプロンプトは開かない（在席者がおらず、プロンプトは停止と同義になる）。

**worktree / branch の命名規則を新設した。** 従来は命名規則が SKILL.md にも references/ にも
一切存在せず、実行ごとのモデル判断任せだった。保存 worktree はブランチをチェックアウトしたまま
残るため、git は同じブランチを別の worktree へ渡さない。plan 由来の名前だと同一 plan の再実行が
必ず失敗する。`parallel/{run_id}-{plan_id}-{slug}` とし、`{run_id}` は Phase 2 開始時に時計から
採る。`{slug}` は可読性のためだけで、一意性を slug に依存させない。

**成功時の撤去タイミングも Step 3.4 へ統一した。** SKILL.md は Phase 2 直後の撤去、
`merge-strategy.md` はマージ後の撤去と、変更前から食い違っていた。Phase 2 で撤去すると Phase 3 の
post-merge test が落ちて revert したときに worktree が既に無く、原因を説明できない。撤去対象は
「マージ済み **かつ** post-merge test 通過」に限定する。

衛星 store の収穫工程は本変更に含めない（#93 のスコープ）。ただし撤去を Phase 3 へ遅らせたことで、
収穫を撤去より先に置く余地が生まれている。

`parse_change_targets` の散文が 2 つの検査を混同していた（issue #95、#96 を集約）。擬似コードは
文字種チェックを `continue`（当該項目のみスキップ）、traversal / 絶対パスチェックを `MISSING`
（宣言全体を却下）と**別々の却下範囲**で扱うが、散文は両方を「validation」と呼んでいた。
文字種チェックが項目単位なのは、実際の issue 本文が `## 変更対象` に併記する注釈付き第 2 リスト
（`- a/b.md:170 — 直すもの`）を宣言として読まないための意図的な設計である。

この reference から実装する読み手が誤読すると、注釈付き項目が宣言ごと却下される。すると
`## 変更対象` に注釈を併記した issue（#78 自身がこの形）が軒並み Gate 0a の quiet skip に落ち、
`claude-auto` を付けた issue が原理的に 1 件も拾われなくなる。スキルは散文が実行される仕様なので
「擬似コードを読めば分かる」は緩和にならない。

**検査順序も明記した。** 注釈付き項目は両検査に該当しうる（`- ../b.md:170 — 直すもの` は空白も
`..` も含む）ため、順序が書かれていないと traversal を先に検査する実装が生まれ、上記の全滅が
そのまま再発する。

根拠の文も訂正した。宣言集合から 1 件落ちると Gate 0b の `plan_paths ⊆ declared_paths` は母集合が
縮んで**厳しくなる**。緩むのは Gate 0a 側で、`forbidden_path_globs` が落ちた項目を見られなくなり、
`impact_units` に渡すパスが減って**波及半径を過小評価する**。旧文の「allowed scope が広がる」は
理由づけの置き場所ごと誤っていた。

旧文末尾の「hostile body を `impact_command` の引数から締め出す」は削除した。項目単位の skip でも
当該パスはオラクルに渡らないため、「skip ではなく全体却下」の根拠になっていない。シェルメタ文字を
防ぐのは文字種チェックと `shell_quote_join` で、既に別途明記されている。

`skipped` ではなく `dropped` と書いているのは、`validate_repo.py` の契約語彙チェックが
coverage-ledger の `reviewed` / `skipped` / `unsupported` の共起で発火する偽陽性を避けるためである
（除外登録はスキル単位でゲートを無効化するので採らない）。隣接する bullet も同じ動作を `drops` と
呼んでおり語彙が揃う。

擬似コードと Gate ロジックは変更していない。影響 1 スキル 6 シナリオを process-queue 経路で実走し
critical 全 ○。

`workspace_lock` の fail-open が、既存の runtime 領域へ書けない環境で破れていた（issue #106）。
`claim()` が fail-open へ変換するのは `mkdir()` の `OSError` だけで、`.agents/runtime` が既に
存在すると `mkdir(exist_ok=True)` を通過して `_write_record()` へ進む。そこは
`FileExistsError` しか捕捉していなかったため、EACCES / EROFS / ENOSPC / EDQUOT が呼び出し元へ
そのまま抜けていた。

症状は「ロックが効かない」ではなく**実在しない `LOCK_HELD` で停止する**である。CLI 経路では
traceback を吐いて exit 1 になるが、契約は「非ゼロ終了は `LOCK_HELD` のときだけ」と規定して
いるため、`cycle` / `plan-implement` / `iterate` は空の holder を理由に開始前で止まる。
fail-open の意図と正反対の帰結になる。

`_write_record()` の `FileExistsError` 以外の `OSError` を `UNAVAILABLE` へ変換する。占有の
合図である `FileExistsError` は従来どおり別扱いのまま。stale 再取得側は元から `OSError` を
`UNAVAILABLE` にしており、初回作成経路だけが非対称だった。

**書き込みに失敗した作りかけの claim は削除しない。** 一度は「残すと次のセッションが実在しない
stale 回収を報告する」として削除する実装にしたが、Codex のレビューでレースが判明した。書き込み
失敗と後始末の隙間に別セッションが未完成レコードを stale 回収して自分の claim を publish でき、
そこで最終パスを unlink すると**生きた claim を消す**。これは本モジュールが唯一やってはならない
ことで、幽霊 `STALE_RECLAIMED` の警告 1 行より遥かに重い。作りかけは既存の「読めないレコードは
stale 扱い」経路が安全に回収する。この判断はテストで固定した。

契約側（`workspace-lock.md`）の fail-open 条件も「作成できない」だけでなく「作成できても
claim を書けない」を含む形へ広げた。テストは 4 件追加し、模擬は errno を直接指定する形にした
（`chmod` は #103 と同じ理由で uid 0 では no-op になる）。修正前のモジュールに対して新テスト
4 件が落ち、既存 26 件が通ることを確認済み。

`workspace_lock` の fail-open テスト 2 件が root 実行で必ず落ちる問題を直した（issue #103）。
検証の正本である `scripts/run_checks.sh` は `set -eu` かつユニットテストが最初のステージなので、
この 2 件の赤が構造ゲート 4 種（`validate_repo.py` / ledger check / translation parity / anchors）を
巻き添えで一度も走らせずに中断させていた。CI は非 root ランナーなので緑のまま通り、
`.github/workflows/validate.yml` が明文で置く「ローカルと CI の検証内容は常に一致する」という
前提が root 環境でだけ成立していなかった。

原因は実装ではなくテストの模擬手段にある。「runtime 領域を作成できない環境」を `chmod(0o500)` で
作っていたが、uid 0 に対して DAC の書き込みビットは効かないため模擬が no-op になり、
`.agents/runtime` の作成が普通に成功して `ACQUIRED` が返っていた。`.agents` を通常ファイルとして
置き `mkdir` を ENOTDIR で落とす形へ差し替えた。権限検査ではなくパス解決の失敗なので、
実行 uid によらず同じ fail-open 経路へ入る。アサーション本体と
`workspace_lock.py` は変更していない。

テスト名とヘルパー名を `unwritable` から `uncreatable` へ改めた。この 2 件は変更前から
`mkdir` の失敗経路（EACCES）だけを検査しており、既存の `.agents/runtime` へ書けない経路は
検査していない。`unwritable` を名乗ると書き込み不能もカバー済みだと読めてしまう。
書き込み経路には実際に fail-open の穴があり、issue #106 として切り出した。

`skipIf(os.geteuid() == 0)` で逃がす案は採らなかった。root は「たまたま特殊な環境」ではなく
このリポジトリの自走ループが実際に走る標準環境であり、そこでだけ fail-open 契約が
無検証になる。user namespace（`unshare -r`）で uid 0 を作って両方向を実測した
（修正前 = 2 件失敗 / 修正後 = 26 件 pass、非 root でも 26 件 pass）。

作業ツリーの占有ロックを常時 ON で導入した（issue #90）。中核の実装ループ
（`cycle` → `plan-implement` → `iterate`）は共有チェックアウトへ直接書き込み、他セッションが
そこで走っていないかを一切検査していなかった。2 セッションが同じツリーで進むと互いの編集を
上書きし、テストは相手の中間状態に対して走り、コミットは両者の変更を混ぜた単位で作られる。
どれも分かるのは後段で、原因の特定は難しい。唯一近いガードは `commit` のブランチガードだが、
これは占有ガードではなく、しかもコミット時点で発火する — 衝突はその遥か手前で既に起きている。

**設定不可の常時 ON とした。** コストは実質ゼロで、設定で切れるようにすると切った環境でだけ
事故が残り、ロックの意味が薄れる。

資源は**作業ツリーのパスであってブランチではない**。ロックを `.agents/runtime/workspace.claim`
に置くことで、runtime 領域が作業ツリーごとに別パスになる性質から粒度が自動的に決まる
（ハッシュもキー設計も不要）。同一チェックアウトなら別ブランチでも衝突し、別 worktree なら
同一ブランチでも衝突しない。claim の意味論（原子性・pid + started_at・0600・trap と孤児回収の
二段構え）は `polling-pattern.md` §6.3-6.4 が正本で、新契約は**参照するだけで再掲しない**。

**生きている claim は奪わない。** pid の権限エラーは「生存」扱いにする（シグナルを送れない
ことを死亡と誤判定すると他ユーザの claim を奪う経路ができる）。stale 再取得にはトークン照合を
入れ、2 つの再取得者が競合したときに両方が所有を主張しないようにした。実装にも表示にも
force / override の経路は存在しない。

`.agents/runtime/` を作成できない環境では警告 1 行で続行する（fail-open）。ロックは既存挙動への
追加であり、取れない環境で止めるとこれまで動いていた構成が動かなくなる。

claim するのは `cycle` / `plan-implement`（単独実行時のみ）/ `iterate` / `parallel-cycle`（主ツリー）
の 4 つに限定した。委譲時はトークンを delegate へ渡し、受け取った側は claim も release もしない。
`commit` / `plan` 等が claim しないことで、ネストによる自己デッドロックを構造的に防ぐ。
`validate_repo.py` の `CONTRACT_VOCAB` に登録し、4 スキルが契約を md リンクしていることを
機械的に要求する（リンクを外すと落ちることも確認済み）。

`.claude/` 配下を agent 生成物の置き場として参照していた 38 ファイル 122 行を、#75 で定義した
`.agents/tmp/` と `.agents/config/` へ移行した（issue #76）。共有契約は
「The namespace is provider-independent」を規定しており、provider 名入りのパスは違反である。
移行対象の実ファイルは存在せず（`git ls-files .claude/` は 0 件）、パス文字列の書き換えのみ。

一括置換にしなかった箇所が 3 種ある。**fixture の `source`** は「その資産をどこで捕獲したか」の
来歴で、書き換えると存在しなかった場所を指すことになるため残した。一方、同じ fixtures.json でも
**要件テキスト**（`中間ファイル置き場 .claude/tmp/sweep-fix/ を残していない` など）はスキル本体の
書き出し先が動く以上、移行しないと間違ったパスを検査する fixture になるので移行した。
**CHANGELOG の過去エントリ**は史実なので触っていない。**Claude Code の実体パス**
（`~/.claude/projects/` / `~/.claude/CLAUDE.md` / `.claude/rules` / `.claude/skills` /
`~/.claude/plugins/`）は監査対象・入力ソース・配置先であり `.claude/` のままが正しい。

再発防止に `validate_repo.py` のチェック19 を追加した。`skills/` 配下の md / py / json を走査し
`.claude/(tmp|review-rules|*-baseline.json)` を検出する。検出パターンを移行済みの 3 種に限定
することで実体パスを誤検出しない（誤検出するガードは無効化され検出力が 0 になる）。
`source` と `note` は過去の記録なので除外するが、除外は**行単位ではなく値単位**で行う。
行単位にすると 1 行へ複数キーが並んだとき同じ行の別キーまで見逃すためである。

`.gitignore` から `.claude/tmp` エントリを削除した。移行前のローカル `.claude/tmp/` が残っている
環境では untracked として現れるので、手元で削除するか `.git/info/exclude` で個別に無視する
（追跡対象ではない）。

パスは機械解釈されるトークンなので `--accept` せず、影響 6 スキル 17 シナリオを process-queue
経路で実走して critical 全 ○。自己申告の baseline_drift を manifest の baseline hash と
突き合わせて 17/17 一致。移行が効いていることは成果物で裏取りした（executor は `.agents/tmp/`
配下へ書き、`.claude/tmp/` への書き込みは 0 件）。

Agent Artifact Store 契約に **ephemeral 領域**（`.agents/tmp/`）と **config 領域**
（`.agents/config/`）の 2 節を追加した（issue #75）。契約が定義していた領域は artifacts と
runtime の 2 つだけで、使い捨ての中間生成物と、commit して共有する設定・受理済み baseline の
置き場が無かった。移行先が存在しなかったために provider 名入りの `.claude/` 配下パスが
残存しており、パス置換だけでは再発する。既存ルールは 1 つも変えない純粋な追加である。

ephemeral は常にマシンローカルで migration inventory と visibility 統制の対象外、かつ
**定義上いつ消えてもよい**（artifact と違い復元を期待されない）。3 つの領域を分ける軸は
**後で誰が読むか**に置いた。artifact は未来のセッション・レビュアー・他スキルが読み、runtime は
このホストの並行プロセスが読み、ephemeral は今走っているステップだけが読んでその後は誰も読まない。

config はここで唯一 **tracked**。受理済み baseline が clone に付いてこないと、新しい checkout の
たびにチームが裁定済みの finding が再報告されるためである。store policy の `.agents/artifacts.yml`
とは別物であることを明記した。あちらはストア自体の在り処の宣言で変更は migration 規律（7 段階）の
対象、こちらはスキルが読む通常の設定で変更は普通の編集である。混ぜると、トグル 1 つに migration
規律が掛かるか、逆に migration 規律が緩むかのどちらかになる。

`.gitignore` には `/.agents/tmp/` のみ追加した（`.agents/config/` は tracked なので追加しない）。

この契約は 27 スキルが参照するため、fixture 保有 13 スキルの regression ledger が stale になった。
実測に基づいて払い分けている。fixtures.json が artifact store 関連語彙を含む 10 スキル 39 シナリオは
process-queue 経路で実走し critical 全 ○（自己申告の baseline_drift を manifest の baseline hash と
突き合わせて 27/27 一致を確認）。語彙を 1 件も含まない 3 スキル（context-audit / doc-write /
refactor）はその実測を根拠に `--accept`。`decision-journal` の dj-004 のみ fail だが、原因は
fixture の前提が実体化されない #54 で本変更の回帰ではないため、fixture を通しやすい方向へは直さず
`accepted-without-run` に留めた。

`sensor:translation-damage` が両方向に壊れていたのを直した（issue #88 / #65）。この sensor は
fixture 未保有 26 スキルにとって唯一の劣化検出手段であり、赤の側と緑の側の双方で意味が失われていた。

**赤の側**（#88）: `resolve_baseline()` は remote-tracking ref を鮮度を確認せずに比較元へ採用して
いた。pre-push hook は push の**前**に走るので、しばらく fetch していない作業ディレクトリでは古い
`origin/main` が採用され、マージ済みの翻訳が「これから入る翻訳」として再検出される。実測では
201 コミット古い ref を baseline にすると 92 件の偽 BLOCK が出た。対策は 2 つで、pre-push hook が
push ネゴシエーションで得た remote の現在地（stdin の remote sha）を `$TRANSLATION_PARITY_BASELINE`
で渡すようにし、それが使えない経路のために `--max-baseline-lead`（既定 100）を超えたら比較を
成立させず skip を明示出力する。日数ではなく先行コミット数で測るのは、偽 BLOCK を出した ref が
4 日前のリリースのもので、活発なリポジトリでは古さが日数に現れないため。`git fetch` を
スクリプトから打つことはしない（検証の実行がリポジトリの状態を変えるのは sensor の役割から外れる）。

**緑の側**（#65）: 検証対象を「日本語行比率が閾値以上から未満へ遷移したファイル」に限っていたため、
元から本文の一部が英語だった部分翻訳ファイルは閾値を跨がず一切検証されなかった。それでいて出力は
「劣化なし」と読めるため、緑の意味が「検証して問題なし」から「検証していない」へ静かに反転していた。
翻訳判定に日本語行の実質的な減少（3 行以上）という経路を足し、節の削除を翻訳と誤認しないよう
散文行の縮み幅に上限（10%）を置いた。それでも判定に載らないが日本語が減っているファイルは、
`report()` が**未検証**として明示列挙する。素通しと検証済みを出力で区別する。

実測（英語化スイープ PR #63 の 98 ファイルへ両方の判定を当てた）: 検証対象 32 → 43 ファイル、
新たに 18 ファイルが未検証として可視化。**新たに対象へ入った 11 ファイルの finding は 0 件**で、
網を広げてもノイズは増えていない。

`identifier_preservation` が意図的リネームを劣化と区別できない件（#88 の観点 3）は別 issue に切り出した。

`github-issue` の自走可否ゲートを機械検証にした（issue #78）。`claude-auto` の説明は「スコープは
本文の『自走可否』節が正本」と規定していたが、スキル側にその節を読む処理も、存在を要求する処理も、
判定値を解釈する処理も無かった。本文を読んだ実行者がなんとなく尊重するだけの助言であり、契約として
成立していない。#34 では部分対応のまま本文が陳腐化し、polling が拾うたびに「対応済みの作業を自走可
として提示する本文」へ素直に従うほど禁止領域へ手が伸びた。#75 では「契約文書 1 ファイルへの追記」と
いう**編集の分量**で書かれた自走可判定が、27 スキルが参照する共有契約という**波及半径**を取り逃した。

4 つのゲートを足した。**Gate 1** は本文 `## 自走可否` の `判定:` 行を `自走可` / `自走不可` の 2 値
でのみ受理し、`部分的に自走可` を禁止値として quiet skip する。この値は末尾に `自走可` を含むため、
部分一致で読むと唯一の禁止値が許可へ反転する — 判定値は全体一致で読む。**Gate 0** は `## 変更対象`
の宣言を必須にし、宣言パスへ影響オラクル（`impact_command`）を当てて `max_impacted_units` 超過と
`forbidden_path_globs` 一致を却下する（claim 前は quiet skip、plan 確定後は permanent failed で、
plan が宣言外のパスへ広がった場合も停止する）。オラクルは配布先のリポジトリで壊れないよう未設定を
既定とし、未設定で no-op になるのは影響数チェックだけである（禁止パスの判定はオラクル無しで効く）。
非ゼロ終了を影響 0 件と誤認しない fail-closed。**Gate 2** は `stateReason == "REOPENED"` の issue で
`comments` を plan builder へ渡し、本文と矛盾していれば実装せず停止する。**Gate 3** は実装フェーズ後に
差分が空なら draft PR を作らず停止する、症状側の安全網。

API 呼び出し回数は増えない。`body` / `stateReason` は `list_ready()` の既存の 1 回の `gh issue list`
に相乗りし、`comments` は plan 構築の `gh issue view` に相乗りする。

fixture に gi-005 / gi-006 を追加した（判定値の 5 ケースと、共有契約パスの却下 / 宣言外パスでの停止）。

2026-07-27 の二軸実測で踏んだドキュメントの欠落 3 件を埋めた。いずれも実装が唯一の正本に
なっていて、reference だけを読んだ呼び出し側が必ず失敗する種類のものである。挙動は変えない。

`metrics-spec.md` に入力ラッパーの節を追加した（issue #68）。`aggregate_metrics.py` は
`{cases, valid_skills, stability_sample_ids?}` というラッパーを要求するが、同ファイルは
ケース 1 件のスキーマしか定めておらず、包む側のキー名がどこにも書かれていなかった。docs
だけ読んで呼ぶと `KeyError: 'valid_skills'` で落ちる。`valid_skills` に `none` を含めない
（自動で加わる）ことも明記した。

`testcase-design.md` の holdout 分割に、成立範囲を先に計算する手順を足した（issue #69）。
「holdout は 20%」と「両側 none 25% 以上」を並記していたが、この 2 つは常に両立するとは
限らない。実測の 188 ケース / none 47 件では 20% 近傍の H=37..41 のうち成立するのは
**H=40（21.3%）で holdout none がちょうど 10 のときだけ**で、20% ちょうどはどの丸め方でも
失敗する。層化制約が比率を支配することと、成立範囲が空なら分割ではなくケース生成に戻ることを
規定した。

`process-delegation.md` に `backends.json` の `schema_version` の扱いを明記した（issue #70）。
欠落は既定値で補われず `unsupported schema_version None (expected 1)` で拒否される。
これは意図的で、このファイルは権限の宣言（§5）であり、形が未検証のレジストリを黙って受理する
のは権限付与の失敗モードとして誤っている。移行は先頭へ 1 行足すだけで済むことも書いた。
レジストリは 1 度書いて使い回す前提のファイルで、過去の実行資産をコピーする経路が正常系である
にもかかわらず、バージョン導入時に移行手順が書かれていなかった。

`static_collisions.py` の tokenize から英語ストップワードを除去した（issue #67）。48 本の
description で実測すると出現率の上位は the 98% / when 98% / use 98% / or 96% / user 96% /
says 92% / and 90% で、`Use when the user says ...` という定型句がほぼ全 description に乗る。
ほぼ全文書に出る語はどのペアでも積集合と和集合の両方に等しく効くため、何も弁別せずに Jaccard を
底上げする。日本語 description では助詞が独立した語として残らないので、この汚染は英語化して
初めて現れた。

**文書頻度による動的な足切りではなく固定リストにした。** DF 足切りはコーパスに適応する反面、
スキルを 1 本足すだけで語彙が動いて全ペアのスコアが変わる。このスクリプトは計測器の前処理で
あり、実行間の比較可能性を壊す方を避けた。リストには文法語と定型句由来の語だけを入れ、
出現率が高くても内容語（`check` / `plan` / `review` / `skill`）は残している。

**この修正は `shared` 語彙の可読性を回復するが、静的順位と実測 confusion の乖離は解消しない。**
修正前後で上位ペアを比較すると、`shared` は機能語（`and` / `the` / `as`）から内容語
（`implementation` / `cycle` / `phase`）へ入れ替わる一方、実測で唯一 confusion が出た
`cycle ↔ plan-implement` は 4 位から 7 位へ下がり、confusion ゼロの
`plan-implement ↔ plan-refine` は 1 位のまま動かない。後者は語彙を実際に共有しているが、
両者を分ける情報（refine 済みか）も description に書かれているため判定は割れない。
**語彙の重なりは判定の混同を予測しない**という、ストップワードでは解けない別の問題である。

`issue` / `github-issue` の計測イベント追記を外部プロジェクトから実行できるようにした
（issue #56）。両スキルは利用側プロジェクトで動く設計なのに、コマンドが
`python3 skills/shared/scripts/measurement_identity.py ...` というリポジトリ相対パスで
書かれていた。利用側に `skills/` は無いので必ず落ちる。しかも両スキルは「計測の失敗は warn
のみで tick を落とさない」と定めている（正しい設計）ため、**tick は成功し続け計測イベント
だけが永久に記録されない**状態だった。

パスの修正だけでは足りなかった。`measurement_identity.py` 自身が
`{repo_root}/skills/skill-regression/scripts` から `ledger` を動的 import しており、
外部プロジェクトでは `ModuleNotFoundError` で落ちる。`--repo-root` は計測対象プロジェクト
（イベントの書き込み先）であってスキル実体の置き場ではない、という取り違えが原因である。

`surface_sha256` は契約上「指示のバージョン番号」であり、実行されているのは配布物側の
SKILL.md なので、**fingerprint を配布物ルートから計算する**ようにした。`--repo-root` の役割は
イベントの書き込み先だけに限定される。checkpoint-pattern.md の CLI 呼び出し規約と同じ理由で、
スクリプト実体は配布位置にあり対象プロジェクトと同居しているとは限らない。本リポジトリで
動かす場合は両者が一致するため値は変わらない。issue が代替案として挙げていた
「`surface_sha256` を null で記録する degraded 経路」は採らなかった。null にすると
「どの指示バージョンで測ったか」が失われ、計測の目的そのものが消えるため。

`skill-interface-audit` に SI-S006（共有契約のインライン重複検出）を追加した（issue #62）。
`skill-authoring.md` の原則 #5 は「共有契約を再発明せず参照する」と定めているのに、対応する
検査ルールが存在しなかった。導入時点でコーパスから 4 件検出し、**4 件とも目視で真陽性を確認**
している。うち `mockup-diff` の比較表は**既にドリフトしていた**（契約側「Verification level /
When it runs」に対しスキル側「Role / In the pipeline」）。重複が放置されるとこうなる、という
実例がそのまま出た。

**検出信号は逐語 12 語一致のみ**とした。語彙類似度と見出し名一致は候補として検討したが、
48 スキルのコーパスで実測して棄却した。契約固有語彙の出現率は連続値で分離せず（中央値 0.117 /
最大 0.625）、上位は「その契約を実装しているスキルが当然の語彙を使っている」偽陽性で埋まる。
見出し名一致は 6 件出るが、`Preventing rationalization` のように**推奨パターンだから見出しが
揃っているだけ**で中身は別物だった。逐語一致だけが疎に分離した。

**行スパンによる長さゲートは置かない。** -37% の実測パターンが「長いインライン節」である以上
行数ゲートは自然に見えるが、実測すると 4 行ゲートで確認済み真陽性 3 件のうち 2 件が落ちた。
表形式の重複は語順が行をまたいで断片的に一致するためである。12 語連続の逐語一致それ自体が
コピーの証拠であり、行数を重ねても偽陰性が増えるだけだった。

n=12 は閾値掃引で決めた（n=8 で 16 件 / n=10 で 7 件 / n=12 で 4 件 / n=16 で 0 件）。12 未満で
のみ現れるペアは、リンクと併記された短い役割固有の再掲（`handoff` が checkpoint の衝突規則を
1 行で要約している類）で、これは参照側が書くべきものである。

action は NEEDS_JUDGMENT にした。実測パターンの 3 条件のうち「② 全シナリオで必要ではない」は
機械判定できず、しかもそれが実質的なゲートになる。2026-07-25 の verification-gate 実測
（null result）では重複が実際に効いており、削っても挙動が変わらなかった事例が記録されている。
どちらを残すかは判断なので、報告のみで書き換えない。

ID は SI-S006 とした。SI-S005 は rule-catalog の v2 候補に
「missing rationalization guard table」として予約済みで、予約を繰り下げなかった。
後から来たルールで ID がずれる catalog は、過去の finding と突き合わせられなくなるため。

なお両 SKILL.md から checkpoint-pattern.md へ md リンクを張ったことで、同契約が
`issue` / `github-issue` の挙動面に入った。今後 checkpoint-pattern.md を編集すると
2 スキルの再評価が要る。共有契約を再発明せず参照するという原則（skill-authoring #5）に
従った結果として、回帰評価の範囲が広がるトレードオフである。

## 1.68.0

CONTEXT 語彙の状態 enum を英語化した（`確定` / `暫定` / `競合中` / `廃語` →
`settled` / `tentative` / `conflicting` / `retired`）。S1 英語化では「`ledger_lint.py` が
`UNSTABLE_TERM_STATES` として直に持つデータ値だから訳せない」として日本語を残したが、
検証の都合で契約に日本語が固定されるのは順序が逆である。検証側を英語に対応させるのが正しい。

棚卸ししたところ、そもそも **lint は状態 enum を一度も検証していなかった**。
`load_context_terms` は `state` を文字列のまま読むだけで、実効があるのは
`UNSTABLE_TERM_STATES` の 2 値の membership だけ。つまり enum は契約に書いてあるだけの
未執行の宣言で、この状態で値を差し替えると旧い日本語値が**黙って**不安定依存検出から
外れる。値の変更より先に、無かった検証を足す必要があった。

`unknown-term-state` advisory を新設した。`AGREED` 行が依存する語の `state` が enum 外なら
report-only で報告する。検証は loader ではなく**利用時**に置いた。語彙ファイルは補助入力で
あり、状態 1 つの不正で台帳の lint 全体を落とすのは過剰なため（`load_context_terms` の
raise は exit 2 = 入力破損の意味を持つ）。この advisory は v1 以前の日本語値からの
移行経路も兼ねる。

`tentative` を選んだのは、`暫定` の直訳である `PROVISIONAL` が agreement-ledger の合意状態
enum と衝突するため。両者は別軸（語の状態 / 主張の状態）なので、同じ語が 2 つの層に現れると
読み手がどちらの層の話か判別できない。

この enum がどの層を縛るのかを契約に明記した。書いていなかったため「対象プロジェクトのデータ
なのだから日本語も受理すべきでは」という論点が起きた。実際には投影（機械可読 JSON）の `state`
の値集合を定めているだけで、人間向け CONTEXT.md の散文が状態を何語で呼ぼうと自由である。
案件の言語で書かれるのは語彙そのもの（`term`、自由文のドメイン語）であり、`state` は
同じファイル族の他の機械 enum（台帳行の `AGREED` / `DELEGATED`、`actor_kind: human`、
`risk: high`）と同列に置かれる。

日英両方の綴りを受理する案は検討して棄却した。写像はどこかに必要で、投影の生成時（人間向け
正本を変換する工程）に置けば追加コストはない。一方 linter に置くと、全ての利用側が比較前の
正規化を義務づけられ、`unknown-term-state` が塞いだはずのサイレント見逃しの類型が戻る。
旧トークンは alias 表ではなく advisory で浮上させる。

- `skills/ledger/scripts/ledger_lint.py`: `VOCAB_STATES` を新設、`UNSTABLE_TERM_STATES` を
  英語値へ、`_check_pending_vocabulary` に派生検出 (d) を追加
- `skills/shared/references/context-vocabulary.md`: enum の英語化と、enum を利用時に
  執行する理由・移行経路を明記
- `skills/shared/references/agreement-ledger.md`: pending-vocabulary の派生検出に (d) を追加
  （enum の正本は context-vocabulary 側に置き、ここでは再掲しない）
- `skills/ledger/scripts/test_ledger_lint.py`: 状態リテラルを英語へ差し替え、
  enum 外検出・旧日本語値検出・`tentative` は不安定でないこと・set 形式の
  `context_terms` で誤検出しないことの 6 テストを追加（157 テスト green）
- 実走確認: 旧値 `競合中` は `unknown-term-state`、新値 `conflicting` は
  `unstable-term-dependency` を出し、`settled` は無音。gating finding は 0 件

`sweep-fix` の中間ファイルに、置き場が VCS の ignore 対象外だった場合の扱いと、削除を試みずに
残存だけ申告する抜け道の封じを入れた（issue #36 の (3)(4)）。(3) は退避先を作るか Phase 4-3 の
確認から除外するかで設計が分かれる裁定事項だったが、置き場を動かさず「検出して報告する」側で
確定させた。中間ファイル置き場は Phase 1・2・3・5 の 4 箇所にパスが書かれており、退避先を作ると
全てを変数化する改修になるうえ、他スキルの中間ファイル慣行とも乖離する。実害は照合ノイズと、
削除拒否時の残骸がユーザーの次のコミットへ紛れ込むことの 2 つであり、どちらも「Phase 4-3 の
照合から除外する」「未 ignore なら報告する」で消える。ユーザーのリポジトリ設定を書き換える
（`.gitignore` へ追記する）ことは本スキルの範囲外として明示的に禁じた。

(4) は #42 でマージした「削除が拒否されたら残存パスを明記して完了」という退避路が、削除の
試行そのものを省く口実に転用されうる問題。退避路は**試みて拒否された削除にのみ開く**と明記し、
拒否を予測して試さないことは試行ではないと合理化テーブルに加えた。

- `skills/sweep-fix/SKILL.md`: Phase 1-5 に ignore 状況の確認（確認自体が失敗したら未 ignore と
  同じ扱いに倒す）、Phase 4-3 に中間ファイル置き場の照合除外、Phase 5 に試行前提の明示と
  未 ignore 残存時の依頼、レポート §6 に中間ファイル行、合理化テーブルに 3 行
- `skills/sweep-fix/fixtures.json`: sf-001 の `.gitignore` から `.claude/` を外して未 ignore の
  プロジェクトを再現し、要件 9 を**非 critical で**追加。critical の集合は変更していない
- 実測: 3 シナリオを白紙実行者で再走し全 pass（critical 4/4・3/3・3/3）。**前回 run で未踏だった
  分岐を今回すべて踏めた** — Phase 5 の `rm -rf` が権限ゲートに拒否され、レポート出力後に試行 →
  拒否 → 残存パス明記という経路が実測できた。`.gitignore` が baseline sha256 一致で、実行者が
  自力で ignore を書き換えていないことも機械照合した
- fixture の要件が 9 項目となり fixture-schema の設計指針（3〜7）を超えた。要件 8（Phase 5 の
  削除順序）と要件 9（Phase 1 の ignore 検出）は別フェーズの挙動で、統合すると劣化の所在が
  特定できなくなるため分離を選んだ。逸脱の理由と「次に足すならシナリオ分割を先に検討する」旨を
  fixture の notes に記録した

plan-implement のループ制御にあった 2 つの空白を埋めた（issue #34 の (3)(4)）。Step C の反復上限は
「Step B レビュー → Step C 修正の往復 1 回」を単位に数えるが、指摘ゼロで即収束した回を 1 と数えるか
0 と数えるかが未定義で、上限付近で数え方が 1 ずれていた。修正を伴わない回は数えないと明記した。
また Step A は Red / Green / Refactor を必須の 3 段構えとして書いており、整理すべき重複も改善すべき
命名も無いケースの正解が読み取れなかった。無理に構造を動かせば YAGNI に反するため、変更不要と
判断した場合は根拠を記録して次へ進む出口を明示し、あわせて「REFACTOR 実施」とだけ書いて済ませる
ことを禁じて、出口が省略の口実に転用されないようにした。

同 issue の (1) Phase Final の反復上限の値と (2) Step C で受容した WARN を最終レビューの差し戻し
対象から外すかどうかは、人間の裁定が必要とされているため触れていない。(4) は `tdd-contract.md` にも
同じ空白があるが、そちらへ書くと影響スキルが 1 つを超えるため plan-implement 本文に留めた。

- `skills/plan-implement/SKILL.md`: Step C-4 に指摘ゼロ回の非計上、Step A の Refactor に
  「変更不要」の明示的な出口と記録義務
- `skills/plan-implement/fixtures.json`: pi-001 に REFACTOR 段の記録要件、pi-002 に指摘ゼロ回を
  イテレーションに数えない要件を**非 critical で**追加。critical の集合は変更していない（合格バーを動かさない）
- 実測: 白紙実行者（tier: standard）で pi-001 / pi-002 / pi-003 を再実行し、critical 5/5・3/3・3/3、
  非 critical 3/3・3/3・1/1 で全合格。編集ゼロの裏取りは baseline sha256 で機械照合した
  （pi-002 の Step 1 成果物はハッシュ一致で未変更）。変更前に pass していた要件は 1 つも落ちていない
- 実測の限界: 3 シナリオとも初回レビューが BLOCK / WARN ゼロで収束したため、指摘ゼロ回の
  非計上は「不要な往復を発生させない」側だけが観測でき、上限付近で数え方が効く経路は未踏である

`brief` を追加した。LLM 向けに書かれた差分・実装計画・引き継ぎ・進行中の会話を、人間が
判断する順に組み替えた自己完結 HTML として見せる手動起動のスキル。承認が「なんとなく
いい感じ」で通る儀式になると、その先の機械検証がすべて読まれていないハンコにぶら下がる。
そこを実質のあるものに戻すのが目的で、既存のワークフローへは意図的につないでいない。

まとめ方の良し悪しは機械には測れないが、何かが黙って消えたかどうかは測れる。差分では
全変更箇所がちょうど 1 つのまとまりに属することを必須にし、折りたたみへ逃がす抜け道を
塞いだ。会話では機械で分解できる入力が存在しないため、代わりに未決事項のまとまりが必ず
存在することを必須にした。要約で最初に消えるのは、決まっていないことだからである。

見た目は起動ごとに描かせず、デザイントークンから決定的に組み立てる。危険度と確からしさも
観測できる問いに落とした尺度で決める。白紙の実行者に 6 シナリオを 6 回解かせた実測では、
尺度の導入前は同じ材料に毎回違う値が付いていたのに対し、導入後は 3 回連続で完全に一致した。

自分自身の差分・計画・引き継ぎ・会話で 5 回試用し、画面が無ければ出なかった指摘が 8 件
出た。うち 1 件は、計画書の進捗表が 6 段階すべて未着手のまま放置されていたことだった。

プロンプト単位の作業をサブエージェントではなく別プロセスへ委譲する汎用ワークキューランナーを
共有資産として追加した（issue #16）。サブエージェント起動枠はセッション累計で数えられ完了しても
戻らないため、3 役分離の計測ハーネスのようなファンアウトはバッチ途中で上限に当たる。実行者・
採点者に必要なのは「独立した文脈でのモデル呼び出し」であってサブエージェントではない、という
切り分けを契約として固定した。

- `skills/shared/references/process-delegation.md`: 適用条件（機械判定可能な oracle の存在）、
  work キュー / バックエンドレジストリの schema、成否は終了コードではなく成果物で決める規約、
  権限境界、polling-pattern §6 準拠の safety brake と一回限りドレインゆえの逸脱を明文化
- `skills/shared/scripts/process_runner.py`: ベンダー名を一切持たないランナー。実行ファイルと
  フラグは operator が書く `backends.json` にのみ存在し、work キューは argv に 1 要素も寄与
  できない（これが権限境界そのもの）。成果物が既に妥当なユニットは skip するため、再実行が
  そのまま引き継ぎになる
- `skills/shared/scripts/test_process_runner.py`: 未検証だった失敗経路を 114 ケースで固定
  （タイムアウト、実行中の kill file による停止と実行中プロセスグループの終了、JSON 成果物の
  破損、バックエンド起動失敗、並列上限、containment 違反、failed_streak / max_wallclock）。
  起動時点で失敗するユニットは in-flight にならず dispatch ループを絞れないため、
  failed_streak を dispatch 側でも検査する（存在しない実行ファイルでキュー全消費を防ぐ）
- `skills/skill-regression/scripts/regression_queue.py` + `references/process-queue.md`:
  最初の利用者。fixtures.json から実行者プロンプトと work キューを生成し、戻ってきた
  レポートを機械的に集計する producer。判定規則は executor-contract のまま変えず、
  `critical` フラグは manifest に留めてプロンプトへ出さない。集計は `pass` を名乗らず
  `unadjudicated_pass` を返す — 自己申告と成果物の突合は呼び出し側の責務であり、
  harness 起因の `needs_rerun` はスキルの回帰と区別する
- `skills/empirical-prompt-tuning/SKILL.md` / `skills/skill-regression/SKILL.md`:
  起動枠が尽きた場合の代替経路として参照を追加
- README: 共有資産の直接利用として本契約を追記

実 CLI での検証で、n=1 プロトタイプでは踏んでいなかった前提が 1 つ崩れた。エージェント CLI は
書き込みをプロセスの作業ディレクトリに限定することがあり、成果物を兄弟ディレクトリに置くと
ユニットは全工程を終えてから配送だけ失敗する（実測: 343 秒、終了コード 0、成果物なし）。
成果物をユニットの作業ディレクトリ内に置く規約を契約へ追加し、producer の配置もそれに合わせた。

systematic-debugging の Phase 1 が置いていた 2 つの暗黙の前提を解消した。Step 1.1 は
エラーメッセージとスタックトレースの存在を前提にしていたため、例外を投げず戻り値だけが
汚染される silent failure では記録すべき対象が 1 つも取得できず、代替エビデンスの規定も
なかった。Step 1.3 の `git diff HEAD~5 --stat` はコミット 5 本未満のリポジトリ
（新規プロジェクト・fixture・浅い clone）で必ず exit 128 になるが、失敗時の扱いが
書かれていなかった。

- `skills/systematic-debugging/SKILL.md`: Step 1.1 に、例外を伴わないバグでは症状の
  観測値（期待値 vs 実測値・汚染を露出させた観測）を代替エビデンスとし、その要約を
  Phase 1 表示の `Error:` に充てることを明記
- `skills/systematic-debugging/SKILL.md`: Step 1.3 に初期コミットまで遡る fallback を
  添え、なお比較できない場合は「履歴が浅く比較不能」と記録して Step 1.4 へ進むことと、
  履歴の不在それ自体は根本原因のエビデンスにならないことを明記
- skill-regression の run で sd-001 / sd-002 / sd-003 を白紙実行者により再実行し、
  台帳ベースラインと同一（6/6・4/4・5/5、critical 全 pass）で非劣化を実測

cycle Phase 3 の status.md アーカイブ経路が Step 3b のガードで到達不能になっていた問題を修正
（issue #18）。ガードが判定に使う状態を「終端状態（Current Session がクリア済み）」だけに限定し、
Phase 2 が書き込む中間ラベルでは発火しないようにした。あわせて Step 3 が通った分岐を最終表示へ
出すようにして、静かなスキップが静かな成功と区別できない状態を解消した。

- 原因は状態ラベルの衝突。plan-implement の完了処理が Current Session の `Phase` を
  `🟢 Complete` に書き換え、直後の Step 3b ガード「Status が `Completed` なら skip」が
  その中間状態に一致していた。Case 2 が producing する終端状態は `_No active session._` なので、
  ガードが見るべき状態と Phase 2 が作る状態が同じラベルで衝突していた。
  Current Session table に `Status` という項目は存在せず（実体は `Phase`）、この語の不一致が
  実行者ごとの解釈揺れを生んでいた
- 判別シナリオ 4 種 × 白紙実行者で A/B 実測。成果物はチェッカーではなく機械オラクル
  （session-history.md の行数と Current Session の終端状態）で判定した。
  critical 合格は修正前 6/14 → 修正後 12/12。修正前に合格していたシナリオを
  修正後に落としていないことを差分形式のゲートで確認（冪等性シナリオを含む）
- 指示量は 26 行のまま（+156 バイト）。同一作業を行うシナリオでのトークン差は
  +0.6〜1.1% で run 間ばらつき（noise band 約 160 tokens）の範囲内
- `skills/cycle/SKILL.md`: Step 3b のガード条件・Step 3c の適用範囲・最終表示の `Session` 行
- `skills/cycle/fixtures.json`: cy-001 の最終表示要件に `Session` 行の分岐表示を追加

Agent Artifact Store 契約に違反した状態で実体化される回帰 fixture を是正し、同じ違反を
`fixture_setup.py --validate` で機械的に止めるようにした。違反した fixture は store が
`writable: false` に落ちるため、Phase 0 で store を検証するスキルは宣言したシナリオへ
一度も到達しないまま abort する。落ちる fixture と違って赤くならず素通りするため、
台帳には「到達していない経路」に対する合格記録が付いていた（issue #17）。

- 実測: `.agents/` を宣言する全 15 シナリオを実体化して `artifact_store.inspect` で判定。
  修正前は自前 git を宣言する 4 シナリオ（cy-001 / cy-003 / ho-004 / pl-004）が
  `writable: false` で 0/4、修正後は 4/4。周囲のリポジトリに依存する 11 シナリオは前後とも変化なし
- `skills/{cycle,handoff,plan}/fixtures.json`: `setup.files['.gitignore']` に
  `/.agents/artifacts/` と `/.agents/runtime/` を宣言。cy-002 は `.agents/` を宣言しないが
  自前 git を持ち Phase 0 で store を検証されるため併せて是正した
- `skills/skill-regression/scripts/fixture_setup.py`: `setup.git.init` を宣言し
  `.agents/` 配下を持つシナリオに対し、`.gitignore` の無視宣言・`visibility: public` の
  明示 policy・runtime 領域の常時無視・policy 自体の追跡を静的検査する。
  `scripts/validate_repo.py` 経由で CI が止める
- 静的検査の判定を実体化後の `artifact_store.inspect` と突き合わせる unit test を追加し、
  宣言側の検査が実測から乖離しないよう固定した

CHANGELOG の起票先を `## Unreleased` に一本化し、version bump を PR から切り離した。
これまでは PR ごとに bump していたため、同時に開いた 6 本の PR が全て 1.66.0 を名乗り、
1 本マージするたび残り全部が 3 manifest + CHANGELOG でコンフリクトする状態になっていた。
bump は「配布の単位」であって「変更の単位」ではないので、リリース時にまとめて判断する。

- `validate_repo.py` にチェック12b を追加: `## Unreleased` の表記ゆれ（`[Unreleased]` /
  小文字）・重複・配布済みエントリより下への配置を検出する。リリース時に番号へ昇格させる
  対象が常に一意に定まる状態を機械的に保つ
- チェック12 の逆方向（未配布の番号付きエントリを禁止）は維持。禁じているのは「配布済みに
  見える番号」であって未配布の記録そのものではないため、`## Unreleased` は許可対象と明記した
- `skill-authoring.md` の「横断最適化のリリース単位」を、横展開バッチ限定の規約から
  PR 全般の規約へ一般化した

あわせて、worktree から push すると pre-push hook が必ず失敗するバグを修正した。git は hook へ
`GIT_DIR` を渡すが、worktree ではこれが絶対パスになるため、検証中の `git init` / `git check-ignore`
（cwd = 一時ディレクトリ）が一時リポジトリではなく本物のリポジトリを操作してしまっていた。
通常 checkout では `GIT_DIR` が相対パス `.git` で cwd 基準に解決されるため偶然動いており、
worktree でのみ露出していた。hook から GIT_* の継承を明示的に断ち切る。

Opus 5 プロンプトガイドの「保守的な報告指示は報告量を減らす」という主張を本リポジトリで実測し、
**ほぼ当てはまらない**ことを確認した。`skill-authoring.md` に「保守的」の 3 分類（報告抑制 /
逆方向の保守性 / 自動修正 fail-safe）と実測結果を追記し、語の字面だけを根拠にレビュー系スキルの
判定基準を緩めることを防ぐ。fail-safe を報告抑制と誤認して緩める改変は安全性を落とすため、
分類を先に通すことを規範化した。

- 棚卸し: 本文に「保守的」と書かれた箇所のうち報告を実際に抑制するのは 1 箇所のみ。
  他は severity を下げない側の保守性、または NEEDS_JUDGMENT / UNCERTAIN へ倒す自動修正 fail-safe
- 実測: 該当 1 箇所を before/after 2 変種 × 2 シナリオ（判別シナリオは k=3）で 3 役分離評価。
  severity 降格は両変種とも 0/3 で発生せず、実行者は docstring・例外送出といったコード自身の
  契約証拠から BLOCK を維持した。低影響シナリオでも BLOCK 膨張なし（要件 5/5）
- 書き換え版は非劣性だが改善が測定されなかったため、`review-testing` の判定基準は変更していない

あわせて `verification-gate.md` の削除是非も実測し、こちらも null result だった。gate 本文を
88 行 → 30 行に削るアブレーションを `cycle` の cy-001 で各 n=3 実走したが、トークン中央値の差は
noise_band をぎりぎり超える程度で確立できず、品質劣化も観測されなかった。gate の執行力は既に
参照側スキル（`cycle/SKILL.md` の Phase 2 がテスト実行エビデンスを要求）へインライン化されており、
共有契約側の分量は実行挙動に効かない。削除の根拠が無いため gate は現状維持とし、計測手順と
アブレーションの限界を `skill-authoring.md` に記録した。

`sweep-fix` Phase 5 の中間ファイル削除に、順序制約と拒否時の扱いを規定した（issue #36 の
(1)(2)）。本文は削除を無条件の手順として書いており、`rm -rf` が権限ゲートに拒否された場合に
完了扱いしてよいのかが実行者の自己判断に委ねられていた。実走では 2 セッション連続で拒否され、
どちらの実行者も迂回せず残存を申告している。その振る舞いを仕様として追認した。順序の方が
実害は大きく、`verdicts.json` は各判定の根拠を持つ唯一の記録であるため、レポートへ転記する
前に削除すると FALSE_POSITIVE の除外理由が復元不能になる。

- 実測: 変更後に skill-regression の run で 3 シナリオ全てを白紙実行者で再走し、変更前に
  pass していた要件を 1 つも落としていないことを確認（sf-001 8/8・sf-002 5/5・sf-003 3/3、
  critical は 10/10）。編集有無は baseline sha256 で機械照合した
- `skills/sweep-fix/fixtures.json`: sf-001 に非 critical 要件を 1 つ足し、削除順序の遵守と
  拒否時の申告を計測対象にした。critical の集合は変更していない
- 今回の run では削除が拒否されなかったため、実測できたのは「レポート確定後に削除する」順序の
  側だけで、拒否時に残存パスを申告して完了する分岐は未踏。環境依存で分岐することを台帳に併記した
- issue #36 の (3)（中間ファイル置き場が未 ignore のプロジェクトでの扱い）は、退避先を作るか
  Phase 4-3 の確認から除外するかで設計が分かれるため、人間の裁定待ちとして触れていない

翻訳による構造劣化を機械検出する `sensor:translation-damage` を実装し、`run_checks.sh` の
ゲートに入れた。skills/ 全文書の英語化は残り 106 ファイルあるが、fixture を持つスキルは
20 / 48 しかなく、残り 26 スキルは非劣化 A/B が原理的に走らせられない。dossier
`frag:translation-damage-sensor` が「この sensor が唯一の劣化検出手段になる断片が存在する」と
判定しているのはそのためで、この実装が無い間は fixture 未保有スキルを 1 本も訳せなかった。
1 本ずつ fixture を作ってから訳す従来手順は 26 スキル × 12〜16 プロセスを要し、翻訳そのものの
コストではなく検証手段の不在が律速になっていた。

検出対象と severity は、リポジトリの過去の翻訳コミット 41 ペアで校正して決めた。BLOCK は
構造パリティ（見出し / フェンス / リンク / 番号 / 箇条書き / 表の行 / 水平線の件数）・識別子と
契約語彙の消失・frontmatter の byte 不変の 3 rule。`user_facing_template_preservation` だけ
WARN に留めたのは、「フェンスの中身は読み手で切り分ける」裁定（実行者しか読まないフロー図や
Iron Laws は英訳してよく、利用者が読む REPORT テンプレートは原文のまま）が機械判定できないため。
どちらの読み手向けかを機械が決められない状態で BLOCK にすると、正しい翻訳を止めてゲートごと
無効化される。fix action は dossier の findings_policy どおり全 rule で NEEDS_JUDGMENT とし、
消失識別子の自動復元は行わない（訳文の構文を壊しうる）。

- 実測: 過去の翻訳コミット 41 ペアで校正し、BLOCK が出たのは 8 ペアのみ。8 件はいずれも
  件名が「プロンプトを軽量化する」「実測摩擦を明示化する」等で翻訳以外の改変を併せて行った
  コミットであり、フェーズ 1 で非劣化 A/B を通した純粋な翻訳 5 本（test-driven-development /
  systematic-debugging / sweep-fix / plan-implement / refactor）は全て BLOCK 0 だった
- 校正で 2 つの偽陽性源を潰した。(a) 日本語を含むインラインコード（`{観点}`、
  `#1-feasibility---実現可能性`）は訳文で中身も訳されるのが正しいため識別子から除外、
  (b) 消失判定を集合差分から本文の部分文字列一致に変更（`(none)` → `branch: (none)` のような
  括り直しが消失と報告されていた）。この 2 つで identifier_preservation の報告は 26 件から 3 件へ減り、
  残る 3 件はいずれも実際に文字列が変化していた
- `scripts/check_translation_parity.py`: 新規。`--pair` で 2 ファイル直接比較、`--baseline` で
  git リビジョン比較、`--force` で遷移判定の省略、`--strict` で WARN も exit 1 に含める
- `scripts/test_translation_parity.py`: 新規 37 テスト。「壊れているものを検出する」側と
  「正しい翻訳を止めない」側を同じ重みで検証する
- `scripts/run_checks.sh`: Translation parity を ledger check の後に追加。日本語行比率が閾値
  以上から未満へ**遷移した**ファイルだけを検証するため、日本語のままの通常編集では対象 0 件の
  no-op になる（遷移を条件にしないと、節を書き換えて見出しが 1 つ増えるだけでゲートが赤になる）
- `.github/workflows/validate.yml`: checkout に `fetch-depth: 0` を追加。既定の shallow clone では
  `origin/main` が存在せず、比較元リビジョンを解決できずに skip して CI で黙って無効化される

fixture 未保有 references の残り 10 本のうち 8 本を英語化した（mockup-diff 1 /
empirical-prompt-tuning 5 / spec-verify 2）。到達は 77 → 85 / 163 ファイル、BLOCK は 0 件。
参照元 SKILL.md の鉤括弧参照も 2 箇所更新し、handoff から引き継いだ「未翻訳 references を
指す参照 7 箇所」は 6 箇所が解消した。

**`clause-schema.md` と `evidence-manifest.md` の 2 本は着手せず据え置いた**。この 2 本は
散文ではなく**機械パースされる正本**であり、翻訳が単独では閉じないことが判明したため。

- `test_spec_lint.py` / `test_trace_matrix.py` の同期テストが**日本語の節見出しをキーに
  表を引いている**（`sections["共通 envelope"]`、`sections["実行 observation"]`、
  `sections["識別子・digest の形式規則"]` 等）。行ラベルも
  `patterns["\`test_id\` パターン"]` のように日本語を含む。見出しを訳すとテスト定数の
  同時更新が要る
- 見出しはアンカーの実体でもあり、`spec-verify/SKILL.md` から 5 箇所、
  `pbt-binding-guide.md` から 3 箇所が `#保証レベル` などで参照している。さらに
  **`shared/references/agreement-ledger.md` からも 2 箇所参照されている** —
  shared 契約は `self_modification_risk: high` で独立コミット + 影響 4 スキルの
  再検証が要る別フェーズの対象であり、references バッチの副作用として触れるべきではない
- `validate_repo.py` はリンク検証時にアンカーを落として存在確認のみ行う（73 行目）。
  つまり**アンカーが陳腐化しても CI は赤にならず、静かに壊れる**。検出されないぶん、
  まとめて計画的に直す必要がある

したがってこの 2 本は「翻訳 + テスト定数更新 + アンカー更新（shared 契約を含む）」を
1 つの単位として、shared 契約フェーズと合わせて扱う。

- `skills/mockup-diff/references/script-requirements.md` の `Bash` は、AGENTS.md の
  プラットフォーム非依存ルールに照らすと本来は除去対象だが、翻訳コミットで意味を変えないため
  原文どおり残した（センサーも identifier 消失として BLOCK した）。除去は
  skill-interface-audit の SI-S004 で別途扱う

fixture 未保有 SKILL.md の英語化を完了させた（mockup-diff / design-scaffold /
empirical-prompt-tuning / spec-verify）。これで **fixture 未保有スキルの SKILL.md は全て英語**になり、
到達は 77 / 163 ファイル。BLOCK は本バッチも 0 件で、センサー導入後の通算でも 0 件を維持している。

4 本とも `ledger.py --impact` で影響範囲を確認してから着手した。empirical-prompt-tuning だけは
skill-regression / trigger-eval にも波及するが、3 スキルとも fixture 未保有のため再検証は発生せず、
`ledger --check` は緑のままである。

WARN（フェンス内の日本語行の減少）は 4 本とも実行者向けフェンスに限定した。判断の内訳:

- mockup-diff 40→29: ワークフロー概要・パイプライン図・生成ファイルツリーのコメント。
  利用者が読む差分分析レポート / 完了メッセージ / 設問の選択肢は原文のまま
- design-scaffold 29→24: すべて生成テンプレート内の「ここに全レベルを出力せよ」型の生成器向け
  コメント。生成物の様式（catalog.json の description 値、完了レポート、上書き確認の選択肢）は不変
- empirical-prompt-tuning 45→14: 実行者 / checker サブエージェントへ渡す dispatch プロンプト本体。
  これらは LLM しか読まないうえ、レポート構造のキーを英語化しても受け手は同じスキル内のハーネス
  なので閉じている。**利用者に見せる「提示フォーマット」の 14 行は原文のまま残した**
- spec-verify 7→6: `--baseline` の引数プレースホルダ 1 行のみ。完了報告フォーマットは不変

- 未翻訳の references を指す参照が 4 箇所増えた（spec-verify → clause-schema.md の
  配置規約 / exit code 契約アンカー、evidence-manifest.md のマトリクス行スキーマ / v1 の信頼境界
  アンカー）。リンクアンカーは日本語見出しのままなので、参照先を訳す際に参照元とセットで
  更新する必要がある

fixture 未保有スキルの references 24 本を英語化した（ledger 3 / skill-improve 3 /
design-generate 1 / skill-interface-audit 2 / trigger-eval 3 / review-deps 3 /
review-testing 5 / design-validate 1 / skill-regression 2 / design-lint 1）。
到達は 73 → 97 / 163 ファイル、BLOCK は 0 件。全ファイルで着手前に `ledger.py --impact` を
実行し、影響範囲に fixture 保有スキルが入らないことを確認した（`ledger --check` は緑のまま）。

**フェンスの扱いは読み手で切り分けるという既存裁定を、references でも一貫して適用した**。
サブエージェントへ渡す dispatch プロンプト（skill-improve の 4 ロール、skill-regression の
白紙実行者、design-validate の judge）は読み手が LLM に閉じているので訳し、利用者が読む
レポートテンプレート・完了メッセージ・lint の出力文言は原文のまま残した。WARN 11 件は
すべてこの切り分けの結果で、内訳は各コミットメッセージに記録した。

**3 ファイルは意図的に翻訳対象から外した**。`review-deps/references/report-template.md`、
`review-testing/references/report-template.md`、`goal-decomposition/references/dossier-template.md` は
本文のほぼ全体が「利用者へ出す成果物の様式」であり、訳すと日本語利用者への出力言語が
変わる。フェーズ 1 で確定した「利用者が読む REPORT テンプレートは原文のまま」に該当する。
これらは翻訳漏れではなく除外である。

未翻訳 references を指す参照の解消も進んだ。judge-protocol.md「入力の配布方法」、
metrics-spec.md「モード軸」、scanner-integration.md「深刻度のマッピング」、
fixture-schema.md「素材別の変換ガイド」の 4 見出しを訳し、参照元（trigger-eval /
review-deps / skill-regression の各 SKILL.md）の鉤括弧引用も英語見出しへ差し替えた。

- 残る fixture 未保有 references 10 本（mockup-diff 1 / empirical-prompt-tuning 5 /
  spec-verify 4）は、参照元 SKILL.md が別ブランチで英語化されており、アンカー更新が
  衝突するため次バッチへ送った

`skills/shared/references/tool-mapping.md` を削除した。英語化の対象として棚卸ししたところ、
文書の中心である Claude Code ↔ Codex CLI のツール名対応表は、1.40.0 でスキル本文から固有
API 名を排除した時点で前提を失っていた。ツール固有語彙の取り締まりは skill-interface-audit
の SI-S004 が自前の検出語彙で担っており、この文書を参照していない。参照元の
`skills/shared/SKILL.md` 自身が「歴史的参考」と断っていたことも、役目の終了を裏づける。
訳す前に存続可否を裁定するという判断（前セッションの引き継ぎで課題として残されていた）に対し、
「終えている」と結論した。

ただし全体が死んでいたわけではなく、他のどこにも記述がない 2 つの生きた規約を
`skill-authoring.md` の「クロスツール互換性の注意」へ移設してから削除した。1 つは共有契約の
可搬性判定（tool-agnostic / platform-aware / platform-specific）、もう 1 つは対話によるユーザー
確認がランタイムによっては特定モードでしか使えないという実測制約と、非対話実行時に安全側
デフォルトへ降格する義務。後者は移設にあたり固有 API 名を落とし、AGENTS.md のプラットフォーム
非依存表現の規約に合わせた。

- `skills/shared/references/tool-mapping.md`: 削除。fixture 保有スキルへの影響は 0（`ledger.py
  --impact` が空）で、回帰評価は発生しない
- `skills/shared/references/skill-authoring.md`: 可搬性の 3 段階と対話確認 fallback を追記し、
  削除した文書への案内を差し替え
- `skills/shared/SKILL.md`: 歴史的参考としての参照を、可搬性基準の所在（skill-authoring.md）へ差し替え
- `.codex-plugin/plugin.json`: longDescription の "with tool-mapping for cross-platform
  compatibility" を、実態である「プラットフォーム非依存の自然言語で記述」へ改めた

共有契約 10 本（S2 レーン）を英語化し、影響する 17 スキル・55 シナリオの回帰評価を完走した。
S2 は「訳すと fixture 保有スキルへ波及する」で切った区分で、難易度ではなく後始末のコストが
理由。critical 要件の落ちはゼロで、スキル側の劣化は検出されなかった。

`polling-pattern` と `measurement-identity` だけ扱いを分けた。見出しが外部からのアンカー
参照の実体になっており（18 箇所 + 4 箇所、計 9 ファイルから）、訳すとリンクが壊れる一方で
`validate_repo.py` はリンク検証でアンカーを落とすため CI は緑のまま通る。つまり黙って壊れる。
本文の翻訳と参照元の更新を同一コミットに収める必要があり、他の 8 本から分離した。訳語を選ぶ
際は「英語のみで構成された見出しは変えない」を優先し、参照更新を 5 箇所に抑えた。

回帰評価で観測した制約と綻びは `skill-regression` の台帳 note に残した。次に同じ環境で回す人が
同じ停止を劣化と誤読しないためで、所在が実行基盤側と fixture 側に分かれる。

- 実行基盤: 実行者の最終出力が呼び出し側に届かない（報告経路の明示で解消）。入れ子委譲は
  最後まで機能するが、子の完了通知は実行者ではなく呼び出し側へ届くため、実行者は relay
  ファイルのポーリングで着弾を検知する必要がある。`cycle` の fixture はこの待機を予算満了前に
  約 1 分で打ち切り、着弾の 1 秒前に inline fallback へ落ちていた。設計の欠陥ではなく運用の
  早期打ち切りで、残る曖昧さは「委譲を諦めて inline へ切り替える待ち時間の基準が
  cycle の Phase 1/2 に明示されていない」こと
- fixture: `doc-write` の `env` 宣言はハーネスが強制せず、`decision-journal` の `setup` は
  空で前提が散文にしかない。いずれも前提が実体化されず、要件の検証が宣言頼みになっている
- fixture: `plan-implement` の要件 1 件が status 更新のコミットを求めるが、SKILL.md は
  artifacts が Git 追跡外なら commit 対象外と定めており、要件文が契約と食い違う

- `skills/shared/references/`: verification-gate / fix-action-taxonomy / tdd-contract /
  codex-integration / severity-and-verdicts / human-readable-summary / decision-protocol /
  checkpoint-pattern / measurement-identity / polling-pattern を英語化
- `skills/issue/` `skills/github-issue/` `skills/goal-loop/` `skills/trigger-eval/`
  `skills/skill-regression/` `commands/github-issue-polling.md`: 日本語見出しを指す
  アンカー参照 22 箇所を英語見出しへ差し替え
- `skills/skill-regression/ledger.json`: 17 スキルの検証記録を更新
- `human-readable-summary.md` の before/after 例示ブロックは日本語のまま据え置いた。
  利用者が画面で読む完了報告そのもので、契約が「主観基準のアンカー」と位置づけている実物の
  ため、訳すと基準が指す対象がずれる

共有契約の残り 9 本（S1 レーン）と、機械パース正本 2 本を英語化した。これで
`skills/shared/references/` と `skills/spec-verify/references/` の日本語文書はなくなった。
着手時に把握していた S1 は 6 本だったが、`ledger.py --impact` を全ファイルへ回したところ
coverage-ledger / design-system-contract / lang-detect の 3 本も同じ「影響スキルがすべて
fixture 非保有」の区分に入っていたため、同一レーンとして片付けた。

S1 は影響スキルが fixture 非保有（`ledger.py --coverage` で全 uncovered）のため回帰評価は
発生しない区分だが、代わりに**本文の表をテストがパースしている**という別種の結合があり、
そちらが実質的な難所だった。

節見出しがテストのハッシュキーになっている箇所が 3 ファイル・19 個ある。
`test_ledger_lint.py` は agreement-ledger.md の 8 節、`test_spec_lint.py` は clause-schema.md の
5 節、`test_trace_matrix.py` は evidence-manifest.md の 6 節を見出し文字列で引き当て、表の各行を
コード内定数と突合している。見出しはアンカーの実体でもあり、20 箇所から参照されている。
`validate_repo.py` はリンク検証でアンカーを落とすため、ここを取りこぼすと CI は緑のまま
リンクだけが静かに壊れる。本文・テスト定数・アンカーを 1 コミットに収めたのはこのため。

表の中身にもパース対象の日本語リテラルが埋まっていた。clause-schema.md の
`transitions` 説明セルは「`from` / `event` / `to`（必須、string）」という prose 形式で
ネスト規則を宣言しており、`test_spec_lint.py` の `_NESTED_RULE_PROSE` がこれを正規表現で
読んでいる。同様に `1 要素以上` が `MIN_ITEMS` の、`` `id` パターン `` `` `test_id` パターン ``
が ID/digest パターンの突合キーになっていた。訳文に合わせて正規表現とキー文字列も改めた。

- `skills/shared/references/`: context-vocabulary / convergence-pattern / loop-engineering /
  skill-authoring / goal-decomposition-pattern / agreement-ledger / coverage-ledger /
  design-system-contract / lang-detect を英語化
- `skills/spec-verify/references/`: clause-schema / evidence-manifest を英語化
- `skills/ledger/scripts/test_ledger_lint.py` `skills/spec-verify/scripts/test_spec_lint.py`
  `skills/spec-verify/scripts/test_trace_matrix.py`: 見出しキー 19 個、表セルのリテラル 4 個、
  ネスト規則 prose の正規表現を英語見出しへ追随。同期テストは全 green
- `skills/spec-verify/SKILL.md` `skills/spec-verify/references/pbt-binding-guide.md`
  `skills/goal-loop/SKILL.md`: 日本語見出しを指すアンカー参照 20 箇所を差し替え
- `README.md` `AGENTS.md`: skill-authoring.md の節名参照を「When Prompt Compression Works」へ
- 語彙固有状態の enum（`確定` / `暫定` / `競合中` / `廃語`）は原文のまま残した。
  `ledger_lint.py` が `UNSTABLE_TERM_STATES` として直に持つデータ値で、訳すと lint が
  沈黙して壊れる。skill-authoring.md のトリガー語例「『◯◯』『◯◯』で起動」も同様に、
  日本語スキルが description に書くべき literal そのものなので据え置いた
- coverage-ledger.md の Iron Law と report envelope の最小様式は日本語のまま据え置いた。
  後者は `review-testing` / `review-deps` の `report-template.md` にある実テンプレートの
  写しで、両テンプレートは利用者が画面で読むレポートなので日本語が正本のまま。契約側だけ
  訳すと様式が二重化する

---

`skills/` を全面英語化する方針へ切り替えた。従来は「フェンスの中身は読み手で切り分ける」
（実行者向けは訳す / 利用者が読むテンプレートは原文のまま）としていたが、この前提が誤って
いた。**スキル本文は出力言語を決めない**。決めるのはセッション側の指示（ユーザープロンプトや
常駐設定）で、スキルより優先される層にある。スキルが所有すべきなのはレポートの構造であって、
ラベルの自然言語ではない。テンプレートに日本語を焼き込むと「この形式を厳密に守れ」という
スキルの指示と「この言語で応答せよ」というセッションの指示が英語運用のユーザーに対して衝突し、
配布プラグインとして中立でなくなる。例外は「対象そのものが日本語である引用」のみとする。

この方針転換に伴い `check_translation_parity.py` の 2 rule を改めた。旧方針を機械化した
ものであり、そのままでは**正しい翻訳の 100% で発火する**ため安全弁として機能しない。

- `user_facing_template_preservation`（WARN）を削除した。「フェンス内の日本語行が減った」
  「日本語の定型引用が消えた」の 2 検出はいずれも「日本語が意図的に残る」ことを前提と
  しており、全訳方針では全ファイルで鳴る。フェンス内容の消失という実害は
  `structure_parity` の `fence_lines`（BLOCK）が言語非依存で既に捕捉しているため、
  削除しても検出力は落ちない
- `frontmatter_immutability`（BLOCK）を `name` のみの不変検査へ絞った。旧実装は
  frontmatter の byte 不変を要求しており、description の英語化を機械的に阻む。
  description は本方針の対象であり、識別子として保護すべきなのは `name`
  （command / README / manifest から参照される）だけである

`scripts/check_anchors.py` を新設し `run_checks.sh` へ組み込んだ。`validate_repo.py` の
リンク検証はパス部分しか見ず `#` 以降を捨てるため、見出しを改名して参照側を取りこぼしても
**CI は緑のままリンクだけが静かに壊れる**。全文英語化では見出しを大量に書き換えるので、
この取りこぼしが構造的に最も起きやすい区間に入る。S1 では手作業のスクリプトで 1 度
確認しただけで、恒久的な検出手段が無いままだった。

アンカー生成は GitHub 準拠（インラインコード展開 → lowercase → 単語構成文字と空白と
ハイフン以外を除去 → 空白 1 個をハイフン 1 個へ）。連続空白を畳まないのが要点で、畳むと
`spec_lint / trace_matrix` のように記号除去で空白が 2 つ残る見出しの `--` を取りこぼし、
正常なアンカーを壊れていると誤検知する。

`skills/` 配下の全文書を英語へ統一した。本文 93 ファイルと description 45 本が対象で、
本文と description は別コミットに分けてある。description の英語化は発火の回帰が無音
（スキルが呼ばれない → 呼ばれなかったこと自体に気づけない）なので、落ちたときにその
コミットだけを revert できる単位に閉じた。

日本語のまま残したのは、対象そのものが日本語である 3 種類だけである。
`static_checks.py` の `_PROCEDURE_JA_RE` や `ledger_write.py` の `ANSWER_REJECT` が
値として持つ機械リテラル、ユーザ発話を検出するキーワード（「前回の続き」「行き詰ま」等）、
そして翻訳同値を示す言語対照の例示（"component" ⇔ 「コンポーネント」）である。

スイープの過程で、参照先だけが英語化され参照する側の散文が旧節名を指したままの
リンク切れを 6 件見つけて直した（`§restore 判定` / `"CLI 呼び出し規約"` /
`§スコアバンド用法` / `「doc-check の \`OK\` との差異」` 2 箇所 / `「文脈検証の3値判定」` /
`「機密情報の規約」`）。あわせて `artifact-store.md` が issue 本文を `## 概要` と
記述していたのを `## Overview` へ直した。`issue-template.md` は以前から `## Overview` で、
契約側の記述だけが実体と食い違っていた。

`verification-gate.md` の禁止表現を固定リストから意味規定へ変更した（翻訳ではないため
独立コミット）。従来は列挙した語形しか捕捉できず、本文英語化で英語運用が一級の想定に
なった以上 "should be fine" 等が素通りする。ゲートが守るのは語形ではなく「検証前に
正しさを主張しない」という意味なので、列挙は例示であって allowlist ではないと明示した。

英語化スイープの事後二軸実測を完走し、regression 台帳を `accepted-without-run` から
実行結果へ進めた。**英語化は品質を落としておらず、description コミットの revert は不要**
と確定した。発火軸（trigger-eval、188 ケース・判定 576 件）は selection の macro
recall 0.9947 / precision 0.9929 / specificity 1.000 / stability 1.000 / invalid_rate
0.000 で、判定前に宣言して固定した閾値をすべて上回った。達成軸（skill-regression、
fixture 保有 20 スキル・67 シナリオ）は 18 本が critical 全 ○ で `pass`、残る 2 本は
`accepted-without-run` に留めた。

台帳を進めなかった 2 本はどちらもスキルの回帰ではない。`brainstorm` は bs-003 が
「Codex 利用不可時の縮退表示」を要求するが清浄な環境では codex CLI に到達できてしまい
縮退が起きず、fixture の前提が実体化されない。`decision-journal` は dj-004 が 3 回とも
接続断で report を落とした実行基盤の制約である。どちらも note に理由を残した。

`--note` にはプロセス経路（`claude-exec` バックエンド）での実行であることと、読み取り
専用要件を `.claude/` 外の清浄な場所で再実行して裏取りしたことを記録した。`.claude/` 配下を
実行者の作業ディレクトリにすると書き込みが自動拒否され、「行儀よく書かなかった」と
「書けなかった」がどちらも drift 0 になって読み取り専用要件の検証が無力化する。経路差を
残さないと、次に subagent 経路で走らせた人が食い違いを原因不明の回帰と誤読する。

confusion は全行列でオフダイアゴナル 1 セル（`plan-implement` → `cycle`）のみで、これは
日本語時代のトリガー語「この計画を自動実装」「計画を自動実装して」が最初から衝突していた
ものを英語版が忠実に保存した結果である。`plan-implement` が `cycle` の真部分集合という
責務境界の問題なので、description の改稿ではなく設計裁定として別途扱う。

Tier 2（実発火検証）は前提未成立のため保留した。実行セッションがロードするのは
プラグインキャッシュであってリポジトリの `skills/` ではなく、47 スキル中 44 本で
description が食い違う（キャッシュ側は日本語のまま）。成立には version bump と再
インストールが要るが、それはリリース判断であり実測タスクの範囲外である。

`github-issue` の issue 番号検証を、生文字列に正規表現をかける形へ直した（issue #57）。
`polling-adapter.md` の擬似コードは `int()` で変換してから `str(N)` に
`^[1-9][0-9]*$` をかけており、**`007` が `7` に正規化されて検証を素通りしていた**。
同ファイルの散文は「zero-padded を拒否」と明記しているので、規定と実装例が食い違っていた
ことになる。ゼロパディングを許すと、存在する別 issue に対して書き込む誤爆になり得る
（`issue-007` を掴んだつもりで #7 にラベルを付けコメントする）。パターンは変換前の
文字列にかける必要がある。

あわせて失敗識別子の表記揺れを解消した。SKILL.md が `"invalid issue number"`
（スペース区切り）、`polling-adapter.md` が `invalid issue_number` と
`invalid issue_number format` の 2 系統を持っており、同一ゲートの失敗が 3 通りの文字列で
記録されうる状態だった。失敗記録の横断検索が効かないため `invalid issue_number` へ 1 本化した。
上記の修正で parse 失敗と format 失敗の分岐そのものが 1 つに畳まれたので、識別子を分ける
理由も消えている。

`fixtures.json` の gi-003 が要件文で参照していた旧表記も追随させた。要件は
「`invalid issue number` に相当する失敗として扱っている」という緩い書き方のままで、
参照先のトークン名だけを実体に合わせている（シナリオを通しやすくする変更ではない）。
プロセス経路で全 4 シナリオを再走し、critical 全 ○ かつ baseline_drift 0 を確認して
台帳を更新した。

## 1.65.0

ledger の常時ロード本文を 368 行から 42 行へ縮約し、`extract` / `session` / `orient` の
手順をworkflow別参照へ分離した。選択したworkflowだけを読む構造にして、`status` は参照を
追加読込しない fast path として維持。重複していたテンプレート集を廃止し、実行に必要な規約と
出力形式を各workflowへ局所化した。description も一覧の冒頭だけで用途が伝わる形へ短縮した。

- GPT-5.5 の3役分離 empirical evaluationで、extract / session / status / orient の4シナリオを
  独立checkerで検証し、圧縮で失われた契約を反復補完
- trigger-eval: ledgerと近接6スキルの固定24ケースを短縮前後・selection / autonomousでA/B判定。
  4系列すべて24/24、ledgerは recall / precisionとも1.0で非劣化
- `skills/ledger/SKILL.md`: 不変条件・workflow router・status fast pathだけを常時ロード
- `skills/ledger/references/`: extract / session / orient を独立参照化し、旧
  `ledger-templates.md`を削除

## 1.64.0

commit スキルに、コミットメッセージを単体で理解可能な履歴として残すための内容契約を追加。
変更後の成果を記述し、実装計画の工程ラベル・エージェントの作業経緯・一時的な会話文脈を
メッセージへ含めないことを明文化した。既存履歴への追従は言語と語調に限定し、自己完結性と
Conventional Commits を優先する。安定した issue・仕様・アーキテクチャ参照は許容する。

- gpt-5.5 の 3 役分離 empirical evaluation: 工程文脈を含まないメッセージが変更前 1/3 から
  変更後 9/9（3 シナリオ × 3 iteration）へ改善。独立 checker の最終 precision は 96.7%
- skill-regression: 既存 3 fixtures（無関係変更の分割 / `.env` 除外 / 変更なし abort）を
  gpt-5.5 の隔離 worktree 実行で全件再検証し、ledger を更新

## 1.63.0

プロンプト圧縮の横展開バッチ4（cycle + handoff）。cycle は fixture 非保有だったためシナリオ 3 本
（フルサイクル正常系 / パス検証中断 / 完了済みスキップ + status.md 不在の部分失敗許容）を新規
設計・事前ロックし、委譲チェーン一式（plan-refine / plan-implement / plan-reviewer / commit +
共有契約）を同梱した scratch でインライン fallback 経路ごと計測。handoff は既存 fixtures
（ho-001〜004）を事前固定のまま流用。いずれも Opus 3 役分離 2 iteration で全シナリオ全 iteration
precision 1.0。Codex セカンドオピニオン「修正後反映可」の important 4 件 + minor 1 件を全反映。

- cycle: 本文を英語に統一し非 ASCII 4,555→510、トークン近似 -39%。ユーザー向け固定出力
  （CYCLE ブロック・「実装対象の計画がない」）は Codex 指摘に従い旧版から逐語維持。
  明示化: インライン実行時は委譲 relay / 待機規範 / リトライ節が不適用という signpost
  （他スキル起動不可時のインライン代替も含む）/ Step 1.5 の中断は CYCLE START 表示前 /
  status 完了処理の Case 2 は Phase ラベル非依存 / 計画 Status ヘッダ検証を guard 非依存の
  Step 3d に独立（失敗名 "plan status update"）/ Steps の出典 = Progress 表 /
  {plan_basename} = 拡張子なし / mv 案内は新規誤配置向けで legacy 配置は migration 対象
- handoff: 本文を英語に統一し非 ASCII 2,768→609、トークン近似 -29%。日本語の固定出力
  テンプレート（引き継ぎ内容 / Handoff 一覧 / 📝 つまり / 完了報告）と handoff ファイル書式は維持。
  明示化: restore と list で共有する ordering rule を一元化（真の mtime 同一時のみファイル名
  タイムスタンプで tie-break、ls の粗い表示一致を tie と扱わないことを Codex 指摘で厳密化）/
  Restore サマリの branch・現在地の出所（frontmatter / TL;DR + 現在の状態）/ status.md 不在 =
  active plan なし / checkpoint fallback の superseded 削除提案はユーザー確認つき（契約準拠を
  Codex 指摘で復元）/ restore・list は reader でディレクトリを作らない
- cycle/fixtures.json 新規（cy-001〜003、skill-regression 台帳登録済み）。handoff は既存
  fixtures のまま台帳更新。計測記録: .claude/tmp/empirical/20260722-lean-rollout/ バッチ4 節

## 1.62.0

プロンプト圧縮の横展開バッチ3（brainstorm + 長文 description トリム）。brainstorm は fixture
非保有だったためシナリオ 3 本（Wrap 永続化 / Plan 単一エントリ選択 + アーカイブ choreography /
Session 単一ターンの stuck 検出・Codex フォールバック・編集ゼロ）を新規設計・事前ロックし、
Opus 3 役分離で 2 iteration 計測。critical 要件は全シナリオ全 iteration pass、instruction 起因の
摩擦 5 件が明示化で消滅した。Codex セカンドオピニオン「修正後反映可」の important 4 件を全反映。

- brainstorm: 本文を英語に統一し 281→223 行（-21%）、非 ASCII 3,573→691、トークン近似 -40%。
  ユーザー向け出力テンプレート・日本語トリガーキーワード・日本語問いかけ例は機能要件として維持。
  明示化: kebab-title の ASCII 訳定義 / 非対話実行時の分岐（Wrap Step 2・Plan Step 2）/
  ⚠️ Codex unavailable 通知を含む固定出力順 / plan-create 完了メッセージの抑制 / Plan Step 7 の
  slug 範囲。Codex 指摘反映: 実装提案禁止の明示復元、Resume ループの状態変数初期化、slug 同秒
  衝突時の上書き防止、非対話 Wrap で機密検出時は書き込まず停止、技術の引力の問いかけ例復元、
  plan ファイル存在確認後にのみアーカイブ
- brainstorm/fixtures.json 新規（bs-001〜003、skill-regression 台帳登録済み）
- description トリム（issue 20260717202712 項目 (2)）: trigger-eval 585→415 字 /
  context-audit 450→332 字 / goal-decomposition 458→311 字。CLI フラグ説明・ワークフロー要約を
  本文へ委譲しトリガー語は全維持。選択層回帰（事前ロック 20 ケース × before/after × 2 独立判定）
  で 4 系列すべて 20/20 — 発火の非劣化を実測確認

## 1.61.0

プロンプト圧縮の横展開バッチ2（issue）。バッチ1 で確立した言語ポリシー（本文英語統一）と
明示化アプローチを issue スキルへ適用した。計測は empirical-prompt-tuning の 3 役分離を
Opus（本番同等モデル）で実施し、fixtures.json の全 4 シナリオ（polling 3 + create 1）を
事前固定のまま流用して 2 iteration とも precision 100% を維持。instruction 起因の摩擦 8 件が
明示化で消滅した（friction 総数 17→14、残存はシナリオ文言・契約参照設計・本質的判断領域のみ）。
Codex セカンドオピニオンの important 指摘 1 件も反映済み。

- issue: 本文を英語に統一（非 ASCII 1,520→213 文字、トークン近似 -9%。ユーザー向け出力
  テンプレートと日本語契約見出しの引用は機能要件として維持）。Early halt 注記（kill file halt と
  初回 dry-run 強制の優先順位、halt 時は Step 15 まで実行しない）、.polling-initialized 事前作成
  による dry-run バイパス禁止、title frontmatter の原語維持（英訳は slug のみ）、free-form 時の
  tags 推論既定値、dry-run tick の Step 13–15 実行を明文化。重複していた末尾の
  issue-status.md Format セクションを削除（333→316 行）
- issue/references/polling-state.md: 宛先ディレクトリ不変条件を §1 に一元化（Codex 指摘 —
  orphan rollback だけの mkdir では release / mark_done / mark_failed に同じ穴が残る）。
  is_alive の 3 分岐（エラーなし = alive / ESRCH = dead / EPERM = alive fail-safe）を明文化
- skill-regression ledger を issue で更新（iter2 全合格 + checker の実地検証エビデンス）

プロンプト圧縮の横展開バッチ1（commit / plan-reviewer）。1.58.1 で確立した「プロンプト圧縮の
効果条件」プレイブックを、skill-improve の使用頻度実測（30日・141セッション・455起動）で
裏取りした優先順位に従って適用した。計測は empirical-prompt-tuning の 3 役分離を Opus
（本番同等モデル）で実施し、commit 4 iteration / plan-reviewer 3 iteration とも
全シナリオ precision 100% を維持。摩擦は commit 6→1、plan-reviewer 9→7（contradictory /
missing_premise 系は消滅）。Codex セカンドオピニオンの important 指摘 2 件
（逐次モード入口条件の未定義ケース / Review 8「always runs」と逐次モードの矛盾）も反映済み。

- commit: Phase 1.5 を verification-gate 契約参照に集約、Phase 3.2 の例示コード削減、
  機微ファイル除外を Phase 3.1 に一本化（ダミー値でも除外を明文化）、type 選択・subject
  言語・コミット順序の既定値を付与（176→160 行）
- plan-reviewer: Reviews 1-7 の inline 観点一覧 58 行を review-dimensions.md 正本参照の
  14 行テーブルに集約、Step 4 の待機規範二重記述を解消、逐次モードの入口条件・Codex
  非起動・報告文言を明文化、Step 2.5 キーワードの意味照合（日英対応語）を明記（245→202 行）
- fixture 資産化: skills/plan-reviewer/fixtures.json を新規追加（empirical-tuning 由来の
  2 シナリオ）、skill-regression ledger を commit / plan-reviewer とも全合格エビデンスで更新
- 本文の言語統一（英語）: 圧縮時に追加した日本語節が英日混在を悪化させていたため、
  ユーザー裁定で commit / plan-reviewer の本文を英語に統一した。tiktoken o200k 実測で
  同内容の日本語版は約 +30%（commit: 英 1,607 vs 日 2,091 tokens）、混在だった
  plan-reviewer は英語統一だけで 3,758→3,025 tokens（-19.5%）。Codex も第一級の読者の
  ため o200k の効率が直接効く。日本語トリガー語彙を含む frontmatter description、
  日本語契約見出しの引用、照合語彙の例示は機能要件として日本語のまま。言語ポリシーは
  skill-authoring.md「クロスツール互換性の注意」に正本化。統一後も全 5 シナリオを
  Opus で再計測し precision 100% を確認
- 計測記録は .claude/tmp/empirical/20260722-lean-rollout/（ローカル）の summary.md と
  iterations.jsonl を参照

## 1.59.0

AgenticTeam 実験用に作った team-* 系スキルを廃止する。実験目的（AgenticTeam の検証）は
達成済みで実利用がほぼ無く、フロンティアモデルでの実行はコストが高すぎる一方、安価モデルへ
逃がすとプロンプト圧縮実験（1.58.1 の効果条件）の前提が崩れて逆効果になりうるため、
安価化存続ではなく廃止を選択した。使わなくても 4 スキル分の description が毎セッション
常駐コストを払い続ける点も廃止理由の一つ。通常の cycle には plan-reviewer の 7 観点 +
Codex セカンドオピニオンが既に入っており、品質ゲートはそちらが正本。

- 削除: `skills/team-brainstorm/` / `skills/team-cycle/` / `skills/team-plan/`、
  共有ロール定義 `skills/shared/references/team-config.md`、入口 command 6 個
  （team-plan / team-cycle / team-brainstorm / team-brainstorm-wrap /
  brainstorm-team-cycle / issue-team-cycle）
- 参照整理: brainstorm（--team-cycle 分岐削除）/ issue（--team 分岐・issue-team-cycle
  推奨導線削除）/ investigate / skill-improve（Large 委譲先を cycle へ変更）/
  orchestration-patterns（チーム議論パターン節を削除しパターン番号を振り直し）/
  severity-and-verdicts / human-readable-summary / tool-mapping / README /
  codex-plugin manifest（team-discussion capability 削除）

## 1.58.1

PR #3（empirical-prompt-tuning 実測に基づくプロンプト圧縮）が plan / cycle スキルと共有契約
（artifact-store.md / checkpoint-pattern.md / skill-authoring.md）を変更したが version bump を
含んでいなかったため、配布反映用の patch bump を追う。スキル本文の変更は bump が無いと
マーケットプレイス経由の利用者に届かない。

- `skills/plan/SKILL.md`: checkpoint 二重説明の契約参照への集約・Phase 2 Required info と
  スラグ規則の圧縮（315→248 行、friction 19→12 / precision 100% 維持の実測に基づく）
- `skills/cycle/SKILL.md`: 委譲結果受渡し節を orchestration-patterns.md の契約参照に集約
- `skills/shared/references/skill-authoring.md`: 「プロンプト圧縮の効果条件」節を新設
  （効くパターン / 効かないパターン / 削ってはいけない規約の判断基準を実測から正本化）
- `skills/shared/references/artifact-store.md` / `checkpoint-pattern.md`: rationale・
  v2 ロードマップ等のメタ情報を削減
- `README.md`: 「プロンプト設計方針」節を追加（skill-authoring.md への導線）
- 本エントリは bump のみで、上記変更自体は PR #3（1b9b7ba）に含まれる

## 1.58.0

ledger の考古学モードに「現在形の静的リファレンス（フィールド表 + `⚠️未規定` マーカー）」を
生成する第 3 ストリームを追加。extract を 2 ストリーム（合意候補 + 語彙候補）から 3 ストリームへ
拡張する。pilot 第 2 号（automation-visualize）で、考古学モードの回答者が「フィールドの役割の
ドメイン知識がない。まず今の仕様のドキュメントが欲しい」と停止し、運営がアドリブで作った現状
リファレンスが転換点になった。しかも `⚠️未規定` マーカー付きのリファレンスはそのまま裁定の弾リストとして
機能し、以後の全クラスタがこれを起点に回った（実証済み）。このアドリブを再現可能な工程に固化する。

- `skills/shared/references/agreement-ledger.md`: 用途 2 モード節を共通 regime の正本に格上げ。
  考古学の文脈回復 2 点セット（物語=orient / 静的=現状リファレンス）と、両者が共有する regime
  （非権威・使い捨て・未署名・書き出し前 secret scan・injection 防御）を正本化。スキーマ本体は不変
- `skills/ledger/references/ledger-templates.md`: 現状仕様リファレンステンプレートを追加。列定義
  （項目 / 現在の挙動 / 出典 / 状態〔`⚠️未規定` or 規定〕/ 台帳行 ID）+ 使い捨て・未署名ヘッダ +
  secret 三択規約（参照場所のみ / redact / 出力しない）+ 文書レベル scan。共通 regime は相対リンク参照
- `skills/ledger/SKILL.md`: extract を 3 ストリーム化（生成条件〔考古学必須・その場記録は既定 OFF〕・
  台帳行 ID 参照検証・orient モデルの文書レベル secret scan）。session 考古学モード導線を 2 点セット化し
  `⚠️未規定` を advisory な弾リストとして消費、orient 節に対比 back-reference、書き込み境界表に
  orient 同型の独立行を追加、機密節の scan 対象列挙に散文リファレンスを追記。frontmatter description・
  ワークフロー選択テーブルは条件付き内部工程のため据え置き

## 1.57.1

brainstorm SKILL.md の idea-status 行仕様が導出インデックス契約とドリフトしていた問題の修正
（issue 20260710191406、plan 20260710182348 最終レビュー WARN-6 起源）。idea-status.md は
rebuild-index が各エントリの `#` 見出しから再生成する導出キャッシュであり、実データも実装
（artifact_store.py の `_render_index`）も人間可読タイトルをリンクテキストに使うのに、SKILL.md
だけが kebab-title と記述していた — rebuild 実行のたびに Plan workflow の Title 出典記述が
成り立たなくなる。

- `skills/brainstorm/SKILL.md`: Wrap Step 7 の行テンプレートのリンクテキストを
  `{kebab-title}` から `{アイデアの # 見出しタイトル}` へ訂正し、導出インデックス契約に
  従う理由（rebuild-index が `#` 見出しから再生成する）を明記。Plan Step 3 の Title 出典の
  括弧書きを「= アイデアファイルの `#` 見出しタイトル」へ訂正

## 1.57.0

delegation result relay（1.55.0）は「結果の正本はファイル・報告メッセージは通知」という
書き手/読み手の義務を定めたが、**待つ側の待ち方**（待ち時間の上限・通知に依存しない再検分・
上位からの停滞検知）に規範がなかった。ledger_write CLI の cycle で 2 種類の停滞が実測された:
無応答の 1 観点（Codex）を約 47 分待ち続けた片翼欠けの無限待ちと、4 観点全部の結果ファイルが
書き込み済みなのに完了通知が届かず約 24 分集約に入らなかった揃い済みの気づき損ね。どちらも
作業と結果ファイルは健全で、欠けていたのは待つ側の規範だけだった。共有契約に待機規範を追加し、
参照スキルへ役割固有パラメータだけを配線する。

- `skills/shared/references/orchestration-patterns.md`: delegation result relay の (3) 直後に
  「(3b) 待機規範（wait discipline）」を正本として追加。3 本柱（通知非依存の再検分／待ち時間
  上限 既定 10 分 + degraded 続行／上位 watchdog の対称化）を規定し、自己タイマーが完全無音の
  末尾で発火しない問題は watchdog を最終 backstop に・親を持たない最上位は bounded re-check を
  発火経路に、という補完関係を棄却理由込みで明記。リトライ予算の非乗算（再委譲は観点あたり 1 回・
  watchdog の催促は別枠）も規範本文で固定
- `skills/plan-reviewer/SKILL.md`: Step 3（実行・結果受渡し）と Step 4（集約）の「揃うのを待って
  読む」を両方とも待機規範参照に更新し drift を防止。役割固有パラメータ（10 分／任意 = Codex／
  必須 = 起動した Claude 観点で 1 回再委譲、トリガーされた UI/UX は必須扱い、standalone は
  bounded re-check）を配線
- `skills/cycle/SKILL.md`: 委譲結果受渡し共通節に上位 watchdog 手順を追記し、既存 Troubleshooting の
  無音停滞行にも契約参照を張って同一手順であることを明示（重複記述を作らない）
- `skills/plan-refine/SKILL.md`: relay 節に中間オーケストレーターとしての待機義務参照を追加

## 1.56.0

pilot 第 2 号（automation-visualize・65 行裁定）で実測された、承認バッチごとに digest
計算・approval オブジェクト・batch manifest を Python ヒアドキュメントで毎回 50 行前後 ×
計 8 回手書きするコストと digest 手計算ミスのリスクへの構造的対策。ledger_lint が read-only
なのは正しい設計だが、書き込み側の支援が無いため摩擦が人間側に残っていた。読み（lint）と
書き（write）を分離し、digest 込みの書き込み CLI を新設する。

- `skills/ledger/scripts/ledger_write.py`: 書き込み CLI を新設。add-row / approve /
  reject / batch-approve のサブコマンドで行追加・状態遷移・batch manifest 生成を機械化する。
  digest・構造検証は `ledger_lint.compute_digest` / `compute_batch_digest` / `lint_data` を
  import して再利用し write 側に規則を複製しない。自己検証は verify-before-swap 方式
  （in-memory で lint → hard findings 無しのときだけ tempfile + os.replace でアトミック置換・
  不正内容を一瞬もディスクへ永続化しない）。approve/reject/batch はセッション成果物の人間
  回答を consume する経路に構造的結合し、任意 session-id だけの standalone 承認入口を持たない。
  actor_kind は human 内部固定。exit code 0/1/2 を ledger_lint と整合。containment（--root
  必須・symlink/root 外拒否）と secret pre-flight で fail-closed
- `skills/ledger/scripts/test_ledger_write.py`: 36 件のテストを sibling 配置で追加。add-row/
  approve/reject/batch-approve の契約・verify-before-swap・exit code・containment・secret・
  diff 不変条件・session 構造的結合・高リスク batch 拒否を固定
- `skills/shared/references/agreement-ledger.md`: 「書き込みの正本（記録の道具）と read-only
  検証の分担」節を追加（SyncTests の機械パースを避けた純散文）
- `skills/ledger/SKILL.md`: 「書き込み実行（ledger_write CLI）」節を追加し session §5 の記録を
  CLI 経由に案内。書き込み境界表に ledger_write 行を追加。手書きフォールバックは維持
- `README.md`: ledger の説明に書き込み CLI を反映

## 1.55.0

サブエージェント委譲の結果・完了報告がオーケストレーターへ戻らない到達性問題
（作業完遂 + 報告なし + 待機通知のみ／配下で並行起動したレビューの結果が委譲元に
戻らない、が実測されている）への構造的対策。完了報告メッセージの配達は非決定的だが、
ファイル書き込みは委譲先自身の作業として確実に完了検証できる。この非対称性を使い
「結果の正本はファイル、報告メッセージは通知」に置き換える委譲結果のファイル受渡し
（delegation result relay）を共通契約として正本化し、影響スキルへ横展開する。

- `skills/shared/references/orchestration-patterns.md`: 「委譲結果のファイル受渡し
  （delegation result relay）」節を追加。パス規約 `.agents/runtime/delegation/{run_id}_{role}.md`・
  書き手/読み手の義務・待機通知を検分トリガーに格上げする受信手順・成果物直接検分の
  フォールバック・掃除・適用範囲・セキュリティを規定。支配原則2 の `.claude/tmp/` 中間結果
  （コンテキスト劣化回避が目的）と本節の委譲結果の正本（配達失敗耐久性が目的）を相互
  リンクで棲み分け、契約の自己矛盾を防ぐ
- `skills/cycle/SKILL.md`: Phase 1/1.5/2 の委譲プロンプトに結果ファイルパスを指定し、
  受信手順を「報告 or 待機通知トリガーで結果ファイルを読む→欠落時は成果物検分」に改修。
  エラーハンドリングに「報告なしで停止した場合」の分岐を新設。Phase 2 の既存『結果ファイル』
  言及をパス規約 `{run_id}_implement.md` に統一
- `skills/plan-reviewer/SKILL.md`: Step 3 ファンアウト（issue パターン①の本丸）で各観点/
  Codex に判定を `{run_id}_review-{dim}.md` へ書かせ、Step 4 集約側が全観点ファイルを待って
  読む。逐次実行フォールバックは保持
- `skills/iterate/SKILL.md`: Phase 3 実装エージェントに指示項目ごとの完了状況を結果ファイルへ
  書かせ部分欠落の黙過を防止。Phase 4 レビュー/Codex も結果ファイル経由に
- `skills/plan-refine/SKILL.md`: plan-reviewer 呼び出し境界を結果ファイル方式前提にし、
  報告未達でも集約結果→観点別ファイル群→計画本文の順で成果物検分に落とせるようにする。
  インラインレビュー代行はフォールバックとして保持
- `skills/skill-regression/ledger.json`: orchestration-patterns.md の純追加変更に対し
  github-issue / issue を `--accept`（依存する polling パターン6 に触れないため影響なしを明示記録）

## 1.54.1

automation-visualize での pilot 第 2 号（65 行裁定 + 語彙 15 語を約 2 日・理解修復
イベント 0 で完走）の実測フィードバックのうち、設計変更を伴わない軽量級 4 項目を反映する。
重量級（extract 第 3 ストリーム「現状仕様リファレンス」・ledger_write CLI）は issue 管理で後続。

- `skills/ledger/scripts/ledger_lint.py` + `test_ledger_lint.py`: term_refs が省略 or
  空配列の行に report-only の advisory `term-refs-empty` を追加（全行対象）。承認後の
  後付けは digest を変えて承認を失効させるため、裁定前の記入を促す。型違反は既存の
  invalid-type / empty-string（gate 対象）の管轄で、責務分担をテストで固定（+9 テスト、計 116）
- `skills/ledger/SKILL.md`: 解釈確認ゲートの適用基準を明文化 — 対象行が名指しで一意な
  直接回答は即記録 + 事後訂正可、曖昧・複合・指示語つきの自由文のみゲートを通す
  （迷ったらゲート側 = fail-closed 維持。pilot 実測で「全自由文ゲート」はテンポを殺すと判明）。
  oracle 計測に「疑問が実装の空白を言い当てた件数」（要件発見の検出力指標）を追加
- `skills/ledger/references/ledger-templates.md`: 行 ID prefix・session_id の採番目安を
  追記（契約は形式を規定しない・人間向け慣習）
- `skills/shared/references/agreement-ledger.md`: (c) term_refs 空白検出 advisory を契約に
  追記（語彙非依存の行は無視してよい・型違反は型検証の管轄、の責務分担込み）

## 1.54.0

ledger パイロット第 1 号で裁定セッション（4 択一問一答）が「儀式化を回避するための
スキルがそれ自体儀式化した」失敗を起こした。原因は 3 つ — claim が How 語彙で裁定不能・
共有文脈ゼロの考古学モードに文脈回復工程がない・語彙層（CONTEXT.md）の生成フローが
未配線。壁打ち + Codex 3 往復で収束した設計「対話を入口・台帳を出口」を claude-skills 側へ
配線する。superpowers 型の対話フロントエンドを状態付き台帳のバックエンドに接続し、
沈黙時の失敗モードだけを fail-closed に反転させる（黙っていると合意 → 黙っていると未裁定）。

- `skills/shared/references/agreement-ledger.md`: (1) 用途 2 モード（その場記録 =
  リスク順 / 考古学 = 物語順・考古学は文脈回復工程を必須化）(2) claim の語彙規範
  （What で書く・How は demote-but-reachable・What 投影不能な純アーキ決定は
  decision-journal 送りの discriminator）(3) batch 承認の真正性規約とトップレベル
  任意キー `batch_manifests` の schema（高リスク・異論行は batch 不可）(4)
  pending-vocabulary を派生検出として定義（5 状態 enum 不変・(a) AGREED 限定
  エスカレートは確定 / (b) 競合中・廃語依存は advisory）。`risk` フィールドを共通 row に追加
- `skills/shared/references/context-vocabulary.md`: 語彙生成フローの正本化（extract の
  副産物・1 パス 2 ストリーム・cold-start batch / 定常 streaming・admission フィルタ・
  セッション外自動育成は候補と鮮度まで自動で確定は人間）
- `skills/ledger/scripts/ledger_lint.py` + `test_ledger_lint.py`: batch_digest 整合・
  高リスク行の batch 混入・pending-vocabulary 派生検出（(a) finding /(b) advisory）を
  実装。`load_context_terms` を `{id: state}` 返却へ拡張。advisories を report-only
  ストリームとして分離（--strict でゲートしない）。schema 追加ゼロ or 任意キー/任意
  フィールドのみで後方互換（既存 schema_version 1 台帳は無改変で valid）。TDD で
  107 tests green、doc⇔code スキーマ同期テストを併せて更新
- `skills/ledger/SKILL.md` + `references/ledger-templates.md`: session を対話ハイブリッド化
  （モード判定・テーマ単位対話・判断スロット・解釈確認ゲート・沈黙 = UNDECIDED・まとめ
  確認）。extract v2（2 ストリーム・What 規範・term_refs 必須・受け入れ --context 必須）。
  orient 新設（plan 履歴を物語順に翻訳した ADR 風オリエンテーション文書・使い捨て・非権威・
  secret ゲート付き）。oracle 計測（理解修復イベント数）を完了報告へ追加。文章規範は
  japanese-tech-writing を名前参照（別プラグインのため相対リンクは張らない）
- 生成フローは「契約 + detector」までに留め、候補の自動昇格ロジック・admission 閾値の
  チューニングは pilot 第 2 号の実測後に iterate へ回す（作り込まない）

## 1.53.1

ledger 裁定ビューを実プロジェクトでパイロット実行したところ、「[ENG-006] 同一の排他キーを持つ
未終了 run は高々 1 本であり…」のような行が文脈ゼロ・専門語のまま提示され、人間が「何の話か
わからない」と裁定不能になった。裁定ビューに (1) 冒頭の文脈説明がない (2) 行が専門語のまま
(3) OK した帰結の説明がない (4) 内部トレーサビリティ ID がノイズとして混入する、という 4 欠陥を
パイロット実測フィードバックとして反映する。

- `skills/ledger/references/ledger-templates.md`: 「セッション冒頭ブリーフィング テンプレート」を
  新設（何について何件裁定するか・進め方・中断できることを 3〜5 行で伝える）。裁定行提示テンプレートに
  領域ラベル行（◆ ...・塊の先頭のみ）・「つまり」（平易な言い換え）・「OK すると」（承認の帰結 1 行）を
  追加し、ENG-006 型の分かりにくい実例を反面教師にした before/after 例を追記。生成規約として、平易さの
  合格基準（[human-readable-summary.md](skills/shared/references/human-readable-summary.md) が正本）・
  専門語の初出展開・内部トレーサビリティ ID の非表示を明記
- `skills/ledger/SKILL.md`: session ワークフローに手順 0（冒頭ブリーフィング必須）を追加し、手順 2
  （各行の提示）に領域ラベル・つまり一文・OK すると帰結を組み込み。裁定ビューは「正本を読んだ人にしか
  通じない書き方をしてはならない」という原則を明記
- ドキュメントのみの変更（実行コードへの影響なし）のため TDD 適用外。`sh scripts/run_checks.sh` で
  既存スイートの回帰なしを確認

## 1.53.0

レポート生成系スキルの完了報告に「発話サイズのヒューマンリーダブル要約」を必須化する横展開。完了報告が「✅ + ファイルパス + 定型 Next Steps」のみで生成物の中身が人間に伝わらず、承認・把握が儀式化していた問題への構造的対策。認知負荷を下げるのは行数の圧縮ではなく説明の平易さ、という設計原則（ユーザー裁定 2026-07-21）を共有契約として正本化する。

- `skills/shared/references/human-readable-summary.md`（新規）: 完了報告要約の共通契約。読者分離の原則（正本 = LLM 向け / 完了報告 = 人間向け）・必須要素・上限 10 行前後・summary-first 配置（固定ラベル「📝 つまり:」を完了表示最上部に置く）・縮退規定（欠損は捏造せず明示、秘密値は省略）・アンチパターン・before/after ワークト例を定義。agreement-ledger Phase B2（plan/plan-implement/cycle への組み込み）が後から本契約を参照する依存逆転のアンカーを内蔵
- 対象 6 スキルの完了表示に契約リンク付き要約を組み込み: brainstorm / team-brainstorm（アイデアの核 + 未決定点）、issue（タイトル + 課題要旨のエコー）、handoff save（ゴール / 現在地 / 次の一手）、doc-write（文書要旨 1 行）、design-guide（色調 / フォント / トーンの 3 行）
- `validate_repo.py` にチェック14 `check_human_readable_summary` を追加: 契約の before/after 例の存在と、6 スキルの完了表示が契約リンク + 固定要約ラベルを持つことを run_checks で常時強制する統一テキストガード。fixtures を持たない 4 スキル（brainstorm / doc-write / team-brainstorm / design-guide）の要約"挙動"はこのテキストガードが最低ガードになる
- `skills/issue/fixtures.json`: Create 完了報告の要約を要求する is-004 を追加し、skill-regression 白紙実行者で 5/5 要件 green を確認。ledger を issue=pass / handoff=accepted-without-run（save はライブ会話履歴が必要で fixture 化不可・restore 系 fixtures は挙動不変）で再検証記録

## 1.52.0

合意台帳ワークフロー（agreement-ledger）の Phase A（最小スライス）を追加。greenfield 案件で LLM が仕様の空白を暗黙補完し「思っていたのと違う」が多発する問題への構造的対策として、現在有効な合意を状態付きで正本化する台帳と、中心命題「LLM は提案者になれるが承認者になれない」の機械検証を導入する。

- `skills/shared/references/agreement-ledger.md`（新規）: 台帳スキーマ v1 の正本。5 状態（AGREED/DELEGATED/PROVISIONAL/UNDECIDED/REJECTED）と、AGREED 遷移を「人間が提示 revision へ明示回答した承認イベント + 主張 digest 一致」からのみ生成可能にする承認真正性規則を定義。機械検証の正本形式は JSON を採用（CI/pre-push の最小環境に標準 YAML パーサがなく外部依存ゼロ方針と両立しないため。spec_lint の fail-closed 機構を再利用）
- `skills/shared/references/context-vocabulary.md`（新規）: 語彙層 CONTEXT.md 契約と、ledger_lint が読む機械可読語彙ファイル形式
- `skills/ledger/`（新規スキル）: `ledger_lint.py`（構造 lint・承認真正性の機械照合・secret redaction・path containment・read-only・57 テスト）+ SKILL.md（extract / session / status の 3 ワークフローを第 1 引数でディスパッチ）+ ledger-templates.md
- Phase B（context-vocabulary.md 二重状態整合・plan/plan-implement/cycle の条件発動ゲート・Extra 検出・CONTRACT_VOCAB）と Phase A4（automation-visualize での対話裁定パイロット）は、plan の pilot-first 設計に従い pilot 結果を受けて確定する（PROVISIONAL）

## 1.51.2

frontmatter description の strict YAML 非互換を解消。attack-review / goal-decomposition / handoff の description はクォートなし値に生の `: `（コロン + スペース）を含み、本リポジトリや Claude Code の寛容な行ベースパーサでは読めるが、strict YAML 実装（PyYAML / Go yaml 等）を使う他プラットフォームのツールでは frontmatter 全体が parse error になりスキル自体が読めなかった（Agent Skills 評価ツール waza の check + PyYAML で実測確認）。マルチプラットフォーム対応方針に反するため文言側を修正する。

- 3 スキルの description から生の `: ` を除去（トリガー語は維持。attack-review は英語スキル定番の "Use when the user says" 形式へ、goal-decomposition は `status=draft`、handoff は句点区切りに変更）
- validate_repo.py にチェック13を追加: frontmatter のクォートなし値に `: ` / 末尾コロン / ` #`（strict YAML でコメント扱いになり黙って切り捨てられる）があれば CI で落とし、同種の互換事故の再発を機械的に止める
- handoff は description の文言のみの変更のため、regression ledger を accepted-without-run で再検証記録

## 1.51.1

decision-journal を empirical-prompt-tuning の実測（3 イテレーション・実行者/採点者各 9 体の 3 役分離）で検出した摩擦に基づき堅牢化。critical 要件は全 pass だったが、実行者の裁量補完に頼って成立していた箇所を指示側で確定させた。

- ワークフロー⇔テンプレートのフィールド整合（Capture の成功基準引き継ぎ、Start の投入上限の既定と記録先、Interview のヘッダ欄復元規則）
- テンプレートに封印セクションの欄定義・着手前（技術未選定）の候補欄規則・状態の選び方を追加
- slug の kebab-title 英訳規約と確信度の判定基準を明文化。安全規約「該当欄を除外して続行」に対応欄が無い場合の意味論を確定（検出をスルーする合理化の逃げ道を封鎖）

## 1.51.0

意思決定の記録・聞き取りスキル `decision-journal` を新規追加。LLM 自動実装時代は cycle 型ワークフローが Why の欠落を加速し、技術選定の来歴（誰が・何を根拠に・どの確信度で裁可したか）が失われる。情報配置 4 象限（How/What/Why/Why not）に収まらない architectural rationale の第 5 のホームを「憲法より判例集」方式で埋める。

- artifact-store 契約に `decisions` kind を追加（canonical namespace / ARTIFACT_KINDS。決定記録は plans/ideas とは検索軸・ライフサイクルが独立するため独立 kind とする）。reviews と異なり `docs/decisions` の旧ストアは存在しないため LEGACY_RELS には加えず、init 対象のみに追加（不要な移行導線を生まない）。migration 分類マニフェスト（`--decisions`）とは層が異なる語であり contract に呼び分けを明記
- 意思決定プロトコル v1 を共有契約 `decision-protocol.md` として正本化（3 通過条件＝生存可能性・検証可能性・退出可能性 / 非対称設計＝選定理由は感覚でよいが棄却条件は反証可能に / 二択にしないクローズ手順 / 個人 Pj・企業 Pj の射程分離）。全条項を規範でなく「プロセス仮説 v1」として明記し、design-principles / testing-anti-patterns / information-placement の上位でなく並置の契約に位置づけ。本文の常駐は他指示を希釈するためルータ 1〜2 行のみ推奨
- `decision-journal` は 3 ワークフロー（start=着手前 1 行プロトコル / capture=LLM 選定会話の固化 / interview=判例の考古学的聞き取り）+ list を $ARGUMENTS 分岐で提供（skills-first、command なし）。5 判例の実測から型化した決定記録テンプレート・聞き取りガイドを references に分離。機密検出時の中断/除外/中止分岐と秘密情報の自動除外を組み込み

## 1.50.0

レビュー出力先を Git 管理外の Agent Artifact Store へ移設。docs/reviews/ 配下への出力はレビュー内容（脆弱性・PoC・再現手順）がコミットに紛れて意図せず公開されるリスクがあった。

- artifact-store 契約に `reviews` kind を追加（canonical namespace / ARTIFACT_KINDS / legacy root `docs/reviews`。既存の docs/reviews/ は artifacts スキルの migrate 導線で回収可能）
- codebase-review / attack-review のレポート出力先を `.agents/artifacts/reviews/` に変更。store 未初期化のプロジェクトでもコピー前に `.gitignore` へ ignore ルールを保証する lazy init をコピー手順に組み込み
- 契約変更に伴い影響 5 スキル（context-audit / github-issue / handoff / issue / plan）の fixture 全 16 シナリオを skill-regression run で実測評価し全合格、ledger を実 run の pass で更新

## 1.49.0

spec-verify に docgen ワークフローを追加し、実地試運転（TypeScript / Vitest プロジェクトでの全ワークフロー完走、mutation score 8/8）のフィードバックを反映。

- docgen: 条項正本 + 証拠マニフェストから読み取り専用 Markdown 仕様ビューを決定論的に生成する spec_docgen スクリプト（stdlib のみ・LLM 不使用・CI 搭載可）。保証レベル・valid ケース数・最終検証日を各条項に併記し、「どの行が実証済みか」が読める台帳にする。自動生成マーカーによる上書きゲートと正本ツリー（specs/clauses/・specs/evidence/）保護、自由文の HTML/リンク注入無効化 + field-aware secret マスキング付き
- trace_matrix: matrix 行に cases_valid_total / last_recorded_at を追加し、行スキーマを evidence-manifest.md「マトリクス行スキーマ」節として正本化（同期テストで行キー集合を突合）
- self-test: 未コミット変更があるときの worktree 手順（生成テスト・依存マニフェストのコピー）を SKILL.md に明文化

## 1.48.0

軽量形式仕様スキル `spec-verify` を新規追加。自然言語仕様に埋もれた検証可能な契約を機械可読な正本（specs/clauses/）へ昇格させ、property-based テストと証拠台帳でドリフトを機械検知する。

- 条項スキーマ v1（invariant / pre_post / transition / authorization の 4 検証意味論、ID/revision ライフサイクル、保証レベルの証拠ベース算出）
- spec_lint / trace_matrix スクリプト（stdlib のみ、fail-closed、report-only/strict の exit code 契約。--baseline diff / --output は trace_matrix のみ、spec_lint は stdout 専用）
- 正本 ⇔ コード定数 ⇔ JSON Schema の三者同期テストと conformance corpus（valid/invalid 26 fixtures）
- formalize / bind / drift-check / self-test の 4 ワークフロー（逆生成レビュー、headless draft 隔離、使い捨て worktree での mutation 自己検証）
- empirical-prompt-tuning による実測チューニング 3 イテレーション（3 役分離 × 3 シナリオ × 9 実行、precision 全 9 run 100%）を反映 — headless draft の検証手順・slug 規則・observation 記録の実務指針（cases_valid 導出・evidence_kind 帰属・ランナー別 test_id の渡し方）等、実行者が詰まった未規定点を確定

## 1.47.2

スキルが参照する設計・テスト原則を、Claude Code 専用の常駐ルールからクロスツール対応の共有契約へ移行。

- `design-principles.md` と `testing-anti-patterns.md` の正本を `skills/shared/references/` へ移動
- plan-implement / plan-reviewer / iterate / test-driven-development / review-testing の参照を可搬な相対 Markdown link に修正
- 対象プロジェクト固有の `AGENTS.md` / `CLAUDE.md` と共有 Design Principles を併用する契約を明確化
- `rules/` への旧参照を検出するリポジトリ検証とユニットテストを追加
- Claude Code の常駐ルールとして共有原則を配置する手順を README に追加

## 1.47.1

attack-review スキルの日英混在を英語に統一。

- `SKILL.md` 本文の日本語を英語化（description のトリガーフレーズは機能的に必要なため維持）
- `references/agent-prompts.md` のプレースホルダ説明・抽出ルール・エージェント紹介文を英語化
- `references/attack-criteria.md` の全チェック項目（WHAT/WHERE/HOW TO EXPLOIT/WHY DANGEROUS/SEVERITY）を英語化（825行の全面書き換え）
- `references/report-template.md` のフィールド説明・表示ルールを英語化
- `references/lang-profiles.md` のヘッダー説明文を英語化

## 1.47.0

cycle / plan-refine / plan-implement のスキル化と、CHANGELOG 起票漏れの機械検証。

- `skills/cycle/` `skills/plan-refine/` `skills/plan-implement/` を新設し、commands に直書きされていたロジックをスキル側へ正本化（AGENTS.md「command は薄い入口」原則への追従。3 つの commands は呼び出しのみに縮小、README のスキル一覧に 2 スキルを追加）
- `validate_repo.py` にチェック12を追加: plugin.json の version に対応する `## <version>` エントリが CHANGELOG.md に存在することを検証（bump だけして起票を忘れるドリフトの再発防止。ユニットテスト付き）
- 欠落していた 1.45.1〜1.46.1 の CHANGELOG エントリを git 履歴から遡って補完
- description 品質検証を関数抽出してテストを追加し、git 依存テストの環境耐性を強化

## 1.46.1

review 系スキルの指示品質改善（empirical-prompt-tuning の適用結果）。

- review-testing の「三層評価」見出しと 4 項目リストの矛盾を解消
- review-deps で見つかった 3 つの指示の穴を修正
- review スキル群の指示契約を強化

## 1.46.0

テスト品質と依存ヘルスの focused レビュースキルを追加。

- `review-testing` を新設（テストスイート自体の欠陥検出力・契約検証・安定性を三層評価）
- `review-deps` を新設（manifest / lockfile / 依存差分の既知脆弱性・サプライチェーン信号を評価）
- coverage ledger 契約（評価範囲台帳）を shared に追加し機械執行
- codebase-review のテスト品質評価を review-testing へ委譲
- README に Composite / Focused レビューの整理を反映

## 1.45.2

- plan スキルの SKILL.md と references の日英混在を英語に統一

## 1.45.1

- plan スキルの File Organization 図の旧パス docs/ を .agents/artifacts/ に修正

## 1.45.0

handoff を Agent Artifact Store に編入（Artifact Store 移行の handoff 漏れを修正）。

- `artifact_store.py` の `LEGACY_RELS` に `docs/handoff` を追加（migrate-check の inventory・legacy 検出・split-brain 判定の対象に）
- `ARTIFACT_KINDS` に `handoff` を追加（init が `.agents/artifacts/handoff/` を作成）
- handoff スキルの生成先パスを `docs/handoff/` から `.agents/artifacts/handoff/` に更新（SKILL.md・fixtures.json・handoff-save コマンド）
- 回帰評価（全 4 シナリオ実 run）合格を確認し ledger を更新

## 1.44.0

Artifact Store v1.1 布石。CI ゲート後退の追認とインデックス導出化・runtime 分離。

- 品質ゲートの所在を明文化（store 内容ゲートは CI では no-op、正のゲートは pre-push/writer 環境。契約に Quality gates 節を追加）
- `artifact_store.py` に `rebuild-index` サブコマンドを追加（idea-status / issue-status をエントリ群から決定論的に再生成。インデックスは「merge しない・再生成する」導出キャッシュに格下げ）
- マシン固有 runtime 状態を `.agents/runtime/{polling,loop}/` へ店内分離（polling 制御ファイル・events.jsonl。契約に Runtime area 節を追加、polling-pattern.md に `runtime_root` を導入）
- migration inventory が runtime 分類ファイルに `suggested_action: skip` を付与
- pre-push 検査ゲートを導入（`githooks/pre-push` + 検証正本 `scripts/run_checks.sh`、CI と同一チェック）

## 1.43.0

Agent Artifact Store を導入し、作業成果物を公開文書の `docs/` から分離。

- LLM 非依存の `.agents/artifacts/` と共有ポリシー `.agents/artifacts.yml` を追加
- `artifacts` スキルに `init / status / migrate` workflow を追加
- fail-closed resolver、Git 追跡検査、legacy/split-brain 検出、2段階 migration を実装
- plan、issue、brainstorm、loop と関連 consumer・fixture を共通 namespace へ移行
- 既定の artifact store を local・Git 非追跡に変更

## 1.42.0

skill-interface-audit 新規追加。各 SKILL.md を API 仕様として静的監査するメタスキル。

- `skill-interface-audit` スキルを追加（SKILL.md + references/ + scripts/）
- SI-S001〜S004 の純関数ルールエンジン（`static_checks.py`、42 テスト）
- SI-C001〜C006 の LLM 意味判断ルール（REPORT\_ONLY 上限）
- skill-authoring.md の執筆原則を正本とし、契約の欠落・構造違反を検出
- empirical-prompt-tuning / trigger-eval / Codex 敵対レビューで品質検証済み

## 1.41.0

統合漏れクリーンアップ。

- `commands/codex-sync.md` を削除（スキル本体は 1.40.0 で削除済み）
- 各 SKILL.md / 共有契約 / issue から「Claude 版のみ」「Codex 移植」等のレガシー前提を除去
- `tool-mapping.md` を「変換リファレンス」から「ランタイム差の参考資料」に改題
- `skill-authoring.md` から Codex 移植セクションを削除
- 関連 issue 2 件をクローズ（統合により superseded）
- `empirical-prompt-tuning`: Codex 自己チューニングにより環境制約の代替案を明確化

## 1.40.0

プラットフォーム非依存化。スキル本文から LLM 固有のツール API 名・モデル名を排除し、
Agent Skills 標準準拠のクロスプラットフォーム互換を実現。superpowers (obra/superpowers)
のアプローチに倣い、自然言語で意図を記述する方式に統一。

- **ツール名変換（111 ファイル）**: `Read` / `Edit` / `Write` / `Bash` / `Agent` /
  `AskUserQuestion` / `SendMessage` / `TeamCreate` / `TeamDelete` / `Grep` / `Glob` /
  `NotebookEdit` / `EnterWorktree` / `ExitWorktree` / `subagent_type` /
  `mode: bypassPermissions` → 全て自然言語に
- **モデル名変換**: `opus` → tier:high / 高性能モデル、`sonnet` → tier:standard / 軽量モデル
- **セクション名統一**: 禁止ツール → 禁止操作、許可ツール → 許可操作
- **codex-skills/ 完全削除**: 62 ファイル・13,902 行削減。デュアル構造を廃止
- **codex-sync スキル削除**: 同期機能が不要に
- **validate_repo.py**: Codex 同期台帳チェック・`--update-manifest` を除去
- **CLAUDE.md / AGENTS.md 統合**: AGENTS.md を正本化、CLAUDE.md は `@AGENTS.md` の薄いラッパーに
- **CLAUDE.md 編集ルール追加**: プラットフォーム非依存の記述を徹底する旨の NG/OK 例付きガイド
- `.codex-plugin/plugin.json`: `skills: "./skills/"` でプラットフォーム共通の skills/ を参照
- `.agents/plugins/marketplace.json`: openai/plugins 標準に準拠した配置に移動

## 1.39.1

empirical-prompt-tuning による 5 スキルの実測チューニング。白紙実行者 計 32 本（rolling-checkpoint 10 +
ループ 4 兄弟 22）で実行し、検出した指示・実装ギャップを解消。全実行 精度 100%・holdout 過適合なし。

- **checkpoint（plan / handoff / checkpoint-pattern.md）**: CLI 呼び出し規約の新設（`--repo` 常時明示・
  プレースホルダ形式のコマンド例）/「checkpoint 生成はセッション最後の書き込み」ルール（handoff save は
  Phase 3 後に実行）/ fallback 提示フォーマット / dirty_overlap 行の不在 = 重なりなし / phase 据え置き遷移
- **goal-loop**: `halt` サブコマンド新設（stall / oscillation 判定を暗算から CLI 化、exit 0/3/4）/
  lock の `__pycache__`・`*.pyc` 自動除外(false-tamper 根治）/ $WORK 絶対パス確定と lock/verify の
  cwd 固定 / implementer への fence 尊重 + no-op 指示と「収束不能 → no-op → stall」正規経路の明文化 /
  oracle 推定の優先順位（README > Makefile > 生ランナー）
- **loop-triage**: SKILL が規定する `sensors.py --context-audit` フラグの実装欠落を解消 /
  `map_context_audit` の `why` 写像欠落を修正（「概要 = what + why」の成立）/ run の引数構文と
  「限定モードなし」/ issue frontmatter の tags 重複キー禁止 / issue-status リンクは `ready/{slug}.md` /
  status ワークフローの定義補強
- **goal-decomposition**: secret パイプラインの実務手順（.claude/tmp で検査 → 合格後配置）/
  proxy の扱い（決定木リーフ不在の明記・headless 採用可）/ oracle_files = verifier ロックの明確化 /
  metrics の `proposed:` プレフィックス / validate はテキスト報告のみ
- **skill-regression**: executor-contract の運用具体化（隔離領域内は編集可 / 非 git フォールバック /
  sha256 ベースライン照合の正式化 / **削除拒否時に別ツールで迂回しない**）/ run vs accept の目安 /
  capture Step 3 = run Step 2〜4 の明記。副次成果: commit スキルの台帳を実 run の pass に格上げ
- 安全性の実測証明: oracle-gaming 誘惑・LLM judge 提案圧力・deny 迂回の 3 種のインシデント経路を
  契約文言で遮断できることを独立実行で確認

## 1.39.0

`rolling-checkpoint` — 長生きセッションの実行状態復元（自動 handoff の再設計）。plan resume /
handoff restore に「dirty のまま終わった実行状態」の復元を追加。**Claude-only**（plan / handoff の
Codex 版追随は v2）。

- **共有契約 `checkpoint-pattern.md`**: checkpoint は worktree バックアップではなく現在の git 状態と
  照合して使う restore ガイド。フォーマット（YAML frontmatter + 固定キー短文）/ 純関数シグネチャ正本 /
  parse ゲート + semantic 5 分類（valid / stale / superseded / degraded / conflict、優先順位
  `superseded > conflict > degraded > stale > valid`）/ 所有境界（4 項目）と禁止事項 / 呼び出し側非対称
  （plan resume は conflict 無視続行・handoff fallback は conflict 停止）/ checkpoint vs handoff 境界 /
  セキュリティ規約 / v1 カバレッジ限界と v2 スコープを定義。
- **`skills/shared/scripts/checkpoint.py`**: 純関数群（`compute_fingerprint` / strict `parse_checkpoint` /
  `classify` / `build_skeleton`）+ skeleton / classify CLI。git 呼び出しは CLI 層のみ（DI）。
  セキュリティは文書でなくコードで強制 — PyYAML 不使用 strict parser（重複キー・未知 owner/mode・
  owner⇔mode 不一致・cycle_id `[0-9]{14}` を拒否）/ realpath containment + symlink 拒否 /
  `secret_detect.mask_secrets` / `verify_on_restore` は `{cmd,args}` 構造のみで**どの verdict でも自動実行しない**
  （headless では確認プロンプトも出さず表示のみ）。fingerprint は `git status --porcelain=v1 -z` +
  `git diff HEAD` 全文 + untracked content sha256 を入力にし `--untracked-files=all` で collapsed dir を展開。
  `test_checkpoint.py` 46 ケース（fingerprint / porcelain -z parse / strict parse / セキュリティ強制 /
  classify マトリクス / skeleton / exit codes）。
- **plan / handoff スキル統合**: plan Resume に checkpoint classify 分岐（orphan / parse conflict 無視続行
  含む）+ Status Update に dirty 出口条件（checkpoint 骨格生成）。handoff save に dirty 時の checkpoint
  書き出し（主トリガー）+ restore に handoff 0 件時の checkpoint fallback（read-only・削除しない）。
  plan / handoff の fixtures に checkpoint 分岐 edge（pl-004 / ho-004）を追加。
- **意図的な非強制**: verdict 語彙（`superseded` 等）は goal-decomposition dossier status との false
  positive を避けるため validate_repo チェック12に登録せず、遵守は skill-regression fixture で守る。
- **v2 送り**: PreCompact / PostToolUse hook（runtime 強制）/ plan 不在の `_workspace` fallback /
  parallel-cycle 多重 writer（契約改訂級）/ measurement `checkpoint_written` イベント（契約改訂級）/
  Codex 版展開。

## 1.38.0

`goal-decomposition` スキル新設 — 大枠ゴールを Loop Readiness Dossier にコンパイルする入口。

- **共有契約 `goal-decomposition-pattern.md`**: 既存 4 契約（loop-engineering / convergence-pattern /
  polling-pattern / measurement-identity）の上流「翻訳層」。Dossier Schema v1（canonical キー階層の単一ソース）/
  第一問決定木（完了条件 / 未達検出器 / 人間判断 → `wire_to` 5 値の導出）/ 5 軸 routing proof /
  status ライフサイクル（draft/approved/superseded/rejected、approved は実行権限を与えない）/
  wire_to×exit_to compatibility matrix / proxy oracle 許容条件（LLM judge 主観評価は禁止）/
  supply gap 3 分類 playbook / 信頼境界 fence 規約 / 既存契約への写像表 / GD001-GD302 rule catalog を定義。
- **`skills/goal-decomposition/`**: 薄い orchestrator（command なし、compile / validate の 2 ワークフロー）。
  compile の出力は常に `status: draft`、承認は人間が JSON を直接編集する。secret redaction は 2 段構え
  （自由文はマスク / 構造フィールドは検出で compile 中止）。
- **`dossier_lint.py`**: 純関数 RULES registry（GD001-GD302、終了コード 0/1/2、object_pairs_hook で
  重複キー検出 / commonpath + symlink 拒否の path containment / secret マスク）。unittest 60 ケース +
  catalog-sync（契約 rule 表 ⇔ RULES の一致保証）。
- **`validate_repo.py` チェック13**: `docs/loop/dossiers/*.json` を dossier_lint で in-process 検査し
  error 級のみ CI fail。壊れた dossier は `[dossier] parse-error` に変換して validate_repo 全体の abort を防ぐ。
  CONTRACT_VOCAB に goal-decomposition-pattern.md（ci_gate / resident_sensor / dissolve）を登録。
- **E2E 具体例**: `docs/loop/dossiers/20260707230000_doc-quality.json`（「ドキュメント品質を上げて維持する」）を
  正式スキーマで作成し lint 合格を確認。md ビューは JSON からの一方向生成 + sha256 marker（tamper-evident）。

## 1.37.2

閉ループの予行演習（③ 残 findings 処理を polling パイプラインで消化）。

- **4 スキルの仕様曖昧点を明文化**（fixture 白紙実行者の報告に基づく。Codex 版 3 スキルへも同期）:
  - github-issue: Common Pre-checks 失敗は fail-closed で polling を起動しない（例外は
    ユーザー明示時のみ）+ nameWithOwner 取得を `fetch_git_remote_url()` と同順に統一
  - handoff: mtime 同秒タイはファイル名タイムスタンプ降順でタイブレーク（restore / list 両方）
  - plan: Completed 日時 = 更新実行時点の現在時刻 / abandoned 行は `YYYY-MM-DD` 粒度
  - commit: 「変更」に untracked を含む（untracked のみでは abort しない、
    非作業成果物は理由付きで除外可）
- **供給→消化の初 E2E 実証**: 4 件を `docs/issues/ready/` に enqueue → 初回強制 dry-run tick
  （claim 4→release 4）→ 本 tick で claim → 並行実装 → 回帰台帳 → mark_done。
  tick イベント 2 件が measurement spine に記録され、`report --skill issue` が
  初の実データ（成功率 100%）を返すようになった

## 1.37.1

fixture カバレッジ拡大（loop-triage 自己修飾ゲートの自動化範囲を広げる）。

- **plan / commit / handoff に回帰 fixture を新規追加**（各 3 シナリオ、白紙実行者で全合格）:
  - plan: headless 作成 / 非 ASCII slug + 未完了セッションの abandoned アーカイブ / Completed 遷移
  - commit: 論理分割（feat/docs 別コミット + 個別 add）/ .env 除外 / 変更なし abort
  - handoff: restore（最新選択・固定サマリ・復元後削除）/ list（原文転記・案内なし）/ not-found
- fixture 保有スキルが 3 → 6 に倍増。これらのスキル（+共有契約経由の挙動面）に触れる
  loop-triage の AUTO_FIX finding が inbox 降格なしで enqueue 可能になった
- iterate は Phase 1 の Agent（Explore）委譲が subagent 実行者では再生不能（入れ子 spawn 禁止）
  なため対象から外し、完全 FS 再生可能な handoff を採用

## 1.37.0

ループエンジニアリング基盤の後半2ピッチ + スコープ明文化。

- **計測 identity 統一（measurement-identity.md）**: 5つの計測系（polling TickResult /
  skill-regression ledger / trigger-eval / skill-improve / cycle 結果）を
  `skill × surface_sha256（挙動面 fingerprint）× run_id` の identity triple で結合する共通契約。
  イベントは `docs/loop/events.jsonl` に append-only で記録し、
  `measurement_identity.py report --skill X` が instruction バージョン別の成功率と
  直近改稿の効果差分を1コマンドで出す。No new silos rule 付き
- **goal-loop スキル新規作成 + convergence-pattern 共有契約**: polling-pattern（キュー消化型）の
  姉妹契約として条件収束型ループを新設。oracle_files のハッシュロック + 毎イテレーション verify で
  「テストを弱めて合格」する oracle-gaming を `oracle_tampered` halt で機械的に遮断
  （ループ内 manifest 更新 API は存在させない）。failure signature による stall / oscillation
  検出、maker/checker 分離（oracle 実行はコントローラのみ）。純関数 40 unittest
- **skill-regression の Codex スコープ明文化**: `codex-skills/` が回帰対象外である理由
  （fixture 再生は Claude Agent ランタイム前提、本文同期は codex-sync が担保）と
  拡張時の順序（実行手段 → 検出範囲）を意図的 non-goal として SKILL.md に明記

## 1.36.0

ループエンジニアリング基盤（出典: Addy Osmani "Loop Engineering"）。polling ループの
「発見 → 供給」上流を新設し、自走ループの安全装置を cron 運用まで拡張した3点。

- **polling 回帰 fixture の資産化**: `issue` / `github-issue` に fixtures.json を新規追加
  （初回 dry-run 強制 / kill file 優先順位 / orphan recovery + fail-safe / state_root 解決 +
  graceful stop / Label Mapping 判定の5シナリオ）。白紙実行者による全シナリオ合格を台帳に記録し、
  ループ本体の挙動面変更が CI で検証を強制されるようになった
- **stateless tick session（polling-pattern §6.5）**: cron / scheduler の 1 invocation = 1 tick
  実行でも 3 重ガード（max_iter / max_wallclock / failed_streak）を `session.json` で維持。
  `--stateless` フラグを両 adapter に追加。`failed_streak` halt は sticky（session.json を
  人間が削除するまで自動再開しない）。fixture 実行者が発見した契約ドリフト6件
  （kill_file_path 戻り順の契約⇔adapter 不一致、state_of_failure 擬似コードの fail-closed 矛盾、
  archive 初回の空文字パス穴、.claim 形式未規定、.polling-initialized 作成責務未規定、
  早期 halt 時の run_id 未定義）も同時修正
- **loop-triage スキル新規作成 + loop-engineering 共有契約**: センサー（validate_repo 違反 /
  ledger --check の stale / context-audit findings）を Finding Schema に正規化し、
  stable finding_id で冪等化（baseline suppression + queue dedup）→ fix_action × severity の
  純関数 admission → AUTO_FIX 級のみ `docs/issues/ready/` に enqueue して polling に供給する
  ループ中枢。loop-defining ファイルに触れる finding は fixture 非保有スキルが1つでもあれば
  inbox 降格する自己修飾ゲート付き（回帰網がある範囲でだけ自動化）。純関数4本 + 111 unittest

## 1.35.0

ベースライン整備。検証インフラの再実装重複と検査の死角を4点まとめて解消。

- **frontmatter パーサの共有化**: validate_repo.py / context-audit / trigger-eval が
  各自再実装していた YAML frontmatter パーサを `skills/shared/scripts/frontmatter.py`
  に統合（TDD、28 テスト）。キー正規表現は最も正確な `[A-Za-z_][A-Za-z0-9_-]*` に統一。
  乖離すると description トリガー語チェックの正しさに直結する箇所
- **チェック5の対象拡大**: references/**/*.md（共有契約含む）の相対リンクも検査対象に。
  検出した実リンク切れ（codex 側 severity-and-verdicts → fix-action-taxonomy）は
  symlink 追加で修正。plan のテンプレ内例示リンクは理由付き `LINK_CHECK_EXEMPT` で免除
- **チェック7/8の word-boundary 化**: bare substring 一致では issue ⊂ github-issue、
  plan ⊂ team-plan が誤合格していたのを `mentions_name` で修正
- **design-lint の機械化**: description の「機械的に検出」「CI 組み込み可能」の実体が
  エージェント prose だったのを、lint-contract 準拠の実行スクリプト
  `skills/design-lint/scripts/design_lint.py`（DL001-006 / DL101-103 / DL201-204、
  標準ライブラリのみ、63 unittest、終了コード 0/1/2）として実装。SKILL.md は
  スクリプト実行 + 結果解釈に書き換え、ルール適用の暗算再現を禁止

## 1.34.0

Codex パリティを「信頼ベース」から「検証ベース」へ。14 ペア全部の Claude 版⇔Codex 版を
意味レベルで敵対的に突き合わせ、9 ペア計 15 件のドリフトを修正。sha 一致 =「見た」の記録
しか守れなかった台帳の死角を、構造ごと塞いだ。

- **構造的根本原因の特定と修正**: ツール名（SendMessage / ExitWorktree / AskUserQuestion）や
  Codex 第二意見節を含む references 10 本が「tool-independent」と誤判定されて symlink 共有
  されており、Codex 実行者に Claude 方言と削除済みの第二意見指示が見え続けていた
  （本文は正しく変換済み = 本文と参照が直接矛盾）。10 本すべてを変換済み実体コピーに置換し、
  `EXTRA_SYNC_PAIRS` で台帳追跡に載せた（15 → 25 ペア）
- **実質的な意味喪失の復元**: codex cycle の実装プロンプトに TDD（tdd-contract）+
  verification-gate 注入を復元 / codex iterate の TDD 義務を「when feasible」から契約準拠に
  復元 + テストアンチパターン禁止を復元 / codex plan-reviewer に最新ドキュメント確認ヒント復元
- **点在ミスの修正**: codex commit の verification-gate 参照を cross-tree パスから codex ローカル
  リンクへ / codex issue の Next Steps を issue スコープ（`$issue cycle --team`）に修正
- **codex shared 契約の拡充**: verification-gate.md / tdd-contract.md を symlink 追加。
  codex-integration（Codex 内では無意味）/ skill-authoring（リポジトリ開発メタ）/
  orchestration-patterns（model 階層が Claude 固有）は不移植と tool-mapping.md に明文化
  （「共有契約の可搬性ポリシー」新設: symlink / 変換コピー / 不移植の3分類）
- **規約統一**: codebase-review / plan-reviewer / commit に `(Codex Edition)` H1 +
  「Codex CLI ツールの使い分け」節を補完、attack-review に同節を補完
- **監査で IN_SYNC を確認**: handoff / investigate / plan / brainstorm / problem-solving の
  5 ペアは移植品質良好（brainstorm の第二意見除去とステップ再番号の整合まで検証済み）
- skill-authoring.md に references 共有の内容基準判定を明文化（「テンプレだから中立」推定の禁止）

## 1.33.0

共有契約システムの意味的再統一。11 本の契約と全スキルを突き合わせ、「宣言だけ共有・実体は
インライン再発明」のドリフトを解消し、以後の再発を CI で機械的に止める。

- **文脈検証3値判定（CONFIRMED/FALSE_POSITIVE/UNCERTAIN）の定義元を新設**:
  CLAUDE.md や refactor が「severity-and-verdicts 準拠」と宣言していたのに、当の契約に
  定義が存在しなかった（事実上の定義は sweep-fix の references に散在）。severity-and-verdicts.md
  に汎用フレーム（3値・Iron Law・fail-safe）を新設し、CONFIRMED の検証述語は各スキルの
  意図的特殊化として維持（sweep-fix = バグ成立 / refactor = 動作保持）・相互リンクで接続
- **team-config の自己矛盾を解消**: 冒頭注記（メンバー = opus、9343065 のモデル階層コミット由来）と
  §モデル指定表（sonnet、階層導入前の残骸）が矛盾していた。opus に統一（Codex 版は model
  パラメータ自体が Claude 固有のため反映不要と判断、台帳更新済み）
- **plan-reviewer のスコアバンド用法を承認済み方言として明文化**: BLOCK/WARN/PASS を
  リスクスコア帯にマップする用法を severity-and-verdicts に記載し、Claude / Codex 両版の
  SKILL.md から契約へリンク（トークン変更なし = 挙動不変）
- **doc-check の軸混同を修正**: fix action（AUTO_FIX/NEEDS_JUDGMENT/OK）を `severity:` と
  ラベルしていた箇所を `action:` に修正し、fix-action-taxonomy の差異節へリンク
- **インライン複製を参照に接続**: doc-audit / context-audit(memory-audit) / iterate(light-review) /
  skill-regression(fixture-schema) / commands/plan-implement / commands/issue-polling に契約リンクを追加。
  severity-and-verdicts ⇔ fix-action-taxonomy を相互リンク化
- **チェック12（共有契約語彙の適合）を validate_repo.py に新設**: 契約を一意に識別する語彙
  （AUTO_FIX 系 / CONFIRMED 系 / PASS WITH NOTES 系 / polling ガード / codex:codex-rescue）を
  使う skill / command が契約への md リンクを持たないと CI fail。免除は理由必須の
  `CONTRACT_VOCAB_EXEMPT`。TDD で追加（6 テスト）、既存リポジトリで偽陽性ゼロを確認
- **regression harness が初稼働**: 契約編集で context-audit が stale 判定され、変更が追記のみで
  挙動無影響と裁定して `--update --accept` を記録（黙殺不可能の設計が機能）
- 不介入と判断した重複（意図的再利用）: Gate Function / Iron Law 見出しの別ドメイン再利用、
  tdd-contract と lang-detect のマーカーファイル表（目的が異なる）、design-system-contract の
  独自検証階層。codex-skills 側の契約未移植（fix-action / verification-gate / codex-integration /
  polling / orchestration が codex shared に不在）は Codex パリティ作業（ピッチ3）の scope として残す

## 1.32.0

`skill-regression` スキルを新規追加。スキルの「調律済みの挙動」を fixture として資産化し、
SKILL.md や共有契約の変更時に影響スキルだけへ回帰評価を回すハーネス。

- **課題**: empirical tuning で確立した合格基準はセッションと共に消え、共有契約 1 ファイルの
  編集が参照スキル十数個の挙動を無検証で変える（実測: `verification-gate.md` の変更は
  推移参照込みで 14 スキルに波及）。trigger-eval が「発火」を守る一方、「実行の質」の回帰は
  誰も見ていなかった
- **挙動面 (behavior surface)**: `skills/<name>/` 配下 + SKILL.md からの md リンク推移閉包
  （共有契約含む）を `dep_graph.py` で算出し、変更ファイル → 影響スキルを逆引き
- **検証台帳 `ledger.json`**: sync-manifest と同思想。挙動面が前回検証時から変わったのに
  台帳が古いままなら CI fail。`--update --accept` で「実行せず不要判断」を明示記録
  （黙殺だけを不可能にする）。fixture を持つスキルのみ追跡（opt-in）
- **fixture 契約**: `skills/<name>/fixtures.json`。シナリオ 2〜3 本 + [critical] 付き要件
  3〜7 項目。白紙実行者 subagent（model 明示・毎回新規 dispatch・worktree 隔離）で再生し、
  critical 全 ○ で合格。生産手段（empirical tuning / plan 受け入れ条件 / 手動設計）に非依存
- **共有純関数 `skills/shared/scripts/md_links.py`** を新設（リンク抽出 + 推移閉包）。
  `dep_graph.py` / `ledger.py` とあわせて全て TDD（RED→GREEN）で unittest 検証
- **初の fixture 資産化: context-audit**: 1.31.1 EPT が検証した挙動（CA-S001 backtick 参照 /
  CA-C001 矛盾 / CA-D001 日本語ツール語彙 / 非対話フォールバックでの AUTO_FIX 不適用・baseline
  非書き込み / 誤検出ゼロの precision）を 3 シナリオ・14 要件に固定。白紙実行者 3 体で全シナリオ
  合格（critical 全 ○ + ファイル無改変をハッシュで機械検証）を確認し台帳に記録
- **CI のテスト発見を自動化**: `.github/workflows/validate.yml` のハードコード 3 ステップを
  `skills/*/scripts` の自動発見ループに置換。従来 CI から漏れていた context-audit の
  96 テストが回るようになった（新スキルのテストが黙って漏れる構造を根絶）。
  あわせて `ledger.py --check` を CI ゲートに追加

## 1.31.1

`context-audit` を empirical-prompt-tuning（白紙実行者 × 3〜4 シナリオ × 5 イテレーション）で改善。

- **検出エンジンの recall 改善**（fixture 実測で炙り出したギャップ 3 件）:
  - CA-S001: リポジトリ全体の basename 索引を導入。親ディレクトリ不在の backtick 参照でも、
    その basename が木のどこにも無ければ「削除済みディレクトリの stale」として検出
    （basename が他所に実在する shorthand 表記は従来どおり skip、precision 維持）
  - CA-D001: 日本語ツール語彙（「Edit ツール」等）を検出対象に追加
  - CA-C001: Jaccard 足切りを 0.5 → 0.2 に緩和（SKILL の「recall 優先の over-generation」契約に整合）
- **SKILL.md に「実行契約」を新設**: スクリプトのパス解決（`{skill_dir}` 絶対パス + root=cwd）/
  非対話フォールバック（明示指示が最優先 → なければ安全側で first-run=(c)・適用なし）/ `{ts}` 採番規約
- **仕様の明文化**: Phase 2 の candidate 0 件スキップ / 非 git での baseline 運用 + `--update-baseline`
  の idempotent 性 / CA-S001 の抽出対象（`/` 含むパス表記のみ）/ CA-D001 の行単位・代表 1 語報告 /
  memory_dir 開示と where マスクの関係
- 評価結果: 3 シナリオ + hold-out で精度 100%・再試行 0・steps 単調減（A: 17→9）。hold-out で過適合なし

## 1.31.0

`context-audit` スキルを新規追加。LLM 向け指示ファイル（root の CLAUDE.md / AGENTS.md、
`.claude/rules` / `rules`、`.claude/review-rules.md`）+ cwd 対応プロジェクトメモリの
老朽化・矛盾・有害指示・クロスツール乖離を監査する棚卸しスキル。

- **純関数ルールエンジン（CA-* ルール体系）**: trigger-eval 踏襲の「純関数は unittest で検証、
  エージェントは JSON 生成・受け渡しのみ」構成。`collect_targets.py`（path allowlist 収集 +
  cwd→memory slug 解決/reverse-verify）/ `static_checks.py`（CA-* rule registry ディスパッチャ）/
  `apply_fixes.py`（AUTO_FIX 適用純関数・body byte 不変・idempotent）/ `aggregate_report.py`
  （baseline suppression + summary-first レポート）の 4 スクリプト。
- **v1 ルール**: CA-S001/S002（参照実在）/ CA-U001（unsafe 語彙）/ CA-D001（ツール語彙混入）/
  CA-D002（カバレッジ差分・validate_repo 検出時は機械的自動スキップ）/ CA-C001（矛盾候補・
  candidate 抽出は純関数、判定は LLM の REPORT_ONLY）/ CA-M001/M101/M301（メモリ系）。
- **fix-action 3値判定（severity と直交）**: AUTO_FIX / NEEDS_JUDGMENT / REPORT_ONLY。
  taxonomy を `skills/shared/references/fix-action-taxonomy.md` に抽出し doc-audit と共有。
  **削除・本文書き換えは絶対に自動化しない**（迷ったら安全側に倒す）。
- **プライバシー制約**: メモリ監査はデフォルト cwd 対応プロジェクトのみ、グローバルは
  `--include-global` opt-in。slug 解決は実 Claude Code 実装に一致 + reverse-verify + fail-safe skip。
  secret は値を転記せずパターン名 + file:line のみ（redaction を全 finding の line-context に適用）。
  secret 検出は `skills/shared/scripts/secret_detect.py`（skill-improve と共有化）を再利用。
- **baseline suppression**: `.claude/context-audit-baseline.json` は commit するが opaque finding ID のみ格納。
- 純関数を unittest で検証（`test_*.py` 6 種、93 テスト）。skills-first のため command なし、初版は Claude 版のみ。

## 1.30.0

`trigger-eval` スキルの v2 改善（発火計測の妥当性強化 + トークン化・fail-closed の堅牢化）。

- **Tier 1 に autonomous モードを追加**。従来の selection モード（「一覧から最適スキルを選べ」＝ description 弁別性の上界）に加え、
  「普通に応答するかスキルを起動するか自分で決めよ。起動する場合のみスキル名を返せ」＝スキル起動を強制しない
  autonomous モード（salience/想起の近似）を新設。デフォルトで両モードを併走計測し、`--selection-only` で従来動作。
  モードごとに `judged-{mode}-iterN.json` / `metrics-{mode}-iterN.json` を別々に生成し**混合禁止**。収束・悪化ガードは
  selection を正、autonomous は参考系列 + Tier1↔Tier2 乖離のキャリブレーション信号（`aggregate_metrics.py` は無改修）
- **判定エージェントへの入力配布方法を正式契約化**: インライン渡し、または `skills.json` + バッチファイルの 2 ファイルのみ
  Read 許可のファイル渡しのいずれか。それ以外のツール・ファイル読取は禁止（soft guarantee）
- **`static_collisions.py` の日本語トークン化を bigram 化**（TDD）。CJK 単字ユニグラムを廃止し、連続 CJK run の
  sliding bigram に変更（単字 run は除外、`計画` のような 2 字語は 1 bigram として保持）。共通助詞・かなでの誤衝突を低減
- **`skill-improve/collect.py` の `output_is_git_ignored` を fail-closed 改善**（TDD）。`git check-ignore` の exit 0/1/その他を
  区別し、undecidable（git 自体が実行不能）のとき stderr に `GIT_CONFIG_GLOBAL=/dev/null` 再実行を促すヒントを出す
  （fail-closed は維持）
- **testcase-design.md の高エントロピー screen を機械判定化**: `[A-Za-z0-9+/=_-]{20,}` かつ数字・英大文字・英小文字の
  3 種混在のトークンのみを高エントロピーとみなす（`migrate-cycles-to-plans` 等の小文字ハイフン長スキル名を誤検出しない）

## 1.29.0

`trigger-eval` スキルを新規追加。スキルセットの description 発火精度（recall / precision /
stability / 80-way confusion matrix）を description-only の判定 subagent で機械的に実測し、
衝突ペアを特定して description 改稿→再評価ループを収束まで回すメタスキル。`empirical-prompt-tuning`
（本文実行の質）に対し選択層（description→発火）を測る姉妹スキル。

- 静的衝突プレパス（`static_collisions.py` の語彙 Jaccard、LLM 不使用）+ Tier 1 選択シミュレーション
  （sonnet 判定 subagent、バッチ ≤20・並行 dispatch）+ Tier 2 E2E 実発火検証（使い捨て git worktree・
  6 セッション上限）の静的プレパス + 2 層評価
- 純関数 `collect_descriptions.py` / `static_collisions.py` / `aggregate_metrics.py` を unittest で検証
  （エージェントは JSON 生成・受け渡しのみ）。references に judge-protocol / testcase-design / metrics-spec
- 事前固定原則 + holdout 採用ゲート + 悪化ガード（max_iterations=5）で過適合と description 盛りを機械的に防ぐ
- `skill-improve/collect.py` に opt-in `--capture-prompts` を追加（マスク済みプロンプト本文を JSONL 出力。
  出力は git-ignored な `cwd/.claude/tmp` 配下に機械制限＝fail-closed）。秘匿マスクを `[REDACTED:kind]` の
  完全マスクに変更し、email / ホームパス / ghp_・github_pat_・xoxb-・sk-・sk-ant-・AIza 等の既知プレフィックス
  トークン（引用符の有無・sk-proj- 等のダッシュ入り・3-part JWT 署名も含む）を検出するよう強化
- CI（`validate.yml`）に trigger-eval / skill-improve scripts の unittest discover ステップを 2 つ追加
- skills-first 方針により command なし。初版は Claude 版のみ

## 1.28.1

`refactor` スキルの empirical prompt tuning（白紙実行者による4イテレーション評価、
3シナリオ + hold-out 1、全12+4ラン成功・精度100%維持）で検出した曖昧箇所を明文化。
挙動の変更なし、判定文言の精度向上のみ。

- `no_verification_means` を除外理由の語彙に追加（検証手段そのものが不在のケース）
- Phase 6 冒頭にレポート形式選択規則を明文化（簡略版は「変更ゼロ かつ 提示項目ゼロ」のときのみ）
- セクション帰属規則を追加（§5 は CONFIRMED + opt-in 待ち専用、複数理由該当は UNCERTAIN を §4 優先、
  重複掲載禁止）
- headless の定義を明文化（ユーザへの確認・質問に応答が得られない文脈全般）
- characterization test / probe は headless Gate で常に同じ扱いであることを明記
- no-op 時のテスト実行は必須ではない（読み取り目的の1回実行は妨げない）ことを明記
- Phase 0 にテストファイルの扱いを追加（スコープ展開に含まれても改善対象ではなく検証手段）
- refactoring-catalog: 兆候列の数値は目安であり足切り条件ではないことを明記

## 1.28.0

新スキル `refactor` を追加。実装完了後のコードを**動作を完全に維持したまま**リファクタリングし、
コードベース全体の類似コードへ文脈検証つきで横展開する。sweep-fix が「問題（バグ）起点の
find-one-fix-all」なのに対し、refactor は「動作保持の表現改善」起点。

- **7フェーズ構成**: SCOPE（スコープ解釈・安全上限 50 ファイル・一時コード除外）→
  UNDERSTAND（Chesterton's Fence + 検証手段の確保。テスト/型検査/probe のない箇所は APPLY しない）→
  IDENTIFY（4値分類 REFACTOR_CANDIDATE / BUG_FOUND / OUT_OF_SCOPE / ALREADY_CLEAN、no-op Gate、
  performance Gate）→ SWEEP（similarity-ts/rs / ast-grep / Grep を役割別に使い分け、存在確認 +
  フォールバック、範囲限定）→ VERIFY（3値判定 ★品質の要）→ APPLY（origin は APPLY、
  スコープ外 sweep_candidates は opt-in、1改善ずつ最大10件、Rule of 500）→ REPORT
- **Iron Laws**: 動作完全維持 / Chesterton's Fence / バグは直さず issue 化案を提示 /
  既にきれいなら no-op / 迷ったら直さない（証明手段なしは APPLY 不可）
- **検証観点は自前で持つ**: sweep-fix の context-verification.md は「同じ**バグ**が成立するか」を
  問う設計で、動作保持検証（「同じ**変換**を動作保持で適用できるか」）とは問いが逆向きのため流用せず、
  refactor 固有の `references/behavior-preservation-checks.md` を新設。3値判定の**定義**は
  共有契約 severity-and-verdicts.md に準拠
- **references**: `refactoring-catalog.md`（改善パターン C1-C12 + 過度な単純化の罠 +
  「新しいチームメンバー」テスト）、`similarity-detection.md`（ツール役割別使い分け +
  存在確認・言語カバレッジ非対称性・フォールバック）、`behavior-preservation-checks.md`
  （動作保持の6観点チェックリスト + 判定例）
- **バグ修正はしない**: 発見した `BUG_FOUND` は修正せず REPORT で `issue` スキルの起動コマンド案
  （タイトル・本文の下書き付き）として提示。refactor 実行中は docs/issues を書き換えない
- **skills-first 方針**: command なし（`/claude-skills:refactor` で直接起動）
- **初版は Claude 版のみ**: sweep-fix と同じ戦略で、Codex 版は需要を見てから codex-sync で移植予定
  （`codex-skills/` / `AGENTS.md` / `sync-manifest.json` は変更なし）

## 1.27.1

sweep-fix を empirical prompt tuning（白紙エージェント10実行 + hold-out 過適合チェック、
全実行で要件精度 100%）で検証し、実行者の申告に基づく曖昧箇所を明文化。

- **早期終了パスの仕様明文化**: 中間ディレクトリ `.claude/tmp/sweep-fix/` の作成を
  Phase 0 から「最初にファイルを保存する時点（Phase 1 の問題リスト保存）」に遅延。
  問題ゼロ終了時は中間ファイル未作成（作成済みなら削除）+ 簡略版レポート +
  「変更なしのため検証対象なし」（テスト実行不要）を明記
- **severity 境界の倒し方**: BLOCK/WARN の境界事例は高い方に倒して根拠を1行記録。
  重大度は修正フローを変えない（Phase 4 続行確認の発火条件のみ）ため境界判定に
  時間をかけない旨を Phase 1 に追記
- **判定例の注記**: context-verification.md の判定例の重大度ラベルが例示である旨を
  明記（境界の倒し方は SKILL.md Phase 1 の規定に従う）

## 1.27.0

新スキル `sweep-fix` を追加。指定範囲で見つけた問題をコードベース全体へ横展開して
一括修正する find-one-fix-all 型ワークフロー。

- **6フェーズ構成**: SCOPE（範囲確定）→ ANALYZE（問題検出、severity-and-verdicts 準拠）→
  SWEEP（パターン化 + 横展開検索。Grep / ast-grep / LSP を使い分け、存在確認 +
  Grep フォールバック付き。問題複数時は並行ファンアウト + `.claude/tmp/sweep-fix/` マージ、
  `model: opus` 明示）→ VERIFY（文脈検証）→ FIX（verification-gate 準拠）→ REPORT
- **偽陽性対策を独立フェーズとして強制**: 候補を CONFIRMED / FALSE_POSITIVE / UNCERTAIN の
  3値判定にし、判定根拠の記録を必須化。UNCERTAIN → CONFIRMED への昇格を禁止する
  fail-safe（迷ったら直さない）。「検索は広く、修正は狭く」で偽陰性対策（検索段階）と
  偽陽性対策（検証段階）の責務を分離
- **references**: `context-verification.md`（判定チェックリスト5項目 + 判定例）、
  `pattern-extraction.md`（問題→検索シグネチャ変換ガイド + アンチパターン）
- **skills-first 方針の初適用**: 新規スキルとして初めて command なしで追加
  （`/claude-skills:sweep-fix` で直接起動）。Codex 版は需要を見てから codex-sync で移植予定

## 1.26.0

サブエージェントのモデル階層（Model Tiering）を導入。高額モデル（Fable 等）の
セッションからスキルを起動しても、配下のエージェントが高額モデルを継承して
コストが暴発する事故を構造的に防止する。

- **共通契約**: `orchestration-patterns.md` に「モデル階層」セクションを新設。
  原則4つ（レバレッジ / 検証ゲートで守られたフェーズは安くできる / ゲートのない
  レビュー・発見系は安くしない / model 明示の第一目的は高額モデルの継承防止）と
  標準マッピング表を定義。fork は model 指定を無視する点、Codex エージェントは
  対象外である点も明記
- **model 指定の追加**: cycle（refine/修正/実装 = opus）、plan-reviewer（7観点 = opus）、
  codebase-review（4体+統合 = opus）、attack-review（6体+統合 = opus）、
  iterate（実装は Small=sonnet / Large=opus のサイズ連動、レビュー = opus）、
  parallel-cycle（分解 = セッションモデル、plan 生成 = sonnet、cycle 実行 = opus）、
  team-config（メンバー spawn = opus、Lead = セッションモデル）
- **attack-review の fable 禁止**: Fable のサイバーセキュリティ分類器は正当な防御
  目的のレビューでも refusal を返しうるため、コスト以前に成果物が壊れる旨を明記
- **Codex 版6ペア**: model パラメータは Claude の Agent tool 固有のため反映不要と
  判断し、同期台帳のみ更新

## 1.25.0

addyosmani/agent-skills の分析結果から良質なプラクティスを移植。

- **Codex バイアス制御**: `codex-integration.md` に「バイアス制御」セクションを新設。
  自分の結論・レビュー結果を Codex に渡さない（アンカリング防止）/ 敵対的フレーミング必須 /
  doubt theater 検出（2回連続全棄却・検証なし全採用の両方を Red Flag 化）。
  セキュリティ節の許可コンテキストから「レビュー結果」を外し、修正ループの再レビューのみ例外化
- **バリデータ強化（チェック11）**: SKILL.md description のトリガー語
  （「〜で起動」/ "Use when" 等）と 1024 字上限を CI で機械検証。複数行
  `description: >` 対応の `extract_description()` を追加。免除リストはバリデータ側に配置
  （スキルファイル編集による検証迂回を防止）
- **description 修正**: トリガー語がなかった commit（Claude/Codex）・parallel-cycle
  （Claude/Codex）・cycle（Codex）の5スキルにトリガー語を追加
- **共有契約 orchestration-patterns.md 新設**: endorsed パターン7種（Agent 委譲 /
  並行ファンアウト+ファイルマージ / worktree 分離 / チーム議論 / セカンドオピニオン /
  polling ループ / リサーチ隔離）+ アンチパターン5種 + 判断フロー + カタログ追加ゲート
- **共有契約 skill-authoring.md 新設**: frontmatter 契約 / 執筆原則 / 合理化防止テーブルの
  書き方 / Codex 移植の注意 / 新規スキル追加チェックリストを集約したスキル執筆仕様

## 1.24.0

codex-sync による brainstorm / problem-solving の Codex 版移植。

- **Codex 版 brainstorm 追加**: `codex-skills/brainstorm/`（codex-sync port）。Codex セカンドオピニオン
  機構は自己レビューで冗長なため丸ごと削除しステップ番号を再整合。`request_user_input` ベースの
  対話ループは維持（壁打ちが本質のため headless 化しない）。wrap / plan のファイル生成は
  `apply_patch`、idea-template.md は symlink で共有
- **Codex 版 problem-solving 追加**: `codex-skills/problem-solving/`（codex-sync port）。
  5つの思考手法（simplify/collide/invert/scale/pattern）の内容は Claude 版と一字一句同一、
  ツール参照のみ変換（`request_user_input` / `shell` 読み取り専用 / `apply_patch` 禁止）
- **brainstorm Codex 版の誘導先を解消**: 行き詰まり検出の誘導ブロックが未移植の problem-solving を
  指していた REVIEW を、problem-solving 移植完了に伴い `$problem-solving` へ置換
- **ソース修正**: `skills/problem-solving/SKILL.md` の Dispatch 選択肢に残っていた UTF-8 破損
  （U+FFFD ×2）を「新しいアイデアが出ない」に修正
- **同期台帳**: 15 ペアに更新。AGENTS.md / README / CLAUDE.md に両スキルの Codex 版を追記

## 1.23.0

リポジトリ自己検証基盤と Claude⇔Codex 一元管理の導入。

- **CI バリデータ新設**: `scripts/validate_repo.py` + GitHub Actions で symlink 切れ /
  相対リンク切れ / frontmatter 欠落 / CLAUDE.md 対応表⇔commands/ の双方向一致 /
  README・AGENTS.md のスキル名カバレッジ / plugin.json⇔marketplace.json のバージョン同期を
  push / PR ごとに機械検証（純関数はユニットテストでカバー、TDD で作成）
- **Claude⇔Codex 同期台帳**: `codex-skills/sync-manifest.json` に sync 時点のソース sha256 を
  記録し、ソースだけ更新して Codex 版を忘れるサイレントドリフトを CI で検出（13ペア）
- **新スキル codex-sync**: Claude 版スキルを Codex 版へ自動移植（port）・差分同期（sync）・
  未同期一括処理（scan）するメタスキル。3層変換ルール（機械的置換 / 構造的変換 / 要判断）を
  適用し、第3層は人間にエスカレーション。validate → 台帳更新まで一気通貫
- **ドリフト修正**: commit Codex 版に v1.17.0 の Phase 1.5 (Best-Effort Test Verification) を
  移植（反映漏れ）。tool-mapping.md を AGENTS.md が示す codex-skills/shared/references/ へ移動
- **ドキュメント追従**: README / AGENTS.md に未記載だった attack-review・design 系・
  mockup-diff・tdd・debug・problem-solving 等を追記。リリースノートを plugin.json から
  本ファイルに分離。marketplace.json のバージョン同期

## 1.22.0

brainstorm skill empirically tuned (4 iterations, dispatch-based evaluation). Session Workflow: step numbering fixed (a2 → b with cascaded rename of sub-steps b→c→d→e→f→g, loop-exit step 4→5), stuck-hint placement locked to response body head (hint → normal answer → Codex section order), Codex prompt `{summary}` first-turn handling specified (`（最初のターン、履歴なし）`), Codex failure conditions expanded (Agent tool unavailable / timeout / empty response all explicit). Plan Workflow: Title/Summary provenance declared (kebab-title from idea-status link text, Summary from `## Summary` section), plan-create output path documented (`docs/plans/{new_timestamp}_{kebab-title}.md`), Step 5/6 reordered to move-first then status-update in archives/, Step 4.5 Skip Step 7 made explicit (cycle produces own completion log). Resume Workflow cross-reference corrected (steps 2-3f → 4a-4g). Mojibake (U+FFFD replacement chars in simplify-invert bullet) removed.

## 1.21.0

Codex CLI edition of handoff skill added under codex-skills/handoff/. Same save/restore/list workflows as the Claude Code version, rewritten for Codex native tools (apply_patch for file creation, shell for cat/rm/date/git, send_message for user output). Headless end-to-end: no request_user_input, no shell redirects for file writes. Handoff skill itself was empirically tuned (3 iterations, dispatch-based evaluation) before porting: status vocabulary locked to 3 values, absolute-path example fixed, restore summary templated, list extraction rules specified, git-less fallback (branch: (none)) added. Both editions share identical frontmatter structure so handoff files are cross-compatible.

## 1.20.0

New mockup-diff skill: visual diff detection between approved mockup HTML and running app. Phase 0 SETUP auto-generates a tailored Playwright comparison script per project (Tauri, Next.js, Vite, etc.) instead of hardcoded framework-specific logic. Captures screenshots of both mockup and app, enables LLM-driven visual comparison, diff analysis, code fix, and verification loop. Complements design-validate (token compliance) as the last-mile implementation quality gate.

## 1.19.0

Mockup Workflow v2: schema-based mockup generation with auto-lint (DL001-204) and Base Design approval gate. Feedback loop for iterating tokens/catalog/page-schema until human approval, then all subsequent validation is mechanical. Baseline confirmed via approval.json + screenshots.

## 1.18.0

Design-guide v2: mechanical verification for design systems. 5 new skills: design-scaffold (DESIGN.md → tokens.json + tokens.css + catalog + pages + layout-rules + rubric), design-generate (constrained page generation from page-defs + catalog), design-validate (multi-stage gate: lint → visual regression → rubric judge with weighted scoring), design-lint (14 rules: DL001-006 tokens, DL101-103 components, DL201-204 pages). Human-in-the-Loop Once: single base design approval → all subsequent validation is mechanical. Shared design-system-contract.md.

## 1.17.0

New TDD, systematic-debugging, and problem-solving skills. TDD contract and verification gate shared references injected into cycle/iterate/commit. Testing anti-patterns rule for project-wide enforcement. Brainstorm now detects stuck keywords and suggests problem-solving tools. Skill-improve gains pressure-test analysis and guardrail-strengthening category.

## 1.16.0

New design-guide skill: interactive discovery-driven DESIGN.md generator. Binary-choice questions to structure vague design vision into concrete design tokens (Google Stitch format). Anti-pattern guardrails to avoid generic AI aesthetics. Session (create), Update (modify), and Mockup (token-strict HTML/React mockup generation) workflows.

## 1.15.0

New attack-review skill: attacker-perspective security review with 6 specialist agents + Codex. Risk-matrix-based threat classification (not scores). Server/client/full mode with auto-detection. Language-adaptive attack profiles (TS/JS, Python, Go, Rust, Dart, PHP, HTML/CSS). Shared language detection contract (lang-detect.md) for cross-skill reuse.

## 1.14.1

Phase 2.5 code review follow-ups for github-issue Polling Phase B: SKILL.md Polling Step 11 now explicitly references increment_retry + should_promote_to_permanent; TickResult schema lists all 7 fields per shared contract §7; list_ready early-termination guarantee documented; retry_count / last_failed_at / run_id validation spec tightened; polling_interval vs tick_interval_loop_mode clarified. README refreshed to cover github-issue / handoff / polling commands and workflow quirks.

## 1.14.0

github-issue Polling Contract Unification (Phase B): Label adapter refactor to conform with shared polling-pattern.md contract. Split `claude-failed` into `claude-failed-transient` / `claude-failed-permanent` with backward-compatible dual-write alias. Atomic dual-write + verification + recovery marker. FS retry state replaces GitHub comment state. WARNING: Downgrade to 1.13.x is NOT supported — issues tagged with the new labels become invisible to older readers, causing silent data loss. Alias `claude-failed` will be removed in 1.16.0 (advance notice in 1.15.0).

## 1.13.x 以前

記録なし（releaseNotes の運用開始は 1.14.0 から）。
