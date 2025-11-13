from django.test import SimpleTestCase

from automatic_job_matching.security import (
    MAX_DESCRIPTION_LENGTH,
    MAX_JSON_PAYLOAD_BYTES,
    MAX_UNIT_LENGTH,
    SecurityValidationError,
    ensure_payload_size,
    is_safe_url,
    sanitize_description,
    sanitize_unit,
)


class SanitizeDescriptionTests(SimpleTestCase):
    def test_valid_description_is_trimmed(self):
        self.assertEqual(sanitize_description("  some text  \n"), "some text")

    def test_missing_description_raises(self):
        with self.assertRaises(SecurityValidationError):
            sanitize_description(None)

    def test_empty_description_raises(self):
        with self.assertRaises(SecurityValidationError):
            sanitize_description("   \t")

    def test_overlong_description_raises(self):
        overlong = "x" * (MAX_DESCRIPTION_LENGTH + 1)
        with self.assertRaises(SecurityValidationError):
            sanitize_description(overlong)


class SanitizeUnitTests(SimpleTestCase):
    def test_none_or_blank_unit_returns_none(self):
        self.assertIsNone(sanitize_unit(None))
        self.assertIsNone(sanitize_unit("   "))

    def test_valid_unit_characters(self):
        self.assertEqual(sanitize_unit(" m3/pcs-01 "), "m3/pcs-01")

    def test_invalid_unit_raises(self):
        with self.assertRaises(SecurityValidationError):
            sanitize_unit("m²")

    def test_unit_too_long_raises(self):
        with self.assertRaises(SecurityValidationError):
            sanitize_unit("a" * (MAX_UNIT_LENGTH + 1))


class PayloadSizeTests(SimpleTestCase):
    def test_payload_within_limit_is_ok(self):
        ensure_payload_size(b"a" * MAX_JSON_PAYLOAD_BYTES)

    def test_payload_over_limit_raises(self):
        with self.assertRaises(SecurityValidationError):
            ensure_payload_size(b"a" * (MAX_JSON_PAYLOAD_BYTES + 1))


class SafeUrlTests(SimpleTestCase):
    def test_empty_or_invalid_urls(self):
        self.assertFalse(is_safe_url(""))
        self.assertFalse(is_safe_url("notaurl"))
        self.assertFalse(is_safe_url("ftp://example.com"))

    def test_domain_urls_are_allowed(self):
        self.assertTrue(is_safe_url("HTTP://Example.com/path"))
        self.assertTrue(is_safe_url("https://example.com:443/resource"))

    def test_public_ip_allows(self):
        self.assertTrue(is_safe_url("http://8.8.8.8"))

    def test_private_or_loopback_blocked(self):
        self.assertFalse(is_safe_url("http://127.0.0.1"))
        self.assertFalse(is_safe_url("http://10.0.0.5"))
        self.assertFalse(is_safe_url("http://0.0.0.0"))

    def test_reserved_ip_blocked(self):
        self.assertFalse(is_safe_url("http://192.0.2.1"))
