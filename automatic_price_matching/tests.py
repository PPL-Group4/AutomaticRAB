import json
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from automatic_job_matching.repository.ahs_repo import DbAhsRepository
from automatic_job_matching.service.exact_matcher import AhsRow
from automatic_price_matching.ahs_cache import AhsCache
from automatic_price_matching.price_retrieval import AhspPriceRetriever, MockAhspSource
from automatic_price_matching.service import AutomaticPriceMatchingService
from automatic_price_matching.total_cost import TotalCostCalculator
from rencanakan_core.models import Ahs


class AhspValidationTests(SimpleTestCase):


	"""Expectations for AHSP payload validation (TDD coverage)."""

	def setUp(self) -> None:
		super().setUp()
		from automatic_price_matching.validators import validate_ahsp_payload  # noqa: WPS433

		self.validate = validate_ahsp_payload

	# --- Input type guards -------------------------------------------------

	def test_rejects_null_payload(self) -> None:
		with self.assertRaisesMessage(ValidationError, "AHSP payload cannot be null"):
			self.validate(None)

	def test_rejects_non_mapping_payload(self) -> None:
		with self.assertRaises(ValidationError) as ctx:
			self.validate(["not", "a", "mapping"])

		self.assertIn("__all__", ctx.exception.message_dict)
		self.assertIn("must be a dictionary", ctx.exception.message_dict["__all__"][0])

	# --- Field level validation -------------------------------------------

	def test_requires_code_field(self) -> None:
		payload = {"name": "Galian Tanah", "unit": "m3", "volume": 1}

		with self.assertRaises(ValidationError) as ctx:
			self.validate(payload)

		self.assertIn("code", ctx.exception.message_dict)

	def test_requires_volume_field(self) -> None:
		payload = {"code": "AT.01.001", "name": "Galian Tanah", "unit": "m3"}

		with self.assertRaises(ValidationError) as ctx:
			self.validate(payload)

		self.assertIn("This field is required.", ctx.exception.message_dict["volume"])

	def test_rejects_blank_code_string(self) -> None:
		payload = {"code": "   ", "name": "Galian", "unit": "m2", "volume": 1}

		with self.assertRaises(ValidationError) as ctx:
			self.validate(payload)

		self.assertIn("This field cannot be blank.", ctx.exception.message_dict["code"])

	def test_rejects_non_string_code(self) -> None:
		payload = {"code": 1234, "name": "Galian Tanah", "unit": "m3", "volume": 1}

		with self.assertRaises(ValidationError) as ctx:
			self.validate(payload)

		self.assertIn("code", ctx.exception.message_dict)

	def test_rejects_code_with_dangerous_characters(self) -> None:
		payload = {"code": "AT.01; DROP TABLE", "name": "Galian Tanah", "unit": "m3", "volume": 1}

		with self.assertRaises(ValidationError) as ctx:
			self.validate(payload)

		self.assertIn("code", ctx.exception.message_dict)

	def test_rejects_invalid_numeric_volume(self) -> None:
		payload = {"code": "AT.01.001", "name": "Galian Tanah", "unit": "m3", "volume": "many"}

		with self.assertRaises(ValidationError) as ctx:
			self.validate(payload)

		self.assertIn("volume", ctx.exception.message_dict)

	def test_rejects_expression_in_unit_price(self) -> None:
		payload = {
			"code": "AT.01.001",
			"name": "Galian Tanah",
			"unit": "m3",
			"volume": 1,
			"unit_price": "3 x 4",
		}

		with self.assertRaises(ValidationError) as ctx:
			self.validate(payload)

		self.assertIn("must be numeric", ctx.exception.message_dict["unit_price"][0])

	def test_rejects_non_numeric_object_unit_price(self) -> None:
		payload = {
			"code": "AT.01.001",
			"name": "Galian Tanah",
			"unit": "m3",
			"volume": 1,
			"unit_price": {"value": 10},
		}

		with self.assertRaises(ValidationError) as ctx:
			self.validate(payload)

		self.assertIn("must be numeric", ctx.exception.message_dict["unit_price"][0])

	# --- Component validation ---------------------------------------------

	def test_components_must_be_list(self) -> None:
		payload = {
			"code": "AT.01.001",
			"name": "Galian Tanah",
			"unit": "m3",
			"volume": 1,
			"components": "oops",
		}

		with self.assertRaises(ValidationError) as ctx:
			self.validate(payload)

		self.assertIn("Must be a list", ctx.exception.message_dict["components"][0])

	def test_component_must_be_mapping(self) -> None:
		payload = {
			"code": "AT.01.001",
			"name": "Galian Tanah",
			"unit": "m3",
			"volume": 1,
			"components": ["invalid"],
		}

		with self.assertRaises(ValidationError) as ctx:
			self.validate(payload)

		messages = ctx.exception.message_dict["components"]
		self.assertTrue(any("must be an object" in msg for msg in messages))

	def test_detects_component_missing_code(self) -> None:
		payload = {
			"code": "AT.01.001",
			"name": "Galian Tanah",
			"unit": "m3",
			"volume": 1,
			"components": [
				{"name": "Tenaga kerja", "type": "labor", "coefficient": 0.5},
			],
		}

		with self.assertRaises(ValidationError) as ctx:
			self.validate(payload)

		messages = ctx.exception.message_dict.get("components", [])
		self.assertTrue(any("index 0" in message for message in messages))

	def test_components_empty_string_normalised_to_list(self) -> None:
		payload = {
			"code": "AT.01.001",
			"name": "Galian Tanah",
			"unit": "m3",
			"volume": 1,
			"components": "",
		}

		cleaned = self.validate(payload)

		self.assertEqual(cleaned["components"], [])

	def test_component_coefficient_variants(self) -> None:
		payload = {
			"code": "AT.01.001",
			"name": "Galian Tanah",
			"unit": "m3",
			"volume": 1,
			"components": [
				{"code": "M001", "coefficient": "1.234,56"},
				{"code": "M002", "coefficient": "1,234.56"},
				{"code": "M003", "coefficient": "1.234567,89"},
				{"code": "M004", "coefficient": Decimal("0.25")},
				{"code": "M005", "coefficient": ""},
			],
		}

		cleaned = self.validate(payload)

		coeffs = [component["coefficient"] for component in cleaned["components"]]
		self.assertEqual(coeffs[0], Decimal("1234.56"))
		self.assertEqual(coeffs[1], Decimal("1234.56"))
		self.assertEqual(coeffs[2], Decimal("1234567.89"))
		self.assertEqual(coeffs[3], Decimal("0.25"))
		self.assertEqual(coeffs[4], Decimal("0"))

	def test_component_coefficient_invalid_reports_context(self) -> None:
		payload = {
			"code": "AT.01.001",
			"name": "Galian Tanah",
			"unit": "m3",
			"volume": 1,
			"components": [
				{"code": "M001", "coefficient": "1.234,567.89"},
			],
		}

		with self.assertRaises(ValidationError) as ctx:
			self.validate(payload)

		messages = ctx.exception.message_dict["components"]
		self.assertTrue(any("Component at index 0 coefficient" in msg for msg in messages))

	# --- Successful scenarios ---------------------------------------------

	def test_returns_clean_payload_on_success(self) -> None:
		payload = {
			"code": " AT.01.001 ",
			"name": "  Galian Tanah Biasa ",
			"unit": " m3 ",
			"volume": "1,5",
			"unit_price": "250000.00",
			"components": [
				{"code": "M001", "name": "Semen", "type": "material", "coefficient": "0.75"},
			],
		}

		cleaned = self.validate(payload)

		self.assertEqual(cleaned["code"], "AT.01.001")
		self.assertEqual(cleaned["name"], "Galian Tanah Biasa")
		self.assertEqual(cleaned["unit"], "m3")
		self.assertIsInstance(cleaned["volume"], Decimal)
		self.assertEqual(cleaned["volume"], Decimal("1.5"))
		self.assertEqual(cleaned["unit_price"], Decimal("250000.00"))
		self.assertEqual(cleaned["total_cost"], Decimal("375000.00"))
		self.assertEqual(cleaned["components"][0]["coefficient"], Decimal("0.75"))

	def test_accepts_decimal_inputs(self) -> None:
		payload = {
			"code": "AT.02.002",
			"name": "Galian Tanah",
			"unit": "m3",
			"volume": Decimal("2.5"),
			"unit_price": Decimal("123.45"),
		}

		cleaned = self.validate(payload)

		self.assertEqual(cleaned["volume"], Decimal("2.5"))
		self.assertEqual(cleaned["unit_price"], Decimal("123.45"))
		self.assertEqual(cleaned["total_cost"], Decimal("308.63"))

	def test_total_cost_rounding(self) -> None:
		payload = {
			"code": "AT.03.003",
			"name": "Beton",
			"unit": "m3",
			"volume": Decimal("2.333"),
			"unit_price": Decimal("123.456"),
		}

		cleaned = self.validate(payload)
		self.assertEqual(cleaned["total_cost"], Decimal("288.02"))

	def test_total_cost_none_when_unit_price_missing(self) -> None:
		payload = {
			"code": "AT.04.004",
			"name": "Tanah",
			"unit": "m3",
			"volume": Decimal("5"),
		}

		cleaned = self.validate(payload)
		self.assertIsNone(cleaned["unit_price"])
		self.assertIsNone(cleaned["total_cost"])

	def test_total_cost_none_when_volume_missing(self) -> None:
		payload = {
			"code": "AT.05.005",
			"name": "Pasir",
			"unit": "m3",
			"volume": None,
			"unit_price": Decimal("111.11"),
		}

		cleaned = self.validate(payload)
		self.assertIsNone(cleaned["volume"])
		self.assertIsNone(cleaned["total_cost"])


class RecomputePayloadValidationTests(SimpleTestCase):
	def setUp(self) -> None:
		super().setUp()
		from automatic_price_matching.validators import validate_recompute_payload  # noqa: WPS433

		self.validate = validate_recompute_payload

	def test_accepts_valid_payload(self) -> None:
		payload = {
			"row_key": "row-001",
			"code": "at-01/001",
			"analysis_code": "AT.01.001",
			"volume": "2.50",
			"unit_price": "1000",
		}
		cleaned = self.validate(payload)
		self.assertEqual(cleaned["row_key"], "row-001")
		self.assertEqual(cleaned["code"], "AT.01.001")
		self.assertEqual(cleaned["analysis_code"], "AT.01.001")
		self.assertEqual(cleaned["volume"], Decimal("2.50"))
		self.assertEqual(cleaned["unit_price"], Decimal("1000"))

	def test_invalid_row_key_rejected(self) -> None:
		with self.assertRaises(ValidationError) as ctx:
			self.validate({"row_key": "bad<script>", "volume": 1})
		self.assertIn("row_key", ctx.exception.message_dict)

	def test_negative_numbers_disallowed(self) -> None:
		with self.assertRaises(ValidationError) as ctx:
			self.validate({"volume": -1, "unit_price": 2})
		self.assertIn("volume", ctx.exception.message_dict)

	def test_analysis_code_defaults_to_code(self) -> None:
		cleaned = self.validate({"code": "AB 01", "volume": 1})
		self.assertEqual(cleaned["analysis_code"], "AB.01")

	def test_rejects_injection_in_code(self) -> None:
		with self.assertRaises(ValidationError) as ctx:
			self.validate({"code": "1; DROP TABLE", "volume": 1})
		self.assertIn("code", ctx.exception.message_dict)


class TotalCostCalculatorTests(SimpleTestCase):
	def test_calculates_when_both_decimals(self) -> None:
		result = TotalCostCalculator.calculate(Decimal("10"), Decimal("3.333"))
		self.assertEqual(result, Decimal("33.33"))

	def test_returns_none_when_missing_inputs(self) -> None:
		self.assertIsNone(TotalCostCalculator.calculate(None, Decimal("5")))
		self.assertIsNone(TotalCostCalculator.calculate(Decimal("5"), None))

	def test_rounds_half_up(self) -> None:
		result = TotalCostCalculator.calculate(Decimal("1.005"), Decimal("1"))
		self.assertEqual(result, Decimal("1.01"))

	def test_handles_negative_values(self) -> None:
		result = TotalCostCalculator.calculate(Decimal("-2"), Decimal("3.5"))
		self.assertEqual(result, Decimal("-7.00"))

	def test_returns_none_for_non_decimal_inputs(self) -> None:
		self.assertIsNone(TotalCostCalculator.calculate(Decimal("2"), 3))
		self.assertIsNone(TotalCostCalculator.calculate("2", Decimal("3")))
class FallbackValidatorTests(SimpleTestCase):
    """Expectations for fallback behaviour when AHSP match is not found."""

    def setUp(self) -> None:
        super().setUp()
        from automatic_price_matching.fallback_validator import apply_fallback
        self.apply_fallback = apply_fallback

    # --- Input type guards -------------------------------------------------

    def test_rejects_null_description(self) -> None:
        """Fallback should still handle None gracefully."""
        result = self.apply_fallback(None)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["uraian"], None)
        self.assertIsNone(result["unit_price"])
        self.assertEqual(result["total_price"], Decimal("0"))
        self.assertEqual(result["match_status"], "Needs Manual Input")

    def test_accepts_string_description(self) -> None:
        """Fallback must accept a valid string description."""
        desc = "Pekerjaan Pondasi Beton"
        result = self.apply_fallback(desc)

        self.assertIsInstance(result, dict)
        self.assertEqual(result["uraian"], desc)
        self.assertIsNone(result["unit_price"])
        self.assertEqual(result["total_price"], Decimal("0"))
        self.assertEqual(result["match_status"], "Needs Manual Input")
        self.assertTrue(result["is_editable"])

    # --- Field value validation --------------------------------------------

    def test_total_price_is_decimal_zero(self) -> None:
        """The fallback must always set total_price as Decimal('0')."""
        result = self.apply_fallback("Any Job Description")
        self.assertIsInstance(result["total_price"], Decimal)
        self.assertEqual(result["total_price"], Decimal("0"))

    def test_unit_price_is_none(self) -> None:
        """The fallback must indicate missing price explicitly as None."""
        result = self.apply_fallback("Any Job")
        self.assertIsNone(result["unit_price"])

    def test_status_is_needs_manual_input(self) -> None:
        """The match_status field must correctly flag 'Needs Manual Input'."""
        result = self.apply_fallback("Pekerjaan Cat Dinding")
        self.assertEqual(result["match_status"], "Needs Manual Input")

    def test_editable_flag_true(self) -> None:
        """The fallback entry must always be editable for manual override."""
        result = self.apply_fallback("Pekerjaan Plumbing")
        self.assertTrue(result["is_editable"])

    # --- Negative path: malformed / unexpected inputs ----------------------

    def test_handles_non_string_input_safely(self) -> None:
        """Fallback should not raise for numeric or dict inputs."""
        weird_inputs = [123, {"desc": "Weird"}, ["array"], True]

        for candidate in weird_inputs:
            with self.subTest(candidate=candidate):
                result = self.apply_fallback(candidate)
                # It must still return a valid fallback dict
                self.assertIn("uraian", result)
                self.assertIsNone(result["unit_price"])
                self.assertEqual(result["total_price"], Decimal("0"))
                self.assertEqual(result["match_status"], "Needs Manual Input")
                self.assertTrue(result["is_editable"])

    # --- Positive scenario: confirm integration contract ------------------

    def test_integration_contract_shape(self) -> None:
        """Ensure the fallback dict shape matches downstream expectations."""
        desc = "Pekerjaan Beton Bertulang"
        result = self.apply_fallback(desc)

        expected_keys = {
            "uraian",
            "unit_price",
            "total_price",
            "match_status",
            "is_editable",
        }

        self.assertEqual(set(result.keys()), expected_keys)
        self.assertEqual(result["uraian"], desc)
        self.assertIsNone(result["unit_price"])
        self.assertEqual(result["total_price"], Decimal("0"))
        self.assertEqual(result["match_status"], "Needs Manual Input")
        self.assertTrue(result["is_editable"])


class AhsCacheTests(SimpleTestCase):
    """Expectations for AHSP in-memory caching behavior (unit-level)."""

    def setUp(self):
        self.cache = AhsCache()
        self.sample_rows = [AhsRow(id=1, code="AT.01.001", name="Galian Tanah")]

    # ✅ NEGATIVE test: triggers DB lookup when cache miss
    def test_cache_miss_triggers_db_lookup(self):
        repo = DbAhsRepository()

        with patch("rencanakan_core.models.Ahs.objects.filter") as mock_filter:
            mock_filter.return_value = Ahs.objects.none()

            # Nothing cached yet → must hit DB
            repo.by_code_like("NON_EXISTENT_CODE")
            self.assertGreater(mock_filter.call_count, 0)

    # ✅ POSITIVE tests
    def test_cache_stores_and_retrieves_by_code(self):
        self.cache.set_by_code("AT.01.001", self.sample_rows)
        cached = self.cache.get_by_code("AT.01.001")
        self.assertEqual(cached, self.sample_rows)

    def test_cache_miss_returns_none(self):
        self.assertIsNone(self.cache.get_by_code("unknown"))

    def test_cache_stores_by_name_token(self):
        self.cache.set_by_name("galian", self.sample_rows)
        cached = self.cache.get_by_name("galian")
        self.assertEqual(cached[0].name, "Galian Tanah")

    def test_cache_stores_full_list(self):
        self.cache.set_all(self.sample_rows)
        cached_all = self.cache.get_all()
        self.assertEqual(len(cached_all), 1)

    # ✅ EDGE CASES
    def test_cache_handles_empty_or_none_key(self):
        """Edge case: Ensure cache handles empty or None keys gracefully."""
        # Empty key should still store and retrieve fine
        self.cache.set_by_code("", self.sample_rows)
        cached_empty = self.cache.get_by_code("")
        self.assertEqual(cached_empty, self.sample_rows)

        # None key → should return None, not crash
        cached_none = self.cache.get_by_code(None)
        self.assertIsNone(cached_none)


class AhsRepositoryCacheIntegrationTests(SimpleTestCase):
    """Integration-level verification for repository caching."""

    def test_uses_cache_after_first_call(self):
        repo = DbAhsRepository()

        with patch("rencanakan_core.models.Ahs.objects.filter") as mock_filter:
            mock_filter.return_value = Ahs.objects.none()

            # First run → will hit DB once per variant (expected)
            repo.by_code_like("AT.01.001")
            first_call_count = mock_filter.call_count

            # Second run → should not call DB at all (cache hit)
            repo.by_code_like("AT.01.001")
            second_call_count = mock_filter.call_count

            # ✅ Assert total calls unchanged → cache prevents new lookups
            self.assertEqual(first_call_count, second_call_count)
SQLITE_DB_SETTINGS = {
	"default": {
		"ENGINE": "django.db.backends.sqlite3",
		"NAME": ":memory:",
	}
}


@override_settings(DATABASES=SQLITE_DB_SETTINGS)
class RecomputeTotalCostTDDTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("recompute_total_cost")

    # ---------- RED TEST CASES ----------
    def test_invalid_input_should_fail(self):
        """🔴 Should return error when given invalid input."""
        payload = {"volume": "abc", "unit_price": "xyz"}
        response = self.client.post(self.url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_invalid_row_key_returns_error(self):
        payload = {"row_key": "bad<script>", "volume": 1, "unit_price": 1}
        response = self.client.post(self.url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.json())
        self.assertIn("row_key", response.json()["detail"])

    def test_invalid_code_characters_rejected(self):
        payload = {"code": "1; DROP TABLE", "volume": 1, "unit_price": 1}
        response = self.client.post(self.url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("code", response.json().get("detail", {}))

    def test_missing_fields_should_default_to_zero(self):
        """🔴 Should still work when one field is missing."""
        payload = {"volume": 3.5}
        response = self.client.post(self.url, json.dumps(payload), content_type="application/json")
        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Decimal(data["total_cost"]), Decimal("0"))

    def test_malformed_json_returns_error(self):
        """🔴 Should safely handle malformed JSON input."""
        response = self.client.post(self.url, "not-a-json", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    # ---------- GREEN TEST CASES ----------
    def test_valid_computation_matches_calculator(self):
        """🟢 Should compute correct total using TotalCostCalculator."""
        payload = {"volume": "2.5", "unit_price": "1500000"}
        response = self.client.post(self.url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        expected = TotalCostCalculator.calculate(Decimal("2.5"), Decimal("1500000"))
        self.assertEqual(Decimal(data["total_cost"]), expected)

    def test_zero_values_returns_zero(self):
        """🟢 Should return 0 total when volume or price is zero."""
        for case in [{"volume": 0, "unit_price": 1000}, {"volume": 2, "unit_price": 0}]:
            response = self.client.post(self.url, json.dumps(case), content_type="application/json")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(Decimal(data["total_cost"]), Decimal("0"))

    def test_persists_override_when_row_key_supplied(self):
        payload = {
            "row_key": "row-001",
            "code": "AT.01.001",
            "analysis_code": "AT.01.001",
            "volume": "2.50",
            "unit_price": "1000",
        }
        response = self.client.post(self.url, json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 200)

        session = self.client.session
        overrides = session.get("rab_overrides")
        self.assertIsNotNone(overrides)
        stored = overrides.get("row-001")
        self.assertIsNotNone(stored)
        self.assertEqual(stored.get("unit_price"), "1000.00")
        self.assertEqual(stored.get("total_price"), "2500.00")
        self.assertEqual(stored.get("volume"), "2.50")


def test_auto_fill_unit_price_after_matching(self):
    svc = AutomaticPriceMatchingService(
        price_retriever=AhspPriceRetriever(MockAhspSource({"AB.01": Decimal("1000")}))
    )
    result = svc.match_one({"code": "AB.01", "volume": Decimal("2")})
    assert result["unit_price"] == Decimal("1000")
    assert result["total_cost"] == Decimal("2000.00")
    assert result["match_status"] == "Matched"


def test_user_override_recalculates_total(self):
    svc = AutomaticPriceMatchingService(
        price_retriever=AhspPriceRetriever(MockAhspSource({"AB.01": Decimal("1000")}))
    )

    # User overrides matched price (was 1000)
    result = svc.match_one({"code": "AB.01", "volume": Decimal("3"), "unit_price": Decimal("1200")})
    assert result["unit_price"] == Decimal("1200")
    assert result["total_cost"] == Decimal("3600.00")
    assert result["match_status"] == "Overridden"
    assert result["is_editable"] is True

def test_user_provided_price_without_match(self):
    svc = AutomaticPriceMatchingService()
    result = svc.match_one({"code": "XX.99", "volume": Decimal("5"), "unit_price": Decimal("1500")})
    assert result["total_cost"] == Decimal("7500.00")
    assert result["match_status"] == "Provided"

def test_override_ignores_old_matched_price(self):
    svc = AutomaticPriceMatchingService(
        price_retriever=AhspPriceRetriever(MockAhspSource({"AB.01": Decimal("1000")}))
    )
    svc.cache.set_by_code("AB.01", Decimal("1000"))
    result = svc.match_one({"code": "AB.01", "volume": Decimal("2"), "unit_price": Decimal("1500")})
    assert result["total_cost"] == Decimal("3000.00")
    assert result["match_status"] == "Overridden"

def test_invalid_unit_price_gracefully_handled(self):
    svc = AutomaticPriceMatchingService()

    result = svc.match_one({"code": "AB.01", "volume": Decimal("3"), "unit_price": "invalid"})
    # Expect fallback because unit_price isn't valid Decimal
    assert result["total_cost"] == Decimal("0")
    assert result["match_status"] in ("Needs Manual Input", "Provided", "Overridden")

def test_missing_volume_and_price_triggers_fallback(self):
    svc = AutomaticPriceMatchingService()
    result = svc.match_one({"code": "AB.01"})
    assert result["unit_price"] is None
    assert result["total_cost"] == Decimal("0")
    assert result["match_status"] == "Needs Manual Input"
