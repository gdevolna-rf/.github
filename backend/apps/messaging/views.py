"""Диалоги, сообщения, read-курсоры, уведомления, настройки, блокировки, счётчики (8.6, 25, COM-07)."""
from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from apps.accounts.models import Account
from apps.common.exceptions import DomainError, NotFound
from apps.messaging import serializers as s
from apps.messaging.models import AccountBlock, Conversation, ConversationParticipant, Notification, NotificationPreference
from apps.messaging.services import conversations as chat
from apps.messaging.services.counters import get_counters, push_counters
from apps.messaging.services.notify import default_channels


def conversation_queryset():
    return Conversation.objects.select_related(
        "inquiry__customer__profile__avatar", "inquiry__provider_account__profile__avatar",
        "inquiry__provider_organization__logo",
    ).prefetch_related(Prefetch("participants", queryset=ConversationParticipant.objects.select_related(
        "account__profile__avatar")))


def _conversation_detail(conversation, request):
    conversation = conversation_queryset().get(pk=conversation.pk)
    conversation._last_message_id = (conversation.messages.filter(is_hidden=False).order_by("-created_at")
                                     .values_list("id", flat=True).first())
    context = {"request": request, "last_messages": chat.last_messages_by_id([conversation._last_message_id])}
    return s.ConversationDetailSerializer(conversation, context=context).data


class ConversationListView(GenericAPIView):
    serializer_class = s.ConversationListSerializer

    @extend_schema(summary="Мои диалоги (обращения и личная переписка GG Surfer)",
                   parameters=[OpenApiParameter("kind", str, enum=["inquiry", "direct", "support"]),
                               OpenApiParameter("unread", bool), OpenApiParameter("page", int),
                               OpenApiParameter("page_size", int)],
                   responses=s.ConversationListSerializer(many=True))
    def get(self, request):
        user = request.user
        qs = conversation_queryset().filter(chat.accessible_conversations_q(user))
        kind = request.query_params.get("kind")
        if kind:
            qs = qs.filter(kind=kind)
        qs = qs.annotate(_unread=chat.unread_count_expression(user, "pk"),
                         _last_message_id=chat.last_message_id_expression("pk"))
        if request.query_params.get("unread") in ("1", "true", "yes"):
            qs = qs.filter(_unread__gt=0)
        page = self.paginate_queryset(qs.order_by("-last_message_at", "-created_at"))
        context = self.get_serializer_context()
        context["last_messages"] = chat.last_messages_by_id([getattr(c, "_last_message_id", None) for c in page])
        return self.get_paginated_response(s.ConversationListSerializer(page, many=True, context=context).data)


class ConversationDetailView(GenericAPIView):
    serializer_class = s.ConversationDetailSerializer

    @extend_schema(summary="Диалог: участники, read-курсоры, возможность отправки",
                   responses=s.ConversationDetailSerializer)
    def get(self, request, pk):
        conversation = chat.get_conversation_for(request.user, pk)
        chat.ensure_participant(conversation, request.user)
        return Response(_conversation_detail(conversation, request))


class MessageListCreateView(GenericAPIView):
    serializer_class = s.ChatMessageSerializer

    def get_throttles(self):
        # Rate limit только на отправку (scope messages); чтение ленты не ограничиваем.
        self.throttle_scope = "messages" if self.request.method == "POST" else None
        return super().get_throttles()

    @extend_schema(
        summary="Сообщения диалога (курсор before/after, новые — последними)",
        parameters=[OpenApiParameter("before", str, description="id сообщения или ISO-время: более ранние"),
                    OpenApiParameter("after", str, description="id сообщения или ISO-время: более новые"),
                    OpenApiParameter("limit", int, description="1…100, по умолчанию 30")],
        responses=s.ChatMessagePageSerializer,
    )
    def get(self, request, pk):
        conversation = chat.get_conversation_for(request.user, pk)
        chat.ensure_participant(conversation, request.user)
        try:
            limit = int(request.query_params.get("limit") or 30)
        except ValueError:
            raise DomainError("validation_error", "limit — число.", fields={"limit": ["Ожидается число."]}) from None
        items, has_more, has_newer = chat.list_messages(conversation, before=request.query_params.get("before"),
                                                        after=request.query_params.get("after"), limit=limit)
        context = self.get_serializer_context()
        return Response({
            "results": s.ChatMessageSerializer(items, many=True, context=context).data,
            "has_more": has_more, "has_newer": has_newer,
            "next_before": str(items[0].pk) if items and has_more else None,
        })

    @extend_schema(summary="Отправить сообщение / фото (участник; до и после принятия обращения)",
                   request=s.ChatMessageCreateSerializer,
                   responses={201: s.ChatMessageSerializer, 200: OpenApiResponse(s.ChatMessageSerializer,
                                                                             description="Повтор с тем же client_id")})
    def post(self, request, pk):
        conversation = chat.get_conversation_for(request.user, pk)
        serializer = s.ChatMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        message, created = chat.send_message(conversation, request.user, body=data["body"],
                                             attachment_ids=data["attachment_ids"], client_id=data["client_id"],
                                             request=request)
        return Response(s.ChatMessageSerializer(message, context=self.get_serializer_context()).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class ConversationReadView(GenericAPIView):
    serializer_class = s.ConversationReadRequestSerializer

    @extend_schema(summary="Отметить прочитанным (read-курсор, BR-10, AT-04, ATX-10)", request=s.ConversationReadRequestSerializer,
                   responses=s.ConversationReadResultSerializer)
    def post(self, request, pk):
        conversation = chat.get_conversation_for(request.user, pk)
        serializer = s.ConversationReadRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        participant = chat.mark_read(conversation, request.user, serializer.validated_data.get("message_id"))
        return Response({
            "conversation_id": str(conversation.pk), "last_read_at": chat.iso(participant.last_read_at),
            "unread_count": chat.unread_count(conversation, request.user), "counters": get_counters(request.user),
        })


class DirectConversationView(GenericAPIView):
    serializer_class = s.DirectConversationCreateSerializer

    @extend_schema(summary="Личная переписка GG Surfer (одна на пару; gg_contact_policy и блокировки)",
                   request=s.DirectConversationCreateSerializer,
                   responses={201: s.ConversationDetailSerializer,
                              200: OpenApiResponse(s.ConversationDetailSerializer, description="Уже существует")})
    def post(self, request):
        serializer = s.DirectConversationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation, created = chat.open_direct_conversation(request.user, serializer.validated_data["account_id"])
        return Response(_conversation_detail(conversation, request),
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


# --- уведомления -------------------------------------------------------------------------------------------------------


class NotificationListView(GenericAPIView):
    serializer_class = s.UserNotificationSerializer

    @extend_schema(summary="Лента уведомлений", parameters=[OpenApiParameter("unread", bool),
                                                            OpenApiParameter("kind", str),
                                                            OpenApiParameter("page", int),
                                                            OpenApiParameter("page_size", int)],
                   responses=s.UserNotificationSerializer(many=True))
    def get(self, request):
        qs = Notification.objects.filter(recipient=request.user).select_related("actor__profile__avatar")
        if request.query_params.get("unread") in ("1", "true", "yes"):
            qs = qs.filter(read_at__isnull=True)
        kind = request.query_params.get("kind")
        if kind:
            qs = qs.filter(kind__in=[k for k in kind.split(",") if k])
        page = self.paginate_queryset(qs.order_by("-created_at"))
        return self.get_paginated_response(s.UserNotificationSerializer(page, many=True).data)


class NotificationReadView(GenericAPIView):
    serializer_class = s.UserNotificationSerializer

    @extend_schema(summary="Отметить уведомление прочитанным", request=None, responses=s.UserNotificationSerializer)
    def post(self, request, pk):
        notification = Notification.objects.filter(pk=pk, recipient=request.user).first()
        if notification is None:
            raise NotFound("Уведомление не найдено.")
        if notification.read_at is None:
            Notification.objects.filter(pk=pk, read_at__isnull=True).update(read_at=timezone.now())
            notification.refresh_from_db()
            push_counters([request.user.pk])
        return Response(s.UserNotificationSerializer(notification).data)


class NotificationReadAllView(GenericAPIView):
    serializer_class = s.NotificationsReadAllSerializer

    @extend_schema(summary="Прочитать все уведомления", request=None, responses=s.NotificationsReadAllSerializer)
    def post(self, request):
        updated = Notification.objects.filter(recipient=request.user, read_at__isnull=True).update(
            read_at=timezone.now())
        push_counters([request.user.pk])
        return Response({"updated": updated})


def _preferences(account):
    saved = {p.kind: p for p in NotificationPreference.objects.filter(account=account)}
    result = []
    for kind, label in Notification.Kind.choices:
        pref = saved.get(kind)
        if pref is None:
            in_app, email, push = default_channels(kind)
        else:
            in_app, email, push = pref.in_app, pref.email, pref.push
        result.append({"kind": kind, "label": str(label), "in_app": in_app, "email": email, "push": push,
                       "is_default": pref is None})
    return {"preferences": result}


class NotificationPreferencesView(GenericAPIView):
    serializer_class = s.NotificationPreferencesSerializer

    @extend_schema(summary="Каналы уведомлений по видам (MSG-12); без записи — значения по умолчанию",
                   responses=s.NotificationPreferencesSerializer)
    def get(self, request):
        return Response(_preferences(request.user))

    @extend_schema(summary="Изменить каналы для перечисленных видов", request=s.NotificationPreferencesSerializer,
                   responses=s.NotificationPreferencesSerializer)
    def put(self, request):
        serializer = s.NotificationPreferencesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            current = {p["kind"]: p for p in _preferences(request.user)["preferences"]}
            for item in serializer.validated_data["preferences"]:
                base = current[item["kind"]]
                NotificationPreference.objects.update_or_create(
                    account=request.user, kind=item["kind"],
                    defaults={"in_app": item.get("in_app", base["in_app"]), "email": item.get("email", base["email"]),
                              "push": item.get("push", base["push"])},
                )
        return Response(_preferences(request.user))


# --- блокировки --------------------------------------------------------------------------------------------------------


class MyBlocksView(GenericAPIView):
    serializer_class = s.AccountBlockSerializer

    @extend_schema(summary="Заблокированные мной пользователи (COM-07)", responses=s.AccountBlockSerializer(many=True))
    def get(self, request):
        qs = (AccountBlock.objects.filter(blocker=request.user).select_related("blocked__profile__avatar")
              .order_by("-created_at"))
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(s.AccountBlockSerializer(page, many=True).data)


class BlockCreateView(GenericAPIView):
    serializer_class = s.AccountBlockCreateSerializer

    @extend_schema(summary="Заблокировать собеседника", request=s.AccountBlockCreateSerializer,
                   responses={201: s.AccountBlockSerializer, 200: OpenApiResponse(s.AccountBlockSerializer, description="Уже заблокирован")})
    def post(self, request):
        serializer = s.AccountBlockCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target = Account.objects.filter(pk=serializer.validated_data["account_id"]).first()
        if target is None:
            raise NotFound("Пользователь не найден.")
        if target.pk == request.user.pk:
            raise DomainError("self_block", "Нельзя заблокировать самого себя.")
        try:
            with transaction.atomic():
                block, created = AccountBlock.objects.get_or_create(blocker=request.user, blocked=target)
        except IntegrityError:
            block, created = AccountBlock.objects.get(blocker=request.user, blocked=target), False
        block = AccountBlock.objects.select_related("blocked__profile__avatar").get(pk=block.pk)
        return Response(s.AccountBlockSerializer(block).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class BlockDeleteView(GenericAPIView):
    serializer_class = s.AccountBlockSerializer

    @extend_schema(summary="Снять блокировку", responses={204: None})
    def delete(self, request, account_id):
        deleted, _ = AccountBlock.objects.filter(blocker=request.user, blocked_id=account_id).delete()
        if not deleted:
            raise NotFound("Блокировка не найдена.")
        return Response(status=status.HTTP_204_NO_CONTENT)


class CountersView(GenericAPIView):
    serializer_class = s.MeCountersSerializer

    @extend_schema(summary="Счётчики шапки: непрочитанные сообщения/уведомления, новые обращения, ожидающие брони",
                   responses=s.MeCountersSerializer)
    def get(self, request):
        return Response(get_counters(request.user))
