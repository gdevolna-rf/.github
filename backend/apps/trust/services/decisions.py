"""Решения модератора (TRUST-04/06/07, 7.4, 7.5, F04, F08, F09, F14).

Каждое решение — одна транзакция: изменение объекта + AuditEvent + закрытие кейсов + уведомление автора
(+ аналитика, где задано). Объекты блокируются select_for_update; повторное решение → 409 invalid_status.
Модератор не принимает решений по собственным материалам (self_moderation).
"""
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Account
from apps.accounts.services.roles import active_roles
from apps.analytics.services import track
from apps.common.exceptions import Conflict, DomainError, Forbidden, NotFound
from apps.learning.models import InstructorCertificate
from apps.messaging.models import Notification
from apps.messaging.services.notify import notify
from apps.organizations.models import Organization
from apps.organizations.services.access import is_member, staff_accounts
from apps.spots.models import Spot, SpotChangeRequest
from apps.spots.services.proposals import apply_proposal, revert_applied
from apps.trust.models import AccountRestriction, AuditEvent, Complaint, ModerationCase, Review
from apps.trust.services.audit import record
from apps.trust.services.complaints import APPEALABLE_ACTIONS, has_open_appeal, hide_target, restore_target
from apps.trust.services.moderation_queue import close_cases
from apps.trust.services.ratings import recalculate_for_review, target_id_of
from apps.trust.services.restrictions import is_restriction_active
from apps.trust.services.reviews import target_name, target_public_link

K = Notification.Kind


def _invalid_status(message="Решение уже принято или недоступно в текущем статусе."):
    return Conflict(message, code="invalid_status")


def _forbid_self(moderator, account_id, what="собственным материалам"):
    if account_id is not None and moderator.pk == account_id:
        raise Forbidden(f"Модератор не принимает решения по {what}.", code="self_moderation")


def _locked(model, pk, *related):
    obj = model.objects.select_for_update(of=("self",)).select_related(*related).filter(pk=pk).first()
    if obj is None:
        raise NotFound("Объект модерации не найден.")
    return obj


def _with_comment(body, comment):
    return f"{body}\nКомментарий модератора: {comment}" if comment else body


# --- правки спотов (7.4, AT-07, F08, ATX-13) ------------------------------------------------------

def _track_proposal_reviewed(proposal, moderator, decision, now):
    hours = round((now - proposal.created_at).total_seconds() / 3600, 2)
    track("spot_proposal_reviewed", subject_type="spot_change_request", subject_id=proposal.pk, actor=moderator,
          context={"hours_from_submitted": hours, "decision": decision, "spot_id": str(proposal.spot_id)},
          dedup_key=f"spot_proposal_reviewed:{proposal.pk}", occurred_at=now)


def _lock_proposal(pk):
    proposal = _locked(SpotChangeRequest, pk, "author")
    proposal.spot = Spot.objects.select_for_update(of=("self",)).select_related("region").get(pk=proposal.spot_id)
    return proposal


def approve_proposal(pk, moderator, *, comment="", add_evidence_to_gallery=False, request=None):
    with transaction.atomic():
        proposal = _lock_proposal(pk)
        if proposal.status not in (SpotChangeRequest.Status.SUBMITTED, SpotChangeRequest.Status.NEEDS_INFO):
            raise _invalid_status()
        _forbid_self(moderator, proposal.author_id, "собственным правкам")
        now = timezone.now()
        before, after, metadata = apply_proposal(proposal, moderator, add_evidence_to_gallery=add_evidence_to_gallery,
                                                 now=now)
        proposal.status, proposal.moderator = SpotChangeRequest.Status.APPROVED, moderator
        proposal.moderator_comment, proposal.decided_at = comment, now
        proposal.save()
        record(moderator, "spot.change_approved", proposal.spot, before=before, after=after,
               metadata={**metadata, "comment": comment}, request=request)
        close_cases("approved", moderator, comment, spot_change_request=proposal)
        spot = proposal.spot
        notify(proposal.author, K.MODERATION_DECISION, "Правка спота принята",
               _with_comment(f"Ваша правка спота «{spot.name}» опубликована. Спасибо!", comment),
               link=f"/spots/{spot.slug}",
               payload={"proposal_id": str(proposal.pk), "spot_id": str(spot.pk), "decision": "approved"},
               event_id=f"proposal:{proposal.pk}:approved", actor=moderator)
        _track_proposal_reviewed(proposal, moderator, "approved", now)
    return proposal, metadata


def reject_proposal(pk, moderator, *, comment, request=None):
    with transaction.atomic():
        proposal = _lock_proposal(pk)
        if proposal.status not in (SpotChangeRequest.Status.SUBMITTED, SpotChangeRequest.Status.NEEDS_INFO):
            raise _invalid_status()
        _forbid_self(moderator, proposal.author_id, "собственным правкам")
        now = timezone.now()
        proposal.status, proposal.moderator = SpotChangeRequest.Status.REJECTED, moderator
        proposal.moderator_comment, proposal.decided_at = comment, now
        proposal.save()
        record(moderator, "spot.change_rejected", proposal, after={"status": proposal.status},
               metadata={"spot_id": str(proposal.spot_id), "comment": comment}, request=request)
        close_cases("rejected", moderator, comment, spot_change_request=proposal)
        notify(proposal.author, K.MODERATION_DECISION, "Правка спота отклонена",
               _with_comment(f"Правка спота «{proposal.spot.name}» не принята.", comment), link="/account/proposals",
               payload={"proposal_id": str(proposal.pk), "spot_id": str(proposal.spot_id), "decision": "rejected"},
               event_id=f"proposal:{proposal.pk}:rejected", actor=moderator)
        _track_proposal_reviewed(proposal, moderator, "rejected", now)
    return proposal


def request_proposal_info(pk, moderator, *, comment, request=None):
    with transaction.atomic():
        proposal = _lock_proposal(pk)
        if proposal.status != SpotChangeRequest.Status.SUBMITTED:
            raise _invalid_status()
        _forbid_self(moderator, proposal.author_id, "собственным правкам")
        proposal.status, proposal.moderator, proposal.moderator_comment = SpotChangeRequest.Status.NEEDS_INFO, moderator, comment
        proposal.save()
        record(moderator, "spot.change_info_requested", proposal, after={"status": proposal.status},
               metadata={"spot_id": str(proposal.spot_id), "comment": comment}, request=request)
        # Кейс ждёт автора — убираем из очереди; ответ автора откроет новый кейс.
        close_cases("needs_info", moderator, comment, spot_change_request=proposal)
        notify(proposal.author, K.MODERATION_DECISION, "Нужны уточнения по правке спота",
               _with_comment(f"Модератор просит уточнить правку спота «{proposal.spot.name}».", comment),
               link="/account/proposals",
               payload={"proposal_id": str(proposal.pk), "spot_id": str(proposal.spot_id), "decision": "needs_info"},
               event_id=f"proposal:{proposal.pk}:needs_info:{timezone.now().timestamp()}", actor=moderator)
    return proposal


def revert_proposal(pk, moderator, *, comment="", force=False, request=None):
    """Откат принятой правки к значениям «до» из журнала (TRUST-04). Статус остаётся approved, ставится reverted_at."""
    with transaction.atomic():
        proposal = _lock_proposal(pk)
        if proposal.status != SpotChangeRequest.Status.APPROVED or proposal.reverted_at is not None:
            raise _invalid_status("Откатить можно только принятую и ещё не откатанную правку.")
        event = AuditEvent.objects.filter(action="spot.change_approved", metadata__proposal_id=str(proposal.pk)) \
            .order_by("-created_at").first()
        if event is None:
            raise Conflict("Не найдена запись журнала об одобрении — откат невозможен.", code="revert_unavailable")
        current, restored, extra = revert_applied(proposal.spot, event, force=force)
        now = timezone.now()
        proposal.reverted_at, proposal.reverted_by = now, moderator
        proposal.save(update_fields=["reverted_at", "reverted_by", "updated_at"])
        record(moderator, "spot.change_reverted", proposal.spot, before=current, after=restored,
               metadata={"proposal_id": str(proposal.pk), "approval_event_id": str(event.pk), "comment": comment,
                         "force": bool(force), **extra}, request=request)
        notify(proposal.author, K.MODERATION_DECISION, "Правка спота отменена",
               _with_comment(f"Принятая ранее правка спота «{proposal.spot.name}» отменена модератором.", comment),
               link="/account/proposals",
               payload={"proposal_id": str(proposal.pk), "spot_id": str(proposal.spot_id), "decision": "reverted"},
               event_id=f"proposal:{proposal.pk}:reverted", actor=moderator)
    return proposal


# --- отзывы (7.5, BR-08, AT-08, F09, ATX-12) ------------------------------------------------------

def _lock_review(pk):
    return _locked(Review, pk, "author", "spot", "instructor__account__profile", "organization")


def _review_owners(review):
    if review.target_type == Review.Target.INSTRUCTOR:
        return [review.instructor.account]
    if review.target_type == Review.Target.ORGANIZATION:
        return staff_accounts(review.organization)
    return []


def approve_review(pk, moderator, *, note="", request=None):
    with transaction.atomic():
        review = _lock_review(pk)
        _forbid_self(moderator, review.author_id, "собственным отзывам")
        now = timezone.now()
        before = {"status": review.status, "rating": review.rating, "text": review.text}
        first_publication = False
        if review.status == Review.Status.PENDING:
            review.status = Review.Status.PUBLISHED
            first_publication = review.published_at is None
            review.published_at = review.published_at or now
            action = "review.published"
        elif review.status == Review.Status.PUBLISHED and review.has_pending_revision:
            review.rating = review.pending_rating or review.rating
            review.text = review.pending_text
            review.photos.set(review.pending_photos.all())
            review.pending_photos.clear()
            review.has_pending_revision, review.pending_rating, review.pending_text = False, None, ""
            action = "review.revision_approved"
        else:
            raise _invalid_status()
        review.moderator, review.moderated_at, review.moderation_note = moderator, now, note[:300]
        review.save()
        rating = recalculate_for_review(review)
        record(moderator, action, review, before=before,
               after={"status": review.status, "rating": review.rating, "text": review.text},
               metadata={"target_type": review.target_type, "target_id": str(target_id_of(review)),
                         "rating_avg": str(rating[0]) if rating else None, "rating_count": rating[1] if rating else None},
               request=request)
        close_cases("approved", moderator, note, review=review)
        link = target_public_link(review)
        notify(review.author, K.REVIEW_PUBLISHED, "Отзыв опубликован",
               f"Ваш отзыв о «{target_name(review)}» опубликован.", link=link,
               payload={"review_id": str(review.pk)}, event_id=f"review:{review.pk}:published:{now.timestamp()}",
               actor=moderator)
        if first_publication:
            track("review_published", subject_type=review.target_type, subject_id=target_id_of(review),
                  actor=review.author,
                  owner_account=review.instructor.account if review.target_type == Review.Target.INSTRUCTOR else None,
                  owner_organization=review.organization if review.target_type == Review.Target.ORGANIZATION else None,
                  context={"review_id": str(review.pk), "rating": review.rating}, dedup_key=f"review_published:{review.pk}",
                  occurred_at=now)
            for owner in _review_owners(review):
                notify(owner, K.REVIEW_PUBLISHED, "Новый отзыв",
                       f"Опубликован новый отзыв: {review.rating}★.", link=link, payload={"review_id": str(review.pk)},
                       event_id=f"review:{review.pk}:owner_published", actor=review.author)
    return review


def reject_review(pk, moderator, *, note, request=None):
    with transaction.atomic():
        review = _lock_review(pk)
        _forbid_self(moderator, review.author_id, "собственным отзывам")
        now = timezone.now()
        if review.status == Review.Status.PENDING:
            before = {"status": review.status}
            review.status = Review.Status.REJECTED
            action, title = "review.rejected", "Отзыв не опубликован"
            body = f"Отзыв о «{target_name(review)}» не прошёл модерацию."
        elif review.status == Review.Status.PUBLISHED and review.has_pending_revision:
            before = {"pending_rating": review.pending_rating, "pending_text": review.pending_text}
            review.has_pending_revision, review.pending_rating, review.pending_text = False, None, ""
            review.pending_photos.clear()
            action, title = "review.revision_rejected", "Правка отзыва отклонена"
            body = f"Правка отзыва о «{target_name(review)}» не принята; опубликованная версия сохранена."
        else:
            raise _invalid_status()
        review.moderator, review.moderated_at, review.moderation_note = moderator, now, note[:300]
        review.save()
        record(moderator, action, review, before=before, after={"status": review.status},
               metadata={"note": note}, request=request)
        close_cases("rejected", moderator, note, review=review)
        notify(review.author, K.MODERATION_DECISION, title, _with_comment(body, note), link="/account/reviews",
               payload={"review_id": str(review.pk), "decision": "rejected"},
               event_id=f"review:{review.pk}:rejected:{now.timestamp()}", actor=moderator)
    return review


def hide_review(pk, moderator, *, note, request=None):
    with transaction.atomic():
        review = _lock_review(pk)
        if review.status != Review.Status.PUBLISHED:
            raise _invalid_status("Скрыть можно только опубликованный отзыв.")
        now = timezone.now()
        review.status = Review.Status.HIDDEN
        review.has_pending_revision, review.pending_rating, review.pending_text = False, None, ""
        review.moderator, review.moderated_at, review.moderation_note = moderator, now, note[:300]
        review.save()
        review.pending_photos.clear()
        rating = recalculate_for_review(review)
        record(moderator, "review.hidden", review, before={"status": Review.Status.PUBLISHED},
               after={"status": review.status},
               metadata={"note": note, "rating_avg": str(rating[0]) if rating else None,
                         "rating_count": rating[1] if rating else None}, request=request)
        close_cases("hidden", moderator, note, review=review)
        notify(review.author, K.MODERATION_DECISION, "Отзыв скрыт модератором",
               _with_comment(f"Ваш отзыв о «{target_name(review)}» скрыт.", note), link="/account/reviews",
               payload={"review_id": str(review.pk), "decision": "hidden"}, event_id=f"review:{review.pk}:hidden",
               actor=moderator)
    return review


# --- сертификаты (BR-07, F04, ATX-05) ------------------------------------------------------------

def _decide_certificate(pk, moderator, *, from_statuses, to_status, action, title, body, note, request):
    with transaction.atomic():
        cert = _locked(InstructorCertificate, pk, "instructor__account")
        if cert.status not in from_statuses:
            raise _invalid_status()
        _forbid_self(moderator, cert.instructor.account_id, "собственным документам")
        before = {"status": cert.status}
        cert.status, cert.moderator, cert.decided_at, cert.moderator_comment = to_status, moderator, timezone.now(), note
        cert.save()
        record(moderator, action, cert, before=before, after={"status": cert.status},
               metadata={"instructor_id": str(cert.instructor_id), "note": note}, request=request)
        close_cases(to_status, moderator, note, certificate=cert)
        notify(cert.instructor.account, K.CERTIFICATE_DECISION, title,
               _with_comment(body.format(title=cert.title), note), link="/account/instructor/certificates",
               payload={"certificate_id": str(cert.pk), "status": cert.status},
               event_id=f"certificate:{cert.pk}:{to_status}", actor=moderator)
    return cert


def approve_certificate(pk, moderator, *, note="", request=None):
    return _decide_certificate(
        pk, moderator, from_statuses=[InstructorCertificate.Status.UPLOADED], to_status=InstructorCertificate.Status.VERIFIED,
        action="certificate.verified", title="Сертификат проверен",
        body="Сертификат «{title}» проверен — на карточке появился значок «Проверен».", note=note, request=request)


def reject_certificate(pk, moderator, *, note, request=None):
    return _decide_certificate(
        pk, moderator, from_statuses=[InstructorCertificate.Status.UPLOADED], to_status=InstructorCertificate.Status.REJECTED,
        action="certificate.rejected", title="Сертификат не подтверждён",
        body="Сертификат «{title}» не прошёл проверку.", note=note, request=request)


def revoke_certificate(pk, moderator, *, note, request=None):
    return _decide_certificate(
        pk, moderator, from_statuses=[InstructorCertificate.Status.VERIFIED], to_status=InstructorCertificate.Status.REVOKED,
        action="certificate.revoked", title="Проверка сертификата отозвана",
        body="Значок «Проверен» для сертификата «{title}» снят.", note=note, request=request)


# --- организации (SCH-13) ------------------------------------------------------------------------

def _notify_org(org, moderator, title, body, decision):
    for account in {a.pk: a for a in [org.owner, *staff_accounts(org)]}.values():
        notify(account, K.MODERATION_DECISION, title, body, link=f"/account/orgs/{org.pk}/profile",
               payload={"organization_id": str(org.pk), "decision": decision},
               event_id=f"organization:{org.pk}:{decision}:{org.updated_at.timestamp()}", actor=moderator)


def approve_organization(pk, moderator, *, note="", request=None):
    with transaction.atomic():
        org = _locked(Organization, pk, "owner")
        if org.status != Organization.Status.PENDING_REVIEW:
            raise _invalid_status()
        if org.owner_id == moderator.pk or is_member(moderator, org):
            raise Forbidden("Модератор не принимает решения по своей организации.", code="self_moderation")
        before = {"status": org.status, "verification_status": org.verification_status}
        org.status, org.verification_status = Organization.Status.PUBLISHED, Organization.Verification.VERIFIED
        org.published_at = org.published_at or timezone.now()
        org.moderation_note = note
        org.save()
        record(moderator, "organization.published", org, before=before,
               after={"status": org.status, "verification_status": org.verification_status},
               organization=org, metadata={"note": note}, request=request)
        close_cases("approved", moderator, note, organization=org)
        _notify_org(org, moderator, "Организация опубликована",
                    _with_comment(f"«{org.name}» прошла проверку и опубликована.", note), "approved")
    return org


def reject_organization(pk, moderator, *, note, request=None):
    with transaction.atomic():
        org = _locked(Organization, pk, "owner")
        if org.status != Organization.Status.PENDING_REVIEW:
            raise _invalid_status()
        if org.owner_id == moderator.pk or is_member(moderator, org):
            raise Forbidden("Модератор не принимает решения по своей организации.", code="self_moderation")
        before = {"status": org.status, "verification_status": org.verification_status}
        org.status, org.verification_status = Organization.Status.DRAFT, Organization.Verification.REJECTED
        org.moderation_note = note
        org.save()
        record(moderator, "organization.rejected", org, before=before,
               after={"status": org.status, "verification_status": org.verification_status},
               organization=org, metadata={"note": note}, request=request)
        close_cases("rejected", moderator, note, organization=org)
        _notify_org(org, moderator, "Организация не опубликована",
                    _with_comment(f"«{org.name}» возвращена в черновик — исправьте замечания и отправьте снова.", note),
                    "rejected")
    return org


# --- жалобы и апелляции (TRUST-07, F14) ----------------------------------------------------------

_REPORTER_BODY = {
    Complaint.Action.NONE: "Нарушений не выявлено.",
    Complaint.Action.WARNING: "Автору материала вынесено предупреждение.",
    Complaint.Action.HIDDEN: "Материал скрыт.",
    Complaint.Action.SUSPENDED: "Профиль нарушителя ограничен.",
}
_OWNER_BODY = {
    Complaint.Action.WARNING: "Модератор вынес предупреждение по жалобе на ваш материал.",
    Complaint.Action.HIDDEN: "Ваш материал скрыт модератором по жалобе.",
    Complaint.Action.SUSPENDED: "Ваш профиль ограничен модератором: публикации и сообщения недоступны.",
}


def resolve_complaint(pk, moderator, *, action, note="", expires_at=None, request=None):
    with transaction.atomic():
        complaint = _locked(Complaint, pk, "target_owner", "reporter")
        if complaint.status != Complaint.Status.OPEN:
            raise _invalid_status()
        _forbid_self(moderator, complaint.target_owner_id, "жалобам на себя")
        owner = complaint.target_owner
        if action in (Complaint.Action.WARNING, Complaint.Action.SUSPENDED) and owner is None:
            raise DomainError("action_not_applicable", "У этого объекта нет владельца — выберите другое действие.")
        before = after = None
        metadata = {"action": action, "target_type": complaint.target_type, "target_id": complaint.target_id,
                    "note": note}
        if action == Complaint.Action.HIDDEN:
            before, after = hide_target(complaint, note, moderator)
        elif action == Complaint.Action.SUSPENDED:
            if expires_at is not None and expires_at <= timezone.now():
                raise DomainError("validation_error", "Срок ограничения должен быть в будущем.",
                                  fields={"expires_at": ["Дата в прошлом."]})
            restriction = AccountRestriction.objects.create(
                account=owner, kind=AccountRestriction.Kind.SUSPENDED, created_by=moderator, expires_at=expires_at,
                reason=(note or f"Жалоба: {complaint.get_reason_display()}")[:300],
            )
            metadata["restriction_id"] = str(restriction.pk)
            record(moderator, "account.restricted", owner, after={"kind": restriction.kind, "reason": restriction.reason},
                   metadata={"restriction_id": str(restriction.pk), "complaint_id": str(complaint.pk)}, request=request)

        # Все открытые жалобы на ту же цель решаются тем же действием (одна мера — один раз).
        siblings = list(Complaint.objects.select_for_update(of=("self",)).select_related("reporter").filter(
            target_type=complaint.target_type, target_id=complaint.target_id, status=Complaint.Status.OPEN))
        for item in siblings:
            item.status, item.action_taken = Complaint.Status.RESOLVED, action
            item.save(update_fields=["status", "action_taken", "updated_at"])
            close_cases(action, moderator, note, complaint=item)
            notify(item.reporter, K.COMPLAINT, "Жалоба рассмотрена", _REPORTER_BODY[action], link="/account/notifications",
                   payload={"complaint_id": str(item.pk), "status": item.status, "action": action},
                   event_id=f"complaint:{item.pk}:resolved", actor=moderator)
        metadata["complaint_ids"] = [str(c.pk) for c in siblings]
        record(moderator, "complaint.resolved", complaint, before=before, after=after, metadata=metadata, request=request)
        if owner is not None and action in _OWNER_BODY:
            notify(owner, K.MODERATION_DECISION, "Решение модератора по жалобе",
                   _with_comment(_OWNER_BODY[action] + " Решение можно обжаловать.", note), link="/account/notifications",
                   payload={"complaint_id": str(complaint.pk), "action": action, "target_type": complaint.target_type,
                            "target_id": complaint.target_id, "can_appeal": True},
                   event_id=f"complaint:{complaint.pk}:owner", actor=moderator)
        complaint.refresh_from_db()
    return complaint


def dismiss_complaint(pk, moderator, *, note="", request=None):
    with transaction.atomic():
        complaint = _locked(Complaint, pk, "reporter")
        if complaint.status != Complaint.Status.OPEN:
            raise _invalid_status()
        complaint.status, complaint.action_taken = Complaint.Status.DISMISSED, Complaint.Action.NONE
        complaint.save(update_fields=["status", "action_taken", "updated_at"])
        record(moderator, "complaint.dismissed", complaint, metadata={"note": note}, request=request)
        close_cases("dismissed", moderator, note, complaint=complaint)
        notify(complaint.reporter, K.COMPLAINT, "Жалоба рассмотрена", "Нарушений не выявлено, жалоба отклонена.",
               link="/account/notifications", payload={"complaint_id": str(complaint.pk), "status": complaint.status},
               event_id=f"complaint:{complaint.pk}:dismissed", actor=moderator)
    return complaint


def decide_appeal(pk, moderator, *, grant, note="", request=None):
    """Апелляция удовлетворена → мера снимается (цель восстанавливается / ограничение снимается)."""
    with transaction.atomic():
        complaint = _locked(Complaint, pk, "target_owner")
        if (complaint.status != Complaint.Status.RESOLVED or complaint.appealed_at is None
                or complaint.action_taken not in APPEALABLE_ACTIONS or not has_open_appeal(complaint)):
            raise _invalid_status("Нет открытой апелляции по этой жалобе.")
        _forbid_self(moderator, complaint.target_owner_id, "жалобам на себя")
        metadata = {"note": note, "action": complaint.action_taken}
        before = after = None
        if grant:
            event = AuditEvent.objects.filter(action="complaint.resolved", object_type="trust.complaint") \
                .filter(metadata__complaint_ids__contains=[str(complaint.pk)]).order_by("-created_at").first()
            if complaint.action_taken == Complaint.Action.HIDDEN and event is not None:
                before = event.after
                after = restore_target(complaint, event.before, moderator)
            if complaint.action_taken == Complaint.Action.SUSPENDED and event is not None:
                restriction_id = (event.metadata or {}).get("restriction_id")
                lifted = AccountRestriction.objects.filter(pk=restriction_id, lifted_at__isnull=True).update(
                    lifted_at=timezone.now())
                metadata["lifted_restriction_id"] = restriction_id if lifted else None
            related_ids = (event.metadata or {}).get("complaint_ids") if event is not None else None
            Complaint.objects.filter(pk__in=related_ids or [complaint.pk]).update(
                action_taken=Complaint.Action.NONE, updated_at=timezone.now())
            complaint.refresh_from_db()
        record(moderator, "complaint.appeal_granted" if grant else "complaint.appeal_denied", complaint,
               before=before, after=after, metadata=metadata, request=request)
        close_cases("appeal_granted" if grant else "appeal_denied", moderator, note, complaint=complaint)
        if complaint.target_owner:
            notify(complaint.target_owner, K.MODERATION_DECISION,
                   "Апелляция удовлетворена" if grant else "Апелляция отклонена",
                   _with_comment("Мера по жалобе снята." if grant else "Решение модератора оставлено в силе.", note),
                   link="/account/notifications", payload={"complaint_id": str(complaint.pk), "granted": bool(grant)},
                   event_id=f"complaint:{complaint.pk}:appeal", actor=moderator)
    return complaint


# --- ограничения аккаунтов ------------------------------------------------------------------------

def restrict_account(account_id, moderator, *, kind, reason, expires_at=None, request=None):
    with transaction.atomic():
        account = Account.objects.select_for_update().filter(pk=account_id).first()
        if account is None:
            raise NotFound("Аккаунт не найден.")
        if account.pk == moderator.pk:
            raise Forbidden("Нельзя ограничить собственный аккаунт.", code="self_moderation")
        if {"moderator", "admin"} & active_roles(account) and "admin" not in active_roles(moderator):
            raise Forbidden("Служебные аккаунты ограничивает только администратор.", code="staff_account")
        if expires_at is not None and expires_at <= timezone.now():
            raise DomainError("validation_error", "Срок ограничения должен быть в будущем.",
                              fields={"expires_at": ["Дата в прошлом."]})
        existing = [r for r in AccountRestriction.objects.filter(account=account, kind=kind, lifted_at__isnull=True)
                    if is_restriction_active(r)]
        if existing:
            raise Conflict("Такое ограничение уже действует — снимите его или дождитесь окончания.",
                           code="restriction_exists")
        restriction = AccountRestriction.objects.create(account=account, kind=kind, reason=reason, created_by=moderator,
                                                        expires_at=expires_at)
        record(moderator, "account.restricted", account,
               after={"kind": kind, "reason": reason, "expires_at": expires_at.isoformat() if expires_at else None},
               metadata={"restriction_id": str(restriction.pk)}, request=request)
        until = f" до {timezone.localtime(expires_at):%d.%m.%Y %H:%M}" if expires_at else ""
        notify(account, K.MODERATION_DECISION, "Аккаунт ограничен",
               f"{restriction.get_kind_display()}{until}. Причина: {reason}", link="/account/settings",
               payload={"restriction_id": str(restriction.pk), "kind": kind},
               event_id=f"restriction:{restriction.pk}:created", actor=moderator)
    return restriction


def lift_restriction(pk, moderator, *, note="", request=None):
    with transaction.atomic():
        restriction = _locked(AccountRestriction, pk, "account")
        if not is_restriction_active(restriction):
            raise _invalid_status("Ограничение уже снято или истекло.")
        restriction.lifted_at = timezone.now()
        restriction.save(update_fields=["lifted_at", "updated_at"])
        record(moderator, "account.restriction_lifted", restriction.account,
               before={"kind": restriction.kind}, after={"lifted_at": restriction.lifted_at.isoformat()},
               metadata={"restriction_id": str(restriction.pk), "note": note}, request=request)
        notify(restriction.account, K.MODERATION_DECISION, "Ограничение снято",
               f"{restriction.get_kind_display()} — ограничение снято.", link="/account/settings",
               payload={"restriction_id": str(restriction.pk)}, event_id=f"restriction:{restriction.pk}:lifted",
               actor=moderator)
    return restriction


def take_case(pk, moderator):
    with transaction.atomic():
        case = _locked(ModerationCase, pk)
        if case.status == ModerationCase.Status.RESOLVED:
            raise _invalid_status("Кейс уже закрыт.")
        case.status, case.assigned_to = ModerationCase.Status.IN_REVIEW, moderator
        case.save(update_fields=["status", "assigned_to", "updated_at"])
    return case
