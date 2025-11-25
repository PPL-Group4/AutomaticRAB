"""
URL configuration for AutomaticRAB project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static
import os


from automatic_price_matching.views import recompute_total_cost

def trigger_error(request):
    division_by_zero = 1 / 0

urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/", include("automatic_job_matching.urls")),
    path("excel_parser/", include("excel_parser.urls")),
    path("pdf_parser/", include("pdf_parser.urls")),
    path("", lambda request: redirect("job-matching")),
    path('automatic_price_matching/', include('automatic_price_matching.urls')),
    path("cost_weight/", include("cost_weight.urls")),
    path("efficiency_recommendations/", include("efficiency_recommendations.urls")),
    path("api/recompute_total_cost/", recompute_total_cost),
    path('sentry-debug/', trigger_error),
    path("efficiency_recommendations/", include("efficiency_recommendations.urls", namespace="efficiency_recommendations"), ),
    path("silk/", include("silk.urls", namespace="silk")),

]

if settings.DEBUG or os.getenv("DOCKER_ENV") == "True":
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
