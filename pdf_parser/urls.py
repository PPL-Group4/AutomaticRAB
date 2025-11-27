from django.urls import path

from . import views

app_name = "pdf_parser"

urlpatterns = [
    path("upload/", views.upload_pdf, name="upload_pdf"),
    path("preview/", views.preview_pdf, name="preview_pdf"),
    path("parse", views.parse_pdf_view, name="parse_pdf"),
    path("rab_converted/", views.rab_converted_pdf, name="rab_converted_pdf"),
]
