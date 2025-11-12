from django.urls import path
from efficiency_recommendations.views import (
    get_job_notifications,
    get_price_deviations
)

app_name = "efficiency_recommendations"

urlpatterns = [
    path(
        "jobs/<int:job_id>/notifications/",
        get_job_notifications,
        name="notifications"
    ),
    path(
        "jobs/<int:job_id>/price-deviations/",
        get_price_deviations,
        name="price_deviations"
    ),
]
