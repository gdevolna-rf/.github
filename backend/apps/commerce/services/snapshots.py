"""Снимок объекта обращения и карточка контекста (MSG-08, F10).

Снимок сохраняется при создании обращения: последующее изменение названия, размеров, артикула или цены
не меняет историю заказа. Карточка контекста в inbox/чате строится из снимка; ссылка — по текущему объекту
(если он ещё существует), иначе из снимка.
"""
from decimal import Decimal

from django.utils import timezone

TARGET_TYPES = ("board_model", "board_variant", "inventory_item", "instructor_offer", "school_program",
                "lesson_session", "organization", "account")


def money(amount):
    return None if amount is None else str(Decimal(amount).quantize(Decimal("0.01")))


def fmt_money(amount, currency="RUB"):
    if amount is None:
        return ""
    value = Decimal(amount).quantize(Decimal("0.01"))
    whole = f"{int(value):,}".replace(",", " ")
    frac = value - int(value)
    text = whole if not frac else f"{whole},{str(value).split('.')[1]}"
    return f"{text} {'₽' if currency == 'RUB' else currency}"


def fmt_inches(value, feet=False):
    if value is None:
        return ""
    value = Decimal(value).normalize()
    if feet:
        ft = int(value // 12)
        inch = (value - ft * 12).normalize()
        return f"{ft}'{inch:f}\"" if ft else f"{inch:f}\""
    return f"{value:f}\""


def _media_url(media):
    if media is None:
        return None
    return media.thumbnail_url or media.url


def _board_model_cover(model):
    from apps.boards.models import BoardMedia

    item = (BoardMedia.objects.filter(model=model).select_related("media")
            .order_by("-is_cover", "variant_id", "position", "id").first())
    return _media_url(item.media) if item else None


def _variant_cover(variant):
    from apps.boards.models import BoardMedia

    item = (BoardMedia.objects.filter(variant=variant).select_related("media")
            .order_by("-is_cover", "position", "id").first())
    return _media_url(item.media) if item else _board_model_cover(variant.model)


def _item_cover(item):
    photo = item.photos.select_related("media").first()
    return _media_url(photo.media) if photo else None


def _avatar(account):
    profile = getattr(account, "profile", None)
    if profile is None or account.anonymized_at:
        return None
    return _media_url(profile.avatar) if profile.avatar_id else None


def _display_name(account):
    profile = getattr(account, "profile", None)
    if account.anonymized_at:
        return "Удалённый пользователь"
    return profile.display_name if profile else "Пользователь"


def _instructor_url(account):
    profile = getattr(account, "profile", None)
    instructor = getattr(account, "instructor_profile", None) if hasattr(account, "instructor_profile") else None
    if profile and instructor is not None and instructor.status == "published":
        return f"/instructors/{profile.handle}"
    return None


def organization_url(org):
    if org.kind == "school":
        return f"/schools/{org.slug}"
    if org.kind == "workshop":
        return f"/shapers/{org.slug}"
    return None


def _variant_dims(variant):
    parts = [f"{fmt_inches(variant.length_in, feet=True)} × {fmt_inches(variant.width_in)}"]
    if variant.thickness_in:
        parts[0] += f" × {fmt_inches(variant.thickness_in)}"
    if variant.volume_l:
        parts.append(f"{Decimal(variant.volume_l).normalize():f} л")
    return " · ".join(parts)


def snapshot_board_model(model):
    prices = [v.price for v in model.variants.filter(is_active=True) if v.price is not None]
    price_from = min(prices) if prices else None
    return {
        "type": "board_model", "id": str(model.pk), "title": model.name,
        "subtitle": " · ".join(filter(None, [model.board_type.name, model.workshop.name,
                                             f"от {fmt_money(price_from)}" if price_from else ""])),
        "image": _board_model_cover(model), "url": f"/boards/{model.pk}",
        "name": model.name, "board_type": model.board_type.name,
        "workshop": {"id": str(model.workshop_id), "name": model.workshop.name, "slug": model.workshop.slug},
        "price_from": money(price_from), "currency": "RUB",
    }


def snapshot_board_variant(variant):
    model = variant.model
    return {
        "type": "board_variant", "id": str(variant.pk), "title": f"{model.name} {fmt_inches(variant.length_in, feet=True)}",
        "subtitle": " · ".join(filter(None, [f"SKU {variant.sku}", _variant_dims(variant),
                                             fmt_money(variant.price, variant.currency)])),
        "image": _variant_cover(variant), "url": f"/boards/{model.pk}?variant={variant.pk}",
        "name": model.name, "board_model_id": str(model.pk), "board_type": model.board_type.name,
        "workshop": {"id": str(model.workshop_id), "name": model.workshop.name, "slug": model.workshop.slug},
        "sku": variant.sku, "version": variant.version,
        "length_in": money(variant.length_in), "width_in": money(variant.width_in),
        "thickness_in": money(variant.thickness_in), "volume_l": money(variant.volume_l),
        "material": variant.material.name if variant.material_id else None,
        "construction": variant.construction, "fin_system": variant.fin_system,
        "price": money(variant.price), "currency": variant.currency,
    }


def snapshot_inventory_item(item):
    price = ""
    if item.rental_price_per_day is not None:
        price = f"{fmt_money(item.rental_price_per_day, item.currency)}/сутки"
    elif item.rental_price_per_hour is not None:
        price = f"{fmt_money(item.rental_price_per_hour, item.currency)}/час"
    elif item.sale_price is not None:
        price = fmt_money(item.sale_price, item.currency)
    variant = item.variant
    return {
        "type": "inventory_item", "id": str(item.pk), "title": item.title,
        "subtitle": " · ".join(filter(None, [item.get_kind_display(), item.size, price])),
        "image": _item_cover(item), "url": f"/rentals/{item.pk}",
        "kind": item.kind, "purpose": item.purpose, "size": item.size, "condition": item.condition,
        "sku": variant.sku if variant else None, "board_variant_id": str(variant.pk) if variant else None,
        "sale_price": money(item.sale_price), "rental_price_per_day": money(item.rental_price_per_day),
        "rental_price_per_hour": money(item.rental_price_per_hour), "currency": item.currency,
        "pickup_location": item.pickup_location,
    }


def snapshot_instructor_offer(offer):
    account = offer.instructor.account
    return {
        "type": "instructor_offer", "id": str(offer.pk), "title": offer.title,
        "subtitle": " · ".join(filter(None, [_display_name(account), f"{offer.duration_min} мин",
                                             fmt_money(offer.price, offer.currency)])),
        "image": _avatar(account), "url": _instructor_url(account),
        "format": offer.format, "level": offer.level, "duration_min": offer.duration_min,
        "price": money(offer.price), "currency": offer.currency,
        "instructor": {"id": str(account.pk), "name": _display_name(account),
                       "handle": getattr(getattr(account, "profile", None), "handle", None)},
    }


def snapshot_school_program(program):
    org = program.organization
    return {
        "type": "school_program", "id": str(program.pk), "title": program.title,
        "subtitle": " · ".join(filter(None, [org.name, program.level, fmt_money(program.price, program.currency)])),
        "image": _media_url(org.logo) or _media_url(org.cover), "url": organization_url(org),
        "level": program.level, "format": program.format, "age_category": program.age_category,
        "duration_min": program.duration_min, "sessions_count": program.sessions_count,
        "price": money(program.price), "currency": program.currency,
        "organization": {"id": str(org.pk), "name": org.name, "slug": org.slug},
    }


def snapshot_lesson_session(session):
    when = timezone.localtime(session.starts_at).strftime("%d.%m.%Y %H:%M")
    org = session.organization
    image = None
    if org is not None:
        image = _media_url(org.logo) or _media_url(org.cover)
    elif session.offer_id:
        image = _avatar(session.offer.instructor.account)
    price = session.price
    if price is None:
        price = session.program.price if session.program_id else (session.offer.price if session.offer_id else None)
    return {
        "type": "lesson_session", "id": str(session.pk), "title": session.title,
        "subtitle": " · ".join(filter(None, [when, session.spot.name if session.spot_id else "",
                                             org.name if org else ""])),
        "image": image, "url": f"/sessions/{session.pk}",
        "starts_at": session.starts_at.isoformat(), "ends_at": session.ends_at.isoformat(),
        "spot": {"id": str(session.spot_id), "name": session.spot.name} if session.spot_id else None,
        "price": money(price), "currency": session.currency,
    }


def snapshot_organization(org):
    return {
        "type": "organization", "id": str(org.pk), "title": org.name,
        "subtitle": " · ".join(filter(None, [org.get_kind_display(), org.city])),
        "image": _media_url(org.logo) or _media_url(org.cover), "url": organization_url(org),
        "kind": org.kind, "slug": org.slug,
    }


def snapshot_account(account):
    return {
        "type": "account", "id": str(account.pk), "title": _display_name(account),
        "subtitle": "Инструктор" if _instructor_url(account) else "",
        "image": _avatar(account), "url": _instructor_url(account),
        "handle": getattr(getattr(account, "profile", None), "handle", None),
    }


BUILDERS = {
    "board_model": snapshot_board_model,
    "board_variant": snapshot_board_variant,
    "inventory_item": snapshot_inventory_item,
    "instructor_offer": snapshot_instructor_offer,
    "school_program": snapshot_school_program,
    "lesson_session": snapshot_lesson_session,
    "organization": snapshot_organization,
    "account": snapshot_account,
}


def build_snapshot(target_type, obj):
    snapshot = BUILDERS[target_type](obj)
    snapshot["captured_at"] = timezone.now().isoformat()
    return snapshot


def context_card(snapshot):
    """{type, id, title, subtitle, image, url} для inbox и шапки чата."""
    if not snapshot:
        return None
    return {key: snapshot.get(key) for key in ("type", "id", "title", "subtitle", "image", "url")}
