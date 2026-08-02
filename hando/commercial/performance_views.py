# ruff: noqa: PLR0913
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone

from access_control.services.authorization import require_permission
from access_control.services.authorization import user_has_permission
from commercial.performance_forms import ManualScoreAdjustmentForm
from commercial.performance_forms import SalesGoalForm
from commercial.performance_forms import SalesScorePolicyForm
from commercial.performance_goals import create_sales_goal
from commercial.performance_goals import deactivate_sales_goal
from commercial.performance_goals import update_sales_goal
from commercial.performance_metrics import active_goal_for_salesperson
from commercial.performance_metrics import compute_goal_progress
from commercial.performance_metrics import compute_salesperson_metrics
from commercial.performance_metrics import salespersons_for_scope
from commercial.performance_metrics import team_summary
from commercial.performance_models import SalesGoal
from commercial.performance_models import SalesScoreEvent
from commercial.performance_models import SalesScorePolicy
from commercial.performance_period import PERIOD_CHOICES
from commercial.performance_period import parse_performance_period
from commercial.performance_ranking import build_ranking
from commercial.performance_score import activate_score_policy
from commercial.performance_score import record_manual_score_adjustment
from core.utils import format_brl
from salespeople.models import Salesperson


def _period_context(request):
    start, end, period = parse_performance_period(request)
    return {
        "period": period,
        "period_choices": PERIOD_CHOICES,
        "start": start,
        "end": end,
        "period_start": start.date() if hasattr(start, "date") else start,
        "period_end": end.date() if hasattr(end, "date") else end,
    }


@require_permission("sales_ranking.view")
def ranking_view(request):
    ctx = _period_context(request)
    metric = request.GET.get("metric", "score")
    include_inactive = request.GET.get("include_inactive") == "1"
    ranking = build_ranking(
        user=request.user,
        start=ctx["start"],
        end=ctx["end"],
        metric=metric,
        include_inactive=include_inactive,
    )
    return render(
        request,
        "commercial/performance/ranking.html",
        {
            "page_title": "Ranking Comercial",
            **ctx,
            **ranking,
            "include_inactive": include_inactive,
            "format_brl": format_brl,
        },
    )


@require_permission("sales_performance.view_own")
def my_performance_view(request):
    ctx = _period_context(request)
    salesperson = getattr(request.user, "salesperson", None)
    if not salesperson:
        return render(
            request,
            "commercial/performance/my_performance.html",
            {
                "page_title": "Meu Desempenho",
                "no_salesperson": True,
                **ctx,
            },
        )
    metrics = compute_salesperson_metrics(
        salesperson=salesperson,
        start=ctx["start"],
        end=ctx["end"],
    )
    goal = active_goal_for_salesperson(salesperson=salesperson)
    goal_data = compute_goal_progress(goal=goal, metrics=metrics) if goal else None
    ranking = build_ranking(user=request.user, start=ctx["start"], end=ctx["end"])
    my_row = next((r for r in ranking["rows"] if r["salesperson"].pk == salesperson.pk), None)
    prev_start = ctx["start"] - (ctx["end"] - ctx["start"])
    prev_metrics = compute_salesperson_metrics(
        salesperson=salesperson,
        start=prev_start,
        end=ctx["start"],
    )
    recent_events = SalesScoreEvent.objects.filter(salesperson=salesperson).select_related(
        "policy",
        "created_by",
    )[:15]
    from commercial.lead_models import LeadTask
    from commercial.lead_models import LeadTaskStatus
    from commercial.lead_models import LeadStatus
    from commercial.lead_queries import leads_queryset_for_user

    my_leads = leads_queryset_for_user(request.user).filter(assigned_salesperson=salesperson)
    pending_tasks = LeadTask.objects.filter(
        lead__in=my_leads,
        assigned_to=request.user,
        status__in=[LeadTaskStatus.PENDING, LeadTaskStatus.IN_PROGRESS],
    ).order_by("due_at")[:10]
    return render(
        request,
        "commercial/performance/my_performance.html",
        {
            "page_title": "Meu Desempenho",
            "salesperson": salesperson,
            "metrics": metrics,
            "goal": goal,
            "goal_data": goal_data,
            "position": my_row["position"] if my_row else None,
            "prev_metrics": prev_metrics,
            "recent_events": recent_events,
            "pending_tasks": pending_tasks,
            "negotiations": my_leads.filter(status=LeadStatus.NEGOTIATION).count(),
            "format_brl": format_brl,
            **ctx,
        },
    )


@require_permission("sales_performance.view_all")
def team_performance_view(request):
    ctx = _period_context(request)
    salesperson_id = request.GET.get("salesperson", "").strip()
    salespersons = salespersons_for_scope(user=request.user)
    selected = None
    if salesperson_id.isdigit():
        selected = salespersons.filter(pk=int(salesperson_id)).first()
    summary = team_summary(user=request.user, start=ctx["start"], end=ctx["end"])
    rows = summary["rows"]
    if selected:
        rows = [r for r in rows if r["salesperson"].pk == selected.pk]
    ranking = build_ranking(user=request.user, start=ctx["start"], end=ctx["end"])
    return render(
        request,
        "commercial/performance/team_performance.html",
        {
            "page_title": "Desempenho da Equipe",
            "summary": summary,
            "rows": rows,
            "salespeople": salespersons,
            "selected_salesperson": selected,
            "ranking_top": ranking["rows"][:5],
            "format_brl": format_brl,
            **ctx,
        },
    )


@require_permission("sales_goals.view")
def goal_list(request):
    qs = SalesGoal.objects.select_related("salesperson").order_by("-start_date")
    if not user_has_permission(request.user, "sales_performance.view_all"):
        salesperson = getattr(request.user, "salesperson", None)
        if salesperson:
            qs = qs.filter(salesperson=salesperson)
        else:
            qs = qs.none()
    sp_filter = request.GET.get("salesperson", "").strip()
    if sp_filter.isdigit():
        qs = qs.filter(salesperson_id=int(sp_filter))
    if request.GET.get("active") == "1":
        qs = qs.filter(is_active=True)
    elif request.GET.get("active") == "0":
        qs = qs.filter(is_active=False)
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    rows = []
    for goal in page_obj:
        rows.append({"goal": goal, "progress": compute_goal_progress(goal=goal)})
    return render(
        request,
        "commercial/performance/goal_list.html",
        {
            "page_title": "Metas Comerciais",
            "page_obj": page_obj,
            "rows": rows,
            "salespeople": Salesperson.objects.filter(is_active=True),
            "format_brl": format_brl,
        },
    )


@require_permission("sales_goals.create")
def goal_create(request):
    form = SalesGoalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        goal = create_sales_goal(form=form, actor=request.user, request=request)
        messages.success(request, f"Meta criada para {goal.salesperson.display_name}.")
        return redirect("leads:goal_detail", pk=goal.pk)
    return render(
        request,
        "commercial/performance/goal_form.html",
        {"page_title": "Nova Meta", "form": form},
    )


@require_permission("sales_goals.view")
def goal_detail(request, pk):
    goal = get_object_or_404(SalesGoal.objects.select_related("salesperson"), pk=pk)
    if not user_has_permission(request.user, "sales_performance.view_all"):
        sp = getattr(request.user, "salesperson", None)
        if not sp or goal.salesperson_id != sp.pk:
            raise PermissionDenied
    progress = compute_goal_progress(goal=goal)
    return render(
        request,
        "commercial/performance/goal_detail.html",
        {
            "page_title": f"Meta — {goal.salesperson.display_name}",
            "goal": goal,
            "progress": progress,
            "format_brl": format_brl,
        },
    )


@require_permission("sales_goals.update")
def goal_update(request, pk):
    goal = get_object_or_404(SalesGoal, pk=pk)
    form = SalesGoalForm(request.POST or None, instance=goal)
    if request.method == "POST" and form.is_valid():
        update_sales_goal(goal=goal, form=form, actor=request.user, request=request)
        messages.success(request, "Meta atualizada.")
        return redirect("leads:goal_detail", pk=goal.pk)
    return render(
        request,
        "commercial/performance/goal_form.html",
        {"page_title": "Editar Meta", "form": form, "goal": goal},
    )


@require_permission("sales_goals.deactivate")
def goal_deactivate(request, pk):
    goal = get_object_or_404(SalesGoal, pk=pk)
    if request.method == "POST":
        deactivate_sales_goal(goal=goal, actor=request.user, request=request)
        messages.success(request, "Meta desativada.")
        return redirect("leads:goal_list")
    return redirect("leads:goal_detail", pk=goal.pk)


@require_permission("sales_score_policy.view")
def score_policy_list(request):
    policies = SalesScorePolicy.objects.order_by("-valid_from")
    return render(
        request,
        "commercial/performance/policy_list.html",
        {
            "page_title": "Política de Score",
            "policies": policies,
        },
    )


@require_permission("sales_score_policy.create")
def score_policy_create(request):
    form = SalesScorePolicyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        policy = form.save(commit=False)
        policy.created_by = request.user
        policy.updated_by = request.user
        try:
            policy.full_clean()
            policy.save()
            if policy.is_active:
                activate_score_policy(policy=policy, actor=request.user, request=request)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Política criada.")
            return redirect("leads:score_policy_list")
    return render(
        request,
        "commercial/performance/policy_form.html",
        {"page_title": "Nova Política de Score", "form": form},
    )


@require_permission("sales_score_policy.update")
def score_policy_update(request, pk):
    policy = get_object_or_404(SalesScorePolicy, pk=pk)
    form = SalesScorePolicyForm(request.POST or None, instance=policy)
    if request.method == "POST" and form.is_valid():
        policy = form.save(commit=False)
        policy.updated_by = request.user
        try:
            policy.full_clean()
            policy.save()
            if policy.is_active:
                activate_score_policy(policy=policy, actor=request.user, request=request)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Política atualizada.")
            return redirect("leads:score_policy_list")
    return render(
        request,
        "commercial/performance/policy_form.html",
        {"page_title": "Editar Política de Score", "form": form, "policy": policy},
    )


@require_permission("sales_score_events.adjust")
def score_adjust(request):
    form = ManualScoreAdjustmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            record_manual_score_adjustment(
                salesperson=form.cleaned_data["salesperson"],
                points=form.cleaned_data["points"],
                adjustment_date=form.cleaned_data["adjustment_date"],
                justification=(
                    form.cleaned_data["justification"]
                    + (
                        f" Ref: {form.cleaned_data['reference']}"
                        if form.cleaned_data.get("reference")
                        else ""
                    )
                ),
                actor=request.user,
                request=request,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Ajuste registrado no ledger.")
            return redirect("leads:score_policy_list")
    return render(
        request,
        "commercial/performance/score_adjust.html",
        {"page_title": "Ajustar Pontuação", "form": form},
    )
