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

