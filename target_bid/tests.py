from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory
from django.test import TestCase
import pytest
from target_bid import validators
from target_bid.service_utils.budgetservice import TargetBudgetConverter
from target_bid.service_utils.proportional_adjustment import ProportionalAdjustmentCalculator
from target_bid.validators import TargetBudgetInput, validate_target_budget_input
from target_bid.services import (
	RabJobItem,
	RabJobItemMapper,
	RabJobItemService,
	_default_queryset,
	_decimal_to_string,
	_is_non_adjustable,
	_is_non_adjustable_by_name,
	_multiply_decimal,
	_normalise_item_name,
	_to_decimal,
	fetch_rab_job_items,
	LockedItemRule,
	NonAdjustableEvaluator
)
from target_bid.views import fetch_rab_job_items_view


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


class RabJobItemHelperTests(SimpleTestCase):
	def test_rab_job_item_to_dict_serialises_numbers(self) -> None:
		item = RabJobItem(
			rab_item_id=10,
			name="Item",
			unit_name="m",
			unit_price=Decimal("12.3400"),
			volume=Decimal("2.000"),
			total_price=Decimal("24.6800"),
			rab_item_header_id=2,
			rab_item_header_name="Header",
			custom_ahs_id=None,
			analysis_code="AT.01",
		)

		self.assertEqual(
			item.to_dict(),
			{
				"id": 10,
				"name": "Item",
				"unit": "m",
				"unit_price": "12.34",
				"volume": "2",
				"total_price": "24.68",
				"rab_item_header_id": 2,
				"rab_item_header_name": "Header",
				"custom_ahs_id": None,
				"analysis_code": "AT.01",
				"is_locked": None,
			},
		)

	def test_normalise_item_name_strips_noise(self) -> None:
		self.assertEqual(
			_normalise_item_name("III. Alat Pelindung Diri (APD)"),
			"alat pelindung diri apd",
		)
		self.assertEqual(_normalise_item_name(None), "")

	def test_is_non_adjustable_by_name_matches_lookup(self) -> None:
		self.assertTrue(_is_non_adjustable_by_name("Alat Pelindung Kerja (APK)"))
		self.assertFalse(_is_non_adjustable_by_name("Pekerjaan Tanah"))

	def test_is_non_adjustable_checks_priority_rules(self) -> None:
		safety = RabJobItem(
			rab_item_id=1,
			name="Alat Pelindung Kerja (APK)",
			unit_name=None,
			unit_price=None,
			volume=None,
			total_price=None,
			rab_item_header_id=None,
			rab_item_header_name=None,
			custom_ahs_id=None,
			analysis_code=None,
		)
		coded = RabJobItem(
			rab_item_id=2,
			name="Mobilisasi",
			unit_name=None,
			unit_price=None,
			volume=None,
			total_price=None,
			rab_item_header_id=None,
			rab_item_header_name=None,
			custom_ahs_id=None,
			analysis_code="AT.10",
		)
		custom = RabJobItem(
			rab_item_id=3,
			name="Mobilisasi",
			unit_name=None,
			unit_price=None,
			volume=None,
			total_price=None,
			rab_item_header_id=None,
			rab_item_header_name=None,
			custom_ahs_id=5,
			analysis_code="AT.10",
		)

		self.assertTrue(_is_non_adjustable(safety))
		self.assertTrue(_is_non_adjustable(coded))
		self.assertFalse(_is_non_adjustable(custom))

	def test_helper_functions_cover_edge_cases(self) -> None:
		value = _to_decimal(Decimal("1.23"))
		self.assertEqual(value, Decimal("1.23"))
		self.assertIsNone(_to_decimal(object()))
		self.assertIsNone(_to_decimal("not-a-number"))
		self.assertIsNone(_multiply_decimal(None, Decimal("2")))
		self.assertEqual(_multiply_decimal(Decimal("2"), Decimal("3")), Decimal("6"))
		self.assertEqual(_decimal_to_string(Decimal("10.500")), "10.5")
		self.assertEqual(_decimal_to_string(Decimal("0")), "0")
		self.assertIsNone(_decimal_to_string(None))


class FetchRabJobItemsTests(SimpleTestCase):
	def test_fetch_rab_job_items_normalises_values(self) -> None:
		unit = SimpleNamespace(name="m2")
		header = SimpleNamespace(id=7, name="Pekerjaan Tanah")
		row = SimpleNamespace(
			id=1,
			name="Galian Tanah",
			unit=unit,
			price=5000,
			volume=2,
			rab_item_header=header,
			custom_ahs_id=42,
			analysis_code=" AT.01 ",
		)

		items = fetch_rab_job_items(10, queryset=[row])
		self.assertEqual(len(items), 1)
		item = items[0]
		self.assertEqual(item.unit_name, "m2")
		self.assertEqual(item.rab_item_header_id, 7)
		self.assertEqual(item.custom_ahs_id, 42)
		self.assertEqual(item.unit_price, Decimal("5000"))
		self.assertEqual(item.total_price, Decimal("10000"))
		self.assertEqual(item.analysis_code, "AT.01")

	def test_fetch_rab_job_items_handles_missing_numeric(self) -> None:
		row = SimpleNamespace(
			id=2,
			name="Mobilisasi",
			price=None,
			volume=None,
			unit=None,
			rab_item_header=None,
			custom_ahs_id=None,
			analysis_code="",
		)
		items = fetch_rab_job_items(11, queryset=[row])
		item = items[0]
		self.assertIsNone(item.unit_price)
		self.assertIsNone(item.total_price)
		self.assertIsNone(item.unit_name)
		self.assertIsNone(item.analysis_code)

	def test_default_queryset_invokes_select_related_chain(self) -> None:
		with patch("target_bid.services.RabItem") as mock_model:
			select = mock_model.objects.select_related.return_value
			filtered = select.filter.return_value
			ordered = filtered.order_by.return_value

			result = _default_queryset(55)

		mock_model.objects.select_related.assert_called_once_with("unit", "rab_item_header")
		select.filter.assert_called_once_with(rab_id=55)
		filtered.order_by.assert_called_once_with("id")
		self.assertEqual(result, ordered)

	def test_service_branch_uses_injected_service(self) -> None:
		class StubService:
			def get_items(self, rab_id: int):
				return [f"rab-{rab_id}"]

		result = fetch_rab_job_items(77, service=StubService())
		self.assertEqual(result, ["rab-77"])

	def test_fetch_rab_job_items_include_non_adjustable_returns_split(self) -> None:
		adjustable_row = SimpleNamespace(
			id=20,
			name="Item Adjustable",
			unit=None,
			rab_item_header=None,
			price=100,
			volume=2,
			custom_ahs_id=None,
			analysis_code=None,
			is_locked=False,
		)
		locked_row = SimpleNamespace(
			id=21,
			name="Item Locked",
			unit=None,
			rab_item_header=None,
			price=150,
			volume=1,
			custom_ahs_id=None,
			analysis_code=None,
			is_locked=True,
		)
		adjustable, locked, excluded = fetch_rab_job_items(
			11, queryset=[adjustable_row, locked_row], include_non_adjustable=True
		)
		self.assertEqual(len(adjustable), 1)
		self.assertEqual(len(locked), 1)
		self.assertFalse(excluded)

	def test_rab_job_item_service_maps_rows(self) -> None:
		row = SimpleNamespace(
			id=9,
			name="Item",
			unit=None,
			rab_item_header=None,
			price=100,
			volume=2,
			custom_ahs_id=None,
			analysis_code=None,
		)
		repository = SimpleNamespace(for_rab=lambda rab_id: [row])
		mapper = RabJobItemMapper()
		service = RabJobItemService(repository, mapper)

		items = service.get_items(5)
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0].total_price, Decimal("200"))

	def test_service_filters_analysis_code_items(self) -> None:
		row = SimpleNamespace(
			id=3,
			name="Mobilisasi",
			unit=None,
			rab_item_header=None,
			price=100,
			volume=1,
			custom_ahs_id=None,
			analysis_code="AT.19-1",
		)
		repository = SimpleNamespace(for_rab=lambda _: [row])
		service = RabJobItemService(repository, RabJobItemMapper())

		self.assertEqual(service.get_items(1), [])

	def test_service_keeps_custom_items_even_with_code(self) -> None:
		row = SimpleNamespace(
			id=4,
			name="Custom Item",
			unit=None,
			rab_item_header=None,
			price=50,
			volume=2,
			custom_ahs_id=99,
			analysis_code="AT.20-1",
		)
		repository = SimpleNamespace(for_rab=lambda _: [row])
		service = RabJobItemService(repository, RabJobItemMapper())

		items = service.get_items(1)
		self.assertEqual(len(items), 1)
		self.assertEqual(items[0].custom_ahs_id, 99)

	def test_service_filters_named_safety_items(self) -> None:
		row = SimpleNamespace(
			id=5,
			name="Alat Pemadam Api Ringan (APAR)",
			unit=None,
			rab_item_header=None,
			price=10,
			volume=1,
			custom_ahs_id=None,
			analysis_code=None,
		)
		repository = SimpleNamespace(for_rab=lambda _: [row])
		service = RabJobItemService(repository, RabJobItemMapper())

		self.assertEqual(service.get_items(1), [])

	def test_service_groups_locked_items(self) -> None:
		adjustable_row = SimpleNamespace(
			id=10,
			name="Pekerjaan Normal",
			unit=None,
			rab_item_header=None,
			price=50,
			volume=2,
			custom_ahs_id=None,
			analysis_code=None,
			is_locked=False,
		)
		locked_row = SimpleNamespace(
			id=11,
			name="Pekerjaan Terkunci",
			unit=None,
			rab_item_header=None,
			price=75,
			volume=1,
			custom_ahs_id=None,
			analysis_code=None,
			is_locked=True,
		)
		repository = SimpleNamespace(for_rab=lambda _: [adjustable_row, locked_row])
		service = RabJobItemService(repository, RabJobItemMapper())

		adjustable, locked, excluded = service.get_items_with_classification(42)
		self.assertEqual(len(adjustable), 1)
		self.assertEqual(len(locked), 1)
		self.assertFalse(excluded)

	def test_classify_mapped_items_respects_policy(self) -> None:
		service = RabJobItemService(SimpleNamespace(for_rab=lambda _: []), RabJobItemMapper())
		adjustable_item = RabJobItem(
			rab_item_id=12,
			name="Generic Work",
			unit_name="m",
			unit_price=Decimal("10"),
			volume=Decimal("2"),
			total_price=Decimal("20"),
			rab_item_header_id=None,
			rab_item_header_name=None,
			custom_ahs_id=None,
			analysis_code=None,
			is_locked=False,
		)
		locked_item = RabJobItem(
			rab_item_id=13,
			name="Locked Work",
			unit_name="m",
			unit_price=Decimal("5"),
			volume=Decimal("1"),
			total_price=Decimal("5"),
			rab_item_header_id=None,
			rab_item_header_name=None,
			custom_ahs_id=None,
			analysis_code=None,
			is_locked=True,
		)

		adjustable, locked, excluded = service.classify_mapped_items([adjustable_item, locked_item])
		self.assertEqual(adjustable, [adjustable_item])
		self.assertEqual(locked, [locked_item])
		self.assertEqual(excluded, [])

	def test_fetch_rab_job_items_uses_service_for_classification(self) -> None:
		class StubService:
			def __init__(self) -> None:
				self.calls = []

			def get_items_with_classification(self, rab_id: int):
				self.calls.append(rab_id)
				return (["a"], ["b"], [])

			def get_items(self, rab_id: int):  # pragma: no cover - safeguard
				raise AssertionError("should not call get_items when include_non_adjustable is true")

		service = StubService()
		result = fetch_rab_job_items(77, service=service, include_non_adjustable=True)
		self.assertEqual(result, (["a"], ["b"], []))
		self.assertEqual(service.calls, [77])


class FetchRabJobItemsViewTests(SimpleTestCase):
	def setUp(self) -> None:
		self.factory = APIRequestFactory()

	def test_view_returns_serialised_payload(self) -> None:
		request = self.factory.get("/target_bid/rabs/99/items/")
		mock_item = RabJobItem(
			rab_item_id=5,
			name="Urugan Tanah",
			unit_name="m2",
			unit_price=Decimal("12500"),
			volume=Decimal("3"),
			total_price=Decimal("37500"),
			rab_item_header_id=4,
			rab_item_header_name="Pekerjaan Persiapan",
			custom_ahs_id=None,
			analysis_code="AT.02",
		)
		with patch(
			"target_bid.views.fetch_rab_job_items",
			return_value=([mock_item], [], []),
		) as mock_fetch:
			response = fetch_rab_job_items_view(request, rab_id=99)

		mock_fetch.assert_called_once_with(99, include_non_adjustable=True)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["rab_id"], 99)
		expected = mock_item.to_dict()
		expected["adjustment_status"] = "adjustable"
		self.assertEqual(response.data["items"], [expected])
		self.assertEqual(response.data["locked_items"], [])

	def test_view_includes_locked_items_section(self) -> None:
		request = self.factory.get("/target_bid/rabs/10/items/")
		adjustable_item = RabJobItem(
			rab_item_id=1,
			name="Item A",
			unit_name="m",
			unit_price=Decimal("100"),
			volume=Decimal("2"),
			total_price=Decimal("200"),
			rab_item_header_id=None,
			rab_item_header_name=None,
			custom_ahs_id=None,
			analysis_code=None,
			is_locked=False,
		)
		locked_item = RabJobItem(
			rab_item_id=2,
			name="Item B",
			unit_name="m2",
			unit_price=Decimal("150"),
			volume=Decimal("1"),
			total_price=Decimal("150"),
			rab_item_header_id=None,
			rab_item_header_name=None,
			custom_ahs_id=None,
			analysis_code=None,
			is_locked=True,
		)
		with patch(
			"target_bid.views.fetch_rab_job_items",
			return_value=([adjustable_item], [locked_item], []),
		):
			response = fetch_rab_job_items_view(request, rab_id=10)

		expected_adjustable = adjustable_item.to_dict()
		expected_adjustable["adjustment_status"] = "adjustable"
		expected_locked = locked_item.to_dict()
		expected_locked["adjustment_status"] = "locked"
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["items"], [expected_adjustable])
		self.assertEqual(response.data["locked_items"], [expected_locked])

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

class LockedItemRuleTests(TestCase):
    """Unit tests for LockedItemRule and its integration with NonAdjustableEvaluator."""

    def setUp(self):
        self.rule = LockedItemRule()
        self.evaluator = NonAdjustableEvaluator([self.rule])

    # ---------- POSITIVE CASES ----------
    def test_locked_item_is_excluded(self):
        """Locked items (is_locked=True) should be non-adjustable."""
        item = RabJobItem(
            rab_item_id=1,
            name="Test Work",
            unit_name="m2",
            unit_price=Decimal("1000"),
            volume=Decimal("2"),
            total_price=Decimal("2000"),
            rab_item_header_id=None,
            rab_item_header_name=None,
            custom_ahs_id=None,
            analysis_code=None,
            is_locked=True,
        )
        decision = self.rule.decide(item)
        self.assertTrue(decision)

    # ---------- NEGATIVE CASES ----------
    def test_non_locked_item_returns_none(self):
        """Unlocked items should not be marked non-adjustable by this rule."""
        item = RabJobItem(
            rab_item_id=2,
            name="Open Work",
            unit_name="m",
            unit_price=Decimal("500"),
            volume=Decimal("5"),
            total_price=Decimal("2500"),
            rab_item_header_id=None,
            rab_item_header_name=None,
            custom_ahs_id=None,
            analysis_code=None,
            is_locked=False,
        )
        decision = self.rule.decide(item)
        self.assertIsNone(decision)

    def test_missing_is_locked_attribute_returns_none(self):
        """Items without is_locked attribute should be ignored."""
        item = RabJobItem(
            rab_item_id=3,
            name="Unnamed Work",
            unit_name=None,
            unit_price=None,
            volume=None,
            total_price=None,
            rab_item_header_id=None,
            rab_item_header_name=None,
            custom_ahs_id=None,
            analysis_code=None,
            is_locked=None,
        )
        decision = self.rule.decide(item)
        self.assertIsNone(decision)

    # ---------- EDGE CASES ----------
    def test_combined_evaluator_prefers_locked_rule(self):
        """Even if multiple rules exist, locked items should be filtered first."""
        locked_item = RabJobItem(
            rab_item_id=4,
            name="Safety Gear",
            unit_name="set",
            unit_price=Decimal("500"),
            volume=Decimal("2"),
            total_price=Decimal("1000"),
            rab_item_header_id=None,
            rab_item_header_name=None,
            custom_ahs_id=None,
            analysis_code=None,
            is_locked=True,
        )
        result = self.evaluator.is_non_adjustable(locked_item)
        self.assertTrue(result)

    def test_unlocked_item_passes_through_combined_evaluator(self):
        """Unlocked items should not be filtered out by evaluator."""
        unlocked_item = RabJobItem(
            rab_item_id=5,
            name="Normal Job",
            unit_name="unit",
            unit_price=Decimal("100"),
            volume=Decimal("10"),
            total_price=Decimal("1000"),
            rab_item_header_id=None,
            rab_item_header_name=None,
            custom_ahs_id=None,
            analysis_code=None,
            is_locked=False,
        )
        result = self.evaluator.is_non_adjustable(unlocked_item)
        self.assertFalse(result)

class ProportionalAdjustmentCalculatorTests(SimpleTestCase):
    """Tests for computing the proportional adjustment factor."""

    # ---------- Positive Cases ----------
    def test_reducing_budget_returns_factor_below_one(self):
        current = Decimal("1000000")
        target = Decimal("800000")
        factor = ProportionalAdjustmentCalculator.compute(current, target)
        self.assertEqual(factor, Decimal("0.8000"))

    def test_increasing_budget_returns_factor_above_one(self):
        current = Decimal("1000000")
        target = Decimal("1200000")
        factor = ProportionalAdjustmentCalculator.compute(current, target)
        self.assertEqual(factor, Decimal("1.2000"))

    def test_same_budget_returns_factor_one(self):
        current = Decimal("500000")
        target = Decimal("500000")
        factor = ProportionalAdjustmentCalculator.compute(current, target)
        self.assertEqual(factor, Decimal("1.0000"))

    # ---------- Negative / Error Cases ----------
    def test_invalid_type_raises_type_error(self):
        with self.assertRaises(TypeError):
            ProportionalAdjustmentCalculator.compute("1000000", Decimal("800000"))

    def test_zero_current_total_raises_value_error(self):
        with self.assertRaises(ValueError):
            ProportionalAdjustmentCalculator.compute(Decimal("0"), Decimal("800000"))

    def test_negative_target_total_raises_value_error(self):
        with self.assertRaises(ValueError):
            ProportionalAdjustmentCalculator.compute(Decimal("1000000"), Decimal("-100"))

    # ---------- Edge Case ----------
    def test_very_small_difference_is_handled_precisely(self):
        current = Decimal("1000000")
        target = Decimal("999999.9")
        factor = ProportionalAdjustmentCalculator.compute(current, target)
        self.assertEqual(factor, Decimal("1.0000"))  # rounds to 4 decimals
