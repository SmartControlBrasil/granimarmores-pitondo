from django.urls import path

from finance import views

app_name = "finance"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("receber/", views.receivable_list, name="receivable_list"),
    path("receber/novo/", views.receivable_create, name="receivable_create"),
    path("receber/<int:pk>/", views.receivable_detail, name="receivable_detail"),
    path("receber/<int:pk>/editar/", views.receivable_update, name="receivable_update"),
    path("receber/<int:pk>/receber/", views.receivable_receive, name="receivable_receive"),
    path("receber/<int:pk>/cancelar/", views.receivable_cancel, name="receivable_cancel"),
    path("receber/pagamentos/<int:pk>/estornar/", views.receivable_payment_reverse, name="receivable_payment_reverse"),
    path("pedidos/<int:order_id>/gerar-receber/", views.generate_from_order, name="generate_from_order"),
    path("pagar/", views.payable_list, name="payable_list"),
    path("pagar/novo/", views.payable_create, name="payable_create"),
    path("pagar/<int:pk>/", views.payable_detail, name="payable_detail"),
    path("pagar/<int:pk>/editar/", views.payable_update, name="payable_update"),
    path("pagar/<int:pk>/pagar/", views.payable_pay, name="payable_pay"),
    path("pagar/<int:pk>/cancelar/", views.payable_cancel, name="payable_cancel"),
    path("pagar/pagamentos/<int:pk>/estornar/", views.payable_payment_reverse, name="payable_payment_reverse"),
    path("fluxo-de-caixa/", views.cash_flow_view, name="cash_flow"),
    path("movimentacoes/", views.movement_list, name="movement_list"),
    path("inadimplencia/", views.overdue_list, name="overdue_list"),
    path("contas/", views.account_list, name="account_list"),
    path("contas/nova/", views.account_create, name="account_create"),
    path("categorias/", views.category_list, name="category_list"),
    path("categorias/nova/", views.category_create, name="category_create"),
    path("centros-de-custo/", views.cost_center_list, name="cost_center_list"),
    path("centros-de-custo/novo/", views.cost_center_create, name="cost_center_create"),
    path("formas-de-pagamento/", views.payment_method_list, name="payment_method_list"),
    path("formas-de-pagamento/nova/", views.payment_method_create, name="payment_method_create"),
    path("condicoes-de-pagamento/", views.payment_term_list, name="payment_term_list"),
    path("condicoes-de-pagamento/nova/", views.payment_term_create, name="payment_term_create"),
    path("transferencias/", views.transfer_view, name="transfer"),
    path("ajustes/", views.adjustment_view, name="adjustment"),
]
