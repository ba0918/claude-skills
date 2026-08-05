"""fixture_setup.py の unittest。

検証（純関数）と、隔離領域への実体化（mtime 順・git 状態・env）を検証する。
実体化のテストは「fixture の宣言だけで前提が決まる」ことを守るためのもので、
呼び出し側の手作業に前提が漏れると測定対象がぶれる。
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

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


class TestRequirementCountWarning(unittest.TestCase):
    """要件数が設計目安（3-7 件）の上端を超えたシナリオを info で報告する。

    超過そのものは不正ではなく、分割か裁定が要る設計上の兆候。violation に
    すると多段スキルの恒常鳴りで検証が止まるため info 側に置く（#262）。
    """

    @staticmethod
    def _validate(count):
        fixture = _fixture(requirements=[
            {"text": f"要件 {index}", "critical": True} for index in range(count)])
        return fixture_setup.validate_with_warnings(fixture)

    @staticmethod
    def _count_warnings(warnings):
        return [w for w in warnings if "requirements が" in w]

    def test_at_the_guideline_upper_bound_stays_silent(self):
        _, warnings = self._validate(7)
        self.assertEqual(self._count_warnings(warnings), [])

    def test_exceeding_the_guideline_is_reported_once_with_count_and_id(self):
        _, warnings = self._validate(8)
        hits = self._count_warnings(warnings)
        self.assertEqual(len(hits), 1)
        self.assertIn("8", hits[0])
        self.assertIn("sf-001", hits[0])

    def test_the_report_is_info_and_not_a_violation(self):
        errors, warnings = self._validate(8)
        self.assertEqual(errors, [])
        self.assertTrue(self._count_warnings(warnings)[0].startswith("[info]"))

    def test_the_cli_still_exits_zero_when_only_the_count_is_exceeded(self):
        fixture = _fixture(requirements=[
            {"text": f"要件 {index}", "critical": True} for index in range(8)])
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "fixtures.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(fixture, handle, ensure_ascii=False)
            self.assertEqual(fixture_setup.main(["--validate", path]), 0)


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

    def test_seeded_commits_after_the_baseline_pass(self):
        f = _fixture(setup={
            "files": {"a.md": "x"},
            "git": {"init": True, "commit": True,
                    "commits": [{"files": {"b.py": "print(1)\n"}, "message": "feat: b"}]},
        })
        self.assertEqual(fixture_setup.validate(f), [])

    def test_git_commits_without_baseline_commit_is_reported(self):
        # baseline の無い積み上げは「どこから後か」が決まらない
        f = _fixture(setup={
            "files": {"a.md": "x"},
            "git": {"init": True,
                    "commits": [{"files": {"b.py": "y"}, "message": "feat: b"}]},
        })
        self.assertTrue(any("setup.git.commits" in e for e in fixture_setup.validate(f)))

    def test_empty_git_commits_list_is_reported(self):
        f = _fixture(setup={
            "files": {"a.md": "x"},
            "git": {"init": True, "commit": True, "commits": []},
        })
        self.assertTrue(any("意図が曖昧" in e for e in fixture_setup.validate(f)))

    def test_unknown_key_in_a_seeded_commit_is_reported(self):
        f = _fixture(setup={
            "files": {"a.md": "x"},
            "git": {"init": True, "commit": True,
                    "commits": [{"files": {"b.py": "y"}, "msg": "feat: b"}]},
        })
        self.assertTrue(any("未知の setup.git.commits" in e
                            for e in fixture_setup.validate(f)))

    def test_seeded_commit_without_message_is_reported(self):
        # 積んだコミットの subject は skill が読む履歴そのもので、既定に委ねられない
        f = _fixture(setup={
            "files": {"a.md": "x"},
            "git": {"init": True, "commit": True, "commits": [{"files": {"b.py": "y"}}]},
        })
        self.assertTrue(any("message" in e for e in fixture_setup.validate(f)))

    def test_seeded_commit_without_files_is_reported(self):
        f = _fixture(setup={
            "files": {"a.md": "x"},
            "git": {"init": True, "commit": True, "commits": [{"message": "feat: b"}]},
        })
        self.assertTrue(any("files" in e for e in fixture_setup.validate(f)))

    def test_seeded_commit_path_escaping_isolation_is_reported(self):
        f = _fixture(setup={
            "files": {"a.md": "x"},
            "git": {"init": True, "commit": True,
                    "commits": [{"files": {"../out.py": "y"}, "message": "feat: b"}]},
        })
        self.assertTrue(any("隔離領域の外" in e for e in fixture_setup.validate(f)))

    def test_seeded_commit_of_a_gitignored_path_is_reported(self):
        # git add が拒否し、空コミットが黙って積まれる（宣言と実体が食い違う）
        f = _fixture(setup={
            "files": {".gitignore": "/build/\n"},
            "git": {"init": True, "commit": True,
                    "commits": [{"files": {"build/out.py": "y"}, "message": "feat: b"}]},
        })
        self.assertTrue(any("無視" in e for e in fixture_setup.validate(f)))

    def test_baseline_commit_list_of_a_gitignored_path_is_reported(self):
        # 配列形の baseline も seed コミットと同じ穴を持つ。git add が拒否されても
        # --allow-empty が空の baseline を作るので、宣言のどれも追跡されないまま
        # git_state["commit"] は True で返り、シナリオは前提が崩れた状態で走る
        f = _fixture(setup={
            "files": {".gitignore": "/build/\n", "build/out.py": "y"},
            "git": {"init": True, "commit": ["build/out.py"]},
        })
        self.assertTrue(any("無視" in e for e in fixture_setup.validate(f)))


    def test_path_escaping_isolation_is_reported(self):
        f = _fixture(setup={"files": {"../outside.md": "x"}})
        self.assertTrue(any("隔離領域の外" in e for e in fixture_setup.validate(f)))

    def test_declaring_a_file_under_the_git_directory_is_reported(self):
        # .git/hooks/ を宣言できると、実体化しただけで隔離領域の外へ効果が漏れる
        f = _fixture(setup={"files": {".git/hooks/pre-commit": "#!/bin/sh\n"}})
        self.assertTrue(any(".git/" in e for e in fixture_setup.validate(f)))

    def test_declaring_a_file_under_a_case_variant_git_directory_is_reported(self):
        # 大文字小文字を区別しない FS（macOS / Windows の既定）では .Git/hooks/ も
        # .git/hooks/ に着地する。完全一致で判定すると遮断をすり抜ける
        f = _fixture(setup={"files": {".Git/hooks/pre-commit": "#!/bin/sh\n"}})
        self.assertTrue(any(".git/" in e for e in fixture_setup.validate(f)))

    def test_seeded_commit_under_the_git_directory_is_reported(self):
        f = _fixture(setup={
            "files": {"a.md": "x"},
            "git": {"init": True, "commit": True,
                    "commits": [{"files": {".git/hooks/pre-commit": "#!/bin/sh\n"},
                                 "message": "feat: hook"}]},
        })
        self.assertTrue(any(".git/" in e for e in fixture_setup.validate(f)))

    def test_absolute_path_is_reported(self):
        f = _fixture(setup={"files": {"/etc/passwd": "x"}})
        self.assertTrue(any("隔離領域の外" in e for e in fixture_setup.validate(f)))

    def test_isolation_none_with_files_is_reported(self):
        f = _fixture(isolation="none", setup={"files": {"a.md": "x"}})
        self.assertTrue(any("isolation: none" in e for e in fixture_setup.validate(f)))

    def test_non_string_env_value_is_reported(self):
        f = _fixture(setup={"env": {"PORT": 8080}})
        self.assertTrue(any("setup.env" in e for e in fixture_setup.validate(f)))


class TestValidateShaPlaceholders(unittest.TestCase):
    """SHA プレースホルダは「コミット後に書き換える」ので、対象が追跡されていると
    working tree が dirty になり、seed が作ろうとしていた前提そのものが壊れる。"""

    IGNORE = "/.agents/artifacts/\n"
    PLAN = ".agents/artifacts/plans/p.md"

    def _validate(self, files, git):
        return fixture_setup.validate(_fixture(setup={"files": files, "git": git}))

    def test_placeholder_in_an_untracked_file_passes(self):
        errors = self._validate(
            {".gitignore": self.IGNORE, self.PLAN: "base: {{fixture:sha:baseline}}\n"},
            {"init": True, "commit": True,
             "commits": [{"files": {"a.py": "x"}, "message": "feat: a"}]})
        self.assertEqual(errors, [])

    def test_placeholder_in_a_baseline_committed_file_is_reported(self):
        errors = self._validate(
            {"plan.md": "base: {{fixture:sha:baseline}}\n"},
            {"init": True, "commit": True,
             "commits": [{"files": {"a.py": "x"}, "message": "feat: a"}]})
        self.assertTrue(any("コミット" in e for e in errors), errors)

    def test_placeholder_in_a_seeded_commit_file_is_reported(self):
        errors = self._validate(
            {".gitignore": self.IGNORE},
            {"init": True, "commit": True,
             "commits": [{"files": {"a.py": "# {{fixture:sha:baseline}}\n"},
                          "message": "feat: a"}]})
        self.assertTrue(any("コミット" in e for e in errors), errors)

    def test_commits_index_out_of_range_is_reported(self):
        errors = self._validate(
            {".gitignore": self.IGNORE, self.PLAN: "{{fixture:sha:commits[3]}}\n"},
            {"init": True, "commit": True,
             "commits": [{"files": {"a.py": "x"}, "message": "feat: a"}]})
        self.assertTrue(any("commits[3]" in e for e in errors), errors)

    def test_misspelled_placeholder_is_reported(self):
        # 素通しすると plan に文字列のまま残り、skill は「SHA が解決できない」経路へ行く
        errors = self._validate(
            {".gitignore": self.IGNORE, self.PLAN: "{{fixture:sha:base}}\n"},
            {"init": True, "commit": True,
             "commits": [{"files": {"a.py": "x"}, "message": "feat: a"}]})
        self.assertTrue(any("fixture:sha" in e for e in errors), errors)

    def test_a_violation_inside_a_seeded_commit_names_that_commit(self):
        # 由来が setup.files と報告されると、宣言のどこを直せばよいか分からない
        errors = self._validate(
            {".gitignore": self.IGNORE},
            {"init": True, "commit": True,
             "commits": [{"files": {"a.py": "x"}, "message": "feat: a"},
                         {"files": {"b.py": "# {{fixture:sha:baseline}}\n"},
                          "message": "feat: b"}]})
        self.assertTrue(
            any("setup.git.commits[1].files['b.py']" in e for e in errors), errors)

    def test_baseline_placeholder_without_a_baseline_commit_is_reported(self):
        errors = self._validate(
            {".gitignore": self.IGNORE, self.PLAN: "{{fixture:sha:baseline}}\n"},
            {"init": True})
        self.assertTrue(any("fixture:sha" in e for e in errors), errors)


class TestMaterializeSeededHistory(unittest.TestCase):
    """seed した履歴と SHA 置換が、宣言だけから決まること。"""

    IGNORE = "/.agents/artifacts/\n"
    PLAN = ".agents/artifacts/plans/p.md"

    def _materialize(self, setup, **kwargs):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        scenario = {"id": "s", "setup": setup}
        return temp.name, fixture_setup.materialize(scenario, temp.name, **kwargs)

    def _git(self, dest, *args):
        return subprocess.run(
            ["git"] + list(args), cwd=dest, capture_output=True, text=True,
            env=dict(os.environ, **fixture_setup._GIT_ENV)).stdout.strip()

    SEED = {
        "files": {".gitignore": IGNORE, "README.md": "# seed\n"},
        "git": {"init": True, "commit": True, "message": "chore: baseline",
                "commits": [
                    {"files": {"app.py": "def f():\n    return 1\n"},
                     "message": "feat: add f"},
                    {"files": {"tests/test_app.py": "assert True\n",
                               "app.py": "def f():\n    return 2\n"},
                     "message": "test: cover f"},
                ]},
    }

    def test_seeded_commits_are_stacked_after_the_baseline_in_order(self):
        dest, result = self._materialize(self.SEED)
        self.assertEqual(
            self._git(dest, "log", "--format=%s").splitlines(),
            ["test: cover f", "feat: add f", "chore: baseline"])
        self.assertEqual(len(result["git"]["commits"]), 2)

    def test_seeded_commit_contents_are_the_declared_ones(self):
        dest, _ = self._materialize(self.SEED)
        self.assertEqual(
            self._git(dest, "show", "HEAD:app.py"), "def f():\n    return 2")
        self.assertEqual(
            self._git(dest, "show", "HEAD~1:app.py"), "def f():\n    return 1")
        self.assertEqual(self._git(dest, "status", "--porcelain"), "")

    def test_a_seeded_commit_holds_only_its_own_files(self):
        # 各要素は宣言したファイルだけを含む（前の要素の変更を巻き込まない）
        dest, _ = self._materialize(self.SEED)
        self.assertEqual(
            sorted(self._git(dest, "show", "--name-only", "--format=", "HEAD").split()),
            ["app.py", "tests/test_app.py"])

    REDECLARED = {
        "files": {".gitignore": IGNORE, "app.py": "def f():\n    return 0\n"},
        "git": {"init": True, "commit": True,
                "commits": [{"files": {"app.py": "def f():\n    return 1\n"},
                             "message": "feat: add f"}]},
    }

    def test_a_path_redeclared_by_a_seeded_commit_takes_the_seeded_content(self):
        # 宣言は重ね書き。期待値を setup.files のままにすると、後から積んだ内容が
        # 「宣言と食い違う」と誤判定され、実体化できていない扱いになる
        dest, result = self._materialize(self.REDECLARED)
        self.assertEqual(result["unmaterialized"], [])
        with open(os.path.join(dest, "app.py"), "rb") as handle:
            self.assertEqual(
                result["baseline"]["app.py"],
                hashlib.sha256(handle.read()).hexdigest())

    def test_paths_that_exist_only_in_a_seeded_commit_are_covered(self):
        # baseline に載らないパスは編集ゼロの裏取りから丸ごと外れる
        _, result = self._materialize(self.SEED)
        self.assertIn("tests/test_app.py", result["baseline"])

    def test_baseline_placeholder_resolves_to_the_baseline_sha(self):
        setup = {
            "files": {".gitignore": self.IGNORE,
                      self.PLAN: "**Implementation Base SHA:** {{fixture:sha:baseline}}\n"},
            "git": {"init": True, "commit": True,
                    "commits": [{"files": {"app.py": "x\n"}, "message": "feat: a"}]},
        }
        dest, result = self._materialize(setup)
        baseline_sha = self._git(dest, "rev-parse", "HEAD~1")
        with open(os.path.join(dest, self.PLAN), encoding="utf-8") as handle:
            written = handle.read()
        self.assertEqual(
            written, f"**Implementation Base SHA:** {baseline_sha}\n")
        self.assertEqual(result["git"]["baseline"], baseline_sha)

    def test_commits_placeholder_resolves_to_that_commit_sha(self):
        setup = {
            "files": {".gitignore": self.IGNORE,
                      self.PLAN: "first={{fixture:sha:commits[0]}} "
                                 "second={{fixture:sha:commits[1]}}\n"},
            "git": {"init": True, "commit": True,
                    "commits": [{"files": {"a.py": "1\n"}, "message": "feat: a"},
                                {"files": {"b.py": "2\n"}, "message": "feat: b"}]},
        }
        dest, result = self._materialize(setup)
        with open(os.path.join(dest, self.PLAN), encoding="utf-8") as handle:
            written = handle.read()
        self.assertEqual(
            written,
            f"first={self._git(dest, 'rev-parse', 'HEAD~1')} "
            f"second={self._git(dest, 'rev-parse', 'HEAD')}\n")
        self.assertEqual(result["git"]["commits"],
                         [self._git(dest, "rev-parse", "HEAD~1"),
                          self._git(dest, "rev-parse", "HEAD")])

    def test_the_tree_stays_clean_after_substitution(self):
        # 置換対象が追跡されていれば dirty になる。前提を壊さないことを実体で確かめる
        setup = {
            "files": {".gitignore": self.IGNORE,
                      self.PLAN: "{{fixture:sha:baseline}}\n"},
            "git": {"init": True, "commit": True,
                    "commits": [{"files": {"app.py": "x\n"}, "message": "feat: a"}]},
        }
        dest, _ = self._materialize(setup)
        self.assertEqual(
            self._git(dest, "status", "--porcelain", "--untracked-files=all"), "")

    def test_the_baseline_hash_is_taken_after_substitution(self):
        setup = {
            "files": {".gitignore": self.IGNORE,
                      self.PLAN: "{{fixture:sha:baseline}}\n"},
            "git": {"init": True, "commit": True,
                    "commits": [{"files": {"app.py": "x\n"}, "message": "feat: a"}]},
        }
        dest, result = self._materialize(setup)
        with open(os.path.join(dest, self.PLAN), "rb") as handle:
            on_disk = hashlib.sha256(handle.read()).hexdigest()
        self.assertEqual(result["baseline"][self.PLAN], on_disk)
        self.assertNotEqual(
            result["baseline"][self.PLAN],
            hashlib.sha256(b"{{fixture:sha:baseline}}\n").hexdigest())

    def test_an_unresolvable_placeholder_fails_materialization(self):
        # 文字列のまま残すと、測りたい経路ではなく「SHA 解決不能」経路が走る
        setup = {
            "files": {".gitignore": self.IGNORE,
                      self.PLAN: "{{fixture:sha:commits[7]}}\n"},
            "git": {"init": True, "commit": True,
                    "commits": [{"files": {"a.py": "1\n"}, "message": "feat: a"}]},
        }
        with self.assertRaises(fixture_setup.MaterializeError):
            self._materialize(setup)

    def test_declared_mtimes_survive_substitution(self):
        setup = {
            "files": {".gitignore": self.IGNORE,
                      self.PLAN: "{{fixture:sha:baseline}}\n"},
            "mtimes": {self.PLAN: -3600},
            "git": {"init": True, "commit": True,
                    "commits": [{"files": {"a.py": "1\n"}, "message": "feat: a"}]},
        }
        dest, _ = self._materialize(setup, base_time=1_700_000_000)
        self.assertEqual(
            int(os.stat(os.path.join(dest, self.PLAN)).st_mtime), 1_699_996_400)


class TestMaterializeIsReproducible(unittest.TestCase):
    """同じ宣言を 2 回実体化したら、seed の SHA も baseline ハッシュも一致すること。

    rerun は manifest に残した baseline と再実体化した baseline を厳密比較してから
    work dir を作り直す。実体化のたびに seed コミットの SHA が変わると、SHA を埋めた
    文書のハッシュも動くので、rerun は毎回「fixture が build 後に変わった」と判定し、
    seed を持つシナリオを再走できなくなる。
    """

    SETUP = {
        "files": {
            ".gitignore": "/.agents/artifacts/\n",
            "README.md": "# seed\n",
            ".agents/artifacts/plans/p.md":
                "**Implementation Base SHA:** {{fixture:sha:baseline}}\n"
                "実装済み: {{fixture:sha:commits[0]}}\n",
        },
        "git": {"init": True, "commit": True, "message": "chore: baseline",
                "commits": [{"files": {"app.py": "def f():\n    return 1\n"},
                             "message": "feat: add f"}]},
    }

    DATES = ("GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE")

    def setUp(self):
        # 実体化の合間に時計が進む状況を決定的に作る。素の 2 連続呼び出しでは同じ秒に
        # 収まってしまい、時刻依存が緑のまま隠れる（git のコミット時刻は秒精度）
        previous = {name: os.environ.get(name) for name in self.DATES}

        def restore():
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
        self.addCleanup(restore)

    def _materialize(self, ambient_date):
        for name in self.DATES:
            os.environ[name] = ambient_date
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        return fixture_setup.materialize(
            {"id": "s", "setup": self.SETUP}, temp.name, base_time=1_750_000_000)

    def _twice(self):
        return (self._materialize("2026-01-02T03:04:05+00:00"),
                self._materialize("2026-06-07T08:09:10+00:00"))

    def test_the_seeded_shas_are_identical_across_materialisations(self):
        first, second = self._twice()
        self.assertEqual(first["git"]["baseline"], second["git"]["baseline"])
        self.assertEqual(first["git"]["commits"], second["git"]["commits"])

    def test_the_baseline_hash_map_is_identical_across_materialisations(self):
        # SHA を埋めた文書のハッシュまで含めて一致すること（rerun の比較対象そのもの）
        first, second = self._twice()
        self.assertEqual(first["baseline"], second["baseline"])


class TestArtifactStoreDeclaration(unittest.TestCase):
    """`.agents/` を宣言する fixture が Artifact Store 契約を満たすか（静的検査）。

    契約違反のまま実体化した fixture は store が writable: false に落ち、Phase 0 で
    store を検証するスキルは宣言したシナリオへ到達しないまま abort する。落ちる
    fixture と違って赤くならないので、宣言の時点で止める。
    """

    STORE = {".agents/artifacts/status.md": "# status\n"}
    IGNORE = "# ignore\n/.agents/artifacts/\n"

    def _store_errors(self, files, git={"init": True, "commit": True}):
        keys = ("artifact store", "runtime 領域", "artifacts.yml")
        return [e for e in fixture_setup.validate(_fixture(setup={"files": files, "git": git}))
                if any(k in e for k in keys)]

    def test_ignored_store_passes(self):
        self.assertEqual(self._store_errors({".gitignore": self.IGNORE, **self.STORE}), [])

    def test_store_without_any_gitignore_is_reported(self):
        errors = self._store_errors(dict(self.STORE))
        self.assertTrue(any("到達できない" in e for e in errors), errors)

    def test_store_with_unrelated_gitignore_is_reported(self):
        files = {".gitignore": "__pycache__/\n*.pyc\n", **self.STORE}
        self.assertTrue(any("到達できない" in e for e in self._store_errors(files)))

    def test_bare_directory_pattern_covers_the_store(self):
        self.assertEqual(self._store_errors({".gitignore": ".agents/\n", **self.STORE}), [])

    def test_negation_re_exposing_the_store_is_reported(self):
        files = {".gitignore": ".agents/\n!.agents/artifacts/\n", **self.STORE}
        self.assertTrue(any("到達できない" in e for e in self._store_errors(files)))

    def test_scenario_without_own_git_is_not_checked(self):
        # 自前の git を持たないシナリオは、周囲のリポジトリが無視設定を持つ。
        # fixture の宣言だけでは判定できないので検査しない（偽陽性を出さない）
        self.assertEqual(self._store_errors(dict(self.STORE), git={}), [])

    def test_scenario_without_store_files_is_not_checked(self):
        self.assertEqual(self._store_errors({"src/a.py": "x\n"}), [])

    def test_explicit_public_policy_may_be_tracked(self):
        files = {".agents/artifacts.yml": "schema_version: 1\nroot: .agents/artifacts\n"
                                          "visibility: public\nworktree_scope: worktree\n",
                 **self.STORE}
        self.assertEqual(self._store_errors(files), [])

    def test_public_store_that_is_gitignored_is_reported(self):
        files = {".gitignore": self.IGNORE,
                 ".agents/artifacts.yml": "schema_version: 1\nvisibility: public\n",
                 **self.STORE}
        self.assertTrue(any("追跡されず" in e for e in self._store_errors(files)))

    def test_gitignored_policy_file_is_reported(self):
        files = {".gitignore": ".agents/\n",
                 ".agents/artifacts.yml": "schema_version: 1\nvisibility: local\n",
                 **self.STORE}
        self.assertTrue(any("policy" in e for e in self._store_errors(files)))

    def test_custom_root_from_the_declared_policy_is_honoured(self):
        policy = {".agents/artifacts.yml": "schema_version: 1\nroot: .agents/store\n"
                                           "visibility: local\n"}
        moved = {".agents/store/status.md": "# status\n"}
        # 既定 root だけ無視しても、宣言された root は無視されていない
        self.assertTrue(self._store_errors({".gitignore": self.IGNORE, **policy, **moved}))
        self.assertEqual(
            self._store_errors({".gitignore": "/.agents/store/\n", **policy, **moved}), [])

    def test_runtime_area_must_be_ignored_regardless_of_visibility(self):
        runtime = {".agents/runtime/polling/session.json": "{}\n"}
        public = {".agents/artifacts.yml": "schema_version: 1\nvisibility: public\n"}
        self.assertTrue(any("runtime 領域" in e
                            for e in self._store_errors({**public, **runtime})))
        files = {".gitignore": "/.agents/runtime/\n", **public, **runtime}
        self.assertEqual(self._store_errors(files), [])


class TestShippedFixturesReachTheirStore(unittest.TestCase):
    """静的検査の判定が、実体化後の store 検査と一致すること。

    宣言だけを読む `--validate` と、実体を読む artifact_store の判定がずれると、
    CI が緑でもシナリオに到達できない状態が復活する。同梱 fixture を実際に
    実体化して両者を突き合わせ、静的検査を実測に固定する。
    """

    @classmethod
    def setUpClass(cls):
        shared = os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "..", "shared", "scripts"))
        if shared not in sys.path:
            sys.path.insert(0, shared)
        import artifact_store  # noqa: PLC0415
        cls.artifact_store = artifact_store
        cls.skills = os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", ".."))

    def _scenarios(self):
        for name in sorted(os.listdir(self.skills)):
            path = os.path.join(self.skills, name, "fixtures.json")
            if not os.path.isfile(path):
                continue
            with open(path, encoding="utf-8") as handle:
                doc = json.load(handle)
            for scenario in doc["scenarios"]:
                setup = scenario.get("setup") or {}
                files = setup.get("files") or {}
                # 自前の git を宣言するシナリオだけが、fixture の宣言だけで判定できる。
                # 宣言しないシナリオは実体化先の周囲のリポジトリが無視設定を持つ
                if (setup.get("git") or {}).get("init") and any(
                        p.startswith(".agents/") for p in files):
                    yield doc["skill"], scenario

    def test_every_declared_store_is_writable_after_materialize(self):
        checked = []
        for skill, scenario in self._scenarios():
            with tempfile.TemporaryDirectory() as dest:
                fixture_setup.materialize(scenario, dest, base_time=1_750_000_000)
                result = self.artifact_store.inspect(dest)
            checked.append(f"{skill}/{scenario['id']}")
            self.assertTrue(
                result["writable"],
                f"{skill}/{scenario['id']} の store が writable でない: {result['errors']}")
        self.assertTrue(checked, "git を宣言する .agents/ シナリオが 1 件も無い（検出側の壊れ）")

    def test_static_check_agrees_with_the_materialized_store(self):
        for skill, scenario in self._scenarios():
            declared_ok = not fixture_setup.validate(
                {"skill": skill, "scenarios": [scenario]}, source=skill)
            with tempfile.TemporaryDirectory() as dest:
                fixture_setup.materialize(scenario, dest, base_time=1_750_000_000)
                actual_ok = self.artifact_store.inspect(dest)["writable"]
            self.assertEqual(
                declared_ok, actual_ok,
                f"{skill}/{scenario['id']}: 宣言の検査={declared_ok} 実体の検査={actual_ok}")


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


class TestShippedSeededScenariosReachTheirPhase(unittest.TestCase):
    """seed した履歴が、対象 phase へ到達できる形になっていること。

    phase 終端型の fixture は「baseline より後に実装コミットがあり、文書が baseline を
    指している」ことで対象 phase に入る。ここが崩れたシナリオは赤くならず、空 diff
    ガードなど別の経路を測って合格するので、宣言の時点で機械的に止める。
    """

    SKILLS = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", ".."))

    @staticmethod
    def _is_seeded(scenario):
        return bool(((scenario.get("setup") or {}).get("git") or {}).get("commits"))

    def _fixtures(self):
        for name in sorted(os.listdir(self.SKILLS)):
            path = os.path.join(self.SKILLS, name, "fixtures.json")
            if not os.path.isfile(path):
                continue
            with open(path, encoding="utf-8") as handle:
                yield json.load(handle)

    def _seeded(self):
        for doc in self._fixtures():
            for scenario in doc["scenarios"]:
                if self._is_seeded(scenario):
                    yield doc["skill"], scenario

    # 最終 phase の完了処理まで到達することを要求する言い回し。別スキルが seed を
    # 使い始めたら、そのスキルの完了語彙をここへ足す
    COMPLETION_MARKERS = ("完了処理", "CYCLE COMPLETE", "アーカイブ", "archived")
    # 停止系シナリオは「最終 phase が実行されていない」を要件に書く。完了語の出現
    # だけを見ると、連鎖を測らない停止系まで smoke に数えてしまう
    NEGATION_MARKERS = ("実行されていない", "実行されず", "生成されていない",
                        "生成されておらず", "行われていない")

    @classmethod
    def _requires_final_phase_completion(cls, scenario):
        for requirement in scenario["requirements"]:
            text = requirement["text"]
            if (any(m in text for m in cls.COMPLETION_MARKERS)
                    and not any(m in text for m in cls.NEGATION_MARKERS)):
                return True
        return False

    def test_a_fixture_with_seeded_scenarios_keeps_a_through_run_smoke(self):
        # fixture-schema § Guarantee boundaries: seed は「phase が実際に連鎖するか」の
        # 保証を通し実行の smoke へ移す変更なので、smoke は 1 本残す規則になっている。
        # 全シナリオが seed 済みになると、連鎖と委譲リレーを測る経路が誰も残らない
        # （unit テストにも phase 終端型にも代替が無い）。
        # 「非 seed が 1 本以上」では守れない: 停止系シナリオは非 seed でも途中 phase で
        # 終わるので、通し実行の smoke を seed 化しても残りの停止系が数に入って通る。
        # 残っているべきは「最終 phase の完了処理まで要求する」非 seed シナリオ
        checked = []
        for doc in self._fixtures():
            if not any(self._is_seeded(s) for s in doc["scenarios"]):
                continue
            checked.append(doc["skill"])
            self.assertTrue(
                [s["id"] for s in doc["scenarios"]
                 if not self._is_seeded(s)
                 and self._requires_final_phase_completion(s)],
                f"{doc['skill']}: 最終 phase の完了処理まで要求する非 seed シナリオが"
                f" 1 本も無く、通し実行の smoke が消えている")
        self.assertTrue(checked, "commits を宣言する fixture が 1 件も無い（検出側の壊れ）")

    def test_every_seeded_scenario_leaves_a_non_empty_range_from_its_baseline(self):
        checked = []
        for skill, scenario in self._seeded():
            where = f"{skill}/{scenario['id']}"
            with tempfile.TemporaryDirectory() as dest:
                result = fixture_setup.materialize(
                    scenario, dest, base_time=1_750_000_000)
                baseline = result["git"]["baseline"]
                diff = subprocess.run(
                    ["git", "diff", "--name-only", f"{baseline}..HEAD"], cwd=dest,
                    capture_output=True, text=True,
                    env=dict(os.environ, **fixture_setup._GIT_ENV))
                self.assertTrue(
                    diff.stdout.strip(),
                    f"{where}: baseline..HEAD が空（対象 phase の手前で止まる）")
                for path, declared in (scenario["setup"].get("files") or {}).items():
                    if "{{fixture:sha:baseline}}" not in declared:
                        continue
                    with open(os.path.join(dest, path), encoding="utf-8") as handle:
                        written = handle.read()
                    self.assertIn(
                        baseline, written,
                        f"{where}: {path} が baseline を指していない")
            checked.append(where)
        self.assertTrue(checked, "commits を宣言するシナリオが 1 件も無い（検出側の壊れ）")

    PROGRESS_DIR = ".agents/artifacts/plans/progress/"
    PLAN_RE = re.compile(r"^\.agents/artifacts/plans/(\d{14})_[^/]+\.md$")
    CYCLE_ID_RE = re.compile(r"\*\*Cycle ID:\*\*\s*`?([0-9]{14})`?")

    @classmethod
    def _declared_cycle_ids(cls, files):
        """runtime-progress の解決順（plan の Cycle ID ヘッダ → ファイル名の timestamp）。"""
        ids = set()
        for path, contents in files.items():
            match = cls.PLAN_RE.match(path)
            if not match:
                continue
            header = cls.CYCLE_ID_RE.search(contents or "")
            ids.add(header.group(1) if header else match.group(1))
        return ids

    DONE_STATUS = "🟢 Done"

    @classmethod
    def _step_statuses(cls, contents):
        """progress の Steps 表から Status 列を取り出す（見出しと区切り行は除く）。"""
        statuses = []
        for line in (contents or "").splitlines():
            line = line.strip()
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < 3:
                continue
            status = cells[2]
            if status == "Status" or set(status) <= set("-: "):
                continue
            statuses.append(status)
        return statuses

    def test_every_seeded_scenario_declares_the_progress_file_of_its_cycle(self):
        # runtime-progress § Rules の re-entry: 再入時は progress を読んで 🟢 Done の
        # step を再実装しない。seed した実装に対応する progress が宣言から抜けると、
        # skill は完了済みの step を最初から実装し直し、phase 終端型の前提が崩れる。
        # 落ちるのではなく前の phase を測って合格するので、宣言の時点で止める。
        # 存在だけでは足りない: 全 step が ⚪ Pending の progress を宣言すると
        # 「宣言はある」まま Phase 1 が再実装に入り、同じ穴が開いたまま合格する。
        # seed した実装と step の対応は宣言から機械的に引けないので、
        # 「seed があるなら Done の step が最低 1 つある」を下限として要求する
        checked = []
        for skill, scenario in self._seeded():
            where = f"{skill}/{scenario['id']}"
            files = (scenario.get("setup") or {}).get("files") or {}
            cycle_ids = self._declared_cycle_ids(files)
            progress = {
                os.path.splitext(p[len(self.PROGRESS_DIR):])[0]
                for p in files if p.startswith(self.PROGRESS_DIR)}
            matched = progress & cycle_ids
            self.assertTrue(
                matched,
                f"{where}: seed した実装に対応する "
                f"{self.PROGRESS_DIR}{{cycle_id}}.md が宣言されていない "
                f"(cycle_id={sorted(cycle_ids)} progress={sorted(progress)})")
            for cycle_id in sorted(matched):
                statuses = self._step_statuses(
                    files[f"{self.PROGRESS_DIR}{cycle_id}.md"])
                self.assertTrue(
                    statuses,
                    f"{where}: progress/{cycle_id}.md の Steps 表に step 行が無い")
                self.assertIn(
                    self.DONE_STATUS, statuses,
                    f"{where}: progress/{cycle_id}.md の step が 1 つも "
                    f"{self.DONE_STATUS} でない（seed 済みの step を再実装する）"
                    f" statuses={statuses}")
            checked.append(where)
        self.assertTrue(checked, "commits を宣言するシナリオが 1 件も無い（検出側の壊れ）")

    TEST_DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+(test_\w+)", re.M)

    @classmethod
    def _test_names_in_the_tree(cls, dest):
        names = set()
        for root, dirs, files in os.walk(dest):
            dirs[:] = [d for d in dirs if d != ".git"]
            for name in files:
                try:
                    with open(os.path.join(root, name), encoding="utf-8") as handle:
                        names |= set(cls.TEST_DEF_RE.findall(handle.read()))
                except (UnicodeDecodeError, OSError):
                    continue
        return names

    def test_a_seed_never_drops_a_test_declared_in_the_baseline(self):
        # seed コミットは setup.files と同じパスを重ね書きできる。baseline が持って
        # いたテストを seed が削ると、シナリオが前提にしている安全網（既存テストが
        # 通る状態から始まる）が黙って消え、実装が壊れても赤くならない経路ができる
        checked = []
        for skill, scenario in self._seeded():
            where = f"{skill}/{scenario['id']}"
            declared = set()
            for contents in ((scenario.get("setup") or {}).get("files") or {}).values():
                declared |= set(self.TEST_DEF_RE.findall(contents or ""))
            if not declared:
                continue
            with tempfile.TemporaryDirectory() as dest:
                fixture_setup.materialize(scenario, dest, base_time=1_750_000_000)
                seeded = self._test_names_in_the_tree(dest)
            self.assertLessEqual(
                declared, seeded,
                f"{where}: baseline のテスト {sorted(declared - seeded)} が "
                f"seed 適用後のツリーから消えている")
            checked.append(where)
        self.assertTrue(
            checked, "baseline にテストを宣言する seed シナリオが 1 件も無い（検出側の壊れ）")

    def test_every_seeded_scenario_materialises_all_of_its_declared_paths(self):
        # 実体化できなかったパスは baseline が実体と食い違い、編集ゼロの裏取りが
        # 成立しなくなる。seed を持つシナリオは宣言を全て実体化できていること
        checked = []
        for skill, scenario in self._seeded():
            where = f"{skill}/{scenario['id']}"
            with tempfile.TemporaryDirectory() as dest:
                result = fixture_setup.materialize(
                    scenario, dest, base_time=1_750_000_000)
            self.assertEqual(
                result["unmaterialized"], [],
                f"{where}: 宣言したパスが実体化されていない")
            checked.append(where)
        self.assertTrue(checked, "commits を宣言するシナリオが 1 件も無い（検出側の壊れ）")


class TestMaterializeRejectsBrokenDeclarations(unittest.TestCase):
    """検証を通さない CLI 経路から呼ばれても、壊れた宣言は MaterializeError で落ちること。

    生の KeyError / AttributeError は呼び出し側の捕捉から漏れるうえ、宣言の
    どこが壊れているかを伝えない。
    """

    def _materialize(self, setup):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        return fixture_setup.materialize({"id": "s", "setup": setup}, temp.name)

    def test_a_seeded_commit_without_a_message_is_reported(self):
        with self.assertRaises(fixture_setup.MaterializeError):
            self._materialize({
                "files": {"a.md": "x"},
                "git": {"init": True, "commit": True, "commits": [{"files": {"b.py": "y"}}]}})

    def test_a_seeded_commit_that_is_not_an_object_is_reported(self):
        with self.assertRaises(fixture_setup.MaterializeError):
            self._materialize(
                {"git": {"init": True, "commit": True, "commits": ["feat: b"]}})

    def test_non_string_file_content_is_reported(self):
        with self.assertRaises(fixture_setup.MaterializeError):
            self._materialize({"files": {"a.md": 42}})

    def test_a_path_escaping_the_isolated_area_is_reported(self):
        with self.assertRaises(fixture_setup.MaterializeError):
            self._materialize({"files": {"../outside.md": "x"}})

    def test_a_seeded_commit_writing_under_the_git_directory_is_reported(self):
        with self.assertRaises(fixture_setup.MaterializeError):
            self._materialize({
                "files": {"a.md": "x"},
                "git": {"init": True, "commit": True,
                        "commits": [{"files": {".git/hooks/pre-commit": "#!/bin/sh\n"},
                                     "message": "feat: hook"}]}})

    def test_a_broken_mtimes_declaration_is_reported_before_anything_is_written(self):
        # 宣言の正規化は書き込みの前に済ませる規則。壊れた宣言のまま書き始めると、
        # 隔離領域に「宣言のどれでもない」中途半端な状態が残る
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        with self.assertRaises(fixture_setup.MaterializeError):
            fixture_setup.materialize(
                {"id": "s", "setup": {"files": {"a.md": "x"},
                                      "mtimes": {"a.md": "1h"}}},
                temp.name)
        self.assertFalse(os.path.exists(os.path.join(temp.name, "a.md")))

    def test_a_seeded_commit_whose_add_is_refused_is_reported(self):
        # add が一部のパスを拒否しても、残りが staged なら commit は成功する。
        # 黙って通すと「seed したつもりの実装が履歴に無い」状態で対象 phase に入る。
        # 無視設定が後続の seed コミットで入る形は、setup.files['.gitignore'] しか
        # 読まない静的検査では捕まらないので、実体化側で止めるほかない
        with self.assertRaises(fixture_setup.MaterializeError):
            self._materialize({
                "files": {"a.md": "x"},
                "git": {"init": True, "commit": True,
                        "commits": [
                            {"files": {".gitignore": "/build/\n"},
                             "message": "chore: build を無視する"},
                            {"files": {"app.py": "x\n", "build/out.py": "y\n"},
                             "message": "feat: app"}]}})

    def test_a_baseline_add_whose_paths_are_refused_is_reported(self):
        # 配列形の baseline も同じ扱いにする。ここで通すと baseline は
        # --allow-empty の空コミットになり、宣言したファイルが 1 つも
        # 追跡されていないのに commit 済みとして先へ進む
        with self.assertRaises(fixture_setup.MaterializeError):
            self._materialize({
                "files": {".gitignore": "/build/\n", "build/out.py": "y\n"},
                "git": {"init": True, "commit": ["build/out.py"]}})


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

    def test_it_ignores_an_inherited_config_injection(self):
        # GIT_CONFIG_COUNT 系は「環境変数で渡す git config」そのもので、
        # 引き継ぐと宣言していない設定が実体化に効く。ここでは呼び出し元の
        # 除外規則が baseline から宣言済みファイルを外していないことを見る
        with tempfile.TemporaryDirectory() as root:
            excludes = os.path.join(root, "excludes")
            with open(excludes, "w", encoding="utf-8") as handle:
                handle.write("a.txt\n")
            dest = os.path.join(root, "area")
            with mock.patch.dict(os.environ, {
                    "GIT_CONFIG_COUNT": "1",
                    "GIT_CONFIG_KEY_0": "core.excludesFile",
                    "GIT_CONFIG_VALUE_0": excludes}):
                fixture_setup.materialize(self.SCENARIO, dest)
            tracked = subprocess.run(
                ["git", "ls-files"], cwd=dest, capture_output=True, text=True,
                env=dict(os.environ, **fixture_setup._GIT_ENV))
            self.assertIn("a.txt", tracked.stdout)

    def test_it_ignores_an_inherited_template_directory(self):
        # GIT_TEMPLATE_DIR を引き継ぐと、呼び出し元の hook が実体化した
        # リポジトリへ複製され、隔離領域の中で他人のスクリプトが走る
        with tempfile.TemporaryDirectory() as root:
            template = os.path.join(root, "template")
            os.makedirs(os.path.join(template, "hooks"))
            with open(os.path.join(template, "hooks", "pre-commit"),
                      "w", encoding="utf-8") as handle:
                handle.write("#!/bin/sh\nexit 1\n")
            dest = os.path.join(root, "area")
            with mock.patch.dict(os.environ, {"GIT_TEMPLATE_DIR": template}):
                fixture_setup.materialize(self.SCENARIO, dest)
            self.assertFalse(
                os.path.exists(os.path.join(dest, ".git", "hooks", "pre-commit")))


class TestValidateExercises(unittest.TestCase):
    """`exercises` は「このシナリオが踏む挙動面ファイル」の完全主張。

    宣言が誤っていると台帳側は「踏まないから再走不要」と読んで持ち越す。
    形の検査（配列・リポジトリ相対・skills/ 配下）はここで閉じ、面に実在するか
    どうかは面を知っている ledger 側が判定する。
    """

    def test_valid_exercises_passes(self):
        f = _fixture(exercises=["skills/shared/references/tdd-contract.md"])
        self.assertEqual(fixture_setup.validate(f), [])

    def test_empty_list_is_a_valid_declaration(self):
        # 空配列 = 「SKILL.md 以外は踏まない」という主張。宣言なしとは別物
        self.assertEqual(fixture_setup.validate(_fixture(exercises=[])), [])

    def test_non_list_is_reported(self):
        self.assertTrue(any(
            "exercises" in e for e in
            fixture_setup.validate(_fixture(exercises="skills/a/SKILL.md"))))

    def test_non_string_element_is_reported(self):
        self.assertTrue(any(
            "exercises" in e
            for e in fixture_setup.validate(_fixture(exercises=[1]))))

    def test_absolute_path_is_reported(self):
        self.assertTrue(any(
            "リポジトリ相対" in e for e in
            fixture_setup.validate(_fixture(exercises=["/etc/passwd"]))))

    def test_parent_traversal_is_reported(self):
        self.assertTrue(any(
            "リポジトリ相対" in e for e in
            fixture_setup.validate(_fixture(exercises=["skills/../../secret"]))))

    def test_path_outside_skills_is_reported(self):
        self.assertTrue(any(
            "skills/" in e for e in
            fixture_setup.validate(_fixture(exercises=["README.md"]))))


class TestScenarioSha256(unittest.TestCase):
    """シナリオ内容ハッシュの正本。`exercises` はハッシュ対象から外す。

    exercises は影響メタデータであってシナリオの挙動定義ではない。含めると
    宣言を足しただけで rerun ガードが再構築を要求し、台帳も差分ありと読む
    （= 宣言の導入コストが実走 1 本ぶんになる）。
    """

    def test_is_stable_hex_digest(self):
        scenario = _fixture()["scenarios"][0]
        sha = fixture_setup.scenario_sha256(scenario)
        self.assertEqual(len(sha), 64)
        self.assertEqual(sha, fixture_setup.scenario_sha256(scenario))

    def test_adding_exercises_does_not_change_the_sha(self):
        base = _fixture()["scenarios"][0]
        declared = dict(base, exercises=["skills/shared/references/tdd-contract.md"])
        self.assertEqual(fixture_setup.scenario_sha256(base),
                         fixture_setup.scenario_sha256(declared))

    def test_changing_exercises_does_not_change_the_sha(self):
        base = _fixture()["scenarios"][0]
        one = dict(base, exercises=["skills/a/x.md"])
        two = dict(base, exercises=["skills/a/y.md", "skills/a/z.md"])
        self.assertEqual(fixture_setup.scenario_sha256(one),
                         fixture_setup.scenario_sha256(two))

    def test_changing_the_prompt_changes_the_sha(self):
        base = _fixture()["scenarios"][0]
        self.assertNotEqual(
            fixture_setup.scenario_sha256(base),
            fixture_setup.scenario_sha256(dict(base, prompt="別の指示")))

    def test_changing_requirements_changes_the_sha(self):
        base = _fixture()["scenarios"][0]
        changed = dict(base, requirements=[{"text": "別の要件", "critical": True}])
        self.assertNotEqual(fixture_setup.scenario_sha256(base),
                            fixture_setup.scenario_sha256(changed))


if __name__ == "__main__":
    unittest.main()
