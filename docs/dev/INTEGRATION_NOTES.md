# Backend: интеграционные заметки и общие соглашения

Читать вместе с `docs/ARCHITECTURE.md` и `docs/dev/BACKEND_GUIDE.md`. Здесь — правила, которые связывают
приложения между собой (их нарушение не ловится тестами одного приложения), и сводка интеграционного прохода.

## Соглашения (обязательны для нового кода)

### 401 / 403
`CsrfSessionAuthentication.authenticate_header` → гость получает **401** `not_authenticated` с заголовком
`WWW-Authenticate: Session realm="api"`; **403** — только вошедшему без прав (и при ошибке CSRF). Не проверяйте
`is_authenticated` вручную с `Forbidden` — используйте `IsAuthenticated`/свои permission-классы.
`tests/test_integration_contracts.py::test_guest_never_gets_403…` обходит все маршруты API.

### Ограничения модератора (TRUST-07, F14)
Единственная точка — `apps.trust.services.restrictions`:

| Функция | Когда вызывать | Ошибка |
|---|---|---|
| `require_can_publish(account)` | создание/изменение/публикация публично видимого: модели, варианты, медиа досок, мастерская, объявления инвентаря, карточка/предложения/слоты инструктора, программы и занятия школ, организации (create/manage/submit), события и анонсы клуба, отзывы, правки спотов, записи дневника `community`/`public` | 403 `account_restricted` |
| `require_can_message(account)` | сообщения, обращения, личные диалоги, приглашения в организацию | 403 `messaging_restricted` |
| `suspended_exists(account_ref)` / `restriction_exists(kinds, ref)` | фильтр queryset: профиль `suspended` скрыт во всех каталогах | — |

Разрешено и при ограничении: вход, свои данные, снятие своего контента с публикации, отмена своего события,
личный дневник, жалобы и апелляции. `messaging.services.safety.has_messaging_restriction` — тонкая обёртка.

### Видимость между приложениями — одно правило на сущность
* Инструктор: `learning.services.catalog.public_profiles()` / `is_profile_public()` — каталог, поиск, избранное,
  помощник, запись на частный слот, обращения (`commerce.resolve_target`).
* Владелец объявления: `inventory.services.rentals.visible_owner_q()` — `/rentals`, поиск, помощник, бронь аренды,
  обращения.
* Спот: `spots.services.catalog.is_public_spot()` (published/closed). Скрытый/черновой спот не показывается в
  карточках занятий, аренды, расписании школ. Карточки участников брони (commerce) спот показывают.
* Координаты спота вне `apps/spots` — только через `spots.services.catalog.public_coordinates(spot)` (SPT-12).
  Сейчас ни один сериализатор вне spots координат не отдаёт; регрессия —
  `test_sensitive_spot_coordinates_never_leak_outside_spots_app`.
* Медиа: `GET media/{id}[/url]` — `mediafiles.services.access.can_access`. Вложения чата — по
  `messaging.conversation_side` (текущее членство, AT-09), сертификаты — по `learning.is_scan_public`,
  фото дневника — по видимости записи (`community.diary.photo_visible_to`). Скан сертификата
  (`certificates/{id}/scan`) и подписи вложений чата идут через `access_url` / `get_storage().presigned_get`.
* Фото дневника — **публичные** файлы (`public/`, неугадываемый ключ, отдаются без presigned-ссылки), но
  метаданные и ссылка через media-эндпоинты выдаются только тем, кто видит запись.

### Уведомления
`Notification.Kind` (+миграция `messaging/0003`): добавлены `event_status` (отмена/перенос/восстановление события,
место из листа ожидания) и `product_available` (товар в продаже); оба с email по умолчанию. Старые записи `system`
остаются валидными. Статусы броней — только через `commerce.services.booking_transitions.notify_booking_status`
(есть `title/body/event_id/payload` для событий без смены статуса — перенос занятия). learning уведомляет клиентов
о переносе/отмене/проведении/неявке через неё.

### Блокировки
Порядок всегда «ресурс → бронь»: `LessonSession`/`InventoryItem` `select_for_update`, затем `Booking`
(commerce `booking_action`, inventory `record_handover`, learning `cancel_session/reschedule`, удаление аккаунта).
Проверка — `test_handover_and_confirm_lock_item_before_booking`.

### Наличие вариантов досок
`InventoryItem.save()/delete()` пересчитывают `BoardVariant.availability` сигналами. После `QuerySet.update()`/
`bulk_create()` по экземплярам — явный `refresh_variants(ids)` (так сделано в `boards.services.variants`).

### Idempotency-Key
`run_idempotent` сам берёт `pg_advisory_xact_lock`; ответ сохраняется кодировщиком DRF, повтор отдаёт тот же JSON
(порядок ключей jsonb не гарантирован). Гонка — `tests/test_idempotency.py`.

### Удаление аккаунта (AT-10)
`accounts.services.deletion.anonymize_account` дополнительно освобождает обязательства:
`commerce.cancel_for_deleted_account` (будущие брони клиента/исполнителя-аккаунта → `cancelled`, side `system`,
уведомление второй стороне), `learning.release_deleted_instructor` (частные слоты отменены, со школьных занятий
снят + уведомление менеджерам, лист ожидания закрыт), `club.release_deleted_account` (места уходят листу ожидания),
`community.purge_account_diary` (дневник и его фото удаляются), подписки магазина удаляются.
Заказы, обращения, сообщения, отзывы, журналы — сохраняются.

### OpenAPI
`docs/openapi.yml` — `make schema` (`spectacular --validate --fail-on-warn`). Перечисления с общими именами полей
(`status`, `kind`, `role`, …) — явные имена в `SPECTACULAR_SETTINGS["ENUM_NAME_OVERRIDES"]`; новое перечисление с
коллизией имени добавьте туда. operationId уникальны (`tests/test_openapi.py` падает на любом предупреждении).

## Тестовая инфраструктура (`backend/conftest.py`)
* Фикстуры: `api_client`, `user`, `auth_client`, `make_client(account=None, two_factor=False)`, `moderator`,
  `mod_client`, `run_on_commit`; autouse `memory_storage` (in-memory S3 + пустой кеш на каждый тест).
* **Transactional-тесты**: просто `transactional_db` или `@pytest.mark.django_db(transaction=True)`. Autouse
  `reference_data` + расширенный `django_db_setup` снимают снимок справочников data-миграций в начале сессии,
  восстанавливают его (flush без post_migrate → deserialize → `sequence_reset_sql` по всем моделям) перед каждым
  тестом после transactional-теста и в конце сессии; если БД осталась пустой после прерванного прогона —
  повторно выполняют RunPython data-миграций (они должны быть идемпотентными). Свои `preserved_reference_data` /
  сброс последовательностей в приложениях больше не нужны и удалены.
* Сквозные сценарии F01–F15 и AT-10 — `tests/test_flows.py`; контракты между приложениями —
  `tests/test_integration_contracts.py`, `tests/test_restrictions.py`, `tests/test_moderation_effects.py`.

## Продакшн-настройки
`APP_ENV=staging|prod`: обязательны `DJANGO_SECRET_KEY` (≥50 символов) и `DJANGO_DEBUG=0` (иначе
`ImproperlyConfigured`), secure-cookie, `SECURE_SSL_REDIRECT` (кроме `api/v1/health`), HSTS 1 год с поддоменами
(`SECURE_HSTS_PRELOAD` — отдельное решение, W021 приглушён), `CONN_HEALTH_CHECKS`, SMTP-учётка из
`EMAIL_HOST_USER/PASSWORD`, `EMAIL_USE_TLS/SSL`. В `prod` entrypoint не выполняет `seed_demo`.
Проверка: `APP_ENV=prod … python manage.py check --deploy` — без замечаний.
