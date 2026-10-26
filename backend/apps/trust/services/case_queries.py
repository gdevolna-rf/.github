"""Чтение очереди модерации: история объекта кейса, доступные действия, сводка по аккаунту."""
from django.db.models import Count, Q

from apps.learning.models import InstructorCertificate
from apps.organizations.models import Membership, Organization
from apps.spots.models import SpotChangeRequest
from apps.trust.models import AccountRestriction, AuditEvent, Complaint, ModerationCase, Review
from apps.trust.services.complaints import APPEALABLE_ACTIONS, has_open_appeal

HISTORY_LIMIT = 50


def case_history(case):
    if case.spot_change_request_id:
        pid = str(case.spot_change_request_id)
        cond = Q(object_type="spots.spotchangerequest", object_id=pid) | Q(metadata__proposal_id=pid)
    elif case.review_id:
        cond = Q(object_type="trust.review", object_id=str(case.review_id))
    elif case.certificate_id:
        cond = Q(object_type="learning.instructorcertificate", object_id=str(case.certificate_id))
    elif case.complaint_id:
        cond = Q(object_type="trust.complaint", object_id=str(case.complaint_id))
    elif case.organization_id:
        cond = Q(object_type="organizations.organization", object_id=str(case.organization_id))
    else:
        return AuditEvent.objects.none()
    return AuditEvent.objects.filter(cond).select_related("actor__profile__avatar").order_by("-created_at")[:HISTORY_LIMIT]


def available_actions(case):
    """Действия, допустимые для объекта кейса в его текущем состоянии (подсказка интерфейсу)."""
    if case.spot_change_request_id:
        p = case.spot_change_request
        if p.status == SpotChangeRequest.Status.SUBMITTED:
            return ["approve", "reject", "request_info"]
        if p.status == SpotChangeRequest.Status.NEEDS_INFO:
            return ["approve", "reject"]
        if p.status == SpotChangeRequest.Status.APPROVED and p.reverted_at is None:
            return ["revert"]
        return []
    if case.review_id:
        r = case.review
        if r.status == Review.Status.PENDING:
            return ["approve", "reject"]
        if r.status == Review.Status.PUBLISHED:
            return ["approve", "reject", "hide"] if r.has_pending_revision else ["hide"]
        return []
    if case.certificate_id:
        c = case.certificate
        if c.status == InstructorCertificate.Status.UPLOADED:
            return ["approve", "reject"]
        if c.status == InstructorCertificate.Status.VERIFIED:
            return ["revoke"]
        return []
    if case.organization_id:
        return ["approve", "reject"] if case.organization.status == Organization.Status.PENDING_REVIEW else []
    if case.complaint_id:
        c = case.complaint
        if case.kind == ModerationCase.Kind.APPEAL:
            appeal_open = (c.status == Complaint.Status.RESOLVED and c.appealed_at is not None
                           and c.action_taken in APPEALABLE_ACTIONS and has_open_appeal(c))
            return ["appeal_grant", "appeal_deny"] if appeal_open else []
        return ["resolve", "dismiss"] if c.status == Complaint.Status.OPEN else []
    return []


def account_summary(account):
    from apps.accounts.services.roles import active_roles

    reviews = dict(Review.objects.filter(author=account).values_list("status").annotate(n=Count("id")))
    against = Complaint.objects.filter(target_owner=account)
    return {
        "roles": sorted(str(r) for r in active_roles(account)),
        "date_joined": account.date_joined,
        "is_active": account.is_active,
        "is_email_verified": account.is_email_verified,
        "is_deleted": account.anonymized_at is not None,
        "organizations": [
            {"id": str(m.organization_id), "name": m.organization.name, "kind": m.organization.kind, "role": m.role,
             "status": m.organization.status}
            for m in Membership.objects.filter(account=account, status=Membership.Status.ACTIVE).select_related("organization")
        ],
        "counts": {
            "reviews": {status: reviews.get(status, 0) for status in Review.Status.values},
            "spot_proposals": SpotChangeRequest.objects.filter(author=account).count(),
            "complaints_filed": Complaint.objects.filter(reporter=account).count(),
            "complaints_against": against.count(),
            "complaints_against_upheld": against.filter(status=Complaint.Status.RESOLVED)
            .exclude(action_taken=Complaint.Action.NONE).count(),
        },
        "restrictions": AccountRestriction.objects.filter(account=account).select_related(
            "account__profile__avatar", "created_by__profile__avatar").order_by("-created_at"),
        "complaints": against.select_related("reporter__profile__avatar").order_by("-created_at")[:50],
    }
