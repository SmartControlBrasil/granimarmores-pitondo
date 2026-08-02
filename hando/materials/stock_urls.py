from django.urls import path

from materials import stock_views

app_name = "stock"

urlpatterns = [
    path("dashboard/", stock_views.stock_dashboard, name="dashboard"),
    path("chapas/", stock_views.slab_list, name="slab_list"),
    path("chapas/entrada/", stock_views.slab_receive, name="slab_receive"),
    path("chapas/<int:pk>/", stock_views.slab_detail, name="slab_detail"),
    path("chapas/<int:pk>/editar/", stock_views.slab_edit, name="slab_edit"),
    path("chapas/<int:pk>/transferir/", stock_views.slab_transfer, name="slab_transfer"),
    path("chapas/<int:pk>/bloquear/", stock_views.slab_block, name="slab_block"),
    path("chapas/<int:pk>/desbloquear/", stock_views.slab_unblock, name="slab_unblock"),
    path("chapas/<int:pk>/ajustar/", stock_views.slab_adjust, name="slab_adjust"),
    path("chapas/<int:pk>/perda/", stock_views.slab_register_loss, name="slab_loss"),
    path("reservas/", stock_views.reservation_list, name="reservation_list"),
    path("reservas/<int:pk>/liberar/", stock_views.reservation_release, name="reservation_release"),
    path("reservas/<int:pk>/consumir/", stock_views.reservation_consume, name="reservation_consume"),
    path("sobras/", stock_views.remnant_list, name="remnant_list"),
    path("sobras/<int:pk>/descartar/", stock_views.remnant_discard, name="remnant_discard"),
    path("movimentacoes/", stock_views.movement_list, name="movement_list"),
    path("inventarios/", stock_views.inventory_list, name="inventory_list"),
    path("inventarios/novo/", stock_views.inventory_create, name="inventory_create"),
    path("inventarios/<int:pk>/", stock_views.inventory_detail, name="inventory_detail"),
    path("inventarios/<int:pk>/iniciar/", stock_views.inventory_start, name="inventory_start"),
    path(
        "inventarios/<int:pk>/itens/<int:item_pk>/contar/",
        stock_views.inventory_count_item,
        name="inventory_count_item",
    ),
    path("inventarios/<int:pk>/concluir/", stock_views.inventory_complete, name="inventory_complete"),
    path("localizacoes/", stock_views.location_list, name="location_list"),
    path("localizacoes/nova/", stock_views.location_create, name="location_create"),
    path("localizacoes/<int:pk>/editar/", stock_views.location_update, name="location_update"),
    path("fornecedores/", stock_views.supplier_list, name="supplier_list"),
    path("fornecedores/novo/", stock_views.supplier_create, name="supplier_create"),
    path("fornecedores/<int:pk>/editar/", stock_views.supplier_update, name="supplier_update"),
    path("pecas/<int:pk>/reservar/", stock_views.piece_reserve_slab, name="piece_reserve"),
]
