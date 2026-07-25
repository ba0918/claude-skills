"""fixture_setup.py の unittest。

検証（純関数）と、隔離領域への実体化（mtime 順・git 状態・env）を検証する。
実体化のテストは「fixture の宣言だけで前提が決まる」ことを守るためのもので、
呼び出し側の手作業に前提が漏れると測定対象がぶれる。
"""
import hashlib
import json
import os
import subprocess
import tempfile
import unittest

import fixture_setup


def _fixture(**overrides):
    scenario = {
        "id": "sf-001",
        "title": "シナリオ",
        "source": "manual",
        "prompt": "やって",
        "requirements": [{"text": "満たす", "critical": True}],
    }
    scenario.update(overrides)
    return {"skill": "sweep-fix", "scenarios": [scenario]}


class TestValidate(unittest.TestCase):
    def test_minimal_valid_fixture_passes(self):
        self.assertEqual(fixture_setup.validate(_fixture()), [])

    def test_missing_skill_is_reported(self):
        f = _fixture()
        del f["skill"]
        self.assertTrue(any("skill がない" in e for e in fixture_setup.validate(f)))

    def test_empty_scenarios_is_reported(self):
        self.assertTrue(any("scenarios" in e
                            for e in fixture_setup.validate({"skill": "x", "scenarios": []})))

    def test_missing_required_scenario_field_is_reported(self):
        f = _fixture()
        del f["scenarios"][0]["prompt"]
        self.assertTrue(any("prompt がない" in e for e in fixture_setup.validate(f)))

    def test_duplicate_scenario_id_is_reported(self):
        f = _fixture()
        f["scenarios"].append(dict(f["scenarios"][0]))
        self.assertTrue(any("重複" in e for e in fixture_setup.validate(f)))

    def test_no_critical_requirement_is_reported(self):
        # critical ゼロの fixture は落ちても合格になり回帰を検出しない
        f = _fixture(requirements=[{"text": "満たす", "critical": False}])
        self.assertTrue(any("critical" in e for e in fixture_setup.validate(f)))

    def test_invalid_tier_is_reported(self):
        self.assertTrue(any("executor_tier" in e
                            for e in fixture_setup.validate(_fixture(executor_tier="turbo"))))

    def test_invalid_isolation_is_reported(self):
        self.assertTrue(any("isolation" in e
                            for e in fixture_setup.validate(_fixture(isolation="sandbox"))))

    def test_unknown_top_level_key_is_reported(self):
        f = _fixture()
        f["skil"] = "typo"
        self.assertTrue(any("未知のトップレベルキー" in e for e in fixture_setup.validate(f)))

    def test_unknown_scenario_key_is_reported(self):
        # 宣言したつもりのキーが黙って無視されると、前提が実行者の裁量で埋まる
        self.assertTrue(any("未知のシナリオキー" in e
                            for e in fixture_setup.validate(_fixture(executor_model="sonnet"))))

    def test_unknown_requirement_key_is_reported(self):
        f = _fixture(requirements=[{"text": "満たす", "criticial": True}])
        self.assertTrue(any("未知の requirements キー" in e
                            for e in fixture_setup.validate(f)))


class TestValidateSetup(unittest.TestCase):
    def test_known_setup_keys_pass(self):
        f = _fixture(setup={
            "files": {"a.md": "x"},
            "mtimes": {"a.md": -3600},
            "git": {"init": True, "commit": True, "remote": "https://example.invalid/r.git"},
            "env": {"XDG_STATE_HOME": "./s"},
        })
        self.assertEqual(fixture_setup.validate(f), [])

    def test_unknown_setup_key_is_reported(self):
        f = _fixture(setup={"symlinks": {"a": "b"}})
        self.assertTrue(any("未知の setup キー" in e for e in fixture_setup.validate(f)))

    def test_mtime_without_matching_file_is_reported(self):
        f = _fixture(setup={"files": {"a.md": "x"}, "mtimes": {"b.md": 1}})
        self.assertTrue(any("対応する setup.files がない" in e
                            for e in fixture_setup.validate(f)))

    def test_non_integer_mtime_is_reported(self):
        f = _fixture(setup={"files": {"a.md": "x"}, "mtimes": {"a.md": "1h"}})
        self.assertTrue(any("整数秒" in e for e in fixture_setup.validate(f)))

    def test_boolean_mtime_is_rejected(self):
        # bool は int のサブクラスなので明示的に弾かないとすり抜ける
        f = _fixture(setup={"files": {"a.md": "x"}, "mtimes": {"a.md": True}})
        self.assertTrue(any("整数秒" in e for e in fixture_setup.validate(f)))

    def test_git_commit_without_init_is_reported(self):
        f = _fixture(setup={"git": {"commit": True}})
        self.assertTrue(any("init: true を必要とする" in e
                            for e in fixture_setup.validate(f)))

    def test_git_branch_and_baseline_message_pass(self):
        f = _fixture(setup={
            "files": {"a.md": "x", "b.md": "y"},
            "git": {"init": True, "branch": "work", "commit": ["a.md"],
                    "message": "chore: 基準コミット"},
        })
        self.assertEqual(fixture_setup.validate(f), [])

    def test_git_branch_without_init_is_reported(self):
        f = _fixture(setup={"git": {"branch": "work"}})
        self.assertTrue(any("setup.git.branch は init: true を必要とする" in e
                            for e in fixture_setup.validate(f)))

    def test_empty_git_branch_is_reported(self):
        f = _fixture(setup={"git": {"init": True, "branch": "  "}})
        self.assertTrue(any("setup.git.branch" in e for e in fixture_setup.validate(f)))

    def test_git_commit_path_outside_files_is_reported(self):
        f = _fixture(setup={"files": {"a.md": "x"}, "git": {"init": True, "commit": ["b.md"]}})
        self.assertTrue(any("対応する setup.files がない" in e
                            for e in fixture_setup.validate(f)))

    def test_empty_git_commit_list_is_reported(self):
        f = _fixture(setup={"files": {"a.md": "x"}, "git": {"init": True, "commit": []}})
        self.assertTrue(any("意図が曖昧" in e for e in fixture_setup.validate(f)))

    def test_non_list_non_bool_git_commit_is_reported(self):
        f = _fixture(setup={"files": {"a.md": "x"}, "git": {"init": True, "commit": "a.md"}})
        self.assertTrue(any("true / パス配列" in e for e in fixture_setup.validate(f)))

    def test_git_message_without_commit_is_reported(self):
        f = _fixture(setup={"git": {"init": True, "message": "chore: x"}})
        self.assertTrue(any("message は commit を必要とする" in e
                            for e in fixture_setup.validate(f)))

    def test_path_escaping_isolation_is_reported(self):
        f = _fixture(setup={"files": {"../outside.md": "x"}})
        self.assertTrue(any("隔離領域の外" in e for e in fixture_setup.validate(f)))

    def test_absolute_path_is_reported(self):
        f = _fixture(setup={"files": {"/etc/passwd": "x"}})
        self.assertTrue(any("隔離領域の外" in e for e in fixture_setup.validate(f)))

    def test_isolation_none_with_files_is_reported(self):
        f = _fixture(isolation="none", setup={"files": {"a.md": "x"}})
        self.assertTrue(any("isolation: none" in e for e in fixture_setup.validate(f)))

    def test_non_string_env_value_is_reported(self):
        f = _fixture(setup={"env": {"PORT": 8080}})
        self.assertTrue(any("setup.env" in e for e in fixture_setup.validate(f)))


class TestMaterialize(unittest.TestCase):
    def _materialize(self, setup, **kwargs):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        scenario = {"id": "s", "setup": setup}
        return temp.name, fixture_setup.materialize(scenario, temp.name, **kwargs)

    def test_writes_files_and_returns_baseline(self):
        dest, result = self._materialize({"files": {"src/a.py": "print(1)\n"}})
        with open(os.path.join(dest, "src/a.py"), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "print(1)\n")
        self.assertEqual(len(result["baseline"]["src/a.py"]), 64)

    def test_mtime_offsets_establish_ordering(self):
        # 一括生成で mtime が同値になり順序規則を測れなかった事故への対処
        dest, _ = self._materialize(
            {"files": {"old.md": "o", "new.md": "n"},
             "mtimes": {"old.md": -7200, "new.md": -3600}},
            base_time=1_700_000_000,
        )
        old = os.stat(os.path.join(dest, "old.md")).st_mtime
        new = os.stat(os.path.join(dest, "new.md")).st_mtime
        self.assertLess(old, new)
        self.assertEqual(new - old, 3600)

    def test_mtime_is_relative_to_base_time(self):
        dest, _ = self._materialize(
            {"files": {"a.md": "x"}, "mtimes": {"a.md": -60}},
            base_time=1_700_000_000,
        )
        self.assertEqual(
            int(os.stat(os.path.join(dest, "a.md")).st_mtime), 1_699_999_940)

    def test_files_without_mtime_entry_are_left_alone(self):
        dest, _ = self._materialize(
            {"files": {"a.md": "x", "b.md": "y"}, "mtimes": {"a.md": -3600}},
            base_time=1_700_000_000,
        )
        self.assertEqual(int(os.stat(os.path.join(dest, "a.md")).st_mtime), 1_699_996_400)
        self.assertNotEqual(int(os.stat(os.path.join(dest, "b.md")).st_mtime), 1_699_996_400)

    def test_git_init_and_commit_yield_clean_tree(self):
        # 「作業ツリーが clean」を要件にするシナリオの前提を宣言で作れること
        dest, result = self._materialize(
            {"files": {"a.md": "x"}, "git": {"init": True, "commit": True}})
        self.assertTrue(result["git"]["commit"])
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=dest,
            capture_output=True, text=True,
            env=dict(os.environ, **fixture_setup._GIT_ENV))
        self.assertEqual(status.stdout.strip(), "")

    def test_git_remote_is_registered(self):
        dest, _ = self._materialize(
            {"git": {"init": True, "remote": "https://example.invalid/r.git"}})
        url = subprocess.run(
            ["git", "remote", "get-url", "origin"], cwd=dest,
            capture_output=True, text=True,
            env=dict(os.environ, **fixture_setup._GIT_ENV))
        self.assertEqual(url.stdout.strip(), "https://example.invalid/r.git")

    def _git(self, dest, *args):
        return subprocess.run(
            ["git"] + list(args), cwd=dest, capture_output=True, text=True,
            env=dict(os.environ, **fixture_setup._GIT_ENV)).stdout.strip()

    def test_declared_branch_is_checked_out(self):
        # commit スキルの fixture は main/master 上だと Phase 2 で abort する
        dest, result = self._materialize({"git": {"init": True, "branch": "fixture-work"}})
        self.assertEqual(self._git(dest, "branch", "--show-current"), "fixture-work")
        self.assertEqual(result["git"]["branch"], "fixture-work")

    def test_default_branch_does_not_depend_on_the_environment(self):
        dest, _ = self._materialize({"git": {"init": True}})
        self.assertEqual(
            self._git(dest, "branch", "--show-current"), fixture_setup.DEFAULT_BRANCH)

    def test_commit_path_list_leaves_remaining_files_untracked(self):
        # 「ベースラインはある / 作業分は未コミット」という前提を宣言で作れること
        dest, _ = self._materialize({
            "files": {"base.md": "b", "work.md": "w"},
            "git": {"init": True, "commit": ["base.md"]},
        })
        self.assertEqual(self._git(dest, "status", "--porcelain"), "?? work.md")
        self.assertEqual(self._git(dest, "ls-files"), "base.md")

    def test_declared_baseline_message_becomes_the_history(self):
        # 「既存履歴のスタイルに合わせる」を測るシナリオは履歴の内容自体が前提
        dest, _ = self._materialize({
            "files": {"a.md": "x"},
            "git": {"init": True, "commit": True, "message": "chore: 基準コミットを作る"},
        })
        self.assertEqual(
            self._git(dest, "log", "-1", "--format=%s"), "chore: 基準コミットを作る")

    def test_git_commit_succeeds_with_no_files(self):
        _, result = self._materialize({"git": {"init": True, "commit": True}})
        self.assertTrue(result["git"]["commit"])

    def test_env_is_returned_for_the_caller(self):
        _, result = self._materialize({"env": {"XDG_STATE_HOME": "./xdg-state"}})
        self.assertEqual(result["env"], {"XDG_STATE_HOME": "./xdg-state"})

    def test_empty_setup_is_a_noop(self):
        _, result = self._materialize({})
        self.assertEqual(result["baseline"], {})
        self.assertEqual(result["git"], {})
        self.assertEqual(result["unmaterialized"], [])

    def test_materialized_files_are_not_reported_as_unmaterialized(self):
        _, result = self._materialize({"files": {"a.md": "x"}})
        self.assertEqual(result["unmaterialized"], [])

    def test_declaration_swallowed_by_the_environment_is_reported(self):
        # 実行基盤が機微な名前のファイルに /dev/null を被せると書き込みが捨てられる。
        # 宣言のハッシュを baseline にすると実体と食い違ったまま編集ゼロを判定してしまう
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        os.symlink("/dev/null", os.path.join(temp.name, ".env"))
        result = fixture_setup.materialize(
            {"id": "s", "setup": {"files": {".env": "API_KEY=dummy\n"}}}, temp.name)
        self.assertEqual(result["unmaterialized"], [".env"])
        self.assertNotEqual(
            result["baseline"][".env"],
            hashlib.sha256(b"API_KEY=dummy\n").hexdigest())


class TestShippedFixtures(unittest.TestCase):
    """リポジトリ同梱の fixtures.json が契約に適合していること。"""

    def test_all_shipped_fixtures_are_valid(self):
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
        skills = os.path.normpath(root)
        errors = []
        for name in sorted(os.listdir(skills)):
            path = os.path.join(skills, name, "fixtures.json")
            if not os.path.isfile(path):
                continue
            with open(path, encoding="utf-8") as handle:
                errors += fixture_setup.validate(json.load(handle), source=f"{name}/fixtures.json")
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()


class MaterializeIsHermeticAgainstAnInheritedRepository(unittest.TestCase):
    """A git hook exports GIT_DIR. Inheriting it makes the isolated area point
    at the caller's repository, so the declaration stops deciding the setup."""

    SCENARIO = {
        "id": "x-001",
        "setup": {"files": {"a.txt": "a\n"}, "git": {"init": True, "commit": True}},
    }

    def _materialize(self):
        with tempfile.TemporaryDirectory() as root:
            dest = os.path.join(root, "area")
            result = fixture_setup.materialize(self.SCENARIO, dest)
            return result, os.path.isdir(os.path.join(dest, ".git"))

    def test_it_initialises_its_own_repository_without_an_inherited_one(self):
        result, has_git = self._materialize()
        self.assertTrue(result["git"].get("init"))
        self.assertTrue(result["git"].get("commit"))
        self.assertTrue(has_git)

    def test_it_still_does_so_when_the_environment_names_another_repository(self):
        previous = os.environ.get("GIT_DIR")
        os.environ["GIT_DIR"] = os.path.abspath(".git")
        try:
            result, has_git = self._materialize()
        finally:
            if previous is None:
                os.environ.pop("GIT_DIR", None)
            else:
                os.environ["GIT_DIR"] = previous
        self.assertTrue(result["git"].get("init"))
        self.assertTrue(result["git"].get("commit"))
        self.assertTrue(has_git)
