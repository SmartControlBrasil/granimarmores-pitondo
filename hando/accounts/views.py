from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render

from access_control.models import UserAccess
from access_control.services.authorization import require_permission
from accounts.forms import AdminPasswordResetForm
from accounts.forms import UserAccessForm
from accounts.forms import UserCreateForm
from accounts.forms import UserUpdateForm
from accounts.services import add_permission_error
from accounts.services import assign_user_access
from accounts.services import create_managed_user
from accounts.services import deactivate_user
from accounts.services import reactivate_user
from accounts.services import reset_user_password
from accounts.services import revoke_user_sessions
from accounts.services import update_managed_user
from audit.models import AuditEvent
from audit.models import UserSessionLog

User = get_user_model()


def _user_queryset():
    active_accesses = UserAccess.objects.filter(is_active=True).select_related("role")
    return User.objects.select_related("profile").prefetch_related(
        Prefetch(
            "access_assignments",
            queryset=active_accesses,
            to_attr="active_accesses",
        ),
    )


@require_permission("users.view")
def user_list(request):
    qs = _user_queryset().order_by("username")
    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(username__icontains=search)
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "accounts/user_list.html",
        {"page_title": "Usuários", "page_obj": page_obj, "search": search},
    )


@require_permission("users.view")
def user_detail(request, pk):
    user_obj = get_object_or_404(_user_queryset(), pk=pk)
    active_access = UserAccess.objects.filter(user=user_obj, is_active=True).first()
    recent_events = AuditEvent.objects.filter(
        object_type="User",
        object_id=str(user_obj.pk),
    )[:10]
    sessions = UserSessionLog.objects.filter(user=user_obj)[:10]
    return render(
        request,
        "accounts/user_detail.html",
        {
            "page_title": f"Usuário {user_obj.username}",
            "user_obj": user_obj,
            "active_access": active_access,
            "recent_events": recent_events,
            "sessions": sessions,
        },
    )


@require_permission("users.create")
def user_create(request):
    form = UserCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user_obj = create_managed_user(form=form, actor=request.user, request=request)
        messages.success(request, "Usuário criado com sucesso.")
        return redirect("accounts:user_detail", pk=user_obj.pk)
    return render(
        request,
        "accounts/user_form.html",
        {"page_title": "Novo usuário", "form": form},
    )


@require_permission("users.update")
def user_update(request, pk):
    user_obj = get_object_or_404(_user_queryset(), pk=pk)
    profile = getattr(user_obj, "profile", None)
    form = UserUpdateForm(request.POST or None, instance=user_obj, profile=profile)
    if request.method == "POST" and form.is_valid():
        try:
            update_managed_user(
                user=user_obj,
                form=form,
                actor=request.user,
                request=request,
            )
        except PermissionDenied as exc:
            add_permission_error(request, exc)
        else:
            messages.success(request, "Usuário atualizado com sucesso.")
            return redirect("accounts:user_detail", pk=user_obj.pk)
    return render(
        request,
        "accounts/user_form.html",
        {
            "page_title": f"Editar {user_obj.username}",
            "form": form,
            "user_obj": user_obj,
        },
    )


@require_permission("users.manage_roles")
def user_access(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    current = UserAccess.objects.filter(user=user_obj, is_active=True).first()
    form = UserAccessForm(request.POST or None, instance=current)
    if request.method == "POST" and form.is_valid():
        try:
            assign_user_access(
                user=user_obj,
                form=form,
                actor=request.user,
                request=request,
            )
        except PermissionDenied as exc:
            add_permission_error(request, exc)
        else:
            messages.success(request, "Acesso atualizado com sucesso.")
            return redirect("accounts:user_detail", pk=user_obj.pk)
    history = UserAccess.objects.filter(user=user_obj).select_related("role", "manager")
    return render(
        request,
        "accounts/user_access_form.html",
        {
            "page_title": f"Acessos de {user_obj.username}",
            "form": form,
            "user_obj": user_obj,
            "history": history,
        },
    )


@require_permission("users.deactivate")
def user_deactivate(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        try:
            deactivate_user(user_obj, actor=request.user, request=request)
        except PermissionDenied as exc:
            add_permission_error(request, exc)
        else:
            messages.success(request, "Usuário desativado e sessões revogadas.")
        return redirect("accounts:user_detail", pk=user_obj.pk)
    return render(
        request,
        "erp/confirm_action.html",
        {
            "page_title": "Desativar usuário",
            "message": f"Desativar {user_obj.username}?",
            "cancel_url": user_obj.pk,
            "cancel_route": "accounts:user_detail",
        },
    )


@require_permission("users.update")
def user_activate(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        reactivate_user(user_obj, actor=request.user, request=request)
        messages.success(request, "Usuário reativado com sucesso.")
        return redirect("accounts:user_detail", pk=user_obj.pk)
    return render(
        request,
        "erp/confirm_action.html",
        {
            "page_title": "Reativar usuário",
            "message": f"Reativar {user_obj.username}?",
            "cancel_url": user_obj.pk,
            "cancel_route": "accounts:user_detail",
        },
    )


@require_permission("users.update")
def user_password_reset(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    form = AdminPasswordResetForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        reset_user_password(
            user=user_obj,
            form=form,
            actor=request.user,
            request=request,
        )
        messages.success(request, "Senha redefinida com sucesso.")
        return redirect("accounts:user_detail", pk=user_obj.pk)
    return render(
        request,
        "accounts/password_reset_form.html",
        {"page_title": f"Redefinir senha de {user_obj.username}", "form": form},
    )


@require_permission("users.view")
def user_sessions(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        revoke_user_sessions(user=user_obj, actor=request.user, request=request)
        messages.success(request, "Sessões ativas revogadas.")
        return redirect("accounts:user_sessions", pk=user_obj.pk)
    qs = UserSessionLog.objects.filter(user=user_obj)
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "accounts/session_list.html",
        {
            "page_title": f"Sessões de {user_obj.username}",
            "page_obj": page_obj,
            "user_obj": user_obj,
        },
    )


@require_permission("users.view")
def user_history(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    qs = AuditEvent.objects.filter(object_type="User", object_id=str(user_obj.pk))
    page_obj = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(
        request,
        "audit/audit_list.html",
        {"page_title": f"Histórico de {user_obj.username}", "page_obj": page_obj},
    )


@require_permission("users.view")
def session_list(request):
    qs = UserSessionLog.objects.select_related("user").all()
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "accounts/session_list.html",
        {"page_title": "Sessões de usuários", "page_obj": page_obj},
    )
