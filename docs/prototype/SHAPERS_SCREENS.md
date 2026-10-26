# ГДеволна — Shapers module («Шейперы»): screens, copy and behaviour

> **Scope.** Everything inside `docs/prototype/source/shapers.html`:
> - the public board catalog;
> - the shaper (workshop) cabinet;
> - modals, chat, uploads, statistics.
>
> The same document is embedded verbatim into `proto.html` as JSON in `<script id="gv-full-shapers-document">`.
>
> **Audience.** Frontend (Next.js + TS) and backend (Django) implementers who will not open the prototype.
>
> **Conventions.**
> - Russian UI copy is quoted verbatim in «…» or `code`.
> - English is used for structure.
> - TZ IDs (SHP/BRD/SHO/MSG/MET/UX/RENT/PAY) reference `docs/TZ.md`.
> - Where the prototype and TZ disagree, **TZ wins** (see §12 and `CABINET_NOTES.md`).
>
> **Companion files.**
> - `frontend-port/styles/prototype-shapers.css`: consolidated CSS of this module, original class names.
> - `frontend-port/icons-cabinet.json`: sprite icons `i-*`, board silhouettes `board-*`, select chevron.
> - `frontend-port/seed_cabinet.json` → key `shapers`: demo shapers, models, requests and chats; all user-generated content is marked `demo:true`.
> - `frontend-port/assets/shaper-board-*.svg`: the 7 generated board silhouettes.
> - Screenshots: `docs/prototype/screens/cabinet-shapers-<screen>-<1440|390>.png` (list in §13).

---

## 1. How the prototype is put together

### 1.1 Panes and navigation primitives
The single HTML page has three `<section class="pane">` elements. Exactly one has `.active` (`display:block`, 0.28 s fade-in).

| pane id | what | notes |
|---|---|---|
| `#catalog` | Public catalog «Каталог шейперов» with tabs «Все доски» / «По шейперам» | opened by `showPage('catalog')` |
| `#dashboard` | «Личный кабинет шейпера»: sidebar + panels `#panel-<name>` | `showPage('dashboard')`, panel switching via `switchPanel(name)` |
| `#registration` | Legacy pane, **always hidden** (`display:none!important`); text «Регистрация перенесена в раздел «Профиль» личного кабинета.» | `showPage('registration')` is redirected to `dashboard` + panel `profile` |

Dashboard panels (`switchPanel(p)`; alias `messages` → `requests`):
- `overview`
- `boards`
- `requests`
- `outgoing`
- `bookings`
- `statistics`
- `reviews`
- `profile`
- `settings`

**Initial state.** The last script ends with `showPage('dashboard'); switchPanel(data.profile?.workshop ? 'overview' : 'profile')`:
- a first-time visitor lands on the **shaper registration form**;
- a registered shaper lands on the **overview**;
- the catalog is never the default.

This is a gap: the public page must open the catalog (SHP-07, ATX-02).

### 1.2 Script layering (what the final behaviour is)
The JS is a stack of monkey-patches. The *last* definition wins, and each layer usually calls the previous one.

| layer | lines | adds |
|---|---|---|
| base | 527–606 | data model, starter data, cards, profile form, board modal, simple chat, catalog, order modal, order status machine, bulk table, deal stats |
| extension v2 | 609–1039 | «Ган» type, generated board silhouettes, IndexedDB media, photos ≤10 + video, promo video, SKU generator, «Фото и параметры» viewer, custom materials, repair flag |
| v3 | 1041–1184 | rich shaper cards «По шейперам», shaper profile modal, demo inbox, chat intro, «О шейпере →» links |
| v4 | 1186–1346 | request/chat tabs, new action buttons, metrics + statistics page, badges, carousel, test incoming message, × on works photos |
| v5 | 1347–1515 | profile inside dashboard, «Посмотреть на сайте», pencil edit icon, notification badges, compact KPI strips, chat photo attachments, thread list |
| v6 | 1516–1564 | catalog card: «Фото и параметры» top-right + clickable title, live SKU preview, SKUs for demo shapers |

**Implement only the final behaviour described below.**

### 1.3 Embedding into the main site (`proto.html`)
The same document is shown in **two iframes** with `srcdoc = JSON.parse(#gv-full-shapers-document.textContent)`.

**1. Public page `#shapers`** (`gv-full-mobile-bridge-v9`, which overrides `window.shapers`):
- main-site hero `hero('people','Каталог шейперов','Мастерские, авторские модели досок и личные кабинеты шейперов — в одной ГДеволна.')`;
- block head «Шейперы и их доски» / «Полный каталог, модели, заявки и кабинет — прямо внутри сайта.»;
- `<iframe id="gvShapersEmbedded" class="gv-shaper-frame" title="Полный каталог и кабинет шейперов">`;
- caption «Прокручивайте содержимое внутри окна мастерских. Верхнее меню переключает остальные разделы ГДеволна.»;
- on parse error: «Раздел шейперов временно недоступен.»;
- iframe height:
  - desktop: `min(1100px, 100dvh − 115px)`, min 650;
  - ≤810px: `100dvh − 155px`, min 570;
  - ≤370px: `100dvh − 145px`, min 500.

**2. Account pane «Шейпер»** (`gv-unified-account-engine`, documented in CABINET_SCREENS):
- `<iframe id="gvUnifiedShaperFrame" class="gv-ac-shaper-frame" title="Рабочий кабинет шейпера">`;
- height 860px (min 560; ≤710px `100dvh − 165px`, min 550);
- below it, «Посмотреть публичный каталог шейперов →» (`data-go="shapers"`).

Consequences:
- **Both iframes show the same dashboard-first document.** The public page shows the cabinet/registration form inside the site, with a second header (`cabinet-shapers-embedded-public-1440.png`).
- **Storage is shared.** A `srcdoc` iframe inherits the parent origin, so localStorage and IndexedDB are shared with the main page. The account engine reads `gdevolna_shaper_demo_v1` to show counters («Моделей досок», «Входящих заявок», «Досок в наличии», «Мастерская оформлена»).
- **No bridge.** There is no postMessage link between the frames. The main-site user (`gg_user`) is unknown inside the iframe; the shaper identity is the separate local `data.profile`.

**Production mapping (recommended).**
- Native pages, no iframes:
  - `/shapers` = catalog (tabs as query `?view=boards|makers`);
  - `/shapers/[slug]` = profile, rendered as a modal over the catalog with a deep link (SHP-10);
  - the board viewer as a modal with its own URL `?board=<id>`;
  - the cabinet as `/account/shaper/*` sub-routes inside the unified account.
- Drop the embedded header.

---

## 2. Global chrome of the shapers document

### 2.1 Frame and page
- `.site`: max-width 1420px, padding 18/22/32px. Behind it a fixed bottom landscape `img/img20.webp` at 22% opacity.
- `.frame`: white-blue card, radius 20px, 1px `#d8effd` border, shadow `0 12px 42px rgba(10,91,139,.1)`.
- ≤830px: frame borderless and full-bleed (`padding:0`, radius 0).
- Body font: `Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif`, 14px, colour `--ink #123f69`. This differs from the main site's «Trebuchet MS»; see the CSS header.
- Body background: `linear-gradient(160deg,#f9feff,#ebf9ff 54%,#f5fcff)`.

### 2.2 Embedded top bar `header.topbar` (74px; 62px ≤610px)
Left to right:

**1. Logo** `img/img24.png` (112×69) → `showPage('catalog')`.

**2. `nav.nav-links`** (hidden ≤830px), 12px/650 `#174b79`. Items:

| label | action |
|---|---|
| «Каталог шейперов» | catalog |
| «Каталог сёрферов» | **opens the dashboard** (bug) |
| «Карта сёрф-спотов» | toast «Карта спотов — раздел основного сайта» |
| «Споты» | toast «Раздел спотов — в основном сайте» |
| «О нас» | toast «О проекте — в основном сайте» |
| «Блог» | toast «Блог — в основном сайте» |

**3. `.top-actions`:**
- Search icon button: toast «Поиск шейперов появится при интеграции с каталогом».
- Heart icon button: toast «Избранное будет доступно после подключения аккаунтов».
- **Messages** `#gvTopMessages`:
  - 37px circle, `#f4fbff`, border `#d0e8f5`, `#i-mail`;
  - red counter `#gvTopNotice` (`#e15d62`, white 2px ring, top −7 / right −8, `99+` cap);
  - title «Обращения и сообщения», or «Обращения · N требуют внимания» when there are pending items;
  - click → dashboard › Обращения.
- Pill «Личный кабинет» (`.outlined.nav-pill`, hidden ≤610px) → dashboard.
- Avatar 36px round (`.gv-avatar-jump`, `img/img25.jpg`) → dashboard › Профиль (UX-10).
- ≤830px: «⋯» button (`#i-more`) toggles `#mobileNav`.

**4. `#mobileNav`** (only when `.open`, ≤830px): white row of pill buttons «Каталог шейперов», «Профиль», «Личный кабинет», «Новая доска» (opens the board modal). Pills are `#eef9ff`, 1px `#d3eafb`, radius 9px. It closes on any `showPage`. See `cabinet-shapers-mobile-nav-390.png`.

> In production remove this bar; the site header and bottom nav handle navigation (UX-03). Keep the messages-badge semantics (§9).

### 2.3 Hero
- `.hero.dash` with background `img/img22.webp` (1800×420); min-height 244px (catalog 220px; 210px ≤830px). White text with a soft shadow.
- Breadcrumb 12px:
  - dashboard: «Главная  /  Личный кабинет»;
  - catalog: «Главная / Мастерские и доски».
- H1 `clamp(29px,3.2vw,46px)`, 800 (dashboard 720):
  - dashboard: «Личный кабинет шейпера»;
  - catalog: «Каталог шейперов».
- Lead text 15px:
  - dashboard: «Управляйте моделями, заявками и профилем.<br>Развивайте мастерскую с Гдеволна!» (line break per SHO-09);
  - catalog: «Найдите доску под свою волну — у мастеров со всей России.»

### 2.4 Shared components
| component | look | behaviour |
|---|---|---|
| `.card` | white 97%, 1px `#ceeafb`, radius 13px, padding 17px, shadow `--shadow` | `h3` inside: 15px/800 `#004f82` with a leading 19px icon `#008bd0` |
| `.primary` | `#006b9e` bg, 1px `#057cad`, white 750, radius 9px, padding 12×17, min-height 42px | hover `#0088c9` + lift 1px |
| `.secondary` | `#eaf7fd` bg, `#005b93`, 1px `#badff2`, radius 9px | hover `#d8f1fe` |
| `.outlined` | white bg, 1px `#b9e3fb`, radius 13px | — |
| `.plain` | text button `#0075b4` 12px/750 | — |
| `.tab` / `.tab.active` | `#ecf8ff` / active `#0277b0` white text, radius 10px | — |
| `.badge` | pill 10px/700 | colours in §7.3 |
| toast `#toast` | fixed bottom-right 20px, `#0a517c`, white 650, radius 10px, max 440px | shown 3.5 s, replaced by the next one |
| overlay `.overlay` | `rgba(2,27,46,.56)` + 5px backdrop blur; `.modal` white, radius 18px, max-width 620px, max-height 92vh, scrolls inside; close button top-right | **Esc** closes all modals. **Backdrop click** closes order, viewer, promo and shaper-profile modals but **not** the board or chat modals |
| inputs | height 39px, 1px `#bfe2f5`, radius 7px, `#fbfeff`; textarea 108px; focus outline 3px `#83cffb` | ≤610px font-size 16px (no iOS zoom) |
| select | custom chevron (`select-chevron` icon) right 9px, padding-right 30px (UX-06) | ≤450px 12px font; ≤340px 11px |
| toggle `.toggle` | 42×23 track `#bad1e2` → checked `#007eb7`, 17px knob | the main site widens to ~58px (UX-07) |
| footer note | «Демонстрационный кабинет. Все данные хранятся локально и не передаются другим пользователям.» | under the dashboard |

---

## 3. Public catalog `#catalog` (SHP-07)

Screens: `cabinet-shapers-catalog-boards-{1440,390}.png`, `cabinet-shapers-catalog-shapers-{1440,390}.png`.

### 3.1 Tools card `.catalog-tools.card`
**Segment buttons** `.catalog-switch`: «Все доски» (`#catalogAllBtn`) and «По шейперам» (`#catalogMakersBtn`). Active state is `.tab.active`.

**Filters** (grid 1.4fr 1fr 1fr; ≤830px 2 columns; ≤610px 1 column):

| label | control | behaviour |
|---|---|---|
| «Поиск» | text, placeholder «Модель, тип, мастерская...» | live on `input` |
| «Тип доски» | select | «Все типы» + union of the standard types, the user's custom types, profile types and demo models' types. Standard: Лонгборд, Шортборд, Фанборд, Фиш, Ган, SUP, Кастом |
| «Я смотрю как» | select: «Сёрфер», «Сёрф-инструктор», «Сёрф-школа», «Шейпер (мой аккаунт)» | default «Шейпер» if the workshop is registered, else «Сёрфер». It only affects order prefill and the «от имени» text. **Demo only — the role comes from the account** |

Help text: «Смена роли здесь — только демонстрация. В реальном сервисе роль определяется аккаунтом. Заказ собственных досок для шейпера заблокирован.»

**Search matching:**
- «Все доски»: model name, workshop name, region, type.
- «По шейперам»: workshop, person, region, city, about text, types, and the names/types of matching models. A type filter hides workshops with no model of that type.

**Section head:** H3 `#catalogHeading` + right muted counter `#catalogCount`:
- boards: «Все доски» / «Найдено N моделей»;
- makers: «Шейперы и их мастерские» / «Найдено N мастерских».

The N is not pluralised; fix this in production.

### 3.2 Tab «Все доски»: board card (`article.model` in `.models.catalog-models`)
Grid 4 columns (≤1100px 3; ≤830px 2; ≤610px 2 with 9px gap; ≤340px 2 narrow). Each card has a 1px `#d4edf9` border, radius 9px, white. Top to bottom:

**1. Visual** `.model-visual`:
- 180px (≥1150px; 230px at 611–1150px; 185px ≤610px; 155px ≤375px); grey-blue gradient `#f6f9fa → #e5ecf0`.
- Board picture centred, `object-fit:contain`, 82% × 88% box, drop shadow:
  - first uploaded photo if any; else the legacy `photo`;
  - else the **generated silhouette** of the board type (§3.7).
- Clicking the picture (cursor zoom-in, role button, Enter key) opens **«Фото и параметры»** (§3.5).
- **Top-right** `.gv-gallery-top` pill «[photo icon] Фото и параметры» (+ « · видео» if the model has a video) → viewer (BRD-08). White 96%, 1px `#cee6f2`, radius 9px, 10px/750 `#086791`.
- **Bottom-left** status badge (in the catalog it moves from top to bottom). Prototype bug: «Нет в наличии» gets the amber «Под заказ» colour here; use the §7.1 colours.

**2. Info** `.model-info` (padding 11/10/10):
- **Title** as a link-styled button `.gv-board-title` (13px/800 `#084b7e`, underline on hover) → viewer.
- `.model-type`: «Лонгборд · 9’2”» (type · length; «—» if empty).
- `.model-owner`: «Шейпер: **<workshop>**<br><region>».
- «[user icon] О шейпере →» (`.gv-maker-link`) → shaper profile modal.
- Price `.model-price` «75 000 ₽» (15px/850 `#004a7e`; `toLocaleString('ru-RU')` + « ₽»).
- `.gv-catalog-meta` (top border):
  - SKU chip «Арт. GV-…» (`.gv-article`: 10px/700 `#4985a6` on `#f0faff`, radius 6px);
  - spec lines `.gv-spec`: ruler «9’2” · 22” × 2.8”», droplets «65 л», fins «FCS II» (only if a fin box is set).
- CTA `.catalog-buy` full width, 11px:
  - «Заказать доску» → order modal (§3.6);
  - own board of a registered shaper: disabled grey «Это ваша доска», title «Собственную доску заказать нельзя» (SHP-11).

Empty state: `.empty-state` «Досок пока не нашлось. Попробуйте другие фильтры.»

> In the demo the "own" workshop **Kamchatka Boards** and its 4 starter models are always in the catalog. Before registration they can be ordered, and such orders appear as incoming requests in the same browser's cabinet.

### 3.3 Tab «По шейперам»: shaper card (SHP-08, SHP-09)
Layout: `.maker-list` 2 columns (1 column ≤830px), gap 15px. Card `.card.maker-card.gv-maker-card-v3[data-maker=<id>]`, inner grid `.gv-maker-main` 1fr / .98fr (single column ≤1030px), min-height 170px.

**Left: `.gv-maker-profile`** (flex column, action pinned to bottom with `margin-top:auto`):
- `.gv-maker-person`:
  - avatar 65px circle: photo for the own workshop; otherwise **initials** of the person, e.g. «АВ», on a light-blue gradient circle with a 2px `#cbe9f7` border;
  - H3 workshop name 16px `#0d4d78`;
  - `.gv-region` «Камчатский край · Петропавловск-Камчатский» (city only if set);
  - small muted person name «Андрей Волков».
- `.gv-maker-intro`: about text, 12px, **clamped to 3 lines**.
- `.gv-maker-tags` (pill tags 10px, `#f2faff`):
  - up to 3 specialisation types;
  - «Ремонт досок» in green (`#e9f8ed` / `#24714b`) if repairs are offered;
  - «Индивидуальный шейпинг» if custom orders are accepted.
- `.gv-maker-kpi` 11px: «N модель|модели|моделей · Изготовление: <lead time>» (correctly pluralised; fallback lead time «Уточняйте у мастера»).
- `.gv-maker-action` (bottom-left): «Профиль шейпера →» (`.primary`, 11px) → profile modal. Optional «▶ Промо» (`.secondary`) if the workshop has a promo video → promo modal.
  - **TZ SHP-09 wants the label «Перейти в профиль» pinned bottom-left.** On ≤1030px the button sits above the carousel; keep it at the card's bottom-left on mobile too.

**Right: `.gv-maker-showcase`** (`#f6fcff` box, 1px `#e2f1f9`, radius 10px, padding 11px):
- Head: «Доски мастерской <small>N моделей</small>» (prototype never inflects) + carousel arrows «‹» «›» (25px white squares, radius 8px, 23px glyph).
- `.gv-maker-boardline`:
  - horizontal scroller with scroll-snap; scrollbar hidden; `overscroll-behavior-x:contain`;
  - **3 boards visible on desktop** (`flex-basis:(100% − 12px)/3`), **2 visible ≤700px**;
  - arrows scroll by 2 board widths, smooth (SHP-09: browse models without opening the profile);
  - arrows are never disabled (add disabled states at the ends).
- Board tile `.gv-maker-board`: white, radius 8px; picture 85px (70px ≤480px); name 10px bold ellipsis; type 9px; price 10px `#0b6b9d`. Click → **viewer** (not the profile).
- Empty: «Модели пока не опубликованы».

Empty state: «По вашему запросу мастерские не найдены.»

### 3.4 Shaper profile modal `#gvShaperOverlay` (SHP-10)
Screens: `cabinet-shapers-shaper-profile-modal-*.png` (demo shaper), `cabinet-shapers-shaper-profile-self-1440.png` (own).

`.modal.gv-profile-modal`: width up to 1020px, max-height 100vh − 32px, scrolls. Close button × (`#gvShaperClose`, aria «Закрыть профиль шейпера»); backdrop click and Esc also close.
- Kicker `.gv-profile-topline` «ГДЕВОЛНА · МАСТЕРСКАЯ» (10px, letter-spacing .11em).
- H2 workshop name.
- Body grid 255px | 1fr (220px ≤1030px; single column ≤690px).

**Aside `.gv-profile-aside`** (gradient box, radius 13px; centred on mobile):
- Avatar 82px (photo or initials).
- H3 person name; region · city.
- Small caps titles «СПЕЦИАЛИЗАЦИЯ», «УСЛУГИ», «МАТЕРИАЛЫ», «КОНТАКТЫ», each followed by chips `.gv-profile-chip`:
  - Специализация: types, or «Не указана».
  - Услуги: «Индивидуальные заказы», «Ремонт досок», «Аренда» per flags; if none, muted «Создание моделей досок».
  - Материалы: materials, or «Уточняйте у мастера».
  - Контакты: phone / email / telegram, one per line (only the own workshop has them; demo shapers have none). Consider privacy before showing them publicly.
- «Демонстрационный профиль» (form-help) for demo shapers and for the own workshop before registration.
- Actions (full-width column):
  - «Написать шейперу» (primary) → closes the modal and opens a chat keyed by the workshop name;
  - own registered workshop: disabled secondary «Это ваша мастерская», title «Нельзя писать самому себе»;
  - optional «▶ Промо-видео» (secondary).

**Details** (right):
- About paragraph (13px, pre-wrap).
- 3 fact tiles `.gv-profile-fact`:
  - «Опыт шейпинга»: value or «Не указан»;
  - «Срок изготовления»: value or «Уточняйте у мастера»;
  - «Доставка»: first 2 methods joined by «, », or «По договорённости».
- Divider.
- Section head «Модели мастерской» + «N моделей».
- Grid of model tiles (3 columns; 2 ≤690px and ≤375px). Each tile:
  - photo button 132px (110px ≤480px) → viewer;
  - name;
  - «Фиш · 5’7” · 35 л» (length fallback «размер уточняется»);
  - price;
  - button «Оставить заявку» → closes the profile and opens the order modal; own registered workshop: disabled «Ваша доска».

Missing per TZ: rating and reviews, deep link, gallery of works, promo video inline.

### 3.5 «Фото и параметры» viewer `#gvViewerOverlay` (BRD-08)
Screen: `cabinet-shapers-model-photos-modal-{1440,390}.png`. `.modal.gv-viewer-modal` (max 760px), z-index 124.
- H2 model name; subtitle «Артикул: GV-…», or «Каталог досок» if there is no SKU.
- Body grid 1.15fr | .85fr (single column ≤600px).
  - **Left:**
    - main image box: min-height 230px (160px mobile), `#f0faff`, radius 12px, picture contain, max-height 380px;
    - thumbnail row: 62×55 buttons, 2px border, active `#078ecb`, one per photo; a model with no photos shows one thumb of its silhouette;
    - if the model has a video, a final button «▶ Видео доски» swaps the main image for a `<video controls playsinline>`.
  - **Right specs** (13px): «**Тип:**», «**Длина:**», «**Ширина / толщина:**», «**Объём:** N л», «**Вид закладных:**» (fallback «Не указан»), «**Материалы:**» (fallback «Не указаны»), then the description paragraph.
- Opening one of **your own** models increments its `views` (demo metric; counts self-views, see MET-08).
- No price or CTA inside the viewer, and no prev/next arrows (consider adding them).
- Closing pauses the video.

### 3.6 Order modal `#orderOverlay`
Screen: `cabinet-shapers-order-modal-*.png`. Opened from «Заказать доску» (catalog) or «Оставить заявку» (profile modal).

- **Title:** «Заказать <model name>» (static default «Заказать доску»).
- **Info line:** «Мастерская: <workshop> · <price> · <region>».
- **Close:** a text «×» button (other modals use the icon).

**Fields** (2-column grid, 1 column ≤610px):

| label | type | rules |
|---|---|---|
| «Ваше имя *» | text, placeholder «Имя покупателя» | required. Prefilled «<first> <last>» only when the role is «Шейпер» and the profile has a first name |
| «Контакт для связи *» | text, placeholder «Телефон или email» | required (no format check) |
| «Тип заявки» | select «Покупка» / «Аренда (если доступна)» | «Аренда» is enabled only for your own workshop with «Сдаю снаряжение в аренду», which in practice is never |
| «Пожелания к заказу» | textarea, placeholder «Размер, цвет, доставка, сроки...» | optional; default text «Хочу уточнить детали заказа» |

- Help text: «Заявка сохраняется локально. Реальный заказ и платёж не создаются.»
- Buttons: «Отмена» (secondary) and «Отправить заявку» (primary).

**Guards and toasts:**
- «Свою доску заказать нельзя. Выберите другого шейпера.» on open of your own board.
- «Доска не найдена».
- «Нельзя заказать доску у самого себя» on submit.

**Result** (toast «Заявка сохранена в деморежиме»):
- record `{name, title:model, modelId, ownerName, ownerId, role, kind, amount:price, contact, ago:'Только что', status:'Новая', text, statusLog:[]}` added to «Мои исходящие заявки»;
- if the board is your own demo workshop's, it is also added to the incoming requests;
- the outgoing badge increments.

**Production:**
- POST an inquiry linked to the model/variant;
- **create the conversation immediately** (MSG-09);
- notify the shaper;
- add the PAY-01 kinds: purchase, custom build, repair, rental.

### 3.7 Board type silhouettes (SHP-06)
Generated by `shapeImage(type)` (shapers.html:626–636) as `data:image/svg+xml` (100×260 viewBox), cached per type.
- One outline path per type.
- Horizontal gradient: white 65% → type colour (stops .26–.72) → `#0b587f` 65%.
- Outline stroke `#377c9c` @ .37, 1.15px.
- White stringer at x=50 from y=12 to y=244.
- Exported as `frontend-port/assets/shaper-board-{longboard,shortboard,funboard,fish,gun,sup,custom}.svg`; full path data is in `icons-cabinet.json` → `board-*`.

| type | file | deck colour | shape |
|---|---|---|---|
| Лонгборд | longboard | `#c69b64` (wood) | parallel rails, round nose |
| Шортборд | shortboard | `#ece9de` (cream) | pointed nose, narrow tail |
| Фанборд | funboard | `#b3d9e9` | mid-length egg |
| Фиш | fish | `#28acc4` | wide body, **swallow-tail notch** |
| Ган | gun | `#4386b3` | long, pointed both ends (added at runtime before SUP) |
| SUP | sup | `#7bc8d0` | wide, round, parallel |
| Кастом (and any unknown/custom type) | custom | `#b3d9e9` | generic |

Used in:
- the profile «Типы досок» picker tiles;
- **as the picture of every model without a photo**: catalog cards, own cards, carousel tiles, profile tiles, viewer thumbnail.

The legacy PNG renders `img/img31–36.png` (340×600, transparent) are effectively unused fallbacks. TZ asks that silhouettes match real shapes, so a designer should redraw them; keep the per-type mapping.

### 3.8 Size / volume / fins icons (BRD-10)
Spec lines `.gv-spec` (11px `#7194ad`, 14px icon, stroke 1.8):
- `i-ruler`: «<length> · <width × thickness>» («—» for missing parts);
- `i-droplets`: «<volume> л»;
- `i-fins`: «<fin box>», shown only when set.

Icons are in `icons-cabinet.json`.

### 3.9 SKU («Артикул») format (BRD-05/06)
Implemented in shapers.html:701–777 and 1543–1559. Format:

```
GV-<shaperCode>-<typeCode>-<length>-<width>-<NNN>
e.g. GV-S62WI5-LNG-9P2-W2200-001   GV-VLC01-FSH-5P7-WNA-002
```

**shaperCode:**
- own workshop: `S` + 5 random base36 uppercase chars, generated once and stored in `profile.shaperCode` (the prototype loses it on profile save; bug);
- demo shapers: `VLC01` (Volna Craft), `BSL02` (Baltic Surf Lab), `KSP03` (Сахалинские доски).

**typeCode:**
- Лонгборд LNG, Шортборд SHT, Фанборд FUN, Фиш FSH, Ган GUN, SUP SUP, Кастом CST;
- other custom types: `X` + last 3 base36 chars of a 31-hash of the name.

**length:**
- feet′inches → `<ft>P<in>`: `9’2”` → `9P2`, `10’0”` → `10P0`; also «6 ft 2»; a bare `6.2` → `6P2`;
- centimetres `275 см` → `C2750`; metres `2.7 м` → `C2700`;
- empty → `LNA`.

**width:** the first number in «Ширина и толщина» × 100 → `W2200` for `22” × 2.8”`. If the value contains «см/cm», it is × 10 with prefix `C`. Empty → `WNA`.

**NNN:**
- a permanent per-workshop serial (`articleSeq`), zero-padded to 3 digits, taken from a counter;
- editing type or size **re-computes the code but keeps the serial**; the old code is kept as `legacyArticle`;
- in the board modal the field is read-only with live preview. Until type, length and width are all filled it shows «Укажите тип, длину и ширину»; for a new board before typing it shows «Присвоится автоматически».

Hint under the field: «Код присваивается автоматически для всего каталога. Изменение типа или размеров обновляет код, а порядковый номер модели сохраняется.» Title attribute: «Артикул: код шейпера · тип доски · длина · ширина · постоянный порядковый номер».

**Production:**
- the server generates the SKU and guarantees uniqueness;
- the immutable UUID is separate from the SKU;
- past orders keep a snapshot of the parameters (F10 scenario).

---

## 4. Shaper cabinet `#dashboard`: layout

Screens: `cabinet-shapers-dashboard-overview-after-{1440,390}.png` and the other `cabinet-shapers-*` files.

**Desktop:**
- grid `232px | 1fr`, gap 17px, inside `.content` (padding 19/25/24, light gradient);
- footer note under it (§2.4).

**Sidebar `aside.card.side`:**
- **Profile summary:**
  - avatar 65px round (`img/img26.jpg`, or the uploaded avatar) as a button → Профиль;
  - name `#sideName` 17px/800: «<first> <last>», fallback «Иван Петров»;
  - workshop `#sideCompany`: fallback «Kamchatka Boards»;
  - rating «★ 4.9 (26)»: **static demo text**.
- **`nav.side-nav`:** buttons 13px/650 `#125487`, 18px icon, radius 8px; active `#e0f4ff` / `#006a9c` / 850. Counters are right-aligned pills (`#e7f6ff` / `#00689a`, hidden when empty).

| item | icon | counter |
|---|---|---|
| «Панель управления» | home | — |
| «Мои доски» | board | — |
| «Обращения» | mail | `#requestNavCount` = unread messages + new requests |
| «Мои исходящие заявки» | send | `#outgoingNavCount` = outgoing orders not yet seen (cleared on opening the panel) |
| «Бронирования» | calendar | static «1» (demo; must come from data) |
| «Статистика» | graph | — |
| «Отзывы» | star | — |
| «Профиль» | user | — |
| «Настройки» | settings | — |

**Mobile (≤830px):**
- single column;
- sidebar becomes a card with the profile summary row (avatar 64px + name/company/rating);
- the nav becomes a **single horizontally scrolling row** of pills (`white-space:nowrap`, `overscroll-behavior-x:contain`);
- panels stack below. See `cabinet-shapers-dashboard-overview-after-390.png`.

### 4.1 Compact KPI strip `.gv-compact-kpis` (SHO-01, MET-02)
One white rounded row (radius 12px, min-height 63px) above the panel content, **only** in these panels:
- Панель управления (`#gvKpiOverview`);
- Обращения (`#gvKpiRequests`);
- Статистика (`#gvKpiStatistics`);
- Бронирования (`#gvKpiBookings`, availability-specific).

Items are separated by vertical dividers. Each item: icon 18px `#63accb` + number 17px/850 `#07547f` + caption 10px `#7393a7`.
- ≤1000px: items get min-width 115px and the strip scrolls horizontally.
- ≤610px: min-width 106px; numbers 16px; captions 9px, wrapping.

| strip | items (icon · caption · value) |
|---|---|
| Overview | board «Моделей» = model count · mail «Новые заявки» = status «Новая» · graph «В работе» · check «Завершено» |
| Requests | brief «Всего заявок» · mail «Новые заявки» · mail «Непрочитанные» = Σ unread messages · check «В работе» |
| Statistics | board «Моделей» · views «Просмотры (демо)» = Σ model views · check «Завершено» · graph «Выручка» = «N ₽» |
| Bookings | board «Свободных бордов» = models «В наличии» − rental requests «В работе» (≥0) · calendar «Забронировано» = rental requests «В работе» (RENT-04) |

---

## 5. Cabinet panels

### 5.1 «Панель управления» (overview, SHO-01)
Top to bottom:
1. KPI strip (overview).
2. `.lower-dash` grid 1.55fr | 1fr (single column ≤830px):
   - **Card «[mail] Входящие заявки»** + plain link «Все обращения →» (→ Обращения). The first 3 requests, rendered exactly like the request rows (§5.3), with action buttons. Empty: «Заявок ещё нет.»
   - **Card «[graph] Показатели мастерской»** + «Вся статистика →». A 2×2 grid of mini-KPIs `.gv-mini-kpi` (22px number, `#f5fbff` tile):
     - «Новых заявок»;
     - «В работе»;
     - «Завершено»;
     - «Выручка, ₽» (sum of `amount` of completed requests, demo).
3. **Card «[board] Мои модели досок»** + primary «Управлять моделями →» (→ Мои доски).
   - Digest chips: «**N** моделей в каталоге», «**N** в наличии», «**N** под заказ».
   - Note: «Редактирование и полный каталог ваших моделей находятся только в разделе «Мои доски».» (BRD-01: no editor on the overview.)
4. **Promo banner `.dash-promo`:** dark gradient over `img/img23.webp`, radius 11px, min-height 150px. H3 22px «Делитесь своей философией»; text «Покажите, как рождаются ваши доски.<br>Вдохновляйте новое поколение сёрферов.»; white outlined button «Редактировать профиль →» (→ Профиль).

### 5.2 «Мои доски» (`#panel-boards`, BRD-01/02/08/09/12)
Screens: `cabinet-shapers-my-boards-*.png`, `cabinet-shapers-my-boards-after-edit-*.png`.

- Head «[board] Мои доски» + primary «[+] Добавить доску» → board modal (new).
- Filter tabs `.tabs`: «Все» · «В наличии» · «Под заказ» · «Нет в наличии» (status filter). Empty: «Нет моделей с таким статусом.»
- **Grid `.models`:** 4 columns (2 columns ≤1150px, which includes tablets; 2 ≤610px).

**Own model card** (same base as §3.2, with these differences):
- Status badge top-left. The 3 colours are in §7.1 and are correct here.
- Top-right **pencil** button `.model-menu`: 32px, white 96%, radius 9px; title/aria «Редактировать карточку доски» → board modal (edit) (BRD-09).
- Picture click → viewer.
- Name is plain bold text, not clickable; consider making it clickable for consistency with BRD-08.
- Type line with the SKU chip «Арт. …» after the type text.
- Spec lines (ruler / droplets / fins) and the price.
- Foot (top border): «[eye] <views>» left, «[heart] <favourites>» right (demo counters).
- If the model has more than 1 photo or a video: link «[photo] N фото · видео» → viewer.

**«Быстрое редактирование моделей»** (BRD-12):
- Below the grid, after a top border.
- Head with H3 + help «Меняйте несколько значений сразу — после сохранения изменения появятся в карточках выше.» + primary «Сохранить изменения».
- Table `.bulk-table` (min-width 700px) inside `.bulk-scroll`: a bordered rounded box with **internal horizontal scroll** on mobile.

| column | control |
|---|---|
| «Модель» | text, required, max 100 |
| «Тип» | select: standard types + custom types |
| «Длина» | text |
| «Объём, л» | number 0–300 |
| «Цена, ₽» | number ≥1, required |
| «Наличие» | select «В наличии / Под заказ / Нет в наличии» |
| «Материал» | text |

Behaviour:
- Any edit marks the row `.changed` (`#f0fbff`).
- Saving validates the changed rows only (native `reportValidity`), applies them, re-renders the cards.
- Toasts: «Пока нет изменений для сохранения», «Укажите название и положительную цену каждой модели», «Сохранено моделей: N. Карточки обновлены.»
- Footer hint: «Изменения применяются только после нажатия «Сохранить изменения».»
- Production: recompute the SKU on save; on mobile also avoid truncated selects (UX-06).

### 5.3 Board create / edit modal `#boardOverlay` (BRD-02/03/04/11, UX-08/09)
Screens: `cabinet-shapers-board-new-modal-*`, `cabinet-shapers-board-edit-modal-*` (top + `-bottom`).

- **Title:** «Добавить новую доску» (new) / «Редактировать модель доски» (edit).
- **Close:** × icon or Esc (no backdrop close).
- **Layout:** 2-column field grid (1 column ≤610px), then full-width fields.

| # | label | control | rules |
|---|---|---|---|
| 1 | «Название модели *» | text, placeholder «Например, Pacific Fish» | required |
| 2 | «Артикул» | read-only text (see §3.9) | live preview |
| 3 | «Тип доски *» | select «Выберите тип» + **the shaper's own profile types** (all standard types if the profile has none) + the current value | required. SHP-05: custom types from the profile appear here |
| 4 | «Длина» | text, placeholder «Например, 9’2”» | `required` (no * shown; bug) |
| 5 | «Ширина и толщина» | text, placeholder «22” × 2.8”» | `required` (no * shown) |
| 6 | «Объём (л)» | number 0–300, placeholder «65» | — |
| 7 | «Цена (₽) *» | number min 1, placeholder «75000» | required |
| 8 | «Наличие» | select «В наличии» (default) / «Под заказ» / «Нет в наличии» | — |
| 9 | «Материалы» | text, placeholder «Стекловолокно, эпоксидная смола» | — |
| 10 | «Вид закладных» | text with datalist: FCS II, FCS I, Futures, US Box, Single Fin, 2+1, Thruster, Quad, Без закладных; placeholder «Например, FCS II или Futures» | — |
| 11 | «Описание» | textarea, placeholder «Для каких волн и райдеров подходит доска...» | — |
| 12 | «Фотографии доски» | photo uploader (below) | ≤10 |
| 13 | «Видео доски» | separate video slot (below) | 1 video |

TZ BRD-02 also lists a separate thickness and a variant/instance model; the prototype keeps «Ширина и толщина» as one free-text field.

**Photo uploader:**
- Dashed upload zone `.uploadzone.model-upload`: icon upload; bold «Загрузите фотографии доски»; small «Выберите несколько файлов · JPG, PNG, WEBP · до 10 фото»; counter line «Фотографий: N из 10 · можно выбрать несколько».
- Hidden `<input type=file accept=image/* multiple>`.
- Below the zone, `.gv-gallery-row` **wraps a grid of 86×86 thumbnails** (radius 10px, cover-cropped). Each has a round 24px **×** at the top-right (aria «Удалить фотографию»; hover reddish).
- Order is upload order: already-saved photos first, then new ones. **Photo #1 is the cover.** There is no cover picker or drag reorder; TZ BRD-03 requires both.
- Limits:
  - max 10 in total → toast «Можно загрузить не более 10 фотографий»;
  - non-image or file >15 MB → «Поддерживаются фотографии до 15 МБ»;
  - success → «Добавлено фотографий: N».
- On save each new photo is downscaled to ≤1200px and re-encoded as JPEG q .84. Transparent PNGs turn black (bug: fill white or keep WebP/PNG).

**Video slot `.gv-video-slot`:**
- Label «Видео доски»; compact dashed zone «Добавить видео доски» / «Отдельно от фотографий · MP4 / WebM · до 80 МБ».
- Filename line: the chosen name, or «Видео доски загружено» (saved), or «Видео ещё не выбрано».
- Below: an inline `<video controls>` preview (≤350px wide, ≤210px tall, radius 10px) + a round × «Удалить видео доски». The × currently sits detached at the right edge of the slot.
- Toasts: «Выберите видеофайл MP4 или WebM», «Видео не должно превышать 80 МБ».
- UX-09 asks for a compact tile with poster, duration and ×.

**Actions:** «Отмена» (secondary) and «Сохранить» (primary). The primary is disabled while media is being stored (BRD-11).

**Submit:**
- native validation → SKU (new: next serial) → photos to IndexedDB → video to IndexedDB;
- new boards go to the **top** of the list;
- toasts: new «Доска добавлена · GV-…», edit «Изменения доски сохранены», error «Не удалось сохранить медиа: <reason>».

### 5.4 «Обращения» (`#panel-requests`, SHO-02/04/05, MSG-01/03/06)
Screens: `cabinet-shapers-requests-*`, `cabinet-shapers-requests-after-accept-*`, `cabinet-shapers-chats-*`, `cabinet-shapers-chats-after-demo-*`.

Top to bottom:
1. KPI strip (requests).
2. Head «[brief] Обращения» with help «Заявки и переписка в одном месте. Клиент может написать ещё до принятия заявки.»
   - Top-right: a dashed muted demo button «+ Тестовое сообщение» (title «Создать демонстрационное входящее сообщение»).
   - **Demo only:** it injects an incoming message from the next of «Анна Морозова / Пётр Иванов / Никита Белов / Дарья Ковалёва»: «Здравствуйте! Подскажите, можно ли обсудить <first model name> и сроки изготовления?». It switches to the «Чаты» tab and toasts «Тестовое входящее сообщение получено». **Remove in production.**
3. **Tabs** `.gv-contact-tabs` (role tablist), radius 9px, active `#0074a9` white:
   - «Входящие заявки · N» (N = new requests);
   - «Чаты · N» (N = unread messages);
   - ≤610px the tabs stretch evenly.

**Tab «Входящие заявки»** (`#allRequests`): rows `.request-item` separated by thin lines. Each row:
- 35px avatar (demo `img/img30.jpg`);
- `.request-copy`:
  - **client name**;
  - meta «<kind || «Запрос»> · <title> · <amount ₽ if any>»;
  - message text, 1 line with ellipsis on desktop;
- `.request-meta` (right): relative time («2 часа назад», «1 день назад», «Только что», «Статус обновлён») + status badge;
- `.order-actions`:

| status | owner buttons |
|---|---|
| «Новая» | «Принять в работу» (`.btn-good`) · «Отказать» (`.btn-danger`) · «[mail] Перейти в чат» |
| «В работе» | «Завершить» · «Отказать» · «Перейти в чат» |
| «Завершена» | «Перейти в чат» only |
| «Отклонена» / «Отменена» | «Перейти в чат» **disabled**, title «Чат недоступен после отмены или отказа» |

- Mobile (≤610px): the row becomes a 2-column grid. Avatar on the left spanning 2 rows; on the right three lines: text, then time + badge, then buttons wrapping. See `cabinet-shapers-requests-390.png`.
- Empty: «Новых заявок нет.»

**Tab «Чаты»** (`#gvInboxList`):
- Summary line «Непрочитанных сообщений: N» or «Все сообщения прочитаны».
- Rows `.gv-inbox-row` (full-width buttons): avatar, **name**, last message preview (ellipsis), right status.
  - Unread: the row is tinted `#f0faff` and the status is a blue pill with a dot «N новых».
  - Read: grey «Прочитано».
  - Extra threads (conversations started by you, e.g. via «Написать шейперу»): an initial-letter avatar and status «Диалог». A photo-only last message shows «📷 Фотография».
- Footnote «Непрочитанные диалоги отмечаются голубым. Открытие помечает сообщения прочитанными.»
- Empty: «Диалогов пока нет.»
- Opening a thread sets its unread to 0 and updates every badge (MSG-06).

**Request status machine** (SHO-05, TZ 7.2):

| from | action (who) | to | confirm / prompt | side effects |
|---|---|---|---|---|
| Новая | «Принять в работу» (shaper) | В работе | — | order thread created (seeded with the client's text) and **chat opens automatically** |
| В работе | «Завершить» (shaper) | Завершена | if no amount: `prompt` «Укажите сумму завершённой сделки в рублях (можно 0, если сделка без оплаты):» default «0»; invalid → toast «Введите корректную сумму сделки» | amount stored → revenue metrics |
| Новая / В работе | «Отказать» (shaper) | Отклонена | `confirm` «Отказать в выполнении заказа?» | chat disabled |
| Новая / В работе | «Отменить» (client, outgoing list) | Отменена | `confirm` «Отменить заявку?» | chat disabled |

- Every change sets the time to «Статус обновлён», appends `statusLog {at: ru-RU datetime, status}`, re-renders and toasts «Статус заявки: <status>».
- Closed statuses (Завершена / Отклонена / Отменена) accept no further transitions.
- Chat is available **before** acceptance (MSG-03).
- Blocked chat toasts: «По отклонённой или отменённой заявке чат недоступен», «Чат недоступен для этой заявки».
- Production mapping: `new`, `in_progress`, `completed`, `declined`, `cancelled`. Revenue only from recorded payments (MET-07). Notify the other side.

### 5.5 Chat modal `#chatOverlay` (MSG-04/05/08)
Screens: `cabinet-shapers-chat-modal-order-*`, `cabinet-shapers-chat-attachment-preview-*`, `cabinet-shapers-chat-photo-message-*`, `cabinet-shapers-chat-modal-inbox-*`.

`.modal.gv-chat-modal` (max 650px). Close: × or Esc.

**Title** H2:
- order thread: «Чат · <model or request title> · <counterpart name>»;
- plain thread: «Чат · <name>».

On mobile the long title runs under the × (fix with right padding).

**Log `#chatLog`:**
- tall: `min(58vh, 560px)`, min 400px (52vh / min 330px ≤690px);
- gradient `#f8fdff → #eef9ff`, radius 9px, gap 10px.
- **Intro block** at the top (MSG-05):
  - 49px round mail icon;
  - «**Начало диалога**»;
  - «Обсудите форму доски, её размеры и сроки изготовления.<br>Переписка работает в демонстрационном режиме.»;
  - divider with the label «СООБЩЕНИЯ».
- A flexible spacer pushes the messages to the bottom.
- **Bubbles:** max 83% width, radius 13px, padding 9×12, line-height 1.5.
  - Incoming: left, white with a 1px border.
  - Mine: right, `#cbeeff`.
  - Optional photo inside: 250px wide, radius 11px, zoom-in cursor; click opens the full image in a new tab.
  - Time «HH:MM» (9px, right-aligned) for messages that have a timestamp; seeded demo messages have none.
- Seed first message:
  - plain thread: the inbox messages;
  - order thread: the request text, or «Здравствуйте! Интересует эта модель.»;
  - fallback: «Здравствуйте! Напишите здесь свои вопросы о заказе.»

**Actions row `#chatActions`** (order threads only): status badge + the same control buttons as the list (owner or client set), including a redundant «Перейти в чат».

**Attachment preview** (MSG-04): appears above the form after choosing a photo. It shows a thumbnail 80×65, the filename (cut to 27 chars + «…»), and a round × «Удалить вложение».

**Form `.gv-chat-form`:**
- attach button `.gv-paperclip`: 43px square, radius 10px, **`#i-link` chain icon** (use a real paperclip), title «Прикрепить фото», accepts JPG/PNG/WebP;
- input placeholder «Напишите сообщение или прикрепите фото…»;
- primary «Отправить».

Validation toasts:
- «Напишите сообщение или прикрепите фото»;
- «Прикрепите JPG, PNG или WebP до 10 МБ»;
- self-messaging: «Нельзя написать своей мастерской», «Шейпер не может писать самому себе», «Нельзя написать самому себе»;
- storage error: «Не удалось сохранить вложение: <reason>».

The send button is disabled while saving. Footnote: «Демо-чат сохраняется в этом браузере. Для сообщений между разными пользователями и устройствами потребуется подключить сервер.»

Production:
- real conversations, message attachments stored as media assets (type/size/AV checks);
- per-participant read cursors;
- a context card for the linked model/order (MSG-08).

### 5.6 «Мои исходящие заявки» = client's «Мои заявки на доски» (`#panel-outgoing`, SHO-03, MSG-02)
Screen: `cabinet-shapers-outgoing-*`.

- Head «[send] Мои исходящие заявки» + right muted «Личная история обращений к другим шейперам».
- Intro «Здесь отображаются заявки, которые вы отправили мастерам. Информация доступна только в этом локальном кабинете.»
- Rows, newest first:
  - «**<model> · <workshop>**»;
  - «<kind> · <amount ₽> · от имени: <role>»;
  - comment text;
  - status badge;
  - buttons «[mail] Перейти в чат» and «Отменить» (while not closed).
- Empty: «Заявок ещё нет. Выберите интересующую доску и нажмите «Заказать».»
- Opening the panel clears the «new outgoing» counter.

TZ: this list belongs to **every** account (not only shaper accounts), with the send icon. Statuses must reflect the shaper's actions on the server; in the demo, orders to demo shapers never change.

### 5.7 «Бронирования» (`#panel-bookings`, RENT-04)
- KPI strip (bookings: «Свободных бордов», «Забронировано»).
- H3 «[calendar] Бронирования».
- Empty state: big calendar icon, «Здесь будут бронирования», «Как только клиент забронирует доску, заявка появится в этом разделе.»
- No real data. Production: board instances, availability calendar, rental requests.

### 5.8 «Статистика» (`#panel-statistics`, SHO-07, MET-03/07)
Screen: `cabinet-shapers-statistics-*`.

- KPI strip (statistics).
- Head «[graph] Статистика мастерской» + right help «По сохранённым данным этого браузера».
- **10 tiles** `.gv-stat-tile` (4 columns; 2 ≤1100px). Each tile: small title, 23px value, 10px note.

| title | value | note |
|---|---|---|
| «Опубликовано моделей» | count of models | «Текущее количество» |
| «Входящих заявок» | all requests | «Все статусы» |
| «Активные заявки» | status В работе | «В работе» |
| «Уникальных клиентов» | distinct contact or name | «По имени или контакту» |
| «Завершено» | status Завершена | «Закрытые сделки» |
| «Конверсия в завершение» | done ÷ all × 100 % | «Завершено / все заявки» |
| «Средний чек» | gross ÷ done ₽ | «По завершённым сделкам» |
| «Выручка» | Σ amount of completed ₽ | «Только завершённые заявки» |
| «Просмотры досок» | Σ views | «Начальные демо-значения + локальные открытия» |
| «Отметки избранного» | Σ hearts | «Демонстрационные значения» |

- Two panels (single column ≤700px), each with label + count + a 7px bar `#68b7d7` on `#e8f3fa`:
  - «Структура заявок»: bars «Новые», «В работе», «Завершены», «Отменены / отклонены», relative to the total;
  - «Ваши типы досок»: one bar per type, relative to the model count. Empty: «Добавьте первую доску для статистики по типам.»
- «Итоги сделок»: text «Продано досок: N · Арендовано: N · Выручка: N ₽. Показатели только из завершённых демонстрационных заказов; расходы не учтены.»
- Footnote «Просмотры и отметки избранного в исходных демонстрационных моделях — тестовые значения. До подключения серверной аналитики показаны только локальные и демонстрационные данные.»

Production:
- conversion per TZ 10.1 (inquiries ÷ qualified views);
- revenue only from confirmed payments;
- exclude self-views;
- interest by type from events.

### 5.9 «Отзывы» (`#panel-reviews`, SHO-08)
- H3 «[star] Отзывы о вашей мастерской».
- One **demo** row: 46px round avatar (`img/img30.jpg`), «★★★★★» 27px amber, «**Алексей**», «Классная доска, всё выполнено аккуратно. Спасибо!»
- Note «Пример отзыва. Реальные отзывы будут доступны после подтверждённых заказов.»

Production: reviews tied to completed orders, with the author avatar, date, context and a moderation policy.

### 5.10 «Профиль» = shaper registration / edit form (`#panel-profile`, SHP-01..05, SHP-12)
Screens: `cabinet-shapers-profile-form-new-*`, `-profile-form-filled-*`, `-profile-form-edit-*`.

**Heading card:**
- «[user] Профиль мастерской» + help «Ваши данные, специализация, фотографии и контакты. Здесь же создаётся аккаунт шейпера.»
- Right: secondary «Посмотреть на сайте →» (SHP-12). If the workshop is not saved: toast «Сначала заполните профиль мастерской». Otherwise opens the catalog and the own profile modal.
- ≤610px: the button goes full-width below the text.

**Form `#shaperForm` (novalidate; native validity checked in JS):**
- 2 columns (`1.04fr | 1fr`), then a bottom row `1.9fr | 1fr`, then the CTA;
- single column ≤610px.

**Left column, card «[monitor] Основная информация»:**
- **Photo block**, floated right, 88px circle:
  - hover/focus overlay on the lower half «[camera] Выбрать фото»; caption «Фото шейпера»;
  - choosing a file immediately downsizes it to 950px JPEG q .82, replaces every avatar on the page, stores it, toast «Фотография профиля обновлена»;
  - per SHP-02: compact round photo left of the title, editable only here.

| field | name | type / options | rules |
|---|---|---|---|
| «Название мастерской *» | workshop | text, placeholder «Например, Kamchatka Boards» | required, max 90 |
| «Имя *» / «Фамилия *» | first / last | text, placeholders «Иван» / «Петров» | required |
| «Регион *» | region | select «Выберите регион» + Камчатский край, Приморский край, Сахалинская область, Калининградская область, Краснодарский край, Республика Крым, Ленинградская область, Москва и Московская область, Другой регион | required. NB: the list differs from the main site's region list |
| «Город *» | city | text, placeholder «Выберите город» | required |
| «Стаж в шейпинге *» | experience | select «Выберите стаж» + Менее года, 1–3 года, 3–5 лет, 5–10 лет, Более 10 лет | required; half width |
| «О себе *» | about | textarea, placeholder «Расскажите о себе, своей мастерской, философии и подходе к созданию досок...» | required, max 1000, live counter «N / 1000» |

**Left column, card «[board] Типы досок, которые изготавливаете»:**
- Grid of type tiles `.board-option`:
  - 7 per row (4 ≤850px, 3 ≤450px); 145px tall (132px ≤1150px);
  - silhouette + label;
  - selected: 2px `#168cce` border, glow, blue round ✓ top-right;
  - default selection «Шортборд»; multi-select.
- Below: full-width dashed button «[+] Добавить другие типы досок (мини-малибу, софтборд и др.)».
  - `prompt` «Какой ещё тип досок вы изготавливаете?» (max 35 chars); a duplicate is ignored.
  - Adds a chip with × (aria «Удалить <type>»). Custom types are always included in the profile types and in the board-modal type selector (SHP-05).
  - Bug: adding resets unsaved tile picks.
- Validation on submit: at least one type → toast «Выберите хотя бы один тип досок» + scroll to the tiles.

**Right column, card «[box] Используемые материалы»:**
- Checkbox pills, defaults checked «Стекловолокно», «Карбон»; also «Эпоксидная смола», «Полиэфирная смола», «Деревянный шпон», «Био-смола», «EPS / PU».
- Button «[+] Добавить свой материал»: `prompt` «Какой материал добавить?» (max 50).
  - Duplicate (case-insensitive) or empty → «Такой материал уже есть в списке»; success → «Материал добавлен».
  - New pill with ×; custom materials are checked by default before registration (SHP-05).

**Right column, card «[truck] Доставка и сроки»:**
- «Способы доставки»: checkboxes «Самовывоз» ✓, «Транспортная компания» ✓, «Почта России», «Международная доставка» (PAY-06).
- «Срок изготовления *» select «Выберите срок» + До 2 недель, 2–4 недели, 1–2 месяца, 2–3 месяца, По договорённости (required).
- «Ценовой диапазон (₽)»: two numbers, placeholders «от» / «до», min 0. Not shown publicly.
- Toggles (each with title + note):
  - «Принимаю индивидуальные заказы» / «Изготовление досок по персональным параметрам» (default on);
  - «Сдаю снаряжение в аренду» / «Прокат досок и другого оборудования»;
  - «Занимаюсь ремонтом досок» / «Принимаю доски на ремонт и восстановление» (SHP-04 «Делаю ремонт»).

**Right column, card «[photo] Фотографии работ»:**
- Upload zone «Загрузите фотографии ваших досок» / «Перетащите файлы сюда или выберите на компьютере». Drag and drop is not implemented.
- Next to it, a horizontal strip of 77×100 previews (demo `img28`, `img29`) with × on each, and a «+» tile.
- First 10 files only; toast «Добавлено фотографий: N».
- Help «Можно загрузить до 10 фотографий (JPG, PNG, WebP).»
- **Not persisted** in the prototype. In production use the same uploader as the board modal: grid below, × top-right (UX-08).

**Right column, card «[photo] Промо-видео шейпера»** (SHP-03):
- Help «Одно короткое видео о вас и мастерской. Посетители увидят его в вашей карточке при поиске по шейперам.»
- Zone «Загрузить промо-видео» / «MP4 или WebM · до 80 МБ · 1 видео».
- Status line:
  - «Сохранение видео в браузере…» → «Загружено: <file>»;
  - toast «Промо-видео готово к сохранению в профиле»;
  - error «Не удалось сохранить видео: …»;
  - while uploading the save button is disabled; submitting meanwhile toasts «Завершите загрузку промо-видео».
- Preview: `<video>` + × «Удалить промо-видео» → status «Промо-видео удалено. Сохраните профиль.»; empty text «Промо-видео не добавлено.»

**Bottom row, card «[link] Контакты и социальные сети»:**
- Row 1 (1fr 1fr 1.2fr):
  - «Телефон *»: tel, placeholder «+7 965 285 87 81», **mask** `+7 XXX XXX XX XX`. As you type, a leading 7 or 8 is dropped and the input is limited to 10 digits.
    - On blur, if incomplete: «Укажите полный номер: +7 965 285 87 81».
    - On submit, if incomplete: «Введите 10 цифр после +7».
    - Pattern `\+7 \d{3} \d{3} \d{2} \d{2}`.
  - «Email *»: email, placeholder «example@mail.ru».
  - «Адрес мастерской»: placeholder «Укажите адрес».
- Row 2 (4 columns): «Telegram» «@мастерская», «VK» «vk.com/...», «Видео» «Ссылка на канал» (field name `youtube`), «Сайт» «https://...».
- Mobile bug: these rows stay 3 and 4 columns at 390px; stack them in production.

**Bottom row, card «[upload] Сертификаты и достижения»:**
- Zone «Загрузите сертификаты (необязательно)» / «JPG, PNG или PDF».
- Selected file names are listed (or «Документы не выбраны»); default «Можно добавить позже в личном кабинете.»
- Not stored. Certificates are user data with personal data risk (TRUST-03).

**CTA** `#profileSaveButton`, full width, primary (SHP-01):
- **«Зарегистрироваться как шейпер»** while no workshop is saved;
- **«Сохранить изменения»** afterwards (also re-applied every time the Профиль tab opens).

Under it: «Демонстрационная версия: данные сохраняются в этом браузере. Для настоящей регистрации потребуется сервер.»

**Submit result:**
- First save: toast «Аккаунт шейпера создан». The catalog role switches to «Шейпер», own boards become non-orderable, and the button text changes.
- Later saves: «Изменения профиля сохранены».
- The user stays on the Профиль tab.

Production: this form = «connect the Шейпер specialty» in the unified account (TZ 17). One account id, no second registration.

### 5.11 «Настройки» (`#panel-settings`)
- H3 «[settings] Настройки».
- Checkboxes «Получать уведомления о новых заявках» ✓ and «Показывать мастерскую в каталоге» ✓. They are not wired to anything.
- Note «Настройки пока действуют только в этой демонстрации.»

Production: notification preferences (MSG-12) and catalog visibility.

### 5.12 Repair (SHO-06)
Only the profile toggle «Занимаюсь ремонтом досок». It shows the green «Ремонт досок» tag on the shaper card and the «Ремонт досок» chip in the profile modal. There is no repair request form or flow and no catalog filter; TZ requires both (SHP-04, SHO-06).

---

## 6. Board / model / request data (as used by the UI)
Full demo data: `frontend-port/seed_cabinet.json` → `shapers` (keys `shapers`, `requests`, `inbox`, `demoChatTemplates`, `reviews`, `certificates`, `statistics`, `notifications`, `options`, `localStorageSchema`).

- **Model:**
  - fields: `id`, `name`, `type`, `length`, `dimensions`, `volume`, `price`, `status`, `material`, `finBox`, `description`;
  - media: `photoIds[]` (IndexedDB ids, ≤10, #0 = cover), `videoId`, legacy `photo` (data URL);
  - SKU: `article`, `articleSeq`, `legacyArticle`;
  - demo counters: `views`, `hearts`;
  - `board` = legacy picture index.
- **Request** (incoming) / **outgoing order:**
  - who and what: `id`, `name` (client), `title` (model or subject), `modelId`, `ownerId`, `ownerName`, `role` («от имени»), `kind` (Покупка/Аренда), `contact`;
  - money and text: `amount`, `text`;
  - state: `ago`, `status`, `statusLog[{at,status}]`.
- **Chat:**
  - `chat["order-<requestId>"]` or `chat["<person or workshop name>"]` = `[{me, text, photoId?, at?}]`;
  - inbox threads `{id, person, preview, unread, messages[]}`.
- **Profile:**
  - identity: `workshop`, `first`, `last`, `region`, `city`, `experience`, `about`;
  - offer: `leadTime`, `priceFrom`, `priceTo`, `delivery[]`, `types[]`, `materials[]`;
  - contacts: `phone`, `email`, `address`, `telegram`, `vk`, `youtube`, `website`;
  - flags and media: `customOrders`, `rentalService`, `repairService`, `promoVideoId`, `shaperCode`.

---

## 7. Visual vocabularies

### 7.1 Model availability («Наличие»)
| value | class | bg / text |
|---|---|---|
| «В наличии» | `.status.available` | `#e7f9eb` / `#178145` |
| «Под заказ» | `.status.made` | `#fcf4df` / `#8d5a09` |
| «Нет в наличии» | `.status.none` | `#fcecec` / `#bf4953` |

Badge: 10px/800, radius 7px, padding 5×8. Position: top-left in the cabinet, bottom-left in the catalog.

### 7.2 Buttons in request rows
- `.btn-good` («Принять в работу», «Завершить»): `#e9f7ff` / `#14678e`, 1px `#b9def0`.
- `.btn-danger` («Отказать», «Отменить»): `#fff6f5` / `#b16867`, 1px `#efd8d4`.
- `.gv-request-chat` («Перейти в чат»): `#f2f9fc` / `#4b7c98`, 1px `#d7e7f0`.
- All: min-height 32px, radius 9px, 11px/700.

### 7.3 Request status badges (SHO-05)
| status | class | bg / text |
|---|---|---|
| «Новая» | `.badge` | `#e7f5ff` / `#127cb7` |
| «В работе» | `.badge.pending` | `#eaf6ff` / `#2d769a` |
| «Завершена» | `.badge.status-done` | `#e5f8ef` / `#136d52` |
| «Отклонена» | `.badge.status-cancel` | `#ffeef0` / `#a44d5b` |
| «Отменена» | `.badge.status-cancel` | `#ffeef0` / `#a44d5b` |

---

## 8. Toasts, confirms, prompts (verbatim)
| trigger | text |
|---|---|
| storage full | «Память браузера заполнена. Удалите часть загруженных фотографий.» |
| first profile save | «Аккаунт шейпера создан» |
| later profile save | «Изменения профиля сохранены» |
| no board type | «Выберите хотя бы один тип досок» |
| promo uploading | «Завершите загрузку промо-видео» |
| «Посмотреть на сайте» before profile | «Сначала заполните профиль мастерской» |
| avatar changed | «Фотография профиля обновлена» |
| works photos | «Добавлено фотографий: N» |
| custom material duplicate | «Такой материал уже есть в списке» |
| custom material ok | «Материал добавлен» |
| promo ready / error | «Промо-видео готово к сохранению в профиле» / «Не удалось сохранить видео: …» |
| no promo | «Промо-видео ещё не добавлено» |
| board photo limit / size | «Можно загрузить не более 10 фотографий» / «Поддерживаются фотографии до 15 МБ» |
| board photos added | «Добавлено фотографий: N» |
| video type / size | «Выберите видеофайл MP4 или WebM» / «Видео не должно превышать 80 МБ» |
| board saved | «Доска добавлена · GV-…» / «Изменения доски сохранены» |
| board media error | «Не удалось сохранить медиа: …» |
| bulk | «Пока нет изменений для сохранения» / «Укажите название и положительную цену каждой модели» / «Сохранено моделей: N. Карточки обновлены.» |
| order own board | «Свою доску заказать нельзя. Выберите другого шейпера.» / «Нельзя заказать доску у самого себя» |
| order not found | «Доска не найдена» |
| order sent | «Заявка сохранена в деморежиме» |
| status change | «Статус заявки: <Новая/В работе/Завершена/Отклонена/Отменена>» |
| bad amount | «Введите корректную сумму сделки» |
| chat blocked | «По отклонённой или отменённой заявке чат недоступен» / «Чат недоступен для этой заявки» |
| self chat | «Шейпер не может писать самому себе» / «Нельзя написать самому себе» / «Нельзя написать своей мастерской» / «Нельзя отправить сообщение самому себе» |
| empty message | «Напишите сообщение или прикрепите фото» |
| bad attachment | «Прикрепите JPG, PNG или WebP до 10 МБ» |
| attachment error | «Не удалось сохранить вложение: …» |
| test message | «Тестовое входящее сообщение получено» |
| profile not found | «Профиль шейпера не найден» |
| header stubs | «Поиск шейперов появится при интеграции с каталогом», «Избранное будет доступно после подключения аккаунтов», «Карта спотов — раздел основного сайта», «Раздел спотов — в основном сайте», «О проекте — в основном сайте», «Блог — в основном сайте» |
| `confirm` | «Отказать в выполнении заказа?» · «Отменить заявку?» |
| `prompt` | «Какой ещё тип досок вы изготавливаете?» · «Какой материал добавить?» · «Укажите сумму завершённой сделки в рублях (можно 0, если сделка без оплаты):» |

Replace the native `confirm` and `prompt` dialogs with design-system modals.

---

## 9. Counters and badges (SHO-04, MSG-06/07)
Computed client-side in `gvCounts()` after every render:
- `unread` = Σ `inbox[].unread`, a stored number per thread set to 0 when the thread is opened;
- `fresh` = number of requests with status «Новая»;
- `sent` = outgoing orders created since the user last opened «Мои исходящие заявки».

Badges:
- topbar messages `#gvTopNotice` = unread + fresh + sent (hidden at 0; «99+»);
- side «Обращения» = unread + fresh;
- side «Мои исходящие заявки» = sent;
- tab «Входящие заявки · fresh»;
- tab «Чаты · unread».

**Production:**
- server aggregates of unread notification events plus conversation read cursors;
- no double counting across tabs;
- the main-site header badge and the bottom-nav badge must show the same number (see CABINET_SCREENS for the site header).

---

## 10. Demo-only behaviour → what must become API
| prototype | storage | replace with |
|---|---|---|
| whole state `data` = profile, models, requests, outgoing, chat, inbox, custom types/materials, SKU counter, unseen outgoing | localStorage `gdevolna_shaper_demo_v1` (shared with the main page origin) | Django: `ShaperProfile` (linked to the unified `User`/specialty), `BoardModel` → `Variant` → `Unit`, `Inquiry` (+ status history), `Conversation`/`Message`/`MessageAttachment`, `Notification` |
| avatar | localStorage `gdevolna_shaper_files_v1` (JPEG data URL) | user avatar media (one per account; edited only in Профиль) |
| board photos/videos, promo video, chat photos | IndexedDB `gdevolna_shaper_media_v2` / store `files`, ids `gv-…` / `gv-chat-…` | `media_assets` upload API (presigned or multipart), type/size/AV validation, thumbnails, ordering + cover flag |
| SKU generator, random shaper code, serial counter | client JS | server-generated, unique SKU; immutable UUID |
| starter models, 3 demo shapers, 3 requests, 2 inbox threads, review «Алексей», rating «4.9 (26)», view/heart counts, «Бронирования 1» | hard-coded | seed only after classification (TZ 12.2); requests, messages, reviews and stats are **demo:true — never imported** |
| «Я смотрю как» role switch | UI select | the account's specialties |
| «+ Тестовое сообщение» | injects fake inbox | remove (or dev-only fixture) |
| deal amount via `prompt` on «Завершить» | stored on the request | payments / completed-deal record (MET-07, PAY-02) |
| self-order/self-chat checks by name | client | server permission checks by account id (SHP-11, ATX-03) |
| views +1 on viewer open | client | `board_viewed` events with dedupe, bots and self-views excluded (MET-08) |

---

## 11. Mobile (390px) summary
- **Embedded header:** logo, search, heart, messages + badge, avatar, «⋯» → 4-pill menu.
- **Hero:** 210px; H1 29px wraps to 2 lines.
- **Catalog:**
  - filters stacked;
  - boards in 2 columns (cards about 180px wide, visual 185px, «Фото и параметры» pill shrinks to 9px);
  - shaper cards in a single column; profile part on top, carousel below with 2 boards visible.
- **Cabinet:**
  - sidebar card + a horizontally scrolling nav pill row;
  - KPI strip scrolls horizontally;
  - request rows use the 2-column grid;
  - models in 2 columns;
  - bulk table scrolls horizontally inside its box.
- **Modals:** nearly full-screen (padding 22×15px; 17×12px ≤375px), max-height `100dvh − 24px`, inner scroll. The board modal is single column with the thumbnail grid 3 per row; the chat log is 52vh.
- **Inputs:** 16px font.

---

## 12. TZ cross-reference (shapers)
| ID | prototype status |
|---|---|
| SHP-01 | ✅ button text rule implemented |
| SHP-02 | ✅ round photo; edit only in Профиль (header avatar jumps to Профиль) |
| SHP-03 | ✅ one promo video slot + modal; ⚠ the promo button ignores which shaper it belongs to |
| SHP-04 | ⚠ toggle + tag; ❌ no catalog filter |
| SHP-05 | ✅ custom materials and types; types flow into the model selector |
| SHP-06 | ✅ Fish/Ган present; ⚠ silhouettes are generic |
| SHP-07 | ⚠ catalog with both tabs exists, but the page **opens the cabinet first** |
| SHP-08 | ⚠ no rating/review in the card |
| SHP-09 | ⚠ in-card carousel ✅; button label «Профиль шейпера →», and not bottom-left on mobile |
| SHP-10 | ⚠ modal ✅; no deep link |
| SHP-11 | ⚠ client-only checks |
| SHP-12 | ✅ «Посмотреть на сайте» |
| BRD-01 | ✅ overview shows only a digest |
| BRD-02 | ⚠ thickness merged with width |
| BRD-03 | ⚠ 10 photos + × + separate video ✅; ❌ cover choice / reorder |
| BRD-04 | ✅ in board modal; ❌ «Фотографии работ» strip |
| BRD-05 | ⚠ client SKU; code-loss bug |
| BRD-06/07/13 | ❌ server / inventory concerns |
| BRD-08 | ✅ catalog title + top-right «Фото и параметры» |
| BRD-09 | ✅ pencil |
| BRD-10 | ✅ ruler / droplets / fins |
| BRD-11 | ✅ «Сохранить» + toast |
| BRD-12 | ✅ bulk table with internal scroll |
| SHO-01 | ✅ requests + metrics on top, models below, one-line KPI |
| SHO-02 | ✅ tabs; chat before acceptance |
| SHO-03 | ⚠ «Мои исходящие заявки» only inside the shaper cabinet |
| SHO-04 | ⚠ local counters |
| SHO-05 | ✅ vocabulary + colours |
| SHO-06 | ❌ |
| SHO-07 | ⚠ formulas differ from TZ |
| SHO-08 | ⚠ one demo review |
| SHO-09 | ✅ line break |
| MSG-01 | ⚠ tabs but no role/status filters |
| MSG-03 | ✅ |
| MSG-04 | ⚠ chain icon instead of a paperclip |
| MSG-05 | ✅ |
| MSG-06/07 | ⚠ |
| MSG-08 | ❌ no context card |
| MSG-09 | ❌ thread is lazy |
| MSG-10 | ❌ local |
| MET-02 | ✅ strips only in Overview / Statistics / Requests (+ Bookings availability) |
| RENT-04 | ✅ labels; ❌ real data |
| UX-06 | ⚠ |
| UX-08 | ⚠ |
| UX-09 | ❌ |
| UX-10 | ✅ |

---

## 13. Screenshot index (`docs/prototype/screens/`, each at 1440 and 390)
- **Profile / registration:** `cabinet-shapers-profile-form-new`, `-profile-form-filled`, `-profile-form-edit`.
- **Dashboard:** `cabinet-shapers-dashboard-overview` (right after registration, still on the Профиль tab with the toast), `-dashboard-overview-after` (the real overview).
- **Boards:** `cabinet-shapers-my-boards`, `-my-boards-after-edit`, `-board-new-modal`, `-board-edit-modal`, `-board-edit-modal-bottom`, `-model-photos-modal`.
- **Catalog:** `cabinet-shapers-catalog-boards`, `-catalog-shapers`, `-catalog-shapers-card-scrolled`, `-shaper-profile-modal`, `-shaper-profile-self`, `-promo-video-modal`, `-order-modal`.
- **Requests and chat:** `cabinet-shapers-requests`, `-requests-after-accept`, `-chat-modal-order`, `-chat-attachment-preview`, `-chat-photo-message`, `-chats`, `-chats-after-demo`, `-chat-modal-inbox`.
- **Other panels:** `cabinet-shapers-outgoing`, `-bookings`, `-statistics`, `-reviews`, `-settings`.
- **Embedded:** `cabinet-shapers-embedded-public` (the main site `#shapers` page with the iframe); `cabinet-shapers-mobile-nav-390` (390 only).
