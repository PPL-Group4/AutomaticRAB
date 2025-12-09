# excel_parser/urls.py
from django.urls import path
from .views import detect_headers, rab_converted, preview_rows, upload_view
from . import views

def trigger_error(request):
    division_by_zero = 1 / 0

urlpatterns = [
    path('sentry-debug/', trigger_error),
    path("detect_headers", views.detect_headers, name="detect_headers"),
    path("preview_rows", views.preview_rows, name="preview_rows"),
    path("rab_converted/", views.rab_converted, name="rab_converted"),
    path("upload/", views.upload_view, name="upload"),
]
