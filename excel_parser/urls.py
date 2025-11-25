# excel_parser/urls.py
from django.urls import path
from .views import (
    detect_headers,
    preview_rows,
    rab_converted,
    # upload_view,  # tidak dipakai lagi untuk routing
)

app_name = "excel_parser"

urlpatterns = [
    # ✅ Pakai halaman RAB Preview sebagai halaman upload utama
    path("upload/", rab_converted, name="upload"),

    # Halaman RAB Preview (bisa juga diakses langsung)
    path("rab_converted/", rab_converted, name="rab_converted"),

    # API untuk deteksi header (kalau dipakai)
    path("detect_headers/", detect_headers, name="detect_headers"),

    # API untuk preview rows (dipanggil lewat JS di rab_converted.html)
    path("preview_rows/", preview_rows, name="preview_rows"),
]
