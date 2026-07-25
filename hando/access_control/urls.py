from django.urls import path

from access_control import views

app_name = "access_control"
urlpatterns = [
    path("cargos/", views.role_list, name="roles"),
    path("cargos/novo/", views.role_create, name="role_create"),
    path("cargos/<int:pk>/", views.role_detail, name="role_detail"),
    path("cargos/<int:pk>/editar/", views.role_update, name="role_update"),
    path(
        "cargos/<int:pk>/permissoes/",
        views.role_permissions_matrix,
        name="role_permissions",
    ),
    path("cargos/<int:pk>/historico/", views.role_history, name="role_history"),
    path("cargos/<int:pk>/ativar/", views.role_activate, name="role_activate"),
    path("cargos/<int:pk>/desativar/", views.role_deactivate, name="role_deactivate"),
    path("permissoes/", views.permission_list, name="permissions"),
]
