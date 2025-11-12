from decimal import Decimal
import pytest
from django.test import SimpleTestCase
from target_bid.utils.budget_service import TargetBudgetConverter, adjust_unit_prices_preserving_volume
from target_bid.validators import TargetBudgetInput


class DummyItem:
    def __init__(self, name, unit_price, volume):
        self.name = name
        self.unit_price = Decimal(unit_price)
        self.volume = Decimal(volume)
        self.total_price = self.unit_price * self.volume


class AdjustUnitPricesPreservingVolumeTests(SimpleTestCase):
    def test_adjustment_scales_prices_correctly(self):
        item = DummyItem("Concrete", "100000", "10")
        adjust_unit_prices_preserving_volume([item], Decimal("1.2"))
        self.assertEqual(item.unit_price, Decimal("120000.0"))
        self.assertEqual(item.total_price, Decimal("1200000.0"))
        self.assertEqual(item.volume, Decimal("10"))

    def test_handles_missing_price_or_volume(self):
        item = DummyItem("Unknown", "0", "0")
        item.unit_price = None
        item.volume = None
        adjust_unit_prices_preserving_volume([item], Decimal("2.0"))
        self.assertEqual(item.unit_price, Decimal("0"))
        self.assertEqual(item.total_price, Decimal("0"))


class TargetBudgetConverterTests(SimpleTestCase):
    def test_percentage_to_nominal(self):
        total = Decimal("1000000")
        data = TargetBudgetInput(mode="percentage", value=Decimal("50"))
        result = TargetBudgetConverter.to_nominal(data, total)
        self.assertEqual(result, Decimal("500000.00"))

    def test_absolute_mode_returns_same_value(self):
        total = Decimal("1000000")
        data = TargetBudgetInput(mode="absolute", value=Decimal("750000"))
        result = TargetBudgetConverter.to_nominal(data, total)
        self.assertEqual(result, Decimal("750000.00"))

    def test_invalid_current_total_raises(self):
        data = TargetBudgetInput(mode="percentage", value=Decimal("50"))
        with pytest.raises(TypeError):
            TargetBudgetConverter.to_nominal(data, "1000000")
