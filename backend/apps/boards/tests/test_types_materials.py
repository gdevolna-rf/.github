"""Пользовательские типы досок и материалы мастерской (SHP-05/06, ATX-07)."""
import pytest

from apps.boards.models import BoardType, Material
from tests.factories import AccountFactory, add_member

from .helpers import published_model, shaper_account, variant, workshop_for

pytestmark = pytest.mark.django_db


def test_board_types_list_has_standard_types_including_fish_and_gun(make_client):
    workshop = workshop_for()
    data = make_client(workshop.owner).get(f"/api/v1/workshops/{workshop.pk}/board-types").json()
    codes = {t["code"] for t in data}
    assert {"shortboard", "fish", "gun", "longboard", "sup"} <= codes
    assert all(t["is_custom"] is False for t in data)
    assert {t["code"]: t["sku_code"] for t in data}["fish"] == "FSH"


def test_custom_fish_type_appears_in_new_model_select(make_client):
    """ATX-07: настроенный тип «Фиш» появляется в селекте новой модели его мастерской — и только его."""
    workshop = workshop_for()
    client = make_client(workshop.owner)
    response = client.post(f"/api/v1/workshops/{workshop.pk}/board-types", {"name": "Фиш", "silhouette": "fish"},
                           format="json")
    assert response.status_code == 201, response.json()
    created = response.json()
    assert created["is_custom"] is True and created["code"] == "fish" and created["sku_code"].startswith("X")
    names = [t["name"] for t in client.get(f"/api/v1/workshops/{workshop.pk}/board-types").json()]
    assert "Фиш" in names
    model = client.post(f"/api/v1/workshops/{workshop.pk}/models",
                        {"name": "Мой фиш", "board_type_id": created["id"]}, format="json")
    assert model.status_code == 201 and model.json()["board_type"]["name"] == "Фиш"

    other = workshop_for()
    other_names = [t["name"] for t in make_client(other.owner).get(f"/api/v1/workshops/{other.pk}/board-types").json()]
    assert "Фиш" not in other_names
    foreign = make_client(other.owner).post(f"/api/v1/workshops/{other.pk}/models",
                                            {"name": "Чужой тип", "board_type_id": created["id"]}, format="json")
    assert foreign.status_code == 400 and foreign.json()["error"]["code"] == "board_type_invalid"


def test_duplicate_custom_type_is_conflict(make_client):
    workshop = workshop_for()
    client = make_client(workshop.owner)
    url = f"/api/v1/workshops/{workshop.pk}/board-types"
    assert client.post(url, {"name": "Мини-малибу"}, format="json").status_code == 201
    response = client.post(url, {"name": "мини-малибу"}, format="json")
    assert response.status_code == 409 and response.json()["error"]["code"] == "board_type_exists"


def test_update_and_delete_custom_type(make_client):
    workshop = workshop_for()
    client = make_client(workshop.owner)
    created = client.post(f"/api/v1/workshops/{workshop.pk}/board-types", {"name": "Эгг+"}, format="json").json()
    url = f"/api/v1/workshops/{workshop.pk}/board-types/{created['id']}"
    patched = client.patch(url, {"name": "Эгг плюс", "silhouette": "egg"}, format="json").json()
    assert patched["name"] == "Эгг плюс" and patched["code"] == created["code"]
    board_type = BoardType.objects.get(pk=created["id"])
    published_model(workshop, board_type=board_type)
    response = client.delete(url)
    assert response.status_code == 409 and response.json()["error"]["code"] == "board_type_in_use"


def test_standard_types_cannot_be_edited_through_workshop(make_client):
    workshop = workshop_for()
    standard = BoardType.objects.get(workshop=None, code="fish")
    response = make_client(workshop.owner).patch(f"/api/v1/workshops/{workshop.pk}/board-types/{standard.pk}",
                                                 {"name": "Взлом"}, format="json")
    assert response.status_code == 404


def test_any_active_member_manages_types_but_strangers_do_not(make_client):
    workshop = workshop_for()
    staff = AccountFactory()
    add_member(workshop, staff, role="staff")
    url = f"/api/v1/workshops/{workshop.pk}/board-types"
    assert make_client(staff).post(url, {"name": "Ган XL"}, format="json").status_code == 201
    assert make_client(shaper_account()).post(url, {"name": "Чужой"}, format="json").status_code == 403


def test_materials_crud_and_conflicts(make_client):
    workshop = workshop_for()
    client = make_client(workshop.owner)
    url = f"/api/v1/workshops/{workshop.pk}/materials"
    names = [m["name"] for m in client.get(url).json()]
    assert "Карбон" in names
    standard_clash = client.post(url, {"name": "карбон"}, format="json")
    assert standard_clash.status_code == 409 and standard_clash.json()["error"]["code"] == "material_exists"
    created = client.post(url, {"name": "Био-смола"}, format="json")
    assert created.status_code == 201 and created.json()["is_custom"] is True
    detail = f"{url}/{created.json()['id']}"
    assert client.patch(detail, {"name": "Био-эпоксид"}, format="json").json()["name"] == "Био-эпоксид"
    model = published_model(workshop)
    variant(model, material=Material.objects.get(pk=created.json()["id"]), length_in=80)
    response = client.delete(detail)
    assert response.status_code == 409 and response.json()["error"]["code"] == "material_in_use"
    other = client.post(url, {"name": "Пробка"}, format="json").json()
    assert client.delete(f"{url}/{other['id']}").status_code == 204
    assert not Material.objects.filter(pk=other["id"]).exists()
