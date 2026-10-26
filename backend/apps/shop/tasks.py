from celery import shared_task

from apps.shop.models import Product, ProductVariant
from apps.shop.services.products import notify_back_in_stock as _notify


@shared_task(name="shop.notify_back_in_stock")
def notify_back_in_stock(product_id, variant_id=None):
    """Ставится из Django Admin после появления остатка или перевода товара в продажу."""
    product = Product.objects.filter(pk=product_id).first()
    if product is None:
        return 0
    variant = ProductVariant.objects.filter(pk=variant_id, product=product).first() if variant_id else None
    return _notify(product, variant)
