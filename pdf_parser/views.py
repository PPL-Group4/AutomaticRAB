from django.shortcuts import render
from django.http import JsonResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
import tempfile
import os
import threading
import uuid
from decimal import Decimal
from .services.pipeline import parse_pdf_to_dtos

# Template constants
RAB_CONVERTED_TEMPLATE = "rab_converted.html"
PDF_UPLOAD_TEMPLATE = "pdf_upload.html"

# Error message constants
NO_FILE_UPLOADED_MSG = "No file uploaded"

# Global dictionary to store background job results
# Structure: {job_id: {"status": "processing|completed|error", "result": {...}, "error": "..."}}
PDF_JOBS = {}


def _convert_decimals(obj):
    """Recursively convert Decimal objects to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, list):
        return [_convert_decimals(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _convert_decimals(v) for k, v in obj.items()}
    return obj


def _process_pdf_file(job_id, file_path):
    """
    Background thread function to process PDF file.
    Updates PDF_JOBS[job_id] with status and results.
    """
    try:
        # Parse PDF
        rows = parse_pdf_to_dtos(file_path) or []
        rows = _convert_decimals(rows)
        
        # Update job status to completed
        PDF_JOBS[job_id] = {
            "status": "completed",
            "result": {"rows": rows},
            "error": None
        }
        
    except Exception as e:
        PDF_JOBS[job_id] = {
            "status": "error",
            "result": None,
            "error": str(e)
        }
    finally:
        # Clean up temp file
        if file_path and os.path.exists(file_path):
            try:
                os.unlink(file_path)
            except OSError:
                pass


@csrf_exempt  # CSRF exempt: API endpoint for file upload from authenticated frontend
def rab_converted_pdf(request):
    """
    GET: Render template
    POST: Immediately return job_id, start background PDF parsing
    """
    if request.method == "GET":
        return render(request, RAB_CONVERTED_TEMPLATE)

    if request.method == "POST":
        file = request.FILES.get("pdf_file")
        if not file:
            return JsonResponse({"error": NO_FILE_UPLOADED_MSG}, status=400)

        try:
            # Save uploaded file to temp location
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                for chunk in file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name

            # Generate unique job_id
            job_id = str(uuid.uuid4())

            # Initialize job status
            PDF_JOBS[job_id] = {
                "status": "processing",
                "result": None,
                "error": None
            }

            # Start background thread to process PDF
            thread = threading.Thread(
                target=_process_pdf_file,
                args=(job_id, tmp_path),
                daemon=True
            )
            thread.start()

            # Return job_id immediately
            return JsonResponse({"job_id": job_id}, status=202)
            
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return HttpResponseNotAllowed(["GET", "POST"])


@csrf_exempt
def check_pdf_status(request, job_id):
    """
    GET /pdf_parser/check_pdf_status/<job_id>
    Poll endpoint to check status of background PDF parsing job.
    Returns: {"status": "processing|completed|error", "result": {...}, "error": "..."}
    """
    if request.method != "GET":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    job_data = PDF_JOBS.get(job_id)
    
    if not job_data:
        return JsonResponse({"detail": "Job not found"}, status=404)

    response = {
        "status": job_data["status"],
        "result": job_data.get("result"),
        "error": job_data.get("error")
    }

    # If job is completed or errored, optionally clean up from memory
    # (Keep for a while to allow multiple polls, or clean up immediately)
    # if job_data["status"] in ["completed", "error"]:
    #     del PDF_JOBS[job_id]

    return JsonResponse(response)


@csrf_exempt  # CSRF exempt: API endpoint for file upload from authenticated frontend
def parse_pdf_view(request):
    """
    POST: Immediately return job_id, start background PDF parsing.
    Legacy endpoint - consider using rab_converted_pdf instead.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    file = request.FILES.get("file")
    if not file:
        return JsonResponse({"error": NO_FILE_UPLOADED_MSG}, status=400)

    try:
        # Save uploaded file to temp location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            for chunk in file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        # Generate unique job_id
        job_id = str(uuid.uuid4())

        # Initialize job status
        PDF_JOBS[job_id] = {
            "status": "processing",
            "result": None,
            "error": None
        }

        # Start background thread to process PDF
        thread = threading.Thread(
            target=_process_pdf_file,
            args=(job_id, tmp_path),
            daemon=True
        )
        thread.start()

        # Return job_id immediately
        return JsonResponse({"job_id": job_id}, status=202)
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def upload_pdf(request):
    """Render PDF upload page."""
    if request.method == "GET":
        return render(request, PDF_UPLOAD_TEMPLATE)
    return HttpResponseNotAllowed(["GET"])


def preview_pdf(request):
    """Preview PDF endpoint (mock data for testing)."""
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