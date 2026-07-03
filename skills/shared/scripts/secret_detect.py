#!/usr/bin/env python3
"""Shared secret/credential detection and redaction.

Single source of truth for secret patterns, reused by:
  - skill-improve/collect.py (originating home; re-exports these names)
  - context-audit/scripts (CA-M301 + finding line-context redaction)

Do NOT hand-roll new regexes in consumers; add patterns here (with a test)
so every consumer benefits and cannot drift. Full-mask only: no partial
disclosure (no first4/last4).
"""

import re

# Order matters: more specific / higher-signal patterns run first so their
# replacement text is not re-matched by the generic fallbacks. Known-prefix
# tokens are detected regardless of surrounding quotes. A prefix-LESS generic
# "unquoted secret" is intentionally NOT covered (too many false positives).
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----")),
    # Full JWT incl. the optional signature segment (a 2-part match would
    # leave the signature in plaintext).
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)?")),
    # Known-prefix credential tokens (quoted or not). sk-ant- must precede sk-.
    # sk- includes _- so modern OpenAI keys (sk-proj-, sk-svcacct-) are masked.
    ("prefix_token", re.compile(
        r"""(?:"""
        r"""ghp_[A-Za-z0-9]{20,}"""
        r"""|github_pat_[A-Za-z0-9_]{20,}"""
        r"""|xoxb-[A-Za-z0-9-]{10,}"""
        r"""|sk-ant-[A-Za-z0-9_-]{20,}"""
        r"""|sk-[A-Za-z0-9_-]{20,}"""
        r"""|AIza[A-Za-z0-9_-]{20,}"""
        r""")"""
    )),
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("home_path", re.compile(r"(?:/home|/Users)/[A-Za-z0-9._-]+")),
    ("generic_secret", re.compile(
        r"""(?:password|secret|token|api[_-]?key|credentials)"""
        r"""\s*[:=]\s*["'][^"']{8,}["']""",
        re.IGNORECASE,
    )),
    ("generic_long_key", re.compile(r"""["'][A-Za-z0-9_\-/+]{40,}["']""")),
]


def redact(kind: str) -> str:
    """Full-mask placeholder. No partial disclosure (no first4/last4)."""
    return f"[REDACTED:{kind}]"


def detect_secrets(text: str) -> list[dict[str, str]]:
    """Detect potential secrets in text. Returns list of {type, masked}."""
    findings: list[dict[str, str]] = []
    for name, pattern in SECRET_PATTERNS:
        for _match in pattern.finditer(text):
            findings.append({"type": name, "masked": redact(name)})
    return findings


def mask_secrets(text: str) -> str:
    """Replace detected secrets with full [REDACTED:kind] placeholders."""
    result = text
    for name, pattern in SECRET_PATTERNS:
        result = pattern.sub(redact(name), result)
    return result
