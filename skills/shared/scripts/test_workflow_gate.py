"""workflow_gate.py の検証。

テスト名は仕様（What）を語る: どの操作がどの判定（allow / escalate / deny）になるか。
正本は skills/shared/references/workflow-gate.md の判定表。
判定コアは pure function（コマンド文字列 + 環境スナップショット → 判定 + 理由文）であり、
テストは I/O を一切必要としない。CLI アダプタのテストのみ一時 git リポジトリを使う。
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

import workflow_gate

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workflow_gate.py")


HEAD_SHA = "a" * 40


def doc_record(target_sha=HEAD_SHA, state="doc_aligned", grounds="doc-check run", **extra):
    record = {
        "schema_version": 1,
        "state": state,
        "target_sha": target_sha,
        "grounds": grounds,
    }
    record.update(extra)
    return json.dumps(record)


def snapshot(
    current_branch="feature/x",
    default_branch="main",
    trunk_config_text=None,
    evidence_exit=None,
    head_sha=HEAD_SHA,
    doc_evidence_text=None,
    evidence_report=None,
):
    return workflow_gate.EnvSnapshot(
        current_branch=current_branch,
        default_branch=default_branch,
        trunk_config_text=trunk_config_text,
        evidence_exit=evidence_exit,
        head_sha=head_sha,
        doc_evidence_text=doc_evidence_text,
        evidence_report=evidence_report,
    )


TRUNK_ADOPTED = "trunk: adopted\nallow_main_commit: false\n"
TRUNK_NOT_ADOPTED = "trunk: not_adopted\nallow_main_commit: false\n"
MAIN_COMMIT_ALLOWED = "trunk: adopted\nallow_main_commit: true\n"


class CommitGate(unittest.TestCase):
    def test_commit_on_default_branch_escalates_with_branch_guidance(self):
        """main 上の commit は escalate になり、理由文にブランチ作成の案内が含まれる。"""
        decision = workflow_gate.decide(
            "git commit -m 'x'", snapshot(current_branch="main")
        )
        self.assertEqual(decision.verdict, "escalate")
        self.assertIn("branch", decision.reason)

    def test_commit_on_feature_branch_allows_silently(self):
        """feature ブランチ上の commit は allow で、出力メッセージを持たない。"""
        decision = workflow_gate.decide("git commit -m 'x'", snapshot())
        self.assertEqual(decision.verdict, "allow")
        self.assertEqual(decision.reason, "")

    def test_declared_main_commit_permission_allows_commit_on_default_branch(self):
        """main 直コミット許可を宣言したプロジェクトでは main 上の commit が allow になる。"""
        decision = workflow_gate.decide(
            "git commit -m 'x'",
            snapshot(current_branch="main", trunk_config_text=MAIN_COMMIT_ALLOWED),
        )
        self.assertEqual(decision.verdict, "allow")

    def test_commit_with_unknown_branch_escalates(self):
        """ブランチが特定できない状態の commit は安全側（escalate）に倒れる。"""
        decision = workflow_gate.decide(
            "git commit -m 'x'", snapshot(current_branch=None)
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_compound_command_with_commit_on_default_branch_escalates(self):
        """`git add && git commit` のような連結コマンドでも commit を検出して判定する。"""
        decision = workflow_gate.decide(
            "git add file.py && git commit -m 'x'", snapshot(current_branch="main")
        )
        self.assertEqual(decision.verdict, "escalate")


class BypassGate(unittest.TestCase):
    def test_no_verify_flag_denies(self):
        """--no-verify を含む git コマンドは deny になる。"""
        decision = workflow_gate.decide(
            "git commit --no-verify -m 'x'", snapshot()
        )
        self.assertEqual(decision.verdict, "deny")
        self.assertNotEqual(decision.reason, "")

    def test_commit_short_no_verify_flag_denies(self):
        """git commit の -n（--no-verify の短縮形）も deny になる。"""
        decision = workflow_gate.decide("git commit -n -m 'x'", snapshot())
        self.assertEqual(decision.verdict, "deny")

    def test_hooks_path_override_denies(self):
        """-c core.hooksPath= によるフック無効化は deny になる。"""
        decision = workflow_gate.decide(
            "git -c core.hooksPath=/dev/null push origin main", snapshot()
        )
        self.assertEqual(decision.verdict, "deny")

    def test_push_no_verify_denies_even_with_valid_evidence(self):
        """バイパスフラグの deny は evidence の有無より優先される。"""
        decision = workflow_gate.decide(
            "git push --no-verify",
            snapshot(trunk_config_text=TRUNK_ADOPTED, evidence_exit=0),
        )
        self.assertEqual(decision.verdict, "deny")


class PushGate(unittest.TestCase):
    def test_push_with_valid_head_bound_evidence_allows(self):
        """trunk 宣言ありで HEAD にバインドされた有効な evidence（検証スライス + doc 整合レコード）がある push は allow になる。"""
        decision = workflow_gate.decide(
            "git push origin feature/x",
            snapshot(
                trunk_config_text=TRUNK_ADOPTED,
                evidence_exit=0,
                doc_evidence_text=doc_record(),
            ),
        )
        self.assertEqual(decision.verdict, "allow")

    def test_push_without_doc_alignment_record_escalates(self):
        """検証スライスが有効でも doc 整合レコードが無い push は escalate になる。"""
        decision = workflow_gate.decide(
            "git push origin feature/x",
            snapshot(
                trunk_config_text=TRUNK_ADOPTED,
                evidence_exit=0,
                doc_evidence_text=None,
            ),
        )
        self.assertEqual(decision.verdict, "escalate")
        self.assertIn("doc", decision.reason)

    def test_push_with_sha_mismatched_doc_record_escalates(self):
        """doc 整合レコードの SHA が HEAD と不一致なら escalate になる。"""
        decision = workflow_gate.decide(
            "git push origin feature/x",
            snapshot(
                trunk_config_text=TRUNK_ADOPTED,
                evidence_exit=0,
                doc_evidence_text=doc_record(target_sha="b" * 40),
            ),
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_push_with_malformed_doc_record_escalates(self):
        """doc 整合レコードが JSON として壊れていれば escalate に倒れる（安全側）。"""
        decision = workflow_gate.decide(
            "git push origin feature/x",
            snapshot(
                trunk_config_text=TRUNK_ADOPTED,
                evidence_exit=0,
                doc_evidence_text="{not json",
            ),
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_push_with_groundless_doc_record_escalates(self):
        """grounds が空の doc 整合レコードは証跡として無効で escalate になる。"""
        decision = workflow_gate.decide(
            "git push origin feature/x",
            snapshot(
                trunk_config_text=TRUNK_ADOPTED,
                evidence_exit=0,
                doc_evidence_text=doc_record(grounds=""),
            ),
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_push_with_wrong_state_doc_record_escalates(self):
        """state が doc_aligned でないレコードは doc 整合の証跡にならない。"""
        decision = workflow_gate.decide(
            "git push origin feature/x",
            snapshot(
                trunk_config_text=TRUNK_ADOPTED,
                evidence_exit=0,
                doc_evidence_text=doc_record(state="semantic_reviewed"),
            ),
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_push_without_evidence_escalates(self):
        """trunk 宣言ありで evidence の無い push（検証器の否定判定）は escalate になる。"""
        decision = workflow_gate.decide(
            "git push origin feature/x",
            snapshot(trunk_config_text=TRUNK_ADOPTED, evidence_exit=1),
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_push_with_broken_verifier_escalates(self):
        """evidence 検証器自体が実行不能（exit 2）の push は allow に倒れない。"""
        decision = workflow_gate.decide(
            "git push origin feature/x",
            snapshot(trunk_config_text=TRUNK_ADOPTED, evidence_exit=2),
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_push_with_ungathered_evidence_escalates(self):
        """evidence 検査結果が渡されていない push は allow に倒れない。"""
        decision = workflow_gate.decide(
            "git push origin feature/x",
            snapshot(trunk_config_text=TRUNK_ADOPTED, evidence_exit=None),
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_push_without_declaration_escalates_with_declaration_guidance(self):
        """trunk 宣言ファイルが無い push は escalate になり、理由文が宣言手順を案内する。"""
        decision = workflow_gate.decide(
            "git push origin feature/x", snapshot(trunk_config_text=None)
        )
        self.assertEqual(decision.verdict, "escalate")
        self.assertIn(".agents/config/trunk.yml", decision.reason)

    def test_push_with_declared_opt_out_allows(self):
        """trunk 不採用を宣言したプロジェクトの push は allow になる。"""
        decision = workflow_gate.decide(
            "git push origin feature/x",
            snapshot(trunk_config_text=TRUNK_NOT_ADOPTED),
        )
        self.assertEqual(decision.verdict, "allow")


class DeclarationParsing(unittest.TestCase):
    def test_unparsable_declaration_escalates(self):
        """宣言ファイルの parse 失敗は escalate に倒れる（安全側）。"""
        decision = workflow_gate.decide(
            "git push origin feature/x",
            snapshot(trunk_config_text="trunk adopted no colon here\n"),
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_unknown_declaration_value_escalates(self):
        """宣言ファイルの未知の値は escalate に倒れる（安全側）。"""
        decision = workflow_gate.decide(
            "git push origin feature/x",
            snapshot(trunk_config_text="trunk: maybe\n"),
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_unknown_main_commit_value_escalates_commit(self):
        """allow_main_commit の未知の値は宣言なしと同じく escalate になる。"""
        decision = workflow_gate.decide(
            "git commit -m 'x'",
            snapshot(
                current_branch="main",
                trunk_config_text="trunk: adopted\nallow_main_commit: yes-please\n",
            ),
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_comments_and_blank_lines_are_tolerated(self):
        """コメント行・空行を含む宣言ファイルは正常に読める。"""
        text = "# gate declaration\n\ntrunk: adopted\nallow_main_commit: true  # ok\n"
        decision = workflow_gate.decide(
            "git commit -m 'x'",
            snapshot(current_branch="main", trunk_config_text=text),
        )
        self.assertEqual(decision.verdict, "allow")


class ConservativeInterpretation(unittest.TestCase):
    def test_shell_wrapped_git_command_escalates(self):
        """`sh -c` 包みの git コマンドは構造を解釈できないため escalate に倒れる。"""
        decision = workflow_gate.decide(
            "sh -c 'git commit -m x'", snapshot(current_branch="main")
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_command_substitution_around_git_escalates(self):
        """コマンド置換の中に git 書き込み操作を含むコマンドは escalate に倒れる。"""
        decision = workflow_gate.decide(
            "echo $(git commit -m x)", snapshot()
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_unbalanced_quotes_with_git_token_escalate(self):
        """クォート破綻で token 化できないが git を含むコマンドは escalate に倒れる。"""
        decision = workflow_gate.decide(
            "git commit -m 'unclosed", snapshot(current_branch="main")
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_read_only_git_operations_allow(self):
        """commit / push 以外の git 操作（status, log, diff 等）は allow になる。"""
        for command in ("git status", "git log --oneline", "git diff", "git add x"):
            decision = workflow_gate.decide(command, snapshot(current_branch="main"))
            self.assertEqual(decision.verdict, "allow", command)
            self.assertEqual(decision.reason, "", command)


class QuotedNewlineInterpretation(unittest.TestCase):
    """引用符内のデータ改行と、コマンド区切りの構造改行を区別する検証。

    複数行コミットメッセージ（コミット規則が要求する why 本文）が
    解釈不能扱いで escalate される偽陽性（issue #304）の再発防止。
    """

    def test_multiline_commit_message_on_feature_branch_allows(self):
        """引用符内の改行はデータであり、feature ブランチのコミットは allow になる。"""
        decision = workflow_gate.decide(
            'git commit -m "feat: subject\n\nwhy body line 1\nwhy body line 2"',
            snapshot(),
        )
        self.assertEqual(decision.verdict, "allow")
        self.assertEqual(decision.reason, "")

    def test_add_and_multiline_commit_compound_allows(self):
        """git add && 複数行 -m コミットの複合形も feature ブランチでは allow になる。"""
        decision = workflow_gate.decide(
            'git add skills/plan/SKILL.md && git commit -m "feat: x\n\nbody"',
            snapshot(),
        )
        self.assertEqual(decision.verdict, "allow")
        self.assertEqual(decision.reason, "")

    def test_multiline_commit_message_on_default_branch_escalates_as_main_commit(self):
        """複数行メッセージでも main へのコミットは main コミットとして escalate する。"""
        decision = workflow_gate.decide(
            'git commit -m "feat: subject\n\nbody"',
            snapshot(current_branch="main"),
        )
        self.assertEqual(decision.verdict, "escalate")
        self.assertIn("branch", decision.reason)

    def test_unquoted_newline_separated_main_commit_escalates(self):
        """引用符の外の改行はコマンド区切りであり、後続の main コミットを検出する。"""
        decision = workflow_gate.decide(
            "ls\ngit commit -m fix", snapshot(current_branch="main")
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_newline_after_and_operator_still_detects_push(self):
        """&& 直後の改行で分割された push も evidence 検査の対象になる。"""
        decision = workflow_gate.decide(
            'git add x &&\ngit push', snapshot(evidence_exit=None)
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_backslash_newline_continuation_push_still_detected(self):
        """バックスラッシュ改行の行継続で分割された push も検出される。"""
        decision = workflow_gate.decide(
            "git \\\npush", snapshot(evidence_exit=None)
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_git_word_split_by_continuation_is_still_gated(self):
        """語中のバックスラッシュ改行で git の語を分断しても検出される。"""
        decision = workflow_gate.decide(
            "gi\\\nt push", snapshot(evidence_exit=None)
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_no_verify_words_inside_quoted_message_are_data(self):
        """引用符内の '--no-verify' や 'git push' の語はデータであり deny を誘発しない。"""
        decision = workflow_gate.decide(
            'git commit -m "note: git push --no-verify is denied\nsecond line"',
            snapshot(),
        )
        self.assertEqual(decision.verdict, "allow")
        self.assertEqual(decision.reason, "")

    def test_ansi_c_quoting_with_escaped_quote_never_allows(self):
        """bash の ANSI-C クォート $'...' は単純追跡では追えないため解釈不能へ倒す。

        $'\\'' は bash ではリテラルの ' でクォートを閉じないが POSIX single とは
        規則が異なる。この状態ズレで後続の push を隠す偽陰性（Codex 敵対レビュー
        実証）を防ぐため、$' を含むコマンドは allow に到達させない。
        """
        payload = "git commit -m $'\\''\ngit push --no" + "-verify"
        decision = workflow_gate.decide(payload, snapshot(current_branch="main"))
        self.assertNotEqual(decision.verdict, "allow")

    def test_ansi_c_quoting_hiding_push_escalates(self):
        """ANSI-C クォートの後にセグメント区切りで push を続ける形も allow にしない。"""
        decision = workflow_gate.decide(
            "git log $'\\x0a' && git push", snapshot()
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_locale_quoting_never_allows(self):
        r"""ロケールクォート $"..." も単純追跡外のため allow に到達させない。"""
        decision = workflow_gate.decide(
            'git commit -m $"x"\ngit push', snapshot(current_branch="main")
        )
        self.assertNotEqual(decision.verdict, "allow")

    def test_command_substitution_still_escalates(self):
        """コマンド置換 $() は展開されうるため従来どおり escalate を維持する。"""
        decision = workflow_gate.decide(
            'git commit -m "$(cat msg.txt)"', snapshot()
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_backtick_substitution_still_escalates(self):
        """バッククォート置換も従来どおり escalate を維持する。"""
        decision = workflow_gate.decide(
            'git commit -m "`cat msg.txt`"', snapshot()
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_unterminated_quote_with_multiline_content_escalates(self):
        """未終端引用符 + 改行は構造を確定できないため escalate に倒れる。"""
        decision = workflow_gate.decide(
            'git commit -m "unclosed\nbody', snapshot(current_branch="main")
        )
        self.assertEqual(decision.verdict, "escalate")


class RedirectedReadOnlyInterpretation(unittest.TestCase):
    """別リポジトリへ向けた git は、ゲート対象操作を含むときだけ止まる検証。

    -C / --git-dir / 向け直し環境変数つきの読み取り専用操作（log / status 等）が
    一律 escalate される偽陽性の再発防止。ゲートが守る遷移（commit / push /
    hooksPath / バイパスフラグ）を含む場合の escalate / deny は従来どおり。
    """

    def test_redirected_log_allows(self):
        decision = workflow_gate.decide(
            "git -C /home/mizumi/develop/other-repo log --oneline -- .agents/ | head -3",
            snapshot(),
        )
        self.assertEqual(decision.verdict, "allow")
        self.assertEqual(decision.reason, "")

    def test_redirected_status_allows(self):
        decision = workflow_gate.decide("git -C /other/repo status", snapshot())
        self.assertEqual(decision.verdict, "allow")

    def test_env_redirected_log_allows(self):
        decision = workflow_gate.decide("GIT_DIR=/x/.git git log", snapshot())
        self.assertEqual(decision.verdict, "allow")

    def test_redirected_commit_still_escalates(self):
        decision = workflow_gate.decide(
            "git -C /other/repo commit -m x", snapshot()
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_redirected_push_still_escalates(self):
        decision = workflow_gate.decide("git -C /other/repo push", snapshot())
        self.assertEqual(decision.verdict, "escalate")

    def test_env_redirected_commit_still_escalates(self):
        decision = workflow_gate.decide(
            "GIT_WORK_TREE=/x git commit -m y", snapshot()
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_redirected_push_with_no_verify_denies(self):
        decision = workflow_gate.decide(
            "git -C /other/repo push --no-verify", snapshot()
        )
        self.assertEqual(decision.verdict, "deny")

    def test_redirected_hookspath_config_still_escalates(self):
        decision = workflow_gate.decide(
            "git -C /other/repo config core.hooksPath /tmp/hooks", snapshot()
        )
        self.assertEqual(decision.verdict, "escalate")


class AdversarialBypassAttempts(unittest.TestCase):
    """回避を試みる呼び出し形が allow に到達しないことの検証（レビュー実証攻撃由来）。"""

    def test_absolute_path_git_is_still_gated(self):
        """絶対パス経由の git 呼び出し（/usr/bin/git）もゲート対象になる。"""
        decision = workflow_gate.decide(
            "/usr/bin/git push origin main", snapshot(trunk_config_text=None)
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_quote_split_git_word_is_still_gated(self):
        """クォート分割（g\"i\"t）で綴りを崩した git 呼び出しもゲート対象になる。"""
        decision = workflow_gate.decide(
            'g"i"t commit -m x', snapshot(current_branch="main")
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_hash_inside_word_does_not_truncate_analysis(self):
        """語中の # で解析が打ち切られず、後続のバイパスフラグを見逃さない。"""
        decision = workflow_gate.decide(
            "git commit -m fix#123 --no-verify", snapshot()
        )
        self.assertEqual(decision.verdict, "deny")

    def test_abbreviated_no_verify_denies(self):
        """--no-verify の一意省略形（--no-verif 等）も deny になる。"""
        for command in ("git commit --no-verif -m x", "git push --no-veri"):
            decision = workflow_gate.decide(command, snapshot())
            self.assertEqual(decision.verdict, "deny", command)

    def test_short_flag_cluster_with_uppercase_denies(self):
        """大文字フラグ混在の短縮束（-nF 等）に含まれる -n も deny になる。"""
        decision = workflow_gate.decide("git commit -nF msg.txt", snapshot())
        self.assertEqual(decision.verdict, "deny")

    def test_repo_redirected_git_escalates(self):
        """-C / --git-dir で別リポジトリへ向けた git 書き込みはスナップショットと
        対応しないため escalate に倒れる。"""
        for command in (
            "git -C /tmp/elsewhere commit -m x",
            "git --git-dir=/tmp/b/.git commit -m x",
        ):
            decision = workflow_gate.decide(command, snapshot())
            self.assertEqual(decision.verdict, "escalate", command)

    def test_cd_before_git_write_escalates(self):
        """cd で作業場所を変えた後の git 書き込みは判定基盤とずれるため escalate。"""
        decision = workflow_gate.decide(
            "cd /tmp/b && git commit -m x", snapshot()
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_unknown_default_branch_escalates_commit(self):
        """default branch を特定できない環境での commit は allow に倒れない。"""
        decision = workflow_gate.decide(
            "git commit -m x", snapshot(current_branch="develop", default_branch=None)
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_bypass_flag_in_uninterpretable_structure_still_denies(self):
        """解釈不能な構造の中でもバイパスフラグの証拠があれば deny が escalate に弱まらない。"""
        for command in (
            "(git commit --no-verify -m x)",
            "GIT_TRACE=1 git commit --no-verify -m x",
            "git commit --no-verify -m 'a\nb'",
        ):
            decision = workflow_gate.decide(command, snapshot(current_branch="main"))
            self.assertEqual(decision.verdict, "deny", repr(command))

    def test_hooks_path_evidence_in_any_form_never_allows(self):
        """core.hooksPath への言及を伴う git コマンドはいかなる形でも allow にならない。"""
        cases = {
            "git -ccore.hooksPath=/dev/null commit -m x": "deny",
            "git --config-env=core.hooksPath=EVIL push": "deny",
        }
        for command, expected in cases.items():
            decision = workflow_gate.decide(command, snapshot())
            self.assertEqual(decision.verdict, expected, command)

    def test_persistent_hooks_path_reconfiguration_escalates(self):
        """git config による恒久的な hooksPath 変更は人間確認（escalate）になる。"""
        decision = workflow_gate.decide(
            "git config core.hooksPath githooks", snapshot()
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_touching_repo_hook_directory_escalates(self):
        """リポジトリのフックディレクトリ（.git/hooks）へ触るコマンドは escalate になる。"""
        decision = workflow_gate.decide(
            "rm .git/hooks/pre-push", snapshot()
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_quote_split_hook_directory_touch_is_still_gated(self):
        """クォート分割（.gi"t/hooks"）で綴りを崩したフックディレクトリ接触もゲート対象になる。"""
        decision = workflow_gate.decide(
            'rm .gi"t/hooks/pre-push"', snapshot()
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_quoted_git_write_phrase_under_arg_executing_head_still_escalates(self):
        """引数を実行しうるコマンドへ渡されたクォート済み git 書き込み句は escalate のまま。"""
        for command in (
            'parallel "git push" ::: 1',
            'tmux send-keys "git push" Enter',
            "python3 -c \"import os; os.system('git push')\"",
            'awk \'BEGIN{system("git push")}\' /dev/null',
        ):
            decision = workflow_gate.decide(command, snapshot())
            self.assertEqual(decision.verdict, "escalate", command)

    def test_gate_self_invocation_with_command_substitution_still_escalates(self):
        """ゲート自身の記録コマンドでも、コマンド置換を含む形は解釈不能のまま素通ししない。"""
        decision = workflow_gate.decide(
            "python3 workflow_gate.py --record-amnesty --gate push_evidence "
            '--gate-command "$(git push)" --reason r --grounds g',
            snapshot(),
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_gate_script_name_in_argument_position_does_not_lift_the_gate(self):
        """引数実行コマンドに workflow_gate.py の語を紛れ込ませてもゲートは緩まない。"""
        decision = workflow_gate.decide(
            'tmux send-keys "git push" Enter workflow_gate.py --decide', snapshot()
        )
        self.assertEqual(decision.verdict, "escalate")

    def test_reconfig_phrase_does_not_suppress_override_deny(self):
        """恒久再設定の語句が同居しても、-c core.hooksPath= 上書きの deny は弱まらない。"""
        decision = workflow_gate.decide(
            "git config core.hooksPath .githooks\n"
            "git -c core.hooksPath=/dev/null commit -m x",
            snapshot(),
        )
        self.assertEqual(decision.verdict, "deny")

    def test_bypass_flag_wins_over_hook_directory_escalation(self):
        """バイパスフラグとフックディレクトリ操作が同居しても deny が escalate に弱まらない。"""
        decision = workflow_gate.decide(
            "git commit --no-verify -m x && rm .git/hooks/pre-push", snapshot()
        )
        self.assertEqual(decision.verdict, "deny")

    def test_env_var_repo_redirect_escalates(self):
        """GIT_DIR / GIT_WORK_TREE の環境変数向け直しはフラグ形（-C 等）と同じく escalate。"""
        for command in (
            "GIT_DIR=/tmp/elsewhere git commit -m 'x'",
            "GIT_WORK_TREE=/tmp/elsewhere git commit -m 'x'",
            "export GIT_DIR=/tmp/elsewhere && git commit -m 'x'",
        ):
            decision = workflow_gate.decide(command, snapshot())
            self.assertEqual(decision.verdict, "escalate", command)

    def test_env_var_hooks_path_override_denies(self):
        """GIT_CONFIG_* 環境変数による core.hooksPath 上書きは -c 形と同じく deny。"""
        decision = workflow_gate.decide(
            "GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=/dev/null "
            "GIT_CONFIG_COUNT=1 git commit -m 'x'",
            snapshot(),
        )
        self.assertEqual(decision.verdict, "deny")


class FalsePositiveBounds(unittest.TestCase):
    """保守的判定の誤検知が無害なデータ位置の git にまで広がらないことの検証。"""

    def test_commit_message_mentioning_git_push_is_not_reinterpreted(self):
        """コミットメッセージ内の 'git push' 文字列は判定を変えない。"""
        decision = workflow_gate.decide(
            'git commit -m "see git push docs"', snapshot()
        )
        self.assertEqual(decision.verdict, "allow")

    def test_commit_message_mentioning_bypass_flag_is_not_a_bypass(self):
        """解釈可能なコマンドでは、メッセージ引数内の --no-verify 言及は deny にならない。"""
        decision = workflow_gate.decide(
            'git commit -m "fix: deny the --no-verify flag"', snapshot()
        )
        self.assertEqual(decision.verdict, "allow")

    def test_searching_for_hooks_path_is_not_a_bypass(self):
        """core.hooksPath を検索するだけの読み取りコマンドは deny にならない。"""
        decision = workflow_gate.decide("git grep core.hooksPath", snapshot())
        self.assertEqual(decision.verdict, "allow")

    def test_echo_of_git_word_without_write_op_allows(self):
        """書き込み操作を伴わない git の語のデータ利用（echo 等）は allow のまま。"""
        decision = workflow_gate.decide('echo "see git log"', snapshot())
        self.assertEqual(decision.verdict, "allow")

    def test_shell_indirection_with_git_escalates(self):
        """シェル間接実行（sh -c / eval）に git の語があれば escalate に倒す。"""
        for command in ("sh -c 'git status'", "eval git push"):
            decision = workflow_gate.decide(command, snapshot())
            self.assertEqual(decision.verdict, "escalate", command)

    def test_common_bare_global_options_do_not_escalate(self):
        """読み取り専用の一般的なグローバルオプションは escalate を生まない。"""
        for command in ("git --version", "git --no-optional-locks status"):
            decision = workflow_gate.decide(command, snapshot())
            self.assertEqual(decision.verdict, "allow", command)

    def test_text_search_and_display_arguments_with_git_write_phrase_allow(self):
        """テキスト検索・表示コマンドの引数内の git 書き込み句は判定を変えない。"""
        for command in (
            'grep -rn "git push" README.md',
            'echo "then git push"',
            'printf "%s" "git commit"',
            'cat "notes about git push.md"',
        ):
            decision = workflow_gate.decide(command, snapshot())
            self.assertEqual(decision.verdict, "allow", command)

    def test_path_fragment_joining_git_and_commit_is_not_a_write(self):
        """URL・パス断片（.../git/commit/...）は git 書き込みの証拠にならない。"""
        decision = workflow_gate.decide(
            "curl https://example.com/git/commit/abc123", snapshot()
        )
        self.assertEqual(decision.verdict, "allow")

    def test_benign_git_env_assignments_do_not_gate(self):
        """向け直しではない環境変数前置（GIT_AUTHOR_NAME / PAGER 等）は判定を変えない。"""
        for command in (
            "GIT_AUTHOR_NAME=bot git commit -m 'x'",
            "PAGER=cat git log",
        ):
            decision = workflow_gate.decide(command, snapshot())
            self.assertEqual(decision.verdict, "allow", command)

    def test_amnesty_recording_command_itself_passes_the_gate(self):
        """恩赦記録コマンド自身は引数に git 書き込み句を含んでいても再エスカレートしない。"""
        command = (
            "python3 skills/shared/scripts/workflow_gate.py --record-amnesty "
            "--gate push_evidence --gate-command 'git push origin feature/x' "
            "--reason 'escalated: evidence absent' --grounds 'human approved after review'"
        )
        decision = workflow_gate.decide(command, snapshot())
        self.assertEqual(decision.verdict, "allow")

    def test_doc_alignment_recording_command_itself_passes_the_gate(self):
        """doc 整合記録コマンド自身は grounds に git の語を含んでいても再エスカレートしない。"""
        command = (
            "python3 skills/shared/scripts/workflow_gate.py --record-doc-alignment "
            "--grounds 'doc-check run over git push docs: no drift'"
        )
        decision = workflow_gate.decide(command, snapshot())
        self.assertEqual(decision.verdict, "allow")


class PardonDiscoverability(unittest.TestCase):
    """escalate 理由文が恩赦の記録手段まで案内する（台帳に実データが集まる配線）。"""

    def test_main_commit_escalation_names_the_amnesty_recording_command(self):
        """main 直コミットの escalate 理由文は恩赦記録コマンドと gate 名を案内する。"""
        decision = workflow_gate.decide(
            "git commit -m 'x'", snapshot(current_branch="main")
        )
        self.assertEqual(decision.verdict, "escalate")
        self.assertIn("--record-amnesty", decision.reason)
        self.assertIn("main_commit", decision.reason)

    def test_push_evidence_escalation_names_the_amnesty_recording_command(self):
        """evidence 不備の escalate 理由文は恩赦記録コマンドと gate 名を案内する。"""
        decision = workflow_gate.decide(
            "git push origin feature/x",
            snapshot(trunk_config_text=TRUNK_ADOPTED, evidence_exit=1),
        )
        self.assertEqual(decision.verdict, "escalate")
        self.assertIn("--record-amnesty", decision.reason)
        self.assertIn("push_evidence", decision.reason)

    def test_doc_alignment_escalation_names_the_amnesty_recording_command(self):
        """doc 整合不備の escalate 理由文も恩赦記録コマンドを案内する。"""
        decision = workflow_gate.decide(
            "git push origin feature/x",
            snapshot(trunk_config_text=TRUNK_ADOPTED, evidence_exit=0),
        )
        self.assertEqual(decision.verdict, "escalate")
        self.assertIn("--record-amnesty", decision.reason)


class EvidenceReasonTransparency(unittest.TestCase):
    def test_push_escalation_reason_carries_the_verifier_report(self):
        """push の escalate 理由文は検証器の報告（何を検査しどう落ちたか）を運ぶ。"""
        decision = workflow_gate.decide(
            "git push origin feature/x",
            snapshot(
                trunk_config_text=TRUNK_ADOPTED,
                evidence_exit=1,
                evidence_report="machine_verified: NG (absent)\nsemantic_reviewed: NG (absent)",
            ),
        )
        self.assertEqual(decision.verdict, "escalate")
        self.assertIn("machine_verified: NG (absent)", decision.reason)


class NonGitCommands(unittest.TestCase):
    def test_non_git_commands_allow_with_no_output(self):
        """git 以外のコマンドは常に allow で、判定コアが何も出力しない。"""
        for command in (
            "ls -la",
            "python3 -m unittest",
            "echo digital gitignore",  # 'git' を部分文字列として含むが git 呼び出しではない
            "cat .gitignore",
        ):
            decision = workflow_gate.decide(command, snapshot())
            self.assertEqual(decision.verdict, "allow", command)
            self.assertEqual(decision.reason, "", command)


class AmnestyRecords(unittest.TestCase):
    def test_amnesty_line_is_single_line_json_with_required_fields(self):
        """恩赦記録は必須フィールドを備えた 1 行 JSON になる。"""
        line = workflow_gate.format_amnesty_line(
            gate="main_commit",
            command="git commit -m 'x'",
            reason="escalated: direct commit on main",
            grounds="human approved a hotfix on main",
            recorded_at="2026-08-09T12:00:00Z",
        )
        self.assertNotIn("\n", line)
        record = json.loads(line)
        self.assertEqual(record["gate"], "main_commit")
        self.assertEqual(record["recorded_at"], "2026-08-09T12:00:00Z")
        self.assertTrue(record["command"])
        self.assertTrue(record["reason"])
        self.assertTrue(record["grounds"])

    def test_amnesty_without_grounds_is_rejected(self):
        """grounds の無い恩赦は記録として成立しない（Iron Law）。"""
        with self.assertRaises(ValueError):
            workflow_gate.format_amnesty_line(
                gate="main_commit",
                command="git commit",
                reason="r",
                grounds="   ",
                recorded_at="2026-08-09T12:00:00Z",
            )

    def test_amnesty_with_unknown_gate_is_rejected(self):
        """判定表に無い gate 値の恩赦は記録として成立しない。"""
        with self.assertRaises(ValueError):
            workflow_gate.format_amnesty_line(
                gate="somewhere_else",
                command="git commit",
                reason="r",
                grounds="g",
                recorded_at="2026-08-09T12:00:00Z",
            )

    def test_amnesty_ledger_supports_counting_by_gate(self):
        """追記された台帳は gate 別の件数集計が機械的にできる。"""
        lines = [
            workflow_gate.format_amnesty_line(
                gate=gate,
                command="c",
                reason="r",
                grounds="g",
                recorded_at="2026-08-09T12:00:00Z",
            )
            for gate in ("main_commit", "push_evidence", "main_commit")
        ]
        ledger = "\n".join(lines) + "\n"
        counts = {}
        for line in ledger.splitlines():
            gate = json.loads(line)["gate"]
            counts[gate] = counts.get(gate, 0) + 1
        self.assertEqual(counts, {"main_commit": 2, "push_evidence": 1})


class AmnestyCli(unittest.TestCase):
    def test_record_amnesty_appends_to_the_decisions_ledger(self):
        """CLI の恩赦記録は decisions 台帳へ 1 行ずつ追記される。"""
        root = tempfile.mkdtemp()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", root], check=False))
        for grounds in ("first approval", "second approval"):
            result = subprocess.run(
                [
                    sys.executable,
                    SCRIPT,
                    "--record-amnesty",
                    "--gate",
                    "push_evidence",
                    "--gate-command",
                    "git push",
                    "--reason",
                    "escalated: no evidence",
                    "--grounds",
                    grounds,
                ],
                capture_output=True,
                text=True,
                cwd=root,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        ledger_path = os.path.join(
            root, ".agents", "artifacts", "decisions", "workflow-gate-amnesties.jsonl"
        )
        with open(ledger_path, encoding="utf-8") as handle:
            lines = [line for line in handle.read().splitlines() if line]
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[1])["grounds"], "second approval")

    def test_record_amnesty_from_subdirectory_lands_at_repo_root(self):
        """サブディレクトリから記録した恩赦もリポジトリ根の台帳へ追記される。"""
        root = tempfile.mkdtemp()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", root], check=False))
        env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null")
        subprocess.run(["git", "init", "-q", "-b", "main", root], check=True, env=env)
        subdir = os.path.join(root, "src")
        os.makedirs(subdir)
        result = subprocess.run(
            [
                sys.executable,
                SCRIPT,
                "--record-amnesty",
                "--gate",
                "main_commit",
                "--gate-command",
                "git commit",
                "--reason",
                "escalated",
                "--grounds",
                "approved from subdir",
            ],
            capture_output=True,
            text=True,
            cwd=subdir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        root_ledger = os.path.join(
            root, ".agents", "artifacts", "decisions", "workflow-gate-amnesties.jsonl"
        )
        self.assertTrue(os.path.exists(root_ledger))
        self.assertFalse(os.path.exists(os.path.join(subdir, ".agents")))

    def test_record_amnesty_refuses_groundless_records(self):
        """grounds を欠く恩赦記録の依頼は非 0 で拒否され、台帳に書かれない。"""
        root = tempfile.mkdtemp()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", root], check=False))
        result = subprocess.run(
            [
                sys.executable,
                SCRIPT,
                "--record-amnesty",
                "--gate",
                "push_evidence",
                "--gate-command",
                "git push",
                "--reason",
                "escalated",
                "--grounds",
                "",
            ],
            capture_output=True,
            text=True,
            cwd=root,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(
            os.path.exists(os.path.join(root, ".agents", "artifacts", "decisions"))
        )


class DecideCliMode(unittest.TestCase):
    """--decide モード: フック機構を持つ任意の環境から呼べる機械可読出力。"""

    def test_decide_mode_reports_verdict_and_reason_as_json(self):
        """--decide はコマンド 1 本の判定を JSON（verdict + reason）で返す。"""
        root = tempfile.mkdtemp()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", root], check=False))
        result = subprocess.run(
            [sys.executable, SCRIPT, "--decide", "--gate-command", "ls -la"],
            capture_output=True,
            text=True,
            cwd=root,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads(result.stdout)
        self.assertEqual(record["verdict"], "allow")
        self.assertEqual(record["reason"], "")

    def test_decide_mode_denies_bypass_flags(self):
        """--decide でもバイパスフラグは deny + 理由文になる。"""
        root = tempfile.mkdtemp()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", root], check=False))
        result = subprocess.run(
            [
                sys.executable,
                SCRIPT,
                "--decide",
                "--gate-command",
                "git commit --no-verify -m x",
            ],
            capture_output=True,
            text=True,
            cwd=root,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads(result.stdout)
        self.assertEqual(record["verdict"], "deny")
        self.assertTrue(record["reason"])


class DocAlignmentProducer(unittest.TestCase):
    """--record-doc-alignment: doc 整合実施の証跡レコードを HEAD へバインドして生成する。"""

    def _make_repo(self):
        root = tempfile.mkdtemp()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", root], check=False))
        env = dict(
            os.environ,
            GIT_AUTHOR_NAME="t",
            GIT_AUTHOR_EMAIL="t@example.com",
            GIT_COMMITTER_NAME="t",
            GIT_COMMITTER_EMAIL="t@example.com",
            GIT_CONFIG_GLOBAL="/dev/null",
            GIT_CONFIG_SYSTEM="/dev/null",
        )
        subprocess.run(["git", "init", "-q", "-b", "main", root], check=True, env=env)
        subprocess.run(
            ["git", "-C", root, "commit", "-q", "--allow-empty", "-m", "init"],
            check=True,
            env=env,
        )
        return root

    def test_produced_record_is_valid_doc_alignment_evidence_for_head(self):
        """生成されたレコードは HEAD にバインドされ、ゲートの doc 整合検証を通る。"""
        root = self._make_repo()
        result = subprocess.run(
            [
                sys.executable,
                SCRIPT,
                "--record-doc-alignment",
                "--grounds",
                "doc-check branch run: no drift found",
            ],
            capture_output=True,
            text=True,
            cwd=root,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        record_path = os.path.join(
            root, ".agents", "artifacts", "reviews", "evidence", "doc_aligned.json"
        )
        with open(record_path, encoding="utf-8") as handle:
            text = handle.read()
        head = subprocess.run(
            ["git", "-C", root, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        env = snapshot(
            head_sha=head,
            doc_evidence_text=text,
            trunk_config_text=TRUNK_ADOPTED,
            evidence_exit=0,
        )
        decision = workflow_gate.decide("git push origin feature/x", env)
        self.assertEqual(decision.verdict, "allow")
        record = json.loads(text)
        self.assertEqual(record["state"], "doc_aligned")
        self.assertEqual(record["target_sha"], head)

    def test_producer_refuses_groundless_records(self):
        """grounds を欠く doc 整合レコードの生成依頼は非 0 で拒否される。"""
        root = self._make_repo()
        result = subprocess.run(
            [sys.executable, SCRIPT, "--record-doc-alignment", "--grounds", "  "],
            capture_output=True,
            text=True,
            cwd=root,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(
            os.path.exists(
                os.path.join(root, ".agents", "artifacts", "reviews", "evidence")
            )
        )


class CliAdapter(unittest.TestCase):
    """CLI ラッパの結線検証。環境スナップショットは一時 git リポジトリから収集される。"""

    def _make_repo(self, branch):
        root = tempfile.mkdtemp()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", root], check=False))
        env = dict(
            os.environ,
            GIT_AUTHOR_NAME="t",
            GIT_AUTHOR_EMAIL="t@example.com",
            GIT_COMMITTER_NAME="t",
            GIT_COMMITTER_EMAIL="t@example.com",
            # 開発者のグローバル git 設定（core.hooksPath / commit.gpgsign 等）から隔離する
            GIT_CONFIG_GLOBAL="/dev/null",
            GIT_CONFIG_SYSTEM="/dev/null",
        )
        subprocess.run(
            ["git", "init", "-q", "-b", "main", root], check=True, env=env
        )
        subprocess.run(
            ["git", "-C", root, "commit", "-q", "--allow-empty", "-m", "init"],
            check=True,
            env=env,
        )
        if branch != "main":
            subprocess.run(
                ["git", "-C", root, "checkout", "-q", "-b", branch],
                check=True,
                env=env,
            )
        return root

    def _run_hook(self, root, command):
        payload = json.dumps(
            {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": root}
        )
        return subprocess.run(
            [sys.executable, SCRIPT, "--hook-io", "claude"],
            input=payload,
            capture_output=True,
            text=True,
            cwd=root,
        )

    def test_hook_adapter_stays_silent_for_conforming_commands(self):
        """規律に適合するコマンドではフック応答が空（発話ゼロ・exit 0）になる。"""
        root = self._make_repo("feature/x")
        result = self._run_hook(root, "git commit -m 'x'")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_hook_adapter_asks_human_for_default_branch_commit(self):
        """main 上の commit ではフック応答が人間確認（ask）+ 理由文になる。"""
        root = self._make_repo("main")
        result = self._run_hook(root, "git commit -m 'x'")
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        specific = output["hookSpecificOutput"]
        self.assertEqual(specific["permissionDecision"], "ask")
        self.assertTrue(specific["permissionDecisionReason"])

    def test_hook_adapter_denies_bypass_flags(self):
        """バイパスフラグではフック応答が deny + 理由文になる。"""
        root = self._make_repo("feature/x")
        result = self._run_hook(root, "git commit --no-verify -m 'x'")
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        specific = output["hookSpecificOutput"]
        self.assertEqual(specific["permissionDecision"], "deny")
        self.assertTrue(specific["permissionDecisionReason"])

    def test_hook_adapter_ignores_non_shell_tools(self):
        """シェル実行以外のツール呼び出しには何も応答しない。"""
        root = self._make_repo("main")
        payload = json.dumps(
            {"tool_name": "Read", "tool_input": {"file_path": "/x"}, "cwd": root}
        )
        result = subprocess.run(
            [sys.executable, SCRIPT, "--hook-io", "claude"],
            input=payload,
            capture_output=True,
            text=True,
            cwd=root,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_hook_adapter_never_crashes_on_malformed_input(self):
        """壊れた入力でもフックはセッションを壊さない（非 0 で落ちない）。"""
        root = self._make_repo("feature/x")
        result = subprocess.run(
            [sys.executable, SCRIPT, "--hook-io", "claude"],
            input="not json at all",
            capture_output=True,
            text=True,
            cwd=root,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
