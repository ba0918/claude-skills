"""semantic_diff.py の unittest。

判定入力の組み立ては git 履歴に触る唯一の経路なので、一時 git repo を作って
「複数コミット遡って変更前を復元できるか」「復元できないとき事前充填で
unaffected 判定への道を塞げるか」を実際の履歴で確かめる。
"""
import hashlib
import json
import os
import subprocess
import tempfile
import unittest

import ledger
import semantic_diff


def _write(root, rel, content=""):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def _git(root, *args):
    subprocess.run(["git", "-C", root] + list(args), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _init_repo(root):
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "test")
    _git(root, "config", "commit.gpgsign", "false")


def _commit(root, message):
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", message)


def _sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class _RepoHarness(unittest.TestCase):
    """スキル a（3 シナリオ）と共有契約 2 本を持つ git repo。"""

    FIXTURE = {
        "skill": "a",
        "scenarios": [
            {"id": "a-001", "prompt": "one",
             "exercises": ["skills/shared/references/tdd.md"]},
            {"id": "a-002", "prompt": "two",
             "exercises": ["skills/shared/references/gate.md"]},
            {"id": "a-003", "prompt": "three",
             "exercises": ["skills/shared/references/tdd.md"]},
        ],
    }

    # リンク行は構造トークンなので、prose-change を作るには地の文だけを動かす
    LINKS = ("see [tdd](../shared/references/tdd.md) and "
             "[gate](../shared/references/gate.md)\n")

    def _repo(self, root):
        _init_repo(root)
        _write(root, "skills/skill-regression/SKILL.md", "self")
        _write(root, "skills/shared/references/tdd.md", "tdd contract v1\n")
        _write(root, "skills/shared/references/gate.md", "gate contract v1\n")
        _write(root, "skills/a/SKILL.md",
               self.LINKS + "This line is plain prose.\n")
        _write(root, "skills/a/fixtures.json",
               json.dumps(self.FIXTURE, ensure_ascii=False))
        _commit(root, "v1")

    def _verified(self, root):
        """今の面で検証済みの台帳エントリを作り、コミットする。"""
        surface = ledger.skill_surface(root, "a")
        entry = ledger.make_entry(root, surface, "pass", "2026-08-01")
        entry["scenarios"] = ledger.full_scenarios_record(
            root, "a", "pass", "2026-08-01")
        ledger.save(root, {"a": entry})
        _commit(root, "ledger")
        return entry

    def _run(self, argv):
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = semantic_diff.main(argv)
        return rc, buf.getvalue()


class TestRestoreBase(_RepoHarness):
    """台帳が記録した内容ハッシュと一致する版を git 履歴から探す。

    コミット位置（「前回検証の頃のコミット」）から逆算しないのは、台帳が
    検証イベントを**内容**で記録していてコミットと紐づいていないため。
    位置から逆算すると、検証後に別経路で履歴が進んだ場合に誤った base を掴む。
    """

    def test_it_restores_a_base_from_several_commits_back(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            recorded = _sha256("tdd contract v1\n")
            for version in ("v2", "v3"):
                _write(root, "skills/shared/references/tdd.md",
                       f"tdd contract {version}\n")
                _commit(root, version)
            _write(root, "skills/shared/references/tdd.md", "tdd contract v4\n")
            self.assertEqual(
                semantic_diff.restore_base(
                    root, "skills/shared/references/tdd.md", recorded),
                "tdd contract v1\n")

    def test_it_returns_none_when_no_revision_matches(self):
        # 台帳の記録がどのコミットにも無い内容（未コミットのまま検証した等）
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self.assertIsNone(semantic_diff.restore_base(
                root, "skills/shared/references/tdd.md", "0" * 64))

    def test_a_file_absent_from_the_previous_surface_has_no_base(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self.assertIsNone(semantic_diff.restore_base(
                root, "skills/shared/references/tdd.md", ledger._MISSING))

    def test_it_returns_none_outside_a_git_repository(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "a.md", "x")
            self.assertIsNone(
                semantic_diff.restore_base(root, "a.md", _sha256("x")))


class TestBuildInput(_RepoHarness):
    """判定入力（diff 本文 + 正準ハッシュ + skeleton）の組み立て。"""

    def _changed(self, root, text="tdd contract v2\n"):
        _write(root, "skills/shared/references/tdd.md", text)

    def test_the_diff_sha256_matches_the_ledger_pure_function(self):
        # 発行側と検証側が同じ値へ到達しないと、正しい判定が常に拒否される
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            entry = self._verified(root)
            self._changed(root)
            built = semantic_diff.build_input(root, "a", entry)
            surface = ledger.skill_surface(root, "a")
            self.assertEqual(
                built["diff_sha256"],
                ledger.semantic_diff_sha256(
                    entry["file_sha256"], ledger.file_hashes(root, surface)))

    def test_the_diff_body_shows_the_change(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            entry = self._verified(root)
            self._changed(root)
            body = semantic_diff.build_input(root, "a", entry)["diff"]
            self.assertIn("skills/shared/references/tdd.md", body)
            self.assertIn("-tdd contract v1", body)
            self.assertIn("+tdd contract v2", body)

    def test_it_names_only_the_impacted_scenarios(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            entry = self._verified(root)
            self._changed(root)
            built = semantic_diff.build_input(root, "a", entry)
            self.assertEqual(sorted(built["skeleton"]["scenarios"]),
                             ["a-001", "a-003"])

    def test_the_skeleton_leaves_the_verdict_blank_for_the_judge(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            entry = self._verified(root)
            self._changed(root)
            skeleton = semantic_diff.build_input(root, "a", entry)["skeleton"]
            self.assertEqual(skeleton["skill"], "a")
            self.assertEqual(skeleton["model"], "")
            self.assertEqual(skeleton["scenarios"]["a-001"]["verdict"], "")

    def test_an_unfilled_skeleton_is_not_a_valid_judgment(self):
        # skeleton をそのまま台帳へ渡しても通らない（空欄は 3 値ではない）
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            entry = self._verified(root)
            self._changed(root)
            built = semantic_diff.build_input(root, "a", entry)
            surface = ledger.skill_surface(root, "a")
            reason = ledger.validate_judgment(
                built["skeleton"], "a", entry["file_sha256"],
                ledger.file_hashes(root, surface),
                ledger.CalibrationGate(entries={}, corpus_sha256="x"))
            self.assertIsNotNone(reason)

    def test_an_added_file_diffs_against_an_empty_base(self):
        # 前回の面に無かったファイルは「復元不能」ではない（変更前が存在しない）
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            entry = self._verified(root)
            _write(root, "skills/a/extra.md", "brand new\n")
            _write(root, "skills/a/SKILL.md",
                   self.LINKS + "and [extra](extra.md)\n")
            built = semantic_diff.build_input(root, "a", entry)
            self.assertEqual(built["unrestorable"], [])
            self.assertIn("+brand new", built["diff"])

    def test_a_deleted_file_diffs_against_an_empty_current(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            entry = self._verified(root)
            os.remove(os.path.join(root, "skills/shared/references/gate.md"))
            built = semantic_diff.build_input(root, "a", entry)
            self.assertEqual(built["unrestorable"], [])
            self.assertIn("-gate contract v1", built["diff"])


class TestUnrestorableBase(_RepoHarness):
    """変更前を復元できない差分は、判定の余地なく unclear を事前充填する。

    diff を見せられないまま unaffected と言える経路を残すと、判定器の権限が
    「見ていないものを安全と宣言する」まで広がってしまう。
    """

    def _unrestorable(self, root, entry):
        # 台帳の記録がどのコミットにも無い内容を指す状態を作る
        entry["file_sha256"]["skills/shared/references/tdd.md"] = "0" * 64
        _write(root, "skills/shared/references/tdd.md", "tdd contract v2\n")
        return entry

    def test_it_reports_the_unrestorable_file(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            entry = self._unrestorable(root, self._verified(root))
            built = semantic_diff.build_input(root, "a", entry)
            self.assertEqual(built["unrestorable"],
                             ["skills/shared/references/tdd.md"])

    def test_the_affected_scenarios_are_prefilled_with_unclear(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            entry = self._unrestorable(root, self._verified(root))
            skeleton = semantic_diff.build_input(root, "a", entry)["skeleton"]
            for sid in ("a-001", "a-003"):
                self.assertEqual(skeleton["scenarios"][sid]["verdict"],
                                 "unclear")
                self.assertIn("復元", skeleton["scenarios"][sid]["rationale"])

    def test_a_prefilled_scenario_is_already_a_valid_judgment_entry(self):
        # 事前充填はそのまま提出できる完成した判定（空欄を埋め忘れた形にしない）
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            entry = self._unrestorable(root, self._verified(root))
            skeleton = semantic_diff.build_input(root, "a", entry)["skeleton"]
            skeleton["scenarios"] = {
                "a-001": skeleton["scenarios"]["a-001"]}
            skeleton["model"] = "m"
            surface = ledger.skill_surface(root, "a")
            reason = ledger.validate_judgment(
                skeleton, "a", entry["file_sha256"],
                ledger.file_hashes(root, surface),
                ledger.CalibrationGate(
                    entries={"m": {"must_flag_fn": 0, "corpus_sha256": "c"}},
                    corpus_sha256="c"))
            self.assertIsNone(reason)

    def test_the_diff_body_states_that_the_base_is_missing(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            entry = self._unrestorable(root, self._verified(root))
            body = semantic_diff.build_input(root, "a", entry)["diff"]
            self.assertIn("復元", body)
            # 復元できていない内容を「追加された行」として見せない
            self.assertNotIn("+tdd contract v2", body)


class TestScopeGuard(_RepoHarness):
    """判定器が引き受けるのは contract-change の帯だけ（A6）。"""

    def test_it_refuses_a_prose_only_change_naming_the_cheaper_route(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            _write(root, "skills/a/SKILL.md",
                   self.LINKS + "This line is plain prose, reworded.\n")
            rc, out = self._run(["a", root])
            self.assertEqual(rc, 1)
            self.assertIn("--accept", out)

    def test_it_refuses_when_there_is_no_difference(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            rc, out = self._run(["a", root])
            self.assertEqual(rc, 1)
            self.assertIn("差分", out)

    def test_it_refuses_a_skill_with_no_ledger_entry(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            rc, out = self._run(["a", root])
            self.assertEqual(rc, 1)
            self.assertIn("a", out)


class TestCli(_RepoHarness):
    """CLI は判定入力を標準出力へ出し、skeleton をファイルにも書ける。"""

    def test_it_prints_the_hash_the_diff_and_the_skeleton(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            _write(root, "skills/shared/references/tdd.md",
                   "tdd contract `v2`\n")
            rc, out = self._run(["a", root])
            self.assertEqual(rc, 0)
            self.assertIn("diff_sha256", out)
            self.assertIn("-tdd contract v1", out)
            self.assertIn('"scenarios"', out)

    def test_the_skeleton_option_writes_a_loadable_file(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            _write(root, "skills/shared/references/tdd.md",
                   "tdd contract `v2`\n")
            out_path = os.path.join(root, "judgment.json")
            rc, _ = self._run(["a", "--skeleton", out_path, root])
            self.assertEqual(rc, 0)
            with open(out_path, encoding="utf-8") as f:
                skeleton = json.load(f)
            self.assertEqual(skeleton["skill"], "a")
            self.assertEqual(sorted(skeleton["scenarios"]), ["a-001", "a-003"])

    def test_it_refuses_a_skeleton_option_without_a_value(self):
        rc, out = self._run(["a", "--skeleton"])
        self.assertEqual(rc, 2)
        self.assertIn("--skeleton", out)

    def test_it_refuses_without_a_skill_name(self):
        rc, _ = self._run([])
        self.assertEqual(rc, 2)


class TestGitIsInvokedSafely(unittest.TestCase):
    """git 呼び出しは引数リスト渡しに限る（shell を経由させない）。"""

    def test_no_shell_invocation_in_the_source(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "semantic_diff.py")
        with open(path, encoding="utf-8") as f:
            source = f.read()
        for forbidden in ("shell=True", "os.system", "os.popen"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
