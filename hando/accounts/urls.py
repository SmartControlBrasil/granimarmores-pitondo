from django.urls import path

from accounts import views

app_name = "accounts"
urlpatterns = [
    path("usuarios/", views.user_list, name="users"),
    path("usuarios/novo/", views.user_create, name="user_create"),
    path("sessoes/", views.session_list, name="sessions"),
    path("usuarios/<int:pk>/", views.user_detail, name="user_detail"),
    path("usuarios/<int:pk>/editar/", views.user_update, name="user_update"),
    path("usuarios/<int:pk>/acessos/", views.user_access, name="user_access"),
    path("usuarios/<int:pk>/sessoes/", views.user_sessions, name="user_sessions"),
    path("usuarios/<int:pk>/historico/", views.user_history, name="user_history"),
    path("usuarios/<int:pk>/ativar/", views.user_activate, name="user_activate"),
    path("usuarios/<int:pk>/desativar/", views.user_deactivate, name="user_deactivate"),
    path("usuarios/<int:pk>/redefinir-senha/", views.user_password_reset, name="password_reset"),
]
