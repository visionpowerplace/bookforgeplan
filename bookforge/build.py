"""End-to-end build: .docx manuscript -> print-ready PDF.

Front matter (roman folios) and body (arabic from 1) are rendered as two
WeasyPrint documents and merged, because WeasyPrint cannot restart the page
counter mid-document. True chapter page numbers for the TOC are read from the
body document's bookmark tree.
"""
import hashlib
import io
import os
import shutil
import tempfile
from weasyprint import HTML
from pypdf import PdfWriter, PdfReader

from .model import BookMeta
from .theme import Theme, BLEED_IN
from .parser import parse_docx
from .images import generate_opener, brief_for_chapter
from . import imagegen
from .styles import build_css
from .render import render_body_html, render_front_html

ASSET_FONTS = os.path.join(os.path.dirname(__file__), "assets", "fonts")


def _pages_from_bookmarks(doc):
    """anchor(bookmark-label) -> 1-indexed page number within the document."""
    out = {}
    for label, target, *_ in doc.make_bookmark_tree():
        out[label] = target[0] + 1
    return out


def build_book(docx_path, out_pdf, meta: BookMeta, theme: Theme,
               art_dir=None, verbose=True):
    book = parse_docx(docx_path, meta)
    if verbose:
        print(f"  parsed: {len(book.front_matter)} front-matter, "
              f"{len(book.chapters)} chapters, "
              f"closing={'yes' if book.closing else 'no'}")
        if book.notes:
            print(f"  note: {book.notes}")

    # chapter art: AI photo (if a style is chosen and a provider is configured),
    # otherwise the procedural emblem crest. Results can be cached across renders.
    art_dir = art_dir or tempfile.mkdtemp(prefix="bf_art_")
    w, h = theme.trim_wh
    px_w = int((w + 2 * BLEED_IN) * 300)
    px_h = int((h + 2 * BLEED_IN) * 300)

    want_ai = theme.art_style and theme.art_style != "emblem"
    ai_ok = want_ai and imagegen.ai_available()
    if want_ai and not ai_ok:
        book.notes = (book.notes + " " if book.notes else "") + \
            "Real images were requested but no image provider is configured, so emblem " \
            "crests were used. Set IMAGE_PROVIDER (e.g. pexels) and the matching key " \
            "(e.g. PEXELS_API_KEY) on the server to enable real photos."
    cache_dir = os.environ.get("BOOKFORGE_ART_CACHE")

    ai_made = 0
    for ch in book.chapters:
        brief = brief_for_chapter(ch.title, ch.number)
        ch.image_prompt = brief
        path = os.path.join(art_dir, f"opener_{ch.number}.jpg")
        made = False
        if ai_ok:
            cpath = None
            if cache_dir:
                key = hashlib.sha1(
                    f"{book.meta.title}|{ch.title}|{theme.art_style}|{theme.mode}|{theme.trim}".encode()
                ).hexdigest()[:16]
                cpath = os.path.join(cache_dir, key + ".jpg")
            if cpath and os.path.exists(cpath):
                shutil.copyfile(cpath, path); made = True
            else:
                made = imagegen.generate_ai_opener(path, px_w, px_h, brief,
                                                   theme.art_style, theme.mode,
                                                   title=ch.title, number=ch.number,
                                                   subtitle=ch.subtitle, book_title=book.meta.title)
                if made and cpath:
                    os.makedirs(cache_dir, exist_ok=True)
                    shutil.copyfile(path, cpath)
            if made:
                ai_made += 1
        if not made:
            generate_opener(path, px_w, px_h, title=ch.title, number=ch.number,
                            mode=theme.mode, seed=1000 + ch.number * 7)
        ch.image = path

    if ai_ok and ai_made == 0:
        why = (" Reason: " + imagegen.LAST_ERROR) if imagegen.LAST_ERROR else ""
        book.notes = (book.notes + " " if book.notes else "") + \
            "Real-image generation failed for every chapter; emblem crests were used." + why
    if verbose:
        kind = f"AI photos ({ai_made}/{len(book.chapters)})" if ai_ok else "emblem crests"
        print(f"  generated {len(book.chapters)} chapter openers ({px_w}x{px_h}px @300dpi, {kind})")

    hint = max(60, len(book.chapters) * 4 + 12)

    # pass 1: body (arabic from 1) -> page numbers for the TOC
    body_css = build_css(theme, ASSET_FONTS, hint, part="body")
    body_doc = HTML(string=render_body_html(book, body_css), base_url=art_dir).render()
    page_of = _pages_from_bookmarks(body_doc)
    body_pdf = body_doc.write_pdf()

    # pass 2: front matter (roman) with the resolved TOC
    front_css = build_css(theme, ASSET_FONTS, hint, part="front")
    front_doc = HTML(string=render_front_html(book, front_css, page_of),
                     base_url=art_dir).render()
    front_n = len(front_doc.pages)
    front_pdf = front_doc.write_pdf()

    # merge: front + (blank to keep body on a recto) + body
    writer = PdfWriter()
    for p in PdfReader(io.BytesIO(front_pdf)).pages:
        writer.add_page(p)
    pad = front_n % 2 == 1
    if pad:
        pw = (w + 2 * BLEED_IN) * 72
        ph = (h + 2 * BLEED_IN) * 72
        writer.add_blank_page(width=pw, height=ph)
    for p in PdfReader(io.BytesIO(body_pdf)).pages:
        writer.add_page(p)
    with open(out_pdf, "wb") as f:
        writer.write(f)

    if verbose:
        total = front_n + (1 if pad else 0) + len(body_doc.pages)
        size_kb = os.path.getsize(out_pdf) // 1024
        print(f"  front={front_n}p (roman) + {'blank + ' if pad else ''}"
              f"body={len(body_doc.pages)}p (arabic) = {total}p total")
        print(f"  wrote {out_pdf} ({size_kb} KB)  trim={theme.trim} mode={theme.mode} "
              f"crop_marks={theme.crop_marks}")
    return book
