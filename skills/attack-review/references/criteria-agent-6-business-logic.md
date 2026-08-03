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
