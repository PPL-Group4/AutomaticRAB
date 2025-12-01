from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect

from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from openpyxl import load_workbook

from .services.header_mapper import map_headers, find_header_row
from .services.reader import preview_file
from .services.validators import validate_excel_file


def validate_pdf_file(file):
    """Validator khusus PDF"""
    if file.content_type != "application/pdf":
        raise ValidationError("Only .pdf files are allowed.")


@api_view(['POST'])
@parser_classes([MultiPartParser])
def detect_headers(request):
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
        "header_row_index": hdr_idx + 1,
        "mapping": mapping,
        "originals": originals,
        "missing": missing
    })


@csrf_exempt
def preview_rows(request):
    """
    POST /excel_parser/preview_rows
    body: multipart form-data dengan 3 field optional:
      - excel_standard
      - excel_apendo
      - pdf_file
    """
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    excel_standard = request.FILES.get("excel_standard")
    excel_apendo = request.FILES.get("excel_apendo")
    pdf_file = request.FILES.get("pdf_file")

    try:
        results = {}

        if excel_standard:
            validate_excel_file(excel_standard)
            results["excel_standard"] = preview_file(excel_standard)

        if excel_apendo:
            validate_excel_file(excel_apendo)
            results["excel_apendo"] = preview_file(excel_apendo)

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
    Render halaman upload untuk Excel & PDF dengan validasi format
    """
    if request.method == 'POST':
        excel_standard = request.FILES.get("excel_standard")
        excel_apendo = request.FILES.get("excel_apendo")
        pdf_file = request.FILES.get("pdf_file")

        try:
            if excel_standard:
                validate_excel_file(excel_standard)
                rows = preview_file(excel_standard)
                request.session["preview_rows"] = rows
                return redirect("rab_converted")

            if excel_apendo:
                validate_excel_file(excel_apendo)
                rows = preview_file(excel_apendo)
                request.session["preview_rows"] = rows
                return redirect("rab_converted")

            if pdf_file:
                validate_pdf_file(pdf_file)
                request.session["preview_rows"] = [
                    {"message": "PDF uploaded successfully"}
                ]
                return redirect("rab_converted")

            return render(request, 'excel_upload.html', {
                'error': 'File belum dipilih'
            }, status=400)

        except ValidationError as ve:
            return render(request, 'excel_upload.html', {
                'error': str(ve)
            }, status=400)

    return render(request, 'excel_upload.html')

def rab_converted(request):
    """
    Show the converted RAB preview.
    For now, just return a template with rows if available.
    """
    rows = request.session.get("preview_rows", [])
    return render(request, "rab_converted.html", {"rows": rows})
