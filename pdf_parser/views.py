from django.shortcuts import render
from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
import tempfile
from decimal import Decimal
from .services.pipeline import parse_pdf_to_dtos


def _convert_decimals(obj):
    """Recursively convert Decimal objects to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, list):
        return [_convert_decimals(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _convert_decimals(v) for k, v in obj.items()}
    return obj


@csrf_exempt
def rab_converted_pdf(request):
    if request.method == "GET":
        return render(request, "pdf_parser/rab_converted.html")

    if request.method == "POST":
        file = request.FILES.get("pdf_file")
        if not file:
            return JsonResponse({"error": "No file uploaded"}, status=400)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            for chunk in file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        try:
            rows = parse_pdf_to_dtos(tmp_path) or []
            rows = _convert_decimals(rows)  
            return JsonResponse({"rows": rows}, status=200)
        except Exception:
            return JsonResponse({"rows": []}, status=200)

    return HttpResponseNotAllowed(["GET", "POST"])
