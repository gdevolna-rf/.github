"""Товары ведутся только в Django Admin (SHOP-02). Появление остатка / переход в продажу ставит задачу
«Сообщить о поступлении» после коммита."""
from django.contrib import admin
from django.db import transaction

from apps.common.text import unique_slug
from apps.shop.models import Product, ProductInterest, ProductVariant


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ("sku", "name", "price", "currency", "stock", "is_active", "sort_order")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "status", "sort_order", "interests_count", "is_demo", "updated_at")
    list_filter = ("status", "category", "is_demo")
    search_fields = ("title", "slug", "description", "variants__sku")
    raw_id_fields = ("cover", "gallery")
    readonly_fields = ("created_at", "updated_at")
    inlines = [ProductVariantInline]

    @admin.display(description="Ждут поступления")
    def interests_count(self, obj):
        return obj.interests.filter(notified_at__isnull=True).count()

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if "slug" in form.base_fields:
            form.base_fields["slug"].required = False
            form.base_fields["slug"].help_text = "Пусто — сгенерируется из названия латиницей."
        return form

    def save_model(self, request, obj, form, change):
        if not obj.slug:
            obj.slug = unique_slug(Product, obj.title, max_length=80)
        previous = Product.objects.filter(pk=obj.pk).values_list("status", flat=True).first() if change else None
        super().save_model(request, obj, form, change)
        if obj.status == Product.Status.PUBLISHED and previous != Product.Status.PUBLISHED:
            self._enqueue(obj.pk)
        request._shop_stock_before = dict(obj.variants.values_list("pk", "stock"))

    def save_formset(self, request, form, formset, change):
        before = getattr(request, "_shop_stock_before", {})
        super().save_formset(request, form, formset, change)
        if formset.model is not ProductVariant:
            return
        product = form.instance
        if product.status != Product.Status.PUBLISHED:
            return
        for variant in product.variants.filter(is_active=True, stock__gt=0):
            if before.get(variant.pk, 0) == 0:
                self._enqueue(product.pk, variant.pk)

    @staticmethod
    def _enqueue(product_id, variant_id=None):
        from apps.shop.tasks import notify_back_in_stock

        transaction.on_commit(lambda: notify_back_in_stock.delay(str(product_id), variant_id))


@admin.register(ProductInterest)
class ProductInterestAdmin(admin.ModelAdmin):
    list_display = ("product", "variant", "account", "created_at", "notified_at")
    list_filter = ("notified_at",)
    search_fields = ("product__title", "account__email")
    raw_id_fields = ("product", "variant", "account")
    readonly_fields = ("created_at", "updated_at", "notified_at")
