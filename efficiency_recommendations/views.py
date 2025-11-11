from django.http import JsonResponse, Http404
from django.views.decorators.http import require_GET
from cost_weight.models import TestJob
from efficiency_recommendations.services.ahsp_availability_checker import (
    check_items_in_ahsp
)
from efficiency_recommendations.services.notification_generator import (
    generate_notifications
)


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

    # Build response
    response_data = {
        'job_id': job_id,
        'total_items': len(items),
        'items_not_in_ahsp': len(notifications),
        'notifications': notifications
    }

    return JsonResponse(response_data)
