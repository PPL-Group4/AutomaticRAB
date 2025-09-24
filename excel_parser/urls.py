# excel_parser/urls.py
from django.urls import path
from .views import detect_headers
from . import views

urlpatterns = [
    path("detect_headers", views.detect_headers, name="detect_headers"),
    path("preview_rows", views.preview_rows, name="preview_rows"),
    path("rab_converted/", views.rab_converted, name="rab_converted"),
    path("upload/", views.upload_view, name="upload_view"),
]
