# Secret Scanner

Scan the selected transport's `get_pr_diff` output before handing it to Codex, and on a
detection transition immediately to `claude-failed`. The scanner is transport-independent policy:
selecting an integration backend never bypasses it.

## Filename Patterns (immediate reject)

When a changed file path matches one of these patterns, reject without looking at the content.

```
\.env(\.|$)
\.env\.local$
\.env\.production$
.*\.key$
.*\.pem$
.*\.p12$
.*\.pfx$
credentials(\.|$)
secrets(\.|$)
id_rsa(\.|$)
id_ed25519(\.|$)
\.aws/credentials$
\.npmrc$
\.pypirc$
```

## Content Regex Patterns

Scan the added lines of the diff (lines beginning with `+`) with the following regular expressions.

### AWS

```
AKIA[0-9A-Z]{16}                                      # AWS Access Key ID
(?i)aws_secret_access_key\s*[=:]\s*['"]?[A-Za-z0-9/+=]{40}['"]?
(?i)aws_session_token\s*[=:]\s*['"]?[A-Za-z0-9/+=]{16,}['"]?
```

### GCP / Google

```
AIza[0-9A-Za-z\-_]{35}                                # Google API key
ya29\.[0-9A-Za-z\-_]+                                 # OAuth access token
"type":\s*"service_account"                           # GCP service account JSON
```

### GitHub

```
gh[pousr]_[A-Za-z0-9]{36,}                            # GitHub PAT/OAuth/refresh
github_pat_[A-Za-z0-9_]{82}                           # Fine-grained PAT
```

### Slack / Discord

```
xox[aboprs]-[A-Za-z0-9-]{10,}                         # Slack token
https?://hooks\.slack\.com/services/[A-Z0-9/]{20,}    # Slack webhook
mfa\.[a-zA-Z0-9_-]{84}                                # Discord token
```

### Stripe / Twilio / SendGrid

```
sk_live_[0-9a-zA-Z]{24,}                              # Stripe secret key
rk_live_[0-9a-zA-Z]{24,}                              # Stripe restricted key
SK[a-f0-9]{32}                                        # Twilio API key
SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}              # SendGrid
```

### Generic

```
-----BEGIN (RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----
(?i)(api[_-]?key|api[_-]?secret|access[_-]?token|auth[_-]?token|client[_-]?secret)\s*[=:]\s*['"][^'"]{16,}['"]
[a-zA-Z0-9+/]{40,}={0,2}                              # Base64-ish (needs false-positive care, optional)
```

#### Generic password (a 2-stage match — the false-positive-suppressing version)

The old single-shot `password|passwd|secret` regex produced far too many false positives, so it is replaced by the following 2-stage match.

**Stage 1: keyword-line detection** (requiring an environment-variable-name context)

```
(?i)\b(PASSWORD|PASSWD|PWD|DB_PASS|DB_PASSWORD|MYSQL_PASSWORD|POSTGRES_PASSWORD|SECRET)\s*[=:]
```

**Stage 2: extract the value from the same line and AND the following conditions**

```
- The value is at least 12 characters long (tightened from the old 8 to 12)
- Exclude known placeholder tokens by **exact match** (case-insensitive). Substring matching is not used because it produces false negatives (it would also exclude a genuinely high-entropy value that happens to contain "xxxxxxxxxxxxxxxx"):
    EXACT_PLACEHOLDER_TOKENS = {
      "xxx", "xxxx", "xxxxxxxx", "your_password", "your-password",
      "example", "placeholder", "changeme", "todo", "fixme",
      "dummy", "sample", "redacted", "your_secret_here", "yourpasswordhere"
    }
  and exclude forms enclosed by the following anchored regexes:
    ^<.+>$            # angle bracket placeholder
    ^\$\{.+\}$        # shell expansion
    ^your[_-].+$      # a whole-string match of "your_*" / "your-*"
- Exclude the case where the whole value is a single alphabetic word (no symbols, no digits) — suppressing lorem-ipsum-style false positives
```

Pseudocode:

```
def scan_generic_password(line):
  m = re.search(r'(?i)\b(PASSWORD|PASSWD|PWD|DB_PASS(WORD)?|MYSQL_PASSWORD|POSTGRES_PASSWORD|SECRET)\s*[=:]\s*[\'"]?([^\'"\s]+)[\'"]?', line)
  if not m: return None
  value = m.group(3)
  if len(value) < 12: return None
  EXACT_PLACEHOLDER_TOKENS = {
    "xxx", "xxxx", "xxxxxxxx", "your_password", "your-password",
    "example", "placeholder", "changeme", "todo", "fixme",
    "dummy", "sample", "redacted", "your_secret_here", "yourpasswordhere",
  }
  if value.lower() in EXACT_PLACEHOLDER_TOKENS: return None
  if re.fullmatch(r'<.+>', value): return None
  if re.fullmatch(r'\$\{.+\}', value): return None
  if re.fullmatch(r'(?i)your[_-].+', value): return None
  if re.fullmatch(r'[A-Za-z]+', value): return None
  return {"type": "content", "pattern": "generic_password", "value_len": len(value)}
```

> **Note:** the last Base64 pattern produces many false positives, so it is disabled by default. For the SSOT of `enable_base64_scan`, see [`config-defaults.md`](config-defaults.md) (default `false`, enabled with `--config enable_base64_scan=true`).

## Output Format

Return the scan result in the following structure.

```json
{
  "matched": true,
  "matches": [
    {"type": "filename" | "content", "pattern": "AKIA[0-9A-Z]{16}", "file": "src/foo.ts", "line": 12}
  ]
}
```

When `matched: true`, the Cycle Workflow does not hand the diff to Codex and transitions immediately to `claude-failed`.
