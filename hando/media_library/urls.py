from django.urls import path

from media_library import views

app_name = "media_library"

urlpatterns = [
    path("", views.library_list, name="library"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("upload/", views.upload, name="upload"),
    path("upload-multiplo/", views.upload_multiple, name="upload_multiple"),
    path("revisao/", views.review_queue, name="review_queue"),
    path("colecoes/", views.collection_list, name="collection_list"),
    path("colecoes/nova/", views.collection_create, name="collection_create"),
    path("colecoes/<int:pk>/", views.collection_detail, name="collection_detail"),
    path("antes-depois/", views.before_after_list, name="before_after_list"),
    path("antes-depois/novo/", views.before_after_create, name="before_after_create"),
    path("materiais/", views.materials_gallery, name="materials_gallery"),
    path("portfolio/", views.portfolio, name="portfolio"),
    path("publicacao/", views.publication_list, name="publication_list"),
    path("publicacao/nova/", views.publication_create, name="publication_create"),
    path("<int:pk>/", views.asset_detail, name="asset_detail"),
    path("<int:pk>/arquivo/", views.asset_file, name="asset_file"),
    path("<int:pk>/classificar/", views.asset_classify, name="asset_classify"),
    path("<int:pk>/revisar/", views.asset_review, name="asset_review"),
    path("<int:pk>/portfolio/aprovar/", views.asset_portfolio_approve, name="asset_portfolio_approve"),
    path("<int:pk>/portfolio/remover/", views.asset_portfolio_remove, name="asset_portfolio_remove"),
    path("<int:pk>/arquivar/", views.asset_archive, name="asset_archive"),
    path("<int:pk>/excluir/", views.asset_request_delete, name="asset_request_delete"),
    path("contexto/producao/<int:pk>/", views.upload_from_production, name="upload_production"),
    path("contexto/peca/<int:pk>/", views.upload_from_piece, name="upload_piece"),
    path("contexto/instalacao/<int:pk>/", views.upload_from_installation, name="upload_installation"),
    path("contexto/pos-venda/<int:pk>/", views.upload_from_after_sales, name="upload_after_sales"),
    path("galeria/cliente/<int:pk>/", views.customer_gallery, name="customer_gallery"),
    path("galeria/pedido/<int:pk>/", views.order_gallery, name="order_gallery"),
]
