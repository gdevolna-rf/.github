"""Дневник катания (COM-04, COM-06, COM-08, MET-06).

Видимость задаётся для каждой записи: private — только владелец; community — участники GG Surfer; public — все.
Чужим зрителям никогда не отдаются записи и статистика сверх того, что владелец опубликовал (COM-08): публичная
статистика считается только по видимым зрителю записям. Трекинг не обязателен — только ручные отметки.
"""
import datetime as dt
import uuid
from collections import defaultdict

from django.db import transaction
from django.utils import timezone

from apps.common.exceptions import DomainError, NotFound
from apps.community.models import SurfSession
from apps.community.services.surfers import is_gg_member
from apps.mediafiles.models import MediaAsset
from apps.mediafiles.serializers import MediaSerializer
from apps.mediafiles.services import claim_many
from apps.search.services.catalog import decimal_str, public_media, region_data
from apps.spots.models import Spot
from apps.trust.services.restrictions import require_can_publish

MAX_PHOTOS = 10
TOP_SPOTS = 5
EDITABLE_FIELDS = ["spot", "spot_name", "date", "duration_min", "board_note", "conditions", "wave_height_m",
                   "mood_rating", "notes", "visibility"]


def visibility_levels(viewer):
    """Уровни видимости чужих записей для зрителя: public — всем, community — участникам GG Surfer."""
    levels = [SurfSession.Visibility.PUBLIC]
    if is_gg_member(viewer):
        levels.append(SurfSession.Visibility.COMMUNITY)
    return levels


def visible_entries(owner, viewer):
    """Записи владельца, которые может видеть зритель."""
    qs = SurfSession.objects.filter(account=owner)
    if viewer is not None and getattr(viewer, "is_authenticated", False) and viewer.pk == owner.pk:
        return qs
    return qs.filter(visibility__in=visibility_levels(viewer))


def photo_visible_to(asset, viewer):
    """Фото дневника доступно через GET media/{id}[/url], только если оно приложено к записи, которую зритель
    видит в surfers/{handle}/diary (видимость записи, согласие GG Surfer владельца, блокировки). Владелец файла
    и модератор проверяются раньше — в apps.mediafiles.services.access.can_access."""
    from apps.community.services.surfers import gg_profiles_for

    owners = gg_profiles_for(viewer).values("account_id")
    return SurfSession.objects.filter(photos=asset, account_id__in=owners,
                                      visibility__in=visibility_levels(viewer)).exists()


def with_relations(qs):
    return qs.select_related("spot__region").prefetch_related("photos")


def get_own_entry(account, pk):
    """Только своя запись; чужая или несуществующая — одинаковый 404 (IDOR)."""
    try:
        pk = uuid.UUID(str(pk))
    except ValueError:
        pk = None
    entry = with_relations(SurfSession.objects.filter(account=account)).filter(pk=pk).first() if pk else None
    if entry is None:
        raise NotFound("Запись дневника не найдена.", code="diary_entry_not_found")
    return entry


def _attach_photos(entry, account, photo_ids):
    if photo_ids is None:
        return
    if len(photo_ids) > MAX_PHOTOS:
        raise DomainError("diary_too_many_photos", f"Не больше {MAX_PHOTOS} фото в записи.",
                          fields={"photo_ids": [f"Не больше {MAX_PHOTOS} фото."]})
    unique_ids = list(dict.fromkeys(photo_ids))
    assets = claim_many(unique_ids, account, purposes=[MediaAsset.Purpose.DIARY_PHOTO], kinds=[MediaAsset.Kind.IMAGE])
    entry.photos.set(assets)


SHARED_VISIBILITY = (SurfSession.Visibility.COMMUNITY, SurfSession.Visibility.PUBLIC)


def _require_can_share(account, visibility):
    """Запись, видимая другим (community/public), — публикация (TRUST-07); личный дневник доступен всегда."""
    if visibility in SHARED_VISIBILITY:
        require_can_publish(account)


def create_entry(account, data):
    _require_can_share(account, data.get("visibility", SurfSession.Visibility.PRIVATE))
    photo_ids = data.pop("photo_ids", None)
    with transaction.atomic():
        entry = SurfSession.objects.create(account=account, **data)
        _attach_photos(entry, account, photo_ids)
    return get_own_entry(account, entry.pk)


def update_entry(entry, account, data):
    _require_can_share(account, data.get("visibility", entry.visibility))
    photo_ids = data.pop("photo_ids", None)
    for field, value in data.items():
        if field in EDITABLE_FIELDS:
            setattr(entry, field, value)
    if not entry.spot_id and not (entry.spot_name or "").strip():
        raise DomainError("diary_spot_required", "Укажите спот из каталога или название места.",
                          fields={"spot_id": ["Выберите спот или впишите название места."]})
    with transaction.atomic():
        entry.save()
        _attach_photos(entry, account, photo_ids)
    return get_own_entry(account, entry.pk)


def delete_entry(entry):
    entry.delete()


def purge_account_diary(account):
    """AT-10: дневник — личные данные, а не «необходимые записи»: записи удаляются, фото дневника помечаются
    удалёнными и стираются из хранилища после коммита."""
    from apps.mediafiles.services.uploads import _delete_objects

    entries = SurfSession.objects.filter(account=account)
    photos = list(MediaAsset.objects.filter(owner=account, purpose=MediaAsset.Purpose.DIARY_PHOTO)
                  .exclude(status=MediaAsset.Status.DELETED))
    deleted, _ = entries.delete()
    MediaAsset.objects.filter(pk__in=[p.pk for p in photos]).update(status=MediaAsset.Status.DELETED)
    for asset in photos:
        transaction.on_commit(lambda asset=asset: _delete_objects(asset))
    return deleted


# ---------------------------------------------------------------- представление

def _spot_data(spot, public):
    if spot is None:
        return None
    if public and spot.status != Spot.Status.PUBLISHED:
        return None
    data = {"id": str(spot.pk), "slug": spot.slug, "name": spot.name, "region": region_data(spot.region),
            "url": f"/spots/{spot.slug}"}
    if not public:
        data["is_published"] = spot.status == Spot.Status.PUBLISHED
    return data


def entry_data(entry, public=False):
    """public=True — представление для других зрителей (только готовые публичные фото, только опубликованный спот)."""
    spot = _spot_data(entry.spot, public)
    if public:
        photos = [p for p in (public_media(a) for a in entry.photos.all()) if p]
    else:
        photos = MediaSerializer(entry.photos.all(), many=True).data
    data = {
        "id": str(entry.pk),
        "date": entry.date.isoformat(),
        "spot": spot,
        "spot_name": entry.spot_name,
        "place_name": spot["name"] if spot else entry.spot_name,
        "duration_min": entry.duration_min,
        "board_note": entry.board_note,
        "conditions": entry.conditions,
        "wave_height_m": decimal_str(entry.wave_height_m, 1),
        "mood_rating": entry.mood_rating,
        "notes": entry.notes,
        "visibility": entry.visibility,
        "visibility_label": entry.get_visibility_display(),
        "photos": photos,
    }
    if not public:
        data["created_at"] = entry.created_at
        data["updated_at"] = entry.updated_at
    return data


# ---------------------------------------------------------------- статистика (MET-06)

def _streaks(dates, today):
    """(самая длинная серия, текущая серия) по уникальным датам катания."""
    if not dates:
        return 0, 0
    ordered = sorted(dates)
    longest = run = 1
    for prev, cur in zip(ordered, ordered[1:]):
        run = run + 1 if (cur - prev).days == 1 else 1
        longest = max(longest, run)
    current = 0
    last = ordered[-1]
    if last >= today - dt.timedelta(days=1):
        current = 1
        for prev, cur in zip(reversed(ordered[:-1]), reversed(ordered)):
            if (cur - prev).days != 1:
                break
            current += 1
    return longest, current


def compute_stats(entries, today=None, public=False):
    """Статистика по набору записей: дни катания — уникальные даты, споты — каталожные + свободные названия."""
    today = today or timezone.localdate()
    rows = list(entries.values_list("date", "spot_id", "spot_name", "spot__slug", "spot__name", "spot__status"))
    dates = {row[0] for row in rows}
    spot_days = defaultdict(set)
    spot_info = {}
    for date, spot_id, spot_name, slug, name, status in rows:
        if spot_id:
            key = ("spot", spot_id)
            published = status == Spot.Status.PUBLISHED
            ref = {"id": str(spot_id), "slug": slug, "name": name, "url": f"/spots/{slug}"} if published else None
            display = name if (published or not public) else (spot_name or "Место")
            spot_info.setdefault(key, (ref, display))
        elif (spot_name or "").strip():
            key = ("name", spot_name.strip().lower())
            spot_info.setdefault(key, (None, spot_name.strip()))
        else:
            continue
        spot_days[key].add(date)
    top = sorted(spot_days.items(), key=lambda kv: (-len(kv[1]), spot_info[kv[0]][1].lower()))[:TOP_SPOTS]
    longest, current = _streaks(dates, today)
    return {
        "ride_days": len(dates),
        "sessions": len(rows),
        "spots_visited": len(spot_days),
        "this_year_days": len({d for d in dates if d.year == today.year}),
        "longest_streak_days": longest,
        "current_streak_days": current,
        "last_ride_date": max(dates).isoformat() if dates else None,
        "top_spots": [{"spot": spot_info[key][0], "name": spot_info[key][1], "days": len(days)} for key, days in top],
    }
