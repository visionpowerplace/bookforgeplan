"""docx -> Book model, with robust structure detection for real manuscripts.

Detection runs in priority order so that strong, unambiguous markers win and noisy
typographic guessing is only a last resort:

  1. Style / outline       Heading1, Title, Heading2, or w:outlineLvl (language-independent)
  2. Explicit markers      "CHAPTER ONE", "Part II", and INTRODUCTION / CONCLUSION /
                           EPILOGUE / ENDNOTES keyword lines  (author TOC lines excluded)
  3. Typographic heuristic  only when neither of the above exists (caps/bold/centered/
                           larger font / page-break) — used for fully unstyled drafts
  4. Single section        if nothing is found, the whole manuscript is still formatted

Real-world handling: a bare "CHAPTER ONE" line takes its display title from the next
line; the author's own typed Table of Contents is dropped (we generate one); bold
in-chapter title lines become sub-headings, not pull-quotes; text in tables is read.
"""
import html
import re
from collections import Counter

from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from docx.table import Table

from .model import (Book, BookMeta, Chapter, FrontMatterPiece,
                    Para, Subhead, PullQuote, ListBlock, ActionStep)

FRONT_HINTS = ("before you begin", "introduction", "preface", "foreword",
               "how to use", "author's note", "dedication", "prologue")
CLOSING_HINTS = ("final word", "conclusion", "afterword", "closing", "epilogue",
                 "about the author", "next steps", "endnote", "notes",
                 "bibliography", "references", "appendix", "acknowledg")

_NUMWORDS = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
             "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
             "eighteen", "nineteen", "twenty"]
_NUMWORD = "|".join(sorted(_NUMWORDS, key=len, reverse=True))  # longest first so 'fourteen' beats 'four'
_CHAP_RE = re.compile(
    r"^\s*(chapter|chap\.?|part|section|lesson|day|step|secret|key|principle|week|move)\s+"
    r"([0-9]{1,3}|[ivxlcdm]{1,7}|" + _NUMWORD + r")\b", re.I)
_NUM_ONLY_RE = re.compile(r"^\s*([0-9]{1,3}|[ivxlcdm]{1,7})[\.\):]?\s*$", re.I)
_CHAP_PREFIX_RE = re.compile(
    r"^\s*(chapter|chap\.?|part|section|lesson|day|step|secret|key|principle|week|move)\s+"
    r"([0-9]{1,3}|[ivxlcdm]{1,7}|" + _NUMWORD + r")\s*[:.\-\u2013\u2014]?\s*", re.I)
_TOC_LINE_RE = re.compile(r"[.\u2026]{3,}")           # dot-leader run -> a contents line


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _clean_chapter_title(t: str) -> str:
    stripped = _CHAP_PREFIX_RE.sub("", t).strip()
    return stripped if len(stripped) >= 2 else t.strip()


# ---------------------------------------------------------------- content access

def _iter_paragraphs(doc):
    out = []
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            out.append(Paragraph(child, doc))
        elif child.tag == qn("w:tbl"):
            for row in Table(child, doc).rows:
                for cell in row.cells:
                    out.extend(cell.paragraphs)
    return out


def _runs_to_html(p) -> str:
    out = []
    for r in p.runs:
        t = html.escape(r.text)
        if not t:
            continue
        if r.italic:
            t = f"<em>{t}</em>"
        if r.bold:
            t = f"<strong>{t}</strong>"
        out.append(t)
    return "".join(out).strip()


# ---------------------------------------------------------------- paragraph probes

def _style_key(p):
    return (getattr(p.style, "style_id", "") or "").lower(), (p.style.name or "").lower()


def _outline_level(p):
    pPr = p._p.find(qn("w:pPr"))
    if pPr is None:
        return None
    o = pPr.find(qn("w:outlineLvl"))
    if o is None:
        return None
    try:
        return int(o.get(qn("w:val")))
    except (TypeError, ValueError):
        return None


def _page_break_before(p) -> bool:
    pPr = p._p.find(qn("w:pPr"))
    if pPr is not None and pPr.find(qn("w:pageBreakBefore")) is not None:
        return True
    return p._p.find(".//" + qn("w:br") + "[@" + qn("w:type") + "='page']") is not None


def _is_centered(p) -> bool:
    try:
        return p.paragraph_format.alignment is not None and int(p.paragraph_format.alignment) == 1
    except Exception:
        return False


def _all_bold(p) -> bool:
    runs = [r for r in p.runs if r.text.strip()]
    return bool(runs) and all(r.bold for r in runs)


def _max_font_pt(p):
    sizes = [r.font.size.pt for r in p.runs if r.font.size]
    if not sizes:
        try:
            if p.style.font.size:
                sizes = [p.style.font.size.pt]
        except Exception:
            pass
    return max(sizes) if sizes else None


def _is_listish(p) -> bool:
    sid, name = _style_key(p)
    if "list" in name:
        return True
    return p._p.find(".//" + qn("w:numPr")) is not None


def _is_ordered(p) -> bool:
    return "number" in (p.style.name or "").lower()


def _is_quote_style(p) -> bool:
    return "quote" in (p.style.name or "").lower()


def _is_toc_line(t: str) -> bool:
    return bool(_TOC_LINE_RE.search(t)) or bool(re.search(r"\.{2,}\s*\d{1,3}\s*$", t))


def _classify_section(title: str):
    t = title.lower()
    if any(h in t for h in CLOSING_HINTS):
        return "closing"
    if any(h in t for h in FRONT_HINTS):
        return "front"
    return "chapter"


# ---------------------------------------------------------------- heading detection

def _style_level(p):
    sid, name = _style_key(p)
    if sid in ("title", "heading1") or name == "title" or name.startswith("heading 1"):
        return 0
    if sid == "heading2" or name.startswith("heading 2"):
        return 1
    lvl = _outline_level(p)
    if lvl in (0, 1):
        return lvl
    return None


def _marker_level(p):
    """Strong, low-false-positive chapter markers (styles, patterns, keywords)."""
    text = p.text.strip()
    if not text:
        return None
    sl = _style_level(p)
    if sl is not None:
        return sl
    if _is_toc_line(text):                       # author's contents entry, never a marker
        return None
    if _CHAP_RE.match(text) and len(text) <= 90:
        return 0
    if len(text) <= 42 and _classify_section(text) in ("front", "closing"):
        if text == text.upper() or _all_bold(p):  # a standalone INTRODUCTION/CONCLUSION line
            return 0
    return None


def _heuristic_level(p, body_pt):
    """Typographic guess for fully unstyled drafts only."""
    text = p.text.strip()
    if not text or len(text) > 80 or len(text.split()) > 12 or _is_toc_line(text):
        return None
    strong = 0
    if _page_break_before(p):
        strong += 1
    if _all_bold(p):
        strong += 1
    if any(c.isalpha() for c in text) and text == text.upper():
        strong += 1
    sz = _max_font_pt(p)
    if sz and body_pt and sz >= body_pt + 2:
        strong += 1
    if _is_centered(p):
        strong += 1
    if _NUM_ONLY_RE.match(text) and (_page_break_before(p) or (sz and body_pt and sz >= body_pt + 2)):
        return 0
    if strong >= 2 and text[-1] not in ".!?,;:":
        return 0
    return None


def _looks_title(p, body_pt) -> bool:
    t = p.text.strip()
    if not t or len(t) > 90 or len(t.split()) > 14:
        return False
    sz = _max_font_pt(p)
    big = bool(sz and body_pt and sz >= body_pt + 1.5)
    return (_all_bold(p) or big) and t[-1] not in ".!?"


def _dominant_size(paras) -> float:
    c = Counter()
    for p in paras:
        for r in p.runs:
            if r.font.size and r.text.strip():
                c[round(r.font.size.pt)] += len(r.text)
    return c.most_common(1)[0][0] if c else 11.0


# ---------------------------------------------------------------- main entry

def parse_docx(path: str, meta: BookMeta) -> Book:
    doc = Document(path)
    paras = _iter_paragraphs(doc)
    body_pt = _dominant_size(paras)
    book = Book(meta=meta)

    # choose the detection mode.
    # strong = real chapter markers (heading style / outline / "Chapter N");
    # kw = front/closing keyword section lines (Introduction, Conclusion, ...).
    strong, kw = [], []
    for i, p in enumerate(paras):
        text = p.text.strip()
        if not text:
            continue
        sl = _style_level(p)
        if sl is not None:
            strong.append((i, sl)); continue
        if _is_toc_line(text):
            continue
        if _CHAP_RE.match(text) and len(text) <= 90:
            strong.append((i, 0)); continue
        if len(text) <= 42 and _classify_section(text) in ("front", "closing") \
                and (text == text.upper() or _all_bold(p)):
            kw.append(i)

    if strong:                       # real chapter markers present -> trust them
        present = {lv for _, lv in strong}
        chap_level = 0 if 0 in present else 1
        head_idx = sorted(set([i for i, lv in strong if lv == chap_level] + kw))
    else:                            # no chapter markers -> use typographic cues + keywords
        heur = [i for i, p in enumerate(paras) if _heuristic_level(p, body_pt) == 0]
        head_idx = sorted(set(heur + kw))

    # nothing found -> format the whole manuscript as one section
    if not head_idx:
        blocks = _blocks_from_paras(paras)
        if blocks:
            book.chapters.append(Chapter(number=1, title=(meta.title or "Chapter 1"), blocks=blocks))
            book.notes = ("No chapter headings were detected, so the manuscript was formatted "
                          "as a single section. Mark chapter titles with Word's Heading 1 style "
                          "(or start each on a new page) to split it into chapters.")
        else:
            book.notes = "No readable text was found in the document."
        return book

    meta_keys = {_norm(meta.title), _norm(meta.author), _norm(meta.subtitle)} - {""}
    bounds = head_idx + [len(paras)]

    # ---- pre-content (before first marker): drop title block + author TOC ----
    pre_blocks = _clean_pre(paras[:head_idx[0]], meta, meta_keys)
    pre_text = sum(len(getattr(b, "html", "") or getattr(b, "text", "")) for b in pre_blocks)
    if pre_blocks and pre_text >= 200:
        book.front_matter.append(FrontMatterPiece(title="Preface", blocks=pre_blocks, show_title=False))

    # ---- build sections ----
    chap_no = 0
    closings = []
    for k in range(len(head_idx)):
        mi, nxt = head_idx[k], bounds[k + 1]
        marker = paras[mi].text.strip()
        m = _CHAP_RE.match(marker)
        # skip a title-page heading (book title / subtitle / author appearing as a heading)
        if not m and (_norm(marker) in meta_keys or re.match(r"^\s*by\s+\w", marker, re.I)):
            continue
        kind = _classify_section(marker)
        remainder = marker[m.end():].strip(" :.\u2013\u2014-") if m else ""
        body_start = mi + 1
        subtitle = ""

        if kind == "chapter":
            if m and remainder:
                title = remainder
            elif m and not remainder:
                j = mi + 1
                while j < nxt and not paras[j].text.strip():
                    j += 1
                if j < nxt and _looks_title(paras[j], body_pt):
                    title = paras[j].text.strip()
                    body_start = j + 1
                    # optional deck line right after the title
                    if body_start < nxt:
                        d = paras[body_start].text.strip()
                        if d and len(d) <= 90 and d[-1:] not in ".!?" and not _looks_title(paras[body_start], body_pt):
                            subtitle = d
                            body_start += 1
                else:
                    title = marker.title()
            else:
                title = marker
        else:
            title = remainder if (m and remainder) else marker.strip().title()

        blocks = _blocks_from_paras(paras[body_start:nxt])
        if kind == "front" and chap_no == 0:
            book.front_matter.append(FrontMatterPiece(title=title, blocks=blocks))
        elif kind == "closing" or (kind == "front" and chap_no > 0):
            closings.append(FrontMatterPiece(title=title, blocks=blocks))
        else:
            chap_no += 1
            book.chapters.append(Chapter(number=chap_no, title=_clean_chapter_title(title),
                                         subtitle=subtitle, blocks=blocks))

    if closings:
        book.closing = closings[0]
        book.back_matter = closings[1:]

    # safety net
    if not book.chapters:
        book.chapters.append(Chapter(number=1, title=(meta.title or "Chapter 1"),
                                     blocks=_blocks_from_paras(paras)))
        book.notes = "No chapter-level headings were found; formatted as a single chapter."
    return book


def _clean_pre(pre_paras, meta, meta_keys):
    """Remove the title block and the author's typed table of contents from the
    pre-chapter region; salvage a scripture/permission note to the copyright page."""
    title_norm = _norm(meta.title)
    keep = []
    for p in pre_paras:
        t = p.text.strip()
        if not t:
            continue
        nt = _norm(t)
        if nt in meta_keys:
            continue
        if t == t.upper() and any(c.isalpha() for c in t) and nt and nt in title_norm and len(t.split()) <= 3:
            continue                                   # title split across caps lines
        if re.match(r"^\s*by\s+\w", t, re.I):
            continue
        if t.lower().startswith("table of contents") or t.lower() == "contents":
            continue
        if _is_toc_line(t):
            continue
        if t.lower().startswith("note") or "scripture" in t.lower():
            if not meta.disclaimer:
                meta.disclaimer = t
            continue
        keep.append(p)
    return _blocks_from_paras(keep)


# ---------------------------------------------------------------- block builder

def _blocks_from_paras(paras):
    blocks = []
    list_buf, list_ordered = [], False
    in_action, action = False, None

    def flush_list(target):
        nonlocal list_buf
        if list_buf:
            target.append(ListBlock(items=list_buf[:], ordered=list_ordered))
            list_buf = []

    for p in paras:
        text = p.text.strip()
        if not text:
            continue
        if re.fullmatch(r"(chapter\s+\d+|\d{1,3}|[ivxl]{1,6})", text.lower()):
            continue
        if _is_toc_line(text):                       # stray contents line
            continue

        target = action.blocks if in_action else blocks

        if "action step" in text.lower() and len(text) < 70:
            flush_list(target)
            if in_action:
                blocks.append(action)
            action = ActionStep(title=text)
            in_action = True
            continue

        if _is_listish(p):
            list_ordered = _is_ordered(p)
            list_buf.append(_runs_to_html(p) or html.escape(text))
            continue
        flush_list(target)

        if _is_quote_style(p):
            target.append(PullQuote(text=text))
        elif _all_bold(p) and len(text) < 240:
            words = len(text.split())
            if words <= 9 and text[-1] not in ".!?":
                target.append(Subhead(text=text))    # in-chapter section heading
            else:
                target.append(PullQuote(text=text))
        else:
            target.append(Para(html=_runs_to_html(p) or html.escape(text)))

    if in_action:
        flush_list(action.blocks)
        blocks.append(action)
    else:
        flush_list(blocks)
    return blocks
