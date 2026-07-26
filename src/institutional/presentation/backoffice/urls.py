from django.contrib.auth import views as auth_views
from django.urls import path

from src.institutional.presentation.backoffice import views

app_name = "backoffice"

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="backoffice/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", views.dashboard, name="dashboard"),
    path("profile/", views.profile, name="profile"),
    path("leads/", views.lead_list, name="lead_list"),
    path("leads/<int:pk>/", views.lead_detail, name="lead_detail"),
    path("leads/<int:pk>/status/", views.lead_status, name="lead_status"),
    path("leads/<int:pk>/assign/", views.lead_assign, name="lead_assign"),
    path("leads/<int:pk>/notes/", views.lead_note, name="lead_note"),
    path("leads/<int:pk>/convert/", views.lead_convert, name="lead_convert"),
    path("opportunities/", views.opportunity_pipeline, name="opportunity_pipeline"),
    path("opportunities/list/", views.opportunity_list, name="opportunity_list"),
    path("opportunities/<int:pk>/", views.opportunity_detail, name="opportunity_detail"),
    path("opportunities/<int:pk>/stage/", views.opportunity_stage, name="opportunity_stage"),
    path("opportunities/<int:opportunity_id>/quotes/new/", views.quote_new, name="quote_new"),
    path("quotes/<int:pk>/", views.quote_detail, name="quote_detail"),
    path("quotes/<int:pk>/preview/", views.quote_preview, name="quote_preview"),
    path("quotes/<int:pk>/documents/generate/", views.quote_generate_document, name="quote_generate_document"),
    path("quotes/<int:pk>/documents/<int:document_id>/download/", views.quote_document_download, name="quote_document_download"),
    path("quotes/<int:pk>/documents/<int:document_id>/send/", views.quote_send, name="quote_send"),
    path("quotes/<int:pk>/documents/<int:document_id>/void/", views.quote_document_void, name="quote_document_void"),
    path("quotes/<int:pk>/status/", views.quote_status, name="quote_status"),
    path("quotes/<int:pk>/revision/", views.quote_revision, name="quote_revision"),
]
