"""ledger.py の unittest。

挙動面フィンガープリントの決定性と、台帳照合（stale / unverified / orphan）
の純関数を検証する。日付は DI（引数渡し）でテスト可能にする。
"""
import os
import tempfile
import unittest

import ledger


def _write(root, rel, content=""):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


class TestFingerprint(unittest.TestCase):
    def test_deterministic(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "a.md", "hello")
            _write(root, "b.md", "world")
            fp1 = ledger.fingerprint(root, ["a.md", "b.md"])
            fp2 = ledger.fingerprint(root, ["b.md", "a.md"])  # 順序非依存
            self.assertEqual(fp1, fp2)
            self.assertEqual(len(fp1), 64)

    def test_changes_when_content_changes(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "a.md", "hello")
            fp1 = ledger.fingerprint(root, ["a.md"])
            _write(root, "a.md", "hello!")
            self.assertNotEqual(fp1, ledger.fingerprint(root, ["a.md"]))

    def test_missing_file_is_distinct_from_empty(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "a.md", "")
            fp_empty = ledger.fingerprint(root, ["a.md"])
            os.remove(os.path.join(root, "a.md"))
            self.assertNotEqual(fp_empty, ledger.fingerprint(root, ["a.md"]))


class TestStaleSeverity(unittest.TestCase):
    """stale の重さを {path: hash} 2 つの比較だけで機械分類する純関数。

    「参照リンクが 1 本増えただけ」と「契約の挙動定義が書き換わった」を同じ stale と
    して扱うと、軽量承認と人間判断の承認が台帳上で区別できなくなる。
    """

    def test_addition_only_is_contract_addition(self):
        recorded = {"a.md": "h1"}
        current = {"a.md": "h1", "b.md": "h2"}
        severity, changed = ledger.stale_severity(recorded, current)
        self.assertEqual(severity, ledger.SEVERITY_ADDITION)
        self.assertEqual(changed, ["b.md"])

    def test_modified_file_is_contract_change(self):
        recorded = {"a.md": "h1"}
        current = {"a.md": "h1-CHANGED"}
        severity, changed = ledger.stale_severity(recorded, current)
        self.assertEqual(severity, ledger.SEVERITY_CHANGE)
        self.assertEqual(changed, ["a.md"])

    def test_removed_file_is_contract_change(self):
        recorded = {"a.md": "h1", "b.md": "h2"}
        current = {"a.md": "h1"}
        severity, changed = ledger.stale_severity(recorded, current)
        self.assertEqual(severity, ledger.SEVERITY_CHANGE)
        self.assertEqual(changed, ["b.md"])

    def test_file_turned_missing_is_contract_change(self):
        # 面には残っているが実体が消えた（MISSING 番兵）ケースも削除として扱う
        recorded = {"a.md": "h1"}
        current = {"a.md": ledger._MISSING}
        severity, _ = ledger.stale_severity(recorded, current)
        self.assertEqual(severity, ledger.SEVERITY_CHANGE)

    def test_file_recovered_from_missing_is_contract_change(self):
        # 消えていたファイルが復活した = 面の内容が前回検証時と別物になった
        recorded = {"a.md": ledger._MISSING}
        current = {"a.md": "h1"}
        severity, changed = ledger.stale_severity(recorded, current)
        self.assertEqual(severity, ledger.SEVERITY_CHANGE)
        self.assertEqual(changed, ["a.md"])

    def test_mixed_addition_and_change_is_contract_change(self):
        # fail-safe: 変更が 1 つでも混ざったら addition 側に倒さない
        recorded = {"a.md": "h1"}
        current = {"a.md": "h1-CHANGED", "b.md": "h2"}
        severity, changed = ledger.stale_severity(recorded, current)
        self.assertEqual(severity, ledger.SEVERITY_CHANGE)
        self.assertEqual(changed, ["a.md", "b.md"])

    def test_added_but_nonexistent_file_is_contract_change(self):
        # 実体のない参照先が面に入った = 壊れたリンク。安全側の contract-change へ
        recorded = {"a.md": "h1"}
        current = {"a.md": "h1", "b.md": ledger._MISSING}
        severity, _ = ledger.stale_severity(recorded, current)
        self.assertEqual(severity, ledger.SEVERITY_CHANGE)

    def test_no_difference_has_no_severity(self):
        severity, changed = ledger.stale_severity({"a.md": "h1"}, {"a.md": "h1"})
        self.assertIsNone(severity)
        self.assertEqual(changed, [])

    def test_missing_baseline_is_contract_change(self):
        # file_sha256 を持たない旧エントリ。差分は形式上「追加のみ」に見えるが、
        # 比較基準が無い以上「追加だけ」と断じる根拠も無い
        severity, changed = ledger.stale_severity({}, {"a.md": "h1"})
        self.assertEqual(severity, ledger.SEVERITY_CHANGE)
        self.assertEqual(changed, ["a.md"])


class TestCheck(unittest.TestCase):
    """check() は (kind, skill, detail) のタプル一覧を返す。空 = 合格。"""

    def _repo(self, root):
        _write(root, "skills/a/SKILL.md", "body")
        _write(root, "skills/a/fixtures.json", '{"skill": "a", "scenarios": []}')
        _write(root, "skills/b/SKILL.md", "body")  # fixtures なし = 対象外

    def test_ok_when_ledger_matches(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            surface = ledger.skill_surface(root, "a")
            entries = {"a": ledger.make_entry(root, surface, "pass", "2026-07-07")}
            self.assertEqual(ledger.check(root, entries), [])

    def test_unverified_when_fixtures_exist_without_entry(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            issues = ledger.check(root, {})
            self.assertEqual([i[0] for i in issues], ["unverified"])
            self.assertEqual(issues[0][1], "a")

    def test_stale_when_surface_changed(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            surface = ledger.skill_surface(root, "a")
            entries = {"a": ledger.make_entry(root, surface, "pass", "2026-07-07")}
            _write(root, "skills/a/SKILL.md", "body CHANGED")
            issues = ledger.check(root, entries)
            self.assertEqual([i[0] for i in issues], ["stale"])
            self.assertIn("skills/a/SKILL.md", issues[0][2])  # 変更ファイルを提示

    def test_stale_detail_labels_content_change_as_contract_change(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            surface = ledger.skill_surface(root, "a")
            entries = {"a": ledger.make_entry(root, surface, "pass", "2026-07-07")}
            _write(root, "skills/a/SKILL.md", "body CHANGED")
            issues = ledger.check(root, entries)
            self.assertEqual([i[0] for i in issues], ["stale"])  # kind は不変
            self.assertTrue(issues[0][2].startswith("[contract-change]"))

    def test_stale_detail_labels_surface_growth_as_contract_addition(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            surface = ledger.skill_surface(root, "a")
            entries = {"a": ledger.make_entry(root, surface, "pass", "2026-07-07")}
            _write(root, "skills/a/extra.md", "new reference")
            issues = ledger.check(root, entries)
            self.assertEqual([i[0] for i in issues], ["stale"])
            self.assertTrue(issues[0][2].startswith("[contract-addition]"))
            self.assertIn("skills/a/extra.md", issues[0][2])

    def test_legacy_entry_without_hashes_is_labeled_contract_change(self):
        """--check の表示と --accept の記録値が同じ規則で動く（食い違わせない）。"""
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            entries = {"a": {"surface": [], "result": "pass",
                             "verified": "2026-07-07"}}
            issues = ledger.check(root, entries)
            self.assertEqual([i[0] for i in issues], ["stale"])
            self.assertTrue(issues[0][2].startswith("[contract-change]"))

    def test_orphan_when_fixtures_removed(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            surface = ledger.skill_surface(root, "a")
            entries = {"a": ledger.make_entry(root, surface, "pass", "2026-07-07")}
            os.remove(os.path.join(root, "skills/a/fixtures.json"))
            issues = ledger.check(root, entries)
            self.assertEqual([i[0] for i in issues], ["orphan"])

    def test_skill_without_fixtures_is_ignored(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            os.remove(os.path.join(root, "skills/a/fixtures.json"))
            self.assertEqual(ledger.check(root, {}), [])

    def test_check_output_shows_result_breakdown(self):
        """--check 合格時の出力に pass / accepted-without-run の内訳が含まれる。"""
        import io
        import contextlib
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            _write(root, "skills/skill-regression/SKILL.md", "self")
            surface = ledger.skill_surface(root, "a")
            entries = {"a": ledger.make_entry(root, surface, "pass", "2026-07-01")}
            ledger.save(root, entries)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = ledger.main(["--check", root])
            self.assertEqual(rc, 0)
            output = buf.getvalue()
            self.assertIn("pass 1", output)
            self.assertIn("accepted-without-run 0", output)

    def test_check_output_counts_accepted_addition_separately(self):
        """機械確認済みの承認が accepted-without-run に混ざって数えられない。"""
        import io
        import contextlib
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            _write(root, "skills/skill-regression/SKILL.md", "self")
            _write(root, "skills/c/SKILL.md", "body")
            _write(root, "skills/c/fixtures.json", '{"skill": "c"}')
            entries = {
                "a": ledger.make_entry(
                    root, ledger.skill_surface(root, "a"),
                    "accepted-addition", "2026-08-03"),
                "c": ledger.make_entry(
                    root, ledger.skill_surface(root, "c"),
                    "accepted-without-run", "2026-08-03"),
            }
            ledger.save(root, entries)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = ledger.main(["--check", root])
            self.assertEqual(rc, 0)
            output = buf.getvalue()
            self.assertIn("accepted-addition 1", output)
            self.assertIn("accepted-without-run 1", output)
            self.assertIn("pass 0", output)


class TestAcceptGuard(unittest.TestCase):
    """--accept は fixtures.json が変わっていたら拒否する。"""

    def _repo(self, root):
        _write(root, "skills/a/SKILL.md", "body")
        _write(root, "skills/a/fixtures.json",
               '{"skill": "a", "scenarios": []}')

    def test_accept_allowed_when_fixtures_unchanged(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            surface = ledger.skill_surface(root, "a")
            entries = {"a": ledger.make_entry(root, surface, "pass", "2026-07-01")}
            _write(root, "skills/a/SKILL.md", "body CHANGED")
            fixtures_rel = "skills/a/fixtures.json"
            prev_hash = entries["a"]["file_sha256"].get(fixtures_rel)
            curr_hash = ledger._file_sha256(root, fixtures_rel)
            self.assertEqual(prev_hash, curr_hash)

    def test_accept_blocked_when_fixtures_changed(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            surface = ledger.skill_surface(root, "a")
            entries = {"a": ledger.make_entry(root, surface, "pass", "2026-07-01")}
            _write(root, "skills/a/fixtures.json",
                   '{"skill": "a", "scenarios": [{"id": "new"}]}')
            fixtures_rel = "skills/a/fixtures.json"
            prev_hash = entries["a"]["file_sha256"].get(fixtures_rel)
            curr_hash = ledger._file_sha256(root, fixtures_rel)
            self.assertNotEqual(prev_hash, curr_hash)

    def test_accept_allowed_for_new_skill(self):
        """台帳に前回エントリがないスキルへの初回 --accept は許可する。"""
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            fixtures_rel = "skills/a/fixtures.json"
            entries = {}
            prev = entries.get("a", {}).get("file_sha256", {})
            prev_hash = prev.get(fixtures_rel)
            self.assertIsNone(prev_hash)

    def test_accept_cli_rejects_when_fixtures_changed(self):
        """CLI 経由で --accept が拒否されることの統合テスト。"""
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            _write(root, "skills/skill-regression/SKILL.md", "self")
            surface = ledger.skill_surface(root, "a")
            entries = {"a": ledger.make_entry(root, surface, "pass", "2026-07-01")}
            ledger.save(root, entries)
            _write(root, "skills/a/fixtures.json",
                   '{"skill": "a", "scenarios": [{"id": "changed"}]}')
            rc = ledger.main(["--update", "a", "--accept", root])
            self.assertEqual(rc, 1)
            reloaded = ledger.load(root)
            self.assertEqual(reloaded["a"]["result"], "pass")

    def test_accept_cli_passes_when_fixtures_unchanged(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            _write(root, "skills/skill-regression/SKILL.md", "self")
            surface = ledger.skill_surface(root, "a")
            entries = {"a": ledger.make_entry(root, surface, "pass", "2026-07-01")}
            ledger.save(root, entries)
            _write(root, "skills/a/SKILL.md", "body CHANGED")
            rc = ledger.main([
                "--update", "a", "--accept",
                "--note", "prose-only change", root,
            ])
            self.assertEqual(rc, 0)
            reloaded = ledger.load(root)
            self.assertEqual(reloaded["a"]["result"], "accepted-without-run")


class TestAcceptResultClassification(unittest.TestCase):
    """--accept の記録値は操作者が選ぶのではなく severity から自動で決まる。

    自己申告だと「軽い変更だった」という主張が台帳に残るだけで裏が取れない。
    hash 比較で addition-only と確認できた承認だけを別の値で記録する。
    """

    def _repo(self, root):
        _write(root, "skills/skill-regression/SKILL.md", "self")
        _write(root, "skills/a/SKILL.md", "body")
        _write(root, "skills/a/fixtures.json", '{"skill": "a", "scenarios": []}')

    def _verified(self, root):
        surface = ledger.skill_surface(root, "a")
        ledger.save(root, {
            "a": ledger.make_entry(root, surface, "pass", "2026-07-01"),
        })

    def test_addition_only_accept_is_recorded_as_accepted_addition(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            _write(root, "skills/a/extra.md", "new reference")
            rc = ledger.main(["--update", "a", "--accept", root])
            self.assertEqual(rc, 0)
            self.assertEqual(ledger.load(root)["a"]["result"], "accepted-addition")

    def test_content_change_accept_stays_accepted_without_run(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            _write(root, "skills/a/SKILL.md", "body CHANGED")
            rc = ledger.main(["--update", "a", "--accept", root])
            self.assertEqual(rc, 0)
            self.assertEqual(
                ledger.load(root)["a"]["result"], "accepted-without-run")

    def test_first_accept_without_prior_entry_is_accepted_without_run(self):
        # 比較基準がない以上 addition と断じる根拠もない
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            rc = ledger.main(["--update", "a", "--accept", root])
            self.assertEqual(rc, 0)
            self.assertEqual(
                ledger.load(root)["a"]["result"], "accepted-without-run")

    def test_accept_with_no_surface_change_is_accepted_without_run(self):
        # 何も追加していない承認が accepted-addition を名乗るのは意味論的に嘘
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            rc = ledger.main(["--update", "a", "--accept", root])
            self.assertEqual(rc, 0)
            self.assertEqual(
                ledger.load(root)["a"]["result"], "accepted-without-run")

    def test_update_without_accept_stays_pass(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            _write(root, "skills/a/extra.md", "new reference")
            rc = ledger.main(["--update", "a", root])
            self.assertEqual(rc, 0)
            self.assertEqual(ledger.load(root)["a"]["result"], "pass")


class TestEntryRoundtrip(unittest.TestCase):
    def test_entry_records_result_and_date(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/a/SKILL.md", "body")
            _write(root, "skills/a/fixtures.json", "{}")
            surface = ledger.skill_surface(root, "a")
            entry = ledger.make_entry(
                root, surface, "accepted-without-run", "2026-07-07")
            self.assertEqual(entry["result"], "accepted-without-run")
            self.assertEqual(entry["verified"], "2026-07-07")
            self.assertEqual(entry["surface"], surface)

    def test_note_is_recorded_when_given(self):
        # 素の pass だけでは「同じ環境で次に回す者」に run の性質が伝わらない
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/a/SKILL.md", "body")
            _write(root, "skills/a/fixtures.json", "{}")
            surface = ledger.skill_surface(root, "a")
            entry = ledger.make_entry(
                root, surface, "pass", "2026-07-25", note="状況照会 4 回")
            self.assertEqual(entry["note"], "状況照会 4 回")

    def test_note_key_is_absent_when_not_given(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/a/SKILL.md", "body")
            _write(root, "skills/a/fixtures.json", "{}")
            entry = ledger.make_entry(
                root, ledger.skill_surface(root, "a"), "pass", "2026-07-25")
            self.assertNotIn("note", entry)

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/skill-regression/SKILL.md", "self")
            entries = {"a": {"surface": [], "surface_sha256": "x",
                             "result": "pass", "verified": "2026-07-07"}}
            ledger.save(root, entries)
            self.assertEqual(ledger.load(root), entries)


class TestCoverage(unittest.TestCase):
    """fixture 保有率の計上。--check は opt-in ゲートなので母数を別に数える。"""

    EXEMPT = {"legacy": "一回限りの移行スキル"}

    def _repo(self, root, skills):
        for name, has_fixtures in skills.items():
            _write(root, f"skills/{name}/SKILL.md", "body")
            if has_fixtures:
                _write(root, f"skills/{name}/fixtures.json", "{}")

    def test_counts_covered_exempt_and_uncovered(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root, {"a": True, "b": False, "legacy": False})
            cov = ledger.coverage(root, exempt=self.EXEMPT)
            self.assertEqual(cov["covered"], ["a"])
            self.assertEqual(cov["uncovered"], ["b"])
            self.assertEqual(list(cov["exempt"]), ["legacy"])
            self.assertEqual(cov["total"], 3)

    def test_exempt_reason_is_carried(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root, {"legacy": False})
            cov = ledger.coverage(root, exempt=self.EXEMPT)
            self.assertEqual(cov["exempt"]["legacy"], "一回限りの移行スキル")

    def test_exempt_skill_that_gained_fixtures_counts_as_covered(self):
        # 免除リストの取り残しで実測済みスキルが未計上にならないこと
        with tempfile.TemporaryDirectory() as root:
            self._repo(root, {"legacy": True})
            cov = ledger.coverage(root, exempt=self.EXEMPT)
            self.assertEqual(cov["covered"], ["legacy"])
            self.assertEqual(cov["exempt"], {})

    def test_directory_without_skill_md_is_not_counted(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root, {"a": True})
            os.makedirs(os.path.join(root, "skills", "not-a-skill"))
            self.assertEqual(ledger.coverage(root, exempt={})["total"], 1)

    def test_shipped_exempt_list_has_reasons(self):
        # 理由なしの免除は「黙って計上から外す」ことと同じ
        for skill, reason in ledger.COVERAGE_EXEMPT.items():
            self.assertTrue(reason.strip(), f"理由が空: {skill}")


if __name__ == "__main__":
    unittest.main()
