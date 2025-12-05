from django.shortcuts import render
from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
import tempfile
import os
from decimal import Decimal
import sentry_sdk
from .services.pipeline import parse_pdf_to_dtos
from cost_weight.models import TestJob, TestItem
import cProfile, pstats, io

# Template constants
RAB_CONVERTED_TEMPLATE = "rab_converted.html"
PDF_UPLOAD_TEMPLATE = "pdf_upload.html"

# Error message constants
NO_FILE_UPLOADED_MSG = "No file uploaded"

class PdfUploadHandler:
    """Template Method for handling PDF upload, temp save, parse, and response."""

    def handle_upload(self, request, parser_fn, enable_profiling=False):
        with sentry_sdk.start_transaction(op="file_upload", name="pdf_upload"):
            file = request.FILES.get("pdf_file")
            if not file:
                sentry_sdk.capture_message("PDF upload failed: No file", level="warning")
                return JsonResponse({"error": "No file uploaded"}, status=400)
            
            sentry_sdk.set_context("file_info", {
                "filename": file.name,
                "size": file.size,
                "content_type": getattr(file, 'content_type', 'unknown')
            })

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
    if isinstance(obj, list):
        return [_convert_decimals(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _convert_decimals(v) for k, v in obj.items()}
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

    with sentry_sdk.start_transaction(op="file_upload", name="parse_pdf_view"):
        try:
            file = request.FILES.get("pdf_file")
            if file:
                sentry_sdk.set_context("file_info", {
                    "filename": file.name,
                    "size": file.size,
                    "content_type": file.content_type
                })
            
            handler = PdfUploadHandler()
            response = handler.handle_upload(request, parse_pdf_to_dtos)
            
            # Log successful parse if status is 200
            if response.status_code == 200:
                sentry_sdk.capture_message(
                    f"PDF parse success: {file.name if file else 'unknown'}",
                    level="info",
                    extras={
                        "filename": file.name if file else None,
                        "file_size": file.size if file else None
                    }
                )
            
            return response
        except Exception as e:
            sentry_sdk.capture_exception(e, extras={
                "error_type": "pdf_parse_failure",
                "filename": request.FILES.get("pdf_file").name if request.FILES.get("pdf_file") else None
            })
            return JsonResponse({"error": str(e)}, status=500)


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
    with sentry_sdk.start_transaction(op="file_upload.async", name="parse_pdf_async"):
        pdf_file = request.FILES.get("pdf_file")

        if not pdf_file:
            sentry_sdk.capture_message(
                "PDF upload failed: No file provided",
                level="warning"
            )
            return Response({"detail": "No PDF file uploaded"}, status=400)

        # Validate file type
        if pdf_file.content_type != "application/pdf":
            sentry_sdk.capture_message(
                f"PDF upload failed: Invalid file type {pdf_file.content_type}",
                level="warning",
                extras={"filename": pdf_file.name, "content_type": pdf_file.content_type}
            )
            return Response({"detail": "Only .pdf files are allowed."}, status=400)

        sentry_sdk.set_context("file_info", {
            "filename": pdf_file.name,
            "size": pdf_file.size,
            "content_type": pdf_file.content_type
        })

        try:
            # Save file to temp location
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                for chunk in pdf_file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name

            # Submit task to Celery
            task = process_pdf_file_task.delay(tmp_path, pdf_file.name)

            sentry_sdk.capture_message(
                f"PDF parse task queued: {pdf_file.name}",
                level="info",
                extras={
                    "task_id": task.id,
                    "filename": pdf_file.name,
                    "file_size": pdf_file.size
                }
            )

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