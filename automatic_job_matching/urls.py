from django.urls import path
from .views import match_best_view, job_matching_page, suggest_matches_view

urlpatterns = [
    path("match-best/", match_best_view, name="match-best"),
    path("job-matching/", job_matching_page, name="job-matching"),
    path("suggest/", suggest_matches_view, name="match-suggest"),
]
