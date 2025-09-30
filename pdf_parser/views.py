import os
from django.http import JsonResponse
from django.shortcuts import render
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt
from .services.pdf_sniffer import PdfSniffer


def upload_pdf(request):
    """Render the PDF upload page (optional, can be merged with Excel upload)."""
    return render(request, "pdf_upload.html")


@csrf_exempt
def preview_pdf(request):
    """Handle PDF upload + validation + simple preview response."""
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    pdf_file = request.FILES.get("pdf_file")
    if not pdf_file:
        return JsonResponse({"error": "No PDF file uploaded"}, status=400)

    tmp_path = f"/tmp/{pdf_file.name}"
    try:
        # Save uploaded file temporarily
        with open(tmp_path, "wb") as f:
            for chunk in pdf_file.chunks():
                f.write(chunk)

        # Validate PDF
        sniffer = PdfSniffer()
        sniffer.is_valid(tmp_path)

        # TODO: integrate real PDF parsing here
        rows = [
            {"page": 1, "text": "PDF uploaded successfully"},
        ]

        return JsonResponse({"rows": rows}, status=200)

    except ValidationError as ve:
        return JsonResponse({"error": str(ve)}, status=400)
    except Exception as e:
        return JsonResponse({"error": f"Unexpected error: {e}"}, status=500)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
