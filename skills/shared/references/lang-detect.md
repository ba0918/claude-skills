# Language Detection Contract

The contract specification for language and framework detection shared by several skills.
Consuming skills reference this file and perform language detection by the same procedure.

> **Consuming skills**: attack-review, generate-review-rules (future: codebase-review)

## 1. Detection Procedure

Identify the target project's language and framework composition by the following procedure.

### Step 1: Glob the Build Files

Glob the project root and one level below it, searching for the following marker files.

| Marker file | Language | Ecosystem |
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

### Step 2: Legacy / Static-site Detection

Auxiliary detection for when no marker file is found:

| Pattern | Language | Notes |
|---------|------|------|
| `*.php` exists at the root level (no composer.json) | PHP (legacy) | A legacy environment, including the PHP 5.x line |
| `index.html` / `*.html` exists at the root level | HTML / CSS | A static site, or the build output of an SPA |

### Step 3: Framework Detection

Read the **dependency section** of the marker file and identify the framework.

#### package.json (dependencies / devDependencies)

| Package name | Framework | role |
|-------------|-------------|------|
| `express` | Express.js | server |
| `fastify` | Fastify | server |
| `hono` | Hono | server |
| `koa` | Koa | server |
| `@nestjs/core` | NestJS | server |
| `next` | Next.js | both |
| `nuxt` | Nuxt.js | both |
| `@remix-run/node` | Remix | both |
| `react` (no server framework) | React SPA | client |
| `vue` (no server framework) | Vue.js SPA | client |
| `svelte` / `@sveltejs/kit` | SvelteKit / Svelte | both / client |
| `@angular/core` | Angular | client |

#### pyproject.toml / requirements.txt

| Package name | Framework | role |
|-------------|-------------|------|
| `django` | Django | server |
| `flask` | Flask | server |
| `fastapi` | FastAPI | server |
| `starlette` | Starlette | server |
| `tornado` | Tornado | server |
| `streamlit` | Streamlit | both |

#### go.mod

| Module path (substring match) | Framework | role |
|--------------------------|-------------|------|
| `github.com/gin-gonic/gin` | Gin | server |
| `github.com/labstack/echo` | Echo | server |
| `github.com/gofiber/fiber` | Fiber | server |
| `net/http` (standard library) | stdlib | server |
| `connectrpc.com` | Connect RPC | server |

#### Cargo.toml

| Crate name | Framework | role |
|-----------|-------------|------|
| `actix-web` | Actix Web | server |
| `axum` | Axum | server |
| `rocket` | Rocket | server |
| `warp` | Warp | server |
| `yew` / `leptos` / `dioxus` | WASM UI | client |

#### pubspec.yaml

| Package name | Framework | role |
|-------------|-------------|------|
| `flutter` | Flutter | client |
| `shelf` / `dart_frog` | Dart server | server |

#### composer.json

| Package name | Framework | role |
|-------------|-------------|------|
| `laravel/framework` | Laravel | both |
| `symfony/framework-bundle` | Symfony | server |
| `slim/slim` | Slim | server |
| `wordpress` (type: wordpress-plugin/theme) | WordPress | server |

### Step 4: role Decision Rules

1. **Explicit role**: use the role column of the framework detection tables as-is
2. **Expanding both**: `both` means the target is analyzed from the server and client
   perspectives alike
3. **Defaults when no framework is detected**:
   - Backend languages (Go, Rust, Python, PHP, Java/Kotlin, Ruby, C#) → `server`
   - Frontend assets only (HTML/CSS, or package.json with no framework) → `client`
   - Undeterminable → `both` (erring on the safe side)

### Step 5: Output Format

Return the detection result in the following structure (JSON representation):

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

- `primary_language`: prefer a server-side language. When there are several, the one whose
  marker file was found first
- `is_monorepo`: `true` when several marker files were found in subdirectories

## 2. Handling Multi-language Projects

In monorepos and composite projects, several languages are detected. Consuming skills use the
language information by the following rules:

1. **Include the information for all languages in context.json** (filtering is the consumer's
   responsibility)
2. **When injecting a language profile into an agent**:
   - A server-only agent → only languages with `role: "server"` or `"both"`
   - A client-only agent → only languages with `role: "client"` or `"both"`
   - A shared agent → all languages
3. **Scope narrowing**: when a specific directory is given, use only the marker files in that
   directory

## 3. Extension Points

To add a new language:

1. Add a row to the marker file table in §1 Step 1
2. Add the corresponding framework detection table to §1 Step 3
3. Add the language to the role defaults in §1 Step 4
4. Add the corresponding section to the consuming skill's own language profile (e.g.
   `lang-profiles.md`)

> **Note**: this contract is a specification, not executable code. Each consuming skill performs
> this procedure within its SKILL.md workflow.
