# ГДеволна — public site screens (from the HTML prototype)

Scope: everything a visitor sees outside the personal account: global layout (top bar, nav, mobile nav,
footer, loader, toast, modal system), Главная, Каталог сёрф-инструкторов (+ instructor card/profile
modal, calendar, booking step), Карта сёрф-спотов (+ spot detail, gallery, wind/swell diagrams, reviews,
rating, «предложить исправление»), GG Surfer, Аренда, О нас и клуб, search, favourites, inbox entry
points, registration UI. The cabinet («Личный кабинет», `gv-unified-account-engine`) and the shapers
module are documented elsewhere and only referenced here.

Companion files:
* `DESIGN_SYSTEM.md` — tokens, components, exact CSS.
* `frontend-port/styles/prototype-public.css` — consolidated CSS (class names as below).
* `frontend-port/icons.json` — inline SVG icons + glyph map.
* `frontend-port/seed_public.json` — all demo data and **all UI copy** in machine-readable form (`pages.*`).
* `ASSETS.md` + `frontend-port/assets/` — images.
* Screenshots: `docs/prototype/screens/public-*.png` (index in §16).

Verbatim Russian copy is quoted «like this». `→` `♡` etc. are part of labels (they are text glyphs in the prototype).

---

## 0. How the prototype works (read first)

### 0.1 Single page, hash routing

`<main id="app">` is re-rendered with `innerHTML` by `render()` on every state change. Pages are chosen by
`location.hash`: `#home` (default) · `#people` · `#spots` · `#gg` · `#rentals` · `#shapers` · `#club` ·
`#profile`. Any element with `data-go="<page>"` navigates (closes an open modal, sets the hash, re-renders,
scrolls to top instantly). `data-go="profile"` for a guest opens the registration modal instead. Unknown
hashes fall back to `home`. Everything else (details, forms, chats) opens in **modals** — there are no URLs for
a spot, an instructor or a rental item.

**Proposed Next.js routes** (TZ NAV-05: unique, human-readable URLs, SEO):

| Prototype | Proposed route | Notes |
|---|---|---|
| `#home` | `/` | |
| `#people` | `/instructors` (filters in query: `?region=&spot=&board=&level=&sort=`) | |
| instructor modal | `/instructors/[slug]` (tabs: `?tab=calendar|reviews` or sub-routes) | can still open as an intercepting modal route over the catalogue |
| `#spots` | `/spots?region=` | |
| spot modal | `/spots/[slug]` | slugs proposed in `seed_public.json` (`zaliv-anglichanka`, `khalaktyrskiy-plyazh`, …) |
| spot edit form | `/spots/[slug]/suggest` (auth) or modal | |
| `#gg` | `/gg-surfer?region=&status=&q=&view=map|list` | |
| `#rentals` | `/rentals?region=&type=&price=&size=` · item `/rentals/[slug]` | |
| `#club` | `/club` | |
| `#shapers` | `/shapers` | shapers docs |
| `#profile` | `/account/*` | cabinet docs |
| search modal | `/search?q=` (+ header overlay) | TZ NAV-04 |

### 0.2 Script layering (important: later scripts override earlier render functions)

The page has 5 public scripts; later ones replace functions defined earlier. The **final** behaviour is:

| Function | Defined by | Final version |
|---|---|---|
| `home()` | main | wrapped by "premium" script: feature «Избранные места» is replaced by «Аренда снаряжения» |
| `people()`, `personCard()` | main | wrapped by premium: adds price row, sorting, new meta line, new outro |
| `showPerson()` | main (simple modal) | **replaced** by the lesson script (tabs + calendar) — the simple version is dead code |
| `showBook()` | main (date input) | **replaced** by the lesson script (2-step booking from calendar slot) |
| `spotCard()` | main | wrapped by premium: adds wind/season signal + hazard line |
| `showSpot()` | main → premium wrapper (adds SVG wind/swell **roses** + photo caption) | **replaced again** by the gallery script, which re-implements the modal from the main version: gallery added, **roses and caption lost**. See §4.4 — implement the roses anyway (TZ SPT-04). |
| `ggPage()` | main | wrapped by premium: intent chips, map/list tabs, schematic map, kindness panel |
| `club()` | main | wrapped by premium: member card, achievements, roadmap |
| `shapers()` | main (static page) | **replaced** by mobile-bridge script: hero + iframe with the full shapers document |
| `openChat()`, `openInbox()`, `readOrders()`, `reviewOrder()` | main | replaced by the lesson script (styling `lesson-*`) |
| `profile()` | main → lesson → premium | replaced by the unified account engine (cabinet) |
| `showRegister()` / `handleRegister()` | main | wrapped by the account engine: «Дополнительные направления» checkboxes in step 1 and `roles[]` on save |

### 0.3 Demo state = localStorage (all of it must become API data)

| Key | Content | Replace with |
|---|---|---|
| `gg_user` | the "logged-in" user (name, handle, region, level, board, role, roles[], gg, rent, public, interests, ggStatus, documents[] names) | session/auth + `GET /me` |
| `gg_favorites` | array of `"spot:<id>"`, `"person:<id>"`, `"rental:<id>"` | `/me/favorites` (TZ MSG-11) |
| `gg_orders_v2` | lesson requests (`pending/accepted/completed/declined/cancelled`) | bookings API (server-side slot locking, TZ INS-07) |
| `gg_chats_v2` | chats `{id:"gg:<target>:" | "lesson:<target>:<orderId>", messages[]}` | messaging API (TZ MSG-*) |
| `gg_reviews_v2` | reviews written after "completed" demo lessons | reviews API (only after a real completed lesson) |
| `gg_availability_v3`, `gg_profile_extras_v3` | instructor schedule overrides / own card edits | instructor cabinet API |
| `gg_rent_orders_premium`, `gg_rent_listings_premium` | rental requests / own rental listings | rentals API |
| `gv_spot_suggestions_v1` | up to 100 local spot-change suggestions | moderation queue API (TZ TRUST-04) |
| `gg_stream_v2` | URL of the home live stream (any visitor can set it!) | CMS/admin setting |

Counters shown in the UI (`Найдено: 6`, `5 анкет на карте · демо`, `Показано 8 предложений`, header badges)
are computed on the client from these arrays — use API counts.

### 0.4 Global interaction rules

* **Modal**: one at a time (opening another replaces it), backdrop click or «×» or `Esc` closes, body scroll locked.
* **Toast**: bottom centre, 2.9 s, replaces previous.
* **Favourites**: any `[data-like]` toggles the id, shows toast «Добавлено в избранное ♡» / «Убрано из избранного», re-renders the page; if the instructor/spot modal is open it is re-rendered too (so tabs/scroll reset).
* **Guest gating**: actions that need an account (book, message, review a spot, rental request/listing, sticker, inbox, chat) close the modal and open registration, sometimes with a toast (texts in each section).
* Focus ring: `2px #078ab8` (buttons, links, inputs), other elements `3px #f18daf`.

---

## 1. Global layout

### 1.1 Site loader (`#siteLoader`) — `public-loader-1440.png`

Full-screen light gradient (`#f5fcff → #dff3fc`), centred animated SVG (volcano with drifting smoke,
dashed running wave, little surfer bobbing), «ГДЕВОЛНА.РФ» (23px/900, letter-spacing 2px), caption «До
встречи на волне» (12px `#4994b3`). `role="status"`, `aria-label="Загружается Гдеволна"`. Fades out
650 ms after `window.load` (hard fallback 2.4 s). Demo-only splash — in Next.js prefer route-level loading
states (TZ UX-13).

### 1.2 Top bar — `public-component-header-1440.png`

Sticky, translucent white with blur, 72px high (61px ≤810, 59px ≤540), content in `.wrap` (1200px).
Left → right:

1. **Logo** `assets/brand/logo.png`, link to home, `title="На главную"`, `alt="Гдеволна.рф"`, 108×61 (103×59 ≤810, 90×52 ≤540).
2. **Desktop nav** (`nav.mainnav#nav`, hidden ≤810px), 12px buttons with a 2px underline for the active page:
   «Каталог сёрф-инструкторов» · «Карта сёрф-спотов» · «GG Surfer» · «Аренда» · «Шейперы» · «О нас и клуб» · «Личный кабинет» (the last one is appended by the account script; for guests it opens registration). Note: there is **no «Главная»** link in the desktop nav (logo only).
3. **Toolbar** (`.navtools`): three 21px line icons (search, heart, chat — `icons.json`) and the outline button with a user icon + label «Войти» (guest) / «Кабинет» (logged in).
   * Search `aria-label="Поиск"` → search modal (§9).
   * Heart `aria-label="Избранное"` → favourites modal (§10); red badge with the count of favourites (hidden when 0; counts rentals too).
   * Chat `title/aria-label="Сообщения"` → inbox (§11); badge = number of chats, only for logged-in users.
   * «Войти»/«Кабинет» → registration modal (guest) / `#profile` (user). There is no sign-in form (see §12).
   Hover on icon buttons turns them pink `#e46b90`.

### 1.3 Mobile nav (≤810px) — `public-home-390-viewport.png`

A second row under the header (`.wrap.mobile-nav`): horizontally scrollable text tabs without scrollbar:
«Главная» · «Инструкторы» · «Споты» · «GG Surfer» · «Аренда» · «Шейперы» · «Клуб» · «Кабинет». Active tab is
underlined. The desktop nav is hidden; the toolbar (3 icons + «Войти») stays in the header.
**TZ NAV-03 / UX-03 require a bottom tab bar** (Главная, Каталог, Избранное, Сообщения, Кабинет) and a lighter
header on phones — the prototype does not implement this; design the bottom bar with the same nav styling.

### 1.4 Footer

`footer.footer`: 270px tall (340px ≤540), background = mountain/ocean panorama `assets/ui/footer-landscape.webp`
(`center 65% / cover`) under a light gradient + top fade. Row: logo (132×76) · white rounded pill nav with
links «Каталог сёрф-инструкторов», «Карта спотов», «GG Surfer», «Аренда», «Шейперы», «О нас и клуб» (12px/700)
· decorative glyphs «◉ ◈ ≋» (21px). Below, right-aligned 10px: «© 2026 Гдеволна.рф · Сделано с любовью к
российскому сёрфингу». ≤540px: logo, nav (wrapping) and glyphs stack left-aligned; copyright left-aligned.

### 1.5 Hero (shared page header)

`section.hero` full-bleed photo with a left-to-right dark-blue gradient, 275px (250px ≤540). Content inside
`.wrap`: kicker «ЛЮДИ · ВОЛНЫ · РОССИЯ» (12px uppercase, always the same), `h1` (52px max, white), text (14px/600,
max 410px), optional CTA (white button with →). Variant `home` (photo `hero-home.webp`: surfer with board on
rocks, back view) is used on Главная, GG Surfer and the guest cabinet; variant `people` (photo
`hero-catalog.webp`: surfer riding a wave) on Инструкторы, Споты, Аренда, Шейперы. The club page has no hero.

### 1.6 Modal system & toast

See DESIGN_SYSTEM §3.16/§3.17. Standard modal 620px, wide 820px (instructor 910px, spot-edit 790px),
radius 17px, padding 29px (21px ≤540), max-height viewport − 45px with inner scroll, close «×» top-right
(`aria-label="Закрыть"`). On phones the modal is almost full-screen with 10px backdrop padding.

---

## 2. Главная (`#home`) — `public-home-1440.png`, `public-home-390.png`

Blocks top → bottom (all inside `.wrap` after the hero):

1. **Hero (home variant)** — h1 «Гдеволна.рф —<br> где волна, там свои», text «Здесь находят любимые споты, знакомятся с людьми и открывают российский сёрфинг — от Камчатки и Сахалина до Крыма.», CTA «Найти свою волну →» → `#spots`.
2. **Two columns** `.home-columns` (2.25fr / 0.95fr; stacked ≤810):
   * **About** card (`.about-hero`, 272px, photo `about-intro-surfer.webp` on the right 59%, white gradient on the left; ≤540 photo becomes a faint full background):
     h2 «◈ О сайте «Гдеволна.рф»», p «**Гдеволна.рф** — уютное место для тех, кто любит сёрфинг в России. Мы собираем вместе споты, инструкторов, мастеров досок и людей, которые понимают, зачем вставать на рассвете ради хорошей волны.», p «Наше дело — помогать находить друг друга. Даже если до ближайшего океана лететь полдня.», pill «Узнать о проекте →» → `#club`.
   * **How-to** side card (`.side-card`): h3 «♧ Как пользоваться сайтом», 4 numbered steps (25px blue circles): «Выберите регион и найдите спот», «Познакомьтесь с сёрферами и инструкторами», «Забронируйте занятие или найдите компанию», «Добавьте любимые места в избранное»; full-width pill «Знакомьтесь через GG Surfer →» → `#gg`.
3. **Live panel** `.live-panel` (2 columns, stacked ≤810): kicker with pulsing pink dot «СОРЕВНОВАНИЯ · LIVE», h2 «Когда наши выходят на волну — смотрим вместе», p «Здесь появятся прямые эфиры соревнований, фестивалей и сёрф-встреч. Можно добавить ссылку на трансляцию в демонстрационном режиме.», pill «Настроить трансляцию» → stream modal (§13.3). Right: dark screen 242px (230px ≤810) with a play circle «▶», «Место для прямого эфира», «Как только включим трансляцию, она появится здесь»; when a stream URL is set it shows an embedded YouTube-nocookie/RuTube iframe. **Demo-only:** any visitor can set the stream, stored in localStorage → move to admin/CMS.
4. **Features** — section title «Что вы найдёте на сайте», grid 3×2 (2 columns ≤810, 1 column ≤540) of `.feature` cards (image 150px + round icon + title + text + «Перейти →» link):

   | Title | Text | Image | Icon | Link |
   |---|---|---|---|---|
   | Каталог сёрф-инструкторов | Опытные инструкторы, проверенные локации и удобный поиск. | feature-volcano-coast | ♧ | `#people` |
   | Карта сёрф-спотов | Места для сёрфинга, прогнозные ориентиры и важные детали. | feature-map-thumb | ⌖ | `#spots` |
   | GG Surfer | Найдите своих людей в регионе и катайтесь вместе. | feature-coast-aerial | ♡ | `#gg` |
   | Каталог шейперов | Мастера, создающие доски ручной работы. | feature-shaper-workshop | ♙ | `#shapers` |
   | Сёрф-клуб | Открытое сообщество, подарки и дружеские встречи. | feature-mountain-lake | ✦ | `#club` |
   | Аренда снаряжения | Доски и гидрокостюмы у своих — в нужном регионе. | feature-barrel-surfer | ◈ | `#rentals` |

   (The sixth card originally was «Избранные места / Сохраняйте споты и планируйте поездки мечты. / ☆ / #spots»; the premium script swaps it for rentals.)
5. **«Свои люди рядом»** — grid 2 (stacked ≤810): left section title «Свои люди рядом», muted p «Приехал на Камчатку или Сахалин? Открой карту и посмотри, кто готов подсказать дорогу, показать спот или разделить поездку.», primary «Открыть GG Surfer →» → `#gg`; right a 160px photo card (volcano) with italic white quote «Сёрфинг — это способ увидеть мир по-новому. Особенно если рядом свои».
6. **Wide banner** (shared, also on spots/GG/rentals): photo `banner-mountains-volny-vezde.webp` (with the painted words «Волны везде!» on the right), h2 «Где волна — там жизнь», p «Вулканы, снег, Ладога и горы Крыма. Открывайте для себя новые горизонты!», pill «Перейти к карте спотов →» → `#spots`.

No news, events or video content exists on the home page (only the empty stream slot).

---

## 3. Каталог сёрф-инструкторов (`#people`) — `public-people-1440.png`, `public-people-390.png`, `public-people-390-filters.png`, `public-people-empty-1440.png`

### 3.1 Page

1. Hero (people variant): h1 «Каталог сёрф-инструкторов», text «Люди, с которыми начинаются хорошие истории: выбирайте споты, читайте отзывы учеников и договаривайтесь о занятии.» (no CTA).
2. **Filter row** `.filters` (4 tiles + reset; 2 columns ≤810 with reset full-width; 2 columns on phones with icon floated right):
   | Tile | Icon | Label | Options |
   |---|---|---|---|
   | Регион | map-pin | «Регион» | Все регионы, Камчатский край, Крым, Сахалин, Ладожское озеро, Приморский край |
   | Споты | «≋» | «Споты» | Любые споты + sorted union of all instructors' spot names (Авачинская бухта, Балаклава, бухта Кирьявалахти, Кача, Ладожские шхеры, Новый Свет, Оленевка, Орджоникидзе, Охотское море, Паратунка, Пильтун, Сортавала, Судак, Тихий океан, Халактырский пляж, Южно-Сахалинск) |
   | Тип доски | board icon | «Тип доски» | Любая доска, Шортборд, Лонгборд, Фанборд |
   | Уровень катания | level icon | «Уровень катания» | Любой уровень, Начинающий, Средний, Продвинутый |
   | — | — | primary «⟳ Сбросить» | resets all four |
   Every change re-renders immediately (no "apply"). Note: «Уровень катания» filters by the instructor's **own** riding level (`level`), not by the student level shown on the card — clarify with product (TZ INS-09 wants filters by region, spot, level, board, price, certificate, date, reviews).
   Spot options are free-text names, not linked to the spot catalogue («Тихий океан», «Южно-Сахалинск» aren't spots) — in the API use spot IDs.
3. **Listing top** `.listing-top`: left «Найдено: {n} · профили и цены демонстрационные» and help line «♧ Новичкам советуем выбирать по уровню учеников, отзывам и подходящему календарю.»; right «Сортировать» + select: «По умолчанию» (data order), «По рейтингу», «По отзывам», «Сначала дешевле» (by demo price), «По опыту». ≤600px stacks, select full width.
4. **Grid of person cards** (3 / 2 ≤810 / 1 ≤540) — §3.2.
5. **Empty state** (no matches): dashed card with the surfer illustration (`icons.json → empty-surfers`), h3 «Похоже, все ушли ловить волну!», p «По этим условиям инструкторы пока не нашлись. Волны подождут — попробуйте другой спот или сбросьте фильтры.», pill «Сбросить фильтры →».
6. Outro: centred pill «Найти компанию для катания через GG Surfer →» → `#gg`.

### 3.2 Instructor card (`article.person-card`)

* **Photo** 184px (218px ≤540), `alt="Демонстрационное фото: {name}"`, lazy. Top-left: region glass pill with pin icon (`.region-tag`, title «Регион работы: {region}»). Top-right: like button ♡/♥ (`aria-label="В избранное"`).
* **Name row**: h3 name (17px) + rating link «★ 4.9 (24 отзывов)» → reviews modal (§3.5). The average includes local demo reviews: `(rating·reviews + Σlocal)/n`.
* **Review peek** (first sample review): «“{text}”» + «Все отзывы →» (light blue box) → reviews modal.
* **Field lines** (icon glyph + label/value): «♧ Инструктор по сёрфингу» + green tag «✓ сертификат» (title «Значок квалификации — только в примере») when `cert`; «⌖ Споты» {spots}; «♧ Доски» {boards}; two columns «◴ Опыт» «{n} лет» and «☻ Уровень учеников» {students}.
* **Fun fact** box: «☀ **Забавный факт**» + text.
* **Price row**: «Занятие от **3 800 ₽**» + small «Пример цены»; right pill «◷ Выбор времени» (static label, not a button).
* **CTA** full-width primary «▦ Профиль, отзывы и запись ❯» → instructor modal.
* Card hover: lift 3px. Data per card: see `seed_public.json → instructors`.

Demo data: 6 instructors (Алексей Морозов, Мария Волкова, Дмитрий Ковалев, Екатерина Соколова, Иван Петров, Анна Лебедева). Prices, ratings, reviews, certificates are fake (TZ PL-02).

### 3.3 Instructor modal (lesson script) — `public-person-modal-1440.png`, `public-person-calendar-1440.png`, `public-person-reviews-1440.png`, `public-person-modal-390.png`, `public-person-calendar-390.png`

Wide modal (910px ≥900px). Opening another instructor resets tab to «О знакомстве» and the calendar.

* **Intro** (`.lesson-dialog-intro`, flex; ≤480 stacked): portrait 185px wide (125px ≤760, full-width 195px tall ≤480), radius 16. Right: kicker «ЛЮДИ, С КОТОРЫМИ ВОЛНА БЛИЖЕ», h2 name (29px), place line with pin «{region} · {town}», rating link «★ 4.9 (24 отзывов)» + green tag «✓ Сертификат · демо» (if cert), hint «{students} · опыт {n} лет», info box «Пример анкеты инструктора. Доступность, фотографии и отзывы демонстрационные.» (for a locally created instructor: «Этот профиль создан на вашем устройстве, документы ещё не проверены.»).
* **Tabs** (segment, `.lesson-tabs`): «О знакомстве» · «Календарь занятий» · «Отзывы ★». On 390px the third tab is cut off (horizontal scroll) — fix.
* **Tab «О знакомстве»**: two info cards: «Про занятия» — «**Где катаемся:** {spots}», «**Доски:** {boards}», «**Для кого:** {students}», «**Опыт:** {n} лет»; «Немного о человеке» — fact text + tag «GG Surfer · участник сообщества» or «Сёрфинг-инструктор». Note box: «Для бронирования выберите свободное окно в календаре. Чат по занятию появится после подтверждения инструктором. До оплаты вы сможете обсудить условия занятия.» Pill «▦ Открыть календарь →».
* **Tab «Календарь занятий»**: kicker «КАЛЕНДАРЬ ДЛЯ ЗАПИСИ», h3 «Найдём удобный день для волны», p «Выбирайте доступную дату и окно. Инструктор подтвердит или предложит альтернативу.» Then two columns (stacked ≤760):
  * **Month calendar** card: header «октябрь 2026» (capitalised via CSS) + ‹ › buttons (`aria-label` «Предыдущий месяц» / «Следующий месяц»; range: current month … +2). Weekday header «Пн Вт Ср Чт Пт Сб Вс» (Monday first). Day cells (square): number + 7px caption: «{n} окна» (free), «выходной» (closed, grey), «{n} занято» (has accepted bookings), «занято» (no free slots, peach). Past days and days >91 days ahead are disabled. Today has an orange outline; selected day is solid blue. Legend: «● Есть окна», «● Выходной», «● Занято». Default demo rule: **Mondays and Thursdays are closed**, other days have slots 09:00, 12:00, 15:00; first bookable day is auto-selected.
  * **Side panel**: kicker «ВЫБЕРИТЕ ВРЕМЯ», h3 «21 октября 2026 г.» (ru-RU long date), p «Время указано ориентировочно, по местному времени инструктора.», slot buttons in a 2-column grid (selected = filled blue; busy = struck-through, disabled «12:00 · занято»), or «В этот день инструктор не принимает заявки. Попробуйте соседнюю дату.» / «Все окна заняты.»; «Стоимость — по договорённости с инструктором» (bold); primary full-width «Продолжить запись →» (disabled until a slot is chosen) → booking step 2 (§3.4); micro «Оплата на этом этапе не списывается.»
* **Tab «Отзывы ★»**: left metric card «ОЦЕНКА УЧЕНИКОВ», big «4.9», gold «★★★★★» (always 5 stars), «24 отзывов · показаны примеры и локальные отзывы»; right list of review cards: author (bold), stars «★★★★★», text, small «Пример отзыва · дизайн-прототип» (or «Отзыв после демо-занятия» for local ones). Empty: «≋», «Первые слова ещё впереди», «Отзывы появятся после завершения подтверждённых занятий.»
* **Footer** (all tabs): pills «♡ В избранное» (pink «♥ В избранное» when saved) and, if the instructor is a GG member, «✉ Написать в GG Surfer» (guest → registration; user → GG chat §11.2); right primary «Выбрать занятие →» (switches to the calendar tab; hidden on that tab).

### 3.4 Booking step 2 — `public-booking-step2-1440.png`

Guest → modal closes, registration opens, toast «Для заявки сначала создайте профиль». Own profile → toast
«Записаться к самому себе нельзя. Для проверки создайте демо-заявку в кабинете.» No slot → back to calendar +
toast «Сначала выберите свободное время».
Content: kicker «ШАГ 2 ИЗ 2 · ЗАЯВКА НА ЗАНЯТИЕ», h2 «Ваша встреча с волной», preview row (64px photo, **name**, «{region} · {date} · {slot}»), two selects: «Формат занятия» (Индивидуальное / Вдвоём с другом / Групповое), «Уровень ученика» (Первое занятие / Начинающий / Средний / Продвинутый); textarea «Пара слов инструктору» (placeholder «Привет! Буду в вашем регионе и хочу попробовать...», max 1000), note «После отправки заявка ожидает подтверждения. Чат по этому занятию откроется после её принятия. Стоимость и условия оплаты уточняются при согласовании, деньги здесь не списываются.», footer pill «← Изменить дату» + primary «Отправить заявку →».
Submit: validates slot still free (toast «Это время уже недоступно — выберите другое»), duplicates (toast «У вас уже есть заявка на это время»), saves order `pending`, toast «Заявка отправлена в демо-режиме», opens «Мои занятия» modal (cabinet doc). **Demo-only**: no server, instructor never notified; implement transactional booking (TZ INS-07, 7.3).

### 3.5 Reviews modal (`showReviews`) — `public-reviews-modal-1440.png`

Wide modal: h2 «Отзывы о {name}», rating link, p «Отзывы помогают выбрать наставника ещё до бронирования.», review cards (as above), notice «Примеры отзывов отмечены соответствующим образом. Добавить новый можно только по завершённой заявке из личного кабинета.» Opened from the rating link and the review peek on cards.

---

## 4. Карта сёрф-спотов (`#spots`) — `public-spots-1440.png`, `public-spots-390.png`, `public-spots-390-viewport.png`

### 4.1 Page

1. Hero (people variant): h1 «Карта сёрф-спотов», text «Открывайте новые места, изучайте особенности берега и выбирайте, где ловить свою волну.»
2. Page head: h2 (29px) «Где сегодня искать свою волну?», p «Спутниковая карта Яндекса, координаты, ветер, сезон, инфраструктура и доступ к берегу.»
3. Toolbar `.gg-filters`: region select (Все регионы + 5 regions) · pill «⌖ Развернуть карту» (→ §4.3) · pill «✎ Мои предложения» with a count badge of local suggestions (→ §4.7) · note «Данные и оценки в прототипе иллюстративные».
4. **Map + sidebar** `.spots-overview-map` (1.55fr / 0.75fr; stacked ≤810; map 390px → 370 → 300 ≤540):
   * Yandex map widget iframe (satellite `l=sat`). Centre: Russia `60.4, 98.2` zoom 3; if all shown spots are in one region → region centre, zoom 6. Markers `pm2rdm1…9` at spot coordinates. Overlays: white label «Яндекс Карты · спутник» + small «Маркеры спотов из демонстрационного списка»; pill «Открыть карту ↗» (new tab to yandex.ru/maps).
   * Sidebar «Точки на карте»: one row per spot — pin icon, **name**, small «{region} · {lat}, {lng}», «→»; click → spot modal. Footer notice «Для полной общей карты в Конструкторе понадобится создать и опубликовать вашу собственную коллекцию объектов.» (internal dev note — drop).
   TZ SPT-01: real interactive map with clustering, filters and a card on marker click — the iframe has no click-through to cards.
5. Section title «Карточки спотов» and grid of spot cards (3 / 2 / 1) — §4.2.
6. Wide banner (as on home).

### 4.2 Spot card (`article.spot-card`) — `public-component-spot-card-liked.png`

* Photo 183px (cover from the gallery). Bottom-left white pill «⌖ {region}»; top-right: like button (shifted left) and the **pencil** button (36px white rounded square, title/aria «Предложить исправление данных спота {name}») → edit form §4.6.
* Title row: h3 name + «★ 4.8 (18)».
* Tags: {type} · {level} · {season} (`.tag.soft`).
* Signal chips: «≋ Ветер: {wind}» and «◷ {season}».
* Summary text (12px).
* Nature chips with emoji (`.chip.info`, title «Подробнее — в карточке спота»), e.g. «🌋 Вулканы», «🏔️ Горы», «🏕️ Дикий пляж».
* Hazard line (rusty colour) «⚑ {first sentence of danger}», e.g. «⚑ Холодная вода, течения, резкие изменения погоды».
* Primary full-width «Подробнее о споте →» → spot modal.

### 4.3 Expanded map modal («⌖ Развернуть карту»)

Wide modal: h2 «Споты на спутниковой карте», 440px map (same widget), note «Выберите конкретную карточку спота, чтобы открыть точные координаты и маршрут.», chips «{spot name} →» per spot → spot modal.

### 4.4 Spot detail modal (final = gallery script) — `public-spot-modal-1440.png`, `public-spot-modal-390.png`; intended rose version `public-spot-modal-rose-variant-1440.png`

Wide modal (820px), content top → bottom:

1. Hero image 235px, radius 11, `alt="Пейзаж спота"`. *(Rose variant also adds an uppercase caption under the photo: «РОССИЙСКИЙ СЁРФИНГ • {region} • фото для демонстрации».)*
2. Title row: h2 name + «★ 4.9 (29)».
3. Chips: «{pin} {region}» · {type} · {level}.
4. Summary paragraph.
5. **Gallery** (if photos): title «Фотографии спота» + tag «{n} фото»; grid `auto-fit minmax(130px,1fr)` (2 columns ≤640), thumbnails 104px (88px) radius 12, captions «Общий вид спота», «Линия волны и берег», «Дополнительный ракурс». Thumbnails are not clickable (no lightbox) — add one (TZ SPT-03).
6. Two columns (`.grid-2`, stacked ≤810):
   * Left: «**Дно:** …», «**Сезон:** …», «**Волна:** …», «**Координаты:** lat, lng»; h3 «Виды вокруг» + nature chips (title «Описание особенностей места появится после проверки»); h3 «Инфраструктура» + infra chips (title «Расстояние и ссылка появятся после проверки»).
   * Right: h3 «Условия волны» + **two compass widgets**:
     * Final prototype: two 114px rings `.compass` with text «Ветер<br>{wind}» / «Свелл<br>{swell}». The blue arc is a fixed decoration and does not show the direction.
     * **Intended (rose) design** — implement this: two `.rose-card`s side by side: icon «≋» + «Направление ветра», icon «◈» + «Направление свелла»; SVG compass with 8 labels С/СВ/В/ЮВ/Ю/ЮЗ/З/СЗ, a blue needle to the stated direction with a pink tip; under it the value («Северо-запад») and caption «Показано указанное направление, не прогноз»; for non-directional values («По прогнозу», «Тихоокеанский», «Зависит от участка») only a centre dot and «Уточняйте под прогноз». TZ SPT-04: show *typically favourable* wind/swell as compass diagrams, never mixed with forecasts. Store direction as degrees/sectors (multi-select) in the API.
7. Hazard notice: «⚠ **Опасности:** {danger} Условия и доступ уточняйте на месте.»
8. **Map section** (light blue panel): h3 «Спутниковая карта и маршрут» + tag «Яндекс Карты»; note «Точная точка спота по указанным координатам (данные в примере требуют проверки).»; 310px iframe (245px ≤540) zoom 13 with a marker; buttons primary «↗ Построить маршрут в Яндекс.Картах» (`yandex.ru/maps/?rtext=~lng,lat&rtt=auto`) and pill «Открыть спутник ↗». TZ SPT-09: **remove «Открыть спутник»** from the card.
9. **Video placeholder** (dark gradient panel): play circle «▶», h3 «Видео с этого спота», p «Здесь появится видео с волной и береговой линией, когда добавим материал от сообщества.», small «Пока видео не опубликовано».
10. Actions: pill «♡ В избранное» (pink «♥ В избранное»), pill «Найти местного сёрфера →» (→ `#gg`, not filtered by region), pill «✎ Предложить исправление» (→ §4.6), primary «☆ Отзыв о споте» (→ §4.5).

Missing vs TZ: no list of spot reviews at all (only rating numbers), no author/date/avatar (SPT-03, SPT-10, TRUST-01), no «access» text shown (the field exists only in the edit form), no last-verified date/source (SPT-11), no infrastructure distances (SPT-06).

### 4.5 Spot review modal — `public-spot-review-modal-1440.png`

Guest → registration (no toast). User: h2 «Оставить отзыв о споте», p «В прототипе можно попробовать интерфейс, но отзыв не публикуется.», select «Оценка» («★★★★★ — отлично», «★★★★☆ — хорошо», «★★★☆☆ — нормально», «★★☆☆☆ — сложно», «★☆☆☆☆ — не понравилось»), textarea «Комментарий» (placeholder «Расскажите о своём опыте...», required), primary «Оставить демо-отзыв». Empty → toast «Введите отзыв»; submit → modal closes, toast «Спасибо! Отзыв о споте сохранится в рабочей версии». **Nothing is saved.** API: create review (pending moderation), recompute rating from published reviews (TZ SPT-10).

### 4.6 «Предложить исправление» form (pencil) — `public-spot-edit-form-1440.png`, `public-spot-edit-form-390.png`

Opened from the card pencil, the modal button, or the queue. **Works for guests too** (TZ table 16 says guests can only view; require auth or capture contact in the port). Modal 790px, padding 25px 26px (18px 14px ≤640).

* Head: 82px spot photo (66px), overline «✎ ПРЕДЛОЖИТЬ ИСПРАВЛЕНИЕ», h2 «Уточним данные спота?», p «**{name}** · {region}».
* Explain box: «✓» + **«Вы помогаете сделать карту точнее»** + «Измените только те поля, о которых знаете. Действующая карточка останется прежней, пока предложение не проверено.»
* Numbered sections (32px number tiles):
  1. **01 «Название и расположение»** — hint «Ошибку в названии, регионе или координатах можно поправить здесь». Fields (2-column grid, 1 column ≤640): «Название спота» (text), «Регион» (text), «Широта» (number, step any, −90…90), «Долгота» (number, −180…180). All prefilled with current values.
  2. **02 «Ветер и условия катания»** — hint «Выберите наиболее подходящее направление ветра для катания на этом споте». Wind box: «↗ Подходящий ветер» + current value pill; hint «Сейчас указано: **{wind}**. Выберите одно направление или уточните вручную.»; 10 toggle buttons in a 5-column grid (2 columns ≤640): Север, Северо-восток, Восток, Юго-восток, Юг, Юго-запад, Запад, Северо-запад, Переменный, Зависит от прогноза (single choice, `aria-pressed`; picked = filled blue); text «Другое / уточнить направление» (placeholder «Например, север и северо-восток»; typing clears the buttons). Then selects (current value always added as the first option): «Тип брейка» (Бич-брейк, Риф-брейк, Пойнт-брейк, Ривер-брейк, Риф / пляж, Ветровая), «Уровень катания» (Начинающий, Средний, Продвинутый, Для всех уровней), text «Основное направление свелла», «Дно» (Песок, Чёрный песок, Камни, Риф, Галька, Песок и камни, Смешанное), «Лучший сезон» (Круглый год, Весна — лето, Лето — осень, Осень — зима, Зима — весна, По погоде), «Направление волны» (Правая, Левая, Левая и правая, Переменная).
     TZ SPT-08 asks for multiple wind directions — make it multi-select in the port.
  3. **03 «Описание, доступ и безопасность»** — hint «Полезные уточнения для тех, кто впервые едет на этот спот». Textareas: «Краткое описание» (placeholder «Что важно знать об этом месте?»), «Природные особенности» + hint «Через запятую» (placeholder «Вулканы, пляж, горы»), «Инфраструктура» + «Через запятую» (placeholder «Парковка, кафе, прокат»), «Как добраться / ограничения доступа» (placeholder «Подъезд, тропа, парковка, проход к воде…»), «Опасности и особенности безопасности» (placeholder «Течения, камни, холодная вода, зоны ограниченного доступа…»).
  4. **04 «Дополнительная информация»** — hint «Необязательно, но поможет проверить предложение». «Комментарий для модератора» (max 1400, placeholder «Например: был здесь неделю назад — лучший ветер северо-восточный, а не западный…»), «Как к вам обращаться» (max 100, placeholder «Имя», prefilled with user name), «Email для уточнений (необязательно)» (placeholder «name@example.com»), «Ссылка на фото, видео или источник (необязательно)» (url, placeholder «https://…»). TZ SPT-08 also wants photo uploads as evidence (UX-08 uploader).
* Live **review strip**: icon «↗», title «Пока нет изменений» / «Изменено полей: {n}» / «Есть уточнение для модератора»; detail: changed field labels joined by « · » (max 4 + « и другие») / «Можно отправлять комментарий без изменения параметров.» / «Измените параметры или напишите комментарий (от 10 символов).»; right pill «Предложение».
* Actions: pill «Отмена», primary «Отправить на модерацию →» — **disabled until ≥1 changed field or a comment ≥10 chars**.
* Privacy note: «Это демоверсия. Пока нет серверной доставки: предложение сохранится в вашем браузере и будет доступно для выгрузки. Публичные данные спота не изменятся.»
* Diff model sent: `{id:"SP-…", spotId, spotName, region, createdAt, status:"pending_local", author, email, note, evidence, changes:[{key,label,before,after}]}` — a good basis for the moderation API (TZ TRUST-04: было/стало, источник, решение, уведомление, откат).

### 4.7 Suggestion success & «Мои предложения» — `public-spot-edit-success-1440.png`, `public-spot-suggestions-queue-1440.png`

* Success modal (centred): 60px circle «✓», overline «ЗАЯВКА ПОДГОТОВЛЕНА», h2 «Спасибо за уточнение!», p «Предложение для спота **{name}** сохранено. В опубликованную карточку изменения не вносились.», box «Номер предложения **SP-MVH55THR-4S9**», explain «i» «**Пока это локальная очередь** Заявка ещё не доставлена модератору через интернет. Сейчас её можно скачать и передать вручную; автоматическую отправку подключим вместе с кабинетом модератора.», buttons pill «↓ Скачать заявку» (downloads JSON `ГДеволна_предложения_споты_{id}.json`) and primary «Мои предложения →».
* Queue modal: overline «ВАШИ ПРЕДЛОЖЕНИЯ», h2 «Предложения по спотам», p «Пока это локальные заявки, созданные на данном устройстве. После подключения сервера они будут поступать модератору.»; items: status pill «◷ Ожидает отправки», spot name, «{date} · {id}», changed labels or «Комментарий для модератора», pill «↓ JSON»; empty: «Пока нет предложений. Нажмите ✎ на фотографии любого спота.»; footer «Закрыть» + primary «Скачать все заявки ↓». In the port: list the user's suggestions with real statuses (pending/approved/rejected) instead of JSON downloads.

---

## 5. GG Surfer (`#gg`) — `public-gg-1440.png`, `public-gg-list-1440.png`, `public-gg-390.png`

1. Hero (home variant): h1 «GG Surfer — свои<br> на каждом берегу», text «Кто подскажет дорогу к споту? С кем поехать на рассвете? Где найти компанию в незнакомом регионе? Здесь встречаются свои.», CTA «Стать GG Surfer →» → `#profile` (guest → registration).
2. Heading (grid text | mini-stat): eyebrow «ДОБРО ПОЖАЛОВАТЬ В СООБЩЕСТВО», h2 (36px) «Люди рядом с волной», p «Ищите участников по регионам, изучайте анкеты, находите компанию и начинайте личное общение.»; mini-stat card «♡ **5** анкет на карте · демо» (count of GG members + own profile).
3. **Intent panel** `.gg-intent`: micro «ПРОСТО ВЫБЕРИТЕ, ЧТО ВАМ НУЖНО», h3 «Поиск своих — без неловких знакомств»; chips «Все участники» · «Покажу спот» · «Ищу компанию» · «Подвезу» (single-select; mirror the status select).
4. **Filters**: search input (placeholder «Поиск по имени или месту», matches name/region/town, live), region select, status select (Все статусы, Покажу споты, Ищу компанию, Могу подвезти), pills «Сбросить» and «✉ Мои чаты» (→ inbox).
5. **Mode tabs**: «⌖ На карте» / «☷ Списком» + right note «Точки на карте приблизительные, анкеты демонстрационные».
6. **Widget** (map 1fr + member list 325px; stacked ≤810):
   * **Schematic map** `.gg-local-map` (470px, 310px ≤600): head card «Свои на карте» / «Координаты приблизительные · карта схематичная», button «Спутник Яндекса ↗» (switches to a Yandex satellite iframe with «← Схематичная карта» back button), stylised land shape, region labels ЛАДОГА / КРЫМ / КАМЧАТКА / САХАЛИН / ПРИМОРЬЕ, avatar pins with first names (picked pin = pink ring, lifted), bottom captions «⌖ Выберите участника прямо на карте» and «◈ GG Surfer». Pins are placed with hard-coded percentage coordinates per person (`mx/my`), clamped to 11–89% / 18–88%.
   * **Member list** «Люди на карте · {n}»: rows = 55×59 photo, **name ✓** (✓ if certified), «⌖ {region}», «{status} · {n} лет в сёрфинге»; under each row pill «✉ Написать» (title «Написать {name}») → GG chat (guest → registration). Click on a row selects it (highlight + toast «{name} · {status} · {region}»). Full-width primary «Посмотреть анкету →» opens the selected person (instructor modal). Notice «Публичные маркеры приблизительны. Домашний адрес не показываем.» Empty: «Пока здесь нет участников. Станьте первым!».
   * **List mode** puts the members in a 2-column grid (1 column ≤600). **Bug:** the schematic map stays visible in list mode (CSS only hides `.mapbox`).
7. **Kindness panel** (blue gradient): eyebrow «НАЧИНАЕМ С ПРОСТОГО», h3 «“Привет! Я завтра на споте. Поедем вместе?”», p «Не нужно долго искать контакты: откройте анкету, узнайте планы и начните беседу прямо здесь. Пока она сохраняется только в вашем браузере.», white pill «Мои сообщения →» (→ inbox).
8. **Quick how** (3 glass cards; 1 column ≤540): «⌖ Найдите своих» / «Регион, интересы, планы и любимые волны.»; «✉ Начните беседу» / «Напишите участнику прямо из профиля или списка рядом с картой.»; «✓ Общайтесь спокойно» / «Приватность и будущая добровольная верификация.»
9. Notice: «**GG Surfer — не отдельная роль.** Этот статус доступен сёрферу, инструктору и представителю школы — при регистрации или позже.»
10. Wide banner.

Data: GG members are the instructors with `gg:true` (5 of 6) + the logged-in user if `gg && public` (status from the cabinet select). TZ COM-02/03: a real community catalogue (photo, region, level, boards/spots, experience, interests, about) with privacy settings and approximate location — not instructor records.

---

## 6. Аренда (`#rentals`) — `public-rentals-1440.png`, `public-rentals-390.png`, `public-rentals-empty-1440.png`

1. Hero (people variant): h1 «Аренда снаряжения», text «Доска или гидрокостюм на пару дней — найдите снаряжение у своих в нужном регионе.»
2. Intro row: eyebrow «ОДИН БЕРЕГ · МНОГО ВОЗМОЖНОСТЕЙ», h2 «Возьми с собой только желание кататься», p «Выбирайте снаряжение по региону и размеру. Все предложения и цены сейчас демонстрационные.»; right pill «+ Сдать своё снаряжение» (guest → registration + toast «Для объявления сначала нужен профиль»; user → own listing form §6.5). Stacks ≤810.
3. **Filter bar** (`.rent-filterbar`, light panel, labels above selects; 4 + full-width reset ≤1100; 2 columns ≤810): «Регион» (Все регионы + 5), «Категория» (Всё снаряжение, Доска, Гидрокостюм), «Цена за день» (Любая цена, До 1 000 ₽, До 1 500 ₽, До 2 000 ₽), «Размер» (Все размеры + sizes present in data: 9′2″, M, 6′4″, S, 7′6″, L, 5′10″, XL — mixes board lengths and suit sizes; split by category in the port), pill «Сбросить».
4. Meta: «Показано {n} предложений · цены и владельцы приведены для демонстрации».
5. **Grid of rental cards** (4 / 3 ≤1100 / 2 ≤810 / 1 ≤380): illustrated art area 215px (158px ≤600) with tint per item, watermark «ГДЕВОЛНА • АРЕНДА», board or wetsuit SVG (rotates/lifts on hover), bottom label «СЁРФБОРД» / «НЕОПРЕН» + «◌»; body: micro-label «{region} · {town}» + small like button; h3 title (e.g. «Лонгборд 9′2″ · Sea Glass»); description; chips {size} · {type} · «У {owner}»; footer «**1 700 ₽**» + «/ день · пример» and primary «Подробнее →» (full width ≤600).
6. Empty: board illustration, h3 «Эти доски укатили на волну», p «Попробуйте другой регион, размер или бюджет.», pill «Сбросить фильтры →».
7. **Safe strip**: «◈» + **«Бережно относимся к чужим вещам»** + «В будущем: проверка владельцев, фотофиксация состояния, залог, правила повреждений и платежи через защищённого провайдера. Сейчас никаких списаний и гарантий нет.»
8. Wide banner.

### 6.1 Rental detail modal — `public-rental-detail-1440.png`

Wide: kicker «ГДЕВОЛНА · АРЕНДА»; grid 220px art | text (stacked ≤600): h2 title, p info, «**Где:** {region}, {town}», «**Размер:** {size}», «**Владелец:** {owner}», big price «1 400 ₽» + «/ день · пример»; notice «Заявки пока не отправляются другому пользователю. Для реальной аренды нужно подключить аккаунты, договор и платежи.»; footer pill «♡ В избранное» (does not show the active state — bug) and primary «Запросить аренду →».

### 6.2 Rental request modal

Guest → registration + toast «Сначала создайте демо-профиль». User: kicker «ЗАЯВКА НА АРЕНДУ · ДЕМО», h2 title, p «{region} · {price} за день», dates «Забрать *» / «Вернуть *» (min = tomorrow), textarea «Сообщение владельцу» (placeholder «Привет! Хочу арендовать снаряжение...», max 500), notice «Демо-заявка сохраняется только на вашем устройстве и не дойдёт до владельца. Оплаты и залога здесь нет.», primary «Сохранить демо-заявку →». Return before pick-up → toast «Дата возврата не может быть раньше выдачи». Success → toast «Демо-заявка сохранена в вашем браузере» and navigation to the cabinet. API: availability per physical item and transactional booking (TZ RENT-03/05).

### 6.3 Own listing modal («+ Сдать своё снаряжение»)

Kicker «МОИ ОБЪЯВЛЕНИЯ · ДЕМО», h2 «Поделиться снаряжением», p «Заполните карточку, и она появится в этом браузере. Не будет опубликована для других людей.»; fields «Что сдаёте? *» (placeholder «Например, лонгборд 9′0″», max 90), «Тип» (Доска / Гидрокостюм), «Регион» (5 regions, default = user region), «Размер *» (placeholder «M / 8′0″», max 15), «Цена, ₽ за день *» (1…50000, placeholder «1200»), «Описание *» (placeholder «Состояние, комплект, особенности...», max 250); primary «Добавить в демокаталог →». Success: the item is prepended to the catalogue, user gets `rent=true`, toast «Объявление добавлено в демонстрационный каталог». No photos (TZ RENT-01 requires them, UX-08 uploader).

---

## 7. О нас и клуб (`#club`) — `public-club-1440.png`, `public-club-390.png`

No hero; content in `.wrap`:

1. **Club hero card** (photo banner with gradient, radius 13): kicker «НАШ МАЛЕНЬКИЙ БОЛЬШОЙ КЛУБ», h2 (31px) «Добро пожаловать, дорогой друг.», p «Неважно, давно ли ты в сёрфинге. Если тебе близки люди, волны и маленькие приключения — здесь тебя ждали.», pill «Присоединиться к клубу →» → registration (**also for logged-in users** — should go to the cabinet/club join flow).
2. **Member club** (grid 1fr / 1.3fr; stacked ≤810):
   * Member card (blue gradient, big faded «≋» watermark): top «ГДЕВОЛНА • КЛУБ» / «№ —» (user: «№ 001 • DEMO»), logo «≋», name «Будущий участник» (user: user name), bottom «МЕСТО ДЛЯ СВОИХ» (user: «СВОЙ НА БЕРЕГУ») / «✦ 2026».
   * Invite: eyebrow «КЛУБНАЯ ИСТОРИЯ НАЧИНАЕТСЯ ЗДЕСЬ», h2 «Волны бывают разные. Свои — всегда рядом.», p «Клубная карточка, маленькие достижения, приветственный электронный стикер и будущие знаки внимания от «Гдеволны».», primary «Получить стикер GG Surfer ↗» (guest → toast «Сначала вступите в клуб — создайте профиль» + registration; user → downloads `GG_Surfer_приветственный_стикер.svg`, toast «Стикер скачан. Добро пожаловать в клуб!»), pill «Мой профиль» → `#profile`.
3. **Achievements**: header section title «Маленькие достижения» + right note «Значки хранятся только в браузере»; 5 tiles (3 columns ≤810, 2 ≤600): «◈ На берегу / Добро пожаловать в клуб» (has account), «♡ Хранитель спотов / Сохрани хотя бы одно место» (≥1 favourite), «≋ Свои люди / Включи GG Surfer», «⌖ На связи / Создай чат или заявку», «✦ Следующая волна / Скоро новые клубные события» (never). Footer of each tile «Открыто» (teal, unlocked tile tinted, icon filled blue) / «Впереди». Demo-only (TZ COM-09: achievements later).
4. **Roadmap strip** (3 columns, 1 ≤600): «01 · ПУТЬ В КЛУБ / Гость → Свой на берегу», «02 · КЛУБНЫЕ ЗНАКИ / Нашивки, наклейки, стикеры», «03 · БУДУЩИЕ ПРИВИЛЕГИИ / Подарки, встречи, партнеры».
5. Section title «Что делает «Гдеволну» особенной» + 6 perk glass cards (3/2/1 columns) with emoji: 🌋 «Сёрфинг по-русски» — «Вулканы Камчатки, северные озёра, суровые моря и тёплые люди.»; 🤝 «Помогаем друг другу» — «Местный сёрфер может показать тропу, подвезти или просто составить компанию.»; 🏄 «Находим волну и людей» — «Споты, инструкторы, общение, аренда и снаряжение — рядом, без лишней суеты.»; 🎁 «Клубные вещи» — «Нашивки, стикеры, флиски, термосы, наклейки на машины и добрые призы.»; 📷 «Истории сообщества» — «Фото-челленджи, поездки, региональные истории и маленькие победы.»; 🧭 «Проверенная информация» — «Советы тех, кто действительно живёт и катается в своём регионе.»
6. Wide banner «Здесь никто не чужой» / «Найдите знакомых на берегу. Даже если приехали впервые.» / pill «Открыть GG Surfer →».

No events/calendar exist (TZ CLB-01..03 deferred).

---

## 8. Шейперы (`#shapers`) — shell only

Hero (people variant): h1 «Каталог шейперов», text «Мастерские, авторские модели досок и личные кабинеты шейперов — в одной ГДеволна.» Then section head «Шейперы и их доски» / «Полный каталог, модели, заявки и кабинет — прямо внутри сайта.», a full-width iframe (min 650px, `calc(100dvh - 115px)` up to 1100px) with the separate shapers document, and a note «Прокручивайте содержимое внутри окна мастерских. Верхнее меню переключает остальные разделы ГДеволна.» Content → shapers documentation (`docs/prototype/source/shapers.html`). In Next.js the shapers catalogue becomes normal routes, not an iframe.

---

## 9. Search modal (header search) — `public-search-modal-1440.png`, `public-search-modal-390.png`

Standard modal: h2 «Что ищем?», p «Споты, сёрферов или своих людей.», search box with «⌕» and input (placeholder «Например: Камчатка, Алексей, Ладога», autofocus). Live results (case-insensitive substring over name + region + town) across spots and **all** instructors, max 8: rows with 55×59 photo, **name**, «{region} · Спот» or «{region} · Сёрфер» (instructors are labelled «Сёрфер» — inconsistent); click → spot/instructor modal. Empty input: «Начните вводить название или имя.» No result message for "nothing found" (same text). TZ NAV-04: unified search with result types (spots, instructors, schools, boards, equipment, users).

## 10. Favourites modal (header heart) — `public-favorites-1440.png`, `public-favorites-empty-1440.png`

Works for guests (stored locally). h2 «♡ Избранное», p «Ваши сохранённые споты и сёрферы.», rows (photo, **name**, region, «Открыть карточку →») → detail modal. Empty: «Пока пусто. Нажмите на сердечко в любой карточке — и она появится здесь.» **Bug:** saved rentals are counted in the header badge but not listed. API: favourites for spots, instructors, schools, boards, shapers, equipment (TZ MSG-11); for guests either require login or keep a local list and merge on sign-in.

## 11. Inbox & chat entry points

### 11.1 Inbox (header chat icon, «✉ Мои чаты», «Мои сообщения →») — `public-inbox-empty-1440.png`

Guest → registration (no toast). User: wide modal, kicker «ОБЩЕНИЕ · ГДЕВОЛНА», h2 «Все сообщения», p «Друзья GG Surfer и инструкторы, у которых подтверждены занятия.», rows «✉» avatar, **name**, «Знакомство GG Surfer · {n} сообщений» or «Запись {date} · {n} сообщений», «→». Empty: «≋», «Сообщений пока нет», «После подтверждения записи откроется чат с инструктором.» The cabinet has its own «Обращения» pane (cabinet doc).

### 11.2 Chat modal (GG) — `public-chat-gg-1440.png`

Header: 49px photo, kicker «GG SURFER · ЗНАКОМСТВО» (lesson chats: «ЧАТ ПО ПОДТВЕРЖДЁННОМУ ЗАНЯТИЮ» + date/slot), h2 name. Message box (min 200, max 310px, scroll to bottom): bubbles left/right with small «Инструктор/Ученик · HH:MM»; empty «Здесь начинается общение» / «Поздоровайтесь и уточните детали встречи.». Form: textarea «Сообщение» (placeholder «Привет! Подскажите, пожалуйста...», max 1000, required), primary «Отправить сообщение →». Note «Это демонстрационный чат, переписка сохраняется только на этом устройстве. В реальной версии сообщения будут доставляться участникам через сервер.» Lesson chats open only after the booking is accepted (toast «Чат появится после подтверждения занятия») — TZ MSG-03/MSG-09 want the dialog to exist from the first request. Also needed: attachments (MSG-04), unread counters (MSG-06).

---

## 12. Authentication UI (public part)

* There is **no sign-in form, password, email/phone verification or recovery** in the prototype. «Войти» always starts a demo registration that creates a local profile; «Выйти» lives in the cabinet. TZ ACC-13 requires real login, recovery and verification — design the login screen in the same modal style (reuse step-1 layout and `.field` inputs).
* **Guest cabinet page** (`#profile` without user; only reachable via hash): hero «Здесь начинается<br> ваша история» / «Заведите профиль, сохраняйте споты и находите своих людей на каждом берегу.» / CTA «Создать профиль» (→ home, bug); two side cards: «Присоединяйтесь к «Гдеволне»» / «Выберите роль: сёрфер, инструктор или школа. Статус GG Surfer доступен для всех.» / primary «Создать аккаунт →»; «Уже с нами?» / «В демо-проекте профиль сохраняется только в браузере.» / pill «Демо-регистрация» (both open registration).

### 12.1 Registration step 1 — `public-register-step1-1440.png`, `public-register-step1-390.png`

Wide modal: h2 «Добро пожаловать в «Гдеволну»!», p «Давайте познакомимся. Выбирайте основную роль — GG Surfer доступен для каждой.», 2-segment progress bar (first filled), bold «Кто вы в нашем сообществе?», role tiles (3 columns; ≤540 2+1): «🏄 Сёрфер» (default), «♧ Инструктор», «🏠 Сёрф-школа» — selected tile has a 2px blue border.
Panel «Дополнительные направления» / «Можно выбрать несколько — они появятся в одном личном кабинете.» with checkbox chips «♧ Сёрф-инструктор», «◈ Шейпер», «⌂ Сёрф-школа» (the main role is excluded) — added by the account engine (TZ ACC-01).
Toggle rows (58px toggles): «♡ Хочу быть GG Surfer» / «Появляться в поиске сообщества, находить компанию, помогать друг другу.»; «◈ Сдаю снаряжение в аренду» / «Смогу добавлять доски и гидрокостюмы в каталог аренды. Доступно сёрферу, инструктору и школе.» Notice «GG Surfer можно включить или выключить и после регистрации. Он не меняет основную роль.» Full-width primary «Продолжить →».

### 12.2 Registration step 2 — `public-register-step2-instructor-1440.png`

h2 «Пара слов о себе», p «{Сёрфер|Инструктор|Сёрф-школа}. {С GG Surfer вас смогут найти люди поблизости. | GG Surfer можно будет добавить позже.}», progress bar (both filled). Form (2-column grid; 1 column ≤540):

| Field | Type / rules | Placeholder / options |
|---|---|---|
| «Имя и фамилия *» | text, required, autocomplete name | «Как к вам обращаться» |
| «Имя пользователя *» | required, pattern `[a-zA-Z0-9_]{3,24}`, title «Латиница, цифры, _ от 3 до 24 символов» | «surfer_123» |
| «Электронная почта *» | email, required | «you@example.com» |
| «Дата рождения *» | date, required, max = today | — |
| «Пол *» | select, required | «Выберите», «Женский», «Мужской» |
| «Регион *» | select, required | «Выберите регион», 5 regions, «Другой регион» |
| «Уровень катания» | select | Начинающий, Средний, Продвинутый |
| «Тип доски» | select | Лонгборд, Шортборд, Фанборд, Пока без своей |

«Выберите минимум 3 интереса *» — toggle chips: Сёрфинг, Кемпинг, Сноуборд, Путешествия, Фотография, Походы, Шейпинг, Йога, Экология, Кофе у океана.
Instructor: «Квалификация» (placeholder «Номер сертификата / организация (при наличии)»). School: «Название школы / юрлица» required (placeholder «Название, ИП / ООО»). Instructor & school: dashed box «Документы для профиля» / «Основной документ обязателен. Дополнительный — по желанию.» with file inputs «Документ о профессиональном статусе или регистрации деятельности *» (school: «Регистрационный документ школы / ИП / ООО *») and «Сертификат / подтверждение квалификации (необязательно)», accept `.pdf,.jpg,.jpeg,.png,.webp`, small «Только PDF и изображения до 10 МБ. В прототипе файлы не загружаются на сервер и не сохраняются — после регистрации показываем лишь имена выбранных файлов.»
Consent checkbox (required): «Согласен на демонстрационное сохранение профиля в этом браузере. Настоящее согласие на обработку данных и публичность будет оформлено при запуске проекта.» Buttons pill «← Назад», primary «Создать демо-профиль →». Note «В реальной версии вход будет с подтверждением email/телефона, проверкой согласий и безопасным хранением. Здесь данные не передаются на сервер; email, дату рождения и пол локально не сохраняем.»
Validation toasts: «Выберите хотя бы три интереса», «Укажите дату рождения», «GG Surfer доступен только участникам от 18 лет» (GG on and age <18), «Документы: PDF/изображения, не более 10 МБ», «Добавьте основной документ». Success → user saved, navigation to the cabinet, toast «Добро пожаловать в «Гдеволну»! ♡».
Note: TZ INS-03/INS-05 say the certificate is optional and workplace documents are not required for independent instructors — the prototype makes a "professional status" document **mandatory** for instructors; confirm with product.

---

## 13. Other modals

### 13.1 «Скоро на «Гдеволне»» (fallback for unknown actions)
h2 «Скоро на «Гдеволне»», p «Эта часть предусмотрена в структуре платформы, но сейчас показан дизайн-прототип.», notice «Чтобы добавить настоящие данные, потребуются сервер, проверка профилей, модерация и необходимые интеграции.», primary «Понятно».

### 13.2 «✓ Верификация личности» (from the cabinet)
p «В будущем участник сможет добровольно подтвердить личность, чтобы общение на GG Surfer было спокойнее.», notice «**Как запланировано:** переход к партнёру проверки личности, паспорт и селфи — внутри защищённого сервиса, в «Гдеволну» возвращается только статус результата. Сканы документов в публичном профиле никогда не появятся.», p «Эта функция пока не подключена. Никаких паспортных данных прототип не принимает и не сохраняет.», primary «Понятно».

### 13.3 «Онлайн-трансляция» (home live panel) — `public-stream-modal-1440.png`
p «Укажите ссылку на видео YouTube или RuTube — встроим в демонстрационное окно на главной.», field «Ссылка на трансляцию» (placeholder «https://www.youtube.com/watch?v=...»), primary «Сохранить», pill «Очистить». Only https YouTube (`youtu.be`, `youtube.com`, `m.youtube.com` → `youtube-nocookie.com/embed/{id}`) and RuTube (`/video/{id}` → `rutube.ru/play/embed/{id}`) are accepted; otherwise toast «Подойдут ссылки YouTube или RuTube»; success toast «Окно трансляции обновлено». Admin-only in production.

---

## 14. Demo-only behaviour → what the real app must do

| Prototype behaviour | Real implementation |
|---|---|
| Hard-coded arrays `PEOPLE`, `SPOTS`, `RENTALS`, `SAMPLE_REVIEWS`, `priceDemo` | API (`/spots`, `/instructors`, `/rentals`, `/reviews`), seeded from `seed_public.json` only where classified as seed |
| Ratings «★ 4.9 (24 отзывов)», spot «★ 4.8 (18)» are constants (+ local reviews) | computed from published reviews server-side; demo numbers must not be imported (TZ PL-02, TRUST-01) |
| Certificate badge from a boolean, labelled «демо» | 3 states none / uploaded / verified with moderator verification (INS-03/04, TRUST-03) |
| Prices «Занятие от 3 800 ₽ / Пример цены» | instructor offers with price, duration, format (INS-08) |
| Calendar availability: Mon/Thu closed, 09/12/15 slots, local overrides | instructor schedule API, server-side conflict checks (INS-06/07) |
| Booking, chat, reviews stored in localStorage; «Имитировать принятие» buttons | bookings + messaging + reviews APIs with real accounts (MSG-10) |
| GG members = instructors with `gg:true`, map positions `mx/my` in % | community profiles with privacy + approximate location (COM-02/03/07/08) |
| Spot suggestions saved locally and downloadable as JSON | moderation queue with statuses and notifications (TRUST-04) |
| Stream URL editable by anyone | admin/CMS setting |
| Favourites in localStorage (guest) | per-user favourites API |
| Achievements unlocked by local flags, sticker download | club module later (COM-09, CLB-*) |
| «Найдено: N», «5 анкет на карте · демо», header counters | API counts / unread counters from server events (MSG-06/07) |
| Registration without server, «Войти» = demo registration | real auth: login, recovery, email/phone verification, consents (ACC-13, TRUST-09) |
| Yandex map widget iframes with `pt=` markers | interactive map component with clustering and card popups (SPT-01) |

## 15. Inconsistencies & bugs found (fix, don't port)

1. **Wind/swell roses are lost**: the gallery script's `showSpot` overrides the premium version; the final modal shows decorative rings that don't indicate direction. Implement the rose (SPT-04).
2. **GG list mode** still shows the schematic map (`.gg-list-view .mapbox{display:none}` doesn't match `.gg-local-map`).
3. **Favourites modal ignores rentals** but the header badge counts them; the rental detail «♡ В избранное» never shows the active state.
4. **Search** labels instructors as «Сёрфер»; no "nothing found" state.
5. **Instructor filter «Уровень катания»** filters by the instructor's riding level, while cards show «Уровень учеников».
6. **Spot names in instructor data** are free text and include non-spots («Тихий океан», «Охотское море», «Южно-Сахалинск»); spot «Ладожские шхеры» region coordinates `61.60, 30.80` and other coordinates are approximate («требуют проверки»).
7. **Spot cover photos**: Sakhalin cover is a news photo of a grounded container ship with MAERSK branding; Ladoga/Olenevka photos look like Street View captures — rights unclear (ASSETS.md).
8. **Instructor modal tabs** overflow on 390px (third tab cut).
9. **Club hero «Присоединиться к клубу →»** opens registration even for logged-in users; guest cabinet hero CTA «Создать профиль» navigates to home instead of registration.
10. **Spot edit form** is available to guests; review/booking/chat are not — align with TZ table 16.
11. **Mobile navigation** is a scrolling top strip; TZ requires a bottom tab bar (NAV-03, UX-03).
12. **Icons** are mixed Unicode glyphs and SVGs with different stroke widths (UX-04); rating stars in the review metric are always 5 gold stars regardless of the value.
13. **«Открыть спутник ↗»** must be removed from the spot card (SPT-09).
14. Brand spelling varies: «Гдеволна.рф», «Гдеволна», «ГДеволна», «ГДЕВОЛНА.РФ» — confirm canonical form (SHOP-03).
15. Legacy unused code: `mapSVG()` schematic map, `.map-marker*`, `.board-grid` model row, the first `showPerson`/`showBook` implementations.
16. Images with baked-in text/artefacts: `about-intro-surfer.webp` (cropped old mock-up text), `feature-shaper-workshop.webp` (cropped banner text/button), white circle artefacts in feature thumbnails, AI watermark on avatars.

## 16. Screenshot index (`docs/prototype/screens/`)

| File | Content |
|---|---|
| public-loader-1440.png | site loader |
| public-component-header-1440.png | top bar with favourites badge |
| public-home-1440.png / public-home-390.png / public-home-390-viewport.png | home page (full / mobile full / mobile first screen) |
| public-people-1440.png / public-people-390.png / public-people-390-filters.png | instructors catalogue |
| public-people-empty-1440.png | instructors empty state |
| public-person-modal-1440.png / -390.png | instructor modal, tab «О знакомстве» |
| public-person-calendar-1440.png / -390.png | instructor modal, tab «Календарь занятий» |
| public-person-reviews-1440.png | instructor modal, tab «Отзывы ★» |
| public-reviews-modal-1440.png | «Отзывы о …» modal |
| public-booking-step2-1440.png | booking step 2 (logged-in) |
| public-spots-1440.png / public-spots-390.png / public-spots-390-viewport.png | spots page |
| public-component-spot-card-liked.png | spot card with active heart |
| public-spot-modal-1440.png / -390.png | spot detail (final prototype version) |
| public-spot-modal-rose-variant-1440.png | spot detail with the intended wind/swell roses and photo caption |
| public-spot-edit-form-1440.png / -390.png | «Предложить исправление» form |
| public-spot-edit-success-1440.png | suggestion success |
| public-spot-suggestions-queue-1440.png | «Мои предложения» |
| public-spot-review-modal-1440.png | spot review form |
| public-gg-1440.png / public-gg-list-1440.png / public-gg-390.png | GG Surfer (map / list / mobile) |
| public-chat-gg-1440.png | GG chat (empty) |
| public-rentals-1440.png / public-rentals-390.png / public-rentals-empty-1440.png | rentals |
| public-rental-detail-1440.png | rental detail |
| public-club-1440.png / public-club-390.png | club page (guest) |
| public-search-modal-1440.png / -390.png | search |
| public-favorites-1440.png / public-favorites-empty-1440.png | favourites |
| public-inbox-empty-1440.png | inbox (logged-in, empty) |
| public-register-step1-1440.png / -390.png | registration step 1 |
| public-register-step2-instructor-1440.png | registration step 2 (instructor role) |
| public-stream-modal-1440.png | live stream settings |
