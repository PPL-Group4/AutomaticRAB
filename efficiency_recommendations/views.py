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
from efficiency_recommendations.services.price_deviation_detector import (
    detect_price_deviations
)
from automatic_job_matching.service.matching_service import MatchingService
from decimal import Decimal


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
def get_price_deviations(request, job_id):
    """
    API endpoint to detect price deviations from AHSP reference prices.

    GET /efficiency_recommendations/jobs/<job_id>/price-deviations/

    Returns:
        JSON response with deviation details
    """
    try:
        job = TestJob.objects.prefetch_related('items').get(id=job_id)
    except TestJob.DoesNotExist:
        raise Http404("Job not found")

    # Get items with AHSP reference prices
    items_with_prices = []

    for item in job.items.all():
        # Skip items with no unit price
        if not item.unit_price or item.unit_price <= 0:
            continue

        try:
            # Try to find AHSP reference price using MatchingService
            match_result = MatchingService.perform_best_match(item.name)

            # Extract reference price from match result
            reference_price = None

            if match_result:
                # Handle different response formats
                if isinstance(match_result, dict):
                    reference_price = match_result.get('unit_price')
                elif isinstance(match_result, list) and len(match_result) > 0:
                    # Get first match
                    first_match = match_result[0]
                    if isinstance(first_match, dict):
                        reference_price = first_match.get('unit_price')

            # Only add if we found a reference price
            if reference_price and Decimal(str(reference_price)) > 0:
                items_with_prices.append({
                    'name': item.name,
                    'actual_price': item.unit_price,
                    'reference_price': Decimal(str(reference_price))
                })

        except Exception as e:
            # Skip items that cause errors
            continue

    # Detect deviations (threshold: 10%)
    deviations = detect_price_deviations(
        items_with_prices,
        threshold_percentage=10.0
    )

    # Serialize Decimal values for JSON response
    serialized_deviations = []
    for dev in deviations:
        serialized_dev = dev.copy()
        # Convert Decimal to float for JSON serialization
        if 'deviation_percentage' in serialized_dev:
            serialized_dev['deviation_percentage'] = float(
                serialized_dev['deviation_percentage']
            )
        if 'actual_price' in serialized_dev:
            serialized_dev['actual_price'] = float(
                serialized_dev['actual_price']
            )
        if 'reference_price' in serialized_dev:
            serialized_dev['reference_price'] = float(
                serialized_dev['reference_price']
            )
        serialized_deviations.append(serialized_dev)

    return JsonResponse({
        'job_id': job_id,
        'total_items': job.items.count(),
        'items_checked': len(items_with_prices),
        'deviations_found': len(deviations),
        'deviations': serialized_deviations
    })