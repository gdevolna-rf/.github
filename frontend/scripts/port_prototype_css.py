"""Port prototype CSS into frontend/src/styles (one-off; documents how public/cabinet/shapers.css were derived).

Re-running overwrites public.css, cabinet.css and shapers.css (not tokens.css / app.css).

- public.css / cabinet.css: prototype files without the :root block (tokens live in tokens.css),
  invalid `url(var(--ignored))` removed, low-contrast blue-grey TEXT colours darkened to >= 4.5:1 (UX-14).
- shapers.css: every selector scoped under `.gv-shapers` (the module used to live in an iframe and
  has its own body/.topbar/.modal/.primary/.toast rules and clashing tokens), keyframes renamed.
"""
import colorsys
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root
SRC = ROOT / "docs/prototype/frontend-port/styles"
DST = ROOT / "frontend/src/styles"
DST.mkdir(parents=True, exist_ok=True)


# ---------- colour helpers ----------
def hex_to_rgb(h):
    h = h.lstrip("#")
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h[:3])
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def lum(rgb):
    def ch(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


CARD_BG = hex_to_rgb("#eef9fd")  # lightest tinted panel the secondary text sits on (#e8f7fc..#f9fdff)
TARGET = 4.6


def darken_to_target(h):
    rgb = hex_to_rgb(h)
    hh, ll, ss = colorsys.rgb_to_hls(*rgb)
    while contrast(colorsys.hls_to_rgb(hh, ll, ss), CARD_BG) < TARGET and ll > 0.05:
        ll -= 0.01
    r, g, b = colorsys.hls_to_rgb(hh, ll, ss)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


changed = {}


def fix_text_colours(css):
    """Darken mid-tone blue-grey text colours (not backgrounds, not accents, not text on dark panels)."""
    def repl(m):
        prop, val = m.group(1), m.group(2)
        hx = val
        if len(hx.lstrip("#")) == 8:  # alpha colours: leave
            return m.group(0)
        rgb = hex_to_rgb(hx)
        hh, ll, ss = colorsys.rgb_to_hls(*rgb)
        hue = hh * 360
        c_white = contrast(rgb, (1, 1, 1))
        # Only blue/teal/grey-blue hues, medium tones: these are the small secondary texts on light cards.
        if not (170 <= hue <= 225) or not (1.9 <= c_white < 4.5) or ss > 0.75:
            return m.group(0)
        new = darken_to_target(hx)
        changed[hx.lower()] = new
        return f"{prop}{new}"
    skip = re.compile(r":disabled|disabled|\.closed|placeholder|\.locked|\.past|\.busy|\.off\b")

    def rule(m):
        sel, body = m.group(1), m.group(2)
        if skip.search(sel):
            return m.group(0)
        return sel + "{" + re.sub(r"((?<![-\w])color:\s*)(#[0-9a-fA-F]{3,8})\b", repl, body) + "}"
    return re.sub(r"([^{}]+)\{([^{}]*)\}", rule, css)


def strip_root(css):
    return re.sub(r":root\s*\{[^}]*\}\s*", "", css, count=1)


# ---------- public ----------
pub = (SRC / "prototype-public.css").read_text()
pub = strip_root(pub)
pub = pub.replace("""  background:
    linear-gradient(135deg, #032f4e9a, #073c5c80),
    url(var(--ignored)) center;""", """  background: linear-gradient(135deg, #032f4e9a, #073c5c80);""")
pub = fix_text_colours(pub)
header = """/*
 * ГДеволна — public site styles (port of docs/prototype/frontend-port/styles/prototype-public.css).
 * Class names are the prototype's: reuse them in markup. Tokens are in tokens.css; new app components
 * and TZ fixes (UX-04…UX-07, ATX-19, ATX-22) are in app.css. Changes vs. the prototype file:
 *   - :root moved to tokens.css;
 *   - invalid `url(var(--ignored))` background removed from .live-empty;
 *   - mid-tone blue-grey text colours darkened to ≥4.5:1 on light panels (UX-14, DESIGN_SYSTEM §4.5).
 * Do not edit to restyle a page — add page-specific rules to app.css or a CSS module.
 */
"""
pub = re.sub(r"^/\*.*?\*/\s*", "", pub, count=1, flags=re.S)
(DST / "public.css").write_text(header + pub)

# ---------- cabinet ----------
cab = (SRC / "prototype-cabinet.css").read_text()
cab_header_end = cab.find("*/") + 2
cab_body = cab[cab_header_end:]
cab_body = strip_root(cab_body)
cab_body = fix_text_colours(cab_body)
# the cabinet nav is made of real links in the app (deep-linkable panes, NAV-05 / CABINET_NOTES A10)
cab_body = cab_body.replace(".gv-ac-nav button", ".gv-ac-nav :is(button, a)")
(DST / "cabinet.css").write_text("""/*
 * ГДеволна — unified personal account (кабинет) styles, port of prototype-cabinet.css.
 * Classes .gv-ac-*, .gv-account, .lesson-*, registration (.role-list, .reg-step…) keep the prototype names.
 * Loaded after public.css. Tokens: tokens.css. Mid-tone secondary text darkened for contrast (UX-14).
 */
""" + cab_body)


# ---------- shapers (scoped) ----------
SCOPE = ".gv-shapers"


def split_selectors(sel):
    out, depth, cur = [], 0, ""
    for ch in sel:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [s.strip() for s in out if s.strip()]


def scope_selector(s):
    if s in (":root", "html", "body", "html,body"):
        return SCOPE
    if s == "*":
        return f"{SCOPE} *"
    m = re.match(r"^(html|body)\b(.*)$", s)
    if m:
        rest = m.group(2)
        if rest.startswith((".", ":", "[", "#")):
            return SCOPE + rest
        return SCOPE + rest if rest.startswith(" ") else f"{SCOPE} {rest.strip()}"
    return f"{SCOPE} {s}"


def tokenize_blocks(css):
    """Yield (kind, text) for top-level items: comment, at-block, at-stmt, rule."""
    i, n = 0, len(css)
    while i < n:
        if css[i].isspace():
            j = i
            while j < n and css[j].isspace():
                j += 1
            yield ("ws", css[i:j])
            i = j
            continue
        if css.startswith("/*", i):
            j = css.index("*/", i) + 2
            yield ("comment", css[i:j])
            i = j
            continue
        # read prelude up to { or ;
        j = i
        while j < n and css[j] not in "{;":
            if css.startswith("/*", j):
                j = css.index("*/", j) + 2
                continue
            j += 1
        prelude = css[i:j]
        if j < n and css[j] == ";":
            yield ("stmt", css[i:j + 1])
            i = j + 1
            continue
        # block: find matching brace
        depth, k = 0, j
        while k < n:
            if css.startswith("/*", k):
                k = css.index("*/", k) + 2
                continue
            if css[k] == "{":
                depth += 1
            elif css[k] == "}":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        body = css[j + 1:k]
        yield ("block", (prelude.strip(), body))
        i = k + 1


renamed_keyframes = {}


def scope_css(css, in_keyframes=False):
    out = []
    for kind, item in tokenize_blocks(css):
        if kind in ("ws", "comment", "stmt"):
            out.append(item)
            continue
        prelude, body = item
        if prelude.startswith("@keyframes") or prelude.startswith("@-webkit-keyframes"):
            name = prelude.split()[1]
            new = f"gvs-{name}"
            renamed_keyframes[name] = new
            out.append(f"@keyframes {new} {{{body}}}")
        elif prelude.startswith("@media") or prelude.startswith("@supports") or prelude.startswith("@container"):
            out.append(f"{prelude} {{{scope_css(body)}}}")
        elif prelude.startswith("@"):
            out.append(f"{prelude} {{{body}}}")
        else:
            sels = split_selectors(prelude)
            out.append(",\n".join(scope_selector(s) for s in sels) + " {" + body + "}")
    return "".join(out)


sh = (SRC / "prototype-shapers.css").read_text()
sh_header_end = sh.find("*/") + 2
sh_body = sh[sh_header_end:]
sh_body = sh_body.replace("url('img/img20.webp')", "url('/ui/shapers-landscape.webp')")
sh_body = sh_body.replace("url('img/img23.webp')", "url('/ui/shapers-landscape.webp')")
sh_body = sh_body.replace("url('img/img21.webp')", "url('/ui/hero-catalog.webp')")
sh_body = sh_body.replace("url('img/img22.webp')", "url('/ui/hero-catalog.webp')")
scoped = scope_css(sh_body)
for old, new in renamed_keyframes.items():
    scoped = re.sub(rf"(animation(?:-name)?:[^;}}]*?)\b{re.escape(old)}\b", rf"\1{new}", scoped)
scoped = fix_text_colours(scoped)
(DST / "shapers.css").write_text("""/*
 * ГДеволна — shapers module styles (port of prototype-shapers.css), SCOPED under `.gv-shapers`.
 * The prototype rendered this module inside an <iframe>, so it has its own body/topbar/modal/primary/toast
 * rules and tokens with the same names but different values (--navy, --text, --shadow). Every selector is
 * prefixed with `.gv-shapers` (body/html/:root → `.gv-shapers` itself) so it cannot leak into the site.
 * Usage: wrap shaper catalogue/cabinet markup in <div className="gv-shapers">…</div>.
 * Images: img20/img23 → /ui/shapers-landscape.webp; the composite hero img21/img22 (contains a person's
 * face) is not shipped — /ui/hero-catalog.webp is used instead. Keyframes renamed with a `gvs-` prefix.
 */
""" + scoped)

print("changed colours:", len(changed))
for k, v in sorted(changed.items()):
    print(f"  {k} -> {v}  ({contrast(hex_to_rgb(k), CARD_BG):.2f} -> {contrast(hex_to_rgb(v), CARD_BG):.2f})")
print("keyframes:", renamed_keyframes)
