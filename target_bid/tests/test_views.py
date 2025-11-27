from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from target_bid.models.rab_job_item import RabJobItem
from target_bid.views import (
    cheaper_suggestions_view,
    fetch_rab_job_items_view,
    optimize_ahs_materials_view,
)


class FetchRabJobItemsViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_view_returns_serialised_payload(self):
        request = self.factory.get("/target_bid/rabs/99/items/")
        mock_item = RabJobItem(
            rab_item_id=5,
            name="Urugan Tanah",
            unit_name="m2",
            unit_price=Decimal("12500"),
            volume=Decimal("3"),
            total_price=Decimal("37500"),
            rab_item_header_id=4,
            rab_item_header_name="Pekerjaan Persiapan",
            custom_ahs_id=None,
            analysis_code="AT.02",
        )
        mock_service = patch("target_bid.views.RabJobItemService")
        mock_service_instance = mock_service.start()
        mock_service_instance.return_value.get_items_with_classification.return_value = ([mock_item], [], [])
        
        response = fetch_rab_job_items_view(request, rab_id=99)
        
        mock_service.stop()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["rab_id"], 99)
        self.assertIn("items", response.data)


class CheaperSuggestionsViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("target_bid.views.get_cheaper_alternatives", return_value=[{"name": "Steel", "price": 500}])
    def test_returns_results(self, mock_get):
        request = self.factory.get("/target_bid/cheaper-suggestions/?name=Steel&unit=kg&price=1000")
        response = cheaper_suggestions_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["name"], "Steel")
        mock_get.assert_called_once()


class OptimizeAhsMaterialsViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("target_bid.views.optimize_ahs_price")
    def test_returns_payload(self, mock_optimize):
        mock_optimize.return_value = {"ahs_code": "AHS-01", "replacements": []}
        request = self.factory.post(
            "/target_bid/ahs/AHS-01/optimize/",
            {"target_budget": "80%", "mode": "percentage"},
            format="json",
        )
        response = optimize_ahs_materials_view(request, ahs_code="AHS-01")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["ahs_code"], "AHS-01")

        args, kwargs = mock_optimize.call_args
        self.assertEqual(args[0], "AHS-01")
        self.assertEqual(kwargs["material_limit"], 2)
        self.assertIsNotNone(kwargs["target_input"])
        self.assertEqual(kwargs["target_input"].mode, "percentage")
        self.assertEqual(kwargs["target_input"].value, Decimal("80"))

    @patch("target_bid.views.optimize_ahs_price", return_value=None)
    def test_returns_not_found_when_breakdown_missing(self, mock_optimize):
        request = self.factory.post(
            "/target_bid/ahs/UNKNOWN/optimize/",
            {},
            format="json",
        )
        response = optimize_ahs_materials_view(request, ahs_code="UNKNOWN")

        self.assertEqual(response.status_code, 404)
        mock_optimize.assert_called_once()

    def test_rejects_non_integer_limit(self):
        request = self.factory.post(
            "/target_bid/ahs/AHS-01/optimize/",
            {"material_limit": "two"},
            format="json",
        )
        response = optimize_ahs_materials_view(request, ahs_code="AHS-01")

        self.assertEqual(response.status_code, 400)
        self.assertIn("material_limit", response.data)

    @patch("target_bid.views.optimize_ahs_price")
    def test_requires_mode_when_target_budget_present(self, mock_optimize):
        request = self.factory.post(
            "/target_bid/ahs/AHS-01/optimize/",
            {"target_budget": "100000"},
            format="json",
        )
        response = optimize_ahs_materials_view(request, ahs_code="AHS-01")

        self.assertEqual(response.status_code, 400)
        self.assertIn("mode", response.data)
        mock_optimize.assert_not_called()

    @patch("target_bid.views.optimize_ahs_price")
    def test_invalid_target_budget_raises_validation_error(self, mock_optimize):
        request = self.factory.post(
            "/target_bid/ahs/AHS-01/optimize/",
            {"target_budget": "abc", "mode": "absolute"},
            format="json",
        )
        response = optimize_ahs_materials_view(request, ahs_code="AHS-01")

        self.assertEqual(response.status_code, 400)
        self.assertIn("target_budget", response.data)
        mock_optimize.assert_not_called()
