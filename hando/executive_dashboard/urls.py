from django.urls import path

from executive_dashboard import views

app_name = "executive_dashboard"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("relatorio/", views.report, name="report"),
    path("exportar/<slug:dataset>/", views.export_csv, name="export_csv"),
]
