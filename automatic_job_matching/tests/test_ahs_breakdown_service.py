from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase

from automatic_job_matching.service.ahs_breakdown_service import get_ahs_breakdown


class AhsBreakdownServiceTests(SimpleTestCase):
    def test_returns_breakdown_for_known_code(self):
        stub_components = {
            "A.01.001": [
                {"component_type": "labor", "component_id": "L1", "quantity": "2"},
                {"component_type": "equipment", "component_id": "E1", "quantity": "1.5"},
                {"component_type": "material", "component_id": "M1", "quantity": "4"},
            ]
        }
        stub_labor = {
            "L1": {"unit_price": Decimal("100"), "code": "LAB1", "name": "Labor", "unit": "OH"}
        }
        stub_equipment = {
            "E1": {"unit_price": Decimal("50"), "code": "EQ1", "name": "Excavator", "unit": "hour"}
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
        stub_main = {"A.01.001": {"name": "Stub Work", "unit_price": Decimal("375")}}

        with patch(
            "automatic_job_matching.service.ahs_breakdown_service._components_by_code",
            return_value=stub_components,
        ) as mock_components, patch(
            "automatic_job_matching.service.ahs_breakdown_service._labor_catalog",
            return_value=stub_labor,
        ) as mock_labor, patch(
            "automatic_job_matching.service.ahs_breakdown_service._equipment_catalog",
            return_value=stub_equipment,
        ) as mock_equipment, patch(
            "automatic_job_matching.service.ahs_breakdown_service._material_catalog",
            return_value=stub_material,
        ) as mock_material, patch(
            "automatic_job_matching.service.ahs_breakdown_service._ahs_main_catalog",
            return_value=stub_main,
        ) as mock_main:
            breakdown = get_ahs_breakdown("a-01-001")

        self.assertIsNotNone(breakdown)
        self.assertEqual(breakdown["name"], "Stub Work")
        self.assertEqual(breakdown["unit_price"], 375.0)
        totals = breakdown["totals"]
        self.assertEqual(totals["labor"], 200.0)
        self.assertEqual(totals["equipment"], 75.0)
        self.assertEqual(totals["materials"], 100.0)
        self.assertEqual(totals["overall"], 375.0)

        materials = breakdown["components"]["materials"]
        self.assertEqual(len(materials), 1)
        self.assertEqual(materials[0]["brand"], "StubBrand")

        mock_components.assert_called_once_with()
        mock_labor.assert_called_once_with()
        mock_equipment.assert_called_once_with()
        mock_material.assert_called_once_with()
        mock_main.assert_called_once_with()

    def test_returns_none_for_unknown_code(self):
        with patch(
            "automatic_job_matching.service.ahs_breakdown_service._components_by_code",
            return_value={},
        ):
            self.assertIsNone(get_ahs_breakdown("ZZ.99.999"))
