"""Мерч и термосы — витрина без оплаты до утверждения платёжной модели (24.2, PAY-03, M3)."""
from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


class Product(TimeStampedModel):
    class Category(models.TextChoices):
        THERMOS = "thermos", "Термосы"
        APPAREL = "apparel", "Одежда"
        ACCESSORY = "accessory", "Аксессуары"

    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        PREORDER = "preorder", "Предзаказ / скоро"
        PUBLISHED = "published", "В продаже"
        ARCHIVED = "archived", "В архиве"

    slug = models.SlugField(max_length=80, unique=True)
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=16, choices=Category.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    description = models.TextField(blank=True)
    specs = models.JSONField(default=dict, blank=True)  # для термоса: объём, удержание температуры, материал
    cover = models.ForeignKey("mediafiles.MediaAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    gallery = models.ManyToManyField("mediafiles.MediaAsset", blank=True, related_name="+")
    delivery_note = models.CharField(max_length=300, blank=True)
    returns_note = models.CharField(max_length=300, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=100)
    is_demo = models.BooleanField(default=False)

    class Meta:
        ordering = ["sort_order", "-created_at"]
        verbose_name = "товар"
        verbose_name_plural = "товары"

    def __str__(self):
        return self.title


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    sku = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="RUB")
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ["sort_order", "price", "id"]
        verbose_name = "вариант товара"
        verbose_name_plural = "варианты товара"

    def __str__(self):
        return f"{self.sku} · {self.name}"


class ProductInterest(TimeStampedModel):
    """«Сообщить о поступлении» — лист интереса вместо оплаты."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="interests")
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    variant = models.ForeignKey(ProductVariant, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    notified_at = models.DateTimeField("сообщено о поступлении", null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["product", "account"], name="uniq_product_interest")]
        verbose_name = "запрос «Сообщить о поступлении»"
        verbose_name_plural = "запросы «Сообщить о поступлении»"
