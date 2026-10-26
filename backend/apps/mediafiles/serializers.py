from rest_framework import serializers

from apps.mediafiles.models import MediaAsset


class MediaSerializer(serializers.ModelSerializer):
    """Единый формат медиа во всех ответах API. Для закрытых файлов url=None (нужен GET /media/{id}/url)."""

    url = serializers.CharField(read_only=True)
    thumbnail_url = serializers.CharField(read_only=True)
    poster_url = serializers.CharField(read_only=True)

    class Meta:
        model = MediaAsset
        fields = ["id", "kind", "purpose", "visibility", "status", "url", "thumbnail_url", "poster_url",
                  "content_type", "size_bytes", "width", "height", "duration_seconds", "alt_text", "original_filename"]
        read_only_fields = fields


class MediaDetailSerializer(MediaSerializer):
    """GET /media/{id}: + причина отклонения и наличие миниатюры (для опроса статуса после complete)."""

    has_thumbnail = serializers.SerializerMethodField()

    class Meta(MediaSerializer.Meta):
        fields = MediaSerializer.Meta.fields + ["rejection_reason", "has_thumbnail", "created_at", "processed_at"]
        read_only_fields = fields

    def get_has_thumbnail(self, obj) -> bool:
        return bool(obj.thumbnail_key)


class MediaUploadRequestSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=MediaAsset.Kind.choices)
    purpose = serializers.ChoiceField(choices=MediaAsset.Purpose.choices)
    filename = serializers.CharField(max_length=500, allow_blank=True, required=False, default="")
    content_type = serializers.CharField(max_length=100)
    size = serializers.IntegerField(min_value=1)
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    alt_text = serializers.CharField(max_length=300, allow_blank=True, required=False, default="")


class MediaUploadResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    upload_url = serializers.CharField(help_text="Presigned PUT URL (через nginx, origin запроса).")
    method = serializers.CharField(help_text="Всегда PUT.")
    headers = serializers.DictField(
        child=serializers.CharField(),
        help_text="Заголовки, которые браузер обязан передать в PUT: Content-Type и If-None-Match: * (ссылка одноразовая).",
    )
    expires_at = serializers.DateTimeField()
    media = MediaSerializer()


class MediaUrlSerializer(serializers.Serializer):
    url = serializers.CharField()
    expires_at = serializers.DateTimeField(allow_null=True, help_text="null для публичных файлов.")
