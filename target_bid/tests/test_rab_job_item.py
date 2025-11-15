from decimal import Decimal
from django.test import SimpleTestCase
from target_bid.models.rab_job_item import RabJobItem, DecimalAdapter


class RabJobItemHelperTests(SimpleTestCase):
    def test_to_dict_serialises_numbers(self):
        item = RabJobItem(
            rab_item_id=10,
            name="Item",
            unit_name="m",
            unit_price=Decimal("12.3400"),
            volume=Decimal("2.000"),
            total_price=Decimal("24.6800"),
            rab_item_header_id=2,
            rab_item_header_name="Header",
            custom_ahs_id=None,
            analysis_code="AT.01",
        )
        data = item.to_dict()
        self.assertEqual(data["unit_price"], "12.34")
        self.assertEqual(data["volume"], "2")
        self.assertEqual(data["total_price"], "24.68")

    def test_decimal_adapter_helpers(self):
        self.assertEqual(DecimalAdapter.to_decimal("2.5"), Decimal("2.5"))
        self.assertEqual(DecimalAdapter.multiply(Decimal("2"), Decimal("3")), Decimal("6"))
        self.assertEqual(DecimalAdapter.to_string(Decimal("10.500")), "10.5")
