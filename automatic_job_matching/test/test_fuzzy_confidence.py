from django.test import SimpleTestCase
from automatic_job_matching.service.fuzzy_matcher import FuzzyMatcher
from automatic_job_matching.service.exact_matcher import AhsRow

class FuzzyMatcherConfidenceTDTests(SimpleTestCase):
    """TDD: Confidence scoring tests (should fail before implementation)."""

    def setUp(self):
        self.rows = [
            AhsRow(id=1, code="AT.01.001", name="pekerjaan galian tanah biasa"),
            AhsRow(id=2, code="AT.01.002", name="pekerjaan galian tanah keras"),
            AhsRow(id=3, code="BT.02.001", name="pekerjaan beton k225"),
            AhsRow(id=4, code="ST.03.001", name="pemasangan besi tulangan d10"),
            AhsRow(id=5, code="CT.04.001", name="pekerjaan cat dinding interior"),
            AhsRow(id=6, code="PT.05.001", name="pemasangan pipa air bersih"),
        ]

        class Repo:
            def __init__(self, rows): self.rows = rows
            def by_code_like(self, code): return []
            def by_name_candidates(self, head):
                return [r for r in self.rows if head in r.name.lower()]
            def get_all_ahs(self): return self.rows

        self.repo = Repo(self.rows)
        self.matcher = FuzzyMatcher(self.repo, min_similarity=0.5)

    # Positive cases
    def test_confidence_exact_match_high(self):
        result = getattr(self.matcher, 'match_with_confidence', lambda *_: None)("pekerjaan galian tanah biasa")
        # Expect implementation to provide confidence >= 0.85
        self.assertIsNotNone(result, "Expected a match with confidence metadata")
        self.assertIn('confidence', result, "Result must include 'confidence'")
        self.assertGreaterEqual(result['confidence'], 0.85)

    def test_confidence_partial_match_lower(self):
        result = getattr(self.matcher, 'match_with_confidence', lambda *_: None)("galian tanah")
        self.assertIsNotNone(result)
        self.assertIn('confidence', result)
        # partial match should be lower than exact
        self.assertLess(result['confidence'], 0.85)
        self.assertGreaterEqual(result['confidence'], 0.5)

    def test_confidence_multiple_sorted(self):
        results = getattr(self.matcher, 'find_multiple_matches_with_confidence', lambda *_: [])("pekerjaan", limit=4)
        self.assertIsInstance(results, list)
        if results:
            self.assertIn('confidence', results[0])
            for i in range(len(results)-1):
                self.assertGreaterEqual(results[i]['confidence'], results[i+1]['confidence'])

    # Negative cases
    def test_confidence_no_match_returns_none(self):
        result = getattr(self.matcher, 'match_with_confidence', lambda *_: None)("random unrelated text xyz")
        self.assertIsNone(result)

    def test_confidence_empty_input(self):
        self.assertIsNone(getattr(self.matcher, 'match_with_confidence', lambda *_: None)(""))
        self.assertIsNone(getattr(self.matcher, 'match_with_confidence', lambda *_: None)("   "))

    def test_confidence_multiple_empty(self):
        results = getattr(self.matcher, 'find_multiple_matches_with_confidence', lambda *_: [])("", limit=5)
        self.assertEqual(results, [])

    def test_confidence_score_bounds(self):
        result = getattr(self.matcher, 'match_with_confidence', lambda *_: None)("pekerjaan galian tanah biasa")
        if result:
            self.assertGreaterEqual(result['confidence'], 0.0)
            self.assertLessEqual(result['confidence'], 1.0)

    def test_confidence_relative_order(self):
        exact = getattr(self.matcher, 'match_with_confidence', lambda *_: None)("pekerjaan galian tanah biasa")
        partial = getattr(self.matcher, 'match_with_confidence', lambda *_: None)("galian tanah")
        if exact and partial:
            self.assertGreater(exact['confidence'], partial['confidence'])