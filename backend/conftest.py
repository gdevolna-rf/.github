"""Общие фикстуры pytest для всего backend (ARCHITECTURE §7, docs/dev/INTEGRATION_NOTES.md).

* ``api_client``, ``user``, ``auth_client``, ``make_client(account=None, two_factor=False)``, ``moderator``,
  ``mod_client`` — клиенты API;
* ``memory_storage`` (autouse) — in-memory хранилище медиа вместо S3 + чистый кеш для каждого теста;
* ``run_on_commit`` — выполнить on_commit-колбэки (Celery, письма, WS) внутри теста;
* ``reference_data`` (autouse для тестов с БД) — справочники data-миграций переживают transactional-тесты:
  достаточно запросить ``transactional_db`` или ``@pytest.mark.django_db(transaction=True)``, отдельные
  фикстуры в приложениях не нужны.
"""
import pytest
from django.core.cache import cache
from pytest_django.fixtures import validate_django_db
from rest_framework.test import APIClient

from apps.accounts.services.roles import OTP_SESSION_KEY
from apps.mediafiles.storage import get_storage
from tests import reference_data as refdata
from tests.factories import AccountFactory, make_moderator


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return AccountFactory()


@pytest.fixture
def make_client(db):
    """Клиент, залогиненный под аккаунтом. two_factor=True помечает сессию как прошедшую 2FA."""

    def _make(account=None, two_factor=False):
        account = account or AccountFactory()
        client = APIClient()
        client.force_login(account)
        if two_factor:
            session = client.session
            session[OTP_SESSION_KEY] = "test"
            session.save()
        client.account = account
        return client

    return _make


@pytest.fixture
def auth_client(make_client, user):
    return make_client(user)


@pytest.fixture
def moderator(db):
    return make_moderator(AccountFactory())


@pytest.fixture
def mod_client(make_client, moderator):
    """Модератор с подтверждённой 2FA в сессии."""
    return make_client(moderator, two_factor=True)


@pytest.fixture(autouse=True)
def memory_storage():
    """In-memory хранилище медиа (без сети) и пустой кеш — для каждого теста заново."""
    storage = get_storage()
    storage.clear()
    cache.clear()
    yield storage
    storage.clear()
    cache.clear()


@pytest.fixture
def run_on_commit(django_capture_on_commit_callbacks):
    """Выполнить on_commit-колбэки (Celery-задачи, письма, WS) внутри теста."""

    def _run(func, *args, **kwargs):
        with django_capture_on_commit_callbacks(execute=True):
            return func(*args, **kwargs)

    return _run


# --- справочники data-миграций и transactional-тесты --------------------------------------------------------------

_TRANSACTIONAL_FIXTURES = {"transactional_db", "live_server", "django_db_reset_sequences"}


def _db_usage(item):
    """(uses_db, transactional) — те же правила, что у pytest-django."""
    names = set(getattr(item, "fixturenames", ()))
    marker = item.get_closest_marker("django_db")
    transactional = bool(names & _TRANSACTIONAL_FIXTURES)
    uses_db = transactional or "db" in names
    if marker is not None:
        transaction, reset_sequences, *_ = validate_django_db(marker)
        uses_db = True
        transactional = transactional or transaction or reset_sequences
    return uses_db, transactional


class _ReferenceState:
    snapshot = None
    dirty = False  # прошёл transactional-тест: его flush стёр справочники


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """Расширение стандартной фикстуры pytest-django: после создания/переиспользования тестовой БД проверяем
    справочники (БД могла остаться пустой после прерванного прогона), выравниваем sequence и снимаем снимок;
    в конце сессии БД возвращается к снимку, чтобы следующий прогон с --reuse-db начинался с полными данными."""
    with django_db_blocker.unblock():
        refdata.ensure()
        _ReferenceState.snapshot = refdata.snapshot()
    yield
    if _ReferenceState.dirty:
        with django_db_blocker.unblock():
            refdata.restore(_ReferenceState.snapshot)
        _ReferenceState.dirty = False


@pytest.fixture(autouse=True)
def reference_data(request, django_db_blocker):
    """Перед тестом с БД справочники на месте и sequence выровнены — даже после flush предыдущего
    transactional-теста. Отдельные фикстуры в приложениях не нужны."""
    uses_db, transactional = _db_usage(request.node)
    if not uses_db:
        yield
        return
    request.getfixturevalue("django_db_setup")
    if _ReferenceState.dirty:
        from django.db import connection

        with django_db_blocker.unblock():
            refdata.restore(_ReferenceState.snapshot)
            # Внутри транзакции обычного теста восстановление откатится — повторим перед следующим тестом.
            _ReferenceState.dirty = connection.in_atomic_block
    if transactional:
        _ReferenceState.dirty = True
    yield
