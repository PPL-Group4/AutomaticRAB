from django.urls import path
from .views import match_exact_view

urlpatterns = [
    path("match/exact", match_exact_view, name="match-exact"),
]