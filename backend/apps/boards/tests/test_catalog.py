"""Публичный каталог: «Все доски», «По шейперам», карточка модели (SHP-07/08/09, NAV-02, ATX-02, AT-01)."""
from decimal import Decimal

import pytest

from apps.boards.models import BoardMedia, BoardModel, BoardType, BoardVariant, Material
from apps.inventory.models import InventoryItem
from apps.organizations.models import Organization
from tests.factories import AccountFactory, InventoryItemFactory, RegionFactory, add_member

from .helpers import photo, published_model, std_type, unpublish, variant, video, workshop_for

pytestmark = pytest.mark.django_db


def ids(response):
    return {item["id"] for item in response.json()["results"]}


def test_guest_sees_all_boards_without_any_specialty(api_client):
    """ATX-02 / NAV-02: каталог открыт гостю, без предложения стать шейпером."""
    model = published_model(workshop_for())
    response = api_client.get("/api/v1/boards")
    assert response.status_code == 200
    assert ids(response) == {str(model.pk)}


def test_plain_surfer_sees_catalog(make_client):
    model = published_model(workshop_for())
    response = make_client().get("/api/v1/boards")
    assert response.status_code == 200 and str(model.pk) in ids(response)


def test_catalog_hides_drafts_unpublished_workshops_and_models_without_active_variants(api_client):
    workshop = workshop_for()
    visible = published_model(workshop)
    draft = published_model(workshop, name="Черновик")
    BoardModel.objects.filter(pk=draft.pk).update(status=BoardModel.Status.DRAFT)
    no_variants = published_model(workshop, name="Без вариантов")
    BoardVariant.objects.filter(model=no_variants).update(is_active=False)
    hidden_workshop = workshop_for()
    in_hidden = published_model(hidden_workshop, name="Скрытая мастерская")
    unpublish(hidden_workshop)
    response = api_client.get("/api/v1/boards")
    assert ids(response) == {str(visible.pk)}
    for model in (draft, no_variants, in_hidden):
        assert api_client.get(f"/api/v1/boards/{model.pk}").status_code == 404


def test_board_card_shape(api_client):
    workshop = workshop_for(name="Kamchatka Boards")
    model = published_model(workshop, board_type=std_type("fish"), variants=[
        {"length_in": Decimal("70"), "width_in": Decimal("20.5"), "volume_l": Decimal("35"), "price": Decimal("60000")},
        {"length_in": Decimal("72"), "width_in": Decimal("21"), "volume_l": Decimal("38.5"), "price": Decimal("65000")},
    ])
    model.video = video(workshop.owner)
    model.save()
    card = api_client.get("/api/v1/boards").json()["results"][0]
    assert card["id"] == str(model.pk)
    assert card["board_type"] == {"id": std_type("fish").pk, "code": "fish", "name": "Fish / Фиш", "silhouette": "fish"}
    assert card["shaper"]["slug"] == workshop.slug and card["shaper"]["name"] == "Kamchatka Boards"
    assert set(card["shaper"]) >= {"logo", "region", "does_repair", "rating_avg", "rating_count"}
    assert card["cover"]["url"].startswith("/")
    assert card["photos_count"] == 1 and card["has_video"] is True
    assert card["price_from"] == "60000.00" and card["currency"] == "RUB"
    assert card["length_range_display"] == "5'10\" – 6'0\""
    assert card["volume_range_display"] == "35–38,5 л"
    assert card["variants_count"] == 2
    assert card["availability"] == "made_to_order"
    assert card["primary_variant"]["dimensions_display"].startswith("5'10\" × 20 1/2\"")
    assert card["is_own"] is False


def test_is_own_flag_for_workshop_members(make_client):
    workshop = workshop_for()
    published_model(workshop)
    staff = AccountFactory()
    add_member(workshop, staff, role="staff")
    for account in (workshop.owner, staff):
        card = make_client(account).get("/api/v1/boards").json()["results"][0]
        assert card["is_own"] is True
    assert make_client().get("/api/v1/boards").json()["results"][0]["is_own"] is False


def test_filters_by_type_region_shaper_and_repair(api_client):
    north = RegionFactory(slug="kamchatka")
    south = RegionFactory(slug="krasnodar")
    a = workshop_for(region=north)
    a.workshop.does_repair = True
    a.workshop.save()
    b = workshop_for(region=south)
    fish = published_model(a, board_type=std_type("fish"))
    gun = published_model(b, name="Big Gun", board_type=std_type("gun"))
    assert ids(api_client.get("/api/v1/boards?type=fish")) == {str(fish.pk)}
    assert ids(api_client.get("/api/v1/boards?type=fish,gun")) == {str(fish.pk), str(gun.pk)}
    assert ids(api_client.get("/api/v1/boards?region=krasnodar")) == {str(gun.pk)}
    assert ids(api_client.get(f"/api/v1/boards?region={north.pk}")) == {str(fish.pk)}
    assert ids(api_client.get(f"/api/v1/boards?shaper={b.slug}")) == {str(gun.pk)}
    assert ids(api_client.get("/api/v1/boards?repair=true")) == {str(fish.pk)}


def test_size_price_and_volume_filters_apply_to_the_same_variant(api_client):
    workshop = workshop_for()
    model = published_model(workshop, variants=[
        {"length_in": Decimal("70"), "volume_l": Decimal("30"), "price": Decimal("90000")},
        {"length_in": Decimal("84"), "volume_l": Decimal("50"), "price": Decimal("50000")},
    ])
    assert ids(api_client.get("/api/v1/boards?length_min=5'8&length_max=6'0")) == {str(model.pk)}
    assert ids(api_client.get("/api/v1/boards?length_min=86")) == set()
    assert ids(api_client.get("/api/v1/boards?volume_min=45&price_max=60000")) == {str(model.pk)}
    # короткий вариант дорогой — комбинация с ценой не совпадает ни с одним вариантом
    assert ids(api_client.get("/api/v1/boards?length_max=72&price_max=60000")) == set()


def test_availability_and_material_filters(api_client):
    workshop = workshop_for()
    epoxy = Material.objects.get(workshop=None, name="EPS / эпоксид")
    stocked = published_model(workshop, name="В наличии", variants=[{"material": epoxy}])
    InventoryItemFactory(owner_account=None, owner_organization=workshop, variant=stocked.variants.get(),
                         purpose=InventoryItem.Purpose.SALE)
    to_order = published_model(workshop, name="Под заказ", variants=[{"made_to_order_days": 30}])
    none = published_model(workshop, name="Нет", variants=[{"made_to_order_days": None}])
    BoardVariant.objects.filter(model=none).update(availability=BoardVariant.Availability.OUT_OF_STOCK)
    BoardVariant.objects.filter(model=to_order).update(availability=BoardVariant.Availability.MADE_TO_ORDER)
    assert ids(api_client.get("/api/v1/boards?availability=in_stock")) == {str(stocked.pk)}
    assert ids(api_client.get("/api/v1/boards?availability=made_to_order")) == {str(to_order.pk)}
    assert ids(api_client.get("/api/v1/boards?availability=out_of_stock")) == {str(none.pk)}
    assert ids(api_client.get(f"/api/v1/boards?material={epoxy.pk}")) == {str(stocked.pk)}
    assert ids(api_client.get("/api/v1/boards", {"material": "eps / эпоксид"})) == {str(stocked.pk)}
    assert api_client.get("/api/v1/boards?availability=soon").status_code == 400
    card = next(c for c in api_client.get("/api/v1/boards").json()["results"] if c["id"] == str(stocked.pk))
    assert card["availability"] == "in_stock" and card["availability_label"] == "В наличии"


def test_search_by_model_workshop_and_sku(api_client):
    workshop = workshop_for(name="Volna Craft")
    model = published_model(workshop, name="Pacific Fish")
    other = published_model(workshop_for(), name="Другая")
    sku = model.variants.get().sku
    assert ids(api_client.get("/api/v1/boards?q=pacific")) == {str(model.pk)}
    assert ids(api_client.get("/api/v1/boards?q=volna")) == {str(model.pk)}
    assert ids(api_client.get(f"/api/v1/boards?q={sku}")) == {str(model.pk)}
    assert str(other.pk) not in ids(api_client.get("/api/v1/boards?q=pacific"))


def test_ordering_by_price(api_client):
    workshop = workshop_for()
    cheap = published_model(workshop, name="A", variants=[{"price": Decimal("10000")}])
    pricey = published_model(workshop, name="B", variants=[{"price": Decimal("90000")}])
    results = api_client.get("/api/v1/boards?ordering=price").json()["results"]
    assert [r["id"] for r in results] == [str(cheap.pk), str(pricey.pk)]
    results = api_client.get("/api/v1/boards?ordering=-price").json()["results"]
    assert [r["id"] for r in results] == [str(pricey.pk), str(cheap.pk)]


def test_invalid_size_filter_is_400(api_client):
    response = api_client.get("/api/v1/boards?length_min=очень длинная")
    assert response.status_code == 400
    assert response.json()["error"]["fields"]["length_min"]


def test_board_detail_with_variants_media_and_video(make_client, api_client):
    workshop = workshop_for()
    model = published_model(workshop, with_cover=False, variants=[
        {"length_in": Decimal("70"), "width_in": Decimal("20.5"), "thickness_in": Decimal("2.625"),
         "fin_system": "futures"},
    ])
    v = model.variants.get()
    second = BoardMedia.objects.create(model=model, media=photo(workshop.owner), position=0)
    cover = BoardMedia.objects.create(model=model, media=photo(workshop.owner), position=1, is_cover=True)
    BoardMedia.objects.create(model=model, variant=v, media=photo(workshop.owner), position=0, is_cover=True)
    inactive = variant(model, length_in=Decimal("80"), is_active=False)
    model.video = video(workshop.owner)
    model.save()
    InventoryItemFactory(owner_account=None, owner_organization=workshop, variant=v, purpose=InventoryItem.Purpose.SALE)

    data = api_client.get(f"/api/v1/boards/{model.pk}").json()
    assert [p["id"] for p in data["photos"]] == [cover.pk, second.pk]  # обложка первой
    assert data["video"]["kind"] == "video"
    assert [x["id"] for x in data["variants"]] == [str(v.pk)]
    assert str(inactive.pk) not in {x["id"] for x in data["variants"]}
    row = data["variants"][0]
    assert row["dimensions_display"] == "5'10\" × 20 1/2\" × 2 5/8\""
    assert row["length_display"] == "5'10\"" and row["width_display"] == '20 1/2"'
    assert row["fin_system_label"] == "Futures"
    assert row["items_available_for_sale"] == 1 and row["availability"] == "in_stock"
    assert len(row["photos"]) == 1 and row["photos"][0]["is_cover"] is True
    assert data["shaper"]["slug"] == workshop.slug and "lead_time" in data["shaper"]
    assert data["is_own"] is False
    assert make_client(workshop.owner).get(f"/api/v1/boards/{model.pk}").json()["is_own"] is True


def test_shapers_tab_lists_published_workshops_with_up_to_8_models(api_client):
    workshop = workshop_for(name="Volna Craft")
    workshop.workshop.specialization = "Фиши и лонгборды"
    workshop.workshop.lead_time = "2–4 недели"
    workshop.workshop.services = ["Индивидуальные заказы"]
    workshop.workshop.save()
    for n in range(10):
        published_model(workshop, name=f"Модель {n}")
    draft_workshop = workshop_for()
    published_model(draft_workshop)
    unpublish(draft_workshop)
    data = api_client.get("/api/v1/shapers").json()
    assert data["count"] == 1
    card = data["results"][0]
    assert card["slug"] == workshop.slug
    assert card["models_count"] == 10 and len(card["models"]) == 8
    assert card["specialization"] == "Фиши и лонгборды" and card["lead_time"] == "2–4 недели"
    assert card["services"] == ["Индивидуальные заказы"]
    assert card["owner"]["display_name"] and "email" not in card["owner"]
    assert {"cover", "price_from", "board_type"} <= set(card["models"][0])


def test_shapers_filters(api_client):
    region = RegionFactory(slug="primorye")
    repairer = workshop_for(region=region, name="Ремонт и Ко")
    repairer.workshop.does_repair = True
    repairer.workshop.save()
    published_model(repairer, board_type=std_type("gun"))
    other = workshop_for(name="Другие")
    published_model(other)
    slugs = lambda r: {x["slug"] for x in r.json()["results"]}  # noqa: E731
    assert slugs(api_client.get("/api/v1/shapers?repair=true")) == {repairer.slug}
    assert slugs(api_client.get("/api/v1/shapers?region=primorye")) == {repairer.slug}
    assert slugs(api_client.get("/api/v1/shapers?type=gun")) == {repairer.slug}
    assert slugs(api_client.get("/api/v1/shapers?q=ремонт")) == {repairer.slug}


def test_shaper_profile_with_promo_video_custom_types_and_models(api_client):
    workshop = workshop_for()
    workshop.workshop.promo_video = video(workshop.owner, purpose="promo_video")
    workshop.workshop.does_repair = True
    workshop.workshop.save()
    BoardType.objects.create(workshop=workshop, code="mini-malibu", name="Мини-малибу", sku_code="X123")
    model = published_model(workshop)
    data = api_client.get(f"/api/v1/shapers/{workshop.slug}").json()
    assert data["promo_video"]["kind"] == "video"
    assert data["does_repair"] is True
    assert [t["name"] for t in data["board_types"]] == ["Мини-малибу"]
    assert [m["id"] for m in data["models"]] == [str(model.pk)]
    assert "phone" not in data and "email" not in data
    assert data["is_own"] is False


def test_shaper_profile_and_boards_404_for_unpublished_workshop(api_client):
    workshop = workshop_for()
    published_model(workshop)
    Organization.objects.filter(pk=workshop.pk).update(status=Organization.Status.SUSPENDED)
    assert api_client.get(f"/api/v1/shapers/{workshop.slug}").status_code == 404
    assert api_client.get(f"/api/v1/shapers/{workshop.slug}/boards").status_code == 404


def test_shaper_boards_list(api_client):
    workshop = workshop_for()
    mine = published_model(workshop)
    published_model(workshop_for())
    assert ids(api_client.get(f"/api/v1/shapers/{workshop.slug}/boards")) == {str(mine.pk)}


def test_public_board_types_include_used_custom_types_only(api_client):
    workshop = workshop_for()
    used = BoardType.objects.create(workshop=workshop, code="fish-custom", name="Фиш", sku_code="X1AB")
    BoardType.objects.create(workshop=workshop, code="unused", name="Не используется", sku_code="X2AB")
    published_model(workshop, board_type=used)
    codes = {t["code"] for t in api_client.get("/api/v1/board-types").json()}
    assert {"fish", "gun", "sup", "fish-custom"} <= codes and "unused" not in codes
    assert api_client.get("/api/v1/board-materials").status_code == 200


def _count_queries(client, url):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as ctx:
        assert client.get(url).status_code == 200
    return len(ctx.captured_queries)


def test_catalog_lists_have_no_n_plus_one(make_client):
    client = make_client()
    workshops = [workshop_for() for _ in range(2)]
    for w in workshops:
        published_model(w, variants=[{"length_in": Decimal("70")}, {"length_in": Decimal("72")}])
    small = {url: _count_queries(client, url) for url in ("/api/v1/boards", "/api/v1/shapers")}
    for w in workshops + [workshop_for() for _ in range(3)]:
        for n in range(3):
            published_model(w, name=f"Ещё {n}", variants=[{"length_in": Decimal("70")}, {"length_in": Decimal("74")}])
    for url, before in small.items():
        assert _count_queries(client, url) == before, url
