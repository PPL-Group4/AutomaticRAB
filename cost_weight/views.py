from __future__ import annotations
from typing import Dict
from decimal import Decimal
from django.http import JsonResponse, Http404
from django.views import View
from django.apps import apps
from django.conf import settings

from cost_weight.services.chart_transformer import to_chart_data
from cost_weight.services.recalc_orchestrator import (
    ITEM_MODEL, JOB_MODEL, ITEM_COST_FIELD, ITEM_WEIGHT_FIELD, ITEM_FK_TO_JOB
)

Item = apps.get_model(ITEM_MODEL)
Job  = apps.get_model(JOB_MODEL)

class JobItemsChartDataView(View):
    """
    GET /cost-weight/jobs/<job_id>/chart-data/?dp=1&sort=desc
    Returns: [{"label": "...", "value": 62.5}, ...]
    """
    def get(self, request, job_id: int):
        try:
            job = Job.objects.get(pk=job_id)
        except Job.DoesNotExist:
            raise Http404("Job not found")

        items = (
            Item.objects
            .filter(**{f"{ITEM_FK_TO_JOB}_id": job_id})
            .only("pk", "name", ITEM_WEIGHT_FIELD)
            .order_by("pk")
        )

        # mapping id->Decimal(weight) & id->name
        weights: Dict[str, Decimal] = {
            str(it.pk): getattr(it, ITEM_WEIGHT_FIELD) or Decimal("0")
            for it in items
        }
        names_by_id = {str(it.pk): it.name for it in items}

        dp = int(request.GET.get("dp", "1"))
        sort_desc = request.GET.get("sort", "desc").lower() != "asc"

        data = to_chart_data(weights, names_by_id, decimal_places=dp, sort_desc=sort_desc)
        return JsonResponse({"jobId": job.pk, "items": data})
