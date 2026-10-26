# Frontend: правила разработки

Читать вместе с `docs/ARCHITECTURE.md` (контракт API, маршруты §9), `docs/TZ.md` (коды требований) и
`docs/prototype/*` (утверждённый дизайн). Дизайн утверждён (PL-01, UX-01, DSN-09): **не редизайним** — используем
классы прототипа и токены, новые компоненты делаем в том же языке.

Стек: Next.js 16.4 (App Router, Turbopack), React 19.3, TypeScript 5.9 strict, TanStack Query 5, Zod 4,
react-leaflet 5 + markercluster, Vitest 3 + Testing Library. **Новые npm-пакеты не добавлять** без согласования.

## 1. Запуск и команды

```bash
docker compose up -d                       # http://localhost:8080 (nginx → next dev / Django / MinIO)
docker compose logs -f frontend
docker compose restart frontend            # см. «Docker и новые файлы» ниже
cd frontend && npm test                    # Vitest (jsdom)
cd frontend && npm run typecheck           # tsc --noEmit
cd frontend && npx next build              # прод-сборка (backend недоступен с хоста → страницы берут заглушки)
```

- **Docker и новые файлы.** На macOS Docker Desktop не всегда пробрасывает события ФС: правки существующих файлов
  подхватываются, а **новый маршрут/файл может отдавать 404 или «Module not found»** — выполните
  `docker compose restart frontend`. Polling не включаем (рекомендация Next).
- **Страница бесконечно перезагружается** (в консоли браузера циклом «[Fast Refresh] rebuilding», в логе
  «Compiled in …» на каждый запрос) — испорчен кеш Turbopack после пересоздания контейнера:
  `docker compose exec frontend rm -rf /app/.next/dev && docker compose restart frontend`.
- `/dev/ui` — живой каталог UI-кита (только dev; в прод-сборке 404, `SHOW_UI_KIT=1` открывает на стенде).
- Демо-аккаунты: `docs/DEMO_DATA.md` (пароль `Demo-2026!`), например `surfer@demo.gdevolna.local`,
  `ivan.petrov@demo.gdevolna.local` (инструктор + шейпер + 2 организации).
- Next 16: `params`/`searchParams` в page/layout — **Promise** (`const { slug } = await params`); `error.tsx`
  получает `retry()`; `middleware` переименован в `proxy` (у нас его нет). Документация версии —
  `frontend/node_modules/next/dist/docs/`.

## 2. Структура

```
frontend/src/
  app/                      маршруты (App Router)
    layout.tsx              корневой: шапка, main#app, подвал, нижняя навигация, провайдеры
    page.tsx                Главная (Server Component, ISR 5 мин)
    login|register|verify-email|reset-password|invites/[token]   аутентификация
    account/layout.tsx      кабинет: RequireAuth + AccountShell (меню, герой)
    account/**/page.tsx     разделы кабинета (сейчас заглушки AccountPlaceholder — заменить)
    moderation/page.tsx     модерация (заглушка, staff)
    sitemap.ts robots.ts not-found.tsx error.tsx global-error.tsx loading.tsx icon.svg
    dev/ui/page.tsx         UI-кит (dev)
  components/
    ui/                     UI-кит (barrel: `@/components/ui`)
    layout/                 SiteHeader, MobileTabBar, CatalogSheet, SearchDialog, SiteFooter, AccountShell, PageBlocks
    auth/                   RequireAuth, LoginPrompt (useRequireAuth), формы входа/регистрации/сброса
    home/                   блоки главной
    account/                экраны кабинета (AccountOverview)
    providers.tsx           QueryClient, тосты, LoginPrompt, realtime
  lib/
    api/client.ts           браузерный fetch-клиент /api/v1 (CSRF, ApiError, ретраи, Idempotency-Key)
    api/server.ts           серверный fetch для Server Components (INTERNAL_API_URL, ISR)
    api/errors.ts types.ts keys.ts
    api/<domain>.ts         функции API домена: auth.ts, favorites.ts, media.ts, …  ← добавляйте свои
    auth/hooks.ts           useMe, useCounters, useLogin/useLogout/useRegister
    favorites/hooks.ts      useFavoriteIds, useIsFavorite, useToggleFavorite
    realtime/               WebSocket-клиент и useRealtime/useRealtimeEvent
    hooks/                  useOnlineStatus, useSearchParamModal
    format.ts labels.ts     форматирование и единый словарь статусов/подписей
    routes.ts               маршруты и навигация (единственный источник путей)
    seo.ts forms.ts schemas/ embed.ts cx.ts account-nav.ts
  styles/                   tokens.css public.css cabinet.css shapers.css app.css (подключены в app/globals.css)
  test/                     утилиты тестов (mockApi, renderWithProviders, мок next/navigation)
frontend/public/brand|ui    логотип, лоадер, фото и иллюстрации бренда (ASSETS.md: только «бренд/UI»)
frontend/scripts/           gen_icons.py (реестр иконок), port_prototype_css.py / port_assets.py (как получены стили и ассеты)
```

## 3. Модель рендеринга

| Где | Как | Данные |
|---|---|---|
| Публичные страницы (`/spots`, `/instructors/[handle]`, `/schools/…`, `/shapers`, `/boards/[id]`, `/rentals`, `/club`, `/gg`) | **Server Component** + клиентские «острова» (`"use client"` только там, где состояние/события) | `serverFetch` / `serverFetchSafe` из `lib/api/server.ts` с `revalidate` (ISR) и `tags` |
| Кабинет `/account/**`, модерация | **Client Components** внутри `AccountShell` (он уже делает RequireAuth) | TanStack Query + `api` из `lib/api/client.ts` |
| Фильтры/сортировки каталогов | URL-параметры (`searchParams` на сервере, `useSearchParams`/`router.replace` в острове) — ссылки шарятся и индексируются | |

- Никогда не тянуть приватные данные в Server Components (cookie не пробрасываются). Всё, что про текущего пользователя
  (избранное, «моё», счётчики), — на клиенте.
- `useSearchParams()` на статических страницах требует `<Suspense>` выше по дереву (иначе сборка упадёт).
- Деталь-модалки с адресом (SHP-10, UX-12): либо `useSearchParamModal("profile")` (параметр в URL, «Назад» закрывает),
  либо intercepting route `app/shapers/@modal/(.)[slug]/page.tsx` + `<RouteModal>` (канонический URL `/shapers/[slug]`
  остаётся отдельной SEO-страницей).
- Карта: `react-leaflet` только в клиентском компоненте, подключать через `next/dynamic(..., { ssr: false })`,
  стили — `import "leaflet/dist/leaflet.css"` и `leaflet.markercluster/dist/MarkerCluster*.css` внутри компонента карты.
- Изображения: обычный `<img loading="lazy">` или `<MediaImage>` (WebP-миниатюры делает backend, `images.unoptimized`).

## 4. Данные и API

### 4.1 Где лежат функции API

Каждый домен — свой файл `src/lib/api/<domain>.ts` с типами ответа и функциями; компоненты не вызывают `fetch`
напрямую и не собирают URL руками.

```ts
// src/lib/api/spots.ts
import { api } from "./client";
import type { Paginated, SpotListItem } from "./types";
export const spotsApi = {
  list: (q: { region?: string; page?: number }) => api.get<Paginated<SpotListItem>>("spots", { query: q }),
  propose: (id: string, body: SpotProposalInput) => api.post("spots/" + id + "/proposals", body),
};
```

Серверная страница:

```tsx
// app/spots/[slug]/page.tsx (Server Component)
import { notFound } from "next/navigation";
import { serverFetch } from "@/lib/api/server";
import { isApiError } from "@/lib/api/errors";
export const revalidate = 300;
export default async function SpotPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const spot = await serverFetch<SpotDetail>(`spots/${slug}`, { tags: ["spots", `spot:${slug}`] }).catch((e) => {
    if (isApiError(e) && e.isNotFound) notFound();
    throw e; // → app/error.tsx с «Повторить»
  });
  return <SpotView spot={spot} />;
}
```

`serverFetchSafe` возвращает `null` вместо ошибки — для необязательных блоков (тизеры, «похожие»).
`serverFetchAll` проходит пагинацию (sitemap). `listResults(data)` принимает и страницу, и массив.

### 4.2 Клиент `api` (`lib/api/client.ts`)

- база `/api/v1`, `credentials: "include"`, JSON; путь без слэша в конце (`APPEND_SLASH=False`);
- CSRF автоматически: один `GET /auth/csrf`, затем `X-CSRFToken` из cookie на POST/PUT/PATCH/DELETE (cookie
  перечитывается каждый раз — Django меняет её при входе; при отказе CSRF — одно обновление и повтор);
- ошибки → `ApiError { status, code, message, fields, requestId }`: `isNetwork`, `isUnauthenticated`, `isForbidden`,
  `isNotFound`, `isValidation`, `isConflict`, `retryable`, `fieldError("email")`. Нет ответа → `code: "network"`,
  `status: 0`, текст «Нет соединения с сервером…» (ATX-25);
- GET автоматически повторяется 2 раза при сети/502–504; POST — только с `idempotencyKey` (обязателен для
  `POST /inquiries` и `POST /bookings`): `api.post("bookings", body, { idempotencyKey: newIdempotencyKey() })` —
  создайте ключ один раз на попытку пользователя (в `useRef`), чтобы ручной повтор не создал дубль;
- гости сейчас получают **403** `not_authenticated` (позже станет 401) — обрабатывайте оба (`err.isUnauthenticated`).

### 4.3 TanStack Query

- Ключи — только из `lib/api/keys.ts` (`qk.inquiries`, `qk.booking(id)`…), новые домены добавляйте туда. Первый
  элемент ключа — домен; инвалидация префиксом обновляет списки и детали.
- Мутация = `useMutation` + `onSuccess: invalidateQueries(...)`; оптимистично — по образцу `useToggleFavorite`
  (`onMutate` → снимок → `onError` откат).
- Ретраи запросов уже в клиенте; QueryClient повторяет только 429/500 один раз.
- `QueryState` рисует загрузку/ошибку/пусто/нет прав по результату `useQuery` — используйте его в каждом списке.

### 4.4 Аутентификация

```ts
const { me, isGuest, isLoading } = useMe();   // me: Me | null (нормализованный, см. lib/api/auth.ts)
const counters = useCounters();               // { unread_messages, unread_notifications, new_inquiries, pending_bookings }
const requireAuth = useRequireAuth();         // requireAuth(() => book(), "Чтобы записаться, войдите в аккаунт.")
```

- `Me`: `displayName`, `handle`, `avatar`, `region`, `specialties` (активные), `primarySpecialty`, `staffRoles`,
  `isModerator`, `organizations[{id, slug, name, kind, role, status, membershipId}]`, `instructorProfile`,
  `deletion`, `emailVerified`, `raw` (полный ответ `/me`).
- `<RequireAuth staff="moderator" | specialty="instructor">` — гостя уводит на `/login?next=…`, без прав показывает
  `NoAccess`. Это только UX: права проверяет сервер.
- Гостевые действия (избранное, запись, сообщение, отзыв) — через `useRequireAuth()`/`useLoginPrompt()`, не молча.
- `?next=` всегда через `safeNext()` (защита от open redirect); ссылка на вход — `loginHref(next)`.

### 4.5 Realtime и счётчики

`useRealtime` уже смонтирован в `Providers` (только для вошедших): события `counters` пишут в `qk.counters`,
`message.new`/`conversation.read` инвалидируют `conversations`+`inquiries`+`counters`, `notification.new` —
`notifications`, `inquiry.updated`/`booking.updated` — свои списки. Источник правды — REST (`GET /me/counters`),
WS только ускоряет (MSG-06/07, ATX-10). В чате подписывайтесь на сырые события:

```ts
useRealtimeEvent("message.new", (e) => { if (e.conversation_id === id) appendMessage(e.message); });
```

После открытия диалога вызовите `POST conversations/{id}/read` — сервер разошлёт `counters` на все устройства.

### 4.6 Особенности ответов backend

- Перечисления в части API приходят объектами `{code, label}` (споты: `difficulty`, `break_type`, `status`…;
  румбы: `{code, label, short, degrees}`), в части — строками. Читайте **только** через `choiceCode()` /
  `choiceLabel(value, СЛОВАРЬ)` из `labels.ts`; `CompassRose` и `StatusBadge` принимают оба вида.
- Деньги — строки-десятичные (`"2500.00"`) + `currency` → `formatMoney()`. `rating_avg` — строка.
- `regions` и `spots/map` (`{count, markers}`) не пагинируются; остальные списки — `{count, next, previous, results}`.
- Медиа — всегда объект `Media` (`url`, `thumbnail_url`, `poster_url`); закрытые файлы — `mediaApi.privateUrl(id)`.

## 5. Как добавить маршрут

1. Путь — в `src/lib/routes.ts` (`routes.xxx(...)`); в навигацию — `MAIN_NAV` (шапка, каталог-лист, футер берут оттуда).
2. Публичная страница: `app/<path>/page.tsx` — Server Component, `export const revalidate = …`,
   `export async function generateMetadata()` через `buildMetadata({ title, description, path, image })`
   (канонический URL на `PUBLIC_SITE_URL`, OpenGraph). Для карточек добавьте JSON-LD (`jsonLd()`).
3. Новые типы объектов — в `app/sitemap.ts` (массив `SOURCES`).
4. Кабинет: `app/account/<section>/page.tsx` с `export const metadata = { title }` и клиентским компонентом из
   `components/account/…`; пункт меню — в `lib/account-nav.ts`. Подразделы — `<NavTabs>` (каждый подраздел — URL).
5. Приватные страницы вне `/account` оборачивайте в `<RequireAuth>` и добавляйте в `disallow` `robots.ts`.
6. После создания файлов в Docker — `docker compose restart frontend`.

## 6. Стили

- Классы прототипа (1:1): `hero`, `wrap`, `section`, `section-title`, `grid grid-3`, `feature`, `person-card`,
  `spot-card`, `rent-card`, `tag soft|verified|gg`, `chip`, `primary`, `pill-btn`, `line-btn`, `filters/filter`,
  `modal`, `toast`, `toggle-row`, `notice`, кабинет — `gv-account`, `gv-ac-panel`, `gv-ac-card(s)`, `gv-ac-line`,
  `gv-ac-empty`, `gv-ac-note`, `gv-ac-btn`… Справочник с CSS — `docs/prototype/DESIGN_SYSTEM.md`, экраны —
  `PUBLIC_SCREENS.md`, `CABINET_SCREENS.md`, `SHAPERS_SCREENS.md`, скриншоты — `docs/prototype/screens/`.
- `styles/public.css`, `cabinet.css` — перенос прототипа (тёмно-серые вторичные тексты затемнены до AA). Не правьте
  их ради одной страницы: страничные правила — в CSS-модуль рядом со страницей (`page.module.css`) или в `app.css`
  (общие компоненты). Глобальные стили не выгружаются при навигации — не пишите глобальные селекторы тегов.
- Цвета/радиусы/тени — токены `tokens.css` (`var(--selected)`, `var(--text-secondary)`, `--st-*`…), не новые hex.
- Шейперы: стили модуля прототипа **изолированы** под `.gv-shapers` — оборачивайте разметку каталога/кабинета
  шейпера в `<div className="gv-shapers">` (у модуля свои `--navy/--text`, шрифт Inter).
- Брейкпоинты прототипа: 1100 · **810** (мобильная навигация, нижняя панель) · 760 · 640 · 600 · **540** (телефон) · 380 · 370 · 340.
- Телефон: на ≤810px снизу фиксированная панель (`--tabbar-h` + safe area); `body` уже имеет отступ. Липкие панели
  действий форм делайте классом `gv-sticky-actions` (встают над панелью, ATX-22). Горизонтальной прокрутки страницы
  быть не должно на 320–430px (ATX-19): длинные строки — `overflow-wrap`, таблицы/ленты — в контейнере `overflow-x:auto`.
- Иконки — только `<Icon name="…" />` (одна сетка 24px, толщина 1.9, UX-04). Юникод-глифы прототипа (♧ ◈ ≋ ⌖ ♡)
  заменены иконками `clover`, `diamond`, `waves`, `target`, `heart`. Новая иконка — в словарь `extra` скрипта
  `frontend/scripts/gen_icons.py` (та же сетка/толщина), затем `python3 frontend/scripts/gen_icons.py`
  (перегенерирует `components/ui/icons/registry.ts`; руками его не править).

## 7. UI-кит (`import { … } from "@/components/ui"`)

| Компонент | Когда | Пример |
|---|---|---|
| `Button`, `ButtonLink` | действие / навигация (ссылка — всегда `ButtonLink`) | `<Button variant="primary" iconRight="arrow" loading={m.isPending}>Отправить</Button>` · варианты `primary line pill link soft danger` |
| `IconButton`, `IconLink` | кнопка-иконка, обязательный `label` | `<IconButton icon="chat" label="Сообщения" badge={3} />` |
| `Icon` | любая иконка | `<Icon name="map-pin" size={14} />` |
| `Avatar` | фото/инициалы | `<Avatar media={user.avatar} name={user.display_name} size={40} />` |
| `Card`, `CardHeader` | панели/карточки | `<Card variant="panel"><CardHeader title="…" description="…" actions={…} /></Card>` |
| `Tag`, `Badge`, `StatusBadge`, `CountBadge` | метки; **статусы только `StatusBadge`** | `<StatusBadge domain="booking" status={b.status} />` |
| `CertificateBadge` | сертификат инструктора: не указан / загружен / проверен (TRUST-03) | `<CertificateBadge status={p.certificate_status} hideNone compact />` |
| `Rating`, `Stars`, `RatingInput` | средняя оценка (0 отзывов → «Пока без отзывов») / ввод оценки | `<Rating value={x.rating_avg} count={x.rating_count} href="#reviews" />` |
| `HeartButton` | избранное (оптимистично, гостю — вход) | `<HeartButton type="spot" id={spot.id} name={spot.name} />` · `variant="pill"`/`"light"` |
| `TextInput`, `Textarea`, `Select`, `Checkbox`, `Field` | поля с подписью, подсказкой, ошибкой (UX-14) | `<Select label="Регион" placeholder="Все регионы" options={…} />` (UX-06: стрелка не перекрывает значение) |
| `Toggle`, `ToggleRow` | переключатель 58×30, `role=switch` (UX-07) | `<ToggleRow title="GG Surfer" description="…" checked={v} onChange={setV} />` |
| `Segmented` | выбор 2–5 вариантов (UX-05) | `<Segmented ariaLabel="Вид" value={v} onChange={setV} options={[…]} />` |
| `Tabs` + `TabPanel`, `NavTabs` | вкладки внутри страницы / подразделы-URL | `<NavTabs ariaLabel="Кабинет инструктора" current={pathname} items={[{href, label}]} />` |
| `Chip`, `ChipGroup` | теги / мультивыбор (интересы, румбы) | `<ChipGroup label="Интересы" value={v} onChange={setV} options={…} max={5} />` |
| `Pagination` | страницы; в каталогах — ссылками (SEO) | `<Pagination page={p} count={data.count} pageSize={20} hrefFor={(n) => "?page=" + n} />` |
| `CompassRose` | роза ветра/свелла, «не прогноз» (SPT-04) | `<div className="gv-rose-pair"><CompassRose kind="wind" directions={spot.best_wind_directions} /><CompassRose kind="swell" directions={spot.best_swell_directions} /></div>` |
| `MediaUploader` | ≤10 фото + отдельное видео, presigned-загрузка (UX-08/09, BRD-03/04) | `<MediaUploader purpose="board_photo" value={photos} onChange={setPhotos} coverId={cover} onCoverChange={setCover} video={{ purpose: "board_video", value: video, onChange: setVideo }} />` |
| `MediaImage` | фото карточки с кропом и заглушкой «Фото пока нет» | `<MediaImage media={spot.cover} alt={spot.name} />` |
| `StatStrip` | компактная строка метрик — только Панель/Статистика/Обращения (MET-02) | `<StatStrip items={[{ label: "Обращения", value: 12 }]} />` |
| `Modal`, `RouteModal` | диалоги (фокус-ловушка, Esc, возврат фокуса, блок прокрутки, inert фон) | `<Modal open={o} onClose={close} title="…" size="wide" footer={…}>…</Modal>` |
| `useToast()` | короткие уведомления; ошибки — с «Повторить» | `toast.error(err, { action: { label: "Повторить", onClick: retry } })` |
| `LoadingState`, `EmptyState`, `ErrorState`, `NoAccess`, `SuccessState`, `QueryState`, `OfflineBanner` | состояния экрана (UX-13) | см. §8 |
| `ClampText` | длинный пользовательский текст с «Показать полностью» | `<ClampText lines={4}>{bio}</ClampText>` |

`MediaUploader` хранит только список готовых `Media` в порядке показа; родитель сохраняет `ids`, порядок и обложку
своей моделью. Ссылки на загрузку одноразовые — повтор делает новый билет автоматически. Удаление на сервере —
через проп `onRemove(media)` (вызовите эндпоинт своей модели). Для сертификатов — `kind="document" maxFiles={1}`.

## 8. Состояния каждого экрана (UX-13, DSN-06) — чек-лист

| Состояние | Чем |
|---|---|
| Загрузка | `LoadingState variant="skeleton"` для списков/карточек, `LoadingState` для панели; кнопки — `loading` |
| Пусто | `EmptyState` (каталоги — с иллюстрацией и «Сбросить фильтры»; кабинет — `compact`) |
| Ошибка | `ErrorState error={err} onRetry={refetch}`; формы — `apiFieldErrors(err)` в поля + общий текст; тост с «Повторить» |
| Нет прав | `NoAccess` (403, не то направление, staff) — без подсказок «включите роль» (BR-04) |
| Нет сети | глобальный `OfflineBanner` уже в layout; ошибки `code: "network"` показывают «Нет соединения» |
| Успех | тост `toast.success(...)` или `SuccessState` для финальных шагов |
| Длинный текст | заголовки карточек — `gv-clamp-2` + `title`; описания — `ClampText`; всё переносится (`overflow-wrap`) |
| 0 / 1 / 10 фото, 1 видео | 0 → `MediaImage` с заглушкой; 1 → одна обложка без сетки; 10 → сетка миниатюр + «+N» в каталоге; видео — отдельная плитка |
| 0 отзывов | `Rating` → «Пока без отзывов» (не «0,0») |

Используйте `QueryState`, чтобы не писать ветки руками.

## 9. Доступность (WCAG 2.2 AA, UX-14) — правила

- У каждого поля видимая подпись (`label`), ошибки связаны (`aria-describedby`) — компоненты кита делают это сами.
- Интерактив — `button`/`a`, не `div onClick`. Навигация — ссылка (`Link`/`ButtonLink`), действие — кнопка.
- Кнопки-иконки — обязательный `label`; декоративные иконки скрыты (`aria-hidden`, по умолчанию в `Icon`).
- Переключатели `role=switch`, избранное `aria-pressed`, вкладки `role=tab`, сегменты `role=radio`, текущий пункт меню
  `aria-current="page"` — уже в компонентах.
- Модалки — только `Modal` (фокус, Esc, возврат фокуса, тач-закрытие по фону).
- Контраст: вторичный текст не светлее `var(--text-secondary)` (#4a7591); статусы — из `--st-*`.
- Видимый фокус не отключать; цель нажатия ≥ 40–44px на телефоне.
- Изображения: осмысленный `alt` для фото объектов, `alt=""` для декоративных.

## 10. Форматирование и подписи

- `format.ts`: `formatDate(d, { timeZone, style })`, `formatTime`, `formatDateTime`, `formatDateRange` — **всегда с
  часовым поясом места** (`region.timezone` / `event.timezone`), `formatRelative`, `formatMoney("2500.00", "RUB")`,
  `formatPriceFrom`, `plural`/`pluralize(n, WORDS.review)`, `formatFeetInches(76)` → «6′4″»,
  `formatBoardDimensions(variant)`, `formatClock`, `initials`.
- `labels.ts`: `STATUS` (обращения, брони, аренда, занятия, отзывы, правки спотов, сертификаты, организации,
  приглашения, наличие досок…), `INQUIRY_ACTIONS`/`BOOKING_ACTIONS` (единые глаголы), словари перечислений,
  `COMPASS`. Никогда не выводите сырой код (`pending`, `sent`).

## 11. SEO (NAV-05, ATX-32)

- `buildMetadata({ title, description, path, image, noindex })` — title по шаблону «… · Гдеволна.рф», canonical на
  `PUBLIC_SITE_URL` (для статических страниц переменная нужна на этапе сборки), OpenGraph/Twitter.
- Человекочитаемые адреса: `/spots/{slug}`, `/instructors/{handle}`, `/schools/{slug}`, `/shapers/{slug}`.
- Приватные страницы — `noindex` (кабинет уже), публичные списки — с пагинацией ссылками.

## 12. Тесты

- Файлы `*.test.ts(x)` рядом с кодом; `npm test`. Окружение jsdom, `next/navigation` замокан глобально:
  `navigation.set({ pathname, search })`, проверки `navigation.router.replace`.
- `mockApi({ "GET /api/v1/me": () => json(RAW_ME), "POST /api/v1/x": () => json({}, 201) })` — подменяет `fetch`,
  `api.calls("POST /api/v1/x")` — вызовы; `CSRF_OK`, `GUEST_403`, `RAW_ME`, `renderWithProviders(ui)`.
- Покрывать: доступность (роли/имена), состояния (загрузка/ошибка/пусто), правила (лимиты, «не к себе»), ошибки сети.
- E2E (Playwright) — `e2e/` против `docker compose`.

## 13. Чего не делать

- Не переносить демо-логику прототипа (localStorage как источник правды, «Имитировать принятие», демо-рейтинги,
  кнопку «Настроить трансляцию» для всех) — PL-02, 12.2.
- Не считать на клиенте рейтинги, выручку, доступность и права — только показывать ответ сервера (9.1).
- Не писать `fetch` в компонентах, не собирать пути строками — `lib/api/*`, `routes.ts`.
- Не дублировать редакторы: фото профиля — только в «Профиле» (ACC-07); модели досок — только в «Мои доски» (BRD-01).

## 14. Дополнения после интеграции

- Обёртка контентных публичных страниц (спот, аренда, клуб, мерч, участник GG Surfer) — `className="wrap gv-page-body"`.
  Класс `.gv-page` занят кнопкой пагинации — не используйте его как контейнер.
- Стили: `styles/learning.css` (кабинеты инструктора/школы `lc-*`, общие списки и формы, карточка спота),
  `styles/account.css` (inbox, чат, настройки `acc-*`), `styles/shaper-cabinet.css` (`gv-sc-*`), доменные
  `components/<domain>/*.css` подключаются самими компонентами/страницами.
- Публичные каталоги аренды, GG Surfer, клуба и мерча: `lib/api/publicCatalogs.ts`, клиентские действия —
  `components/public/CatalogIslands.tsx`. Кабинет школы: `components/school-cabinet/*`, маршрут
  `app/account/orgs/[id]/[[...tab]]`.
- Realtime: `RealtimeClient` строит адрес `ws(s)://<host>/ws/events/`; явный `url: undefined` не должен затирать
  значение по умолчанию (регрессионный тест в `lib/realtime/realtime.test.ts`).
