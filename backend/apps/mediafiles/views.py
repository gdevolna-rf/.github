from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import NotFound
from apps.common.s3 import request_origin
from apps.mediafiles.serializers import (
    MediaDetailSerializer,
    MediaUrlSerializer,
    MediaUploadRequestSerializer,
    MediaUploadResponseSerializer,
)
from apps.mediafiles.services import access, uploads


class UploadCreateView(APIView):
    """Шаг 1: заявка на загрузку → presigned PUT (15 мин, одноразовая)."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "uploads"

    @extend_schema(request=MediaUploadRequestSerializer, responses={201: MediaUploadResponseSerializer}, tags=["media"],
                   summary="Создать загрузку (presigned PUT)")
    def post(self, request):
        serializer = MediaUploadRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        organization = None
        if data.get("organization_id"):
            from apps.organizations.models import Organization

            organization = Organization.objects.filter(id=data["organization_id"]).first()
            if organization is None:
                raise NotFound("Организация не найдена.")
        asset, url, headers = uploads.create_upload(
            request.user,
            kind=data["kind"],
            purpose=data["purpose"],
            filename=data.get("filename", ""),
            content_type=data["content_type"],
            size=data["size"],
            origin=request_origin(request),
            organization=organization,
            alt_text=data.get("alt_text", ""),
        )
        payload = {
            "id": asset.id,
            "upload_url": url,
            "method": "PUT",
            "headers": headers,
            "expires_at": asset.upload_expires_at,
            "media": asset,
        }
        return Response(MediaUploadResponseSerializer(payload).data, status=status.HTTP_201_CREATED)


class UploadCompleteView(APIView):
    """Шаг 3: файл загружен → проверка HEAD → processing → Celery."""

    permission_classes = [IsAuthenticated]
    throttle_scope = "uploads"

    @extend_schema(request=None, responses={200: MediaDetailSerializer}, tags=["media"],
                   summary="Завершить загрузку")
    def post(self, request, pk):
        asset = uploads.complete_upload(pk, request.user)
        return Response(MediaDetailSerializer(asset).data)


class MediaDetailView(APIView):
    permission_classes = [AllowAny]

    def get_permissions(self):
        if self.request.method == "DELETE":
            return [IsAuthenticated()]
        return super().get_permissions()

    @extend_schema(responses={200: MediaDetailSerializer}, tags=["media"], summary="Медиафайл")
    def get(self, request, pk):
        asset = access.get_accessible(pk, request)
        return Response(MediaDetailSerializer(asset).data)

    @extend_schema(responses={204: None}, tags=["media"], summary="Удалить свой файл")
    def delete(self, request, pk):
        uploads.delete_media(pk, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MediaUrlView(APIView):
    """Ссылка на файл: публичный путь или presigned GET (2 мин) после проверки прав (ATX-23)."""

    permission_classes = [AllowAny]

    @extend_schema(
        parameters=[OpenApiParameter("variant", OpenApiTypes.STR, enum=["original", "thumbnail"], required=False)],
        responses={200: MediaUrlSerializer}, tags=["media"], summary="Ссылка на файл",
    )
    def get(self, request, pk):
        asset = access.get_accessible(pk, request)
        variant = request.query_params.get("variant", "original")
        if variant not in ("original", "thumbnail"):
            variant = "original"
        return Response(MediaUrlSerializer(access.access_url(asset, request, variant)).data)

