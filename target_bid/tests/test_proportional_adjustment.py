from decimal import Decimal

from django.test import SimpleTestCase

from target_bid.utils.proportional_adjustment import ProportionalAdjustmentCalculator


class ProportionalAdjustmentCalculatorTests(SimpleTestCase):
    def test_factor_below_one_for_reduction(self):
        f = ProportionalAdjustmentCalculator.compute(Decimal("1000000"), Decimal("800000"))
        self.assertEqual(f, Decimal("0.8000"))

    def test_factor_above_one_for_increase(self):
        f = ProportionalAdjustmentCalculator.compute(Decimal("1000000"), Decimal("1200000"))
        self.assertEqual(f, Decimal("1.2000"))

    def test_raises_on_zero_total(self):
        with self.assertRaises(ValueError):
            ProportionalAdjustmentCalculator.compute(Decimal("0"), Decimal("800000"))
