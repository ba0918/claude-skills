"""release_publish.sh の失敗経路テスト。

PATH に fake の git / gh を置き、公開順序の契約
（draft 完成 → atomic push → publish）と再実行の回復を検証する。
実行: python3 -m unittest discover scripts
"""
import os
import stat
import subprocess
import tempfile
import unittest


SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLISH_SH = os.path.join(SCRIPTS_DIR, "release_publish.sh")
HEAD_SHA = "a" * 40
OTHER_SHA = "b" * 40

FAKE_GIT = """#!/bin/sh
cmd="git $*"
echo "$cmd" >> "$FAKE_DIR/calls.log"
if [ -f "$FAKE_DIR/fail_on" ]; then
  while IFS= read -r prefix; do
    [ -n "$prefix" ] || continue
    case "$cmd" in "$prefix"*) echo "fake: injected failure: $prefix" >&2; exit 1;; esac
  done < "$FAKE_DIR/fail_on"
fi
case "$1" in
  rev-parse)
    if [ "$2" = "HEAD" ]; then
      cat "$FAKE_DIR/head"
    elif [ "$2" = "-q" ]; then
      [ -f "$FAKE_DIR/local_tag" ] || exit 1
    else
      cat "$FAKE_DIR/local_tag"
    fi
    ;;
  ls-remote)
    case "$3" in
      *"^{}") [ -f "$FAKE_DIR/ls_remote_peel_out" ] && cat "$FAKE_DIR/ls_remote_peel_out" ;;
      *) [ -f "$FAKE_DIR/ls_remote_out" ] && cat "$FAKE_DIR/ls_remote_out" ;;
    esac
    exit 0
    ;;
  tag)
    cat "$FAKE_DIR/head" > "$FAKE_DIR/local_tag"
    ;;
  push)
    ;;
esac
exit 0
"""

FAKE_GH = """#!/bin/sh
cmd="gh $*"
echo "$cmd" >> "$FAKE_DIR/calls.log"
if [ -f "$FAKE_DIR/fail_on" ]; then
  while IFS= read -r prefix; do
    [ -n "$prefix" ] || continue
    case "$cmd" in "$prefix"*) echo "fake: injected failure: $prefix" >&2; exit 1;; esac
  done < "$FAKE_DIR/fail_on"
fi
case "$2" in
  view)
    [ -f "$FAKE_DIR/release" ] || exit 1
    cat "$FAKE_DIR/release"
    ;;
  delete)
    rm -f "$FAKE_DIR/release"
    ;;
  create)
    prev=""
    for arg in "$@"; do
      if [ "$prev" = "--target" ]; then
        grep -qxF "$arg" "$FAKE_DIR/remote_shas" 2>/dev/null || {
          echo "fake: target commitish $arg is not reachable on the remote" >&2
          exit 1
        }
      fi
      prev="$arg"
    done
    echo "true" > "$FAKE_DIR/release"
    ;;
  edit)
    echo "false" > "$FAKE_DIR/release"
    ;;
esac
exit 0
"""


class ReleasePublishTest(unittest.TestCase):
    """公開順序の契約と失敗窓からの回復を fake で検証する。"""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.fake_dir = self.tempdir.name
        self.bin_dir = os.path.join(self.fake_dir, "bin")
        os.makedirs(self.bin_dir)
        self._install_fake("git", FAKE_GIT)
        self._install_fake("gh", FAKE_GH)
        self._write("head", HEAD_SHA + "\n")
        self.notes = os.path.join(self.fake_dir, "notes.md")
        self._write_path(self.notes, "notes\n")

    def tearDown(self):
        self.tempdir.cleanup()

    def _install_fake(self, name, body):
        path = os.path.join(self.bin_dir, name)
        self._write_path(path, body)
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)

    def _write(self, name, text):
        self._write_path(os.path.join(self.fake_dir, name), text)

    def _write_path(self, path, text):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def _run(self):
        env = dict(os.environ)
        env["PATH"] = self.bin_dir + os.pathsep + env["PATH"]
        env["FAKE_DIR"] = self.fake_dir
        return subprocess.run(
            ["sh", PUBLISH_SH, "1.73.0", self.notes, "asset.json#asset.json"],
            capture_output=True,
            text=True,
            env=env,
        )

    def _calls(self):
        path = os.path.join(self.fake_dir, "calls.log")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as handle:
            return handle.read().splitlines()

    def _release_state(self):
        path = os.path.join(self.fake_dir, "release")
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as handle:
            return handle.read().strip()

    def test_fresh_release_completes_draft_before_any_push(self):
        """新規リリースは draft 完成 → atomic push → publish の順で完走する。

        fake gh の release create は、リモート未到達の commitish を --target に
        受け取ると失敗する。fixture は HEAD をリモート到達済みに登録しない
        （changed=true の初回経路: release commit は draft 作成時点で未 push）ため、
        このテストの完走自体が「draft 作成が未 push SHA を参照しない」ことの検証になる。
        """
        proc = self._run()

        self.assertEqual(proc.returncode, 0, proc.stderr)
        calls = self._calls()
        create = next(i for i, c in enumerate(calls) if c.startswith("gh release create"))
        push = next(i for i, c in enumerate(calls) if c.startswith("git push"))
        edit = next(i for i, c in enumerate(calls) if c.startswith("gh release edit"))
        self.assertLess(create, push)
        self.assertLess(push, edit)
        self.assertNotIn("--target", calls[create])
        self.assertIn("--atomic origin HEAD:main refs/tags/v1.73.0", calls[push])
        self.assertEqual(self._release_state(), "false")

    def test_fake_gh_rejects_unpushed_target_commitish(self):
        """fake gh 自体の検出力: リモート未到達 SHA の --target は create を落とす。

        本体が --target を復活させる回帰をテストが検出できることの自己検証。
        """
        env = dict(os.environ)
        env["PATH"] = self.bin_dir + os.pathsep + env["PATH"]
        env["FAKE_DIR"] = self.fake_dir
        proc = subprocess.run(
            ["gh", "release", "create", "v1.73.0", "--draft", "--target", HEAD_SHA],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("not reachable", proc.stderr)

    def test_draft_failure_leaves_nothing_public(self):
        """draft 作成が失敗したら push は走らず、公開物ゼロで失敗する。"""
        self._write("fail_on", "gh release create\n")

        proc = self._run()

        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(any(c.startswith("git push") for c in self._calls()))
        self.assertIsNone(self._release_state())

    def test_publish_failure_recovers_on_rerun(self):
        """publish のみ失敗した後の再実行は draft を作り直して完走する。"""
        self._write("fail_on", "gh release edit\n")
        first = self._run()
        self.assertNotEqual(first.returncode, 0)
        self.assertEqual(self._release_state(), "true")

        os.remove(os.path.join(self.fake_dir, "fail_on"))
        os.remove(os.path.join(self.fake_dir, "calls.log"))
        # 前回の atomic push でリモートタグは HEAD を指している
        self._write("ls_remote_out", f"{OTHER_SHA}\trefs/tags/v1.73.0\n")
        self._write("ls_remote_peel_out", f"{HEAD_SHA}\trefs/tags/v1.73.0^{{}}\n")

        second = self._run()

        self.assertEqual(second.returncode, 0, second.stderr)
        calls = self._calls()
        self.assertTrue(any(c.startswith("gh release delete") for c in calls))
        push = next(c for c in calls if c.startswith("git push"))
        self.assertNotIn("refs/tags/", push)
        self.assertEqual(self._release_state(), "false")

    def test_published_release_is_idempotent_success(self):
        """publish 済みなら何も変更せず成功する。"""
        self._write("release", "false\n")
        self._write("ls_remote_out", f"{OTHER_SHA}\trefs/tags/v1.73.0\n")
        self._write("ls_remote_peel_out", f"{HEAD_SHA}\trefs/tags/v1.73.0^{{}}\n")

        proc = self._run()

        self.assertEqual(proc.returncode, 0, proc.stderr)
        calls = self._calls()
        self.assertFalse(any(c.startswith("gh release create") for c in calls))
        self.assertFalse(any(c.startswith("git push") for c in calls))

    def test_remote_tag_mismatch_fails_before_any_mutation(self):
        """リモートタグが別 SHA を指すなら、何も変更せず失敗する（付け替え禁止）。"""
        self._write("ls_remote_out", f"{OTHER_SHA}\trefs/tags/v1.73.0\n")
        self._write("ls_remote_peel_out", f"{OTHER_SHA}\trefs/tags/v1.73.0^{{}}\n")

        proc = self._run()

        self.assertNotEqual(proc.returncode, 0)
        calls = self._calls()
        self.assertFalse(any(c.startswith("gh ") for c in calls))
        self.assertFalse(any(c.startswith("git tag") for c in calls))
        self.assertFalse(any(c.startswith("git push") for c in calls))

    def test_lightweight_remote_tag_is_rejected(self):
        """リモートタグが annotated でなければ失敗する。"""
        self._write("ls_remote_out", f"{OTHER_SHA}\trefs/tags/v1.73.0\n")

        proc = self._run()

        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("not an annotated tag", proc.stderr)


if __name__ == "__main__":
    unittest.main()
