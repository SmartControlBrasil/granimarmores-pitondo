from src.institutional.presentation.seo import build_site_seo_context


def institutional_seo(request):
    return {"site_seo": build_site_seo_context(request)}
