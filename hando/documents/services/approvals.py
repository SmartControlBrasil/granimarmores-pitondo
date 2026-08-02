# ruff: noqa: PLR0913
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from audit.services import record_audit_event
from documents.models import ApprovalStepStatus
from documents.models import DocumentApprovalStep
from documents.models import DocumentReview
from documents.models import DocumentStatus
from documents.models import ReviewStatus
from documents.models import VersionStatus


@transaction.atomic
def submit_document_for_review(*, document, actor, reviewers=None, request=None):
    if not user_has_permission(actor, "documents.submit_review"):
        raise PermissionDenied("Sem permissão.")
    version = document.current_version
    if not version:
        raise ValidationError("Documento sem versão.")
    if version.status not in {VersionStatus.DRAFT, VersionStatus.REJECTED}:
        raise ValidationError("Somente versão em rascunho/rejeitada pode ir para revisão.")
    version.status = VersionStatus.UNDER_REVIEW
    version.save(update_fields=["status", "updated_at"])
    document.status = DocumentStatus.UNDER_REVIEW
    document.updated_by = actor
    document.save(update_fields=["status", "updated_by", "updated_at"])

    reviewers = list(reviewers or [])
    if not reviewers:
        reviewers = [actor]
    reviews = []
    for idx, reviewer in enumerate(reviewers, start=1):
        review = DocumentReview.objects.create(
            document_version=version,
            reviewer=reviewer,
            status=ReviewStatus.PENDING,
        )
        DocumentApprovalStep.objects.create(
            document=document,
            document_version=version,
            sequence=idx,
            approver_user=reviewer,
            approver_name_snapshot=getattr(reviewer, "get_username", lambda: str(reviewer))(),
            status=ApprovalStepStatus.PENDING if idx == 1 else ApprovalStepStatus.PENDING,
        )
        reviews.append(review)
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="documents",
        action="submit_document_for_review",
        obj=document,
    )
    return reviews


def _next_pending_step(version):
    return (
        version.approval_steps.filter(status=ApprovalStepStatus.PENDING)
        .order_by("sequence")
        .first()
    )


@transaction.atomic
def approve_document_version(*, version, actor, comments="", request=None):
    if not user_has_permission(actor, "documents.approve"):
        raise PermissionDenied("Sem permissão.")
    if version.status != VersionStatus.UNDER_REVIEW:
        raise ValidationError("Somente versão em revisão pode ser aprovada.")
    if version.status == VersionStatus.SUPERSEDED:
        raise ValidationError("Versão substituída.")

    step = _next_pending_step(version)
    if step:
        if step.approver_user_id and step.approver_user_id != actor.pk:
            # allow privileged approvers with documents.approve to decide any step
            pass
        previous_pending = version.approval_steps.filter(
            status=ApprovalStepStatus.PENDING,
            sequence__lt=step.sequence,
        ).exists()
        if previous_pending:
            raise ValidationError("Há passo anterior pendente.")
        step.status = ApprovalStepStatus.APPROVED
        step.decided_at = timezone.now()
        step.decision_notes = comments or ""
        step.approver_name_snapshot = actor.get_username()
        step.save(
            update_fields=[
                "status",
                "decided_at",
                "decision_notes",
                "approver_name_snapshot",
                "updated_at",
            ],
        )
        DocumentReview.objects.filter(
            document_version=version,
            reviewer=actor,
            status=ReviewStatus.PENDING,
        ).update(
            status=ReviewStatus.APPROVED,
            decision="approved",
            comments=comments or "",
            reviewed_at=timezone.now(),
        )
        if version.approval_steps.filter(status=ApprovalStepStatus.PENDING).exists():
            record_audit_event(
                request=request,
                user=actor,
                event_type="update",
                module="documents",
                action="approve_document_step",
                obj=version,
            )
            return version

    version.status = VersionStatus.APPROVED
    version.approved_by = actor
    version.approved_at = timezone.now()
    version.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    document = version.document
    document.status = DocumentStatus.APPROVED
    document.current_version = version
    document.updated_by = actor
    document.save(update_fields=["status", "current_version", "updated_by", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="documents",
        action="approve_document_version",
        obj=version,
        metadata={"comments": (comments or "")[:500]},
    )
    return version


@transaction.atomic
def reject_document_version(*, version, actor, reason, request=None):
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Motivo obrigatório.")
    if not user_has_permission(actor, "documents.reject"):
        raise PermissionDenied("Sem permissão.")
    if version.status != VersionStatus.UNDER_REVIEW:
        raise ValidationError("Somente versão em revisão pode ser rejeitada.")
    version.status = VersionStatus.REJECTED
    version.save(update_fields=["status", "updated_at"])
    DocumentReview.objects.create(
        document_version=version,
        reviewer=actor,
        status=ReviewStatus.REJECTED,
        decision="rejected",
        comments=reason,
        reviewed_at=timezone.now(),
    )
    version.approval_steps.filter(status=ApprovalStepStatus.PENDING).update(
        status=ApprovalStepStatus.REJECTED,
        decided_at=timezone.now(),
        decision_notes=reason,
    )
    document = version.document
    document.status = DocumentStatus.REJECTED
    document.updated_by = actor
    document.save(update_fields=["status", "updated_by", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="documents",
        action="reject_document_version",
        obj=version,
        metadata={"reason": reason[:500]},
    )
    return version


@transaction.atomic
def request_changes(*, version, actor, comments, request=None):
    comments = (comments or "").strip()
    if not comments:
        raise ValidationError("Comentários obrigatórios.")
    if not user_has_permission(actor, "documents.reject"):
        raise PermissionDenied("Sem permissão.")
    DocumentReview.objects.create(
        document_version=version,
        reviewer=actor,
        status=ReviewStatus.CHANGES_REQUESTED,
        decision="changes_requested",
        comments=comments,
        reviewed_at=timezone.now(),
    )
    version.status = VersionStatus.DRAFT
    version.save(update_fields=["status", "updated_at"])
    document = version.document
    document.status = DocumentStatus.DRAFT
    document.updated_by = actor
    document.save(update_fields=["status", "updated_by", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="documents",
        action="request_document_changes",
        obj=version,
    )
    return version
