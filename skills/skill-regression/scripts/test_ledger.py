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

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/skill-regression/SKILL.md", "self")
            entries = {"a": {"surface": [], "surface_sha256": "x",
                             "result": "pass", "verified": "2026-07-07"}}
            ledger.save(root, entries)
            self.assertEqual(ledger.load(root), entries)


if __name__ == "__main__":
    unittest.main()
