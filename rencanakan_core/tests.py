from django.test import SimpleTestCase
from unittest.mock import patch, MagicMock
from rencanakan_core.models import Project, Unit, ItemPrice, Ahs, AhsItem, Rab, RabItemHeader, RabItem, CustomAhs, CustomAhsItem


class RencanakanCoreModelTests(SimpleTestCase):
    def test_table_names_match(self):
        self.assertEqual(Project._meta.db_table, "projects")
        self.assertEqual(Unit._meta.db_table, "units")
        self.assertEqual(ItemPrice._meta.db_table, "item_prices")
        self.assertEqual(Ahs._meta.db_table, "ahs")
        self.assertEqual(AhsItem._meta.db_table, "ahs_items")

    def test_field_names_exist(self):
        field_names = [f.name for f in AhsItem._meta.get_fields()]
        for expected in [
            "ahs", "name", "unit", "coefficient",
            "section", "ahs_itemable_id", "ahs_itemable_type"
        ]:
            self.assertIn(expected, field_names)

    def test_resolve_item_price_returns_none_if_not_itemprice(self):
        item = AhsItem(ahs_itemable_type="Not\\ItemPrice")
        with patch.object(ItemPrice.objects, "get", side_effect=Exception("Should not be called")) as mock_get:
            self.assertIsNone(item.resolve_item_price())
            mock_get.assert_not_called()

    def test_resolve_item_price_success(self):
        dummy_price = MagicMock(spec=ItemPrice)
        item = AhsItem(ahs_itemable_type="App\\Models\\ItemPrice", ahs_itemable_id="M.01")
        with patch.object(ItemPrice.objects, "get", return_value=dummy_price) as mock_get:
            self.assertEqual(item.resolve_item_price(), dummy_price)
            mock_get.assert_called_once_with(id="M.01")

    def test_new_models_table_names(self):
        self.assertEqual(Rab._meta.db_table, "rabs")
        self.assertEqual(RabItemHeader._meta.db_table, "rab_item_headers")
        self.assertEqual(RabItem._meta.db_table, "rab_items")
        self.assertEqual(CustomAhs._meta.db_table, "custom_ahs")
        self.assertEqual(CustomAhsItem._meta.db_table, "custom_ahs_items")

    def test_new_models_are_unmanaged(self):
        models = [Rab, RabItemHeader, RabItem, CustomAhs, CustomAhsItem]
        for model in models:
            self.assertFalse(model._meta.managed)

    def test_rab_fields(self):
        field_names = [f.name for f in Rab._meta.get_fields()]
        for expected in ["id", "name", "project_id"]:
            self.assertIn(expected, field_names)

    def test_rab_item_header_fields(self):
        field_names = [f.name for f in RabItemHeader._meta.get_fields()]
        for expected in ["id", "rab", "name"]:
            self.assertIn(expected, field_names)

    def test_rab_item_fields(self):
        field_names = [f.name for f in RabItem._meta.get_fields()]
        for expected in ["id", "rab", "rab_item_header", "name", "custom_ahs_id", "volume", "price", "unit", "profit_margin"]:
            self.assertIn(expected, field_names)

    def test_custom_ahs_fields(self):
        field_names = [f.name for f in CustomAhs._meta.get_fields()]
        for expected in ["id", "code", "name", "project_id"]:
            self.assertIn(expected, field_names)

    def test_custom_ahs_item_fields(self):
        field_names = [f.name for f in CustomAhsItem._meta.get_fields()]
        for expected in ["id", "custom_ahs", "name", "unit", "coefficient", "section", "custom_ahs_itemable_id", "custom_ahs_itemable_type"]:
            self.assertIn(expected, field_names)