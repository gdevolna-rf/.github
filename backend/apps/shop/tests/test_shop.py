"""Витрина мерча без оплаты (SHOP-01..04, PAY-03): каталог, карточка, «Сообщить о поступлении»."""
from decimal import Decimal

import pytest

from apps.messaging.models import Notification
from apps.shop.models import Product, ProductInterest
from apps.shop.services.products import notify_back_in_stock
from apps.shop.tests.factories import ProductFactory, ProductVariantFactory
from tests.factories import AccountFactory, MediaAssetFactory

pytestmark = pytest.mark.django_db


def test_catalog_shows_only_published_and_preorder(api_client):
    published = ProductFactory(sort_order=1)
    preorder = ProductFactory(status=Product.Status.PREORDER, sort_order=2)
    ProductFactory(status=Product.Status.DRAFT)
    ProductFactory(status=Product.Status.ARCHIVED)
    body = api_client.get("/api/v1/shop/products").json()
    assert [p["slug"] for p in body["results"]] == [published.slug, preorder.slug]
    assert [p["slug"] for p in api_client.get("/api/v1/shop/products", {"status": "preorder"}).json()["results"]] == [
        preorder.slug]
    assert api_client.get("/api/v1/shop/products", {"status": "draft"}).status_code == 400
    assert api_client.get("/api/v1/shop/products", {"category": "boats"}).status_code == 400


def test_card_price_range_and_stock(api_client):
    product = ProductFactory(category=Product.Category.APPAREL)
    ProductVariantFactory(product=product, price=Decimal("2990"), stock=0)
    ProductVariantFactory(product=product, price=Decimal("3490"), stock=2)
    ProductVariantFactory(product=product, price=Decimal("100"), stock=9, is_active=False)
    card = api_client.get("/api/v1/shop/products", {"category": "apparel"}).json()["results"][0]
    assert card["price_from"] == "2990.00"
    assert card["price_to"] == "3490.00"
    assert card["in_stock"] is True
    assert card["url"] == f"/shop/{product.slug}"


def test_preorder_product_is_never_in_stock(api_client):
    product = ProductFactory(status=Product.Status.PREORDER)
    ProductVariantFactory(product=product, stock=10)
    assert api_client.get("/api/v1/shop/products").json()["results"][0]["in_stock"] is False


def test_detail_has_variants_specs_notes_and_no_payment(api_client):
    product = ProductFactory(specs={"volume_ml": 500, "keeps_hot_hours": 12})
    product.gallery.add(MediaAssetFactory(purpose="product_photo"))
    variant = ProductVariantFactory(product=product)
    body = api_client.get(f"/api/v1/shop/products/{product.slug}").json()
    assert body["specs"] == {"volume_ml": 500, "keeps_hot_hours": 12}
    assert body["variants"] == [{"id": variant.pk, "sku": variant.sku, "name": variant.name, "price": "3490.00",
                                 "currency": "RUB", "stock": 5, "in_stock": True}]
    assert body["delivery_note"] and body["returns_note"]
    assert body["purchase_available"] is False
    assert "оплата" in body["purchase_note"].lower()
    assert len(body["gallery"]) == 1
    assert body["my_interest"] is None


def test_draft_product_detail_is_404(api_client):
    product = ProductFactory(status=Product.Status.DRAFT)
    assert api_client.get(f"/api/v1/shop/products/{product.slug}").status_code == 404


def test_interest_is_idempotent_and_shown_in_detail(make_client):
    product = ProductFactory(status=Product.Status.PREORDER)
    variant = ProductVariantFactory(product=product)
    client = make_client()
    url = f"/api/v1/shop/products/{product.pk}/interest"
    first = client.post(url, {}, format="json")
    assert first.status_code == 201
    assert first.json()["variant_id"] is None
    second = client.post(url, {"variant_id": variant.pk}, format="json")
    assert second.status_code == 200
    assert second.json()["variant_id"] == variant.pk
    assert ProductInterest.objects.count() == 1
    detail = client.get(f"/api/v1/shop/products/{product.slug}").json()
    assert detail["my_interest"]["id"] == first.json()["id"]
    assert client.delete(url).status_code == 204
    assert client.delete(url).status_code == 204
    assert not ProductInterest.objects.exists()


def test_interest_rules(make_client, api_client):
    product = ProductFactory()
    foreign_variant = ProductVariantFactory()
    client = make_client()
    url = f"/api/v1/shop/products/{product.pk}/interest"
    assert api_client.post(url, {}, format="json").status_code == 401
    response = client.post(url, {"variant_id": foreign_variant.pk}, format="json")
    assert response.status_code == 400
    assert "variant_id" in response.json()["error"]["fields"]
    draft = ProductFactory(status=Product.Status.DRAFT)
    assert client.post(f"/api/v1/shop/products/{draft.pk}/interest", {}, format="json").status_code == 404
    assert client.post("/api/v1/shop/products/not-a-uuid/interest", {}, format="json").status_code == 404


def test_back_in_stock_notifies_each_interest_once():
    product = ProductFactory()
    blue = ProductVariantFactory(product=product, name="синий")
    red = ProductVariantFactory(product=product, name="красный")
    wants_blue = ProductInterest.objects.create(product=product, account=AccountFactory(), variant=blue)
    wants_any = ProductInterest.objects.create(product=product, account=AccountFactory())
    wants_red = ProductInterest.objects.create(product=product, account=AccountFactory(), variant=red)
    assert notify_back_in_stock(product, blue) == 2
    assert set(Notification.objects.values_list("recipient_id", flat=True)) == {wants_blue.account_id,
                                                                                 wants_any.account_id}
    assert notify_back_in_stock(product, blue) == 0
    assert notify_back_in_stock(product) == 1  # оставшийся — wants_red
    assert Notification.objects.filter(recipient=wants_red.account, link=f"/shop/{product.slug}").exists()


def test_back_in_stock_not_sent_for_preorder():
    product = ProductFactory(status=Product.Status.PREORDER)
    ProductInterest.objects.create(product=product, account=AccountFactory())
    assert notify_back_in_stock(product) == 0


@pytest.fixture
def superuser_client(make_client):
    return make_client(AccountFactory(is_staff=True, is_superuser=True), two_factor=True)


def test_admin_publishing_product_notifies_waiting_users(superuser_client, django_capture_on_commit_callbacks):
    product = ProductFactory(status=Product.Status.PREORDER, slug="thermos")
    variant = ProductVariantFactory(product=product, stock=0)
    interest = ProductInterest.objects.create(product=product, account=AccountFactory())
    data = {
        "slug": "thermos", "title": product.title, "category": "thermos", "status": "published", "description": "",
        "specs": "{}", "delivery_note": "", "returns_note": "", "sort_order": "100",
        "variants-TOTAL_FORMS": "1", "variants-INITIAL_FORMS": "1", "variants-MIN_NUM_FORMS": "0",
        "variants-MAX_NUM_FORMS": "1000", "variants-0-id": str(variant.pk), "variants-0-product": str(product.pk),
        "variants-0-sku": variant.sku, "variants-0-name": variant.name, "variants-0-price": "3490",
        "variants-0-currency": "RUB", "variants-0-stock": "4", "variants-0-is_active": "on",
        "variants-0-sort_order": "100",
    }
    with django_capture_on_commit_callbacks(execute=True):
        response = superuser_client.post(f"/admin/shop/product/{product.pk}/change/", data, format="multipart")
    assert response.status_code == 302
    interest.refresh_from_db()
    assert interest.notified_at is not None
    assert Notification.objects.filter(recipient=interest.account).count() == 1


def test_admin_pages_load(superuser_client):
    product = ProductFactory()
    ProductInterest.objects.create(product=product, account=AccountFactory())
    for url in ("/admin/shop/product/", f"/admin/shop/product/{product.pk}/change/", "/admin/shop/productinterest/"):
        assert superuser_client.get(url).status_code == 200, url
