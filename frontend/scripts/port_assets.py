"""Copy brand/UI images allowed by ASSETS.md into frontend/public and generate SVG art from icons.json."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root
PORT = ROOT / "docs/prototype/frontend-port"
PUB = ROOT / "frontend/public"
(PUB / "brand").mkdir(parents=True, exist_ok=True)
(PUB / "ui/boards").mkdir(parents=True, exist_ok=True)

icons = json.loads((PORT / "icons.json").read_text())["icons"]

# brand
for f in ["logo.png", "logo-hq.png"]:
    shutil.copy2(PORT / "assets/brand" / f, PUB / "brand" / f)

# ui — бренд/UI only; «не переносить» (feature-map-thumb, feature-shaper-workshop) are replaced by SVG art below
for f in [
    "footer-landscape.webp", "hero-home.webp", "hero-catalog.webp", "banner-mountains-volny-vezde.webp",
    "about-intro-surfer.webp", "feature-volcano-coast.webp", "feature-coast-aerial.webp",
    "feature-mountain-lake.webp", "feature-barrel-surfer.webp",
]:
    shutil.copy2(PORT / "assets/ui" / f, PUB / "ui" / f)
# clean landscape used by the shapers module background (prototype img20 = img23)
shutil.copy2(ROOT / "docs/prototype/source/img/img20.webp", PUB / "ui/shapers-landscape.webp")
# generated board silhouettes (shapers module, one per board type)
for p in PORT.glob("assets/shaper-board-*.svg"):
    shutil.copy2(p, PUB / "ui/boards" / p.name.replace("shaper-board-", ""))

# loader (brand art) — standalone animated SVG
loader = icons["loader-art"]["inner"]
(PUB / "brand/loader.svg").write_text(f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 330 165" role="img" aria-label="Гдеволна.рф">
<style>
.smoke-smile{{animation:smoke 2.6s ease-in-out infinite;transform-origin:155px 25px}}
.surfer-svg{{animation:surferRide 2s ease-in-out infinite;transform-origin:190px 105px}}
.surfwave{{stroke-dasharray:55 16;animation:waveRun 2s linear infinite}}
@keyframes smoke{{50%{{transform:translateY(-9px);opacity:.35}}}}
@keyframes surferRide{{50%{{transform:translate(13px,-4px) rotate(-5deg)}}}}
@keyframes waveRun{{to{{stroke-dashoffset:-142}}}}
@media (prefers-reduced-motion:reduce){{.smoke-smile,.surfer-svg,.surfwave{{animation:none}}}}
</style>
{loader}
</svg>
""")

# empty-state illustration
es = icons["empty-surfers"]
(PUB / "ui/empty-surfers.svg").write_text(
    f'<svg xmlns="http://www.w3.org/2000/svg" width="158" height="94" viewBox="{es["viewBox"]}">{es["inner"]}</svg>\n')

# rental art (no-photo fallbacks for rental cards)
for name in ["rental-wetsuit", "rental-board-long", "rental-board-short"]:
    v = icons[name]
    (PUB / f"ui/{name}.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{v["viewBox"]}">{v["inner"]}</svg>\n')

# replacement for «не переносить» feature-map-thumb (map of Europe): own schematic map of Russia's coasts
land_path = "M32 40L120 48L150 92L220 67L277 109L332 91L386 111L454 75L518 114L579 96L638 133L685 114L767 143L824 124L887 173L870 236L816 221L778 281L726 267L673 301L618 283L566 337L509 311L466 360L405 321L363 358L309 312L261 333L213 297L156 310L123 267L85 260L69 199L26 160Z"


def pin(x, y, color="#0a83ad", ring="#ffffff", scale=1.0):
    return (f'<g transform="translate({x} {y}) scale({scale})">'
            f'<path d="M0 0C-10-12-16-20-16-28a16 16 0 1 1 32 0C16-20 10-12 0 0Z" fill="{color}" stroke="{ring}" stroke-width="3"/>'
            f'<circle cx="0" cy="-28" r="6" fill="#fff"/></g>')


map_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 400" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Схематичная карта сёрф-спотов России">
<defs>
<linearGradient id="w" x1="0" x2="0" y1="0" y2="1"><stop stop-color="#d6f0f8"/><stop offset="1" stop-color="#aee0ee"/></linearGradient>
<linearGradient id="l" x1="0" x2="1" y1="0" y2="1"><stop stop-color="#e8f3f1"/><stop offset="1" stop-color="#cfe3e6"/></linearGradient>
<pattern id="g" width="60" height="60" patternUnits="userSpaceOnUse"><path d="M60 0H0V60" fill="none" stroke="#ffffff" stroke-opacity=".55" stroke-width="1.5"/></pattern>
</defs>
<rect width="900" height="400" fill="url(#w)"/><rect width="900" height="400" fill="url(#g)"/>
<g transform="translate(0 -20)"><path d="{land_path}" fill="url(#l)" stroke="#8bc3d5" stroke-width="3"/>
<path d="M140 130Q290 142 408 240T770 200" stroke="#b3ced7" stroke-width="6" fill="none" stroke-dasharray="2 16" opacity=".8"/></g>
<path d="M0 372Q180 340 338 380T900 365" fill="none" stroke="#ffffff" stroke-width="10" opacity=".55"/>
<path d="M150 236Q330 300 520 250T840 210" fill="none" stroke="#0a83ad" stroke-width="3" stroke-dasharray="7 9" opacity=".55"/>
{pin(150, 236)}{pin(300, 300, scale=.85)}{pin(520, 250)}{pin(700, 262, scale=.85)}{pin(840, 210, color="#f86189")}
</svg>
"""
(PUB / "ui/feature-map-russia.svg").write_text(map_svg)

# replacement for «не переносить» feature-shaper-workshop (crop with baked-in text): boards in a workshop rack
boards = {
    "longboard": "#c69b64", "fish": "#28acc4", "shortboard": "#e9f6fb", "funboard": "#0a83ad", "gun": "#f2d0a4",
}
paths = {}
for p in PORT.glob("assets/shaper-board-*.svg"):
    t = p.read_text()
    d = t.split('<path d="', 1)[1].split('"', 1)[0]
    paths[p.stem.replace("shaper-board-", "")] = d
items = []
x = 120
for i, (name, color) in enumerate(boards.items()):
    d = paths.get(name) or paths["shortboard"]
    rot = [-7, -3, 2, 5, 9][i]
    items.append(
        f'<g transform="translate({x} 40) rotate({rot} 50 130) scale(1.18)">'
        f'<path d="{d}" fill="{color}" stroke="#377c9c" stroke-opacity=".45" stroke-width="1.6"/>'
        f'<path d="M50 14 L50 242" stroke="#fff" stroke-opacity=".6" stroke-width="1.6"/></g>')
    x += 140
shaper_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 400" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Доски ручной работы в мастерской">
<defs>
<linearGradient id="bg" x1="0" x2="1" y1="0" y2="1"><stop stop-color="#f5fcff"/><stop offset="1" stop-color="#d5eef8"/></linearGradient>
<linearGradient id="bench" x1="0" x2="0" y1="0" y2="1"><stop stop-color="#0b587f"/><stop offset="1" stop-color="#064c73"/></linearGradient>
</defs>
<rect width="900" height="400" fill="url(#bg)"/>
<g stroke="#cfe8f2" stroke-width="2">{''.join(f'<path d="M0 {y}H900"/>' for y in range(40, 330, 48))}</g>
<path d="M90 70 L810 70" stroke="#8bc3d5" stroke-width="6" stroke-linecap="round"/>
{''.join(items)}
<rect x="0" y="340" width="900" height="60" fill="url(#bench)"/>
<path d="M0 340H900" stroke="#ffffff" stroke-opacity=".35" stroke-width="3"/>
<g fill="#f6fcff" opacity=".7"><circle cx="760" cy="300" r="5"/><circle cx="776" cy="292" r="3"/><circle cx="748" cy="288" r="2.5"/></g>
</svg>
"""
(PUB / "ui/feature-shaper-boards.svg").write_text(shaper_svg)

# favicon from the brand sticker motif (no text)
st = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#dff6fc"/><circle cx="32" cy="31" r="25" fill="#0776a1"/><path d="M15 23l9-11 4 5 5-7 10 13 4-4 7 9H15Z" fill="#d0effb"/><path d="M10 37q5-5 10 0t10 0 10 0 10 0 6 0" stroke="#b0ecfc" stroke-width="3.6" fill="none" stroke-linecap="round"/><circle cx="46" cy="16" r="5" fill="#f86189" stroke="#fff" stroke-width="2"/></svg>
"""
(ROOT / "frontend/src/app/icon.svg").write_text(st)
print(sorted(p.name for p in (PUB / "ui").rglob("*")), sorted(p.name for p in (PUB / "brand").iterdir()))
