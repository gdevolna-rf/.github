"""Глобальный поиск (NAV-04): типы результатов, только публичные объекты, частичные слова, порядок, маршруты §9."""
import pytest

from apps.inventory.models import InventoryItem
from apps.organizations.models import Organization
from apps.community.tests.factories import gg_account
from apps.messaging.models import AccountBlock
from tests.factories import (
    BoardModelFactory,
    BoardVariantFactory,
    InstructorProfileFactory,
    InventoryItemFactory,
    OrganizationFactory,
    RegionFactory,
    SpotFactory,
    WorkshopFactory,
)

pytestmark = pytest.mark.django_db


def search(client, q, **params):
    response = client.get("/api/v1/search", {"q": q, **params})
    assert response.status_code == 200, response.content
    return response.json()


def group(body, type_):
    return next(g for g in body["groups"] if g["type"] == type_)


def titles(body, type_):
    return [r["title"] for r in group(body, type_)["results"]]


def test_query_must_be_at_least_two_chars(api_client):
    response = api_client.get("/api/v1/search", {"q": " к "})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "search_query_too_short"
    assert api_client.get("/api/v1/search").status_code == 400


def test_all_groups_returned_in_stable_order(api_client):
    body = search(api_client, "волна")
    assert [g["type"] for g in body["groups"]] == ["spots", "instructors", "schools", "shapers", "boards",
                                                   "equipment", "surfers"]
    assert body["query"] == "волна"
    for g in body["groups"]:
        assert set(g) == {"type", "label", "total", "results", "more_url"}


def test_types_filter_and_validation(api_client):
    body = search(api_client, "волна", types="spots,surfer")
    assert [g["type"] for g in body["groups"]] == ["spots", "surfers"]
    assert api_client.get("/api/v1/search", {"q": "волна", "types": "planets"}).status_code == 400


def test_spot_search_partial_case_insensitive_and_region(api_client):
    region = RegionFactory(name="Камчатский край")
    spot = SpotFactory(name="Халактырский пляж", region=region)
    SpotFactory(name="Скрытый пляж", status="hidden", region=region)
    body = search(api_client, "ХАЛАКТ", types="spots")
    result = group(body, "spots")["results"][0]
    assert result == {"type": "spots", "id": str(spot.pk), "title": "Халактырский пляж",
                      "subtitle": "Камчатский край · Средний", "image": None, "url": f"/spots/{spot.slug}"}
    assert group(search(api_client, "камчат", types="spots"), "spots")["total"] == 1


def test_full_text_matches_word_forms(api_client):
    SpotFactory(name="Оленевка", description="Длинные волны и мягкое песчаное дно")
    assert titles(search(api_client, "волна", types="spots"), "spots") == ["Оленевка"]


def test_multi_word_query_requires_all_words(api_client):
    region = RegionFactory(name="Крым")
    SpotFactory(name="Кача", region=region)
    SpotFactory(name="Кача-2", region=RegionFactory(name="Сахалин"))
    assert titles(search(api_client, "кача крым", types="spots"), "spots") == ["Кача"]


def test_exact_and_prefix_matches_come_first(api_client):
    SpotFactory(name="Большая Кача")
    SpotFactory(name="Кача")
    SpotFactory(name="Качалка")
    SpotFactory(name="Бухта", description="Рядом посёлок Кача")
    assert titles(search(api_client, "кача", types="spots", limit=10), "spots")[:3] == ["Кача", "Качалка",
                                                                                      "Большая Кача"]


def test_limit_and_total(api_client):
    for i in range(7):
        SpotFactory(name=f"Риф {i}")
    g = group(search(api_client, "риф", types="spots", limit=3), "spots")
    assert g["total"] == 7 and len(g["results"]) == 3
    assert g["more_url"] == "/spots?q=%D1%80%D0%B8%D1%84"


def test_instructors_schools_shapers_boards_equipment(api_client):
    instructor = InstructorProfileFactory(headline="Сёрф-инструктор на Байкале")
    instructor.account.profile.first_name = "Алексей"
    instructor.account.profile.last_name = "Байкалов"
    instructor.account.profile.save()
    InstructorProfileFactory(status="draft", headline="Байкал черновик")
    school = OrganizationFactory(kind=Organization.Kind.SCHOOL, name="Байкал Сёрф Школа")
    OrganizationFactory(kind=Organization.Kind.SCHOOL, name="Байкал скрытая", status=Organization.Status.DRAFT)
    workshop = WorkshopFactory(name="Байкал Шейп")
    model = BoardModelFactory(workshop=workshop, name="Байкалка")
    BoardVariantFactory(model=model)
    BoardModelFactory(workshop=workshop, name="Байкал черновик", status="draft")
    item = InventoryItemFactory(title="Гидрокостюм Байкал 5/4", kind=InventoryItem.Kind.WETSUIT)
    InventoryItemFactory(title="Байкал продано", status=InventoryItem.Status.SOLD)
    body = search(api_client, "байкал")
    assert group(body, "instructors")["results"][0]["url"] == f"/instructors/{instructor.account.profile.handle}"
    assert group(body, "instructors")["total"] == 1
    assert group(body, "schools")["results"] == [
        {"type": "schools", "id": str(school.pk), "title": school.name, "subtitle": "Сёрф-школа", "image": None,
         "url": f"/schools/{school.slug}"}]
    assert group(body, "shapers")["results"][0]["url"] == f"/shapers/{workshop.slug}"
    assert [r["url"] for r in group(body, "boards")["results"]] == [f"/boards/{model.pk}"]
    assert [r["url"] for r in group(body, "equipment")["results"]] == [f"/rentals/{item.pk}"]


def test_instructor_found_by_region(api_client):
    region = RegionFactory(name="Приморский край")
    instructor = InstructorProfileFactory()
    instructor.regions.add(region)
    assert group(search(api_client, "Приморский", types="instructors"), "instructors")["total"] == 1


def test_surfers_only_with_gg_consent_and_respecting_privacy(api_client, make_client):
    region = RegionFactory(name="Сахалин")
    shown = gg_account(first_name="Марина", last_name="Волнова", region=region, gg_show_region=True)
    gg_account(first_name="Марина", last_name="Скрытная", region=region, gg_show_region=False)
    from tests.factories import AccountFactory

    plain = AccountFactory()
    plain.profile.first_name = "Марина"
    plain.profile.save()
    body = search(api_client, "марина", types="surfers")
    assert group(body, "surfers")["total"] == 2
    by_region = search(api_client, "сахалин", types="surfers")
    assert [r["url"] for r in group(by_region, "surfers")["results"]] == [f"/surfers/{shown.profile.handle}"]
    assert str(plain.pk) not in {r["id"] for r in group(body, "surfers")["results"]}
    # блокировка скрывает участника из поиска
    viewer = make_client(gg_account())
    AccountBlock.objects.create(blocker=shown, blocked=viewer.account)
    assert group(search(viewer, "волнова", types="surfers"), "surfers")["total"] == 0


def test_surfer_result_subtitle_hides_region_when_not_allowed(api_client):
    gg_account(first_name="Олег", region=RegionFactory(name="Крым"), gg_show_region=False, riding_level="pro")
    result = group(search(api_client, "олег", types="surfers"), "surfers")["results"][0]
    assert result["subtitle"] == "Профи"


def test_special_characters_do_not_break_search(api_client):
    SpotFactory(name="Мыс & Бухта")
    for q in ["мыс & бухта", "'; drop table", "!!", "(кача", "кача:*"]:
        assert api_client.get("/api/v1/search", {"q": q}).status_code == 200
