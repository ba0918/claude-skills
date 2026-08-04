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


if __name__ == "__main__":
    unittest.main()
