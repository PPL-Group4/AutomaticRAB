from django.urls import path
from .views import match_best_view

urlpatterns = [
    path("match-best/", match_best_view, name="match-best"),
]
