from __future__ import annotations
from decimal import Decimal
from typing import Dict
from django.http import JsonResponse, Http404
from django.views import View
from django.apps import apps
from django.shortcuts import render

from cost_weight.services.recalc_orchestrator import (
    ITEM_MODEL, JOB_MODEL, ITEM_WEIGHT_FIELD, ITEM_FK_TO_JOB
)
from cost_weight.services.chart_transformer import to_chart_data

Item = apps.get_model(ITEM_MODEL)
Job  = apps.get_model(JOB_MODEL)

def chart_page(request):
    return render(request, "cost_weight/weight_chart.html")

class JobItemsChartDataView(View):
    """Return JSON data untuk chart frontend."""
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

        weights: Dict[str, Decimal] = {
            str(it.pk): getattr(it, ITEM_WEIGHT_FIELD) or Decimal("0")
            for it in items
        }
        names_by_id = {str(it.pk): it.name for it in items}

        dp = int(request.GET.get("dp", "1"))
        sort_desc = request.GET.get("sort", "desc").lower() != "asc"

        data = to_chart_data(weights, names_by_id, decimal_places=dp, sort_desc=sort_desc)
        return JsonResponse({"jobId": job.pk, "items": data})
