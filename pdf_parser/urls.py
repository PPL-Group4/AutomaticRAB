from django.urls import path
from . import views

app_name = "pdf_parser"

urlpatterns = [
    path("rab_converted/", views.rab_converted_pdf, name="rab_converted_pdf"),
]
