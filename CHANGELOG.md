# Changelog

claude-skills プラグインのバージョン履歴。
`.claude-plugin/plugin.json` の `version` を bump したら、このファイルにエントリを追加すること
（マーケットプレイスがスキル変更を認識するのは version bump 時のみ）。

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
