from django.urls import path

from salespeople import views

app_name = "salespeople"
urlpatterns = [path("", views.list_view, name="list")]
