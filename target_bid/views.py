from decimal import Decimal

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from target_bid.repository.rab_item_repo import DjangoRabItemRepository
from target_bid.services.ahs_optimizer import optimize_ahs_price
from target_bid.services.cheaper_price_service import get_cheaper_alternatives
from target_bid.services.rab_job_item_service import RabJobItemService, _DEFAULT_POLICY
from target_bid.utils.rab_job_item_mapper import RabJobItemMapper
from target_bid.validators import validate_target_budget_input


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


@api_view(["POST"])
def optimize_ahs_materials_view(request, ahs_code: str):
    material_limit_raw = request.data.get("material_limit", 2)
    try:
        int(material_limit_raw)
    except (TypeError, ValueError):
        return Response(
            {"material_limit": ["material_limit must be an integer."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    material_limit = 2

    target_input = None
    if "target_budget" in request.data and request.data.get("target_budget") is not None:
        mode = request.data.get("mode")
        if not mode:
            return Response(
                {"mode": ["Mode must be provided when target_budget is set."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            target_input = validate_target_budget_input(request.data.get("target_budget"), mode=mode)
        except ValidationError as exc:
            return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)

    result = optimize_ahs_price(
        ahs_code,
        material_limit=material_limit,
        target_input=target_input,
    )

    if result is None:
        return Response(
            {"detail": "AHS breakdown not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(result, status=status.HTTP_200_OK)
