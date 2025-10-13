import unittest
from decimal import Decimal
from unittest.mock import patch

from cost_weight.services.cost_weight_calc import (
    calculate_cost_weights,
    format_weights,
    _to_decimal,
    _normalize_weights
)

class CostWeightCalcTests(unittest.TestCase):
    def test_simple_exact_split_no_distribution(self):
        items = {"A": Decimal("200"), "B": Decimal("200")}
        res = calculate_cost_weights(items)
        self.assertEqual(res, {"A": Decimal("50.00"), "B": Decimal("50.00")})
        self.assertEqual(sum(res.values()), Decimal("100.00"))

    def test_rounding_distribution_happens_and_sums_100(self):
        items = {"A": 1, "B": 1, "C": 1}
        res = calculate_cost_weights(items)
        self.assertEqual(sum(res.values()), Decimal("100.00"))
        self.assertTrue(any(v >= Decimal("33.34") for v in res.values()))

    def test_zero_total_early_return(self):
        res = calculate_cost_weights({"A": 0, "B": 0})
        self.assertEqual(res["A"], Decimal("0.00"))
        self.assertEqual(res["B"], Decimal("0.00"))
        self.assertEqual(sum(res.values()), Decimal("0.00"))

    def test_accepts_various_number_types_hits_float_branch(self):
        items = {"i": 2, "s": "3", "f": 5.0, "d": Decimal("0")}  # total=10
        res = calculate_cost_weights(items)
        self.assertEqual(
            res, {"i": Decimal("20.00"), "s": Decimal("30.00"),
                  "f": Decimal("50.00"), "d": Decimal("0.00")}
        )
        self.assertEqual(_to_decimal(1.2), Decimal("1.2"))     # float branch
        self.assertEqual(_to_decimal("4.50"), Decimal("4.50")) # str branch
        self.assertEqual(_to_decimal(3), Decimal("3"))         # int branch
        self.assertEqual(_to_decimal(Decimal("7.7")), Decimal("7.7"))  # decimal branch

    def test_custom_decimal_places_paths(self):
        items = {"A": 1, "B": 2}
        res = calculate_cost_weights(items, decimal_places=1)
        self.assertEqual(res["A"], Decimal("33.3"))
        self.assertEqual(res["B"], Decimal("66.7"))
        self.assertEqual(sum(res.values()), Decimal("100.0"))

    def test_deterministic_order_on_ties(self):
        items = {"X": Decimal("10.01"), "Y": Decimal("10.01"), "Z": Decimal("9.98")}
        r1 = calculate_cost_weights(items)
        r2 = calculate_cost_weights(items)
        self.assertEqual(r1, r2)
        self.assertEqual(sum(r1.values()), Decimal("100.00"))

    def test_format_weights_serializes_strings(self):
        items = {"A": Decimal("2500"), "B": Decimal("1500"), "C": Decimal("1000")}
        res = calculate_cost_weights(items)
        self.assertEqual(format_weights(res), {"A": "50.00", "B": "30.00", "C": "20.00"})

class CostWeightNormalizationTests(unittest.TestCase):
    def test_normalization_handles_total_below_100(self):
        weights = {"A": Decimal("33.33"), "B": Decimal("33.33"), "C": Decimal("33.33")}
        res = _normalize_weights(weights.copy())
        self.assertEqual(sum(res.values()), Decimal("100.00"))

    def test_normalization_handles_total_above_100(self):
        weights = {"A": Decimal("33.34"), "B": Decimal("33.34"), "C": Decimal("33.34")}
        res = _normalize_weights(weights.copy())
        self.assertEqual(sum(res.values()), Decimal("100.00"))

    def test_normalization_does_nothing_if_exact_100(self):
        weights = {"A": Decimal("20.00"), "B": Decimal("30.00"), "C": Decimal("50.00")}
        res = _normalize_weights(weights.copy())
        self.assertEqual(res, weights)

    def test_normalization_zero_total_skipped(self):
        weights = {"A": Decimal("0.00"), "B": Decimal("0.00")}
        res = _normalize_weights(weights.copy())
        self.assertEqual(res, weights)

    def test_normalization_keeps_values_within_valid_range(self):
        weights = {"A": Decimal("33.33"), "B": Decimal("33.33"), "C": Decimal("33.33")}
        res = _normalize_weights(weights.copy())
        for v in res.values():
            self.assertTrue(Decimal("0.00") <= v <= Decimal("100.00"))
        self.assertEqual(sum(res.values()), Decimal("100.00"))

    def test_normalization_varied_decimal_places(self):
        weights = {"A": Decimal("33.3"), "B": Decimal("33.3"), "C": Decimal("33.3")}
        res = _normalize_weights(weights.copy(), decimal_places=1)
        self.assertEqual(sum(res.values()), Decimal("100.0"))

    def test_normalization_is_deterministic(self):
        weights = {"X": Decimal("25.00"), "Y": Decimal("25.00"), "Z": Decimal("50.00")}
        r1 = _normalize_weights(weights.copy())
        r2 = _normalize_weights(weights.copy())
        self.assertEqual(r1, r2)

    def test_normalization_affects_largest_weight_only(self):
        weights = {"A": Decimal("30.00"), "B": Decimal("30.00"), "C": Decimal("39.99")}
        res = _normalize_weights(weights.copy())
        changed_key = [k for k in res if res[k] != weights[k]]
        self.assertEqual(changed_key, ["C"])  # only the largest should change

class IntegrationWithCostWeightCalcTests(unittest.TestCase):
    def test_integration_normalization_makes_total_exactly_100(self):
        items = {"A": Decimal("333.33"), "B": Decimal("333.33"), "C": Decimal("333.34")}
        res = calculate_cost_weights(items)
        self.assertEqual(sum(res.values()), Decimal("100.00"))

class CostWeightZeroDivisionTests(unittest.TestCase):
    def test_zero_division_returns_all_zero(self):
        items = {"A": 0, "B": 0, "C": 0}
        res = calculate_cost_weights(items)
        self.assertTrue(all(v == Decimal("0.00") for v in res.values()))
        self.assertEqual(sum(res.values()), Decimal("0.00"))

    def test_zero_division_with_empty_input(self):
        res = calculate_cost_weights({})
        self.assertEqual(res, {})

    def test_zero_division_with_partial_nonzero(self):
        items = {"A": 0, "B": 0, "C": 100}
        res = calculate_cost_weights(items)
        self.assertEqual(res["C"], Decimal("100.00"))
        self.assertEqual(res["A"], Decimal("0.00"))


from django.test import TestCase, TransactionTestCase
from django.apps import apps

from cost_weight.services.recalc_orchestrator import (
    ITEM_MODEL, JOB_MODEL, ITEM_COST_FIELD, ITEM_WEIGHT_FIELD
)

Item = apps.get_model(ITEM_MODEL)
Job  = apps.get_model(JOB_MODEL)

class LiveRecalcSignalsTests(TestCase):
    def setUp(self):
        self.job = Job.objects.create(name="J1")

    def _mk(self, name, cost):
        return Item.objects.create(**{
            "name": name,
            ITEM_COST_FIELD: Decimal(cost),
            "job": self.job,
        })

    def test_create_items_triggers_weights_sum_100(self):
        a = self._mk("A", "200")
        b = self._mk("B", "200")
        a.refresh_from_db(); b.refresh_from_db()
        self.assertEqual(
            getattr(a, ITEM_WEIGHT_FIELD) + getattr(b, ITEM_WEIGHT_FIELD),
            Decimal("100.00")
        )
        self.assertEqual(getattr(a, ITEM_WEIGHT_FIELD), Decimal("50.00"))
        self.assertEqual(getattr(b, ITEM_WEIGHT_FIELD), Decimal("50.00"))

    def test_update_cost_rebalances(self):
        a = self._mk("A", "100")
        b = self._mk("B", "100")
        # Only cost changes: pass update_fields to ensure selective trigger
        setattr(a, ITEM_COST_FIELD, Decimal("300"))
        a.save(update_fields=[ITEM_COST_FIELD])
        a.refresh_from_db(); b.refresh_from_db()
        self.assertEqual(getattr(a, ITEM_WEIGHT_FIELD), Decimal("75.00"))
        self.assertEqual(getattr(b, ITEM_WEIGHT_FIELD), Decimal("25.00"))

    def test_delete_item_rebalances_remaining(self):
        a = self._mk("A", "2500")
        b = self._mk("B", "1500")
        c = self._mk("C", "1000")
        c.delete()
        a.refresh_from_db(); b.refresh_from_db()
        self.assertEqual(getattr(a, ITEM_WEIGHT_FIELD), Decimal("62.50"))
        self.assertEqual(getattr(b, ITEM_WEIGHT_FIELD), Decimal("37.50"))

    def test_zero_total_sets_all_zero(self):
        a = self._mk("A", "0")
        b = self._mk("B", "0")
        a.refresh_from_db(); b.refresh_from_db()
        self.assertEqual(getattr(a, ITEM_WEIGHT_FIELD), Decimal("0.00"))
        self.assertEqual(getattr(b, ITEM_WEIGHT_FIELD), Decimal("0.00"))

    def test_irrelevant_item_update_does_not_trigger_recalc(self):
        a = self._mk("A", "100")
        b = self._mk("B", "100")
        with patch("cost_weight.services.recalc_orchestrator.recalc_weights_for_job") as recalc:
            # Change name only; cost untouched — should NOT recalc
            a.name = "A-rename"
            a.save(update_fields=["name"])
            recalc.assert_not_called()

    def test_job_field_in_whitelist_triggers_recalc(self):
        # Temporarily add a job field to the whitelist to simulate dependency
        from cost_weight import signals
        orig = signals.JOB_FIELDS_THAT_AFFECT_WEIGHTS
        try:
            signals.JOB_FIELDS_THAT_AFFECT_WEIGHTS = ("name",)
            with patch("cost_weight.services.recalc_orchestrator.recalc_weights_for_job") as recalc:
                self.job.name = "J1-new"
                self.job.save(update_fields=["name"])
                recalc.assert_called_once_with(self.job.pk)
        finally:
            signals.JOB_FIELDS_THAT_AFFECT_WEIGHTS = orig


class OrchestratorBehaviorTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.job = Job.objects.create(name="J2")
        self.a = Item.objects.create(job=self.job, name="A", **{ITEM_COST_FIELD: Decimal("100")})
        self.b = Item.objects.create(job=self.job, name="B", **{ITEM_COST_FIELD: Decimal("100")})

    def test_bulk_update_used_and_single_tx(self):
        # Spy: ensure bulk_update is called once; calculate_cost_weights called once
        with patch("cost_weight.services.recalc_orchestrator.Item.objects.bulk_update") as bulk_upd, \
             patch("cost_weight.services.recalc_orchestrator.calculate_cost_weights") as calc:
            # mock calc to return deterministic 60/40
            calc.return_value = {str(self.a.pk): Decimal("60.00"), str(self.b.pk): Decimal("40.00")}
            from cost_weight.services.recalc_orchestrator import recalc_weights_for_job
            updated = recalc_weights_for_job(self.job.pk)
            self.assertEqual(updated, 2)
            self.assertTrue(bulk_upd.called)
            calc.assert_called_once()
