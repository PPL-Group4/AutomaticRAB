# excel_parser/urls.py
from django.urls import path
from .views import detect_headers

urlpatterns = [
    path("headers/detect", detect_headers, name="detect_headers"),
]
