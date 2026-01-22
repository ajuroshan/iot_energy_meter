"""
URL configuration for IoT Energy Meter project.
"""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),
    # Apps
    path("accounts/", include("accounts.urls")),
    path("station/", include("stations.urls")),
    path("credits/", include("credits.urls")),
    # Home redirect to dashboard
    path("", RedirectView.as_view(pattern_name="accounts:dashboard"), name="home"),
]
