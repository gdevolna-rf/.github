"""Обращения и чат (7.2, MSG-01…09, SHP-11, SHO-06, BR-05/06, AT-01/03/04, ATX-03/09/27/28/29).

Создание обращения — одна транзакция: Inquiry + история + Conversation + участники + первое сообщение +
уведомления сотрудникам исполнителя + событие ``inquiry_created``. Чат доступен сразу (MSG-03/09).
"""
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.analytics.services import track
from apps.commerce.models import Inquiry, InquiryMilestone, InquiryStatusChange
from apps.commerce.services import access
from apps.commerce.services.snapshots import TARGET_TYPES, build_snapshot
from apps.common.exceptions import Conflict, DomainError, Forbidden, NotFound
from apps.mediafiles.models import MediaAsset
from apps.mediafiles.services import claim_media
from apps.messaging.models import Conversation, ConversationParticipant, Notification
from apps.messaging.services import conversations as chat
from apps.messaging.services.counters import push_counters
from apps.messaging.services.notify import notify
from apps.messaging.services.realtime import push_to_users
from apps.messaging.services.safety import is_blocked

K = Inquiry.Kind
S = Inquiry.Status
ALL_TARGETS = set(TARGET_TYPES)

# Какие объекты допустимы для каждого вида обращения (PAY-01, MSG-08).
KIND_TARGETS = {
    K.BOARD_PURCHASE: {"board_model", "board_variant", "inventory_item", "organization"},
    K.CUSTOM_ORDER: {"board_model", "board_variant", "organization"},
    K.REPAIR: {"organization", "board_model", "board_variant"},
    K.LESSON: {"instructor_offer", "lesson_session", "school_program", "organization", "account"},
    K.PROGRAM: {"school_program", "lesson_session", "organization"},
    K.RENTAL: {"inventory_item", "organization", "account"},
    K.MERCH: {"organization", "account"},
    K.GENERAL: ALL_TARGETS,
}
WORKSHOP_ONLY = {K.CUSTOM_ORDER, K.REPAIR}
SCHOOL_ONLY = {K.PROGRAM}
PRO_SPECIALTIES = ("instructor", "shaper", "rental")
MAX_MESSAGE = 4000
MAX_REPAIR_PHOTOS = 10

# действие → (сторона, исходные статусы, новый статус)
TRANSITIONS = {
    "accept": (access.PROVIDER, {S.NEW}, S.IN_PROGRESS),
    "decline": (access.PROVIDER, {S.NEW, S.IN_PROGRESS}, S.DECLINED),
    "complete": (access.PROVIDER, {S.IN_PROGRESS}, S.COMPLETED),
    "cancel": (access.CUSTOMER, {S.NEW, S.IN_PROGRESS}, S.CANCELLED),
}
OPEN_STATUSES = (S.NEW, S.IN_PROGRESS)


@dataclass
class ResolvedTarget:
    target_type: str
    obj: object
    provider_account: object = None
    provider_organization: object = None
    links: dict = field(default_factory=dict)
    source_channel: str = ""


def _invalid_target(message):
    return DomainError("invalid_target", message, fields={"target_type": [message]})


def _not_found(what="Объект обращения не найден."):
    return NotFound(what)


def _org_available(org):
    from apps.organizations.models import Organization

    return org is not None and org.status not in (Organization.Status.SUSPENDED, Organization.Status.ARCHIVED)


def _channel_for_org(org):
    return {"school": "schools", "workshop": "shapers", "rental": "rentals"}.get(org.kind, "organizations")


def resolve_target(target_type, target_id):
    """Определяет исполнителя по объекту (ARCHITECTURE §3 commerce).

    Видимость объекта — те же правила, что у публичных каталогов: мастерская опубликована, владелец объявления
    виден (inventory.visible_owner_q), карточка инструктора публична (learning.public_profiles), аккаунт без
    ограничения профиля. Скрытое из каталога нельзя «достать» прямым POST по id.
    """
    from apps.accounts.models import Account, UserSpecialty
    from apps.boards.models import BoardModel, BoardVariant
    from apps.inventory.models import InventoryItem
    from apps.inventory.services.rentals import visible_owner_q
    from apps.learning.models import InstructorOffer, LessonSession, SchoolProgram
    from apps.learning.services.access import is_session_public
    from apps.learning.services.catalog import public_profiles
    from apps.organizations.models import Organization
    from apps.trust.services.restrictions import suspended_exists

    if target_type not in ALL_TARGETS:
        raise _invalid_target("Неизвестный тип объекта обращения.")
    if target_type == "board_model":
        model = (BoardModel.objects.select_related("workshop", "board_type")
                 .filter(pk=target_id, status=BoardModel.Status.PUBLISHED,
                         workshop__status=Organization.Status.PUBLISHED).first())
        if model is None or not _org_available(model.workshop):
            raise _not_found("Модель доски не найдена.")
        return ResolvedTarget(target_type, model, provider_organization=model.workshop,
                              links={"board_model": model}, source_channel="boards")
    if target_type == "board_variant":
        variant = (BoardVariant.objects.select_related("model__workshop", "model__board_type", "material")
                   .filter(pk=target_id, is_active=True, model__status=BoardModel.Status.PUBLISHED,
                           model__workshop__status=Organization.Status.PUBLISHED).first())
        if variant is None or not _org_available(variant.model.workshop):
            raise _not_found("Вариант доски не найден.")
        return ResolvedTarget(target_type, variant, provider_organization=variant.model.workshop,
                              links={"board_model": variant.model, "board_variant": variant}, source_channel="boards")
    if target_type == "inventory_item":
        item = (InventoryItem.objects.select_related("owner_account__profile", "owner_organization",
                                                     "variant__model")
                .filter(visible_owner_q(), pk=target_id, is_published=True)
                .exclude(status=InventoryItem.Status.RETIRED).first())
        if item is None:
            raise _not_found("Объявление не найдено.")
        links = {"inventory_item": item}
        if item.variant_id:
            links.update(board_variant=item.variant, board_model=item.variant.model)
        return ResolvedTarget(target_type, item, provider_account=item.owner_account,
                              provider_organization=item.owner_organization, links=links, source_channel="rentals")
    if target_type == "instructor_offer":
        offer = (InstructorOffer.objects.select_related("instructor__account__profile")
                 .filter(pk=target_id, is_active=True, instructor__in=public_profiles()).first())
        if offer is None:
            raise _not_found("Предложение инструктора не найдено.")
        return ResolvedTarget(target_type, offer, provider_account=offer.instructor.account,
                              links={"instructor_offer": offer}, source_channel="instructors")
    if target_type == "school_program":
        program = (SchoolProgram.objects.select_related("organization")
                   .filter(pk=target_id, is_active=True, organization__status=Organization.Status.PUBLISHED).first())
        if program is None:
            raise _not_found("Программа школы не найдена.")
        return ResolvedTarget(target_type, program, provider_organization=program.organization,
                              links={"school_program": program}, source_channel="schools")
    if target_type == "lesson_session":
        session = (LessonSession.objects.select_related("organization", "program", "offer__instructor__account__profile",
                                                        "spot", "instructor")
                   .filter(pk=target_id).exclude(status=LessonSession.Status.CANCELLED).first())
        if session is None:
            raise _not_found("Занятие не найдено.")
        links = {"lesson_session": session}
        if session.program_id:
            links["school_program"] = session.program
        if session.offer_id:
            links["instructor_offer"] = session.offer
        if not is_session_public(session):
            raise _not_found("Занятие не найдено.")
        if session.organization_id:
            return ResolvedTarget(target_type, session, provider_organization=session.organization, links=links,
                                  source_channel="schools")
        return ResolvedTarget(target_type, session, provider_account=session.offer.instructor.account, links=links,
                              source_channel="instructors")
    if target_type == "organization":
        org = Organization.objects.select_related("logo", "cover").filter(
            pk=target_id, status=Organization.Status.PUBLISHED).first()
        if org is None:
            raise _not_found("Организация не найдена.")
        return ResolvedTarget(target_type, org, provider_organization=org, source_channel=_channel_for_org(org))
    # account
    account = (Account.objects.select_related("profile__avatar")
               .filter(pk=target_id, is_active=True, anonymized_at__isnull=True)
               .exclude(suspended_exists("pk")).first())
    if account is None or not hasattr(account, "profile"):
        raise _not_found("Пользователь не найден.")
    is_pro = UserSpecialty.objects.filter(account=account, specialty_id__in=PRO_SPECIALTIES,
                                          status=UserSpecialty.Status.ACTIVE).exists()
    if not is_pro:
        raise Forbidden("Этот пользователь не принимает обращения. Для знакомства используйте GG Surfer.",
                        code="provider_not_available")
    return ResolvedTarget(target_type, account, provider_account=account, source_channel="profile")


def _validate_kind(kind, target):
    from apps.inventory.models import InventoryItem
    from apps.organizations.models import Organization

    if target.target_type not in KIND_TARGETS[kind]:
        raise _invalid_target(f"Обращение «{K(kind).label}» нельзя отправить к этому объекту.")
    org = target.provider_organization
    if kind in WORKSHOP_ONLY or (kind == K.BOARD_PURCHASE and target.target_type == "organization"):
        if org is None or org.kind != Organization.Kind.WORKSHOP:
            raise _invalid_target("Такое обращение принимает только мастерская шейпера.")
    if kind in SCHOOL_ONLY or (kind == K.LESSON and target.target_type == "organization"):
        if org is None or org.kind != Organization.Kind.SCHOOL:
            raise _invalid_target("Такое обращение принимает только сёрф-школа.")
    if kind == K.REPAIR:
        workshop = getattr(org, "workshop", None)
        if workshop is None or not workshop.does_repair:
            raise DomainError("repair_not_offered", "Эта мастерская не принимает доски в ремонт.")
    if target.target_type == "inventory_item":
        item = target.obj
        if kind == K.BOARD_PURCHASE:
            if item.purpose not in (InventoryItem.Purpose.SALE, InventoryItem.Purpose.BOTH):
                raise _invalid_target("Этот экземпляр не продаётся.")
            if item.status != InventoryItem.Status.AVAILABLE:
                raise Conflict("Экземпляр уже продан или зарезервирован.", code="item_unavailable")
        if kind == K.RENTAL and item.purpose not in (InventoryItem.Purpose.RENTAL, InventoryItem.Purpose.BOTH):
            raise _invalid_target("Этот экземпляр не сдаётся в аренду.")


def _require_not_self(customer, target):
    """BR-05, SHP-11, AT-03, ATX-03: нельзя обратиться к себе или к своей организации, даже прямым POST."""
    message = "Нельзя отправить обращение самому себе или своей организации."
    if target.provider_account is not None and target.provider_account.pk == customer.pk:
        raise Forbidden(message, code="self_inquiry")
    if target.provider_organization is not None and access.is_active_member(customer, target.provider_organization):
        raise Forbidden(message, code="self_inquiry")
    session = target.links.get("lesson_session")
    if session is not None and session.instructor_id == customer.pk:
        raise Forbidden(message, code="self_inquiry")


def _require_contact_allowed(customer, target):
    from apps.trust.services.restrictions import require_can_message

    require_can_message(customer)
    principal = access.provider_principal(target.provider_account, target.provider_organization)
    if principal is not None and is_blocked(customer, principal):
        raise Forbidden("Обращение недоступно: один из участников заблокировал другого.", code="blocked")


def _clean_date(value, name):
    if value in (None, ""):
        return None
    parsed = parse_date(str(value))
    if parsed is None:
        raise DomainError("validation_error", "Дата должна быть в формате ГГГГ-ММ-ДД.",
                          fields={f"details.{name}": ["Неверная дата."]})
    if parsed < timezone.localdate():
        raise DomainError("validation_error", "Дата не может быть в прошлом.",
                          fields={f"details.{name}": ["Дата в прошлом."]})
    return parsed.isoformat()


def _clean_scalar_map(value, name, max_keys=20, max_len=500):
    if value in (None, ""):
        return {}
    if not isinstance(value, dict):
        raise DomainError("validation_error", "Ожидается объект.", fields={name: ["Ожидается объект."]})
    if len(value) > max_keys:
        raise DomainError("validation_error", "Слишком много параметров.", fields={name: [f"Не более {max_keys}."]})
    out = {}
    for key, item in value.items():
        key = str(key)[:40]
        if isinstance(item, bool) or item is None or isinstance(item, (int, float)):
            out[key] = item
        elif isinstance(item, str):
            if len(item) > max_len:
                raise DomainError("validation_error", "Слишком длинное значение.",
                                  fields={f"{name}.{key}": [f"Не более {max_len} символов."]})
            out[key] = item.strip()
        elif isinstance(item, list) and all(isinstance(x, (str, int, float)) for x in item) and len(item) <= 20:
            out[key] = [x.strip()[:max_len] if isinstance(x, str) else x for x in item]
        else:
            raise DomainError("validation_error", "Допустимы только простые значения.",
                              fields={f"{name}.{key}": ["Неподдерживаемое значение."]})
    return out


def clean_details(kind, details, customer):
    """Проверка details по виду обращения. Возвращает (details, repair_photo_assets)."""
    details = details or {}
    if not isinstance(details, dict):
        raise DomainError("validation_error", "details должен быть объектом.", fields={"details": ["Ожидается объект."]})
    if kind == K.REPAIR:
        problem = str(details.get("problem") or "").strip()
        if not problem:
            raise DomainError("validation_error", "Опишите проблему с доской.",
                              fields={"details.problem": ["Обязательное поле."]})
        if len(problem) > 2000:
            raise DomainError("validation_error", "Описание слишком длинное.",
                              fields={"details.problem": ["Не более 2000 символов."]})
        photo_ids = details.get("photo_ids") or []
        if not isinstance(photo_ids, list):
            raise DomainError("validation_error", "photo_ids — список.", fields={"details.photo_ids": ["Ожидается список."]})
        photo_ids = list(dict.fromkeys(str(p) for p in photo_ids))
        if len(photo_ids) > MAX_REPAIR_PHOTOS:
            raise DomainError("validation_error", f"Не более {MAX_REPAIR_PHOTOS} фото.",
                              fields={"details.photo_ids": [f"Не более {MAX_REPAIR_PHOTOS}."]})
        assets = [claim_media(pid, customer, purposes=[MediaAsset.Purpose.REPAIR_PHOTO], kinds=[MediaAsset.Kind.IMAGE])
                  for pid in photo_ids]
        board = str(details.get("board") or "").strip()[:200]
        cleaned = {"problem": problem, "desired_date": _clean_date(details.get("desired_date"), "desired_date"),
                   "photo_ids": [str(a.pk) for a in assets], "board": board}
        return cleaned, assets
    if kind == K.CUSTOM_ORDER:
        cleaned = {"params": _clean_scalar_map(details.get("params"), "details.params", max_keys=30, max_len=300),
                   "desired_date": _clean_date(details.get("desired_date"), "desired_date")}
        budget = details.get("budget")
        if budget not in (None, ""):
            try:
                budget = Decimal(str(budget))
            except InvalidOperation:
                budget = None
            if budget is None or budget < 0:
                raise DomainError("validation_error", "Бюджет должен быть неотрицательным числом.",
                                  fields={"details.budget": ["Неверная сумма."]})
            cleaned["budget"] = str(budget.quantize(Decimal("0.01")))
        comment = str(details.get("comment") or "").strip()
        if comment:
            cleaned["comment"] = comment[:1000]
        return cleaned, []
    return _clean_scalar_map(details, "details"), []


def _subject(kind, snapshot, explicit=""):
    explicit = (explicit or "").strip()
    if explicit:
        return explicit[:200]
    title = snapshot.get("title") or ""
    return f"{K(kind).label}: {title}"[:200] if title else K(kind).label


def _participant_rows(inquiry, customer):
    rows = [(customer, ConversationParticipant.Role.CUSTOMER, None)]
    if inquiry.provider_account_id:
        rows.append((inquiry.provider_account, ConversationParticipant.Role.PROVIDER, None))
    else:
        rows += [(account, ConversationParticipant.Role.MEMBER, inquiry.provider_organization)
                 for account in access.provider_staff(inquiry.provider_organization)]
    return rows


def _customer_name(account):
    from apps.accounts.serializers_public import PublicAccountSerializer

    return PublicAccountSerializer(account).data["display_name"]


def create_inquiry(customer, *, kind, message, target_type=None, target_id=None, provider_account_id=None,
                   provider_organization_id=None, details=None, subject="", source_channel="", request=None):
    if kind not in K.values:
        raise DomainError("validation_error", "Неизвестный вид обращения.", fields={"kind": ["Неверное значение."]})
    if provider_account_id:
        target_type, target_id = "account", provider_account_id
    elif provider_organization_id:
        target_type, target_id = "organization", provider_organization_id
    if not target_type or not target_id:
        raise DomainError("validation_error", "Укажите объект обращения или исполнителя.",
                          fields={"target_type": ["Обязательное поле."]})
    message = (message or "").strip()
    if not message:
        raise DomainError("validation_error", "Напишите сообщение исполнителю.", fields={"message": ["Обязательное поле."]})
    if len(message) > MAX_MESSAGE:
        raise DomainError("validation_error", "Сообщение слишком длинное.",
                          fields={"message": [f"Не более {MAX_MESSAGE} символов."]})

    target = resolve_target(target_type, target_id)
    _require_not_self(customer, target)
    _validate_kind(kind, target)
    _require_contact_allowed(customer, target)

    with transaction.atomic():
        cleaned_details, photo_assets = clean_details(kind, details, customer)
        snapshot = build_snapshot(target.target_type, target.obj)
        inquiry = Inquiry.objects.create(
            kind=kind, customer=customer, provider_account=target.provider_account,
            provider_organization=target.provider_organization if target.provider_account is None else None,
            subject=_subject(kind, snapshot, subject), message=message, details=cleaned_details,
            object_snapshot=snapshot, source_channel=(source_channel or target.source_channel)[:32],
            currency=snapshot.get("currency") or "RUB",
            **target.links,
        )
        InquiryStatusChange.objects.create(inquiry=inquiry, from_status="", to_status=S.NEW, actor=customer)
        conversation = Conversation.objects.create(kind=Conversation.Kind.INQUIRY, inquiry=inquiry,
                                                   subject=inquiry.subject)
        chat.add_participants(conversation, _participant_rows(inquiry, customer))
        chat.create_message(conversation, customer, body=message, assets=photo_assets, request=request,
                            notify_recipients=False)
        name = _customer_name(customer)
        for account in access.inquiry_provider_accounts(inquiry):
            notify(account, Notification.Kind.INQUIRY_NEW, f"Новое обращение: {K(kind).label}",
                   body=f"{name}: {inquiry.subject}", link=f"/account/inquiries/{inquiry.pk}",
                   payload={"inquiry_id": str(inquiry.pk), "conversation_id": str(conversation.pk), "kind": kind},
                   event_id=f"inquiry_new:{inquiry.pk}", actor=customer)
        track("inquiry_created", subject_type="inquiry", subject_id=inquiry.pk, actor=customer,
              owner_account=inquiry.provider_account, owner_organization=inquiry.provider_organization,
              context={"source_channel": inquiry.source_channel, "kind": kind, "target_type": target.target_type,
                       "target_id": str(target.obj.pk)},
              dedup_key=f"inquiry_created:{inquiry.pk}", request=request)
        audience = access.inquiry_audience_ids(inquiry)
        push_to_users(audience, {"type": "inquiry.updated", "inquiry_id": str(inquiry.pk), "status": inquiry.status})
        push_counters(audience)
    return inquiry


# --- выборки ---------------------------------------------------------------------------------------------------------

def get_inquiry_for(account, pk, *, lock=False):
    """Обращение, видимое аккаунту (клиент / исполнитель / текущий сотрудник). Иначе 404 (IDOR)."""
    qs = Inquiry.objects.filter(pk=pk)
    if lock:
        qs = qs.select_for_update(of=("self",))
    inquiry = qs.select_related("provider_organization", "provider_account", "customer").first()
    if inquiry is None:
        raise NotFound("Обращение не найдено.")
    side = access.inquiry_side(inquiry, account)
    if side is None:
        raise NotFound("Обращение не найдено.")
    return inquiry, side


def available_actions(inquiry, side):
    actions = [name for name, (who, sources, _to) in TRANSITIONS.items() if who == side and inquiry.status in sources]
    return actions


# --- переходы ---------------------------------------------------------------------------------------------------------

_SYSTEM_TEXT = {
    S.IN_PROGRESS: "Обращение принято в работу.",
    S.DECLINED: "Исполнитель отказал по обращению.",
    S.COMPLETED: "Работа по обращению завершена.",
    S.CANCELLED: "Клиент отменил обращение.",
}


def _status_notification(inquiry, to_status, actor, side, extra=""):
    title = f"Обращение «{inquiry.subject[:120]}»: {S(to_status).label.lower()}"
    recipients = [inquiry.customer] if side == access.PROVIDER else access.inquiry_provider_accounts(inquiry)
    for account in recipients:
        notify(account, Notification.Kind.INQUIRY_STATUS, title, body=extra,
               link=f"/account/inquiries/{inquiry.pk}",
               payload={"inquiry_id": str(inquiry.pk), "status": to_status},
               event_id=f"inquiry_status:{inquiry.pk}:{to_status}", actor=actor)


def _broadcast(inquiry, **extra):
    audience = access.inquiry_audience_ids(inquiry)
    push_to_users(audience, {"type": "inquiry.updated", "inquiry_id": str(inquiry.pk), "status": inquiry.status,
                             **extra})
    push_counters(audience)


def _mark_item_sold(inquiry, actor):
    from apps.boards.services.availability import refresh_variant_availability
    from apps.inventory.models import InventoryItem
    from apps.trust.services.audit import record

    item = InventoryItem.objects.select_for_update().filter(pk=inquiry.inventory_item_id).first()
    if item is None or item.status == InventoryItem.Status.SOLD:
        return
    before = {"status": item.status}
    item.status = InventoryItem.Status.SOLD
    item.save(update_fields=["status", "updated_at"])
    record(actor, "inventory.sold", item, before=before, after={"status": item.status, "inquiry": str(inquiry.pk)},
           organization=item.owner_organization)
    if item.variant_id:
        refresh_variant_availability(item.variant)


def transition_inquiry(account, pk, action, *, reason="", agreed_amount=None, amount_confirmed=False, request=None):
    if action not in TRANSITIONS:
        raise NotFound("Неизвестное действие.")
    required_side, sources, to_status = TRANSITIONS[action]
    reason = (reason or "").strip()
    if len(reason) > 300:
        raise DomainError("validation_error", "Причина слишком длинная.", fields={"reason": ["Не более 300 символов."]})
    with transaction.atomic():
        inquiry, side = get_inquiry_for(account, pk, lock=True)
        if side != required_side:
            who = "исполнитель" if required_side == access.PROVIDER else "клиент"
            raise Forbidden(f"Это действие может выполнить только {who}.", code="forbidden")
        if inquiry.status not in sources:
            raise Conflict(f"Нельзя выполнить действие в статусе «{inquiry.get_status_display()}».",
                           code="invalid_transition")
        from_status = inquiry.status
        now = timezone.now()
        inquiry.status = to_status
        extra = ""
        if to_status == S.DECLINED:
            inquiry.decline_reason = reason
            inquiry.closed_at = now
        elif to_status == S.CANCELLED:
            inquiry.cancel_reason = reason
            inquiry.closed_at = now
        elif to_status == S.COMPLETED:
            if amount_confirmed and agreed_amount is None and inquiry.agreed_amount is None:
                raise DomainError("validation_error", "Укажите согласованную сумму, чтобы подтвердить её.",
                                  fields={"agreed_amount": ["Обязательно при amount_confirmed."]})
            if agreed_amount is not None:
                inquiry.agreed_amount = agreed_amount
            inquiry.amount_confirmed = bool(amount_confirmed)
            inquiry.closed_at = now
        inquiry.save()
        InquiryStatusChange.objects.create(inquiry=inquiry, from_status=from_status, to_status=to_status,
                                           actor=account, comment=reason[:300])
        text = _SYSTEM_TEXT[to_status]
        if reason:
            text += f" Причина: {reason}"
            extra = f"Причина: {reason}"
        if to_status == S.COMPLETED and inquiry.agreed_amount is not None:
            from apps.commerce.services.snapshots import fmt_money

            amount_text = fmt_money(inquiry.agreed_amount, inquiry.currency)
            text += f" Сумма: {amount_text}{' (подтверждена)' if inquiry.amount_confirmed else ''}."
            extra = f"Сумма: {amount_text}"
        conversation = Conversation.objects.filter(inquiry=inquiry).first()
        if conversation is not None:
            chat.post_system_message(conversation, account, text, request=request)
        if to_status == S.COMPLETED:
            track("deal_completed", subject_type="inquiry", subject_id=inquiry.pk, actor=account,
                  owner_account=inquiry.provider_account, owner_organization=inquiry.provider_organization,
                  context={"amount": str(inquiry.agreed_amount) if inquiry.agreed_amount is not None else None,
                           "confirmed": inquiry.amount_confirmed, "currency": inquiry.currency, "kind": inquiry.kind},
                  dedup_key=f"deal_completed:{inquiry.pk}", request=request)
            if inquiry.kind == K.BOARD_PURCHASE and inquiry.inventory_item_id:
                _mark_item_sold(inquiry, account)
        _status_notification(inquiry, to_status, account, side, extra)
        _broadcast(inquiry)
    return inquiry


# --- этапы (SHO-06) ----------------------------------------------------------------------------------------------------

def _require_provider(side):
    if side != access.PROVIDER:
        raise Forbidden("Этапы ведёт исполнитель.", code="forbidden")


def _require_open(inquiry):
    if inquiry.status not in OPEN_STATUSES:
        raise Conflict("Обращение закрыто — этапы больше не меняются.", code="inquiry_closed")


def create_milestone(account, inquiry_pk, *, title, amount=None, due_date=None, position=None):
    with transaction.atomic():
        inquiry, side = get_inquiry_for(account, inquiry_pk, lock=True)
        _require_provider(side)
        _require_open(inquiry)
        if position is None:
            position = inquiry.milestones.count()
        milestone = InquiryMilestone.objects.create(inquiry=inquiry, title=title.strip(), amount=amount,
                                                    due_date=due_date, position=position)
        _broadcast(inquiry, milestone_id=str(milestone.pk))
    return milestone


def _get_milestone(account, pk, lock=True):
    qs = InquiryMilestone.objects.filter(pk=pk)
    if lock:
        qs = qs.select_for_update()
    milestone = qs.first()
    if milestone is None:
        raise NotFound("Этап не найден.")
    inquiry, side = get_inquiry_for(account, milestone.inquiry_id)
    return milestone, inquiry, side


def get_milestone_of(account, inquiry_pk, milestone_pk):
    milestone, inquiry, side = _get_milestone(account, milestone_pk)
    if str(milestone.inquiry_id) != str(inquiry_pk):
        raise NotFound("Этап не найден.")
    return milestone, inquiry, side


def update_milestone(account, inquiry_pk, milestone_pk, **changes):
    with transaction.atomic():
        milestone, inquiry, side = get_milestone_of(account, inquiry_pk, milestone_pk)
        _require_provider(side)
        _require_open(inquiry)
        if milestone.status != InquiryMilestone.Status.PLANNED:
            raise Conflict("Выполненный этап изменить нельзя.", code="milestone_locked")
        for key in ("title", "amount", "due_date", "position"):
            if key in changes:
                value = changes[key]
                setattr(milestone, key, value.strip() if key == "title" else value)
        milestone.save()
        _broadcast(inquiry, milestone_id=str(milestone.pk))
    return milestone


def delete_milestone(account, inquiry_pk, milestone_pk):
    with transaction.atomic():
        milestone, inquiry, side = get_milestone_of(account, inquiry_pk, milestone_pk)
        _require_provider(side)
        _require_open(inquiry)
        if milestone.status != InquiryMilestone.Status.PLANNED:
            raise Conflict("Выполненный этап удалить нельзя.", code="milestone_locked")
        milestone_id = str(milestone.pk)
        milestone.delete()
        _broadcast(inquiry, milestone_id=milestone_id)


def milestone_done(account, pk, request=None):
    with transaction.atomic():
        milestone, inquiry, side = _get_milestone(account, pk)
        _require_provider(side)
        _require_open(inquiry)
        if milestone.status != InquiryMilestone.Status.PLANNED:
            raise Conflict("Этап уже отмечен выполненным.", code="invalid_transition")
        milestone.status = InquiryMilestone.Status.DONE
        milestone.completed_at = timezone.now()
        milestone.save(update_fields=["status", "completed_at", "updated_at"])
        conversation = Conversation.objects.filter(inquiry=inquiry).first()
        if conversation is not None:
            chat.post_system_message(conversation, account,
                                     f"Этап «{milestone.title}» выполнен. Подтвердите, пожалуйста.", request=request)
        notify(inquiry.customer, Notification.Kind.INQUIRY_STATUS, f"Этап «{milestone.title[:100]}» выполнен",
               body="Исполнитель отметил этап выполненным — подтвердите его в обращении.",
               link=f"/account/inquiries/{inquiry.pk}",
               payload={"inquiry_id": str(inquiry.pk), "milestone_id": str(milestone.pk)},
               event_id=f"milestone_done:{milestone.pk}", actor=account)
        _broadcast(inquiry, milestone_id=str(milestone.pk))
    return milestone


def milestone_confirm(account, pk, request=None):
    with transaction.atomic():
        milestone, inquiry, side = _get_milestone(account, pk)
        if side != access.CUSTOMER:
            raise Forbidden("Подтвердить этап может только клиент.", code="forbidden")
        if milestone.status != InquiryMilestone.Status.DONE:
            raise Conflict("Подтвердить можно только выполненный этап.", code="invalid_transition")
        milestone.status = InquiryMilestone.Status.CONFIRMED
        milestone.confirmed_at = timezone.now()
        milestone.save(update_fields=["status", "confirmed_at", "updated_at"])
        conversation = Conversation.objects.filter(inquiry=inquiry).first()
        if conversation is not None:
            chat.post_system_message(conversation, account, f"Клиент подтвердил этап «{milestone.title}».",
                                     request=request)
        for provider in access.inquiry_provider_accounts(inquiry):
            notify(provider, Notification.Kind.INQUIRY_STATUS, f"Клиент подтвердил этап «{milestone.title[:100]}»",
                   link=f"/account/inquiries/{inquiry.pk}",
                   payload={"inquiry_id": str(inquiry.pk), "milestone_id": str(milestone.pk)},
                   event_id=f"milestone_confirmed:{milestone.pk}", actor=account)
        _broadcast(inquiry, milestone_id=str(milestone.pk))
    return milestone
