"""Справочные данные миграций в тестовой БД (специальности, стандартные типы досок, материалы, contenttypes).

Transactional-тесты (``transactional_db`` / ``django_db(transaction=True)``) в конце делают flush — TRUNCATE всех
таблиц, включая строки, созданные data-миграциями. Без восстановления следующий transactional-тест и следующий
прогон с ``--reuse-db`` остаются без справочников. Здесь — снимок, восстановление и сброс последовательностей;
подключение — в ``backend/conftest.py`` (фикстура ``reference_data``).
"""
from django.apps import apps as global_apps
from django.core.management import call_command
from django.core.management.color import no_style
from django.db import connection


def reference_data_missing():
    """Нет строк, которые создают data-миграции (признак БД, очищенной прерванным transactional-тестом)."""
    from apps.accounts.models import Specialty
    from apps.boards.models import BoardType, Material

    return not (Specialty.objects.exists() and BoardType.objects.filter(workshop=None).exists()
                and Material.objects.filter(workshop=None).exists())


def rerun_data_migrations():
    """Повторно выполняет RunPython-операции миграций проекта (они идемпотентны: update_or_create)."""
    from django.db.migrations.loader import MigrationLoader
    from django.db.migrations.operations.special import RunPython

    loader = MigrationLoader(connection, ignore_no_migrations=True)
    with connection.schema_editor() as editor:
        for (app_label, name), migration in sorted(loader.disk_migrations.items()):
            if not migration.__module__.startswith("apps."):
                continue
            for operation in migration.operations:
                if isinstance(operation, RunPython):
                    operation.code(global_apps, editor)


def reset_sequences():
    """setval(max(id)) для всех таблиц с автоинкрементом — после вставки строк с явными id."""
    models = global_apps.get_models(include_auto_created=True)
    statements = connection.ops.sequence_reset_sql(no_style(), models)
    if statements:
        with connection.cursor() as cursor:
            for sql in statements:
                cursor.execute(sql)


def ensure():
    if reference_data_missing():
        rerun_data_migrations()
    reset_sequences()


def snapshot():
    return connection.creation.serialize_db_to_string()


def restore(data):
    """Очистить БД (без post_migrate — contenttypes берутся из снимка) и вернуть снимок с корректными sequence."""
    call_command("flush", verbosity=0, interactive=False, inhibit_post_migrate=True, reset_sequences=False)
    connection.creation.deserialize_db_from_string(data)
    reset_sequences()
    from django.contrib.contenttypes.models import ContentType

    ContentType.objects.clear_cache()
