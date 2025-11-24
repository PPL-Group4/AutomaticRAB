import json
from django.http import JsonResponse
from django.test import SimpleTestCase, Client
from unittest.mock import patch
from django.urls import reverse

from automatic_job_matching.security import SecurityValidationError

class MatchBestViewTests(SimpleTestCase):
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
        self.mock_best.assert_called_once_with("X.01", unit=None)

    def test_best_view_returns_fuzzy_when_no_exact(self):
        self.mock_best.return_value = {"id": 2, "code": "Y.01", "name": "Some Name"}
        url = reverse("match-best")
        payload = {"description": "Some Name"}
        response = self.client.post(url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["match"]["code"], "Y.01")
        self.assertEqual(data["status"], "found")
        self.mock_best.assert_called_once_with("Some Name", unit=None)

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

    def test_best_view_invalid_content_type(self):
        url = reverse("match-best")
        response = self.client.post(url, json.dumps({"description": "x"}), content_type="text/plain")
        self.assertEqual(response.status_code, 415)
        self.assertIn("error", response.json())
        self.mock_best.assert_not_called()

    @patch("automatic_job_matching.views.ensure_payload_size", side_effect=SecurityValidationError("too big"))
    def test_best_view_payload_too_large(self, _mock_size):
        url = reverse("match-best")
        payload = {"description": "x"}
        response = self.client.post(url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 413)
        self.assertIn("error", response.json())
        self.mock_best.assert_not_called()

    def test_best_view_missing_description_defaults(self):
        self.mock_best.return_value = None
        url = reverse("match-best")
        response = self.client.post(url, json.dumps({}), content_type="application/json")
        data = response.json()
        # The view now requires description and returns 400 for missing description
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", data)

    # NEW TESTS FOR UNIT PARAMETER
    def test_best_view_with_unit_m2(self):
        """Test that unit parameter is passed to matching service."""
        self.mock_best.return_value = {"id": 10, "code": "A.4.4.3.35", "name": "Pemasangan 1m2 Lantai Keramik"}
        url = reverse("match-best")
        payload = {"description": "pemasangan keramik", "unit": "m2"}
        response = self.client.post(url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["match"]["code"], "A.4.4.3.35")
        self.mock_best.assert_called_once_with("pemasangan keramik", unit="m2")

    def test_best_view_with_unit_m3(self):
        """Test with m3 unit."""
        self.mock_best.return_value = {"id": 11, "code": "A.5.1", "name": "Galian tanah biasa"}
        url = reverse("match-best")
        payload = {"description": "galian tanah", "unit": "m3"}
        response = self.client.post(url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.mock_best.assert_called_once_with("galian tanah", unit="m3")

    def test_best_view_with_unit_linear_m(self):
        """Test with linear meter unit."""
        self.mock_best.return_value = {"id": 12, "code": "A.7.2", "name": "Pipa PVC 3 inch"}
        url = reverse("match-best")
        payload = {"description": "pipa pvc", "unit": "m"}
        response = self.client.post(url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.mock_best.assert_called_once_with("pipa pvc", unit="m")

    def test_best_view_with_unit_ls(self):
        """Test with lump sum unit."""
        self.mock_best.return_value = {"id": 13, "code": "AT.01-1", "name": "Mobilisasi alat"}
        url = reverse("match-best")
        payload = {"description": "mobilisasi alat", "unit": "Ls"}
        response = self.client.post(url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.mock_best.assert_called_once_with("mobilisasi alat", unit="Ls")

    def test_best_view_with_unit_bh(self):
        """Test with piece unit."""
        self.mock_best.return_value = {"id": 14, "code": "A.9.1", "name": "Pintu panel"}
        url = reverse("match-best")
        payload = {"description": "pintu panel", "unit": "bh"}
        response = self.client.post(url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.mock_best.assert_called_once_with("pintu panel", unit="bh")

    def test_best_view_with_empty_unit_string(self):
        """Test that empty unit string is passed as None (sanitized)."""
        self.mock_best.return_value = {"id": 15, "code": "A.1", "name": "Test"}
        url = reverse("match-best")
        payload = {"description": "test", "unit": ""}
        response = self.client.post(url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        # sanitize_unit converts empty string to None
        self.mock_best.assert_called_once_with("test", unit=None)

    def test_best_view_unit_mismatch_returns_empty(self):
        """Test that unit mismatch returns appropriate response."""
        self.mock_best.return_value = []
        url = reverse("match-best")
        payload = {"description": "pemasangan keramik", "unit": "m"}
        response = self.client.post(url, json.dumps(payload), content_type="application/json")
        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "not found")
        self.assertEqual(data["match"], [])

    def test_best_view_with_confidence_and_unit(self):
        """Test response with confidence score and unit."""
        self.mock_best.return_value = {
            "id": 16,
            "code": "A.1.1",
            "name": "Test item",
            "confidence": 0.92
        }
        url = reverse("match-best")
        payload = {"description": "test", "unit": "m2"}
        response = self.client.post(url, json.dumps(payload), content_type="application/json")
        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "similar")  # confidence < 1.0
        self.assertEqual(data["match"]["confidence"], 0.92)

    def test_best_view_multiple_results_with_unit(self):
        """Test multiple results with unit parameter."""
        self.mock_best.return_value = [
            {"id": 17, "code": "A.1", "name": "Result 1"},
            {"id": 18, "code": "A.2", "name": "Result 2"},
            {"id": 19, "code": "A.3", "name": "Result 3"}
        ]
        url = reverse("match-best")
        payload = {"description": "test", "unit": "m2"}
        response = self.client.post(url, json.dumps(payload), content_type="application/json")
        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "found 3 similar")
        self.assertEqual(len(data["match"]), 3)

    def test_best_view_unit_with_special_characters(self):
        """Test unit with special characters - m² is NOT allowed by security validation."""
        url = reverse("match-best")
        payload = {"description": "test", "unit": "m²"}
        response = self.client.post(url, json.dumps(payload), content_type="application/json")
        # The security validation rejects units with special characters like ²
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_best_view_unit_case_insensitive(self):
        """Test that unit case is preserved."""
        self.mock_best.return_value = {"id": 21, "code": "A.1", "name": "Test"}
        url = reverse("match-best")
        payload = {"description": "test", "unit": "M3"}
        response = self.client.post(url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.mock_best.assert_called_once_with("test", unit="M3")

    def test_best_view_returns_alternatives_payload(self):
        alt_payload = {
            "message": "No matches with the same unit found.",
            "alternatives": [{"id": 42, "code": "X.1", "name": "Alt"}],
        }
        self.mock_best.return_value = alt_payload
        url = reverse("match-best")
        payload = {"description": "test", "unit": "m"}
        response = self.client.post(url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), alt_payload)


class JobMatchingPageTests(SimpleTestCase):
    def setUp(self):
        self.client = Client()

    @patch("automatic_job_matching.views.render")
    def test_job_matching_page_renders_template(self, mock_render):
        mock_render.return_value = JsonResponse({"ok": True})
        response = self.client.get(reverse("job-matching"))
        self.assertEqual(response.status_code, 200)
        self.assertIs(response, mock_render.return_value)
        mock_render.assert_called_once()
        args, _kwargs = mock_render.call_args
        self.assertEqual(args[1], "job_matching.html")


class AhsBreakdownViewTests(SimpleTestCase):
    def setUp(self):
        self.client = Client()

    def test_breakdown_returns_totals_for_known_code(self):
        url = reverse("ahs-breakdown", args=["1.1.1.1"])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], "1.1.1.1")
        self.assertIn("breakdown", payload)
        totals = payload["breakdown"]["totals"]
        self.assertAlmostEqual(totals["labor"], 127600.0)
        self.assertAlmostEqual(totals["materials"], 588215.63)
        self.assertGreater(len(payload["breakdown"]["components"]["materials"]), 0)
        self.assertNotIn("labor", payload["breakdown"]["components"])
        self.assertNotIn("equipment", payload["breakdown"]["components"])

    def test_breakdown_returns_404_for_unknown_code(self):
        url = reverse("ahs-breakdown", args=["ZZ.99.999"])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.json())


class BulkMatchViewTests(SimpleTestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("match-bulk")
        self._bulk_patch = patch("automatic_job_matching.views.MatchingService.perform_bulk_best_match")
        self.mock_bulk = self._bulk_patch.start()
        self._tag_patch = patch("automatic_job_matching.views.tag_match_event")
        self._log_patch = patch("automatic_job_matching.views.log_unmatched_entry")
        self.mock_tag = self._tag_patch.start()
        self.mock_log = self._log_patch.start()

    def tearDown(self):
        self._bulk_patch.stop()
        self._tag_patch.stop()
        self._log_patch.stop()

    def test_bulk_match_returns_results(self):
        self.mock_bulk.return_value = [
            {"description": "item a", "unit": "m2", "status": "found", "match": {"id": 1}},
            {"description": "item b", "unit": None, "status": "not found", "match": None},
        ]

        payload = [
            {"description": "item a", "unit": "m2"},
            {"description": "item b"},
        ]

        response = self.client.post(self.url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(len(data["results"]), 2)
        self.assertEqual(data["results"][1]["status"], "not found")
        self.mock_bulk.assert_called_once_with([
            {"description": "item a", "unit": "m2"},
            {"description": "item b", "unit": None},
        ])
        self.mock_log.assert_called_once_with("item b", None)

    def test_bulk_match_handles_invalid_items(self):
        self.mock_bulk.return_value = [
            {"description": "valid", "unit": "m", "status": "found", "match": {"id": 5}},
        ]

        payload = [
            {"description": "valid", "unit": "m"},
            {"unit": "m2"},
            "oops",
        ]

        response = self.client.post(self.url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(len(data["results"]), 3)
        self.assertEqual(data["results"][0]["status"], "found")
        self.assertEqual(data["results"][1]["status"], "error")
        self.assertEqual(data["results"][2]["status"], "error")
        self.mock_bulk.assert_called_once_with([
            {"description": "valid", "unit": "m"},
        ])

    def test_bulk_match_requires_array_payload(self):
        response = self.client.post(self.url, json.dumps({"description": "x"}), content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())
        self.mock_bulk.assert_not_called()

    def test_bulk_match_invalid_json(self):
        response = self.client.post(self.url, "not-json", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())
        self.mock_bulk.assert_not_called()

    def test_bulk_match_rejects_wrong_content_type(self):
        response = self.client.post(self.url, json.dumps([]), content_type="text/plain")
        self.assertEqual(response.status_code, 415)
        self.assertIn("error", response.json())
        self.mock_bulk.assert_not_called()

    @patch("automatic_job_matching.views.ensure_payload_size", side_effect=SecurityValidationError("too big"))
    def test_bulk_match_payload_too_large(self, _mock_size):
        response = self.client.post(self.url, json.dumps([]), content_type="application/json")
        self.assertEqual(response.status_code, 413)
        self.assertIn("error", response.json())
        self.mock_bulk.assert_not_called()

    def test_bulk_match_handles_missing_bulk_results(self):
        self.mock_bulk.return_value = []
        payload = [{"description": "desc", "unit": "m"}]

        response = self.client.post(self.url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["results"][0]["status"], "error")
