from access_control.services.authorization import user_has_permission


def erp_permissions(request):
    return {"can": lambda code: user_has_permission(request.user, code)}
