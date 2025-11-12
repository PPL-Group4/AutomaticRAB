from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from decimal import Decimal

from target_bid.services.cheaper_price_service import get_cheaper_alternatives
from target_bid.repository.rab_item_repo import DjangoRabItemRepository
from target_bid.utils.rab_job_item_mapper import RabJobItemMapper
from target_bid.services.rab_job_item_service import RabJobItemService, _DEFAULT_POLICY


@api_view(["GET"])
def fetch_rab_job_items_view(request, rab_id: int):
    """Return all job items within a RAB, grouped by adjustment status."""
    service = RabJobItemService(
        repository=DjangoRabItemRepository(),
        mapper=RabJobItemMapper(),
        non_adjustable_policy=_DEFAULT_POLICY,
    )

    adjustable, locked, _ = service.get_items_with_classification(rab_id)

    def _serialize(item, status_label: str) -> dict:
        data = item.to_dict()
        data["adjustment_status"] = status_label
        return data

    payload = [_serialize(item, "adjustable") for item in adjustable]
    locked_payload = [_serialize(item, "locked") for item in locked]

    return Response(
        {"rab_id": rab_id, "items": payload, "locked_items": locked_payload},
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
def cheaper_suggestions_view(request):
    name = request.GET.get("name", "")
    unit = request.GET.get("unit", "")
    price = Decimal(request.GET.get("price", "0"))
    results = get_cheaper_alternatives(name, unit, price)
    return Response(results)
