from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from target_bid.services import fetch_rab_job_items
@api_view(["GET"])
def fetch_rab_job_items_view(request, rab_id: int):
	"""Return all job items within a RAB, including their unit prices."""

	items = fetch_rab_job_items(rab_id)
	payload = [item.to_dict() for item in items]
	return Response({"rab_id": rab_id, "items": payload}, status=status.HTTP_200_OK)


import json
from decimal import Decimal
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from target_bid.service_utils.proportional_adjustment import ProportionalAdjustmentCalculator
from target_bid.services import (
    RabJobItemService,
    RabJobItemMapper,
    DjangoRabItemRepository,

)
from rencanakan_core.models import RabItem


@csrf_exempt
def adjusted_summary(request):
    """
    Compute the adjusted RAB summary using real RAB items from rencanakan_core.models.RabItem.
    Expects JSON body with:
      - "rab_id" (required)
      - "target_total" (optional, if not provided use default or send from frontend)
    """
    try:
        body = json.loads(request.body or "{}")
        rab_id = body.get("rab_id")
        target_total_raw = body.get("target_total")

        if not rab_id:
            return JsonResponse({"error": "Missing 'rab_id' in request."}, status=400)

        # --- Fetch job items (filtered for adjustable items only) ---
        service = RabJobItemService(DjangoRabItemRepository(), RabJobItemMapper())
        job_items = service.get_items(rab_id=rab_id)

        # --- Compute current total (sum of unlocked items) ---
        current_total = sum(
            (item.total_price or Decimal(0)) for item in job_items
        )
        if current_total <= 0:
            return JsonResponse({"error": "No valid items found or total is zero."}, status=400)

        # --- Target total: frontend may send it or you can default it ---
        if target_total_raw is None:
            # You can later link this to a model or user input
            target_total = Decimal("100000000")  # placeholder default
        else:
            target_total = Decimal(str(target_total_raw))

        # --- Compute proportional factor ---
        factor = ProportionalAdjustmentCalculator.compute(current_total, target_total)
        adjusted_total = (current_total * factor).quantize(Decimal("0.01"))

        data = {
            "rab_id": rab_id,
            "current_total": float(current_total),
            "target_total": float(target_total),
            "factor": float(factor),
            "adjusted_total": float(adjusted_total),
        }
        return JsonResponse(data)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
