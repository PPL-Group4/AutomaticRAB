from unittest.mock import patch
from django.test import SimpleTestCase
from target_bid.services.cheaper_price_service import get_cheaper_alternatives


class CheaperPriceServiceTests(SimpleTestCase):
    @patch("target_bid.services.cheaper_price_service.repo")
    def test_get_cheaper_alternatives_uses_repository(self, mock_repo):
        mock_repo.find_cheaper_same_unit.return_value = [{"name": "Alt", "price": 1}]

        result = get_cheaper_alternatives("Steel", "kg", 1000)

        mock_repo.find_cheaper_same_unit.assert_called_once_with("Steel", "kg", 1000)
        self.assertEqual(result, [{"name": "Alt", "price": 1}])
