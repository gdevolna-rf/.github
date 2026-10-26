"""python manage.py seed_demo [--if-empty | --reset] — посевные данные прототипа v14 (docs/DEMO_DATA.md).

Без флагов: загрузить, если демо-данных ещё нет (иначе — подсказка про --reset, ничего не меняется).
--if-empty: тихо ничего не делать, если есть хотя бы один демо-спот; так вызывается из entrypoint (SEED_DEMO=1),
           поэтому ошибка посева печатается в лог, но не мешает старту сервера.
--reset:   удалить демо-записи (и зависящие от них брони/обращения/диалоги, созданные при ручной проверке) и создать
           заново. Посевные файлы в S3 и их MediaAsset переиспользуются по storage_key.

Загрузка в S3 — вне транзакции; всё в БД — в одной transaction.atomic().
"""
import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.demo import data as D
from apps.demo.assets import AssetUploader
from apps.demo.seeding import (
    DEMO_LOGINS,
    DemoSeeder,
    any_demo_data,
    asset_plan,
    demo_email,
    demo_present,
    reset_demo_data,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Загружает демо-данные прототипа ГДеволна v14 (все записи is_demo=True)."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--if-empty", action="store_true", help="Ничего не делать, если демо-споты уже есть.")
        group.add_argument("--reset", action="store_true", help="Удалить демо-данные и создать заново.")

    def handle(self, *args, **options):
        if options["if_empty"]:
            try:
                self._run(if_empty=True, reset=False)
            except Exception as exc:  # noqa: BLE001 — автозапуск при старте контейнера не должен ронять сервер
                logger.exception("seed_demo --if-empty failed")
                self.stderr.write(self.style.ERROR(f"seed_demo: демо-данные не загружены: {exc!r}"))
            return
        self._run(if_empty=False, reset=options["reset"])

    def _run(self, *, if_empty, reset):
        if if_empty and demo_present():
            self.stdout.write("seed_demo: демо-данные уже есть — пропускаю (--if-empty).")
            return
        if not reset and any_demo_data():
            self.stdout.write("seed_demo: демо-данные уже есть. Для пересоздания: python manage.py seed_demo --reset")
            return

        specs = asset_plan()
        uploader = AssetUploader()
        prepared = uploader.upload(specs)  # S3 — вне транзакции БД

        deleted = {}
        with transaction.atomic():
            if reset:
                deleted = reset_demo_data()
            counts = DemoSeeder().build(specs, prepared)

        self._summary(counts, deleted, uploader, reset)

    def _summary(self, counts, deleted, uploader, reset):
        out = self.stdout
        if reset:
            total = sum(deleted.values())
            details = ", ".join(f"{label.split('.')[-1]}: {n}" for label, n in sorted(deleted.items()))
            out.write(f"seed_demo --reset: удалено записей {total}" + (f" ({details})" if details else ""))
        out.write(self.style.SUCCESS("seed_demo: демо-данные загружены"))
        out.write("  " + " · ".join(f"{label}: {n}" for label, n in counts.items()))
        out.write(f"  S3 public/seed/: загружено объектов {uploader.uploaded}, без изменений {uploader.reused}")
        out.write("  Не созданы (TZ 12.2, PL-02, ATX-33): отзывы, обращения, сообщения, уведомления, аналитика, "
                  "проверенные сертификаты, статистика")
        out.write(f"Демо-логины (пароль для всех: {D.PASSWORD}):")
        for local, note in DEMO_LOGINS:
            out.write(f"  {demo_email(local):<40} {note}")
