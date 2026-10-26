# Backend: правила разработки

Читать вместе с `docs/ARCHITECTURE.md` (контракт API), `docs/TZ.md` (требования с кодами) и
`docs/dev/INTEGRATION_NOTES.md` (сквозные правила: 401/403, ограничения модератора, видимость, уведомления, блокировки).

## Структура приложения

```
backend/apps/<app>/
  models.py          # модели (уже созданы; поля можно добавлять — сразу `makemigrations <app>`)
  services/*.py      # бизнес-правила, транзакции, проверки прав; бросают DomainError/Forbidden/Conflict/NotFound
  serializers.py     # валидация входа и формат выхода
  views.py           # тонкие DRF-представления: права → сервис → сериализатор
  urls.py            # пути БЕЗ префикса /api/v1/ и без завершающего слэша
  tasks.py           # Celery: @shared_task(name="<app>.<task>")
  admin.py           # Django Admin для моделей приложения
  tests/test_*.py    # pytest; фабрики — backend/tests/factories.py или apps/<app>/tests/factories.py
```

## Правила

1. Сообщения для пользователя — по-русски; машинные `code` — snake_case по-английски.
2. Права проверяет сервер на каждом действии. Публичное чтение — явный `AllowAny` / `ReadOnlyOrAuthenticated`.
   Querysets фильтруются по доступу (IDOR). Чужой объект → 404, если само существование не должно раскрываться, иначе 403.
3. Изменения нескольких таблиц — в `transaction.atomic()`. Гонки (вместимость, бронь, статус) — `select_for_update()`.
   `IntegrityError` от exclusion/unique-ограничений переводить в `Conflict` с понятным текстом.
4. Сквозные сервисы (аудит, уведомления, WS, аналитика, права в организации, специальности, медиа) — только через функции
   из таблицы в ARCHITECTURE §2. Не писать альтернативные реализации.
5. Медиа в ответах — `apps.mediafiles.serializers.MediaSerializer`; люди — `apps.accounts.serializers_public.PublicAccountSerializer`.
   Закрытые поля профиля (email, phone, birth_date, private_contacts) — только в `GET /me`.
6. Демо-записи (`is_demo=True`) отображаются как обычные посевные данные, но отзывы/статистика/сообщения из прототипа не создаются.
7. Для APIView/функциональных представлений с нестандартным телом добавлять `@extend_schema` (drf-spectacular), чтобы
   `python manage.py spectacular --file /tmp/schema.yml` проходил без ошибок.
8. Тесты — на каждое правило и приёмочный сценарий ТЗ (AT-xx, ATX-xx, Fxx), включая негативные (чужой пользователь, гость,
   неверный статус, гонка). Тест называется по поведению.

## Команды

```bash
# тесты одного приложения в отдельной тестовой БД (параллельные прогоны не мешают друг другу)
docker compose run --rm -e TEST_DB_NAME=test_<name> backend pytest apps/<app> --create-db   # первый раз / после миграций
docker compose run --rm -e TEST_DB_NAME=test_<name> backend pytest apps/<app>               # повторно (reuse-db)

docker compose run --rm backend python manage.py makemigrations <app>
docker compose run --rm backend python manage.py spectacular --file /tmp/schema.yml --validate --fail-on-warn
make schema                                   # docs/openapi.yml
docker compose restart backend celery-worker   # подхватить изменения кода в живом сервере
```

Фикстуры (`backend/conftest.py`): `api_client`, `user`, `auth_client`, `make_client(account=None, two_factor=False)` —
клиент с сессией; `two_factor=True` помечает сессию прошедшей 2FA (нужно для модераторских эндпоинтов); `moderator`,
`mod_client`, `run_on_commit`; autouse `memory_storage` (in-memory S3, пустой кеш). Transactional-тесты — просто
`transactional_db` / `django_db(transaction=True)`: справочники и sequence восстанавливает autouse `reference_data`.
Фабрики (`backend/tests/factories.py`): AccountFactory (+профиль, направление surfer), `add_specialty`, `make_moderator`,
RegionFactory, SpotFactory, MediaAssetFactory, OrganizationFactory (+owner membership), `add_member`, WorkshopFactory,
BoardModelFactory, BoardVariantFactory, InventoryItemFactory, InstructorProfileFactory, InstructorOfferFactory,
SchoolProgramFactory, LessonSessionFactory, `future(hours, duration)`.
