import unittest
from decimal import Decimal
from cost_weight.services.cost_weight_calc import (
    calculate_cost_weights,
    format_weights,
    _to_decimal,
)

class CostWeightCalcTests(unittest.TestCase):
    def test_simple_exact_split_no_distribution(self):
        items = {"A": Decimal("200"), "B": Decimal("200")}
        res = calculate_cost_weights(items)
        self.assertEqual(res, {"A": Decimal("50.00"), "B": Decimal("50.00")})
        self.assertEqual(sum(res.values()), Decimal("100.00"))

    def test_rounding_distribution_happens_and_sums_100(self):
        items = {"A": 1, "B": 1, "C": 1}
        res = calculate_cost_weights(items)
        self.assertEqual(sum(res.values()), Decimal("100.00"))
        self.assertTrue(any(v >= Decimal("33.34") for v in res.values()))

    def test_zero_total_early_return(self):
        res = calculate_cost_weights({"A": 0, "B": 0})
        self.assertEqual(res["A"], Decimal("0.00"))
        self.assertEqual(res["B"], Decimal("0.00"))
        self.assertEqual(sum(res.values()), Decimal("0.00"))

    def test_accepts_various_number_types_hits_float_branch(self):
        items = {"i": 2, "s": "3", "f": 5.0, "d": Decimal("0")}  # total=10
        res = calculate_cost_weights(items)
        self.assertEqual(
            res, {"i": Decimal("20.00"), "s": Decimal("30.00"),
                  "f": Decimal("50.00"), "d": Decimal("0.00")}
        )
        self.assertEqual(_to_decimal(1.2), Decimal("1.2"))     # float branch
        self.assertEqual(_to_decimal("4.50"), Decimal("4.50")) # str branch
        self.assertEqual(_to_decimal(3), Decimal("3"))         # int branch
        self.assertEqual(_to_decimal(Decimal("7.7")), Decimal("7.7"))  # decimal branch

    def test_custom_decimal_places_paths(self):
        items = {"A": 1, "B": 2}
        res = calculate_cost_weights(items, decimal_places=1)
        self.assertEqual(res["A"], Decimal("33.3"))
        self.assertEqual(res["B"], Decimal("66.7"))
        self.assertEqual(sum(res.values()), Decimal("100.0"))

    def test_deterministic_order_on_ties(self):
        items = {"X": Decimal("10.01"), "Y": Decimal("10.01"), "Z": Decimal("9.98")}
        r1 = calculate_cost_weights(items)
        r2 = calculate_cost_weights(items)
        self.assertEqual(r1, r2)
        self.assertEqual(sum(r1.values()), Decimal("100.00"))

    def test_format_weights_serializes_strings(self):
        items = {"A": Decimal("2500"), "B": Decimal("1500"), "C": Decimal("1000")}
        res = calculate_cost_weights(items)
        self.assertEqual(format_weights(res), {"A": "50.00", "B": "30.00", "C": "20.00"})

if __name__ == "__main__":
    unittest.main()