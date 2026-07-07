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
            self.assertEqual(
                dep_graph.impacted_skills(
                    graph, ["skills/shared/references/gate.md"]),
                ["a", "b"],
            )

    def test_own_file_change_impacts_only_owner(self):
        with tempfile.TemporaryDirectory() as root:
            _repo(root)
            graph = dep_graph.build_graph(root)
            self.assertEqual(
                dep_graph.impacted_skills(
                    graph, ["skills/a/references/unlinked.md"]),
                ["a"],
            )

    def test_unrelated_change_impacts_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            _repo(root)
            graph = dep_graph.build_graph(root)
            self.assertEqual(
                dep_graph.impacted_skills(graph, ["README.md"]), [])


if __name__ == "__main__":
    unittest.main()
