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

