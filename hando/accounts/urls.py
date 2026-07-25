from django.urls import path

from accounts import views

app_name = "accounts"
urlpatterns = [
    path("", views.user_list, name="users"),
    path("sessoes/", views.session_list, name="sessions"),
]
