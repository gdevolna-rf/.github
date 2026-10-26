"""Аналитика: квалифицированные просмотры и метрики дашбордов (раздел 10, MET-01…08)."""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics import serializers as s
from apps.analytics.services.metrics import compute
from apps.analytics.services.periods import resolve_period
from apps.analytics.services.views import COOKIE_MAX_AGE, COOKIE_NAME, record_view


class ViewsView(APIView):
    """Квалифицированный просмотр публичной карточки. Боты, самопросмотры, сотрудники владельца и повторы зрителя
    за сутки не учитываются; анонимному зрителю выдаётся cookie gv_aid."""

    permission_classes = [AllowAny]

    @extend_schema(tags=["analytics"], request=s.AnalyticsViewInputSerializer, responses={200: s.AnalyticsViewResultSerializer})
    def post(self, request):
        serializer = s.AnalyticsViewInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        subject, event, aid, is_new = record_view(request, data["subject_type"], data["subject_id"])
        response = Response({"counted": event is not None, "event": subject.event,
                             "subject_type": subject.subject_type, "subject_id": subject.subject_id})
        if is_new:
            response.set_cookie(COOKIE_NAME, aid, max_age=COOKIE_MAX_AGE, httponly=True, samesite="Lax",
                                secure=request.is_secure())
        return response


class MetricsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["analytics"], parameters=[
        OpenApiParameter("scope", OpenApiTypes.STR, required=True, enum=["shaper", "instructor", "school", "rental", "surfer"]),
        OpenApiParameter("organization_id", OpenApiTypes.UUID, description="Мастерская/школа/прокат (owner/manager/staff)"),
        OpenApiParameter("from", OpenApiTypes.STR, description="YYYY-MM-DD (по умолчанию — 30 дней по сегодня)"),
        OpenApiParameter("to", OpenApiTypes.STR, description="YYYY-MM-DD включительно"),
        OpenApiParameter("tz", OpenApiTypes.STR, description="IANA-часовой пояс периода (Europe/Moscow)"),
    ], responses={200: s.MetricsResponseSerializer}, description=(
        "Метрики дашборда по формулам ТЗ 10.1 (MET-01…07). Разбивки: shaper — interest_by_board_type, "
        "views_by_subject, inquiries_by_status, revenue_by_currency; instructor — by_organization, "
        "cancellations_by_side; school — instructors, programs, cancellations_by_side; rental — by_kind, "
        "top_items, revenue_by_currency; surfer — spots, by_month."))
    def get(self, request):
        query = s.MetricsQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        period = resolve_period(request.query_params, past_days=30, max_days=366)
        data = compute(request.user, query.validated_data["scope"], period,
                       organization_id=query.validated_data.get("organization_id"))
        return Response(data)
