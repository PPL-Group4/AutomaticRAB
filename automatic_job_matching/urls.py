from django.urls import path
from .views import match_best_view, job_matching_page
from django.urls import path

def trigger_error(request):
    division_by_zero = 1 / 0

urlpatterns = [
    path('sentry-debug/', trigger_error),
    path("match-best/", match_best_view, name="match-best"),
    path("job-matching/", job_matching_page, name="job-matching"),
]
