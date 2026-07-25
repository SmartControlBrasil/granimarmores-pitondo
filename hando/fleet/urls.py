from django.urls import path

from fleet import views

app_name = "fleet"
urlpatterns = [path("", views.list_view, name="list")]
