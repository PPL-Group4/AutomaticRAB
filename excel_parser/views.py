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
    f = request.FILES.get('file')
    if not f:
        return Response({"detail": "file is required"}, status=400)

    try:
        validate_excel_file(f)
    except ValidationError as ve:
        return Response({"detail": str(ve)}, status=400)

    wb = load_workbook(f, data_only=True, read_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = [[c for c in r] for r in ws.iter_rows(values_only=True, min_row=1, max_row=200)]

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


@csrf_exempt
def preview_rows(request):
    """
    POST /excel_parser/preview_rows
    Accepts either:
      - file (legacy, for frontend JS)
      - excel_standard / excel_apendo / pdf_file (extended, from git)
    """
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    # legacy (frontend expects 'file')
    legacy_file = request.FILES.get("file")

    # extended (multiple file support)
    excel_standard = request.FILES.get("excel_standard")
    excel_apendo = request.FILES.get("excel_apendo")
    pdf_file = request.FILES.get("pdf_file")

    try:
        results = {}
        session_overrides = request.session.get("rab_overrides", {})

        # === Legacy path ===
        if legacy_file:
            validate_excel_file(legacy_file)
            rows = preview_file(legacy_file)
            _apply_preview_overrides(rows, session_overrides)
            results["rows"] = rows

        # === Extended path ===
        if excel_standard:
            validate_excel_file(excel_standard)
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
        return JsonResponse({"error": str(e)}, status=500)


def upload_view(request):
    """
    Render upload page for Excel & PDF with format validation.
    """
    if request.method == 'POST':
        excel_standard = request.FILES.get("excel_standard")
        excel_apendo = request.FILES.get("excel_apendo")
        pdf_file = request.FILES.get("pdf_file")

        try:
            if excel_standard:
                validate_excel_file(excel_standard)
                return render(request, 'excel_upload.html', {
                    'success': 'Standard Excel uploaded successfully'
                })

            if excel_apendo:
                validate_excel_file(excel_apendo)
                return render(request, 'excel_upload.html', {
                    'success': 'APENDO Excel uploaded successfully'
                })

            if pdf_file:
                validate_pdf_file(pdf_file)
                return render(request, 'excel_upload.html', {
                    'success': 'PDF uploaded successfully'
                })

            return render(request, 'excel_upload.html', {
                'error': 'No file selected'
            }, status=400)

        except ValidationError as ve:
            return render(request, 'excel_upload.html', {
                'error': str(ve)
            }, status=400)

    return render(request, 'excel_upload.html')


def rab_converted(request):
    """
    Display converted rows in a table with ability to edit.
    This will hit the preview_rows endpoint via AJAX/fetch.
    """
    return render(request, "rab_converted.html")


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


from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from decimal import Decimal
import json
from target_bid.service_utils.budgetservice import adjust_unit_prices_preserving_volume, TargetBudgetConverter
from target_bid.validators import TargetBudgetInput


@require_http_methods(["POST"])
def apply_adjustment(request):
    try:
        data = json.loads(request.body)
        mode = data.get("mode")
        value = Decimal(str(data.get("value", 0)))
        current_total = Decimal(str(data.get("current_total", 0)))

        if current_total <= 0:
            return JsonResponse({"error": "Current total must be positive"}, status=400)

        # Calculate adjustment factor
        if mode == "percentage":
            reduction_pct = abs(value)
            adjustment_factor = Decimal("1") - (reduction_pct / Decimal("100"))
            target_total = current_total * adjustment_factor
        else:
            target_input = TargetBudgetInput(mode=mode, value=value)
            target_total = TargetBudgetConverter.to_nominal(target_input, current_total)
            adjustment_factor = target_total / current_total


        original_data = request.session.get("rab_overrides", {})




        # --- Rebuild fresh items every apply (no cascading) ---
        class Item:
            def __init__(self, row_key, volume, unit_price):
                self.row_key = row_key
                self.volume = Decimal(str(volume))
                self.unit_price = Decimal(str(unit_price))
                self.total_price = self.volume * self.unit_price

        items = [
            Item(k, v.get("volume", 0), v.get("unit_price", 0) or v.get("price", 0))
            for k, v in original_data.items()
        ]

        # --- Apply adjustment once ---
        for item in items:
            item.unit_price = item.unit_price * adjustment_factor
            item.total_price = item.volume * item.unit_price

        # Update session with adjusted values
        session_overrides = request.session.get("rab_overrides", {})
        for item in items:
            session_overrides[item.row_key]["unit_price"] = float(item.unit_price)
            session_overrides[item.row_key]["price"] = float(item.unit_price)
            session_overrides[item.row_key]["total_price"] = float(item.total_price)

        request.session["rab_overrides"] = session_overrides
        request.session.modified = True

        adjusted_total = sum(item.total_price for item in items)

        return JsonResponse({
            "original_total": float(current_total),
            "target_total": float(target_total),
            "adjustment_factor": float(adjustment_factor),
            "adjusted_total": float(adjusted_total),
            "adjusted_rows": [
                {
                    "row_key": item.row_key,
                    "unit_price": float(item.unit_price),
                    "total_price": float(item.total_price)
                }
                for item in items
            ]
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
