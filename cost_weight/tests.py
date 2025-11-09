import unittest
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, TransactionTestCase
from django.apps import apps
from django.db import connection

# ✅ Check if estimator app is installed before importing anything that uses it
ESTIMATOR_INSTALLED = apps.is_installed("estimator")

# ✅ Always safe to import cost_weight_calc (pure functions)
from cost_weight.services.cost_weight_calc import (
    calculate_cost_weights,
    format_weights,
    _to_decimal,
    _normalize_weights,
)

# ✅ Only import these if the estimator app exists
if ESTIMATOR_INSTALLED:
    from cost_weight.services.recalc_orchestrator import (
        ITEM_MODEL,
        JOB_MODEL,
        ITEM_COST_FIELD,
        ITEM_WEIGHT_FIELD,
    )
    # Get model references safely
    Item = apps.get_model(ITEM_MODEL)
    Job = apps.get_model(JOB_MODEL)
else:
    # Otherwise define placeholders to prevent NameErrors
    ITEM_MODEL = JOB_MODEL = ITEM_COST_FIELD = ITEM_WEIGHT_FIELD = None
    Item = Job = None




def _sqlite_type_for(field):
    dbt = (field.db_type(connection) or "NUMERIC").upper()
    if "CHAR" in dbt or "TEXT" in dbt or "VARCHAR" in dbt:
        return "TEXT"
    if "INT" in dbt:
        return "INTEGER"
    if "DECIMAL" in dbt or "NUMERIC" in dbt or "REAL" in dbt or "FLOAT" in dbt:
        return "NUMERIC"
    if "DATE" in dbt or "TIME" in dbt:
        return "TEXT"
    return "NUMERIC"


def _ensure_table_for_model(Model):
    meta = Model._meta
    table = meta.db_table
    columns = []
    for f in meta.concrete_fields:
        col = f.column
        col_type = _sqlite_type_for(f)
        col_def = f'"{col}" {col_type}'
        if f.primary_key:
            col_def += " PRIMARY KEY"
        columns.append(col_def)
    create_sql = f'CREATE TABLE IF NOT EXISTS "{table}" ({", ".join(columns)});'
    with connection.cursor() as c:
        c.execute(create_sql)


def _ensure_min_tables():
    if not ESTIMATOR_INSTALLED or not JOB_MODEL or not ITEM_MODEL:
        return  # Skip table creation if estimator is missing

    Job = apps.get_model(JOB_MODEL)
    Item = apps.get_model(ITEM_MODEL)
    _ensure_table_for_model(Job)
    _ensure_table_for_model(Item)



class DBBootstrapTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _ensure_min_tables()


class DBBootstrapTransactionTestCase(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _ensure_min_tables()

_job_seq = 0
def mk_job(Job, name="J", project_id=None, **extra):
    """Buat row Job dengan id manual (aman jika pk non-auto)."""
    global _job_seq
    _job_seq += 1
    payload = {"id": _job_seq}
    job_field_names = {f.name for f in Job._meta.concrete_fields}
    if "name" in job_field_names:
        payload["name"] = name
    if "project_id" in job_field_names:
        payload["project_id"] = project_id
    payload.update({k: v for k, v in extra.items() if k in job_field_names})
    return Job.objects.create(**payload)


def mk_item(Item, job_obj, name, initial_cost=None):

    from cost_weight.services.recalc_orchestrator import ITEM_FK_TO_JOB
    item_fields = {f.name for f in Item._meta.concrete_fields}
    payload = {}
    if ITEM_FK_TO_JOB in item_fields:
        payload[ITEM_FK_TO_JOB] = job_obj
    if "name" in item_fields:
        payload["name"] = name
    if initial_cost is not None and ITEM_COST_FIELD in item_fields:
        payload[ITEM_COST_FIELD] = initial_cost
    obj = Item.objects.create(**payload)
    if initial_cost is not None and hasattr(obj, ITEM_COST_FIELD):
        setattr(obj, ITEM_COST_FIELD, Decimal(str(initial_cost)))
        try:
            obj.save(update_fields=[ITEM_COST_FIELD])
        except Exception:
            obj.save()
    return obj


def set_cost_safe(obj, value):
    """Set kolom cost jika ada; abaikan jika tidak ada (biar test tetap jalan)."""
    if hasattr(obj, ITEM_COST_FIELD):
        setattr(obj, ITEM_COST_FIELD, Decimal(str(value)))
        try:
            obj.save(update_fields=[ITEM_COST_FIELD])
        except Exception:
            obj.save()


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
            res,
            {
                "i": Decimal("20.00"),
                "s": Decimal("30.00"),
                "f": Decimal("50.00"),
                "d": Decimal("0.00"),
            },
        )
        self.assertEqual(_to_decimal(1.2), Decimal("1.2"))
        self.assertEqual(_to_decimal("4.50"), Decimal("4.50"))
        self.assertEqual(_to_decimal(3), Decimal("3"))
        self.assertEqual(_to_decimal(Decimal("7.7")), Decimal("7.7"))

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
        self.assertEqual(
            format_weights(res),
            {"A": "50.00", "B": "30.00", "C": "20.00"},
        )

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
        self.assertEqual(changed_key, ["C"])

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



@unittest.skipUnless(ESTIMATOR_INSTALLED, "estimator app not installed")
class LiveRecalcSignalsTests(DBBootstrapTestCase):
    def setUp(self):
        self.job = mk_job(Job, "J1")

    def _mk(self, name, cost):
        obj = mk_item(Item,self.job, name, initial_cost=None)
        set_cost_safe(obj, cost)
        return obj

    def test_create_items_triggers_weights_sum_100(self):
        a = self._mk("A", "200")
        b = self._mk("B", "200")
        a.refresh_from_db(); b.refresh_from_db()
        self.assertEqual(
            getattr(a, ITEM_WEIGHT_FIELD) + getattr(b, ITEM_WEIGHT_FIELD),
            Decimal("100.00"),
        )
        self.assertEqual(getattr(a, ITEM_WEIGHT_FIELD), Decimal("50.00"))
        self.assertEqual(getattr(b, ITEM_WEIGHT_FIELD), Decimal("50.00"))

    def test_update_cost_rebalances(self):
        a = self._mk("A", "100")
        b = self._mk("B", "100")
        set_cost_safe(a, Decimal("300"))
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
        _ = self._mk("B", "100")
        with patch("cost_weight.services.recalc_orchestrator.recalc_weights_for_job") as recalc:
            if hasattr(a, "name"):
                a.name = "A-rename"
                a.save(update_fields=["name"])
            else:
                a.save()
            recalc.assert_not_called()

    def test_job_field_in_whitelist_triggers_recalc(self):
        job_fields = {f.name for f in Job._meta.concrete_fields}
        if "name" not in job_fields:
            self.skipTest("Job model has no 'name' field to whitelist")

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

@unittest.skipUnless(ESTIMATOR_INSTALLED, "estimator app not installed")
class OrchestratorBehaviorTests(DBBootstrapTransactionTestCase):

    reset_sequences = True

    def setUp(self):
        self.job = mk_job(Job, "J2")
        self.a = mk_item(Item, self.job, "A", initial_cost=Decimal("100"))
        self.b = mk_item(Item, self.job, "B", initial_cost=Decimal("100"))

    def test_bulk_update_used_and_single_tx(self):
        with patch("cost_weight.services.recalc_orchestrator.Item.objects.bulk_update") as bulk_upd, \
             patch("cost_weight.services.recalc_orchestrator.calculate_cost_weights") as calc:
            calc.return_value = {str(self.a.pk): Decimal("60.00"), str(self.b.pk): Decimal("40.00")}
            from cost_weight.services.recalc_orchestrator import recalc_weights_for_job
            updated = recalc_weights_for_job(self.job.pk)
            self.assertEqual(updated, 2)
            self.assertTrue(bulk_upd.called)
            calc.assert_called_once()

@unittest.skipUnless(ESTIMATOR_INSTALLED, "estimator app not installed")
class CostWeightValidationTests(unittest.TestCase):
    def test_negative_cost_rejected(self):
        with self.assertRaises(ValueError):
            calculate_cost_weights({"A": -100, "B": 200})

    def test_invalid_cost_type_rejected(self):
        with self.assertRaises(ValueError):
            calculate_cost_weights({"A": "invalid", "B": 200})

    def test_zero_cost_is_allowed(self):
        res = calculate_cost_weights({"A": 0, "B": 100})
        self.assertIn("A", res)
        self.assertIn("B", res)


from cost_weight.services.chart_transformer import to_chart_data

@unittest.skipUnless(ESTIMATOR_INSTALLED, "estimator app not installed")
class ChartTransformerTests(unittest.TestCase):
    def test_basic_transform_from_decimal(self):
        weights = {"1": Decimal("62.50"), "2": Decimal("37.50")}
        names   = {"1": "Item A", "2": "Item B"}
        out = to_chart_data(weights, names)
        self.assertEqual(out, [
            {"label": "Item A", "value": 62.5},
            {"label": "Item B", "value": 37.5},
        ])

    def test_missing_name_falls_back_to_id(self):
        weights = {"10": Decimal("100.00")}
        names   = {}
        out = to_chart_data(weights, names)
        self.assertEqual(out, [{"label": "10", "value": 100.0}])

    def test_empty_input_returns_empty_list(self):
        self.assertEqual(to_chart_data({}, {}), [])

    def test_rounding_and_order_by_value_desc(self):
        weights = {"a": Decimal("33.333"), "b": Decimal("66.667")}
        names   = {"a": "A", "b": "B"}
        out = to_chart_data(weights, names, sort_desc=True, decimal_places=1)
        self.assertEqual(out, [
            {"label": "B", "value": 66.7},
            {"label": "A", "value": 33.3},
        ])

@unittest.skipUnless(ESTIMATOR_INSTALLED, "estimator app not installed")
class ChartEndpointTests(DBBootstrapTestCase):
    def setUp(self):
        from cost_weight.services.recalc_orchestrator import ITEM_FK_TO_JOB
        ItemModel = apps.get_model(ITEM_MODEL)
        JobModel  = apps.get_model(JOB_MODEL)
        self.job = mk_job(JobModel, "J Chart")
        self.a = mk_item(ItemModel, self.job, "A", initial_cost=Decimal("200"))
        self.b = mk_item(ItemModel, self.job, "B", initial_cost=Decimal("200"))

    def test_chart_json_structure(self):
        url = f"/cost-weight/jobs/{self.job.pk}/chart-data/?dp=1&sort=desc"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertIn("items", payload)
        self.assertTrue(all(set(r.keys()) == {"label","value"} for r in payload["items"]))

@unittest.skipUnless(ESTIMATOR_INSTALLED, "estimator app not installed")
class AutoFillIntegrationTests(DBBootstrapTestCase):

    def setUp(self):
        self.Item = apps.get_model(ITEM_MODEL)
        self.Job  = apps.get_model(JOB_MODEL)
        self.job = mk_job(self.Job, "Auto-Fill Job")
        self.a = mk_item(self.Item, self.job, "A", initial_cost=Decimal("0"))
        self.b = mk_item(self.Item, self.job, "B", initial_cost=Decimal("0"))

    def test_autofill_single_save_triggers_signals(self):
        set_cost_safe(self.a, Decimal("200"))
        set_cost_safe(self.b, Decimal("200"))

        self.a.refresh_from_db(); self.b.refresh_from_db()
        from cost_weight.services.recalc_orchestrator import ITEM_WEIGHT_FIELD
        self.assertEqual(getattr(self.a, ITEM_WEIGHT_FIELD), Decimal("50.00"))
        self.assertEqual(getattr(self.b, ITEM_WEIGHT_FIELD), Decimal("50.00"))

    def test_autofill_bulk_update_requires_single_manual_recalc(self):
        from cost_weight.services.recalc_orchestrator import (
            recalc_weights_for_job, ITEM_WEIGHT_FIELD
        )
        if hasattr(self.a, ITEM_COST_FIELD):
            setattr(self.a, ITEM_COST_FIELD, Decimal("300"))
        if hasattr(self.b, ITEM_COST_FIELD):
            setattr(self.b, ITEM_COST_FIELD, Decimal("100"))

        item_fields = {f.name for f in self.Item._meta.concrete_fields}
        if ITEM_COST_FIELD in item_fields:
            self.Item.objects.bulk_update([self.a, self.b], [ITEM_COST_FIELD])
        else:
            self.a.save(); self.b.save()

        updated_count = recalc_weights_for_job(self.job.pk)
        self.assertEqual(updated_count, 2)

        self.a.refresh_from_db(); self.b.refresh_from_db()
        self.assertEqual(getattr(self.a, ITEM_WEIGHT_FIELD), Decimal("75.00"))
        self.assertEqual(getattr(self.b, ITEM_WEIGHT_FIELD), Decimal("25.00"))

    def test_autofill_zeroed_costs_result_all_zero(self):
        from cost_weight.services.recalc_orchestrator import (
            recalc_weights_for_job, ITEM_WEIGHT_FIELD
        )
        set_cost_safe(self.a, 0)
        set_cost_safe(self.b, 0)
        recalc_weights_for_job(self.job.pk)
        self.a.refresh_from_db(); self.b.refresh_from_db()
        self.assertEqual(getattr(self.a, ITEM_WEIGHT_FIELD), Decimal("0.00"))
        self.assertEqual(getattr(self.b, ITEM_WEIGHT_FIELD), Decimal("0.00"))

    def test_recalc_is_idempotent(self):
        from cost_weight.services.recalc_orchestrator import (
            recalc_weights_for_job, ITEM_WEIGHT_FIELD
        )
        set_cost_safe(self.a, Decimal("500"))
        set_cost_safe(self.b, Decimal("500"))

        recalc_weights_for_job(self.job.pk)
        first_a, first_b = [
            getattr(x, ITEM_WEIGHT_FIELD) for x in
            [self.Item.objects.get(pk=self.a.pk), self.Item.objects.get(pk=self.b.pk)]
        ]
        recalc_weights_for_job(self.job.pk)
        second_a, second_b = [
            getattr(x, ITEM_WEIGHT_FIELD) for x in
            [self.Item.objects.get(pk=self.a.pk), self.Item.objects.get(pk=self.b.pk)]
        ]
        self.assertEqual(first_a, second_a)
        self.assertEqual(first_b, second_b)
@unittest.skipUnless(ESTIMATOR_INSTALLED, "estimator app not installed")
class OrchestratorEdgeCasesTests(DBBootstrapTestCase):
    def setUp(self):
        self.Item = apps.get_model(ITEM_MODEL)
        self.Job  = apps.get_model(JOB_MODEL)

    def test_recalc_when_no_items_returns_zero(self):
        from cost_weight.services.recalc_orchestrator import recalc_weights_for_job
        job = mk_job(self.Job, "Empty")
        self.assertEqual(recalc_weights_for_job(job.pk), 0)

if __name__ == "__main__":
    unittest.main()