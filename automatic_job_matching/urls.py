from django.urls import path
from .views import match_best_view, job_matching_page, ahs_breakdown_view

urlpatterns = [
    path("match-best/", match_best_view, name="match-best"),
    path("job-matching/", job_matching_page, name="job-matching"),
    path("ahs-breakdown/<str:code>/", ahs_breakdown_view, name="ahs-breakdown"),
]
