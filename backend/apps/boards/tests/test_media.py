"""Фото и видео моделей: ≤10, обложка, порядок, удаление, отдельное видео (BRD-03/04, UX-08/09, ATX-06)."""
import pytest

from apps.boards.models import BoardMedia
from tests.factories import AccountFactory

from .helpers import photo, published_model, shaper_account, video, workshop_for

pytestmark = pytest.mark.django_db


def media_url(model):
    return f"/api/v1/models/{model.pk}/media"


@pytest.fixture
def setup(make_client):
    workshop = workshop_for()
    model = published_model(workshop, with_cover=False)
    return workshop, model, make_client(workshop.owner)


def test_ten_photos_with_cover_and_separate_video(setup):
    """ATX-06: после 10 фото — миниатюры, обложка, удаление и отдельное видео; 11-е фото отклоняется."""
    workshop, model, client = setup
    owner = workshop.owner
    assets = [photo(owner) for _ in range(10)]
    response = client.post(media_url(model), {"media_ids": [str(a.pk) for a in assets]}, format="json")
    assert response.status_code == 201, response.json()
    photos = response.json()["photos"]
    assert len(photos) == 10
    assert photos[0]["is_cover"] is True and sum(p["is_cover"] for p in photos) == 1
    assert [p["media"]["id"] for p in photos] == [str(a.pk) for a in assets]
    assert all(p["media"]["thumbnail_url"] for p in photos)

    extra = client.post(media_url(model), {"media_ids": [str(photo(owner).pk)]}, format="json")
    assert extra.status_code == 409 and extra.json()["error"]["code"] == "photo_limit"

    clip = video(owner)
    with_video = client.put(f"/api/v1/models/{model.pk}/video", {"media_id": str(clip.pk)}, format="json")
    assert with_video.status_code == 200 and with_video.json()["video"]["id"] == str(clip.pk)
    public = client.get(f"/api/v1/boards/{model.pk}").json()
    assert len(public["photos"]) == 10 and public["video"]["id"] == str(clip.pk) and public["has_video"] is True
    removed = client.delete(f"/api/v1/models/{model.pk}/video")
    assert removed.json()["video"] is None


def test_variant_gallery_has_its_own_limit(setup):
    workshop, model, client = setup
    v = model.variants.get()
    client.post(media_url(model), {"media_ids": [str(photo(workshop.owner).pk) for _ in range(10)]}, format="json")
    response = client.post(media_url(model), {"media_ids": [str(photo(workshop.owner).pk) for _ in range(10)],
                                              "variant_id": str(v.pk)}, format="json")
    assert response.status_code == 201
    gallery = response.json()["variants"][0]
    assert gallery["variant_id"] == str(v.pk) and len(gallery["photos"]) == 10
    over = client.post(media_url(model), {"media_ids": [str(photo(workshop.owner).pk)], "variant_id": str(v.pk)},
                       format="json")
    assert over.status_code == 409


def test_set_cover_moves_photo_first_and_reorder(setup):
    workshop, model, client = setup
    assets = [photo(workshop.owner) for _ in range(3)]
    photos = client.post(media_url(model), {"media_ids": [str(a.pk) for a in assets]}, format="json").json()["photos"]
    third = photos[2]["id"]
    response = client.post(f"{media_url(model)}/{third}/cover")
    data = response.json()["photos"]
    assert data[0]["id"] == third and data[0]["is_cover"] is True and data[0]["position"] == 0
    assert [p["is_cover"] for p in data] == [True, False, False]
    order = [photos[1]["id"], photos[0]["id"], third]
    data = client.put(f"{media_url(model)}/order", {"ids": order}, format="json").json()["photos"]
    assert [p["id"] for p in data] == order and data[0]["is_cover"] is True
    mismatch = client.put(f"{media_url(model)}/order", {"ids": order[:2]}, format="json")
    assert mismatch.status_code == 400 and mismatch.json()["error"]["code"] == "order_mismatch"


def test_delete_cover_passes_cover_to_next_photo(setup):
    workshop, model, client = setup
    photos = client.post(media_url(model), {"media_ids": [str(photo(workshop.owner).pk) for _ in range(3)]},
                         format="json").json()["photos"]
    data = client.delete(f"{media_url(model)}/{photos[0]['id']}").json()["photos"]
    assert [p["id"] for p in data] == [photos[1]["id"], photos[2]["id"]]
    assert data[0]["is_cover"] is True and [p["position"] for p in data] == [0, 1]


def test_published_model_keeps_its_last_photo(setup):
    workshop, model, client = setup
    only = client.post(media_url(model), {"media_ids": [str(photo(workshop.owner).pk)]}, format="json").json()["photos"]
    response = client.delete(f"{media_url(model)}/{only[0]['id']}")
    assert response.status_code == 409 and response.json()["error"]["code"] == "cover_required"
    client.post(f"/api/v1/models/{model.pk}/unpublish")
    assert client.delete(f"{media_url(model)}/{only[0]['id']}").status_code == 200
    assert not BoardMedia.objects.filter(model=model).exists()


def test_media_purpose_kind_and_ownership_are_checked(setup):
    workshop, model, client = setup
    wrong_purpose = client.post(media_url(model), {"media_ids": [str(photo(workshop.owner, purpose="avatar").pk)]},
                                format="json")
    assert wrong_purpose.status_code == 400 and wrong_purpose.json()["error"]["code"] == "media_purpose"
    stranger_asset = client.post(media_url(model), {"media_ids": [str(photo(AccountFactory()).pk)]}, format="json")
    assert stranger_asset.status_code == 400 and stranger_asset.json()["error"]["code"] == "media_invalid"
    as_video = client.put(f"/api/v1/models/{model.pk}/video", {"media_id": str(photo(workshop.owner).pk)},
                          format="json")
    assert as_video.status_code == 400
    asset = photo(workshop.owner)
    client.post(media_url(model), {"media_ids": [str(asset.pk)]}, format="json")
    twice = client.post(media_url(model), {"media_ids": [str(asset.pk)]}, format="json")
    assert twice.status_code == 409 and twice.json()["error"]["code"] == "media_in_use"


def test_foreign_shaper_cannot_manage_media(setup, make_client):
    workshop, model, client = setup
    stranger = shaper_account()
    other = make_client(stranger)
    assert other.post(media_url(model), {"media_ids": [str(photo(stranger).pk)]}, format="json").status_code == 404
    item = client.post(media_url(model), {"media_ids": [str(photo(workshop.owner).pk)]}, format="json").json()
    item_id = item["photos"][0]["id"]
    assert other.delete(f"{media_url(model)}/{item_id}").status_code == 404
    assert other.put(f"/api/v1/models/{model.pk}/video", {"media_id": str(video(stranger).pk)},
                     format="json").status_code == 404
