from __future__ import annotations
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.apps import apps

from cost_weight.services.recalc_orchestrator import (
    recalc_weights_for_job,
    ITEM_MODEL, JOB_MODEL, ITEM_FK_TO_JOB, ITEM_COST_FIELD
)

Item = apps.get_model(ITEM_MODEL)
Job  = apps.get_model(JOB_MODEL)

# If job-level fields affect weighting, list them here (e.g. ("contingency",))
JOB_FIELDS_THAT_AFFECT_WEIGHTS = tuple()

def _job_id_from_item(instance):
    return getattr(instance, f"{ITEM_FK_TO_JOB}_id", None)

@receiver(post_save, sender=Item, dispatch_uid="cw_item_saved")
def cw_item_saved(sender, instance, created, update_fields, **kwargs):
    if update_fields is not None and len(update_fields) > 0:
        if not created and ITEM_COST_FIELD not in update_fields:
            return
    job_id = _job_id_from_item(instance)
    if job_id:
        recalc_weights_for_job(job_id)

@receiver(post_delete, sender=Item, dispatch_uid="cw_item_deleted")
def cw_item_deleted(sender, instance, **kwargs):
    job_id = _job_id_from_item(instance)
    if job_id:
        recalc_weights_for_job(job_id)

@receiver(post_save, sender=Job, dispatch_uid="cw_job_saved")
def cw_job_saved(sender, instance, update_fields, **kwargs):
    if update_fields is not None and len(update_fields) > 0:
        if not any(f in update_fields for f in JOB_FIELDS_THAT_AFFECT_WEIGHTS):
            return
    recalc_weights_for_job(instance.pk)
