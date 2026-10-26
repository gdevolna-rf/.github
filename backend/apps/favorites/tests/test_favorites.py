"""Избранное: все типы объектов (MSG-11, ATX-11), только опубликованные цели, идемпотентность, IDOR."""
import pytest
from django.db import IntegrityError

from apps.boards.models import BoardMedia, BoardModel
from apps.favorites.models import Favorite
from apps.inventory.models import InventoryItem
from apps.learning.models import InstructorProfile
from apps.mediafiles.models import MediaAsset
from apps.organizations.models import Organization
from apps.spots.models import Spot
from tests.factories import (
    AccountFactory,
    BoardModelFactory,
    BoardVariantFactory,
    InstructorProfileFactory,
    InventoryItemFactory,
    MediaAssetFactory,
    OrganizationFactory,
    SpotFactory,
    WorkshopFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def targets():
    spot = SpotFactory(name="Халактырский пляж")
    instructor = InstructorProfileFactory(headline="Учу с нуля", price_from=4000)
    school = OrganizationFactory(kind=Organization.Kind.SCHOOL, name="Школа Волна")
    workshop = WorkshopFactory(name="Мастерская Шторм")
    model = BoardModelFactory(workshop=workshop, name="Ракета")
    BoardVariantFactory(model=model, price=65000, volume_l=30)
    BoardVariantFactory(model=model, price=70000, volume_l=34)
    item = InventoryItemFactory(title="Софттоп 8'0")
    return {"spot": spot, "instructor": instructor, "organization": school, "board_model": model,
            "inventory_item": item, "workshop": workshop}


def add(client, target_type, target_id):
    return client.post("/api/v1/favorites", {"target_type": target_type, "target_id": str(target_id)}, format="json")


def test_guest_cannot_use_favorites(api_client, targets):
    assert add(api_client, "spot", targets["spot"].pk).status_code == 401
    assert api_client.get("/api/v1/me/favorites").status_code == 401
    assert api_client.get("/api/v1/me/favorites/ids").status_code == 401


def test_all_supported_types_are_added_and_listed_with_typed_cards(make_client, targets):
    """ATX-11: избранное содержит и отображает все поддерживаемые типы."""
    client = make_client()
    for target_type in ["spot", "instructor", "organization", "board_model", "inventory_item"]:
        response = add(client, target_type, targets[target_type].pk)
        assert response.status_code == 201, response.content
        assert response.json()["target_type"] == target_type
    response = client.get("/api/v1/me/favorites")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 5
    by_type = {row["target_type"]: row for row in body["results"]}
    assert set(by_type) == {"spot", "instructor", "organization", "board_model", "inventory_item"}
    spot = targets["spot"]
    assert by_type["spot"]["card"]["url"] == f"/spots/{spot.slug}"
    assert by_type["spot"]["card"]["title"] == "Халактырский пляж"
    assert by_type["spot"]["card"]["extra"]["region"]["slug"] == spot.region.slug
    handle = targets["instructor"].account.profile.handle
    assert by_type["instructor"]["card"]["url"] == f"/instructors/{handle}"
    assert by_type["instructor"]["card"]["extra"]["price_from"] == "4000.00"
    assert by_type["organization"]["card"]["url"] == f"/schools/{targets['organization'].slug}"
    board = by_type["board_model"]["card"]
    assert board["url"] == f"/boards/{targets['board_model'].pk}"
    assert board["extra"]["price_from"] == "65000.00"
    assert board["extra"]["shaper"]["url"] == f"/shapers/{targets['workshop'].slug}"
    assert by_type["inventory_item"]["card"]["url"] == f"/rentals/{targets['inventory_item'].pk}"
    for row in body["results"]:
        assert set(row) == {"target_type", "target_id", "created_at", "card"}
        assert set(row["card"]) == {"title", "subtitle", "image", "url", "extra"}


def test_workshop_favorite_links_to_shaper_profile(make_client, targets):
    client = make_client()
    add(client, "organization", targets["workshop"].pk)
    row = client.get("/api/v1/me/favorites?type=shaper").json()["results"][0]
    assert row["card"]["url"] == f"/shapers/{targets['workshop'].slug}"
    assert client.get("/api/v1/me/favorites?type=school").json()["count"] == 0
    assert client.get("/api/v1/me/favorites?type=shapers").json()["count"] == 1  # алиасы вкладок


def test_rental_organization_favorite_links_to_rentals_catalog(make_client):
    org = OrganizationFactory(kind=Organization.Kind.RENTAL)
    client = make_client()
    add(client, "organization", org.pk)
    row = client.get("/api/v1/me/favorites?type=rental").json()["results"][0]
    assert row["card"]["url"] == f"/rentals?organization={org.slug}"


def test_adding_twice_is_idempotent(make_client, targets):
    client = make_client()
    assert add(client, "spot", targets["spot"].pk).status_code == 201
    second = add(client, "spot", targets["spot"].pk)
    assert second.status_code == 200
    assert Favorite.objects.filter(account=client.account).count() == 1


def test_instructor_can_be_added_by_account_id(make_client, targets):
    client = make_client()
    instructor = targets["instructor"]
    response = add(client, "instructor", instructor.account_id)
    assert response.status_code == 201
    assert response.json()["target_id"] == str(instructor.pk)


@pytest.mark.parametrize("target_type,make", [
    ("spot", lambda: SpotFactory(status=Spot.Status.HIDDEN)),
    ("spot", lambda: SpotFactory(status=Spot.Status.DRAFT)),
    ("instructor", lambda: InstructorProfileFactory(status=InstructorProfile.Status.DRAFT)),
    ("organization", lambda: OrganizationFactory(status=Organization.Status.DRAFT)),
    ("organization", lambda: OrganizationFactory(status=Organization.Status.SUSPENDED)),
    ("board_model", lambda: BoardModelFactory(status=BoardModel.Status.DRAFT)),
    ("board_model", lambda: BoardModelFactory(workshop=WorkshopFactory(status=Organization.Status.DRAFT))),
    ("inventory_item", lambda: InventoryItemFactory(is_published=False)),
    ("inventory_item", lambda: InventoryItemFactory(status=InventoryItem.Status.RETIRED)),
    ("inventory_item", lambda: InventoryItemFactory(
        owner_account=None, owner_organization=OrganizationFactory(status=Organization.Status.DRAFT))),
])
def test_unpublished_targets_cannot_be_favorited(make_client, target_type, make):
    target = make()
    response = add(make_client(), target_type, target.pk)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "favorite_target_not_found"


def test_unknown_target_id_and_type_are_rejected(make_client):
    client = make_client()
    assert add(client, "spot", "00000000-0000-0000-0000-000000000000").status_code == 404
    response = add(client, "planet", "00000000-0000-0000-0000-000000000000")
    assert response.status_code == 400
    assert "target_type" in response.json()["error"]["fields"]
    assert client.get("/api/v1/me/favorites?type=planet").status_code == 400


def test_instructor_of_anonymized_account_is_not_favoritable(make_client):
    from django.utils import timezone

    instructor = InstructorProfileFactory()
    instructor.account.anonymized_at = timezone.now()
    instructor.account.save()
    assert add(make_client(), "instructor", instructor.pk).status_code == 404


def test_delete_is_idempotent_and_scoped_to_owner(make_client, targets):
    owner, other = make_client(), make_client()
    add(owner, "spot", targets["spot"].pk)
    add(other, "spot", targets["spot"].pk)
    url = f"/api/v1/favorites/spot/{targets['spot'].pk}"
    assert owner.delete(url).status_code == 204
    assert owner.delete(url).status_code == 204
    assert not Favorite.objects.filter(account=owner.account).exists()
    assert Favorite.objects.filter(account=other.account).count() == 1


def test_delete_instructor_by_account_id(make_client, targets):
    client = make_client()
    add(client, "instructor", targets["instructor"].pk)
    assert client.delete(f"/api/v1/favorites/instructor/{targets['instructor'].account_id}").status_code == 204
    assert not Favorite.objects.exists()


def test_delete_with_invalid_ids(make_client):
    client = make_client()
    assert client.delete("/api/v1/favorites/spot/not-a-uuid").status_code == 204
    assert client.delete("/api/v1/favorites/planet/00000000-0000-0000-0000-000000000000").status_code == 400


def test_list_only_shows_own_favorites(make_client, targets):
    owner, other = make_client(), make_client()
    add(owner, "spot", targets["spot"].pk)
    assert other.get("/api/v1/me/favorites").json()["count"] == 0
    assert other.get("/api/v1/me/favorites/ids").json()["spot"] == []


def test_ids_endpoint_groups_by_type(make_client, targets):
    client = make_client()
    add(client, "spot", targets["spot"].pk)
    add(client, "board_model", targets["board_model"].pk)
    ids = client.get("/api/v1/me/favorites/ids").json()
    assert ids == {"spot": [str(targets["spot"].pk)], "instructor": [], "organization": [],
                   "board_model": [str(targets["board_model"].pk)], "inventory_item": []}


def test_hidden_target_disappears_from_list_and_ids(make_client, targets):
    client = make_client()
    add(client, "spot", targets["spot"].pk)
    add(client, "organization", targets["organization"].pk)
    Spot.objects.filter(pk=targets["spot"].pk).update(status=Spot.Status.HIDDEN)
    body = client.get("/api/v1/me/favorites").json()
    assert [row["target_type"] for row in body["results"]] == ["organization"]
    assert client.get("/api/v1/me/favorites/ids").json()["spot"] == []
    # Запись сохраняется и вернётся после повторной публикации.
    Spot.objects.filter(pk=targets["spot"].pk).update(status=Spot.Status.PUBLISHED)
    assert client.get("/api/v1/me/favorites").json()["count"] == 2


def test_list_filter_by_type_and_newest_first(make_client, targets):
    client = make_client()
    add(client, "spot", targets["spot"].pk)
    other_spot = SpotFactory()
    add(client, "spot", other_spot.pk)
    add(client, "inventory_item", targets["inventory_item"].pk)
    body = client.get("/api/v1/me/favorites?type=spot").json()
    assert body["count"] == 2
    assert body["results"][0]["target_id"] == str(other_spot.pk)


def test_card_image_uses_only_ready_public_media(make_client, targets):
    model = targets["board_model"]
    pending = MediaAssetFactory(status=MediaAsset.Status.PROCESSING)
    ready = MediaAssetFactory()
    BoardMedia.objects.create(model=model, media=pending, position=0, is_cover=True)
    BoardMedia.objects.create(model=model, media=ready, position=1)
    client = make_client()
    card = add(client, "board_model", model.pk).json()["card"]
    assert card["image"]["id"] == str(ready.pk)
    assert card["image"]["url"].endswith(ready.storage_key)


def test_db_rejects_favorite_with_mismatched_target():
    spot = SpotFactory()
    with pytest.raises(IntegrityError):
        Favorite.objects.create(account=AccountFactory(), target_type="organization", spot=spot)


def test_list_query_count_is_bounded(make_client, targets, django_assert_max_num_queries):
    client = make_client()
    for target_type in ["spot", "instructor", "organization", "board_model", "inventory_item"]:
        add(client, target_type, targets[target_type].pk)
    for _ in range(3):
        add(client, "spot", SpotFactory().pk)
    with django_assert_max_num_queries(20):
        assert client.get("/api/v1/me/favorites").status_code == 200


def test_admin_pages_load(make_client, targets):
    admin = make_client(AccountFactory(is_staff=True, is_superuser=True), two_factor=True)
    add(admin, "spot", targets["spot"].pk)
    favorite = Favorite.objects.get()
    assert admin.get("/admin/favorites/favorite/").status_code == 200
    assert admin.get(f"/admin/favorites/favorite/{favorite.pk}/change/").status_code == 200
