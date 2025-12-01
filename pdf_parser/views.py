from django.shortcuts import render
from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
import tempfile
import os
from decimal import Decimal
from .services.pipeline import parse_pdf_to_dtos
from cost_weight.models import TestJob, TestItem
import cProfile, pstats, io

from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from celery.result import AsyncResult
from .tasks import process_pdf_file_task

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

            # Create TestJob from parsed rows
            job = _create_test_job_from_rows(rows, file.name)

            rows = _convert_decimals(rows)
            return JsonResponse({"rows": rows, "job_id": job.id}, status=200)

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

    if isinstance(obj, dict):
        new = {}
        for k, v in obj.items():
            if isinstance(v, (int, float, str, bool, type(None))):
                new[k] = v
            elif isinstance(v, Decimal):
                new[k] = float(v)
            elif isinstance(v, list):
                new[k] = [_convert_decimals(i) for i in v]
            elif isinstance(v, dict):
                new[k] = _convert_decimals(v)
            else:
                # fallback for match objects or unusual data types
                new[k] = str(v)
        return new

    if isinstance(obj, list):
        return [_convert_decimals(i) for i in obj]

    # primitive types
    return obj


def _create_test_job_from_rows(rows, filename="Uploaded PDF"):
    """
    Create TestJob and TestItems from parsed PDF rows
    Returns the created TestJob instance
    """
    # Create job
    job = TestJob.objects.create(name=f"RAB - {filename}")

    # Create items from rows (skip section headers)
    for row in rows:
        # Skip section/category rows
        if row.get("is_section") or row.get("job_match_status") == "skipped":
            continue

        description = row.get("description", "Unknown Item")
        if not description or description.strip() == "":
            continue

        # Parse quantity and price
        try:
            quantity = Decimal(str(row.get("volume", 0)))
            if quantity <= 0:
                quantity = Decimal("1")
        except (ValueError, TypeError, KeyError):
            quantity = Decimal("1")

        try:
            unit_price = Decimal(str(row.get("price", 0)))
            if unit_price < 0:
                unit_price = Decimal("0")
        except (ValueError, TypeError, KeyError):
            unit_price = Decimal("0")

        # Create item
        TestItem.objects.create(
            job=job,
            name=description,
            quantity=quantity,
            unit_price=unit_price
        )

    # Calculate totals and weights
    job.calculate_totals()

    return job


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


@api_view(['POST'])
@parser_classes([MultiPartParser])
def parse_pdf_async(request):
    """
    POST /pdf_parser/parse_pdf_async
    Accepts PDF file upload and processes it asynchronously.
    Returns task_id for status checking.
    """
    try:
        pdf_file = request.FILES.get("pdf_file")

        if not pdf_file:
            return Response({"detail": "No PDF file uploaded"}, status=400)

        # Validate file type
        if pdf_file.content_type != "application/pdf":
            return Response({"detail": "Only .pdf files are allowed."}, status=400)

        # Save file to temp location
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            for chunk in pdf_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        # Submit task to Celery
        task = process_pdf_file_task.delay(tmp_path, pdf_file.name)

        return Response({
            "task_id": task.id,
            "status": "processing",
            "message": "PDF is being processed. Use task_id to check status."
        }, status=202)

    except Exception as e:
        return Response({"detail": str(e)}, status=500)


@api_view(['GET'])
def task_status(request, task_id):
    """
    GET /pdf_parser/task_status/<task_id>
    Check the status of an async task.
    """
    try:
        task = AsyncResult(task_id)

        if task.state == 'PENDING':
            response = {
                'state': task.state,
                'status': 'Task is waiting to be processed...'
            }
        elif task.state == 'PROCESSING':
            response = {
                'state': task.state,
                'status': task.info.get('status', 'Processing...'),
            }
        elif task.state == 'SUCCESS':
            response = {
                'state': task.state,
                'result': task.result,
                'status': 'completed'
            }
        elif task.state == 'FAILURE':
            response = {
                'state': task.state,
                'status': str(task.info),
                'error': str(task.info)
            }
        else:
            response = {
                'state': task.state,
                'status': str(task.info)
            }

        return Response(response)

    except Exception as e:
        return Response({"error": str(e)}, status=500)