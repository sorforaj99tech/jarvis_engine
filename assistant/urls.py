from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("settings/", views.settings_view, name="settings"),
    path("history/", views.history, name="history"),
    path("api/command/", views.api_command, name="api_command"),
    path("api/shutdown/", views.api_shutdown, name="api_shutdown"),
    path("api/shutdown/cancel/", views.api_shutdown_cancel, name="api_shutdown_cancel"),
    path("api/status/", views.api_status, name="api_status"),
]
