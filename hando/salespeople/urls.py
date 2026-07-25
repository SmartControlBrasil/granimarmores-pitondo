from django.urls import path

from salespeople import views

app_name = "salespeople"
urlpatterns = [
    path("", views.list_view, name="list"),
    path("novo/", views.create_view, name="create"),
    path("<int:pk>/", views.detail_view, name="detail"),
    path("<int:pk>/editar/", views.update_view, name="update"),
    path("<int:pk>/historico/", views.history_view, name="history"),
    path("<int:pk>/ativar/", views.activate_view, name="activate"),
    path("<int:pk>/desativar/", views.deactivate_view, name="deactivate"),
]
