#!/usr/bin/env python3
"""fixtures.json の検証と、隔離領域への決定的な実体化（純関数 + 薄い CLI）。

fixture の `setup` は長らく `files`（パス → 内容）だけを持ち、実体化は run のたびに
呼び出し側の手作業だった。その結果 mtime 順・ファイル件数・git の状態といった
「内容以外の前提」が実行者の裁量で埋まり、シナリオが意図した分岐を踏まないまま
合格する事故が起きた（2026-07-25 のバッチ実行で 21 シナリオ中 5 件）。

このモジュールは前提を fixture 側の宣言として受け取り、決定的に再現する。

CLI:
  python3 fixture_setup.py --validate PATH...        # fixtures.json を検証（違反があれば exit 1）
  python3 fixture_setup.py --materialize FIXTURE SCENARIO_ID DEST
      シナリオの setup を DEST に実体化し、baseline ハッシュと env を JSON で出力
"""
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import time

TIERS = ("standard", "high")
ISOLATIONS = ("worktree", "none")
TOP_KEYS = ("skill", "scenarios")
SCENARIO_KEYS = (
    "id", "title", "source", "executor_tier", "isolation", "setup",
    "prompt", "requirements", "notes",
)
REQUIREMENT_KEYS = ("text", "critical")
SETUP_KEYS = ("files", "mtimes", "git", "env")
GIT_KEYS = ("init", "commit", "remote", "branch", "message")

# 実体化した git リポジトリの既定値。git 本体の既定（init.defaultBranch 未設定時の
# 分岐や実装バージョン）に委ねると実体化が環境依存になるため、ここで固定する。
DEFAULT_BRANCH = "master"
DEFAULT_MESSAGE = "fixture baseline"

# baseline の番兵。宣言したパスが通常ファイルとして存在しない（実行基盤が
# デバイスファイルを被せた等）ことを、ハッシュ欄で区別できる形にする
NOT_A_REGULAR_FILE = "NOT-A-REGULAR-FILE"

# 実体化した git リポジトリの著者情報。実行環境の gitconfig に依存すると
# サンドボックスで読み取りを拒否されて実体化ごと失敗するため固定する。
_GIT_ENV = {
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_AUTHOR_NAME": "fixture",
    "GIT_AUTHOR_EMAIL": "fixture@local",
    "GIT_COMMITTER_NAME": "fixture",
    "GIT_COMMITTER_EMAIL": "fixture@local",
}

# git hook の中では GIT_DIR などが環境に置かれており、それを引き継ぐと隔離領域の
# `git init` が呼び出し元のリポジトリを指してしまう。fixture の実体化は宣言だけから
# 決まらなければならないので、継承した状態は落とす。
_GIT_INHERITED = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_PREFIX",
)


# Agent Artifact Store 契約（skills/shared/references/artifact-store.md）の写し。
# ここで扱うのは「fixture の宣言が契約を満たすか」だけで、実体の検査は
# skills/shared/scripts/artifact_store.py が行う。二重定義に見えるが、--validate は
# 実体化せず宣言だけを読む静的検査なので、実体側のモジュールには寄せられない。
STORE_CONFIG_REL = ".agents/artifacts.yml"
DEFAULT_STORE_ROOT = ".agents/artifacts"
RUNTIME_ROOT = ".agents/runtime"
# local / shared-private は「Git 無視かつ追跡ファイルなし」が不変条件。
# public だけが追跡され、逆に無視されていてはならない
IGNORED_VISIBILITIES = ("local", "shared-private")
_YAML_SCALAR_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*?)\s*$")


def _err(where, message):
    return f"[fixture] {where}: {message}"


def _declared_policy(files):
    """setup.files の `.agents/artifacts.yml` から (root, visibility, explicit) を読む。

    宣言が無ければ契約の既定（local / .agents/artifacts）に解決する。外部 YAML
    エンジンは使わない（契約が禁じているのと、fixture の policy は平坦スカラだけ）。
    """
    raw = files.get(STORE_CONFIG_REL)
    if raw is None:
        return DEFAULT_STORE_ROOT, "local", False
    root, visibility = DEFAULT_STORE_ROOT, "local"
    for line in raw.splitlines():
        match = _YAML_SCALAR_RE.match(line)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip("'\"")
        if key == "root" and value:
            root = value.strip("/")
        elif key == "visibility" and value:
            visibility = value
    return root, visibility, True


def _gitignore_covers(text, path):
    """`.gitignore` の宣言が path（またはその祖先ディレクトリ）を無視するか。

    git の完全な実装ではない。fixture の `.gitignore` は宣言なので、
    「ディレクトリを丸ごと無視する」形だけを解釈すれば足りる。
    スラッシュを含まないパターンは任意の階層のベース名に、含むパターンは
    リポジトリ相対パスに当てる（git の規則と同じ切り分け）。
    """
    if not text:
        return False
    segments = [s for s in path.strip("/").split("/") if s]
    ancestors = ["/".join(segments[:i + 1]) for i in range(len(segments))]
    covered = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        if negated:
            line = line[1:]
        pattern = line.strip("/")
        if not pattern:
            continue
        for ancestor in ancestors:
            target = ancestor if "/" in pattern else ancestor.rsplit("/", 1)[-1]
            if fnmatch.fnmatchcase(target, pattern):
                covered = not negated
                break
    return covered


def _validate_artifact_store(where, files, git):
    """`.agents/` 配下を宣言する fixture が Artifact Store 契約を満たすか検査する。

    `setup.git.init` を宣言したシナリオは実体化先が自前の git リポジトリになるため、
    Git 無視の前提は fixture の `.gitignore` 宣言が全てになる。宣言が欠けると
    store が `writable: false` に落ち、Phase 0 で store を検証するスキル
    （cycle 等）は宣言したシナリオへ一度も到達しないまま abort する。
    赤くならず素通りするぶん、落ちる fixture より質が悪い。
    """
    if not git.get("init"):
        # 自前の git を持たないシナリオは、実体化先を用意する側（周囲のリポジトリ）
        # が無視設定を持つ。fixture の宣言だけでは判定できないので検査しない
        return []
    root, visibility, explicit = _declared_policy(files)
    gitignore = files.get(".gitignore", "")
    errors = []

    store_files = [p for p in files if p == root or p.startswith(root + "/")]
    if store_files and visibility in IGNORED_VISIBILITIES:
        if not _gitignore_covers(gitignore, root):
            errors.append(_err(
                where,
                f"visibility {visibility!r} の artifact store {root!r} を setup.files で"
                f"宣言しているが、setup.files['.gitignore'] が無視していない"
                f"（store が writable: false になり、宣言したシナリオに到達できない）。"
                f"`/{root}/` を .gitignore に足すか、`{STORE_CONFIG_REL}` で"
                f" visibility: public を明示する"))
    if store_files and visibility == "public":
        if not explicit:
            errors.append(_err(
                where, f"visibility: public は {STORE_CONFIG_REL} の明示宣言を必要とする"))
        if _gitignore_covers(gitignore, root):
            errors.append(_err(
                where,
                f"visibility: public の artifact store {root!r} を"
                f" setup.files['.gitignore'] が無視している（追跡されず存在しない扱いになる）"))

    # runtime 領域は visibility に関わらず常にマシンローカル（契約 Runtime area）
    runtime_files = [
        p for p in files if p == RUNTIME_ROOT or p.startswith(RUNTIME_ROOT + "/")]
    if runtime_files and not _gitignore_covers(gitignore, RUNTIME_ROOT):
        errors.append(_err(
            where,
            f"runtime 領域 {RUNTIME_ROOT!r} を setup.files で宣言しているが、"
            f"setup.files['.gitignore'] が無視していない"
            f"（runtime は visibility に関わらず常に Git 無視）"))

    if explicit and _gitignore_covers(gitignore, STORE_CONFIG_REL):
        errors.append(_err(
            where,
            f"{STORE_CONFIG_REL} は追跡される policy なので"
            f" setup.files['.gitignore'] で無視してはならない"))
    return errors


def _validate_git(where, git, files):
    errors = []
    for key in git:
        if key not in GIT_KEYS:
            errors.append(
                _err(where, f"未知の setup.git キー {key!r}（有効: {', '.join(GIT_KEYS)}）"))
    if not git.get("init"):
        for dependent in ("commit", "remote", "branch", "message"):
            if git.get(dependent):
                errors.append(
                    _err(where, f"setup.git.{dependent} は init: true を必要とする"))
    remote = git.get("remote")
    if remote is not None and not isinstance(remote, str):
        errors.append(_err(where, "setup.git.remote は文字列である必要がある"))

    branch = git.get("branch")
    if branch is not None and (not isinstance(branch, str) or not branch.strip()):
        errors.append(_err(where, "setup.git.branch は空でない文字列である必要がある"))

    commit = git.get("commit")
    if isinstance(commit, list):
        if not commit:
            errors.append(_err(
                where,
                "setup.git.commit の空配列は意図が曖昧（全件は true、"
                "ベースラインコミットを作らないならキー自体を省く）"))
        for path in commit:
            if not isinstance(path, str):
                errors.append(_err(where, "setup.git.commit の各要素は文字列である必要がある"))
            elif path not in files:
                errors.append(_err(
                    where, f"setup.git.commit[{path!r}] に対応する setup.files がない"))
    elif commit is not None and not isinstance(commit, bool):
        errors.append(_err(
            where, "setup.git.commit は true / パス配列である必要がある"))

    message = git.get("message")
    if message is not None:
        if not isinstance(message, str) or not message.strip():
            errors.append(_err(where, "setup.git.message は空でない文字列である必要がある"))
        if not commit:
            errors.append(_err(
                where, "setup.git.message は commit を必要とする（コミットしないなら message は無意味）"))
    return errors


def _validate_setup(where, setup):
    errors = []
    if not isinstance(setup, dict):
        return [_err(where, "setup はオブジェクトである必要がある")]
    for key in setup:
        if key not in SETUP_KEYS:
            errors.append(
                _err(where, f"未知の setup キー {key!r}（有効: {', '.join(SETUP_KEYS)}）"))

    files = setup.get("files") or {}
    if not isinstance(files, dict):
        errors.append(_err(where, "setup.files はオブジェクトである必要がある"))
        files = {}
    for path, content in files.items():
        if not isinstance(content, str):
            errors.append(_err(where, f"setup.files[{path!r}] の内容が文字列でない"))
        if os.path.isabs(path) or ".." in path.split("/"):
            errors.append(_err(where, f"setup.files[{path!r}] が隔離領域の外を指している"))

    mtimes = setup.get("mtimes") or {}
    if not isinstance(mtimes, dict):
        errors.append(_err(where, "setup.mtimes はオブジェクトである必要がある"))
    else:
        for path, offset in mtimes.items():
            if path not in files:
                errors.append(
                    _err(where, f"setup.mtimes[{path!r}] に対応する setup.files がない"))
            if not isinstance(offset, int) or isinstance(offset, bool):
                errors.append(
                    _err(where, f"setup.mtimes[{path!r}] は整数秒（基準時刻からの相対）である必要がある"))

    git = setup.get("git")
    if git is not None:
        if not isinstance(git, dict):
            errors.append(_err(where, "setup.git はオブジェクトである必要がある"))
        else:
            errors += _validate_git(where, git, files)
            errors += _validate_artifact_store(where, files, git)

    env = setup.get("env") or {}
    if not isinstance(env, dict):
        errors.append(_err(where, "setup.env はオブジェクトである必要がある"))
    else:
        for name, value in env.items():
            if not isinstance(value, str):
                errors.append(_err(where, f"setup.env[{name!r}] は文字列である必要がある"))
    return errors


def validate(fixture, source="fixtures.json"):
    """fixtures.json の内容を検証し、違反メッセージ一覧を返す（空なら合格）。"""
    errors = []
    if not isinstance(fixture, dict):
        return [_err(source, "トップレベルはオブジェクトである必要がある")]
    # 未知キーは黙って無視されるのが最も危険な失敗の形（宣言したつもりの前提が
    # 実体化されず、run のたびに実行者の裁量で埋まる）。タイポも含めて拒否する
    for key in fixture:
        if key not in TOP_KEYS:
            errors.append(
                _err(source, f"未知のトップレベルキー {key!r}（有効: {', '.join(TOP_KEYS)}）"))
    if not fixture.get("skill"):
        errors.append(_err(source, "skill がない"))
    scenarios = fixture.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        return errors + [_err(source, "scenarios が空、または配列でない")]

    seen = set()
    for index, scenario in enumerate(scenarios):
        where = f"{source}#{scenario.get('id') or index}"
        if not isinstance(scenario, dict):
            errors.append(_err(where, "シナリオはオブジェクトである必要がある"))
            continue
        for key in scenario:
            if key not in SCENARIO_KEYS:
                errors.append(_err(
                    where, f"未知のシナリオキー {key!r}（有効: {', '.join(SCENARIO_KEYS)}）"))
        for key in ("id", "title", "source", "prompt"):
            if not scenario.get(key):
                errors.append(_err(where, f"{key} がない"))
        sid = scenario.get("id")
        if sid in seen:
            errors.append(_err(where, f"id {sid!r} が重複している（報告の追跡キーが壊れる）"))
        seen.add(sid)

        tier = scenario.get("executor_tier", "standard")
        if tier not in TIERS:
            errors.append(_err(where, f"executor_tier {tier!r} が不正（有効: {', '.join(TIERS)}）"))
        isolation = scenario.get("isolation", "worktree")
        if isolation not in ISOLATIONS:
            errors.append(_err(where, f"isolation {isolation!r} が不正（有効: {', '.join(ISOLATIONS)}）"))

        setup = scenario.get("setup")
        if setup is not None:
            errors += _validate_setup(where, setup)
            if isolation == "none" and (setup.get("files") or setup.get("git")):
                errors.append(
                    _err(where, "isolation: none のシナリオは setup.files / setup.git を持てない"))

        requirements = scenario.get("requirements")
        if not isinstance(requirements, list) or not requirements:
            errors.append(_err(where, "requirements が空、または配列でない"))
            continue
        for req in requirements:
            if not isinstance(req, dict) or not req.get("text"):
                errors.append(_err(where, "requirements の各項目は text を持つ必要がある"))
                continue
            for key in req:
                if key not in REQUIREMENT_KEYS:
                    errors.append(_err(
                        where,
                        f"未知の requirements キー {key!r}（有効: {', '.join(REQUIREMENT_KEYS)}）"))
        # critical が 1 つも無い fixture は「落ちても合格」になり回帰を検出しない
        if not any(isinstance(r, dict) and r.get("critical") for r in requirements):
            errors.append(_err(where, "critical: true の要件が 1 つもない（回帰を検出できない）"))
    return errors


def _run_git(args, cwd):
    env = dict(os.environ, **_GIT_ENV)
    for name in _GIT_INHERITED:
        env.pop(name, None)
    return subprocess.run(
        ["git"] + args, cwd=cwd, env=env, capture_output=True, text=True)


def materialize(scenario, dest, base_time=None):
    """シナリオの setup を dest に実体化し、{dir, baseline, env, git} を返す。

    baseline は「編集ゼロの裏取り」用の {相対パス: sha256}。
    mtime は base_time からの相対秒で刻む（既定は実行時刻）。相対にするのは、
    絶対時刻を fixture に書くと時間経過で陳腐化するため。
    """
    if base_time is None:
        base_time = time.time()
    setup = scenario.get("setup") or {}
    files = setup.get("files") or {}
    mtimes = setup.get("mtimes") or {}
    git = setup.get("git") or {}

    os.makedirs(dest, exist_ok=True)
    baseline = {}
    unmaterialized = []
    for path, content in files.items():
        full = os.path.join(dest, path)
        os.makedirs(os.path.dirname(full) or dest, exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(content)
        # 書けたことを実体側で確認する。実行基盤が機微な名前のファイル（.env 等）に
        # /dev/null を被せることがあり、書き込みが黙って捨てられる。宣言のハッシュを
        # そのまま baseline にすると、実体と食い違ったまま「編集ゼロ」を判定してしまう
        expected = content.encode("utf-8")
        actual = None
        if os.path.isfile(full):
            with open(full, "rb") as handle:
                actual = handle.read()
        if actual == expected:
            baseline[path] = hashlib.sha256(expected).hexdigest()
        else:
            unmaterialized.append(path)
            baseline[path] = (
                hashlib.sha256(actual).hexdigest() if actual is not None
                else NOT_A_REGULAR_FILE)

    # mtime は全ファイル書き込み後にまとめて適用する。書き込みの合間に適用すると
    # 後続の書き込みが同一ディレクトリの mtime を巻き戻して順序が崩れる
    for path, offset in mtimes.items():
        full = os.path.join(dest, path)
        if os.path.isfile(full):
            stamp = base_time + offset
            os.utime(full, (stamp, stamp))

    git_state = {}
    if git.get("init"):
        branch = git.get("branch") or DEFAULT_BRANCH
        _run_git(["init", "-q", "-b", branch], dest)
        git_state["init"] = True
        git_state["branch"] = branch
        if git.get("remote"):
            _run_git(["remote", "add", "origin", git["remote"]], dest)
            git_state["remote"] = git["remote"]
        commit = git.get("commit")
        if commit:
            # パス配列は「ベースラインに含めるファイル」の宣言。残りは未追跡のまま
            # 残り、「未コミットの作業がある」状態そのものが前提になるシナリオ
            # （commit スキル等）を宣言で作れる
            paths = ["-A"] if commit is True else list(commit)
            _run_git(["add"] + paths, dest)
            # --allow-empty: setup.files が空でも基準コミットを作る
            # （「作業ツリーが clean」を要件にするシナリオの前提）
            result = _run_git(
                ["commit", "-q", "-m", git.get("message") or DEFAULT_MESSAGE,
                 "--allow-empty"], dest)
            git_state["commit"] = result.returncode == 0
            # commit 後に mtime が変わることはないが、checkout 系を足す場合は再適用が要る

    return {
        "dir": os.path.abspath(dest),
        "baseline": baseline,
        "env": dict(setup.get("env") or {}),
        "git": git_state,
        "unmaterialized": unmaterialized,
    }


def main(argv):
    args = list(argv)
    if "--validate" in args:
        args.remove("--validate")
        errors = []
        for path in args:
            try:
                with open(path, encoding="utf-8") as handle:
                    fixture = json.load(handle)
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(_err(path, f"読み込めない: {exc}"))
                continue
            errors += validate(fixture, source=path)
        for message in errors:
            print(message)
        if errors:
            print(f"✗ {len(errors)} 件の違反")
            return 1
        print(f"✓ fixtures {len(args)} 件: 違反なし")
        return 0

    if "--materialize" in args:
        idx = args.index("--materialize")
        fixture_path, scenario_id, dest = args[idx + 1:idx + 4]
        with open(fixture_path, encoding="utf-8") as handle:
            fixture = json.load(handle)
        for scenario in fixture.get("scenarios", []):
            if scenario.get("id") == scenario_id:
                print(json.dumps(
                    materialize(scenario, dest), ensure_ascii=False, indent=2))
                return 0
        print(_err(fixture_path, f"シナリオ {scenario_id!r} がない"))
        return 1

    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
