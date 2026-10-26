# ГДеволна — images of the prototype: inventory and classification

Source files: `docs/prototype/source/img/imgNN.*` (base64 images extracted from the prototype).
Copies with meaningful names: `docs/prototype/frontend-port/assets/` (paths below are relative to that folder).
Classification follows TZ 12.2 («посевные данные / данные пользователя / не переносить») plus a
"бренд/UI" class for site chrome. TZ PL-02: demo avatars, reviews, statistics, certificates must never
become real production records.

Folder layout:

```
assets/brand/   logo files (бренд/UI)
assets/ui/      hero, banner, footer and home-feature photos (бренд/UI — temporary, see notes)
assets/seed/spots/   spot photos (посевные данные, rights to be confirmed)
assets/demo/avatars/ fictional instructor portraits (не переносить в прод; dev/staging fixtures only)
```

## Byte-identical duplicates (deduplicated)

| Group (md5) | Files | Kept as |
|---|---|---|
| `dbc13c4b…` | `img01.png` (header logo) = `img02.png` (footer logo) | `brand/logo.png` |
| `a2995d0a…` | `img20.webp` = `img23.webp` = `img29.webp` (shapers module) | not copied (shapers) |
| `6051faf0…` | `img25.jpg` = `img26.jpg` = `img27.jpg` = `img30.jpg` (shapers module) | not copied (shapers) |

## Public-site images

| New name | Original | What it shows | Where used in the prototype | Classification |
|---|---|---|---|---|
| `brand/logo.png` | img01.png, img02.png (448×248, PNG α) | Logo: blue map of Russia with red pin, lettering «ГДЕ ВОЛНА.РФ» (soft/blurry raster) | Header `.logo img` 108×61 (103×59 ≤810, 90×52 ≤540); footer 132×76 | бренд/UI |
| `brand/logo-hq.png` | img24.png (482×365, PNG α) | Same logo, sharper lettering «ГДЕВОЛНА.РФ», bigger pin | Only inside the shapers sub-document; recommended source for the new site (request a vector SVG from the designer) | бренд/UI |
| `ui/footer-landscape.webp` | img03.webp (1800×600) | Panorama: snowy volcanoes, ocean waves | Footer background (`--footer-image`, `center 65%/cover`, under a light gradient) | бренд/UI |
| `ui/hero-home.webp` | img04.webp (1160×416) | Surfer in wetsuit with board on rocks, snowy mountains, back view | Hero of Главная, GG Surfer, guest «Личный кабинет» (`--hero-photo`) | бренд/UI |
| `ui/hero-catalog.webp` | img05.webp (1160×416) | Surfer riding a wave, volcano behind | Hero of Инструкторы, Споты, Аренда, Шейперы (`.hero.people`, `--people-photo`) | бренд/UI |
| `ui/banner-mountains-volny-vezde.webp` | img06.webp (1170×278) | Mountain lake/sea with rocky island; **baked-in handwritten text «Волны везде!» + squiggle** at right | `.wide-banner` (bottom of home/spots/GG/rentals; club «Здесь никто не чужой»), `.club-hero` | бренд/UI (text is part of the artwork — keep it on the right, don't put copy over it) |
| `ui/about-intro-surfer.webp` | img07.webp (714×514) | Surfer with board on a beach, mountains; **left edge contains cropped text of an older mock-up** («…ех, …ном месте, …укторах, …ждого, …овня») hidden by the white gradient | Home «О сайте» block background (`--intro-photo`, right/59%) | бренд/UI — **replace with a clean photo** (artefacts visible on mobile where gradient is lighter) |
| `ui/feature-volcano-coast.webp` | img08.webp (412×198) `volcano` | Volcano over a rocky coast at sunset | Home feature «Каталог сёрф-инструкторов»; quote card «Сёрфинг — это способ…» | бренд/UI (white circle artefact bottom-left from the old mock-up; covered by the float-icon) |
| `ui/feature-map-thumb.webp` | img18.webp (400×202) `mapThumb` | Map of Europe with blue pins (generic web map screenshot) | Home feature «Карта сёрф-спотов» | не переносить (map of Europe, not Russia; looks like a third-party map screenshot) — replace with own map illustration |
| `ui/feature-coast-aerial.webp` | img09.webp (376×196) `wave` | Aerial view of a cliffy coast with surf | Home feature «GG Surfer»; also the JS fallback image `ASSET.wave` | бренд/UI (circle artefact bottom-left) |
| `ui/feature-shaper-workshop.webp` | img12.webp (486×306) `shaper` | Shaper sanding a board in a workshop; **baked-in cropped text «…шейперов», «…ощие доски под ваш стиль», a button «…шейпров →»** | Home feature «Каталог шейперов»; old shapers page block | не переносить — crop of an older banner with text; replace |
| `ui/feature-mountain-lake.webp` | img10.webp (638×170) `coast` | Snowy peak over a lake at dusk | Home feature «Сёрф-клуб» | бренд/UI (circle artefact bottom-left) |
| `ui/feature-barrel-surfer.webp` | img11.webp (600×170) `wave2` | Surfer inside a barrel wave | Home feature «Аренда снаряжения» | бренд/UI (circle artefact bottom-left) |
| `demo/avatars/avatar-instructor-aleksey-morozov.webp` | img13.webp (600×306) `p0` | AI-generated bearded man in black jacket with board, volcano | Instructor «Алексей Морозов» card/modal, GG pin & list; also default avatar of any locally created instructor | не переносить (fictional person; AI artefacts: blurred patches, "∞" watermark bottom-right) |
| `demo/avatars/avatar-instructor-mariya-volkova.webp` | img14.webp (570×306) `p1` | AI woman in beanie on a snowy field | «Мария Волкова» | не переносить |
| `demo/avatars/avatar-instructor-dmitriy-kovalev.webp` | img15.webp (600×306) `p2` | AI man in wetsuit, Crimean-like cliffs | «Дмитрий Ковалев» | не переносить |
| `demo/avatars/avatar-instructor-ekaterina-sokolova.webp` | img16.webp (600×294) `p3` | AI woman in wetsuit, rocky coast | «Екатерина Соколова» | не переносить |
| `demo/avatars/avatar-instructor-ivan-petrov.webp` | img17.webp (568×294) `p4` | AI bearded man in beanie with board, volcanoes | «Иван Петров» | не переносить |
| `demo/avatars/avatar-instructor-anna-lebedeva.webp` | img19.webp (598×294) `p5` | AI woman with board, cliffs | «Анна Лебедева» (not GG) | не переносить |
| `seed/spots/spot-zaliv-anglichanka-1.jpg` | img37.jpg (550×324) `spot_user_01` | Surfer on a green wave, overcast | Cover + gallery #1 of «Залив Англичанка» | посевные данные (seed) — confirm author/licence |
| `seed/spots/spot-zaliv-anglichanka-2.jpg` | img38.jpg (445×285) | Surfer on a small clean wave | Gallery #2 «Залив Англичанка» | seed — confirm licence |
| `seed/spots/spot-khalaktyrskiy-plyazh-1.jpg` | img42.jpg (1280×854) `spot_user_06` | Two boards on snowy black-sand beach, waves, volcano range | Cover + gallery #1 «Халактырский пляж» | seed — confirm licence (high quality, good cover) |
| `seed/spots/spot-khalaktyrskiy-plyazh-2.jpg` | img43.jpg (960×720) | Line-up: wave with surfers paddling | Gallery #2 «Халактырский пляж» | seed — confirm licence |
| `seed/spots/spot-khalaktyrskiy-plyazh-3.jpg` | img47.jpg (1280×720) | Surfer in hood on a big green wave | Gallery #3 «Халактырский пляж» | seed — confirm licence |
| `seed/spots/spot-ladozhskie-shkhery-1.jpg` | img48.jpg (1274×786) | Rocky breakwater, choppy grey water (Street-View-like) | Cover + gallery #1 «Ладожские шхеры» | seed — **source looks like Google Maps/Street View user photo → rights unclear**, verify the place |
| `seed/spots/spot-ladozhskie-shkhery-2.jpg` | img49.jpg (435×300) | Surfer on a small choppy wave | Gallery #2 «Ладожские шхеры» | seed — confirm licence |
| `seed/spots/spot-olenevka-1.jpg` | img39.jpg (1234×782) | White lighthouse (Tarkhankut-like) behind a rocky shore | Cover + gallery #1 «Оленевка» | seed — Street-View-like, rights unclear |
| `seed/spots/spot-olenevka-2.jpg` | img40.jpg (1067×826) | Overcast stony shore, lighthouse far away | Gallery #2 «Оленевка» | seed — Street-View panorama look, rights unclear |
| `seed/spots/spot-olenevka-3.jpg` | img41.jpg (1129×791) | Red-soil cliff edge over calm sea, overcast | Gallery #3 «Оленевка» | seed — rights unclear |
| `seed/spots/spot-poberezhye-sakhalina-1.jpg` | img45.jpg (1200×762) `spot_user_09` | **Grounded container ship with MAERSK/Hamburg Süd containers** in surf near a town | Cover + gallery #1 «Побережье Сахалина» | не переносить as cover (news photo with third-party brands; not a surf view). Keep only if rights + editorial reason |
| `seed/spots/spot-poberezhye-sakhalina-2.jpg` | img46.jpg (800×455) | Surfer on a wave, red fishing vessel behind | Gallery #2 «Побережье Сахалина» | seed — confirm licence (better candidate for cover) |
| `seed/spots/spot-poberezhye-primorya-1.jpg` | img44.jpg (1280×854) `spot_user_08` | Backlit surfer in a big glassy green barrel | Cover + gallery #1 «Побережье Приморья» | seed — confirm the photo is really from Primorye + licence |
| `seed/spots/spot-poberezhye-primorya-2.jpg` | img50.jpg (857×509) | Surfer on a turquoise wave near a concrete tetrapod breakwater | Gallery #2 «Побережье Приморья» | seed — confirm licence |

Spot gallery captions are positional, not per-photo: #1 «Общий вид спота», #2 «Линия волны и берег», #3+ «Дополнительный ракурс» — store real captions per photo in the backend.

Before the gallery script ran, spots used generic images (`coast`, `volcano`, `p1` = Maria's portrait (!), `wave`, `coast`, `wave2`); those were overridden and are listed in `seed_public.json → spots[].photos.prototypePlaceholderBeforeGallery` only for traceability.

Rental cards have **no photos** (inline SVG illustrations, see `icons.json`): the `img` field of `RENTALS` (`wave2`, `p0`, …) is never rendered.

## Shapers module images (handled by the shapers documentation — not copied here)

| Original | What it is |
|---|---|
| img20.webp (= img23, img29; 820×500) | Snowy volcano over the ocean (shapers-module imagery; exact usage — see shapers docs) |
| img21.webp, img22.webp (1800×420) | Dark-tinted composite banner: surfer on the shore + shaper's face (shapers hero, two variants; img22 also has board silhouettes) |
| img24.png (482×365) | High-resolution logo — **copied** as `brand/logo-hq.png` |
| img25.jpg (= img26, img27, img30; 400×400) | Square crop of the bearded-man portrait with black bar at the bottom (shaper avatar placeholder) |
| img28.webp (740×500) | Blurry crop of the shaper-in-workshop photo |
| img31–img36.png (340×600, α) | Surfboard renders: wood-veneer longboard (31, 36), blue shortboard (32), cream longboard (33), others — shaper model images |

## Images that are not files

* Loader art, empty-state illustration, rental board/wetsuit art, GG schematic map land, wind/swell roses, welcome sticker — inline SVG, see `frontend-port/icons.json`.
* Yandex Maps — live iframes (`yandex.ru/map-widget/v1/…`), not images. In the sandboxed screenshot run the map tiles sometimes stayed blank.
