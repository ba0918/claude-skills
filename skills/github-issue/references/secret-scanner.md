# Secret Scanner

`gh pr diff` 出力を Codex に渡す前にスキャンし、検出時は即 `claude-failed` に遷移させる。

## Filename Patterns (即 reject)

変更ファイルパスがこのパターンに合致する場合、内容を見ずに reject。

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

diff の追加行（`+` で始まる行）に対して以下の正規表現でスキャンする。

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
[a-zA-Z0-9+/]{40,}={0,2}                              # Base64-ish (要 false-positive 配慮、optional)
```

#### Generic password (2 段階マッチ — 誤検知抑制版)

旧 `password|passwd|secret` の単発正規表現は誤検知が多すぎたため、以下の 2 段階マッチに置き換える。

**Stage 1: キーワード行検出**（環境変数名コンテキストを必須化）

```
(?i)\b(PASSWORD|PASSWD|PWD|DB_PASS|DB_PASSWORD|MYSQL_PASSWORD|POSTGRES_PASSWORD|SECRET)\s*[=:]
```

**Stage 2: 同行から値を抽出して以下を AND 判定**

```
- 値長が 12 文字以上（旧 8 → 12 に厳格化）
- 既知のプレースホルダトークンを **exact match**（case-insensitive）で除外。substring match は誤検知（"xxxxxxxxxxxxxxxx" を含む真の高エントロピ値まで除外する）を生むため使わない:
    EXACT_PLACEHOLDER_TOKENS = {
      "xxx", "xxxx", "xxxxxxxx", "your_password", "your-password",
      "example", "placeholder", "changeme", "todo", "fixme",
      "dummy", "sample", "redacted", "your_secret_here", "yourpasswordhere"
    }
  および以下の anchored regex で囲まれた形を除外:
    ^<.+>$            # angle bracket placeholder
    ^\$\{.+\}$        # shell expansion
    ^your[_-].+$      # "your_*" / "your-*" 全体マッチ
- 値全体が単一の英字単語（記号・数字なし）の場合は除外（lorem ipsum 系の誤検知抑制）
```

擬似コード:

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

> **Note:** 最後の Base64 パターンは誤検知が多いため、デフォルトでは無効。`enable_base64_scan` の SSOT は [`config-defaults.md`](config-defaults.md) を参照（デフォルト `false`、`--config enable_base64_scan=true` で有効化）。

## Output Format

スキャン結果は以下の構造で返す。

```json
{
  "matched": true,
  "matches": [
    {"type": "filename" | "content", "pattern": "AKIA[0-9A-Z]{16}", "file": "src/foo.ts", "line": 12}
  ]
}
```

`matched: true` の場合、Cycle Workflow は Codex に diff を渡さず即 `claude-failed` に遷移する。
