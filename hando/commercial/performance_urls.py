from django.urls import path

from commercial import performance_views

performance_urlpatterns = [
    path("ranking/", performance_views.ranking_view, name="ranking"),
    path("meu-desempenho/", performance_views.my_performance_view, name="my_performance"),
    path("desempenho/", performance_views.team_performance_view, name="team_performance"),
    path("metas/", performance_views.goal_list, name="goal_list"),
    path("metas/nova/", performance_views.goal_create, name="goal_create"),
    path("metas/<int:pk>/", performance_views.goal_detail, name="goal_detail"),
    path("metas/<int:pk>/editar/", performance_views.goal_update, name="goal_update"),
    path("metas/<int:pk>/desativar/", performance_views.goal_deactivate, name="goal_deactivate"),
]

performance_admin_urlpatterns = [
    path("politica-score/", performance_views.score_policy_list, name="score_policy_list"),
    path("politica-score/nova/", performance_views.score_policy_create, name="score_policy_create"),
    path(
        "politica-score/<int:pk>/editar/",
        performance_views.score_policy_update,
        name="score_policy_update",
    ),
    path("politica-score/ajustar/", performance_views.score_adjust, name="score_adjust"),
]
