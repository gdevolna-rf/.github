# ГДеволна — cabinet & shapers: where the prototype differs from the TZ

When the prototype (`source/proto.html`, `source/shapers.html`) and `docs/TZ.md` disagree, **follow the TZ**.
IDs refer to TZ requirement codes. Screen-level detail is in `CABINET_SCREENS.md` and `SHAPERS_SCREENS.md`.

Global rule (TZ §2, §12.2, MSG-10, BR-10): everything in the prototype is local to one browser (localStorage / IndexedDB).
Counters, statuses, ratings and statistics are computed on the client, and many records are synthetic.
Production needs one `account.id`, server-side permissions and state, and no import of demo reviews, requests, messages, statistics or certificates.

# Part 1 — Unified cabinet (proto.html)

## A. Account, registration, navigation (TZ §16–17, §29)

| # | TZ | Prototype | Follow TZ |
|---|---|---|---|
| A1 | ACC-13, 5.3 | «Войти» opens **registration**. No login, password, recovery, email or phone verification. Email, birthday and gender are thrown away. | Real auth: email + password with verification, recovery, consents, export/delete. |
| A2 | ACC-01 | Primary role choice is Сёрфер / Инструктор / Сёрф-школа. Шейпер is only an extra checkbox. | Primary types: сёрфер / инструктор / **шейпер** / школа, plus extra-specialty checkboxes. |
| A3 | ACC-11, SCH-01, BR-03 | School is a flag on the personal account (`gv_unified_school_<handle>`). «Название школы / юрлица» from registration is not saved. | School = organization (create / join by invite), memberships with roles. |
| A4 | INS-03/05, ATX-04 | Instructor/school registration **requires** a document upload. «Квалификация» is not saved. | Instructor can register without a certificate or work document. Certificate states «не указан / загружен / проверен» with moderation. |
| A5 | ACC-02 | No «Уведомления» screen in the cabinet. | Add Notifications (feed + read state; MSG-12 preferences in Settings). |
| A6 | ACC-09 | Профиль is the 2nd nav item, Настройки the 7th. | Put Profile and Settings next to each other. Don't duplicate editors. |
| A7 | ACC-07, UX-10 | Header shows a generic person icon + «Кабинет». No avatar. | Header avatar → cabinet. Photo editable only in Profile. |
| A8 | ACC-08 | Profile form has a fixed «Сохранить профиль». No «Посмотреть на сайте». | One registration/edit form with state-dependent button text + «Посмотреть на сайте». |
| A9 | NAV-03, UX-03, ATX-22 | Phones: a scrolling text strip under the header. **No bottom tab bar**. | Bottom bar «Главная, Каталог, Избранное, Сообщения, Кабинет» with safe area. |
| A10 | NAV-05 | Pane / tab state is in memory. URL is always `#profile`. Reload resets to Обзор. | Deep-linkable routes per pane/tab (`/account/inbox`, `/account/school/programs` …). |
| A11 | 7.1, BR-11, ACC-12 | Specialty switch toggles instantly. Even the last specialty can be removed. No warning. | Server activation of `user_specialties`. Disabling warns about active bookings, offers to unpublish, keeps history. |
| A12 | ACC-06, BR-12 | GG toggle in Settings skips the 18+ check (only checked at registration). GG status select («Покажу споты / Ищу компанию / Могу подвезти») is no longer reachable. | GG Surfer = separate consent with age check. Keep the status select in Settings. |
| A13 | ACC-14 | Public and private fields are not separated. | Split public profile from private data (contacts, documents, history). |

## B. Inbox, bookings, favorites, chat (TZ §7.2–7.3, §25)

| # | TZ | Prototype | Follow TZ |
|---|---|---|---|
| B1 | MSG-01, 8.6 | «Обращения» is a hub of links + 6 latest lesson orders (raw status codes). Shaper and school inboxes live separately. | One inbox with role/organization/status filters and shared counters. |
| B2 | MSG-06/07, AT-04, ATX-10 | Badges count **dialogs** (`chats.length`), not unread messages. | Server unread aggregates per participant. Opening a dialog clears it everywhere. |
| B3 | MSG-02, ATX-27 | Bookings and «Мои занятия» show **all** orders in the browser, including incoming orders to one's own instructor card. Self-booking via the demo generator and self-review are possible. | Client sees only outgoing. Provider sees only incoming. BR-05: no request or review to oneself. |
| B4 | BR-06, MSG-03/09, ATX-09 | Lesson chat appears only **after** the instructor accepts. | Conversation created with the first request; client can write before acceptance. |
| B5 | MSG-04/05 | Lesson/GG chat: no paperclip or photos, small box (max 310 px). | Attachments with preview and remove-before-send, taller window, empty-state illustration. |
| B6 | MSG-08 | No context card (lesson, rental) inside the chat. | Context card of the linked object in the chat. |
| B7 | 7.3 | Order statuses: pending / accepted / completed / declined / cancelled. Decline has no reason. No reschedule, no in_progress or no_show. | requested → confirmed / declined (reason) → in_progress → completed; cancelled; no_show; reschedule. |
| B8 | — | Bookings pane is read-only. Cancel, chat and review are reachable only from the «Мои занятия» modal, which no cabinet button opens. | Bookings list with actions (cancel, chat, review, reschedule). |
| B9 | MSG-11, ATX-11 | Favorites list shows raw ids (`spot:halak`). Only spot and person are resolved; `rental:` items are dropped in the modal. | Typed favorites (spot, school, instructor, model, shaper, equipment) rendered as cards. |
| B10a | SHO-03, MSG-02 | Board/repair orders a client sends exist only in the shaper module («Мои исходящие заявки»). A plain client has no «Мои заявки на доски». | Common «Мои бронирования / заявки» lists lesson, rental and board/repair orders. |
| B10 | AT-08, 26 | Lesson reviews publish instantly (local). | Moderation before publication. Rating only from approved reviews. |

## C. Instructor (TZ §19, §28)

| # | TZ | Prototype | Follow TZ |
|---|---|---|---|
| C1 | INS-06/07, SCH-07, F11, ATX-15 | Availability = 3 fixed slots (09/12/15). Days off default to Mon/Thu. Per-day toggles. Window is 91 days / 3 months. No duration or recurring rules. School sessions are not merged. | Real schedule: slots/duration, recurring rules, exceptions, cancellations and reschedules, school assignments in the same calendar, server double-booking guard. |
| C2 | INS-01/02/08/12 | Own card fields: name, town, spots, experience, student level, bio. Photo is a demo photo of someone else (`p0`). | First/last name, own photo/video gallery (add, preview, delete ×), formats, prices, languages, boards, offer objects (individual/group, duration, price, spot, equipment). |
| C3 | INS-10, MET-04 | Stats: counts of local orders (twice: outer + inner rows). | Views, inquiries, conversion, unique/repeat students, completed lessons, load, cancellations, rating — one compact row (MET-02). |
| C4 | — | «Как это видит инструктор (демо)» impersonates sample instructors. «+ Создать тестовую заявку» generates fake requests. | Do not port (demo-only). |

## D. School (TZ §20)

| # | TZ | Prototype | Follow TZ |
|---|---|---|---|
| D1 | SCH-03 | Tabs: Обзор, Программы, Расписание, Ученики, Команда, Аналитика, «Страница школы». | Add **Оборудование, Обращения, Отзывы**. Name the profile tab «Профиль школы». |
| D2 | SCH-04 | Program: name, duration (free text), price, level, description. | + age categories, individual/group, max group size. |
| D3 | SCH-05/06 | Session: program, date, time, spot, capacity, coach (stored as a **name string**). No free seats, no statuses, no weather reschedule. | Sessions with instructor account id, free seats from bookings, statuses, reschedules. Manager assigns requests. |
| D4 | SCH-09, 5.3, ATX-18 | Team = plain records, always «Без доступа». Role select includes «Владелец». | Invitations to existing accounts, accept flow, roles owner/manager/instructor, revoke, audit log. |
| D5 | SCH-10/11 | Students added manually; status cycles Новая → Подтверждена → Завершено → Отменена. | Enrollments come from public booking. Attendance, progress, guardian consent for minors. |
| D6 | SCH-12, MET-05 | Analytics = counts of sessions and capacity. | Fill rate, conversion, attendance, repeat students, instructor quality (TZ 10.1 formulas). |
| D7 | SCH-13, ACC-15 | School card «не публикуется». Preview modal only. | Publication after required fields + organization check. |

## E. Rental (TZ §22)

| # | TZ | Prototype | Follow TZ |
|---|---|---|---|
| E1 | ACC-05, RENT-01/03/04 | Listing = title, type (Доска/Гидрокостюм), region, size, price/day, description. No photos, condition, quantity or availability. No edit or delete. | Inventory with photos, condition, pickup place, physical items, interval availability, «Свободных бордов / Забронировано» counters. |
| E2 | RENT-05/06 | Requests are saved locally with status `sent`. The pane counts the user's **outgoing** requests as «Заявок на аренду». No incoming requests. | Incoming requests for owners. Server overlap check. Request → confirm → issue → return/damage/overdue → close, with history. |
| E3 | — | Saving a listing navigates to the public rentals page (leaves the cabinet). `town` is set to the region. | Stay in the cabinet. Real town/pickup place. |

## F. Shaper wrapper / analytics / UX

| # | TZ | Prototype | Follow TZ |
|---|---|---|---|
| F1 | ACC-03, PL-04, SHP-07 | Shaper pane = iframe with the whole shapers document (second header, logo, nav and hero inside the cabinet). It always starts on the shaper dashboard/registration, also on the public «Шейперы» page. Its data lives in a separate localStorage. Wrapper stats are read before the iframe initialises (show 0). | Native cabinet tabs bound to `account.id`. No iframe. |
| F2 | MET-01/02/07 | Every cabinet pane opens with a 4-tile stat row of client-side counts. | Summary dashboard with a specialty filter. Compact one-line stats only in Dashboard / Statistics / Inquiries. No fictitious revenue. |
| F3 | UX-04 | Icons are Unicode glyphs (≋ ♧ ◈ ⌂ ▤ ◉ ✉ ▣ ♡ ⊕ ⚙). | Unified SVG icon set, equal stroke width, optically centred. |
| F4 | UX-13 | No loading, error, no-network or no-permission states. Only empty states. | Full state set for every screen. |
| F5 | UX-02 | Phone: the cabinet tab strip does not scroll to the active tab. Calendar captions are 6–7 px. | Readable at 320–430 px. Keep the active tab in view. |
| F6 | 12.2 | Demo data mixed with user data in localStorage. | Classify seed vs user data. Never import demo reviews, requests, messages, statistics or certificates. |

## G. Prototype bugs — do not replicate

* `data-gv-delete` handler destructures the string (`const [typ,id]=…`). Deleting school programs, sessions and members never works.
* School overview buttons «Расписание →» / «Мои программы →» use `data-gv-pane` and land on the general «Ваш обзор».
* Guest hero button «Создать профиль →» goes to the home page.
* Inbox list prints raw status codes (`pending`); bookings print `cancelled` and rental `sent` untranslated.
* Calendar caption «{n} окна» is used for every n (no Russian plural forms).
* In GG chats, own messages are saved as `from:'student'` but detected as `from==='me'`, so they render as the other side.
* Program price left empty is saved as 0. Session coach is stored by name.
* Logout keeps orders, chats, favorites and reviews; the next user inherits them.
* Diary «today» uses the UTC date (`toISOString`). It can be off by one day around midnight.
* Registration `max` date is hard-coded to `2026-10-19`.

# Part 2 — Shapers module (shapers.html)

Source: `docs/prototype/source/shapers.html` (embedded into proto.html as an iframe `srcdoc`). Screens: `docs/prototype/screens/cabinet-shapers-*.png`.

## Gaps (TZ requires, prototype lacks / does differently)

- **SHP-07 / ATX-02: the public "Шейперы" page opens the shaper cabinet, not the catalog.** The last init script runs `showPage('dashboard'); switchPanel(profile ? 'overview' : 'profile')`, so a guest on `#shapers` sees «Личный кабинет шейпера» and the registration form (`cabinet-shapers-embedded-public-1440.png`). The catalog only appears after clicking «Каталог шейперов» inside the iframe. In production `/shapers` must open the catalog (tab «Все доски») for everyone, with no prompt to become a shaper.
- **Double chrome.** The iframe has its own header (logo, a «Каталог сёрферов» link, search, heart, messages, «Личный кабинет», avatar, ⋯ menu) inside the site header. Most of its links are toast stubs. Drop it and use the site header and the bottom mobile navigation (UX-03).
- **SHP-08: the shaper card has no rating or review.** Demo shapers have no photo (they show initials), and "lead time" appears only as a text line. The sidebar «★ 4.9 (26)» is static text.
- **SHP-09: the profile button says «Профиль шейпера →», not «Перейти в профиль».** It is pinned bottom-left on desktop. Below 1030px it sits above the model carousel, not at the bottom-left of the card.
- **SHP-10: no URL or deep link for the profile modal.** There is also no history entry, so the Back button does not close it.
- **SHP-04: no repair filter.** «Ремонт досок» is only a tag on the shaper card and a chip in the profile modal; the catalog has no filter for it.
- **SHP-11 / ATX-03: the "not yourself" checks are client-side only.** They compare the workshop *name* string (`person === data.profile.workshop`) or `ownerId==='self'`. They must be server-side checks by account id, on both orders and messages.
- **SHO-06: no repair request.** Repair is only a profile toggle. There is no separate request with problem, damage photo, preliminary price, deadline and stages.
- **PAY-01: order types are only «Покупка» / «Аренда (если доступна)».** «Аренда» is effectively never enabled. There are no «индивидуальное изготовление» or «ремонт» types, although the demo requests are titled «Индивидуальный заказ». Delivery method is not asked in the order.
- **SHO-03 / MSG-02: "my orders" exist only inside the shaper cabinet.** They appear as «Мои исходящие заявки» (send icon). A plain client without the shaper specialty has nowhere to see «Мои заявки на доски». It must live in the common account (see CABINET_SCREENS).
- **MSG-09: no dialog is created with the order.** Creating an order makes no chat thread. The thread is created lazily on first «Перейти в чат» or when the request is accepted. TZ: create the dialog at the first inquiry.
- **MSG-08: no context card inside the chat.** The order chat shows only «Чат · <модель> · <имя>», a status badge and action buttons. There is no model card (photo, SKU, price).
- **MSG-06/07 and SHO-04: unread counts are stored, not computed.** Unread is a stored integer per inbox thread (`unread: 2`), not read cursors. The badges are client sums: topbar = unread + new requests + unseen outgoing. This must come from server events.
- **MSG-10: chat is local to one browser.** Writing «Написать шейперу» to another workshop stores the thread in *your own* «Чаты» list (row status «Диалог»).
- **MSG-04: the attach button shows a chain-link icon (`#i-link`), not a paperclip.** Preview and remove-before-send are implemented.
- **MSG-11: favourites are a stub.** The heart icon shows the toast «Избранное будет доступно после подключения аккаунтов»; the model ♡ counter is demo data.
- **BRD-03: no cover selection and no photo reordering.** Photo 1 is implicitly the cover. The ×-delete and the 10-photo limit work.
- **BRD-04 / UX-08: «Фотографии работ» in the profile is a horizontal strip of 77×100 thumbnails.** On mobile it is the thin vertical strip that TZ forbids. These photos are also not persisted (preview only). The board modal itself already uses the correct layout: upload zone on top, 86×86 grid below.
- **UX-09: the video tile is not a compact tile.** It is a full `<video controls>` (≤350×210) with no poster or duration. Its × is detached at the far right of the slot instead of on the tile.
- **BRD-05/06/07: SKU, ids and model structure need server rules.**
  - The SKU is built client-side as `GV-<код шейпера>-<тип>-<длина>-<ширина>-<NNN>`, with a random code `S` + 5 base36 chars stored in the profile.
  - There is no server uniqueness check and no stable UUID; the `Date.now()` id is used.
  - Model, size variant and physical unit are all one record.
  - Demo shapers have no width, so their SKUs contain `WNA`.
- **BRD-13 / RENT-03/05: statuses are a manual select.** «В наличии / Под заказ / Нет в наличии» is not linked to inventory, sales or bookings.
  - «Бронирования» is an empty state.
  - «Свободных бордов» = in-stock models − rental requests in work.
  - The side badge «1» is hard-coded.
- **SHO-07 / MET-03 / MET-07 / MET-08: statistics are not trustworthy.**
  - «Конверсия в завершение» = completed ÷ all requests. TZ: conversion = unique inquiries ÷ qualified views.
  - «Выручка» and «Средний чек» come from a sum typed into a `prompt` on «Завершить». TZ forbids showing unconfirmed money; it must come from recorded payments.
  - Views are demo values + 1 per own opening of «Фото и параметры». Self-views are counted, which MET-08 says to exclude.
  - «Отметки избранного» are fixed demo numbers.
  - Sales vs rental is shown only in the text «Продано досок: N · Арендовано: N…».
- **SHO-08 / TRUST-02: one static demo review** («Алексей», ★★★★★). There is no review model or publication policy.
- **UX-06: some selects still truncate on mobile.** The bulk-table «Тип» select shows «Л…» at 390px.
- **UX-12/13/14: states and keyboard handling are incomplete.**
  - No loading, error or no-network states.
  - The board and chat modals do not close on backdrop click; the others do.
  - Esc closes everything.
  - Focus is not trapped.
- **TZ 12.2 / MSG-10: everything lives in this browser.**
  - localStorage `gdevolna_shaper_demo_v1` and `gdevolna_shaper_files_v1`, plus IndexedDB `gdevolna_shaper_media_v2`.
  - These are shared with the parent page's origin; the account engine reads `gdevolna_shaper_demo_v1` for its own counters.
  - The demo requests, inbox, reviews, view/heart counts and the «4.9 (26)» rating must not become real records.

## Prototype bugs (do not reproduce)

1. **Saving the profile drops the SKU shaper code.** `data.profile = p` replaces the whole profile object, so `shaperCode` is lost. The next board save generates a new random code, and one workshop ends up with mixed SKU prefixes. Observed: models 1, 2, 4 = `GV-S62WI5-…`, model 3 after editing = `GV-S70EP0-…`.
2. **Adding a custom board type («+ Добавить другие типы досок…») resets unsaved tile selection.** It re-renders the tiles from the saved `profile.types`. In the run, Фиш/Ган clicks were lost.
3. **Wrong status colour in the catalog.** The «Все доски» badge uses class `made` (amber) for everything not «В наличии», so «Нет в наличии» looks like «Под заказ». In «Мои доски» it is correctly red (`none`).
4. **Pluralisation.**
   - «Доски мастерской · 1 моделей», «2 моделей» and «Модели мастерской · 2 моделей» are wrong.
   - «Найдено N моделей» never inflects.
   - Only the card KPI line inflects correctly («1 модель», «2 модели»).
5. **Transparent PNG photos get a black background.** Board photos are re-encoded to JPEG on a canvas without a white fill.
6. **Mobile contact fields are cramped.** At ≤610px the profile «Контакты и социальные сети» rows keep the inline `grid-template-columns:1fr 1fr 1.2fr` and `repeat(4,…)`, giving fields like «+7 965 28…» and «example@…». The override targets `#registration …`, but the form now lives in `#panel-profile`.
7. **Mobile chat modal: the long title runs under the × button.**
8. **Inside the embedded header, «Каталог сёрферов» opens the shaper dashboard.** No nav link ever gets the `.active` state.
9. **The profile «Фотографии работ» and «Сертификаты» uploads are not saved.** The «Перетащите файлы сюда» text promises drag-and-drop, but there is no drop handler. The «+» placeholder tile disappears after the first upload.
10. **Board modal: «Длина» and «Ширина и толщина» are `required` but have no «*».** Bulk editing type or length does not recompute the SKU until the next page load; then `initializeArticles()` silently rewrites it and keeps `legacyArticle`.
11. **The «Промо» / «▶ Промо-видео» button ignores which shaper it belongs to.** `GVShowPromo()` always plays your own promo; only the own workshop can have one in the demo.
12. **After the first registration the user stays on the «Профиль» tab.** The code comment promises the overview. On submit the user sees «Аккаунт шейпера создан» on first save and «Изменения профиля сохранены» afterwards.
13. **Orders sent to demo shapers never change status** (there is no counterpart side). An order for your *own* demo board placed before registering appears in both «Обращения» and «Мои исходящие заявки», and both update together.
14. **The carousel arrows ‹ › are never disabled at the ends.** They scroll 2 items per click.
15. **«Перейти в чат» is also rendered inside the open chat window** (in the actions row under the log).
