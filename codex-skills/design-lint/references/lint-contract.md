# Design Lint Contract

design-lint スキルの lint ルール仕様。全ルールは `.design/tokens.json` を正解データとして参照する。

## 前提条件

lint 実行前に以下のファイルが存在すること:

- `.design/tokens.json` — 検証の正解データ
- `.design/lint-config.json` — lint 設定（省略時はデフォルト値を使用）

## lint-config.json

```json
{
  "include": ["src/**/*.tsx", "src/**/*.css", "src/**/*.jsx", "src/**/*.ts"],
  "exclude": ["node_modules/**", ".design/**", "*.test.*", "*.spec.*"],
  "rules": {
    "DL001": "error",
    "DL002": "error",
    "DL003": "warn",
    "DL004": "warn",
    "DL005": "warn",
    "DL006": "error"
  },
  "allowRawValues": {
    "colors": ["transparent", "inherit", "currentColor", "white", "black"],
    "spacing": [0, "auto"],
    "borderRadius": [0, "50%", "9999px"]
  }
}
```

## Phase 1: Token Compliance ルール (DL001-DL006)

### DL001: 直書きカラーコード

**検出対象:** CSS/JSX で `#XXXXXX`、`#XXX`、`rgb()`、`rgba()`、`hsl()`、`hsla()` が tokens に定義されていないカラーを使用している。

**検出方法:**
1. ファイルから以下のパターンを正規表現で抽出:
   - `#[0-9a-fA-F]{3,8}` — hex カラー
   - `rgba?\([^)]+\)` — rgb/rgba
   - `hsla?\([^)]+\)` — hsl/hsla
2. tokens.json の `colors` オブジェクトの全値を許可リストとして構築
3. `allowRawValues.colors` の値も許可リストに追加
4. 抽出した値が許可リストにない場合 → 違反

**除外:**
- CSS custom property 経由の使用（`var(--color-*)`)` は OK
- コメント内の値は無視
- `allowRawValues.colors` に明示された値（`transparent` 等）は OK

**レポート例:**
```json
{
  "rule": "DL001",
  "severity": "error",
  "file": "src/components/Header.tsx",
  "line": 42,
  "column": 15,
  "value": "#FF6B6B",
  "message": "直書きカラーコード '#FF6B6B' を検出。tokens.json に定義された色または CSS 変数 var(--color-*) を使用してください。",
  "suggestion": "最も近いトークン: colors.error (#DC2626)"
}
```

### DL002: 直書きフォント

**検出対象:** `font-family` に tokens.json の `typography.headingFont`、`typography.bodyFont`、`typography.codeFont` に定義されていないフォントを使用。

**検出方法:**
1. `font-family:` 宣言を正規表現で抽出
2. tokens.json の typography フォント名を許可リストとして構築
3. system font stack（`-apple-system`, `BlinkMacSystemFont`, `system-ui` 等）は許可
4. フォールバック（`sans-serif`, `serif`, `monospace`）は許可
5. 上記以外のフォント名が含まれている場合 → 違反

### DL003: 直書き spacing

**検出対象:** `padding`、`margin`、`gap`、`top`、`right`、`bottom`、`left` に tokens.json の `spacing.scale` に定義されていない px 値を使用。

**検出方法:**
1. spacing 関連 CSS プロパティの値を正規表現で抽出
2. px 値を数値に変換
3. tokens.json の `spacing.scale` 配列と照合
4. `allowRawValues.spacing` の値（`0`, `auto`）は許可
5. scale にない値 → 違反

**除外:**
- `%`, `vw`, `vh`, `em`, `rem` 単位は spacing scale の範囲外として許可
- ショートハンド（`padding: 12px 24px`）は各値を個別に検証

### DL004: 直書き border-radius

**検出対象:** `border-radius` に tokens.json の `components.{type}.borderRadius` に定義されていない値を使用。

**検出方法:**
1. `border-radius` 宣言の値を抽出
2. tokens.json の全 borderRadius 値を許可リストとして構築
3. `allowRawValues.borderRadius` の値（`0`, `50%`, `9999px`）は許可
4. リストにない値 → 違反

### DL005: 直書き shadow

**検出対象:** `box-shadow` に tokens.json の `depth.*.shadow` に定義されていない shadow 値を使用。

**検出方法:**
1. `box-shadow` 宣言の値を抽出
2. tokens.json の depth 全レベルの shadow 値を許可リストとして構築
3. `none` は許可
4. リストにない値 → 違反

### DL006: CSS 変数未使用

**検出対象:** tokens.json に対応する CSS 変数が存在するのに、直書き値を使用している。
DL001-005 の上位ルール。直書き値が tokens に定義された値と **一致する** 場合でも、CSS 変数経由でないなら違反。

**検出方法:**
1. tokens.json の全値を CSS 変数名にマッピング（design-system-contract の命名規則に従う）
2. ソースコード内で tokens の値が直書きで使用されている箇所を検出
3. 同じ値が `var(--*)` 経由でなく使用されている → 違反

**レポート例:**
```json
{
  "rule": "DL006",
  "severity": "error",
  "file": "src/components/Button.tsx",
  "line": 15,
  "value": "#2563EB",
  "message": "トークン値 '#2563EB' が直書きされています。var(--color-primary) を使用してください。"
}
```

## lint 実行フロー

```
1. .design/tokens.json を shell（cat）で読み込む
2. .design/lint-config.json を shell（cat）で読み込む（なければデフォルト）
3. include パターンに一致するファイル一覧を shell（find）で取得
4. exclude パターンを除外
5. 各ファイルを shell（cat）で読み込み、有効な全ルールを適用
6. 違反を収集
7. レポート出力:
   - サマリー: {total} violations ({errors} errors, {warnings} warnings)
   - 詳細: ファイル別・ルール別の違反一覧
8. 終了コード判定:
   - error が 1つ以上 → FAIL
   - warn のみ → PASS (with warnings)
   - 違反なし → PASS
```

## レポート形式

### サマリー

```
🔍 Design Lint Results
━━━━━━━━━━━━━━━━━━━━━━━
Files scanned: 24
Violations: 7 (5 errors, 2 warnings)

❌ DL001 (color): 3 violations
❌ DL006 (css-var): 2 violations
⚠️  DL003 (spacing): 2 violations

Result: FAIL (5 errors)
```

### 詳細（JSON）

```json
{
  "summary": {
    "filesScanned": 24,
    "totalViolations": 7,
    "errors": 5,
    "warnings": 2,
    "result": "FAIL"
  },
  "violations": [
    {
      "rule": "DL001",
      "severity": "error",
      "file": "src/components/Header.tsx",
      "line": 42,
      "value": "#FF6B6B",
      "message": "...",
      "suggestion": "..."
    }
  ]
}
```

## Phase 2: Component Compliance ルール (DL101-DL103)

`.design/component-catalog.json` が存在する場合にのみ有効。存在しない場合はこのカテゴリ全体をスキップする。

### DL101: 未登録コンポーネント

**検出対象:** catalog.json に定義されていないカスタムコンポーネントの使用。

**検出方法:**
1. JSX ファイルから PascalCase の要素名を正規表現で抽出: `/<([A-Z][a-zA-Z0-9]+)/g`
2. catalog.json の `components[].name` 一覧を許可リストとして構築
3. 以下は除外（違反としない）:
   - HTML ネイティブ要素: `div`, `span`, `p`, `a`, `button`, `input`, `form`, `img`, `h1`-`h6`, `ul`, `ol`, `li`, `table`, `tr`, `td`, `th`, `thead`, `tbody`, `section`, `article`, `header`, `footer`, `nav`, `main`, `aside`, `label`, `select`, `textarea`, `option`, `svg`, `path`, `circle`, `rect`, `line`
   - React 標準: `Fragment`, `Suspense`, `StrictMode`, `Profiler`, `Provider`, `Consumer`
   - Preact 標準: `Fragment`
   - テストユーティリティ: テストファイル内のコンポーネントは対象外（lint-config の exclude で制御）

**severity:** `error`

### DL102: 未登録バリアント

**検出対象:** catalog コンポーネントに対して、catalog.json に定義されていない variant 値を prop として渡している。

**検出方法:**
1. catalog の各コンポーネント名 `{Name}` に対して:
   - `<{Name}\s+[^>]*variant\s*=\s*["']([^"']+)["']` で variant 値を抽出
   - `<{Name}\s+[^>]*variant\s*=\s*\{["']([^"']+)["']\}` でも抽出（JSX expression）
2. catalog.json の `components[name={Name}].variants[].name` を許可リストとして構築
3. 許可リストにない variant 値 → 違反

**severity:** `error`

### DL103: 直接スタイル上書き

**検出対象:** catalog コンポーネントへの inline style による tokens 対象プロパティの上書き。

**検出方法:**
1. catalog の各コンポーネント名 `{Name}` に対して:
   - `<{Name}\s+[^>]*style\s*=\s*\{\{([^}]+)\}\}` で inline style を抽出
   - `<{Name}\s+[^>]*style\s*=\s*\{([^}]+)\}` でも抽出
2. inline style 内の CSS プロパティを解析
3. 以下のトークン対象プロパティが含まれている場合 → 違反:
   - `color`, `backgroundColor`, `background`
   - `fontFamily`, `fontSize`, `fontWeight`
   - `padding`, `margin`, `gap` (spacing)
   - `borderRadius`
   - `boxShadow`
   - `border`, `borderColor`
4. 以下のレイアウトプロパティは許可（違反としない）:
   - `display`, `position`, `top`, `left`, `right`, `bottom`
   - `width`, `height`, `maxWidth`, `minWidth`, `maxHeight`, `minHeight`
   - `flex`, `flexDirection`, `flexGrow`, `flexShrink`, `flexBasis`
   - `gridColumn`, `gridRow`, `gridArea`
   - `overflow`, `zIndex`, `visibility`, `transform`
   - `textAlign`, `verticalAlign`

**severity:** `warn`（完全に禁止すると柔軟性がなくなるため、警告レベル）

## Phase 3: Page/Layout Compliance ルール (DL201-DL204)

`.design/pages/` と `.design/layout-rules.json` が存在する場合にのみ有効。

### DL201: page-def 未定義ページ

**検出対象:** `.design/pages/` に定義がないページの作成。

**検出方法:**
1. ソースコード内のルーティング定義（React Router の `<Route>`, Next.js の `pages/` ディレクトリ等）からページ一覧を抽出
2. `.design/pages/` 内の JSON ファイル名と照合
3. page-def が存在しないページ → 違反

**注意:** フレームワーク固有のルーティングパターンを検出するため、正規表現ベースでの近似検出になる。

**severity:** `warn`（新規ページ追加時に page-def を先に作ることを促す）

### DL202: allowedComponents 違反

**検出対象:** ページ定義の `allowedComponents` に含まれていないコンポーネントの使用。

**検出方法:**
1. 各ページファイル（ルーティングから特定 or ファイル名マッチ）内で使用されているコンポーネントを抽出
2. 対応する page-def の `allowedComponents` と照合
3. `allowedComponents` が定義されているのに、リスト外のコンポーネントが使用されている → 違反

**severity:** `error`

### DL203: セクション順序違反

**検出対象:** page-def の `sections[].order` と異なる順序でセクションが配置されている。

**検出方法:**
1. ページファイル内の セクション ID（`className` や `id` 属性から抽出）の出現順を取得
2. page-def の sections を `order` でソートした順序と比較
3. 順序が異なる → 違反

**severity:** `warn`

### DL204: レイアウトルール違反

**検出対象:** `layout-rules.json` の `constraints` に定義された `enforcement: "lint"` のルールに違反。

**検出方法:**
1. layout-rules.json の constraints から `enforcement: "lint"` のルールを抽出
2. 各ルールの `checkPattern`（正規表現）をソースコードに適用
3. パターンに一致する違反を検出

**例:**
```json
{
  "id": "LC003",
  "rule": "grid-template-columns の列数 ≤ 3",
  "enforcement": "lint",
  "checkPattern": "grid-template-columns\\s*:.*\\b(repeat\\(([4-9]|\\d{2,})|.*\\s+.*\\s+.*\\s+)"
}
```

**severity:** constraints の `severity` フィールドに従う（デフォルト: `warn`）
