from __future__ import annotations

from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict

from django.apps import apps
from django.conf import settings

ITEM_MODEL = getattr(settings, "COST_WEIGHT_ITEM_MODEL", "estimator.JobItem")
JOB_MODEL  = getattr(settings, "COST_WEIGHT_JOB_MODEL",  "estimator.Job")
ITEM_COST_FIELD = getattr(settings, "COST_WEIGHT_ITEM_COST_FIELD", "total_cost")  # ← was "price"
ITEM_WEIGHT_FIELD = getattr(settings, "COST_WEIGHT_ITEM_WEIGHT_FIELD", "weight_pct")
ITEM_FK_TO_JOB = getattr(settings, "COST_WEIGHT_ITEM_FK_TO_JOB", "job")           # ← was "rab"

ITEM_COST_FALLBACKS = getattr(
    settings,
    "COST_WEIGHT_ITEM_COST_FALLBACKS",
    ("total_cost", "cost", "price"),
)

class _ItemProxy:
    @property
    def objects(self):
        return apps.get_model(ITEM_MODEL).objects

Item = _ItemProxy()  


def calculate_cost_weights(costs_by_id: Dict[str, Decimal], decimal_places: int = 1) -> Dict[str, Decimal]:
    norm_costs: Dict[str, Decimal] = {}
    total = Decimal("0")
    for k, v in costs_by_id.items():
        dv = Decimal(str(v or "0"))
        norm_costs[k] = dv
        total += dv

    if total == 0:
        q = Decimal("1." + "0" * decimal_places) if decimal_places > 0 else Decimal("1")
        zero = Decimal("0").quantize(q)
        return {k: zero for k in norm_costs}

    raw = {k: (v / total) * Decimal("100") for k, v in norm_costs.items()}

    q = Decimal("1." + "0" * decimal_places) if decimal_places > 0 else Decimal("1")
    rounded = {k: r.quantize(q, rounding=ROUND_HALF_UP) for k, r in raw.items()}
    target = Decimal("100").quantize(q)
    sum_rounded = sum(rounded.values())

    if sum_rounded == target:
        return rounded

    diff = target - sum_rounded
    step = Decimal("1") / (Decimal(10) ** decimal_places)

    def frac_part(d: Decimal) -> Decimal:
        return (d - d.quantize(step, rounding=ROUND_HALF_UP)).copy_abs()

    order_plus = sorted(raw.items(), key=lambda kv: (-frac_part(kv[1]), str(kv[0])))
    order_minus = sorted(raw.items(), key=lambda kv: (frac_part(kv[1]), str(kv[0])))

    if diff > 0:
        i = 0
        while diff > 0:
            k = order_plus[i % len(order_plus)][0]
            rounded[k] += step
            diff -= step
            i += 1
    elif diff < 0:
        i = 0
        while diff < 0:
            k = order_minus[i % len(order_minus)][0]
            rounded[k] -= step
            diff += step
            i += 1

    return rounded

def _items_to_mapping(items: Iterable) -> Dict[str, Decimal]:
    out: Dict[str, Decimal] = {}
    for it in items:
        val = getattr(it, ITEM_COST_FIELD, None)
        if val in (None, ""):
            for alt in ITEM_COST_FALLBACKS:
                if alt == ITEM_COST_FIELD:
                    continue
                if hasattr(it, alt):
                    val = getattr(it, alt)
                    if val not in (None, ""):
                        break
        dv = Decimal(str(val or "0"))
        out[str(it.pk)] = dv
    return out

def recalc_weights_for_job(job_id) -> int:
    ItemModel = apps.get_model(ITEM_MODEL)

    items = list(
        ItemModel.objects
        .filter(**{f"{ITEM_FK_TO_JOB}_id": job_id})
        .only("pk", ITEM_COST_FIELD)  
    )

    if not items:
        return 0

    costs_map = _items_to_mapping(items)
    weights = calculate_cost_weights(costs_map, decimal_places=1)

    for it in items:
        setattr(it, ITEM_WEIGHT_FIELD, weights.get(str(it.pk), Decimal("0")))

    ItemModel.objects.bulk_update(items, [ITEM_WEIGHT_FIELD])

    return len(items)
