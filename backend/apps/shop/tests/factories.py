from decimal import Decimal

import factory

from apps.shop.models import Product, ProductVariant


class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product

    slug = factory.Sequence(lambda n: f"product-{n}")
    title = factory.Sequence(lambda n: f"Термос ГДеволна {n}")
    category = Product.Category.THERMOS
    status = Product.Status.PUBLISHED
    specs = factory.LazyFunction(lambda: {"volume_ml": 500, "keeps_hot_hours": 12})
    delivery_note = "Доставка СДЭК по России"
    returns_note = "Возврат в течение 14 дней"


class ProductVariantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProductVariant

    product = factory.SubFactory(ProductFactory)
    sku = factory.Sequence(lambda n: f"GV-TH-{n:04d}")
    name = "500 мл, синий"
    price = Decimal("3490")
    stock = 5
