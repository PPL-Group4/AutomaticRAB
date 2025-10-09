from django.urls import path
from .views import match_best_view, job_matching_page

urlpatterns = [
    path("match-best/", match_best_view, name="match-best"),
    path("job-matching/", job_matching_page, name="job-matching"),
]
