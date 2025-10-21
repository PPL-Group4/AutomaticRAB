from __future__ import annotations
from decimal import Decimal
from typing import Dict

from django.http import JsonResponse
from django.views import View
from django.apps import apps
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse, Http404
from django.views.decorators.http import require_GET

from cost_weight.services.chart_transformer import to_chart_data
from cost_weight.services.chart_render import render_chart_bytes

from cost_weight.services.recalc_orchestrator import (
    ITEM_MODEL, JOB_MODEL, ITEM_COST_FIELD, ITEM_WEIGHT_FIELD, ITEM_FK_TO_JOB
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

@require_GET
def chart_export(request, job_id: int):
    fmt = request.GET.get("format", "png").lower()
    if fmt not in {"png", "pdf"}:
        raise Http404("Unsupported format")

    try:
        dp = int(request.GET.get("dp", "1"))
        dp = max(0, min(4, dp))
    except ValueError:
        dp = 1

    Job = apps.get_model(JOB_MODEL)
    Item = apps.get_model(ITEM_MODEL)

    try:
        job = Job.objects.get(pk=job_id)
    except Job.DoesNotExist:
        raise Http404("Job not found")

    qs = Item.objects.filter(**{ITEM_FK_TO_JOB: job}).values("id", "name", ITEM_WEIGHT_FIELD)
    weights = {str(r["id"]): Decimal(r[ITEM_WEIGHT_FIELD]) for r in qs}
    names = {str(r["id"]): r["name"] or str(r["id"]) for r in qs}

    items = to_chart_data(weights, names, sort_desc=True, decimal_places=dp)

    title = f"Cost Weight Chart — Job #{job.pk} ({job.name})" if getattr(job, "name", None) else f"Cost Weight Chart — Job #{job.pk}"

    payload = render_chart_bytes(items, title=title, decimal_places=dp, fmt=fmt)

    content_type = {"png": "image/png", "pdf": "application/pdf", "svg": "image/svg+xml"}[fmt]
    filename = f"job-{job.pk}-cost-weight.{fmt}"
    resp = HttpResponse(payload, content_type=content_type)
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp