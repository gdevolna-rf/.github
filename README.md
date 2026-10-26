# ГДеволна 2.0 — Гдеволна.рф

Единая платформа для сёрфинга в России: споты и карта, инструкторы, сёрф-школы, шейперы и доски, аренда,
обращения с чатом, бронирования без конфликтов, модерация, отзывы, GG Surfer, клуб.
Реализация ТЗ v0.2 (`docs/TZ.md`) с визуальным референсом прототипа v12/v14 (`docs/prototype/`).

## Быстрый старт

```bash
cp .env.example .env          # необязательно: значения по умолчанию подходят для локального запуска
docker compose up -d --build  # production-сборка: код в образах, Next.js standalone (то же, что make up)
make dev                      # режим разработки: исходники смонтированы, Next.js dev server с hot reload
```

Первый старт занимает несколько минут (сборка образов, миграции, загрузка посевных данных в MinIO).

| Что | Адрес |
|---|---|
| Сайт | http://localhost:8080 |
| API (OpenAPI / Swagger) | http://localhost:8080/api/v1/schema · http://localhost:8080/api/v1/docs |
| Django Admin (нужна 2FA) | http://localhost:8080/admin/ |
| Почта (Mailpit) | http://localhost:8025 |
| RabbitMQ | http://localhost:15672 (gdevolna / gdevolna) |
| MinIO console | http://localhost:9001 (gdevolna / gdevolna-secret) |

При первом старте backend применяет миграции, создаёт бакет, регистрирует периодические задачи и загружает
посевные данные из прототипа (`SEED_DEMO=1`). Демо-аккаунты (пароль `Demo-2026!`) и что на них проверять —
в `docs/DEMO_DATA.md`. Модератор/админ входят с TOTP: секрет `JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP`
(добавьте в любое приложение-аутентификатор).

## Архитектура

| Сервис | Технология |
|---|---|
| nginx | единая точка входа: `/api`, `/ws`, `/admin` → Django; `/gdevolna-media` → MinIO; остальное → Next.js |
| frontend | Next.js 16 (App Router, SSR публичных страниц), React 19, TypeScript, TanStack Query, Zod, Leaflet + OSM |
| backend | Python 3.12, Django 5.2, DRF, drf-spectacular, Channels + Daphne (WebSocket) |
| celery-worker, celery-beat | Celery 5 + RabbitMQ, расписания в django-celery-beat |
| postgres | PostgreSQL 17 (exclusion-ограничения против двойных броней и пересечений занятий) |
| redis | кеш, channel layer, результаты Celery |
| minio | объектное хранилище медиа (presigned-загрузка напрямую из браузера) |
| mailpit | перехват писем в dev |

Подробно: `docs/ARCHITECTURE.md` (контракт API, машины состояний, периодические задачи, маршруты),
`docs/dev/BACKEND_GUIDE.md`, `docs/dev/FRONTEND_GUIDE.md`, `docs/dev/INTEGRATION_NOTES.md`, `docs/openapi.yml`.

## Тесты

```bash
make test-backend    # pytest: 1093 теста — бизнес-правила, API, права, гонки, сквозные сценарии F01–F15 и AT-10
make test-frontend   # Vitest + Testing Library (143 теста) и проверка типов — в одноразовом контейнере node
make test-e2e        # Playwright в контейнере против запущенного стенда: 18 сценариев пользователя + мобильный
```

E2E покрывают: просмотр каталогов гостем (BR-01, ATX-02), карточку спота с розами ветра/свелла (SPT-04), отсутствие
горизонтальной прокрутки на 320–430 px (ATX-19), регистрацию с подтверждением email через Mailpit, заявку на доску
с чатом до принятия и синхронизацией непрочитанных между устройствами (AT-01, AT-04, ATX-09/10), запрет заявки самому
себе (AT-03), запись на занятие и подтверждение инструктором (F03), блокировку пересечения занятий инструктора (AT-06),
модерацию правки спота с TOTP-входом модератора и журналом (AT-07), гонку двух броней одной доски (AT-05), немедленный
отзыв прав менеджера школы (AT-09) и нижнюю мобильную навигацию (NAV-03). С хоста: `cd e2e && npm ci && npx playwright test`.

## Эксплуатация

```bash
make backup          # pg_dump в ./backups
make restore-check   # тренировочное восстановление в отдельную БД и сверка (ATX-30)
make seed-reset      # пересоздать демо-данные
make logs | make ps | make down
```

Продакшен-отличия (TLS, секреты, `APP_ENV=prod`, внешний S3/SMTP, отключение демо-данных) — `docs/OPERATIONS.md`.
