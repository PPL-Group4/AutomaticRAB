from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from target_bid import validators
from target_bid.validators import TargetBudgetInput, validate_target_budget_input


class TargetBudgetValidationTests(SimpleTestCase):
    def test_percentage_accepts_percent_string(self):
        result = validate_target_budget_input("90%", mode="percentage")
        self.assertEqual(result.mode, "percentage")
        self.assertEqual(result.value, Decimal("90"))

    def test_percentage_mode_symbol(self):
        result = validate_target_budget_input("75", mode="%")
        self.assertEqual(result.mode, "percentage")

    def test_percentage_rejects_out_of_range_values(self):
        with self.assertRaises(ValidationError):
            validate_target_budget_input(Decimal("0"), mode="percentage")
        with self.assertRaises(ValidationError):
            validate_target_budget_input("150", mode="percentage")

    def test_percentage_rejects_non_numeric_input(self):
        with self.assertRaises(ValidationError):
            validate_target_budget_input("ninety", mode="percentage")

    def test_absolute_accepts_currency_like_strings(self):
        result = validate_target_budget_input("Rp 1.500.000,75", mode="absolute")
        self.assertEqual(result.value, Decimal("1500000.75"))

    def test_absolute_rejects_zero_or_negative(self):
        with self.assertRaises(ValidationError):
            validate_target_budget_input(0, mode="absolute")

    def test_blank_string_requires_value(self):
        with self.assertRaises(ValidationError):
            validate_target_budget_input("   ", mode="absolute")
