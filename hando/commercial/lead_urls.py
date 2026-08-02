from django.urls import path

from commercial import lead_views
from commercial.performance_urls import performance_urlpatterns

app_name = "leads"

urlpatterns = [
    path("dashboard/", lead_views.commercial_dashboard, name="dashboard"),
    path("leads/", lead_views.lead_list, name="list"),
    path("leads/novo/", lead_views.lead_create, name="create"),
    path("leads/funil/", lead_views.lead_funnel, name="funnel"),
    path("leads/<int:pk>/", lead_views.lead_detail, name="detail"),
    path("leads/<int:pk>/editar/", lead_views.lead_update, name="update"),
    path("leads/<int:pk>/atribuir/", lead_views.lead_assign, name="assign"),
    path("leads/<int:pk>/status/", lead_views.lead_change_status, name="change_status"),
    path("leads/<int:pk>/atividade/", lead_views.lead_add_activity, name="add_activity"),
    path("leads/<int:pk>/tarefa/", lead_views.lead_add_task, name="add_task"),
    path("leads/<int:pk>/tarefa/<int:task_pk>/concluir/", lead_views.lead_complete_task, name="complete_task"),
    path("leads/<int:pk>/tarefa/<int:task_pk>/cancelar/", lead_views.lead_cancel_task, name="cancel_task"),
    path("leads/<int:pk>/tarefa/<int:task_pk>/reabrir/", lead_views.lead_reopen_task, name="reopen_task"),
    path("leads/<int:pk>/converter/novo/", lead_views.lead_convert_new, name="convert_new"),
    path("leads/<int:pk>/converter/vincular/", lead_views.lead_convert_link, name="convert_link"),
    path("leads/<int:pk>/orcamento/", lead_views.lead_create_quote, name="create_quote"),
    path("leads/<int:pk>/ganho/", lead_views.lead_mark_won, name="mark_won"),
    path("leads/<int:pk>/perda/", lead_views.lead_mark_lost, name="mark_lost"),
    path("leads/<int:pk>/reabrir/", lead_views.lead_reopen_view, name="reopen"),
    *performance_urlpatterns,
]
