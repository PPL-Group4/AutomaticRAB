from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from openpyxl import load_workbook

from .services.header_mapper import map_headers, find_header_row


@api_view(['POST'])
@parser_classes([MultiPartParser])
def detect_headers(request):
    f = request.FILES.get('file')
    if not f:
        return Response({"detail": "file is required"}, status=400)

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
        "header_row_index": hdr_idx + 1,
        "mapping": mapping,
        "originals": originals,
        "missing": missing
    })
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .services.reader import preview_file   # make sure this points to the right place

@csrf_exempt
def preview_rows(request):
    """
    POST /excel_parser/preview_rows
    body: multipart form-data with 'file'
    """
    if request.method == "POST":
        file = request.FILES.get("file")
        if not file:
            return JsonResponse({"detail": "file is required"}, status=400)

        try:
            rows = preview_file(file)
            return JsonResponse({"rows": rows}, safe=False)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"detail": "Method not allowed"}, status=405)

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .services.reader import preview_file 

def rab_converted(request):
    """
    Display converted rows in a table with ability to edit.
    This will hit the preview_rows endpoint via AJAX/fetch.
    """
    return render(request, "rab_converted.html")