# automatic_price_matching/urls.py
from django.urls import path

from .views import recompute_total_cost

urlpatterns = [
    path("api/recompute_total_cost/", recompute_total_cost, name="recompute_total_cost"),
]
