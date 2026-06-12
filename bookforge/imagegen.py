"""Real chapter art, from a configurable provider. Choose with IMAGE_PROVIDER:

  pexels    — free, commercial-safe stock photos      (PEXELS_API_KEY)        [recommended]
  unsplash  — free, commercial-safe stock photos      (UNSPLASH_ACCESS_KEY)
  openai    — generated images, gpt-image-1            (OPENAI_API_KEY)

All three plug into the same slot the procedural crest uses. The path is fail-safe:
if no provider is configured or a call errors, `generate_ai_opener()` returns False
and the caller falls back to the vector crest — so the tool always produces a book.

Pexels and Unsplash both grant free commercial use of their photos (Pexels requires
no attribution; Unsplash appreciates it). We search a thematic query derived from the
chapter title, then cover-crop the photo to the opener and apply the print treatment.
"""
import io
import json
import os
import random
import urllib.parse
import urllib.request

from PIL import Image, ImageFilter

from .images import finish_opener, motif_for_title


# ---- provider plumbing ----------------------------------------------------

def provider() -> str:
    return os.environ.get("IMAGE_PROVIDER", "pexels").lower()


def ai_available() -> bool:
    p = provider()
    if p == "pexels":
        return bool(os.environ.get("PEXELS_API_KEY"))
    if p == "unsplash":
        return bool(os.environ.get("UNSPLASH_ACCESS_KEY"))
    if p == "openai":
        if not os.environ.get("OPENAI_API_KEY"):
            return False
        try:
            import openai  # noqa: F401
            return True
        except Exception:
            return False
    return False


# ---- title -> rich AI prompt ----------------------------------------------

# A concrete visual metaphor per motif, used as an anchor (not a straitjacket).
_MOTIF_VISUAL = {
    "swords":   "a lone figure standing firm at dawn, or two crossed blades of light",
    "book":     "an open book glowing with light, pages lifting",
    "shield":   "a figure standing guard, or a shield catching the light",
    "chain":    "broken chains falling away as a figure rises free",
    "sprout":   "a single seedling breaking through soil toward the sun",
    "flame":    "one steady flame holding against the dark",
    "crown":    "a triumphant summit, or a crown of light",
    "sun":      "a sunrise cresting the horizon over open land",
    "mountain": "a lone figure reaching a mountain summit above the clouds",
    "compass":  "a path winding into the distance, or a compass on weathered ground",
    "wave":     "a powerful ocean wave beneath a vast dramatic sky",
    "dove":     "a bird ascending into bright open sky",
    "star":     "a single guiding star in an immense night sky",
}

# Per-book art direction — chosen by the book title so every book has its own
# coherent look, and two different books never come out the same.
_ART_DIRECTIONS = [
    "warm golden-hour light, cinematic, shallow depth of field",
    "cool blue twilight with soft mist, moody and quiet",
    "dramatic high-contrast chiaroscuro lighting, deep shadow and rim light",
    "desaturated misty-morning tones, ethereal and calm",
    "rich teal-and-amber cinematic colour grade, filmic",
    "soft pastel dawn light, hopeful and airy",
    "storm light with god-rays breaking through cloud",
    "minimal fine-art composition, muted earthy palette",
]


def _stable_hash(s: str) -> int:
    import hashlib
    return int(hashlib.sha1((s or "").encode("utf-8")).hexdigest(), 16)


def _art_direction(book_title: str) -> str:
    return _ART_DIRECTIONS[_stable_hash(book_title) % len(_ART_DIRECTIONS)]


def _compose_prompt(title, subtitle, book_title, style, number):
    from .images import motif_for_title
    anchor = _MOTIF_VISUAL.get(motif_for_title(title, number), "a single evocative symbol")
    style_desc = STYLE_PROMPTS.get(style, STYLE_PROMPTS["photographic"])
    direction = _art_direction(book_title or title)
    sub = f" — {subtitle}" if subtitle else ""
    book = f' from the book "{book_title}"' if book_title else ""
    return (
        f'A symbolic, emotionally resonant chapter-opener image{book}. '
        f'The chapter is titled "{title}{sub}". '
        f'Express the core idea of THIS specific chapter title through one strong, clear visual '
        f'metaphor (for instance: {anchor}) — interpreted freshly for this exact title, not generic. '
        f'{style_desc}. {direction}. '
        f'Premium book-cover quality, cinematic and atmospheric, a single focal subject. '
        f'Vertical 2:3 composition with calm, unobstructed negative space across the lower third '
        f'for a title overlay. '
        f'Absolutely no text, no words, no letters, no numbers, no typography, no watermark, '
        f'no logos, no borders, no frames.'
    )


# ---- title -> photographic search query -----------------------------------

_STOCK_QUERIES = {
    "swords":   "spiritual warfare light beam",
    "book":     "open bible sunlight",
    "shield":   "armor shield dramatic",
    "chain":    "breaking chains freedom silhouette",
    "sprout":   "seedling growth sunrise",
    "flame":    "single candle flame dark",
    "crown":    "crown of thorns light",
    "sun":      "sunrise over mountains hope",
    "mountain": "mountain summit above clouds",
    "compass":  "path through forest light",
    "wave":     "stormy ocean waves dramatic",
    "dove":     "dove flying bright sky",
    "star":     "starry night sky over landscape",
}


def stock_query(title: str, number: int) -> str:
    return _STOCK_QUERIES.get(motif_for_title(title, number), "dramatic inspirational landscape")


# ---- image helpers --------------------------------------------------------

def _orientation(w_px, h_px) -> str:
    if h_px > w_px * 1.1:
        return "portrait"
    if w_px > h_px * 1.1:
        return "landscape"
    return "square"


def _cover_resize(img, tw, th):
    """Scale to cover the target box, then centre-crop to exactly (tw, th)."""
    iw, ih = img.size
    scale = max(tw / iw, th / ih)
    nw, nh = max(tw, int(iw * scale + 0.5)), max(th, int(ih * scale + 0.5))
    img = img.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - tw) // 2, (nh - th) // 2
    return img.crop((left, top, left + tw, top + th))


def _http_json(url, headers, timeout=20):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _http_bytes(url, headers=None, timeout=40):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ---- providers ------------------------------------------------------------

def _pexels_url(query, w_px, h_px, pick):
    key = os.environ["PEXELS_API_KEY"]
    q = urllib.parse.quote(query)
    api = (f"https://api.pexels.com/v1/search?query={q}"
           f"&orientation={_orientation(w_px, h_px)}&per_page=15&size=large")
    data = _http_json(api, {"Authorization": key})
    photos = data.get("photos", [])
    if not photos:
        return None
    photo = photos[pick % len(photos)]
    return photo["src"].get("original") or photo["src"].get("large2x") or photo["src"].get("large")


def _unsplash_url(query, w_px, h_px, pick):
    key = os.environ["UNSPLASH_ACCESS_KEY"]
    q = urllib.parse.quote(query)
    api = (f"https://api.unsplash.com/search/photos?query={q}"
           f"&orientation={_orientation(w_px, h_px)}&per_page=15&content_filter=high")
    data = _http_json(api, {"Authorization": f"Client-ID {key}", "Accept-Version": "v1"})
    results = data.get("results", [])
    if not results:
        return None
    urls = results[pick % len(results)]["urls"]
    base = urls.get("raw") or urls.get("full")
    if not base:
        return None
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}w={max(w_px, 1600)}&fit=max"


STYLE_PROMPTS = {
    "photographic": "photorealistic cinematic photograph, dramatic natural light, fine detail",
    "cinematic":    "cinematic film still, moody volumetric light, epic and atmospheric",
    "watercolor":   "soft watercolor painting on textured paper, flowing washes",
    "painterly":    "classical oil painting, expressive brushwork, rich light",
    "lineart":      "refined single-weight line illustration, elegant and minimal",
    "abstract":     "abstract textured composition, subtle tonal gradients, evocative",
}


def _openai_opener(out_path, w_px, h_px, title, subtitle, book_title, style, mode, number=1):
    import base64
    from openai import OpenAI
    prompt = _compose_prompt(title, subtitle, book_title, style, number)
    size = "1024x1536" if h_px > w_px * 1.1 else ("1536x1024" if w_px > h_px * 1.1 else "1024x1024")
    client = OpenAI()
    resp = client.images.generate(
        model=os.environ.get("BOOKFORGE_IMAGE_MODEL", "gpt-image-1"),
        prompt=prompt, size=size, quality=_quality(), n=1)
    raw = base64.b64decode(resp.data[0].b64_json)
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    img = _cover_resize(img, w_px, h_px).filter(ImageFilter.UnsharpMask(2, 80, 2))
    finish_opener(img, w_px, h_px, mode, out_path, title_band=True, photo=True)


# ---- public entry ---------------------------------------------------------

def diagnose() -> dict:
    """Actively test the configured image provider from the server, for debugging."""
    p = provider()
    info = {"provider": p, "configured": ai_available(), "ok": False, "detail": ""}
    if not info["configured"]:
        info["detail"] = ("Provider key not detected. Set IMAGE_PROVIDER and the matching "
                          "key (e.g. PEXELS_API_KEY) in the server environment, then redeploy.")
        return info
    try:
        if p in ("pexels", "unsplash"):
            url = (_pexels_url if p == "pexels" else _unsplash_url)("mountain sunrise", 1024, 1536, 0)
            if not url:
                info["detail"] = "Search returned no photos (key may be invalid or rejected)."
                return info
            _http_bytes(url, timeout=20)[:32]
            info["ok"] = True
            info["detail"] = "Fetched a test photo successfully — real photos are working."
        elif p == "openai":
            info["ok"] = True
            info["detail"] = "Key present (generation not run here to avoid cost)."
    except Exception as e:
        info["detail"] = f"{type(e).__name__}: {e}"
    return info


def diagnose() -> dict:
    """Actively test the configured image provider from this server.
    Returns a dict the /api/diag route exposes so setup can be verified."""
    p = provider()
    info = {"provider": p, "configured": ai_available(), "ok": False, "detail": ""}
    if not info["configured"]:
        info["detail"] = ("Provider key not detected in the environment. Set IMAGE_PROVIDER "
                          "and the matching key (e.g. PEXELS_API_KEY).")
        return info
    try:
        if p in ("pexels", "unsplash"):
            url = (_pexels_url if p == "pexels" else _unsplash_url)("mountain sunrise", 1024, 1536, 0)
            if not url:
                info["detail"] = "Authenticated, but the test search returned no photos."
                return info
            _http_bytes(url, timeout=20)
            info["ok"] = True
            info["detail"] = "Fetched a test photo successfully — real photos are working."
        elif p == "openai":
            info["ok"] = True
            info["detail"] = "OpenAI key present (live generation not run here to avoid cost)."
    except Exception as e:
        info["detail"] = f"{type(e).__name__}: {e}"
    return info


def _quality() -> str:
    """Normalise the configured quality so a typo/abbreviation can't 400 the API."""
    q = (os.environ.get("BOOKFORGE_IMAGE_QUALITY", "high") or "high").strip().lower()
    aliases = {"med": "medium", "mid": "medium", "hi": "high", "lo": "low",
               "standard": "medium", "default": "auto", "hd": "high"}
    q = aliases.get(q, q)
    return q if q in ("low", "medium", "high", "auto") else "high"


LAST_ERROR = ""


def generate_ai_opener(out_path, w_px, h_px, brief, style="photographic",
                       mode="bw", seed=None, title="", number=1, subtitle="", book_title=""):
    """Produce one real chapter opener with the configured provider.
    Returns True on success, False to signal the caller to use the crest."""
    global LAST_ERROR
    p = provider()
    try:
        if p == "openai":
            _openai_opener(out_path, w_px, h_px, title, subtitle, book_title, style, mode, number)
            return True

        if p in ("pexels", "unsplash"):
            query = stock_query(title or brief, number)
            pick = random.Random(1000 + number).randint(0, 14)
            url = (_pexels_url if p == "pexels" else _unsplash_url)(query, w_px, h_px, pick)
            if not url:
                LAST_ERROR = "search returned no photos for the chapter query"
                return False
            img = Image.open(io.BytesIO(_http_bytes(url))).convert("RGB")
            img = _cover_resize(img, w_px, h_px)
            finish_opener(img, w_px, h_px, mode, out_path, title_band=True, photo=True)
            return True

        return False
    except Exception as e:
        LAST_ERROR = f"{type(e).__name__}: {e}"
        print(f"  [imagegen:{p}] falling back to crest ({LAST_ERROR})")
        return False
