from django.urls import path
from target_bid import views

urlpatterns = [
    path("rabs/<int:rab_id>/items/", views.fetch_rab_job_items_view, name="fetch_rab_job_items_view"),
    path("cheaper-suggestions/", views.cheaper_suggestions_view, name="cheaper_suggestions_view"),
]
