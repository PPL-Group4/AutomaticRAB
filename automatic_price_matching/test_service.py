from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from .service import AutomaticPriceMatchingService
from .price_retrieval import MockAhspSource, AhspPriceRetriever


class AutomaticPriceMatchingServiceTests(SimpleTestCase):
    def setUp(self) -> None:
        data = {
            "AT.01.001": Decimal("250000.00"),
            "BT.02.010": Decimal("12500"),
        }
        self.retriever = AhspPriceRetriever(MockAhspSource(data))
        self.svc = AutomaticPriceMatchingService(price_retriever=self.retriever)

    def test_match_one_with_provided_unit_price_preserves_and_recalculates_total(self):
        cleaned = {
            "code": "AT.01.001",
            "name": "Some work",
            "volume": Decimal("2"),
            "unit_price": Decimal("100.50"),
        }
        with patch("automatic_price_matching.service.validate_ahsp_payload", return_value=cleaned):
            out = self.svc.match_one({"irrelevant": "payload"})
        self.assertEqual(out["unit_price"], Decimal("100.50"))
        self.assertEqual(out["total_cost"], Decimal("201.00"))
        self.assertEqual(out["match_status"], "Provided")
        self.assertTrue(out["is_editable"])

    def test_match_one_finds_price_from_ahsp_and_marks_not_editable(self):
        cleaned = {
            "code": "AT.01.001",
            "name": "Excavation",
            "volume": Decimal("1.5"),
            "unit_price": None,
        }
        with patch("automatic_price_matching.service.validate_ahsp_payload", return_value=cleaned):
            out = self.svc.match_one({"irrelevant": "payload"})
        # Price from mock source
        self.assertEqual(out["unit_price"], Decimal("250000.00"))
        self.assertEqual(out["total_cost"], Decimal("375000.00"))
        self.assertEqual(out["match_status"], "Matched")
        self.assertFalse(out["is_editable"])

    def test_match_one_applies_fallback_when_no_code_or_price(self):
        cleaned = {
            "code": "",
            "name": "Manual task",
            "volume": Decimal("3"),
            "unit_price": None,
        }
        with patch("automatic_price_matching.service.validate_ahsp_payload", return_value=cleaned):
            out = self.svc.match_one({"irrelevant": "payload"})
        # fallback returns unit_price None and zero total per fallback_validator
        self.assertIsNone(out["unit_price"])
        self.assertEqual(out["total_cost"], Decimal("0"))
        self.assertEqual(out["match_status"], "Needs Manual Input")
        self.assertTrue(out["is_editable"])

    def test_match_one_raises_when_validation_fails(self):
        def raiser(_):
            raise ValidationError({"code": ["required"]})

        with patch("automatic_price_matching.service.validate_ahsp_payload", side_effect=raiser):
            with self.assertRaises(ValidationError):
                self.svc.match_one({"bad": "payload"})

    def test_match_batch_returns_errors_and_results_for_mixed_inputs(self):
        # side effects: first valid, second validation error, third fallback valid
        valid1 = {"code": "BT.02.010", "name": "A", "volume": Decimal("2"), "unit_price": None}
        err = ValidationError({"code": ["required"]})
        valid3 = {"code": "", "name": "C", "volume": None, "unit_price": None}

        side_effects = [valid1, err, valid3]

        with patch("automatic_price_matching.service.validate_ahsp_payload", side_effect=side_effects):
            results = self.svc.match_batch([{}, {}, {}])

        self.assertEqual(len(results), 3)
        # first must be matched from AHSP
        self.assertEqual(results[0]["unit_price"], Decimal("12500"))
        # second is an error entry
        self.assertIn("error", results[1])
        # third is fallback entry
        self.assertEqual(results[2]["match_status"], "Needs Manual Input")

    def test_match_one_with_missing_volume_but_unit_price_provided_yields_none_total(self):
        cleaned = {
            "code": "AT.01.001",
            "name": "X",
            "volume": None,
            "unit_price": Decimal("100"),
        }
        with patch("automatic_price_matching.service.validate_ahsp_payload", return_value=cleaned):
            out = self.svc.match_one({"irrelevant": "payload"})
        # volume missing -> TotalCostCalculator returns None
        self.assertIsNone(out["total_cost"])

    def test_match_batch_empty_list_returns_empty_list(self):
        results = self.svc.match_batch([])
        self.assertEqual(results, [])
