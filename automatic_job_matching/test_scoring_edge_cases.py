from django.test import SimpleTestCase

from automatic_job_matching.service.scoring import FuzzyConfidenceScorer, ExactConfidenceScorer, NoOpScorer

class FuzzyConfidenceScorerEdgeCaseTests(SimpleTestCase):
    def setUp(self):
        self.scorer = FuzzyConfidenceScorer()

    def test_overlap_metrics_empty_union(self):
        j, c = self.scorer._overlap_metrics([], [])  # type: ignore[attr-defined]
        self.assertEqual((j, c), (0.0, 0.0))

    def test_token_pair_short_tokens(self):
        self.assertEqual(self.scorer._token_pair_score('ab', 'abcd'), 0.0)  # short token branch (len<3)

    def test_token_pair_equality(self):
        self.assertEqual(self.scorer._token_pair_score('abcd', 'abcd'), 1.0)

    def test_token_pair_substring(self):
        self.assertEqual(self.scorer._token_pair_score('abcd', 'abcdef'), 0.8)

    def test_token_pair_ratio_high_and_low(self):
        # high ratio but not substring/equal should scale by 0.6
        # choose tokens with similarity ratio >=0.75 but not substring; e.g., 'galian' vs 'galiam'
        high = self.scorer._token_pair_score('galian', 'galiam')
        self.assertGreater(high, 0.0)
        # Low ratio case should return 0.0
        low = self.scorer._token_pair_score('abcdef', 'ghijkl')
        self.assertEqual(low, 0.0)

    def test_near_similarity_no_pairs(self):
        # All tokens too short -> no pairs counted
        v = self.scorer._near_similarity(['a', 'b'], ['c'])
        self.assertEqual(v, 0.0)

    def test_bonus_eligibility_true_false(self):
        self.assertTrue(self.scorer._eligible_bonus(self.scorer.BONUS_THRESHOLD_SEQ, self.scorer.BONUS_THRESHOLD_JACCARD))
        self.assertFalse(self.scorer._eligible_bonus(self.scorer.BONUS_THRESHOLD_SEQ - 0.01, self.scorer.BONUS_THRESHOLD_JACCARD))
        self.assertFalse(self.scorer._eligible_bonus(self.scorer.BONUS_THRESHOLD_SEQ, self.scorer.BONUS_THRESHOLD_JACCARD - 0.01))

    def test_clamp_bounds(self):
        self.assertEqual(self.scorer._clamp(-0.5), 0.0)
        self.assertEqual(self.scorer._clamp(1.5), 1.0)
        self.assertEqual(self.scorer._clamp(0.75), 0.75)

    def test_exact_and_noop_consistency(self):
        exact = ExactConfidenceScorer()
        noop = NoOpScorer()
        self.assertEqual(exact.score('', 'abc'), 0.0)  # empty guard path in ExactConfidenceScorer
        self.assertEqual(noop.score('anything', 'else'), 0.0)

    def test_full_score_flow_with_bonus(self):
        # Craft inputs that likely trigger bonus: highly similar tokens sets
        q = 'pekerjaan galian tanah biasa'
        c = 'pekerjaan galian tanah biasa'
        s = self.scorer.score(q, c)
        self.assertGreaterEqual(s, 0.99)

    def test_full_score_flow_without_bonus(self):
        q = 'pekerjaan galian tanah'
        c = 'pemasangan besi tulangan'
        s = self.scorer.score(q, c)
        # Should be low and certainly no bonus applied
        self.assertLess(s, 0.5)

    def test_score_with_one_empty_token_list(self):
        # norm_query has tokens, candidate lacks (""), early return path after token split
        s = self.scorer.score('abc def', '')
        self.assertEqual(s, 0.0)

    def test_score_whitespace_only_candidate_triggers_token_empty_branch(self):
        # Candidate string is whitespace -> passes trivial (not empty string) but splits to [] triggering line 60
        s = self.scorer.score('abc def', '   ')
        self.assertEqual(s, 0.0)
        # Also reversed: query whitespace, candidate tokens
        s2 = self.scorer.score('   ', 'abc def')
        self.assertEqual(s2, 0.0)
