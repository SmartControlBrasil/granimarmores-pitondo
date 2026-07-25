from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render

from access_control.forms import PermissionMatrixForm
from access_control.forms import RoleForm
from access_control.models import AccessPermission
from access_control.models import AccessRole
from access_control.models import RolePermission
from access_control.role_services import create_role
from access_control.role_services import set_role_active
from access_control.role_services import update_permission_matrix
from access_control.role_services import update_role
from access_control.services.authorization import require_permission
from audit.models import AuditEvent


@require_permission("roles.view")
def role_list(request):
    qs = AccessRole.objects.all().order_by("hierarchy_level", "name")
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "access_control/role_list.html",
        {"page_title": "Cargos e níveis de acesso", "page_obj": page_obj},
    )


@require_permission("roles.view")
def role_detail(request, pk):
    role = get_object_or_404(AccessRole, pk=pk)
    role_permissions = RolePermission.objects.filter(role=role).select_related(
        "permission",
    )
    recent_events = AuditEvent.objects.filter(
        object_type="AccessRole",
        object_id=str(role.pk),
    )[:10]
    return render(
        request,
        "access_control/role_detail.html",
        {
            "page_title": role.name,
            "role": role,
            "role_permissions": role_permissions,
            "recent_events": recent_events,
        },
    )


@require_permission("roles.create")
def role_create(request):
    form = RoleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            role = create_role(form=form, actor=request.user, request=request)
        except PermissionDenied as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Cargo criado com sucesso.")
            return redirect("access_control:role_detail", pk=role.pk)
    return render(
        request,
        "access_control/role_form.html",
        {"page_title": "Novo cargo", "form": form},
    )


@require_permission("roles.update")
def role_update(request, pk):
    role = get_object_or_404(AccessRole, pk=pk)
    form = RoleForm(request.POST or None, instance=role)
    if request.method == "POST" and form.is_valid():
        try:
            role = update_role(
                role=role,
                form=form,
                actor=request.user,
                request=request,
            )
        except PermissionDenied as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Cargo atualizado com sucesso.")
            return redirect("access_control:role_detail", pk=role.pk)
    return render(
        request,
        "access_control/role_form.html",
        {"page_title": f"Editar {role.name}", "form": form, "role": role},
    )


@require_permission("roles.update")
def role_activate(request, pk):
    role = get_object_or_404(AccessRole, pk=pk)
    if request.method == "POST":
        try:
            set_role_active(
                role=role,
                is_active=True,
                actor=request.user,
                request=request,
            )
        except PermissionDenied as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Cargo ativado com sucesso.")
        return redirect("access_control:role_detail", pk=role.pk)
    return render(
        request,
        "erp/confirm_action.html",
        {
            "page_title": "Ativar cargo",
            "message": f"Ativar {role.name}?",
            "cancel_href": role.get_absolute_url()
            if hasattr(role, "get_absolute_url")
            else None,
        },
    )


@require_permission("roles.delete")
def role_deactivate(request, pk):
    role = get_object_or_404(AccessRole, pk=pk)
    if request.method == "POST":
        try:
            set_role_active(
                role=role,
                is_active=False,
                actor=request.user,
                request=request,
            )
        except PermissionDenied as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Cargo desativado com sucesso.")
        return redirect("access_control:role_detail", pk=role.pk)
    return render(
        request,
        "erp/confirm_action.html",
        {"page_title": "Desativar cargo", "message": f"Desativar {role.name}?"},
    )


@require_permission("roles.manage_permissions")
def role_permissions_matrix(request, pk):
    role = get_object_or_404(AccessRole, pk=pk)
    permissions = AccessPermission.objects.filter(is_active=True).order_by(
        "module",
        "code",
    )
    initial = {
        f"permission_{item.permission_id}": item.allowed
        for item in RolePermission.objects.filter(role=role)
    }
    form = PermissionMatrixForm(
        request.POST or None,
        permissions=permissions,
        initial=initial,
    )
    if request.method == "POST" and form.is_valid():
        try:
            update_permission_matrix(
                role=role,
                form=form,
                actor=request.user,
                request=request,
            )
        except PermissionDenied as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Matriz de permissões atualizada.")
            return redirect("access_control:role_detail", pk=role.pk)
    grouped = {}
    for permission in permissions:
        field_name = f"permission_{permission.pk}"
        grouped.setdefault(permission.module, []).append(
            {
                "permission": permission,
                "field_name": field_name,
                "checked": form[field_name].value(),
            },
        )
    return render(
        request,
        "access_control/permission_matrix.html",
        {
            "page_title": f"Permissões de {role.name}",
            "role": role,
            "form": form,
            "grouped_permissions": grouped,
        },
    )


@require_permission("roles.view")
def role_history(request, pk):
    role = get_object_or_404(AccessRole, pk=pk)
    qs = AuditEvent.objects.filter(object_type="AccessRole", object_id=str(role.pk))
    page_obj = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(
        request,
        "audit/audit_list.html",
        {"page_title": f"Histórico de {role.name}", "page_obj": page_obj},
    )


@require_permission("roles.view")
def permission_list(request):
    qs = AccessPermission.objects.all().order_by("module", "code")
    page_obj = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(
        request,
        "access_control/permission_list.html",
        {"page_title": "Permissões", "page_obj": page_obj},
    )
