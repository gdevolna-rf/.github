"""Предложения правок спота (7.4, SPT-07/08, TRUST-04).

Публичная карточка не меняется до решения модератора: здесь только валидация, хранение diff
{field: {old, new}} и действия автора. Применение/откат вызываются из решений модерации (apps.trust).
"""
import logging
import os
import uuid

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.common.exceptions import Conflict, DomainError, NotFound
from apps.mediafiles.models import MediaAsset
from apps.mediafiles.services import claim_many
from apps.spots.choices import (
    CHOICE_FIELDS,
    COMPASS,
    FIELD_LABELS,
    HAZARD_CHOICES,
    HAZARDS,
    INFRASTRUCTURE_MAX_DISTANCE_M,
    INFRASTRUCTURE_MAX_ITEMS,
    INFRASTRUCTURE_TYPES,
    field_kind,
    field_max_length,
)
from apps.spots.models import COMPASS_POINTS, EDITABLE_SPOT_FIELDS, SpotChangeRequest, SpotPhoto, SpotSourceRecord
from apps.trust.services.audit import record
from apps.trust.services.moderation_queue import close_cases, open_case
from apps.trust.services.restrictions import require_can_publish

logger = logging.getLogger(__name__)

OPEN_STATUSES = (SpotChangeRequest.Status.SUBMITTED, SpotChangeRequest.Status.NEEDS_INFO)
MAX_OPEN_PER_SPOT = 3
MAX_EVIDENCE = 10
_HAZARD_ORDER = [code for code, _ in HAZARD_CHOICES]


class _Invalid(Exception):
    pass


def _as_month(value):
    if isinstance(value, bool):
        raise _Invalid("Месяц — число от 1 до 12.")
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if not isinstance(value, int) or not 1 <= value <= 12:
        raise _Invalid("Месяц — число от 1 до 12.")
    return value


def _normalize_infrastructure(value):
    if not isinstance(value, list):
        raise _Invalid("Ожидается список объектов инфраструктуры.")
    if len(value) > INFRASTRUCTURE_MAX_ITEMS:
        raise _Invalid(f"Не больше {INFRASTRUCTURE_MAX_ITEMS} объектов инфраструктуры.")
    items = []
    for item in value:
        if not isinstance(item, dict):
            raise _Invalid("Каждый объект: {type, name, distance_m}.")
        extra = set(item) - {"type", "name", "distance_m"}
        if extra:
            raise _Invalid(f"Неизвестные ключи: {', '.join(sorted(extra))}.")
        kind = item.get("type")
        if kind not in INFRASTRUCTURE_TYPES:
            raise _Invalid(f"Неизвестный тип инфраструктуры: {kind}.")
        name = item.get("name") or ""
        if not isinstance(name, str) or len(name.strip()) > 120:
            raise _Invalid("Название объекта — строка до 120 символов.")
        distance = item.get("distance_m")
        if distance is not None:
            if isinstance(distance, bool) or not isinstance(distance, (int, float)) or distance != int(distance):
                raise _Invalid("Расстояние — целое число метров.")
            distance = int(distance)
            if not 0 <= distance <= INFRASTRUCTURE_MAX_DISTANCE_M:
                raise _Invalid(f"Расстояние — от 0 до {INFRASTRUCTURE_MAX_DISTANCE_M} м.")
        items.append({"type": kind, "name": name.strip(), "distance_m": distance})
    return items


def normalize_value(field, value):
    """Проверка и нормализация значения поля по его типу. Бросает _Invalid с текстом для пользователя."""
    kind = field_kind(field)
    if kind == "choice":
        if not isinstance(value, str) or value not in CHOICE_FIELDS[field].values:
            raise _Invalid("Недопустимое значение.")
        return value
    if kind == "compass":
        if not isinstance(value, list):
            raise _Invalid("Ожидается список направлений компаса.")
        codes = set()
        for item in value:
            code = item.strip().upper() if isinstance(item, str) else None
            if code not in COMPASS:
                raise _Invalid(f"Неизвестное направление: {item}.")
            codes.add(code)
        return sorted(codes, key=COMPASS_POINTS.index)
    if kind == "months":
        if not isinstance(value, list):
            raise _Invalid("Ожидается список месяцев.")
        return sorted({_as_month(v) for v in value})
    if kind == "hazards":
        if not isinstance(value, list):
            raise _Invalid("Ожидается список опасностей.")
        codes = set()
        for item in value:
            if item not in HAZARDS:
                raise _Invalid(f"Неизвестный код опасности: {item}.")
            codes.add(item)
        return sorted(codes, key=_HAZARD_ORDER.index)
    if kind == "infrastructure":
        return _normalize_infrastructure(value)
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise _Invalid("Ожидается текст.")
    value = value.strip()
    limit = field_max_length(field)
    if len(value) > limit:
        raise _Invalid(f"Не длиннее {limit} символов.")
    return value


def current_value(spot, field):
    """Текущее значение в нормализованной форме (для сравнения и журнала)."""
    raw = getattr(spot, field)
    try:
        return normalize_value(field, raw)
    except _Invalid:
        return list(raw) if isinstance(raw, (list, tuple)) else raw


def build_diff(spot, changes):
    if not isinstance(changes, dict) or not changes:
        raise DomainError("no_changes", "Выберите хотя бы одно поле и предложите новое значение.",
                          fields={"changes": ["Нет изменений."]})
    errors, diff = {}, {}
    for field, new in changes.items():
        if field not in EDITABLE_SPOT_FIELDS:
            errors[f"changes.{field}"] = ["Это поле нельзя изменить через предложение правки."]
            continue
        try:
            new_value = normalize_value(field, new)
        except _Invalid as exc:
            errors[f"changes.{field}"] = [str(exc)]
            continue
        old_value = current_value(spot, field)
        if new_value != old_value:
            diff[field] = {"old": old_value, "new": new_value}
    if errors:
        raise DomainError("validation_error", "Проверьте предложенные значения.", fields=errors)
    if not diff:
        raise DomainError("no_changes", "Предложенные значения совпадают с текущими данными спота.",
                          fields={"changes": ["Нет изменений."]})
    return {field: diff[field] for field in EDITABLE_SPOT_FIELDS if field in diff}


def proposal_summary(proposal):
    labels = ", ".join(FIELD_LABELS.get(f, f) for f in proposal.changes)
    return f"Правка спота «{proposal.spot.name}»: {labels}"[:300]


def _claim_evidence(evidence_ids, author):
    ids = list(dict.fromkeys(str(i) for i in (evidence_ids or [])))
    if len(ids) > MAX_EVIDENCE:
        raise DomainError("too_many_files", f"Не больше {MAX_EVIDENCE} фото-доказательств.",
                          fields={"evidence_ids": [f"Не больше {MAX_EVIDENCE} файлов."]})
    return claim_many(ids, author, purposes=[MediaAsset.Purpose.SPOT_EVIDENCE], kinds=[MediaAsset.Kind.IMAGE])


def create_proposal(spot, author, *, changes, comment="", source="", evidence_ids=None, request=None):
    require_can_publish(author)
    with transaction.atomic():
        diff = build_diff(spot, changes)
        open_count = SpotChangeRequest.objects.filter(spot=spot, author=author, status__in=OPEN_STATUSES).count()
        if open_count >= MAX_OPEN_PER_SPOT:
            raise Conflict("У вас уже есть несколько предложений по этому споту на рассмотрении. "
                           "Дождитесь решения модератора.", code="too_many_open_proposals")
        evidence = _claim_evidence(evidence_ids, author)
        proposal = SpotChangeRequest.objects.create(
            spot=spot, author=author, changes=diff, comment=comment.strip(), source=source.strip(),
        )
        proposal.evidence.set(evidence)
        open_case("spot_change", proposal_summary(proposal), spot_change_request=proposal)
        record(author, "spot.change_proposed", proposal, after=diff,
               metadata={"spot_id": str(spot.id)}, request=request)
    return proposal


def _locked_own(proposal_id, author):
    proposal = (SpotChangeRequest.objects.select_for_update(of=("self",)).select_related("spot")
                .filter(pk=proposal_id, author=author).first())
    if proposal is None:
        raise NotFound("Предложение не найдено.")
    return proposal


def update_proposal(proposal_id, author, *, changes=None, comment=None, source=None, evidence_ids=None, request=None):
    """Ответ автора на «нужны уточнения»: needs_info → submitted, кейс снова в очереди."""
    require_can_publish(author)
    with transaction.atomic():
        proposal = _locked_own(proposal_id, author)
        if proposal.status != SpotChangeRequest.Status.NEEDS_INFO:
            raise Conflict("Изменить предложение можно, только когда модератор запросил уточнения.",
                           code="invalid_status")
        if changes is None:
            changes = {field: value["new"] for field, value in proposal.changes.items()}
        before = proposal.changes
        proposal.changes = build_diff(proposal.spot, changes)
        if comment is not None:
            proposal.comment = comment.strip()
        if source is not None:
            proposal.source = source.strip()
        if evidence_ids is not None:
            proposal.evidence.set(_claim_evidence(evidence_ids, author))
        proposal.status = SpotChangeRequest.Status.SUBMITTED
        proposal.save()
        open_case("spot_change", proposal_summary(proposal), spot_change_request=proposal)
        record(author, "spot.change_resubmitted", proposal, before=before, after=proposal.changes,
               metadata={"spot_id": str(proposal.spot_id)}, request=request)
    return proposal


def withdraw_proposal(proposal_id, author, request=None):
    with transaction.atomic():
        proposal = _locked_own(proposal_id, author)
        if proposal.status not in OPEN_STATUSES:
            raise Conflict("Отозвать можно только предложение, которое ещё рассматривается.", code="invalid_status")
        proposal.status = SpotChangeRequest.Status.WITHDRAWN
        proposal.save(update_fields=["status", "updated_at"])
        close_cases("withdrawn", None, "Отозвано автором", spot_change_request=proposal)
        record(author, "spot.change_withdrawn", proposal, metadata={"spot_id": str(proposal.spot_id)}, request=request)
    return proposal


# --- применение решением модератора -------------------------------------------------------------

def _copy_to_public(media):
    """Закрытое фото-доказательство → новый публичный MediaAsset (копия объекта в S3)."""
    from apps.common.s3 import internal_client

    ext = os.path.splitext(media.storage_key)[1].lower()[:10]
    base = f"{settings.MEDIA_PUBLIC_PREFIX}spot_photo/{uuid.uuid4().hex}"
    key, thumb = f"{base}{ext}", ""
    try:
        client = internal_client()
        client.copy_object(Bucket=settings.S3_BUCKET, Key=key,
                           CopySource={"Bucket": settings.S3_BUCKET, "Key": media.storage_key})
        if media.thumbnail_key:
            thumb = f"{base}-thumb{os.path.splitext(media.thumbnail_key)[1].lower()[:10]}"
            client.copy_object(Bucket=settings.S3_BUCKET, Key=thumb,
                               CopySource={"Bucket": settings.S3_BUCKET, "Key": media.thumbnail_key})
    except Exception:
        logger.warning("evidence copy to public failed media=%s", media.pk, exc_info=True)
        return None
    return MediaAsset.objects.create(
        owner=media.owner, kind=MediaAsset.Kind.IMAGE, purpose=MediaAsset.Purpose.SPOT_PHOTO,
        visibility=MediaAsset.Visibility.PUBLIC, status=MediaAsset.Status.READY, storage_key=key, thumbnail_key=thumb,
        original_filename=media.original_filename, content_type=media.content_type, size_bytes=media.size_bytes,
        width=media.width, height=media.height, checksum_sha256=media.checksum_sha256, alt_text=media.alt_text,
        processed_at=timezone.now(),
    )


def _evidence_to_gallery(proposal):
    added, skipped = [], []
    position = (proposal.spot.photos.aggregate(m=Max("position"))["m"] or 0) + 1
    for media in proposal.evidence.all():
        if media.kind != MediaAsset.Kind.IMAGE or media.status != MediaAsset.Status.READY:
            skipped.append(str(media.pk))
            continue
        asset = media if media.is_public else _copy_to_public(media)
        if asset is None or SpotPhoto.objects.filter(spot=proposal.spot, media=asset).exists():
            skipped.append(str(media.pk))
            continue
        photo = SpotPhoto.objects.create(spot=proposal.spot, media=asset, position=position,
                                         caption="Фото от участника", author=proposal.author)
        position += 1
        added.append(photo)
    return added, skipped


def apply_proposal(proposal, moderator, *, add_evidence_to_gallery=False, now=None):
    """Применяет proposal.changes к споту (вызывать в транзакции с заблокированными proposal и spot).

    Возвращает (before, after, metadata) для AuditEvent "spot.change_approved".
    """
    now = now or timezone.now()
    spot = proposal.spot
    before = {field: current_value(spot, field) for field in proposal.changes}
    after = {field: value["new"] for field, value in proposal.changes.items()}
    previous_confirmed = spot.last_confirmed_at
    for field, value in after.items():
        setattr(spot, field, value)
    spot.last_confirmed_at = now
    spot.save()
    metadata = {
        "proposal_id": str(proposal.pk),
        "author_id": str(proposal.author_id),
        "previous_last_confirmed_at": previous_confirmed.isoformat() if previous_confirmed else None,
        "added_photo_ids": [],
        "skipped_evidence_ids": [],
        "source_record_id": None,
    }
    if proposal.source:
        source_record = SpotSourceRecord.objects.create(
            spot=spot, source=proposal.source[:200], note=f"Принятая правка: {', '.join(FIELD_LABELS.get(f, f) for f in after)}",
            confirmed_at=now, created_by=moderator,
        )
        metadata["source_record_id"] = source_record.pk
    if add_evidence_to_gallery:
        added, skipped = _evidence_to_gallery(proposal)
        metadata["added_photo_ids"] = [p.pk for p in added]
        metadata["skipped_evidence_ids"] = skipped
    return before, after, metadata


def revert_applied(spot, event, *, force=False):
    """Восстанавливает значения «до» из AuditEvent одобрения. Конфликт, если поля менялись позже."""
    before, after = event.before or {}, event.after or {}
    conflicts = [field for field in before if current_value(spot, field) != after.get(field)]
    if conflicts and not force:
        raise Conflict(
            "После этой правки поля спота уже менялись: " + ", ".join(FIELD_LABELS.get(f, f) for f in conflicts)
            + ". Подтвердите откат с force=true.",
            code="revert_conflict", fields={f: ["Изменено после одобрения правки."] for f in conflicts},
        )
    current = {field: current_value(spot, field) for field in before}
    for field, value in before.items():
        if field in EDITABLE_SPOT_FIELDS:
            setattr(spot, field, value)
    previous = (event.metadata or {}).get("previous_last_confirmed_at")
    spot.last_confirmed_at = parse_datetime(previous) if previous else None
    spot.save()
    metadata = event.metadata or {}
    photo_ids = metadata.get("added_photo_ids") or []
    removed = SpotPhoto.objects.filter(spot=spot, pk__in=photo_ids).delete()[0] if photo_ids else 0
    # Источник подтверждал откатанные значения — убираем его из публичного журнала (история остаётся в аудите).
    source_id = metadata.get("source_record_id")
    removed_source = SpotSourceRecord.objects.filter(spot=spot, pk=source_id).delete()[0] if source_id else 0
    return current, before, {"removed_photo_ids": photo_ids if removed else [],
                             "removed_source_record_id": source_id if removed_source else None}
