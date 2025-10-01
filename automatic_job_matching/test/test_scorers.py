from django.test import SimpleTestCase
from automatic_job_matching.service.scoring import FuzzyConfidenceScorer, ExactConfidenceScorer, NoOpScorer

class ConfidenceScorerStrategyTests(SimpleTestCase):
    """Unit tests for new scoring strategy classes."""

    def setUp(self):
        from automatic_job_matching.service.scoring import FuzzyConfidenceScorer, ExactConfidenceScorer, NoOpScorer
        self.fuzzy = FuzzyConfidenceScorer()
        self.exact = ExactConfidenceScorer()
        self.noop = NoOpScorer()

    def test_exact_scorer(self):
        self.assertEqual(self.exact.score("abc", "abc"), 1.0)
        self.assertEqual(self.exact.score("abc", "abcd"), 0.0)

    def test_noop_scorer(self):
        self.assertEqual(self.noop.score("anything", "here"), 0.0)

    def test_fuzzy_exact_equivalence(self):
        self.assertGreaterEqual(self.fuzzy.score("pekerjaan galian", "pekerjaan galian"), 0.99)

    def test_fuzzy_partial_lower(self):
        exact = self.fuzzy.score("pekerjaan galian tanah", "pekerjaan galian tanah")
        partial = self.fuzzy.score("pekerjaan galian", "pekerjaan galian tanah")
        self.assertGreater(exact, partial)

    def test_fuzzy_bounds(self):
        s = self.fuzzy.score("", "abc")
        self.assertEqual(s, 0.0)
        s2 = self.fuzzy.score("abc", "")
        self.assertEqual(s2, 0.0)
        within = self.fuzzy.score("abc", "abc d")
        self.assertGreaterEqual(within, 0.0)
        self.assertLessEqual(within, 1.0)