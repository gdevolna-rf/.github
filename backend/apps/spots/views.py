"""Публичный API спотов (BR-01) и предложения правок (SPT-07/08). Тонкие представления: права → сервис → сериализатор."""
from django.db.models import Prefetch, Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import generics, serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import DomainError, NotFound
from apps.learning.models import InstructorProfile
from apps.organizations.models import Organization
from apps.spots import choices
from apps.spots.models import Spot, SpotChangeRequest
from apps.spots.serializers import (
    DictionariesSerializer,
    ForecastResponseSerializer,
    MapMarkerSerializer,
    ProposalCreateSerializer,
    ProposalSerializer,
    ProposalUpdateSerializer,
    RegionSerializer,
    SpotDetailSerializer,
    SpotListSerializer,
)
from apps.spots.services import proposals as proposal_service
from apps.spots.services.catalog import get_public_spot, map_markers, public_spots, regions_with_counts
from apps.spots.services.forecasts import current_forecast

_MULTI = "Можно несколько значений через запятую."


def _multi(request, name, allowed=None):
    raw = request.query_params.get(name, "")
    values = [v.strip() for v in raw.split(",") if v.strip()]
    if allowed is not None:
        unknown = [v for v in values if v not in allowed]
        if unknown:
            raise DomainError("validation_error", "Неизвестное значение фильтра.",
                              fields={name: [f"Неизвестные значения: {', '.join(unknown)}."]})
    return values


class RegionListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    pagination_class = None
    serializer_class = RegionSerializer

    def get_queryset(self):
        return regions_with_counts()


@extend_schema(parameters=[
    OpenApiParameter("region", str, description=f"slug региона. {_MULTI}"),
    OpenApiParameter("difficulty", str, description=f"beginner|intermediate|advanced|expert. {_MULTI}"),
    OpenApiParameter("bottom", str, description=f"Тип дна. {_MULTI}"),
    OpenApiParameter("break", str, description=f"Тип брейка. {_MULTI}"),
    OpenApiParameter("q", str, description="Поиск по названию, описанию, региону"),
    OpenApiParameter("sort", str, enum=["name", "rating"], description="Порядок (по умолчанию — регион и название)"),
])
class SpotListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = SpotListSerializer

    def get_queryset(self):
        request = self.request
        qs = public_spots().select_related("region", "cover").prefetch_related("photos__media")
        regions = _multi(request, "region")
        if regions:
            qs = qs.filter(region__slug__in=regions)
        difficulty = _multi(request, "difficulty", Spot.Difficulty.values)
        if difficulty:
            qs = qs.filter(difficulty__in=difficulty)
        bottom = _multi(request, "bottom", Spot.Bottom.values)
        if bottom:
            qs = qs.filter(bottom_type__in=bottom)
        brk = _multi(request, "break", Spot.Break.values)
        if brk:
            qs = qs.filter(break_type__in=brk)
        q = request.query_params.get("q", "").strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(short_description__icontains=q) | Q(description__icontains=q)
                           | Q(region__name__icontains=q))
        sort = request.query_params.get("sort", "")
        if sort == "rating":
            qs = qs.order_by("-rating_avg", "-rating_count", "name")
        elif sort == "name":
            qs = qs.order_by("name")
        return qs


class SpotMapView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        parameters=[OpenApiParameter("region", str, description=f"slug региона. {_MULTI}")],
        responses=inline_serializer("SpotMapResponse", {
            "count": serializers.IntegerField(), "markers": MapMarkerSerializer(many=True),
        }),
    )
    def get(self, request):
        markers = map_markers()
        regions = set(_multi(request, "region"))
        if regions:
            markers = [m for m in markers if m["region_slug"] in regions]
        return Response({"count": len(markers), "markers": markers})


class SpotDictionariesView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses=DictionariesSerializer)
    def get(self, request):
        return Response(choices.dictionaries())


class SpotDetailView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = SpotDetailSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return public_spots().select_related("region", "cover").prefetch_related(
            "photos__media", "photos__author__profile__avatar", "sources",
            Prefetch("organizations", queryset=Organization.objects.filter(status=Organization.Status.PUBLISHED)
                     .select_related("logo").order_by("name")),
            Prefetch("instructors", queryset=InstructorProfile.objects.filter(status=InstructorProfile.Status.PUBLISHED)
                     .select_related("account__profile__avatar").prefetch_related("certificates")
                     .order_by("-rating_avg", "created_at")),
        )

    def get_object(self):
        return get_public_spot(slug=self.kwargs["slug"], queryset=self.get_queryset())


class SpotForecastView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses=ForecastResponseSerializer)
    def get(self, request, slug):
        spot = get_public_spot(slug=slug)
        return Response(ForecastResponseSerializer(current_forecast(spot)).data)


class SpotProposalCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=ProposalCreateSerializer, responses={201: ProposalSerializer})
    def post(self, request, pk):
        spot = get_public_spot(pk=pk)
        body = ProposalCreateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        proposal = proposal_service.create_proposal(spot, request.user, request=request, **body.validated_data)
        return Response(ProposalSerializer(proposal, context={"request": request}).data, status=status.HTTP_201_CREATED)


def _own_proposals(user):
    return SpotChangeRequest.objects.filter(author=user).select_related("spot").prefetch_related("evidence")


@extend_schema(parameters=[
    OpenApiParameter("status", str, description="submitted|needs_info|approved|rejected|withdrawn (через запятую)"),
    OpenApiParameter("spot", OpenApiTypes.UUID, description="id спота"),
])
class MyProposalListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProposalSerializer

    def get_queryset(self):
        qs = _own_proposals(self.request.user).order_by("-created_at")
        statuses = _multi(self.request, "status", SpotChangeRequest.Status.values)
        if statuses:
            qs = qs.filter(status__in=statuses)
        spot = self.request.query_params.get("spot")
        if spot:
            try:
                qs = qs.filter(spot_id=serializers.UUIDField().to_internal_value(spot))
            except serializers.ValidationError:
                raise DomainError("validation_error", "Неверный идентификатор спота.", fields={"spot": ["Неверный UUID."]})
        return qs


class ProposalDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, request, pk):
        proposal = _own_proposals(request.user).filter(pk=pk).first()
        if proposal is None:
            raise NotFound("Предложение не найдено.")
        return proposal

    @extend_schema(responses=ProposalSerializer)
    def get(self, request, pk):
        return Response(ProposalSerializer(self._get(request, pk), context={"request": request}).data)

    @extend_schema(request=ProposalUpdateSerializer, responses=ProposalSerializer)
    def patch(self, request, pk):
        body = ProposalUpdateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        proposal_service.update_proposal(pk, request.user, request=request, **body.validated_data)
        return Response(ProposalSerializer(self._get(request, pk), context={"request": request}).data)


class ProposalWithdrawView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses=ProposalSerializer)
    def post(self, request, pk):
        proposal_service.withdraw_proposal(pk, request.user, request=request)
        proposal = _own_proposals(request.user).get(pk=pk)
        return Response(ProposalSerializer(proposal, context={"request": request}).data)
