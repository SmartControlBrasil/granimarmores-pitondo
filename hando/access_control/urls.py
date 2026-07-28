from django.urls import path

from access_control import views

app_name = "access_control"
urlpatterns = [
    path("acessos/", views.role_list, name="roles"),
    path("acessos/novo/", views.role_create, name="role_create"),
    path("acessos/<int:pk>/", views.role_detail, name="role_detail"),
    path("acessos/<int:pk>/editar/", views.role_update, name="role_update"),
    path(
        "acessos/<int:pk>/permissoes/",
        views.role_permissions_matrix,
        name="role_permissions",
    ),
    path("acessos/<int:pk>/historico/", views.role_history, name="role_history"),
    path("acessos/<int:pk>/ativar/", views.role_activate, name="role_activate"),
    path("acessos/<int:pk>/desativar/", views.role_deactivate, name="role_deactivate"),
    path("permissoes/", views.permission_list, name="permissions"),
]
