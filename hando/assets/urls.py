from django.urls import path

from assets import views

app_name = "assets"
urlpatterns = [path("", views.list_view, name="list")]
