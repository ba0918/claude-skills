"""ledger.py の unittest。

挙動面フィンガープリントの決定性と、台帳照合（stale / unverified / orphan）
の純関数を検証する。日付は DI（引数渡し）でテスト可能にする。
"""
import datetime
import json
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


class TestStaleSeverityProse(unittest.TestCase):
    """散文のみ変更（prose-change）の機械分類。

    file hash は不一致でも構造フィンガープリントが一致すれば、変わったのは
    散文だけ。判定材料が欠けるケースはすべて contract-change（重い側）へ倒す。
    """

    def test_prose_only_modification_is_prose_change(self):
        severity, changed = ledger.stale_severity(
            {"a.md": "h1"}, {"a.md": "h2"},
            recorded_struct={"a.md": "s1"}, current_struct={"a.md": "s1"})
        self.assertEqual(severity, ledger.SEVERITY_PROSE)
        self.assertEqual(changed, ["a.md"])

    def test_structural_mismatch_is_contract_change(self):
        severity, _ = ledger.stale_severity(
            {"a.md": "h1"}, {"a.md": "h2"},
            recorded_struct={"a.md": "s1"}, current_struct={"a.md": "s2"})
        self.assertEqual(severity, ledger.SEVERITY_CHANGE)

    def test_legacy_entry_without_struct_record_is_contract_change(self):
        # structural_sha256 を持たない旧エントリ。散文のみと断じる基準が無い
        severity, _ = ledger.stale_severity(
            {"a.md": "h1"}, {"a.md": "h2"},
            recorded_struct={}, current_struct={"a.md": "s1"})
        self.assertEqual(severity, ledger.SEVERITY_CHANGE)

    def test_non_md_modification_is_contract_change(self):
        # 非 md には散文の概念が無い。構造記録の対象外 = 常に重い側
        severity, _ = ledger.stale_severity(
            {"a.py": "h1"}, {"a.py": "h2"},
            recorded_struct={}, current_struct={})
        self.assertEqual(severity, ledger.SEVERITY_CHANGE)

    def test_prose_with_removed_file_is_contract_change(self):
        severity, _ = ledger.stale_severity(
            {"a.md": "h1", "b.md": "h2"}, {"a.md": "h1b"},
            recorded_struct={"a.md": "s1", "b.md": "s2"},
            current_struct={"a.md": "s1"})
        self.assertEqual(severity, ledger.SEVERITY_CHANGE)

    def test_prose_with_own_addition_stays_prose_change(self):
        severity, changed = ledger.stale_severity(
            {"skills/a/SKILL.md": "h1"},
            {"skills/a/SKILL.md": "h2", "skills/a/new.md": "h3"},
            recorded_struct={"skills/a/SKILL.md": "s1"},
            current_struct={"skills/a/SKILL.md": "s1", "skills/a/new.md": "s3"},
            own_prefix="skills/a/")
        self.assertEqual(severity, ledger.SEVERITY_PROSE)
        self.assertEqual(changed, ["skills/a/SKILL.md", "skills/a/new.md"])

    def test_prose_with_foreign_addition_is_contract_change(self):
        severity, _ = ledger.stale_severity(
            {"skills/a/SKILL.md": "h1"},
            {"skills/a/SKILL.md": "h2", "skills/shared/c.md": "h3"},
            recorded_struct={"skills/a/SKILL.md": "s1"},
            current_struct={"skills/a/SKILL.md": "s1", "skills/shared/c.md": "s3"},
            own_prefix="skills/a/")
        self.assertEqual(severity, ledger.SEVERITY_CHANGE)


class TestStaleSeverityForeignAddition(unittest.TestCase):
    """第 3 fail-safe: 自スキル外のファイルが面へ追加されたら addition と呼ばない。

    素パス参照の実体が後から作られて面へ入るケースは未検証の新規内容であり、
    「直前に実走で確かめた内容から増えただけ」という addition の意味論を満たさない
    （#182 で Why not 見送り → #222 で導入）。
    """

    def test_foreign_addition_is_contract_change(self):
        severity, _ = ledger.stale_severity(
            {"skills/a/SKILL.md": "h1"},
            {"skills/a/SKILL.md": "h1", "skills/shared/c.md": "h2"},
            own_prefix="skills/a/")
        self.assertEqual(severity, ledger.SEVERITY_CHANGE)

    def test_own_addition_is_still_contract_addition(self):
        severity, _ = ledger.stale_severity(
            {"skills/a/SKILL.md": "h1"},
            {"skills/a/SKILL.md": "h1", "skills/a/new.md": "h2"},
            own_prefix="skills/a/")
        self.assertEqual(severity, ledger.SEVERITY_ADDITION)

    def test_without_own_prefix_addition_is_unrestricted(self):
        # 後方互換: own_prefix 省略時は従来どおり出所を検査しない
        severity, _ = ledger.stale_severity(
            {"skills/a/SKILL.md": "h1"},
            {"skills/a/SKILL.md": "h1", "skills/shared/c.md": "h2"})
        self.assertEqual(severity, ledger.SEVERITY_ADDITION)


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
            _write(root, "skills/a/SKILL.md", "run `changed-command` now")
            issues = ledger.check(root, entries)
            self.assertEqual([i[0] for i in issues], ["stale"])  # kind は不変
            self.assertTrue(issues[0][2].startswith("[contract-change]"))

    def test_stale_detail_labels_prose_only_change_as_prose_change(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            surface = ledger.skill_surface(root, "a")
            entries = {"a": ledger.make_entry(root, surface, "pass", "2026-07-07")}
            _write(root, "skills/a/SKILL.md", "body reworded, no tokens touched")
            issues = ledger.check(root, entries)
            self.assertEqual([i[0] for i in issues], ["stale"])  # kind は不変
            self.assertTrue(issues[0][2].startswith("[prose-change]"))

    def test_legacy_entry_without_struct_record_never_labels_prose(self):
        # structural_sha256 の無い旧エントリは散文変更でも contract-change 表示
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            surface = ledger.skill_surface(root, "a")
            entry = ledger.make_entry(root, surface, "pass", "2026-07-07")
            del entry["structural_sha256"]
            _write(root, "skills/a/SKILL.md", "body reworded, no tokens touched")
            issues = ledger.check(root, {"a": entry})
            self.assertTrue(issues[0][2].startswith("[contract-change]"))

    def test_check_treats_foreign_surface_growth_as_contract_change(self):
        # check() が own_prefix を配線していることの統合確認。recorded に無い
        # 自スキル外ファイルが面へ現れたら addition ではなく重い側で報告する
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            _write(root, "skills/shared/refs/c.md", "shared contract")
            _write(root, "skills/a/SKILL.md", "see [c](../shared/refs/c.md)")
            surface = ledger.skill_surface(root, "a")
            entry = ledger.make_entry(root, surface, "pass", "2026-07-07")
            entry["file_sha256"].pop("skills/shared/refs/c.md", None)
            issues = ledger.check(root, {"a": entry})
            self.assertEqual([i[0] for i in issues], ["stale"])
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

    def test_check_output_counts_accepted_prose_separately(self):
        """散文承認も内訳に別建てで出す（accepted-without-run に畳まない）。"""
        import io
        import contextlib
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            _write(root, "skills/skill-regression/SKILL.md", "self")
            entries = {
                "a": ledger.make_entry(
                    root, ledger.skill_surface(root, "a"),
                    "accepted-prose", "2026-08-03"),
            }
            ledger.save(root, entries)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = ledger.main(["--check", root])
            self.assertEqual(rc, 0)
            self.assertIn("accepted-prose 1", buf.getvalue())


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
            _write(root, "skills/a/SKILL.md", "run `changed-command` now")
            rc = ledger.main([
                "--update", "a", "--accept",
                "--note", "reviewed by hand", root,
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
            _write(root, "skills/a/SKILL.md", "run `changed-command` now")
            rc = ledger.main(["--update", "a", "--accept", root])
            self.assertEqual(rc, 0)
            self.assertEqual(
                ledger.load(root)["a"]["result"], "accepted-without-run")

    def test_prose_only_accept_on_pass_baseline_is_accepted_prose(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            _write(root, "skills/a/SKILL.md", "body reworded, no tokens touched")
            rc = ledger.main(["--update", "a", "--accept", root])
            self.assertEqual(rc, 0)
            self.assertEqual(ledger.load(root)["a"]["result"], "accepted-prose")

    def test_prose_only_accept_on_unrun_baseline_stays_accepted_without_run(self):
        """accepted-prose も実走 pass の上でだけ成立する（accepted-addition と同条件）。

        実走していない台帳の上に散文承認を積めると、一度も実走しないまま
        「機械確認済み」の見た目で Red flag の計上から逃げ続けられる。
        """
        for baseline in ("accepted-without-run", "accepted-addition",
                         "accepted-prose"):
            with self.subTest(baseline=baseline), \
                    tempfile.TemporaryDirectory() as root:
                self._repo(root)
                ledger.save(root, {
                    "a": ledger.make_entry(
                        root, ledger.skill_surface(root, "a"),
                        baseline, "2026-07-01"),
                })
                _write(root, "skills/a/SKILL.md",
                       "body reworded, no tokens touched")
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

    def test_addition_on_an_unrun_baseline_stays_accepted_without_run(self):
        """accepted-addition を名乗れるのは実走 pass の上に積んだ追加だけ。

        実走していない台帳の上に addition-only の accept を重ねると、実走証拠が
        1 度も無いまま Red flag の accepted-without-run 計上から恒久的に逃げられる。
        """
        for baseline in ("accepted-without-run", "accepted-addition"):
            with self.subTest(baseline=baseline), tempfile.TemporaryDirectory() as root:
                self._repo(root)
                ledger.save(root, {
                    "a": ledger.make_entry(
                        root, ledger.skill_surface(root, "a"), baseline, "2026-07-01"),
                })
                _write(root, "skills/a/extra.md", "new reference")
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

    def test_entry_records_structural_hashes_for_md_only(self):
        # 散文のみ判定の比較基準。md だけが対象（非 md に散文の概念は無い）
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/a/SKILL.md", "body")
            _write(root, "skills/a/fixtures.json", "{}")
            _write(root, "skills/a/helper.py", "x = 1")
            surface = ledger.skill_surface(root, "a")
            entry = ledger.make_entry(root, surface, "pass", "2026-08-03")
            self.assertIn("skills/a/SKILL.md", entry["structural_sha256"])
            self.assertNotIn("skills/a/fixtures.json", entry["structural_sha256"])
            self.assertNotIn("skills/a/helper.py", entry["structural_sha256"])

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/skill-regression/SKILL.md", "self")
            entries = {"a": {"surface": [], "surface_sha256": "x",
                             "result": "pass", "verified": "2026-07-07"}}
            ledger.save(root, entries)
            self.assertEqual(ledger.load(root), entries)


class TestImpactedScenarios(unittest.TestCase):
    """変更ファイル → 影響シナリオ。判定規則はすべて安全側優先。

    再走単位をスキルからシナリオへ細分化する中核。宣言を持たないシナリオが
    従来どおり全変更で再走される（後方互換 = 安全側）ことが土台になる。
    """

    SKILL = "a"
    SURFACE = [
        "skills/a/SKILL.md",
        "skills/a/fixtures.json",
        "skills/shared/references/tdd.md",
        "skills/shared/references/gate.md",
    ]

    def _scenarios(self):
        return [
            {"id": "a-001", "prompt": "one",
             "exercises": ["skills/shared/references/tdd.md"]},
            {"id": "a-002", "prompt": "two",
             "exercises": ["skills/shared/references/gate.md"]},
            {"id": "a-003", "prompt": "three"},
        ]

    def _impacted(self, changed, scenarios=None, recorded=None):
        return ledger.impacted_scenarios(
            self.SKILL, self.SURFACE, scenarios or self._scenarios(),
            changed, recorded)

    def _recorded(self, scenarios=None):
        return {
            s["id"]: {"scenario_sha256": ledger.scenario_sha256(s),
                      "result": "pass", "verified": "2026-08-01"}
            for s in (scenarios or self._scenarios())
        }

    def test_no_change_impacts_nothing(self):
        self.assertEqual(self._impacted([]), [])

    def test_skill_md_change_impacts_every_scenario(self):
        # SKILL.md は全シナリオが必ず読む暗黙の依存
        self.assertEqual(self._impacted(["skills/a/SKILL.md"]),
                         ["a-001", "a-002", "a-003"])

    def test_declared_file_change_impacts_declarers_and_undeclared_only(self):
        self.assertEqual(self._impacted(["skills/shared/references/tdd.md"]),
                         ["a-001", "a-003"])

    def test_empty_declaration_is_a_claim_of_no_dependency(self):
        # 空配列 = 「SKILL.md 以外は踏まない」。宣言なし（安全側）とは別物
        scenarios = self._scenarios()
        scenarios[2]["exercises"] = []
        self.assertEqual(
            self._impacted(["skills/shared/references/tdd.md"], scenarios),
            ["a-001"])

    def test_a_declaration_off_the_surface_is_always_impacted(self):
        # typo・移動で面に無いパスを指した宣言は信用できない。安全側の常時再走へ
        scenarios = self._scenarios()
        scenarios[1]["exercises"] = ["skills/shared/references/typo.md"]
        self.assertEqual(
            self._impacted(["skills/shared/references/tdd.md"], scenarios),
            ["a-001", "a-002", "a-003"])

    def test_a_removed_surface_file_impacts_every_scenario(self):
        # 面から消えたファイルは現在の宣言と突き合わせようがない（安全側）
        self.assertEqual(self._impacted(["skills/shared/references/gone.md"]),
                         ["a-001", "a-002", "a-003"])

    def test_fixtures_change_impacts_only_scenarios_whose_content_moved(self):
        recorded = self._recorded()
        scenarios = self._scenarios()
        scenarios[1]["prompt"] = "two, but stricter"
        self.assertEqual(
            self._impacted(["skills/a/fixtures.json"], scenarios, recorded),
            ["a-002"])

    def test_adding_a_declaration_alone_impacts_nothing(self):
        # exercises は sha 対象外。宣言追加だけの fixtures.json 変更は再走ゼロ
        recorded = self._recorded()
        scenarios = self._scenarios()
        scenarios[2]["exercises"] = ["skills/shared/references/gate.md"]
        self.assertEqual(
            self._impacted(["skills/a/fixtures.json"], scenarios, recorded), [])

    def test_a_new_scenario_is_impacted(self):
        recorded = self._recorded()
        scenarios = self._scenarios() + [{"id": "a-004", "prompt": "four"}]
        self.assertEqual(
            self._impacted(["skills/a/fixtures.json"], scenarios, recorded),
            ["a-004"])

    def test_fixtures_change_without_per_scenario_record_impacts_all(self):
        # 突き合わせ基準の無い旧エントリ。差分と断じる根拠がない
        self.assertEqual(self._impacted(["skills/a/fixtures.json"]),
                         ["a-001", "a-002", "a-003"])


class TestImpactScenariosCli(unittest.TestCase):
    """`--impact-scenarios` は skill<TAB>scenario_id 行を出す。"""

    def _repo(self, root):
        _write(root, "skills/skill-regression/SKILL.md", "self")
        _write(root, "skills/shared/references/tdd.md", "contract")
        _write(root, "skills/shared/references/gate.md", "contract")
        _write(root, "skills/a/SKILL.md",
               "see [tdd](../shared/references/tdd.md) and "
               "[gate](../shared/references/gate.md)")
        fixture = {
            "skill": "a",
            "scenarios": [
                {"id": "a-001", "prompt": "one",
                 "exercises": ["skills/shared/references/tdd.md"]},
                {"id": "a-002", "prompt": "two",
                 "exercises": ["skills/shared/references/gate.md"]},
            ],
        }
        _write(root, "skills/a/fixtures.json",
               json.dumps(fixture, ensure_ascii=False))

    def _run(self, argv):
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = ledger.main(argv)
        return rc, buf.getvalue()

    def test_prints_only_the_scenarios_that_exercise_the_changed_file(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            rc, out = self._run([
                "--impact-scenarios", "skills/shared/references/tdd.md", root])
            self.assertEqual(rc, 0)
            self.assertEqual(out.strip(), "a\ta-001")

    def test_unaffected_change_prints_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            rc, out = self._run(["--impact-scenarios", "README.md", root])
            self.assertEqual(rc, 0)
            self.assertEqual(out.strip(), "")

    def test_a_file_deleted_from_the_surface_still_names_every_scenario(self):
        # 削除されたファイルは現在の依存グラフのどの面にも載らない。台帳が記録した
        # 前回の面から拾わないと、削除が「影響ゼロ」に見えて check() の
        # 「scenarios: all」と食い違う
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            surface = ledger.skill_surface(root, "a")
            ledger.save(root, {
                "a": ledger.make_entry(root, surface, "pass", "2026-08-01")})
            os.remove(os.path.join(root, "skills/shared/references/gate.md"))
            rc, out = self._run([
                "--impact-scenarios", "skills/shared/references/gate.md", root])
            self.assertEqual(rc, 0)
            self.assertEqual(out.strip().splitlines(), ["a\ta-001", "a\ta-002"])


class TestCheckShowsImpactedScenarios(unittest.TestCase):
    """stale 表示にシナリオ粒度の内訳を添える（合否判定は不変）。"""

    def _repo(self, root):
        _write(root, "skills/shared/references/tdd.md", "contract")
        _write(root, "skills/a/SKILL.md", "see [tdd](../shared/references/tdd.md)")
        fixture = {
            "skill": "a",
            "scenarios": [
                {"id": "a-001", "prompt": "one",
                 "exercises": ["skills/shared/references/tdd.md"]},
                {"id": "a-002", "prompt": "two", "exercises": []},
            ],
        }
        _write(root, "skills/a/fixtures.json",
               json.dumps(fixture, ensure_ascii=False))

    def test_stale_detail_names_the_impacted_scenarios(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            surface = ledger.skill_surface(root, "a")
            entries = {"a": ledger.make_entry(root, surface, "pass", "2026-08-01")}
            _write(root, "skills/shared/references/tdd.md", "contract `changed`")
            issues = ledger.check(root, entries)
            self.assertEqual([i[0] for i in issues], ["stale"])  # kind は不変
            self.assertIn("scenarios: a-001 (1/2)", issues[0][2])

    def test_zero_impact_is_shown_as_none(self):
        # 宣言追加だけの fixtures.json 変更。空文字を出すと「表示が壊れている」
        # のか「再走ゼロ」なのかが読み手に判別できない
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            surface = ledger.skill_surface(root, "a")
            entry = ledger.make_entry(root, surface, "pass", "2026-08-01")
            entry["scenarios"] = ledger.full_scenarios_record(
                root, "a", "pass", "2026-08-01")
            fixture = json.loads(
                open(os.path.join(root, "skills/a/fixtures.json")).read())
            fixture["scenarios"][1]["exercises"] = [
                "skills/shared/references/tdd.md"]
            _write(root, "skills/a/fixtures.json",
                   json.dumps(fixture, ensure_ascii=False))
            issues = ledger.check(root, {"a": entry})
            self.assertIn("scenarios: none (0/2)", issues[0][2])

    def test_full_impact_is_shown_as_all(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            surface = ledger.skill_surface(root, "a")
            entries = {"a": ledger.make_entry(root, surface, "pass", "2026-08-01")}
            _write(root, "skills/a/SKILL.md",
                   "see [tdd](../shared/references/tdd.md) `changed`")
            issues = ledger.check(root, entries)
            self.assertIn("scenarios: all (2/2)", issues[0][2])


class _PartialHarness(unittest.TestCase):
    """per-scenario 記録・持ち越し・部分更新の共通土台。"""

    FIXTURE = {
        "skill": "a",
        "scenarios": [
            {"id": "a-001", "prompt": "one",
             "exercises": ["skills/shared/references/tdd.md"]},
            {"id": "a-002", "prompt": "two",
             "exercises": ["skills/shared/references/gate.md"]},
            {"id": "a-003", "prompt": "three"},
        ],
    }

    def _write_fixture(self, root, fixture=None):
        _write(root, "skills/a/fixtures.json",
               json.dumps(fixture or self.FIXTURE, ensure_ascii=False))

    def _repo(self, root):
        _write(root, "skills/skill-regression/SKILL.md", "self")
        _write(root, "skills/shared/references/tdd.md", "tdd contract")
        _write(root, "skills/shared/references/gate.md", "gate contract")
        _write(root, "skills/a/SKILL.md",
               "see [tdd](../shared/references/tdd.md) and "
               "[gate](../shared/references/gate.md)")
        self._write_fixture(root)

    def _verified(self, root, result="pass", with_scenarios=True):
        surface = ledger.skill_surface(root, "a")
        entry = ledger.make_entry(root, surface, result, "2026-08-01")
        if with_scenarios:
            entry["scenarios"] = ledger.full_scenarios_record(
                root, "a", result, "2026-08-01")
        ledger.save(root, {"a": entry})
        return entry

    def _run(self, argv):
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = ledger.main(argv)
        return rc, buf.getvalue()


class TestScenarioRecords(_PartialHarness):
    """非 partial の --update も per-scenario 記録を書く（部分再走の土台）。"""

    def test_update_records_every_scenario(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            rc, _ = self._run(["--update", "a", root])
            self.assertEqual(rc, 0)
            recorded = ledger.load(root)["a"]["scenarios"]
            self.assertEqual(sorted(recorded), ["a-001", "a-002", "a-003"])
            self.assertEqual(recorded["a-001"]["result"], "pass")

    def test_recorded_sha_ignores_the_exercises_declaration(self):
        # 宣言追加だけの fixtures.json 変更が「シナリオが変わった」にならない
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._run(["--update", "a", root])
            before = ledger.load(root)["a"]["scenarios"]["a-003"]["scenario_sha256"]
            fixture = json.loads(json.dumps(self.FIXTURE))
            fixture["scenarios"][2]["exercises"] = ["skills/shared/references/gate.md"]
            self._write_fixture(root, fixture)
            after = ledger.scenario_sha256(fixture["scenarios"][2])
            self.assertEqual(before, after)


class TestCarryOver(_PartialHarness):
    """持ち越しの有効性は直前エントリとの帰納で決まる。"""

    def _reason(self, root, scenario_id, entry=None):
        entry = entry or ledger.load(root)["a"]
        surface = ledger.skill_surface(root, "a")
        scenario = next(s for s in ledger.load_scenarios(root, "a")
                        if s["id"] == scenario_id)
        return ledger.carryover_reason(
            "a", scenario, surface, entry.get("file_sha256", {}),
            ledger.file_hashes(root, surface), entry.get("scenarios"))

    def test_untouched_dependencies_carry_over(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            self.assertIsNone(self._reason(root, "a-001"))

    def test_a_changed_declared_dependency_blocks_carry_over(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            _write(root, "skills/shared/references/tdd.md", "tdd contract CHANGED")
            self.assertIsNotNone(self._reason(root, "a-001"))
            # 宣言していないシナリオの合格は影響を受けない
            self.assertIsNone(self._reason(root, "a-002"))

    def test_an_undeclared_scenario_never_carries_over_a_surface_change(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            _write(root, "skills/shared/references/gate.md", "gate contract CHANGED")
            self.assertIsNotNone(self._reason(root, "a-003"))

    def test_a_fixtures_edit_of_another_scenario_does_not_block(self):
        # fixtures.json はシナリオ内容ハッシュで見る。ファイルハッシュで見ると
        # 他シナリオの編集だけで全シナリオの持ち越しが壊れ、impact 規則と食い違う
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            fixture = json.loads(json.dumps(self.FIXTURE))
            fixture["scenarios"][1]["prompt"] = "two, but stricter"
            self._write_fixture(root, fixture)
            self.assertIsNone(self._reason(root, "a-001"))
            self.assertIsNotNone(self._reason(root, "a-002"))

    def test_a_dependency_recorded_as_missing_blocks_carry_over(self):
        # 前回検証時に実体が無かった参照（壊れたリンク）は帰納の土台にならない
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            entry = self._verified(root)
            entry["file_sha256"]["skills/shared/references/tdd.md"] = ledger._MISSING
            self.assertIsNotNone(self._reason(root, "a-001", entry))

    def test_an_entry_without_scenario_records_blocks_carry_over(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            entry = self._verified(root, with_scenarios=False)
            self.assertIsNotNone(self._reason(root, "a-001", entry))


class TestPartialUpdate(_PartialHarness):
    """`--update <skill> --partial` は実走分を記録し、残りを持ち越す。"""

    def test_all_carried_over_keeps_the_skill_level_pass(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            fixture = json.loads(json.dumps(self.FIXTURE))
            fixture["scenarios"][2]["exercises"] = ["skills/shared/references/gate.md"]
            self._write_fixture(root, fixture)
            rc, _ = self._run(["--update", "a", "--partial", root])
            self.assertEqual(rc, 0)
            entry = ledger.load(root)["a"]
            self.assertEqual(entry["result"], "pass")
            # 持ち越したシナリオは前回の検証日を保つ（実走した日ではない）
            self.assertEqual(entry["scenarios"]["a-001"]["verified"], "2026-08-01")

    def test_a_rerun_scenario_is_recorded_with_todays_date(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            _write(root, "skills/shared/references/tdd.md", "tdd contract CHANGED")
            # a-003 は宣言を持たないので、面のどの変更でも再走側（安全側）
            rc, _ = self._run([
                "--update", "a", "--partial",
                "--scenario", "a-001", "--scenario", "a-003", root])
            self.assertEqual(rc, 0)
            entry = ledger.load(root)["a"]
            self.assertEqual(entry["result"], "pass")
            self.assertNotEqual(entry["scenarios"]["a-001"]["verified"], "2026-08-01")
            self.assertEqual(entry["scenarios"]["a-002"]["verified"], "2026-08-01")

    def test_it_refuses_and_lists_the_scenarios_that_still_need_a_run(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            _write(root, "skills/shared/references/tdd.md", "tdd contract CHANGED")
            rc, out = self._run(["--update", "a", "--partial", root])
            self.assertEqual(rc, 1)
            self.assertIn("a-001", out)
            self.assertNotIn("a-002", out)
            # 拒否時に台帳は書き換わらない
            self.assertEqual(ledger.load(root)["a"]["verified"], "2026-08-01")

    def test_it_refuses_an_unknown_scenario_id(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            rc, out = self._run(
                ["--update", "a", "--partial", "--scenario", "a-999", root])
            self.assertEqual(rc, 1)
            self.assertIn("a-999", out)

    def test_it_refuses_to_combine_with_accept(self):
        # --accept は「実走せず承認」、--partial は「実走分を記録」。混ぜると
        # 台帳の result がどちらの意味なのか読めなくなる
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            rc, _ = self._run(["--update", "a", "--partial", "--accept", root])
            self.assertEqual(rc, 1)

    def test_a_carried_over_acceptance_does_not_become_a_pass(self):
        # 実走していないシナリオが混ざる限り skill レベルを pass と名乗らせない
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root, result="accepted-without-run")
            rc, _ = self._run(["--update", "a", "--partial", root])
            self.assertEqual(rc, 0)
            self.assertEqual(ledger.load(root)["a"]["result"],
                             "accepted-without-run")

    def test_a_new_scenario_must_be_run(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            fixture = json.loads(json.dumps(self.FIXTURE))
            fixture["scenarios"].append({"id": "a-004", "prompt": "four"})
            self._write_fixture(root, fixture)
            rc, out = self._run(["--update", "a", "--partial", root])
            self.assertEqual(rc, 1)
            self.assertIn("a-004", out)

    def test_a_file_leaving_the_surface_refuses_a_zero_run_partial(self):
        # 削除は影響規則では「全シナリオ再走」。持ち越し規則だけで判定すると、
        # 消えたファイルはどのシナリオの依存集合にも現れず全件が持ち越されてしまう
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            os.remove(os.path.join(root, "skills/shared/references/gate.md"))
            rc, out = self._run(["--update", "a", "--partial", root])
            self.assertEqual(rc, 1)
            for sid in ("a-001", "a-002", "a-003"):
                self.assertIn(sid, out)
            self.assertEqual(ledger.load(root)["a"]["verified"], "2026-08-01")

    def test_the_refusal_names_the_files_that_forced_the_rerun(self):
        # 原因ファイルを理由行に添えないと、何が再走を呼んだのかを見るのに
        # --impact-scenarios を別途叩き直すことになる
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            os.remove(os.path.join(root, "skills/shared/references/gate.md"))
            rc, out = self._run(["--update", "a", "--partial", root])
            self.assertEqual(rc, 1)
            self.assertIn("skills/shared/references/gate.md", out)


class TestNoteIsNeverSilentlyDiscarded(_PartialHarness):
    """エントリを作り直す更新が、前任の申し送りを黙って落とさない。

    note には実走証拠の性質（誰がどの経路を通ったか）が入る。持ち越しだけの
    更新でこれが消えると、台帳に残るのは記録の形だけで由来が読めなくなる。
    """

    def _verified_with_note(self, root, note):
        entry = self._verified(root)
        entry["note"] = note
        ledger.save(root, {"a": entry})

    def test_a_zero_run_partial_keeps_the_previous_note(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified_with_note(root, "初代: 実走 3 本 / 経路 B")
            rc, _ = self._run(["--update", "a", "--partial", root])
            self.assertEqual(rc, 0)
            self.assertEqual(ledger.load(root)["a"]["carried_note"],
                             "初代: 実走 3 本 / 経路 B")

    def test_a_new_note_does_not_erase_the_previous_one(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified_with_note(root, "初代: 実走 3 本 / 経路 B")
            rc, _ = self._run(
                ["--update", "a", "--partial", "--note", "二代目: 宣言追加のみ", root])
            self.assertEqual(rc, 0)
            entry = ledger.load(root)["a"]
            self.assertEqual(entry["note"], "二代目: 宣言追加のみ")
            self.assertEqual(entry["carried_note"], "初代: 実走 3 本 / 経路 B")

    def test_the_carried_note_survives_a_further_note_less_partial(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified_with_note(root, "初代: 実走 3 本 / 経路 B")
            self._run(["--update", "a", "--partial", root])
            rc, _ = self._run(["--update", "a", "--partial", root])
            self.assertEqual(rc, 0)
            self.assertEqual(ledger.load(root)["a"]["carried_note"],
                             "初代: 実走 3 本 / 経路 B")

    def test_only_the_most_recent_prior_note_is_kept(self):
        # 引き継ぎスロットは 1 つ。全世代を積むと台帳が伸び続ける
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified_with_note(root, "初代")
            self._run(["--update", "a", "--partial", "--note", "二代目", root])
            rc, _ = self._run(["--update", "a", "--partial", "--note", "三代目", root])
            self.assertEqual(rc, 0)
            entry = ledger.load(root)["a"]
            self.assertEqual(entry["note"], "三代目")
            self.assertEqual(entry["carried_note"], "二代目")
            self.assertNotIn("初代", json.dumps(entry, ensure_ascii=False))

    def test_an_accept_keeps_the_previous_note(self):
        # --partial だけが申し送りを守ると、定例の --accept 1 回で実走証拠が消える
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified_with_note(root, "初代: 実走 3 本 / 経路 B")
            _write(root, "skills/a/extra.md", "new reference")
            rc, _ = self._run(["--update", "a", "--accept", root])
            self.assertEqual(rc, 0)
            self.assertEqual(ledger.load(root)["a"]["carried_note"],
                             "初代: 実走 3 本 / 経路 B")

    def test_a_full_update_keeps_the_previous_note(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified_with_note(root, "初代: 実走 3 本 / 経路 B")
            rc, _ = self._run(["--update", "a", root])
            self.assertEqual(rc, 0)
            self.assertEqual(ledger.load(root)["a"]["carried_note"],
                             "初代: 実走 3 本 / 経路 B")

    def test_a_chain_of_accepts_keeps_the_most_recent_prior_note(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified_with_note(root, "初代")
            self._run(["--update", "a", "--accept", "--note", "二代目", root])
            rc, _ = self._run(["--update", "a", "--accept", root])
            self.assertEqual(rc, 0)
            entry = ledger.load(root)["a"]
            self.assertEqual(entry["carried_note"], "二代目")


class TestAcceptKeepsPerScenarioRunDates(_PartialHarness):
    """1 本も走らせていない --accept が per-scenario の検証日を塗り替えない。

    per-scenario の verified は「そのシナリオを最後に実走で確かめた日」で、
    partial-rerun.md は run の新しさをここから読めと指示している。承認が今日で
    上書きすると、実走記録と承認記録が日付から区別できなくなる。
    """

    def test_an_accept_keeps_the_dates_of_the_last_real_run(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            _write(root, "skills/a/extra.md", "new reference")
            rc, _ = self._run(["--update", "a", "--accept", root])
            self.assertEqual(rc, 0)
            entry = ledger.load(root)["a"]
            self.assertEqual(entry["result"], "accepted-addition")
            for sid in ("a-001", "a-002", "a-003"):
                # result は承認値へ倒す（partial-rerun.md の既存意味論）
                self.assertEqual(entry["scenarios"][sid]["result"],
                                 "accepted-addition")
                self.assertEqual(entry["scenarios"][sid]["verified"], "2026-08-01")

    def test_a_scenario_without_a_previous_record_falls_back_to_the_entry_date(self):
        # 旧エントリには per-scenario 記録が無い。実走日を知る材料が無いので
        # skill レベルの検証日まで落とす（今日を名乗らない）
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root, with_scenarios=False)
            _write(root, "skills/a/extra.md", "new reference")
            rc, _ = self._run(["--update", "a", "--accept", root])
            self.assertEqual(rc, 0)
            entry = ledger.load(root)["a"]
            self.assertEqual(entry["scenarios"]["a-001"]["verified"], "2026-08-01")

    def test_a_first_accept_without_any_previous_entry_stamps_today(self):
        # 前任がいない＝古い日付を捏造する材料が無い。today が唯一正直な値
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            rc, _ = self._run(["--update", "a", "--accept", root])
            self.assertEqual(rc, 0)
            entry = ledger.load(root)["a"]
            self.assertEqual(entry["scenarios"]["a-001"]["verified"],
                             datetime.date.today().isoformat())

    def test_a_full_run_update_still_stamps_today_on_every_scenario(self):
        # --accept でない --update は全シナリオを実走した記録なので日付は動く
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            rc, _ = self._run(["--update", "a", root])
            self.assertEqual(rc, 0)
            entry = ledger.load(root)["a"]
            today = datetime.date.today().isoformat()
            for sid in ("a-001", "a-002", "a-003"):
                self.assertEqual(entry["scenarios"][sid]["verified"], today)


class TestPartialUpdateAgreesWithTheImpactRule(_PartialHarness):
    """影響ありと報告したシナリオを、同じ状態の --partial が持ち越さない。

    影響規則（check / --impact-scenarios）と持ち越し規則が別々の材料で動くと、
    片方が「全 20 本を再走せよ」と言う状態で、もう片方が実走ゼロの更新を通す。
    """

    def _impacted(self, root):
        entry = ledger.load(root)["a"]
        surface = ledger.skill_surface(root, "a")
        _, changed = ledger.stale_severity(
            entry.get("file_sha256", {}), ledger.file_hashes(root, surface),
            entry.get("structural_sha256", {}),
            ledger.structural_hashes(root, surface),
            own_prefix="skills/a/")
        return set(ledger.impacted_scenarios(
            "a", surface, ledger.load_scenarios(root, "a"), changed,
            entry.get("scenarios")))

    def test_no_impacted_scenario_can_be_carried_over_after_a_deletion(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            os.remove(os.path.join(root, "skills/shared/references/gate.md"))
            impacted = self._impacted(root)
            self.assertTrue(impacted)
            for held_back in sorted(impacted):
                argv = ["--update", "a", "--partial"]
                for sid in sorted(impacted - {held_back}):
                    argv += ["--scenario", sid]
                rc, out = self._run(argv + [root])
                self.assertEqual(rc, 1, f"{held_back} が持ち越された")
                self.assertIn(held_back, out)


class TestSeedScenarios(_PartialHarness):
    """`--seed-scenarios` は移行用ワンショット。検証イベントではない。"""

    def test_it_fills_the_records_from_the_skill_level_entry(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root, with_scenarios=False)
            rc, _ = self._run(["--seed-scenarios", "a", root])
            self.assertEqual(rc, 0)
            entry = ledger.load(root)["a"]
            self.assertEqual(sorted(entry["scenarios"]), ["a-001", "a-002", "a-003"])
            self.assertEqual(entry["scenarios"]["a-002"]["result"], "pass")
            # 検証していないので検証日は動かさない
            self.assertEqual(entry["scenarios"]["a-002"]["verified"], "2026-08-01")
            self.assertEqual(entry["verified"], "2026-08-01")

    def test_it_refuses_a_stale_entry(self):
        # stale = 面が前回検証時と違う。「全シナリオ合格」の保証が今の面に無い
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root, with_scenarios=False)
            _write(root, "skills/shared/references/tdd.md", "tdd contract CHANGED")
            rc, out = self._run(["--seed-scenarios", "a", root])
            self.assertEqual(rc, 1)
            self.assertIn("stale", out)
            self.assertNotIn("scenarios", ledger.load(root)["a"])

    def test_it_refuses_when_records_already_exist(self):
        # 既存記録の上書きを許すと、実走していないシナリオ記録を skill レベルの
        # pass で塗り替えられる（承認の洗浄経路になる）
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            rc, _ = self._run(["--seed-scenarios", "a", root])
            self.assertEqual(rc, 1)

    def test_it_refuses_a_skill_with_no_entry(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            rc, _ = self._run(["--seed-scenarios", "a", root])
            self.assertEqual(rc, 1)


class TestLegacyEntriesKeepWorking(_PartialHarness):
    """scenarios キーを持たない旧エントリでも既存経路は現行どおり動く。"""

    def test_check_status_and_update_are_unaffected(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root, with_scenarios=False)
            self.assertEqual(ledger.check(root, ledger.load(root)), [])
            rc, out = self._run(["--status", root])
            self.assertEqual(rc, 0)
            self.assertIn("verified", out)
            rc, _ = self._run(["--update", "a", root])
            self.assertEqual(rc, 0)

    def test_accept_still_classifies_by_severity(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root, with_scenarios=False)
            _write(root, "skills/a/extra.md", "new reference")
            rc, _ = self._run(["--update", "a", "--accept", root])
            self.assertEqual(rc, 0)
            self.assertEqual(ledger.load(root)["a"]["result"], "accepted-addition")


class TestArgumentErrorsAreReported(_PartialHarness):
    """値を伴うオプションの欠落は traceback ではなく usage + exit 2 で返す。"""

    def test_scenario_without_a_value(self):
        rc, out = self._run(["--update", "a", "--partial", "--scenario"])
        self.assertEqual(rc, 2)
        self.assertIn("--scenario", out)

    def test_note_without_a_value(self):
        rc, out = self._run(["--update", "a", "--partial", "--note"])
        self.assertEqual(rc, 2)
        self.assertIn("--note", out)

    def test_update_without_a_skill(self):
        rc, out = self._run(["--update"])
        self.assertEqual(rc, 2)
        self.assertIn("--update", out)

    def test_seed_scenarios_without_a_skill(self):
        rc, out = self._run(["--seed-scenarios"])
        self.assertEqual(rc, 2)
        self.assertIn("--seed-scenarios", out)

    def test_impact_scenarios_without_any_changed_file(self):
        # 何も出力せず rc 0 だと「再走すべきシナリオが無い」と区別が付かず、
        # 呼び出し側の引数組み立てミスが影響ゼロに化ける
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            rc, _ = self._run(["--impact-scenarios", root])
            self.assertNotEqual(rc, 0)


class TestMisplacedOptionsAreRefused(_PartialHarness):
    """モード指定より前に書かれた既知オプションを黙って捨てない。

    位置依存で読むオプションは、置き場所を間違えると存在しなかったことになる。
    捨てられた --partial / --scenario は「全シナリオを実走して合格した」という
    偽の per-scenario 記録を台帳へ書き込み、以後の持ち越し帰納がその上に積まれる。
    """

    def test_partial_and_scenario_before_update_are_refused(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            rc, out = self._run([
                "--partial", "--scenario", "a-001", "--update", "a", root])
            self.assertEqual(rc, 2)
            self.assertIn("--partial", out)
            self.assertEqual(ledger.load(root)["a"]["verified"], "2026-08-01")

    def test_accept_before_update_is_refused(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            rc, out = self._run(["--accept", "--update", "a", root])
            self.assertEqual(rc, 2)
            self.assertIn("--accept", out)
            self.assertEqual(ledger.load(root)["a"]["verified"], "2026-08-01")

    def test_a_misplaced_flag_on_check_is_refused(self):
        # root の位置に `--partial` が居座ると、存在しない root の照合が
        # 「issue なし」として rc 0 で通る
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            rc, out = self._run(["--check", "--partial", root])
            self.assertEqual(rc, 2)
            self.assertIn("--partial", out)

    def test_a_correctly_ordered_invocation_still_works(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            rc, _ = self._run(["--update", "a", "--partial", root])
            self.assertEqual(rc, 0)

    def test_a_misplaced_flag_on_impact_scenarios_is_refused(self):
        # フラグ風トークンが「変更ファイル」として消費されると、誤配置が
        # 出力なし rc 0 =「再走対象なし」の顔になる
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            rc, out = self._run(["--impact-scenarios", "--partial", root])
            self.assertEqual(rc, 2)
            self.assertIn("--partial", out)


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


class TestCoverageTiers(unittest.TestCase):
    """static-only 階層。「まだ書いていない」と「意図的に static 検証へ留める」を
    台帳の上で区別する（#244）。"""

    STATIC_ONLY = {"analyzer": "read-only 分析。static 検証で担保"}

    def _repo(self, root, skills):
        for name, has_fixtures in skills.items():
            _write(root, f"skills/{name}/SKILL.md", "body")
            if has_fixtures:
                _write(root, f"skills/{name}/fixtures.json", "{}")

    def test_counts_static_only_separately_from_uncovered(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root, {"a": True, "analyzer": False, "b": False})
            cov = ledger.coverage(root, exempt={}, static_only=self.STATIC_ONLY)
            self.assertEqual(cov["covered"], ["a"])
            self.assertEqual(list(cov["static_only"]), ["analyzer"])
            self.assertEqual(cov["uncovered"], ["b"])

    def test_static_only_reason_is_carried(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root, {"analyzer": False})
            cov = ledger.coverage(root, exempt={}, static_only=self.STATIC_ONLY)
            self.assertEqual(cov["static_only"]["analyzer"],
                             "read-only 分析。static 検証で担保")

    def test_static_only_skill_that_gained_fixtures_counts_as_covered(self):
        # 宣言リストの取り残しで behavioral 昇格済みスキルが二重計上されないこと
        with tempfile.TemporaryDirectory() as root:
            self._repo(root, {"analyzer": True})
            cov = ledger.coverage(root, exempt={}, static_only=self.STATIC_ONLY)
            self.assertEqual(cov["covered"], ["analyzer"])
            self.assertEqual(cov["static_only"], {})

    def test_shipped_static_only_list_has_reasons(self):
        # 理由なしの宣言は「黙って落とす」ことと同じ（coverage-ledger の Iron Law）
        for skill, reason in ledger.COVERAGE_STATIC_ONLY.items():
            self.assertTrue(reason.strip(), f"理由が空: {skill}")

    def test_shipped_tier_lists_are_disjoint(self):
        overlap = set(ledger.COVERAGE_EXEMPT) & set(ledger.COVERAGE_STATIC_ONLY)
        self.assertEqual(overlap, set())

    def test_shipped_static_only_skills_all_exist(self):
        # typo・改名の取り残しを機械検出する。存在しない名前の宣言は誰も守らない
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "..", "..")
        skills = ledger._all_skills(root)
        missing = set(ledger.COVERAGE_STATIC_ONLY) - skills
        self.assertEqual(missing, set())

    def test_shipped_static_only_skills_have_no_fixtures(self):
        # fixture を得たら behavioral 昇格 = リストから外す。残すと宣言が嘘になる
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "..", "..")
        stale = set(ledger.COVERAGE_STATIC_ONLY) & ledger._fixtures_skills(root)
        self.assertEqual(stale, set())


class TestSemanticDiffHash(unittest.TestCase):
    """判定対象の diff を指す正準ハッシュ。git に依存せず台帳と現状だけで決まる。

    判定ファイルはこのハッシュで「どの差分を見て出した判定か」を名乗る。値が
    現在の差分から再計算したものと一致しなければ、古い判定を別の変更へ
    使い回した記録として拒否できる。
    """

    def test_it_is_order_independent_and_deterministic(self):
        recorded = {"a.md": "h1", "b.md": "h2"}
        current = {"b.md": "h2x", "a.md": "h1x"}
        reordered_recorded = {"b.md": "h2", "a.md": "h1"}
        reordered_current = {"a.md": "h1x", "b.md": "h2x"}
        self.assertEqual(
            ledger.semantic_diff_sha256(recorded, current),
            ledger.semantic_diff_sha256(reordered_recorded, reordered_current))

    def test_no_change_differs_from_a_change(self):
        unchanged = ledger.semantic_diff_sha256({"a.md": "h1"}, {"a.md": "h1"})
        changed = ledger.semantic_diff_sha256({"a.md": "h1"}, {"a.md": "h2"})
        self.assertNotEqual(unchanged, changed)
        self.assertEqual(len(changed), 64)

    def test_unchanged_files_do_not_enter_the_hash(self):
        # 判定対象は「変わったファイル」。無関係な面の増減でハッシュが動くと、
        # 同じ diff を見た判定が別物として拒否される
        self.assertEqual(
            ledger.semantic_diff_sha256({"a.md": "h1"}, {"a.md": "h2"}),
            ledger.semantic_diff_sha256(
                {"a.md": "h1", "b.md": "same"}, {"a.md": "h2", "b.md": "same"}))

    def test_an_added_and_a_removed_file_hash_differently(self):
        added = ledger.semantic_diff_sha256({}, {"a.md": "h1"})
        removed = ledger.semantic_diff_sha256({"a.md": "h1"}, {})
        self.assertNotEqual(added, removed)

    def test_the_direction_of_a_modification_matters(self):
        self.assertNotEqual(
            ledger.semantic_diff_sha256({"a.md": "h1"}, {"a.md": "h2"}),
            ledger.semantic_diff_sha256({"a.md": "h2"}, {"a.md": "h1"}))


class _JudgmentHarness(unittest.TestCase):
    """判定ファイル検証の共通土台。合格する材料を組み、1 か所ずつ壊して試す。"""

    SKILL = "a"
    MODEL = "judge-model-1"
    RECORDED = {"skills/shared/references/tdd.md": "h1"}
    CURRENT = {"skills/shared/references/tdd.md": "h2"}
    CORPUS = "corpus-fingerprint-1"

    def _judgment(self, **overrides):
        judgment = {
            "skill": self.SKILL,
            "diff_sha256": ledger.semantic_diff_sha256(
                self.RECORDED, self.CURRENT),
            "model": self.MODEL,
            "scenarios": {
                "a-001": {"verdict": "unaffected", "rationale": "要件に触れない"},
            },
        }
        judgment.update(overrides)
        return judgment

    def _calibration(self, entries=None, corpus=None):
        if entries is None:
            entries = {
                self.MODEL: {
                    "must_flag_fn": 0,
                    "must_pass_fp": 2,
                    "corpus_sha256": self.CORPUS,
                    "verified": "2026-08-05",
                },
            }
        return ledger.CalibrationGate(
            entries=entries,
            corpus_sha256=self.CORPUS if corpus is None else corpus)

    def _reason(self, judgment=None, calibration=None):
        return ledger.validate_judgment(
            self._judgment() if judgment is None else judgment,
            self.SKILL, self.RECORDED, self.CURRENT,
            self._calibration() if calibration is None else calibration)


class TestValidateJudgment(_JudgmentHarness):
    """判定ファイルの形式検証。1 つでも欠ければ記録ごと拒否する（C1）。"""

    def test_a_well_formed_judgment_is_accepted(self):
        self.assertIsNone(self._reason())

    def test_a_non_dict_judgment_is_refused(self):
        self.assertIsNotNone(self._reason(judgment=["not", "a", "mapping"]))

    def test_each_required_field_is_mandatory(self):
        for field in ("skill", "diff_sha256", "model", "scenarios"):
            with self.subTest(field=field):
                judgment = self._judgment()
                del judgment[field]
                reason = self._reason(judgment=judgment)
                self.assertIsNotNone(reason)
                self.assertIn(field, reason)

    def test_a_verdict_outside_the_three_values_is_refused(self):
        judgment = self._judgment(scenarios={
            "a-001": {"verdict": "probably-fine", "rationale": "…"}})
        reason = self._reason(judgment=judgment)
        self.assertIsNotNone(reason)
        self.assertIn("a-001", reason)

    def test_an_empty_rationale_is_refused(self):
        # 根拠のない判定は監査できない。空白だけも空と同じ
        for rationale in ("", "   ", None):
            with self.subTest(rationale=rationale):
                judgment = self._judgment(scenarios={
                    "a-001": {"verdict": "unaffected", "rationale": rationale}})
                self.assertIsNotNone(self._reason(judgment=judgment))

    def test_a_scenario_entry_that_is_not_a_mapping_is_refused(self):
        judgment = self._judgment(scenarios={"a-001": "unaffected"})
        self.assertIsNotNone(self._reason(judgment=judgment))

    def test_scenarios_must_be_a_mapping(self):
        self.assertIsNotNone(
            self._reason(judgment=self._judgment(scenarios=["a-001"])))

    def test_a_judgment_for_another_skill_is_refused(self):
        judgment = self._judgment(skill="b")
        reason = self._reason(judgment=judgment)
        self.assertIsNotNone(reason)
        self.assertIn("b", reason)

    def test_a_stale_diff_hash_is_refused(self):
        # 別の変更に対して出した古い判定の使い回しを機械的に塞ぐ（C2）
        judgment = self._judgment(diff_sha256="0" * 64)
        reason = self._reason(judgment=judgment)
        self.assertIsNotNone(reason)
        self.assertIn("diff", reason)

    def test_the_unclear_and_affected_verdicts_are_well_formed_too(self):
        # 形式検証の段階では 3 値すべて正当。記録できるかは別の規則（C3）
        for verdict in ("unclear", "affected"):
            with self.subTest(verdict=verdict):
                judgment = self._judgment(scenarios={
                    "a-001": {"verdict": verdict, "rationale": "判断できない"}})
                self.assertIsNone(self._reason(judgment=judgment))


class TestCalibrationGate(_JudgmentHarness):
    """較正ゲート。未較正のモデルの判定は記録経路へ入れない（A7, A8）。"""

    def test_an_unknown_model_is_refused(self):
        reason = self._reason(calibration=self._calibration(entries={}))
        self.assertIsNotNone(reason)
        self.assertIn(self.MODEL, reason)

    def test_a_judgment_from_a_different_model_is_refused(self):
        # 較正はモデルに固有。別モデルの合格実績を借りられない
        judgment = self._judgment(model="another-model")
        reason = self._reason(judgment=judgment)
        self.assertIsNotNone(reason)
        self.assertIn("another-model", reason)

    def test_a_false_negative_in_the_must_flag_corpus_blocks_the_gate(self):
        calibration = self._calibration(entries={
            self.MODEL: {"must_flag_fn": 1, "must_pass_fp": 0,
                         "corpus_sha256": self.CORPUS, "verified": "2026-08-05"},
        })
        reason = self._reason(calibration=calibration)
        self.assertIsNotNone(reason)
        self.assertIn("must_flag_fn", reason)

    def test_a_corpus_revision_invalidates_the_calibration(self):
        calibration = self._calibration(corpus="corpus-fingerprint-2")
        reason = self._reason(calibration=calibration)
        self.assertIsNotNone(reason)
        self.assertIn("corpus", reason)

    def test_a_missing_calibration_file_blocks_the_gate(self):
        # calibration.json 不在 = 一度も較正していない。advisor 止まり
        with tempfile.TemporaryDirectory() as root:
            calibration = ledger.load_calibration(root)
            self.assertEqual(calibration.entries, {})
            self.assertIsNotNone(self._reason(calibration=calibration))

    def test_a_malformed_entry_is_refused(self):
        # must_flag_fn が数値でない記録を「0 でない」と読めない形で通さない
        for entry in ({}, {"must_flag_fn": None}, {"must_flag_fn": "0"},
                      {"must_flag_fn": 0}):
            with self.subTest(entry=entry):
                calibration = self._calibration(entries={self.MODEL: entry})
                self.assertIsNotNone(self._reason(calibration=calibration))


class TestLoadCalibration(unittest.TestCase):
    """calibration.json とコーパスのフィンガープリントを読む I/O 層。"""

    def _corpus(self, root, must_flag=1, must_pass=1):
        for i in range(must_flag):
            _write(root, f"skills/skill-regression/calibration/must_flag/f{i}.json",
                   json.dumps({"id": f"f{i}", "expected": "must-flag"}))
        for i in range(must_pass):
            _write(root, f"skills/skill-regression/calibration/must_pass/p{i}.json",
                   json.dumps({"id": f"p{i}", "expected": "must-pass"}))

    def test_it_reads_the_entries_and_the_corpus_fingerprint(self):
        with tempfile.TemporaryDirectory() as root:
            self._corpus(root)
            _write(root, "skills/skill-regression/calibration.json",
                   json.dumps({"m": {"must_flag_fn": 0}}))
            calibration = ledger.load_calibration(root)
            self.assertEqual(calibration.entries, {"m": {"must_flag_fn": 0}})
            self.assertEqual(len(calibration.corpus_sha256), 64)

    def test_the_corpus_fingerprint_moves_when_a_case_changes(self):
        with tempfile.TemporaryDirectory() as root:
            self._corpus(root)
            before = ledger.corpus_sha256(root)
            _write(root,
                   "skills/skill-regression/calibration/must_flag/f0.json",
                   json.dumps({"id": "f0", "expected": "must-flag", "x": 1}))
            self.assertNotEqual(before, ledger.corpus_sha256(root))

    def test_the_corpus_fingerprint_moves_when_a_case_is_added(self):
        with tempfile.TemporaryDirectory() as root:
            self._corpus(root)
            before = ledger.corpus_sha256(root)
            self._corpus(root, must_flag=2, must_pass=1)
            self.assertNotEqual(before, ledger.corpus_sha256(root))

    def test_a_broken_calibration_file_reads_as_no_calibration(self):
        # 壊れた JSON を例外で落とすと、--check の経路まで巻き込んで死ぬ。
        # 較正が読めない = 較正していない（advisor 止まり）へ倒す
        with tempfile.TemporaryDirectory() as root:
            _write(root, "skills/skill-regression/calibration.json", "{ broken")
            self.assertEqual(ledger.load_calibration(root).entries, {})


class TestSkillResultTiers(unittest.TestCase):
    """skill レベル result の 3 段階化。pass の意味だけは絶対に薄めない。"""

    def _records(self, *results):
        return {f"s-{i}": {"result": r} for i, r in enumerate(results)}

    def test_every_scenario_run_is_pass(self):
        self.assertEqual(
            ledger.skill_result(self._records("pass", "pass")), "pass")

    def test_run_plus_semantic_is_accepted_semantic(self):
        self.assertEqual(
            ledger.skill_result(self._records("pass", "accepted-semantic")),
            "accepted-semantic")

    def test_only_semantic_is_accepted_semantic(self):
        self.assertEqual(
            ledger.skill_result(self._records("accepted-semantic")),
            "accepted-semantic")

    def test_anything_else_in_the_mix_falls_back_to_accepted_without_run(self):
        # 判定器より確度の低い記録が 1 つでも混ざれば、台帳は下の段を名乗る
        for other in ("accepted-without-run", "accepted-addition",
                      "accepted-prose"):
            with self.subTest(other=other):
                self.assertEqual(
                    ledger.skill_result(
                        self._records("pass", "accepted-semantic", other)),
                    "accepted-without-run")

    def test_no_records_is_not_a_pass(self):
        self.assertEqual(ledger.skill_result({}), "accepted-without-run")


class _SemanticHarness(_PartialHarness):
    """semantic triage の記録経路の共通土台。

    面の tdd.md を変えると a-001（宣言あり）と a-003（宣言なし）が影響側、
    a-002 は持ち越し側になる。この非対称が「判定で進む分」と「機械で進む分」を
    同じ更新の中で区別できることの確認になる。
    """

    MODEL = "judge-model-1"

    def _calibrate(self, root, model=None, must_flag_fn=0, corpus_sha256=None):
        _write(root, "skills/skill-regression/calibration/must_flag/f0.json",
               json.dumps({"id": "f0", "expected": "must-flag"}))
        _write(root, "skills/skill-regression/calibration/must_pass/p0.json",
               json.dumps({"id": "p0", "expected": "must-pass"}))
        _write(root, "skills/skill-regression/calibration.json", json.dumps({
            model or self.MODEL: {
                "must_flag_fn": must_flag_fn,
                "must_pass_fp": 0,
                "corpus_sha256": (corpus_sha256 if corpus_sha256 is not None
                                  else ledger.corpus_sha256(root)),
                "verified": "2026-08-05",
            },
        }))

    def _judgment(self, root, verdicts, model=None, skill="a", **overrides):
        entry = ledger.load(root).get(skill, {})
        surface = ledger.skill_surface(root, skill)
        judgment = {
            "skill": skill,
            "diff_sha256": ledger.semantic_diff_sha256(
                entry.get("file_sha256", {}), ledger.file_hashes(root, surface)),
            "model": model or self.MODEL,
            "scenarios": {
                sid: {"verdict": verdict, "rationale": "要件の合否には効かない"}
                for sid, verdict in verdicts.items()
            },
        }
        judgment.update(overrides)
        path = os.path.join(root, "judgment.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(judgment, f, ensure_ascii=False)
        return path

    def _touch_contract(self, root):
        _write(root, "skills/shared/references/tdd.md", "tdd contract CHANGED")


class TestSemanticRecording(_SemanticHarness):
    """`--partial --semantic` は unaffected 判定の分だけ accepted-semantic を書く。"""

    def test_an_unaffected_verdict_is_recorded_as_accepted_semantic(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            self._calibrate(root)
            self._touch_contract(root)
            path = self._judgment(
                root, {"a-001": "unaffected", "a-003": "unaffected"})
            rc, _ = self._run(
                ["--update", "a", "--partial", "--semantic", path, root])
            self.assertEqual(rc, 0)
            entry = ledger.load(root)["a"]
            for sid in ("a-001", "a-003"):
                self.assertEqual(entry["scenarios"][sid]["result"],
                                 "accepted-semantic")
            # 実走していないので検証日は据え置き（accepted_scenarios_record と同規則）
            self.assertEqual(entry["scenarios"]["a-001"]["verified"], "2026-08-01")
            # 機械で持ち越せた分は従来どおり前回の pass のまま
            self.assertEqual(entry["scenarios"]["a-002"]["result"], "pass")

    def test_the_skill_level_result_stops_calling_itself_pass(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            self._calibrate(root)
            self._touch_contract(root)
            path = self._judgment(
                root, {"a-001": "unaffected", "a-003": "unaffected"})
            self._run(["--update", "a", "--partial", "--semantic", path, root])
            self.assertEqual(ledger.load(root)["a"]["result"],
                             "accepted-semantic")

    def test_the_entry_records_the_provenance_of_the_judgment(self):
        # どのモデルが何を根拠に進めたのかが台帳から読めないと、蓄積した
        # accepted-semantic の抜き打ち監査ができない
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            self._calibrate(root)
            self._touch_contract(root)
            path = self._judgment(
                root, {"a-001": "unaffected", "a-003": "unaffected"})
            self._run(["--update", "a", "--partial", "--semantic", path, root])
            semantic = ledger.load(root)["a"]["semantic"]
            self.assertEqual(semantic["model"], self.MODEL)
            self.assertEqual(len(semantic["diff_sha256"]), 64)
            self.assertEqual(semantic["scenarios"]["a-001"]["verdict"],
                             "unaffected")
            self.assertTrue(semantic["scenarios"]["a-001"]["rationale"])

    def test_a_run_scenario_and_a_semantic_one_coexist(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            self._calibrate(root)
            self._touch_contract(root)
            path = self._judgment(root, {"a-003": "unaffected"})
            rc, _ = self._run([
                "--update", "a", "--partial", "--scenario", "a-001",
                "--semantic", path, root])
            self.assertEqual(rc, 0)
            entry = ledger.load(root)["a"]
            self.assertEqual(entry["scenarios"]["a-001"]["result"], "pass")
            self.assertEqual(entry["scenarios"]["a-001"]["verified"],
                             datetime.date.today().isoformat())
            self.assertEqual(entry["scenarios"]["a-003"]["result"],
                             "accepted-semantic")

    def test_an_entry_without_semantic_records_has_no_semantic_key(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            rc, _ = self._run(["--update", "a", "--partial", root])
            self.assertEqual(rc, 0)
            self.assertNotIn("semantic", ledger.load(root)["a"])


class TestSemanticVerdictsThatCannotRecord(_SemanticHarness):
    """unaffected 以外は記録経路へ入らない（C3）。表示は人間への推奨まで。"""

    def _blocked(self, root, verdicts):
        self._repo(root)
        self._verified(root)
        self._calibrate(root)
        self._touch_contract(root)
        path = self._judgment(root, verdicts)
        return self._run(["--update", "a", "--partial", "--semantic", path, root])

    def test_an_unclear_verdict_blocks_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            rc, out = self._blocked(
                root, {"a-001": "unclear", "a-003": "unaffected"})
            self.assertEqual(rc, 1)
            self.assertIn("a-001", out)
            # 全か無か: 記録できた分があっても台帳は 1 バイトも動かさない
            self.assertEqual(ledger.load(root)["a"]["verified"], "2026-08-01")
            self.assertNotIn("semantic", ledger.load(root)["a"])

    def test_an_affected_verdict_blocks(self):
        with tempfile.TemporaryDirectory() as root:
            rc, out = self._blocked(
                root, {"a-001": "affected", "a-003": "unaffected"})
            self.assertEqual(rc, 1)
            self.assertIn("a-001", out)

    def test_a_scenario_with_no_verdict_blocks(self):
        with tempfile.TemporaryDirectory() as root:
            rc, out = self._blocked(root, {"a-001": "unaffected"})
            self.assertEqual(rc, 1)
            self.assertIn("a-003", out)

    def test_a_changed_scenario_definition_blocks_even_when_unaffected(self):
        # 合否基準そのものが動いたシナリオは判定器の管轄外（実走でしか確かめられない）
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            self._calibrate(root)
            self._touch_contract(root)
            fixture = json.loads(json.dumps(self.FIXTURE))
            fixture["scenarios"][1]["prompt"] = "two, but stricter"
            self._write_fixture(root, fixture)
            path = self._judgment(root, {
                "a-001": "unaffected", "a-002": "unaffected",
                "a-003": "unaffected"})
            rc, out = self._run(
                ["--update", "a", "--partial", "--semantic", path, root])
            self.assertEqual(rc, 1)
            self.assertIn("a-002", out)


class TestSemanticJudgmentIsRefusedWholesale(_SemanticHarness):
    """判定ファイルが信用できないときは、記録ごと拒否する（C1, C2）。"""

    def _setup(self, root):
        self._repo(root)
        self._verified(root)
        self._calibrate(root)
        self._touch_contract(root)

    def test_a_stale_diff_hash_refuses_the_update(self):
        with tempfile.TemporaryDirectory() as root:
            self._setup(root)
            path = self._judgment(
                root, {"a-001": "unaffected", "a-003": "unaffected"})
            # 判定を出した後にもう 1 つ面が動いた = 判定は今の差分のものではない
            _write(root, "skills/shared/references/gate.md", "gate CHANGED")
            rc, out = self._run(
                ["--update", "a", "--partial", "--semantic", path, root])
            self.assertEqual(rc, 1)
            self.assertIn("diff_sha256", out)
            self.assertEqual(ledger.load(root)["a"]["verified"], "2026-08-01")

    def test_an_uncalibrated_model_refuses_the_update(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            self._calibrate(root, must_flag_fn=1)
            self._touch_contract(root)
            path = self._judgment(
                root, {"a-001": "unaffected", "a-003": "unaffected"})
            rc, out = self._run(
                ["--update", "a", "--partial", "--semantic", path, root])
            self.assertEqual(rc, 1)
            self.assertIn("advisor", out)

    def test_a_missing_calibration_file_refuses_the_update(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            self._touch_contract(root)
            path = self._judgment(
                root, {"a-001": "unaffected", "a-003": "unaffected"})
            rc, out = self._run(
                ["--update", "a", "--partial", "--semantic", path, root])
            self.assertEqual(rc, 1)
            self.assertIn("advisor", out)

    def test_a_revised_corpus_refuses_the_update(self):
        with tempfile.TemporaryDirectory() as root:
            self._setup(root)
            path = self._judgment(
                root, {"a-001": "unaffected", "a-003": "unaffected"})
            _write(root, "skills/skill-regression/calibration/must_flag/f1.json",
                   json.dumps({"id": "f1", "expected": "must-flag"}))
            rc, out = self._run(
                ["--update", "a", "--partial", "--semantic", path, root])
            self.assertEqual(rc, 1)
            self.assertIn("corpus", out)

    def test_a_malformed_judgment_file_refuses_the_update(self):
        with tempfile.TemporaryDirectory() as root:
            self._setup(root)
            path = os.path.join(root, "judgment.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write("{ not json")
            rc, out = self._run(
                ["--update", "a", "--partial", "--semantic", path, root])
            self.assertEqual(rc, 1)
            self.assertIn("judgment.json", out)

    def test_a_missing_judgment_file_refuses_the_update(self):
        with tempfile.TemporaryDirectory() as root:
            self._setup(root)
            rc, out = self._run([
                "--update", "a", "--partial", "--semantic",
                os.path.join(root, "absent.json"), root])
            self.assertEqual(rc, 1)
            self.assertIn("absent.json", out)

    def test_a_judgment_for_another_skill_refuses_the_update(self):
        with tempfile.TemporaryDirectory() as root:
            self._setup(root)
            path = self._judgment(root, {"a-001": "unaffected"}, skill="b")
            rc, out = self._run(
                ["--update", "a", "--partial", "--semantic", path, root])
            self.assertEqual(rc, 1)
            self.assertIn("skill", out)


class TestSemanticFlagWiring(_SemanticHarness):
    """`--semantic` は --partial 専用で、--accept とは併用できない。"""

    def test_it_refuses_to_combine_with_accept(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            self._calibrate(root)
            path = self._judgment(root, {})
            rc, _ = self._run([
                "--update", "a", "--partial", "--accept",
                "--semantic", path, root])
            self.assertEqual(rc, 1)
            self.assertEqual(ledger.load(root)["a"]["verified"], "2026-08-01")

    def test_it_refuses_without_partial(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            self._calibrate(root)
            path = self._judgment(root, {})
            rc, out = self._run(["--update", "a", "--semantic", path, root])
            self.assertEqual(rc, 1)
            self.assertIn("--partial", out)

    def test_it_refuses_a_value_less_flag(self):
        rc, out = self._run(["--update", "a", "--partial", "--semantic"])
        self.assertEqual(rc, 2)
        self.assertIn("--semantic", out)

    def test_a_misplaced_semantic_flag_is_refused(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            self._verified(root)
            rc, out = self._run(
                ["--semantic", "x.json", "--update", "a", "--partial", root])
            self.assertEqual(rc, 2)
            self.assertIn("--semantic", out)


class TestSemanticIsCountedSeparately(_SemanticHarness):
    """--check の内訳で accepted-semantic を独立カウントする（C4, A3）。

    他の accepted と混ぜると「判定器に寄りかかりすぎている」という新しい
    危険信号が読めなくなる。
    """

    def test_check_counts_accepted_semantic_on_its_own_line(self):
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            surface = ledger.skill_surface(root, "a")
            ledger.save(root, {
                "a": ledger.make_entry(
                    root, surface, "accepted-semantic", "2026-08-05"),
            })
            rc, out = self._run(["--check", root])
            self.assertEqual(rc, 0)
            self.assertIn("accepted-semantic 1", out)
            self.assertIn("accepted-without-run 0", out)

    def test_status_keeps_its_four_column_structure(self):
        # --status は 4 消費経路の 1 つ。列構造が動くと下流が黙って壊れる
        with tempfile.TemporaryDirectory() as root:
            self._repo(root)
            surface = ledger.skill_surface(root, "a")
            ledger.save(root, {
                "a": ledger.make_entry(
                    root, surface, "accepted-semantic", "2026-08-05"),
            })
            rc, out = self._run(["--status", root])
            self.assertEqual(rc, 0)
            self.assertEqual(
                out.strip().split("\t"),
                ["a", "verified", "accepted-semantic", "2026-08-05"])


class TestNoExecutionAuthority(unittest.TestCase):
    """C5: 判定器側のスクリプトは実行系 API を持ち込まない。

    判定器へ実行権限を与えないという仕様の要（docs/spec/semantic-triage.md
    「権限の境界」）は散文の約束では守れない。設計性質の退行を canary で検出する。
    """

    SCRIPTS = ("ledger.py", "semantic_calibration.py")

    def _source(self, name):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_no_execution_api_is_imported(self):
        for name in self.SCRIPTS:
            with self.subTest(script=name):
                source = self._source(name)
                for forbidden in ("subprocess", "os.system", "os.exec",
                                  "os.spawn", "os.popen"):
                    self.assertNotIn(forbidden, source,
                                     f"{name} に {forbidden} が現れた")


if __name__ == "__main__":
    unittest.main()
