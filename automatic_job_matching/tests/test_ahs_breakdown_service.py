from django.test import SimpleTestCase

from automatic_job_matching.service.ahs_breakdown_service import get_ahs_breakdown


class AhsBreakdownServiceTests(SimpleTestCase):
    def test_returns_breakdown_for_known_code(self):
        breakdown = get_ahs_breakdown("1.1.1.1")

        self.assertIsNotNone(breakdown)
        self.assertIn("totals", breakdown)
        self.assertAlmostEqual(breakdown["totals"]["labor"], 127600.0)
        self.assertAlmostEqual(breakdown["totals"]["materials"], 588215.63)
        self.assertGreater(len(breakdown["components"]["materials"]), 0)
        self.assertNotIn("labor", breakdown["components"])
        self.assertNotIn("equipment", breakdown["components"])

    def test_returns_none_for_unknown_code(self):
        self.assertIsNone(get_ahs_breakdown("ZZ.99.999"))
