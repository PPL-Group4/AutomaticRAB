from __future__ import annotations
from decimal import Decimal
from typing import Dict

from django.http import JsonResponse
from django.views import View
from django.apps import apps
from django.shortcuts import render

from cost_weight.services.recalc_orchestrator import (
    ITEM_MODEL, JOB_MODEL, ITEM_WEIGHT_FIELD, ITEM_FK_TO_JOB
)
from cost_weight.services.chart_transformer import to_chart_data


def _get_models():
    Item = apps.get_model(ITEM_MODEL)
    Job = apps.get_model(JOB_MODEL)
    return Item, Job


def chart_page(request):
    return render(request, "cost_weight/weight_chart.html")


class JobItemsChartDataView(View):
    def get(self, request, job_id: int):
        Item, Job = _get_models()

        _ = Job.objects.filter(pk=job_id).exists()

        qs = (
            Item.objects
            .filter(**{f"{ITEM_FK_TO_JOB}_id": job_id})
            .order_by("pk")
        )

        weights: Dict[str, Decimal] = {}
        names_by_id: Dict[str, str | None] = {}

        for it in qs:
            pk_str = str(it.pk)
            weight_val = getattr(it, ITEM_WEIGHT_FIELD, None)
            try:
                weights[pk_str] = Decimal(str(weight_val)) if weight_val is not None else Decimal("0")
            except Exception:
                weights[pk_str] = Decimal("0")
            names_by_id[pk_str] = getattr(it, "name", None)

        try:
            dp = int(request.GET.get("dp", "1"))
        except ValueError:
            dp = 1
        sort_desc = request.GET.get("sort", "desc").lower() != "asc"

        data = to_chart_data(weights, names_by_id, decimal_places=dp, sort_desc=sort_desc)
        return JsonResponse({"jobId": job_id, "items": data})
