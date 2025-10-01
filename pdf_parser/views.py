# pdf_parser/views.py
from django.shortcuts import render
from django.http import JsonResponse, HttpResponseNotAllowed
# pdf_parser/views.py
import tempfile
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .services.pipeline import parse_pdf_to_dtos

@csrf_exempt
def parse_pdf_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    file = request.FILES.get("file")
    if not file:
        return JsonResponse({"error": "No file uploaded"}, status=400)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        for chunk in file.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        # ✅ Already normalized in pipeline
        dtos = parse_pdf_to_dtos(tmp_path)
        return JsonResponse({"rows": dtos}, safe=False)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


def upload_pdf(request):
    if request.method == "GET":
        return render(request, "pdf_upload.html")
    return HttpResponseNotAllowed(["GET"])

def preview_pdf(request):
    if request.method == "POST":
        file = request.FILES.get("pdf_file")
        if not file:
            return JsonResponse({"error": "No file uploaded"}, status=400)

        # 🚧 TODO: hook your PdfSniffer + parser here
        # For now, return mock rows
        rows = [
            {"description": "Item A", "code": "001", "volume": 2, "unit": "m2", "price": 10000, "total_price": 20000},
            {"description": "Item B", "code": "002", "volume": 3, "unit": "m2", "price": 5000, "total_price": 15000},
        ]
        return JsonResponse({"rows": rows})
    return HttpResponseNotAllowed(["POST"])

def rab_converted_pdf(request):
    if request.method == "GET":
        return render(request, "rab_converted.html")
    return HttpResponseNotAllowed(["GET"])
