from django.test import TestCase, Client
from unittest.mock import patch
from django.urls import reverse
import json

class MatchBestViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self._best_patcher = patch("automatic_job_matching.views.MatchingService.perform_best_match")
        self.mock_best = self._best_patcher.start()

    def tearDown(self):
        self._best_patcher.stop()

    def test_best_view_returns_exact_match(self):
        self.mock_best.return_value = {"id": 1, "code": "X.01", "name": "Dummy"}
        url = reverse("match-best")
        payload = {"description": "X.01"}
        response = self.client.post(url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["match"]["code"], "X.01")
        self.assertEqual(data["status"], "found")   
        self.mock_best.assert_called_once_with("X.01")

    def test_best_view_returns_fuzzy_when_no_exact(self):
        self.mock_best.return_value = {"id": 2, "code": "Y.01", "name": "Some Name"}
        url = reverse("match-best")
        payload = {"description": "Some Name"}
        response = self.client.post(url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["match"]["code"], "Y.01")
        self.assertEqual(data["status"], "found")  
        self.mock_best.assert_called_once_with("Some Name")

    def test_best_view_returns_multiple_one_item(self):
        self.mock_best.return_value = [{"id": 2, "code": "Y.01", "name": "Some Name"}]
        url = reverse("match-best")
        payload = {"description": "Single fuzzy"}
        response = self.client.post(url, json.dumps(payload), content_type="application/json")
        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data["match"]), 1)
        self.assertEqual(data["status"], "similar")  

    def test_best_view_returns_multiple_more_than_one(self):
        self.mock_best.return_value = [
            {"id": 3, "code": "Z.01", "name": "Fallback 1"},
            {"id": 4, "code": "Z.02", "name": "Fallback 2"}
        ]
        url = reverse("match-best")
        payload = {"description": "Unknown"}
        response = self.client.post(url, json.dumps(payload), content_type="application/json")
        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data["match"]), 2)
        self.assertEqual(data["status"], "found 2 similar")  

    def test_best_view_invalid_json_returns_400(self):
        url = reverse("match-best")
        response = self.client.post(url, "not-json", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_best_view_missing_description_defaults(self):
        self.mock_best.return_value = None
        url = reverse("match-best")
        response = self.client.post(url, json.dumps({}), content_type="application/json")
        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(data["match"])
        self.assertEqual(data["status"], "not found") 
        self.mock_best.assert_called_once_with("")


class SuggestMatchesViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    @patch("automatic_job_matching.views.MatchingService.search_candidates")
    def test_suggest_view_uses_query(self, mock_search):
        mock_search.return_value = [{"code": "A.1", "name": "Pondasi"}]
        url = reverse("match-suggest")
        response = self.client.get(url, {"q": "A.1"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["results"][0]["code"], "A.1")
        mock_search.assert_called_once_with("A.1", 10)

    @patch("automatic_job_matching.views.MatchingService.perform_multiple_match")
    def test_suggest_view_falls_back_to_description(self, mock_multi):
        mock_multi.return_value = [{"code": "B.2", "name": "Beton"}]
        url = reverse("match-suggest")
        response = self.client.get(url, {"description": "Pekerjaan beton"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["results"][0]["code"], "B.2")
        mock_multi.assert_called_once_with("Pekerjaan beton", 10, 0.4)