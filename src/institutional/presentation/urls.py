from django.urls import path

from . import views


app_name = "institutional"

urlpatterns = [
    path("", views.home, name="home"),
    path("sobre/", views.about, name="about"),
    path("solucoes/", views.services, name="services"),
    path("projetos/", views.projects, name="projects"),
    path("materiais/", views.materials, name="materials"),
    path("blog/", views.blog, name="blog"),
    path("contato/", views.contact, name="contact"),
    path("orcamento/", views.quotation, name="quotation"),
]
