from src.institutional.application.services.access_policy import user_role_label


def backoffice_user(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    return {"backoffice_role_label": user_role_label(request.user)}
