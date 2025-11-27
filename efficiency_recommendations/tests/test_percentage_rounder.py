import unittest
from decimal import Decimal

from efficiency_recommendations.services.percentage_rounder import round_weight_percentages


class PercentageRounderTest(unittest.TestCase):

    def test_sum_is_exactly_100(self):
        items = [
            {"name": "A", "weight_pct": Decimal("33.335")},
            {"name": "B", "weight_pct": Decimal("33.335")},
            {"name": "C", "weight_pct": Decimal("33.33")},
        ]
        out = round_weight_percentages(items)
        self.assertEqual(sum(it["weight_pct"] for it in out), Decimal("100.00"))

    def test_many_small_items(self):
        items = [{"name": f"I{i}", "weight_pct": Decimal("1.111")} for i in range(90)]
        out = round_weight_percentages(items)
        self.assertEqual(sum(it["weight_pct"] for it in out), Decimal("100.00"))
        self.assertTrue(all(Decimal("0") <= it["weight_pct"] <= Decimal("100") for it in out))

    def test_single_item(self):
        items = [{"name": "Only", "weight_pct": Decimal("100")}]
        out = round_weight_percentages(items)
        self.assertEqual(out[0]["weight_pct"], Decimal("100.00"))

    def test_all_zeros(self):
        items = [{"name": "A", "weight_pct": Decimal("0")}, {"name": "B", "weight_pct": Decimal("0")}]
        out = round_weight_percentages(items)
        self.assertEqual(sum(it["weight_pct"] for it in out), Decimal("0.00"))

if __name__ == '__main__':
    unittest.main()