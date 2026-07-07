# Review Criteria - 4 Agent Integrated Version

Detailed information for SKILL.md. Reference the relevant section when constructing each agent's prompt.
Check items are identical to the pre-integration version. Only the organizational structure has been reorganized for the 4-agent system.

## 1. Security + Secrets (security-auditor)

### 1-A. Security (Weight: 20%)

#### Checklist

- **Input validation**: User input sanitization, validation, type checking
- **Authentication/Authorization**: Access control, permission checks, session management, JWT verification
- **Injection**: SQLi, XSS, command injection, path traversal
- **Encryption**: Appropriate algorithm usage, presence of hardcoded keys
- **CORS/CSP**: Cross-origin settings, Content Security Policy
- **Dependencies**: Usage of libraries with known vulnerabilities
- **Error information leakage**: Stack trace or DB info exposure to client

#### Severity Criteria

| Severity | Example |
|----------|---------|
| critical | Unsanitized input inserted into DOM, SQL injection possible |
| major | Improper CORS settings, session fixation |
| minor | CSP header not set, Cookie without HttpOnly |
| info | Security best practice recommendations |

### 1-B. Secrets (Weight: 15%)

#### Checklist

- **Hardcoded secrets**: API keys, passwords, tokens, private keys
- **Environment variable leakage**: `.env` file committed, environment variables logged
- **PII (Personal Identifiable Information)**: Hardcoded email addresses, phone numbers, addresses
- **Credentials**: DB connection strings, OAuth secrets, service accounts
- **gitignore omissions**: `.env`, `credentials.json`, `*.pem` not excluded
- **Log output**: Sensitive data written to console/file

#### Pattern Matching

```
API keys: /[A-Za-z0-9_-]{20,}/ exists as literal in code
Passwords: password|secret|token|key = "..." pattern
AWS: AKIA[0-9A-Z]{16}
JWT: eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+
Private keys: -----BEGIN (RSA |EC )?PRIVATE KEY-----
```

#### Severity Criteria

| Severity | Example |
|----------|---------|
| critical | Production API key hardcoded, private key committed |
| major | Leftover test tokens, .env not in gitignore |
| minor | Dummy data using real email format |
| info | Environment variable naming improvement suggestions |

---

## 2. Performance + Memory Efficiency (performance-analyzer)

### 2-A. Performance (Weight: 12%)

#### Checklist

- **Algorithm efficiency**: O(n^2)+ nested loops, unnecessary recomputation
- **N+1 problem**: DB/API queries inside loops, non-batch processing
- **Bundle size**: Unnecessary large libraries, tree-shaking impediment
- **Rendering**: Unnecessary re-renders, large lists without virtualization
- **Async processing**: Parallelizable tasks run serially, await hell
- **Caching**: Repeated computation without caching, missing memoization
- **I/O efficiency**: Synchronous file operations, large data without streaming

#### Severity Criteria

| Severity | Example |
|----------|---------|
| critical | O(n^3) loop with n>1000 expected, N+1 DB queries in loop |
| major | Unnecessary full data loading, inefficient regex |
| minor | Memoizable pure functions, unnecessary re-renders |
| info | Performance optimization opportunities |

### 2-B. Memory Efficiency (Weight: 8%)

#### Checklist

- **Memory leaks**: Unremoved event listeners, uncleared timers, reference retention via closures
- **Large data**: Full in-memory expansion, unused streaming/generators
- **Circular references**: Inter-object circular references, GC impediment
- **Global state**: Global variable accumulation, singleton bloat
- **Buffer management**: Unnecessary copies, appropriate buffer sizing
- **DOM operations**: Detached DOM nodes, unused event delegation

#### Severity Criteria

| Severity | Example |
|----------|---------|
| critical | Event listeners without remove (long-running app) |
| major | Large data fully loaded into array, missing clearInterval/clearTimeout |
| minor | Unnecessary object copies, unnecessary temporary variable retention |
| info | Memory usage optimization suggestions |

---

## 3. Implementation Quality + Logical Consistency (quality-inspector)

### 3-A. Implementation Quality (Weight: 15%)

#### Checklist

- **Naming conventions**: Consistent naming, meaningful variable names, appropriate abbreviation usage
- **Function design**: Single responsibility, appropriate argument count (<=4), side effect management
- **Type safety**: Overuse of any/unknown, type guards, null safety
- **Error handling**: Appropriate try-catch, error propagation, user-facing messages
- **Comments**: Self-documenting code, WHY comments, JSDoc/docstring
- **Testability**: Dependency injection, mock-friendliness, pure function utilization
- **Coding standards**: Compliance with project-specific rules (AGENTS.md)

#### Severity Criteria

| Severity | Example |
|----------|---------|
| critical | Complete lack of type safety, no error handling |
| major | Giant functions (200+ lines), deep nesting (4+ levels), unclear naming |
| minor | Magic numbers, insufficient comments, unnecessary any |
| info | Improvement opportunities through refactoring |

### 3-B. Logical Consistency / Bugs (Weight: 15%)

#### Checklist

- **Logic errors**: Incorrect branching, off-by-one errors, comparison operator misuse
- **Edge cases**: null/undefined/empty arrays, boundary values, division by zero
- **State management**: Race conditions, inconsistent state transitions, deadlocks
- **Data flow**: Uninitialized variables, unreachable code, infinite loops
- **API consistency**: Type mismatch between arguments and return values, interface violations
- **Business logic**: Deviation from specifications (reference AGENTS.md/documentation)

#### Severity Criteria

| Severity | Example |
|----------|---------|
| critical | Potential data corruption, infinite loops, deadlocks |
| major | Unhandled edge cases, potential state inconsistency |
| minor | Hard-to-reach but potential bugs, unnecessary type conversions |
| info | Logic improvement suggestions |

---

## 4. Code Hygiene + Improvements (codebase-hygiene)

### 4-A. Code Duplication / Dead Code (Weight: 8%)

#### Checklist

- **Code duplication**: Duplicate identical/similar logic (DRY principle violation)
- **Dead code**: Unused exports, unreachable code, commented-out code
- **Unused dependencies**: Unused packages in package.json/deno.json
- **Unused files**: Modules not imported from anywhere
- **Extraction candidates**: Candidates for extraction to shared/utils
- **Over-abstraction**: Unnecessary abstractions called from only 1 location

#### Severity Criteria

| Severity | Example |
|----------|---------|
| critical | Same logic duplicated in 5+ locations |
| major | Similar logic in 3+ locations, large amounts of dead code |
| minor | Small-scale duplication, unused imports |
| info | Maintainability improvement suggestions through consolidation |

### 4-B. Other Improvements (Weight: 7%)

#### Checklist

- **Architecture**: Layer violations, dependency direction, module splitting
- **Testing**: Coverage gaps, test quality, insufficient edge case tests
- **Documentation**: README, API docs, architecture docs
- **CI/CD**: Build config, lint config, automated test config
- **Developer experience (DX)**: Script setup, environment setup procedures, debug support
- **Accessibility**: a11y compliance (for web projects)
- **Internationalization/Localization**: i18n status

#### Severity Criteria

| Severity | Example |
|----------|---------|
| critical | Layer violations (architecture breakdown) |
| major | Significant test coverage gaps, documentation deficiencies |
| minor | DX improvements, CI/CD optimization |
| info | Best practice recommendations |
