from rest_framework import serializers

from apps.mediafiles.serializers import MediaSerializer
from apps.shop.models import Product


class ShopProductCardSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    slug = serializers.CharField()
    title = serializers.CharField()
    category = serializers.ChoiceField(choices=Product.Category.choices)
    category_label = serializers.CharField()
    status = serializers.ChoiceField(choices=Product.Status.choices)
    status_label = serializers.CharField()
    cover = MediaSerializer(allow_null=True)
    price_from = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    price_to = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    currency = serializers.CharField()
    in_stock = serializers.BooleanField()
    url = serializers.CharField()


class ShopProductVariantSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    sku = serializers.CharField()
    name = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()
    stock = serializers.IntegerField()
    in_stock = serializers.BooleanField()


class ShopProductInterestSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    variant_id = serializers.IntegerField(allow_null=True)
    created_at = serializers.DateTimeField()
    notified_at = serializers.DateTimeField(allow_null=True)


class ShopProductDetailSerializer(ShopProductCardSerializer):
    description = serializers.CharField(allow_blank=True)
    specs = serializers.DictField(help_text="Технические параметры (для термоса — объём, удержание температуры, …)")
    gallery = MediaSerializer(many=True)
    variants = ShopProductVariantSerializer(many=True)
    delivery_note = serializers.CharField(allow_blank=True)
    returns_note = serializers.CharField(allow_blank=True)
    purchase_available = serializers.BooleanField(help_text="Всегда false до решения PAY-03")
    purchase_note = serializers.CharField()
    my_interest = ShopProductInterestSerializer(allow_null=True)


class ShopProductInterestInputSerializer(serializers.Serializer):
    variant_id = serializers.IntegerField(required=False, allow_null=True)
