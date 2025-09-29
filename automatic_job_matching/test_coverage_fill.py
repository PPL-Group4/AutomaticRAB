from django.test import SimpleTestCase
from unittest.mock import patch

from automatic_job_matching.repository.ahs_repo import DbAhsRepository
from automatic_job_matching.service.exact_matcher import ExactMatcher, AhsRow as ExactAhsRow
from automatic_job_matching.service.fuzzy_matcher import FuzzyMatcher, AhsRow as FuzzyAhsRow
from automatic_job_matching.service.scoring import NoOpScorer


class AdditionalDbAhsRepositoryCoverageTests(SimpleTestCase):
    def test_by_code_like_deduplicates_ids(self):
        """Cover loop branch ensuring duplicate IDs skipped (lines with seen set)."""
        class FakeAhs:
            def __init__(self, _id, code, name):
                self.id = _id
                self.code = code
                self.name = name
        # Simulate two result variants that would union into duplicate id
        class FakeQS(list):
            def union(self, other):
                return FakeQS(self + list(other))
        with patch("rencanakan_core.models.Ahs.objects.none", return_value=FakeQS()) as mock_none:
            with patch("rencanakan_core.models.Ahs.objects.filter") as mock_filter:
                mock_filter.side_effect = [FakeQS([FakeAhs(1, "T.10.a", "Name1")]), FakeQS([FakeAhs(1, "T.10.a", "Name1")]), FakeQS([FakeAhs(1, "T.10.a", "Name1")])]
                repo = DbAhsRepository()
                rows = repo.by_code_like("T.10.a")
                self.assertEqual(len(rows), 1)
                # Ensure filter called for each variant produced (original + two replacements)
                self.assertGreaterEqual(mock_filter.call_count, 1)


class ExactMatcherUncoveredLineTests(SimpleTestCase):
    def test_match_by_code_path_breaks_after_first(self):
        """Cover code branch where looks_like_code true but no candidate matches until later iterations."""
        class Repo:
            def by_code_like(self, code):
                # first row won't match normalized code; second will
                return [
                    ExactAhsRow(id=1, code="X.01", name="Dummy"),
                    ExactAhsRow(id=2, code="T.15.a.1", name="Target"),
                ]
            def by_name_candidates(self, head):
                return []
        matcher = ExactMatcher(Repo())
        result = matcher.match("T.15.a.1")
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], 2)
        self.assertEqual(result["matched_on"], "code")

    def test_match_non_empty_description_normalizes_empty(self):
        """Exercise branch where description provided but normalization yields empty => returns None."""
        class Repo:
            def by_code_like(self, code): return []
            def by_name_candidates(self, head): return []
        matcher = ExactMatcher(Repo())
        # punctuation that normalizer should strip to empty
        self.assertIsNone(matcher.match("!!!???///"))


class FuzzyMatcherAdditionalCoverageTests(SimpleTestCase):
    def setUp(self):
        # Provide rows including one with empty name to exercise skip branch
        self.rows = [
            FuzzyAhsRow(id=1, code="A", name="pekerjaan galian tanah biasa"),
            FuzzyAhsRow(id=2, code="B", name=""),  # should be skipped in loops
            FuzzyAhsRow(id=3, code="C", name="pekerjaan beton k225"),
        ]
        class Repo:
            def __init__(self, rows): self.rows = rows
            def by_code_like(self, code): return []
            def by_name_candidates(self, head): return self.rows
            def get_all_ahs(self): return self.rows
        self.repo = Repo(self.rows)

    def test_find_multiple_matches_zero_limit_early_return(self):
        matcher = FuzzyMatcher(self.repo)
        self.assertEqual(matcher.find_multiple_matches("anything", limit=0), [])

    def test_match_with_confidence_skips_empty_candidate_name(self):
        # Use NoOpScorer with lowered threshold to still process candidates and ensure skip path for empty name executed.
        matcher = FuzzyMatcher(self.repo, min_similarity=0.0, scorer=NoOpScorer())
        # patch scorer to return >0 for non-empty names so only empty name path relies on skip
        with patch.object(matcher.scorer, 'score', side_effect=lambda q,c: 0.9 if c else 0.0):
            result = matcher.match_with_confidence("pekerjaan galian tanah biasa")
            self.assertIsNotNone(result)
            self.assertNotEqual(result['id'], 2)  # id=2 had empty name and must be skipped

    def test_find_multiple_matches_with_confidence_limit_negative(self):
        matcher = FuzzyMatcher(self.repo)
        self.assertEqual(matcher.find_multiple_matches_with_confidence("query", limit=-5), [])

    def test_internal_calculate_partial_similarity_prefers_jaccard_vs_partial(self):
        matcher = FuzzyMatcher(self.repo)
        # two strings sharing a common word but no substring relations beyond that word
        score = matcher._calculate_partial_similarity("alpha beta", "alpha gamma")
        self.assertGreaterEqual(score, 0.25)  # jaccard 1/3 ≈ 0.333 ensures branch executed

    def test_candidate_provider_empty_input_returns_all(self):
        from automatic_job_matching.service.fuzzy_matcher import CandidateProvider
        provider = CandidateProvider(self.repo)
        all_rows = provider.get_candidates_by_head_token("")
        self.assertEqual(len(all_rows), len(self.rows))

    def test_matching_processor_limit_early_return(self):
        # Access internal matching processor to hit its own limit guard
        matcher = FuzzyMatcher(self.repo)
        proc = matcher._matching_processor  # type: ignore[attr-defined]
        self.assertEqual(proc.find_multiple_matches("anything", limit=0), [])

    def test_multiple_matches_with_confidence_executes_conf_line(self):
        matcher = FuzzyMatcher(self.repo, min_similarity=0.0)
        results = matcher.find_multiple_matches_with_confidence("pekerjaan")
        # ensure we actually computed confidence for at least one candidate (line computing conf)
        self.assertGreater(len(results), 0)
        self.assertIn('confidence', results[0])


class ScoringClampRemainingLine(SimpleTestCase):
    def test_noop_scorer_direct_call_line_coverage(self):
        # ensure direct call already covered; repeat to guarantee measurement (idempotent)
        scorer = NoOpScorer()
        self.assertEqual(scorer.score("anything", "value"), 0.0)
    def test_overlap_metrics_non_empty_union(self):
        from automatic_job_matching.service.scoring import FuzzyConfidenceScorer
        s = FuzzyConfidenceScorer()
        j, c = s._overlap_metrics(["a", "b"], ["b", "c"])  # type: ignore[attr-defined]
        self.assertGreater(j, 0.0)
        self.assertGreater(c, 0.0)
