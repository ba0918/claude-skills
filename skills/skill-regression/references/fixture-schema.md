# fixtures.json スキーマと設計指針

`skills/<skill>/fixtures.json` の契約。fixture は「このスキルが守るべき挙動」を
再実行可能な形で固定した回帰資産であり、スキル本体と同じリポジトリで commit する。

## スキーマ

```json
{
  "skill": "sweep-fix",
  "scenarios": [
    {
      "id": "sf-001",
      "title": "単一ファイル指摘からの横展開",
      "source": ".agents/artifacts/plans/20260702143000_sweep-fix.md",
      "executor_tier": "standard",
      "isolation": "worktree",
      "setup": {
        "files": {
          "src/example.py": "def f(x):\n    return eval(x)\n"
        },
        "mtimes": { "src/example.py": -3600 },
        "git": { "init": true, "commit": true },
        "env": { "XDG_STATE_HOME": "./xdg-state" }
      },
      "prompt": "src/example.py の eval 使用が危険だと指摘された。同種の問題をコードベース全体から探して直したい。",
      "requirements": [
        { "text": "指摘箇所をパターン化してから横展開検索している", "critical": true },
        { "text": "検出箇所を CONFIRMED/FALSE_POSITIVE/UNCERTAIN の3値で判定している", "critical": true },
        { "text": "UNCERTAIN を修正対象に含めていない", "critical": true },
        { "text": "修正後に検証コマンドの実行結果を提示している", "critical": false }
      ]
    }
  ]
}
```

例中の CONFIRMED / FALSE_POSITIVE / UNCERTAIN は
[severity-and-verdicts.md](../../shared/references/severity-and-verdicts.md) の
「文脈検証の3値判定」の語彙（要件文で共有語彙を使うときは定義元の意味で書く）。

| フィールド | 必須 | 意味 |
|-----------|------|------|
| `skill` | ✓ | 対象スキル名（ディレクトリ名と一致） |
| `scenarios[].id` | ✓ | スキル内で一意な短い ID。安定させる（報告・履歴の追跡キー） |
| `scenarios[].title` | ✓ | 1 行のシナリオ名 |
| `scenarios[].source` | ✓ | この合格基準の出どころ（tuning セッションの plan doc / 手動設計なら `manual`）。来歴が追えない fixture は陳腐化判断ができない |
| `scenarios[].executor_tier` | - | 省略時 `standard`。`high` に上げた場合は理由を `notes` に書く |
| `scenarios[].isolation` | - | `worktree`（ファイル生成・編集を伴う）/ `none`（読み取り・対話のみ）。省略時 `worktree`（安全側） |
| `scenarios[].setup.files` | - | シナリオ実行前に worktree 内へ配置するファイル（相対パス → 内容）。isolation が `worktree` の場合のみ有効 |
| `scenarios[].setup.mtimes` | - | ファイルの mtime（`files` のパス → 基準時刻からの相対秒。負値が過去）。順序を判定材料にするスキルで必要。相対にするのは絶対時刻が時間経過で陳腐化するため |
| `scenarios[].setup.git` | - | 隔離領域の git 状態。キーは下表 |
| `scenarios[].setup.env` | - | 実行者に前提として与える環境変数（名前 → 値）。実体化では設定されず、呼び出し側がプロンプトへ注入する |
| `scenarios[].prompt` | ✓ | 実行者に渡す状況設定。ユーザー発話として自然な文にする（スキル名を直接指定しない — 発火判定は trigger-eval の領分、ここでは本文実行の質だけを測る） |
| `scenarios[].requirements[]` | ✓ | 成果物が満たすべき要件。3〜7 項目、`critical: true` を最低 1 つ。キーは `text` / `critical` のみ |
| `scenarios[].notes` | - | 設計判断のメモ（edge の意図・tier 変更理由など） |

未知のキーは検証で拒否される（トップレベル / シナリオ / `requirements` / `setup` / `setup.git` の全階層）。
黙って無視されると「宣言したつもりの前提が実体化されない」という最も気づきにくい形で
測定対象がぶれるため、タイポも含めて違反として落とす。

### `setup.git` のキー

| キー | 意味 |
|------|------|
| `init` | 隔離領域を git リポジトリにする。他の git キーはすべてこれを必要とする |
| `branch` | 初期ブランチ名。省略時 `master`（git 本体の既定に委ねると実体化が環境依存になるため固定値）。ブランチ名で分岐するスキル（例: commit の main/master 直コミット禁止）では必ず宣言する |
| `commit` | `true` = 全ファイルを含む基準コミットを作り作業ツリーを clean にする / パス配列 = そのファイルだけをコミットし、残りは未追跡のまま置く（「ベースラインはあるが作業分は未コミット」の宣言） |
| `message` | 基準コミットのメッセージ。省略時 `fixture baseline`。「既存履歴のスタイルに合わせる」を測るシナリオでは履歴の言語・形式そのものが前提なので宣言する |
| `remote` | origin の URL |

`setup` は [scripts/fixture_setup.py](../scripts/fixture_setup.py) が実体化する。
run / capture で隔離領域を手作業で組み立てない — 手作業は前提が宣言の外に漏れる経路そのもので、
同じ fixture が実行のたびに違う前提で動く。

```bash
python3 {skill_dir}/scripts/fixture_setup.py --materialize \
  skills/<skill>/fixtures.json <scenario_id> <dest>
```

出力の `baseline`（相対パス → sha256）は「編集ゼロの裏取り」にそのまま使う。
ハッシュは宣言ではなく**書き込み後の実体**から取る。`env` は実行者プロンプトの
環境セットアップ節へ転記する。

出力の `unmaterialized` が非空なら、そのパスは宣言と実体が食い違っている
（実行基盤が `.env` 等にデバイスファイルを被せると書き込みが黙って捨てられる）。
内容に依存する要件はそのシナリオに書けない — run の報告に記録し、要件が内容前提なら
fixture 側を直す。

スキーマ適合は `--validate` で検査でき、`scripts/validate_repo.py` のチェック17が
CI で全 `skills/*/fixtures.json` に対して同じ検証を強制する。

## 設計指針

1. **シナリオ数は 2〜3 本**: 現実の使用場面の中央値 1 本 + edge 1〜2 本。
   1 本では過適合し、4 本以上は run のコストが釣り合わない
2. **要件は観測可能な形で書く**: 「正しく動く」ではなく「3値判定の verdict が出力に含まれる」。
   実行者の成果物・報告から ○/× を機械的に判定できる粒度まで落とす
3. **critical の基準**: それが × ならスキルの存在意義が崩れる項目だけに付ける。
   全項目 critical は「全部大事 = 何も大事じゃない」で回帰の解像度を失う
4. **事前固定**: capture で確定した requirements は run の結果を見て動かさない。
   動かすのは「スキル仕様そのものが意図的に変わった」ときだけで、その場合は
   fixture を修正して capture からやり直す（`source` も更新する）
5. **シナリオを楽にする方向の修正は禁止**: 落ちたから prompt を簡単にする・critical を外す、は
   回帰の隠蔽。落ちた原因の切り分け（スキル回帰 or 仕様変更）が先
6. **秘密情報を入れない**: fixture は commit される。実在の認証情報・内部 URL・個人情報を
   setup / prompt に含めない
7. **`setup.files` で表現できない前提に依存させない**: `setup.files` は「パス → 内容」しか
   持たない。mtime・git の状態・ファイル**件数**・環境変数といった前提はスキーマの外にあり、
   run のたびに実行者の裁量で埋められる。埋め方が変われば測っている経路も変わる

### `setup.files` の外にある前提（実測で観測した落とし穴）

2026-07-25 のバッチ実行（10 スキル / 21 シナリオ）で、意図した分岐を踏めていない
シナリオが 5 件出た。いずれも原因は同じで、**内容以外の前提が宣言できないこと**にある。

| 依存する前提 | 起きること | 宣言する場所 |
|---|---|---|
| ファイルの mtime 順 | setup を一括生成すると mtime が同値になり、「mtime 降順」が主規則のスキルでも稀なタイブレーク分岐しか踏まない | `setup.mtimes` |
| mtime の表示値 | 一覧表示の日時欄がファイル名の日付と食い違い、要件が曖昧になる | 表示値は要件に入れない。順序だけを assert する |
| 対象ファイルの件数 | 上限（例: `max_parallel=4`）による早期打ち切りが、件数不足で発火せず未検証のまま ○ になる | `setup.files`（上限を踏む件数を置く） |
| git の状態（初期コミット / remote） | 「作業ツリーが clean」を要件にしても未追跡ファイルで最初から dirty になる。remote 前提のスキルでは実行者が架空 remote を自作する | `setup.git` |
| ブランチ名 | `git init` の既定ブランチが main/master になり、ブランチ名で中断するスキル（commit）が本題に入る前に abort する | `setup.git.branch` |
| 既存履歴の内容 | 「既存履歴のスタイルに合わせる」が測れない（履歴が空 or harness 既定の英語メッセージ 1 件） | `setup.git.message` |
| 未コミットの作業がどれか | `commit: true` は全ファイルをコミットしてしまい「未コミットの変更が N 件ある」前提が作れない | `setup.git.commit` にパス配列 |
| 機微な名前のファイルの内容 | 実行基盤が `.env` 等に `/dev/null` を被せ、宣言した内容が実体化されない（宣言のハッシュを baseline にすると実体と食い違ったまま「編集ゼロ」を判定する） | 宣言できない。`materialize` の `unmaterialized` で検出し、要件を名前・種別ベースにする |
| 実行基盤が作るセッション残骸 | `.claude/` や `__pycache__` が作業ツリーを汚し、「clean」要件の成否が実行者の裁量（ignore を自作するか / スコープ外と判断するか）で決まる | `setup.files` に `.gitignore` |
| 環境変数 | 実行者が値を推測して埋め、run ごとに違う前提で動く | `setup.env` |
| 入れ子委譲が成立する実行環境 | 多段委譲スキルは委譲先の完了通知が親に届かず停止する | 宣言できない。[executor-contract.md](executor-contract.md) の環境制約に従い上位 watchdog を前提に組む |

**要件を書くときの指針**: その要件が `setup` の宣言だけで決まるか確認する。決まらないなら、
前提を宣言できる形に直すか、要件をその前提に依存しない形へ書き直す。
「実行者が気を利かせて埋めてくれた」は、測定対象がぶれたということでもある。

## 素材別の変換ガイド

- **[empirical tuning](../../empirical-prompt-tuning/SKILL.md) の実測から**: 収束時に出力される
  `fixture.json`（`.claude/tmp/empirical/{ts}/fixture.json`）の `scenarios` / `requirements` を
  そのまま本スキーマの scenarios / requirements に写す。`source` は `"empirical-tuning:{ts}"` とする。
  収束時点のチェックリストが最良の回帰資産（tuning 中に動かした項目は最終版だけを採る）
- **plan の受け入れ条件から**: plan 文書の「完了条件」「検証」節を requirements に変換する。
  実装手順ではなく成果物の性質を書いている項目だけを採る
- **手動設計**: スキルの description が約束していることを requirements に落とす。
  description と body の乖離がある場合は fixture 化の前に本体を直す
