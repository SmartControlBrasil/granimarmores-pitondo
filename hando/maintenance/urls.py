from django.urls import path

from maintenance import views

app_name = "maintenance"
urlpatterns = [
    path("ordens/", views.order_list, name="orders"),
    path("planos/", views.plan_list, name="plans"),
]
