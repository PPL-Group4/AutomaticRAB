from __future__ import annotations
from decimal import Decimal
from typing import Dict, Iterable
from django.db import transaction
from django.apps import apps
from django.conf import settings
from cost_weight.services.cost_weight_calc import calculate_cost_weights

# Configurable references to populating model 
ITEM_MODEL = getattr(settings, "COST_WEIGHT_ITEM_MODEL", "estimator.JobItem")
JOB_MODEL  = getattr(settings, "COST_WEIGHT_JOB_MODEL",  "estimator.Job")
ITEM_COST_FIELD   = getattr(settings, "COST_WEIGHT_ITEM_COST_FIELD", "cost")
ITEM_WEIGHT_FIELD = getattr(settings, "COST_WEIGHT_ITEM_WEIGHT_FIELD", "weight_pct")
ITEM_FK_TO_JOB    = getattr(settings, "COST_WEIGHT_ITEM_FK_TO_JOB", "job")

def _get_models():
    Item = apps.get_model(ITEM_MODEL)
    Job = apps.get_model(JOB_MODEL)
    return Item, Job

def _items_for_job(job_id) -> Iterable:
    Item, _ = _get_models()
    return (
        Item.objects
        .select_for_update()
        .filter(**{f"{ITEM_FK_TO_JOB}_id": job_id})
        .order_by("pk")
    )

def _items_to_mapping(items) -> Dict[str, Decimal]:
    return {str(it.pk): getattr(it, ITEM_COST_FIELD) or Decimal("0") for it in items}

@transaction.atomic
def recalc_weights_for_job(job_id: int, *, decimal_places: int = 2) -> int:
    """
    Recalculate & save cost weight (%) for all items in a given job.
    Called automatically after population is complete.
    """
    Item, _ = _get_models()
    items = list(_items_for_job(job_id))
    if not items:
        return 0

    mapping = _items_to_mapping(items)
    weights = calculate_cost_weights(mapping, decimal_places=decimal_places)

    for it in items:
        setattr(it, ITEM_WEIGHT_FIELD, weights[str(it.pk)])
    Item.objects.bulk_update(items, [ITEM_WEIGHT_FIELD])
    return len(items)
