from decimal import Decimal

from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
from decimal import Decimal
import tempfile
import os

from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from celery.result import AsyncResult

from cost_weight.models import TestItem, TestJob

from .services.header_mapper import find_header_row, map_headers
from .services.reader import preview_file
from .services.validators import validate_excel_file
from cost_weight.models import TestJob, TestItem
from .tasks import process_excel_file_task

# Template constant
EXCEL_UPLOAD_TEMPLATE = 'excel_upload.html'
RAB_CONVERTED_TEMPLATE = 'rab_converted.html'


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


@csrf_exempt  # CSRF exempt: This is an API endpoint called by authenticated frontend
def preview_rows(request):
    """
    POST /excel_parser/preview_rows
    Accepts either:
      - file (legacy, for frontend JS)
      - excel_standard / excel_apendo / pdf_file (extended, from git)
    
    Also creates a TestJob for cost weight analysis and returns job_id
    """
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    try:
        # legacy (frontend expects 'file')
        legacy_file = request.FILES.get("file")

        # extended (multiple file support)
        excel_standard = request.FILES.get("excel_standard")
        excel_apendo = request.FILES.get("excel_apendo")
        pdf_file = request.FILES.get("pdf_file")

        results = {}
        session_overrides = request.session.get("rab_overrides", {})

        # === Legacy path ===
        if legacy_file:
            validate_excel_file(legacy_file)
            rows = preview_file(legacy_file)
            _apply_preview_overrides(rows, session_overrides)
            
            # Create TestJob from rows
            job = _create_test_job_from_rows(rows, legacy_file.name)
            
            results["rows"] = rows
            results["job_id"] = job.id

        # === Extended path ===
        if excel_standard:
            validate_excel_file(excel_standard)
            excel_rows = preview_file(excel_standard)
            _apply_preview_overrides(excel_rows, session_overrides)
            
            # Create TestJob from rows
            job = _create_test_job_from_rows(excel_rows, excel_standard.name)
            
            results["excel_standard"] = excel_rows
            results["job_id"] = job.id
            excel_rows = preview_file(excel_standard)
            _apply_preview_overrides(excel_rows, session_overrides)
            results["excel_standard"] = excel_rows

        if excel_apendo:
            validate_excel_file(excel_apendo)
            apendo_rows = preview_file(excel_apendo)
            _apply_preview_overrides(apendo_rows, session_overrides)
            results["excel_apendo"] = apendo_rows

        if pdf_file:
            validate_pdf_file(pdf_file)
            results["pdf_file"] = {"message": "PDF uploaded successfully (no parser yet)"}

        if not results:
            return JsonResponse({"detail": "No file uploaded"}, status=400)

        return JsonResponse(results, safe=False)

    except ValidationError as ve:
        return JsonResponse({"error": str(ve)}, status=400)
    except Exception as e:
        # Catch-all error handler - returns JSON instead of crashing
        return JsonResponse({"error": str(e)}, status=500)


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


@api_view(['POST'])
@parser_classes([MultiPartParser])
def preview_rows_async(request):
    """
    POST /excel_parser/preview_rows_async
    Accepts file upload and processes it asynchronously.
    Returns task_id for status checking.
    """
    try:
        # Get the uploaded file
        legacy_file = request.FILES.get("file")
        excel_standard = request.FILES.get("excel_standard")
        excel_apendo = request.FILES.get("excel_apendo")
        
        if not (legacy_file or excel_standard or excel_apendo):
            return Response({"detail": "No file uploaded"}, status=400)
        
        # Determine which file to process and its type
        file_to_process = None
        file_type = None
        
        if legacy_file:
            file_to_process = legacy_file
            file_type = 'legacy'
        elif excel_standard:
            file_to_process = excel_standard
            file_type = 'standard'
        elif excel_apendo:
            file_to_process = excel_apendo
            file_type = 'apendo'
        
        # Validate the file
        try:
            validate_excel_file(file_to_process)
        except ValidationError as ve:
            return Response({"detail": str(ve)}, status=400)
        
        # Save file to temp location
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            for chunk in file_to_process.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name
        
        # Submit task to Celery
        task = process_excel_file_task.delay(tmp_path, file_to_process.name, file_type)
        
        return Response({
            "task_id": task.id,
            "status": "processing",
            "message": "File is being processed. Use task_id to check status."
        }, status=202)
        
    except Exception as e:
        return Response({"detail": str(e)}, status=500)


@api_view(['GET'])
def task_status(request, task_id):
    """
    GET /excel_parser/task_status/<task_id>
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

def _apply_preview_overrides(rows, overrides):
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


def _create_test_job_from_rows(rows, filename="Uploaded File"):
    """
    Create TestJob and TestItems from parsed rows
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