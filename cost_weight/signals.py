from __future__ import annotations
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.apps import apps
from django.conf import settings

from cost_weight.services.recalc_orchestrator import (
    recalc_weights_for_job,
    ITEM_MODEL, JOB_MODEL, ITEM_FK_TO_JOB, ITEM_COST_FIELD
)

# If job-level fields affect weighting, list them here (e.g. ("contingency",))
JOB_FIELDS_THAT_AFFECT_WEIGHTS = tuple()

def _safe_get_model(label: str):
    try:
        return apps.get_model(label)
    except LookupError:
        return None

def _job_id_from_item(instance):
    return getattr(instance, f"{ITEM_FK_TO_JOB}_id", None)

@receiver(post_save, dispatch_uid="cw_item_saved")
def cw_item_saved(sender, instance, created, update_fields=None, **kwargs):
    # Only handle signals for the intended Item model
    Item = _safe_get_model(ITEM_MODEL)
    if Item is None or sender is not Item:
        return

    if update_fields:
        if not created and ITEM_COST_FIELD not in update_fields:
            return

    job_id = _job_id_from_item(instance)
    if job_id:
        recalc_weights_for_job(job_id)

@receiver(post_delete, dispatch_uid="cw_item_deleted")
def cw_item_deleted(sender, instance, **kwargs):
    Item = _safe_get_model(ITEM_MODEL)
    if Item is None or sender is not Item:
        return

    job_id = _job_id_from_item(instance)
    if job_id:
        recalc_weights_for_job(job_id)

@receiver(post_save, dispatch_uid="cw_job_saved")
def cw_job_saved(sender, instance, update_fields=None, **kwargs):
    Job = _safe_get_model(JOB_MODEL)
    if Job is None or sender is not Job:
        return

    if update_fields:
        if not any(f in update_fields for f in JOB_FIELDS_THAT_AFFECT_WEIGHTS):
            return

    recalc_weights_for_job(instance.pk)
