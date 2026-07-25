from django.urls import path

from access_control import views

app_name = "access_control"
urlpatterns = [
    path("cargos/", views.role_list, name="roles"),
    path("permissoes/", views.permission_list, name="permissions"),
]
