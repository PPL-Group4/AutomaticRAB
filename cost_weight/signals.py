from __future__ import annotations
from typing import Optional, Set

from django.apps import apps
from django.conf import settings
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from cost_weight.services.recalc_orchestrator import (
    ITEM_MODEL, JOB_MODEL, ITEM_FK_TO_JOB, recalc_weights_for_job
)

JOB_FIELDS_THAT_AFFECT_WEIGHTS: Set[str] = set(getattr(
    settings,
    "COST_WEIGHT_JOB_FIELDS_THAT_AFFECT_WEIGHTS",
    ["name"],
))


def _model_label(obj) -> str:
    return f"{obj._meta.app_label}.{obj._meta.model_name}".lower()


def _is_item_instance(instance) -> bool:
    return _model_label(instance) == ITEM_MODEL.lower()


def _is_job_instance(instance) -> bool:
    return _model_label(instance) == JOB_MODEL.lower()


def _extract_job_id_from_item(instance) -> Optional[int]:
    attr = f"{ITEM_FK_TO_JOB}_id"
    return getattr(instance, attr, None)


@receiver(post_save)
def cw_item_saved(sender, instance, created, update_fields, **kwargs):
    if not _is_item_instance(instance):
        return
    job_id = _extract_job_id_from_item(instance)
    if job_id is None:
        return

    if not created and update_fields:
        from cost_weight.services.recalc_orchestrator import ITEM_COST_FIELD
        if ITEM_COST_FIELD not in set(update_fields):
            return
    recalc_weights_for_job(job_id)


@receiver(post_delete)
def cw_item_deleted(sender, instance, **kwargs):
    if not _is_item_instance(instance):
        return
    job_id = _extract_job_id_from_item(instance)
    if job_id is None:
        return
    recalc_weights_for_job(job_id)


@receiver(post_save)
def cw_job_saved(sender, instance, created, update_fields, **kwargs):
    if not _is_job_instance(instance):
        return
    if update_fields:
        if not JOB_FIELDS_THAT_AFFECT_WEIGHTS.intersection(set(update_fields)):
            return
    job_id = getattr(instance, "pk", None)
    if job_id is None:
        return
    recalc_weights_for_job(job_id)
