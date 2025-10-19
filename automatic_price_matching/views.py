import json
import logging
from decimal import Decimal, InvalidOperation
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from automatic_price_matching.total_cost import TotalCostCalculator

logger = logging.getLogger(__name__)

@csrf_exempt
@require_POST
def recompute_total_cost(request):
    """Compute total cost in real time using backend rounding rules."""
    try:
        data = json.loads(request.body.decode("utf-8"))
        volume = Decimal(str(data.get("volume", "0")))
        unit_price = Decimal(str(data.get("unit_price", "0")))
        total = TotalCostCalculator.calculate(volume, unit_price)

        # 👇 Add this line to confirm the backend is hit
        print(f"[DEBUG] recompute_total_cost called: volume={volume}, unit_price={unit_price}, total={total}")

        if total is None:
            return JsonResponse({"error": "Invalid numeric input"}, status=400)
        return JsonResponse({"total_cost": str(total)})
    except (InvalidOperation, ValueError, KeyError, json.JSONDecodeError):
        print("[DEBUG] recompute_total_cost encountered invalid input")
        return JsonResponse({"error": "Invalid input"}, status=400)
