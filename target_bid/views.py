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
