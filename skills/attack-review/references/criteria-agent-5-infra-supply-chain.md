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

