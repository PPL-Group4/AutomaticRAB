from decimal import Decimal
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory
from unittest.mock import patch
from target_bid.views import fetch_rab_job_items_view
from target_bid.models.rab_job_item import RabJobItem
from target_bid.services.rab_job_item_service import RabJobItemService


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

        with patch.object(
            RabJobItemService,
            "get_items_with_classification",
            return_value=([mock_item], [], []),
        ):
            response = fetch_rab_job_items_view(request, rab_id=99)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["rab_id"], 99)
        self.assertIn("items", response.data)
        self.assertIn("locked_items", response.data)
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(response.data["items"][0]["name"], "Urugan Tanah")