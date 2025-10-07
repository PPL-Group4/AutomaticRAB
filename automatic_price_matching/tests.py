from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase


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
