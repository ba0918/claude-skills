#!/usr/bin/env python3
"""Rolling checkpoint — long-lived session execution-state restore.

A checkpoint is NOT a worktree backup. It is a *restore guide* that is matched
against the current git state. The contract of record is
`skills/shared/references/checkpoint-pattern.md`; this module is the mechanical
enforcement of its security rules (strict parse / path containment / secret
masking / no execution).

Design (design-principles §4/§5): all decision logic is pure functions over
string/bytes input. git is invoked only in the CLI layer. We deliberately do
NOT use PyYAML (deserialization RCE surface) nor the shared frontmatter.py
(it silently overwrites duplicate keys — a strict checkpoint parser must reject
duplicates). See checkpoint-pattern.md § "セキュリティ規約".
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from secret_detect import mask_secrets  # noqa: E402

CHECKPOINTS_SUBDIR = ".agents/artifacts/plans/checkpoints"
_CHECKPOINT_PREFIX = ".agents/artifacts/plans/checkpoints/"

# v1 accepts only [0-9]{14}. The reserved checkpoint_id grammar (for future
# parallel-cycle) is [0-9]{14}(-[a-z0-9-]+)? — kept as documentation only; v1
# rejects the -suffix form.
CYCLE_ID_RE = re.compile(r"[0-9]{14}")
CHECKPOINT_ID_RESERVED_RE = re.compile(r"[0-9]{14}(-[a-z0-9-]+)?")  # v2 reserve

OWNERS = {"manual-session", "precompact"}
MODES = {"normal", "degraded"}
# owner <-> mode must agree.
OWNER_MODE = {"manual-session": "normal", "precompact": "degraded"}

REQUIRED_SCALARS = ("cycle_id", "owner", "mode", "written_at", "base_head",
                    "dirty_fingerprint")

_HEX_SHA_RE = re.compile(r"[0-9a-f]{7,64}")
_FINGERPRINT_RE = re.compile(r"sha256:[0-9a-f]{64}")

VERDICT_EXIT_CODES = {
    "valid": 0,
    "stale": 10,
    "superseded": 11,
    "degraded": 12,
    "conflict": 13,
}


class ParseError(Exception):
    """Strict-parse / validation failure. In restore terms: parse conflict."""


class ContainmentError(Exception):
    """Path escapes .agents/artifacts/plans/checkpoints/ or is a symlink."""


@dataclass
class CheckpointMeta:
    cycle_id: str
    owner: str
    mode: str
    written_at: str
    base_head: str
    dirty_fingerprint: str
    dirty_files: list = field(default_factory=list)
    verify_on_restore: list = field(default_factory=list)


@dataclass
class Verdict:
    verdict: str
    dirty_overlap: list = field(default_factory=list)
    reason: str = ""


# ==========================================================================
# porcelain=v1 -z parsing (pure)
# ==========================================================================
def parse_porcelain(porcelain_z):
    """Parse `git status --porcelain=v1 -z` output into entries.

    Returns a list of dicts: {"xy": 2-char status, "path": str, ["orig": str]}.
    -z uses NUL terminators and does NOT quote, so spaces/unicode/newlines in a
    path are literal. Rename/copy entries are two NUL-separated fields
    (new-path then orig-path).
    """
    if isinstance(porcelain_z, str):
        porcelain_z = porcelain_z.encode("utf-8")
    tokens = porcelain_z.split(b"\x00")
    if tokens and tokens[-1] == b"":
        tokens.pop()
    entries = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if len(tok) < 3:
            i += 1
            continue
        xy = tok[:2].decode("utf-8", "surrogateescape")
        path = tok[3:].decode("utf-8", "surrogateescape")
        entry = {"xy": xy, "path": path}
        if xy[0] in ("R", "C") or xy[1] in ("R", "C"):
            i += 1
            if i < len(tokens):
                entry["orig"] = tokens[i].decode("utf-8", "surrogateescape")
        entries.append(entry)
        i += 1
    return entries


def _is_checkpoint_path(path):
    return path.replace("\\", "/").startswith(_CHECKPOINT_PREFIX)


def dirty_paths(entries):
    """Sorted dirty file paths, excluding the checkpoints dir (self-noise)."""
    return sorted(
        e["path"] for e in entries if not _is_checkpoint_path(e["path"])
    )


# ==========================================================================
# fingerprint (pure)
# ==========================================================================
def compute_fingerprint(porcelain_z, diff_text, untracked_hashes):
    """sha256 fingerprint of the dirty state.

    Order-independent over porcelain entries and untracked files; sensitive to
    diff body (so identical stat + different edit differs) and to untracked
    content. The checkpoints dir is excluded from all inputs.
    """
    entries = parse_porcelain(porcelain_z)
    kept = [e for e in entries if not _is_checkpoint_path(e["path"])]
    porc_lines = sorted(
        e["xy"] + "\x01" + e["path"] + ("\x01" + e["orig"] if e.get("orig") else "")
        for e in kept
    )
    unt_lines = sorted(
        p + "\x01" + h
        for p, h in (untracked_hashes or {}).items()
        if not _is_checkpoint_path(p)
    )
    canonical = (
        "\x00".join(porc_lines)
        + "\x00\x02DIFF\x02\x00"
        + (diff_text or "")
        + "\x00\x02UNT\x02\x00"
        + "\x00".join(unt_lines)
    )
    digest = hashlib.sha256(canonical.encode("utf-8", "surrogateescape")).hexdigest()
    return "sha256:" + digest


# ==========================================================================
# strict frontmatter parse (pure) — no PyYAML, no frontmatter.py
# ==========================================================================
def _unquote(val):
    val = val.strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
        return val[1:-1]
    return val


def _split_frontmatter(text):
    if not text.startswith("---\n"):
        raise ParseError("frontmatter 開始デリミタ (---) がない")
    rest = text[4:]
    idx = rest.find("\n---")
    if idx == -1:
        raise ParseError("frontmatter 終了デリミタ (---) がない")
    return rest[:idx], rest[idx + 4:]


def _consume_block(lines, start):
    """Collect consecutive indented (space-prefixed) or blank lines as a block."""
    block = []
    i = start
    while i < len(lines):
        ln = lines[i]
        if ln == "" or ln.startswith(" "):
            block.append(ln)
            i += 1
        else:
            break
    # trim trailing blank lines
    while block and block[-1] == "":
        block.pop()
    return block, i


def _parse_scalar_list(block):
    out = []
    for ln in block:
        if ln == "":
            continue
        m = re.match(r"^  - (.+)$", ln)
        if not m:
            raise ParseError(f"リスト構文が不正: {ln!r}")
        out.append(_unquote(m.group(1)))
    return out


def _parse_vor_list(block):
    """verify_on_restore: list of {cmd, args}. Free-form shell strings rejected."""
    items = []
    i = 0
    while i < len(block):
        ln = block[i]
        if ln == "":
            i += 1
            continue
        m = re.match(r"^  - cmd:\s*(.+)$", ln)
        if not m:
            raise ParseError(
                f"verify_on_restore の要素は '- cmd: ...' 構造のみ受理: {ln!r}"
            )
        cmd = _unquote(m.group(1))
        i += 1
        args = []
        if i < len(block):
            am = re.match(r"^    args:\s*(\[.*\])\s*$", block[i])
            if am:
                try:
                    args = json.loads(am.group(1))
                except json.JSONDecodeError:
                    raise ParseError("verify_on_restore args が JSON 配列でない")
                if not isinstance(args, list) or not all(
                    isinstance(a, str) for a in args
                ):
                    raise ParseError("verify_on_restore args は文字列配列のみ")
                i += 1
        items.append({"cmd": cmd, "args": args})
    return items


def _parse_frontmatter(fm):
    lines = fm.split("\n")
    result = {}
    seen = set()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip() == "" or line.lstrip().startswith("#"):
            i += 1
            continue
        if line[0] in (" ", "\t"):
            raise ParseError(f"予期しないインデント行（トップレベル期待）: {line!r}")
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):(.*)$", line)
        if not m:
            raise ParseError(f"不正なキー行: {line!r}")
        key, raw = m.group(1), m.group(2)
        if key in seen:
            raise ParseError(f"重複キー: {key}")
        seen.add(key)
        val = raw.strip()
        if val == "":
            block, i = _consume_block(lines, i + 1)
            if key == "dirty_files":
                result[key] = _parse_scalar_list(block)
            elif key == "verify_on_restore":
                result[key] = _parse_vor_list(block)
            else:
                if block:
                    raise ParseError(f"{key} はスカラーだがブロックが続く")
                result[key] = ""
        elif key in ("dirty_files", "verify_on_restore"):
            # Inline list form: only the empty list `[]` is accepted. A
            # non-empty inline list must use block style (keeps the parser
            # strict and the verify_on_restore {cmd,args} shape enforceable).
            if val == "[]":
                result[key] = []
                i += 1
            else:
                raise ParseError(
                    f"{key} のインライン非空リストは非対応（ブロック記法を使う）: {val!r}"
                )
        else:
            result[key] = _unquote(val)
            i += 1
    return result


def parse_checkpoint(text, filename_cycle_id):
    """Strict parse + validate. Raises ParseError on any inconsistency
    (= parse conflict in restore terms)."""
    fm, _body = _split_frontmatter(text)
    data = _parse_frontmatter(fm)

    for k in REQUIRED_SCALARS:
        if k not in data or data[k] == "":
            raise ParseError(f"必須キー欠落: {k}")

    cycle_id = data["cycle_id"]
    if not CYCLE_ID_RE.fullmatch(cycle_id):
        raise ParseError(f"cycle_id 形式違反（[0-9]{{14}} のみ）: {cycle_id!r}")
    if cycle_id != filename_cycle_id:
        raise ParseError(
            f"ファイル名 cycle_id ({filename_cycle_id!r}) と frontmatter "
            f"({cycle_id!r}) が不一致"
        )

    owner = data["owner"]
    if owner not in OWNERS:
        raise ParseError(f"未知 owner: {owner!r}")
    mode = data["mode"]
    if mode not in MODES:
        raise ParseError(f"未知 mode: {mode!r}")
    if OWNER_MODE[owner] != mode:
        raise ParseError(f"owner⇔mode 不一致: owner={owner!r} mode={mode!r}")

    base_head = data["base_head"]
    if not _HEX_SHA_RE.fullmatch(base_head):
        raise ParseError(f"base_head が hex sha でない: {base_head!r}")
    fp = data["dirty_fingerprint"]
    if not _FINGERPRINT_RE.fullmatch(fp):
        raise ParseError(f"dirty_fingerprint 形式不正: {fp!r}")

    return CheckpointMeta(
        cycle_id=cycle_id,
        owner=owner,
        mode=mode,
        written_at=data["written_at"],
        base_head=base_head,
        dirty_fingerprint=fp,
        dirty_files=data.get("dirty_files", []) or [],
        verify_on_restore=data.get("verify_on_restore", []) or [],
    )


# ==========================================================================
# classify (pure) — parse gate already passed
# ==========================================================================
def classify(meta, current_head, current_fingerprint, *,
             current_dirty_files=None, conflict_marker=False):
    """Semantic 5-verdict classification on a parsed checkpoint.

    Priority: superseded > conflict > degraded > stale > valid.
    (Parse conflict is terminal and handled *before* this — see the CLI layer /
    checkpoint-pattern.md § "層分離".)

    conflict_marker is the write-side overwrite-race signal. In v1 no caller
    sets it (single-writer/single-host model — the anti-overwrite guarantee is
    skill discipline, not code-enforced); the parameter is the v2 wire point for
    written_at/fingerprint race detection and is exercised by the unit tests so
    the priority ordering stays frozen.
    """
    # 1. superseded — HEAD advanced. base_head is ground-truth-relative.
    if meta.base_head != current_head:
        overlap = []
        if current_dirty_files:
            overlap = sorted(set(meta.dirty_files) & set(current_dirty_files))
        return Verdict("superseded", dirty_overlap=overlap,
                       reason="HEAD が前進した（コミットが ground truth）")
    # 2. semantic conflict — overwrite-race artifact detected by the caller.
    if conflict_marker:
        return Verdict("conflict", reason="上書き競合痕（人間照会）")
    # 3. degraded — precompact / degraded owner.
    if meta.owner == "precompact":
        return Verdict("degraded", reason="precompact: dirty set と HEAD のみ信用")
    # 4. stale — fingerprint drifted.
    if meta.dirty_fingerprint != current_fingerprint:
        return Verdict("stale", reason="fingerprint 不一致（叙述は参考扱い）")
    # 5. valid.
    return Verdict("valid", reason="HEAD・fingerprint 一致（叙述を復元の起点に）")


# ==========================================================================
# build_skeleton (pure) + atomic write
# ==========================================================================
def _escape_list_item(s):
    """Keep a dirty-file list item on a single line so the freshly-written
    skeleton round-trips through the strict parser. Paths may legitimately
    contain newlines/CR/tab (git -z is byte-literal); we escape them to visible
    two-char sequences. dirty_files is informational — the staleness source of
    truth is dirty_fingerprint (computed from raw porcelain), so a display-only
    escape is safe."""
    return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r").replace(
        "\t", "\\t"
    )


def build_skeleton(porcelain_z, head, fingerprint, owner, cycle_id, written_at):
    """Generate the machine-field skeleton. Narrative is filled by the LLM."""
    if owner not in OWNERS:
        raise ParseError(f"未知 owner: {owner!r}")
    if not CYCLE_ID_RE.fullmatch(cycle_id):
        raise ParseError(f"cycle_id 形式違反: {cycle_id!r}")
    mode = OWNER_MODE[owner]
    files = dirty_paths(parse_porcelain(porcelain_z))
    masked = [_escape_list_item(mask_secrets(p)) for p in files]
    files_block = "\n".join(f"  - {p}" for p in masked) if masked else ""

    lines = [
        "---",
        f'cycle_id: "{cycle_id}"',
        f"owner: {owner}",
        f"mode: {mode}",
        f"written_at: {written_at}",
        f"base_head: {head}",
        f"dirty_fingerprint: {fingerprint}",
        "dirty_files:",
    ]
    if files_block:
        lines.append(files_block)
    # Empty verify list as a block (empty) so it round-trips to [] through the
    # strict parser (inline non-empty lists are rejected by design).
    lines.append("verify_on_restore: []")
    lines.append("---")
    if mode == "degraded":
        decision = "unknown"
        nxt = "reconstruct_from_diff"
    else:
        decision = "{plan からの逸脱判断を 1 文。逸脱なしなら none}"
        nxt = "{次の一手 1 個だけ}"
    lines += [
        "## decision",
        mask_secrets(decision),
        "",
        "## evidence",
        "{観測コマンド + タイムスタンプ必須。例: Observed HH:MM: <cmd> exited 0}",
        "",
        "## next",
        mask_secrets(nxt),
        "",
    ]
    return "\n".join(lines)


def atomic_write(path, content):
    """mkdir -p + temp file + atomic rename (single-writer, single-host)."""
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


# ==========================================================================
# path containment (pure-ish; filesystem probe only)
# ==========================================================================
def check_containment(path, checkpoints_dir):
    """Ensure path resolves strictly inside checkpoints_dir and is not a symlink."""
    if os.path.islink(path):
        raise ContainmentError(f"symlink は拒否: {path}")
    real = os.path.realpath(path)
    reald = os.path.realpath(checkpoints_dir)
    try:
        common = os.path.commonpath([real, reald])
    except ValueError:
        raise ContainmentError(f"パスが checkpoints ディレクトリ外: {path}")
    if common != reald:
        raise ContainmentError(f"パスが checkpoints ディレクトリ外: {path}")
    return path


def checkpoint_path(checkpoints_dir, cycle_id):
    """Resolve {checkpoints_dir}/{cycle_id}.md, enforcing cycle_id grammar."""
    if not CYCLE_ID_RE.fullmatch(cycle_id):
        raise ParseError(f"cycle_id 形式違反（[0-9]{{14}} のみ）: {cycle_id!r}")
    p = os.path.join(checkpoints_dir, cycle_id + ".md")
    if os.path.islink(p):
        raise ContainmentError(f"symlink は拒否: {p}")
    reald = os.path.realpath(checkpoints_dir)
    real = os.path.realpath(p)
    if os.path.dirname(real) != reald:
        raise ContainmentError(f"パスが checkpoints ディレクトリ外: {p}")
    return p


def verdict_exit_code(verdict):
    if verdict not in VERDICT_EXIT_CODES:
        raise ValueError(f"未知 verdict: {verdict!r}")
    return VERDICT_EXIT_CODES[verdict]


# ==========================================================================
# CLI layer — the ONLY place git is invoked
# ==========================================================================
def _git(repo, *args, timeout=30):
    return subprocess.run(
        ["git", "-C", repo, *args],
        capture_output=True, timeout=timeout,
        env={**os.environ, "LC_ALL": "C"},
    )


def _git_head(repo):
    r = _git(repo, "rev-parse", "HEAD")
    return r.stdout.decode("utf-8", "surrogateescape").strip()


def _git_status_z(repo):
    # --untracked-files=all forces git to list individual untracked FILES rather
    # than collapsing a fully-untracked directory into a single `?? dir/` entry.
    # Without it, a bare `?? docs/` entry would NOT match the checkpoints-path
    # exclusion and would poison the fingerprint (false stale). See
    # checkpoint-pattern.md § "fingerprint の正規化".
    return _git(repo, "status", "--porcelain=v1", "--untracked-files=all", "-z").stdout


def _git_fingerprint(repo):
    """Return (fingerprint, dirty_files, porcelain_z)."""
    porc = _git_status_z(repo)
    diff = _git(repo, "diff", "HEAD").stdout.decode("utf-8", "surrogateescape")
    entries = parse_porcelain(porc)
    untracked = {}
    for e in entries:
        if e["xy"] == "??":
            fpath = os.path.join(repo, e["path"])
            try:
                with open(fpath, "rb") as f:
                    untracked[e["path"]] = hashlib.sha256(f.read()).hexdigest()
            except OSError:
                untracked[e["path"]] = "<unreadable>"
    return compute_fingerprint(porc, diff, untracked), dirty_paths(entries), porc


def _cli_skeleton(args):
    repo = args.repo
    head = args.head or _git_head(repo)
    fp, _dirty, porc = _git_fingerprint(repo)
    out = build_skeleton(porc, head, fp, args.owner, args.cycle_id, args.written_at)
    if args.output:
        ckdir = os.path.join(repo, CHECKPOINTS_SUBDIR)
        target = checkpoint_path(ckdir, args.cycle_id)
        atomic_write(target, out)
        print(f"checkpoint 骨格を書き出した: {target}")
    else:
        sys.stdout.write(out)
    return 0


def _cli_classify(args):
    repo = args.repo
    ckdir = os.path.join(repo, CHECKPOINTS_SUBDIR)
    path = args.file
    try:
        check_containment(path, ckdir)
    except ContainmentError as e:
        print(f"verdict: conflict\nreason: containment 違反: {e}")
        return verdict_exit_code("conflict")
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(f"verdict: conflict\nreason: 読み込み失敗: {e}")
        return verdict_exit_code("conflict")
    filename_cycle_id = os.path.basename(path)[:-3] if path.endswith(".md") \
        else os.path.basename(path)
    try:
        meta = parse_checkpoint(text, filename_cycle_id)
    except ParseError as e:
        print(f"verdict: conflict\nreason: parse conflict: {e}")
        return verdict_exit_code("conflict")
    head = _git_head(repo)
    fp, dirty, _porc = _git_fingerprint(repo)
    v = classify(meta, head, fp, current_dirty_files=dirty)
    print(f"verdict: {v.verdict}")
    if v.reason:
        print(f"reason: {v.reason}")
    if v.dirty_overlap:
        print("dirty_overlap: " + ", ".join(v.dirty_overlap))
    if meta.verify_on_restore:
        print("verify_on_restore (表示のみ・自動実行しない):")
        for item in meta.verify_on_restore:
            print(f"  - {item['cmd']} {' '.join(item.get('args', []))}")
    return verdict_exit_code(v.verdict)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Rolling checkpoint restore guide")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sk = sub.add_parser("skeleton", help="checkpoint 骨格を生成")
    sk.add_argument("--repo", default=".")
    sk.add_argument("--cycle-id", dest="cycle_id", required=True)
    sk.add_argument("--owner", default="manual-session", choices=sorted(OWNERS))
    sk.add_argument("--head", default=None)
    sk.add_argument("--written-at", dest="written_at", required=True)
    sk.add_argument("--output", action="store_true",
                    help="骨格を checkpoints ディレクトリに atomic 書き出し")
    sk.set_defaults(func=_cli_skeleton)

    cl = sub.add_parser("classify", help="checkpoint を現 git 状態と照合し verdict を出す")
    cl.add_argument("--repo", default=".")
    cl.add_argument("--file", required=True)
    cl.set_defaults(func=_cli_classify)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
