from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
import pytest
from target_bid import validators
from target_bid.services.services import TargetBudgetConverter
from target_bid.validators import TargetBudgetInput, validate_target_budget_input


class TargetBudgetValidationTests(SimpleTestCase):
	def test_percentage_accepts_percent_string(self) -> None:
		result = validate_target_budget_input("90%", mode="percentage")

		self.assertIsInstance(result, TargetBudgetInput)
		self.assertEqual(result.mode, "percentage")
		self.assertEqual(result.value, Decimal("90"))

	def test_percentage_mode_symbol(self) -> None:
		result = validate_target_budget_input("75", mode="%")

		self.assertEqual(result.mode, "percentage")
		self.assertEqual(result.value, Decimal("75"))

	def test_percentage_rejects_out_of_range_values(self) -> None:
		with self.assertRaises(ValidationError) as exc:
			validate_target_budget_input(Decimal("0"), mode="percentage")

		self.assertIn("target_budget", exc.exception.message_dict)
		self.assertEqual(
			exc.exception.message_dict["target_budget"],
			["Percentage value must be between 0 and 100."],
		)

		with self.assertRaises(ValidationError) as exc:
			validate_target_budget_input("150", mode="percentage")

		self.assertIn("target_budget", exc.exception.message_dict)
		self.assertEqual(
			exc.exception.message_dict["target_budget"],
			["Percentage value must be between 0 and 100."],
		)

	def test_percentage_rejects_non_numeric_input(self) -> None:
		with self.assertRaises(ValidationError) as exc:
			validate_target_budget_input("ninety", mode="percentage")

		self.assertIn("target_budget", exc.exception.message_dict)
		self.assertEqual(
			exc.exception.message_dict["target_budget"],
			["Target budget must be a numeric value."],
		)

	def test_percentage_rejects_malformed_numeric(self) -> None:
		with self.assertRaises(ValidationError) as exc:
			validate_target_budget_input("--10%", mode="percentage")

		self.assertEqual(
			exc.exception.message_dict["target_budget"],
			["Target budget must be a numeric value."],
		)

	def test_absolute_accepts_currency_like_strings(self) -> None:
		result = validate_target_budget_input("Rp 1.500.000,75", mode="absolute")

		self.assertEqual(result.mode, "absolute")
		self.assertEqual(result.value, Decimal("1500000.75"))

	def test_absolute_accepts_decimal_comma(self) -> None:
		result = validate_target_budget_input("1,5", mode="absolute")

		self.assertEqual(result.value, Decimal("1.5"))

	def test_absolute_handles_mixed_separators(self) -> None:
		result = validate_target_budget_input("1234.5,67", mode="absolute")

		self.assertEqual(result.value, Decimal("12345.67"))

	def test_absolute_handles_dot_after_comma(self) -> None:
		result = validate_target_budget_input("1,23.45", mode="absolute")

		self.assertEqual(result.value, Decimal("123.45"))

	def test_absolute_handles_comma_before_decimal(self) -> None:
		result = validate_target_budget_input("12,34.56", mode="absolute")

		self.assertEqual(result.value, Decimal("1234.56"))

	def test_absolute_handles_thousand_commas(self) -> None:
		result = validate_target_budget_input("1,234.56", mode="absolute")

		self.assertEqual(result.value, Decimal("1234.56"))

	def test_normalise_numeric_string_removes_comma(self) -> None:
		self.assertEqual(
			validators._normalise_numeric_string("1,23.45"),
			"123.45",
		)

	def test_normalise_mode_returns_canonical_name(self) -> None:
		self.assertEqual(validators._normalise_mode("Percent"), "percentage")

	def test_normalise_mode_returns_none_for_invalid(self) -> None:
		self.assertIsNone(validators._normalise_mode(123))
		self.assertIsNone(validators._normalise_mode("custom"))

	def test_absolute_strips_currency_and_underscores(self) -> None:
		result = validate_target_budget_input("IDR 1_000", mode="absolute")

		self.assertEqual(result.value, Decimal("1000"))

	def test_absolute_rejects_percent_symbol(self) -> None:
		with self.assertRaises(ValidationError) as exc:
			validate_target_budget_input("90%", mode="absolute")

		self.assertIn("target_budget", exc.exception.message_dict)
		self.assertEqual(
			exc.exception.message_dict["target_budget"],
			["Percentage input is not allowed when mode is absolute."],
		)

	def test_absolute_rejects_zero_or_negative(self) -> None:
		with self.assertRaises(ValidationError) as exc:
			validate_target_budget_input(0, mode="absolute")

		self.assertEqual(
			exc.exception.message_dict["target_budget"],
			["Target budget must be greater than zero."],
		)

		with self.assertRaises(ValidationError) as exc:
			validate_target_budget_input("-1000", mode="absolute")

		self.assertEqual(
			exc.exception.message_dict["target_budget"],
			["Target budget must be greater than zero."],
		)

	def test_missing_value_raises_error(self) -> None:
		with self.assertRaises(ValidationError) as exc:
			validate_target_budget_input(None, mode="absolute")

		self.assertEqual(
			exc.exception.message_dict["target_budget"],
			["Target budget is required."],
		)

	def test_invalid_mode_rejected(self) -> None:
		with self.assertRaises(ValidationError) as exc:
			validate_target_budget_input("90", mode="invalid")

		self.assertIn("mode", exc.exception.message_dict)
		self.assertEqual(
			exc.exception.message_dict["mode"],
			["Mode must be either 'percentage' or 'absolute'."],
		)

	def test_non_string_mode_rejected(self) -> None:
		with self.assertRaises(ValidationError) as exc:
			validate_target_budget_input("90%", mode=None)

		self.assertIn("mode", exc.exception.message_dict)
		self.assertEqual(
			exc.exception.message_dict["mode"],
			["Mode must be either 'percentage' or 'absolute'."],
		)
		self.assertEqual(
			exc.exception.message_dict["target_budget"],
			["Percentage input is not allowed when mode is absolute."],
		)

	def test_absolute_rejects_non_numeric_type(self) -> None:
		with self.assertRaises(ValidationError) as exc:
			validate_target_budget_input([], mode="absolute")

		self.assertEqual(
			exc.exception.message_dict["target_budget"],
			["Target budget must be a numeric value."],
		)

	def test_blank_string_requires_value(self) -> None:
		with self.assertRaises(ValidationError) as exc:
			validate_target_budget_input("   ", mode="absolute")

		self.assertEqual(
			exc.exception.message_dict["target_budget"],
			["Target budget is required."],
		)

def test_percentage_to_nominal_conversion():
    current_total = Decimal("1000000")
    input_data = TargetBudgetInput(mode="percentage", value=Decimal("75"))
    result = TargetBudgetConverter.to_nominal(input_data, current_total)
    assert result == Decimal("750000.00")


def test_absolute_mode_returns_same_value():
    current_total = Decimal("1000000")
    input_data = TargetBudgetInput(mode="absolute", value=Decimal("800000"))
    result = TargetBudgetConverter.to_nominal(input_data, current_total)
    assert result == Decimal("800000.00")


def test_invalid_current_total_type_raises():
    input_data = TargetBudgetInput(mode="percentage", value=Decimal("50"))
    try:
        TargetBudgetConverter.to_nominal(input_data, "1000000")
    except TypeError as e:
        assert "current_total" in str(e)
    else:
        pytest.fail("TypeError expected but not raised")

def test_zero_percent_returns_zero():
    current_total = Decimal("1000000")
    input_data = TargetBudgetInput(mode="percentage", value=Decimal("0"))
    result = TargetBudgetConverter.to_nominal(input_data, current_total)
    assert result == Decimal("0.00")


def test_hundred_percent_returns_same_total():
    current_total = Decimal("1000000")
    input_data = TargetBudgetInput(mode="percentage", value=Decimal("100"))
    result = TargetBudgetConverter.to_nominal(input_data, current_total)
    assert result == Decimal("1000000.00")
