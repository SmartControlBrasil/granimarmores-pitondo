from django.urls import path

from purchasing import views

app_name = "purchasing"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("solicitacoes/", views.request_list, name="request_list"),
    path("solicitacoes/nova/", views.request_create, name="request_create"),
    path("solicitacoes/<int:pk>/", views.request_detail, name="request_detail"),
    path("solicitacoes/<int:pk>/editar/", views.request_update, name="request_update"),
    path("solicitacoes/<int:pk>/enviar/", views.request_submit, name="request_submit"),
    path("solicitacoes/<int:pk>/aprovar/", views.request_approve, name="request_approve"),
    path("solicitacoes/<int:pk>/rejeitar/", views.request_reject, name="request_reject"),
    path("solicitacoes/<int:pk>/cancelar/", views.request_cancel, name="request_cancel"),
    path("solicitacoes/<int:pk>/comparar/", views.request_compare, name="request_compare"),
    path("comparacao/", views.comparison_hub, name="comparison_hub"),
    path("cotacoes/", views.quotation_list, name="quotation_list"),
    path("cotacoes/nova/", views.quotation_create, name="quotation_create"),
    path("cotacoes/<int:pk>/", views.quotation_detail, name="quotation_detail"),
    path("cotacoes/<int:pk>/editar/", views.quotation_update, name="quotation_update"),
    path("pedidos/", views.order_list, name="order_list"),
    path("pedidos/<int:pk>/", views.order_detail, name="order_detail"),
    path("pedidos/<int:pk>/editar/", views.order_update, name="order_update"),
    path("pedidos/<int:pk>/aprovar/", views.order_approve, name="order_approve"),
    path("pedidos/<int:pk>/cancelar/", views.order_cancel, name="order_cancel"),
    path("pedidos/<int:pk>/gerar-pagar/", views.order_generate_payable, name="order_generate_payable"),
    path("recebimentos/", views.receipt_list, name="receipt_list"),
    path("recebimentos/novo/", views.receipt_create, name="receipt_create"),
    path("recebimentos/<int:pk>/", views.receipt_detail, name="receipt_detail"),
    path("recebimentos/<int:pk>/inspecionar/", views.receipt_inspect, name="receipt_inspect"),
    path("recebimentos/<int:pk>/aceitar/", views.receipt_accept, name="receipt_accept"),
    path("recebimentos/<int:pk>/rejeitar/", views.receipt_reject, name="receipt_reject"),
    path("divergencias/", views.divergence_list, name="divergence_list"),
    path("devolucoes/", views.return_list, name="return_list"),
    path("devolucoes/nova/", views.return_create, name="return_create"),
    path("fornecedores/", views.supplier_list, name="supplier_list"),
    path("fornecedores/<int:pk>/", views.supplier_detail, name="supplier_detail"),
]
