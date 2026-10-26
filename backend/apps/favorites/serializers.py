from rest_framework import serializers

from apps.favorites.models import Favorite
from apps.mediafiles.serializers import MediaSerializer


class FavoriteCardSerializer(serializers.Serializer):
    """Типовая карточка объекта (избранное, поиск): ссылка — маршрут фронтенда (ARCHITECTURE §9)."""

    title = serializers.CharField()
    subtitle = serializers.CharField(allow_blank=True)
    image = MediaSerializer(allow_null=True)
    url = serializers.CharField()
    extra = serializers.DictField(
        help_text="Зависит от типа: рейтинг, цена (строка-десятичное + currency), регион, тип доски, наличие и т.п."
    )


class FavoriteInputSerializer(serializers.Serializer):
    target_type = serializers.ChoiceField(choices=Favorite.Target.choices)
    target_id = serializers.UUIDField(
        help_text="UUID объекта. Для инструктора — id профиля инструктора (принимается и id аккаунта)."
    )


class FavoriteSerializer(serializers.Serializer):
    target_type = serializers.ChoiceField(choices=Favorite.Target.choices)
    target_id = serializers.UUIDField()
    created_at = serializers.DateTimeField()
    card = FavoriteCardSerializer()


class FavoriteIdsSerializer(serializers.Serializer):
    spot = serializers.ListField(child=serializers.UUIDField())
    instructor = serializers.ListField(child=serializers.UUIDField())
    organization = serializers.ListField(child=serializers.UUIDField())
    board_model = serializers.ListField(child=serializers.UUIDField())
    inventory_item = serializers.ListField(child=serializers.UUIDField())
