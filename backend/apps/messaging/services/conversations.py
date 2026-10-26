"""Диалоги: доступ участников, непрочитанность по read-курсорам, отправка, системные сообщения (7.2, 8.6, 25).

Непрочитанность — не статус обращения (7.2): это сообщения других участников, созданные позже моего
``last_read_at`` и не скрытые модератором. Доступ к диалогу обращения вычисляется по текущему членству в
организации-исполнителе (отзыв доступа действует немедленно, AT-09); строки участников для новых сотрудников
создаются лениво, а до этого их непрочитанное считается от начала диалога.
"""
from django.db import IntegrityError, transaction
from django.db.models import Count, F, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce, Greatest
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.serializers_public import PublicAccountSerializer
from apps.commerce.services import access as commerce_access
from apps.common.exceptions import Conflict, DomainError, NotFound
from apps.mediafiles.models import MediaAsset
from apps.mediafiles.services import claim_media
from apps.messaging.models import Conversation, ConversationParticipant, Message, MessageAttachment, Notification
from apps.messaging.services.counters import push_counters
from apps.messaging.services.media import signed_media
from apps.messaging.services.notify import notify
from apps.messaging.services.realtime import push_to_user
from apps.trust.models import AccountRestriction
from apps.trust.services.restrictions import MESSAGE_CODE, require_can_message, restriction_message
from apps.messaging.services.safety import is_blocked

MAX_BODY = 4000
MAX_ATTACHMENTS = 10
CLOSED_INQUIRY_STATUSES = ("declined", "cancelled")
PEER = "peer"

_iso_field = serializers.DateTimeField()


def iso(value):
    return _iso_field.to_representation(value) if value else None


# --- доступ -----------------------------------------------------------------------------------------------------

def accessible_conversations_q(account, org_ids=None):
    """Q для Conversation: диалоги, которые аккаунт видит прямо сейчас."""
    org_ids = commerce_access.provider_org_ids(account) if org_ids is None else org_ids
    own_rows = ConversationParticipant.objects.filter(account=account, left_at__isnull=True).values("conversation_id")
    inquiry_q = Q(kind=Conversation.Kind.INQUIRY) & (
        Q(inquiry__customer=account) | Q(inquiry__provider_account=account)
        | Q(inquiry__provider_organization_id__in=org_ids)
    )
    return inquiry_q | (~Q(kind=Conversation.Kind.INQUIRY) & Q(id__in=own_rows))


def conversation_side(conversation, account):
    """customer / provider (обращение) / peer (личная переписка) / None."""
    if not getattr(account, "is_authenticated", False):
        return None
    if conversation.kind == Conversation.Kind.INQUIRY:
        if conversation.inquiry_id is None:
            return None
        return commerce_access.inquiry_side(conversation.inquiry, account)
    if ConversationParticipant.objects.filter(conversation=conversation, account=account, left_at__isnull=True).exists():
        return PEER
    return None


def audience_ids(conversation):
    """Аккаунты, которые сейчас имеют доступ к диалогу (получатели WS-событий)."""
    if conversation.kind == Conversation.Kind.INQUIRY and conversation.inquiry_id:
        return commerce_access.inquiry_audience_ids(conversation.inquiry)
    return set(ConversationParticipant.objects.filter(conversation=conversation, left_at__isnull=True)
               .values_list("account_id", flat=True))


def get_conversation_for(account, pk):
    """Диалог, доступный аккаунту; чужой → 404 (существование не раскрывается)."""
    conversation = (Conversation.objects.select_related(
        "inquiry", "inquiry__provider_organization", "inquiry__provider_organization__owner",
        "inquiry__provider_account", "inquiry__customer",
    ).filter(pk=pk).first())
    if conversation is None or conversation_side(conversation, account) is None:
        raise NotFound("Диалог не найден.")
    return conversation


def ensure_participant(conversation, account):
    """Строка участника с read-курсором (создаётся лениво для новых сотрудников организации)."""
    defaults = {"role": ConversationParticipant.Role.PEER}
    inquiry = conversation.inquiry if conversation.kind == Conversation.Kind.INQUIRY else None
    if inquiry is not None:
        if inquiry.customer_id == account.pk:
            defaults = {"role": ConversationParticipant.Role.CUSTOMER}
        elif inquiry.provider_account_id == account.pk:
            defaults = {"role": ConversationParticipant.Role.PROVIDER}
        else:
            defaults = {"role": ConversationParticipant.Role.MEMBER, "organization_id": inquiry.provider_organization_id}
    participant, _ = ConversationParticipant.objects.get_or_create(
        conversation=conversation, account=account, defaults=defaults)
    return participant


def add_participants(conversation, rows):
    """rows: [(account, role, organization|None)] — без дублей."""
    existing = set(conversation.participants.values_list("account_id", flat=True))
    new = []
    for account, role, organization in rows:
        if account.pk in existing:
            continue
        existing.add(account.pk)
        new.append(ConversationParticipant(conversation=conversation, account=account, role=role,
                                           organization=organization))
    ConversationParticipant.objects.bulk_create(new, ignore_conflicts=True)


# --- непрочитанное ------------------------------------------------------------------------------------------------

def _unread_messages(account):
    my_read = (ConversationParticipant.objects
               .filter(conversation_id=OuterRef("conversation_id"), account_id=account.pk)
               .values("last_read_at")[:1])
    return (Message.objects.filter(is_hidden=False).exclude(sender_id=account.pk)
            .annotate(_my_read=Subquery(my_read))
            .filter(Q(_my_read__isnull=True) | Q(created_at__gt=F("_my_read"))))


def unread_messages_count(account, org_ids=None):
    conversation_ids = Conversation.objects.filter(accessible_conversations_q(account, org_ids)).values("id")
    return _unread_messages(account).filter(conversation_id__in=conversation_ids).count()


def unread_count_expression(account, outer_conversation_ref="pk"):
    """Аннотация «непрочитано мной» для queryset диалогов (``pk``) или обращений (``conversation__id``)."""
    qs = (_unread_messages(account).filter(conversation_id=OuterRef(outer_conversation_ref))
          .order_by().values("conversation_id").annotate(c=Count("id")).values("c"))
    return Coalesce(Subquery(qs, output_field=IntegerField()), Value(0))


def last_message_id_expression(outer_conversation_ref="pk"):
    return Subquery(Message.objects.filter(conversation_id=OuterRef(outer_conversation_ref), is_hidden=False)
                    .order_by("-created_at").values("id")[:1])


def unread_count(conversation, account):
    return _unread_messages(account).filter(conversation=conversation).count()


def last_messages_by_id(message_ids):
    ids = [m for m in message_ids if m]
    if not ids:
        return {}
    return {m.pk: m for m in Message.objects.filter(pk__in=ids).select_related("sender__profile")}


def last_message_preview(message, viewer):
    if message is None:
        return None
    body = message.body
    if not body and message.attachments.exists():
        body = "📎 Фото"
    sender_name = None
    if message.sender_id:
        sender_name = PublicAccountSerializer(message.sender).data["display_name"]
    return {
        "id": str(message.pk), "kind": message.kind, "body": body[:200], "created_at": iso(message.created_at),
        "sender_name": sender_name, "is_mine": bool(viewer and message.sender_id == viewer.pk),
    }


# --- сериализация сообщений -------------------------------------------------------------------------------------

def message_payload(message, request=None, viewer_id=None):
    mine = bool(viewer_id and message.sender_id == viewer_id)
    attachments = []
    if not message.is_hidden:
        attachments = [signed_media(att.media, request) for att in message.attachments.all()
                       if att.media.status != MediaAsset.Status.DELETED]
    return {
        "id": str(message.pk),
        "conversation_id": str(message.conversation_id),
        "kind": message.kind,
        "body": "" if message.is_hidden else message.body,
        "sender": PublicAccountSerializer(message.sender).data if message.sender_id else None,
        "is_mine": mine,
        "is_hidden": message.is_hidden,
        "client_id": message.client_id if mine else "",
        "created_at": iso(message.created_at),
        "edited_at": iso(message.edited_at),
        "attachments": attachments,
    }


def message_queryset():
    return Message.objects.select_related("sender__profile__avatar").prefetch_related("attachments__media")


# --- отправка ------------------------------------------------------------------------------------------------------

def counterpart_ids(conversation, account):
    """Аккаунты «другой стороны» для проверки блокировок."""
    if conversation.kind == Conversation.Kind.INQUIRY and conversation.inquiry_id:
        inquiry = conversation.inquiry
        principal = commerce_access.provider_principal(inquiry.provider_account, inquiry.provider_organization)
        if account.pk == inquiry.customer_id:
            return [principal.pk] if principal else []
        return [inquiry.customer_id]
    return list(ConversationParticipant.objects.filter(conversation=conversation)
                .exclude(account=account).values_list("account_id", flat=True))


def send_block_reason(conversation, account):
    """None — можно писать; иначе (http_status, code, message)."""
    if conversation.is_locked:
        return 409, "conversation_closed", "Переписка закрыта модератором."
    inquiry = conversation.inquiry if conversation.kind == Conversation.Kind.INQUIRY else None
    if inquiry is not None and inquiry.status in CLOSED_INQUIRY_STATUSES:
        return 409, "conversation_closed", "Обращение закрыто — отправка сообщений недоступна, история сохранена."
    restricted = restriction_message(account, AccountRestriction.Kind.MESSAGING)
    if restricted:
        return 403, MESSAGE_CODE, restricted
    pairs = [(account.pk, other) for other in counterpart_ids(conversation, account)]
    if inquiry is not None and account.pk != inquiry.customer_id:
        principal = commerce_access.provider_principal(inquiry.provider_account, inquiry.provider_organization)
        if principal is not None:
            pairs.append((principal.pk, inquiry.customer_id))
    if any(is_blocked(a, b) for a, b in pairs):
        return 403, "blocked", "Переписка недоступна: один из участников заблокировал другого."
    return None


def require_can_send(conversation, account):
    reason = send_block_reason(conversation, account)
    if reason:
        status_code, code, message = reason
        raise DomainError(code, message, status_code=status_code)


def _move_cursor(conversation, account, cursor):
    participant = ensure_participant(conversation, account)
    ConversationParticipant.objects.filter(pk=participant.pk).update(
        last_read_at=Greatest(F("last_read_at"), Value(cursor)))
    participant.refresh_from_db(fields=["last_read_at"])
    return participant


def _link_for(conversation):
    if conversation.inquiry_id:
        return f"/account/inquiries/{conversation.inquiry_id}"
    return f"/account/inquiries?conversation={conversation.pk}"


def _preview(message):
    if message.body:
        text = " ".join(message.body.split())
        return text if len(text) <= 140 else text[:139] + "…"
    return "📎 Фото"


def create_message(conversation, sender, *, body="", kind=Message.Kind.TEXT, assets=(), client_id="",
                   request=None, notify_recipients=True):
    """Низкоуровневое создание сообщения + WS message.new + уведомления + счётчики. Права проверяет вызывающий.

    Вызывать внутри transaction.atomic(): WS и счётчики уходят после коммита.
    """
    message = Message.objects.create(conversation=conversation, sender=sender, kind=kind, body=body,
                                     client_id=client_id or "")
    MessageAttachment.objects.bulk_create([
        MessageAttachment(message=message, media=asset, position=i) for i, asset in enumerate(assets)
    ])
    Conversation.objects.filter(pk=conversation.pk).update(last_message_at=message.created_at,
                                                          updated_at=timezone.now())
    conversation.last_message_at = message.created_at
    if sender is not None:
        _move_cursor(conversation, sender, message.created_at)
    message = message_queryset().get(pk=message.pk)
    fan_out_message(message, conversation, request=request, notify_recipients=notify_recipients)
    return message


def fan_out_message(message, conversation, request=None, notify_recipients=True):
    audience = audience_ids(conversation)
    sender_id = message.sender_id
    base = message_payload(message, request)
    for account_id in audience:
        payload = dict(base, is_mine=account_id == sender_id,
                       client_id=message.client_id if account_id == sender_id else "")
        push_to_user(account_id, {"type": "message.new", "conversation_id": str(conversation.pk), "message": payload})
    if notify_recipients and message.kind == Message.Kind.TEXT:
        from apps.accounts.models import Account

        muted = set(ConversationParticipant.objects.filter(conversation=conversation, is_muted=True)
                    .values_list("account_id", flat=True))
        sender_name = base["sender"]["display_name"] if base["sender"] else "ГДеволна"
        recipients = Account.objects.filter(pk__in=audience - {sender_id} - muted, is_active=True)
        for recipient in recipients:
            notify(recipient, Notification.Kind.MESSAGE_NEW, f"Новое сообщение от {sender_name}"[:200],
                   body=_preview(message), link=_link_for(conversation),
                   payload={"conversation_id": str(conversation.pk), "message_id": str(message.pk),
                            "inquiry_id": str(conversation.inquiry_id) if conversation.inquiry_id else None},
                   event_id=f"message_new:{message.pk}", actor=message.sender)
    push_counters(audience)


def send_message(conversation, sender, *, body="", attachment_ids=(), client_id="", request=None):
    """POST conversations/{id}/messages. Возвращает (message, created). Повтор с тем же client_id — без дубля."""
    body = (body or "").strip()
    client_id = (client_id or "").strip()
    if len(client_id) > 64:
        raise DomainError("validation_error", "Слишком длинный client_id.", fields={"client_id": ["Не более 64 символов."]})
    if client_id:
        existing = message_queryset().filter(conversation=conversation, sender=sender, client_id=client_id).first()
        if existing is not None:
            return existing, False
    require_can_send(conversation, sender)
    ids = list(dict.fromkeys(str(i) for i in (attachment_ids or [])))
    if not body and not ids:
        raise DomainError("message_empty", "Напишите сообщение или прикрепите фото.", fields={"body": ["Пустое сообщение."]})
    if len(body) > MAX_BODY:
        raise DomainError("validation_error", f"Сообщение длиннее {MAX_BODY} символов.",
                          fields={"body": [f"Не более {MAX_BODY} символов."]})
    if len(ids) > MAX_ATTACHMENTS:
        raise DomainError("too_many_attachments", f"Можно прикрепить не более {MAX_ATTACHMENTS} фото.",
                          fields={"attachment_ids": [f"Не более {MAX_ATTACHMENTS} файлов."]})
    with transaction.atomic():
        assets = [claim_media(mid, sender, purposes=[MediaAsset.Purpose.MESSAGE_ATTACHMENT],
                              kinds=[MediaAsset.Kind.IMAGE]) for mid in ids]
        try:
            with transaction.atomic():
                message = create_message(conversation, sender, body=body, assets=assets, client_id=client_id,
                                         request=request)
        except IntegrityError:
            if not client_id:
                raise
            existing = message_queryset().filter(conversation=conversation, sender=sender, client_id=client_id).first()
            if existing is None:
                raise
            return existing, False
    return message, True


def post_system_message(conversation, actor, body, request=None):
    """Системное сообщение в чате (смена статуса, этапы). Уведомления о статусе отправляет вызывающий."""
    return create_message(conversation, actor, body=body, kind=Message.Kind.SYSTEM, request=request,
                          notify_recipients=False)


# --- прочтение ------------------------------------------------------------------------------------------------------

def mark_read(conversation, account, message_id=None):
    """Двигает read-курсор вперёд (никогда назад), гасит уведомления о прочитанных сообщениях, рассылает WS."""
    if message_id:
        message = Message.objects.filter(conversation=conversation, pk=message_id).first()
        if message is None:
            raise NotFound("Сообщение не найдено в этом диалоге.")
        cursor = message.created_at
    else:
        # Курсор — время последнего видимого сообщения, а не «сейчас»: ещё не закоммиченное сообщение
        # с более ранним created_at не должно оказаться «прочитанным».
        cursor = (Message.objects.filter(conversation=conversation).order_by("-created_at")
                  .values_list("created_at", flat=True).first()) or conversation.created_at
    with transaction.atomic():
        participant = _move_cursor(conversation, account, cursor)
        _mark_message_notifications_read(conversation, account, participant.last_read_at)
        payload = {"type": "conversation.read", "conversation_id": str(conversation.pk),
                   "account_id": str(account.pk), "last_read_at": iso(participant.last_read_at)}
        for account_id in audience_ids(conversation) | {account.pk}:
            push_to_user(account_id, payload)
        push_counters([account.pk])
    return participant


def _mark_message_notifications_read(conversation, account, cursor):
    pending = list(Notification.objects.filter(
        recipient=account, kind=Notification.Kind.MESSAGE_NEW, read_at__isnull=True,
        payload__conversation_id=str(conversation.pk),
    ).values_list("id", "payload"))
    if not pending:
        return 0
    message_ids = [p.get("message_id") for _, p in pending if p.get("message_id")]
    read_ids = {str(pk) for pk in Message.objects.filter(conversation=conversation, pk__in=message_ids,
                                                         created_at__lte=cursor).values_list("pk", flat=True)}
    to_mark = [nid for nid, p in pending if not p.get("message_id") or p.get("message_id") in read_ids]
    return Notification.objects.filter(pk__in=to_mark).update(read_at=timezone.now())


# --- личная переписка GG Surfer -------------------------------------------------------------------------------------

def direct_key(a_id, b_id):
    return ":".join(sorted([str(a_id), str(b_id)]))


def open_direct_conversation(me, other_id):
    """POST direct-conversations: одна беседа на пару; учитывает согласие GG Surfer, политику контактов и блокировки."""
    from apps.accounts.models import Account

    other = (Account.objects.select_related("profile")
             .filter(pk=other_id, is_active=True, anonymized_at__isnull=True).first())
    if other is None or not hasattr(other, "profile"):
        raise NotFound("Пользователь не найден.")
    if other.pk == me.pk:
        raise DomainError("self_conversation", "Нельзя написать самому себе.")
    require_can_message(me)
    if is_blocked(me, other):
        raise DomainError("blocked", "Переписка недоступна: один из участников заблокировал другого.", status_code=403)
    key = direct_key(me.pk, other.pk)
    existing = Conversation.objects.filter(direct_key=key).first()
    if existing is not None:
        return existing, False
    profile = other.profile
    if not profile.gg_surfer_enabled or profile.gg_contact_policy != profile.ContactPolicy.EVERYONE:
        raise DomainError("contact_not_allowed", "Пользователь не принимает сообщения от участников GG Surfer.",
                          status_code=403)
    try:
        with transaction.atomic():
            conversation = Conversation.objects.create(kind=Conversation.Kind.DIRECT, direct_key=key)
            ConversationParticipant.objects.bulk_create([
                ConversationParticipant(conversation=conversation, account=me, role=ConversationParticipant.Role.PEER),
                ConversationParticipant(conversation=conversation, account=other, role=ConversationParticipant.Role.PEER),
            ])
    except IntegrityError:
        conversation = Conversation.objects.filter(direct_key=key).first()
        if conversation is None:
            raise Conflict("Не удалось открыть переписку, повторите попытку.") from None
        return conversation, False
    return conversation, True


# --- выдача сообщений -------------------------------------------------------------------------------------------------

def _parse_cursor(conversation, value):
    if not value:
        return None
    import uuid

    from django.utils.dateparse import parse_datetime

    try:
        message_id = uuid.UUID(str(value))
    except ValueError:
        message_id = None
    if message_id is not None:
        message = Message.objects.filter(conversation=conversation, pk=message_id).only("created_at", "id").first()
        if message is None:
            raise DomainError("invalid_cursor", "Сообщение-курсор не найдено.", fields={"before": ["Неизвестный id."]})
        return message.created_at, message.pk
    parsed = parse_datetime(str(value))
    if parsed is None:
        raise DomainError("invalid_cursor", "Курсор должен быть id сообщения или датой ISO 8601.")
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed, None


def list_messages(conversation, *, before=None, after=None, limit=30):
    """Страница сообщений (по возрастанию времени, новые — последними) + флаг наличия более ранних."""
    limit = max(1, min(int(limit or 30), 100))
    qs = message_queryset().filter(conversation=conversation)
    after_cursor = _parse_cursor(conversation, after)
    if after_cursor:
        created, pk = after_cursor
        cond = Q(created_at__gt=created) | (Q(created_at=created, id__gt=pk) if pk else Q(pk__in=[]))
        items = list(qs.filter(cond).order_by("created_at", "id")[:limit + 1])
        has_more_newer = len(items) > limit
        return items[:limit], False, has_more_newer
    before_cursor = _parse_cursor(conversation, before)
    if before_cursor:
        created, pk = before_cursor
        cond = Q(created_at__lt=created) | (Q(created_at=created, id__lt=pk) if pk else Q(pk__in=[]))
        qs = qs.filter(cond)
    items = list(qs.order_by("-created_at", "-id")[:limit + 1])
    has_more = len(items) > limit
    items = list(reversed(items[:limit]))
    return items, has_more, False
