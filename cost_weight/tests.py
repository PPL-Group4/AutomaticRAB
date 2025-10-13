import unittest
from decimal import Decimal
from cost_weight.services.cost_weight_calc import (
    calculate_cost_weights,
    format_weights,
    _to_decimal,
    _normalize_weights
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

class CostWeightNormalizationTests(unittest.TestCase):
    def test_normalization_handles_total_below_100(self):
        weights = {"A": Decimal("33.33"), "B": Decimal("33.33"), "C": Decimal("33.33")}
        res = _normalize_weights(weights.copy())
        self.assertEqual(sum(res.values()), Decimal("100.00"))

    def test_normalization_handles_total_above_100(self):
        weights = {"A": Decimal("33.34"), "B": Decimal("33.34"), "C": Decimal("33.34")}
        res = _normalize_weights(weights.copy())
        self.assertEqual(sum(res.values()), Decimal("100.00"))

    def test_normalization_does_nothing_if_exact_100(self):
        weights = {"A": Decimal("20.00"), "B": Decimal("30.00"), "C": Decimal("50.00")}
        res = _normalize_weights(weights.copy())
        self.assertEqual(res, weights)

    def test_normalization_zero_total_skipped(self):
        weights = {"A": Decimal("0.00"), "B": Decimal("0.00")}
        res = _normalize_weights(weights.copy())
        self.assertEqual(res, weights)

    def test_normalization_keeps_values_within_valid_range(self):
        weights = {"A": Decimal("33.33"), "B": Decimal("33.33"), "C": Decimal("33.33")}
        res = _normalize_weights(weights.copy())
        for v in res.values():
            self.assertTrue(Decimal("0.00") <= v <= Decimal("100.00"))
        self.assertEqual(sum(res.values()), Decimal("100.00"))

    def test_normalization_varied_decimal_places(self):
        weights = {"A": Decimal("33.3"), "B": Decimal("33.3"), "C": Decimal("33.3")}
        res = _normalize_weights(weights.copy(), decimal_places=1)
        self.assertEqual(sum(res.values()), Decimal("100.0"))

    def test_normalization_is_deterministic(self):
        weights = {"X": Decimal("25.00"), "Y": Decimal("25.00"), "Z": Decimal("50.00")}
        r1 = _normalize_weights(weights.copy())
        r2 = _normalize_weights(weights.copy())
        self.assertEqual(r1, r2)

    def test_normalization_affects_largest_weight_only(self):
        weights = {"A": Decimal("30.00"), "B": Decimal("30.00"), "C": Decimal("39.99")}
        res = _normalize_weights(weights.copy())
        changed_key = [k for k in res if res[k] != weights[k]]
        self.assertEqual(changed_key, ["C"])  # only the largest should change

class IntegrationWithCostWeightCalcTests(unittest.TestCase):
    def test_integration_normalization_makes_total_exactly_100(self):
        items = {"A": Decimal("333.33"), "B": Decimal("333.33"), "C": Decimal("333.34")}
        res = calculate_cost_weights(items)
        self.assertEqual(sum(res.values()), Decimal("100.00"))

class CostWeightZeroDivisionTests(unittest.TestCase):
    def test_zero_division_returns_all_zero(self):
        items = {"A": 0, "B": 0, "C": 0}
        res = calculate_cost_weights(items)
        self.assertTrue(all(v == Decimal("0.00") for v in res.values()))
        self.assertEqual(sum(res.values()), Decimal("0.00"))

    def test_zero_division_with_empty_input(self):
        res = calculate_cost_weights({})
        self.assertEqual(res, {})

    def test_zero_division_with_partial_nonzero(self):
        items = {"A": 0, "B": 0, "C": 100}
        res = calculate_cost_weights(items)
        self.assertEqual(res["C"], Decimal("100.00"))
        self.assertEqual(res["A"], Decimal("0.00"))

if __name__ == "__main__":
    unittest.main()