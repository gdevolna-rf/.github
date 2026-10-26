"""Generate frontend/src/components/ui/icons/registry.ts from icons.json + icons-cabinet.json.

Run: python3 frontend/scripts/gen_icons.py   (add new icons to `extra` below: 24px grid, stroke 1.9, round caps)

UX-04: one family, one stroke width (1.9 on the 24px grid), round caps/joins, currentColor.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root
PORT = ROOT / "docs/prototype/frontend-port"
OUT = ROOT / "frontend/src/components/ui/icons/registry.ts"
OUT.parent.mkdir(parents=True, exist_ok=True)

pub = json.loads((PORT / "icons.json").read_text())["icons"]
cab = json.loads((PORT / "icons-cabinet.json").read_text())

icons = {}


def add(name, viewBox, inner, source):
    inner = re.sub(r'\s+stroke-width="[^"]*"', "", inner)  # the root sets the width
    icons[name] = {"viewBox": viewBox, "body": inner, "source": source}


# public line icons (header, filters, cards)
for name in ["search", "heart", "chat", "user", "pencil", "board", "level", "map-pin"]:
    v = pub[name]
    add(name, v["viewBox"], v["inner"], f"icons.json#{name}")

# cabinet/shapers sprite (i-*), already 1.9 on 24px
for k, v in cab.items():
    if k.startswith("i-") and k not in ("i-search", "i-heart", "i-user"):
        add(k[2:], v["viewBox"], v["inner"], f"icons-cabinet.json#{k}")

# additions drawn on the same 24px grid (same stroke, caps, joins) for UI the prototype rendered with glyphs
extra = {
    "arrow-left": '<path d="M20 12H4m7-7-7 7 7 7"/>',
    "chevron-left": '<path d="m15 5-7 7 7 7"/>',
    "chevron-right": '<path d="m9 5 7 7-7 7"/>',
    "chevron-down": '<path d="m5 9 7 7 7-7"/>',
    "chevron-up": '<path d="m5 15 7-7 7 7"/>',
    "external": '<path d="M14 4h6v6M20 4 11 13"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    "paperclip": '<path d="m20 11-8.5 8.5a5 5 0 0 1-7-7L13 4a3.3 3.3 0 0 1 4.7 4.7l-8.5 8.5a1.7 1.7 0 0 1-2.4-2.4L14.5 7"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.01"/>',
    "alert": '<path d="M12 3 2.5 20h19L12 3Z"/><path d="M12 10v4.5M12 17.5v.01"/>',
    "waves": '<path d="M3 8c2-1.6 4-1.6 6 0s4 1.6 6 0 4-1.6 6 0M3 13c2-1.6 4-1.6 6 0s4 1.6 6 0 4-1.6 6 0M3 18c2-1.6 4-1.6 6 0s4 1.6 6 0 4-1.6 6 0"/>',
    "target": '<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2.5"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/>',
    "grid": '<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/>',
    "play": '<circle cx="12" cy="12" r="9"/><path d="m10 8.5 5.5 3.5-5.5 3.5Z"/>',
    "refresh": '<path d="M20 11a8 8 0 0 0-14.3-4.9L4 8M4 4v4h4M4 13a8 8 0 0 0 14.3 4.9L20 16M20 20v-4h-4"/>',
    "trash": '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6"/>',
    "grip": '<circle cx="9" cy="6" r="1" fill="currentColor"/><circle cx="15" cy="6" r="1" fill="currentColor"/><circle cx="9" cy="12" r="1" fill="currentColor"/><circle cx="15" cy="12" r="1" fill="currentColor"/><circle cx="9" cy="18" r="1" fill="currentColor"/><circle cx="15" cy="18" r="1" fill="currentColor"/>',
    "video": '<rect x="2.5" y="6" width="13" height="12" rx="2"/><path d="m15.5 10.5 6-3.5v10l-6-3.5"/>',
    "logout": '<path d="M15 4h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4M10 16l-4-4 4-4M6 12h10"/>',
    "lock": '<rect x="4.5" y="10.5" width="15" height="10" rx="2"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/>',
    "shield": '<path d="M12 3 4.5 6v5.5c0 4.5 3.2 8.2 7.5 9.5 4.3-1.3 7.5-5 7.5-9.5V6L12 3Z"/><path d="m9 12 2 2 4-4"/>',
    "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20v-1.5a6.5 6.5 0 0 1 13 0V20"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M18.5 14.2a6.5 6.5 0 0 1 3 5.3V20"/>',
    "school": '<path d="M2.5 9 12 4.5 21.5 9 12 13.5 2.5 9Z"/><path d="M6.5 11v5c1.5 1.6 3.4 2.5 5.5 2.5s4-.9 5.5-2.5v-5M21.5 9v6"/>',
    "map": '<path d="M9 4 3.5 6v14L9 18l6 2 5.5-2V4L15 6 9 4Z"/><path d="M9 4v14M15 6v14"/>',
    "clover": '<path d="M12 11.2a3.4 3.4 0 1 1 0-6.4 3.4 3.4 0 1 1 0 6.4Z"/><path d="M11.4 12.2a3.4 3.4 0 1 1-5.6 3.4 3.4 3.4 0 1 1 5.6-3.4ZM12.6 12.2a3.4 3.4 0 1 0 5.6 3.4 3.4 3.4 0 1 0-5.6-3.4Z"/><path d="M12 12.5v8.5"/>',
    "diamond": '<path d="M12 2.8 21.2 12 12 21.2 2.8 12 12 2.8Z"/><path d="M12 7.5 16.5 12 12 16.5 7.5 12 12 7.5Z"/>',
    "sparkle": '<path d="M12 3c.8 4.6 2.9 7 8 9-5.1 2-7.2 4.4-8 9-.8-4.6-2.9-7-8-9 5.1-2 7.2-4.4 8-9Z"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2.5M12 19v2.5M2.5 12H5M19 12h2.5M5.3 5.3l1.8 1.8M16.9 16.9l1.8 1.8M5.3 18.7l1.8-1.8M16.9 7.1l1.8-1.8"/>',
    "wifi-off": '<path d="M3 3l18 18M8.5 12.4a6 6 0 0 1 3.6-1.4M5 9a11 11 0 0 1 3.3-2.1M12 5a11 11 0 0 1 7 3.4M15.6 11.8l.3.2M10 16a3 3 0 0 1 4 0M12 19.5v.01"/>',
    "image": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8.5" cy="9.5" r="1.8"/><path d="m3.5 18 5.5-6 4 4 3-3 4.5 5"/>',
    "cover": '<path d="m12 3.5 2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9L12 3.5Z"/>',
    "minus": '<path d="M5 12h14"/>',
    "filter": '<path d="M4 5h16l-6 7.5V19l-4 1.5v-8L4 5Z"/>',
    "shop": '<path d="M4 9h16l-1.2 11H5.2L4 9Z"/><path d="M8.5 9V7a3.5 3.5 0 0 1 7 0v2"/>',
}
for name, body in extra.items():
    icons[name] = {"viewBox": "0 0 24 24", "body": body, "source": "app (24px grid, stroke 1.9)"}

# 28px-grid filter icons: keep their own viewBox; the stroke is scaled so the rendered weight matches
STROKE = {name: ("2.2" if v["viewBox"] == "0 0 28 28" else "1.9") for name, v in icons.items()}

lines = [
    "/* AUTO-GENERATED by frontend/scripts/gen_icons.py from docs/prototype/frontend-port/icons*.json (+ app additions).",
    " * Do not edit by hand: add icons to the script (same 24px grid, stroke 1.9, round caps — UX-04) and re-run it. */",
    "",
    "export interface IconDef {",
    "  viewBox: string;",
    "  strokeWidth: string;",
    "  body: string;",
    "}",
    "",
    "export const ICONS = {",
]
for name in sorted(icons):
    v = icons[name]
    lines.append(f"  {json.dumps(name)}: {{ viewBox: {json.dumps(v['viewBox'])}, strokeWidth: {json.dumps(STROKE[name])}, body: {json.dumps(v['body'], ensure_ascii=False)} }},")
lines += ["} satisfies Record<string, IconDef>;", "", "export type IconName = keyof typeof ICONS;", ""]
OUT.write_text("\n".join(lines))
print(len(icons), "icons:", ", ".join(sorted(icons)))
