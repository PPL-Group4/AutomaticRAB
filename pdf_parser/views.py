from django.shortcuts import render
from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
import tempfile
import os
from decimal import Decimal
from .services.pipeline import parse_pdf_to_dtos
import cProfile, pstats, io

# Template constants
RAB_CONVERTED_TEMPLATE = "rab_converted.html"
PDF_UPLOAD_TEMPLATE = "pdf_upload.html"

# Error message constants
NO_FILE_UPLOADED_MSG = "No file uploaded"

class PdfUploadHandler:
    """Template Method for handling PDF upload, temp save, parse, and response."""

    def handle_upload(self, request, parser_fn, enable_profiling=False):
        file = request.FILES.get("pdf_file")
        if not file:
            return JsonResponse({"error": "No file uploaded"}, status=400)

        tmp_path = None
        try:
            # Step 1 — Save uploaded file to temporary path
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                for chunk in file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name

            # Step 2 — Optional profiling
            if enable_profiling:
                profiler = cProfile.Profile()
                profiler.enable()
                rows = parser_fn(tmp_path)
                profiler.disable()

                s = io.StringIO()
                pstats.Stats(profiler, stream=s).sort_stats(pstats.SortKey.TIME).print_stats(15)
                print(s.getvalue())  
            else:
                rows = parser_fn(tmp_path)

            rows = _convert_decimals(rows)
            return JsonResponse({"rows": rows}, status=200)

        except Exception as e:
            return JsonResponse({"error": str(e), "rows": []}, status=500)

        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass


def _convert_decimals(obj):
    """Recursively convert Decimal objects to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, list):
        return [_convert_decimals(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _convert_decimals(v) for k, v in obj.items()}
    return obj


@csrf_exempt  # CSRF exempt: API endpoint for file upload from authenticated frontend
def rab_converted_pdf(request):
    if request.method == "GET":
        return render(request, RAB_CONVERTED_TEMPLATE)

    if request.method == "POST":
        handler = PdfUploadHandler()
        return handler.handle_upload(request, parse_pdf_to_dtos, enable_profiling=True)
    
    return HttpResponseNotAllowed(["GET", "POST"])


@csrf_exempt  # CSRF exempt: API endpoint for file upload from authenticated frontend
def parse_pdf_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    handler = PdfUploadHandler()
    return handler.handle_upload(request, parse_pdf_to_dtos)


def upload_pdf(request):
    if request.method == "GET":
        return render(request, PDF_UPLOAD_TEMPLATE)
    return HttpResponseNotAllowed(["GET"])


def preview_pdf(request):
    if request.method == "POST":
        file = request.FILES.get("pdf_file")
        if not file:
            return JsonResponse({"error": NO_FILE_UPLOADED_MSG}, status=400)

        # return mock rows
        rows = [
            {"description": "Item A", "code": "001", "volume": 2, "unit": "m2", "price": 10000, "total_price": 20000},
            {"description": "Item B", "code": "002", "volume": 3, "unit": "m2", "price": 5000, "total_price": 15000},
        ]
        return JsonResponse({"rows": rows})
    return HttpResponseNotAllowed(["POST"])