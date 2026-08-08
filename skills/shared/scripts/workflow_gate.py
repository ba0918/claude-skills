#!/usr/bin/env python3
"""Workflow gate — 幹ワークフローの遷移点をツール実行直前に守る判定コア + CLI アダプタ.

正本契約は skills/shared/references/workflow-gate.md（判定表・宣言ファイル形式・恩赦記録）。
判定コア decide() は pure function（コマンド文字列 + EnvSnapshot → Decision）で、
git 呼び出し・ファイル読みなどの I/O はすべて CLI アダプタ側から注入される。

3 値の意味:
  allow    = 素通し（発話ゼロ。理由文は常に空）
  escalate = 人間確認へ（理由文が破られた規律と正規の恩赦手順を案内する）
  deny     = 実行拒否（検査回避フラグ。理由文が just-in-time リマインダを兼ねる）

コマンド文字列は parse するだけで、評価・展開・実行は一切しない。
解釈できない構造（多重化・コマンド置換・シェル包み・別リポジトリへの向け直し）は
allow ではなく escalate に倒す。バイパスフラグの証拠は構造が解釈不能でも deny を保つ
（deny は escalate に弱化しない — 契約の "deny never degrades" 節）。
"""

import datetime
import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

TRUNK_CONFIG_RELPATH = os.path.join(".agents", "config", "trunk.yml")

# 単語としての git（digital / .gitignore / gitk / git-lfs 等の部分一致を除外しつつ、
# /usr/bin/git のようなパス経由の呼び出しは対象に含める）
_GIT_WORD = re.compile(r"(?<![\w.-])git(?![\w.-])")
# --no-verify とその一意省略形（git は一意な長オプション省略を受理する。
# --no-verbose と衝突する --no-ve 以下の曖昧形は git 側がエラーにするため対象外）
_NO_VERIFY = re.compile(r"--no-veri(?:fy|f)?(?![\w-])")
# 構造解釈できたコマンドではトークン全体一致だけをバイパスとみなす
# （メッセージ引数内の言及を deny にしないため。deny は恩赦できない verdict）
_NO_VERIFY_TOKEN = re.compile(r"--no-veri(?:fy|f)?(?:=.*)?$")
# フック無効化系の設定キー（大文字小文字を git は区別しない）
_HOOKS_PATH = re.compile(r"core\.hookspath", re.IGNORECASE)
# 恒久的な再設定（git config core.hooksPath <値>）だけは deny でなく escalate に落とす:
# フック有効化の正当な設定操作でもありうるため、人間確認に回す
_HOOKS_PATH_RECONFIG = re.compile(
    r"git\s+config\s+(?:--\S+\s+)*core\.hookspath", re.IGNORECASE
)
# 解釈を打ち切る構造マーカー（コマンド置換 $( / バッククォート / プロセス置換 <( >( ）。
# プロセス置換 <(...) / >(...) の中身は実シェルが別プロセスとして実行するため、
# 内部に隠した書き込みを取りこぼさないよう解釈不能に倒す。改行は
# _split_unquoted_newlines が引用状態を追跡して構造改行だけを区切りに正規化するため
# 生文字列マーカーにしない（引用符内のデータ改行 = 複数行コミットメッセージまで
# 解釈不能扱いになる偽陽性を防ぐ）
_UNPARSEABLE_MARKERS = ("$(", "`", "<(", ">(")
# セグメント区切り（shlex punctuation_chars が生成する演算子トークン + サブシェル括弧）
_SEGMENT_DELIMITERS = {";", "&", "&&", "|", "||", ";;", "|&", "(", ")"}
# シェル間接実行の入口。この先の構造は解釈しない（escalate）
_INDIRECTION_COMMANDS = {
    "sh", "bash", "zsh", "dash", "ksh", "fish", "eval", "exec", "xargs", "env",
    "sudo", "doas", "command", "nohup", "nice", "setsid", "timeout", "watch", "script",
}
_ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# git の判定対象を別リポジトリ・別設定へ向け直す環境変数（フラグ形 -C / --git-dir /
# --work-tree と同じ向け直しクラス）。GIT_CONFIG* は core.hooksPath を運べるため同列。
# GIT_AUTHOR_NAME 等の無害な変数まで含めないよう、列挙 + GIT_CONFIG 接頭辞に限定する
_GIT_ENV_REDIRECTS = {
    "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CEILING_DIRECTORIES", "GIT_NAMESPACE",
}


def _is_env_redirect_assignment(token):
    name = token.split("=", 1)[0]
    return name in _GIT_ENV_REDIRECTS or name.startswith("GIT_CONFIG")
# git のグローバルオプションのうち、直後に値トークンを 1 つ取りうるもの
_GIT_GLOBAL_OPTS_WITH_VALUE = {"-c", "-C", "--git-dir", "--work-tree"}
# 別リポジトリへ判定対象を向け直すオプション（スナップショットと対応しなくなる）
_GIT_REPO_REDIRECT_OPTS = {"-C", "--git-dir", "--work-tree"}
# 純粋に情報取得のみで副作用を持たない git サブコマンド。コマンド置換
# $(...) 内でこれ単体のときだけ特例で allow に畳む対象（案A）。書き込みルートを
# 持つ config / branch / tag / reflog / stash 等は意図的に除外する（安全側）
_READONLY_GIT_SUBCOMMANDS = frozenset({
    "status", "log", "diff", "show", "merge-base", "rev-parse", "symbolic-ref",
    "describe", "show-ref", "rev-list", "for-each-ref", "ls-files", "ls-tree",
    "cat-file", "name-rev", "shortlog", "whatchanged", "blame", "ls-remote",
})
# 安全と証明できた read-only git 置換を畳んだ後に残すプレースホルダ（git の語を
# 含まない通常の識別子。以降のフローでは単なる代入値トークンとして扱われる）
_SAFE_SUBST_PLACEHOLDER = "__gate_readonly_subst__"
# read-only サブコマンドでも外部コマンド実行を誘発しうるフラグ。事前設定された
# diff.external / textconv / pager を発火させたり、値に直接コマンドを取る。
# これらを引数に持つ置換は畳まない（Codex 敵対レビューで diff.external 経由の
# gated write 秘匿を実証）
_EXTERNAL_EXEC_FLAG = re.compile(
    r"^(--ext-diff|--textconv|--open-files-in-pager|-O.+|"
    r"--upload-pack(=.*)?|--exec(=.*)?|--receive-pack(=.*)?)$"
)
_GIT_GLOBAL_OPTS_BARE = {
    "--no-pager", "-P", "--paginate", "-p", "--no-replace-objects", "--version",
    "--help", "--html-path", "--man-path", "--info-path", "--exec-path", "--bare",
    "--no-optional-locks", "--literal-pathspecs", "--glob-pathspecs",
    "--noglob-pathspecs", "--icase-pathspecs", "--no-lazy-fetch", "--no-advice",
}
# commit の短縮フラグ束に紛れた -n（--no-verify の短縮形）。大文字フラグ混在も対象
_SHORT_N_CLUSTER = re.compile(r"-[A-Za-z]*n[A-Za-z]*")
# 単一トークン内の git 書き込み句（クォート済み引数に埋まった "git push" 等）。
# 区切り文字から / を除くのは、URL・パス断片（.../git/commit/<sha>）を書き込みの
# 証拠にしないため — スラッシュだけで連結された git/push はファイルパスであり、
# どのシェル・ラッパも git サブコマンドの起動としては解釈しない
_IN_TOKEN_WRITE = re.compile(r"git[^A-Za-z0-9_/]+(commit|push)(?![\w-])")
# 引数を実行しないテキスト処理・表示コマンド。この head の引数はデータであり、
# git の語・書き込み句を含んでも人間確認を発生させない。
# rg（--pre）・sed（GNU の e）・awk（system()）・find（-exec）は引数から外部
# コマンドを起動する経路を持つため意図的に載せない — 追加は経路の不在を確認してから
_DATA_SINK_COMMANDS = {"echo", "printf", "grep", "cat"}
# ゲート自身の CLI（恩赦・doc 整合の記録、判定出力）。判定対象コマンドを引数に運ぶ
_GATE_SCRIPT_BASENAME = "workflow_gate.py"
_GATE_SELF_MODES = {"--record-amnesty", "--record-doc-alignment", "--decide"}

_TRUNK_VALUES = {"adopted", "not_adopted"}
_BOOL_VALUES = {"true": True, "false": False}
_INVALID = object()  # 宣言ファイル内の「未知の値」を表す番兵（未宣言と同じ扱いに落とす）


@dataclass(frozen=True)
class EnvSnapshot:
    """判定に必要な環境の読み取り結果。収集（I/O）は呼び出し側の責務。"""

    current_branch: Optional[str]  # None = 特定不能（detached 等）
    default_branch: Optional[str]  # None = 特定不能
    trunk_config_text: Optional[str]  # None = 宣言ファイル不在
    evidence_exit: Optional[int]  # evidence_check.py の exit code。None = 未収集
    head_sha: Optional[str] = None  # 現在の HEAD（full 40-hex）。None = 特定不能
    doc_evidence_text: Optional[str] = None  # doc_aligned.json の生テキスト。None = 不在
    evidence_report: Optional[str] = None  # 検証器の報告テキスト（escalate 理由文に載せる）


@dataclass(frozen=True)
class Decision:
    verdict: str  # "allow" | "escalate" | "deny"
    reason: str  # allow のときは常に ""


@dataclass(frozen=True)
class CommandAnalysis:
    has_git: bool
    uninterpretable: bool
    bypass_reasons: tuple
    operations: tuple  # ("commit" | "push") の列
    escalate_reasons: tuple = ()  # バイパス以外で人間確認が要る構文上の根拠


def parse_trunk_config(text):
    """宣言ファイル本文 → {key: value} / None（構文として読めない）。

    未知のキーは無視、未知の値は _INVALID（未宣言と同等 = 安全側）に落とす。
    意図的に YAML の部分集合（`key: value` 行とコメントのみ）しか読まない —
    それ以外の YAML 構文は「読めない宣言」として escalate 側に倒れる。
    """
    result = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(\S+)$", line)
        if match is None:
            return None
        key, value = match.groups()
        if key == "trunk":
            result["trunk"] = value if value in _TRUNK_VALUES else _INVALID
        elif key == "allow_main_commit":
            result["allow_main_commit"] = _BOOL_VALUES.get(value, _INVALID)
    return result


def _is_git_token(token):
    """トークンが git 本体の呼び出しか（素の git / パス経由の git）。"""
    return token == "git" or (token.rsplit("/", 1)[-1] == "git" and "/" in token)


def _is_gate_self_invocation(body):
    """セグメントがゲート自身の記録・判定 CLI の呼び出しか。

    恩赦・doc 整合の記録コマンドは判定対象コマンド（"git push" 等）を引数に運ぶため、
    引数内 git 句の検出から除外しないと記録フローがゲートと自己衝突する。
    スクリプト名を引数位置へ紛れ込ませた形（他コマンドの引数末尾に付け足す等）で
    ゲートが緩まないよう、コマンド位置（先頭、または python 起動の直後）にある
    場合だけ自己呼び出しとみなす。
    """
    def basename(token):
        return token.rsplit("/", 1)[-1]

    if basename(body[0]) == _GATE_SCRIPT_BASENAME:
        script_in_command_position = True
    else:
        script_in_command_position = (
            basename(body[0]).startswith("python")
            and len(body) > 1
            and basename(body[1]) == _GATE_SCRIPT_BASENAME
        )
    return script_in_command_position and any(
        token in _GATE_SELF_MODES for token in body
    )


def _tokenize(command):
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    # bash は語中の # をコメントにしないが shlex 既定は行末まで捨てる。
    # コメント扱いを無効化しないと `-m fix#123 --no-verify` の後続フラグを見逃す
    lexer.commenters = ""
    return list(lexer)


def _split_unquoted_newlines(command):
    """引用状態を追跡し、構造改行（unquoted \\n）だけを `;` 区切りへ正規化する。

    - 引用符の中の改行はデータとして保持する（shlex がそのままトークンに含める）
    - バックスラッシュ + 改行は行継続なので除去して結合する（分断された語や
      サブコマンドが再構成され、検出がむしろ強くなる）
    - 未終端の引用符は構造を確定できないため None を返す（呼び出し側で
      トークン化不能と同じ保守分岐に落とす）
    """
    out = []
    state = "normal"  # normal | single | double
    i = 0
    n = len(command)
    while i < n:
        ch = command[i]
        if state == "single":
            if ch == "'":
                state = "normal"
            out.append(ch)
            i += 1
            continue
        # normal / double 共通: バックスラッシュは次の 1 文字を伴う
        if ch == "\\":
            if i + 1 < n and command[i + 1] == "\n":
                i += 2  # 行継続: 両文字を除去して結合
                continue
            out.append(ch)
            if i + 1 < n:
                out.append(command[i + 1])
                i += 2
            else:
                i += 1
            continue
        if state == "normal":
            # bash 拡張クォート $'...'（ANSI-C）/ $"..."（ロケール）は、この単純な
            # quote-state 追跡では追えない（\' などのエスケープ規則が POSIX single/
            # double と異なり、状態がシェル実行とずれて改行の内外を誤判定しうる）。
            # 追えないものは解釈不能に倒す（None → 保守分岐 escalate、deny は生スキャンで維持）
            if ch == "$" and i + 1 < n and command[i + 1] in ("'", '"'):
                return None
            if ch == "'":
                state = "single"
            elif ch == '"':
                state = "double"
            elif ch == "\n":
                out.append(" ; ")
                i += 1
                continue
        else:  # double
            if ch == '"':
                state = "normal"
        out.append(ch)
        i += 1
    if state != "normal":
        return None
    return "".join(out)


def _scan_bypass_evidence(text):
    """解釈不能な構造に対する、生テキストレベルの回避フラグ証拠検出。

    構造を解釈できないときだけ使う（deny を escalate に弱めないための最終防衛線。
    解釈できたコマンドではトークン単位の検出が優先され、引数内の言及を deny にしない）。
    core.hooksPath は「恒久再設定（git config …）の形に含まれない出現が残るか」で
    判定する — 再設定の語句が同居していても、上書き形の出現が別にあれば deny を保つ。
    """
    reasons = []
    if _NO_VERIFY.search(text):
        reasons.append("--no-verify (or an unambiguous abbreviation) skips inspection hooks")
    reconfig_spans = [m.span() for m in _HOOKS_PATH_RECONFIG.finditer(text)]
    for match in _HOOKS_PATH.finditer(text):
        covered = any(
            start <= match.start() and match.end() <= end
            for start, end in reconfig_spans
        )
        if not covered:
            reasons.append("a core.hooksPath override disables repository hooks")
            break
    return reasons


def _analyze_git_segment(tokens):
    """git に続くトークン列 → (bypass, operations, uninterpretable, escalate_reasons)."""
    bypass = []
    operations = []
    escalates = []
    redirected = False
    index = 0
    while index < len(tokens) and tokens[index].startswith("-"):
        token = tokens[index]
        name = token.split("=", 1)[0]
        if name in _GIT_REPO_REDIRECT_OPTS:
            # 判定スナップショット（cwd のブランチ・宣言・証跡）と対応しない。
            # ただし即 bail せずサブコマンドまで読み、ゲート対象操作を含むとき
            # だけ解釈不能に倒す（読み取り系まで一律 escalate しない）
            redirected = True
        if name in _GIT_GLOBAL_OPTS_WITH_VALUE:
            value = token.split("=", 1)[1] if "=" in token else (
                tokens[index + 1] if index + 1 < len(tokens) else ""
            )
            if name == "-c" and _HOOKS_PATH.match(value.split("=", 1)[0]):
                bypass.append(
                    "hook-path override (-c core.hooksPath=...) disables repository hooks"
                )
            index += 1 if "=" in token else 2
        elif name in _GIT_GLOBAL_OPTS_BARE:
            index += 1
        else:
            # 未知のグローバルオプション: サブコマンドの特定を諦め、安全側へ
            return tuple(bypass), (), True, ()
    if index >= len(tokens):
        return tuple(bypass), (), False, ()
    subcommand = tokens[index]
    rest = tokens[index + 1 :]
    if "--" in rest:  # pathspec 区切り以降はフラグではない
        rest = rest[: rest.index("--")]
    # --no-verify はフック検査を持つサブコマンド全般（commit / push / merge 等）で
    # 回避フラグになるため、サブコマンドを限定せずフラグ位置のトークンだけを見る
    for token in rest:
        if _NO_VERIFY_TOKEN.match(token):
            bypass.append(
                "--no-verify (or an unambiguous abbreviation) skips inspection hooks"
            )
    if subcommand == "commit":
        operations.append("commit")
        for token in rest:
            if _SHORT_N_CLUSTER.fullmatch(token):
                bypass.append("-n (--no-verify) skips commit inspection hooks")
    elif subcommand == "push":
        operations.append("push")
    elif subcommand == "config":
        if any(token.lower().startswith("core.hookspath") for token in rest):
            escalates.append(
                "persistent hook-path reconfiguration (git config core.hooksPath)"
            )
    if redirected:
        # 向け直し先の操作は cwd スナップショットの main / evidence 検査に流さない。
        # ゲート対象操作（commit / push）を含むときだけ解釈不能として人間確認へ、
        # hooksPath 再設定はそれ自身の理由文で escalate、それ以外は素通し
        return tuple(bypass), (), bool(operations), tuple(escalates)
    return tuple(bypass), tuple(operations), False, tuple(escalates)


def _first_git_subcommand(tokens):
    """グローバルオプションを飛ばした最初の非オプション語（サブコマンド）を返す。

    未知オプションや到達できない場合は None（呼び出し側で不採用に倒す）。
    """
    index = 0
    while index < len(tokens) and tokens[index].startswith("-"):
        name = tokens[index].split("=", 1)[0]
        if name in _GIT_GLOBAL_OPTS_WITH_VALUE:
            index += 1 if "=" in tokens[index] else 2
        elif name in _GIT_GLOBAL_OPTS_BARE:
            index += 1
        else:
            return None
    if index >= len(tokens):
        return None
    return tokens[index]


def _readonly_substitution_span(command, dollar_idx):
    """`$(` の対応閉じ括弧の index と、本体にネスト `(` があったかを返す。

    quote 状態を追い、引用符内の括弧は数えない。閉じ括弧が見つからなければ
    (None, nested)。ネストがあれば呼び出し側は畳まない（安全側）。
    """
    depth = 1
    i = dollar_idx + 2
    n = len(command)
    state = "normal"
    nested = False
    while i < n:
        ch = command[i]
        if state == "single":
            if ch == "'":
                state = "normal"
        elif state == "double":
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == '"':
                state = "normal"
        else:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == "'":
                state = "single"
            elif ch == '"':
                state = "double"
            elif ch == "(":
                depth += 1
                nested = True
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return i, nested
        i += 1
    return None, nested


def _is_safe_readonly_git_body(body):
    """置換本体が read-only git 単一コマンドで、ゲート対象操作を含まないか。

    案A の受理条件（Codex 敵対レビューで抜けなしを確認）:
    バッククォート / プロセス置換 / 拡張クォート / ネスト置換 / コマンド区切りを
    含まず、先頭 env 代入（向け直しは不可）を除いた本体が git で、
    `_analyze_git_segment` が全クリーンを返し、サブコマンドが read-only allowlist。
    """
    if "`" in body or "<(" in body or ">(" in body:
        return False
    if "$'" in body or '$"' in body or "$(" in body:
        return False
    rewritten = _split_unquoted_newlines(body)
    if rewritten is None:
        return False
    try:
        tokens = _tokenize(rewritten)
    except ValueError:
        return False
    if any(t in _SEGMENT_DELIMITERS for t in tokens):
        return False
    start = 0
    while start < len(tokens) and _ENV_ASSIGNMENT.match(tokens[start]):
        if _is_env_redirect_assignment(tokens[start]):
            return False
        start += 1
    body_tokens = tokens[start:]
    if not body_tokens or not _is_git_token(body_tokens[0]):
        return False
    rest = body_tokens[1:]
    # グローバルオプション（git とサブコマンドの間の - トークン）を持つ形は畳まない。
    # とくに -c / --config-env は diff.external / core.pager / *.textconv 等の
    # 任意 config を注入でき、read-only サブコマンドでも外部コマンド実行に化ける
    if rest and rest[0].startswith("-"):
        return False
    # サブコマンド後の引数に外部実行を誘発するフラグを持つ形も畳まない
    if any(_EXTERNAL_EXEC_FLAG.match(token) for token in rest):
        return False
    seg_bypass, seg_ops, seg_broken, seg_escalates = _analyze_git_segment(rest)
    if seg_bypass or seg_ops or seg_broken or seg_escalates:
        return False
    return _first_git_subcommand(rest) in _READONLY_GIT_SUBCOMMANDS


def _fold_safe_readonly_git_substitutions(command):
    """安全な read-only git 置換だけをプレースホルダへ畳む（他は原文のまま残す）。

    畳めない置換（write git / 複数コマンド / ネスト / バイパス等）は `$(` を
    残すため、後段で従来どおり解釈不能 → escalate / deny に倒れる。deny 証拠を
    畳んで消すことはない（畳む対象は _analyze_git_segment が全クリーンのものだけ）。
    """
    if "$(" not in command:
        return command
    out = []
    i = 0
    n = len(command)
    while i < n:
        idx = command.find("$(", i)
        if idx == -1:
            out.append(command[i:])
            break
        out.append(command[i:idx])
        end, nested = _readonly_substitution_span(command, idx)
        if end is None:
            out.append(command[idx:])
            break
        body = command[idx + 2:end]
        # コマンド位置（行頭 / セグメント区切り直後）の置換は、出力そのものが
        # コマンドとして実行される。read-only でも --format 等で任意文字列を
        # 出力させ得るため畳まない（代入値・引数位置の置換だけを畳む）
        j = idx - 1
        while j >= 0 and command[j] in " \t":
            j -= 1
        at_command_position = j < 0 or command[j] in ";&|(`{\n"
        if not at_command_position and not nested and _is_safe_readonly_git_body(body):
            out.append(_SAFE_SUBST_PLACEHOLDER)
        else:
            out.append(command[idx:end + 1])
        i = end + 1
    return "".join(out)


def analyze_command(command):
    """コマンド文字列の保守的な構文解析（評価・展開はしない）。"""
    # フックディレクトリへ触る操作は git の語の有無に関わらず人間確認へ
    # （バイパスフラグと同居した場合は後段の deny 優先が生きるよう、ここでは
    # 早期 return せずフラグとして持ち回る）
    hooks_dir_touch = ".git/hooks" in command
    hooks_dir_reason = "the command touches the repository hook directory"
    raw_has_git = bool(_GIT_WORD.search(command))
    # 安全な read-only git 置換（base=$(git merge-base ...) 等）だけをプレースホルダへ
    # 畳む。畳めない置換は $( を残すため以降で従来どおり解釈不能に倒れる。バイパス証拠の
    # 生走査は元 command に対して維持するため deny never degrades は破れない
    effective = _fold_safe_readonly_git_substitutions(command)
    # 構造改行の正規化（引用符内の改行はデータ、行継続は結合）。未終端引用符は
    # None が返り、トークン化不能と同じ保守分岐に落ちる
    rewritten = _split_unquoted_newlines(effective)
    try:
        tokens = _tokenize(rewritten) if rewritten is not None else None
    except ValueError:
        tokens = None
    if tokens is None:
        # token 化できないコマンドは、git の痕跡があるときだけ escalate 対象。
        # 構造が見えないので生テキスト走査でバイパス証拠だけは拾う（deny 維持）
        gated = raw_has_git or hooks_dir_touch
        bypass = tuple(_scan_bypass_evidence(command)) if raw_has_git else ()
        escalates = []
        if hooks_dir_touch:
            escalates.append(hooks_dir_reason)
        if raw_has_git and _HOOKS_PATH_RECONFIG.search(command):
            escalates.append(
                "persistent hook-path reconfiguration (git config core.hooksPath)"
            )
        return CommandAnalysis(gated, gated, bypass, (), tuple(escalates))
    # クォート分割（.gi"t/hooks" 等）はトークン化（クォート解決）後にだけ現れる。
    # git の語なしでも成立する形なので、git 有無の早期 return より前に拾う
    hooks_dir_touch = hooks_dir_touch or any(".git/hooks" in token for token in tokens)
    token_has_git = any(
        _is_git_token(token) or _GIT_WORD.search(token) for token in tokens
    )
    if not (raw_has_git or token_has_git):
        if hooks_dir_touch:
            return CommandAnalysis(True, False, (), (), (hooks_dir_reason,))
        return CommandAnalysis(False, False, (), ())

    bypass = []
    escalate_reasons = []
    if hooks_dir_touch:
        escalate_reasons.append(hooks_dir_reason)

    operations = []
    uninterpretable = any(marker in effective for marker in _UNPARSEABLE_MARKERS)
    if not uninterpretable:
        # 構造を解釈できる場合はトークン単位でバイパス・操作・再設定を検出する
        segments = [[]]
        for token in tokens:
            if token in _SEGMENT_DELIMITERS:
                segments.append([])
            else:
                segments[-1].append(token)
        cd_seen = False
        for segment in segments:
            # 先頭の環境変数代入（VAR=value）はコマンド位置の判定から除く。
            # ただし向け直し系（GIT_DIR 等）はフラグ形 -C と同じ扱いにする
            start = 0
            env_redirect = False
            while start < len(segment) and _ENV_ASSIGNMENT.match(segment[start]):
                if _is_env_redirect_assignment(segment[start]):
                    env_redirect = True
                start += 1
            body = segment[start:]
            if not body:
                continue
            head = body[0]
            if _is_git_token(head):
                seg_bypass, seg_ops, seg_broken, seg_escalates = _analyze_git_segment(
                    body[1:]
                )
                bypass.extend(seg_bypass)
                escalate_reasons.extend(seg_escalates)
                if env_redirect:
                    # 判定スナップショット（cwd のブランチ・宣言・証跡）と対応しない。
                    # フラグ形 -C と同じく、ゲート対象操作を含むときだけ解釈不能へ
                    # 倒し、操作は cwd の main / evidence 検査に流さない
                    seg_broken = seg_broken or bool(seg_ops)
                else:
                    operations.extend(seg_ops)
                uninterpretable = uninterpretable or seg_broken
            elif head == "cd":
                cd_seen = True
            elif head == "export":
                # export された向け直し変数は後続セグメントの git にも及ぶ
                if any(
                    _ENV_ASSIGNMENT.match(t) and _is_env_redirect_assignment(t)
                    for t in body[1:]
                ):
                    uninterpretable = True
            elif head in _INDIRECTION_COMMANDS:
                if any(_is_git_token(t) or _GIT_WORD.search(t) for t in body[1:]):
                    uninterpretable = True
            else:
                # コマンド位置以外の git は、書き込み操作の証拠を伴うときだけ解釈不能扱い
                # （単なるデータ位置の 'git' の語で人間確認を発生させない）
                if body[0].rsplit("/", 1)[-1] in _DATA_SINK_COMMANDS:
                    continue  # 引数を実行しないコマンド: git 句はデータ
                if _is_gate_self_invocation(body):
                    continue  # ゲート自身の記録・判定 CLI は対象コマンドを引数に運ぶ
                in_token_write = any(_IN_TOKEN_WRITE.search(t) for t in body)
                standalone = any(_is_git_token(t) for t in body) and any(
                    t in ("commit", "push") for t in body
                )
                if in_token_write or standalone:
                    uninterpretable = True
        if cd_seen and operations:
            # cd で作業場所が変わった後の git 書き込みはスナップショットと対応しない
            uninterpretable = True
    if uninterpretable:
        # 構造で確定できなかった部分に限り、生テキスト + token 復元テキストで
        # バイパス証拠を拾い直す（deny を escalate に弱めない最終防衛線）
        scan_text = command + "\n" + " ".join(tokens)
        bypass.extend(_scan_bypass_evidence(scan_text))
        if _HOOKS_PATH_RECONFIG.search(scan_text):
            escalate_reasons.append(
                "persistent hook-path reconfiguration (git config core.hooksPath)"
            )
    return CommandAnalysis(
        True, uninterpretable, tuple(bypass), tuple(operations), tuple(escalate_reasons)
    )


def _decide_commit(env):
    config = (
        parse_trunk_config(env.trunk_config_text)
        if env.trunk_config_text is not None
        else None
    )
    if env.current_branch is None:
        return Decision(
            "escalate",
            "The gate cannot determine the current branch, so it cannot verify this "
            "commit stays off the default branch. Confirm the branch, or approve to "
            "proceed.",
        )
    if env.default_branch is None:
        return Decision(
            "escalate",
            "The gate cannot determine the default branch of this repository, so it "
            "cannot verify this commit stays off it. Confirm the branch layout, or "
            "approve to proceed.",
        )
    if env.current_branch != env.default_branch:
        return Decision("allow", "")
    if config is not None and config.get("allow_main_commit") is True:
        return Decision("allow", "")
    if env.trunk_config_text is not None and (
        config is None or config.get("allow_main_commit") is _INVALID
    ):
        return Decision(
            "escalate",
            f"The declaration file {TRUNK_CONFIG_RELPATH} could not be read "
            "(unparsable content or unknown value), so committing on the default "
            f"branch '{env.default_branch}' falls to the safe side. Fix the "
            "declaration, or approve to proceed.",
        )
    return Decision(
        "escalate",
        f"Direct commit on the default branch '{env.default_branch}'. The trunk "
        "discipline commits on a working branch — create one first (for example: "
        f"git switch -c feature/<topic>). If this project deliberately commits on "
        f"'{env.default_branch}', a human may approve and persist "
        f"`allow_main_commit: true` in {TRUNK_CONFIG_RELPATH} (written only after "
        "human approval). If a human approves this one commit instead, record the "
        "pardon: `workflow_gate.py --record-amnesty --gate main_commit "
        "--gate-command '<command>' --reason '<this reason>' --grounds '<why the "
        "human approved>'`.",
    )


_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def _doc_alignment_defect(env):
    """doc_aligned.json の検証（pure）。欠陥の説明文 / None（有効）。"""
    if env.doc_evidence_text is None:
        return "absent"
    try:
        record = json.loads(env.doc_evidence_text)
    except ValueError:
        return "malformed (not valid JSON)"
    if not isinstance(record, dict):
        return "malformed (not a JSON object)"
    if record.get("schema_version") != 1:
        return "of an unknown schema version"
    if record.get("state") != "doc_aligned":
        return "not testifying for the doc_aligned state"
    target = record.get("target_sha")
    if not isinstance(target, str) or not _FULL_SHA.fullmatch(target):
        return "missing a full 40-hex target SHA"
    if env.head_sha is None:
        return "unverifiable (the current HEAD SHA could not be determined)"
    if target != env.head_sha:
        return "bound to a different SHA than the current HEAD"
    grounds = record.get("grounds")
    if not isinstance(grounds, str) or not grounds.strip():
        return "missing non-empty grounds"
    return None


def _with_verifier_report(reason, env):
    """escalate 理由文に検証器の報告を添える（人間が根拠を見て恩赦できるように）。"""
    if not env.evidence_report:
        return reason
    report = env.evidence_report.strip()
    if len(report) > 1500:
        report = report[:1500] + "\n... (truncated)"
    return reason + "\nVerifier report:\n" + report


def _decide_push(env):
    if env.trunk_config_text is None:
        return Decision(
            "escalate",
            "No workflow declaration found. Pushing under the trunk discipline "
            "requires review and doc-alignment evidence bound to HEAD; whether this "
            "project adopts the trunk is a human decision. Ask the human, then "
            f"persist the answer in {TRUNK_CONFIG_RELPATH} "
            "(`trunk: adopted` or `trunk: not_adopted` — written only after human "
            "approval).",
        )
    config = parse_trunk_config(env.trunk_config_text)
    if config is None or config.get("trunk", _INVALID) is _INVALID:
        return Decision(
            "escalate",
            f"The declaration file {TRUNK_CONFIG_RELPATH} could not be read "
            "(unparsable content or unknown value), so this push falls to the safe "
            "side. Fix the declaration, or approve to proceed.",
        )
    if config["trunk"] == "not_adopted":
        return Decision("allow", "")
    if env.evidence_exit == 0:
        doc_defect = _doc_alignment_defect(env)
        if doc_defect is None:
            return Decision("allow", "")
        return Decision(
            "escalate",
            f"Push under a declared trunk, but the doc-alignment record is {doc_defect}. "
            "The trunk discipline requires a doc_aligned.json record bound to the exact "
            "HEAD SHA (see skills/shared/references/workflow-gate.md). Run the "
            "doc-alignment check, then record it with `workflow_gate.py "
            "--record-doc-alignment --grounds <what the check ran and found>` — only "
            "after actually running it — or ask the human to approve this push as a "
            "recorded pardon (`workflow_gate.py --record-amnesty --gate "
            "push_evidence --gate-command '<command>' --reason '<this reason>' "
            "--grounds '<why the human approved>'`).",
        )
    if env.evidence_exit == 1:
        detail = "verification evidence for HEAD is absent, expired (SHA mismatch), or invalid"
    elif env.evidence_exit == 2:
        detail = "the evidence verifier could not run"
    else:
        detail = "the evidence check did not run"
    return Decision(
        "escalate",
        _with_verifier_report(
            f"Push under a declared trunk, but {detail}. The trunk discipline requires "
            "review and doc-alignment evidence bound to the exact HEAD SHA "
            "(see skills/shared/references/workflow-gate.md). Produce the evidence, or "
            "ask the human to approve this push as a recorded pardon "
            "(`workflow_gate.py --record-amnesty --gate push_evidence "
            "--gate-command '<command>' --reason '<this reason>' --grounds '<why the "
            "human approved>'`).",
            env,
        ),
    )


def decide(command, env):
    """判定コア（pure）。正本の判定表: skills/shared/references/workflow-gate.md."""
    analysis = analyze_command(command)
    if not analysis.has_git:
        return Decision("allow", "")
    if analysis.bypass_reasons:
        return Decision(
            "deny",
            "Inspection-bypass flag detected: "
            + "; ".join(dict.fromkeys(analysis.bypass_reasons))
            + ". An agent must not skip inspection hooks; only a human may pardon a "
            "gate escalation. Re-run the command without the bypass flag.",
        )
    if analysis.escalate_reasons:
        return Decision(
            "escalate",
            "Hook-configuration change detected: "
            + "; ".join(dict.fromkeys(analysis.escalate_reasons))
            + ". Repository hooks guard the trunk discipline — a human must confirm "
            "this change before it runs.",
        )
    if analysis.uninterpretable:
        return Decision(
            "escalate",
            "This command contains what may be a git invocation the gate cannot "
            "interpret (multiplexed, substituted, shell-wrapped, executed through "
            "another program's arguments, or aimed at another working directory or "
            "repository). The gate never guesses toward allow — run the git "
            "operation as a plain command from the repository root, rephrase the "
            "command so the git wording is visibly data, or ask the human to "
            "approve this form.",
        )
    decisions = []
    for operation in analysis.operations:
        if operation == "commit":
            decisions.append(_decide_commit(env))
        elif operation == "push":
            decisions.append(_decide_push(env))
    for verdict in ("deny", "escalate"):
        matching = [d for d in decisions if d.verdict == verdict]
        if matching:
            return Decision(verdict, "\n".join(d.reason for d in matching))
    return Decision("allow", "")


AMNESTY_GATES = ("main_commit", "push_evidence", "push_undeclared", "uninterpretable")
AMNESTY_LEDGER_RELPATH = os.path.join(
    ".agents", "artifacts", "decisions", "workflow-gate-amnesties.jsonl"
)


def format_amnesty_line(gate, command, reason, grounds, recorded_at):
    """恩赦 1 件 → 台帳の 1 行 JSON（pure）。書式の正本は workflow-gate.md。

    grounds を欠く恩赦は記録として成立しない（evidence-format と同じ Iron Law）。
    """
    if gate not in AMNESTY_GATES:
        raise ValueError(f"unknown gate {gate!r}; expected one of {AMNESTY_GATES}")
    if not isinstance(grounds, str) or not grounds.strip():
        raise ValueError("a pardon that cannot say why it was granted is not a record")
    return json.dumps(
        {
            "recorded_at": recorded_at,
            "gate": gate,
            "command": command,
            "reason": reason,
            "grounds": grounds,
        },
        ensure_ascii=False,
    )


# --- ここから下は I/O（環境スナップショットの収集と CLI アダプタ） ---


def record_amnesty(cwd, gate, command, reason, grounds, now=None):
    """人間が承認した恩赦を decisions 台帳へ追記する（承認後にのみ呼ぶこと）。"""
    recorded_at = now or datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    line = format_amnesty_line(gate, command, reason, grounds, recorded_at)
    path = os.path.join(cwd, AMNESTY_LEDGER_RELPATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def record_doc_alignment(cwd, grounds, now=None):
    """doc 整合実施の証跡を HEAD へバインドして生成する（実施後にのみ呼ぶこと）。

    ゲート拡張レコード doc_aligned.json の唯一の出荷 producer。スキーマの正本は
    workflow-gate.md（正準 2 状態と同形・state=doc_aligned・full SHA・grounds 必須）。
    """
    if not isinstance(grounds, str) or not grounds.strip():
        raise ValueError(
            "a doc-alignment record that cannot say what ran is not evidence"
        )
    root = _repo_root(cwd)
    head = _git_output(["rev-parse", "HEAD"], root)
    if head is None or not _FULL_SHA.fullmatch(head):
        raise RuntimeError(
            "cannot resolve the current HEAD SHA; the record must bind to an exact commit"
        )
    recorded_at = now or datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    record = {
        "schema_version": 1,
        "state": "doc_aligned",
        "target_sha": head,
        "produced_at": recorded_at,
        "grounds": grounds,
    }
    path = os.path.join(root, DOC_EVIDENCE_RELPATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False)
        handle.write("\n")


_GIT_TIMEOUT = 30
_EVIDENCE_TIMEOUT = 120


def _git_output(args, cwd):
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=_GIT_TIMEOUT,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        # ValueError はデコード失敗を含む。読めない環境は「特定不能」として
        # 呼び出し側の保守的判定（escalate）に委ねる
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _detect_current_branch(cwd):
    branch = _git_output(["rev-parse", "--abbrev-ref", "HEAD"], cwd)
    if branch is None or branch == "HEAD":  # HEAD = detached
        return None
    return branch


def _detect_default_branch(cwd):
    ref = _git_output(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd)
    if ref:
        return ref.split("/", 1)[1] if "/" in ref else ref
    for candidate in ("main", "master"):
        if _git_output(["rev-parse", "--verify", "--quiet", f"refs/heads/{candidate}"], cwd) is not None:
            return candidate
    # 推測で "main" を返すと develop 等を既定にするリポジトリで main 直コミット検査が
    # 素通しになる。特定不能は None（コアが escalate に倒す）
    return None


def _repo_root(cwd):
    """宣言・証跡の探索基点。サブディレクトリからの実行でもリポジトリ根を使う。"""
    return _git_output(["rev-parse", "--show-toplevel"], cwd) or cwd


def _read_trunk_config(root):
    try:
        with open(os.path.join(root, TRUNK_CONFIG_RELPATH), encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return None


def _run_evidence_check(root):
    """evidence_check.py を同梱ディレクトリから起動し (exit code, 報告) を返す。"""
    checker = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evidence_check.py")
    contract = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "references", "quality-gate-contract.md",
    )
    try:
        result = subprocess.run(
            [sys.executable, checker, "--repo-root", root, "--contract", contract],
            capture_output=True,
            text=True,
            check=False,
            timeout=_EVIDENCE_TIMEOUT,
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return 2, f"(the verifier could not be started: {exc})"
    return result.returncode, (result.stdout or "") + (result.stderr or "")


DOC_EVIDENCE_RELPATH = os.path.join(
    ".agents", "artifacts", "reviews", "evidence", "doc_aligned.json"
)


def _read_doc_evidence(root):
    try:
        with open(os.path.join(root, DOC_EVIDENCE_RELPATH), encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return None


def gather_env(cwd, need_evidence):
    root = _repo_root(cwd)
    evidence_exit = None
    evidence_report = None
    if need_evidence:
        evidence_exit, evidence_report = _run_evidence_check(root)
    return EnvSnapshot(
        current_branch=_detect_current_branch(cwd),
        default_branch=_detect_default_branch(cwd),
        trunk_config_text=_read_trunk_config(root),
        evidence_exit=evidence_exit,
        head_sha=_git_output(["rev-parse", "HEAD"], cwd) if need_evidence else None,
        doc_evidence_text=_read_doc_evidence(root) if need_evidence else None,
        evidence_report=evidence_report,
    )


def run_gate(command, cwd):
    """コマンド 1 本ぶんの収集 + 判定。git 痕跡のないコマンドは I/O なしで allow。"""
    analysis = analyze_command(command)
    if not analysis.has_git:
        return Decision("allow", "")
    need_evidence = "push" in analysis.operations
    env = gather_env(cwd, need_evidence=need_evidence)
    return decide(command, env)


def _hook_io_claude():
    """ツール実行前フックの標準入出力アダプタ。

    フック側の障害でセッションを壊さないため、内部エラーは沈黙（exit 0・出力なし）に
    落とす。保守的判定（escalate/deny）は decide() 側で完結しており、ここでの沈黙は
    「ゲート基盤そのものが動けない」場合だけに限られる。
    """
    try:
        payload = json.load(sys.stdin)
        if payload.get("tool_name") != "Bash":
            return 0
        command = (payload.get("tool_input") or {}).get("command")
        if not isinstance(command, str) or not command:
            return 0
        cwd = payload.get("cwd") or os.getcwd()
        decision = run_gate(command, cwd)
        if decision.verdict == "allow":
            return 0
        permission = "ask" if decision.verdict == "escalate" else "deny"
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": permission,
                    "permissionDecisionReason": decision.reason,
                }
            },
            sys.stdout,
        )
        return 0
    except Exception:
        return 0


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hook-io",
        choices=["claude"],
        help="ツール実行前フックの入出力形式で stdin/stdout を処理する",
    )
    parser.add_argument(
        "--record-amnesty",
        action="store_true",
        help="人間が承認した恩赦を decisions 台帳へ追記する（承認後にのみ使う）",
    )
    parser.add_argument(
        "--decide",
        action="store_true",
        help="--gate-command の判定を JSON（verdict + reason）で出力する",
    )
    parser.add_argument(
        "--record-doc-alignment",
        action="store_true",
        help="doc 整合実施の証跡を HEAD へバインドして記録する（実施後にのみ使う）",
    )
    parser.add_argument("--gate", choices=AMNESTY_GATES)
    parser.add_argument("--gate-command", help="判定・恩赦の対象となるコマンド文字列")
    parser.add_argument("--reason", help="escalate 時にゲートが提示した理由文")
    parser.add_argument("--grounds", help="人間が何を見て承認したか（必須・空不可）")
    args = parser.parse_args(argv)
    if args.hook_io == "claude":
        return _hook_io_claude()
    if args.decide:
        if not args.gate_command:
            parser.error("--decide requires --gate-command")
        decision = run_gate(args.gate_command, os.getcwd())
        json.dump({"verdict": decision.verdict, "reason": decision.reason}, sys.stdout)
        return 0
    if args.record_doc_alignment:
        try:
            record_doc_alignment(os.getcwd(), args.grounds or "")
        except (ValueError, RuntimeError) as exc:
            print(f"doc-alignment not recorded: {exc}", file=sys.stderr)
            return 1
        return 0
    if args.record_amnesty:
        if not (args.gate and args.gate_command and args.reason):
            parser.error("--record-amnesty requires --gate, --gate-command, --reason")
        try:
            record_amnesty(
                _repo_root(os.getcwd()),
                args.gate,
                args.gate_command,
                args.reason,
                args.grounds or "",
            )
        except ValueError as exc:
            print(f"amnesty not recorded: {exc}", file=sys.stderr)
            return 1
        return 0
    parser.error(
        "no mode selected: pass --hook-io, --decide, --record-doc-alignment, "
        "or --record-amnesty"
    )


if __name__ == "__main__":
    sys.exit(main())
