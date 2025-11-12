from django.http import JsonResponse, Http404
from django.views.decorators.http import require_GET
from cost_weight.models import TestJob
from efficiency_recommendations.services.ahsp_availability_checker import (
    check_items_in_ahsp
)
from efficiency_recommendations.services.notification_generator import (
    generate_notifications
)
from efficiency_recommendations.services.warning_indicator_builder import build_indicator
from decimal import Decimal
from . import items_with_status
from . import items


@require_GET
def get_job_notifications(request, job_id):
    """
    API endpoint to get notifications for items not found in AHSP database.

    GET /efficiency_recommendations/jobs/<job_id>/notifications/

    Returns:
        JSON response with structure:
        {
            'job_id': int,
            'total_items': int,
            'items_not_in_ahsp': int,
            'notifications': [
                {
                    'type': 'NOT_IN_DATABASE',
                    'item_name': str,
                    'message': str
                }
            ]
        }
    """
    # Get job or return 404
    try:
        job = TestJob.objects.prefetch_related('items').get(id=job_id)
    except TestJob.DoesNotExist:
        raise Http404("Job not found")

    # Get all items for the job
    items_queryset = job.items.all()

    # Convert queryset to list of dicts for service layer
    items = [
        {
            'name': item.name,
            'cost': item.cost,
            'weight_pct': item.weight_pct,
            'quantity': item.quantity,
            'unit_price': item.unit_price
        }
        for item in items_queryset
    ]

    # Check AHSP availability (adds 'in_ahsp' field to each item)
    items_with_status = check_items_in_ahsp(items)

    # Generate notifications for items not in AHSP
    notifications = generate_notifications(items_with_status)

    # Aggregate/indicator fields
    total_items = len(items)
    warning_count = len(notifications)
    indicator = build_indicator(total_items, warning_count)

    # Build response
    response_data = {
        'job_id': job_id,
        'total_items': total_items,
        'items_not_in_ahsp': warning_count,
        'notifications': notifications,
        'has_warnings': warning_count > 0,
        'warning_count': warning_count,
        'warning_ratio': indicator['ratio'],
        'indicator': {
            'level': indicator['level'],
            'label': indicator['label'],
            'badge_color': indicator['badge_color'],
            'icon': indicator['icon'],
        }
    }

    return JsonResponse(response_data)

def _build_warning_indicator(total_items: int, warning_count: int):
    if total_items <= 0:
        ratio = 0.0
    else:
        ratio = float(Decimal(warning_count) / Decimal(total_items))

    if warning_count == 0:
        return {
            "has_warnings": False,
            "warning_count": 0,
            "warning_ratio": 0.0,
            "indicator": {
                "level": "NONE",
                "badge_color": "#D1D5DB",   # gray-300
                "icon": "check-circle",
                "label": "No warnings"
            }
        }

    if ratio > 0.5:
        level = "CRITICAL"; color = "#DC2626"; icon = "x-octagon"
    elif ratio > 0.2:
        level = "WARN";     color = "#F59E0B"; icon = "alert-triangle"
    else:
        level = "INFO";     color = "#2563EB"; icon = "info"

    return {
        "has_warnings": True,
        "warning_count": warning_count,
        "warning_ratio": ratio,
        "indicator": {
            "level": level,
            "badge_color": color,
            "icon": icon,
            "label": f"{warning_count} warnings"
        }
    }

@require_GET
def get_job_notifications(request, job_id):
    ...
    notifications = generate_notifications(items_with_status)

    indicator = _build_warning_indicator(len(items), len(notifications))

    response_data = {
        'job_id': job_id,
        'total_items': len(items),
        'items_not_in_ahsp': len(notifications),
        'notifications': notifications,
        'has_warnings': indicator['has_warnings'],
        'warning_count': indicator['warning_count'],
        'warning_ratio': indicator['warning_ratio'],
        'indicator': indicator['indicator'],
    }

    return JsonResponse(response_data)