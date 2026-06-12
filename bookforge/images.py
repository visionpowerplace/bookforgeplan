"""Chapter-opener art — a themed emblem illustration generated per chapter title.

`motif_for_title()` maps the title to a symbolic motif (swords, open book, shield,
flame, sprout, crown, ...); `generate_opener()` composes a designed crest: a tonal
themed background, radiating light, a circular seal, the motif glyph, and a darkened
band where the centered title sits.

This is the production seam: swap the body of `generate_opener()` for a text-to-image
API call seeded by `brief_for_chapter()` and nothing else in the pipeline changes.
"""
import math
import random
from PIL import Image, ImageDraw, ImageFilter, ImageChops


# ---- title -> motif -------------------------------------------------------

_MOTIF_KEYWORDS = [
    ("swords",   ("fight", "battle", "war", "enemy", "strategy", "weapon", "conquer", "victor", "overcome", "stand")),
    ("book",     ("word", "scripture", "bible", "truth", "promise", "study", "read", "gospel", "knowledge", "wisdom")),
    ("shield",   ("guard", "protect", "armor", "defense", "environment", "cover", "safe", "keep")),
    ("chain",    ("thief", "thieve", "steal", "break", "free", "bondage", "chain", "trap", "loss")),
    ("sprout",   ("grow", "growth", "develop", "seed", "plant", "increase", "mature", "fruit", "harvest")),
    ("flame",    ("fuel", "fire", "passion", "burn", "zeal", "sacrifice", "altar", "love", "heart", "desire")),
    ("crown",    ("champion", "victory", "win", "reward", "king", "crown", "triumph", "honor", "glory", "destiny")),
    ("sun",      ("begin", "start", "new", "dawn", "rise", "morning", "momentum", "now", "release", "hope", "light")),
    ("mountain", ("impossible", "mountain", "summit", "climb", "peak", "high", "contradiction", "struggle", "endure")),
    ("compass",  ("decision", "choice", "direction", "way", "journey", "path", "purpose", "found", "actually", "define", "characteristic")),
    ("wave",     ("storm", "water", "flood", "wave", "deep", "sea", "trouble", "fear", "doubt")),
    ("dove",     ("spirit", "peace", "prayer", "faith", "grace", "believe", "trust", "rest")),
]
_FALLBACK = ("compass", "sun", "star")


def motif_for_title(title: str, number: int = 1) -> str:
    t = (title or "").lower()
    for motif, keys in _MOTIF_KEYWORDS:
        if any(k in t for k in keys):
            return motif
    return _FALLBACK[(number - 1) % len(_FALLBACK)]


_BRIEFS = {
    "swords": "two crossed swords emblem, heraldic, the good fight",
    "book":   "open book radiating light, sacred scripture, rays",
    "shield": "a guardian shield emblem with a cross, protection",
    "chain":  "a broken chain link, freedom and breakthrough",
    "sprout": "a young sprout with two leaves, growth from a seed",
    "flame":  "a single rising flame, devotion and sacrifice",
    "crown":  "a laurel-framed crown, the victor's reward",
    "sun":    "a rising sun with rays over a horizon, new beginning",
    "mountain":"a tall mountain peak above clouds, the impossible climb",
    "compass":"a compass rose pointing north, direction and purpose",
    "wave":   "a cresting wave, the storm of contradiction",
    "dove":   "a descending dove, the spirit and peace",
    "star":   "a radiant guiding star, destiny",
}


def brief_for_chapter(title: str, number: int) -> str:
    return _BRIEFS.get(motif_for_title(title, number), _BRIEFS["star"])


# ---- glyph primitives -----------------------------------------------------

def _poly(d, pts, ink, w):
    d.line(pts + [pts[0]], fill=ink, width=w, joint="curve")


def _star(d, cx, cy, R, ink, w, points=5, ratio=0.42, fill=False):
    pts = []
    for i in range(points * 2):
        ang = -math.pi / 2 + i * math.pi / points
        rr = R if i % 2 == 0 else R * ratio
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    if fill:
        d.polygon(pts, fill=ink)
    else:
        _poly(d, pts, ink, w)


def g_swords(d, cx, cy, s, ink, w):
    for sgn in (-1, 1):
        dx, dy = sgn * s * 0.62, s * 0.62
        # blade
        d.line([(cx - dx, cy + dy), (cx + dx, cy - dy)], fill=ink, width=w)
        # tip
        tipx, tipy = cx + dx, cy - dy
        d.line([(tipx, tipy), (tipx - sgn * s * 0.12, tipy + s * 0.04)], fill=ink, width=w)
        # hilt / guard near bottom
        gx, gy = cx - dx * 0.74, cy + dy * 0.74
        d.line([(gx - s * 0.12, gy - s * 0.12), (gx + s * 0.12, gy + s * 0.12)], fill=ink, width=w)
        # pommel
        d.line([(cx - dx, cy + dy), (cx - dx * 1.12, cy + dy * 1.12)], fill=ink, width=w)


def g_book(d, cx, cy, s, ink, w):
    # rays above
    for a in range(-60, 61, 20):
        ang = math.radians(a - 90)
        d.line([(cx, cy - s * 0.30),
                (cx + math.cos(ang) * s * 0.95, cy - s * 0.30 + math.sin(ang) * s * 0.95)],
               fill=ink, width=max(2, w // 2))
    # two pages
    d.line([(cx, cy - s * 0.18), (cx, cy + s * 0.5)], fill=ink, width=w)
    for sgn in (-1, 1):
        d.line([(cx, cy - s * 0.18), (cx + sgn * s * 0.78, cy + s * 0.02)], fill=ink, width=w)
        d.line([(cx + sgn * s * 0.78, cy + s * 0.02), (cx + sgn * s * 0.78, cy + s * 0.56)], fill=ink, width=w)
        d.line([(cx + sgn * s * 0.78, cy + s * 0.56), (cx, cy + s * 0.5)], fill=ink, width=w)
        for k in (0.16, 0.30, 0.44):
            d.line([(cx + sgn * s * 0.12, cy + s * (0.02 + k)),
                    (cx + sgn * s * 0.66, cy + s * (0.12 + k))], fill=ink, width=max(2, w // 3))


def g_shield(d, cx, cy, s, ink, w):
    top, half, sh = cy - s * 0.62, s * 0.6, s * 0.72
    pts = [(cx, top), (cx + half, top + s * 0.12), (cx + half, cy + s * 0.18),
           (cx, cy + sh + s * 0.18), (cx - half, cy + s * 0.18), (cx - half, top + s * 0.12)]
    _poly(d, pts, ink, w)
    d.line([(cx, top + s * 0.16), (cx, cy + s * 0.34)], fill=ink, width=w)
    d.line([(cx - half * 0.6, cy - s * 0.12), (cx + half * 0.6, cy - s * 0.12)], fill=ink, width=w)


def g_chain(d, cx, cy, s, ink, w):
    rw, rh = s * 0.34, s * 0.5
    for sgn, off in ((-1, -0.34), (1, 0.34)):
        ox = cx + s * off
        oy = cy + sgn * s * 0.16
        ang = math.radians(35)
        bb = [ox - rw, oy - rh, ox + rw, oy + rh]
        d.arc(bb, start=(70 if sgn < 0 else 250), end=(250 if sgn < 0 else 70 + 360), fill=ink, width=w)
    # snapped gap sparks
    for a in (0, 120, 240):
        ang = math.radians(a)
        d.line([(cx, cy), (cx + math.cos(ang) * s * 0.18, cy + math.sin(ang) * s * 0.18)],
               fill=ink, width=max(2, w // 2))


def g_sprout(d, cx, cy, s, ink, w):
    base = cy + s * 0.6
    d.line([(cx, base), (cx, cy - s * 0.36)], fill=ink, width=w)
    for sgn in (-1, 1):
        d.arc([cx - s * 0.7 if sgn < 0 else cx, cy - s * 0.5,
               cx if sgn < 0 else cx + s * 0.7, cy + s * 0.12],
              start=(200 if sgn < 0 else 290), end=(340 if sgn < 0 else 70), fill=ink, width=w)
        d.line([(cx, cy - s * 0.05), (cx + sgn * s * 0.46, cy - s * 0.34)], fill=ink, width=max(2, w // 2))
    d.line([(cx - s * 0.22, base), (cx + s * 0.22, base)], fill=ink, width=w)


def g_flame(d, cx, cy, s, ink, w):
    pts = [(cx, cy - s * 0.7), (cx + s * 0.42, cy - s * 0.05), (cx + s * 0.3, cy + s * 0.5),
           (cx, cy + s * 0.64), (cx - s * 0.3, cy + s * 0.5), (cx - s * 0.42, cy - s * 0.05)]
    _poly(d, pts, ink, w)
    inner = [(cx, cy - s * 0.28), (cx + s * 0.2, cy + s * 0.12), (cx, cy + s * 0.4),
             (cx - s * 0.2, cy + s * 0.12)]
    _poly(d, inner, ink, max(2, w // 2))


def g_crown(d, cx, cy, s, ink, w):
    base = cy + s * 0.4
    pts = [(cx - s * 0.6, base), (cx - s * 0.6, cy - s * 0.2),
           (cx - s * 0.28, cy + s * 0.06), (cx, cy - s * 0.42),
           (cx + s * 0.28, cy + s * 0.06), (cx + s * 0.6, cy - s * 0.2),
           (cx + s * 0.6, base)]
    _poly(d, pts, ink, w)
    d.line([(cx - s * 0.6, base), (cx + s * 0.6, base)], fill=ink, width=w)
    for px in (-0.6, 0, 0.6):
        d.ellipse([cx + s * px - w, cy - s * (0.42 if px == 0 else 0.2) - w,
                   cx + s * px + w, cy - s * (0.42 if px == 0 else 0.2) + w], fill=ink)


def g_sun(d, cx, cy, s, ink, w):
    cy2 = cy + s * 0.1
    d.arc([cx - s * 0.5, cy2 - s * 0.5, cx + s * 0.5, cy2 + s * 0.5], start=180, end=360, fill=ink, width=w)
    d.line([(cx - s * 0.85, cy2), (cx + s * 0.85, cy2)], fill=ink, width=w)
    for a in range(-150, -29, 30):
        ang = math.radians(a)
        d.line([(cx + math.cos(ang) * s * 0.62, cy2 + math.sin(ang) * s * 0.62),
                (cx + math.cos(ang) * s * 0.92, cy2 + math.sin(ang) * s * 0.92)],
               fill=ink, width=max(2, w // 2))


def g_mountain(d, cx, cy, s, ink, w):
    base = cy + s * 0.55
    _poly(d, [(cx - s * 0.8, base), (cx - s * 0.05, cy - s * 0.65), (cx + s * 0.45, base)], ink, w)
    _poly(d, [(cx - s * 0.1, base), (cx + s * 0.45, cy - s * 0.3), (cx + s * 0.85, base)], ink, w)
    # snow cap
    d.line([(cx - s * 0.22, cy - s * 0.36), (cx - s * 0.05, cy - s * 0.65),
            (cx + s * 0.12, cy - s * 0.36)], fill=ink, width=max(2, w // 2))


def g_compass(d, cx, cy, s, ink, w):
    d.ellipse([cx - s * 0.7, cy - s * 0.7, cx + s * 0.7, cy + s * 0.7], outline=ink, width=w)
    d.polygon([(cx, cy - s * 0.55), (cx + s * 0.16, cy), (cx, cy + s * 0.55), (cx - s * 0.16, cy)],
              outline=ink)
    _poly(d, [(cx, cy - s * 0.55), (cx + s * 0.16, cy), (cx, cy + s * 0.55), (cx - s * 0.16, cy)], ink, w)
    for a in (0, 90, 180, 270):
        ang = math.radians(a)
        d.line([(cx + math.cos(ang) * s * 0.7, cy + math.sin(ang) * s * 0.7),
                (cx + math.cos(ang) * s * 0.84, cy + math.sin(ang) * s * 0.84)], fill=ink, width=w)


def g_wave(d, cx, cy, s, ink, w):
    d.arc([cx - s * 0.8, cy - s * 0.4, cx + s * 0.2, cy + s * 0.6], start=180, end=20, fill=ink, width=w)
    d.arc([cx - s * 0.1, cy - s * 0.1, cx + s * 0.8, cy + s * 0.7], start=180, end=360, fill=ink, width=w)
    d.arc([cx + s * 0.1, cy + s * 0.1, cx + s * 0.5, cy + s * 0.5], start=180, end=360, fill=ink, width=max(2, w // 2))


def g_dove(d, cx, cy, s, ink, w):
    d.ellipse([cx - s * 0.16, cy - s * 0.55, cx + s * 0.16, cy - s * 0.2], outline=ink, width=w)  # head
    _poly(d, [(cx, cy - s * 0.2), (cx + s * 0.2, cy + s * 0.5), (cx - s * 0.2, cy + s * 0.5)], ink, w)  # body
    for sgn in (-1, 1):
        d.arc([cx + (0 if sgn > 0 else -s * 0.9), cy - s * 0.2,
               cx + (s * 0.9 if sgn > 0 else 0), cy + s * 0.5],
              start=(200 if sgn < 0 else 270), end=(340 if sgn < 0 else 50), fill=ink, width=w)


def g_star(d, cx, cy, s, ink, w):
    _star(d, cx, cy, s * 0.7, ink, w, points=5, ratio=0.42)
    for a in range(0, 360, 45):
        ang = math.radians(a)
        d.line([(cx + math.cos(ang) * s * 0.82, cy + math.sin(ang) * s * 0.82),
                (cx + math.cos(ang) * s * 0.95, cy + math.sin(ang) * s * 0.95)],
               fill=ink, width=max(2, w // 3))


_GLYPHS = {"swords": g_swords, "book": g_book, "shield": g_shield, "chain": g_chain,
           "sprout": g_sprout, "flame": g_flame, "crown": g_crown, "sun": g_sun,
           "mountain": g_mountain, "compass": g_compass, "wave": g_wave, "dove": g_dove,
           "star": g_star}


# ---- composition ----------------------------------------------------------

def _seal(d, cx, cy, R, ink, stroke):
    d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=ink, width=stroke)
    r2 = R * 0.85
    d.ellipse([cx - r2, cy - r2, cx + r2, cy + r2], outline=ink, width=max(2, stroke // 2))
    for a in range(0, 360, 10):
        ang = math.radians(a)
        d.line([(cx + math.cos(ang) * R * 0.9, cy + math.sin(ang) * R * 0.9),
                (cx + math.cos(ang) * R * 0.96, cy + math.sin(ang) * R * 0.96)],
               fill=ink, width=max(2, stroke // 2))


def generate_opener(out_path, w_px, h_px, title="", number=1, mode="bw", seed=None):
    rnd = random.Random(seed if seed is not None else (hash(title) & 0xffff) + number)
    motif = motif_for_title(title, number)

    img = Image.new("L", (w_px, h_px), 0)
    cx, cy = w_px / 2, h_px * 0.30
    R = w_px * 0.23

    # dark tonal gradient (so the light emblem pops)
    col = Image.new("L", (1, h_px))
    for y in range(h_px):
        f = y / h_px
        col.putpixel((0, y), int(64 - 50 * f))
    img.paste(col.resize((w_px, h_px)), (0, 0))

    # soft halo behind the seal
    glow = Image.new("L", (w_px, h_px), 0)
    ImageDraw.Draw(glow).ellipse([cx - R * 2.2, cy - R * 2.2, cx + R * 2.2, cy + R * 2.2], fill=255)
    glow = glow.filter(ImageFilter.GaussianBlur(w_px * 0.13))
    halo = glow.point(lambda p: int(p * 0.30))
    img = ImageChops.lighter(img, halo)

    # faint sunburst rays, confined to the halo
    rays = Image.new("L", (w_px, h_px), 0)
    rd = ImageDraw.Draw(rays)
    base_a = rnd.uniform(0, 30)
    for a in range(0, 360, 15):
        ang = math.radians(a + base_a)
        rd.line([(cx, cy), (cx + math.cos(ang) * w_px, cy + math.sin(ang) * w_px)],
                fill=255, width=max(2, w_px // 360))
    rays = ImageChops.multiply(rays.filter(ImageFilter.GaussianBlur(3)), glow).point(lambda p: int(p * 0.16))
    img = ImageChops.lighter(img, rays)

    d = ImageDraw.Draw(img)
    ink = 246
    stroke = max(4, w_px // 200)

    _seal(d, cx, cy, R, ink, stroke)
    _GLYPHS.get(motif, g_star)(d, cx, cy, R * 0.6, ink, max(4, int(stroke * 1.3)))

    # thin flourish rule lower, for balance
    ry = h_px * 0.8
    d.line([(cx - w_px * 0.11, ry), (cx + w_px * 0.11, ry)], fill=190, width=max(2, stroke // 2))
    d.ellipse([cx - stroke, ry - stroke, cx + stroke, ry + stroke], fill=190)

    # finish (title band + grain + vignette + colour mode) and save
    finish_opener(img, w_px, h_px, mode, out_path)


def finish_opener(img, w_px, h_px, mode, out_path, title_band=True, photo=False):
    """Shared print treatment for any opener art (vector crest OR AI photo):
    darken a band where the centred title sits, add grain + vignette, apply the
    colour mode, and save at 300 DPI. Photos keep full colour in 'color' mode;
    vector crests become an indigo duotone."""
    keep_color = photo and mode == "color"

    # build a single multiply mask (band + vignette)
    mask = Image.new("L", (w_px, h_px), 255)
    if title_band:
        band = Image.new("L", (w_px, h_px), 255)
        ImageDraw.Draw(band).rectangle([0, h_px * 0.55, w_px, h_px * 0.71], fill=78)
        mask = ImageChops.multiply(mask, band.filter(ImageFilter.GaussianBlur(h_px * 0.045)))
    vig = Image.new("L", (w_px, h_px), 0)
    ImageDraw.Draw(vig).ellipse([-w_px * 0.3, -h_px * 0.3, w_px * 1.3, h_px * 1.3], fill=255)
    mask = ImageChops.multiply(mask, vig.filter(ImageFilter.GaussianBlur(w_px * 0.12)))

    grain = Image.effect_noise((w_px, h_px), 12).point(lambda p: int((p - 128) * 0.5 + 128))

    if keep_color:
        base = img.convert("RGB")
        m3 = Image.merge("RGB", (mask, mask, mask))
        base = ImageChops.multiply(base, m3)
        g3 = Image.merge("RGB", (grain, grain, grain))
        out = Image.blend(base, ImageChops.multiply(base, g3), 0.07)
    else:
        base = ImageChops.multiply(img.convert("L"), mask)
        base = Image.blend(base, ImageChops.multiply(base, grain), 0.09)
        out = _duotone(base, (14, 18, 44), (232, 234, 248)) if mode == "color" else base.convert("RGB")

    out.save(out_path, "JPEG", quality=88, dpi=(300, 300))


def _duotone(gray, dark, light):
    lut = []
    for ch in range(3):
        lut += [int(dark[ch] + (light[ch] - dark[ch]) * (i / 255)) for i in range(256)]
    return gray.convert("L").convert("RGB").point(lut)
