from django.urls import path
from .views import match_exact_view, match_fuzzy_view, match_multiple_view, debug_ahs_data

urlpatterns = [
    path("match/exact", match_exact_view, name="match-exact"),
    path("match/fuzzy", match_fuzzy_view, name="match-fuzzy"),
    path("match/multiple", match_multiple_view, name="match-multiple"),
    path("debug/ahs", debug_ahs_data, name="debug-ahs"),
]