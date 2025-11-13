from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase

from target_bid.services.ahs_optimizer import optimize_ahs_price
from target_bid.validators import TargetBudgetInput


class OptimizeAhsPriceTests(SimpleTestCase):
    @patch("target_bid.services.ahs_optimizer.get_cheaper_alternatives")
    @patch("target_bid.services.ahs_optimizer.get_ahs_breakdown")
    def test_optimize_swaps_top_two_materials(self, mock_breakdown, mock_cheaper):
        mock_breakdown.return_value = {
            "totals": {"materials": 570.0, "overall": 970.0},
            "components": {
                "materials": [
                    {
                        "name": "Material A",
                        "unit": "kg",
                        "quantity": 5,
                        "unit_price": 50,
                        "total_cost": 250,
                        "brand": "Brand A",
                    },
                    {
                        "name": "Material B",
                        "unit": "kg",
                        "quantity": 2,
                        "unit_price": 100,
                        "total_cost": 200,
                        "brand": "Brand B",
                    },
                    {
                        "name": "Material C",
                        "unit": "kg",
                        "quantity": 1,
                        "unit_price": 120,
                        "total_cost": 120,
                        "brand": "Brand C",
                    },
                ]
            },
        }

        mock_cheaper.side_effect = [
            [
                {
                    "name": "Alt Material A",
                    "price": 40,
                    "unit": "kg",
                    "url": "http://example.com/a",
                    "source": "alt_source",
                }
            ],
            [
                {
                    "name": "Alt Material B",
                    "price": 80,
                    "unit": "kg",
                    "url": "http://example.com/b",
                    "source": "alt_source",
                }
            ],
        ]

        result = optimize_ahs_price("AHS-001")

        self.assertIsNotNone(result)
        self.assertEqual(result["total_saving"], "90")
        self.assertEqual(result["adjusted_totals"]["materials"], "480")
        self.assertEqual(result["adjusted_totals"]["overall"], "880")
        self.assertEqual(len(result["replacements"]), 2)
        self.assertEqual(result["replacements"][0]["name"], "Material A")
        self.assertEqual(result["replacements"][0]["alternative"]["price"], "40")
        self.assertEqual(result["replacements"][1]["name"], "Material B")

        calls = mock_cheaper.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].args[0], "Material A")
        self.assertEqual(calls[1].args[0], "Material B")

    @patch("target_bid.services.ahs_optimizer.get_cheaper_alternatives")
    @patch("target_bid.services.ahs_optimizer.get_ahs_breakdown")
    def test_optimize_returns_none_when_breakdown_missing(self, mock_breakdown, mock_cheaper):
        mock_breakdown.return_value = None
        result = optimize_ahs_price("AHS-UNKNOWN")
        self.assertIsNone(result)
        mock_cheaper.assert_not_called()

    @patch("target_bid.services.ahs_optimizer.get_cheaper_alternatives")
    @patch("target_bid.services.ahs_optimizer.get_ahs_breakdown")
    def test_optimize_with_target_budget_metadata(self, mock_breakdown, mock_cheaper):
        mock_breakdown.return_value = {
            "totals": {"materials": 570.0, "overall": 970.0},
            "components": {
                "materials": [
                    {
                        "name": "Material A",
                        "unit": "kg",
                        "quantity": 5,
                        "unit_price": 50,
                        "total_cost": 250,
                    },
                    {
                        "name": "Material B",
                        "unit": "kg",
                        "quantity": 2,
                        "unit_price": 100,
                        "total_cost": 200,
                    },
                ]
            },
        }
        mock_cheaper.side_effect = [
            [
                {
                    "name": "Alt Material A",
                    "price": 40,
                    "unit": "kg",
                    "url": "http://example.com/a",
                    "source": "alt_source",
                }
            ],
            [
                {
                    "name": "Alt Material B",
                    "price": 80,
                    "unit": "kg",
                    "url": "http://example.com/b",
                    "source": "alt_source",
                }
            ],
        ]

        target_input = TargetBudgetInput(mode="absolute", value=Decimal("900"))
        result = optimize_ahs_price("AHS-001", target_input=target_input)

        self.assertIsNotNone(result)
        self.assertIn("target_budget", result)
        self.assertEqual(result["target_budget"]["nominal"], "900")
        self.assertFalse(result["target_budget"]["met_before_adjustment"])
        self.assertTrue(result["target_budget"]["met_after_adjustment"])
        self.assertEqual(result["target_budget"]["remaining_gap"], "0")

    @patch("target_bid.services.ahs_optimizer.get_cheaper_alternatives")
    @patch("target_bid.services.ahs_optimizer.get_ahs_breakdown")
    def test_optimize_handles_absence_of_cheaper_options(self, mock_breakdown, mock_cheaper):
        mock_breakdown.return_value = {
            "totals": {"materials": 300.0, "overall": 500.0},
            "components": {
                "materials": [
                    {
                        "name": "Material A",
                        "unit": "kg",
                        "quantity": 3,
                        "unit_price": 50,
                        "total_cost": 150,
                    },
                    {
                        "name": "Material B",
                        "unit": "kg",
                        "quantity": 3,
                        "unit_price": 50,
                        "total_cost": 150,
                    },
                ]
            },
        }
        mock_cheaper.return_value = []

        result = optimize_ahs_price("AHS-001")

        self.assertIsNotNone(result)
        self.assertEqual(result["total_saving"], "0")
        self.assertEqual(len(result["replacements"]), 0)
        self.assertEqual(result["adjusted_totals"]["overall"], "500")
