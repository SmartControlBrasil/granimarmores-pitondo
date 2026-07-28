from django.urls import path

from materials import views

app_name = "materials"

urlpatterns = [
    path("materiais/", views.material_list, name="list"),
    path("materiais/novo/", views.material_create, name="create"),
    path("materiais/<int:pk>/", views.material_detail, name="detail"),
    path("materiais/<int:pk>/editar/", views.material_update, name="update"),
    path("materiais/<int:pk>/ativar/", views.material_activate, name="activate"),
    path("materiais/<int:pk>/desativar/", views.material_deactivate, name="deactivate"),
    path("categorias/", views.category_list, name="categories"),
    path("categorias/nova/", views.category_create, name="category_create"),
    path("categorias/<int:pk>/editar/", views.category_update, name="category_update"),
    path("acabamentos/", views.finish_list, name="finishes"),
    path("acabamentos/novo/", views.finish_create, name="finish_create"),
    path("acabamentos/<int:pk>/editar/", views.finish_update, name="finish_update"),
    path("servicos/", views.service_list, name="services"),
    path("servicos/novo/", views.service_create, name="service_create"),
    path("servicos/<int:pk>/editar/", views.service_update, name="service_update"),
    path("chapas/", views.slab_list, name="slabs"),
    path("chapas/nova/", views.slab_create, name="slab_create"),
]
