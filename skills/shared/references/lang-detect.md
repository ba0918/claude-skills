# Language Detection Contract

複数スキルが共有する言語・フレームワーク検出の契約仕様。
消費スキルはこのファイルを参照し、同じ手順で言語検出を行う。

> **利用スキル**: attack-review, generate-review-rules（将来: codebase-review）

## 1. Detection Procedure

以下の手順で対象プロジェクトの言語・フレームワーク構成を特定する。

### Step 1: ビルドファイル Glob

プロジェクトルートおよび直下1階層を Glob で走査し、以下のマーカーファイルを検索する。

| マーカーファイル | 言語 | エコシステム |
|----------------|------|------------|
| `Cargo.toml` | Rust | cargo |
| `package.json` | TypeScript / JavaScript | npm / yarn / pnpm / bun |
| `go.mod` | Go | go modules |
| `pyproject.toml` | Python | poetry / hatch / pdm |
| `requirements.txt` | Python | pip |
| `setup.py` / `setup.cfg` | Python | setuptools |
| `pubspec.yaml` | Dart | pub |
| `composer.json` | PHP | composer |
| `build.gradle` / `build.gradle.kts` | Java / Kotlin | gradle |
| `pom.xml` | Java / Kotlin | maven |
| `Gemfile` | Ruby | bundler |
| `*.csproj` / `*.sln` | C# | .NET |

### Step 2: レガシー / 静的サイト検出

マーカーファイルが見つからない場合の補助検出:

| パターン | 言語 | 備考 |
|---------|------|------|
| `*.php` がルートレベルに存在（composer.json なし） | PHP (legacy) | PHP 5.x 系を含むレガシー環境 |
| `index.html` / `*.html` がルートレベルに存在 | HTML / CSS | 静的サイト、または SPA のビルド出力 |

### Step 3: フレームワーク検出

マーカーファイルの **依存関係セクション** を読み、フレームワークを特定する。

#### package.json (dependencies / devDependencies)

| パッケージ名 | フレームワーク | role |
|-------------|-------------|------|
| `express` | Express.js | server |
| `fastify` | Fastify | server |
| `hono` | Hono | server |
| `koa` | Koa | server |
| `@nestjs/core` | NestJS | server |
| `next` | Next.js | both |
| `nuxt` | Nuxt.js | both |
| `@remix-run/node` | Remix | both |
| `react` (サーバーFW なし) | React SPA | client |
| `vue` (サーバーFW なし) | Vue.js SPA | client |
| `svelte` / `@sveltejs/kit` | SvelteKit / Svelte | both / client |
| `@angular/core` | Angular | client |

#### pyproject.toml / requirements.txt

| パッケージ名 | フレームワーク | role |
|-------------|-------------|------|
| `django` | Django | server |
| `flask` | Flask | server |
| `fastapi` | FastAPI | server |
| `starlette` | Starlette | server |
| `tornado` | Tornado | server |
| `streamlit` | Streamlit | both |

#### go.mod

| モジュールパス（部分一致） | フレームワーク | role |
|--------------------------|-------------|------|
| `github.com/gin-gonic/gin` | Gin | server |
| `github.com/labstack/echo` | Echo | server |
| `github.com/gofiber/fiber` | Fiber | server |
| `net/http` (標準ライブラリ) | stdlib | server |
| `connectrpc.com` | Connect RPC | server |

#### Cargo.toml

| クレート名 | フレームワーク | role |
|-----------|-------------|------|
| `actix-web` | Actix Web | server |
| `axum` | Axum | server |
| `rocket` | Rocket | server |
| `warp` | Warp | server |
| `yew` / `leptos` / `dioxus` | WASM UI | client |

#### pubspec.yaml

| パッケージ名 | フレームワーク | role |
|-------------|-------------|------|
| `flutter` | Flutter | client |
| `shelf` / `dart_frog` | Dart server | server |

#### composer.json

| パッケージ名 | フレームワーク | role |
|-------------|-------------|------|
| `laravel/framework` | Laravel | both |
| `symfony/framework-bundle` | Symfony | server |
| `slim/slim` | Slim | server |
| `wordpress` (type: wordpress-plugin/theme) | WordPress | server |

### Step 4: role 判定ルール

1. **明示的 role**: フレームワーク検出表の role 列をそのまま使用
2. **both の展開**: `both` は server と client 両方の観点で分析対象
3. **FW 未検出時のデフォルト**:
   - バックエンド言語（Go, Rust, Python, PHP, Java/Kotlin, Ruby, C#）→ `server`
   - フロントエンド資産のみ（HTML/CSS, package.json + FW なし）→ `client`
   - 判定不能 → `both`（安全側に倒す）

### Step 5: 出力形式

検出結果は以下の構造で返す（JSON 表現）:

```json
{
  "detected_languages": [
    {
      "language": "typescript",
      "role": "client",
      "framework": "React",
      "marker_file": "package.json"
    },
    {
      "language": "go",
      "role": "server",
      "framework": "Gin",
      "marker_file": "go.mod"
    }
  ],
  "is_monorepo": false,
  "primary_language": "go"
}
```

- `primary_language`: サーバーサイド言語を優先。複数ある場合はマーカーファイルが最初に見つかったもの
- `is_monorepo`: マーカーファイルがサブディレクトリに複数見つかった場合 `true`

## 2. マルチ言語プロジェクトの扱い

モノレポや複合プロジェクトでは複数の言語が検出される。消費スキルは以下のルールで言語情報を利用する:

1. **全言語の情報を context.json に含める**（フィルタリングは消費側の責任）
2. **エージェントへの言語プロファイル注入時**:
   - server 専用エージェント → `role: "server"` または `"both"` の言語のみ
   - client 専用エージェント → `role: "client"` または `"both"` の言語のみ
   - 共通エージェント → 全言語
3. **スコープ絞り込み**: 特定ディレクトリが指定された場合、そのディレクトリのマーカーファイルのみ使用

## 3. 拡張ポイント

新しい言語を追加する場合:

1. §1 Step 1 のマーカーファイル表に行を追加
2. §1 Step 3 に該当フレームワーク検出表を追加
3. §1 Step 4 の role デフォルトに言語を追加
4. 消費スキル固有の言語プロファイル（例: `lang-profiles.md`）に該当セクションを追加

> **Note**: この契約は仕様定義であり、実行可能コードではない。各消費スキルがこの手順を SKILL.md のワークフロー内で実行する。
