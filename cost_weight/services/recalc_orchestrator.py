from __future__ import annotations
from decimal import Decimal
from typing import Dict, Protocol
from django.db import transaction
from django.apps import apps

from cost_weight.services.cost_weight_calc import calculate_cost_weights

ITEM_MODEL = "estimator.JobItem"
JOB_MODEL = "estimator.Job"
ITEM_COST_FIELD = "cost"
ITEM_WEIGHT_FIELD = "weight_pct"
ITEM_FK_TO_JOB = "job"


class JobItemRepository(Protocol):
    def get_costs_for_job_locked(self, job_id: int) -> Dict[str, Decimal]:
        ...

    def apply_weights_for_job(self, job_id: int, weights: Dict[str, Decimal]) -> int:
        ...

def _get_models():
    Item = apps.get_model(ITEM_MODEL)
    Job = apps.get_model(JOB_MODEL)
    return Item, Job


class DjangoJobItemRepository(JobItemRepository):

    def __init__(self) -> None:
        self.Item, self.Job = _get_models()
        self._locked_items = []  

    def get_costs_for_job_locked(self, job_id: int) -> Dict[str, Decimal]:
        qs = (
            self.Item.objects
            .select_for_update()
            .filter(**{f"{ITEM_FK_TO_JOB}_id": job_id})
            .order_by("pk")
        )
        self._locked_items = list(qs)

        return {
            str(it.pk): getattr(it, ITEM_COST_FIELD) or Decimal("0")
            for it in self._locked_items
        }

    def apply_weights_for_job(self, job_id: int, weights: Dict[str, Decimal]) -> int:
        items = self._locked_items
        if not items:
            return 0

        for it in items:
            setattr(it, ITEM_WEIGHT_FIELD, weights[str(it.pk)])

        self.Item.objects.bulk_update(items, [ITEM_WEIGHT_FIELD])
        return len(items)

def recalc_weights_for_job_core(
    job_id: int,
    repo: JobItemRepository,
    *,
    decimal_places: int = 2,
) -> int:

    mapping = repo.get_costs_for_job_locked(job_id)
    if not mapping:
        return 0

    weights = calculate_cost_weights(mapping, decimal_places=decimal_places)  # pk -> pct
    updated_count = repo.apply_weights_for_job(job_id, weights)
    return updated_count


@transaction.atomic
def recalc_weights_for_job(job_id: int, *, decimal_places: int = 2) -> int:

    repo = DjangoJobItemRepository()
    return recalc_weights_for_job_core(
        job_id=job_id,
        repo=repo,
        decimal_places=decimal_places,
    )