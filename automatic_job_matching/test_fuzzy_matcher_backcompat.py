from django.test import SimpleTestCase
from automatic_job_matching.service.fuzzy_matcher import FuzzyMatcher, AhsRow
from automatic_job_matching.service.scoring import NoOpScorer, FuzzyConfidenceScorer

class RepoAll:
    def __init__(self, rows): self.rows = rows
    def by_code_like(self, code): return []
    def by_name_candidates(self, head): return self.rows
    def get_all_ahs(self): return self.rows

class FuzzyMatcherBackwardCompatTests(SimpleTestCase):
    def setUp(self):
        self.rows = [
            AhsRow(id=1, code='AT.01', name='pekerjaan galian tanah biasa'),
            AhsRow(id=2, code='AT.02', name='pemasangan besi tulangan d10'),
            AhsRow(id=3, code='AT.03', name='pekerjaan beton k225'),
        ]
        self.repo = RepoAll(self.rows)

    def test_calculate_confidence_score_delegate(self):
        matcher = FuzzyMatcher(self.repo, scorer=FuzzyConfidenceScorer())
        q = 'pekerjaan galian tanah'
        c = 'pekerjaan galian tanah biasa'
        score = matcher._calculate_confidence_score(q, c)
        self.assertGreater(score, 0.5)

    def test_match_with_confidence_noop_scorer_blocks_all(self):
        matcher = FuzzyMatcher(self.repo, scorer=NoOpScorer())
        result = matcher._fuzzy_match_name_with_confidence('pekerjaan galian tanah biasa')
        # NoOp scorer always returns 0.0 => below default min_similarity (0.6) so None
        self.assertIsNone(result)

    def test_multiple_with_confidence_limit_zero(self):
        matcher = FuzzyMatcher(self.repo)
        results = matcher._get_multiple_name_matches_with_confidence('pekerjaan', 0)
        self.assertEqual(results, [])

    def test_multiple_with_confidence_empty_normalized(self):
        matcher = FuzzyMatcher(self.repo)
        results = matcher._get_multiple_name_matches_with_confidence('   ', 5)
        self.assertEqual(results, [])

    def test_multiple_with_confidence_basic(self):
        matcher = FuzzyMatcher(self.repo, min_similarity=0.3)
        results = matcher._get_multiple_name_matches_with_confidence('pekerjaan', 5)
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertIn('confidence', r)
