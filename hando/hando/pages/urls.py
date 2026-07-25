from django.urls import path

from hando.pages.views import dynamic_pages_view
from hando.pages.views import root_page_view

app_name = "pages"

urlpatterns = [
    path("", root_page_view, name="dashboard"),
    path("<str:template_name>/", dynamic_pages_view, name="dynamic_pages"),
]
