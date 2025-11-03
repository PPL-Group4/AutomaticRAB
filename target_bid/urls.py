from django.urls import path

from . import views

app_name = "target_bid"

urlpatterns = [
    path(
        "rabs/<int:rab_id>/items/",
        views.fetch_rab_job_items_view,
        name="rab-job-items",
    ),
]
