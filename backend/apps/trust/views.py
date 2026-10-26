"""API trust: отзывы, жалобы/апелляции, единая очередь и решения модератора, журнал, ограничения."""
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view, inline_serializer
from rest_framework import generics, serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Account
from apps.accounts.serializers_public import PublicAccountSerializer
from apps.common.exceptions import DomainError
from apps.common.pagination import StandardPagination
from apps.common.permissions import IsModerator, ReadOnlyOrAuthenticated
from apps.learning.models import InstructorCertificate
from apps.organizations.models import Organization
from apps.spots.models import SpotChangeRequest
from apps.trust.models import AuditEvent, Complaint, ModerationCase, Review
from apps.trust.serializers import (
    AppealDecisionSerializer,
    AppealSerializer,
    AuditEventSerializer,
    CaseDetailSerializer,
    CaseListSerializer,
    CertificateCaseTargetSerializer,
    CommentRequiredSerializer,
    ComplaintAgainstMeSerializer,
    ComplaintCaseTargetSerializer,
    ComplaintCreateSerializer,
    ComplaintResolveSerializer,
    ModeratorComplaintShortSerializer,
    MyComplaintSerializer,
    MyReviewSerializer,
    NoteOptionalSerializer,
    NoteRequiredSerializer,
    OrganizationCaseTargetSerializer,
    ProposalApproveSerializer,
    ProposalRevertSerializer,
    PublicReviewSerializer,
    RestrictionSerializer,
    RestrictSerializer,
    ReviewCaseTargetSerializer,
    ReviewSubmitSerializer,
    SpotChangeCaseTargetSerializer,
)
from apps.trust.services import complaints as complaint_service
from apps.trust.services import decisions
from apps.trust.services import reviews as review_service
from apps.trust.services.audit import record
from apps.trust.services.case_queries import account_summary
from apps.trust.services.stats import moderation_stats


def _multi(request, name, allowed):
    values = [v.strip() for v in request.query_params.get(name, "").split(",") if v.strip()]
    unknown = [v for v in values if v not in allowed]
    if unknown:
        raise DomainError("validation_error", "Неизвестное значение фильтра.",
                          fields={name: [f"Неизвестные значения: {', '.join(unknown)}."]})
    return values


def _uuid_param(request, name):
    value = request.query_params.get(name)
    if not value:
        return None
    try:
        return serializers.UUIDField().to_internal_value(value)
    except serializers.ValidationError:
        raise DomainError("validation_error", "Неверный идентификатор.", fields={name: ["Неверный UUID."]})


def _review_qs():
    return Review.objects.select_related(
        "author__profile__avatar", "spot", "instructor__account__profile", "organization"
    ).prefetch_related("photos", "pending_photos")


# --- отзывы ---------------------------------------------------------------------------------------

@extend_schema_view(
    get=extend_schema(
        parameters=[
            OpenApiParameter("target_type", str, enum=Review.Target.values, required=True),
            OpenApiParameter("target_id", OpenApiTypes.UUID, required=True),
        ],
        responses=PublicReviewSerializer(many=True),
    ),
    post=extend_schema(request=ReviewSubmitSerializer, responses={201: MyReviewSerializer, 200: MyReviewSerializer}),
)
class ReviewListCreateView(generics.GenericAPIView):
    permission_classes = [ReadOnlyOrAuthenticated]
    serializer_class = PublicReviewSerializer

    def get(self, request):
        target_type = request.query_params.get("target_type")
        if target_type not in Review.Target.values:
            raise DomainError("validation_error", "Укажите тип объекта отзыва.", fields={"target_type": ["Обязательный параметр."]})
        target_id = _uuid_param(request, "target_id")
        if target_id is None:
            raise DomainError("validation_error", "Укажите объект отзыва.", fields={"target_id": ["Обязательный параметр."]})
        review_service.resolve_target(target_type, target_id)
        qs = Review.objects.filter(
            status=Review.Status.PUBLISHED, target_type=target_type,
            **{f"{review_service.TARGET_FK[target_type]}_id": target_id},
        ).select_related("author__profile__avatar").prefetch_related("photos").order_by("-published_at", "-created_at")
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(PublicReviewSerializer(page, many=True).data)

    def post(self, request):
        body = ReviewSubmitSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        review, created = review_service.submit_review(request.user, request=request, **body.validated_data)
        review = _review_qs().get(pk=review.pk)
        return Response(MyReviewSerializer(review).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class ReviewDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None})
    def delete(self, request, pk):
        review_service.delete_own_review(pk, request.user, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(parameters=[OpenApiParameter("status", str, description="pending|published|rejected|hidden (через запятую)")])
class MyReviewListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MyReviewSerializer

    def get_queryset(self):
        qs = _review_qs().filter(author=self.request.user).order_by("-created_at")
        statuses = _multi(self.request, "status", Review.Status.values)
        return qs.filter(status__in=statuses) if statuses else qs


# --- жалобы ---------------------------------------------------------------------------------------

class ComplaintCreateView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "reports"

    @extend_schema(request=ComplaintCreateSerializer, responses={201: MyComplaintSerializer})
    def post(self, request):
        body = ComplaintCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        complaint = complaint_service.create_complaint(request.user, request=request, **body.validated_data)
        return Response(MyComplaintSerializer(complaint).data, status=status.HTTP_201_CREATED)


@extend_schema(
    parameters=[OpenApiParameter("box", str, enum=["filed", "against"],
                                 description="filed — мои жалобы (по умолчанию); against — решения по жалобам на мои материалы")],
    responses=MyComplaintSerializer(many=True),
)
class MyComplaintListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]

    def _box(self):
        return "against" if self.request.query_params.get("box") == "against" else "filed"

    def get_serializer_class(self):
        return ComplaintAgainstMeSerializer if self._box() == "against" else MyComplaintSerializer

    def get_queryset(self):
        if self._box() == "against":
            # Открытые жалобы и отклонённые не показываются владельцу; личность автора жалобы не раскрывается.
            return Complaint.objects.filter(target_owner=self.request.user, status=Complaint.Status.RESOLVED) \
                .exclude(action_taken=Complaint.Action.NONE).order_by("-updated_at")
        return Complaint.objects.filter(reporter=self.request.user).order_by("-created_at")


class ComplaintAppealView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=AppealSerializer, responses=ComplaintAgainstMeSerializer)
    def post(self, request, pk):
        body = AppealSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        complaint = complaint_service.appeal_complaint(pk, request.user, body.validated_data["text"], request=request)
        return Response(ComplaintAgainstMeSerializer(complaint).data)


# --- модерация: очередь ---------------------------------------------------------------------------

OPEN_CASE_STATUSES = [ModerationCase.Status.OPEN, ModerationCase.Status.IN_REVIEW]


@extend_schema(parameters=[
    OpenApiParameter("kind", str, description="spot_change|review|certificate|complaint|organization|appeal (через запятую)"),
    OpenApiParameter("status", str, enum=["open", "in_review", "resolved", "all"],
                     description="open (по умолчанию) — открытые и в работе"),
    OpenApiParameter("overdue", bool, description="Только просроченные по SLA"),
    OpenApiParameter("assigned", str, enum=["me", "none"]),
    OpenApiParameter("q", str, description="Поиск по краткому описанию"),
])
class CaseListView(generics.ListAPIView):
    permission_classes = [IsModerator]
    serializer_class = CaseListSerializer

    def get_queryset(self):
        request = self.request
        qs = ModerationCase.objects.select_related("assigned_to__profile__avatar", "resolved_by__profile__avatar")
        kinds = _multi(request, "kind", ModerationCase.Kind.values)
        if kinds:
            qs = qs.filter(kind__in=kinds)
        status_param = request.query_params.get("status", "open")
        if status_param == "resolved":
            qs = qs.filter(status=ModerationCase.Status.RESOLVED).order_by("-resolved_at")
        elif status_param == "in_review":
            qs = qs.filter(status=ModerationCase.Status.IN_REVIEW).order_by(F("due_at").asc(nulls_last=True), "created_at")
        elif status_param == "all":
            qs = qs.order_by("-created_at")
        elif status_param == "open":
            qs = qs.filter(status__in=OPEN_CASE_STATUSES).order_by(F("due_at").asc(nulls_last=True), "created_at")
        else:
            raise DomainError("validation_error", "Неизвестный статус.", fields={"status": ["open|in_review|resolved|all"]})
        if request.query_params.get("overdue") in ("1", "true", "True"):
            qs = qs.filter(status__in=OPEN_CASE_STATUSES, due_at__lt=timezone.now())
        assigned = request.query_params.get("assigned")
        if assigned == "me":
            qs = qs.filter(assigned_to=request.user)
        elif assigned == "none":
            qs = qs.filter(assigned_to__isnull=True)
        q = request.query_params.get("q", "").strip()
        if q:
            qs = qs.filter(summary__icontains=q)
        return qs


def _case_detail_qs():
    return ModerationCase.objects.select_related(
        "assigned_to__profile__avatar", "resolved_by__profile__avatar",
        "spot_change_request__spot__region", "spot_change_request__author__profile__avatar",
        "spot_change_request__moderator__profile",
        "review__author__profile__avatar", "review__spot", "review__instructor__account__profile", "review__organization",
        "certificate__instructor__account__profile__avatar", "certificate__document",
        "complaint__reporter__profile__avatar", "complaint__target_owner__profile__avatar",
        "organization__owner__profile__avatar", "organization__region", "organization__logo", "organization__cover",
    )


class CaseDetailView(APIView):
    permission_classes = [IsModerator]

    @extend_schema(responses=CaseDetailSerializer)
    def get(self, request, pk):
        case = get_object_or_404(_case_detail_qs(), pk=pk)
        if case.certificate_id:  # скан может содержать персональные данные (TRUST-03) — фиксируем доступ
            record(request.user, "certificate.scan_viewed", case.certificate, metadata={"case_id": str(case.pk)},
                   request=request)
        elif case.complaint_id and case.complaint.target_type == Complaint.Target.MESSAGE:
            record(request.user, "message.viewed_by_moderator", object_type="messaging.message",
                   object_id=case.complaint.target_id, metadata={"case_id": str(case.pk)}, request=request)
        return Response(CaseDetailSerializer(case, context={"request": request}).data)


class CaseTakeView(APIView):
    permission_classes = [IsModerator]

    @extend_schema(request=None, responses=CaseListSerializer)
    def post(self, request, pk):
        case = decisions.take_case(pk, request.user)
        return Response(CaseListSerializer(case).data)


# --- модерация: решения ---------------------------------------------------------------------------

class _DecisionView(APIView):
    """POST с телом body_serializer → handler(pk, moderator, request=..., **data) → response_serializer(obj)."""

    permission_classes = [IsModerator]
    body_serializer = NoteOptionalSerializer
    response_serializer = None
    queryset_factory = None

    def handler(self, pk, moderator, **data):  # pragma: no cover - переопределяется
        raise NotImplementedError

    def post(self, request, pk):
        body = self.body_serializer(data=request.data)
        body.is_valid(raise_exception=True)
        obj = self.handler(pk, request.user, request=request, **body.validated_data)
        if isinstance(obj, tuple):
            obj = obj[0]
        if self.queryset_factory is not None:
            obj = self.queryset_factory().get(pk=obj.pk)
        return Response(self.response_serializer(obj, context={"request": request}).data)


def _decision(handler, body, response, queryset_factory=None):
    view = type(f"{handler.__name__.title().replace('_', '')}View", (_DecisionView,), {
        "body_serializer": body, "response_serializer": response,
        "queryset_factory": staticmethod(queryset_factory) if queryset_factory else None,
        "handler": lambda self, pk, moderator, **data: handler(pk, moderator, **data),
    })
    return extend_schema_view(post=extend_schema(request=body, responses=response,
                                                 operation_id=f"moderation_{handler.__name__}"))(view)


def _proposal_qs():
    return SpotChangeRequest.objects.select_related("spot__region", "author__profile__avatar", "moderator__profile") \
        .prefetch_related("evidence")


def _certificate_qs():
    return InstructorCertificate.objects.select_related("instructor__account__profile__avatar", "document")


def _organization_qs():
    return Organization.objects.select_related("owner__profile__avatar", "region", "logo", "cover")


def _complaint_qs():
    return Complaint.objects.select_related("reporter__profile__avatar", "target_owner__profile__avatar")


ProposalApproveView = _decision(decisions.approve_proposal, ProposalApproveSerializer, SpotChangeCaseTargetSerializer,
                                _proposal_qs)
ProposalRejectView = _decision(decisions.reject_proposal, CommentRequiredSerializer, SpotChangeCaseTargetSerializer,
                               _proposal_qs)
ProposalRequestInfoView = _decision(decisions.request_proposal_info, CommentRequiredSerializer,
                                    SpotChangeCaseTargetSerializer, _proposal_qs)
ProposalRevertView = _decision(decisions.revert_proposal, ProposalRevertSerializer, SpotChangeCaseTargetSerializer,
                               _proposal_qs)
ReviewApproveView = _decision(decisions.approve_review, NoteOptionalSerializer, ReviewCaseTargetSerializer, _review_qs)
ReviewRejectView = _decision(decisions.reject_review, NoteRequiredSerializer, ReviewCaseTargetSerializer, _review_qs)
ReviewHideView = _decision(decisions.hide_review, NoteRequiredSerializer, ReviewCaseTargetSerializer, _review_qs)
CertificateApproveView = _decision(decisions.approve_certificate, NoteOptionalSerializer, CertificateCaseTargetSerializer,
                                   _certificate_qs)
CertificateRejectView = _decision(decisions.reject_certificate, NoteRequiredSerializer, CertificateCaseTargetSerializer,
                                  _certificate_qs)
CertificateRevokeView = _decision(decisions.revoke_certificate, NoteRequiredSerializer, CertificateCaseTargetSerializer,
                                  _certificate_qs)
OrganizationApproveView = _decision(decisions.approve_organization, NoteOptionalSerializer,
                                    OrganizationCaseTargetSerializer, _organization_qs)
OrganizationRejectView = _decision(decisions.reject_organization, NoteRequiredSerializer,
                                   OrganizationCaseTargetSerializer, _organization_qs)
ComplaintResolveView = _decision(decisions.resolve_complaint, ComplaintResolveSerializer, ComplaintCaseTargetSerializer,
                                 _complaint_qs)
ComplaintDismissView = _decision(decisions.dismiss_complaint, NoteOptionalSerializer, ComplaintCaseTargetSerializer,
                                 _complaint_qs)
ComplaintAppealDecisionView = _decision(decisions.decide_appeal, AppealDecisionSerializer, ComplaintCaseTargetSerializer,
                                        _complaint_qs)
RestrictionLiftView = _decision(decisions.lift_restriction, NoteOptionalSerializer, RestrictionSerializer)


# --- модерация: аккаунты, журнал, статистика -------------------------------------------------------

class ModerationAccountView(APIView):
    permission_classes = [IsModerator]

    @extend_schema(responses=inline_serializer("ModerationAccountSummary", {
        "account": PublicAccountSerializer(),
        "summary": serializers.DictField(),
        "restrictions": RestrictionSerializer(many=True),
        "complaints": ModeratorComplaintShortSerializer(many=True),
    }))
    def get(self, request, pk):
        account = get_object_or_404(Account.objects.select_related("profile__avatar"), pk=pk)
        summary = account_summary(account)
        restrictions, complaints = summary.pop("restrictions"), summary.pop("complaints")
        return Response({
            "account": PublicAccountSerializer(account).data,
            "summary": summary,
            "restrictions": RestrictionSerializer(restrictions, many=True).data,
            "complaints": ModeratorComplaintShortSerializer(complaints, many=True).data,
        })


class AccountRestrictView(APIView):
    permission_classes = [IsModerator]

    @extend_schema(request=RestrictSerializer, responses={201: RestrictionSerializer})
    def post(self, request, pk):
        body = RestrictSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        restriction = decisions.restrict_account(pk, request.user, request=request, **body.validated_data)
        return Response(RestrictionSerializer(restriction).data, status=status.HTTP_201_CREATED)


@extend_schema(parameters=[
    OpenApiParameter("object_type", str, description="Например spots.spot, trust.review"),
    OpenApiParameter("object_id", str),
    OpenApiParameter("actor", OpenApiTypes.UUID),
    OpenApiParameter("action", str, description="Точное имя действия, например spot.change_approved"),
    OpenApiParameter("action_prefix", str, description="Префикс действия, например spot."),
    OpenApiParameter("from", OpenApiTypes.DATETIME),
    OpenApiParameter("to", OpenApiTypes.DATETIME),
])
class AuditListView(generics.ListAPIView):
    permission_classes = [IsModerator]
    serializer_class = AuditEventSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        params = self.request.query_params
        qs = AuditEvent.objects.select_related("actor__profile__avatar").order_by("-created_at")
        for name in ("object_type", "object_id", "action"):
            if params.get(name):
                qs = qs.filter(**{name: params[name]})
        if params.get("action_prefix"):
            qs = qs.filter(action__startswith=params["action_prefix"])
        actor = _uuid_param(self.request, "actor")
        if actor:
            qs = qs.filter(actor_id=actor)
        for name, lookup in (("from", "created_at__gte"), ("to", "created_at__lte")):
            if params.get(name):
                value = parse_datetime(params[name])
                if value is None:
                    raise DomainError("validation_error", "Неверная дата.", fields={name: ["Формат ISO 8601."]})
                qs = qs.filter(**{lookup: value})
        return qs


class ModerationStatsView(APIView):
    permission_classes = [IsModerator]

    @extend_schema(
        parameters=[OpenApiParameter("days", int, description="Период для скорости модерации (по умолчанию 30)")],
        responses=inline_serializer("ModerationStats", {
            "generated_at": serializers.DateTimeField(),
            "open_cases": serializers.DictField(),
            "overdue_cases": serializers.DictField(),
            "oldest_open_case_hours": serializers.FloatField(allow_null=True),
            "spot_proposals": serializers.DictField(),
            "resolved_last_period": serializers.IntegerField(),
        }),
    )
    def get(self, request):
        try:
            days = max(1, min(365, int(request.query_params.get("days", 30))))
        except ValueError:
            raise DomainError("validation_error", "days — целое число.", fields={"days": ["Целое число."]})
        return Response(moderation_stats(days=days))

