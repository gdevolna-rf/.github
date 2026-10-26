from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.search.serializers import (
    BoardSizeInputSerializer,
    BoardSizeResponseSerializer,
    RecommendInputSerializer,
    RecommendResponseSerializer,
    SearchResponseSerializer,
)
from apps.search.services import assistant
from apps.search.services.search import search


class SearchView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        parameters=[
            OpenApiParameter("q", OpenApiTypes.STR, required=True, description="Не короче 2 символов"),
            OpenApiParameter("types", OpenApiTypes.STR,
                             description="Через запятую: spots,instructors,schools,shapers,boards,equipment,surfers"),
            OpenApiParameter("limit", OpenApiTypes.INT, description="Результатов в группе (1–20, по умолчанию 5)"),
        ],
        responses=SearchResponseSerializer, summary="Глобальный поиск (NAV-04)", tags=["search"],
    )
    def get(self, request):
        return Response(search(request.query_params, request.user))


class BoardSizeView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=BoardSizeInputSerializer, responses=BoardSizeResponseSerializer,
                   summary="Подбор объёма доски по гильд-фактору (AIX-03)", tags=["assistant"])
    def post(self, request):
        data = BoardSizeInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(assistant.board_size(**data.validated_data))


class RecommendView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=RecommendInputSerializer, responses=RecommendResponseSerializer,
                   summary="Споты, инструкторы и прокат под уровень (AIX-01/02, только данные каталога)",
                   tags=["assistant"])
    def post(self, request):
        data = RecommendInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        return Response(assistant.recommend(values["region"], values["level"], values.get("date")))
