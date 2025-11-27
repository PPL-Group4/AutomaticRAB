# excel_parser/urls.py
from django.urls import path

from . import views

urlpatterns = [
    path("detect_headers", views.detect_headers, name="detect_headers"),
    path("preview_rows", views.preview_rows, name="preview_rows"),
    path("preview_rows_async", views.preview_rows_async, name="preview_rows_async"),
    path("task_status/<str:task_id>", views.task_status, name="task_status"),
    path("rab_converted/", views.rab_converted, name="rab_converted"),
    path("upload/", views.upload_view, name="upload"),
]
