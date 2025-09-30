from django.urls import path
from . import views

app_name = "pdf_parser"

urlpatterns = [
    path("upload/", views.upload_pdf, name="upload_pdf"),
    path("preview/", views.preview_pdf, name="preview_pdf"),
]
