from django.urls import path

from customers import views

app_name = "customers"

urlpatterns = [
    path("", views.customer_list, name="list"),
    path("novo/", views.customer_create, name="create"),
]
