from django.urls import path

from cost_weight.views import (
    JobItemsChartDataView,
    chart_export,
    chart_page,
    cost_weight_analysis_view,
    recalc_job_weights,
    upload_excel_view,
)

app_name = "cost_weight"

urlpatterns = [
    path("weight/<int:job_id>/", chart_page, name="weight_chart_page"),
    path("jobs/<int:job_id>/chart-data/", JobItemsChartDataView.as_view(), name="cw-job-chart-data"),
    path("jobs/<int:job_id>/chart-export/", chart_export, name="cw-job-chart-export"),
    path("jobs/<int:job_id>/recalc/", recalc_job_weights, name="cw-job-recalc"),
    path("upload/", upload_excel_view, name="upload_excel"),
    path("analysis/<int:job_id>/", cost_weight_analysis_view, name="cost_analysis"),
]
