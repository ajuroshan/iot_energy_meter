from django.urls import path

from . import views

app_name = "stations"

urlpatterns = [
    path("", views.station_list, name="list"),
    path("<uuid:station_uuid>/", views.station_detail, name="detail"),
    path("<uuid:station_uuid>/start/", views.start_charging, name="start"),
    path("<uuid:station_uuid>/qr/", views.station_qr_code, name="qr_code"),
    path("session/<int:session_id>/", views.session_detail, name="session"),
    path("session/<int:session_id>/stop/", views.stop_charging, name="stop"),
    path("session/<int:session_id>/data/", views.session_data, name="session_data"),
    path("history/", views.session_history, name="history"),
]
