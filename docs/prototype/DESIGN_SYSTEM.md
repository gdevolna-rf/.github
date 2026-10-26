# ГДеволна — design system of the public site (from the HTML prototype)

Source: `docs/prototype/source/proto.html` (UI v12/v14 prototype). All CSS below is copied from the
**consolidated, cascade-resolved** stylesheet `docs/prototype/frontend-port/styles/prototype-public.css`
(validated: 0 computed-style differences vs. the original prototype on every public screen and modal at
1440 / 800 / 390 px). Class names are the prototype's; port them 1:1 into a global stylesheet or CSS
modules. Screens and copy are described in `PUBLIC_SCREENS.md`; screenshots are in
`docs/prototype/screens/public-*.png`. Inside each snippet the rules are grouped by `@media` context for
readability; when the exact cascade order matters (rare), follow `prototype-public.css`. The same selector
can appear several times in one snippet (the prototype was built in layers; declarations that were always
overridden have already been removed) — **all occurrences are needed**; merge them when you port.

TZ constraints that apply to everything here: UX-01 / PL-01 (keep the approved look: marine light-blue
palette, logo, soft cards, airy spacing — no redesign), UX-02 (320–430 px phones, 768 tablet, desktop),
UX-04 (one icon family, centred glyphs, standard heart), UX-05 (equal-height segment groups),
UX-06 (select arrow must not cover the value), UX-07 (wide toggles ≈58 px), UX-13 (states), UX-14 (WCAG 2.2 AA).

---

## 1. Design tokens

### 1.1 CSS custom properties (final values after both `:root` blocks)

| Token | Value | Used for |
|---|---|---|
| `--font` | `'Trebuchet MS','Segoe UI',Arial,sans-serif` | whole site (`body{font:15px/1.55 var(--font)}`) |
| `--sea` | `#08739e` | active nav underline, float-icon glyph, mini-stat, accents |
| `--deep` | `#005481` | `.section-title`, `.side-card h3` |
| `--navy` | `#064c73` | text of `.line-btn`/`.pill-btn`, header icon buttons, shaper head |
| `--aqua` | `#dff6ff` | hover of the white hero CTA |
| `--ice` | `#eaf8fd` | defined, not referenced by public CSS |
| `--text` | `#0c517a` | body text colour |
| `--muted` | `#5d8dac` | `.muted`, toggle-row descriptions, gallery captions |
| `--line` | `#cce9f5` | 1px borders of cards/panels |
| `--white` | `#fff` | defined, not referenced |
| `--shadow` | `0 5px 22px #2f9fc518` | soft card shadow (feature, side-card, glass, filters, mapbox, rent-card…) |
| `--lesson-ink` `--lesson-blue` `--lesson-border` `--lesson-soft` | `#09496c` `#0878a5` `#d7edf5` `#f1faff` | defined by the lesson block, **never referenced** (hard-coded hexes are used instead) |

Runtime (inline) custom properties set by markup: `--hero-photo`, `--people-photo` (hero), `--intro-photo`
(about block), `--volcano-photo` (quote), `--mountain-photo` (wide banner, club hero), `--footer-image`
(set on `<html>` by JS = footer landscape), `--rent-tint` (rental art tint per item).

```css
:root {
  --font: "Trebuchet MS", "Segoe UI", Arial, sans-serif;
  --sea: #08739e;
  --deep: #005481;
  --navy: #064c73;
  --aqua: #dff6ff;
  --ice: #eaf8fd;
  --text: #0c517a;
  --muted: #5d8dac;
  --line: #cce9f5;
  --white: #fff;
  --shadow: 0 5px 22px #2f9fc518;
  --lesson-ink: #09496c;
  --lesson-blue: #0878a5;
  --lesson-border: #d7edf5;
  --lesson-soft: #f1faff;
}
```

### 1.2 Colour palette (hex values actually used; the prototype has ~550 ad-hoc tints — consolidate into these roles)

**Brand / interactive blues**

| Role | Hex | Where |
|---|---|---|
| Primary gradient | `linear-gradient(115deg,#05648a,#0075a3)` | `.primary` buttons, `.gg-kindness` panel |
| Primary hover | `linear-gradient(115deg,#034968,#026389)` | `.primary:hover` |
| Selected / active fill | `#075c86` (intent chip), `#0a6b99` (GG mode tab), `#096f9c` (`.tab`), `#04749f` (calendar day), `#066e99` (time slot), `#087eaa` (wind choice), `#037aa6` (interest), `#06658d` (`.chip.on`), `#0a83ad` (toggle on), `#078aba` (stepper), `#086b98` (step number), `#0b80a8` (unlocked achievement) | all mean "selected" — unify to one token (suggest `#06709c`) |
| Section-title diamond | `#0797c4` | `.section-title:before` "◈" |
| Links / small CTAs | `#0875a7` (`.feature-link`), `#0578a7` (`.rating-link`), `#046891` (review peek link) | |
| Focus ring | `2px solid #078ab8`, offset 3px (button/a/select/input); others `3px solid #f18daf` | `:focus-visible` |

**Text**

| Role | Hex |
|---|---|
| Body | `#0c517a` (`--text`) |
| Headings | `#005481` section titles; `#06547b`–`#07567c` modal/rental headings; white on photos |
| Nav | `#175e85`, active/hover `#035886` |
| Secondary | `#2f84ac` (fieldline), `#337da3` (feature text), `#4d90ad` (spot summary), `#628ca3` (modal p), `#6398af` (`.note`), `#5d8dac` (`--muted`), `#65a0be` (fieldline label) |

**Surfaces**

| Role | Value |
|---|---|
| Page background | `linear-gradient(112deg,#f8fdff 0%,#eafaff 90%)` |
| Top bar | `#f9fdffef` + `backdrop-filter:blur(18px)` + `0 1px 9px #07689013` |
| Cards | `#f9fdff` (person/spot/rent), `#f6fdff` (feature), `#fbfeff` (filter), `#ffffffc9` (glass) |
| Modal | `#faffff`, border `#cdf0f8`, shadow `0 20px 80px #002e4d67`; backdrop `#003f639a` + `blur(5px)` |
| Info panels | `.notice #e8f7fc` + left border `3px #0c9ac8`; `.fact #e3f7ff`; `.lesson-form-note #f3fbff` + `3px #88cfe5` |
| Soft tags | `#e6f6fd` text `#09628b` (`.tag.soft`); chips `#f4fcff` border `#b4dbed` text `#1e7299` |
| Dark panels | live screen `#043c5c`; video placeholder `linear-gradient(125deg,#083955,#126885)`; member card `linear-gradient(125deg,#05547c,#087ba1)`; toast `#044f75` |

**Lines**: `--line #cce9f5`, `#d7f0fa` (cards), `#85ceec` (1.5px outline of `.line-btn`/`.pill-btn`), `#bfe1ee` (inputs), `#c6e7f3` (spot-edit inputs), `#e0eff6` (row separators).

**Accent pink (favourites & live)**: active heart `color #ec789c; background #fff0f5; border-color #f7d4e1` (final `!important` rule), counter badge `#f44667`, live kicker `#d14e75` + pulsing dot `#ed638b`, rose needle dot `#f86189`, picked GG pin ring `#ef628d`, header icon hover `#e46b90`.

**Status colours**: verified `#def7f1/#137762`; GG tag `#e7f2ff/#116da4`; order pending `#fff4dd/#916c23`, accepted `#e3f6ed/#218064`, completed `#e8f0ff/#3875af`, declined/cancelled `#f3edf1/#90677c`; suggestion queue `#fff5d9/#8c6e24`; hazard text `#9d6256`; danger outline button `#fff6f7/#9b6171/#f1d8d5`; review stars gold `#f1aa39`, rating stars blue `#087eab`/`#0578a7`.

### 1.3 Typography

Font stack only (no web font is loaded). Trebuchet MS exists on macOS/Windows; Android/Linux fall back
to Segoe UI → Arial. If pixel-identical rendering across platforms is required, pick a licensed web font
with similar metrics (TZ UX-16 asks for optimised web fonts) — otherwise keep the stack.

| Element | Size / weight / line-height / letter-spacing | Colour |
|---|---|---|
| `body` | 15px / 400 / 1.55 | `#0c517a` |
| `h1` (hero) | `clamp(36px,4.6vw,52px)` / 700 / 1.07 / −1.5px; ≤540px: 37px, ls −1px | white |
| `h2` | 25px / 700 / 1.18 / −0.65px; ≤540px: 22px | inherit |
| `h3` | 19px / 700 / 1.18 / −0.65px | inherit |
| `p` | line-height 1.6 | |
| `.section-title` | 23px / 900 / ls −0.65px (≤540: 22px), prefixed "◈" 23px `#0797c4` | `#005481` |
| `.pagehead h2` / `.rental-intro h2` / `.club-invite h2` | 29px / 25px / 25px | |
| `.gg-heading h2` | 36px (≤540: 30px) | |
| `.modal h2` | 27px | |
| Hero kicker `.kicker` | 12px uppercase, ls 1.6px | |
| Hero text `.hero p` | 14px / 600 / 1.42, max-width 410px (≤810: 350px; ≤540: 13px) | white |
| Nav `.navlink` | 12px / 500 (active 700); ≤1100: 11px; mobile strip 12px | `#175e85` / `#035886` |
| Buttons | `.primary` 13px/800; `.line-btn`/`.pill-btn` 13px/750; `.card-cta` 12px | |
| Eyebrow `.eyebrow` / `.lesson-kicker` / `.micro-label` | 10px uppercase, ls .12em, 800/900 | `#0384b2` (lesson-kicker), `#3b8db0` (micro-label) |
| Card title `.feature h3` / `.person-name h3` | 17px | |
| Card body | `.feature p` 13px `#337da3`; `.fieldline` 12px/1.35 `#2f84ac`; label `b` 11px/500 `#65a0be`; `.fact` 11px | |
| Tags `.tag` | 10px / 800, radius 24px, padding 4px 11px | |
| Notes `.note` / `.small` / `.micro` | 11px / 12px / 11px | |
| Footer links | 12px / 700; bottom line 10px | `#0b5d8b` / `#1c6180` |

Most used sizes (count in CSS): 12px (70), 11px (49), 10px (37), 13px (26). Weights: 800 (32×), 900 (18×), 700, 750, 850 (non-standard; browsers round to 800/900 for Trebuchet).

### 1.4 Spacing, layout, radii, shadows

* **Container `.wrap`**: `width:min(1200px,calc(100% - 64px)); margin:auto` → ≤1100px `min(1150px,calc(100% - 40px))` → ≤810px `calc(100% - 30px)` → ≤540px `calc(100% - 24px)`.
* **Sections**: `.section{margin:28px auto 39px}` (≤540: 24px auto 30px). Grids: `.grid{gap:18px}` (≤540: 13px); `.grid-3` = 3 columns → 2 (≤810) → 1 (≤540); `.grid-2` = 2 → 1 (≤810).
* **Radii**: 9px (primary buttons, inputs, footer nav), 11px (line-btn, filter, member row, interest list), 12px (cards, feature, side-card, glass, wide banner, rent-card, gallery images, spot map section), 13–14px (mapbox, member list, lesson cards/tabs), 16–18px (lesson calendar, rose-card, gg-intent), 17px (modal), 20–28px pills, 24px tags/chips, 50% circles (avatars, close, step numbers, like button).
* **Shadows**: `--shadow` (`0 5px 22px #2f9fc518`) for panels; cards `0 4px 14px #1389b21e`; primary button `0 4px 11px #007ba21c`; modal `0 20px 80px #002e4d67`; toast `0 8px 29px #04587d35`; top bar `0 1px 9px #07689013`.
* **Hover motion**: cards (`.feature`, `.person-card`, `.spot-card`, `.rent-card`) `transform:translateY(-3px)` with `transition: transform .16s`; rental illustration rotates −6° → −2° and lifts 6px. `prefers-reduced-motion` disables all of it.

### 1.5 Breakpoints (max-width unless noted)

| px | What changes |
|---|---|
| 1100 | nav gaps shrink, navlink 11px, logo 88px (later overridden to 108), GG widget sidebar 270px, rent grid 4→3, rent filterbar 4 columns + full-width reset, GG intent stacks |
| 900 (min-width) | lesson (instructor) modal widens to 910px |
| **810** | **desktop nav hidden → horizontal `.mobile-nav` strip under the header**; grid-3 → 2, grid-2 → 1, filters 2 columns (reset full width), home columns stack, GG map/list stack, map heights 430/370px, rent grid 2, rental intro stacks, member club stacks, achievements 3 columns, `.filter` becomes block with icon floated right |
| 760 | lesson modal: calendar/side, info columns, reviews → 1 column; portrait 125px |
| 640 | spot-edit modal full-width, form 1 column, wind choices 2 columns; gallery 2 columns 88px |
| 600 | rental cards compact (art 158px), sorting full width, GG schematic map 310px, achievements 2 columns, roadmap 1 column |
| **540** | **phone**: wrap −24px, h1 37px, header 59px, logo 90×52, grid-3 → 1, hero 250px, person photo 218px, footer stacks, formgrid 1 column, role list 2+1, modal padding 21px |
| 480 | lesson modal portrait full-width 195px, calendar compact |
| 380 | rent grid 1 column |
| 370 / 340 | filter selects 10px, filter icons hidden at 340 |

---

## 2. Base elements

```css
* {
  box-sizing: border-box;
}
html {
  scroll-behavior: smooth;
}
body {
  margin: 0;
  font: 15px/1.55 var(--font);
  color: var(--text);
}
h1,
h2,
h3,
p {
  margin-top: 0;
}
h1,
h2,
h3 {
  line-height: 1.18;
  letter-spacing: -0.65px;
}
h1 {
  font-size: clamp(36px, 4.6vw, 52px);
  line-height: 1.07;
  letter-spacing: -1.5px;
}
h2 {
  font-size: 25px;
}
h3 {
  font-size: 19px;
}
p {
  line-height: 1.6;
}
button,
input,
select,
textarea {
  font: inherit;
}
button {
  cursor: pointer;
}
a {
  text-decoration: none;
  color: inherit;
}
.wrap {
  width: min(1200px, calc(100% - 64px));
  margin: auto;
}
.hidden {
  display: none !important;
}
.muted {
  color: var(--muted);
}
.small {
  font-size: 12px;
}
.micro {
  font-size: 11px;
}
.bold {
  font-weight: 800;
}
.accent {
  color: #078db6;
}
.note {
  font-size: 11px;
  color: #6398af;
}
.separ {
  height: 1px;
  background: #d9edf4;
  margin: 22px 0;
}
.spacer {
  height: 15px;
}
.only-desktop {
  display: inline;
}
:focus-visible {
  outline: 3px solid #f18daf;
  outline-offset: 3px;
}
body {
  font-size: 15px;
  background: linear-gradient(112deg, #f8fdff 0%, #eafaff 90%);
}
button:focus-visible,
a:focus-visible,
select:focus-visible,
input:focus-visible {
  outline: 2px solid #078ab8;
  outline-offset: 3px;
}
html,
body {
  max-width: 100%;
}
body,
#app,
.topbar,
.footer {
  min-width: 0;
}
#app > .wrap,
.section,
.hero,
.filters,
.grid,
.gg-widget,
.rent-grid,
.account-sections {
  min-width: 0;
}
#app img,
#app video {
  max-width: 100%;
}
@media (max-width: 1100px) {
  .wrap {
      width: min(1150px, calc(100% - 40px));
  }
}
@media (max-width: 810px) {
  .wrap {
      width: calc(100% - 30px);
  }
  #app h1,
    #app h2,
    #app h3,
    #app p,
    #app .spot-summary {
      overflow-wrap: anywhere;
  }
}
@media (max-width: 540px) {
  h1 {
      font-size: 37px;
  }
  h2 {
      font-size: 22px;
  }
  .only-desktop {
      display: none;
  }
  .wrap {
      width: calc(100% - 24px);
  }
}
@media (prefers-reduced-motion: reduce) {
  html {
      scroll-behavior: auto;
  }
}
```

Reduced-motion & `:where()` safety rules (keep them — they prevent card overflow on phones):

```css
.line-btn,
.pill-btn {
  border: 1.5px solid #85ceec;
  background: #fff9;
  color: var(--navy);
  border-radius: 11px;
  padding: 9px 17px;
  font-weight: 750;
  font-size: 13px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  justify-content: center;
}
.pill-btn {
  border-radius: 28px;
}
.primary {
  border: 0;
  color: #fff;
  font-size: 13px;
  font-weight: 800;
  display: inline-flex;
  gap: 10px;
  align-items: center;
  justify-content: center;
  padding: 12px 20px;
}
.hero {
  position: relative;
  background:
    linear-gradient(90deg, #00406fd6 0%, #00517b9d 31%, #00507500 83%),
    var(--hero-photo) center 43% / cover no-repeat;
  display: flex;
  align-items: center;
  color: white;
  overflow: hidden;
}
.grid {
  display: grid;
}
.grid-3 {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.grid-2 {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.feature {
  background: #f6fdff;
  border: 1px solid var(--line);
  overflow: hidden;
  transition: transform 0.16s;
}
.filters {
  display: grid;
  grid-template-columns: repeat(4, 1fr) auto;
  gap: 13px;
  margin: 22px 0 24px;
}
.person-card,
.spot-card {
  background: #f9fdff;
  border: 1px solid #d7f0fa;
  overflow: hidden;
  transition: transform 0.16s;
}
.gg-widget {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 325px;
  gap: 17px;
  min-height: 510px;
  margin: 20px 0;
}
.board-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 13px;
}
.account-sections {
  display: grid;
  grid-template-columns: 1.3fr 0.7fr;
  gap: 20px;
}
.spots-overview-map {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(250px, 0.75fr);
  gap: 16px;
  min-height: 390px;
}
.rent-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-top: 17px;
}
.rent-illustration {
  height: 94%;
  position: relative;
  filter: drop-shadow(9px 14px 10px #214e6133);
  transform: rotate(-6deg);
  transition: transform 0.35s;
}
.hero,
.hero.tall {
  min-height: 275px;
}
.section {
  margin: 28px auto 39px;
}
.grid {
  gap: 18px;
}
.primary {
  border-radius: 9px;
  background: linear-gradient(115deg, #05648a, #0075a3);
  box-shadow: 0 4px 11px #007ba21c;
}
.feature,
.person-card,
.spot-card {
  border-radius: 12px;
  box-shadow: 0 4px 14px #1389b21e;
}
.rent-grid {
  gap: 18px;
}
:where(
    .feature,
    .person-card,
    .spot-card,
    .rent-card,
    .achievement,
    .safe-strip,
    .member-card
  ) {
  min-width: 0;
}
:where(.rent-card, .feature, .person-card, .spot-card) img {
  max-width: 100%;
}
:where(.rent-card-body h3, .rent-card-body p, .club-invite p) {
  overflow-wrap: anywhere;
}
#app > .wrap,
.section,
.hero,
.filters,
.grid,
.gg-widget,
.rent-grid,
.account-sections {
  min-width: 0;
}
@media (max-width: 1100px) {
  .gg-widget {
      grid-template-columns: minmax(0, 1fr) 270px;
  }
  .rent-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 810px) {
  .hero {
      min-height: 260px;
  }
  .grid-3 {
      grid-template-columns: repeat(2, 1fr);
  }
  .grid-2 {
      grid-template-columns: 1fr;
  }
  .gg-widget {
      grid-template-columns: 1fr;
  }
  .board-grid {
      grid-template-columns: repeat(3, 1fr);
  }
  .account-sections {
      grid-template-columns: 1fr;
  }
  .spots-overview-map {
      grid-template-columns: 1fr;
  }
  .rent-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .filters {
      grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
      gap: 9px;
  }
  .grid,
    .grid-2,
    .grid-3,
    .board-grid,
    .gg-widget,
    .rent-grid,
    .spots-overview-map {
      min-width: 0;
  }
  #app .spot-card,
    #app .person-card,
    #app .rent-card {
      min-width: 0;
  }
  #app .spot-body,
    #app .person-body,
    #app .rent-body {
      min-width: 0;
  }
}
@media (max-width: 540px) {
  .grid-3 {
      grid-template-columns: 1fr;
  }
  .filters {
      gap: 8px;
  }
  .gg-widget {
      gap: 10px;
  }
  .board-grid {
      grid-template-columns: repeat(2, 1fr);
  }
  .hero,
    .hero.tall {
      min-height: 250px;
  }
  .section {
      margin: 24px auto 30px;
  }
  .grid {
      gap: 13px;
  }
  .rent-grid {
      gap: 12px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .primary,
    .pill-btn,
    .feature,
    .person-card,
    .spot-card,
    .rent-card,
    .rent-illustration {
      transition: none !important;
  }
  .feature:hover img,
    .person-card:hover img,
    .spot-card:hover img {
      transform: none;
  }
  .feature,
    .person-card,
    .spot-card,
    .rent-card {
      transition: none !important;
      transform: none !important;
  }
}
@media (max-width: 600px) {
  .rent-grid {
      gap: 10px;
  }
}
@media (max-width: 380px) {
  .rent-grid {
      grid-template-columns: 1fr;
  }
}
@media (max-width: 370px) {
  .filters {
      gap: 7px;
  }
}
```

---

## 3. Components

### 3.1 Top bar, logo, desktop nav, toolbar, mobile nav

Structure: `.topbar(sticky, z 30) > .wrap.header > a.logo + nav.mainnav#nav (button.navlink[data-go]…) + .navtools (3× button.square-btn + button.line-btn)`, then `.wrap.mobile-nav` (hidden >810px).
Counters: `span.count#favoritesCount` (hidden when 0) and `span.count#inboxCount` (only logged-in with chats) — 15×15 red circle, top-right of the icon.
Active page: `.navlink.active` (2px bottom border `--sea`, bold). Logo 108×61 → 103×59 (≤810) → 90×52 (≤540).
TZ NAV-03 / UX-03 require a **bottom** mobile tab bar (Главная, Каталог, Избранное, Сообщения, Кабинет) — the prototype only has the scrolling strip; build the bottom bar but reuse `.navlink` styling.
Screens: `public-component-header-1440.png`, `public-home-390-viewport.png`.

```css
.topbar {
  position: sticky;
  top: 0;
  z-index: 30;
  background: #f9fdffef;
  backdrop-filter: blur(18px);
  box-shadow: 0 1px 9px #07689013;
}
.header {
  display: flex;
  align-items: center;
}
.logo {
  display: flex;
  align-items: center;
  flex: none;
  margin-right: 7px;
}
.mainnav {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
}
.navlink {
  padding: 23px 0 20px;
  background: none;
  border: 0;
  color: #175e85;
  white-space: nowrap;
  border-bottom: 2px solid transparent;
}
.navtools {
  display: flex;
  align-items: center;
  white-space: nowrap;
}
.square-btn {
  position: relative;
  border: 0;
  background: transparent;
  color: var(--navy);
  padding: 7px;
  display: grid;
  place-items: center;
}
.square-btn svg,
.navtools svg {
  width: 21px;
  height: 21px;
  stroke: currentColor;
}
.count {
  position: absolute;
  top: 0;
  right: 0;
  min-width: 15px;
  height: 15px;
  line-height: 15px;
  font: 10px Arial;
  border-radius: 50%;
  color: white;
  background: #f44667;
}
.mobile-nav {
  display: none;
}
.logo img {
  width: 116px;
  height: 62px;
  object-fit: contain;
  object-position: center;
  display: block;
  filter: drop-shadow(0 1px 0 #effaff);
}
.logo {
  overflow: visible;
  min-width: 116px;
  justify-content: center;
}
.square-btn:hover {
  color: #e46b90;
}
.navtools .line-btn svg {
  flex: none;
}
.header {
  gap: 18px;
  min-height: 72px;
}
.header .logo,
.footer .logo {
  flex: none;
  min-width: 110px;
  padding: 0;
  overflow: visible;
}
.header .logo img {
  width: 108px;
  height: 61px;
  max-width: 100%;
  border: 0;
  border-radius: 0;
  object-fit: contain;
  filter: none;
}
.mainnav {
  gap: clamp(10px, 1.2vw, 18px);
}
.navlink {
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0;
}
.navlink:hover,
.navlink.active {
  font-weight: 700;
  color: #035886;
  border-color: var(--sea);
}
.navtools {
  gap: 10px;
}
body,
#app,
.topbar,
.footer {
  min-width: 0;
}
@media (max-width: 1100px) {
  .logo img {
      width: 88px;
  }
  .header {
      gap: 13px;
  }
  .navtools {
      gap: 8px;
  }
  .mainnav {
      gap: 12px;
  }
  .navlink {
      font-size: 11px;
  }
}
@media (max-width: 810px) {
  .mobile-nav {
      padding: 0 0 7px;
  }
  .navtools {
      gap: 4px;
  }
  .header {
      min-height: 61px;
  }
  .navtools .line-btn {
      padding: 8px 10px;
  }
  .logo img {
      width: 103px;
      height: 59px;
  }
  .logo {
      min-width: 103px;
  }
  .header {
      justify-content: space-between;
      gap: 12px;
  }
  .mainnav {
      display: none;
  }
  .header .logo {
      min-width: 103px;
  }
  .header .logo img {
      width: 103px;
      height: 59px;
  }
  .mobile-nav {
      display: flex;
      gap: 7px;
      overflow-x: auto;
      scrollbar-width: none;
      white-space: nowrap;
  }
  .mobile-nav .navlink {
      font-size: 12px;
      padding: 5px 9px 8px;
  }
}
@media (max-width: 540px) {
  .logo img {
      width: 88px;
      height: 50px;
  }
  .navtools .square-btn {
      padding: 6px;
  }
  .navtools .line-btn {
      font-size: 12px;
  }
  .header {
      min-height: 59px;
      gap: 8px;
  }
  .header .logo {
      min-width: 90px;
  }
  .header .logo img {
      width: 90px;
      height: 52px;
  }
  .navtools {
      gap: 2px;
  }
}
```

### 3.2 Buttons

| Variant | Class | Look | Typical label |
|---|---|---|---|
| Primary | `.primary` | gradient `#05648a→#0075a3`, white 13px/800, radius 9px, padding 12×20, shadow; disabled opacity .5 | «Найти свою волну →» (white variant inside hero), «Подробнее о споте →» |
| Primary on photo | `.hero .primary` | white background, text `#065a85`; hover `#dff6ff` | hero CTA |
| Line | `.line-btn` | white 60% bg, 1.5px `#85ceec` border, radius 11px, 13px/750 navy | header «Войти» |
| Pill | `.pill-btn` | same as line-btn, radius 28px | «Узнать о проекте →», «Сбросить», «♡ В избранное» |
| Card CTA | `.primary.card-cta` | full width, 12px, padding 10px | «▦ Профиль, отзывы и запись ❯» |
| Text link | `.feature-link` | 12px/800 `#0875a7`, no border | «Перейти →» |
| Danger outline | `.lesson-outline-danger` | `#fff6f7` bg, `#f1d8d5` border, `#9b6171` text | «Отменить заявку», «Отклонить» |
| Square icon | `.square-btn` | transparent, 21px stroke icon, hover pink `#e46b90` | header search/favourites/inbox |
| Close | `.close` | 33×33 circle `#e4f4fa`, "×" 24px `#085778`, absolute 12px/15px | every modal |

Arrows are text glyphs (`→`, `❯`, `↗`, `←`) inside the label; `.arrow{font-size:18px}` for the hero CTA.

```css
.line-btn,
.pill-btn {
  border: 1.5px solid #85ceec;
  background: #fff9;
  color: var(--navy);
  border-radius: 11px;
  padding: 9px 17px;
  font-weight: 750;
  font-size: 13px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  justify-content: center;
}
.pill-btn {
  border-radius: 28px;
}
.line-btn:hover,
.pill-btn:hover {
  background: #e5f9ff;
}
.primary {
  border: 0;
  color: #fff;
  font-size: 13px;
  font-weight: 800;
  display: inline-flex;
  gap: 10px;
  align-items: center;
  justify-content: center;
  padding: 12px 20px;
}
.primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.primary svg,
.line-btn svg,
.pill-btn svg {
  width: 16px;
  height: 16px;
  stroke: currentColor;
}
.arrow {
  font-size: 18px;
}
.hero .primary {
  background: #fff;
  color: #065a85;
}
.hero .primary:hover {
  background: #dff6ff;
}
.feature-link {
  font-size: 12px;
  color: #0875a7;
  font-weight: 800;
  border: 0;
  background: transparent;
  padding: 0;
}
.card-cta {
  width: 100%;
  font-size: 12px;
  padding: 10px;
}
.close {
  position: absolute;
  right: 15px;
  top: 12px;
  border: 0;
  background: #e4f4fa;
  color: #085778;
  width: 33px;
  height: 33px;
  border-radius: 50%;
  font-size: 24px;
  line-height: 25px;
}
.view-tools {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin: 13px 0;
}
.lesson-outline-danger {
  border: 1px solid #f1d8d5;
  color: #9b6171;
  background: #fff6f7;
  padding: 9px 12px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 800;
}
.btn-icon-card {
  width: 21px;
  height: 21px;
}
.story-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}
.story-actions button {
  white-space: nowrap;
}
.primary {
  border-radius: 9px;
  background: linear-gradient(115deg, #05648a, #0075a3);
  box-shadow: 0 4px 11px #007ba21c;
}
.primary:hover {
  background: linear-gradient(115deg, #034968, #026389);
}
@media (prefers-reduced-motion: reduce) {
  .primary,
    .pill-btn,
    .feature,
    .person-card,
    .spot-card,
    .rent-card,
    .rent-illustration {
      transition: none !important;
  }
}
@media (max-width: 810px) {
  .story-actions {
      width: 100%;
  }
}
```

### 3.3 Hero

`section.hero[.tall][.people] > .wrap > .kicker «Люди · волны · Россия» + h1 + p + [button.primary]`. Two photo variants:
`.hero` (home/GG) uses `--hero-photo` = `assets/ui/hero-home.webp`; `.hero.people` (instructors, spots, rentals, shapers) uses `--people-photo` = `assets/ui/hero-catalog.webp`. Left-to-right dark-blue gradient overlay keeps text readable; 32px bottom fade (`:after`). Min-height 275px (≤540: 250px).

```css
.hero {
  position: relative;
  background:
    linear-gradient(90deg, #00406fd6 0%, #00517b9d 31%, #00507500 83%),
    var(--hero-photo) center 43% / cover no-repeat;
  display: flex;
  align-items: center;
  color: white;
  overflow: hidden;
}
.hero.people {
  background-image: linear-gradient(
      90deg,
      #003d63d9 0%,
      #064e79ba 30%,
      transparent 77%
    ),
    var(--people-photo);
}
.hero:after {
  content: "";
  position: absolute;
  inset: auto 0 0;
  height: 32px;
  background: linear-gradient(transparent, #003a5921);
  pointer-events: none;
}
.hero .wrap {
  position: relative;
  z-index: 1;
  padding: 24px 0;
}
.kicker {
  text-transform: uppercase;
  letter-spacing: 1.6px;
  font-size: 12px;
  margin-bottom: 9px;
}
.hero p {
  max-width: 410px;
  font-weight: 600;
  margin: 7px 0 15px;
}
.hero,
.hero.tall {
  min-height: 275px;
}
.hero h1 {
  letter-spacing: -1.5px;
}
.hero p {
  font-size: 14px;
  line-height: 1.42;
}
#app > .wrap,
.section,
.hero,
.filters,
.grid,
.gg-widget,
.rent-grid,
.account-sections {
  min-width: 0;
}
@media (max-width: 810px) {
  .hero {
      min-height: 260px;
  }
  .hero p {
      max-width: 350px;
  }
}
@media (max-width: 540px) {
  .hero p {
      font-size: 13px;
  }
  .hero,
    .hero.tall {
      min-height: 250px;
  }
  .hero .wrap {
      padding: 24px 0;
  }
  .hero h1 {
      letter-spacing: -1px;
  }
}
```

### 3.4 Section headings, eyebrows, page head

```css
.section-title {
  font-weight: 900;
  margin: 2px 0 16px;
  color: var(--deep);
  display: flex;
  align-items: center;
  gap: 12px;
}
.section-title:before {
  content: "◈";
  display: inline-grid;
  place-items: center;
  color: #0797c4;
  font-size: 23px;
}
.pagehead {
  margin: 29px 0 19px;
}
.pagehead h2 {
  font-size: 29px;
  margin: 0 0 8px;
}
.pagehead p {
  color: #4987a3;
  font-size: 14px;
  max-width: 680px;
}
.gg-heading {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 25px;
  align-items: center;
}
.gg-heading .eyebrow {
  font-size: 12px;
  color: #078cba;
  text-transform: uppercase;
  letter-spacing: 1.2px;
  font-weight: 900;
}
.gg-heading h2 {
  font-size: 36px;
  margin: 8px 0;
}
.gg-heading p {
  max-width: 690px;
}
.mini-stat {
  background: #e7f7fd;
  border-radius: 11px;
  padding: 14px 19px;
  display: flex;
  gap: 15px;
  align-items: center;
  color: var(--sea);
}
.mini-stat strong {
  font-size: 21px;
  display: block;
}
.mini-stat span {
  font-size: 12px;
}
.lesson-kicker {
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-size: 10px;
  font-weight: 900;
  color: #0384b2;
}
.micro-label {
  font-size: 10px;
  letter-spacing: 0.07em;
  font-weight: 900;
  color: #3b8db0;
}
.eyebrow {
  font-size: 10px !important;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-weight: 800;
}
.catalog-meta {
  font-size: 12px;
  color: #53819c;
}
.catalog-help {
  color: #31718f;
  font-size: 12px;
}
.catalog-outro {
  text-align: center;
  padding: 27px 0;
}
.section-title {
  letter-spacing: -0.65px;
  font-size: 23px;
}
.eyebrow {
  font-size: 10px;
}
@media (max-width: 540px) {
  .gg-heading {
      grid-template-columns: 1fr;
  }
  .gg-heading h2 {
      font-size: 30px;
  }
  .gg-heading .primary {
      width: 100%;
  }
  .section-title {
      font-size: 22px;
  }
}
```

### 3.5 Home blocks (about, how-to steps, live panel, feature card, quote, wide banner, glass)

Feature card = `article.feature > .feature-image(img + span.float-icon glyph) + .feature-body(h3, p, button.feature-link)`.
Image area 150px cover; the round 48px icon overlaps the image bottom-left (−16px). Wide banner = rounded photo strip with gradient and white text (`--mountain-photo`), used at the bottom of home/spots/GG/rentals and in the club page.

```css
.feature {
  background: #f6fdff;
  border: 1px solid var(--line);
  overflow: hidden;
  transition: transform 0.16s;
}
.feature-image {
  height: 150px;
  position: relative;
  overflow: hidden;
}
.feature-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.feature h3 {
  font-size: 17px;
  margin: 0 0 7px;
}
.feature p {
  font-size: 13px;
  color: #337da3;
  margin: 0 0 13px;
  min-height: 40px;
}
.float-icon {
  position: absolute;
  bottom: -16px;
  left: 15px;
  border: 5px solid #f6fdff;
  border-radius: 50%;
  width: 48px;
  height: 48px;
  background: #fff;
  display: grid;
  place-items: center;
  color: var(--sea);
  font-size: 21px;
}
.home-columns {
  display: grid;
  grid-template-columns: 2.25fr 0.95fr;
  gap: 22px;
}
.about-hero {
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--line);
  box-shadow: var(--shadow);
  background:
    linear-gradient(90deg, #f1fbff 0%, #f1fbff 46%, #f1fbff1a 73%),
    var(--intro-photo) right/59% 100% no-repeat;
  min-height: 272px;
  padding: 25px 24px;
}
.about-hero p {
  width: 55%;
  font-size: 13px;
  line-height: 1.65;
  margin: 0 0 13px;
}
.about-hero .line-btn {
  margin-top: 9px;
}
.side-card {
  border-radius: 12px;
  border: 1px solid var(--line);
  background: linear-gradient(145deg, #e5f6fd, #f6fdff);
  padding: 20px 19px;
  box-shadow: var(--shadow);
}
.side-card h3 {
  color: var(--deep);
}
.step {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  font-size: 13px;
  margin: 14px 0;
}
.step i {
  width: 25px;
  height: 25px;
  flex: none;
  border-radius: 50%;
  background: #086b98;
  color: #fff;
  display: grid;
  place-items: center;
  font-style: normal;
  font-weight: 900;
  font-size: 12px;
}
.quote {
  height: 160px;
  color: white;
  background:
    linear-gradient(#00365350, #00365385),
    var(--volcano-photo) center/cover;
  border-radius: 10px;
  display: flex;
  align-items: end;
  padding: 18px;
  font-size: 16px;
  font-style: italic;
  font-weight: 750;
}
.wide-banner {
  min-height: 171px;
  border-radius: 12px;
  overflow: hidden;
  background:
    linear-gradient(90deg, #073f60d9 0%, #06537767 47%, #06537720),
    var(--mountain-photo) center/cover;
  padding: 24px 25px;
  color: white;
  display: flex;
  align-items: center;
  margin-top: 22px;
}
.wide-banner p {
  font-size: 14px;
  max-width: 405px;
}
.glass {
  border: 1px solid var(--line);
  background: #ffffffc9;
  box-shadow: var(--shadow);
  border-radius: 12px;
}
.is-live {
  color: #fff;
  background: #db6b7a;
  font-size: 10px;
  padding: 3px 7px;
  border-radius: 9px;
}
.video-play,
.play-icon {
  height: 62px;
  width: 62px;
  background: #ffffff26;
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: white;
  font-size: 25px;
  flex: none;
  border: 1px solid #ffffff6c;
}
.live-panel {
  display: grid;
  grid-template-columns: 0.95fr 1.05fr;
  gap: 20px;
  background: linear-gradient(110deg, #e5f7fe, #fcfeff);
  border: 1px solid #caeaf7;
  border-radius: 14px;
  padding: 20px;
  box-shadow: var(--shadow);
}
.live-panel-copy {
  padding: 12px;
}
.live-panel-copy h2 {
  font-size: 23px;
  margin: 10px 0;
}
.live-panel-copy p {
  font-size: 13px;
  color: #4d89a7;
}
.live-kicker {
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 1px;
  color: #d14e75;
}
.live-dot {
  display: inline-block;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #ed638b;
  margin-right: 5px;
  animation: pulseLive 1.5s infinite;
}
.live-screen {
  min-height: 242px;
  background: #043c5c;
  border-radius: 11px;
  overflow: hidden;
}
.live-screen iframe {
  width: 100%;
  height: 100%;
  border: 0;
  display: block;
}
.live-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 13px;
  background:
    linear-gradient(135deg, #032f4e9a, #073c5c80),
    url(var(--ignored)) center;
  color: #fff;
  text-align: center;
  padding: 16px;
}
.live-empty small {
  color: #9ed3eb;
}
.feature,
.person-card,
.spot-card {
  border-radius: 12px;
  box-shadow: 0 4px 14px #1389b21e;
}
.feature:hover,
.person-card:hover,
.spot-card:hover,
.rent-card:hover {
  transform: translateY(-3px);
}
.feature-body {
  padding: 16px 18px 18px;
}
@media (max-width: 810px) {
  .home-columns {
      grid-template-columns: 1fr;
  }
  .about-hero {
      min-height: 260px;
  }
  .live-panel {
      grid-template-columns: 1fr;
  }
  .live-screen {
      height: 230px;
  }
}
@media (max-width: 540px) {
  .about-hero {
      background:
        linear-gradient(90deg, #f2fbffdf, #f2fbffc7),
        var(--intro-photo) center/cover;
      min-height: 300px;
  }
  .about-hero p {
      width: 100%;
  }
}
@media (prefers-reduced-motion: reduce) {
  .smoke-smile,
    .surfer-svg,
    .surfwave,
    .live-dot {
      animation: none !important;
  }
  .primary,
    .pill-btn,
    .feature,
    .person-card,
    .spot-card,
    .rent-card,
    .rent-illustration {
      transition: none !important;
  }
  .feature,
    .person-card,
    .spot-card,
    .rent-card {
      transition: none !important;
      transform: none !important;
  }
}
```
```css
@keyframes pulseLive {
  50% {
    opacity: 0.3;
    transform: scale(0.85);
  }
}
```

### 3.6 Filters, selects (UX-06), sorting

Instructor filters: `.filters` grid `repeat(4,1fr) auto` (4 filter tiles + «⟳ Сбросить» primary); each tile `.filter > span.sym(icon) + label(text + select)`; the select is borderless with a top hairline.
**UX-06**: every `select` inside `#app` and `.modal` gets `appearance:none`, a single thin chevron (`select-chevron` in icons.json) at `right 10px center`, size 11×8 and `padding-right:30px` reserved so the value («Все регионы», «Любой уровень») is never covered; text overflows with ellipsis. Inside `.filter` on ≤810px the chevron moves to `right 3px` (10×7) with 24px reserve, ≤370px 18px reserve.
Other filter bars: `.gg-filters` (flex: search input + 2 selects + 2 pills), `.rent-filterbar` (grid `1.1fr .95fr 1fr 1fr auto`, labels above selects), `.sorting` (label + select). Inputs share one look: border `#bfe1ee`, radius 9px, padding 11×12, focus `#0c9ac4` + 3px halo.

```css
.filters {
  display: grid;
  grid-template-columns: repeat(4, 1fr) auto;
  gap: 13px;
  margin: 22px 0 24px;
}
.filter {
  padding: 8px 14px 9px;
  background: #fbfeff;
  border: 1px solid var(--line);
  border-radius: 11px;
  box-shadow: var(--shadow);
  color: #07588b;
  display: flex;
  align-items: flex-start;
  gap: 10px;
}
.filter label {
  flex: 1;
  min-width: 0;
  font-size: 11px;
  font-weight: 900;
}
.filter select {
  display: block;
  width: 100%;
  appearance: auto;
  font-size: 12px;
  margin-top: 5px;
  padding: 6px 0 1px;
  background: transparent;
  color: #2479a2;
  border: none;
  border-top: 1px solid #d4ecf6;
  outline: none;
}
.filter .sym {
  font-size: 20px;
}
.filters > .primary {
  align-self: stretch;
}
.gg-filters {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  margin: 14px 0;
}
.gg-filters select,
.gg-filters input,
.field input,
.field select,
.field textarea {
  border: 1px solid #bfe1ee;
  background: #fff;
  color: #1a668b;
  border-radius: 9px;
  padding: 11px 12px;
  outline: none;
  min-width: 0;
}
.gg-filters select {
  max-width: 220px;
}
.gg-filters input {
  flex: 1;
  min-width: 170px;
}
.gg-filters select:focus,
.field input:focus,
.field select:focus,
.field textarea:focus {
  border-color: #0c9ac4;
  box-shadow: 0 0 0 3px #0c9ac422;
}
.filter .sym {
  display: grid;
  place-items: center;
  min-width: 26px;
  color: #0874a1;
}
.filter .sym svg {
  width: 23px;
  height: 23px;
}
.listing-top {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: center;
  margin: 3px 0 17px;
}
.listing-top > div {
  display: grid;
  gap: 6px;
}
.sorting {
  display: flex;
  gap: 11px;
  align-items: center;
  white-space: nowrap;
  color: #527c92;
  font-size: 12px;
  font-weight: 800;
}
.sorting select {
  padding: 10px 12px;
  border: 1px solid #cce7f1;
  border-radius: 12px;
  color: #064f77;
  background: #fff;
  max-width: 200px;
}
.rent-filterbar {
  display: grid;
  grid-template-columns: 1.1fr 0.95fr 1fr 1fr auto;
  align-items: end;
  padding: 14px;
  margin: 17px 0 13px;
}
.rent-filterbar label {
  display: grid;
  gap: 6px;
  font-size: 11px;
  font-weight: 850;
  color: #126185;
}
.rent-filterbar select {
  min-width: 0;
  width: 100%;
  background: white;
  border: 1px solid #cfebf5;
  border-radius: 11px;
  padding: 11px 10px;
  color: #245b7a;
  font-size: 12px;
}
.rent-filterbar .pill-btn {
  min-height: 42px;
}
.rent-card,
.rose-card,
.achievement,
.rent-filterbar,
.gg-intent,
.gg-kindness {
  border-radius: 12px;
  box-shadow: var(--shadow);
}
.rent-filterbar,
.gg-intent {
  background: #effaff;
  border: 1px solid var(--line);
}
.rent-filterbar {
  gap: 12px;
}
#app > .wrap,
.section,
.hero,
.filters,
.grid,
.gg-widget,
.rent-grid,
.account-sections {
  min-width: 0;
}
#app select,
.modal select {
  box-sizing: border-box;
  min-width: 0;
  max-width: 100%;
  -webkit-appearance: none !important;
  appearance: none !important;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath fill='none' stroke='%232b7b9e' stroke-width='1.6' stroke-linecap='round' stroke-linejoin='round' d='m1 1 5 5 5-5'/%3E%3C/svg%3E") !important;
  background-repeat: no-repeat !important;
  background-position: right 10px center !important;
  background-size: 11px 8px !important;
  padding-right: 30px !important;
  text-overflow: ellipsis;
  overflow: hidden;
}
#app .filter select {
  max-width: none;
  width: 100%;
  font-size: 12px;
  line-height: 1.3;
  padding-top: 7px;
  padding-bottom: 5px;
  padding-left: 0;
  background-color: transparent !important;
}
#app .filter,
#app .filter label {
  min-width: 0;
}
#app .filters {
  min-width: 0;
}
@media (max-width: 540px) {
  .filters {
      gap: 8px;
  }
  .filter {
      padding: 6px 10px;
  }
  .filters > .primary {
      grid-column: 1/-1;
  }
}
@media (max-width: 1100px) {
  .rent-filterbar {
      grid-template-columns: repeat(4, minmax(0, 1fr));
  }
  .rent-filterbar .pill-btn {
      grid-column: 1/-1;
  }
}
@media (max-width: 810px) {
  .rent-filterbar {
      grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .rent-filterbar .pill-btn {
      grid-column: auto;
  }
  .filters {
      grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
      gap: 9px;
  }
  .filter {
      min-width: 0;
      display: block !important;
      padding: 9px 10px !important;
  }
  .filter .sym {
      float: right;
      font-size: 16px !important;
      line-height: 1.2;
      min-width: 0 !important;
      margin-left: 3px;
  }
  .filter label {
      display: block !important;
      min-width: 0;
      width: 100%;
      font-size: 11px;
  }
  #app .filter select {
      font-size: 11px !important;
      padding-right: 24px !important;
      background-position: right 3px center !important;
      background-size: 10px 7px !important;
  }
  .filters > .primary {
      grid-column: 1/-1;
  }
}
@media (max-width: 600px) {
  .rent-filterbar {
      padding: 11px;
      gap: 8px;
  }
  .rent-filterbar label {
      font-size: 10px;
  }
  .rent-filterbar select {
      font-size: 11px;
      padding: 9px 5px;
  }
  .listing-top {
      flex-direction: column;
      align-items: stretch;
  }
  .sorting {
      justify-content: space-between;
  }
  .sorting select {
      max-width: none;
      flex: 1;
  }
}
@media (max-width: 370px) {
  .filters {
      gap: 7px;
  }
  .filter {
      padding: 8px !important;
  }
  #app .filter select {
      font-size: 10px !important;
      letter-spacing: -0.13px;
      padding-right: 18px !important;
      background-position: right 0px center !important;
      background-size: 9px 6px !important;
  }
}
@media (max-width: 340px) {
  .filter .sym {
      display: none !important;
  }
  #app .filter select {
      font-size: 10px !important;
  }
}
```

### 3.7 Form fields, field grid, stepper, interests, role tiles, file upload

```css
.gg-filters select,
.gg-filters input,
.field input,
.field select,
.field textarea {
  border: 1px solid #bfe1ee;
  background: #fff;
  color: #1a668b;
  border-radius: 9px;
  padding: 11px 12px;
  outline: none;
  min-width: 0;
}
.gg-filters select:focus,
.field input:focus,
.field select:focus,
.field textarea:focus {
  border-color: #0c9ac4;
  box-shadow: 0 0 0 3px #0c9ac422;
}
.formgrid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 13px;
}
.field {
  display: block;
  margin-bottom: 14px;
  font-size: 12px;
  font-weight: 800;
  color: #17658b;
}
.field input,
.field select,
.field textarea {
  display: block;
  width: 100%;
  margin-top: 6px;
  font-size: 13px;
  font-weight: 400;
}
.field textarea {
  resize: vertical;
  min-height: 80px;
}
.interests {
  display: flex;
  gap: 7px;
  flex-wrap: wrap;
  margin: 8px 0 12px;
}
.interest {
  padding: 6px 12px;
  border-radius: 18px;
  background: #ecfaff;
  border: 1px solid #c3e5ef;
  color: #137399;
  font-size: 12px;
}
.interest.selected {
  background: #037aa6;
  border-color: #037aa6;
  color: white;
}
.stepper {
  display: flex;
  gap: 8px;
  margin: 12px 0 22px;
}
.stepper div {
  height: 5px;
  flex: 1;
  background: #ddedf3;
  border-radius: 9px;
}
.stepper .current {
  background: #078aba;
}
.role-list {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 11px;
  margin: 15px 0;
}
.role-item {
  padding: 16px 9px;
  border: 1px solid #c2e0ea;
  background: #f0faff;
  border-radius: 11px;
  font-size: 12px;
  text-align: center;
  color: #0c7099;
}
.role-item.selected {
  background: #e0f6ff;
  border: 2px solid #0390bd;
}
.role-item span {
  display: block;
  font-size: 27px;
}
.searchbox {
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1px solid #cae5f0;
  border-radius: 9px;
  background: white;
  padding: 5px 11px;
}
.searchbox input {
  background: transparent;
  border: 0;
  outline: none;
  flex: 1;
  min-width: 0;
  padding: 7px;
}
.doc-upload {
  background: #ecf8fe;
  border: 1px dashed #8bd0ed;
  border-radius: 11px;
  padding: 13px;
  margin: 13px 0;
}
.doc-upload p {
  font-size: 12px;
  margin: 3px 0 10px;
}
.doc-upload small {
  font-size: 10px;
  color: #5c93ab;
}
.lesson-fieldset {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 13px;
}
@media (max-width: 540px) {
  .formgrid {
      grid-template-columns: 1fr;
      gap: 0;
  }
  .role-list {
      grid-template-columns: 1fr 1fr;
  }
  .role-item:last-child {
      grid-column: span 2;
  }
}
@media (max-width: 760px) {
  .lesson-fieldset {
      grid-template-columns: 1fr;
  }
}
```

### 3.8 Toggle (UX-07) and toggle rows

`button.toggle[.on]` — pill track with a white knob drawn by `:before`. Base track is 43×26 but inside `.toggle-row` and `.rent-profile-actions` it is widened to **58×30 with a 22px knob** (v12 rule, TZ UX-07). Off `#b9dbe9`, on `#0a83ad` (knob jumps right via `justify-content:flex-end`; no knob animation — only background transition). Always render it as the right-hand control of a `.toggle-row` (text left, `min-width:0; flex:1`). Add `role="switch"` + `aria-checked` in the port (prototype only has `aria-label`).

```css
.toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 13px;
  padding: 13px 0;
  border-top: 1px solid #e0eff6;
}
.toggle-row p {
  margin: 3px 0 0;
  font-size: 12px;
  color: var(--muted);
}
.toggle {
  width: 43px;
  height: 26px;
  border-radius: 22px;
  background: #b9dbe9;
  border: 0;
  padding: 4px;
  display: flex;
  align-items: center;
  transition: background 0.15s;
}
.toggle.on {
  background: #0a83ad;
  justify-content: flex-end;
}
.toggle:before {
  content: "";
  width: 18px;
  height: 18px;
  background: white;
  border-radius: 50%;
  display: block;
  box-shadow: 0 2px 5px #1e527650;
}
.toggle-row > button.toggle,
.rent-profile-actions > button.toggle {
  box-sizing: border-box;
  width: 58px;
  min-width: 58px;
  height: 30px;
  flex: 0 0 58px;
  padding: 4px;
}
.toggle-row > button.toggle::before,
.rent-profile-actions > button.toggle::before {
  width: 22px;
  height: 22px;
  flex: 0 0 22px;
}
.toggle-row > div:first-child {
  min-width: 0;
  flex: 1 1 auto;
}
```

### 3.9 Segments & tabs (UX-05)

Three segment styles exist — unify to one height/radius (UX-05):
* `.lesson-tabs > .lesson-tab[.active]` — instructor modal tabs (track `#e8f6fb` radius 13, active tab white with shadow); overflows horizontally on 390px (third tab is cut — fix in the port).
* `.gg-mode-tabs > button[.active]` — «⌖ На карте / ☷ Списком» (radius 9, active `#0a6b99`).
* `.intent-chips > .intent-chip[.active]` — GG intent pills (radius 20, active `#075c86`).
* `.tabs > .tab[.active]` — generic pill tabs (radius 26, active `#096f9c`), currently unused in public screens.

```css
.tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 17px;
}
.tab {
  border: 1px solid #bcdfe9;
  background: #fff;
  color: #22779d;
  padding: 9px 14px;
  border-radius: 26px;
  font-size: 12px;
  font-weight: 800;
}
.tab.active {
  background: #096f9c;
  color: white;
}
.lesson-tabs {
  display: flex;
  gap: 5px;
  background: #e8f6fb;
  border-radius: 13px;
  padding: 5px;
  margin: 16px 0;
  overflow: auto;
}
.lesson-tab {
  appearance: none;
  flex: 1;
  min-width: 110px;
  border: 0;
  border-radius: 10px;
  padding: 11px 12px;
  background: transparent;
  color: #367a9a;
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}
.lesson-tab.active {
  background: white;
  color: #005a82;
  box-shadow: 0 2px 8px #32627c14;
}
.intent-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.intent-chip {
  border: 1px solid #bfe1f0;
  border-radius: 20px;
  background: #fff;
  padding: 10px 13px;
  color: #1d729a;
  font-size: 12px;
  font-weight: 750;
  white-space: nowrap;
  cursor: pointer;
}
.intent-chip.active {
  background: #075c86;
  color: white;
  border-color: #075c86;
  box-shadow: 0 6px 16px #176a9e21;
}
.gg-mode-tabs {
  display: flex;
  align-items: center;
  gap: 9px;
  margin: 13px 0;
}
.gg-mode-tabs button {
  border: 1px solid #cfe7f1;
  border-radius: 9px;
  padding: 8px 14px;
  background: #fff;
  color: #1b7198;
  font-weight: 800;
  font-size: 12px;
  cursor: pointer;
}
.gg-mode-tabs button.active {
  background: #0a6b99;
  color: #fff;
}
.gg-mode-tabs span {
  margin-left: auto;
  color: #7fa2b6;
  font-size: 10px;
}
@media (max-width: 810px) {
  .gg-mode-tabs span {
      display: none;
  }
}
@media (max-width: 600px) {
  .intent-chips {
      gap: 6px;
  }
  .intent-chip {
      font-size: 11px;
      padding: 8px 10px;
  }
}
@media (max-width: 540px) {
  .gg-mode-tabs {
      overflow-x: auto;
  }
}
```

### 3.10 Tags, chips, badges (certificate states)

* `.tag.soft` — neutral info pill (spot type/level/season, region in modals).
* `.tag.verified` — green «✓ сертификат» / «✓ Сертификат · демо». In the prototype the certificate has only two visual states (badge shown = `cert:true`, nothing = `cert:false`). TZ INS-03 / TRUST-03 require **three** distinguishable states — proposal using existing styles: *не указан* → no badge (or `.tag.soft` «Сертификат не указан» in the profile); *загружен* → `.tag.soft` «Сертификат загружен» (blue-grey); *проверен* → `.tag.verified` «✓ Сертификат проверен».
* `.tag.gg` — «GG Surfer · {status}».
* `.chip` / `.chip.info` (cursor help, emoji + label: nature & infrastructure) / `.chip.on`.
* `.photo-badge` (bottom-left on photo), `.region-tag` (glass pill with pin icon, max-width 195/165px with ellipsis), `.instructor-ready` «◷ Выбор времени».
* Counter badge `.count` (header).

```css
.person-photo .tag {
  position: absolute;
  top: 12px;
  left: 12px;
  background: #e9f9ff;
  color: #0a618c;
}
.tag {
  border-radius: 24px;
  padding: 4px 11px;
  font-size: 10px;
  font-weight: 800;
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.tag.soft {
  background: #e6f6fd;
  color: #09628b;
}
.tag.verified {
  background: #def7f1;
  color: #137762;
}
.tag.gg {
  background: #e7f2ff;
  color: #116da4;
}
.conditions {
  display: flex;
  gap: 9px;
  flex-wrap: wrap;
  margin: 10px 0 15px;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip {
  border: 1px solid #b4dbed;
  background: #f4fcff;
  color: #1e7299;
  border-radius: 24px;
  padding: 7px 11px;
  font-size: 12px;
  cursor: pointer;
}
.chip.on {
  background: #06658d;
  color: white;
  border-color: #06658d;
}
.chip.info {
  cursor: help;
}
.photo-badge {
  position: absolute;
  bottom: 10px;
  left: 10px;
  background: #ffffffdd;
  color: #0b6994;
  border-radius: 20px;
  font-size: 11px;
  padding: 5px 10px;
  font-weight: 800;
}
.region-on-photo {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 2;
}
.region-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  max-width: 195px;
  border: 1px solid #daedfa;
  padding: 5px 10px 5px 8px;
  border-radius: 25px;
  background: #f1fbffed;
  color: #0b6592;
  font-size: 11px;
  font-weight: 800;
  box-shadow: 0 3px 13px #17496822;
  backdrop-filter: blur(6px);
  white-space: nowrap;
}
.region-tag span {
  overflow: hidden;
  text-overflow: ellipsis;
}
.region-tag svg {
  flex: none;
}
.instructor-ready {
  font-size: 10px;
  background: #e3f6fb;
  border: 1px solid #c8eaf3;
  border-radius: 10px;
  padding: 5px 8px;
  color: #1e789d;
}
@media (max-width: 540px) {
  .region-tag {
      max-width: 165px;
  }
}
```

### 3.11 Rating stars & reviews

Ratings are text: `★ 4.9 (24 отзывов)` (`.rating-link`, clickable → reviews modal) or `★ 4.8 (18)` (`.stars` on spots). Review cards show `★★★★★`/`☆` strings. The big metric in the instructor «Отзывы ★» tab: 45px number + gold `★★★★★` (`.lesson-review-stars`, always five gold stars regardless of value — fix: render filled/partial stars). Rating average = `(rating·reviews + Σ local) / n` on the client — replace with API value (TZ SPT-10, TRUST-01).

```css
.stars {
  white-space: nowrap;
  color: #087eab;
  font-size: 12px;
}
.rating-link {
  border: 0;
  background: transparent;
  color: #0578a7;
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
  padding: 1px 0;
  text-align: right;
  cursor: pointer;
}
.rating-link:hover {
  text-decoration: underline;
}
.review-peek {
  font: 11px/1.4 var(--font);
  color: #4d84a2;
  display: block;
  width: 100%;
  padding: 6px 8px 7px;
  text-align: left;
  background: #eaf8fc;
  border: 0;
  border-radius: 7px;
  margin: -4px 0 9px;
}
.review-peek span {
  display: block;
  color: #046891;
  font-weight: 800;
  margin-top: 4px;
}
.review-item {
  padding: 12px 14px;
  border: 1px solid #d4edf6;
  border-radius: 10px;
  background: #f7fcff;
  margin: 10px 0;
}
.review-item p {
  margin: 5px 0 6px;
  color: #3c7796;
}
.review-item small {
  color: #77a0b3;
}
.review-top {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}
.detail-score {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
}
.detail-score small {
  color: #6396ac;
}
.reviews-inline {
  max-height: 280px;
  overflow: auto;
}
.lesson-review-stars {
  font-size: 17px;
  color: #f1aa39;
  letter-spacing: 0.08em;
}
.lesson-reviews-section {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 17px;
}
.lesson-review-metric {
  text-align: center;
  background: #effaff;
  border: 1px solid #d4ecf6;
  border-radius: 14px;
  padding: 20px;
}
.lesson-review-metric strong {
  display: block;
  font-size: 45px;
  color: #086c93;
}
.lesson-review-metric .stars {
  font-size: 18px;
}
.lesson-review-metric p {
  font-size: 11px;
  margin-top: 6px;
}
.lesson-review-list {
  max-height: 360px;
  overflow: auto;
}
@media (max-width: 760px) {
  .lesson-cal-wrap,
    .lesson-info-columns,
    .lesson-reviews-section {
      grid-template-columns: 1fr;
  }
}
```

### 3.12 Heart / like button (pink active state)

`button.like-btn[.active][data-like="person:id|spot:id|rental:id"]` — 35×35 circle, translucent navy `#003c6788`, white glyph ♡ (inactive) / ♥ (active), font-size 26px. Active (final rule, `!important`): **text `#ec789c`, background `#fff0f5`, border `#f7d4e1`**. Position: person card top 9px/right 3px; spot card shifted left (`right:55px`) to make room for the pencil; rental card static 32×32 light variant. Pills with hearts use `.pill-btn.pink-heart` when active. The header heart is an SVG; cards use glyphs — TZ UX-04/MSG-11 want one standard heart: use the `heart` SVG from icons.json everywhere (stroke when inactive, fill `#ec789c` when active).

```css
.like-btn {
  position: absolute;
  top: 9px;
  right: 3px;
  color: #fff;
  background: #003c6788;
  border: 0;
  border-radius: 50%;
  height: 35px;
  width: 35px;
  font-size: 26px;
  line-height: 32px;
  text-shadow: 0 2px 5px #003a5d50;
}
.like-btn.active {
  text-shadow: none;
}
.like-btn {
  transition:
    background 0.15s,
    color 0.15s;
}
.spot-pic .like-btn {
  right: 55px;
  top: 11px;
  z-index: 1;
}
.rent-details .like-btn {
  position: static;
  width: 32px;
  height: 32px;
  background: #f6fdff;
  color: #25789e;
  border-color: #d6edf5;
}
.pink-heart,
.like-btn.active,
.like-btn.active:hover {
  color: #ec789c !important;
  background: #fff0f5 !important;
  border-color: #f7d4e1 !important;
}
```

### 3.13 Person (instructor) card

`article.person-card > .person-photo(img 184px cover; span.region-on-photo > .region-tag; button.like-btn) + .person-body( .person-name(h3 + rating-link) , button.review-peek , .fieldline×(role, spots, boards) , .tiny-cols(.fieldline опыт, .fieldline уровень учеников) , .fact , .instructor-price , button.primary.card-cta )`.
Photo height 184px (≤540: 218px). Screens: `public-people-1440.png`, `public-people-390.png`.

```css
.person-card,
.spot-card {
  background: #f9fdff;
  border: 1px solid #d7f0fa;
  overflow: hidden;
  transition: transform 0.16s;
}
.person-photo {
  height: 184px;
  position: relative;
  overflow: hidden;
  background: #b5ddea;
}
.person-photo img {
  height: 100%;
  width: 100%;
  object-fit: cover;
}
.person-body {
  padding: 14px 13px 13px;
}
.person-name {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: flex-start;
}
.person-name h3 {
  font-size: 17px;
  margin: 0 0 10px;
}
.fieldline {
  display: flex;
  gap: 9px;
  align-items: flex-start;
  font-size: 12px;
  color: #2f84ac;
  min-height: 37px;
  line-height: 1.35;
  margin: 2px 0;
}
.fieldline b {
  font-size: 11px;
  display: block;
  color: #65a0be;
  font-weight: 500;
}
.fieldline .sym {
  width: 22px;
  color: #056a9d;
  font-size: 15px;
  flex: none;
}
.tiny-cols {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 9px;
}
.fact {
  background: #e3f7ff;
  border-radius: 9px;
  padding: 11px;
  font-size: 11px;
  color: #2983a9;
  min-height: 69px;
  margin: 10px 0 10px;
}
.fact strong {
  color: #07648d;
}
.empty {
  padding: 35px 15px;
  text-align: center;
  color: #6996aa;
  border: 1px dashed #b1dbe9;
  border-radius: 11px;
}
.surfer-empty {
  width: 100%;
  max-width: 590px;
  margin: 28px auto 45px;
  padding: 28px 24px;
  background: #effbff;
}
.surfer-empty h3 {
  margin: 12px 0 5px;
  color: #075a83;
}
.surfer-empty p {
  max-width: 450px;
  margin: 0 auto 14px;
}
.instructor-price {
  margin-top: 13px;
  margin-bottom: 10px;
  display: flex;
  justify-content: space-between;
  gap: 7px;
  align-items: center;
  padding: 11px 0;
  border-top: 1px solid #e3f1f6;
  color: #175b7c;
  font-size: 12px;
}
.instructor-price strong {
  color: #075577;
  font-size: 16px;
}
.instructor-price small {
  display: block;
  font-size: 10px;
  color: #94afbd;
}
.feature,
.person-card,
.spot-card {
  border-radius: 12px;
  box-shadow: 0 4px 14px #1389b21e;
}
.feature:hover,
.person-card:hover,
.spot-card:hover,
.rent-card:hover {
  transform: translateY(-3px);
}
@media (max-width: 540px) {
  .person-photo {
      height: 218px;
  }
  .surfer-empty svg {
      width: 135px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .primary,
    .pill-btn,
    .feature,
    .person-card,
    .spot-card,
    .rent-card,
    .rent-illustration {
      transition: none !important;
  }
  .feature,
    .person-card,
    .spot-card,
    .rent-card {
      transition: none !important;
      transform: none !important;
  }
}
```

### 3.14 Spot card

`article.spot-card > .spot-pic(img 183px; span.photo-badge «⌖ Регион»; button.like-btn; button.gv-spot-edit-trigger (pencil)) + .spot-body( .spot-title(h3 + .stars) , .conditions(3× .tag.soft) , .spot-signal(«≋ Ветер: …», «◷ сезон») , p.spot-summary , .chips(nature .chip.info) , .spot-safety «⚑ первое предложение опасностей» , button.primary.card-cta «Подробнее о споте →» )`.
Screen: `public-component-spot-card-liked.png`.

```css
.person-card,
.spot-card {
  background: #f9fdff;
  border: 1px solid #d7f0fa;
  overflow: hidden;
  transition: transform 0.16s;
}
.spot-pic {
  height: 183px;
  position: relative;
}
.spot-pic img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.spot-title {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}
.spot-body {
  padding: 16px;
}
.spot-body h3 {
  margin: 0 0 10px;
}
.spot-summary {
  font-size: 12px;
  color: #4d90ad;
  min-height: 44px;
}
.gv-spot-edit-trigger {
  position: absolute;
  right: 11px;
  top: 11px;
  z-index: 2;
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border: 1px solid #ffffffaa;
  border-radius: 11px;
  background: #ffffffee;
  color: #09638c;
  box-shadow: 0 4px 13px #0036533b;
  transition:
    background 0.16s,
    transform 0.16s;
}
.gv-spot-edit-trigger:hover {
  background: #fff;
  transform: translateY(-1px);
}
.gv-spot-edit-trigger:focus-visible,
.gv-wind-choice:focus-visible {
  outline: 3px solid #70c4e5;
  outline-offset: 2px;
}
.spot-signal {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 9px;
  font-size: 10px;
  color: #2b7798;
}
.spot-signal span {
  background: #e5f6fb;
  padding: 5px 8px;
  border-radius: 7px;
}
.spot-safety {
  font-size: 11px;
  color: #9d6256;
  border-top: 1px solid #e1eff5;
  padding: 8px 2px 11px;
  margin-top: 5px;
}
.feature,
.person-card,
.spot-card {
  border-radius: 12px;
  box-shadow: 0 4px 14px #1389b21e;
}
.feature:hover,
.person-card:hover,
.spot-card:hover,
.rent-card:hover {
  transform: translateY(-3px);
}
@media (prefers-reduced-motion: reduce) {
  .primary,
    .pill-btn,
    .feature,
    .person-card,
    .spot-card,
    .rent-card,
    .rent-illustration {
      transition: none !important;
  }
  .feature,
    .person-card,
    .spot-card,
    .rent-card {
      transition: none !important;
      transform: none !important;
  }
}
```

### 3.15 Rental card, rental detail, safe strip, empty state

`article.rent-card.premium-card > .rent-art(style --rent-tint; span.rent-watermark «ГДЕВОЛНА • АРЕНДА»; .rent-illustration > svg (board/wetsuit); .rent-art-bottom «СЁРФБОРД|НЕОПРЕН ◌») + .rent-card-body( .rent-details(span.micro-label «Регион · Город» + like-btn) , h3 , p , .rent-chips(size, type, «У {owner}») , .rent-card-footer(strong price + small «/ день · пример», button.primary «Подробнее →») )`.
Grid 4 → 3 (≤1100) → 2 (≤810) → 1 (≤380). There are no photos — illustrations only; TZ RENT-01 needs real photos: keep `.rent-art` as the no-photo fallback.

```css
.rental-intro {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 22px;
  margin: 28px 0;
}
.rental-intro h2 {
  margin: 5px 0 9px;
  color: #07567c;
}
.rental-intro p {
  font-size: 13px;
  color: #5d8a9f;
  margin: 0;
}
.rental-intro button {
  flex: none;
}
.rent-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-top: 17px;
}
.rent-card {
  overflow: hidden;
  border: 1px solid #d2eaf4;
  transition: 0.25s;
}
.rent-art {
  height: 215px;
  background: radial-gradient(circle at 80% 10%, #fff9, transparent 50%),
    linear-gradient(135deg, var(--rent-tint), #e1f6fa 85%);
  position: relative;
  overflow: hidden;
  display: grid;
  place-items: center;
}
.rent-art:before {
  content: "";
  position: absolute;
  inset: auto -20% -38% -20%;
  height: 70%;
  border-radius: 50%;
  background: #fff6;
  transform: rotate(-7deg);
}
.rent-watermark {
  position: absolute;
  left: 13px;
  top: 12px;
  font-size: 9px;
  letter-spacing: 0.14em;
  font-weight: 900;
  color: #357f9b;
  opacity: 0.85;
}
.rent-illustration {
  height: 94%;
  position: relative;
  filter: drop-shadow(9px 14px 10px #214e6133);
  transform: rotate(-6deg);
  transition: transform 0.35s;
}
.rent-card:hover .rent-illustration {
  transform: rotate(-2deg) translateY(-6px);
}
.rent-illustration svg {
  height: 100%;
  width: auto;
}
.rent-art-bottom {
  position: absolute;
  bottom: 11px;
  left: 14px;
  right: 14px;
  display: flex;
  justify-content: space-between;
  font-size: 9px;
  color: #5f93ab;
  letter-spacing: 0.13em;
  font-weight: 900;
}
.rent-card-body h3 {
  font-size: 16px;
  line-height: 1.25;
  min-height: 39px;
  margin: 4px 0 9px;
  color: #075477;
}
.rent-card-body p {
  font-size: 12px;
  color: #6290a4;
  min-height: 56px;
  margin: 0 0 10px;
}
.rent-details {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}
.rent-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-bottom: 13px;
}
.rent-chips span {
  border-radius: 6px;
  padding: 4px 7px;
  font-size: 10px;
  background: #eaf7fb;
  color: #337998;
}
.rent-card-footer {
  display: flex;
  gap: 8px;
  justify-content: space-between;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid #e7f3f7;
}
.rent-card-footer strong {
  font-size: 18px;
  color: #00557d;
  white-space: nowrap;
}
.rent-card-footer small {
  display: block;
  color: #88aaba;
  font-size: 10px;
}
.rent-card-footer .primary {
  padding: 10px 11px;
  font-size: 11px;
}
.rental-detail {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 24px;
  align-items: center;
}
.rental-detail .rent-art {
  height: 245px;
  border-radius: 16px;
}
.rental-detail p {
  font-size: 13px;
  color: #66889b;
}
.rental-bigprice {
  font-size: 25px;
  font-weight: 900;
  color: #06587e;
}
.rental-bigprice small {
  font-size: 11px;
  color: #7595a6;
}
.safe-strip {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  margin-top: 23px;
  padding: 20px;
  border: 1px solid #d3e8f1;
  border-radius: 16px;
  background: linear-gradient(140deg, #e6f7fc, #f6fdff);
}
.safe-strip > span {
  font-size: 26px;
  color: #087ba8;
}
.safe-strip strong {
  font-size: 14px;
}
.safe-strip p {
  font-size: 12px;
  color: #5686a0;
  margin: 5px 0 0;
}
.premium-empty {
  text-align: center;
  padding: 34px;
  background: #eaf9fe;
  border: 1px dashed #afdce9;
  border-radius: 17px;
}
.premium-empty svg {
  height: 95px;
  width: auto;
}
.premium-empty h3 {
  margin: 8px 0 5px;
}
.premium-empty p {
  color: #6296ac;
}
.rent-profile-panel,
.club-profile-mini {
  background: linear-gradient(115deg, #e9f8fc, #f8fdff);
  border: 1px solid #cfe8f3;
  border-radius: 17px;
  padding: 20px 22px;
  margin: 20px 0 15px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}
.rent-profile-panel h3 {
  font-size: 18px;
  margin: 5px 0;
}
.rent-profile-panel p {
  font-size: 12px;
  color: #6690a2;
  margin: 0;
}
.rent-profile-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.rent-profile-actions .toggle {
  flex: none;
}
.feature:hover,
.person-card:hover,
.spot-card:hover,
.rent-card:hover {
  transform: translateY(-3px);
}
.rent-card,
.rose-card,
.achievement,
.rent-filterbar,
.gg-intent,
.gg-kindness {
  border-radius: 12px;
  box-shadow: var(--shadow);
}
.rent-card,
.achievement {
  background: #f9fdff;
  border-color: #d7f0fa;
}
.rent-card-body {
  padding: 16px 17px;
}
.rental-intro h2,
.club-invite h2 {
  font-size: 25px;
  letter-spacing: -0.65px;
}
.rent-grid {
  gap: 18px;
}
#app > .wrap,
.section,
.hero,
.filters,
.grid,
.gg-widget,
.rent-grid,
.account-sections {
  min-width: 0;
}
@media (prefers-reduced-motion: reduce) {
  .primary,
    .pill-btn,
    .feature,
    .person-card,
    .spot-card,
    .rent-card,
    .rent-illustration {
      transition: none !important;
  }
  .feature,
    .person-card,
    .spot-card,
    .rent-card {
      transition: none !important;
      transform: none !important;
  }
}
@media (max-width: 1100px) {
  .rent-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 810px) {
  .rental-intro {
      align-items: flex-start;
      flex-direction: column;
  }
  .rental-intro h2 {
      font-size: 26px;
  }
  .rent-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .grid,
    .grid-2,
    .grid-3,
    .board-grid,
    .gg-widget,
    .rent-grid,
    .spots-overview-map {
      min-width: 0;
  }
}
@media (max-width: 600px) {
  .rent-grid {
      gap: 10px;
  }
  .rent-card-body {
      padding: 11px;
  }
  .rent-card-body h3 {
      font-size: 13px;
      min-height: 36px;
  }
  .rent-card-body p {
      font-size: 11px;
      min-height: 72px;
  }
  .rent-art {
      height: 158px;
  }
  .rent-watermark {
      font-size: 7px;
      letter-spacing: 0.09em;
  }
  .rent-chips {
      gap: 4px;
  }
  .rent-chips span {
      font-size: 9px;
  }
  .rent-card-footer {
      align-items: flex-start;
      flex-direction: column;
  }
  .rent-card-footer strong {
      font-size: 16px;
  }
  .rent-card-footer .primary {
      width: 100%;
  }
  .rental-detail {
      grid-template-columns: 1fr;
  }
  .rental-detail .rent-art {
      height: 175px;
  }
  .rental-detail .rent-illustration {
      height: 100%;
  }
  .rent-profile-panel,
    .club-profile-mini {
      flex-wrap: wrap;
      padding: 15px;
  }
  .rent-profile-actions {
      width: 100%;
      justify-content: space-between;
  }
}
@media (max-width: 380px) {
  .rent-card-body p {
      min-height: auto;
  }
  .rent-grid {
      grid-template-columns: 1fr;
  }
  .rent-art {
      height: 205px;
  }
}
@media (max-width: 540px) {
  .rent-grid {
      gap: 12px;
  }
  .rent-card-body {
      padding: 12px;
  }
  .rent-art {
      height: 170px;
  }
}
```

### 3.16 Modal system

`#modalRoot > .modal-backdrop[data-dismiss] > .modal[.wide][role=dialog][aria-modal=true] > button.close[data-action=close] + content`.
Width 620px (`.wide` 820px; instructor modal 910px ≥900px; spot-edit 790px with padding 0). `max-height: calc(100vh - 45px)` with internal scroll; body scroll locked (`overflow:hidden`) while open. Closing: click on backdrop (only if the click target is the backdrop itself), «×», Esc. Only one modal at a time — opening another replaces the content (no stack, no history). TZ UX-12: add focus trap, return focus, history/back-button support and `100dvh` on phones.
Shared modal parts: `.notice` (blue left rule), `.lesson-form-note`, `.lesson-safe`, `.lesson-demo-banner` (dashed), `.view-tools` / `.lesson-footer-actions` (button rows), `.lesson-two-actions`.

```css
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: #003f639a;
  z-index: 80;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 22px;
  overflow: auto;
  backdrop-filter: blur(5px);
}
.modal {
  position: relative;
  width: min(620px, 100%);
  max-height: calc(100vh - 45px);
  overflow: auto;
  background: #faffff;
  border-radius: 17px;
  box-shadow: 0 20px 80px #002e4d67;
  padding: 29px;
  border: 1px solid #cdf0f8;
}
.modal.wide {
  width: min(820px, 100%);
}
.modal h2 {
  font-size: 27px;
  margin-bottom: 8px;
}
.modal p {
  color: #628ca3;
  font-size: 13px;
}
.notice {
  padding: 12px 15px;
  background: #e8f7fc;
  border-left: 3px solid #0c9ac8;
  border-radius: 8px;
  font-size: 12px;
  color: #3984a3;
  margin: 14px 0;
}
.modal.wide:has(.gv-spot-edit-modal) {
  width: min(790px, 100%);
  padding: 0;
  overflow: auto;
}
.modal:has(.gv-spot-success) {
  padding: 30px;
}
.lesson-hint {
  font-size: 12px;
  color: #618ca4;
  line-height: 1.6;
}
.lesson-micro {
  font-size: 11px;
  color: #7196aa;
}
.lesson-safe {
  background: #f0f9fc;
  color: #2c7792;
  border: 1px solid #d5edf5;
  padding: 9px 12px;
  border-radius: 10px;
  font-size: 11px;
  line-height: 1.5;
}
.lesson-footer-actions {
  border-top: 1px solid #dceef4;
  margin-top: 17px;
  padding-top: 15px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.lesson-footer-actions .primary {
  width: auto;
  min-width: 220px;
}
.lesson-form-note {
  background: #f3fbff;
  border-left: 3px solid #88cfe5;
  border-radius: 5px;
  padding: 11px 13px;
  margin: 13px 0;
  color: #4a819a;
  font-size: 11px;
  line-height: 1.6;
}
.lesson-demo-banner {
  border: 1px dashed #acd6e6;
  color: #347d9b;
  background: #eff9fe;
  border-radius: 12px;
  padding: 11px 13px;
  font-size: 11px;
  line-height: 1.6;
  margin: 12px 0;
}
.lesson-two-actions {
  display: flex;
  gap: 9px;
  flex-wrap: wrap;
}
@media (max-width: 540px) {
  .modal {
      padding: 21px;
  }
}
@media (max-width: 640px) {
  .modal-backdrop {
      padding: 10px;
  }
  .modal.wide:has(.gv-spot-edit-modal) {
      width: 100%;
      max-height: calc(100dvh - 20px);
  }
}
@media (min-width: 900px) {
  .modal.wide:has(.lesson-dialog-intro) {
      width: min(910px, 100%);
  }
}
```

### 3.17 Toast

`#toast.toast[.hidden]` — fixed bottom-centre pill, `#044f75`, white 13px, auto-hide after **2.9 s** (one at a time; new text replaces the old). Use `role="status"` / `aria-live="polite"` in the port.

```css
.toast {
  position: fixed;
  z-index: 100;
  bottom: 21px;
  left: 50%;
  transform: translateX(-50%);
  background: #044f75;
  color: white;
  padding: 12px 18px;
  border-radius: 12px;
  box-shadow: 0 8px 29px #04587d35;
  font-size: 13px;
  max-width: 90vw;
  text-align: center;
}
```

### 3.18 Instructor modal internals (intro, info cards, calendar, slots, booking preview)

```css
.preview-profile {
  display: grid;
  grid-template-columns: 170px 1fr;
  gap: 19px;
  margin-top: 13px;
}
.preview-profile img {
  width: 100%;
  height: 220px;
  object-fit: cover;
  border-radius: 11px;
}
.preview-profile p {
  font-size: 13px;
}
.lesson-dialog-intro {
  display: flex;
  gap: 19px;
  align-items: stretch;
  margin: 0 0 16px;
}
.lesson-portrait {
  width: 185px;
  min-height: 195px;
  border-radius: 16px;
  object-fit: cover;
  flex: none;
  box-shadow: 0 7px 22px #03567b16;
}
.lesson-dialog-summary {
  flex: 1;
  min-width: 0;
  padding: 3px 14px 0 0;
}
.lesson-dialog-summary h2 {
  font-size: 29px;
  color: #06547b;
  line-height: 1.13;
  margin: 7px 0 8px;
}
.lesson-place {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 7px 0 10px;
  color: #116b93;
  font-size: 12px;
  font-weight: 800;
}
.lesson-top-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin: 12px 0;
}
.lesson-info-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
.lesson-info-card {
  background: #f0f9fd;
  border: 1px solid #d5edf6;
  border-radius: 14px;
  padding: 17px;
}
.lesson-info-card h3 {
  font-size: 15px;
  color: #065c85;
  margin: 0 0 8px;
}
.lesson-info-card p {
  margin: 0 0 6px;
}
.lesson-cal-wrap {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(220px, 0.9fr);
  gap: 16px;
  margin: 14px 0;
}
.lesson-cal {
  border: 1px solid #d3eaf5;
  background: white;
  border-radius: 16px;
  padding: 16px;
  min-width: 0;
  box-shadow: 0 7px 20px #1a81b10d;
}
.lesson-cal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}
.lesson-cal-header strong {
  font-size: 16px;
  color: #065983;
  text-transform: capitalize;
}
.lesson-cal-nav {
  display: flex;
  align-items: center;
  gap: 7px;
}
.lesson-cal-nav button {
  border: 1px solid #d3e9f3;
  background: #f2fbff;
  color: #0c7199;
  border-radius: 10px;
  width: 32px;
  height: 32px;
  font-size: 20px;
}
.lesson-cal-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 5px;
}
.lesson-weekday {
  text-align: center;
  color: #7b9cab;
  font-size: 10px;
  font-weight: 800;
  padding: 8px 0;
}
.lesson-day {
  position: relative;
  border: 1px solid transparent;
  background: #eaf8fe;
  color: #0b648c;
  border-radius: 10px;
  min-width: 0;
  aspect-ratio: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1px;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
}
.lesson-day span {
  font-size: 7px;
  letter-spacing: 0.01em;
  font-weight: 700;
  color: #5c9caf;
  white-space: nowrap;
}
.lesson-day:hover:not(:disabled) {
  border-color: #0393c2;
  box-shadow: 0 3px 9px #0a789b16;
}
.lesson-day.selected {
  background: #04749f;
  color: white;
  box-shadow: 0 5px 13px #0877a441;
}
.lesson-day.selected span {
  color: #d5f6ff;
}
.lesson-day.closed {
  background: #f1f3f6;
  color: #a7b2be;
}
.lesson-day.closed span {
  color: #afbbc6;
}
.lesson-day.booked {
  background: #fff1e9;
  color: #a66b37;
}
.lesson-day.booked span {
  color: #b68a64;
}
.lesson-day:disabled {
  background: #f6f8f9;
  color: #c4d1d6;
  cursor: default;
}
.lesson-day.today:not(.selected) {
  border-color: #f4ba82;
}
.lesson-day.empty {
  background: transparent;
  pointer-events: none;
}
.lesson-cal-legend {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  margin-top: 12px;
  color: #668da4;
  font-size: 10px;
}
.lesson-cal-legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.lesson-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #c8eefb;
}
.lesson-dot.muted {
  background: #e6e9ec;
}
.lesson-dot.busy {
  background: #ffddc3;
}
.lesson-side {
  padding: 19px 17px;
  background: linear-gradient(150deg, #f5fcff, #e9f7fc);
  border-radius: 16px;
  border: 1px solid #d6edf6;
}
.lesson-side h3 {
  font-size: 17px;
  color: #075f86;
  margin: 6px 0 10px;
}
.lesson-side p {
  font-size: 12px;
  line-height: 1.6;
}
.lesson-slot-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  margin: 14px 0;
}
.lesson-slot {
  border: 1px solid #c5e6f3;
  padding: 10px 9px;
  border-radius: 10px;
  background: #fff;
  color: #10678b;
  font-size: 12px;
  font-weight: 800;
}
.lesson-slot.selected {
  background: #066e99;
  color: #fff;
  border-color: #066e99;
}
.lesson-slot:disabled {
  background: #eaf0f3;
  color: #acbbc2;
  text-decoration: line-through;
}
.lesson-slot.manage {
  border-color: #b7dfe8;
}
.lesson-slot.manage.selected {
  background: #f3dfe7;
  color: #a04b73;
  border-color: #eabbcd;
  text-decoration: line-through;
}
.lesson-cal-cta {
  width: 100%;
  margin-top: 8px;
  padding: 12px;
}
.lesson-status-pill {
  padding: 6px 10px;
  border-radius: 100px;
  font-size: 11px;
  font-weight: 800;
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.lesson-status-pill.pending {
  background: #fff4dd;
  color: #916c23;
}
.lesson-status-pill.accepted {
  background: #e3f6ed;
  color: #218064;
}
.lesson-status-pill.completed {
  background: #e8f0ff;
  color: #3875af;
}
.lesson-status-pill.declined,
.lesson-status-pill.cancelled {
  background: #f3edf1;
  color: #90677c;
}
.lesson-order-list {
  display: grid;
  gap: 12px;
}
.lesson-order {
  background: #fbfeff;
  border: 1px solid #d3ebf4;
  border-radius: 15px;
  padding: 16px;
}
.lesson-order-main {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}
.lesson-order-icon {
  width: 44px;
  height: 44px;
  border-radius: 13px;
  background: #e3f4fb;
  display: grid;
  place-items: center;
  color: #08648f;
  flex: none;
  font-size: 19px;
}
.lesson-order-info {
  flex: 1;
  min-width: 0;
}
.lesson-order-info h3 {
  font-size: 15px;
  margin: 0 0 5px;
  color: #095f85;
}
.lesson-order-info p {
  font-size: 12px;
  margin: 4px 0;
  color: #5487a1;
}
.lesson-order-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin: 12px 0;
}
.lesson-order-meta span {
  background: #eaf6fc;
  color: #3f7e9b;
  font-size: 11px;
  border-radius: 30px;
  padding: 5px 9px;
}
.lesson-order-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  border-top: 1px solid #e7f2f7;
  margin-top: 13px;
  padding-top: 13px;
}
.lesson-order-actions button {
  font-size: 12px;
}
.lesson-price {
  font-size: 13px;
  color: #055c81;
  font-weight: 800;
}
.lesson-empty {
  padding: 27px 18px;
  text-align: center;
  border: 1px dashed #aed7e9;
  border-radius: 15px;
  background: #f7fcff;
}
.lesson-empty strong {
  display: block;
  font-size: 15px;
  color: #267294;
  margin: 10px 0 5px;
}
.lesson-empty p {
  font-size: 12px;
  color: #638fa5;
}
.lesson-waves {
  font-size: 38px;
  line-height: 1.4;
  color: #80cadf;
}
.lesson-weekly {
  display: flex;
  gap: 7px;
  flex-wrap: wrap;
}
.lesson-weekly span {
  background: #e7f4f9;
  border-radius: 100px;
  padding: 5px 10px;
  color: #4384a2;
  font-size: 11px;
}
.lesson-chat-header {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 8px;
}
.lesson-chat-photo {
  width: 49px;
  height: 49px;
  border-radius: 50%;
  object-fit: cover;
}
.lesson-chat-box {
  background: #f5fbff;
  min-height: 200px;
  max-height: 310px;
  overflow-y: auto;
  border: 1px solid #e0eff6;
  padding: 17px;
  border-radius: 13px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.lesson-chat-msg {
  max-width: 82%;
  align-self: flex-start;
  background: #fff;
  border: 1px solid #d6e8f2;
  border-radius: 13px 13px 13px 3px;
  padding: 12px 14px;
  font-size: 12px;
  line-height: 1.55;
  color: #165a7b;
}
.lesson-chat-msg.mine {
  align-self: flex-end;
  background: #d9effa;
  border-color: #c5e8f6;
  border-radius: 13px 13px 3px 13px;
}
.lesson-chat-msg small {
  display: block;
  color: #719cb0;
  font-size: 9px;
  margin-top: 6px;
}
.lesson-book-preview {
  display: flex;
  align-items: center;
  gap: 13px;
  background: #e9f6fb;
  padding: 12px;
  border: 1px solid #d1eaf4;
  border-radius: 13px;
  margin: 14px 0;
}
.lesson-book-preview img {
  width: 64px;
  height: 64px;
  object-fit: cover;
  border-radius: 12px;
}
.lesson-book-preview b {
  font-size: 13px;
  color: #07618b;
}
.lesson-book-preview p {
  font-size: 11px;
  margin: 4px 0;
  color: #6690a3;
}
.lesson-cta-small {
  font-size: 11px;
}
@media (max-width: 540px) {
  .preview-profile {
      grid-template-columns: 1fr;
  }
  .preview-profile img {
      max-height: 210px;
  }
}
@media (max-width: 760px) {
  .lesson-cal-wrap,
    .lesson-info-columns,
    .lesson-reviews-section {
      grid-template-columns: 1fr;
  }
  .lesson-dialog-intro {
      gap: 11px;
  }
  .lesson-portrait {
      width: 125px;
      min-height: 162px;
  }
  .lesson-dialog-summary h2 {
      font-size: 21px;
  }
}
@media (max-width: 480px) {
  .lesson-dialog-intro {
      flex-direction: column;
  }
  .lesson-portrait {
      width: 100%;
      height: 195px;
  }
  .lesson-day {
      font-size: 11px;
      border-radius: 8px;
  }
  .lesson-day span {
      font-size: 6px;
  }
  .lesson-cal-grid {
      gap: 3px;
  }
  .lesson-cal {
      padding: 11px;
  }
  .lesson-side {
      padding: 14px;
  }
  .lesson-order-main {
      gap: 9px;
  }
  .lesson-order-icon {
      width: 37px;
      height: 37px;
  }
}
```

### 3.19 Compass / wind & swell rose

Two implementations exist:
1. **`.compass` rings (what the final prototype actually renders)** — 114px circle with a conic-gradient arc (fixed 28–46% sector, *not* related to the real direction) and a white 74px centre with text «Ветер<br>{wind}». Purely decorative.
2. **`.rose-card` SVG roses (intended design, written in the "premium" script but overwritten by the later gallery script)** — card with icon (≋ / ◈), title «Направление ветра» / «Направление свелла», a 200×200 SVG compass (8 labelled points С…СЗ, needle to the stated direction, pink tip), the direction text and the caption «Показано указанное направление, не прогноз» (or «Уточняйте под прогноз» when the text is not a compass direction). See `icons.json → wind-rose-example` for the exact SVG and formula and the screenshot `public-spot-modal-rose-variant-1440.png`. **Implement the rose** (TZ SPT-04: "наглядные компасные диаграммы, не смешивать с прогнозом"); store direction as degrees/sector in the API rather than parsing Russian text.

```css
.compass-wrap {
  display: flex;
  gap: 19px;
  align-items: center;
  flex-wrap: wrap;
}
.compass {
  height: 114px;
  width: 114px;
  border-radius: 50%;
  background: conic-gradient(
    from 0deg,
    #eaf9ff 0 28%,
    #55b8d7 28% 46%,
    #eaf9ff 46% 100%
  );
  display: grid;
  place-items: center;
  position: relative;
  border: 5px solid #d5edf8;
}
.compass span {
  height: 74px;
  width: 74px;
  background: #fff;
  border-radius: 50%;
  display: grid;
  place-items: center;
  text-align: center;
  font-size: 12px;
  font-weight: 800;
  color: #0a6998;
}
.rose-wrap {
  display: grid !important;
  grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
  gap: 14px !important;
  align-items: stretch;
}
.rose-card {
  border: 1px solid #d9eef6;
  padding: 13px 10px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.rose-icon {
  color: #1b8aab;
  font-size: 21px;
}
.rose-card h4 {
  font-size: 12px;
  color: #145e7f;
  margin: 2px 0 4px;
}
.rose-card svg {
  width: min(100%, 198px);
  height: auto;
}
.rose-card strong {
  font-size: 12px;
  color: #0c5b81;
}
.rose-card small {
  font-size: 9px;
  color: #7d9fb0;
  margin-top: 4px;
}
.rent-card,
.rose-card,
.achievement,
.rent-filterbar,
.gg-intent,
.gg-kindness {
  border-radius: 12px;
  box-shadow: var(--shadow);
}
.rose-card {
  background: #f8fdff;
}
.rose-wrap .rose-card svg {
  max-width: 175px;
}
@media (max-width: 600px) {
  .rose-wrap {
      gap: 8px;
  }
  .rose-card {
      padding: 10px 4px;
  }
  .rose-card h4 {
      font-size: 11px;
  }
}
@media (max-width: 540px) {
  .rose-wrap {
      gap: 9px !important;
  }
}
```

### 3.20 Spot detail: hero image, caption, gallery, map section, video placeholder

```css
.spot-detail-hero {
  width: 100%;
  height: 235px;
  object-fit: cover;
  border-radius: 11px;
  margin-bottom: 15px;
}
.spot-map-section {
  margin: 20px 0;
  padding: 16px;
  background: #edf9fd;
  border-radius: 12px;
  border: 1px solid #cfedf8;
}
.spot-map-section h3 {
  margin: 0 0 8px;
}
.spot-iframe {
  height: 310px;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #cae8f1;
  background: #ddebf0;
}
.video-placeholder {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 20px;
  margin: 20px 0;
  border-radius: 12px;
  background: linear-gradient(125deg, #083955, #126885);
  color: white;
  min-height: 140px;
}
.video-placeholder h3 {
  margin: 0 0 5px;
}
.video-placeholder p {
  margin: 0 0 6px;
  color: #d3eaf7;
}
.video-placeholder small {
  color: #a6d0e1;
}
.spot-photo-caption {
  font-size: 10px;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: #4c7f9c;
  margin-top: 8px;
  margin-bottom: 14px;
  font-weight: 800;
}
.spot-photo-caption span {
  margin: 0 7px;
}
.spot-gallery-section {
  margin: 16px 0 18px;
}
.spot-gallery {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 10px;
}
.spot-gallery figure {
  margin: 0;
}
.spot-gallery img {
  width: 100%;
  height: 104px;
  object-fit: cover;
  border-radius: 12px;
  border: 1px solid var(--line);
  box-shadow: 0 5px 16px rgba(6, 105, 147, 0.1);
  background: #eaf8fd;
  display: block;
}
.spot-gallery figcaption {
  font-size: 11px;
  line-height: 1.35;
  color: var(--muted);
  margin-top: 6px;
}
@media (max-width: 540px) {
  .spot-iframe {
      height: 245px;
  }
}
@media (max-width: 640px) {
  .spot-gallery {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
  }
  .spot-gallery img {
      height: 88px;
  }
}
```

### 3.21 Map boxes (Yandex iframe, spots overview, GG schematic map, member list)

* `.mapbox.yandex-mapbox` — rounded box with an absolutely-filled `iframe.ya-frame` (Yandex map widget, satellite layer `l=sat`, markers `pm2rdm1…9`), a white label `.yandex-ribbon` top-left («Яндекс Карты · спутник» + small caption) and `.map-open` pill bottom-right («Открыть карту ↗»).
* `.spots-overview-map` — grid map (1.55fr) + `.spots-map-sidebar` (0.75fr, min 250px) list of `.map-spot-row` buttons.
* `.gg-local-map` — schematic illustrated map (gradient + 46px grid + `gg-schematic-land` SVG), region labels `.gg-place-label`, avatar pins `.gg-map-pin` (40px photo with blue ring, first name label; picked = pink ring, lifted), overlay head `.gg-map-head` with «Спутник Яндекса ↗» switch and bottom captions.
* `.gg-widget` — grid map + 325px `.member-list` (270px ≤1100; stacked ≤810).

```css
.gg-widget {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 325px;
  gap: 17px;
  min-height: 510px;
  margin: 20px 0;
}
.mapbox {
  position: relative;
  overflow: hidden;
  border: 1px solid #b8e3f4;
  border-radius: 14px;
  background: #cbeaf4;
  box-shadow: var(--shadow);
}
.member-list {
  border: 1px solid #cce9f5;
  background: #f8fdff;
  box-shadow: var(--shadow);
  border-radius: 14px;
  padding: 14px;
  overflow: auto;
  max-height: 560px;
}
.member-list h3 {
  font-size: 17px;
  margin: 4px 0 11px;
}
.member {
  width: 100%;
  border: 1px solid #dfedf4;
  background: #fff;
  border-radius: 11px;
  padding: 9px;
  display: flex;
  gap: 10px;
  align-items: center;
  text-align: left;
  color: var(--text);
  margin-bottom: 9px;
  cursor: pointer;
}
.member.active {
  border-color: #008ec1;
  background: #e6f8ff;
  box-shadow: 0 0 0 1px #008ec155;
}
.member img {
  height: 55px;
  width: 59px;
  border-radius: 8px;
  object-fit: cover;
}
.member strong {
  font-size: 12px;
  display: block;
}
.member small {
  color: #5b94b1;
  font-size: 10px;
  display: block;
}
.member p {
  margin: 2px 0 0;
  color: #257fa5;
  font-size: 11px;
  line-height: 1.28;
}
.ya-frame {
  display: block;
  border: 0;
  width: 100%;
  height: 100%;
  background: #cae4ee;
}
.spots-overview-map {
  display: grid;
  grid-template-columns: minmax(0, 1.55fr) minmax(250px, 0.75fr);
  gap: 16px;
  min-height: 390px;
}
.spots-overview-map .mapbox {
  min-height: 390px;
}
.spots-map-sidebar {
  border: 1px solid #d7ecf5;
  background: #f8fdff;
  border-radius: 13px;
  padding: 16px;
  overflow: auto;
  max-height: 410px;
}
.spots-map-sidebar h3 {
  margin: 0 0 9px;
}
.map-spot-row {
  display: flex;
  align-items: center;
  gap: 9px;
  width: 100%;
  background: transparent;
  border: 0;
  border-bottom: 1px solid #e3f1f7;
  text-align: left;
  padding: 10px 4px;
  color: #146b90;
  font-size: 12px;
}
.map-spot-row > span:nth-child(2) {
  flex: 1;
}
.map-spot-row small {
  display: block;
  color: #719ab0;
  margin-top: 2px;
}
.map-spot-row:hover {
  background: #e9f7fc;
}
.yandex-mapbox .ya-frame {
  position: absolute;
  inset: 0;
}
.yandex-ribbon {
  position: absolute;
  left: 12px;
  top: 12px;
  z-index: 1;
  padding: 8px 12px;
  max-width: 260px;
  border-radius: 10px;
  background: #fffffff0;
  color: #155978;
  font-size: 12px;
  font-weight: 800;
  pointer-events: none;
  box-shadow: 0 4px 16px #0848652c;
}
.yandex-ribbon small {
  display: block;
  font-weight: 400;
}
.map-open {
  position: absolute;
  right: 12px;
  bottom: 12px;
  z-index: 1;
  background: #fff;
  border: 1px solid #cce5f0;
  border-radius: 20px;
  padding: 8px 12px;
  color: #0b688c;
  font-size: 12px;
  font-weight: 800;
}
.gg-member-item {
  position: relative;
  border-bottom: 1px solid #e0eff5;
}
.gg-member-item .member {
  border: 0;
}
.mini-chat {
  font-size: 11px;
  background: #eef9ff;
  border: 1px solid #bee1ee;
  border-radius: 22px;
  padding: 5px 10px;
  margin: 0 8px 9px 73px;
  color: #0d6d95;
  font-weight: 700;
}
.gg-widget .member-list {
  max-height: 570px;
  overflow: auto;
}
.gg-list-view {
  grid-template-columns: 1fr !important;
}
.gg-list-view .mapbox {
  display: none !important;
}
.gg-list-view .member-list {
  display: grid !important;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 9px;
  max-height: none !important;
  height: auto !important;
  overflow: visible !important;
}
.gg-list-view .member-list > h3,
.gg-list-view .member-list > .notice,
.gg-list-view .member-list > .primary {
  grid-column: 1/-1;
}
.gg-local-map {
  position: relative;
  min-height: 470px;
  border-radius: 17px;
  overflow: hidden;
  background: radial-gradient(ellipse at 35% 12%, #d9f4f6 0%, transparent 55%),
    linear-gradient(145deg, #b8e2ec, #deeff0 70%);
  box-shadow: inset 0 1px 11px #2584a313;
  border: 1px solid #cae5ed;
  isolation: isolate;
}
.gg-local-map:before {
  content: "";
  position: absolute;
  inset: 0;
  background-image: linear-gradient(#ffffff3e 1px, transparent 1px),
    linear-gradient(90deg, #ffffff3e 1px, transparent 1px);
  background-size: 46px 46px;
  opacity: 0.7;
}
.gg-land-svg {
  position: absolute;
  inset: 10px 0 25px;
  width: 100%;
  height: calc(100% - 35px);
  opacity: 0.78;
  z-index: -1;
}
.gg-map-head {
  position: absolute;
  left: 16px;
  right: 16px;
  top: 15px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  z-index: 3;
  gap: 10px;
  pointer-events: none;
}
.gg-map-head > div {
  display: grid;
  gap: 4px;
  background: #f9ffffeb;
  padding: 11px 14px;
  border-radius: 12px;
  box-shadow: 0 7px 18px #0c669128;
}
.gg-map-head strong {
  font-size: 14px;
  color: #075d81;
}
.gg-map-head small {
  font-size: 10px;
  color: #6297ab;
}
.gg-satellite-switch,
.gg-back-to-local {
  pointer-events: auto !important;
  box-shadow: 0 7px 18px #0c669126;
  border: 1px solid #bbdce7;
  color: #07648e;
  background: #faffff;
  padding: 9px 11px;
  font-size: 11px;
  font-weight: 800;
  border-radius: 10px;
  cursor: pointer;
}
.gg-place-label {
  position: absolute;
  transform: translate(-50%, -50%);
  font-size: 10px;
  letter-spacing: 0.14em;
  font-weight: 900;
  color: #5c97ad;
  opacity: 0.8;
  pointer-events: none;
  text-shadow: 0 1px white;
  z-index: 1;
}
.gg-map-pin {
  position: absolute;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  gap: 3px;
  align-items: center;
  z-index: 2;
  border: 0;
  background: transparent;
  cursor: pointer;
  filter: drop-shadow(0 5px 5px #0b557c31);
  transition: transform 0.18s;
}
.gg-map-pin:hover,
.gg-map-pin.picked {
  transform: translate(-50%, -59%) scale(1.09);
  z-index: 4;
}
.gg-map-pin img {
  height: 40px;
  width: 40px;
  object-fit: cover;
  border: 3px solid white;
  border-radius: 50%;
  box-shadow: 0 0 0 3px #0877a5a3;
}
.gg-map-pin.picked img {
  box-shadow: 0 0 0 4px #ef628d;
}
.gg-map-pin span {
  border-radius: 6px;
  padding: 4px 7px;
  background: #f9ffffed;
  font-size: 10px;
  font-weight: 900;
  color: #0e6286;
  white-space: nowrap;
}
.gg-map-bottom {
  position: absolute;
  bottom: 11px;
  left: 15px;
  right: 15px;
  display: flex;
  justify-content: space-between;
  gap: 9px;
  color: #336d89;
  font-size: 10px;
  font-weight: 800;
  pointer-events: none;
}
.gg-satellite-view {
  height: 100%;
  position: relative;
}
.gg-satellite-view > .mapbox {
  height: 100% !important;
}
.gg-back-to-local {
  position: absolute;
  left: 12px;
  bottom: 11px;
  z-index: 4;
}
#app > .wrap,
.section,
.hero,
.filters,
.grid,
.gg-widget,
.rent-grid,
.account-sections {
  min-width: 0;
}
@media (max-width: 1100px) {
  .gg-widget {
      grid-template-columns: minmax(0, 1fr) 270px;
  }
}
@media (max-width: 810px) {
  .gg-widget {
      grid-template-columns: 1fr;
  }
  .mapbox {
      height: 430px;
  }
  .member-list {
      max-height: 350px;
  }
  .spots-overview-map {
      grid-template-columns: 1fr;
  }
  .spots-overview-map .mapbox {
      height: 370px;
  }
  .spots-map-sidebar {
      max-height: 290px;
  }
  .grid,
    .grid-2,
    .grid-3,
    .board-grid,
    .gg-widget,
    .rent-grid,
    .spots-overview-map {
      min-width: 0;
  }
}
@media (max-width: 540px) {
  .gg-widget {
      gap: 10px;
  }
  .mapbox {
      height: 370px;
  }
  .spots-overview-map .mapbox {
      height: 300px;
  }
  .gg-local-map {
      min-height: 310px;
  }
}
@media (max-width: 600px) {
  .gg-list-view .member-list {
      grid-template-columns: 1fr;
  }
  .gg-local-map {
      min-height: 310px;
  }
  .gg-map-pin img {
      width: 30px;
      height: 30px;
      border-width: 2px;
  }
  .gg-map-pin span {
      font-size: 8px;
      padding: 3px 5px;
  }
  .gg-map-head {
      left: 9px;
      right: 9px;
      top: 9px;
  }
  .gg-map-head > div {
      padding: 7px 9px;
  }
  .gg-map-head strong {
      font-size: 11px;
  }
  .gg-map-head small {
      font-size: 8px;
  }
  .gg-satellite-switch {
      font-size: 9px;
      padding: 8px;
  }
  .gg-place-label {
      font-size: 7px;
  }
}
```

Legacy, unused map styles (`.map-canvas`, `.map-svg`, `.map-marker*`, `.maplabel`, `.map-controls`) remain in the CSS — safe to drop.

### 3.22 GG Surfer panels

```css
.quickhow {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 15px;
  margin: 19px 0;
}
.quickhow .glass {
  padding: 18px;
}
.quickhow h3 {
  font-size: 16px;
  margin-bottom: 6px;
}
.quickhow p {
  font-size: 12px;
  color: #5a8da8;
  margin: 0;
}
.gg-intent {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 18px;
  margin: 17px 0 15px;
}
.gg-intent h3 {
  font-size: 17px;
  margin: 5px 0 0;
}
.gg-kindness {
  color: #fff;
  padding: 22px 25px;
  display: flex;
  gap: 18px;
  align-items: center;
  justify-content: space-between;
  margin: 24px 0;
}
.gg-kindness .eyebrow {
  color: #b3eaff;
}
.gg-kindness h3 {
  font-size: 21px;
  color: white;
  margin: 4px 0 8px;
}
.gg-kindness p {
  font-size: 12px;
  max-width: 600px;
  margin: 0;
  color: #daf5fd;
}
.gg-kindness .pill-btn {
  background: #fff;
  flex: none;
}
.gg-profile-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 15px;
  margin: 16px 0 0;
  padding: 18px 22px;
  border: 1px solid #cfeaf4;
}
.gg-profile-panel h3 {
  font-size: 16px;
  margin: 3px 0 7px;
}
.gg-profile-panel p {
  font-size: 11px;
  color: #6594a7;
  margin: 0;
}
.gg-profile-panel select {
  border: 1px solid #bce1ed;
  border-radius: 11px;
  background: white;
  color: #0b658b;
  font-size: 12px;
  padding: 11px;
  max-width: 190px;
  width: 100%;
}
.rent-card,
.rose-card,
.achievement,
.rent-filterbar,
.gg-intent,
.gg-kindness {
  border-radius: 12px;
  box-shadow: var(--shadow);
}
.rent-filterbar,
.gg-intent {
  background: #effaff;
  border: 1px solid var(--line);
}
.gg-kindness {
  background: linear-gradient(115deg, #05648a, #0075a3);
}
.club-roadmap,
.gg-profile-panel {
  background: #eaf8fd;
  border-color: var(--line);
  border-radius: 12px;
}
@media (max-width: 540px) {
  .quickhow {
      grid-template-columns: 1fr;
  }
  .gg-intent {
      padding: 14px;
  }
}
@media (max-width: 1100px) {
  .gg-intent {
      flex-direction: column;
      align-items: flex-start;
  }
}
@media (max-width: 810px) {
  .gg-kindness {
      flex-direction: column;
      align-items: flex-start;
  }
}
@media (max-width: 600px) {
  .gg-intent {
      padding: 14px;
  }
  .gg-kindness {
      padding: 19px;
  }
  .gg-kindness h3 {
      font-size: 18px;
  }
  .gg-profile-panel {
      flex-wrap: wrap;
      padding: 14px;
  }
  .gg-profile-panel select {
      max-width: none;
  }
}
@media (max-width: 380px) {
  .gg-intent h3 {
      font-size: 15px;
  }
}
```

### 3.23 Club page

```css
.club-hero {
  padding: 24px;
  background:
    linear-gradient(100deg, #034366e6, #0e89b174),
    var(--mountain-photo) center/cover;
  border-radius: 13px;
  color: #fff;
  margin-bottom: 21px;
}
.club-hero h2 {
  color: #fff;
  font-size: 31px;
}
.club-hero p {
  max-width: 680px;
}
.perk {
  padding: 19px;
}
.perk .emoji {
  font-size: 29px;
}
.perk h3 {
  margin: 11px 0 7px;
}
.perk p {
  font-size: 12px;
  color: #558da8;
}
.rent-profile-panel,
.club-profile-mini {
  background: linear-gradient(115deg, #e9f8fc, #f8fdff);
  border: 1px solid #cfe8f3;
  border-radius: 17px;
  padding: 20px 22px;
  margin: 20px 0 15px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}
.club-profile-mini {
  margin: 0 0 16px;
  justify-content: flex-start;
  background: #fff;
}
.club-profile-mini > div {
  font-size: 25px;
  color: #118eb2;
}
.club-profile-mini > span {
  flex: 1;
  display: grid;
  gap: 5px;
}
.club-profile-mini strong {
  font-size: 13px;
}
.club-profile-mini small {
  font-size: 11px;
  color: #7399ac;
}
.member-club {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.3fr);
  gap: 23px;
  align-items: center;
  margin: 28px 0 35px;
}
.member-card {
  min-height: 235px;
  color: white;
  padding: 23px;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  isolation: isolate;
}
.member-card:after {
  content: "≋";
  position: absolute;
  right: -13px;
  bottom: -92px;
  font-size: 270px;
  color: #bcecff1b;
  line-height: 1;
  z-index: -1;
}
.member-card-top,
.member-card-foot {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  letter-spacing: 0.14em;
  font-size: 10px;
  font-weight: 850;
}
.member-card-foot {
  font-size: 10px;
  color: #c8ecf9;
}
.member-card-name {
  font-size: 22px;
  font-weight: 850;
}
.member-logo {
  font-size: 52px;
  line-height: 0.8;
  color: #9adcf4;
}
.club-invite h2 {
  margin: 6px 0 10px;
  color: #075879;
}
.club-invite p {
  font-size: 13px;
  color: #608b9f;
}
.club-invite .story-actions {
  margin-top: 19px;
}
.achievement-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 15px;
}
.achievement-head > span {
  font-size: 11px;
  color: #7b9cac;
}
.achievement-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  margin: 15px 0 26px;
}
.achievement {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 18px 12px;
  border: 1px solid #d9edf5;
  min-height: 168px;
}
.achievement-symbol {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border-radius: 13px;
  background: #edf4f8;
  color: #9cbac7;
  font-size: 26px;
  margin-bottom: 4px;
}
.achievement strong {
  font-size: 12px;
  color: #60889b;
}
.achievement small {
  font-size: 10px;
  color: #98b0bb;
  line-height: 1.45;
}
.achievement em {
  margin-top: auto;
  font-size: 10px;
  font-style: normal;
  color: #95b0be;
}
.achievement.unlocked {
  background: #e8f9fe;
  border-color: #bce6f4;
}
.achievement.unlocked .achievement-symbol {
  background: #0b80a8;
  color: white;
}
.achievement.unlocked strong {
  color: #045779;
}
.achievement.unlocked em {
  color: #0a9a9d;
  font-weight: 800;
}
.club-roadmap {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  padding: 15px;
  margin-bottom: 28px;
}
.club-roadmap > div {
  padding: 10px;
  border-right: 1px solid #c3e4ef;
  display: grid;
  gap: 6px;
}
.club-roadmap > div:last-child {
  border: 0;
}
.club-roadmap span {
  font-size: 10px;
  font-weight: 800;
  color: #4283a2;
}
.club-roadmap b {
  font-size: 12px;
  color: #075477;
}
.rent-card,
.rose-card,
.achievement,
.rent-filterbar,
.gg-intent,
.gg-kindness {
  border-radius: 12px;
  box-shadow: var(--shadow);
}
.rent-card,
.achievement {
  background: #f9fdff;
  border-color: #d7f0fa;
}
.rental-intro h2,
.club-invite h2 {
  font-size: 25px;
  letter-spacing: -0.65px;
}
.member-card {
  background: linear-gradient(125deg, #05547c, #087ba1);
  border-radius: 14px;
  box-shadow: 0 5px 22px #2f9fc52c;
}
.member-card:after {
  opacity: 0.35;
}
.club-roadmap,
.gg-profile-panel {
  background: #eaf8fd;
  border-color: var(--line);
  border-radius: 12px;
}
.achievement-grid {
  gap: 13px;
}
@media (max-width: 810px) {
  .member-club {
      grid-template-columns: 1fr;
  }
  .achievement-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 600px) {
  .member-card {
      min-height: 208px;
  }
  .achievement-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 9px;
  }
  .achievement {
      min-height: 145px;
      padding: 13px;
  }
  .club-roadmap {
      grid-template-columns: 1fr;
  }
  .club-roadmap > div {
      border-right: 0;
      border-bottom: 1px solid #c3e4ef;
  }
  .rent-profile-panel,
    .club-profile-mini {
      flex-wrap: wrap;
      padding: 15px;
  }
  .club-profile-mini > .pill-btn {
      width: 100%;
  }
}
@media (max-width: 540px) {
  .member-card {
      min-height: 205px;
  }
}
```

### 3.24 Spot «propose change» form (pencil)

```css
.gv-spot-edit-trigger:focus-visible,
.gv-wind-choice:focus-visible {
  outline: 3px solid #70c4e5;
  outline-offset: 2px;
}
.gv-spot-my-suggestions {
  display: inline-flex;
  gap: 6px;
  align-items: center;
}
.gv-spot-queue-count:empty {
  display: none;
}
.gv-spot-queue-count:not(:empty) {
  padding: 0 6px;
  border-radius: 20px;
  background: #dcf4ff;
  color: #006087;
  font-size: 11px;
}
.gv-spot-edit-modal {
  padding: 25px 26px 22px;
}
.gv-spot-edit-head {
  display: flex;
  align-items: center;
  gap: 16px;
  margin: 0 28px 18px 0;
}
.gv-spot-edit-head > img {
  width: 82px;
  height: 82px;
  flex: 0 0 82px;
  object-fit: cover;
  border-radius: 13px;
  border: 1px solid #bce8f6;
}
.gv-spot-overline {
  font-size: 10px;
  letter-spacing: 1.5px;
  color: #2989af;
  font-weight: 900;
}
.gv-spot-edit-head h2,
.gv-spot-success h2 {
  font-size: 25px;
  color: #07547e;
  margin: 4px 0 4px;
  letter-spacing: -0.4px;
}
.gv-spot-edit-head p {
  margin: 0;
  font-size: 13px;
}
.gv-spot-explain {
  display: flex;
  gap: 10px;
  background: linear-gradient(115deg, #edfaff, #f7fdff);
  border: 1px solid #c9e9f6;
  border-radius: 12px;
  padding: 12px 13px;
  margin-bottom: 20px;
  color: #1b628a;
}
.gv-spot-explain strong {
  display: block;
  font-size: 12px;
  margin-bottom: 3px;
}
.gv-spot-explain small {
  font-size: 11px;
  color: #5b90a8;
  line-height: 1.55;
  display: block;
}
.gv-spot-explain-ic {
  flex: 0 0 26px;
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  background: #cdeffc;
  border-radius: 50%;
  font-weight: 900;
  color: #006895;
}
.gv-spot-section-head {
  display: flex;
  align-items: center;
  gap: 11px;
  margin: 22px 0 12px;
  padding-top: 18px;
  border-top: 1px solid #deeff5;
}
.gv-spot-section-num {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  flex: none;
  border-radius: 10px;
  background: #e4f5fc;
  color: #077aa7;
  font-weight: 900;
  font-size: 12px;
}
.gv-spot-section-head h3 {
  font-size: 15px;
  margin: 0 0 2px;
  color: #07577f;
}
.gv-spot-section-head small,
.gv-spot-muted {
  font-size: 11px;
  color: #6c95a9;
  font-weight: 400;
}
.gv-spot-formgrid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 15px;
}
.gv-spot-field {
  display: block;
}
.gv-spot-edit-modal .field {
  font-size: 12px;
  color: #215f81;
  min-width: 0;
}
.gv-spot-edit-modal input,
.gv-spot-edit-modal textarea,
.gv-spot-edit-modal select {
  border: 1px solid #c6e7f3 !important;
  background: #fff !important;
  border-radius: 9px !important;
  padding: 10px 11px;
  color: #174967;
  min-width: 0;
  box-shadow: none;
}
.gv-spot-edit-modal input:focus,
.gv-spot-edit-modal textarea:focus,
.gv-spot-edit-modal select:focus {
  outline: none;
  border-color: #45acd6 !important;
  box-shadow: 0 0 0 3px #c7efff9c;
}
.gv-spot-label-hint {
  display: block;
  font-size: 10px;
  color: #76a0b4;
  font-weight: 400;
}
.gv-spot-wind-box {
  border: 1px solid #cce9f5;
  background: #f4fbfe;
  padding: 15px;
  border-radius: 12px;
  margin-bottom: 15px;
}
.gv-spot-wind-title {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
  margin-bottom: 6px;
}
.gv-spot-wind-title span {
  font-size: 13px;
  font-weight: 800;
}
.gv-spot-wind-title strong {
  font-size: 12px;
  border-radius: 30px;
  background: #d7f2ff;
  padding: 5px 11px;
  color: #006894;
}
.gv-spot-winds {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 6px;
  margin: 13px 0 10px;
}
.gv-wind-choice {
  min-height: 35px;
  padding: 5px 6px;
  border: 1px solid #b8deed;
  background: white;
  color: #28769a;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 700;
  white-space: normal;
  line-height: 1.2;
}
.gv-wind-choice.is-picked {
  background: #087eaa;
  color: #fff;
  border-color: #087eaa;
  box-shadow: 0 4px 10px #0d96c225;
}
.gv-spot-other-wind {
  margin: 5px 0 0 !important;
}
.gv-spot-other-wind input {
  margin-top: 5px !important;
}
.gv-spot-review {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 17px;
  border: 1px solid #cae7f3;
  border-radius: 12px;
  background: linear-gradient(100deg, #e9f8fe, #fbfeff);
  padding: 12px;
}
.gv-spot-review > div {
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  column-gap: 9px;
  min-width: 0;
}
.gv-spot-review-icon {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: white;
  display: grid;
  place-items: center;
  color: #047da9;
  font-size: 17px;
  grid-row: span 2;
}
.gv-spot-review strong {
  font-size: 12px;
  line-height: 1.4;
}
.gv-spot-review small {
  font-size: 11px;
  color: #5489a3;
  overflow-wrap: anywhere;
}
.gv-spot-review-status {
  border: 1px solid #aedbeb;
  border-radius: 20px;
  padding: 5px 9px;
  font-size: 10px;
  white-space: nowrap;
  color: #0674a0;
  background: white;
}
.gv-spot-form-actions {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 10px;
  margin: 15px 0 0;
}
.gv-spot-form-actions .pill-btn,
.gv-spot-form-actions .primary {
  min-height: 41px;
}
.gv-spot-privacy {
  font-size: 11px !important;
  margin: 14px 0 0 !important;
  line-height: 1.55 !important;
  color: #7796a7 !important;
}
.gv-spot-success {
  text-align: center;
}
.gv-spot-success-mark {
  width: 60px;
  height: 60px;
  margin: 0 auto 12px;
  border-radius: 50%;
  background: #ddf5ff;
  color: #0077a1;
  display: grid;
  place-items: center;
  font-size: 31px;
}
.gv-spot-success > p {
  margin: 12px auto 20px;
  max-width: 430px;
}
.gv-spot-success-number {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
  background: #f2fbff;
  border: 1px solid #d8eef7;
  border-radius: 12px;
  padding: 13px;
  margin: 15px 0;
  font-size: 12px;
  color: #587d97;
}
.gv-spot-success-number strong {
  font-size: 13px;
  color: #08648b;
}
.gv-spot-success .gv-spot-explain {
  text-align: left;
}
.gv-spot-queue-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  border: 1px solid #d4ebf5;
  border-radius: 11px;
  padding: 13px 14px;
  margin: 10px 0;
  background: #f5fcff;
}
.gv-spot-queue-item h3 {
  font-size: 15px;
  margin: 5px 0 2px;
}
.gv-spot-queue-item small {
  font-size: 11px;
  color: #79a0b1;
}
.gv-spot-queue-item p {
  margin: 6px 0 0;
  font-size: 12px;
}
.gv-spot-queue-status {
  border-radius: 20px;
  padding: 3px 8px;
  font-size: 10px;
  color: #8c6e24;
  background: #fff5d9;
}
.gv-spot-empty {
  padding: 24px;
  border: 1px dashed #cde5ef;
  border-radius: 12px;
  text-align: center;
  color: #7da2b6;
}
@media (max-width: 640px) {
  .gv-spot-edit-modal {
      padding: 18px 14px;
  }
  .gv-spot-edit-head {
      gap: 10px;
      margin-right: 20px;
  }
  .gv-spot-edit-head > img {
      width: 66px;
      height: 66px;
      flex-basis: 66px;
  }
  .gv-spot-edit-head h2 {
      font-size: 20px;
  }
  .gv-spot-formgrid {
      grid-template-columns: minmax(0, 1fr);
      gap: 0;
  }
  .gv-spot-winds {
      grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .gv-spot-form-actions > * {
      flex: 1 1 130px;
  }
  .gv-spot-review {
      align-items: flex-start;
      flex-direction: column;
  }
  .gv-spot-queue-item {
      align-items: flex-start;
      flex-direction: column;
  }
  .gv-spot-section-head small {
      font-size: 10px;
  }
}
```

### 3.25 Chat, inbox, orders (entry points reachable from public pages)

```css
.chat-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.chat-thread {
  background: linear-gradient(130deg, #f0faff, #e1f5fb);
  height: 270px;
  overflow: auto;
  padding: 15px;
  border-radius: 12px;
  margin: 12px 0 18px;
}
.chat-bubble {
  padding: 11px 14px;
  border-radius: 15px 15px 15px 4px;
  background: #fff;
  color: #286c8a;
  width: fit-content;
  max-width: 82%;
  margin: 8px 0;
  font-size: 13px;
  overflow-wrap: anywhere;
  box-shadow: 0 1px 4px #4e9dbc16;
}
.chat-bubble.mine {
  margin-left: auto;
  background: #c8eaf9;
  border-radius: 15px 15px 4px 15px;
}
.chat-welcome {
  text-align: center;
  padding: 64px 8px;
  color: #5a9dbc;
  font-size: 13px;
}
.inbox-item {
  width: 100%;
  display: flex;
  gap: 12px;
  align-items: center;
  text-align: left;
  border: 0;
  border-bottom: 1px solid #e1f0f7;
  padding: 12px 0;
  background: transparent;
  color: #165f81;
}
.inbox-item > span:nth-child(2) {
  flex: 1;
}
.inbox-item small {
  display: block;
  color: #6594ab;
}
.inbox-item:hover {
  background: #e9f7fc;
}
.order-item {
  border: 1px solid #c8e6f2;
  border-radius: 12px;
  padding: 15px;
  background: #f8fdff;
  margin: 12px 0;
}
.order-item p {
  margin: 8px 0;
  color: #4589a6;
}
.order-head {
  display: flex;
  gap: 12px;
  justify-content: space-between;
  align-items: center;
}
.order-status {
  font-size: 11px;
  border-radius: 16px;
  background: #e5f0f6;
  padding: 4px 9px;
  color: #577889;
  white-space: nowrap;
}
.order-status.accepted {
  background: #e0f7ed;
  color: #18755e;
}
.order-status.completed {
  background: #e8eeff;
  color: #3860a0;
}
@media (max-width: 540px) {
  .chat-heading {
      flex-direction: column;
  }
  .order-head {
      flex-direction: column;
      align-items: flex-start;
  }
}
```

### 3.26 Footer

`footer.footer` — landscape photo (`--footer-image` = `assets/ui/footer-landscape.webp`, positioned `center 65%`) under a white→aqua gradient, 48px top fade; content: logo 132×76 (white drop-shadow), white rounded nav pill with 6 links, decorative glyphs «◉ ◈ ≋», right-aligned copyright 10px. ≤540px: stacks left-aligned, min-height 340px.

```css
.footer {
  position: relative;
  margin-top: 52px;
  color: #0b5d8b;
}
.footer:before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
}
.footer-inner {
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 30px;
}
.footer nav {
  display: flex;
  gap: 22px;
  flex-wrap: wrap;
  font-size: 12px;
}
.footer-bottom {
  margin-top: 24px;
  font-size: 10px;
  text-align: right;
}
.footer {
  min-height: 270px;
  padding: 95px 0 26px;
  background:
    linear-gradient(0deg, #c4e9f0b5 0%, #effaff80 58%, #ffffff35 100%),
    var(--footer-image) center 65% / cover no-repeat;
}
.footer:before {
  height: 48px;
  background: linear-gradient(#edfaff, #edfaff00);
}
.footer nav {
  background: #ffffffe3;
  border-radius: 9px;
  padding: 10px 13px;
}
.footer-bottom {
  color: #1c6180;
  text-shadow: 0 1px 3px white;
}
.footer-inner .logo {
  filter: drop-shadow(0 2px 5px white);
}
.footer a {
  font-weight: 700;
}
.footer .logo img {
  width: 132px;
  height: 76px;
  max-width: none;
  border-radius: 0;
  object-fit: contain;
}
body,
#app,
.topbar,
.footer {
  min-width: 0;
}
@media (max-width: 540px) {
  .footer-inner {
      flex-direction: column;
      align-items: flex-start;
  }
  .footer-bottom {
      text-align: left;
  }
  .footer {
      min-height: 340px;
  }
}
@media (max-width: 810px) {
  .footer {
      background-position: center center;
  }
}
```

### 3.27 Site loader

Full-screen overlay `#siteLoader.site-loader` with the animated SVG (`icons.json → loader-art`), brand «ГДЕВОЛНА.РФ» (23px/900, ls 2px, `#05638a`) and caption «До встречи на волне». Hidden 650 ms after `window.load` (fallback 2.4 s) by adding `.is-hidden` (opacity/visibility transition .65 s). In Next.js use it only as an initial splash (or drop it — TZ UX-13 wants per-screen loading states instead).

```css
.site-loader {
  position: fixed;
  inset: 0;
  z-index: 999;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 2px;
  background: linear-gradient(145deg, #f5fcff, #dff3fc);
  transition:
    opacity 0.65s,
    visibility 0.65s;
}
.site-loader.is-hidden {
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
}
.loader-art {
  width: 330px;
  max-width: 87vw;
}
.loader-brand {
  font-size: 23px;
  color: #05638a;
  font-weight: 900;
  letter-spacing: 2px;
}
.loader-caption {
  font-size: 12px;
  color: #4994b3;
}
.smoke-smile {
  animation: smoke 2.6s ease-in-out infinite;
  transform-origin: 155px 25px;
}
.surfer-svg {
  animation: surferRide 2s ease-in-out infinite;
  transform-origin: 190px 105px;
}
.surfwave {
  stroke-dasharray: 55 16;
  animation: waveRun 2s linear infinite;
}
@media (prefers-reduced-motion: reduce) {
  .smoke-smile,
    .surfer-svg,
    .surfwave,
    .live-dot {
      animation: none !important;
  }
}
```
```css
@keyframes smoke {
  50% {
    transform: translateY(-9px);
    opacity: 0.35;
  }
}
@keyframes surferRide {
  50% {
    transform: translate(13px, -4px) rotate(-5deg);
  }
}
@keyframes waveRun {
  to {
    stroke-dashoffset: -142;
  }
}
```

### 3.28 Shapers shell (iframe wrapper on the public «Шейперы» page)

```css
.gv-shaper-integrated {
  margin: 18px auto 34px;
  min-width: 0;
}
.gv-shaper-integrated-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 14px;
  margin-bottom: 12px;
}
.gv-shaper-integrated-head h2 {
  font-size: 23px;
  margin: 0 0 6px;
  color: var(--navy);
}
.gv-shaper-integrated-head p {
  color: #6897af;
  font-size: 13px;
  margin: 0;
  line-height: 1.45;
}
.gv-shaper-frame {
  display: block;
  width: 100%;
  height: min(1100px, calc(100dvh - 115px));
  min-height: 650px;
  background: #f7fcff;
  border: 1px solid #ceeaf7;
  border-radius: 16px;
  box-shadow: 0 8px 30px #00699b14;
}
.gv-shaper-frame:focus-visible {
  outline: 3px solid #65b9e8;
  outline-offset: 2px;
}
.gv-shapers-status {
  margin: 0 0 8px;
  color: #7a9caf;
  font-size: 12px;
}
@media (max-width: 810px) {
  .gv-shaper-integrated {
      width: 100%;
      margin: 12px auto 28px;
  }
  .gv-shaper-integrated-head h2 {
      font-size: 19px;
  }
  .gv-shaper-frame {
      min-height: 570px;
      height: calc(100dvh - 155px);
      border-radius: 12px;
  }
}
@media (max-width: 370px) {
  .gv-shaper-integrated-head {
      padding: 0 2px;
  }
  .gv-shaper-frame {
      min-height: 500px;
      height: calc(100dvh - 145px);
  }
}
@media (max-width: 340px) {
  .gv-shaper-integrated-head h2 {
      font-size: 18px;
  }
}
```

### 3.29 Misc. legacy blocks still present in CSS

`.board-grid/.board` (old shapers model row), `.profile-banner`, `.avatar`, `.account-sections`, `.settings-card`, `.post-card`, `.demo-ribbon`, `.feeling`, `.tabs/.tab` — not visible on the final public screens (cabinet/legacy); kept in `prototype-public.css` for completeness.

---

## 4. Porting notes

1. **Global vs modules**: put tokens + base + buttons/tags/fields/modal/toast in a global stylesheet (they are used everywhere); page-specific blocks (rentals, club, GG map, spot form) can become CSS modules with the same class names.
2. **Do not copy the `!important` noise blindly** — they exist only to override earlier prototype layers. In the consolidated file the cascade is already resolved; when splitting into modules keep the final values and drop `!important` where no override remains (exceptions: `.like-btn.active` colours, `#app select` arrow rules — keep until you have one select component).
3. **Icons**: replace Unicode glyph icons with the SVG set (icons.json) at one stroke width (TZ UX-04).
4. **Images**: hero/banner/footer backgrounds are set through CSS variables in inline styles; in React pass them via `style={{'--hero-photo': `url(${src})`}}` or use `next/image` with `fill` + the same gradients as overlays (TZ UX-16: WebP/AVIF, lazy-loading).
5. **Accessibility**: like buttons need `aria-pressed`; toggles `role=switch`; tabs `role=tab/aria-selected`; modal focus trap; contrast of the light secondary text on `#f9fdff` is below WCAG AA for small copy (TZ UX-14): `#6398af` ≈3.1:1, `#5d8dac` (`--muted`) ≈3.5:1, `#7da2b6` ≈2.7:1, `#94afbd` ≈2.3:1 (body `#0c517a` is 8.3:1). Darken secondary text to ≈`#44738c` (≥4.5:1 on white and on `#e8f7fc`) when porting.
