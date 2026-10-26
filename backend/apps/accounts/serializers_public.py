"""Публичное представление аккаунта (автор отзыва, собеседник, участник команды). Без закрытых полей."""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.mediafiles.serializers import MediaSerializer


class PublicAccountSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    handle = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    is_deleted = serializers.SerializerMethodField()

    def _profile(self, account):
        return getattr(account, "profile", None)

    def get_handle(self, account) -> str | None:
        profile = self._profile(account)
        return profile.handle if profile and not account.anonymized_at else None

    def get_display_name(self, account) -> str:
        if account.anonymized_at:
            return "Удалённый пользователь"
        profile = self._profile(account)
        return profile.display_name if profile else "Пользователь"

    @extend_schema_field(MediaSerializer(allow_null=True))
    @extend_schema_field(MediaSerializer(allow_null=True))
    def get_avatar(self, account):
        profile = self._profile(account)
        if account.anonymized_at or not profile or not profile.avatar_id:
            return None
        return MediaSerializer(profile.avatar).data

    def get_is_deleted(self, account) -> bool:
        return account.anonymized_at is not None
