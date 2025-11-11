from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from target_bid.services import fetch_rab_job_items


@api_view(["GET"])
def fetch_rab_job_items_view(request, rab_id: int):
	"""Return all job items within a RAB, grouped by adjustment status."""

	adjustable, locked, _ = fetch_rab_job_items(
		rab_id, include_non_adjustable=True
	)

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
