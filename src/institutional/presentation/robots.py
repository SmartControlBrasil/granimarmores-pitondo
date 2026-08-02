from django.http import HttpResponse

from src.institutional.presentation.seo import build_robots_txt


def robots_txt(request):
    return HttpResponse(build_robots_txt(), content_type="text/plain")
