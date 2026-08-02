from django.urls import path

from production import views

app_name = "production"

operacao_urlpatterns = [
    path("pedidos/", views.order_list, name="order_list"),
    path("pedidos/<int:pk>/", views.order_detail, name="order_detail"),
    path("pedidos/<int:pk>/editar/", views.order_update, name="order_update"),
    path("pedidos/<int:pk>/status/", views.order_change_status, name="order_change_status"),
    path("pedidos/<int:pk>/espera/", views.order_hold, name="order_hold"),
    path("pedidos/<int:pk>/cancelar/", views.order_cancel, name="order_cancel"),
    path("pedidos/<int:pk>/producao/", views.order_create_production, name="order_create_production"),
    path("pedidos/<int:pk>/entrega/", views.delivery_schedule, name="delivery_schedule"),
    path(
        "pedidos/<int:pk>/entrega/<int:delivery_pk>/concluir/",
        views.delivery_complete,
        name="delivery_complete",
    ),
    path("pedidos/<int:pk>/instalacao/", views.installation_schedule, name="installation_schedule"),
    path(
        "pedidos/<int:pk>/instalacao/<int:installation_pk>/concluir/",
        views.installation_complete,
        name="installation_complete",
    ),
    path("entregas/", views.delivery_list, name="delivery_list"),
    path("instalacoes/", views.installation_list, name="installation_list"),
]

producao_urlpatterns = [
    path("", views.production_dashboard, name="dashboard"),
    path("dashboard/", views.production_dashboard, name="production_dashboard"),
    path("ordens/", views.production_list, name="production_list"),
    path("ordens/<int:pk>/", views.production_detail, name="production_detail"),
    path("ordens/<int:pk>/editar/", views.production_update, name="production_update"),
    path("ordens/<int:pk>/liberar/", views.production_release, name="production_release"),
    path("ordens/<int:pk>/iniciar/", views.production_start, name="production_start"),
    path("ordens/<int:pk>/pausar/", views.production_pause, name="production_pause"),
    path("ordens/<int:pk>/retomar/", views.production_resume, name="production_resume"),
    path("ordens/<int:pk>/concluir/", views.production_complete, name="production_complete"),
    path("ordens/<int:pk>/cancelar/", views.production_cancel, name="production_cancel"),
    path("ordens/<int:pk>/quadro/", views.production_order_board, name="production_order_board"),
    path("quadro/", views.production_board, name="board"),
    path("pecas/", views.piece_stage_list, name="piece_list"),
    path("etapas/", views.stage_list, name="stage_list"),
]

urlpatterns = operacao_urlpatterns + producao_urlpatterns
