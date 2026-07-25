from django.urls import path

from quotes import views

app_name = "quotes"

urlpatterns = [
    path("", views.quote_list, name="list"),
    path("novo/", views.quote_create, name="create"),
    path("politica-comercial/", views.policy_update, name="policy"),
    path("<int:pk>/", views.quote_detail, name="detail"),
    path("<int:pk>/editar/", views.quote_update, name="update"),
    path("<int:pk>/itens/", views.quote_items, name="items"),
    path("<int:pk>/itens/novo/", views.quote_item_create, name="item_create"),
    path("<int:pk>/itens/<int:item_pk>/", views.quote_item_detail, name="item_detail"),
    path(
        "<int:pk>/itens/<int:item_pk>/editar/",
        views.quote_item_update,
        name="item_update",
    ),
    path(
        "<int:pk>/itens/<int:item_pk>/remover/",
        views.quote_item_remove,
        name="item_remove",
    ),
    path(
        "<int:pk>/itens/<int:item_pk>/medidas/nova/",
        views.measurement_create,
        name="measurement_create",
    ),
    path(
        "<int:pk>/itens/<int:item_pk>/acabamentos/novo/",
        views.finish_create,
        name="finish_create",
    ),
    path("<int:pk>/servicos/novo/", views.service_create, name="service_create"),
    path("<int:pk>/revisar/", views.quote_review, name="review"),
    path("<int:pk>/versoes/", views.quote_versions, name="versions"),
    path("<int:pk>/historico/", views.quote_history, name="history"),
    path("<int:pk>/enviar-aprovacao/", views.quote_review, name="submit_approval"),
    path("<int:pk>/aprovar/", views.quote_approve, name="approve"),
    path("<int:pk>/rejeitar/", views.quote_reject, name="reject"),
    path("<int:pk>/cancelar/", views.quote_cancel, name="cancel"),
    path("<int:pk>/enviar/", views.quote_send, name="send"),
    path(
        "<int:pk>/historico-envios/",
        views.quote_delivery_history,
        name="delivery_history",
    ),
    path("<int:pk>/versoes/<int:version>/pdf/", views.quote_pdf, name="pdf"),
]
