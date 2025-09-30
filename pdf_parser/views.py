# pdf_parser/views.py
from django.shortcuts import render
from django.http import JsonResponse, HttpResponseNotAllowed

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
