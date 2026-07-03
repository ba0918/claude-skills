#!/usr/bin/env python3
"""Catalog <-> registry drift guard.

references/rule-catalog.md and static_checks.RULES are dual sources of truth
for the CA-* rules. This test parses the catalog table and asserts the id /
category / severity / action of every rule match the registry exactly, so the
two cannot silently drift.
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import static_checks as sc

CATALOG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "references", "rule-catalog.md"
)

_ROW = re.compile(r"^\|\s*(CA-[A-Z0-9]+)\s*\|(.+)\|\s*$")


def parse_catalog(path):
    """Return {id: {category, severity, action}} from the catalog table."""
    rows = {}
    for line in open(path, encoding="utf-8"):
        m = _ROW.match(line.rstrip("\n"))
        if not m:
            continue
        rid = m.group(1)
        cells = [c.strip() for c in m.group(2).split("|")]
        # columns after ID: Category | Severity | Action | ...
        category, severity, action = cells[0], cells[1], cells[2]
        rows[rid] = {"category": category, "severity": severity, "action": action}
    return rows


class TestCatalogSync(unittest.TestCase):
    def test_catalog_file_exists(self):
        self.assertTrue(os.path.isfile(CATALOG))

    def test_ids_match(self):
        catalog = parse_catalog(CATALOG)
        self.assertEqual(set(catalog), set(sc.RULES),
                         "catalog IDs and RULES registry IDs diverge")

    def test_fields_match(self):
        catalog = parse_catalog(CATALOG)
        for rid, meta in sc.RULES.items():
            self.assertIn(rid, catalog)
            self.assertEqual(catalog[rid]["category"], meta["category"], f"{rid} category")
            self.assertEqual(catalog[rid]["severity"], meta["severity"], f"{rid} severity")
            self.assertEqual(catalog[rid]["action"], meta["action"], f"{rid} action")


if __name__ == "__main__":
    unittest.main()
