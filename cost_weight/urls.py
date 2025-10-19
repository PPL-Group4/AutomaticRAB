from django.urls import path
from .views import JobItemsChartDataView

urlpatterns = [
    path("jobs/<int:job_id>/chart-data/", JobItemsChartDataView.as_view(), name="cw-job-chart-data"),
]
