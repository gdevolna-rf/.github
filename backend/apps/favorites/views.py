from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.favorites.serializers import FavoriteIdsSerializer, FavoriteInputSerializer, FavoriteSerializer
from apps.favorites.services import favorites as service


class FavoriteCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=FavoriteInputSerializer,
        responses={201: FavoriteSerializer, 200: FavoriteSerializer},
        summary="Добавить в избранное (идемпотентно; только опубликованные объекты)",
        tags=["favorites"],
    )
    def post(self, request):
        data = FavoriteInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        favorite, created = service.add_favorite(request.user, data.validated_data["target_type"],
                                                 data.validated_data["target_id"])
        favorite = service.favorites_for(request.user).get(pk=favorite.pk)
        return Response(service.favorite_data(favorite), status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class FavoriteDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={204: None},
        summary="Убрать из избранного (идемпотентно)",
        parameters=[OpenApiParameter("target_type", OpenApiTypes.STR, OpenApiParameter.PATH),
                    OpenApiParameter("target_id", OpenApiTypes.UUID, OpenApiParameter.PATH)],
        tags=["favorites"],
    )
    def delete(self, request, target_type, target_id):
        service.remove_favorite(request.user, target_type, target_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyFavoritesView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FavoriteSerializer

    def get_queryset(self):
        type_filter = service.parse_type_filter(self.request.query_params.get("type"))
        return service.favorites_for(self.request.user, type_filter)

    @extend_schema(
        parameters=[OpenApiParameter(
            "type", OpenApiTypes.STR, description="spot | instructor | organization | school | shaper | rental | "
                                                  "board_model | inventory_item")],
        summary="Моё избранное — типизированные карточки",
        tags=["favorites"],
    )
    def get(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        return self.get_paginated_response([service.favorite_data(f) for f in page])


class MyFavoriteIdsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=FavoriteIdsSerializer, summary="id объектов в избранном по типам", tags=["favorites"])
    def get(self, request):
        return Response(service.favorite_ids(request.user))
