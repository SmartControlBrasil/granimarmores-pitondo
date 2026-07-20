from django.urls import path

from .views import home


app_name = "institutional"

urlpatterns = [
    path("", home, name="home"),
]
