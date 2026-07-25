from django.urls import path

from accounts import views

app_name = "accounts"
urlpatterns = [
    path("", views.user_list, name="users"),
    path("novo/", views.user_create, name="user_create"),
    path("sessoes/", views.session_list, name="sessions"),
    path("<int:pk>/", views.user_detail, name="user_detail"),
    path("<int:pk>/editar/", views.user_update, name="user_update"),
    path("<int:pk>/acessos/", views.user_access, name="user_access"),
    path("<int:pk>/sessoes/", views.user_sessions, name="user_sessions"),
    path("<int:pk>/historico/", views.user_history, name="user_history"),
    path("<int:pk>/ativar/", views.user_activate, name="user_activate"),
    path("<int:pk>/desativar/", views.user_deactivate, name="user_deactivate"),
    path("<int:pk>/redefinir-senha/", views.user_password_reset, name="password_reset"),
]
