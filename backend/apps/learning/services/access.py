"""Права на занятия, программы и учеников (5.2, SCH-06, SCH-10, AT-09/F15).

Доступ проверяется по активному членству на каждом запросе: отзыв членства закрывает управление немедленно.
"""
from apps.accounts.models import Specialty
from apps.accounts.services.specialties import require_specialty
from apps.common.exceptions import Forbidden, NotFound
from apps.learning.models import InstructorProfile, LessonSession
from apps.organizations.models import Membership, Organization
from apps.organizations.services.access import MANAGE_ROLES, active_membership, can_manage

R = Membership.Role
TEACHING_ROLES = (R.OWNER, R.MANAGER, R.INSTRUCTOR)
SCHOOL_STAFF_ROLES = (R.OWNER, R.MANAGER, R.STAFF)


def require_instructor(account):
    require_specialty(account, Specialty.INSTRUCTOR,
                      "Подключите направление «Сёрф-инструктор» в разделе «Мои направления».")


def get_own_profile(account, *, required=True):
    profile = InstructorProfile.objects.filter(account=account).first()
    if profile is None and required:
        raise NotFound("Карточка инструктора ещё не создана. Заполните и сохраните профиль.",
                       code="instructor_profile_not_found")
    return profile


def get_school(org_id, account, roles=MANAGE_ROLES, *, message=None):
    """Школа + проверка роли. Чужая/несуществующая организация → 404, нет роли → 403."""
    org = Organization.objects.filter(pk=org_id).select_related("region").first()
    if org is None:
        raise NotFound("Организация не найдена.")
    membership = active_membership(account, org)
    if membership is None:
        if org.status != Organization.Status.PUBLISHED:
            raise NotFound("Организация не найдена.")
        raise Forbidden(message or "Нет полномочий в этой организации.")
    if membership.role not in roles:
        raise Forbidden(message or "Нет полномочий в этой организации.")
    if org.kind != Organization.Kind.SCHOOL:
        raise Forbidden("Программы и расписание доступны только сёрф-школам.", code="not_a_school")
    return org, membership


def is_private_owner(account, session):
    if session.organization_id or not session.offer_id:
        return False
    return session.offer.instructor.account_id == getattr(account, "pk", None)


def can_manage_session(account, session):
    """Школьное занятие — owner/manager школы; частное — сам инструктор-владелец предложения."""
    if not account or not account.is_authenticated:
        return False
    if session.organization_id:
        return can_manage(account, session.organization)
    return is_private_owner(account, session)


def can_complete_session(account, session):
    if can_manage_session(account, session):
        return True
    if session.instructor_id and session.instructor_id == account.pk:
        if not session.organization_id:
            return True
        return active_membership(account, session.organization) is not None
    return False


def can_view_session_internals(account, session):
    """Участники и внутренние данные: менеджмент, назначенный инструктор, сотрудники школы."""
    if not account or not account.is_authenticated:
        return False
    if session.instructor_id == account.pk:
        return True
    if session.organization_id:
        return active_membership(account, session.organization) is not None
    return is_private_owner(account, session)


def is_session_public(session):
    if session.organization_id:
        org = session.organization
        return org.kind == Organization.Kind.SCHOOL and org.status == Organization.Status.PUBLISHED
    if not session.offer_id:
        return False
    from apps.learning.services.catalog import is_profile_public

    return is_profile_public(session.offer.instructor)


def get_session_for(account, session_id, *, lock=False):
    """Занятие, видимое пользователю (публичное или внутреннее). Иначе 404 (не раскрываем существование)."""
    qs = LessonSession.objects.select_related(
        "organization__region", "program", "offer__instructor__account", "spot__region", "instructor__profile",
    )
    if lock:
        qs = qs.select_for_update(of=("self",))
    session = qs.filter(pk=session_id).first()
    if session is None or not (is_session_public(session) or can_view_session_internals(account, session)):
        raise NotFound("Занятие не найдено.")
    return session


def require_manage_session(account, session):
    if not can_manage_session(account, session):
        raise Forbidden("Управлять занятием может владелец или менеджер школы (для частных уроков — инструктор).")


def require_complete_session(account, session):
    if not can_complete_session(account, session):
        raise Forbidden("Отметить проведение может назначенный инструктор, владелец или менеджер школы.")


def active_school_member(account_id, org):
    return Membership.objects.filter(organization=org, account_id=account_id,
                                     status=Membership.Status.ACTIVE).select_related("account__profile").first()
