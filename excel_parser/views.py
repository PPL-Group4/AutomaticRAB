from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError

from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from openpyxl import load_workbook

from .services.header_mapper import map_headers, find_header_row
from .services.reader import preview_file
from .services.validators import validate_excel_file

import threading
import uuid
import tempfile
import os

# Template constant
EXCEL_UPLOAD_TEMPLATE = 'excel_upload.html'
RAB_CONVERTED_TEMPLATE = 'rab_converted.html'

# Global dictionary to store background job results
# Structure: {job_id: {"status": "processing|completed|error", "result": {...}, "error": "..."}}
EXCEL_JOBS = {}


def validate_pdf_file(file):
    """Special validator for PDF files."""
    if file.content_type != "application/pdf":
        raise ValidationError("Only .pdf files are allowed.")


@api_view(['POST'])
@parser_classes([MultiPartParser])
def detect_headers(request):
    """
    POST /excel_parser/detect_headers
    body: multipart form-data with 'file'
    """
    try:
        f = request.FILES.get('file')
        if not f:
            return Response({"detail": "file is required"}, status=400)

        try:
            validate_excel_file(f)
        except ValidationError as ve:
            return Response({"detail": str(ve)}, status=400)

        wb = load_workbook(f, data_only=True, read_only=True)
        ws = wb[wb.sheetnames[0]]
        rows = [list(r) for r in ws.iter_rows(values_only=True, min_row=1, max_row=200)]

        hdr_idx = find_header_row(rows)
        if hdr_idx < 0:
            return Response({"detail": "header not found"}, status=422)

        header_row = [str(c or '') for c in rows[hdr_idx]]
        mapping, missing, originals = map_headers(header_row)

        return Response({
            "sheet": ws.title,
            "header_row_index": hdr_idx + 1,  # 1-based index
            "mapping": mapping,
            "originals": originals,
            "missing": missing
        })
        
    except Exception as e:
        # Catch-all error handler - returns JSON instead of crashing
        return Response({"detail": str(e)}, status=500)


def _process_excel_files(job_id, files_dict, session_overrides):
    """
    Background thread function to process Excel files.
    Updates EXCEL_JOBS[job_id] with status and results.
    """
    tmp_paths = []
    try:
        results = {}

        # Process legacy file
        if files_dict.get("legacy_file"):
            tmp_path = _save_temp_file(files_dict["legacy_file"])
            tmp_paths.append(tmp_path)
            validate_excel_file(files_dict["legacy_file"])
            rows = preview_file(tmp_path)
            _apply_preview_overrides(rows, session_overrides)
            results["rows"] = rows

        # Process excel_standard
        if files_dict.get("excel_standard"):
            tmp_path = _save_temp_file(files_dict["excel_standard"])
            tmp_paths.append(tmp_path)
            validate_excel_file(files_dict["excel_standard"])
            excel_rows = preview_file(tmp_path)
            _apply_preview_overrides(excel_rows, session_overrides)
            results["excel_standard"] = excel_rows

        # Process excel_apendo
        if files_dict.get("excel_apendo"):
            tmp_path = _save_temp_file(files_dict["excel_apendo"])
            tmp_paths.append(tmp_path)
            validate_excel_file(files_dict["excel_apendo"])
            apendo_rows = preview_file(tmp_path)
            _apply_preview_overrides(apendo_rows, session_overrides)
            results["excel_apendo"] = apendo_rows

        # Process PDF (validation only, no parsing yet)
        if files_dict.get("pdf_file"):
            validate_pdf_file(files_dict["pdf_file"])
            results["pdf_file"] = {"message": "PDF uploaded successfully (no parser yet)"}

        # Update job status to completed
        EXCEL_JOBS[job_id] = {
            "status": "completed",
            "result": results,
            "error": None
        }

    except ValidationError as ve:
        EXCEL_JOBS[job_id] = {
            "status": "error",
            "result": None,
            "error": str(ve)
        }
    except Exception as e:
        EXCEL_JOBS[job_id] = {
            "status": "error",
            "result": None,
            "error": str(e)
        }
    finally:
        # Clean up temporary files
        for tmp_path in tmp_paths:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass


def _save_temp_file(uploaded_file):
    """Save uploaded file to temporary location and return path."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        for chunk in uploaded_file.chunks():
            tmp.write(chunk)
        return tmp.name


@csrf_exempt  # CSRF exempt: This is an API endpoint called by authenticated frontend
def preview_rows(request):
    """
    POST /excel_parser/preview_rows
    Immediately returns a job_id. Client polls /check_preview_status/<job_id> for results.
    Accepts either:
      - file (legacy, for frontend JS)
      - excel_standard / excel_apendo / pdf_file (extended, from git)
    """
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    try:
        # Collect uploaded files
        files_dict = {
            "legacy_file": request.FILES.get("file"),
            "excel_standard": request.FILES.get("excel_standard"),
            "excel_apendo": request.FILES.get("excel_apendo"),
            "pdf_file": request.FILES.get("pdf_file")
        }

        # Check if at least one file was uploaded
        if not any(files_dict.values()):
            return JsonResponse({"detail": "No file uploaded"}, status=400)

        # Generate unique job_id
        job_id = str(uuid.uuid4())

        # Initialize job status
        EXCEL_JOBS[job_id] = {
            "status": "processing",
            "result": None,
            "error": None
        }

        # Get session overrides
        session_overrides = request.session.get("rab_overrides", {})

        # Start background thread to process files
        thread = threading.Thread(
            target=_process_excel_files,
            args=(job_id, files_dict, session_overrides),
            daemon=True
        )
        thread.start()

        # Return job_id immediately
        return JsonResponse({"job_id": job_id}, status=202)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def check_preview_status(request, job_id):
    """
    GET /excel_parser/check_preview_status/<job_id>
    Poll endpoint to check status of background Excel parsing job.
    Returns: {"status": "processing|completed|error", "result": {...}, "error": "..."}
    """
    if request.method != "GET":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    job_data = EXCEL_JOBS.get(job_id)
    
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
    #     del EXCEL_JOBS[job_id]

    return JsonResponse(response)


def upload_view(request):
    """
    Render upload page for Excel & PDF with format validation.
    """
    if request.method == 'POST':
        try:
            excel_standard = request.FILES.get("excel_standard")
            excel_apendo = request.FILES.get("excel_apendo")
            pdf_file = request.FILES.get("pdf_file")

            if excel_standard:
                validate_excel_file(excel_standard)
                return render(request, EXCEL_UPLOAD_TEMPLATE, {
                    'success': 'Standard Excel uploaded successfully'
                })

            if excel_apendo:
                validate_excel_file(excel_apendo)
                return render(request, EXCEL_UPLOAD_TEMPLATE, {
                    'success': 'APENDO Excel uploaded successfully'
                })

            if pdf_file:
                validate_pdf_file(pdf_file)
                return render(request, EXCEL_UPLOAD_TEMPLATE, {
                    'success': 'PDF uploaded successfully'
                })

            return render(request, EXCEL_UPLOAD_TEMPLATE, {
                'error': 'No file selected'
            }, status=400)

        except ValidationError as ve:
            return render(request, EXCEL_UPLOAD_TEMPLATE, {
                'error': str(ve)
            }, status=400)
        except Exception as e:
            # Catch-all error handler
            return render(request, EXCEL_UPLOAD_TEMPLATE, {
                'error': str(e)
            }, status=500)

    return render(request, EXCEL_UPLOAD_TEMPLATE)


def rab_converted(request):
    """
    Display converted rows in a table with ability to edit.
    This will hit the preview_rows endpoint via AJAX/fetch.
    """
    return render(request, RAB_CONVERTED_TEMPLATE)


def _apply_preview_overrides(rows, overrides):
    """Apply session overrides to parsed rows."""
    if not overrides:
        return
    for row in rows:
        row_key = row.get("row_key")
        if not row_key:
            continue
        data = overrides.get(row_key)
        if not data:
            continue
        volume = data.get("volume")
        if volume is not None:
            row["volume"] = volume
        analysis_code = data.get("analysis_code")
        if analysis_code is not None:
            row["analysis_code"] = analysis_code
        unit_price = data.get("unit_price") or data.get("price")
        if unit_price is not None:
            row["price"] = unit_price
        total_price = data.get("total_price")
        if total_price is not None:
            row["total_price"] = total_price