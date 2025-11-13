from django.test import SimpleTestCase
from automatic_job_matching.service.exact_matcher import AhsRow, ExactMatcher, _norm_code, _norm_name

class ExactMatcherTests(SimpleTestCase):
    def setUp(self):
        self.sample_row = AhsRow(
            id=10, code="T.15.a.1", name="Pemadatan pasir sebagai bahan pengisi"
        )

        class FakeRepo:
            def __init__(self, rows):
                self.rows = rows
            def by_code_like(self, code): return self.rows
            def by_name_candidates(self, head_token): return self.rows

        self.fake_repo = FakeRepo([self.sample_row])

    def test_match_by_code_success(self):
        matcher = ExactMatcher(self.fake_repo)
        result = matcher.match("T.15.a.1")
        self.assertIsNotNone(result)
        self.assertEqual(result["matched_on"], "code")
        self.assertEqual(result["code"], "T.15.a.1")
        self.assertEqual(result["id"], 10)

    def test_match_by_code_variant_success(self):
        matcher = ExactMatcher(self.fake_repo)
        result = matcher.match("T-15.a-1")
        self.assertIsNotNone(result)
        self.assertEqual(result["matched_on"], "code")

    def test_match_by_name_success(self):
        matcher = ExactMatcher(self.fake_repo)
        result = matcher.match("Pemadatan pasir sebagai bahan pengisi")
        self.assertIsNotNone(result)
        self.assertEqual(result["matched_on"], "name")

    def test_match_returns_none_for_empty_input(self):
        matcher = ExactMatcher(self.fake_repo)
        self.assertIsNone(matcher.match(""))

    def test_match_returns_none_if_no_match(self):
        bad_repo = type(
            "BadRepo",
            (),
            {
                "by_code_like": lambda self, c: [],
                "by_name_candidates": lambda self, h: [],
            },
        )()
        matcher = ExactMatcher(bad_repo)
        self.assertIsNone(matcher.match("Some random description"))

    def test_norm_code_and_norm_name_helpers(self):
        self.assertEqual(_norm_code("t.15-a/1"), "T15A1")
        self.assertEqual(_norm_name("Pemadatan Pasir!"), "pemadatan pasir")