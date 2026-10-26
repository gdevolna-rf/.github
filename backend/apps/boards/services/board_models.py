"""Модели досок мастерской: создание, правка, публикация, архив (BRD-01/02/06, F10)."""
from django.db import transaction
from django.utils import timezone

from apps.accounts.services.verification import require_verified_email
from apps.boards.models import BoardMedia, BoardModel, BoardVariant
from apps.boards.services.history import model_has_history, variant_has_history
from apps.boards.services.sku import ensure_model_serial
from apps.boards.services.types import resolve_board_type
from apps.boards.services.variants import _save_with_sku, create_new_version, create_variant
from apps.boards.services.workshops import ensure_workshop_profile
from apps.common.exceptions import Conflict, DomainError
from apps.common.text import slugify_ru, unique_slug
from apps.trust.services.audit import record
from apps.trust.services.restrictions import require_can_publish

S = BoardModel.Status


def _slug_for(workshop, value, exclude_pk=None):
    slug = slugify_ru(value, max_length=76)
    qs = BoardModel.objects.filter(workshop=workshop, slug=slug)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return slug if not qs.exists() else None


@transaction.atomic
def create_model(workshop, account, data, request=None):
    require_can_publish(account)
    ensure_workshop_profile(workshop)
    board_type = resolve_board_type(workshop, data["board_type_id"])
    if data.get("slug"):
        slug = _slug_for(workshop, data["slug"])
        if slug is None:
            raise Conflict("Модель с таким адресом уже есть в мастерской.", code="slug_taken",
                           fields={"slug": ["Адрес занят."]})
    else:
        slug = unique_slug(BoardModel, data["name"], max_length=80, workshop=workshop)
    model = BoardModel.objects.create(
        workshop=workshop, name=data["name"].strip(), slug=slug, board_type=board_type,
        description=data.get("description", ""), tags=data.get("tags", []), status=S.DRAFT,
    )
    ensure_model_serial(model)
    for variant_data in data.get("variants") or []:
        create_variant(model, account, variant_data, request=request)
    record(account, "board_model.created", model, after={"name": model.name, "serial": model.serial},
           organization=workshop, request=request)
    return model


@transaction.atomic
def update_model(model, account, data, request=None):
    model = BoardModel.objects.select_for_update().select_related("workshop", "board_type").get(pk=model.pk)
    if model.status == S.ARCHIVED:
        raise Conflict("Модель в архиве и не редактируется.", code="model_archived")
    require_can_publish(account)
    before = {"name": model.name, "board_type": model.board_type.code, "slug": model.slug}
    if "name" in data:
        model.name = data["name"].strip()
    if "description" in data:
        model.description = data["description"]
    if "tags" in data:
        model.tags = data["tags"]
    if data.get("slug") and data["slug"] != model.slug:
        slug = _slug_for(model.workshop, data["slug"], exclude_pk=model.pk)
        if slug is None:
            raise Conflict("Модель с таким адресом уже есть в мастерской.", code="slug_taken",
                           fields={"slug": ["Адрес занят."]})
        model.slug = slug
    type_changed = False
    if "board_type_id" in data and data["board_type_id"] != model.board_type_id:
        model.board_type = resolve_board_type(model.workshop, data["board_type_id"])
        type_changed = True
    model.save()
    if type_changed:
        _resku_after_type_change(model, account, request)
    record(account, "board_model.updated", model, before=before,
           after={"name": model.name, "board_type": model.board_type.code, "slug": model.slug},
           organization=model.workshop, request=request)
    return model


def _resku_after_type_change(model, account, request):
    """Тип входит в артикул: варианты без истории получают новый артикул, с историей — новую версию (F10)."""
    for variant in BoardVariant.objects.select_for_update().filter(model=model, is_active=True).order_by("length_in"):
        if variant_has_history(variant):
            create_new_version(variant, account, {}, request=request, board_type=model.board_type)
        else:
            _save_with_sku(variant, model=model, board_type=model.board_type)


def publish_requirements(model, account=None):
    has_variant = BoardVariant.objects.filter(model=model, is_active=True).exists()
    has_cover = BoardMedia.objects.filter(model=model, variant=None).exists()
    items = [
        ("active_variant", "Хотя бы один активный размерный вариант", has_variant),
        ("cover", "Обложка — фото в галерее модели", has_cover),
    ]
    if account is not None:
        items.append(("email_verified", "Подтверждённый email", account.is_email_verified))
    return [{"code": code, "label": label, "ok": ok} for code, label, ok in items]


@transaction.atomic
def publish_model(model, account, request=None):
    model = BoardModel.objects.select_for_update().select_related("workshop").get(pk=model.pk)
    if model.status == S.HIDDEN:
        raise Conflict("Модель скрыта модератором и не может быть опубликована.", code="model_hidden")
    if model.status == S.ARCHIVED:
        raise Conflict("Модель в архиве.", code="model_archived")
    require_verified_email(account, "публикации модели")
    require_can_publish(account)
    missing = [item for item in publish_requirements(model) if not item["ok"]]
    if missing:
        raise DomainError("model_incomplete", "Для публикации нужно: " + "; ".join(m["label"] for m in missing) + ".",
                          fields={m["code"]: [m["label"]] for m in missing})
    if model.status != S.PUBLISHED:
        before = model.status
        model.status = S.PUBLISHED
        model.published_at = model.published_at or timezone.now()
        model.save(update_fields=["status", "published_at", "updated_at"])
        record(account, "board_model.published", model, before={"status": before}, after={"status": model.status},
               organization=model.workshop, request=request)
    return model


@transaction.atomic
def unpublish_model(model, account, request=None):
    model = BoardModel.objects.select_for_update().select_related("workshop").get(pk=model.pk)
    if model.status == S.HIDDEN:
        raise Conflict("Модель скрыта модератором.", code="model_hidden")
    if model.status == S.ARCHIVED:
        raise Conflict("Модель в архиве.", code="model_archived")
    if model.status == S.PUBLISHED:
        model.status = S.DRAFT
        model.save(update_fields=["status", "updated_at"])
        record(account, "board_model.unpublished", model, before={"status": S.PUBLISHED}, after={"status": S.DRAFT},
               organization=model.workshop, request=request)
    return model


@transaction.atomic
def delete_model(model, account, request=None):
    """Модель с обращениями/экземплярами уходит в архив (ссылки и снимки заказов сохраняются), иначе удаляется."""
    model = BoardModel.objects.select_for_update().select_related("workshop").get(pk=model.pk)
    if model_has_history(model):
        before = model.status
        model.status = S.ARCHIVED
        model.save(update_fields=["status", "updated_at"])
        record(account, "board_model.archived", model, before={"status": before}, after={"status": S.ARCHIVED},
               organization=model.workshop, request=request)
        return "archived"
    record(account, "board_model.deleted", model, before={"name": model.name}, organization=model.workshop,
           request=request)
    BoardMedia.objects.filter(model=model).delete()
    BoardVariant.objects.filter(model=model, previous_version__isnull=False).update(previous_version=None)
    BoardVariant.objects.filter(model=model).delete()
    model.delete()
    return "deleted"
