from decimal import Decimal, InvalidOperation
from unittest.mock import patch, MagicMock
from django.test import SimpleTestCase
from io import StringIO

from automatic_job_matching.service.ahs_breakdown_service import get_ahs_breakdown, _parse_decimal, _load_catalog, _format_decimal, _MONEY_QUANTUM


class AhsBreakdownServiceTests(SimpleTestCase):

    def test_returns_breakdown_for_known_code(self):
        # Stub data matching new backend schema
        stub_components = {
            "A.01.001": [
                {"component_type": "labor", "component_id": "L1", "quantity": "2"},
                {"component_type": "equipment", "component_id": "E1", "quantity": "1.5"},
                {"component_type": "material", "component_id": "M1", "quantity": "4"},
            ]
        }

        stub_labor = {
            "L1": {
                "unit_price": Decimal("100"),
                "code": "LAB1",
                "name": "Labor",
                "unit": "OH"
            }
        }
        stub_equipment = {
            "E1": {
                "unit_price": Decimal("50"),
                "code": "EQ1",
                "name": "Excavator",
                "unit": "hour"
            }
        }
        stub_material = {
            "M1": {
                "unit_price": Decimal("25"),
                "code": "MAT1",
                "name": "Sand",
                "unit": "m3",
                "brand": "StubBrand",
            }
        }

        # unit_price now comes from ahs_main.csv
        stub_main = {
            "A.01.001": {
                "name": "Stub Work",
                "unit_price": Decimal("500")
            }
        }

        with patch(
            "automatic_job_matching.service.ahs_breakdown_service._components_by_code",
            return_value=stub_components,
        ), patch(
            "automatic_job_matching.service.ahs_breakdown_service._labor_catalog",
            return_value=stub_labor,
        ), patch(
            "automatic_job_matching.service.ahs_breakdown_service._equipment_catalog",
            return_value=stub_equipment,
        ), patch(
            "automatic_job_matching.service.ahs_breakdown_service._material_catalog",
            return_value=stub_material,
        ), patch(
            "automatic_job_matching.service.ahs_breakdown_service._ahs_main_catalog",
            return_value=stub_main,
        ):

            breakdown = get_ahs_breakdown("A-01-001")

        # Validate metadata
        self.assertIsNotNone(breakdown)
        self.assertEqual(breakdown["name"], "Stub Work")
        self.assertEqual(breakdown["unit_price"], 500.0)

        totals = breakdown["totals"]

        # New backend logic:
        # labor = 2 * 100 = 200
        # equipment = 1.5 * 50 = 75
        # materials = 4 * 25 = 100
        self.assertEqual(totals["labor"], 200.0)
        self.assertEqual(totals["equipment"], 75.0)
        self.assertEqual(totals["materials"], 100.0)
        self.assertEqual(totals["overall"], 375.0)

        # Validate component sections exist
        self.assertIn("labor", breakdown["components"])
        self.assertIn("equipment", breakdown["components"])
        self.assertIn("materials", breakdown["components"])

        # material brand still required
        materials = breakdown["components"]["materials"]
        self.assertEqual(len(materials), 1)
        self.assertEqual(materials[0]["brand"], "StubBrand")

    def test_returns_none_for_unknown_code(self):
        with patch(
            "automatic_job_matching.service.ahs_breakdown_service._components_by_code",
            return_value={}
        ):
            self.assertIsNone(get_ahs_breakdown("ZZ.99.999"))
    
    def test_none_code_returns_none(self):
        self.assertIsNone(get_ahs_breakdown(""))
        self.assertIsNone(get_ahs_breakdown(None))

    @patch("automatic_job_matching.service.ahs_breakdown_service._components_by_code",
           return_value={"A.01.001": []})
    def test_components_exist_but_empty(self, _):
        self.assertIsNone(get_ahs_breakdown("A.01.001"))

    @patch("automatic_job_matching.service.ahs_breakdown_service._ahs_main_catalog",
           return_value={})
    @patch("automatic_job_matching.service.ahs_breakdown_service._components_by_code",
           return_value={"A.01.001": [
               {"component_type": "labor", "component_id": "L1", "quantity": "1"}
           ]})
    @patch("automatic_job_matching.service.ahs_breakdown_service._labor_catalog",
           return_value={"L1": {
               "unit_price": Decimal("100"),
               "code": "LAB1",
               "name": "Labor",
               "unit": "OH"
           }})
    @patch("automatic_job_matching.service.ahs_breakdown_service._equipment_catalog",
           return_value={})
    @patch("automatic_job_matching.service.ahs_breakdown_service._material_catalog",
           return_value={})
    def test_main_catalog_missing(self, *_):
        result = get_ahs_breakdown("A.01.001")
        self.assertIsNone(result["name"])
        self.assertIsNone(result["unit_price"])

    @patch("automatic_job_matching.service.ahs_breakdown_service._components_by_code",
           return_value={"A.01.001": [
               {"component_type": "labor", "component_id": "L1",
                "quantity": "", "coefficient": ""}
           ]})
    @patch("automatic_job_matching.service.ahs_breakdown_service._labor_catalog",
           return_value={"L1": {
               "unit_price": Decimal("100"),
               "code": "LAB1",
               "name": "Labor",
               "unit": "OH"
           }})
    @patch("automatic_job_matching.service.ahs_breakdown_service._ahs_main_catalog",
           return_value={"A.01.001": {"name": "X", "unit_price": Decimal("999")}})
    @patch("automatic_job_matching.service.ahs_breakdown_service._equipment_catalog", return_value={})
    @patch("automatic_job_matching.service.ahs_breakdown_service._material_catalog", return_value={})
    def test_quantity_and_coefficient_missing_defaults_to_zero(self, *_):
        result = get_ahs_breakdown("A.01.001")
        labor = result["totals"]["labor"]
        self.assertEqual(labor, 0.0)

    @patch("automatic_job_matching.service.ahs_breakdown_service._components_by_code",
           return_value={"A.01.001": [
               {"component_type": "labor", "component_id": "L1", "quantity": "2"}
           ]})
    @patch("automatic_job_matching.service.ahs_breakdown_service._labor_catalog",
           return_value={"L1": {
               "unit_price": None,
               "code": "LAB1",
               "name": "Labor",
               "unit": "OH"
           }})
    @patch("automatic_job_matching.service.ahs_breakdown_service._material_catalog", return_value={})
    @patch("automatic_job_matching.service.ahs_breakdown_service._equipment_catalog", return_value={})
    @patch("automatic_job_matching.service.ahs_breakdown_service._ahs_main_catalog",
           return_value={"A.01.001": {"name": "X", "unit_price": Decimal("100")}})
    def test_unit_price_missing(self, *_):
        result = get_ahs_breakdown("A.01.001")
        # totals should remain 0 because unit_price is None
        self.assertEqual(result["totals"]["labor"], 0.0)

    @patch("automatic_job_matching.service.ahs_breakdown_service._components_by_code",
           return_value={"A.01.001": [
               {"component_type": "material", "component_id": "M1", "quantity": "1"}
           ]})
    @patch("automatic_job_matching.service.ahs_breakdown_service._material_catalog",
           return_value={"M1": {
               "unit_price": Decimal("50"),
               "code": "MAT1",
               "name": "Sand",
               "unit": "kg",
               "brand": None
           }})
    @patch("automatic_job_matching.service.ahs_breakdown_service._labor_catalog", return_value={})
    @patch("automatic_job_matching.service.ahs_breakdown_service._equipment_catalog", return_value={})
    @patch("automatic_job_matching.service.ahs_breakdown_service._ahs_main_catalog",
           return_value={"A.01.001": {"name": "X", "unit_price": Decimal("123")}})
    def test_material_missing_brand(self, *_):
        result = get_ahs_breakdown("A.01.001")
        materials = result["components"]["materials"]
        self.assertEqual(materials[0]["brand"], None)

    def test_catalog_loader_handles_file_not_found(self):
        """Force loader to handle FileNotFoundError safely."""
        mock_path = MagicMock()
        mock_path.open.side_effect = FileNotFoundError

        from automatic_job_matching.service.ahs_breakdown_service import _load_catalog
        result = _load_catalog(mock_path)

        self.assertEqual(result, {})

    def test_parse_decimal_cases(self):
        self.assertIsNone(_parse_decimal(None))
        self.assertIsNone(_parse_decimal(""))
        self.assertIsNone(_parse_decimal("   "))
        self.assertEqual(_parse_decimal("10.55"), Decimal("10.55"))
        self.assertIsNone(_parse_decimal("abc"))

    @patch("automatic_job_matching.service.ahs_breakdown_service.csv.DictReader")
    def test_load_catalog_normal(self, mock_reader):
        mock_reader.return_value = [
            {"id": "1", "code": "A", "name": "Item", "unit": "kg", "unit_price": "100"},
            {"id": "", "code": "skip", "name": "skip", "unit": "x", "unit_price": "1"},  # skipped
        ]

        mock_path = MagicMock()
        mock_path.open.return_value = StringIO("fake")

        result = _load_catalog(mock_path, extra_fields=["brand"])

        self.assertIn("1", result)
        self.assertEqual(result["1"]["unit_price"], Decimal("100"))
        self.assertIn("brand", result["1"])

    @patch("automatic_job_matching.service.ahs_breakdown_service._components_by_code",
        return_value={"A.01.001": [
            # labor with quantity only
            {"component_type": "labor", "component_id": "L1", "quantity": "2", "coefficient": ""},
            # equipment with coefficient only
            {"component_type": "equipment", "component_id": "E1", "quantity": "", "coefficient": "3"},
            # material missing catalog entry
            {"component_type": "material", "component_id": "M9", "quantity": "1", "coefficient": ""},
        ]})
    @patch("automatic_job_matching.service.ahs_breakdown_service._labor_catalog",
        return_value={"L1": {
            "unit_price": Decimal("10"),
            "code": "LC",
            "name": "Labor Item",
            "unit": "OH"
        }})
    @patch("automatic_job_matching.service.ahs_breakdown_service._equipment_catalog",
        return_value={"E1": {
            "unit_price": Decimal("5"),
            "code": "EQ",
            "name": "Excavator",
            "unit": "hour"
        }})
    @patch("automatic_job_matching.service.ahs_breakdown_service._material_catalog",
        return_value={})  # empty → M9 missing
    @patch("automatic_job_matching.service.ahs_breakdown_service._ahs_main_catalog",
        return_value={"A.01.001": {
            "name": "EdgeCase AHS",
            "unit_price": Decimal("999.99")
        }})
    def test_full_edge_case_branch_coverage(self, *_):
        result = get_ahs_breakdown("A.01.001")

        # Validate totals:
        # labor: 2 * 10 = 20
        # equipment: 3 * 5 = 15
        # materials: missing → total_cost None → not added
        totals = result["totals"]
        self.assertEqual(totals["labor"], 20.0)
        self.assertEqual(totals["equipment"], 15.0)
        self.assertEqual(totals["materials"], 0.0)

        # Check missing catalog entry produces None fields
        missing_mat = result["components"]["materials"][0]
        self.assertEqual(missing_mat["code"], None)
        self.assertEqual(missing_mat["name"], None)
        self.assertEqual(missing_mat["unit_price"], None)
        self.assertEqual(missing_mat["total_cost"], None)

    def test_format_decimal_raises_invalid_operation(self):
        class BadDecimal:
            def quantize(self, *args, **kwargs):
                raise InvalidOperation()
            def __float__(self):
                return 1.23

        result = _format_decimal(BadDecimal(), _MONEY_QUANTUM)
        self.assertEqual(result, 1.23)

    def test_format_decimal_raises_value_error(self):
        class BadDecimal2:
            def quantize(self, *args, **kwargs):
                raise ValueError()
            def __float__(self):
                return 4.56

        result = _format_decimal(BadDecimal2(), _MONEY_QUANTUM)
        self.assertEqual(result, 4.56)

    
    @patch("automatic_job_matching.service.ahs_breakdown_service._load_catalog")
    def test_labor_catalog_calls_loader(self, mock_loader):
        from automatic_job_matching.service.ahs_breakdown_service import _labor_catalog
        _labor_catalog.cache_clear()
        _labor_catalog()
        mock_loader.assert_called_once()
    
    @patch("automatic_job_matching.service.ahs_breakdown_service._load_catalog")
    def test_equipment_catalog_calls_loader(self, mock_loader):
        from automatic_job_matching.service.ahs_breakdown_service import _equipment_catalog
        _equipment_catalog.cache_clear()
        _equipment_catalog()
        mock_loader.assert_called_once()

    @patch("automatic_job_matching.service.ahs_breakdown_service._load_catalog")
    def test_material_catalog_calls_loader_with_brand(self, mock_loader):
        from automatic_job_matching.service.ahs_breakdown_service import _material_catalog
        _material_catalog.cache_clear()
        _material_catalog()
        args, kwargs = mock_loader.call_args
        self.assertIn("extra_fields", kwargs)
        self.assertEqual(kwargs["extra_fields"], ["brand"])
    
    @patch("automatic_job_matching.service.ahs_breakdown_service.csv.DictReader")
    def test_main_catalog_normal(self, mock_reader):
        mock_reader.return_value = [
            {"code": "A.01", "name": "Test", "unit_price": "123"},
            {"code": "", "name": "Skip", "unit_price": "10"},  # skipped
        ]

        mock_path = MagicMock()
        mock_path.open.return_value = StringIO("fake")

        from automatic_job_matching.service.ahs_breakdown_service import _ahs_main_catalog
        _ahs_main_catalog.cache_clear()
        result = _ahs_main_catalog()

        self.assertIn("A.01", result)
        self.assertEqual(result["A.01"]["name"], "Test")
        self.assertEqual(result["A.01"]["unit_price"], Decimal("123"))

    @patch("automatic_job_matching.service.ahs_breakdown_service._parse_decimal", return_value=None)
    @patch("automatic_job_matching.service.ahs_breakdown_service.csv.DictReader")
    def test_main_catalog_missing_price(self, mock_reader, _):
        mock_reader.return_value = [{"code": "A.01", "name": "X", "unit_price": ""}]
        mock_path = MagicMock()
        mock_path.open.return_value = StringIO("fake")

        from automatic_job_matching.service.ahs_breakdown_service import _ahs_main_catalog
        _ahs_main_catalog.cache_clear()
        result = _ahs_main_catalog()

        self.assertIsNone(result["A.01"]["unit_price"])

    @patch("automatic_job_matching.service.ahs_breakdown_service.Path.open", side_effect=FileNotFoundError)
    def test_main_catalog_file_not_found(self, _):
        from automatic_job_matching.service.ahs_breakdown_service import _ahs_main_catalog
        _ahs_main_catalog.cache_clear()
        result = _ahs_main_catalog()
        self.assertEqual(result, {})


    @patch("automatic_job_matching.service.ahs_breakdown_service.Path.open", side_effect=RuntimeError("boom"))
    def test_main_catalog_generic_exception(self, _):
        from automatic_job_matching.service.ahs_breakdown_service import _ahs_main_catalog
        _ahs_main_catalog.cache_clear()
        result = _ahs_main_catalog()
        self.assertEqual(result, {})


    @patch("automatic_job_matching.service.ahs_breakdown_service.csv.DictReader")
    def test_components_normal(self, mock_reader):
        mock_reader.return_value = [
            {"ahs_code": "A.01", "component_type": "labor", "component_id": "L1", "quantity": "2", "coefficient": ""}
        ]

        mock_path = MagicMock()
        mock_path.open.return_value = StringIO("fake")

        from automatic_job_matching.service.ahs_breakdown_service import _components_by_code
        _components_by_code.cache_clear()
        result = _components_by_code()

        self.assertIn("A.01", result)
        self.assertEqual(result["A.01"][0]["component_id"], "L1")

    @patch("automatic_job_matching.service.ahs_breakdown_service.csv.DictReader")
    def test_components_skips_invalid(self, mock_reader):
        mock_reader.return_value = [
            {"ahs_code": "", "component_type": "labor", "component_id": "L1"},  # skip canonical
            {"ahs_code": "A.01", "component_type": "invalid", "component_id": "L1"},  # skip invalid type
            {"ahs_code": "A.01", "component_type": "labor", "component_id": ""},  # skip missing id
        ]

        mock_path = MagicMock()
        mock_path.open.return_value = StringIO("fake")

        from automatic_job_matching.service.ahs_breakdown_service import _components_by_code
        _components_by_code.cache_clear()
        result = _components_by_code()

        self.assertEqual(result, {})

    @patch("automatic_job_matching.service.ahs_breakdown_service.Path.open", side_effect=FileNotFoundError)
    def test_components_file_not_found(self, _):
        from automatic_job_matching.service.ahs_breakdown_service import _components_by_code
        _components_by_code.cache_clear()
        result = _components_by_code()
        self.assertEqual(result, {})


    @patch("automatic_job_matching.service.ahs_breakdown_service.Path.open", side_effect=RuntimeError("boom"))
    def test_components_generic_exception(self, _):
        from automatic_job_matching.service.ahs_breakdown_service import _components_by_code
        _components_by_code.cache_clear()
        result = _components_by_code()
        self.assertEqual(result, {})
