"""Регистрация (ATX-01, ACC-01): один Account + UserProfile + направления + согласия; вход в той же сессии."""
from django.contrib.auth import login
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction

from apps.accounts.models import Account, ConsentRecord, Specialty, UserProfile
from apps.accounts.services import consents, handles
from apps.accounts.services.specialties import SCHOOL, grant_specialty
from apps.common.exceptions import DomainError

PRIMARY_TYPES = (Specialty.SURFER, Specialty.INSTRUCTOR, Specialty.SHAPER, SCHOOL, Specialty.RENTAL)
EXTRA_SPECIALTIES = (Specialty.INSTRUCTOR, Specialty.SHAPER, Specialty.RENTAL, SCHOOL)
AUTH_BACKEND = "django.contrib.auth.backends.ModelBackend"


def normalize_email(email):
    return (email or "").strip().lower()


def validate_new_password(password, account=None, email=""):
    probe = account or Account(email=email)
    try:
        validate_password(password, user=probe)
    except DjangoValidationError as exc:
        raise DomainError("password_invalid", exc.messages[0], fields={"password": exc.messages}) from exc


def attach_pending_invites(account):
    """Приглашения, отправленные на этот email до регистрации, адресуются аккаунту (5.3)."""
    from apps.organizations.models import OrganizationInvite

    return OrganizationInvite.objects.filter(
        email__iexact=account.email, account__isnull=True, status=OrganizationInvite.Status.PENDING
    ).update(account=account)


def register(*, email, password, first_name, last_name, primary_type, extra_specialties=(), accept_terms,
             accept_privacy, request=None):
    """Возвращает (account, next_step)."""
    email = normalize_email(email)
    if not accept_terms or not accept_privacy:
        fields = {}
        if not accept_terms:
            fields["accept_terms"] = ["Необходимо принять пользовательское соглашение."]
        if not accept_privacy:
            fields["accept_privacy"] = ["Необходимо согласие на обработку персональных данных."]
        raise DomainError("consent_required", "Примите соглашение и согласие на обработку данных.", fields=fields)
    if primary_type not in PRIMARY_TYPES:
        raise DomainError("primary_type_invalid", "Выберите основной тип профиля.",
                          fields={"primary_type": ["Недопустимое значение."]})
    extras = []
    for code in extra_specialties or []:
        if code not in EXTRA_SPECIALTIES:
            raise DomainError("specialty_invalid", "Недопустимое направление.",
                              fields={"extra_specialties": [f"Недопустимое значение: {code}."]})
        if code not in extras and code != primary_type:
            extras.append(code)
    if Account.objects.filter(email__iexact=email).exists():
        raise DomainError("email_taken", "Аккаунт с таким email уже существует. Войдите или восстановите пароль.",
                          fields={"email": ["Email уже зарегистрирован."]})
    validate_new_password(password, email=email)

    wants_school = primary_type == SCHOOL or SCHOOL in extras
    try:
        with transaction.atomic():
            account = Account.objects.create_user(email=email, password=password)
            UserProfile.objects.create(
                account=account,
                handle=handles.generate_handle(first_name, last_name, email),
                first_name=first_name.strip(),
                last_name=last_name.strip(),
            )
            surfer_primary = primary_type in (Specialty.SURFER, SCHOOL)
            grant_specialty(account, Specialty.SURFER, primary=surfer_primary)
            if not surfer_primary:
                grant_specialty(account, primary_type, primary=True)
            for code in extras:
                if code != SCHOOL:
                    grant_specialty(account, code)
            consents.record_consent(account, ConsentRecord.Kind.TERMS, True, request)
            consents.record_consent(account, ConsentRecord.Kind.PRIVACY, True, request)
            attach_pending_invites(account)

            from apps.accounts.tasks import send_verification_email

            account_id = str(account.pk)
            transaction.on_commit(lambda: send_verification_email.delay(account_id))
    except IntegrityError as exc:  # гонка двух регистраций одного email
        raise DomainError("email_taken", "Аккаунт с таким email уже существует.",
                          fields={"email": ["Email уже зарегистрирован."]}) from exc

    if request is not None:
        login(request, account, backend=AUTH_BACKEND)
    return account, ("create_school" if wants_school else None)
