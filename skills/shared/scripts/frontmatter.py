"""YAML frontmatter の共有パーサ（PyYAML 非依存の純関数）。

scripts/validate_repo.py / skills/context-audit/scripts/static_checks.py /
skills/trigger-eval/scripts/collect_descriptions.py が各自再実装していた
パーサの統合版。乖離すると SKILL.md の発火判定（description トリガー語
チェック等）の正しさに直結するため、実装をここに一本化する。

利用側は skills/shared/scripts/secret_detect.py と同様に
`sys.path.insert` でこのディレクトリを追加して import する。

判定規則:
- frontmatter は先頭行の `---` から次の `---` まで。閉じデリミタが
  なければ不成立（None / 空 dict）
- トップレベルキーは `[A-Za-z_][A-Za-z0-9_-]*` を列 0 から（YAML リスト
  行 `- item:` や数字始まり、インデント行はキーとして扱わない）
"""
import re

_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(.*)$")
_BLOCK_SCALARS = (">", "|", ">-", "|-")


def _block_lines(text):
    """frontmatter ブロック内の行リストを返す。不成立なら None。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return lines[1:i]
    return None  # 閉じデリミタなし = frontmatter 不成立


def parse_frontmatter_lines(text):
    """トップレベルキーを [(key, value, raw_line)] で返す。不成立なら None。

    raw_line は整形正規化チェック（context-audit CA-M001）が
    `key:value` のような非正規整形を検出するために保持する。
    """
    body = _block_lines(text)
    if body is None:
        return None
    out = []
    for line in body:
        m = _KEY_RE.match(line)
        if m:
            out.append((m.group(1), m.group(2).strip(), line))
    return out


def parse_frontmatter_fields(text):
    """トップレベル `key: value` を dict で返す。frontmatter がなければ空 dict。"""
    fm = parse_frontmatter_lines(text)
    if fm is None:
        return {}
    return {key: value for key, value, _ in fm}


def extract_description(text):
    """description の全文を返す（複数行ブロックスカラー対応）。なければ None。

    `description: >` 形式の継続行を次のトップレベルキーまで収集し、
    空行を除いてスペース結合する。
    """
    body = _block_lines(text)
    if body is None:
        return None
    desc_lines = []
    in_desc = False
    for line in body:
        m = _KEY_RE.match(line)
        if m:
            if m.group(1) == "description":
                in_desc = True
                desc_lines.append(m.group(2).strip())
            elif in_desc:
                break  # 次のトップレベルキーで終了
            continue
        if in_desc:
            desc_lines.append(line.strip())
    if not in_desc:
        return None
    if desc_lines and desc_lines[0] in _BLOCK_SCALARS:
        desc_lines = desc_lines[1:]
    return " ".join(l for l in desc_lines if l).strip()


def parse_name_and_description(text):
    """{name, description} を返す。frontmatter がなければ None。

    欠落キーは空文字列（trigger-eval collect_descriptions の契約）。
    """
    fm = parse_frontmatter_lines(text)
    if fm is None:
        return None
    name = next((value for key, value, _ in fm if key == "name"), "")
    return {"name": name, "description": extract_description(text) or ""}
