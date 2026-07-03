#!/usr/bin/env python3
"""Unit tests for static_collisions.py."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import static_collisions as sc


class TestTokenize(unittest.TestCase):
    def test_lowercases_and_splits(self):
        self.assertEqual(sc.tokenize("Apple Banana"), {"apple", "banana"})

    def test_drops_single_char_ascii(self):
        # single ASCII letters are dropped as noise
        toks = sc.tokenize("a bb ccc")
        self.assertNotIn("a", toks)
        self.assertIn("bb", toks)

    def test_cjk_bigrams(self):
        # Japanese runs are tokenized as sliding bigrams (not unigrams).
        toks = sc.tokenize("計画レビュー")
        self.assertIn("計画", toks)
        self.assertIn("画レ", toks)
        self.assertIn("ュー", toks)
        # single-char CJK unigrams are no longer emitted
        self.assertNotIn("計", toks)
        self.assertNotIn("画", toks)

    def test_two_char_word_is_one_bigram(self):
        # a 2-char run yields exactly one bigram token
        toks = sc.tokenize("計画")
        self.assertEqual(toks, {"計画"})

    def test_single_char_run_excluded(self):
        # a length-1 CJK run produces no token (surrounded by ASCII/space)
        toks = sc.tokenize("A 語 B")
        self.assertNotIn("語", toks)
        self.assertEqual(toks, set())

    def test_ascii_and_japanese_mixed(self):
        # ASCII words and Japanese bigrams coexist; ASCII unchanged
        toks = sc.tokenize("commit を実行する")
        self.assertIn("commit", toks)
        self.assertIn("実行", toks)
        self.assertIn("行す", toks)
        self.assertNotIn("を", toks)  # length-1 run dropped

    def test_empty(self):
        self.assertEqual(sc.tokenize(""), set())


class TestJaccard(unittest.TestCase):
    def test_identical(self):
        s = {"a", "b", "c"}
        self.assertEqual(sc.jaccard(s, s), 1.0)

    def test_disjoint(self):
        self.assertEqual(sc.jaccard({"a", "b"}, {"c", "d"}), 0.0)

    def test_partial(self):
        a = {"apple", "banana", "cherry"}
        b = {"banana", "cherry", "date"}
        self.assertAlmostEqual(sc.jaccard(a, b), 0.5)

    def test_both_empty_is_zero(self):
        self.assertEqual(sc.jaccard(set(), set()), 0.0)


class TestPairwiseCollisions(unittest.TestCase):
    def _skills(self):
        return [
            {"name": "alpha", "description": "banana cherry date fig"},
            {"name": "beta", "description": "banana cherry date grape"},
            {"name": "gamma", "description": "xylophone zebra wombat"},
        ]

    def test_ranks_by_jaccard_desc(self):
        pairs = sc.pairwise_collisions(self._skills())
        # alpha/beta share 3 of 5 union -> highest
        self.assertEqual({pairs[0]["a"], pairs[0]["b"]}, {"alpha", "beta"})
        # sorted descending
        scores = [p["jaccard"] for p in pairs]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_includes_all_pairs(self):
        pairs = sc.pairwise_collisions(self._skills())
        self.assertEqual(len(pairs), 3)  # C(3,2)

    def test_shared_tokens_reported(self):
        pairs = sc.pairwise_collisions(self._skills())
        top = pairs[0]
        self.assertIn("banana", top["shared"])
        self.assertIn("cherry", top["shared"])

    def test_top_n_limit(self):
        pairs = sc.pairwise_collisions(self._skills(), top_n=1)
        self.assertEqual(len(pairs), 1)

    def test_single_skill_no_pairs(self):
        pairs = sc.pairwise_collisions([{"name": "solo", "description": "x y z"}])
        self.assertEqual(pairs, [])


if __name__ == "__main__":
    unittest.main()
