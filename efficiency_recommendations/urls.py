from django.urls import path
from efficiency_recommendations.views import get_job_notifications

app_name = "efficiency_recommendations"

urlpatterns = [
    path("jobs/<int:job_id>/notifications/", get_job_notifications, name="notifications"),
]