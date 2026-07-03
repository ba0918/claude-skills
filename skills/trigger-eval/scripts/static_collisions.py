#!/usr/bin/env python3
"""
trigger-eval: Static collision pre-pass.

Ranks description pairs by lexical Jaccard similarity to surface
collision candidates. Pure functions, no LLM. Used for:
  (a) defining "adjacent" skills for hard-negative case generation,
  (b) rework prioritization,
  (c) surfacing self-evident merge candidates without a judge round.
"""

import argparse
import json
import re
import sys
from itertools import combinations
from pathlib import Path
from typing import Any

_ASCII_RE = re.compile(r"[a-z0-9]{2,}")
# CJK unigram ranges: Hiragana, Katakana, CJK unified ideographs.
_CJK_RE = re.compile(r"[぀-ヿ一-鿿]")


def tokenize(text: str) -> set[str]:
    """Lexical tokenization for similarity.

    - ASCII alphanumeric runs of length >= 2 (single letters dropped as noise),
      lowercased.
    - Each CJK character as its own unigram token (so Japanese descriptions
      overlap measurably).
    """
    lowered = text.lower()
    tokens = set(_ASCII_RE.findall(lowered))
    tokens.update(_CJK_RE.findall(lowered))
    return tokens


def jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity |a∩b| / |a∪b|. Empty ∪ empty := 0.0."""
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def pairwise_collisions(
    skills: list[dict[str, str]], top_n: int | None = None
) -> list[dict[str, Any]]:
    """Rank all skill pairs by description Jaccard similarity (descending).

    Each entry: {a, b, jaccard, shared: [sorted shared tokens]}.
    Ties are broken deterministically by (a, b) name order.
    """
    tokenized = [(s["name"], tokenize(s.get("description", ""))) for s in skills]
    pairs: list[dict[str, Any]] = []
    for (name_a, tok_a), (name_b, tok_b) in combinations(tokenized, 2):
        score = jaccard(tok_a, tok_b)
        pairs.append(
            {
                "a": name_a,
                "b": name_b,
                "jaccard": score,
                "shared": sorted(tok_a & tok_b),
            }
        )
    pairs.sort(key=lambda p: (-p["jaccard"], p["a"], p["b"]))
    if top_n is not None:
        pairs = pairs[:top_n]
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rank skill description pairs by lexical Jaccard similarity"
    )
    parser.add_argument(
        "input", type=str,
        help="collect_descriptions.py JSON output (file path, or '-' for stdin)",
    )
    parser.add_argument("--top-n", type=int, default=None, help="Limit to top N pairs")
    parser.add_argument("--output", type=str, default=None, help="Output file (default stdout)")
    args = parser.parse_args()

    if args.input == "-":
        data = json.load(sys.stdin)
    else:
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))

    skills = data["skills"] if isinstance(data, dict) else data
    pairs = pairwise_collisions(skills, top_n=args.top_n)
    result = {"pair_count": len(pairs), "pairs": pairs}

    json_str = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(json_str + "\n", encoding="utf-8")
    else:
        print(json_str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
