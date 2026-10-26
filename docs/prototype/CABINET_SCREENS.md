# ГДеволна — unified personal account (кабинет): screen spec from the prototype

Source: `docs/prototype/source/proto.html` (served as `http://127.0.0.1:8811/orig.html`).
This file covers the logged-in **cabinet** (`#profile`) and everything you can reach from it: registration,
the header account entry, the general panes, the specialty panes (surfer, instructor, shaper wrapper,
school, rental) and the modals they open. The shapers module inside the iframe has its own document:
`docs/prototype/SHAPERS_SCREENS.md`. The public site (home, catalogues, spots, GG Surfer, rentals, club,
header and footer layout) is documented elsewhere. Only the account-related parts of the header are repeated here.

UI copy is quoted verbatim in «…» or `code`. Where the prototype has a bug or departs from the TZ it is
flagged **[BUG]** or **[TZ]**. The full list is in `CABINET_NOTES.md`.

Related files:

| File | What |
|---|---|
| `frontend-port/styles/prototype-cabinet.css` | consolidated CSS for every class named below |
| `frontend-port/icons-cabinet.json` | SVG icons + the Unicode glyph icon map used by the cabinet |
| `frontend-port/seed_cabinet.json` | demo data, option lists, status dictionaries, localStorage schema |
| `screens/cabinet-*-1440.png`, `screens/cabinet-*-390.png` | screenshots (desktop 1440 / phone 390) |

---

## 0. How the prototype cabinet is assembled (read this first)

The cabinet is built from four layers that patch each other at runtime. Each layer wraps
`window.profile()` / `window.render()`:

| # | Script (proto.html line) | What it adds |
|---|---|---|
| 1 | main script, `function profile()` (l.479) | legacy profile page + the **guest page** (still used when logged out) |
| 2 | lesson script (l.650–859) | instructor/client lesson system: `accountDashboard()` (`.lesson-dash`), calendar, orders, lesson chat, reviews. It inserts the dash into the legacy page. |
| 3 | rentals script (l.860–953) | legacy GG-status / rental / club panels inserted into the legacy page, plus the rental catalogue and forms |
| 4 | `<script id="gv-unified-account-engine">` (l.1121–1379) | **replaces the whole logged-in profile** with the unified cabinet `renderAccount()`. It renders layers 1–3 only to (a) show the guest page and (b) cut the `.lesson-dash` element out of layer 2 for the instructor pane. It also patches registration (extra specialty checkboxes) and appends the «Личный кабинет»/«Кабинет» nav links. |

So the legacy panels of layers 1 and 3 (GG status select, rental toggle panel, club mini-card, passport
verification row) are **not visible any more**. See §12; some of those features are required by the TZ.

State is held in module variables plus `localStorage` (see §11). The selected pane and school tab are
in-memory only: `pane` defaults to `'overview'` and `schoolPane` to `'overview'`. A reload always opens «Обзор».
There are no per-pane URLs; the route is always `#profile` **[TZ NAV-05]**.

Event handling: one capture-phase `click` listener handles `data-gv-*` attributes and one `submit` listener
handles the cabinet forms. Lesson actions use `data-lesson-*` attributes. Legacy actions use
`data-action="…"` / `data-go="…"`.

---

## 1. Account entry points (header, nav, gating)

### 1.1 Desktop header (≥ 811 px) — `cabinet-guest-profile-1440.png`, `cabinet-overview-1440.png`

The account-relevant controls, right to left:

| Control | Markup | Behaviour |
|---|---|---|
| Account button | `button.line-btn[data-action=account]`: user SVG (`header-account-user`) + `<span id="loginLabel">` | Label is «Войти» when logged out and «Кабинет» when logged in (`syncHeader()`). Click: logged in → `go('profile')`; logged out → registration modal (§3). **There is no login form**: «Войти» opens registration. **[TZ ACC-13]** |
| Messages | `button.square-btn[data-action=inbox]` (title/aria «Сообщения») + `span.count#inboxCount` | Opens the «Все сообщения» modal (§7.2). Logged out → registration. Badge = `chats.length`; shown only when logged in and > 0. It counts dialogs, not unread messages **[TZ MSG-06/07]**. |
| Favorites | `button.square-btn[data-action=favorites]` (aria «Избранное») + `span.count#favoritesCount` | Opens the «♡ Избранное» modal (§7.5). Works for guests too. Badge = `favorites.length`, hidden at 0. |
| Search | `button.square-btn[data-action=search]` | public, not covered here |
| Main nav | `nav#nav` | The engine appends `<button class="navlink" data-go="profile">Личный кабинет</button>` as the 7th item. It gets `.active` (bold + underline) while on `#profile`. |

The header **never shows the user's photo or initials**. TZ ACC-07/UX-10 expect an avatar in the header that leads to the
cabinet and cannot be edited there. Implement it as an avatar button that navigates to `/account`. Fall back to the
initial letter, as in the cabinet hero.

Badge style (`.count`): 15×15 circle, `#f44667`, white 10 px Arial, absolute top-right of the icon button.

### 1.2 Phone header (≤ 810 px) — `cabinet-header-loggedin-390.png`

* The main nav is hidden. The logo stays on the left; search, favorites, messages and the account button «Кабинет»/«Войти»
  stay on the right. Their padding shrinks at ≤ 540 px (`.navtools .square-btn{padding:6px}`, line-btn 12 px).
* Under the header there is a **horizontally scrolling text nav** `.mobile-nav` (no scrollbar):
  «Главная», «Инструкторы», «Споты», «GG Surfer», «Аренда», «Шейперы», «Клуб», and «Кабинет» (`data-go="profile"`,
  appended by the engine). «Кабинет» is off-screen until you scroll the strip.
* **There is no bottom tab bar in the prototype.** TZ NAV-03/UX-03 require one: «Главная, Каталог,
  Избранное, Сообщения, Кабинет». It must respect the safe area (ATX-22). Build it. The «Кабинет» tab has the same
  gating as the header button.

### 1.3 Gating (what a guest gets)

| Trigger | Guest result |
|---|---|
| `data-go="profile"` (nav links) | `openRegister()` (no navigation) |
| `data-action="account"` | `openRegister()` |
| direct `#profile` URL | guest page (§2) |
| messages icon, «Мои занятия», «✉ Написать в GG Surfer», booking, rental request, own rental listing | `openRegister()`; some add a toast: «Для заявки сначала создайте профиль» (booking), «Сначала создайте демо-профиль» (rental request), «Для объявления сначала нужен профиль» (own listing) |

### 1.4 Logout

Settings → «Выйти из демо-аккаунта» (`data-action="logout"`): `user=null`, `localStorage.removeItem('gg_user')`,
`go('home')`, toast «Вы вышли из демо-профиля». The other keys (orders, chats, favorites, reviews, availability)
are **not** cleared and are not scoped per user. The next demo user inherits them. **[BUG]**

---

## 2. Guest page (`#profile`, logged out) — `cabinet-guest-profile-1440.png`

* Hero, tall type, photo `hero_home` (`img/img04.webp`): kicker «Люди · волны · Россия», H1 «Здесь начинается<br> ваша история»,
  text «Заведите профиль, сохраняйте споты и находите своих людей на каждом берегу.», white button «Создать профиль →».
  **[BUG]** That button is `data-go="home"` and goes to the home page. It should open registration.
* Two `.side-card` boxes in a 2-column grid (1 column ≤ 810 px):
  * «Присоединяйтесь к «Гдеволне»» / «Выберите роль: сёрфер, инструктор или школа. Статус GG Surfer доступен для всех.» / primary «Создать аккаунт →» → registration.
  * «Уже с нами?» / «В демо-проекте профиль сохраняется только в браузере.» / pill «Демо-регистрация» → registration (there is no login form).

---

## 3. Registration modal (2 steps) — `cabinet-register-step1*.png`, `cabinet-register-step2*.png`

The modal is `.modal.wide` (820 px max, 29 px padding; 21 px padding at ≤ 540 px) with a close × at the top right.
`openRegister()` resets the data to `{role:'surfer', gg:false, public:true, interests:[]}`. Note that `rent` is undefined, and
`extraRoles` is created by the engine.

### 3.1 Step 1 — role

| Element | Copy / behaviour |
|---|---|
| H2 | «Добро пожаловать в «Гдеволну»!» |
| Lead | «Давайте познакомимся. Выбирайте основную роль — GG Surfer доступен для каждой.» |
| Stepper | 2 bars of 5 px, the first one `.current` (`#078aba`), the other `#ddedf3` |
| Label | «Кто вы в нашем сообществе?» (`b.small`) |
| Role cards `.role-list` (3 columns; ≤ 540 px: 2 columns, last card spans both) | `🏄` «Сёрфер», `♧` «Инструктор», `🏠` «Сёрф-школа». Click → `regData.role`, re-render. Selected card: `#e0f6ff` bg + 2 px `#0390bd` border. **[TZ ACC-01]** «Шейпер» must also be a primary type. In the prototype it is only an extra. |
| Extra specialties box (engine) | Title «Дополнительные направления», text «Можно выбрать несколько — они появятся в одном личном кабинете.». Checkbox pills: every role except the primary, `surfer` and `rental` (primary Сёрфер → «♧ Сёрф-инструктор», «◈ Шейпер», «⌂ Сёрф-школа»; primary Инструктор → «◈ Шейпер», «⌂ Сёрф-школа»; primary Школа → «♧ Сёрф-инструктор», «◈ Шейпер»). The state persists while you switch the primary role. Box: `#f1faff`, 1 px `#d7eaf5`, radius 12, padding 13; pills white, radius 9. |
| Toggle row | «♡ &nbsp; Хочу быть GG Surfer» / «Появляться в поиске сообщества, находить компанию, помогать друг другу.» → `regData.gg` |
| Toggle row | «◈ &nbsp; Сдаю снаряжение в аренду» / «Смогу добавлять доски и гидрокостюмы в каталог аренды. Доступно сёрферу, инструктору и школе.» → `regData.rent` (becomes the `rental` specialty) |
| Notice | «GG Surfer можно включить или выключить и после регистрации. Он не меняет основную роль.» |
| Button | full-width primary «Продолжить →» → step 2 |

Toggle geometry: v12 widened it to **58×30 px** with a 22 px knob (`.toggle-row > button.toggle`). Off `#b9dbe9`, on `#0a83ad`.
The knob moves via `justify-content:flex-end`. This is required by TZ UX-07.

### 3.2 Step 2 — about you (`form#registerForm`)

H2 «Пара слов о себе». Lead: `«{Сёрфер|Инструктор|Сёрф-школа}. »` + («С GG Surfer вас смогут найти люди поблизости.» | «GG Surfer можно будет добавить позже.»). Both stepper bars are current.
The grid has 2 columns (`.formgrid`; 1 column ≤ 540 px).

| Field (label verbatim) | Type / attrs | Options / placeholder |
|---|---|---|
| «Имя и фамилия *» | text `name`, required, autocomplete=name | «Как к вам обращаться» |
| «Имя пользователя *» | text `handle`, required, `pattern="[a-zA-Z0-9_]{3,24}"`, title «Латиница, цифры, _ от 3 до 24 символов» | «surfer_123» |
| «Электронная почта *» | email, required | «you@example.com» |
| «Дата рождения *» | date, required, `max="2026-10-19"` (hard-coded) | — |
| «Пол *» | select, required | «Выберите» (""), «Женский» (female), «Мужской» (male) |
| «Регион *» | select, required | «Выберите регион», Камчатский край, Крым, Сахалин, Ладожское озеро, Приморский край, Другой регион |
| «Уровень катания» | select | Начинающий, Средний, Продвинутый |
| «Тип доски» | select | Лонгборд, Шортборд, Фанборд, Пока без своей |
| «Выберите минимум 3 интереса *» | toggle chips `.interest` (selected = filled `#037aa6`) | Сёрфинг, Кемпинг, Сноуборд, Путешествия, Фотография, Походы, Шейпинг, Йога, Экология, Кофе у океана |
| instructor only: «Квалификация» | text `cert` | «Номер сертификата / организация (при наличии)» (**not saved** **[BUG]**) |
| school only: «Название школы / юрлица» | text `school`, required | «Название, ИП / ООО» (**not saved**, and no organization is created **[BUG][TZ ACC-11]**) |
| instructor/school: `.doc-upload` block | «Документы для профиля» / «Основной документ обязателен. Дополнительный — по желанию.» | file «Документ о профессиональном статусе или регистрации деятельности *» (school: «Регистрационный документ школы / ИП / ООО *»), required, `accept=".pdf,.jpg,.jpeg,.png,.webp"`; file «Сертификат / подтверждение квалификации (необязательно)»; small print «Только PDF и изображения до 10 МБ. В прототипе файлы не загружаются на сервер и не сохраняются — после регистрации показываем лишь имена выбранных файлов.» **[TZ INS-03/ATX-04]** An instructor must be able to register **without** documents. The prototype makes the main document mandatory. |
| consent | checkbox `consent`, required | «Согласен на демонстрационное сохранение профиля в этом браузере. Настоящее согласие на обработку данных и публичность будет оформлено при запуске проекта.» |
| buttons | pill «← Назад» (step 1), primary submit «Создать демо-профиль →» | |
| note | «В реальной версии вход будет с подтверждением email/телефона, проверкой согласий и безопасным хранением. Здесь данные не передаются на сервер; email, дату рождения и пол локально не сохраняем.» | |

Validation on submit (toasts verbatim; checked in this order after native HTML validation):

1. fewer than 3 interests → «Выберите хотя бы три интереса»
2. no birthday → «Укажите дату рождения»
3. GG on and age < 18 → «GG Surfer доступен только участникам от 18 лет» (the age is checked only when GG is switched on at registration; turning GG on later in Settings is not checked **[BUG]**)
4. any document > 10 MB or with a wrong extension → «Документы: PDF/изображения, не более 10 МБ»
5. instructor/school without the main document → «Добавьте основной документ»

On success the user object becomes `{documents:[file names], name, handle, region, level, board, role, gg, rent, public, interests}`.
Email, birthday and gender are dropped. Then `roles = unique([role, …(rent?['rental']:[]), …extraRoles])`, it is stored to `gg_user`, the modal closes, the app goes to `#profile`
(the cabinet «Обзор»), and the toast is **«Добро пожаловать в «Гдеволну»! ♡»**.
If the user has the instructor role, a local instructor card is created in the public catalogue (`mine_<handle>`, see §6.2.6).

---

## 4. Cabinet layout (`.gv-account`) — `cabinet-overview-1440.png`, `cabinet-overview-390.png`

```
.gv-account (max 1240px, centered, margin 26px auto 65px)
 ├─ .gv-ac-hero      avatar · kicker/name/handle·region/specialty tags · [+ Направление] [Мой профиль]
 └─ .gv-ac-grid      225px | 1fr  (gap 17)
     ├─ nav.gv-ac-nav   sticky (top 15px) sidebar: «ОБЩЕЕ» group + «МОИ СПЕЦИАЛЬНОСТИ» group
     └─ .gv-ac-workspace#gvAcWorkspace   one .gv-ac-panel per pane
```

### 4.1 Hero (`.gv-ac-hero`)

* Gradient `#f4fcff → #e4f6ff`, 1 px `#cdeaf7`, radius 22, padding 22×24.
* Avatar 66 px circle: the `user.avatar` image (data URL in the demo), otherwise the first letter of the name, upper-cased, 26 px `#0875aa` on `#d9f1ff`.
  It has a 3 px white border. It is not clickable («Фото в шапке не редактируется»).
* Kicker «Личный кабинет ГДеволна» (10 px, uppercase, letter-spacing .13em, `#3692b6`). H1 = `user.name` or «Участник» (23 px `#094b78`).
  Line `@{handle} · {region | «Регион не указан»}`.
* Tags `.gv-ac-tag`: one per connected specialty, in `user.roles` order, as `{glyph} {name}`: «≋ Сёрфер», «♧ Сёрф-инструктор», «◈ Шейпер», «⌂ Сёрф-школа», «▤ Прокат».
* Right-side buttons (`.gv-ac-btn`): «+ Направление» → Мои направления, «Мой профиль» → Профиль.

### 4.2 Sidebar nav (`nav.gv-ac-nav`, aria-label «Навигация личного кабинета»)

Group label «Общее» (10 px uppercase `#8aa6b6`), fixed items:

| id | glyph | label | badge |
|---|---|---|---|
| overview | ⌂ | Обзор | |
| profile | ◉ | Профиль | |
| inbox | ✉ | Обращения | `chats.length` if > 0 (`.gv-ac-nav-count`, `#0784bb` pill) |
| bookings | ▣ | Бронирования | |
| favorites | ♡ | Избранное | |
| directions | ⊕ | Мои направления | |
| settings | ⚙ | Настройки | |

Group label «Мои специальности» is shown only when at least one specialty is on. Items appear in a fixed order: «≋ Сёрфер», «♧ Сёрф-инструктор», «◈ Шейпер», «⌂ Сёрф-школа», «▤ Прокат».

Item style: 12.5 px / 650, color `#466f8a`, padding 11×10, radius 10. Hover `#e9f6fc`.
**Active**: `#def3ff` bg, `#056c9d` text, inset 3 px left bar `#159bd0`, `aria-current="page"` (general items only).

**[TZ ACC-02]** The general screens must also include «Уведомления» (missing). **[TZ ACC-09]** The prototype places «Профиль» and «Настройки» far apart
(Профиль is 2nd, Настройки 7th). Place them next to each other.

### 4.3 Responsive

| Width | Change |
|---|---|
| ≤ 900 px | sidebar 185 px; stat grid 2 columns; panel padding 17 |
| ≤ 710 px | `.gv-account` width = 100% − 20 px. Hero: avatar 50 px, H1 18 px, action buttons full row. **Sidebar becomes a horizontal scrolling tab strip** (`display:flex; overflow-x:auto`); group labels are hidden; the active tab gets an inset 2 px **bottom** bar and a border. Cards 1 column, form fields 1 column, list rows wrap. The shaper iframe height becomes `calc(100dvh - 165px)` (min 550). |
| ≤ 360 px | width = 100% − 14 px; smaller paddings; stat number 18 px |

On phones the strip does not auto-scroll to the active tab. When you open a specialty (e.g. instructor) the active tab is
off-screen (`cabinet-instructor-requests-accepted-390.png`). Scroll the active tab into view in the real build.

### 4.4 Building blocks (all panes)

| Block | Class | Spec |
|---|---|---|
| Panel | `.gv-ac-panel` | white 96%, 1 px `#d1e8f4`, radius 17, padding 22 (16 on phones), shadow `0 6px 26px #056e9a0b`. H2 20 px `#0a5b85`; lead `.gv-ac-desc` 12.5 px `#7897aa` |
| Stat tiles | `.gv-ac-stats > .gv-ac-stat` | grid of 4 (2 at ≤ 900 px). Tile `#f0f9ff`, radius 12; number 22 px `#096e9f`; label 11 px `#668aa1` |
| Cards | `.gv-ac-cards > .gv-ac-card` | 2 columns (1 at ≤ 710 px). Card `#fcfeff`, 1 px `#d7ebf5`, radius 13, padding 16. Head: H3 + 24 px glyph on the right |
| List row | `.gv-ac-line` | title 13 px bold `#115c86` + `small` meta 11 px `#83a0b0`; actions on the right; 1 px `#e7f2f8` divider |
| Empty | `.gv-ac-empty` | `#f4fbff`, 1 px **dashed** `#c4e7f7`, radius 12, centered 12 px text |
| Note | `.gv-ac-note` | `#f1faff`, 1 px `#d8edf8`, radius 12, 12 px `#6c91a7` |
| Module row | `.gv-ac-module` | 42 px icon tile `#e8f7ff` + title/description + control on the right |
| Switch | `.gv-ac-switch` | **56×30**, knob 20 px, off `#d1e1e9`, on `#0b95c4`, knob translateX(28px). `aria-pressed` |
| Button | `.gv-ac-btn` | white, 1 px `#b7dced`, radius 10, 9×12, 12 px/700 `#086b9f`; `.primary` `#087fae` filled; `.danger` text `#a74b52`; `[disabled]` opacity .45 |
| Status chip | `.gv-ac-status` | 10 px pill: default blue `#e7f7ff`/`#267aa4`; `.done` green `#e7f8eb`/`#328253`; `.warn` amber `#fff6e8`/`#ac8027` |
| Mini tabs | `.gv-ac-mini-tabs` | horizontal scroll pills; active `#e0f5ff`, border `#69bada`, 750 weight |
| Form | `.gv-ac-form`, `.gv-ac-fields` | 2-column grid, labels 12 px/650 `#40718c`; inputs radius 10, 1 px `#c5e5f4`, `#fbfeff`; focus outline 2 px `#8bd0f5`; select with custom chevron and 31 px right padding (UX-06) |

---

## 5. General panes

### 5.1 «Обзор» (overview) — `cabinet-overview-1440.png`

Panel «Ваш обзор» / «Общие события и инструменты всех подключённых направлений в одном месте.»

Stats: `chats.length` «Диалогов GG Surfer / занятий» · `orders.length` «Заявок на занятия» · `rentalRequests.length` «Заявок на аренду» · `favorites.length` «В избранном».

Four cards. Each has an H3, a glyph and a description, plus a button «Открыть →»:

| Title | Glyph | Text | Goes to |
|---|---|---|---|
| Обращения | ⌖ | Заявки и чаты от клиентов, инструкторов, школ и мастерских. | inbox |
| Мои бронирования | ♧ | Занятия, аренда и записи на ближайшие даты. | bookings |
| Мои направления | ⊕ | Подключайте новые специальности без повторной регистрации. | directions |
| Профиль и настройки | ⚙ | Общая информация, видимость и управление аккаунтом. | profile |

Conditional notes:
* instructor: «♧ Инструктор: рабочее расписание, заявки, ученики и отзывы доступны в разделе «Сёрф-инструктор».»
* school: «⌂ Сёрф-школа: {name | «организация пока не оформлена»} · {N} программ · {N} занятий.»
* shaper: «◈ Шейпер: {N} моделей · {N} обращений в локальном кабинете мастерской.» (read from the shaper module's localStorage `gdevolna_shaper_demo_v1`)

**[TZ MET-01]** This screen should be a summary dashboard with a filter by specialty.

### 5.2 «Профиль» (common profile) — `cabinet-pane-profile-1440.png`

Panel «Мой профиль» / «Имя, регион и фотография общие для всех подключённых направлений. Профессиональные сведения редактируются в соответствующих разделах.»

`form#gvCommonProfile`:

| Label | Control | Notes |
|---|---|---|
| «Имя / название пользователя» | text `name`, required, maxlength 90 | |
| «Регион» | select | Камчатский край, Крым, Приморский край, Сахалин, Ладожское озеро, Другой регион, plus the current value if it is not in the list |
| «Уровень катания» | select | Начинающий, Средний, Продвинутый, Эксперт (+ current) |
| «Основная доска» | text `board`, maxlength 70 | (registration offers a select here, the profile a free text field) |
| «Фото пользователя (только здесь)» | file `avatar`, `accept="image/jpeg,image/png,image/webp"` | hint «Новый снимок до 1,5 МБ сохранится локально. Фото в шапке не редактируется.» |
| note | | «Ваш идентификатор: **@handle**. Он не меняется при подключении новых специальностей, чтобы сохранялись связи заявок и записей.» |
| buttons | primary «Сохранить профиль», «Управление специальностями →» (→ directions) | |

On submit: photo > 1.5 MB → «Фото не больше 1,5 МБ»; wrong type → «Нужен JPG, PNG или WebP». Otherwise the photo is saved
as a data URL in `gg_user.avatar` and the toast is «Профиль сохранён».

**[TZ ACC-08]** This must be the single registration/edit form, with the button text depending on state and a «Посмотреть на сайте» link.
There is no handle change, email, phone, password or account deletion **[TZ ACC-13/14]**. The avatar has no preview, crop or remove control.

### 5.3 «Обращения» (inbox hub) — `cabinet-pane-inbox*.png`

Panel «Обращения» / «Единая точка входа для разных направлений. Внутренние сообщения шейпера и школы остаются доступны в их рабочих разделах.»

Stats: `chats.length` «Диалогов» · `orders.length` «Заявок на занятия» · `rentalRequests.length` «Заявок на аренду» · shaper `requests.length` (0 without the shaper role) «Заявок мастерской».

Cards:
* «Чаты и занятия» / «Сообщения участников GG Surfer, клиентов и инструкторов. История открывается в существующем чате.» / **primary** «Открыть переписку →» → «Все сообщения» modal (§7.2).
* «Мои записи» / «Подтверждение, переносы и завершённые занятия.» / «Посмотреть бронирования →» → bookings.
* (shaper) «Заказы на доски» / «Приём заявок, переписка и статусы заказов.» / «К обращениям мастерской →» → shaper pane (the iframe does not deep-link to its requests tab).
* (school) «Заявки школы» / «Список учеников и внутренние записи школы.» / «Открыть учеников →» → school › Ученики.

Separator, then H3 «Последние заявки на занятия»: up to 6 lesson orders. Title = `service` («Занятие»), meta `{clientName|«Ученик»} · {date|«Дата уточняется»} · {status|«Ожидает»}`.
The status shows the **raw code** (`pending`, `completed`) **[BUG]**. Button «Подробнее →» → bookings. Empty state: «Обращений по занятиям ещё нет.»

**[TZ MSG-01/8.6]** The real build needs a single inbox with filters «Клиент / Шейпер / Школа / Инструктор / Прокат», statuses, unread counters and context cards.
The prototype screen is only a hub of links.

### 5.4 «Бронирования» (my bookings) — `cabinet-pane-bookings*.png`

Panel «Мои бронирования» / «Занятия, аренда оборудования и ваши записи. Профессиональные рабочие календари находятся в соответствующих модулях.»

Stats: all orders «Заявок на уроки» · accepted «Подтверждено» · completed «Проведено» · `rentalRequests.length` «Заявок на аренду».

* H3 «Занятия»: up to 12 rows. Title `service` («Обучение сёрфингу»), meta `{date} {slot} · {clientName}`. Status chip:
  pending «Ожидает», accepted «Подтверждено», completed «Завершено» (green `.done`), declined «Отклонено», anything else raw («cancelled» **[BUG]**), empty «Новое».
  Empty state: «Пока нет записей на обучение.»
* Separator, H3 «Аренда»: up to 10 rows. Title (fallback «Оборудование»), meta `{from} — {to}`, chip = raw status (`sent` **[BUG]**, the rentals module maps it to «Отправлена»).
  Empty state: «Аренда ещё не бронировалась.»
* Buttons «Найти инструктора →» (→ instructors catalogue), «Каталог аренды →» (→ rentals).

**[BUG / TZ MSG-02, ATX-27]** The list holds **all** lesson orders in the browser, including incoming orders to the user's own
instructor card (e.g. «Саша — тестовый ученик»). Client-side bookings and provider-side requests are not separated.
The rows are read-only: cancel, chat and review exist only in the «Мои занятия» modal (§7.1), and no cabinet button opens that modal.
Board orders that a client sends to shapers do not appear here. They exist only inside the shaper module as «Мои исходящие заявки». A client without the shaper specialty has no «Мои заявки на доски» anywhere **[TZ SHO-03, MSG-02]**.
The real «Мои бронирования / Мои заявки» must merge lesson bookings, rental bookings and board/repair orders, all client-side.

### 5.5 «Избранное» — `cabinet-pane-favorites*.png`

Panel «Избранное» / «Ваши сохранённые споты и анкеты, независимо от выбранной специальности.»
Note «Всего сохранено: **N**. Избранное уже связано с публичными каталогами.»
Rows: title «Спот» (`spot:` prefix) / «Инструктор / участник» (`person:`) / «Сохранённое» (other, e.g. `rental:`). The meta shows the **raw id** (`spot:halak`) **[BUG]**.
Button «Показать →» opens the generic favorites modal (§7.5), not the item. Empty: «Избранного пока нет. Сохраните спот или инструктора из каталога.»
**[TZ MSG-11, ATX-11]** Typed favorites (spot, school, instructor, model, shaper, equipment) need real cards and filters.

### 5.6 «Мои направления» (specialties) — `cabinet-pane-directions*.png`

Panel «Мои направления» / «Можно быть сёрфером, инструктором и шейпером одновременно. Добавление роли не создаёт второй аккаунт.»
Note «Аккаунт **@handle** · подключено направлений: **N**. Отключение специальности скрывает её вкладку, но не удаляет локальные данные.»

Five `.gv-ac-module` rows. Each has a switch (`data-gv-toggle`, aria-label «Подключить: X»/«Отключить: X»):

| id | Glyph | Name | Description |
|---|---|---|---|
| surfer | ≋ | Сёрфер | Дневник катания, любимые споты и клубная активность |
| instructor | ♧ | Сёрф-инструктор | Календарь занятий, ученики, заявки и отзывы |
| shaper | ◈ | Шейпер | Мастерская, доски, заявки, аренда и аналитика |
| school | ⌂ | Сёрф-школа | Программы, расписание, команда и ученики |
| rental | ▤ | Прокат | Снаряжение, доступность и заявки на аренду |

Button: primary «Вернуться в обзор →».
Toggling updates `user.roles` (and `user.rent` for rental), saves, re-renders, and shows the toast «Направление добавлено» / «Направление скрыто».
**[TZ 7.1]** Real flow: server check → create/activate `user_specialties`. School → «Создать» or «Присоединиться по приглашению».
Disabling must warn about active bookings and offer to stop publishing. All roles can be switched off in the demo, including the last one.

### 5.7 «Настройки» — `cabinet-pane-settings-1440.png`

Panel «Настройки» / «Общие предпочтения для всех направлений. Административные права не выдаются через подключение специальности.»

| Glyph | Title | Text | Control |
|---|---|---|---|
| ≋ | GG Surfer | Участвовать в поиске единомышленников | switch → `user.gg` (no toast) |
| ◎ | Показываться на карте | Показывать приблизительное местоположение вашего региона, без точного адреса | switch → `user.public` |
| ♧ | Управление специальностями | Добавить или скрыть инструменты своих направлений | «Настроить →» → directions |

Note «В демонстрационной версии данные, документы и настройки доступны только в текущем браузере. Настоящие права доступа, безопасность и совместная работа появятся после подключения сервера.»
Danger button «Выйти из демо-аккаунта» (§1.4).
**[TZ]** Notification preferences (MSG-12), data export/deletion and consents (ACC-13) are missing. The GG status select («Покажу споты / Ищу компанию / Могу подвезти») from the legacy page is gone (§12).

---

## 6. Specialty panes

### 6.1 «Сёрфер · мой дневник» (surfer) — `cabinet-pane-surfer-1440.png`, `cabinet-surfer-diary-1440.png`

Lead «Личная история катания, любимые споты и сообщество. Дневник виден только вам в этом браузере.»
Stats: diary entries «Выходов на воду» · distinct spots «Разных спотов» · favorite spots «Любимых спотов» · «Да/Нет» «GG Surfer».

Two cards:
* «Добавить катание» (`form#gvDiaryForm`): «Дата» (date, required, defaults to today as a UTC ISO date), «Спот» (select «Выберите спот» + 6 demo spots),
  «Как прошла сессия?» (textarea maxlength 450, placeholder «Волна, погода, доска, впечатления...»), full-width primary «Записать катание».
  Missing date or spot → «Укажите дату и спот»; success → «Выход на воду сохранён» (the new entry goes on top).
* «Последние выходы»: 7 most recent; title = spot name («Другой спот»), meta `{date} · {notes|«Без заметок»}`, small «×» button (aria «Удалить запись»)
  → confirm «Удалить запись о катании?». Empty: «Дневник пока пуст.»

Buttons «Карта спотов →», «Найти компанию →» (→ GG Surfer). Storage: `gv_unified_diary_<handle>`. TZ MET-06 / F12.

### 6.2 «Сёрф-инструктор» (instructor workspace) — `cabinet-pane-instructor-1440.png`, `cabinet-instructor-*.png`

Outer panel «Инструктор · рабочее место» / «Расписание, занятия и заявки уже используют существующий механизм записи на урок.»
Outer stats for orders where `personId = mine_<handle>`: «Всего заявок» · «Ожидают ответа» · «Подтверждено» · «Проведено».
Below that is the `.lesson-dash` card, cut out of the legacy renderer and wrapped in `.gv-ac-lesson`.
If extraction fails, the fallback is panel «Сёрф-инструктор» / «Сейчас доступен только прототип.» / «Здесь появятся расписание, занятия, ученики и статистика.»
**[TZ MET-01/02]** This shows two stat rows (outer + inner) for the same data. Keep one compact row.

`.lesson-dash`: white, 1 px `#d0eaf5`, radius 20, padding 21. Header:
kicker «Личный кабинет · инструктор», H2 «Мой сёрф-день», line «{name} · расписание, заявки и общение с учениками».
Button on the right: «Заявки ({pending}) →» (→ tab Заявки). In demo preview mode it is «← Вернуться к ученику».
Banner (`.lesson-demo-banner`, dashed): «Личный кабинет и расписание пока работают локально. В боевой версии заявки и доступ к данным будут проверяться сервером.»

Tabs (`.lesson-dash-tab-row`, segmented, active = white raised): **Обзор · Календарь · Заявки · Сообщения · Отзывы · Мой профиль**
(min-width 120 px each; the row scrolls horizontally on phones).

#### 6.2.1 Обзор — `cabinet-instructor-overview-after-1440.png`
Stat row (4): «Новых заявок» (pending) · «Подтверждено» · «Завершено» · «Новых отзывов».
Two `.lesson-info-card`s:
* «Ближайшие заявки»: up to 3 pending as `◷ {clientName} · {день месяц год} {slot}`, or «Новых заявок нет. Хорошее время проверить расписание.»; pill «Открыть заявки →».
* «Ваш рабочий день» / «Отмечайте свободные дни, отвечайте ученикам после подтверждения заявки и закрывайте занятия по факту.» / pill «Настроить календарь →».

#### 6.2.2 Календарь (availability management) — `cabinet-instructor-calendar-1440.png`
Kicker «Рабочее расписание», H3 «Когда вы готовы встречать учеников?». Two columns (`1.3fr | .9fr`; stacked ≤ 760 px):

* **Month grid** `.lesson-cal`. Header: «{месяц} {год}» (CSS capitalize, e.g. «Октябрь 2026») with ‹ › buttons (aria «Предыдущий месяц»/«Следующий месяц»).
  You can move from the current month up to +2 months. Weekdays «Пн Вт Ср Чт Пт Сб Вс». Monday-first grid, square cells.
  Cell = day number + 7 px caption:

  | State | Rule | Caption | Style |
  |---|---|---|---|
  | out of range | before today or > 91 days ahead | — (disabled) | `#f6f8f9` / `#c4d1d6` |
  | closed | saved `closed`, or default weekday **Mon or Thu** | «выходной» | `.closed` grey `#f1f3f6` |
  | booked | ≥ 1 accepted order | «{n} занято» | `.booked` peach `#fff1e9` / `#a66b37` |
  | full | no free slot | «занято» | `.booked` |
  | open | free slots | «{n} окна» (always «окна», even «1 окна» **[BUG]** plural) | `#eaf8fe` / `#0b648c` |
  | today | | | 1 px border `#f4ba82` |
  | selected | | | filled `#04749f`, white |

  Legend: «Есть окна» (`#c8eefb` dot), «Выходной» (`#e6e9ec`), «Занято» (`#ffddc3`).
  Default selection is the first day in the next 35 days that has a free slot.
* **Side panel** `.lesson-side`: kicker «Управление доступностью», H3 = the selected date in long form («21 октября 2026 г.»),
  text «Нажмите на время, чтобы открыть или закрыть запись. Подтверждённые занятия нельзя убрать из календаря.»
  Slot buttons for the 3 standard slots **09:00, 12:00, 15:00**. Suffix «· закрыто» marks a closed slot (style `.selected`). Suffix «· занято» marks an accepted order (disabled).
  Pill «Сделать день выходным» / «Открыть этот день». Hint «Изменения сохраняются в этом браузере. В настоящем сервисе потребуется сервер и синхронизация расписания.»
  Errors: closing a day that has accepted lessons → «Здесь уже есть подтверждённые занятия». Toggling a booked slot → «Это время уже подтверждено ученику».
  Re-opening any slot on a closed day re-opens the day.

**[TZ INS-06/07, SCH-07]** The real calendar needs custom slots and duration, recurring rules, cancellations and reschedules,
merged school sessions and server-side double-booking prevention. The prototype only has 3 fixed slots.

#### 6.2.3 Заявки (incoming lesson requests) — `cabinet-instructor-requests-demo|accepted|completed-1440.png`
Line «Заявки учеников к этому инструктору · всего {N}» with pill «+ Создать тестовую заявку» (demo generator).
Empty state: «≋» / «Пока спокойно — ждём первую запись» / «Попробуйте создать тестовую заявку, чтобы посмотреть весь путь ученика.» / «Добавить пример заявки →».

**Order card** `.lesson-order` (shared by the coach and client views):
```
[♧|≋ 42px tile]  ● {status label}  (status pill)
                 {coach view: clientName | client view: instructor name}   (H3)
                 {21 октября 2026 г.} · {09:00} · {service}
                 «{note}»                                         (hint, optional)
                 [level chip] [№ {last 8 chars of id}]
──────────────────────────────────────────────── actions
```

| Status code | Label (`allOrderStates`) | Pill colors |
|---|---|---|
| pending | Ожидает ответа | `#fff4dd` / `#916c23` |
| accepted | Подтверждено | `#e3f6ed` / `#218064` |
| completed | Занятие завершено | `#e8f0ff` / `#3875af` |
| declined | Отклонено | `#f3edf1` / `#90677c` |
| cancelled | Отменено | `#f3edf1` / `#90677c` |

Actions by status and side:

| Status | Coach | Client |
|---|---|---|
| pending | primary «✓ Принять заявку», outline-danger «Отклонить» | «Отменить заявку» |
| accepted | pill «✉ Чат с учеником», primary «Завершить занятие» | pill «✉ Чат с инструктором», «Отменить заявку» |
| completed | hint «Клиент оставил отзыв» / «Ожидаем отзыв ученика» | primary «★ Оценить занятие» / disabled «★ Отзыв оставлен» |
| client & sample instructor | — | pill «Как это видит инструктор (демо) ↗» (preview mode, see 6.2.7) |

Transitions (toasts verbatim):
* Accept: blocked if the slot is already taken by another accepted order («Время уже занято другой подтверждённой заявкой») or the day is closed («Сначала откройте эту дату в расписании»).
  Otherwise `accepted` + `acceptedAt`, a lesson chat is created with the first coach message **«Привет! Подтверждаю занятие. Давайте уточним детали встречи и снаряжение.»**, and the toast is «Заявка подтверждена — чат открыт».
* Decline → `declined`, «Заявка отклонена (демо)». (No reason field **[TZ 7.3]**.)
* Complete → `completed` + `completedAt`, «Занятие завершено. Теперь ученик может оставить отзыв.»
* Client cancel → `cancelled`, «Заявка отменена. Для нового времени создайте новую заявку.»
* Demo generator: the first date in the next 37 days with a free slot. Order: `clientName:'Саша — тестовый ученик'`, `service:'Индивидуальное'`, `level:'Первое занятие'`,
  `note:'Буду в вашем регионе. Это тестовая заявка для проверки работы кабинета.'`, `demo:true` → «Тестовая заявка создана. Можно подтвердить её.». No free date → «Сначала откройте свободную дату в календаре».

**[TZ 7.3]** Target statuses: requested → confirmed / declined (with reason), confirmed → in_progress → completed, cancelled, no_show. Reschedule is missing.

#### 6.2.4 Сообщения
A list of lesson chats linked to this instructor's orders, as `.inbox-item` rows: initial avatar, client name, «{дата} · {N} сообщ.», →. Each opens the chat in coach perspective.
Empty: «Здесь появятся переписки по урокам» / «Когда инструктор примет заявку, чат откроется автоматически.»

#### 6.2.5 Отзывы
`.lesson-reviews-section`: metric card with kicker «Оценка учеников», a big average (or «—»), and «{n} отзывов · показаны примеры и локальные отзывы». Above that line there is a static gold «★★★★★» that does not reflect the average **[BUG]**.
Review list: cards with name, stars and text, and the caption «Отзыв после демо-занятия» (local) or «Пример отзыва · дизайн-прототип» (seed).
Empty: «≋» «Первые слова ещё впереди» / «Отзывы появятся после завершения подтверждённых занятий.»

#### 6.2.6 Мой профиль (instructor card) — `cabinet-instructor-about-1440.png`
* Card «Публичная карточка»: **name**, «{region} · {spots}», pill «Посмотреть как ученик →» (opens the public instructor modal).
* Card «Верификация»: «Документы загружены: {N}» + hint «Статус пока «Не проверено». Фото и данные доступны только локально.» **[TZ INS-03]** Use the 3-state certificate badge «не указан / загружен / проверен» with moderation.
* Own profile only: `form#lessonProfileForm` «Редактировать карточку инструктора». Fields:
  «Имя / название» (required) · «Город» · «Споты (через запятую)» · «Опыт (лет)» (number 0–60) · «Уровень учеников» · «О себе — с душой» (textarea, maxlength 650, 3 rows).
  Primary «Сохранить карточку». Hint «Изменения сохраняются только на вашем устройстве, без публикации на сервер.»
  Saved to `gg_profile_extras_v3[mine_<handle>]` with limits name 90 / town 100 / spots 220 / students 100 / bio 650 → «Карточка инструктора сохранена в браузере».
* In preview mode (someone else's card), banner «Вы смотрите пример панели инструктора. Чтобы редактировать собственный публичный профиль, зарегистрируйтесь с ролью «Инструктор» или «Сёрф-школа».»

Own public card defaults (`syncOwnInstructor`). It is inserted into the public catalogue array:
name = extras.name | user.name | «Новый инструктор»; region = user.region | «Камчатский край»; spots by region
(Камчатский край «Халактырский пляж, Авачинская бухта», Ладожское озеро «Ладожские шхеры, бухта Кирьявалахти», Крым «Балаклава, Судак»,
Сахалин «Охотское море, Пильтун», Приморский край «Русский остров», else «Споты уточняются»); students «Начинающий, средний»; exp 1; rating «—»; reviews 0;
photo `p0` (a demo photo of another person **[BUG]**); fact «Очень люблю океан и хочу делиться этим чувством!»; status «Познакомимся».
**[TZ INS-01/02/08/12, ACC-15]** The real card needs first/last name, photo/video management, formats, prices, languages and a publication check.

#### 6.2.7 Demo preview «Как это видит инструктор (демо)»
From the client's «Мои занятия» modal you can open the coach side of a sample instructor (`demoStaffId`). The code sets `accountTab='requests'` and navigates to `#profile`,
but the unified cabinet stays on its current pane. The coach view appears only inside the «Сёрф-инструктор» pane, so
a pure surfer lands on «Ваш обзор» **[BUG]**. The banner in this mode reads «Демонстрационный просмотр стороны инструктора «{name}». Это не настоящий доступ к чужому кабинету — все изменения существуют только в вашем браузере.»
**Do not port**: this is demo-only impersonation.

### 6.3 «Шейпер · мастерская» (shaper wrapper) — `cabinet-pane-shaper-1440.png`, `-390.png`

Lead «Полный существующий кабинет шейпера сохранён: модели досок, артикулы, медиа, обращения, бронирования и аналитика.»
Stats read from `localStorage.gdevolna_shaper_demo_v1`: `models.length` «Моделей досок» · `requests.length` «Входящих заявок» · models with status «В наличии» «Досок в наличии» · `profile.workshop ? «Да» : «Нет»` «Мастерская оформлена».
The values are computed before the iframe has initialised its demo data, so they show 0 until the next re-render **[BUG]**.
Note «Профессиональные данные мастерской остаются в её локальном хранилище. В будущем объединим их с общим серверным идентификатором аккаунта.»
Then `iframe#gvUnifiedShaperFrame.gv-ac-shaper-frame` (title «Рабочий кабинет шейпера»). It is 860 px high on desktop (min 560) and `calc(100dvh - 165px)` (min 550) on phones, radius 13.
Its `srcdoc` is the whole shapers document (`#gv-full-shapers-document`, = `source/shapers.html`). Button below: «Посмотреть публичный каталог шейперов →» (→ `#shapers`).
The embedded document always starts on its **shaper dashboard**. Its init runs `showPage('dashboard'); switchPanel(profile ? 'overview' : 'profile')`, so a user without a workshop profile lands on the «Профиль мастерской» registration form, as in the screenshot.
It renders **its own header, logo, nav and hero** («Личный кабинет шейпера») inside the cabinet.
A `srcdoc` iframe shares the parent origin, so both documents read and write the same localStorage. That is how the wrapper reads `gdevolna_shaper_demo_v1`.
In the real app, render the shaper tools as native cabinet tabs: no iframe and no second header. See `SHAPERS_SCREENS.md` for the content.

### 6.4 «Сёрф-школа · управление организацией» (school) — `cabinet-pane-school-1440.png`, `cabinet-school-*.png`

Storage: `gv_unified_school_<handle>` = `{name, region, description, contacts, spot, programs[], sessions[], members[], students[]}`. In the demo the school belongs to the personal account, not to an organization **[TZ SCH-01, ACC-11]**.

**Empty state** (no name): lead «Сначала заполните карточку школы. Затем откроются программы, занятия и команда.»,
note «⌂ Школа — отдельная организация, к которой позже можно будет назначить владельца, менеджера и инструкторов. Подключение роли не создаёт вторую учётную запись.», primary «Создать карточку школы →» (→ tab «Страница школы»).
When a name is set the lead becomes «{name} · {region} · отдельные рабочие данные организации».

Tabs (`.gv-ac-mini-tabs`): **Обзор · Программы · Расписание · Ученики · Команда · Аналитика · Страница школы**.
**[TZ SCH-03]** The required set is Обзор, Профиль школы, Программы, Расписание, Ученики, Команда, **Оборудование**, **Обращения**, Аналитика, **Отзывы**. The three in bold are missing.
Creating any entity before the school has a name → toast «Сначала создайте школу» and a jump to «Страница школы».

| Tab | Content |
|---|---|
| **Обзор** — `cabinet-school-overview-1440.png` | Stats «Программ» · «Занятий в плане» · «Записей учеников» · «Сотрудников». Card «Ближайшие занятия»: up to 4 upcoming sessions, sorted, as `{program} / {date} · {time} · {coach|«Инструктор не выбран»}`. Empty «Занятий пока нет. Добавьте первое в расписание.» Button «Расписание →». Card «Развитие школы» / «Создайте программы, настройте расписание и добавьте сотрудников. Каждая запись сохраняется внутри организации, а не личного кабинета инструктора.» / «Мои программы →». **[BUG]** Both buttons use `data-gv-pane` instead of `data-gv-school` and land on the general «Ваш обзор». |
| **Программы** — `cabinet-school-programs-1440.png` | Header «Программы обучения ({N})» + primary «+ Программа». Rows: name / `{duration|«Продолжительность не указана»} · {price|0} ₽ · {level|«Любой уровень»}` / «✎ Изменить». Empty «Добавьте первую программу обучения.» |
| **Расписание** — `cabinet-school-schedule-1440.png` | Header «Расписание ({N})» + primary «+ Занятие» (disabled without programs, with note «Сначала создайте программу обучения.»). Rows sorted by date: program / `{date} {time} · {spot|school spot|«Спот не выбран»} · {capacity} мест · {coach|«Инструктор не назначен»}` / «✎». Empty «Добавьте дату и время занятия.» |
| **Ученики** — `cabinet-school-students-1440.png` | Header «Ученики ({N})» + «+ Добавить запись». Lead «Пока записи создаются вручную для тестирования. В боевой версии они будут поступать из публичного бронирования.» Rows: name / `{contact|«Контакты не указаны»} · {program|«Программа не выбрана»}` / status chip + «Статус». Each click cycles **Новая → Подтверждена → Завершено → Отменена → Новая**; «Завершено» is green. Empty «Учеников пока нет.» |
| **Команда** — `cabinet-school-team-1440.png` | Header «Команда ({N})» + «+ Добавить сотрудника». Note «Добавление сотрудника здесь формирует запись о команде, но не выдаёт доступ к аккаунту. Реальные приглашения и права появятся после подключения сервера.» Rows: name / `{role|«Инструктор»} · {contact|«Контакт не указан»}` / amber chip «Без доступа» / «Изменить». Empty «Команда пока не добавлена.» |
| **Аналитика** — `cabinet-school-analytics-1440.png` | Stats «Всего занятий» · «Предстоящих» · «Прошедших по дате» · «Мест по расписанию» (sum of capacities). Note «Эти значения рассчитаны по вашим сохранённым данным. Фактическая посещаемость, просмотры карточки, конверсия и выручка появятся только после подключения учёта событий и подтверждения оплаты.» |
| **Страница школы** — `cabinet-school-profile-empty-1440.png` | `form#gvSchoolProfile`, H3 «Публичная страница школы»: «Название школы» (required, max 100, placeholder «Например, Kamchatka Surf School») · «Регион» (text, max 90) · «Основные споты» (max 150) · «Контакт для заявок» (max 160, «Телефон или email») · «О школе» (textarea, max 850, «Кому подходят занятия, чем отличается школа...»). Buttons primary «Сохранить школу», «Посмотреть карточку». Hint «Пока карточка сохраняется локально и не публикуется в общем каталоге.» Save → «Карточка школы сохранена», then the Обзор tab. |

Edit modals (`editModal`): H2 + `.gv-ac-form`, buttons «Сохранить» (primary) and «Отмена». Edit mode adds a danger delete button.
Inputs made with the `field()` helper always get `maxlength="160"`.

| Modal | Title | Fields | Validation / toast |
|---|---|---|---|
| Program — `cabinet-school-program-modal|edit-modal-1440.png` | «Новая программа» / «Редактирование программы» | «Название программы» (required) · «Продолжительность» (default «90 минут») · «Стоимость, ₽» (number) · «Для какого уровня» select Начинающий / Средний / Продвинутый / Любой уровень · «Описание» (textarea, max 600). Delete «Удалить программу» (also deletes its sessions) | price not finite or < 0 → «Проверьте стоимость»; an empty price saves as 0 |
| Session — `cabinet-school-session-modal-1440.png` | «Добавить занятие» / «Изменить занятие» | «Программа» (select, required) · «Дата» (date, required, today) · «Время» (time, required, 10:00) · «Спот» (default school spot) · «Количество мест» (number, required, 5) · «Инструктор» select «Пока не назначен» + team names. Delete «Удалить занятие» | capacity outside 1–500 → «Укажите число мест от 1 до 500» |
| Student — `cabinet-school-student-modal-1440.png` | «Новая запись ученика» | «Имя ученика» (required) · «Контакт» · «Программа» select «Выберите» + programs. Note «В демоверсии запись добавляется вручную. Клиент ещё не получает уведомления.» | status «Новая» |
| Member — `cabinet-school-member-modal-1440.png` | «Добавить сотрудника» / «Изменить сотрудника» | «Имя сотрудника» (required) · «Email или телефон» · «Роль в школе» select Инструктор / Администратор расписания / Менеджер / Владелец. Delete «Удалить из списка» | — |
| Preview — `cabinet-school-preview-modal-1440.png` | H2 {name|«Моя сёрф-школа»} | box: kicker «Карточка школы · предварительный просмотр», H3 name (22 px `#0773a1`), «{region} · {spot}», description or «Описание школы пока не заполнено.», «{N} программ обучения · {N} сотрудников». Note «Карточка пока не опубликована для других пользователей.» | |

All successful saves: modal closes, toast «Сохранено в кабинете школы».
Delete: confirm «Удалить эту запись из локального кабинета?». **[BUG]** Deleting never works: `const [typ,id]=el.dataset.gvDelete` destructures characters, not the `type:id` parts. The modal stays open.
**[TZ SCH-04/05/09/10]** Missing: age groups, individual/group format, max group size, free seats, session statuses and weather reschedules, real invitations with owner/manager/instructor roles, attendance and progress, and enrollment from public booking.

### 6.5 «Прокат · оборудование» (rental) — `cabinet-pane-rental*.png`, `cabinet-rental-own-form-1440.png`

Lead «Добавляйте оборудование в уже существующий каталог аренды. Запросы и доступность пока сохраняются локально.»
Stats: own listings «Моих объявлений» · **all** rental requests in the browser «Заявок на аренду» (these are the user's outgoing requests, not incoming ones **[BUG]**) · type «Доска» «Досок» · other types «Другого снаряжения».
Buttons: primary «+ Добавить оборудование» (opens the form modal), «Открыть каталог →». H3 «Мои объявления»: rows `title / {type} · {region} · {price} ₽/день`. Empty «Объявления ещё не добавлены.»

Own listing modal (`form#rentOwnForm`): kicker «Мои объявления · демо», H2 «Поделиться снаряжением», lead «Заполните карточку, и она появится в этом браузере. Не будет опубликована для других людей.»

| Label | Control |
|---|---|
| «Что сдаёте? *» | text, required, max 90, «Например, лонгборд 9′0″» |
| «Тип» | select Доска / Гидрокостюм |
| «Регион» | select (5 regions; user region preselected) |
| «Размер *» | text, required, max 15, «M / 8′0″» |
| «Цена, ₽ за день *» | number, required, 1–50000, «1200» |
| «Описание *» | textarea, required, max 250, 3 rows, «Состояние, комплект, особенности...» |
| submit | «Добавить в демокаталог →» |

On save the listing `{id:'mine_'+ts, _mine:true, …, owner: first name, town: user.region **[BUG: region used as town]**, visual: 'long'|'suit', tone:'#add7e9', img:'wave'}` is added.
`user.rent=true`, the app **navigates to the public rentals page** (leaving the cabinet), toast «Объявление добавлено в демонстрационный каталог».
**[TZ ACC-05, RENT-01..06]** Missing: photos, condition, inventory items and quantity, availability by intervals, «Свободных бордов»/«Забронировано» counters, incoming requests, issue/return/damage flow, edit/delete of listings.

---

## 7. Modals reachable from the cabinet

### 7.1 «Мои занятия» (client lesson orders, `window.readOrders`) — `cabinet-my-lessons-modal-1440.png`
Wide modal: kicker «Личный кабинет», H2 «Мои занятия», lead «Отправленные заявки и переписка с инструкторами.»,
banner «Демонстрация одного браузера: подтверждение от лица инструктора можно проверить кнопкой в заявке. В рабочей версии менять статус сможет только авторизованный инструктор.»
Then client-view order cards (§6.2.3) for **all** orders **[BUG]**. Empty: «≋ 🏄 ≋» / «Волна зовёт, а заявок ещё нет» / «Выберите инструктора и удобное время, а мы соберём всё в одном месте.» / primary «Найти инструктора →».
It opens after a booking is sent, after cancel/review, and from «Вернуться к заявкам». In the real build, put this content in the «Бронирования» pane.

Booking creation happens on the public instructor page. Its toasts are «Сначала выберите свободное время», «Записаться к самому себе нельзя. Для проверки создайте демо-заявку в кабинете.», «Это время уже недоступно — выберите другое», «У вас уже есть заявка на это время» and «Заявка отправлена в демо-режиме».
The order object it creates: `{id:'b'+ts+'_'+rnd, personId, date, slot, clientName, clientKey:handle, service:'Индивидуальное'|'Вдвоём с другом'|'Групповое', level:'Первое занятие'|'Начинающий'|'Средний'|'Продвинутый', note≤1000, status:'pending', createdAt}`.

### 7.2 «Все сообщения» (`window.openInbox`) — `cabinet-inbox-modal-1440.png`
Kicker «Общение · Гдеволна», H2 «Все сообщения», lead «Друзья GG Surfer и инструкторы, у которых подтверждены занятия.»
Rows `.inbox-item`: round ✉ avatar (43 px gradient), name (for lesson chats: the instructor's name, which for one's own instructor card is the user's own name), small «Запись {дата}» or «Знакомство GG Surfer» + « · {N} сообщений», →.
Empty: «≋» «Сообщений пока нет» / «После подтверждения записи откроется чат с инструктором.»
No unread state and no filters **[TZ MSG-01/06]**.

### 7.3 Lesson / GG chat (`window.openChat(id, perspective)`) — `cabinet-instructor-chat*.png`
Header: 49 px photo (the instructor's photo for the student; ✉ avatar for the coach), kicker «Чат по подтверждённому занятию» or «GG Surfer · знакомство», H2 name, date line `{дата} · {slot|«Время уточняется»}`.
Message box `.lesson-chat-box` (min 200 / max 310 px, scrolls to the bottom). Bubbles: others' messages left, white with a 3 px bottom-left corner. Own messages right, `#d9effa`, with a 3 px bottom-right corner.
Each bubble has a footer «Инструктор|Ученик · HH:MM».
Empty: «Здесь начинается общение» / «Поздоровайтесь и уточните детали встречи.»
Form: «Сообщение» textarea (required, max 1000, 3 rows, «Привет! Подскажите, пожалуйста...»), primary «Отправить сообщение →». Note «Это демонстрационный чат, переписка сохраняется только на этом устройстве. В реальной версии сообщения будут доставляться участникам через сервер.»
A lesson chat opens only when the order is accepted or completed. Otherwise the toast is «Чат появится после подтверждения занятия».
**[TZ BR-06, MSG-03/09, ATX-09]** The chat must exist from the first request, before acceptance.
**[TZ MSG-04/05]** No paperclip/photo attachment here (the shaper chat has one). The window should be taller.
**[BUG]** In GG chats, new messages are saved with `from:'student'` while «own» is detected by `from==='me'`, so the user's own GG messages render as the other side's.

### 7.4 Lesson review (`window.reviewOrder`)
Kicker «После занятия · отзыв ученика», H2 «Как прошла ваша встреча?», lead «{instructor} · {дата}. Ваш отзыв поможет другим сёрферам выбрать инструктора.»,
note «В прототипе отзыв будет виден только в этом браузере. В настоящей версии ссылка на отзыв появится после подтверждённого завершения урока.»
«Оценка *» select: «★★★★★ Отлично!», «★★★★☆ Хорошо», «★★★☆☆ Нормально», «★★☆☆☆ Не очень», «★☆☆☆☆ Не понравилось».
«Ваши впечатления *» textarea (max 1000, 5 rows, «Как проходил урок? Что понравилось, что можно улучшить?»).
Buttons «Вернуться к заявкам», primary «Опубликовать отзыв →».
Gate: «Оценить можно только завершённое занятие — один раз». Empty text → «Напишите несколько слов об уроке». Success → «Спасибо! Отзыв добавлен в этот браузер».
**[TZ BR-05, ATX-26]** Self-review is possible in the demo: one browser is both the client and the instructor. **[TZ AT-08]** Moderation before publication is missing.

### 7.5 Favorites modal (`showFavorites`) — `cabinet-favorites-modal-1440.png`
H2 «♡ Избранное», lead «Ваши сохранённые споты и сёрферы.». `.member` rows: 59×55 photo, name, region, «Открыть карточку →».
Empty: «Пока пусто. Нажмите на сердечко в любой карточке — и она появится здесь.» Rental favorites (`rental:<id>`) are silently skipped **[BUG]**.

### 7.6 Rental request (public catalogue → saved into the cabinet counters)
Kicker «Заявка на аренду · демо», H2 = title, «{region} · {price} за день».
«Забрать *» / «Вернуть *» (dates, min = tomorrow), «Сообщение владельцу» (max 500, «Привет! Хочу арендовать снаряжение...»).
Notice «Демо-заявка сохраняется только на вашем устройстве и не дойдёт до владельца. Оплаты и залога здесь нет.», primary «Сохранить демо-заявку →».
«Дата возврата не может быть раньше выдачи». Success «Демо-заявка сохранена в вашем браузере», then `#profile`.
The saved object: `{id:'rr'+ts, rental, title, from, to, note, client:handle, status:'sent'}`.

---

## 8. Status dictionaries (summary)

| Domain | Codes → labels | Where |
|---|---|---|
| Lesson order (lesson system) | pending «Ожидает ответа», accepted «Подтверждено», completed «Занятие завершено», declined «Отклонено», cancelled «Отменено» | `.lesson-status-pill.<code>` |
| Lesson order (cabinet bookings list) | pending «Ожидает», accepted «Подтверждено», completed «Завершено», declined «Отклонено», empty «Новое» | `.gv-ac-status` (+`.done`) |
| Legacy orders modal (unused) | pending «На рассмотрении», accepted «Принята», other «Завершена» | `.order-status` |
| Rental request | sent «Отправлена», other «В обработке» (`rentStatus`, rentals module only) | |
| School student | «Новая» → «Подтверждена» → «Завершено» → «Отменена» (cycle) | `.gv-ac-status` (+`.done` for Завершено) |
| School member access | always «Без доступа» | `.gv-ac-status.warn` |
| Calendar day | out of range / «выходной» / «{n} занято» / «занято» / «{n} окна» | `.lesson-day` classes |

TZ target status machines are in TZ §7.2 (inquiries: new/in_progress/declined/completed/cancelled) and §7.3 (bookings: requested/confirmed/declined/in_progress/completed/cancelled/no_show).

## 9. Counters and badges — where the numbers come from

| Badge | Prototype source | Real source (TZ) |
|---|---|---|
| Header favorites | `favorites.length` (`gg_favorites`) | favorites count from the API |
| Header messages / nav «Обращения» | `chats.length` (number of dialogs) | sum of **unread messages** per conversation read cursor (MSG-06/07, AT-04) |
| Lesson dash «Заявки (N)» | pending orders where `personId = mine_<handle>` | provider inbox: count of requests with status new |
| Shaper iframe badges | shaper module (see SHAPERS_SCREENS.md) | same unread service |
| Every stat tile | client-side counts over localStorage arrays | server aggregates of real events (TZ §10, MET-07/08) |

## 10. Toasts, confirms, and other system copy (verbatim)

Toasts appear centred at the bottom (`.toast`: fixed, bottom 21 px, `#044f75`, radius 12) for about 2.9 s.

| Context | Text |
|---|---|
| registration success | Добро пожаловать в «Гдеволну»! ♡ |
| registration errors | Выберите хотя бы три интереса · Укажите дату рождения · GG Surfer доступен только участникам от 18 лет · Документы: PDF/изображения, не более 10 МБ · Добавьте основной документ |
| profile | Профиль сохранён · Фото не больше 1,5 МБ · Нужен JPG, PNG или WebP |
| specialties | Направление добавлено · Направление скрыто |
| diary | Укажите дату и спот · Выход на воду сохранён · confirm: Удалить запись о катании? |
| school | Сначала создайте школу · Проверьте стоимость · Укажите число мест от 1 до 500 · Сохранено в кабинете школы · Карточка школы сохранена · confirm: Удалить эту запись из локального кабинета? |
| instructor | Заявка подтверждена — чат открыт · Заявка отклонена (демо) · Занятие завершено. Теперь ученик может оставить отзыв. · Время уже занято другой подтверждённой заявкой · Сначала откройте эту дату в расписании · Здесь уже есть подтверждённые занятия · Это время уже подтверждено ученику · Тестовая заявка создана. Можно подтвердить её. · Сначала откройте свободную дату в календаре · Карточка инструктора сохранена в браузере |
| client lessons | Заявка отправлена в демо-режиме · У вас уже есть заявка на это время · Сначала выберите свободное время · Это время уже недоступно — выберите другое · Заявка отменена. Для нового времени создайте новую заявку. · Чат появится после подтверждения занятия · Оценить можно только завершённое занятие — один раз · Напишите несколько слов об уроке · Спасибо! Отзыв добавлен в этот браузер |
| rental | Объявление добавлено в демонстрационный каталог · Дата возврата не может быть раньше выдачи · Демо-заявка сохранена в вашем браузере · Для объявления сначала нужен профиль · Сначала создайте демо-профиль |
| favorites (global) | Добавлено в избранное ♡ · Убрано из избранного |
| logout | Вы вышли из демо-профиля |

## 11. Demo-only behaviour and localStorage → replace with API

| Key | Shape | Replace with (TZ §9 sketch) |
|---|---|---|
| `gg_user` | `{name, handle, region, level, board, role, roles[], gg, rent, public, interests[], documents[] (file names), avatar (data URL), ggStatus?}` | `POST /auth/register`, `GET/PATCH /me`, `PUT /me/specialties/{code}`, avatar via media upload (signed URL), settings in `/me` |
| `gg_favorites` | `["spot:halak","person:alex","rental:r1",…]` | typed favorites `/me/favorites` (spot, school, instructor, model, shaper, equipment) |
| `gg_orders_v2` | lesson orders, see §7.1 (+`acceptedAt`, `completedAt`, `demo`) | `POST /bookings`, `/bookings/{id}/confirm|decline|complete|cancel`; client vs provider lists separated |
| `gg_chats_v2` | `{id:"lesson:<personId>:<orderId>" or "gg:<personId>:", target, type:'gg'|'lesson', orderId, messages:[{from:'me'|'student'|'coach', text, created}]}` | conversations + messages + read cursors; attachments (`media_assets`, `message_attachments`) |
| `gg_reviews_v2` | `{orderId, personId, name, rating, text}` | `POST /reviews` with moderation |
| `gg_availability_v3` | `{[personId]: {[YYYY-MM-DD]: {closed:boolean, slots:["09:00",…]}}}` | instructor availability rules/exceptions (server-validated) |
| `gg_profile_extras_v3` | `{["mine_<handle>"]: {name,town,spots,students,exp,bio}}` | instructor professional profile |
| `gg_rent_listings_premium` | own listings (`_mine:true`) | rental listings/inventory items with availability |
| `gg_rent_orders_premium` | outgoing rental requests | rental bookings |
| `gv_unified_school_<handle>` | school object (§6.4) | `POST /organizations` + programs, sessions, members/invites, enrollments |
| `gv_unified_diary_<handle>` | `[{id, date, spot, notes}]` | surfer diary entries |
| `gdevolna_shaper_demo_v1`, `gdevolna_shaper_files_v1` | shaper module state (read by the cabinet for stats only) | shaper API — see SHAPERS_SCREENS.md |

Demo-only UI that must **not** be ported:
* «+ Создать тестовую заявку» / «Добавить пример заявки →»
* «Как это видит инструктор (демо) ↗» and preview mode
* manual «Статус» cycling of students
* «Демо-регистрация» and the consent text for local storage
* every banner and note that says «демо», «локально» or «в этом браузере»
* the email/birthday/gender drop

Real auth needs login, recovery and email verification (ACC-13).

All counts, rankings and «Проведено/Завершено» numbers are computed in the client. TZ §9.1 requires the server to be the source of truth.
The demo data follow TZ §12.2: seed reviews, orders, chats, statistics and certificates are **demo** and must not become real records (see `seed_cabinet.json`, `"demo": true`).

## 12. Legacy profile panels (not rendered any more — features to keep)

These are still in the code (layers 1–3) but the unified engine hides them. Keep the features in the new cabinet where the TZ asks for them:

* **GG status** panel: kicker «GG Surfer · о чём вы готовы договориться», H3 «Чем я могу помочь на берегу», text «Этот статус виден другим участникам в вашей демонстрационной анкете.», select «Покажу споты» / «Ищу компанию» (default) / «Могу подвезти» → `user.ggStatus`, toast «Статус GG Surfer обновлён». The public GG map uses `ggStatus`, so put this select into Настройки → GG Surfer.
* **Rental** panel: kicker «Мои возможности», H3 «Сдаю снаряжение в аренду», «Статус доступен любой роли. …», toggle + «Добавить объявление →»/«Попробовать аренду →». Toasts «Аренда включена/выключена». This is now covered by Мои направления › Прокат.
* **Club mini card**: «✦ Ваш клубный след» / «{N} в избранном · {N} объявлений · {N} заявок на аренду (демо)» / «Клубная карточка →».
* **Voluntary passport verification** row («Добровольная паспортная верификация» / «В будущем — через защищённого провайдера.» / «Подробнее →»). The modal «✓ Верификация личности» explains that a partner will do the check and only a status returns. Keep it as a future Settings item.
* «Заявленные документы» row (file names + tag «Не проверены»): put it in the instructor/school verification card.
* Legacy greeting hero «Привет, {Имя}!» and the «Мои занятия и сообщения» block: superseded.

## 13. Public «Шейперы» page wrapper (`<script id="gv-full-mobile-bridge-v9">`, l.1020–1046)

This script replaces the public `shapers()` page renderer. The account engine reuses the same embedded document.
* Hero (people type, photo `hero_people` = `img/img05.webp`): H1 «Каталог шейперов», text «Мастерские, авторские модели досок и личные кабинеты шейперов — в одной ГДеволна.». It has no button.
* `section.gv-shaper-integrated` (aria-label «Каталог и кабинет шейперов»):
  * H2 «Шейперы и их доски» (23 px, `--navy`), text «Полный каталог, модели, заявки и кабинет — прямо внутри сайта.»
  * `iframe#gvShapersEmbedded.gv-shaper-frame` (title «Полный каталог и кабинет шейперов», `allow="camera; microphone; clipboard-write"`). Height `min(1100px, 100dvh − 115px)`, min 650. At ≤ 810 px it is `100dvh − 155px` (min 570, radius 12); at ≤ 370 px it is `100dvh − 145px` (min 500). Background `#f7fcff`, border 1 px `#ceeaf7`, radius 16.
  * Caption `.gv-shapers-status`: «Прокручивайте содержимое внутри окна мастерских. Верхнее меню переключает остальные разделы ГДеволна.»
* `srcdoc` is set once per render from `#gv-full-shapers-document` (JSON string, identical to `source/shapers.html`). On a parse error it shows «Раздел шейперов временно недоступен.»
* **[TZ SHP-07/ATX-02]** Because of the init described in §6.3, a guest on `#shapers` also sees the shaper cabinet/registration first, not the catalogue.
  `/shapers` must open «Все доски» for everyone.

The other script in scope, l.1049–1119, adds spot photo galleries (`img/img37–50.jpg`) to the public spot modal. It is public-site and documented in `PUBLIC_SCREENS.md`.

## 14. Visual summary

* Palette: the main-site blues. The cabinet hard-codes hex values close to the tokens (see the CSS header for the mapping).
  The lesson tokens `--lesson-*` are declared but never used.
* Corner radii: hero 22, lesson dash 20, panels 17, cards 13, inputs and buttons 10, chips 14–24, switches 30.
* Font: inherited `Trebuchet MS, Segoe UI, Arial`. Sizes: H1 23, panel H2 20, card H3 15, body 12–13, labels 11–12, kickers 10 uppercase.
* Shadows are very soft (`0 6px 26px #056e9a0b`). The page background is the site gradient. The footer landscape stays below the cabinet.
* Icons: Unicode glyphs in nav, tags, module rows and tiles (`icons-cabinet.json → glyphs`). TZ UX-04 asks for a unified SVG set.
