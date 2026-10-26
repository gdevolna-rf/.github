# ГДеволна 2.0 — архитектура и контракт API

Документ — единый контракт для backend и frontend. Требования ссылаются на коды ТЗ (`docs/TZ.md`).
Модели данных — в `backend/apps/*/models.py` (источник правды по полям).

## 1. Стек и сервисы

| Сервис | Технология | Назначение |
|---|---|---|
| nginx | nginx 1.27 | Точка входа `http://localhost:8080`: `/api/`, `/admin/`, `/ws/` → backend; `/gdevolna-media/` → MinIO; остальное → Next.js |
| backend | Python 3.12, Django 5.2, DRF, drf-spectacular, Channels + Daphne | Единый API `/api/v1/`, WebSocket `/ws/events/`, Django Admin |
| celery-worker / celery-beat | Celery 5 + RabbitMQ, django-celery-beat | Фоновые и периодические задачи |
| postgres | PostgreSQL 17 (+ btree_gist) | Основные данные, exclusion-ограничения против пересечений |
| redis | Redis 7 | Кеш Django, channel layer, результаты Celery |
| minio | MinIO (S3) | Фото/видео/документы; публичный префикс `public/`, закрытый `private/` |
| mailpit | Mailpit | Перехват писем (http://localhost:8025) |
| frontend | Next.js 16 (App Router), React 19, TypeScript, TanStack Query, Zod, react-leaflet | SSR публичных страниц + клиентский кабинет |

Модульный монолит: каждое доменное приложение `backend/apps/<app>` содержит `models.py`, `services/` (бизнес-правила),
`serializers.py`, `views.py`, `urls.py`, `tasks.py` (Celery), `tests/`.

| App | Домен (раздел 6.1) |
|---|---|
| accounts | Identity: аккаунт, профиль, специальности, серверные роли, 2FA, согласия, экспорт/удаление |
| organizations | Организации, членства, приглашения |
| mediafiles | Медиаобъекты, presigned-загрузка, обработка |
| spots | Регионы, споты, фото, источники, прогнозы, предложения правок |
| learning | Инструкторы, сертификаты, предложения, программы школ, занятия, лист ожидания, заметки об учениках |
| boards | Мастерские, типы досок, материалы, модели, варианты, медиа досок |
| inventory | Физические экземпляры (продажа/аренда), акты выдачи/возврата |
| commerce | Обращения (inquiries), бронирования (bookings), история статусов, этапы |
| messaging | Диалоги, сообщения, вложения, read-курсоры, уведомления, настройки, блокировки, WebSocket |
| trust | Отзывы, очередь модерации, жалобы, ограничения, журнал аудита |
| analytics | События и метрики дашбордов |
| favorites | Избранное |
| community | GG Surfer: дневник катания, поздравления |
| club | События клуба, регистрации, анонсы |
| shop | Витрина мерча (без оплаты, M3) |
| search | Глобальный поиск и помощник подбора (rule-based) |

## 2. Соглашения API

- Базовый путь `/api/v1/`, **без завершающего слэша** (`APPEND_SLASH=False`). OpenAPI: `/api/v1/schema`, Swagger: `/api/v1/docs`.
- JSON, поля `snake_case`. Даты — ISO 8601 с часовым поясом. Деньги — строки-десятичные (`"65000.00"`) + `currency`.
- Аутентификация — сессия Django (cookie `sessionid`) + CSRF: клиент вызывает `GET /api/v1/auth/csrf`, затем шлёт
  заголовок `X-CSRFToken` со значением cookie `csrftoken` во всех небезопасных запросах.
- По умолчанию `IsAuthenticated`; публичные каталоги явно `AllowAny`/`ReadOnlyOrAuthenticated` (BR-01).
- Пагинация списков: `?page=&page_size=` (≤100) → `{"count", "next", "previous", "results"}`.
- Ошибки — единый формат (раздел 9):
  `{"error": {"code": "machine_code", "message": "Текст для пользователя", "fields": {"field": ["..."]}, "request_id": "..."}}`.
  Коды статусов: 400 валидация/бизнес-правило, 401 нет входа, 403 нет прав, 404, 409 конфликт (пересечение брони,
  дубль SKU, нет мест), 429 rate limit.
- Бизнес-правила проверяются только на сервере в `services/` и бросают `DomainError(code, message)`, `Forbidden`,
  `Conflict`, `NotFound` из `apps.common.exceptions`. Клиент не источник правды для цен, рейтингов, доступности (9.1).
- `Idempotency-Key` обязателен к поддержке для `POST /inquiries` и `POST /bookings` (`apps.common.idempotency`).
- IDOR: queryset всегда фильтруется по правам текущего пользователя; закрытые медиа — только через `GET /media/{id}/url`.
- Публичные сериализаторы никогда не отдают email, телефон, дату рождения, закрытые контакты, документы (ACC-14).
- Rate limit: DRF throttling; scope `auth` (вход/регистрация/сброс), `messages`, `uploads`, `reports`.

### Сквозные сервисы (использовать, не дублировать)

| Функция | Где | Назначение |
|---|---|---|
| `record(actor, action, obj, before=, after=, organization=, request=)` | `apps.trust.services.audit` | Журнал аудита — в той же транзакции |
| `notify(recipient, kind, title, body, link, payload, event_id, actor)` | `apps.messaging.services.notify` | In-app уведомление (уникальный event_id) + WS + email по настройкам |
| `push_to_user(account_id, payload)` | `apps.messaging.services.realtime` | WS-событие после коммита |
| `track(name, ...)`, `track_view(name, request, ...)` | `apps.analytics.services` | События аналитики с дедупликацией |
| `member_role / require_role / can_manage / staff_accounts` | `apps.organizations.services.access` | Права в организации |
| `has_specialty / require_specialty` | `apps.accounts.services.specialties` | Подключённые направления |
| `has_role / has_verified_staff_role` | `apps.accounts.services.roles` | Серверные роли + 2FA в сессии |
| `IsModerator`, `IsPlatformAdmin` | `apps.common.permissions` | DRF-permission для модерации/админки |
| `claim_media(media_id, account, purposes=, kinds=)` | `apps.mediafiles.services` | Привязка загруженного файла |
| `run_idempotent`, `IdempotentCreateMixin` | `apps.common.idempotency` | Idempotency-Key |
| `require_can_publish / require_can_message / suspended_exists` | `apps.trust.services.restrictions` | Ограничения модератора во всех приложениях (403 `account_restricted` / `messaging_restricted`) |
| `public_coordinates(spot)`, `is_public_spot(spot)` | `apps.spots.services.catalog` | Координаты (SPT-12) и видимость спота в чужих карточках |
| `notify_booking_status(booking, actor, …)` | `apps.commerce.services.booking_transitions` | Уведомления о бронях (commerce, inventory, learning) |
| `public_profiles()`, `visible_owner_q()` | `apps.learning.services.catalog`, `apps.inventory.services.rentals` | Видимость инструкторов и владельцев объявлений во всех каталогах |

### WebSocket `/ws/events/`

Один персональный канал на пользователя (сессионная cookie). Сервер → клиент:

```json
{"type": "message.new", "conversation_id": "…", "message": {…}}
{"type": "conversation.read", "conversation_id": "…", "account_id": "…", "last_read_at": "…"}
{"type": "notification.new", "notification": {"id", "kind", "title", "body", "link"}}
{"type": "counters", "counters": {"unread_messages": 2, "unread_notifications": 1, "new_inquiries": 1, "pending_bookings": 0}}
{"type": "inquiry.updated", "inquiry_id": "…", "status": "in_progress"}
{"type": "booking.updated", "booking_id": "…", "status": "confirmed"}
```
Клиент → сервер: `{"type": "ping"}`. WS — только ускоритель; источник правды — REST (`GET /me/counters`).

### Медиа (DATA-04, 9.1, ATX-24)

1. `POST /media/uploads {kind, purpose, filename, content_type, size}` → проверка типа/размера (`MEDIA_LIMITS`),
   создание `MediaAsset(status=pending)` и presigned PUT URL (15 мин) на origin запроса.
2. Браузер делает `PUT upload_url` напрямую в MinIO (через nginx, файл не проходит через Django).
3. `POST /media/{id}/complete` → проверка объекта (HEAD: размер, тип) → `processing` → Celery: проверка сигнатуры
   (magic bytes / Pillow), WebP-миниатюра для изображений → `ready` или `rejected`.
4. Публичные файлы отдаются по `/gdevolna-media/public/...`; закрытые (`private/`, сертификаты, вложения чата,
   выгрузки) — только `GET /media/{id}/url` (presigned GET на 2 мин после проверки прав).

## 3. Каталог эндпоинтов `/api/v1/`

Обозначения доступа: **all** — все, **auth** — вошедший, **owner** — владелец объекта, **org:roles** — активное членство,
**mod** — модератор с 2FA в сессии, **admin** — администратор с 2FA.

### accounts
| Метод и путь | Доступ | Поведение |
|---|---|---|
| GET `auth/csrf` | all | Ставит cookie `csrftoken` |
| POST `auth/register` | all | `{email, password, first_name, last_name, primary_type: surfer\|instructor\|shaper\|school\|rental, extra_specialties[], accept_terms, accept_privacy}` → создаёт Account + Profile + специальности (school → только surfer + `next_step:"create_school"`), согласия, письмо подтверждения; логинит. ATX-01 |
| POST `auth/login` / `auth/logout` | all / auth | Сессия |
| POST `auth/verify-email` `{token}`, `auth/verify-email/resend` | all / auth | Подтверждение адреса (5.3) |
| POST `auth/password-reset` `{email}`, `auth/password-reset/confirm` `{uid, token, new_password}` | all | Восстановление (ACC-13) |
| POST `auth/password-change` | auth | |
| POST `auth/2fa/verify` `{code}` | auth | TOTP → отметка сессии (для mod/admin) |
| GET/PATCH `me` | auth | Свой аккаунт: профиль (вкл. закрытые поля), специальности, роли, организации, `two_factor` |
| GET `me/counters` | auth | `{unread_messages, unread_notifications, new_inquiries, pending_bookings}` |
| PUT/DELETE `me/specialties/{code}` | auth | Подключить/отключить направление; отключение не удаляет историю, возвращает `warnings` об активных бронях/публикациях (BR-11, 7.1) |
| POST `me/2fa/setup`, `me/2fa/enable`, `me/2fa/disable` | auth | TOTP (pyotp) |
| GET/POST `me/consents` | auth | Журнал согласий |
| POST/GET `me/exports` | auth | Выгрузка данных JSON (Celery → закрытый файл) |
| POST/GET/DELETE `me/deletion` | auth | Запрос удаления с отсрочкой; Celery анонимизирует, сохраняя заказы/журналы (AT-10) |
| GET `profiles/{handle}` | all | Публичный профиль; старый handle → `{"redirect": "<new>"}` |
| GET/POST/DELETE `staff/roles` | admin | Выдача/отзыв модератора (BR-04) |

### organizations
| Метод и путь | Доступ | Поведение |
|---|---|---|
| GET `organizations?kind=&region=&q=` | all | Опубликованные |
| GET `organizations/{slug}` | all | Публичная карточка (школа: программы, ближайшие занятия со свободными местами, команда, споты, рейтинг) |
| POST `organizations` | auth | Создать; создатель = owner. workshop требует направление shaper |
| GET `me/organizations` | auth | Мои членства |
| GET/PATCH `organizations/{id}/manage` | org:owner,manager | Закрытая карточка, редактирование |
| POST `organizations/{id}/submit` | org:owner | На проверку перед публикацией → ModerationCase (SCH-13) |
| GET `organizations/{id}/members` | org:any | Команда |
| PATCH/DELETE `organizations/{id}/members/{membership_id}` | org:owner | Смена роли / отзыв доступа (немедленно, история сохраняется; AT-09, F15, ATX-18) |
| POST/GET `organizations/{id}/invites`, DELETE `invites/{id}` | org:owner,manager (manager — только instructor/staff) | Приглашение по email на аккаунт |
| GET `me/invites`, POST `invites/{token}/accept`, `invites/{token}/decline` | auth (адресат) | Роль активируется только после принятия |
| POST `organizations/{id}/transfer-ownership` `{account_id}` | org:owner | Передача владения активному участнику |
| POST `organizations/{id}/leave` | org:non-owner | |

### mediafiles
`POST media/uploads`, `POST media/{id}/complete`, `GET media/{id}`, `GET media/{id}/url`, `DELETE media/{id}` — см. §2.

### spots
| Метод и путь | Доступ | Поведение |
|---|---|---|
| GET `regions` | all | |
| GET `spots?region=&difficulty=&bottom=&break=&q=` | all | Опубликованные; координаты чувствительных спотов округляются (SPT-12) |
| GET `spots/map` | all | Лёгкие маркеры для карты (кеш Redis) |
| GET `spots/{slug}` | all | Детальная карточка: типичные условия отдельно от прогноза, источники, дата подтверждения, рейтинг |
| GET `spots/{slug}/forecast` | all | Прогноз провайдера или `{"provider": null}` (GEO-04) |
| POST `spots/{id}/proposals` | auth | `{changes: {field: new}, comment, source, evidence_ids[]}` — только `EDITABLE_SPOT_FIELDS`; diff «было → стало» сохраняется (SPT-07/08) |
| GET `me/proposals`, PATCH `proposals/{id}`, POST `proposals/{id}/withdraw` | owner | Ответ на `needs_info`, отзыв |

### trust (отзывы, модерация, жалобы)
| Метод и путь | Доступ | Поведение |
|---|---|---|
| GET `reviews?target_type=&target_id=` | all | Только published (BR-08) |
| POST `reviews` | auth | Создать/заменить свой отзыв `{target_type, target_id, rating, text, photo_ids}`; правка опубликованного → pending-ревизия, повтор не увеличивает число голосов; запрет на себя/свою организацию (BR-05, ATX-26); инструктор/организация — только после завершённого заказа/занятия |
| GET `me/reviews`, DELETE `reviews/{id}` | owner | |
| POST `complaints`, GET `me/complaints`, POST `complaints/{id}/appeal` | auth | Жалобы и апелляции (TRUST-07) |
| GET `moderation/cases?kind=&status=` , GET `moderation/cases/{id}` | mod | Единая очередь (TRUST-04) |
| POST `moderation/proposals/{id}/approve\|reject\|request-info\|revert` | mod | approve: обновление спота + AuditEvent + уведомление автору в одной транзакции (7.4, AT-07, F08) |
| POST `moderation/reviews/{id}/approve\|reject\|hide` | mod | Пересчёт рейтинга цели в транзакции (AT-08, F09) |
| POST `moderation/certificates/{id}/approve\|reject` | mod | Бейдж «проверен» только после решения (BR-07, F04, ATX-05) |
| POST `moderation/organizations/{id}/approve\|reject` | mod | Публикация школы/мастерской |
| POST `moderation/complaints/{id}/resolve` `{action, note}`, `dismiss` | mod | Скрыть объявление/ограничить профиль + журнал (F14) |
| GET `moderation/audit?object_type=&object_id=&actor=` | mod | Журнал |
| GET `moderation/stats` | mod | Скорость модерации (spot_proposal_reviewed) |

### learning
| Метод и путь | Доступ | Поведение |
|---|---|---|
| GET `instructors?region=&spot=&level=&board_type=&format=&price_max=&certificate=&date=&rating_min=&q=` | all | INS-09 |
| GET `instructors/{handle}` | all | Профиль, предложения, свободные слоты, школы, бейдж сертификата |
| GET/PUT `me/instructor`, POST `me/instructor/publish\|unpublish` | auth+instructor | Публикация после обязательных полей; сертификат не обязателен (F03, ATX-04, ACC-15) |
| POST/DELETE/PATCH `me/instructor/media...` | owner | Фото/видео (INS-12) |
| POST/GET/DELETE `me/instructor/certificates` | owner | Загрузка → ModerationCase; скан закрытый (INS-04) |
| GET `certificates/{id}/scan` | all если проверен и разрешён показ, иначе владелец/mod | presigned URL |
| CRUD `me/instructor/offers` | owner | INS-08 |
| CRUD `me/instructor/sessions` | owner | Слоты частных занятий; конфликт с уроками школ → 409 (F11) |
| GET `me/schedule?from=&to=` | auth | Все занятия, где я инструктор: школы + частные (INS-07, AT-06) |
| GET `me/students` | instructor | Уникальные/повторные ученики, заметки |
| CRUD `organizations/{id}/programs` | org:owner,manager | SCH-04 |
| CRUD `organizations/{id}/sessions`; POST `sessions/{id}/assign\|reschedule\|cancel\|complete` | org:owner,manager (assigned instructor — complete) | Назначение только активному инструктору школы; конфликт → 409; перенос уведомляет записанных (SCH-05/06) |
| GET `sessions/{id}` | all | Публичная карточка занятия с числом свободных мест |
| POST/DELETE `sessions/{id}/waitlist` | auth | SCH-08 |
| GET `organizations/{id}/students`, CRUD `student-notes` | org staff / автор | SCH-10 |

### boards
| Метод и путь | Доступ | Поведение |
|---|---|---|
| GET `boards?type=&region=&shaper=&length_min=&length_max=&volume_min=&volume_max=&price_max=&availability=&material=&repair=&q=` | all | «Все доски» (SHP-07, NAV-02) |
| GET `shapers?region=&repair=&q=` | all | «По шейперам» с несколькими моделями в карточке (SHP-08/09) |
| GET `shapers/{slug}`, GET `shapers/{slug}/boards` | all | Профиль мастерской (промо-видео, услуги, ремонт) |
| GET `boards/{id}` | all | Модель + варианты + медиа + наличие |
| GET/PUT `me/workshop` | auth+shaper | Создание/редактирование мастерской («Зарегистрироваться как шейпер» / «Сохранить изменения», SHP-01) |
| CRUD `workshops/{id}/board-types`, `workshops/{id}/materials` | org:workshop staff | Пользовательские типы и материалы появляются в селекте моделей (SHP-05, ATX-07) |
| CRUD `workshops/{id}/models`, POST `models/{id}/publish\|unpublish` | org:workshop staff | «Мои доски» — единственное место управления (BRD-01) |
| POST/PATCH/DELETE `models/{id}/media...` | staff | ≤10 фото, обложка, порядок, отдельное видео (BRD-03, ATX-06) |
| CRUD `models/{id}/variants`, PATCH `workshops/{id}/variants/bulk` | staff | SKU генерируется сервером: `{КОД}-{ТИП}-{ДЛИНА}-{ШИРИНА}[-суффикс]`, уникален (BRD-05, ATX-08); изменение размеров варианта с заказами → новая версия (F10) |

### inventory
| Метод и путь | Доступ | Поведение |
|---|---|---|
| GET `rentals?kind=&region=&spot=&organization=&owner=&from=&to=&price_max=&q=` | all | RENT-01; при from/to — только свободные; `organization` — slug или id организации-владельца |
| GET `rentals/{id}` | all | + занятые интервалы (подтверждённые) |
| CRUD `me/inventory` (+ `?organization=`) | rental-направление или сотрудник организации | RENT-02 |
| GET `me/inventory/availability?from=&to=` | owner | «Свободных бордов» / «Забронировано» (RENT-03/04) |
| POST `bookings/{id}/handover` | provider | Акт выдачи/возврата, повреждения (RENT-06) |

### commerce
| Метод и путь | Доступ | Поведение |
|---|---|---|
| POST `inquiries` (Idempotency-Key) | auth, не к себе | `{kind, target_type, target_id \| provider_account_id \| provider_organization_id, message, details}`: создаёт обращение + диалог + первое сообщение + уведомления сотрудникам + `inquiry_created` (MSG-03/09, AT-01, AT-03, SHP-11) |
| GET `inquiries?box=incoming\|outgoing&role=customer\|shaper\|school\|instructor\|rental&status=&organization=` | auth | Единый inbox с `unread_count`, последним сообщением, карточкой контекста (MSG-01/02/08, ATX-27) |
| GET `inquiries/{id}` | участник | |
| POST `inquiries/{id}/accept\|decline\|complete\|cancel` | provider / customer (cancel) | Машина состояний 7.2; complete принимает `agreed_amount`, `amount_confirmed` (MET-07, ATX-29) |
| CRUD `inquiries/{id}/milestones`, POST `milestones/{id}/done\|confirm` | provider / customer | SHO-06 |
| POST `bookings` (Idempotency-Key) | auth, не к себе | Занятие `{lesson_session_id, seats, participant_name, participant_is_minor, guardian_consent}` или аренда `{inventory_item_id, starts_at, ends_at}`; `group_key` для связанных броней (F06); статус requested |
| POST `bookings/{id}/confirm` | provider / org staff / назначенный инструктор | В транзакции: `select_for_update` занятия, проверка вместимости; для аренды — exclusion-ограничение → 409 (AT-05, F07, ATX-14/16) |
| POST `bookings/{id}/decline\|start\|complete\|no-show\|cancel` | по 7.3 | cancel освобождает ресурс, уведомляет стороны, `booking_cancelled` с причиной и стороной (F13) |
| GET `bookings?box=mine\|provider&status=&from=&to=&organization=` , GET `bookings/{id}` | участник | |

### messaging
| Метод и путь | Доступ | Поведение |
|---|---|---|
| GET `conversations/{id}`, GET `conversations/{id}/messages?before=&limit=` | участник | |
| POST `conversations/{id}/messages` `{body, attachment_ids[], client_id}` | участник | Разрешено до принятия обращения (BR-06); запрещено при declined/cancelled, блокировке, ограничении messaging |
| POST `conversations/{id}/read` | участник | Read-курсор; WS `conversation.read` + `counters` на все устройства (AT-04, ATX-10) |
| POST `direct-conversations` `{account_id}` | auth | GG Surfer: с учётом `gg_contact_policy` и блокировок |
| GET `me/notifications?unread=`, POST `me/notifications/{id}/read`, `me/notifications/read-all` | owner | |
| GET/PUT `me/notification-preferences` | owner | MSG-12 |
| GET `me/blocks`, POST `blocks`, DELETE `blocks/{account_id}` | auth | COM-07 |

### favorites, analytics, community, club, shop, search
| Метод и путь | Доступ | Поведение |
|---|---|---|
| GET `me/favorites?type=`, GET `me/favorites/ids`, POST `favorites`, DELETE `favorites/{target_type}/{target_id}` | auth | Все типы (MSG-11, ATX-11) |
| POST `analytics/views` `{subject_type, subject_id}` | all | Квалифицированный просмотр (track_view) |
| GET `me/metrics?scope=shaper\|instructor\|school\|rental\|surfer&organization_id=&from=&to=` | owner/org staff | Формулы 10.1, MET-01…07 |
| GET `surfers?region=&spot=&level=&q=`, GET `surfers/{handle}` | all (только с согласием GG Surfer) | COM-02/03 |
| CRUD `me/diary`, GET `me/diary/stats`, GET `surfers/{handle}/diary` | owner / по видимости | COM-04/06, MET-06 |
| GET `club`, GET `club/events`, GET `club/events/{slug}`, POST/DELETE `club/events/{id}/registration` | all / auth | CLB-01/02 |
| CRUD `club/manage/events`, `club/manage/announcements` | organizer/admin | CLB-03 |
| GET `shop/products`, GET `shop/products/{slug}`, POST/DELETE `shop/products/{id}/interest` | all / auth | SHOP-02 (без оплаты) |
| GET `search?q=&types=` | all | Споты, инструкторы, школы, доски, оборудование, участники (NAV-04) |
| POST `assistant/board-size`, POST `assistant/recommend` | all | Rule-based подбор с источниками и оговорками (AIX-01…03) |

## 4. Машины состояний

- Inquiry (7.2): `new → in_progress → completed`; `new|in_progress → declined` (исполнитель); `new|in_progress → cancelled` (клиент).
  Непрочитанность — не статус: считается по read-курсорам участников.
- Booking (7.3): `requested → confirmed|declined|cancelled`; `confirmed → in_progress|cancelled|no_show`; `in_progress → completed`.
  Аренда: `in_progress` = «выдано», `completed` = «возвращено»; просрочка — флаг `is_overdue` (Celery beat).
- LessonSession: `scheduled → in_progress → completed`, `scheduled → cancelled`; перенос меняет время с проверкой пересечений.
- SpotChangeRequest (7.4): `submitted → needs_info|approved|rejected|withdrawn`, `needs_info → submitted|withdrawn`.
- Review: `pending → published|rejected`, `published → hidden`; правка published хранится как pending-ревизия.
- Certificate: `uploaded → verified|rejected`, `verified → revoked`.
- Organization: `draft → pending_review → published|draft`, `published → suspended` (модератор).
Каждый переход пишет историю (`*StatusChange`) и/или `AuditEvent`, рассылает уведомления и WS-события.

## 5. Периодические задачи (django-celery-beat)

Регистрируются командой `python manage.py setup_periodic_tasks` (вызывается в entrypoint после миграций).

| Задача | Расписание | Что делает |
|---|---|---|
| `mediafiles.cleanup_expired_uploads` | каждый час | Удаляет pending-загрузки с истёкшей ссылкой |
| `commerce.expire_stale_booking_requests` | каждые 15 мин | Запросы старше `BOOKING_REQUEST_TTL_HOURS` или начавшиеся → cancelled (side=system) |
| `commerce.mark_overdue_rentals` | каждые 15 мин | Выданная аренда после `ends_at` → `is_overdue` + уведомление |
| `learning.send_lesson_reminders` | каждый час | За 24 ч до занятия — клиентам и инструктору |
| `club.send_event_reminders` | каждый час | За 24 ч до события |
| `community.send_birthday_greetings` | ежедневно 09:00 | Только при согласии; дата не раскрывается (COM-05, ATX-34) |
| `accounts.process_deletion_requests` | ежедневно 03:00 | Анонимизация по истечении отсрочки |
| `organizations.expire_invites` | ежедневно | |
| `trust.recalculate_ratings` | ежедневно 04:00 | Контрольный пересчёт агрегатов по published-отзывам |
| `spots.refresh_forecasts` | каждые 3 ч | Через провайдера `FORECAST_PROVIDER` (по умолчанию `none` — без внешних запросов) |

## 6. Аналитика (раздел 10)

События: `profile_viewed`, `board_viewed`, `spot_viewed`, `organization_viewed`, `item_viewed` (квалифицированные просмотры
через `track_view`: без ботов, самопросмотров, повторов зрителя за сутки), `inquiry_created`, `booking_confirmed`,
`booking_cancelled` (context: reason, side), `session_completed`, `review_published`, `spot_proposal_reviewed`
(context: hours_from_submitted), `deal_completed` (context: amount, confirmed).

Формулы (10.1): конверсия = уникальные обращения / квалифицированные просмотры × 100%; заполняемость = подтверждённые места /
доступные места × 100%; повторные ученики = ученики с ≥2 завершёнными / ученики с ≥1 завершённым × 100%; средняя оценка —
только published-отзывы; выручка — только `amount_confirmed` завершённых сделок (MET-07, ATX-29). `rule_version` в событиях.

## 7. Тесты

- Backend: `docker compose run --rm -e TEST_DB_NAME=test_<имя> backend pytest apps/<app>` (pytest + pytest-django +
  factory_boy; общие фабрики `backend/tests/factories.py`, фикстуры `backend/conftest.py`: `api_client`, `make_client(account, two_factor=False)`).
- Frontend unit: `cd frontend && npm test` (Vitest + Testing Library).
- E2E: `cd e2e && npx playwright test` против поднятого `docker compose` (http://localhost:8080).

## 8. Демо-данные

`python manage.py seed_demo` — посевные данные из прототипа v14 (споты, регионы, демо-аккаунты специалистов, школы,
мастерские, модели досок, аренда, события клуба). Все записи помечены `is_demo=True`. Отзывы, обращения, сообщения,
статистика и сертификаты из прототипа **не переносятся** как реальные (PL-02, 12.2, ATX-33). Демо-аккаунты для ручной
проверки перечислены в README.

## 9. Маршруты фронтенда (для ссылок в уведомлениях, поиске, sitemap)

| Путь | Экран |
|---|---|
| `/` | Главная |
| `/spots`, `/spots/{slug}` | Карта и каталог спотов, карточка спота |
| `/instructors`, `/instructors/{handle}` | Каталог инструкторов, профиль |
| `/schools`, `/schools/{slug}` | Сёрф-школы, карточка школы |
| `/sessions/{id}` | Занятие (запись) |
| `/shapers?tab=boards\|shapers`, `/shapers/{slug}`, `/boards/{id}` | Каталог досок и шейперов, профиль мастерской, модель |
| `/rentals`, `/rentals/{id}` | Аренда |
| `/gg`, `/surfers/{handle}` | GG Surfer |
| `/club`, `/club/events/{slug}` | Клуб и события |
| `/shop`, `/shop/{slug}` | Мерч |
| `/search?q=` , `/assistant` | Поиск, помощник подбора |
| `/login`, `/register`, `/verify-email?token=`, `/reset-password?uid=&token=`, `/invites/{token}` | Аутентификация, приглашения |
| `/account` | Обзор кабинета |
| `/account/profile`, `/account/settings`, `/account/specialties` | Профиль, настройки (приватность, уведомления, 2FA, экспорт, удаление), «Мои направления» |
| `/account/inquiries`, `/account/inquiries/{id}` | Обращения (единый inbox + чат) |
| `/account/bookings`, `/account/bookings/{id}` | Мои бронирования / бронирования исполнителя (`?box=provider`) |
| `/account/favorites`, `/account/notifications`, `/account/proposals`, `/account/reviews`, `/account/invites`, `/account/diary` | Избранное, уведомления, мои правки спотов, отзывы, приглашения, дневник |
| `/account/instructor/...` | Кабинет инструктора: `profile`, `offers`, `schedule`, `students`, `certificates`, `stats` |
| `/account/shaper/...` | Кабинет шейпера: панель, `boards`, `workshop`, `stats` |
| `/account/rental/...` | Прокат: `inventory`, `bookings` |
| `/account/orgs`, `/account/orgs/{id}/...` | Организации; кабинет школы: `profile`, `programs`, `schedule`, `students`, `team`, `equipment`, `inquiries`, `analytics`, `reviews` |
| `/moderation`, `/moderation/cases/{id}`, `/moderation/audit` | Модерация (только серверная роль + 2FA) |
