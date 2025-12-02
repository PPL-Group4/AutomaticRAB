from django.test import TestCase, Client
from django.urls import reverse
import json

class RecomputeCostSecurityTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("recompute_total_cost")  # use your URL name

    def test_new_request_generates_row_key(self):
        payload = {
            "code": "A.1.1.4",
            "volume": 1.5
        }

        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # row_key must exist
        self.assertIn("row_key", data)

        # row_key must be hex and length 32 (token_hex(16))
        self.assertEqual(len(data["row_key"]), 32)
        int(data["row_key"], 16)  # will raise if not hex

    def test_reject_invalid_row_key(self):
            payload = {
                "code": "A.1.1.4",
                "volume": 2,
                "row_key": "FAKEKEY123"  # attacker-supplied
            }

            response = self.client.post(
                self.url,
                data=json.dumps(payload),
                content_type="application/json"
            )

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()["error"], "invalid_row_key")

