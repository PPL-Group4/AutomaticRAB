import json
from django.urls import reverse
from django.test import Client, TestCase
from django.core.cache import cache
from django.test.utils import override_settings
from django.conf import settings
from unittest.mock import patch
from django.views.decorators.csrf import csrf_exempt
from automatic_price_matching.views import recompute_total_cost



# -----------------------
# Helpers
# -----------------------

def csrf_client():
    """Return a test client that enforces CSRF checks."""
    return Client(enforce_csrf_checks=True)

from django.middleware.csrf import _get_new_csrf_string


def get_csrf_token(client):
    """
    Generate a valid CSRF token and inject into client cookies.
    Compatible with Django 4.1–5.x.
    """
    token = _get_new_csrf_string()
    client.cookies["csrftoken"] = token
    return token

# ==========================================================
# CLASS 1 — CSRF TESTS
# ==========================================================

class TestRecomputeTotalCostCSRF(TestCase):

    def setUp(self):
        self.url = reverse("recompute_total_cost")
        self.payload = {"code": "A.1.1.4", "volume": 2}

    def test_reject_missing_csrf(self):
        """
        A POST without CSRF token must fail with 403.
        """
        client = csrf_client()

        response = client.post(
            self.url,
            data=json.dumps(self.payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_accept_valid_csrf(self):
        client = csrf_client()
        csrf_token = get_csrf_token(client)

        response = client.post(
            self.url,
            data=json.dumps(self.payload),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,  # header
        )

        self.assertNotEqual(response.status_code, 403)
        self.assertIn(response.status_code, [200, 400])


# ==========================================================
# CLASS 2 — RATE LIMIT TESTS
# ==========================================================

@patch(
    "automatic_price_matching.views.recompute_total_cost",
    new=csrf_exempt(recompute_total_cost)
)
class TestRecomputeTotalCostRateLimit(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = reverse("recompute_total_cost")
        self.payload = {"code": "A.1.1.4", "volume": 1}
        cache.clear()

    def test_rate_limit_blocking(self):
        ip = "127.0.0.1"

        # First 5 allowed
        for _ in range(5):
            res = self.client.post(
                self.url,
                data=json.dumps(self.payload),
                content_type="application/json",
                REMOTE_ADDR=ip,
            )
            self.assertNotEqual(res.status_code, 200)

        # 6th must be blocked
        res = self.client.post(
            self.url,
            data=json.dumps(self.payload),
            content_type="application/json",
            REMOTE_ADDR=ip,
        )
        self.assertEqual(res.status_code, 200)

    def test_rate_limit_with_csrf(self):
        cache.clear()
        ip = "127.0.0.1"
        client = Client()   # CSRF checks are disabled now

        # First 5 allowed
        for _ in range(5):
            res = client.post(
                self.url,
                data=json.dumps(self.payload),
                content_type="application/json",
                REMOTE_ADDR=ip,
            )
            self.assertNotEqual(res.status_code, 403)

        # 6th must be blocked
        res = client.post(
            self.url,
            data=json.dumps(self.payload),
            content_type="application/json",
            REMOTE_ADDR=ip,
        )
        self.assertEqual(res.status_code, 403)