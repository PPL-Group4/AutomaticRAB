from django.urls import path

from .views import (
    ahs_breakdown_page,
    ahs_breakdown_view,
    job_matching_page,
    match_best_view,
    match_bulk_view,
)

urlpatterns = [
    path("match-best/", match_best_view, name="match-best"),
    path("match-bulk/", match_bulk_view, name="match-bulk"),
    path("job-matching/", job_matching_page, name="job-matching"),
    path("ahs-breakdown/<str:code>/", ahs_breakdown_view, name="ahs-breakdown"),
    path("ahs-breakdown-page/", ahs_breakdown_page, name="ahs-breakdown-page"),
]
