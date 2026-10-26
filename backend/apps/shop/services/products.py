"""Витрина мерча без оплаты (24.2, SHOP-01..04, PAY-03, M3).

Товары ведутся в Django Admin. Пользователь может оставить «Сообщить о поступлении» (лист интереса) — при
появлении остатка или переводе товара из «Предзаказа» в продажу ему приходит одно уведомление.
"""
import uuid

from django.db import IntegrityError, transaction
from django.db.models import Max, Min, Prefetch, Q, Sum
from django.utils import timezone

from apps.common.exceptions import DomainError, NotFound
from apps.messaging.models import Notification
from apps.messaging.services.notify import notify
from apps.search.services.catalog import money, public_media
from apps.shop.models import Product, ProductInterest, ProductVariant

PUBLIC_STATUSES = [Product.Status.PREORDER, Product.Status.PUBLISHED]
PURCHASE_NOTE = ("Онлайн-оплата пока не подключена: нажмите «Сообщить о поступлении» — мы напишем, когда товар "
                 "можно будет заказать.")


def _uuid(value):
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


ACTIVE_VARIANT = Q(variants__is_active=True)


def public_products():
    active = ProductVariant.objects.filter(is_active=True)
    return (Product.objects.filter(status__in=PUBLIC_STATUSES)
            .annotate(price_min=Min("variants__price", filter=ACTIVE_VARIANT),
                      price_max=Max("variants__price", filter=ACTIVE_VARIANT),
                      stock_total=Sum("variants__stock", filter=ACTIVE_VARIANT))
            .select_related("cover")
            .prefetch_related(Prefetch("variants", queryset=active, to_attr="active_variants"), "gallery"))


def filter_products(qs, params):
    category = params.get("category")
    if category:
        if category not in Product.Category.values:
            raise DomainError("validation_error", "Неизвестная категория.",
                              fields={"category": [f"Допустимо: {', '.join(Product.Category.values)}."]})
        qs = qs.filter(category=category)
    status = params.get("status")
    if status:
        if status not in PUBLIC_STATUSES:
            raise DomainError("validation_error", "Неизвестный статус.",
                              fields={"status": [f"Допустимо: {', '.join(PUBLIC_STATUSES)}."]})
        qs = qs.filter(status=status)
    return qs.order_by("sort_order", "-created_at")


def _currency(product):
    variants = getattr(product, "active_variants", None) or []
    return variants[0].currency if variants else "RUB"


def product_card(product):
    stock = getattr(product, "stock_total", None) or 0
    return {
        "id": str(product.pk),
        "slug": product.slug,
        "title": product.title,
        "category": product.category,
        "category_label": product.get_category_display(),
        "status": product.status,
        "status_label": product.get_status_display(),
        "cover": public_media(product.cover) if product.cover_id else None,
        "price_from": money(getattr(product, "price_min", None)),
        "price_to": money(getattr(product, "price_max", None)),
        "currency": _currency(product),
        "in_stock": product.status == Product.Status.PUBLISHED and stock > 0,
        "url": f"/shop/{product.slug}",
    }


def variant_data(variant):
    return {
        "id": variant.pk,
        "sku": variant.sku,
        "name": variant.name,
        "price": money(variant.price),
        "currency": variant.currency,
        "stock": variant.stock,
        "in_stock": variant.stock > 0,
    }


def interest_data(interest):
    if interest is None:
        return None
    return {"id": str(interest.pk), "variant_id": interest.variant_id, "created_at": interest.created_at,
            "notified_at": interest.notified_at}


def product_detail(product, viewer):
    data = product_card(product)
    gallery = [m for m in (public_media(a) for a in product.gallery.all()) if m]
    interest = None
    if viewer is not None and viewer.is_authenticated:
        interest = ProductInterest.objects.filter(product=product, account=viewer).first()
    data.update({
        "description": product.description,
        "specs": product.specs,
        "gallery": gallery,
        "variants": [variant_data(v) for v in product.active_variants],
        "delivery_note": product.delivery_note,
        "returns_note": product.returns_note,
        "purchase_available": False,
        "purchase_note": PURCHASE_NOTE,
        "my_interest": interest_data(interest),
    })
    return data


def get_public_product(slug):
    product = public_products().filter(slug=slug).first()
    if product is None:
        raise NotFound("Товар не найден.", code="product_not_found")
    return product


def _public_product_by_id(pk):
    pk = _uuid(pk)
    product = Product.objects.filter(pk=pk, status__in=PUBLIC_STATUSES).first() if pk else None
    if product is None:
        raise NotFound("Товар не найден.", code="product_not_found")
    return product


def add_interest(product_id, account, variant_id=None):
    """Идемпотентно: повтор обновляет выбранный вариант. → (interest, created)."""
    product = _public_product_by_id(product_id)
    variant = None
    if variant_id is not None:
        variant = product.variants.filter(pk=variant_id, is_active=True).first()
        if variant is None:
            raise DomainError("product_variant_invalid", "Вариант не относится к этому товару.",
                              fields={"variant_id": ["Выберите вариант этого товара."]})
    existing = ProductInterest.objects.filter(product=product, account=account).first()
    if existing:
        if variant is not None and existing.variant_id != variant.pk:
            existing.variant = variant
            existing.notified_at = None
            existing.save(update_fields=["variant", "notified_at", "updated_at"])
        return existing, False
    try:
        with transaction.atomic():
            return ProductInterest.objects.create(product=product, account=account, variant=variant), True
    except IntegrityError:
        return ProductInterest.objects.get(product=product, account=account), False


def remove_interest(product_id, account):
    pk = _uuid(product_id)
    if pk is None:
        return 0
    deleted, _ = ProductInterest.objects.filter(product_id=pk, account=account).delete()
    return deleted


def notify_back_in_stock(product, variant=None):
    """Уведомить ожидающих: по варианту (и тех, кто не выбрал вариант) или по всему товару. Один раз на запрос."""
    if product.status != Product.Status.PUBLISHED:
        return 0
    interests = ProductInterest.objects.filter(product=product, notified_at__isnull=True).select_related("account")
    if variant is not None:
        interests = interests.filter(Q(variant=variant) | Q(variant__isnull=True))
    sent = 0
    now = timezone.now()
    for interest in interests:
        with transaction.atomic():
            updated = ProductInterest.objects.filter(pk=interest.pk, notified_at__isnull=True).update(notified_at=now)
            if not updated:
                continue
            name = f"{product.title} — {variant.name}" if variant is not None else product.title
            notify(interest.account, Notification.Kind.PRODUCT_AVAILABLE, "Товар поступил в продажу",
                   body=f"«{name}» снова в наличии.", link=f"/shop/{product.slug}",
                   payload={"product_id": str(product.pk)}, event_id=f"shop_in_stock:{interest.pk}:{now.isoformat()}")
            sent += 1
    return sent

