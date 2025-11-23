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
from efficiency_recommendations.services.matching_cache_service import (
    MatchingCacheService,
    extract_ahsp_data_from_match
)
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

    # Create cache instance for this request
    cache = MatchingCacheService()

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

    # Check AHSP availability (adds 'in_ahsp' field to each item) - using cache
    items_with_status = check_items_in_ahsp(items, cache=cache)

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


def _get_item_with_reference_price(item, cache: MatchingCacheService):
    """Get item data with AHSP reference price if available."""
    # Skip items with no unit price
    if not item.unit_price or item.unit_price <= 0:
        return None

    try:
        # Use cache instead of direct matching
        match_result = cache.get_or_match(item.name)

        # Extract AHSP data using the helper
        ahsp_data = extract_ahsp_data_from_match(match_result, item.name)
        reference_price = ahsp_data.get('reference_price')

        if reference_price and reference_price > 0:
            return {
                'name': item.name,
                'actual_price': item.unit_price,
                'reference_price': reference_price
            }
    except Exception:
        # Skip items that cause errors
        pass

    return None


def _serialize_deviation(deviation):
    """Convert Decimal values to float for JSON serialization."""
    serialized = deviation.copy()
    decimal_fields = ['deviation_percentage', 'actual_price', 'reference_price']

    for field in decimal_fields:
        if field in serialized:
            serialized[field] = float(serialized[field])

    return serialized


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

    # Create cache instance for this request
    cache = MatchingCacheService()

    # Get items with AHSP reference prices (using cache)
    items_with_prices = []
    for item in job.items.all():
        item_data = _get_item_with_reference_price(item, cache)
        if item_data:
            items_with_prices.append(item_data)

    # Detect deviations (threshold: 10%)
    deviations = detect_price_deviations(
        items_with_prices,
        threshold_percentage=10.0
    )

    # Serialize Decimal values for JSON response
    serialized_deviations = [_serialize_deviation(dev) for dev in deviations]

    return JsonResponse({
        'job_id': job_id,
        'total_items': job.items.count(),
        'items_checked': len(items_with_prices),
        'deviations_found': len(deviations),
        'deviations': serialized_deviations
    })