"""dep_graph.py の unittest。

スキル → 依存クロージャ（挙動面 = スキル配下ファイル + 参照 md の推移閉包）の
算出と、変更ファイル → 影響スキルの逆引きを検証する。
"""
import os
import tempfile
import unittest

import dep_graph


def _write(root, rel, content=""):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def _repo(root):
    """最小のテストリポジトリ: スキル a / b が共有契約を参照する。"""
    _write(root, "skills/a/SKILL.md",
           "[gate](../shared/references/gate.md) [own](references/own.md)")
    _write(root, "skills/a/references/own.md", "own ref")
    _write(root, "skills/a/references/unlinked.md", "リンクされてないが挙動面")
    _write(root, "skills/a/scripts/helper.py", "print('x')")
    _write(root, "skills/a/scripts/test_helper.py", "# test")
    _write(root, "skills/a/scripts/__pycache__/helper.cpython-312.pyc", "bin")
    _write(root, "skills/b/SKILL.md", "[gate](../shared/references/gate.md)")
    _write(root, "skills/c/SKILL.md", "no links")
    _write(root, "skills/shared/references/gate.md", "contract")


class TestBehaviorSurface(unittest.TestCase):
    def test_includes_skill_dir_files_and_linked_contracts(self):
        with tempfile.TemporaryDirectory() as root:
            _repo(root)
            surface = dep_graph.behavior_surface(root, "a")
            self.assertIn("skills/a/SKILL.md", surface)
            self.assertIn("skills/a/references/own.md", surface)
            self.assertIn("skills/a/references/unlinked.md", surface)
            self.assertIn("skills/a/scripts/helper.py", surface)
            self.assertIn("skills/shared/references/gate.md", surface)

    def test_excludes_tests_and_pycache(self):
        with tempfile.TemporaryDirectory() as root:
            _repo(root)
            surface = dep_graph.behavior_surface(root, "a")
            self.assertNotIn("skills/a/scripts/test_helper.py", surface)
            self.assertTrue(
                all("__pycache__" not in p for p in surface), surface)

    def test_sorted_and_deduped(self):
        with tempfile.TemporaryDirectory() as root:
            _repo(root)
            surface = dep_graph.behavior_surface(root, "a")
            self.assertEqual(surface, sorted(set(surface)))

    def test_excludes_regression_ledger_itself(self):
        """台帳は検証の記録であって挙動ではない。挙動面に含めると
        「--update で台帳が変わる → 自分の挙動面が変わる → また stale」の
        自己参照ループになるため必ず除外する。"""
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/skill-regression/SKILL.md", "self")
            _write(root, "skills/skill-regression/ledger.json", "{}")
            surface = dep_graph.behavior_surface(root, "skill-regression")
            self.assertIn("skills/skill-regression/SKILL.md", surface)
            self.assertNotIn("skills/skill-regression/ledger.json", surface)

    def test_does_not_traverse_out_of_external_files(self):
        # 共有契約から他スキルへの「関連」リンク 1 本で、実行経路の交わらない
        # スキルが同じ面に載る回帰（issue -> ... -> skill-regression）を防ぐ
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/a/SKILL.md",
                   "[gate](../shared/references/gate.md)")
            _write(root, "skills/shared/references/gate.md",
                   "関連: [pattern](pattern.md)")
            _write(root, "skills/shared/references/pattern.md",
                   "[unrelated](../../z/SKILL.md)")
            _write(root, "skills/z/SKILL.md", "無関係なスキル")
            surface = dep_graph.behavior_surface(root, "a")
            self.assertIn("skills/shared/references/gate.md", surface)
            self.assertNotIn("skills/shared/references/pattern.md", surface)
            self.assertNotIn("skills/z/SKILL.md", surface)

    def test_own_references_reach_their_direct_contracts(self):
        # スキル自身の references/ は起点なので、そこからの 1 ホップは面に入る
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/a/SKILL.md", "[own](references/own.md)")
            _write(root, "skills/a/references/own.md",
                   "[gate](../../shared/references/gate.md)")
            _write(root, "skills/shared/references/gate.md", "contract")
            self.assertIn(
                "skills/shared/references/gate.md",
                dep_graph.behavior_surface(root, "a"),
            )

    def test_bare_path_reference_in_prompt_is_a_dependency(self):
        # 委譲プロンプト内の契約は md リンクではなく素のパスで書かれる
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/a/SKILL.md",
                   "プロンプト: `skills/shared/references/tdd-contract.md` に従うこと")
            _write(root, "skills/shared/references/tdd-contract.md", "contract")
            self.assertIn(
                "skills/shared/references/tdd-contract.md",
                dep_graph.behavior_surface(root, "a"),
            )

    def test_runtime_artifact_paths_are_not_dependencies(self):
        # 実行時に書き換わる成果物を面に入れると恒久 stale になる
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/a/SKILL.md",
                   "`.agents/artifacts/status.md` を更新する")
            _write(root, ".agents/artifacts/status.md", "runtime")
            self.assertNotIn(
                ".agents/artifacts/status.md",
                dep_graph.behavior_surface(root, "a"),
            )

    def test_bare_path_py_reference_is_a_dependency(self):
        # SKILL.md 内で素パスとして書かれた共有スクリプト(.py)も挙動面に入る
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/a/SKILL.md",
                   "Run `python3 skills/shared/scripts/checkpoint.py classify`")
            _write(root, "skills/shared/scripts/checkpoint.py", "# script")
            self.assertIn(
                "skills/shared/scripts/checkpoint.py",
                dep_graph.behavior_surface(root, "a"),
            )

    def test_bare_path_sh_reference_is_a_dependency(self):
        # .sh スクリプトへの素パス参照も挙動面に入る
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/a/SKILL.md",
                   "Execute `skills/shared/scripts/run.sh`")
            _write(root, "skills/shared/scripts/run.sh", "#!/bin/sh")
            self.assertIn(
                "skills/shared/scripts/run.sh",
                dep_graph.behavior_surface(root, "a"),
            )

    def test_bare_path_test_py_is_excluded(self):
        # test_*.py は面に入れない
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/a/SKILL.md",
                   "See `skills/shared/scripts/test_checkpoint.py`")
            _write(root, "skills/shared/scripts/test_checkpoint.py", "# test")
            self.assertNotIn(
                "skills/shared/scripts/test_checkpoint.py",
                dep_graph.behavior_surface(root, "a"),
            )

    def test_shared_script_change_impacts_referencing_skill(self):
        # 共有スクリプトを参照するスキルは、そのスクリプトの変更で impact に入る
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/a/SKILL.md",
                   "`python3 skills/shared/scripts/checkpoint.py skeleton`")
            _write(root, "skills/shared/scripts/checkpoint.py", "# script")
            _write(root, "skills/b/SKILL.md", "no refs")
            graph = dep_graph.build_graph(root)
            skills, _ = dep_graph.impacted_skills(
                graph, ["skills/shared/scripts/checkpoint.py"], root)
            self.assertEqual(skills, ["a"])

    def test_bare_path_re_matches_py_paths(self):
        # _BARE_PATH_RE が .py パスを拾うことの直接テスト
        matches = dep_graph._BARE_PATH_RE.findall(
            "Run skills/shared/scripts/checkpoint.py to verify")
        self.assertIn("skills/shared/scripts/checkpoint.py", matches)

    def test_bare_path_re_matches_sh_paths(self):
        matches = dep_graph._BARE_PATH_RE.findall(
            "Execute scripts/run.sh for setup")
        self.assertIn("scripts/run.sh", matches)

    def test_bare_path_to_missing_file_is_ignored(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/a/SKILL.md", "skills/shared/references/nope.md")
            self.assertEqual(
                dep_graph.behavior_surface(root, "a"), ["skills/a/SKILL.md"])

    def test_python_import_of_shared_module_is_a_dependency(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/a/SKILL.md", "skill body")
            _write(root, "skills/a/scripts/run.py",
                   "import secret_detect  # noqa: E402\n")
            _write(root, "skills/shared/scripts/secret_detect.py", "# module")
            surface = dep_graph.behavior_surface(root, "a")
            self.assertIn("skills/shared/scripts/secret_detect.py", surface)

    def test_python_from_import_of_shared_module_is_a_dependency(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/a/SKILL.md", "skill body")
            _write(root, "skills/a/scripts/run.py",
                   "from frontmatter import parse_frontmatter_lines\n")
            _write(root, "skills/shared/scripts/frontmatter.py", "# module")
            surface = dep_graph.behavior_surface(root, "a")
            self.assertIn("skills/shared/scripts/frontmatter.py", surface)

    def test_python_import_alias_is_a_dependency(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/a/SKILL.md", "skill body")
            _write(root, "skills/a/scripts/run.py",
                   "import secret_detect as _sd  # noqa: E402\n")
            _write(root, "skills/shared/scripts/secret_detect.py", "# module")
            surface = dep_graph.behavior_surface(root, "a")
            self.assertIn("skills/shared/scripts/secret_detect.py", surface)

    def test_python_import_of_nonexistent_shared_module_is_ignored(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/a/SKILL.md", "skill body")
            _write(root, "skills/a/scripts/run.py", "import nonexistent\n")
            _write(root, "skills/shared/scripts/secret_detect.py", "# module")
            surface = dep_graph.behavior_surface(root, "a")
            self.assertNotIn("skills/shared/scripts/nonexistent.py", surface)

    def test_python_import_does_not_traverse_shared_module_imports(self):
        """共有モジュール間の import は辿らない（1 ホップ原則）。"""
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/a/SKILL.md", "skill body")
            _write(root, "skills/a/scripts/run.py",
                   "import checkpoint  # noqa: E402\n")
            _write(root, "skills/shared/scripts/checkpoint.py",
                   "from secret_detect import mask_secrets\n")
            _write(root, "skills/shared/scripts/secret_detect.py", "# module")
            surface = dep_graph.behavior_surface(root, "a")
            self.assertIn("skills/shared/scripts/checkpoint.py", surface)
            self.assertNotIn("skills/shared/scripts/secret_detect.py", surface)

    def test_python_import_in_test_file_is_ignored(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/a/SKILL.md", "skill body")
            _write(root, "skills/a/scripts/test_run.py",
                   "import secret_detect\n")
            _write(root, "skills/shared/scripts/secret_detect.py", "# module")
            surface = dep_graph.behavior_surface(root, "a")
            self.assertNotIn("skills/shared/scripts/secret_detect.py", surface)

    def test_shared_script_import_change_impacts_importing_skill(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/a/SKILL.md", "skill body")
            _write(root, "skills/a/scripts/run.py",
                   "import secret_detect  # noqa: E402\n")
            _write(root, "skills/shared/scripts/secret_detect.py", "# module")
            _write(root, "skills/b/SKILL.md", "no imports")
            graph = dep_graph.build_graph(root)
            skills, _ = dep_graph.impacted_skills(
                graph, ["skills/shared/scripts/secret_detect.py"], root)
            self.assertEqual(skills, ["a"])

    def test_missing_skill_returns_empty(self):
        with tempfile.TemporaryDirectory() as root:
            _repo(root)
            self.assertEqual(dep_graph.behavior_surface(root, "nope"), [])


class TestBuildGraph(unittest.TestCase):
    def test_maps_every_skill_except_shared(self):
        with tempfile.TemporaryDirectory() as root:
            _repo(root)
            graph = dep_graph.build_graph(root)
            self.assertEqual(sorted(graph), ["a", "b", "c"])

    def test_shared_contract_appears_in_both_dependents(self):
        with tempfile.TemporaryDirectory() as root:
            _repo(root)
            graph = dep_graph.build_graph(root)
            for skill in ("a", "b"):
                self.assertIn("skills/shared/references/gate.md", graph[skill])
            self.assertNotIn("skills/shared/references/gate.md", graph["c"])


class TestImpactedSkills(unittest.TestCase):
    def test_shared_contract_change_impacts_all_dependents(self):
        with tempfile.TemporaryDirectory() as root:
            _repo(root)
            graph = dep_graph.build_graph(root)
            skills, unresolved = dep_graph.impacted_skills(
                graph, ["skills/shared/references/gate.md"], root)
            self.assertEqual(skills, ["a", "b"])
            self.assertEqual(unresolved, [])

    def test_own_file_change_impacts_only_owner(self):
        with tempfile.TemporaryDirectory() as root:
            _repo(root)
            graph = dep_graph.build_graph(root)
            skills, unresolved = dep_graph.impacted_skills(
                graph, ["skills/a/references/unlinked.md"], root)
            self.assertEqual(skills, ["a"])
            self.assertEqual(unresolved, [])

    def test_unrelated_change_impacts_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            _repo(root)
            graph = dep_graph.build_graph(root)
            skills, unresolved = dep_graph.impacted_skills(
                graph, ["README.md"], root)
            self.assertEqual(skills, [])
            self.assertEqual(unresolved, [])


class TestPathNormalization(unittest.TestCase):
    """#139: パス表記の違いで impacted_skills の結果が変わらないことを検証。"""

    def test_dot_slash_prefix(self):
        with tempfile.TemporaryDirectory() as root:
            _repo(root)
            graph = dep_graph.build_graph(root)
            skills, unresolved = dep_graph.impacted_skills(
                graph, ["./skills/a/SKILL.md"], root)
            self.assertEqual(skills, ["a"])
            self.assertEqual(unresolved, [])

    def test_absolute_path(self):
        with tempfile.TemporaryDirectory() as root:
            _repo(root)
            graph = dep_graph.build_graph(root)
            abs_path = os.path.join(root, "skills/a/SKILL.md")
            skills, unresolved = dep_graph.impacted_skills(
                graph, [abs_path], root)
            self.assertEqual(skills, ["a"])
            self.assertEqual(unresolved, [])

    def test_non_normalized_path(self):
        with tempfile.TemporaryDirectory() as root:
            _repo(root)
            graph = dep_graph.build_graph(root)
            skills, unresolved = dep_graph.impacted_skills(
                graph, ["skills/a/../a/SKILL.md"], root)
            self.assertEqual(skills, ["a"])
            self.assertEqual(unresolved, [])

    def test_path_outside_root_is_unresolved(self):
        with tempfile.TemporaryDirectory() as root:
            _repo(root)
            graph = dep_graph.build_graph(root)
            skills, unresolved = dep_graph.impacted_skills(
                graph, ["/completely/outside/path.md"], root)
            self.assertEqual(skills, [])
            self.assertEqual(unresolved, ["/completely/outside/path.md"])

    def test_nonexistent_relative_path_resolves(self):
        """存在しないが正規化可能な相対パスは影響なし（解決不能ではない）。"""
        with tempfile.TemporaryDirectory() as root:
            _repo(root)
            graph = dep_graph.build_graph(root)
            skills, unresolved = dep_graph.impacted_skills(
                graph, ["skills/nope/SKILL.md"], root)
            self.assertEqual(skills, [])
            self.assertEqual(unresolved, [])

    def test_all_variants_return_same_result(self):
        """issue #139 の再現テスト: 同一ファイルの表記違いがすべて同じ結果を返す。"""
        with tempfile.TemporaryDirectory() as root:
            _repo(root)
            graph = dep_graph.build_graph(root)
            variants = [
                "skills/a/SKILL.md",
                "./skills/a/SKILL.md",
                os.path.join(root, "skills/a/SKILL.md"),
                "skills/a/../a/SKILL.md",
            ]
            for v in variants:
                skills, _ = dep_graph.impacted_skills(graph, [v], root)
                self.assertEqual(skills, ["a"], f"Failed for variant: {v}")


if __name__ == "__main__":
    unittest.main()
