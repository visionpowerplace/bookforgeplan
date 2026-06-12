"""Book model -> HTML. Rendered as two independently-numbered documents
(front matter in roman, body in arabic-from-1) because WeasyPrint cannot restart
the page counter mid-document; build.py merges them. The body carries PDF
bookmarks so build.py can read true chapter page numbers for the TOC.
"""
import html
from .model import Book, Para, Subhead, PullQuote, ListBlock, ActionStep


def _esc(s: str) -> str:
    return html.escape(s, quote=False)


def _render_blocks(blocks, first_para_plain=True) -> str:
    out, first = [], first_para_plain
    for b in blocks:
        if isinstance(b, Para):
            cls = ' class="first"' if first else ""
            out.append(f"<p{cls}>{b.html}</p>")
            first = False
        elif isinstance(b, Subhead):
            out.append(f'<h3 class="subhead">{_esc(b.text)}</h3>')
            first = True
        elif isinstance(b, PullQuote):
            out.append(f'<p class="pull-quote">{_esc(b.text)}</p>')
            first = True
        elif isinstance(b, ListBlock):
            tag = "ol" if b.ordered else "ul"
            cls = "num" if b.ordered else "bul"
            lis = "".join(f"<li>{it}</li>" for it in b.items)
            out.append(f'<{tag} class="{cls}">{lis}</{tag}>')
            first = True
        elif isinstance(b, ActionStep):
            inner = _render_blocks(b.blocks, first_para_plain=True)
            out.append(f'<div class="action"><h3>{_esc(b.title)}</h3>{inner}</div>')
            first = True
    return "".join(out)


def _doc(css: str, body: str) -> str:
    return (f"<html><head><meta charset='utf-8'><style>{css}</style></head>"
            f"<body>{body}</body></html>")


def render_body_html(book: Book, css: str) -> str:
    """Chapters + closing. Each chapter/closing gets a bookmark so the caller can
    read its page number. Page numbering starts at 1 (standalone document)."""
    P = []
    for ch in book.chapters:
        img = f'<img src="file://{ch.image}" alt="">' if ch.image else ""
        deck = f'<div class="deck">{_esc(ch.subtitle)}</div>' if ch.subtitle else ""
        P.append(
            f'<section class="opener" id="{ch.anchor}" '
            f'style="bookmark-level:1; bookmark-label:\'{ch.anchor}\'">{img}'
            f'<div class="scrim"></div><div class="inner">'
            f'<div class="eyebrow">Chapter {ch.number:02d}</div>'
            f'<h1>{_esc(ch.title)}</h1>{deck}</div></section>')
        P.append('<section class="chapter-body">')
        P.append(f'<p class="run-title">{_esc(ch.title)}</p>')
        P.append(_render_blocks(ch.blocks))
        P.append('</section>')

    for piece in ([book.closing] if book.closing else []) + list(book.back_matter):
        P.append(f'<section class="closing" id="{piece.anchor}" '
                 f'style="bookmark-level:1; bookmark-label:\'{piece.anchor}\'">')
        P.append(f'<p class="run-title">{_esc(piece.title)}</p>')
        P.append(f'<h1>{_esc(piece.title)}</h1>')
        P.append(_render_blocks(piece.blocks))
        P.append('</section>')
    return _doc(css, "".join(P))


def render_front_html(book: Book, css: str, page_of: dict) -> str:
    """Title, copyright, epigraph, auto-TOC, and front-matter prose.
    `page_of` maps anchor -> arabic page number in the merged book (chapters/closing)."""
    m = book.meta
    P = []

    # half-title / title page
    P.append('<section class="titlepage">')
    P.append(f'<div class="bt">{_esc(m.title)}</div>')
    if m.subtitle:
        P.append(f'<div class="sub">{_esc(m.subtitle)}</div>')
    P.append('<div class="orn">&#10070;</div>')
    if m.author:
        P.append(f'<div class="au">{_esc(m.author)}</div>')
    P.append('</section>')

    # copyright
    P.append('<section class="copyright">')
    P.append(f'<div class="ttl">{_esc(m.title)}</div>')
    P.append(f'<p>&copy; {_esc(m.author)} {_esc(m.year)}</p>')
    if m.isbn:
        P.append(f'<p>ISBN: {_esc(m.isbn)}</p>')
    P.append(f'<p>{_esc(m.rights)}</p>')
    if m.disclaimer:
        P.append(f'<p>{_esc(m.disclaimer)}</p>')
    if m.edition:
        P.append(f'<p>{_esc(m.edition)}</p>')
    P.append('<p>Printed in the United States of America</p>')
    if m.publisher:
        P.append(f'<p><strong>{_esc(m.publisher)}</strong></p>')
    for line in m.publisher_lines:
        P.append(f'<p>{_esc(line)}</p>')
    P.append('</section>')

    # epigraph (optional)
    if m.epigraph:
        P.append(f'<section class="epigraph"><div class="q">{_esc(m.epigraph)}</div></section>')

    # table of contents
    P.append('<nav class="toc"><h2>Table of Contents</h2><ul>')
    for fm in book.front_matter:           # roman, resolved inside this front document
        P.append(f'<li class="roman nonum"><span class="num"></span>'
                 f'<a class="entry" href="#{fm.anchor}"><span class="t">{_esc(fm.title)}</span></a></li>')
    for ch in book.chapters:               # arabic, literal page from body render
        pg = page_of.get(ch.anchor, "")
        P.append(f'<li><span class="num">{ch.number}</span>'
                 f'<a class="entry" href="#{ch.anchor}"><span class="t">{_esc(ch.title)}</span></a>'
                 f'<span class="pg">{pg}</span></li>')
    if book.closing:
        pg = page_of.get(book.closing.anchor, "")
        P.append(f'<li class="nonum"><span class="num"></span>'
                 f'<a class="entry" href="#{book.closing.anchor}"><span class="t">{_esc(book.closing.title)}</span></a>'
                 f'<span class="pg">{pg}</span></li>')
    for piece in book.back_matter:
        pg = page_of.get(piece.anchor, "")
        P.append(f'<li class="nonum"><span class="num"></span>'
                 f'<a class="entry" href="#{piece.anchor}"><span class="t">{_esc(piece.title)}</span></a>'
                 f'<span class="pg">{pg}</span></li>')
    P.append('</ul></nav>')

    # front-matter prose (roman folios continue from title page)
    for fm in book.front_matter:
        P.append(f'<section class="frontsec" id="{fm.anchor}">')
        if fm.show_title:
            P.append(f'<h1>{_esc(fm.title)}</h1>')
        P.append(_render_blocks(fm.blocks))
        P.append('</section>')

    return _doc(css, "".join(P))
