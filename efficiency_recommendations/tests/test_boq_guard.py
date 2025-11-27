import unittest
from decimal import Decimal

from efficiency_recommendations.services.boq_guard import EMPTY_MSG, ZERO_MSG, check_boq_health
from efficiency_recommendations.services.highest_cost_weight_identifier import identify_highest_cost_weight_item
from efficiency_recommendations.services.recommendation_text_generator import generate_recommendation_text


class BoqGuardTest(unittest.TestCase):
    """Tests for BoQ health checking and safe fallbacks"""

    def test_empty_items_returns_false_and_message(self):
        job = {
            "job_id": 1,
            "job_name": "Empty Project",
            "total_cost": Decimal("0"),
            "items": []
        }
        ok, msg = check_boq_health(job)
        self.assertFalse(ok)
        self.assertEqual(msg, EMPTY_MSG)

    def test_zero_total_returns_false_and_message(self):
        job = {
            "job_id": 2,
            "job_name": "Zero Cost Project",
            "total_cost": Decimal("0"),
            "items": [
                {"name": "Excavation", "cost": Decimal("0"), "weight_pct": Decimal("0")}
            ]
        }
        ok, msg = check_boq_health(job)
        self.assertFalse(ok)
        self.assertEqual(msg, ZERO_MSG)

    def test_valid_boq_returns_true(self):
        job = {
            "job_id": 3,
            "job_name": "Valid BoQ",
            "total_cost": Decimal("500000"),
            "items": [
                {"name": "Foundation", "cost": Decimal("500000"), "weight_pct": Decimal("100")}
            ]
        }
        ok, msg = check_boq_health(job)
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_downstream_safe_with_empty_boq(self):
        """Even with empty items, downstream functions shouldn't crash"""
        job = {
            "job_id": 4,
            "job_name": "Empty BoQ",
            "total_cost": Decimal("0"),
            "items": []
        }
        result = identify_highest_cost_weight_item(job)
        self.assertIsNone(result["highest_item"])
        text = generate_recommendation_text(result["highest_item"])
        self.assertEqual(text, "")

    def test_downstream_safe_with_zero_total(self):
        """When total cost is zero, recommendation text should be empty"""
        job = {
            "job_id": 5,
            "job_name": "Zero Total",
            "total_cost": Decimal("0"),
            "items": [
                {"name": "Item A", "cost": Decimal("0"), "weight_pct": Decimal("0")}
            ]
        }
        ok, msg = check_boq_health(job)
        self.assertFalse(ok)
        self.assertIn("zero", msg.lower())

        result = identify_highest_cost_weight_item(job)
        self.assertIsNone(result["highest_item"])
        text = generate_recommendation_text(result["highest_item"])
        self.assertEqual(text, "")


if __name__ == "__main__":
    unittest.main()
