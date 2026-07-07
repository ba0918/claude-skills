#!/usr/bin/env python3
"""design-lint: .design/tokens.json に基づくデザイントークン lint（純関数エンジン）。

ルール仕様は references/lint-contract.md、CSS 変数命名規則は
shared/references/design-system-contract.md を正とする。

  DL001-006: Token Compliance（tokens.json のみで有効）
  DL101-103: Component Compliance（.design/component-catalog.json 存在時）
  DL201-203: Page Compliance（.design/pages/ 存在時）
  DL204:     Layout Rules（.design/layout-rules.json 存在時）

検出は正規表現ベースの近似（AST 不使用 = 言語非依存）。ファイルは読むだけで
修正は行わない。

実行: python3 design_lint.py [--root DIR] [--design-dir .design]
                             [--json] [--output PATH]
終了コード: 0 = PASS / 1 = FAIL (error あり) / 2 = 前提条件不足
"""
import argparse
import fnmatch
import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "include": ["src/**/*.tsx", "src/**/*.css", "src/**/*.jsx", "src/**/*.ts"],
    "exclude": ["node_modules/**", ".design/**", "*.test.*", "*.spec.*"],
    "rules": {
        "DL001": "error", "DL002": "error", "DL003": "warn",
        "DL004": "warn", "DL005": "warn", "DL006": "error",
        "DL101": "error", "DL102": "error", "DL103": "warn",
        "DL201": "warn", "DL202": "error", "DL203": "warn",
        # DL204 の severity は constraint 側の定義に従う（off のみ有効）
        "DL204": "warn",
    },
    "allowRawValues": {
        "colors": ["transparent", "inherit", "currentColor", "white", "black"],
        "spacing": [0, "auto"],
        "borderRadius": [0, "50%", "9999px"],
    },
}

# HTML ネイティブ要素は小文字なので PascalCase 抽出に掛からない。
# ここは PascalCase の標準コンポーネントのみ（React/Preact + ルーター標準）。
STANDARD_COMPONENTS = {
    "Fragment", "Suspense", "StrictMode", "Profiler", "Provider", "Consumer",
    "Route", "Routes", "Router", "BrowserRouter", "HashRouter", "MemoryRouter",
    "Link", "NavLink", "Outlet", "Navigate", "Switch",
}

SYSTEM_FONTS = {"-apple-system", "blinkmacsystemfont", "system-ui", "segoe ui"}
GENERIC_FONTS = {"sans-serif", "serif", "monospace", "cursive", "fantasy"}

# DL103: inline style で上書き禁止のトークン対象プロパティ
TOKEN_STYLE_PROPS = {
    "color", "backgroundColor", "background",
    "fontFamily", "fontSize", "fontWeight",
    "padding", "margin", "gap",
    "borderRadius", "boxShadow", "border", "borderColor",
}
_TOKEN_STYLE_PREFIXES = ("padding", "margin")

_SPACING_PROP_RE = re.compile(
    r"(?<![-\w])(?:padding|margin|gap|top|right|bottom|left)"
    r"(?:-(?:top|right|bottom|left|inline|block|inline-start|inline-end))?"
    r"\s*:\s*([^;}\n]+)"
)
_PX_RE = re.compile(r"(-?\d+(?:\.\d+)?)px\b")
_HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_FUNC_COLOR_RE = re.compile(r"(?:rgba?|hsla?)\([^)]*\)")
_SHADOW_DECL_RE = re.compile(
    r"(?:box-shadow\s*:\s*([^;}\n]+)|boxShadow\s*:\s*['\"]([^'\"]+)['\"])"
)
_RADIUS_DECL_RE = re.compile(
    r"(?:border-radius\s*:\s*([^;}\n]+)|borderRadius\s*:\s*(\d+(?:\.\d+)?))"
)
_FONT_DECL_RE = re.compile(
    r"(?:font-family\s*:\s*([^;}\n]+)|fontFamily\s*:\s*['\"`]([^'\"`]+)['\"`])"
)
_PASCAL_TAG_RE = re.compile(r"<([A-Z][a-zA-Z0-9]+)")
_ROUTE_PATH_RE = re.compile(r"<Route\b[^>]*?\bpath\s*=\s*['\"]([^'\"]+)['\"]")
_JSX_EXTS = (".tsx", ".jsx", ".ts", ".js")


def merge_config(user_config):
    """lint-config.json の内容をデフォルト設定にマージする。"""
    cfg = {
        "include": list(DEFAULT_CONFIG["include"]),
        "exclude": list(DEFAULT_CONFIG["exclude"]),
        "rules": dict(DEFAULT_CONFIG["rules"]),
        "allowRawValues": {
            k: list(v) for k, v in DEFAULT_CONFIG["allowRawValues"].items()
        },
    }
    if not user_config:
        return cfg
    if "include" in user_config:
        cfg["include"] = list(user_config["include"])
    if "exclude" in user_config:
        cfg["exclude"] = list(user_config["exclude"])
    cfg["rules"].update(user_config.get("rules", {}))
    for key, values in user_config.get("allowRawValues", {}).items():
        cfg["allowRawValues"][key] = list(values)
    return cfg


# ---------------------------------------------------------------------------
# テキスト前処理・正規化
# ---------------------------------------------------------------------------

def _blank(match):
    """マッチ範囲を改行以外スペースで置換（行番号を保存）。"""
    return re.sub(r"[^\n]", " ", match.group(0))


def strip_comments(text):
    """/* */ と // コメントを除去する（行番号保存、URL の // は除外）。"""
    text = re.sub(r"/\*.*?\*/", _blank, text, flags=re.DOTALL)
    text = re.sub(r"(?m)(?:^|(?<=\s))//.*$", lambda m: _blank(m), text)
    return text


def normalize_hex(value):
    """hex カラーを小文字 6/8 桁に正規化する（#abc → #aabbcc）。"""
    v = value.lower()
    if len(v) in (4, 5):  # #rgb / #rgba
        v = "#" + "".join(c * 2 for c in v[1:])
    return v


def _norm_value(value):
    """shadow / rgb 等の値文字列を比較用に正規化する。"""
    return re.sub(r",\s+", ",", re.sub(r"\s+", " ", value.strip())).lower()


def _kebab(name):
    return re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()


def _line_at(text, pos):
    return text.count("\n", 0, pos) + 1


def _font_names(stack):
    return [item.strip().strip("'\"").lower()
            for item in stack.split(",") if item.strip()]


def match_pattern(pattern, rel):
    """glob パターン（** 対応）と repo 相対パスの一致判定。

    "/" を含まないパターン（*.test.* 等）は basename に対して一致させる。
    """
    if "/" not in pattern:
        return fnmatch.fnmatch(os.path.basename(rel), pattern)
    i, n, out = 0, len(pattern), []
    while i < n:
        c = pattern[i]
        if c == "*":
            if pattern[i:i + 3] == "**/":
                out.append("(?:[^/]+/)*")
                i += 3
            elif pattern[i:i + 2] == "**":
                out.append(".*")
                i += 2
            else:
                out.append("[^/]*")
                i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    return re.match("".join(out) + r"\Z", rel) is not None


# ---------------------------------------------------------------------------
# コンテキスト構築（許可リスト・CSS 変数マップ）
# ---------------------------------------------------------------------------

def build_context(tokens, config, catalog=None, pages=None, layout_rules=None):
    """tokens / config / catalog / pages / layout-rules から lint 文脈を構築する。"""
    allow_raw = config["allowRawValues"]

    colors = dict(tokens.get("colors", {}))
    colors_dark = dict(tokens.get("colorsDark", {}))
    color_values = {}  # normalized hex -> token 名（suggestion 用）
    color_var_map = {}  # normalized hex -> CSS 変数名
    for name, value in {**colors_dark, **colors}.items():
        norm = normalize_hex(value)
        color_values[norm] = name
        color_var_map[norm] = f"--color-{_kebab(name)}"
    allow_colors = set(color_var_map) | {
        _norm_value(str(v)) for v in allow_raw.get("colors", [])
    }

    typography = tokens.get("typography", {})
    allow_fonts = set(SYSTEM_FONTS) | set(GENERIC_FONTS)
    for key in ("headingFont", "bodyFont", "codeFont"):
        allow_fonts.update(_font_names(typography.get(key, "")))

    scale = list(tokens.get("spacing", {}).get("scale", []))
    spacing_var_map = {float(v): f"--spacing-{i}" for i, v in enumerate(scale)}
    spacing_raw = {float(v) for v in allow_raw.get("spacing", [])
                   if isinstance(v, (int, float))}

    radius_var_map = {}
    for comp, spec in tokens.get("components", {}).items():
        if isinstance(spec, dict) and "borderRadius" in spec:
            singular = comp[:-1] if comp.endswith("s") else comp
            radius_var_map.setdefault(
                float(spec["borderRadius"]), f"--radius-{singular}")
    radius_raw = {_norm_value(str(v)) for v in allow_raw.get("borderRadius", [])}

    shadow_var_map = {}
    for level, spec in tokens.get("depth", {}).items():
        shadow = (spec or {}).get("shadow")
        if shadow and shadow != "none":
            shadow_var_map[_norm_value(shadow)] = f"--shadow-{level}"

    catalog_variants = {}
    for comp in (catalog or {}).get("components", []):
        variants = set()
        for var in comp.get("variants", []) or []:
            variants.add(var["name"] if isinstance(var, dict) else str(var))
        catalog_variants[comp["name"]] = variants

    return {
        "config": config,
        "colors": colors,
        "color_values": color_values,
        "color_var_map": color_var_map,
        "allow_colors": allow_colors,
        "allow_fonts": allow_fonts,
        "spacing_scale": set(spacing_var_map),
        "spacing_var_map": spacing_var_map,
        "spacing_raw": spacing_raw,
        "radius_var_map": radius_var_map,
        "radius_raw": radius_raw,
        "shadow_var_map": shadow_var_map,
        "catalog": catalog,
        "catalog_variants": catalog_variants,
        "pages": pages or {},
        "layout_rules": layout_rules,
    }


def _violation(rule, severity, rel, line, value, message, suggestion=None):
    v = {"rule": rule, "severity": severity, "file": rel, "line": line,
         "value": value, "message": message}
    if suggestion:
        v["suggestion"] = suggestion
    return v


def nearest_color(hex_value, colors):
    """RGB ユークリッド距離が最小のトークンを (name, hex) で返す。"""
    def rgb(h):
        h = normalize_hex(h)[1:7]
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    try:
        target = rgb(hex_value)
    except ValueError:
        return None
    best = None
    for name, value in colors.items():
        cand = rgb(value)
        dist = sum((a - b) ** 2 for a, b in zip(target, cand))
        if best is None or dist < best[0]:
            best = (dist, name, value)
    return (best[1], best[2]) if best else None


def _nearest_number(target, values):
    return min(values, key=lambda v: abs(v - target)) if values else None


# ---------------------------------------------------------------------------
# DL001-006: Token Compliance
# ---------------------------------------------------------------------------

def _blank_regions(text, spans):
    chars = list(text)
    for start, end in spans:
        for i in range(start, end):
            if chars[i] != "\n":
                chars[i] = " "
    return "".join(chars)


def check_colors(rel, text, ctx):
    """DL001（非トークン色）+ DL006 色（トークン色の直書き）。"""
    # box-shadow の値と url(...) は色スキャンの対象外
    # （shadow は DL005/DL006 が宣言単位で扱う）
    spans = [m.span() for m in _SHADOW_DECL_RE.finditer(text)]
    spans += [m.span() for m in re.finditer(r"url\([^)]*\)", text)]
    scan = _blank_regions(text, spans)

    violations = []
    for m in _HEX_RE.finditer(scan):
        norm = normalize_hex(m.group(0))
        line = _line_at(scan, m.start())
        if norm in ctx["color_var_map"]:
            var = ctx["color_var_map"][norm]
            violations.append(_violation(
                "DL006", "error", rel, line, m.group(0),
                f"トークン値 '{m.group(0)}' が直書きされています。"
                f"var({var}) を使用してください。"))
        elif norm not in ctx["allow_colors"]:
            near = nearest_color(m.group(0), ctx["colors"])
            suggestion = (f"最も近いトークン: colors.{near[0]} ({near[1]})"
                          if near else None)
            violations.append(_violation(
                "DL001", "error", rel, line, m.group(0),
                f"直書きカラーコード '{m.group(0)}' を検出。tokens.json に定義された"
                "色または CSS 変数 var(--color-*) を使用してください。",
                suggestion))
    for m in _FUNC_COLOR_RE.finditer(scan):
        norm = _norm_value(m.group(0))
        if norm in ctx["allow_colors"]:
            continue
        violations.append(_violation(
            "DL001", "error", rel, _line_at(scan, m.start()), m.group(0),
            f"直書きカラー '{m.group(0)}' を検出。tokens.json に定義された"
            "色または CSS 変数 var(--color-*) を使用してください。"))
    return violations


def check_fonts(rel, text, ctx):
    """DL002: 直書きフォント。"""
    violations = []
    for m in _FONT_DECL_RE.finditer(text):
        value = m.group(1) or m.group(2)
        for item in value.split(","):
            item = item.strip()
            if not item or item.lower().startswith("var("):
                continue
            name = item.strip("'\"`").strip()
            if name.lower() not in ctx["allow_fonts"]:
                violations.append(_violation(
                    "DL002", "error", rel, _line_at(text, m.start()), name,
                    f"直書きフォント '{name}' を検出。tokens.json に定義された"
                    "フォントまたは var(--font-*) を使用してください。"))
    return violations


def check_spacing(rel, text, ctx):
    """DL003（スケール外 spacing）+ DL006 spacing（スケール値の直書き）。"""
    violations = []
    for m in _SPACING_PROP_RE.finditer(text):
        value = m.group(1)
        line = _line_at(text, m.start())
        for px in _PX_RE.finditer(value):
            num = float(px.group(1))
            if num in ctx["spacing_raw"]:
                continue
            if num in ctx["spacing_scale"]:
                var = ctx["spacing_var_map"][num]
                violations.append(_violation(
                    "DL006", "error", rel, line, px.group(0),
                    f"トークン値 '{px.group(0)}' が直書きされています。"
                    f"var({var}) を使用してください。"))
            else:
                near = _nearest_number(num, ctx["spacing_scale"])
                suggestion = (f"最も近いスケール値: {near:g}px"
                              if near is not None else None)
                violations.append(_violation(
                    "DL003", "warn", rel, line, px.group(0),
                    f"スケール外の spacing '{px.group(0)}' を検出。"
                    "tokens.json の spacing.scale の値を使用してください。",
                    suggestion))
    return violations


def check_radius(rel, text, ctx):
    """DL004（未定義 border-radius）+ DL006 radius。"""
    violations = []
    for m in _RADIUS_DECL_RE.finditer(text):
        line = _line_at(text, m.start())
        items = m.group(1).split() if m.group(1) else [f"{m.group(2)}px"]
        for item in items:
            item = item.strip().rstrip(";")
            if not item or item.lower().startswith("var("):
                continue
            if _norm_value(item) in ctx["radius_raw"]:
                continue
            px = _PX_RE.fullmatch(item)
            if not px:
                continue  # % や em はここでは扱わない（raw 許可のみ照合）
            num = float(px.group(1))
            if num in {float(v) for v in ctx["radius_raw"]
                       if re.fullmatch(r"\d+(?:\.\d+)?", v)}:
                continue
            if num in ctx["radius_var_map"]:
                var = ctx["radius_var_map"][num]
                violations.append(_violation(
                    "DL006", "error", rel, line, item,
                    f"トークン値 '{item}' が直書きされています。"
                    f"var({var}) を使用してください。"))
            else:
                near = _nearest_number(num, list(ctx["radius_var_map"]))
                suggestion = (f"最も近いトークン値: {near:g}px"
                              if near is not None else None)
                violations.append(_violation(
                    "DL004", "warn", rel, line, item,
                    f"未定義の border-radius '{item}' を検出。tokens.json の"
                    " borderRadius 値を使用してください。", suggestion))
    return violations


def check_shadows(rel, text, ctx):
    """DL005(未定義 shadow) + DL006 shadow。"""
    violations = []
    for m in _SHADOW_DECL_RE.finditer(text):
        value = (m.group(1) or m.group(2)).strip().rstrip(";").strip()
        norm = _norm_value(value)
        line = _line_at(text, m.start())
        if norm == "none" or norm.startswith("var("):
            continue
        if norm in ctx["shadow_var_map"]:
            var = ctx["shadow_var_map"][norm]
            violations.append(_violation(
                "DL006", "error", rel, line, value,
                f"トークン値 '{value}' が直書きされています。"
                f"var({var}) を使用してください。"))
        else:
            violations.append(_violation(
                "DL005", "warn", rel, line, value,
                f"未定義の box-shadow '{value}' を検出。tokens.json の"
                " depth.*.shadow の値を使用してください。"))
    return violations


# ---------------------------------------------------------------------------
# DL101-103: Component Compliance
# ---------------------------------------------------------------------------

def _used_components(text):
    """PascalCase タグ名 → 初出位置。"""
    seen = {}
    for m in _PASCAL_TAG_RE.finditer(text):
        seen.setdefault(m.group(1), m.start())
    return seen


def check_components(rel, text, ctx):
    """DL101: 未登録コンポーネント。"""
    allowed = set(ctx["catalog_variants"]) | STANDARD_COMPONENTS
    violations = []
    for name, pos in sorted(_used_components(text).items(), key=lambda x: x[1]):
        if name in allowed:
            continue
        registered = ", ".join(sorted(ctx["catalog_variants"])) or "(なし)"
        violations.append(_violation(
            "DL101", "error", rel, _line_at(text, pos), name,
            f"未登録コンポーネント '{name}' を検出。component-catalog.json に"
            "定義されたコンポーネントのみ使用してください。",
            f"catalog に登録するか、既存コンポーネント ({registered}) で"
            "代替してください。"))
    return violations


def check_variants(rel, text, ctx):
    """DL102: 未登録バリアント。"""
    violations = []
    for name, variants in ctx["catalog_variants"].items():
        pattern = re.compile(
            rf"<{re.escape(name)}\b[^>]*?\bvariant\s*=\s*"
            rf"(?:['\"]([^'\"]+)['\"]|\{{\s*['\"]([^'\"]+)['\"]\s*\}})")
        for m in pattern.finditer(text):
            value = m.group(1) or m.group(2)
            if value in variants:
                continue
            known = ", ".join(sorted(variants)) or "(なし)"
            violations.append(_violation(
                "DL102", "error", rel, _line_at(text, m.start()), value,
                f"コンポーネント '{name}' に未登録の variant '{value}' を検出。"
                f"定義済み variant: {known}"))
    return violations


def _is_token_style_prop(prop):
    return prop in TOKEN_STYLE_PROPS or prop.startswith(_TOKEN_STYLE_PREFIXES)


def check_style_overrides(rel, text, ctx):
    """DL103: catalog コンポーネントへの inline style によるトークン上書き。"""
    violations = []
    for name in ctx["catalog_variants"]:
        pattern = re.compile(
            rf"<{re.escape(name)}\b[^>]*?\bstyle\s*=\s*\{{\{{(.*?)\}}\}}",
            re.DOTALL)
        for m in pattern.finditer(text):
            props = re.findall(r"([A-Za-z]+)\s*:", m.group(1))
            flagged = sorted({p for p in props if _is_token_style_prop(p)})
            if not flagged:
                continue
            violations.append(_violation(
                "DL103", "warn", rel, _line_at(text, m.start()),
                ", ".join(flagged),
                f"コンポーネント '{name}' の inline style がトークン対象"
                f"プロパティ ({', '.join(flagged)}) を上書きしています。"
                "レイアウト目的以外の上書きは tokens / variant で表現してください。"))
    return violations


# ---------------------------------------------------------------------------
# DL201-204: Page / Layout Compliance
# ---------------------------------------------------------------------------

def _page_slug(route_path):
    slug = route_path.strip("/").replace("/", "-")
    return slug or "home"


def _page_def_for(rel, pages):
    stem = os.path.splitext(os.path.basename(rel))[0]
    for key in (_kebab(stem), stem.lower()):
        if key in pages:
            return key, pages[key]
    return None, None


def check_page_defs(rel, text, ctx):
    """DL201: page-def 未定義ページ（ルーティング定義の近似検出）。"""
    violations = []
    pages = ctx["pages"]
    for m in _ROUTE_PATH_RE.finditer(text):
        slug = _page_slug(m.group(1))
        candidates = {slug, "index"} if slug == "home" else {slug}
        if candidates & set(pages):
            continue
        violations.append(_violation(
            "DL201", "warn", rel, _line_at(text, m.start()), m.group(1),
            f"ルート '{m.group(1)}' に対応する page-def "
            f"(.design/pages/{slug}.json) がありません。"
            "新規ページは page-def を先に作成してください。"))
    return violations


def check_allowed_components(rel, text, ctx):
    """DL202: page-def の allowedComponents 違反。"""
    _, page_def = _page_def_for(rel, ctx["pages"])
    if not page_def:
        return []
    allowed = page_def.get("allowedComponents")
    if not isinstance(allowed, list):
        return []
    permitted = set(allowed) | STANDARD_COMPONENTS
    violations = []
    for name, pos in sorted(_used_components(text).items(), key=lambda x: x[1]):
        if name in permitted:
            continue
        violations.append(_violation(
            "DL202", "error", rel, _line_at(text, pos), name,
            f"page-def の allowedComponents にない '{name}' を検出。"
            f"許可: {', '.join(sorted(allowed))}"))
    return violations


def check_section_order(rel, text, ctx):
    """DL203: page-def の sections[].order と実装の出現順の不一致。"""
    _, page_def = _page_def_for(rel, ctx["pages"])
    if not page_def:
        return []
    sections = sorted(
        (s for s in page_def.get("sections", []) if "id" in s),
        key=lambda s: s.get("order", 0))
    found = []
    for section in sections:
        sid = section["id"]
        m = re.search(
            rf"(?:className|id)\s*=\s*['\"][^'\"]*"
            rf"(?<![\w-]){re.escape(sid)}(?![\w-])[^'\"]*['\"]", text)
        if m:
            found.append((sid, m.start()))
    positions = [pos for _, pos in found]
    if positions == sorted(positions):
        return []
    expected = " → ".join(sid for sid, _ in found)
    actual = " → ".join(
        sid for sid, _ in sorted(found, key=lambda x: x[1]))
    return [_violation(
        "DL203", "warn", rel, _line_at(text, found[0][1]), actual,
        f"セクション順序が page-def と一致しません。期待: {expected} / "
        f"実装: {actual}")]


def check_layout_rules(rel, text, ctx):
    """DL204: layout-rules.json の enforcement=lint 制約違反。"""
    violations = []
    constraints = (ctx["layout_rules"] or {}).get("constraints", [])
    for c in constraints:
        if c.get("enforcement") != "lint" or not c.get("checkPattern"):
            continue
        try:
            pattern = re.compile(c["checkPattern"])
        except re.error:
            continue  # 壊れた checkPattern は fail-safe でスキップ
        for m in pattern.finditer(text):
            violations.append(_violation(
                "DL204", c.get("severity", "warn"), rel,
                _line_at(text, m.start()), m.group(0).strip(),
                f"レイアウトルール違反 [{c.get('id', '?')}]: "
                f"{c.get('rule', '')}"))
    return violations


# ---------------------------------------------------------------------------
# ファイル単位の lint と集約
# ---------------------------------------------------------------------------

def lint_text(rel, text, ctx):
    """1ファイル分のテキストに全ルールを適用し、violation リストを返す。"""
    stripped = strip_comments(text)
    violations = []
    violations += check_colors(rel, stripped, ctx)
    violations += check_fonts(rel, stripped, ctx)
    violations += check_spacing(rel, stripped, ctx)
    violations += check_radius(rel, stripped, ctx)
    violations += check_shadows(rel, stripped, ctx)
    if rel.endswith(_JSX_EXTS):
        if ctx["catalog"]:
            violations += check_components(rel, stripped, ctx)
            violations += check_variants(rel, stripped, ctx)
            violations += check_style_overrides(rel, stripped, ctx)
        if ctx["pages"]:
            violations += check_page_defs(rel, stripped, ctx)
            violations += check_allowed_components(rel, stripped, ctx)
            violations += check_section_order(rel, stripped, ctx)
    if ctx["layout_rules"]:
        violations += check_layout_rules(rel, stripped, ctx)

    rules = ctx["config"]["rules"]
    out = []
    for v in violations:
        configured = rules.get(v["rule"])
        if configured == "off":
            continue
        # DL204 の severity は constraint 定義が優先（契約仕様）
        if configured and v["rule"] != "DL204":
            v["severity"] = configured
        out.append(v)
    return out


def summarize(violations, files_scanned):
    """violation リストをレポート形式に集約する。"""
    errors = sum(1 for v in violations if v.get("severity") == "error")
    warnings = sum(1 for v in violations if v.get("severity") == "warn")
    return {
        "summary": {
            "filesScanned": files_scanned,
            "totalViolations": len(violations),
            "errors": errors,
            "warnings": warnings,
            "result": "FAIL" if errors else "PASS",
        },
        "violations": violations,
    }


def _load_json(path):
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def collect_files(root, include, exclude):
    """include/exclude パターンに従い lint 対象の相対パスを列挙する。"""
    matched = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in {".git", "node_modules", "__pycache__"}]
        for name in sorted(filenames):
            rel = os.path.relpath(
                os.path.join(dirpath, name), root).replace(os.sep, "/")
            if not any(match_pattern(p, rel) for p in include):
                continue
            if any(match_pattern(p, rel) for p in exclude):
                continue
            matched.append(rel)
    return sorted(matched)


def run(root, design_dir=".design"):
    """lint を実行し (report, exit_code) を返す。tokens.json 不在は (None, 2)。"""
    design = os.path.join(root, design_dir)
    tokens = _load_json(os.path.join(design, "tokens.json"))
    if tokens is None:
        return None, 2
    config = merge_config(_load_json(os.path.join(design, "lint-config.json")))
    catalog = _load_json(os.path.join(design, "component-catalog.json"))
    layout_rules = _load_json(os.path.join(design, "layout-rules.json"))
    pages = {}
    pages_dir = os.path.join(design, "pages")
    if os.path.isdir(pages_dir):
        for name in sorted(os.listdir(pages_dir)):
            if name.endswith(".json"):
                loaded = _load_json(os.path.join(pages_dir, name))
                if loaded is not None:
                    pages[os.path.splitext(name)[0]] = loaded

    ctx = build_context(tokens, config, catalog=catalog, pages=pages,
                        layout_rules=layout_rules)
    files = collect_files(root, config["include"], config["exclude"])
    violations = []
    for rel in files:
        with open(os.path.join(root, rel), encoding="utf-8",
                  errors="replace") as f:
            violations += lint_text(rel, f.read(), ctx)
    report = summarize(violations, files_scanned=len(files))
    return report, (1 if report["summary"]["errors"] else 0)


def _print_summary(report):
    s = report["summary"]
    print("🔍 Design Lint Results")
    print("━" * 23)
    print(f"Files scanned: {s['filesScanned']}")
    print(f"Violations: {s['totalViolations']} "
          f"({s['errors']} errors, {s['warnings']} warnings)")
    by_rule = {}
    for v in report["violations"]:
        by_rule.setdefault(v["rule"], []).append(v)
    for rule in sorted(by_rule):
        sev = by_rule[rule][0]["severity"]
        mark = "❌" if sev == "error" else "⚠️ "
        print(f"{mark} {rule}: {len(by_rule[rule])} violations")
    if s["result"] == "FAIL":
        print(f"\nResult: FAIL ({s['errors']} errors)")
    elif s["warnings"]:
        print("\nResult: PASS (with warnings)")
    else:
        print("\nResult: PASS")


def main():
    parser = argparse.ArgumentParser(
        description="Design token lint (.design/tokens.json 基準)")
    parser.add_argument("--root", default=".", help="プロジェクトルート")
    parser.add_argument("--design-dir", default=".design",
                        help=".design ディレクトリの相対パス")
    parser.add_argument("--json", action="store_true",
                        help="レポート全体を JSON で stdout に出力")
    parser.add_argument("--output", default=None,
                        help="レポート JSON の保存先パス")
    args = parser.parse_args()

    report, exit_code = run(args.root, design_dir=args.design_dir)
    if report is None:
        print("error: tokens.json が見つかりません。"
              "design-scaffold で生成してください。", file=sys.stderr)
        return 2
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
            f.write("\n")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_summary(report)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
