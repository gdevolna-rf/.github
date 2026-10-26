"""Доступ к кабинету мастерской: только активное членство в организации kind=workshop (5.2, 5.3).

Права в организации — через apps.organizations.services.access (не дублируем логику ролей).
Чужая мастерская → 403 (её id ничего не раскрывает), чужая модель/вариант → 404 (черновики не раскрываются).
"""
from django.db.models import Case, IntegerField, Value, When

from apps.boards.models import BoardModel, BoardVariant
from apps.common.exceptions import Forbidden, NotFound
from apps.organizations.models import Membership, Organization
from apps.organizations.services.access import MANAGE_ROLES, member_role, organization_ids_for


def member_workshop_ids(account):
    if not account or not account.is_authenticated:
        return set()
    ids = organization_ids_for(account)
    return set(Organization.objects.filter(pk__in=ids, kind=Organization.Kind.WORKSHOP).values_list("pk", flat=True))


def my_workshop_membership(account, organization_id=None):
    """Первая мастерская, где я активный участник: owner → manager → остальные, затем самая ранняя."""
    qs = Membership.objects.filter(
        account=account, status=Membership.Status.ACTIVE, organization__kind=Organization.Kind.WORKSHOP,
    ).exclude(organization__status=Organization.Status.ARCHIVED).select_related("organization")
    if organization_id:
        qs = qs.filter(organization_id=organization_id)
    order = Case(
        When(role=Membership.Role.OWNER, then=Value(0)),
        When(role=Membership.Role.MANAGER, then=Value(1)),
        default=Value(2), output_field=IntegerField(),
    )
    return qs.order_by(order, "joined_at").first()


def get_workshop(workshop_id):
    workshop = Organization.objects.filter(pk=workshop_id, kind=Organization.Kind.WORKSHOP).first()
    if workshop is None:
        raise NotFound("Мастерская не найдена.", code="workshop_not_found")
    return workshop


def require_workshop_member(account, workshop):
    role = member_role(account, workshop)
    if role is None:
        raise Forbidden("Вы не состоите в этой мастерской.", code="not_workshop_member")
    return role


def require_workshop_manager(account, workshop):
    role = require_workshop_member(account, workshop)
    if role not in MANAGE_ROLES:
        raise Forbidden("Изменять профиль мастерской могут только владелец и менеджер.", code="workshop_manage_forbidden")
    return role


def member_workshop(account, workshop_id, manage=False):
    workshop = get_workshop(workshop_id)
    (require_workshop_manager if manage else require_workshop_member)(account, workshop)
    return workshop


def model_for_member(account, model_id, *, lock=False):
    qs = BoardModel.objects.filter(pk=model_id, workshop_id__in=member_workshop_ids(account))
    if lock:
        qs = qs.select_for_update(of=("self",))
    model = qs.select_related("workshop", "board_type").first()
    if model is None:
        raise NotFound("Модель не найдена.", code="model_not_found")
    return model


def variant_for_member(account, model, variant_id, *, lock=False):
    qs = BoardVariant.objects.filter(pk=variant_id, model=model)
    if lock:
        qs = qs.select_for_update(of=("self",))
    variant = qs.select_related("material").first()
    if variant is None:
        raise NotFound("Вариант не найден.", code="variant_not_found")
    return variant
