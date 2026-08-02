# ruff: noqa: PLR0913
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render

from access_control.services.authorization import require_permission
from access_control.services.authorization import user_has_permission
from after_sales.forms import AfterSalesCaseCreateForm
from after_sales.forms import AssignCaseForm
from after_sales.forms import AttachmentForm
from after_sales.forms import ChangeStatusForm
from after_sales.forms import CloseCaseForm
from after_sales.forms import DiagnosisForm
from after_sales.forms import InstallationPendingForm
from after_sales.forms import InteractionForm
from after_sales.forms import MaterialRequestForm
from after_sales.forms import MediaConsentForm
from after_sales.forms import ReasonForm
from after_sales.forms import ReferralForm
from after_sales.forms import ResolveCaseForm
from after_sales.forms import ResolvePendingForm
from after_sales.forms import ReviewRequestForm
from after_sales.forms import ReworkLinkForm
from after_sales.forms import SatisfactionSurveyForm
from after_sales.forms import ScheduleVisitForm
from after_sales.forms import SurveyResponseForm
from after_sales.forms import WarrantyDecisionForm
from after_sales.forms import WarrantyForm
from after_sales.models import AfterSalesAttachment
from after_sales.models import CasePriority
from after_sales.models import CaseSeverity
from after_sales.models import CaseStatus
from after_sales.models import CaseType
from after_sales.models import CustomerReferral
from after_sales.models import CustomerSatisfactionSurvey
from after_sales.models import InstallationPendingItem
from after_sales.models import MediaUsageConsent
from after_sales.models import PendingStatus
from after_sales.models import ReviewRequest
from after_sales.models import WarrantyRecord
from after_sales.selectors import after_sales_dashboard_metrics
from after_sales.selectors import cases_queryset_for_user
from after_sales.selectors import filter_cases
from after_sales.selectors import parse_period
from after_sales.services.cases import add_diagnosis
from after_sales.services.cases import add_interaction
from after_sales.services.cases import assign_case
from after_sales.services.cases import cancel_case
from after_sales.services.cases import change_case_status
from after_sales.services.cases import close_after_sales_case
from after_sales.services.cases import link_rework
from after_sales.services.cases import open_after_sales_case
from after_sales.services.cases import reject_case
from after_sales.services.cases import reopen_case
from after_sales.services.cases import request_material
from after_sales.services.cases import resolve_after_sales_case
from after_sales.services.cases import schedule_case_visit
from after_sales.services.cases import start_case_work
from after_sales.services.cases import triage_case
from after_sales.services.follow_up import create_installation_pending
from after_sales.services.follow_up import resolve_installation_pending
from after_sales.services.satisfaction import convert_referral_to_lead
from after_sales.services.satisfaction import create_referral
from after_sales.services.satisfaction import create_review_request
from after_sales.services.satisfaction import create_satisfaction_survey
from after_sales.services.satisfaction import record_media_consent
from after_sales.services.satisfaction import register_survey_response
from after_sales.services.satisfaction import revoke_media_consent
from after_sales.services.warranties import create_warranty_record
from after_sales.services.warranties import decide_warranty_eligibility
from after_sales.services.warranties import evaluate_warranty_eligibility
from audit.services import record_audit_event
from salespeople.models import Salesperson


def _case_or_403(request, pk):
    return get_object_or_404(cases_queryset_for_user(request.user), pk=pk)


def _handle_exc(request, exc):
    messages.error(request, str(exc))


@require_permission("after_sales_dashboard.view")
def dashboard(request):
    start, end, period = parse_period(request)
    metrics = after_sales_dashboard_metrics(
        user=request.user,
        start=start,
        end=end,
        assigned_user=request.GET.get("assigned_user") or None,
        case_type=request.GET.get("case_type") or None,
        status=request.GET.get("status") or None,
    )
    return render(
        request,
        "after_sales/dashboard.html",
        {
            "page_title": "Dashboard de Pós-venda",
            "metrics": metrics,
            "period": period,
            "case_types": CaseType.choices,
            "status_choices": CaseStatus.choices,
        },
    )


@require_permission("after_sales_cases.view")
def case_list(request):
    qs = filter_cases(cases_queryset_for_user(request.user), request.GET)
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "after_sales/case_list.html",
        {
            "page_title": "Casos de pós-venda",
            "page_obj": page_obj,
            "status_choices": CaseStatus.choices,
            "type_choices": CaseType.choices,
            "priority_choices": CasePriority.choices,
            "severity_choices": CaseSeverity.choices,
            "salespeople": Salesperson.objects.filter(is_active=True),
        },
    )


@require_permission("after_sales_cases.create")
def case_create(request):
    form = AfterSalesCaseCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            case = open_after_sales_case(
                actor=request.user,
                customer=data["customer"],
                sales_order=data.get("sales_order"),
                delivery_schedule=data.get("delivery_schedule"),
                installation_schedule=data.get("installation_schedule"),
                case_type=data["case_type"],
                subject=data["subject"],
                description=data["description"],
                priority=data["priority"],
                severity=data["severity"],
                reported_by_name=data.get("reported_by_name") or "",
                reported_by_phone=data.get("reported_by_phone") or "",
                reported_channel=data.get("reported_channel") or "",
                next_action_at=data.get("next_action_at"),
                allow_without_order=bool(data.get("allow_without_order")),
                request=request,
            )
        except (ValidationError, PermissionDenied) as exc:
            _handle_exc(request, exc)
        else:
            messages.success(request, f"Caso {case.code} aberto.")
            return redirect("after_sales:case_detail", pk=case.pk)
    return render(
        request,
        "after_sales/simple_form.html",
        {
            "page_title": "Novo caso de pós-venda",
            "form": form,
            "cancel_url": "after_sales:case_list",
        },
    )


@require_permission("after_sales_cases.view")
def case_detail(request, pk):
    case = _case_or_403(request, pk)
    from scheduling.models import OperationalEvent

    events = OperationalEvent.objects.filter(after_sales_case=case).order_by("-start_at")
    return render(
        request,
        "after_sales/case_detail.html",
        {
            "page_title": case.code,
            "case": case,
            "interactions": case.interactions.all()[:50],
            "history": case.history.all()[:50],
            "attachments": case.attachments.all()[:50],
            "pending_items": case.pending_items.all(),
            "surveys": case.satisfaction_surveys.all(),
            "events": events,
            "assign_form": AssignCaseForm(),
            "interaction_form": InteractionForm(),
            "diagnosis_form": DiagnosisForm(
                initial={
                    "technical_diagnosis": case.technical_diagnosis,
                    "root_cause": case.root_cause,
                    "root_cause_notes": case.root_cause_notes,
                    "responsibility": case.responsibility,
                    "responsibility_notes": case.responsibility_notes,
                },
            ),
            "resolve_form": ResolveCaseForm(
                initial={
                    "root_cause": case.root_cause,
                    "responsibility": case.responsibility,
                },
            ),
            "close_form": CloseCaseForm(),
            "reason_form": ReasonForm(),
            "status_form": ChangeStatusForm(),
            "visit_form": ScheduleVisitForm(),
            "warranty_decision_form": WarrantyDecisionForm(
                initial={"warranty": case.warranty_id},
            ),
            "material_form": MaterialRequestForm(),
            "rework_form": ReworkLinkForm(
                initial={"production_order": case.rework_production_order_id},
            ),
            "attachment_form": AttachmentForm(),
            "can_assign": user_has_permission(request.user, "after_sales_cases.assign"),
            "can_diagnose": user_has_permission(request.user, "after_sales_cases.diagnose"),
            "can_resolve": user_has_permission(request.user, "after_sales_cases.resolve"),
            "can_close": user_has_permission(request.user, "after_sales_cases.close"),
            "can_decide_warranty": user_has_permission(request.user, "warranties.decide"),
        },
    )


def _post_action(request, pk, service_call, success_msg):
    case = _case_or_403(request, pk)
    if request.method != "POST":
        return redirect("after_sales:case_detail", pk=pk)
    try:
        service_call(case)
    except (ValidationError, PermissionDenied) as exc:
        _handle_exc(request, exc)
    else:
        messages.success(request, success_msg)
    return redirect("after_sales:case_detail", pk=pk)


@require_permission("after_sales_cases.change_status")
def case_triage(request, pk):
    return _post_action(
        request,
        pk,
        lambda case: triage_case(case=case, actor=request.user, request=request),
        "Caso triado.",
    )


@require_permission("after_sales_cases.assign")
def case_assign(request, pk):
    case = _case_or_403(request, pk)
    form = AssignCaseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            assign_case(
                case=case,
                actor=request.user,
                assigned_user=form.cleaned_data.get("assigned_user"),
                assigned_salesperson=form.cleaned_data.get("assigned_salesperson"),
                request=request,
            )
        except (ValidationError, PermissionDenied) as exc:
            _handle_exc(request, exc)
        else:
            messages.success(request, "Caso atribuído.")
    return redirect("after_sales:case_detail", pk=pk)


@require_permission("after_sales_cases.change_status")
def case_change_status(request, pk):
    case = _case_or_403(request, pk)
    form = ChangeStatusForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            change_case_status(
                case=case,
                actor=request.user,
                new_status=form.cleaned_data["new_status"],
                notes=form.cleaned_data.get("notes") or "",
                request=request,
            )
        except (ValidationError, PermissionDenied) as exc:
            _handle_exc(request, exc)
        else:
            messages.success(request, "Status atualizado.")
    return redirect("after_sales:case_detail", pk=pk)


@require_permission("after_sales_cases.update")
def case_interaction(request, pk):
    case = _case_or_403(request, pk)
    form = InteractionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            add_interaction(case=case, actor=request.user, request=request, **form.cleaned_data)
        except (ValidationError, PermissionDenied) as exc:
            _handle_exc(request, exc)
        else:
            messages.success(request, "Interação registrada.")
    return redirect("after_sales:case_detail", pk=pk)


@require_permission("after_sales_cases.diagnose")
def case_diagnosis(request, pk):
    case = _case_or_403(request, pk)
    form = DiagnosisForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            add_diagnosis(case=case, actor=request.user, request=request, **form.cleaned_data)
        except (ValidationError, PermissionDenied) as exc:
            _handle_exc(request, exc)
        else:
            messages.success(request, "Diagnóstico registrado.")
    return redirect("after_sales:case_detail", pk=pk)


@require_permission("warranties.view")
def case_evaluate_warranty(request, pk):
    case = _case_or_403(request, pk)
    try:
        decision, notes = evaluate_warranty_eligibility(case=case, actor=request.user)
    except (ValidationError, PermissionDenied) as exc:
        _handle_exc(request, exc)
    else:
        messages.info(request, f"Avaliação automática: {decision} — {notes}")
    return redirect("after_sales:case_detail", pk=pk)


@require_permission("warranties.decide")
def case_decide_warranty(request, pk):
    case = _case_or_403(request, pk)
    form = WarrantyDecisionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            decide_warranty_eligibility(
                case=case,
                actor=request.user,
                decision=form.cleaned_data["decision"],
                notes=form.cleaned_data["notes"],
                warranty=form.cleaned_data.get("warranty"),
                request=request,
            )
        except (ValidationError, PermissionDenied) as exc:
            _handle_exc(request, exc)
        else:
            messages.success(request, "Decisão de garantia registrada.")
    return redirect("after_sales:case_detail", pk=pk)


@require_permission("after_sales_cases.update")
def case_schedule_visit(request, pk):
    case = _case_or_403(request, pk)
    form = ScheduleVisitForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            event = schedule_case_visit(
                case=case,
                actor=request.user,
                start_at=data["start_at"],
                end_at=data.get("end_at"),
                title=data.get("title") or "",
                address=data.get("address") or "",
                city=data.get("city") or "",
                state=data.get("state") or "",
                contact_phone=data.get("contact_phone") or "",
                description=data.get("description") or "",
                request=request,
            )
        except (ValidationError, PermissionDenied) as exc:
            _handle_exc(request, exc)
        else:
            messages.success(request, f"Visita agendada ({event.code}).")
    return redirect("after_sales:case_detail", pk=pk)


@require_permission("after_sales_cases.update")
def case_request_material(request, pk):
    case = _case_or_403(request, pk)
    form = MaterialRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            request_material(
                case=case,
                actor=request.user,
                notes=form.cleaned_data["notes"],
                request=request,
            )
        except (ValidationError, PermissionDenied) as exc:
            _handle_exc(request, exc)
        else:
            messages.success(request, "Solicitação de material registrada.")
    return redirect("after_sales:case_detail", pk=pk)


@require_permission("after_sales_cases.change_status")
def case_start(request, pk):
    return _post_action(
        request,
        pk,
        lambda case: start_case_work(case=case, actor=request.user, request=request),
        "Atendimento iniciado.",
    )


@require_permission("after_sales_cases.resolve")
def case_resolve(request, pk):
    case = _case_or_403(request, pk)
    form = ResolveCaseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            resolve_after_sales_case(case=case, actor=request.user, request=request, **form.cleaned_data)
        except (ValidationError, PermissionDenied) as exc:
            _handle_exc(request, exc)
        else:
            messages.success(request, "Caso resolvido.")
    return redirect("after_sales:case_detail", pk=pk)


@require_permission("after_sales_cases.close")
def case_close(request, pk):
    case = _case_or_403(request, pk)
    form = CloseCaseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            close_after_sales_case(
                case=case,
                actor=request.user,
                closing_notes=form.cleaned_data.get("closing_notes") or "",
                request=request,
            )
        except (ValidationError, PermissionDenied) as exc:
            _handle_exc(request, exc)
        else:
            messages.success(request, "Caso fechado.")
    return redirect("after_sales:case_detail", pk=pk)


@require_permission("after_sales_cases.reopen")
def case_reopen(request, pk):
    case = _case_or_403(request, pk)
    form = ReasonForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reopen_case(
                case=case,
                actor=request.user,
                reason=form.cleaned_data["reason"],
                request=request,
            )
        except (ValidationError, PermissionDenied) as exc:
            _handle_exc(request, exc)
        else:
            messages.success(request, "Caso reaberto.")
    return redirect("after_sales:case_detail", pk=pk)


@require_permission("after_sales_cases.reject")
def case_reject(request, pk):
    case = _case_or_403(request, pk)
    form = ReasonForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reject_case(
                case=case,
                actor=request.user,
                reason=form.cleaned_data["reason"],
                request=request,
            )
        except (ValidationError, PermissionDenied) as exc:
            _handle_exc(request, exc)
        else:
            messages.success(request, "Caso rejeitado.")
    return redirect("after_sales:case_detail", pk=pk)


@require_permission("after_sales_cases.cancel")
def case_cancel(request, pk):
    case = _case_or_403(request, pk)
    form = ReasonForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            cancel_case(
                case=case,
                actor=request.user,
                reason=form.cleaned_data["reason"],
                request=request,
            )
        except (ValidationError, PermissionDenied) as exc:
            _handle_exc(request, exc)
        else:
            messages.success(request, "Caso cancelado.")
    return redirect("after_sales:case_detail", pk=pk)


@require_permission("after_sales_cases.update")
def case_link_rework(request, pk):
    case = _case_or_403(request, pk)
    form = ReworkLinkForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            link_rework(
                case=case,
                actor=request.user,
                production_order=form.cleaned_data.get("production_order"),
                estimated_cost=form.cleaned_data.get("estimated_cost"),
                notes=form.cleaned_data.get("notes") or "",
                request=request,
            )
        except (ValidationError, PermissionDenied) as exc:
            _handle_exc(request, exc)
        else:
            messages.success(request, "Retrabalho vinculado.")
    return redirect("after_sales:case_detail", pk=pk)


@require_permission("after_sales_cases.update")
def case_attach(request, pk):
    case = _case_or_403(request, pk)
    form = AttachmentForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        att = form.save(commit=False)
        att.case = case
        att.uploaded_by = request.user
        att.save()
        record_audit_event(
            request=request,
            user=request.user,
            event_type="create",
            module="after_sales",
            action="case_attachment_added",
            obj=case,
            metadata={"attachment_id": att.pk},
        )
        messages.success(request, "Anexo registrado.")
    elif request.method == "POST":
        messages.error(request, "Anexo inválido.")
    return redirect("after_sales:case_detail", pk=pk)


@require_permission("installation_pending_items.view")
def pending_list(request):
    qs = InstallationPendingItem.objects.select_related(
        "sales_order",
        "installation_schedule",
        "after_sales_case",
        "responsible",
    ).order_by("due_date", "-created_at")
    status = request.GET.get("status")
    if status:
        qs = qs.filter(status=status)
    if request.GET.get("open") == "1":
        qs = qs.filter(
            status__in=[PendingStatus.OPEN, PendingStatus.SCHEDULED, PendingStatus.IN_PROGRESS],
        )
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "after_sales/pending_list.html",
        {
            "page_title": "Pendências de instalação",
            "page_obj": page_obj,
            "status_choices": PendingStatus.choices,
        },
    )


@require_permission("installation_pending_items.create")
def pending_create(request):
    form = InstallationPendingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            item, case = create_installation_pending(
                actor=request.user,
                installation_schedule=data["installation_schedule"],
                description=data["description"],
                priority=data["priority"],
                responsible=data.get("responsible"),
                due_date=data.get("due_date"),
                create_case=bool(data.get("create_case")),
                request=request,
            )
        except (ValidationError, PermissionDenied) as exc:
            _handle_exc(request, exc)
        else:
            msg = "Pendência registrada."
            if case:
                msg += f" Caso {case.code} criado."
            messages.success(request, msg)
            return redirect("after_sales:pending_list")
    return render(
        request,
        "after_sales/simple_form.html",
        {
            "page_title": "Registrar pendência",
            "form": form,
            "cancel_url": "after_sales:pending_list",
        },
    )


@require_permission("installation_pending_items.update")
def pending_resolve(request, pk):
    item = get_object_or_404(InstallationPendingItem, pk=pk)
    form = ResolvePendingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            resolve_installation_pending(
                item=item,
                actor=request.user,
                resolution=form.cleaned_data["resolution"],
                request=request,
            )
        except (ValidationError, PermissionDenied) as exc:
            _handle_exc(request, exc)
        else:
            messages.success(request, "Pendência resolvida.")
            return redirect("after_sales:pending_list")
    return render(
        request,
        "after_sales/simple_form.html",
        {
            "page_title": "Resolver pendência",
            "form": form,
            "cancel_url": "after_sales:pending_list",
        },
    )


@require_permission("warranties.view")
def warranty_list(request):
    qs = WarrantyRecord.objects.select_related("customer", "sales_order").order_by("-start_date")
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "after_sales/warranty_list.html",
        {"page_title": "Garantias", "page_obj": page_obj},
    )


@require_permission("warranties.create")
def warranty_create(request):
    form = WarrantyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            warranty = create_warranty_record(actor=request.user, request=request, **data)
        except (ValidationError, PermissionDenied) as exc:
            _handle_exc(request, exc)
        else:
            messages.success(request, f"Garantia {warranty.number} criada.")
            return redirect("after_sales:warranty_detail", pk=warranty.pk)
    return render(
        request,
        "after_sales/simple_form.html",
        {
            "page_title": "Nova garantia",
            "form": form,
            "cancel_url": "after_sales:warranty_list",
        },
    )


@require_permission("warranties.view")
def warranty_detail(request, pk):
    warranty = get_object_or_404(
        WarrantyRecord.objects.select_related("customer", "sales_order", "policy"),
        pk=pk,
    )
    return render(
        request,
        "after_sales/warranty_detail.html",
        {"page_title": warranty.number, "warranty": warranty, "cases": warranty.cases.all()[:20]},
    )


@require_permission("customer_satisfaction.view")
def survey_list(request):
    qs = CustomerSatisfactionSurvey.objects.select_related("customer", "sales_order").order_by(
        "-requested_at",
    )
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "after_sales/survey_list.html",
        {"page_title": "Pesquisas de satisfação", "page_obj": page_obj},
    )


@require_permission("customer_satisfaction.create")
def survey_create(request):
    form = SatisfactionSurveyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            survey = create_satisfaction_survey(actor=request.user, request=request, **data)
        except (ValidationError, PermissionDenied) as exc:
            _handle_exc(request, exc)
        else:
            messages.success(request, "Pesquisa criada.")
            return redirect("after_sales:survey_list")
    return render(
        request,
        "after_sales/simple_form.html",
        {
            "page_title": "Nova pesquisa",
            "form": form,
            "cancel_url": "after_sales:survey_list",
        },
    )


@require_permission("customer_satisfaction.update")
def survey_respond(request, pk):
    survey = get_object_or_404(CustomerSatisfactionSurvey, pk=pk)
    form = SurveyResponseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            register_survey_response(
                survey=survey,
                actor=request.user,
                request=request,
                **form.cleaned_data,
            )
        except (ValidationError, PermissionDenied) as exc:
            _handle_exc(request, exc)
        else:
            messages.success(request, "Resposta registrada.")
            return redirect("after_sales:survey_list")
    return render(
        request,
        "after_sales/simple_form.html",
        {
            "page_title": "Registrar satisfação",
            "form": form,
            "cancel_url": "after_sales:survey_list",
        },
    )


@require_permission("review_requests.view")
def review_list(request):
    qs = ReviewRequest.objects.select_related("customer", "sales_order").order_by("-requested_at")
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "after_sales/review_list.html",
        {"page_title": "Solicitações de avaliação", "page_obj": page_obj},
    )


@require_permission("review_requests.create")
def review_create(request):
    form = ReviewRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            create_review_request(
                actor=request.user,
                customer=data["customer"],
                sales_order=data.get("sales_order"),
                channel=data.get("channel") or "",
                notes=data.get("notes") or "",
                request=request,
            )
        except (ValidationError, PermissionDenied) as exc:
            _handle_exc(request, exc)
        else:
            messages.success(request, "Solicitação de avaliação registrada.")
            return redirect("after_sales:review_list")
    return render(
        request,
        "after_sales/simple_form.html",
        {
            "page_title": "Solicitar avaliação",
            "form": form,
            "cancel_url": "after_sales:review_list",
        },
    )


@require_permission("media_usage_consents.view")
def consent_list(request):
    qs = MediaUsageConsent.objects.select_related("customer", "sales_order").order_by("-created_at")
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "after_sales/consent_list.html",
        {"page_title": "Autorizações de imagem", "page_obj": page_obj},
    )


@require_permission("media_usage_consents.create")
def consent_create(request):
    form = MediaConsentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            record_media_consent(actor=request.user, request=request, **data)
        except (ValidationError, PermissionDenied) as exc:
            _handle_exc(request, exc)
        else:
            messages.success(request, "Consentimento registrado.")
            return redirect("after_sales:consent_list")
    return render(
        request,
        "after_sales/simple_form.html",
        {
            "page_title": "Registrar autorização de imagem",
            "form": form,
            "cancel_url": "after_sales:consent_list",
        },
    )


@require_permission("media_usage_consents.update")
def consent_revoke(request, pk):
    consent = get_object_or_404(MediaUsageConsent, pk=pk)
    if request.method == "POST":
        try:
            revoke_media_consent(
                consent=consent,
                actor=request.user,
                notes=request.POST.get("notes", ""),
                request=request,
            )
        except (ValidationError, PermissionDenied) as exc:
            _handle_exc(request, exc)
        else:
            messages.success(request, "Consentimento revogado.")
    return redirect("after_sales:consent_list")


@require_permission("customer_referrals.view")
def referral_list(request):
    qs = CustomerReferral.objects.select_related(
        "referring_customer",
        "sales_order",
        "converted_lead",
    ).order_by("-created_at")
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "after_sales/referral_list.html",
        {"page_title": "Indicações", "page_obj": page_obj},
    )


@require_permission("customer_referrals.create")
def referral_create(request):
    form = ReferralForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            create_referral(actor=request.user, request=request, **data)
        except (ValidationError, PermissionDenied) as exc:
            _handle_exc(request, exc)
        else:
            messages.success(request, "Indicação registrada.")
            return redirect("after_sales:referral_list")
    return render(
        request,
        "after_sales/simple_form.html",
        {
            "page_title": "Registrar indicação",
            "form": form,
            "cancel_url": "after_sales:referral_list",
        },
    )


@require_permission("customer_referrals.convert")
def referral_convert(request, pk):
    referral = get_object_or_404(CustomerReferral, pk=pk)
    if request.method == "POST":
        try:
            lead = convert_referral_to_lead(referral=referral, actor=request.user, request=request)
        except (ValidationError, PermissionDenied) as exc:
            _handle_exc(request, exc)
        else:
            messages.success(request, f"Lead {lead.code} criado a partir da indicação.")
    return redirect("after_sales:referral_list")
