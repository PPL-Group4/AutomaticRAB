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
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator

from cost_weight.services.recalc_orchestrator import (
    ITEM_MODEL, JOB_MODEL, ITEM_COST_FIELD, ITEM_WEIGHT_FIELD, ITEM_FK_TO_JOB
)
from cost_weight.services.chart_transformer import to_chart_data
from cost_weight.models import TestJob, TestItem


@require_POST
def recalc_job_weights(request, job_id: int):
    from cost_weight.services.recalc_orchestrator import recalc_weights_for_job
    try:
        updated = recalc_weights_for_job(job_id)
        return JsonResponse({"jobId": job_id, "updated": updated})
    except Exception:
        return JsonResponse({"error": "recalc failed"}, status=500)


def upload_excel_view(request):
    """View to upload and parse Excel RAB file"""
    if request.method == 'POST' and request.FILES.get('excel_file'):
        from cost_weight.services.excel_parser import create_job_from_excel
        
        excel_file = request.FILES['excel_file']
        job_name = request.POST.get('job_name', '')
        
        try:
            # Parse and create job
            job = create_job_from_excel(excel_file, job_name)
            
            # Redirect to analysis page
            return JsonResponse({
                'success': True,
                'job_id': job.id,
                'redirect_url': f'/cost_weight/analysis/{job.id}/'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    
    return render(request, 'cost_weight/upload_excel.html')


def cost_weight_analysis_view(request, job_id: int):
    """View to display cost weight analysis with pie chart"""
    try:
        job = TestJob.objects.prefetch_related('items').get(id=job_id)
        items = job.items.all().order_by('-cost')
        
        # Prepare chart data
        chart_data = {
            'labels': [item.name for item in items],
            'costs': [float(item.cost) for item in items],
            'weights': [float(item.weight_pct) for item in items],
            'colors': [
                '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', 
                '#9966FF', '#FF9F40', '#FF6384', '#C9CBCF',
                '#E7E9ED', '#FFA1B5'
            ]
        }
        
        context = {
            'job': job,
            'items': items,
            'chart_data': chart_data,
            'total_items': items.count()
        }
        
        return render(request, 'cost_weight/analysis.html', context)
    except TestJob.DoesNotExist:
        return HttpResponse('Job not found', status=404)

def _get_models():
    Item = apps.get_model(ITEM_MODEL)
    Job = apps.get_model(JOB_MODEL)
    return Item, Job

def chart_page(request, job_id: int):
    return render(request, "cost_weight/weight_chart.html", {"job_id": job_id})

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