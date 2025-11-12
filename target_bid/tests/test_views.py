from decimal import Decimal
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory
from unittest.mock import patch
from target_bid.views import fetch_rab_job_items_view, cheaper_suggestions_view
from target_bid.models.rab_job_item import RabJobItem


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
        with patch("target_bid.views.fetch_rab_job_items", return_value=([mock_item], [], [])):
            response = fetch_rab_job_items_view(request, rab_id=99)

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
