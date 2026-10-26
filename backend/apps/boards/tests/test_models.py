"""«Мои доски»: модели в кабинете, публикация, архив (BRD-01/02/06/11, F02, F10)."""
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.boards.models import BoardMedia, BoardModel, BoardVariant
from apps.trust.models import AuditEvent
from tests.factories import AccountFactory, InventoryItemFactory, add_member

from .helpers import inquiry_for, photo, published_model, shaper_account, std_type, variant, workshop_for

pytestmark = pytest.mark.django_db


def models_url(workshop):
    return f"/api/v1/workshops/{workshop.pk}/models"


def test_create_model_with_variants_in_one_request(make_client):
    workshop = workshop_for()
    client = make_client(workshop.owner)
    response = client.post(models_url(workshop), {
        "name": "Pacific Fish", "board_type_id": std_type("fish").pk, "description": "Для мягких волн",
        "variants": [
            {"length": "5'10\"", "width": "20 1/2", "thickness": "2 5/8", "volume_l": "35", "price": "60000"},
            {"length_in": "72", "width_in": "21", "price": "65000", "made_to_order_days": 30},
        ],
    }, format="json")
    assert response.status_code == 201, response.json()
    data = response.json()
    assert data["status"] == "draft" and data["slug"] == "pacific-fish" and data["serial"] == 1
    code = workshop.workshop.shaper_code
    skus = sorted(v["sku"] for v in data["variants"])
    assert skus == [f"GV-{code}-FSH-5P10-W2050-001", f"GV-{code}-FSH-6P0-W2100-001"]
    assert data["variants"][0]["dimensions_display"] == "5'10\" × 20 1/2\" × 2 5/8\""
    assert {r["code"]: r["ok"] for r in data["publish_requirements"]} == {
        "active_variant": True, "cover": False, "email_verified": True}
    assert AuditEvent.objects.filter(action="board_model.created", object_id=data["id"]).exists()
    # Порядковый номер следующей модели
    second = client.post(models_url(workshop), {"name": "Pacific Fish", "board_type_id": std_type().pk}, format="json")
    assert second.json()["serial"] == 2 and second.json()["slug"] == "pacific-fish-2"


def test_invalid_nested_variant_rejects_whole_model(make_client):
    workshop = workshop_for()
    response = make_client(workshop.owner).post(models_url(workshop), {
        "name": "Broken", "board_type_id": std_type().pk, "variants": [{"length": "огромная", "width_in": "20"}],
    }, format="json")
    assert response.status_code == 400
    assert not BoardModel.objects.filter(name="Broken").exists()


def test_guest_and_foreign_shaper_cannot_manage_models(api_client, make_client):
    workshop = workshop_for()
    model = published_model(workshop)
    assert api_client.get(models_url(workshop)).status_code == 401
    foreign = make_client(shaper_account())
    assert foreign.get(models_url(workshop)).status_code == 403
    assert foreign.post(models_url(workshop), {"name": "X", "board_type_id": std_type().pk},
                        format="json").status_code == 403
    assert foreign.get(f"/api/v1/models/{model.pk}").status_code == 404
    assert foreign.patch(f"/api/v1/models/{model.pk}", {"name": "Взлом"}, format="json").status_code == 404
    assert foreign.delete(f"/api/v1/models/{model.pk}").status_code == 404
    assert foreign.post(f"/api/v1/models/{model.pk}/unpublish").status_code == 404
    model.refresh_from_db()
    assert model.name != "Взлом" and model.status == BoardModel.Status.PUBLISHED


def test_cabinet_list_includes_drafts_and_filters_by_availability(make_client):
    workshop = workshop_for()
    published = published_model(workshop, name="Опубликована")
    draft = published_model(workshop, name="Черновик")
    BoardModel.objects.filter(pk=draft.pk).update(status=BoardModel.Status.DRAFT)
    archived = published_model(workshop, name="Архив")
    BoardModel.objects.filter(pk=archived.pk).update(status=BoardModel.Status.ARCHIVED)
    InventoryItemFactory(owner_account=None, owner_organization=workshop, variant=published.variants.get(),
                         purpose="sale")
    client = make_client(workshop.owner)
    results = client.get(models_url(workshop)).json()["results"]
    assert {r["id"] for r in results} == {str(published.pk), str(draft.pk)}
    assert {r["status"] for r in results} == {"published", "draft"}
    in_stock = client.get(models_url(workshop) + "?availability=in_stock").json()["results"]
    assert [r["id"] for r in in_stock] == [str(published.pk)]
    assert client.get(models_url(workshop) + "?status=archived").json()["count"] == 1
    # Модель доступна и по вложенному адресу workshops/{id}/models/{model_id}
    assert client.get(f"{models_url(workshop)}/{draft.pk}").json()["status"] == "draft"


def test_staff_member_can_manage_models(make_client):
    workshop = workshop_for()
    staff = AccountFactory()
    add_member(workshop, staff, role="staff")
    response = make_client(staff).post(models_url(workshop), {"name": "От сотрудника", "board_type_id": std_type().pk},
                                       format="json")
    assert response.status_code == 201


def test_publish_requires_variant_cover_and_verified_email(make_client):
    owner = shaper_account(email_verified_at=None)
    workshop = workshop_for(owner)
    client = make_client(owner)
    model_id = client.post(models_url(workshop), {"name": "Lazy", "board_type_id": std_type().pk},
                           format="json").json()["id"]
    response = client.post(f"/api/v1/models/{model_id}/publish")
    assert response.status_code == 403 and response.json()["error"]["code"] == "email_not_verified"
    owner.email_verified_at = timezone.now()
    owner.save()
    response = client.post(f"/api/v1/models/{model_id}/publish")
    assert response.status_code == 400 and response.json()["error"]["code"] == "model_incomplete"
    assert set(response.json()["error"]["fields"]) == {"active_variant", "cover"}
    client.post(f"/api/v1/models/{model_id}/variants", {"length_in": "70", "width_in": "20"}, format="json")
    client.post(f"/api/v1/models/{model_id}/media", {"media_ids": [str(photo(owner).pk)]}, format="json")
    response = client.post(f"/api/v1/models/{model_id}/publish")
    assert response.status_code == 200 and response.json()["status"] == "published"
    assert response.json()["is_public"] is True
    assert make_client().get(f"/api/v1/boards/{model_id}").status_code == 200
    assert client.post(f"/api/v1/models/{model_id}/unpublish").json()["status"] == "draft"
    assert make_client().get(f"/api/v1/boards/{model_id}").status_code == 404


def test_hidden_model_cannot_be_republished(make_client):
    workshop = workshop_for()
    model = published_model(workshop)
    BoardModel.objects.filter(pk=model.pk).update(status=BoardModel.Status.HIDDEN)
    response = make_client(workshop.owner).post(f"/api/v1/models/{model.pk}/publish")
    assert response.status_code == 409 and response.json()["error"]["code"] == "model_hidden"


def test_update_model_fields_keeps_uuid(make_client):
    workshop = workshop_for()
    model = published_model(workshop)
    response = make_client(workshop.owner).patch(f"/api/v1/models/{model.pk}",
                                                 {"name": "Новое имя", "tags": ["fish"]}, format="json")
    assert response.status_code == 200
    assert response.json()["id"] == str(model.pk) and response.json()["name"] == "Новое имя"


def test_type_change_recomputes_skus_and_versions_ordered_variants(make_client):
    """Тип входит в артикул: без заказов — новый артикул, с заказом — новая версия, старая ссылка сохраняется (F10)."""
    workshop = workshop_for()
    client = make_client(workshop.owner)
    data = client.post(models_url(workshop), {"name": "Model", "board_type_id": std_type("shortboard").pk, "variants": [
        {"length_in": "70", "width_in": "20"}, {"length_in": "74", "width_in": "21"}]}, format="json").json()
    ordered = BoardVariant.objects.get(pk=next(v["id"] for v in data["variants"] if v["length_in"] == "70.00"))
    free = BoardVariant.objects.get(pk=next(v["id"] for v in data["variants"] if v["length_in"] == "74.00"))
    inquiry = inquiry_for(ordered)
    response = client.patch(f"/api/v1/models/{data['id']}", {"board_type_id": std_type("fish").pk}, format="json")
    assert response.status_code == 200
    free.refresh_from_db()
    ordered.refresh_from_db()
    assert "-FSH-" in free.sku and free.is_active
    assert ordered.is_active is False and "-SHT-" in ordered.sku
    new_version = BoardVariant.objects.get(previous_version=ordered)
    assert new_version.version == 2 and new_version.sku.endswith("-V2") and "-FSH-" in new_version.sku
    inquiry.refresh_from_db()
    assert inquiry.board_variant_id == ordered.pk


def test_delete_model_without_history_removes_it(make_client):
    workshop = workshop_for()
    model = published_model(workshop)
    response = make_client(workshop.owner).delete(f"/api/v1/models/{model.pk}")
    assert response.status_code == 200 and response.json() == {"result": "deleted"}
    assert not BoardModel.objects.filter(pk=model.pk).exists()
    assert not BoardMedia.objects.filter(model_id=model.pk).exists()


def test_delete_model_with_inquiries_archives_it(make_client):
    workshop = workshop_for()
    model = published_model(workshop)
    inquiry = inquiry_for(model.variants.get())
    response = make_client(workshop.owner).delete(f"/api/v1/models/{model.pk}")
    assert response.json() == {"result": "archived"}
    model.refresh_from_db()
    assert model.status == BoardModel.Status.ARCHIVED
    inquiry.refresh_from_db()
    assert inquiry.board_model_id == model.pk
    assert make_client().get(f"/api/v1/boards/{model.pk}").status_code == 404
    patch = make_client(workshop.owner).patch(f"/api/v1/models/{model.pk}", {"name": "X"}, format="json")
    assert patch.status_code == 409 and patch.json()["error"]["code"] == "model_archived"


def test_delete_model_with_inventory_archives_it(make_client):
    workshop = workshop_for()
    model = published_model(workshop, variants=[{"length_in": Decimal("70")}])
    InventoryItemFactory(owner_account=None, owner_organization=workshop, variant=model.variants.get())
    assert make_client(workshop.owner).delete(f"/api/v1/models/{model.pk}").json() == {"result": "archived"}


def test_variant_table_lists_workshop_variants(make_client):
    workshop = workshop_for()
    model = published_model(workshop, variants=[{"length_in": Decimal("70")}, {"length_in": Decimal("72")}])
    variant(model, length_in=Decimal("80"), is_active=False)
    rows = make_client(workshop.owner).get(f"/api/v1/workshops/{workshop.pk}/variants").json()
    assert len(rows) == 2 and rows[0]["model"]["name"] == model.name
    rows = make_client(workshop.owner).get(f"/api/v1/workshops/{workshop.pk}/variants?include_inactive=true").json()
    assert len(rows) == 3
