from django.urls import path

from . import views

app_name = "credits"

urlpatterns = [
    path("history/", views.transaction_history, name="history"),
]
