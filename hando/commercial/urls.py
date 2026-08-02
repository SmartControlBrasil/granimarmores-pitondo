from django.urls import path

from commercial import views

app_name = "commercial"

urlpatterns = [
    path("resumo/", views.master_data_summary, name="summary"),
    path("origens/", views.source_list, name="sources"),
    path("origens/nova/", views.source_create, name="source_create"),
    path("origens/<int:pk>/editar/", views.source_update, name="source_update"),
    path("tipos-projeto/", views.project_type_list, name="project_types"),
    path("tipos-projeto/novo/", views.project_type_create, name="project_type_create"),
    path(
        "tipos-projeto/<int:pk>/editar/",
        views.project_type_update,
        name="project_type_update",
    ),
    path("parceiros/", views.partner_list, name="partners"),
    path("parceiros/novo/", views.partner_create, name="partner_create"),
    path("parceiros/<int:pk>/", views.partner_detail, name="partner_detail"),
    path("parceiros/<int:pk>/editar/", views.partner_update, name="partner_update"),
    path("parceiros/<int:pk>/ativar/", views.partner_activate, name="partner_activate"),
    path(
        "parceiros/<int:pk>/desativar/",
        views.partner_deactivate,
        name="partner_deactivate",
    ),
    path("motivos-perda/", views.loss_reason_list, name="loss_reasons"),
    path("motivos-perda/novo/", views.loss_reason_create, name="loss_reason_create"),
    path(
        "motivos-perda/<int:pk>/editar/",
        views.loss_reason_update,
        name="loss_reason_update",
    ),
    path("regioes/", views.region_list, name="regions"),
    path("regioes/nova/", views.region_create, name="region_create"),
    path("regioes/<int:pk>/editar/", views.region_update, name="region_update"),
    path("canais/", views.channel_list, name="channels"),
    path("canais/novo/", views.channel_create, name="channel_create"),
    path("canais/<int:pk>/editar/", views.channel_update, name="channel_update"),
]
