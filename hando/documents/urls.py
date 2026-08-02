from django.urls import path

from documents import views

app_name = "documents"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("", views.document_list, name="document_list"),
    path("novo/", views.document_create, name="document_create"),
    path("novo/modelo/", views.document_from_template, name="document_from_template"),
    path("<int:pk>/", views.document_detail, name="document_detail"),
    path("<int:pk>/imprimir/", views.document_print, name="document_print"),
    path("<int:pk>/enviar-revisao/", views.document_submit_review, name="document_submit_review"),
    path("<int:pk>/aprovar/", views.document_approve, name="document_approve"),
    path("<int:pk>/rejeitar/", views.document_reject, name="document_reject"),
    path("<int:pk>/nova-versao/", views.document_new_version, name="document_new_version"),
    path("<int:pk>/editar-versao/", views.document_edit_version, name="document_edit_version"),
    path("<int:pk>/registrar-envio/", views.document_send, name="document_send"),
    path("<int:pk>/registrar-visualizacao/", views.document_view_record, name="document_view_record"),
    path("<int:pk>/aceite/", views.document_accept, name="document_accept"),
    path("<int:pk>/assinatura/", views.document_signature, name="document_signature"),
    path("<int:pk>/cancelar/", views.document_cancel, name="document_cancel"),
    path("<int:pk>/encerrar/", views.document_terminate, name="document_terminate"),
    path("<int:pk>/renovar/", views.document_renew, name="document_renew"),
    path("modelos/", views.template_list, name="template_list"),
    path("modelos/novo/", views.template_create, name="template_create"),
    path("modelos/<int:pk>/aprovar/", views.template_approve, name="template_approve"),
    path("tipos/", views.type_list, name="type_list"),
    path("tipos/novo/", views.type_create, name="type_create"),
    path("revisoes/", views.review_queue, name="review_queue"),
    path("aprovacoes/", views.approval_queue, name="approval_queue"),
    path("aguardando-aceite/", views.acceptance_queue, name="acceptance_queue"),
    path("vencimentos/", views.expiration_list, name="expiration_list"),
]
