from django.urls import path

from . import views


app_name = "institutional"

urlpatterns = [
    path("", views.home, name="home"),
    path("sobre/", views.sobre, name="sobre"),
    path("solucoes/", views.services, name="services"),
    path("projetos/", views.projects, name="projects"),
    path("materiais/", views.materials, name="materials"),
    path("blog/", views.blog, name="blog"),
    path("blog/<slug:slug>/", views.blog_article, name="blog_article"),
    path("contato/", views.contato, name="contato"),
    path("marmoraria-saude-sp/", views.marmoraria_saude_sp, name="marmoraria_saude_sp"),
    path("marmoraria-zona-sul-sp/", views.marmoraria_zona_sul_sp, name="marmoraria_zona_sul_sp"),
    path(
        "politica-de-privacidade/",
        views.politica_de_privacidade,
        name="politica_de_privacidade",
    ),
    path("orcamento/", views.quotation, name="quotation"),
    path("cozinhas/", views.cozinhas, name="cozinhas"),
    path("escadas/", views.escadas, name="escadas"),
    path("areas-gourmet/", views.areas_gourmet, name="areas_gourmet"),
    path("banheiros/", views.banheiros, name="banheiros"),
    path("projetos-comerciais/", views.projetos_comerciais, name="projetos_comerciais"),
]
