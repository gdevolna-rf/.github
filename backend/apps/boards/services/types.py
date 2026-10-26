"""Пользовательские типы досок и материалы мастерской (SHP-05/06, ATX-07)."""
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.db.models.functions import Lower

from apps.boards.models import BoardModel, BoardType, BoardVariant, Material
from apps.boards.services.sku import custom_type_sku_code
from apps.common.exceptions import Conflict, DomainError, NotFound
from apps.common.text import slugify_ru

SILHOUETTES = ["shortboard", "fish", "funboard", "midlength", "longboard", "gun", "hybrid", "egg", "softtop", "sup",
               "custom"]


def types_for_workshop(workshop):
    """Стандартные + собственные типы мастерской (для селекта формы модели)."""
    return BoardType.objects.filter(Q(workshop__isnull=True) | Q(workshop=workshop)).order_by("sort_order", "name")


def materials_for_workshop(workshop):
    return Material.objects.filter(Q(workshop__isnull=True) | Q(workshop=workshop)).order_by("name")


def resolve_board_type(workshop, board_type_id):
    board_type = types_for_workshop(workshop).filter(pk=board_type_id).first()
    if board_type is None:
        raise DomainError("board_type_invalid", "Выберите тип доски из списка вашей мастерской.",
                          fields={"board_type_id": ["Недоступный тип доски."]})
    return board_type


def resolve_material(workshop, material_id):
    if material_id is None:
        return None
    material = materials_for_workshop(workshop).filter(pk=material_id).first()
    if material is None:
        raise DomainError("material_invalid", "Выберите материал из списка вашей мастерской.",
                          fields={"material_id": ["Недоступный материал."]})
    return material


def custom_type(workshop, type_id):
    board_type = BoardType.objects.filter(pk=type_id, workshop=workshop).first()
    if board_type is None:
        raise NotFound("Тип доски не найден.", code="board_type_not_found")
    return board_type


def _unique_type_code(workshop, name):
    base = slugify_ru(name, max_length=34)
    candidate, n = base, 2
    while BoardType.objects.filter(workshop=workshop, code=candidate).exists():
        candidate, n = f"{base}-{n}", n + 1
    return candidate


@transaction.atomic
def create_board_type(workshop, data):
    name = data["name"].strip()
    if BoardType.objects.filter(workshop=workshop).annotate(n=Lower("name")).filter(n=name.lower()).exists():
        raise Conflict("Такой тип досок уже есть в вашей мастерской.", code="board_type_exists",
                       fields={"name": ["Тип уже добавлен."]})
    try:
        with transaction.atomic():
            return BoardType.objects.create(
                workshop=workshop, name=name, code=_unique_type_code(workshop, name),
                silhouette=data.get("silhouette") or "custom", sort_order=data.get("sort_order", 200),
                sku_code=custom_type_sku_code(name),
            )
    except IntegrityError as exc:
        raise Conflict("Такой тип досок уже есть в вашей мастерской.", code="board_type_exists") from exc


@transaction.atomic
def update_board_type(board_type, data):
    if "name" in data:
        name = data["name"].strip()
        clash = BoardType.objects.filter(workshop=board_type.workshop_id).exclude(pk=board_type.pk).annotate(
            n=Lower("name")).filter(n=name.lower())
        if clash.exists():
            raise Conflict("Такой тип досок уже есть в вашей мастерской.", code="board_type_exists",
                           fields={"name": ["Тип уже добавлен."]})
        board_type.name = name  # code и sku_code стабильны: на них ссылаются фильтры и артикулы
    for field in ("silhouette", "sort_order"):
        if field in data:
            setattr(board_type, field, data[field])
    board_type.save()
    return board_type


@transaction.atomic
def delete_board_type(board_type):
    if BoardModel.objects.filter(board_type=board_type).exists():
        raise Conflict("Тип используется в моделях. Сначала смените тип у этих моделей.", code="board_type_in_use")
    board_type.delete()


def custom_material(workshop, material_id):
    material = Material.objects.filter(pk=material_id, workshop=workshop).first()
    if material is None:
        raise NotFound("Материал не найден.", code="material_not_found")
    return material


def _material_clash(workshop, name, exclude_pk=None):
    qs = Material.objects.filter(Q(workshop__isnull=True) | Q(workshop=workshop)).annotate(n=Lower("name")).filter(
        n=name.lower())
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.exists()


@transaction.atomic
def create_material(workshop, data):
    name = data["name"].strip()
    if _material_clash(workshop, name):
        raise Conflict("Такой материал уже есть в списке.", code="material_exists", fields={"name": ["Материал уже есть."]})
    try:
        with transaction.atomic():
            return Material.objects.create(workshop=workshop, name=name)
    except IntegrityError as exc:
        raise Conflict("Такой материал уже есть в списке.", code="material_exists") from exc


@transaction.atomic
def update_material(material, data):
    name = data["name"].strip()
    if _material_clash(material.workshop, name, exclude_pk=material.pk):
        raise Conflict("Такой материал уже есть в списке.", code="material_exists", fields={"name": ["Материал уже есть."]})
    material.name = name
    material.save()
    return material


@transaction.atomic
def delete_material(material):
    if BoardVariant.objects.filter(material=material).exists():
        raise Conflict("Материал указан в вариантах досок. Сначала замените его в этих вариантах.", code="material_in_use")
    material.delete()
