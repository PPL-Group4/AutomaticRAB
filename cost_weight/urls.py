from django.urls import path
from cost_weight.views import chart_page, JobItemsChartDataView, chart_export  

app_name = "cost_weight"

urlpatterns = [
    path("weight/<int:job_id>/", chart_page, name="weight_chart_page"),
    path("jobs/<int:job_id>/chart-data/", JobItemsChartDataView.as_view(), name="cw-job-chart-data"),
    path("jobs/<int:job_id>/chart-export/", chart_export, name="cw-job-chart-export"),  
]
