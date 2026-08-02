from django.urls import path

from commissions import views

app_name = "commissions"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("eventos/", views.event_list, name="event_list"),
    path("eventos/<int:pk>/estornar/", views.event_reverse, name="event_reverse"),
    path("eventos/ajustar/", views.event_adjust, name="event_adjust"),
    path("politicas/", views.policy_list, name="policy_list"),
    path("politicas/nova/", views.policy_create, name="policy_create"),
    path("politicas/<int:pk>/", views.policy_detail, name="policy_detail"),
    path("politicas/<int:pk>/editar/", views.policy_update, name="policy_update"),
    path("politicas/<int:pk>/ativar/", views.policy_activate, name="policy_activate"),
    path("politicas/<int:pk>/desativar/", views.policy_deactivate, name="policy_deactivate"),
    path("fechamentos/", views.settlement_list, name="settlement_list"),
    path("fechamentos/novo/", views.settlement_create, name="settlement_create"),
    path("fechamentos/<int:pk>/", views.settlement_detail, name="settlement_detail"),
    path("fechamentos/<int:pk>/aprovar/", views.settlement_approve, name="settlement_approve"),
    path("fechamentos/<int:pk>/gerar-conta-pagar/", views.settlement_generate_payable, name="settlement_generate_payable"),
    path("fechamentos/<int:pk>/cancelar/", views.settlement_cancel, name="settlement_cancel"),
    path("fechamentos/<int:pk>/pagar/", views.settlement_pay, name="settlement_pay"),
    path("simulador/", views.simulator, name="simulator"),
    path("vendedores/", views.salesperson_list, name="salesperson_list"),
    path("parceiros/", views.partner_list, name="partner_list"),
    path("parceiros/<int:pk>/", views.partner_detail, name="partner_detail"),
]
