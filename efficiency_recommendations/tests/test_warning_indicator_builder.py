from unittest import TestCase

from efficiency_recommendations.services.warning_indicator_builder import build_indicator


class TestWarningIndicatorBuilder(TestCase):
    def test_none_level(self):
        ind = build_indicator(total_items=3, warning_count=0)
        self.assertEqual(ind["level"], "NONE")
        self.assertEqual(ind["badge_color"], "#D1D5DB")
        self.assertEqual(ind["icon"], "check-circle")
        self.assertEqual(ind["ratio"], 0.0)

    def test_warn_level(self):
        ind = build_indicator(total_items=3, warning_count=1)  # 0.333
        self.assertEqual(ind["level"], "WARN")
        self.assertEqual(ind["badge_color"], "#F59E0B")
        self.assertEqual(ind["icon"], "alert-triangle")
        self.assertEqual(ind["label"], "1 warning")

    def test_critical_level(self):
        ind = build_indicator(total_items=3, warning_count=2)  # 0.666
        self.assertEqual(ind["level"], "CRITICAL")
        self.assertEqual(ind["badge_color"], "#DC2626")
        self.assertIn("warnings", ind["label"])
