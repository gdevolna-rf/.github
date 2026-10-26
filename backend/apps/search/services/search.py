"""Глобальный поиск (NAV-04, DATA-08): PostgreSQL full-text (config 'russian') + icontains для неполных слов.

Порядок внутри группы: точное совпадение названия → начало названия → вхождение в название → прочее, затем
SearchRank и название. В выдачу попадают только опубликованные объекты; участники — только с согласием GG Surfer.
"""
import re
from urllib.parse import quote

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import Case, CharField, IntegerField, Q, Value, When
from django.db.models.functions import Concat

from apps.common.exceptions import DomainError
from apps.community.services.surfers import gg_profiles_for
from apps.learning.models import InstructorProfile
from apps.organizations.models import Organization
from apps.search.services import catalog

MIN_QUERY = 2
MAX_QUERY = 100
DEFAULT_LIMIT = 5
MAX_LIMIT = 20

GROUPS = {
    "spots": "Споты",
    "instructors": "Инструкторы",
    "schools": "Сёрф-школы",
    "shapers": "Шейперы",
    "boards": "Доски",
    "equipment": "Оборудование",
    "surfers": "Участники GG Surfer",
}
ALIASES = {"spot": "spots", "instructor": "instructors", "school": "schools", "shaper": "shapers",
           "board": "boards", "rentals": "equipment", "rental": "equipment", "surfer": "surfers",
           "people": "surfers", "users": "surfers"}
MORE_URLS = {
    "spots": "/spots?q={q}",
    "instructors": "/instructors?q={q}",
    "schools": "/schools?q={q}",
    "shapers": "/shapers?tab=shapers&q={q}",
    "boards": "/shapers?tab=boards&q={q}",
    "equipment": "/rentals?q={q}",
    "surfers": "/gg?q={q}",
}


def parse_params(params):
    q = " ".join((params.get("q") or "").split())
    if len(q) < MIN_QUERY:
        raise DomainError("search_query_too_short", f"Введите не меньше {MIN_QUERY} символов.",
                          fields={"q": [f"Минимум {MIN_QUERY} символа."]})
    q = q[:MAX_QUERY]
    raw_types = [t.strip().lower() for t in (params.get("types") or "").split(",") if t.strip()]
    types = []
    for value in raw_types or list(GROUPS):
        value = ALIASES.get(value, value)
        if value not in GROUPS:
            raise DomainError("search_type_invalid", "Неизвестный тип результатов.",
                              fields={"types": [f"Допустимо: {', '.join(GROUPS)}."]})
        if value not in types:
            types.append(value)
    try:
        limit = int(params.get("limit") or DEFAULT_LIMIT)
    except ValueError:
        raise DomainError("validation_error", "limit должен быть числом.", fields={"limit": ["Ожидается число."]}) \
            from None
    return q, [t for t in GROUPS if t in types], max(1, min(limit, MAX_LIMIT))


def _terms(q):
    return [t for t in re.split(r"[\s,;]+", q) if t][:8]


def _text_q(fields, terms):
    """Каждое слово запроса должно найтись хотя бы в одном поле (неполные слова: «камч» → «Камчатка»)."""
    condition = Q()
    for term in terms:
        part = Q()
        for field in fields:
            part |= Q(**{f"{field}__icontains": term})
        condition &= part
    return condition


def ranked(qs, q, *, name, fts_fields, text_fields, extra_q=None):
    query = SearchQuery(q, config="russian", search_type="websearch")
    vector = SearchVector(*fts_fields, config="russian")
    match = Q(_fts=query) | _text_q(text_fields, _terms(q))
    if extra_q is not None:
        match |= extra_q
    return (qs.annotate(_fts=vector).filter(match)
            .annotate(_rank=SearchRank(vector, query),
                      _match=Case(When(**{f"{name}__iexact": q}, then=Value(0)),
                                  When(**{f"{name}__istartswith": q}, then=Value(1)),
                                  When(**{f"{name}__icontains": q}, then=Value(2)),
                                  default=Value(3), output_field=IntegerField()))
            .order_by("_match", "-_rank", name, "pk"))


def _result(type_, obj_id, card):
    return {"type": type_, "id": str(obj_id), "title": card["title"], "subtitle": card["subtitle"],
            "image": card["image"], "url": card["url"]}


def search_spots(q, viewer):
    qs = ranked(catalog.public_spots(), q, name="name",
                fts_fields=["name", "short_description", "description", "region__name"],
                text_fields=["name", "short_description", "region__name", "wave_character"])
    return qs, lambda s: _result("spots", s.pk, catalog.spot_card(s))


def search_instructors(q, viewer):
    by_region = InstructorProfile.objects.filter(regions__name__icontains=q).values("pk")
    qs = catalog.public_instructors().annotate(
        _name=Concat("account__profile__first_name", Value(" "), "account__profile__last_name",
                     output_field=CharField()))
    qs = ranked(qs, q, name="_name",
                fts_fields=["account__profile__first_name", "account__profile__last_name", "headline", "about"],
                text_fields=["_name", "account__profile__handle", "headline"],
                extra_q=Q(pk__in=by_region))
    return qs, lambda i: _result("instructors", i.pk, catalog.instructor_card(i))


def _organizations(q, kind, type_, extra_fields=()):
    qs = ranked(catalog.public_organizations(kind), q, name="name",
                fts_fields=["name", "short_description", "description", "city", "region__name", *extra_fields],
                text_fields=["name", "short_description", "city", "region__name", *extra_fields])
    return qs, lambda o: _result(type_, o.pk, catalog.organization_card(o))


def search_schools(q, viewer):
    return _organizations(q, Organization.Kind.SCHOOL, "schools")


def search_shapers(q, viewer):
    return _organizations(q, Organization.Kind.WORKSHOP, "shapers", extra_fields=("workshop__specialization",))


def search_boards(q, viewer):
    qs = ranked(catalog.public_board_models(), q, name="name",
                fts_fields=["name", "description", "board_type__name", "workshop__name"],
                text_fields=["name", "board_type__name", "workshop__name"])
    return qs, lambda m: _result("boards", m.pk, catalog.board_model_card(m))


def search_equipment(q, viewer):
    qs = ranked(catalog.public_inventory_items(), q, name="title",
                fts_fields=["title", "description", "region__name", "spot__name"],
                text_fields=["title", "size", "region__name", "spot__name"])
    return qs, lambda i: _result("equipment", i.pk, catalog.inventory_item_card(i))


def _surfer_result(profile):
    region = profile.region.name if profile.gg_show_region and profile.region_id else ""
    level = profile.get_riding_level_display() if profile.riding_level else ""
    return {"type": "surfers", "id": str(profile.account_id), "title": profile.display_name,
            "subtitle": " · ".join(filter(None, [region, level])),
            "image": catalog.public_media(profile.avatar) if profile.avatar_id else None,
            "url": f"/surfers/{profile.handle}"}


def search_surfers(q, viewer):
    qs = gg_profiles_for(viewer).annotate(
        _name=Concat("first_name", Value(" "), "last_name", output_field=CharField()))
    # Регион ищется только у тех, кто разрешил его показывать (gg_show_region).
    region_q = Q(gg_show_region=True) & _text_q(["region__name"], _terms(q))
    qs = ranked(qs, q, name="_name", fts_fields=["first_name", "last_name", "bio"],
                text_fields=["_name", "handle", "bio", "interests"], extra_q=region_q)
    return qs, _surfer_result


SEARCHERS = {
    "spots": search_spots,
    "instructors": search_instructors,
    "schools": search_schools,
    "shapers": search_shapers,
    "boards": search_boards,
    "equipment": search_equipment,
    "surfers": search_surfers,
}


def search(params, viewer):
    q, types, limit = parse_params(params)
    groups = []
    for type_ in types:
        qs, to_result = SEARCHERS[type_](q, viewer)
        total = qs.count()
        results = [to_result(obj) for obj in qs[:limit]] if total else []
        groups.append({"type": type_, "label": GROUPS[type_], "total": total, "results": results,
                       "more_url": MORE_URLS[type_].format(q=quote(q))})
    return {"query": q, "groups": groups}
