# BookForge

Automatic manuscript → print-ready book. Drop in a `.docx`, get back a press-ready
interior PDF (B&W or colour, correct trim, bleed, crop marks, roman/arabic folios,
auto table of contents, chapter-opener art, running heads, pull-quotes, and
end-of-chapter exercise modules).

This is the **formatting engine** — the hard, deterministic core that the hosted
multi-user product wraps. Two clearly-marked seams are where the cloud version
plugs in its AI calls; everything else is final.

## What it does, automatically

Given a plain author manuscript (Heading-1 chapter titles, normal paragraphs, the
occasional bold line, "Your Nth Action Step", bullet lists), it:

1. **Parses structure** (`parser.py`) — classifies front matter, chapters, and the
   closing section; detects pull-quotes, lists, and the recurring action-step module.
2. **Generates chapter art** (`images.py`) — a procedural grayscale/duotone opener
   per chapter. *(Production seam #1: replace `generate_opener()` with a text-to-image
   call seeded by `brief_for_chapter()`.)*
3. **Lays out the book** (`styles.py` + `render.py`) — HTML + paged-media CSS:
   full-bleed openers, mirrored gutters, running heads, auto-TOC with dot leaders and
   real page numbers, tinted action-step callouts.
4. **Renders & assembles** (`build.py`) — WeasyPrint to PDF, front matter (roman) and
   body (arabic from 1) merged with correct recto alignment.

## Usage

```bash
python -m bookforge manuscript.docx out.pdf \
    --title "You Can Do It" --subtitle "A Journey From Doubt to Destiny" \
    --author "Benjamin Beckley" --isbn "9798248036295" \
    --publisher "Vision Power Publishers" --year 2026 \
    --epigraph "No matter where you are..." \
    --mode bw --trim 6x9 --no-crop-marks      # KDP-ready interior
```

`--mode {bw,color}` · `--trim {6x9,5.5x8.5,5x8,5.25x8,8.5x11}` ·
`--no-crop-marks` omits printer marks (KDP wants a clean trim+bleed box; offset
printers want the marks).

## Install

```bash
pip install weasyprint python-docx pillow pypdf
# fonts: assets/fonts/Oswald.ttf, EBGaramond.ttf, EBGaramond-Italic.ttf (OFL)
```

## Architecture seams for the hosted product

| Seam | File | Swap in |
|------|------|---------|
| Structure tagging of messy manuscripts | `parser.py` | an LLM pass to resolve ambiguous pull-quotes / section roles |
| Chapter-opener imagery | `images.py::generate_opener` | a text-to-image API keyed on `brief_for_chapter()` |
| Fonts | `assets/fonts` | licensed display/body faces (current ones are OFL) |

## Engineering notes

* **Folio restart.** WeasyPrint 69 ignores `counter-reset:page` / `counter-set:page`,
  so front matter (roman) and body (arabic, restarting at 1) are rendered as two
  documents and merged with `pypdf`; a blank is padded so the body opens on a recto.
* **TOC page numbers** come from the body document's bookmark tree, injected as
  literal numbers — accurate across the front/body split.
* **Bleed & marks** use the CSS `@page { bleed; marks: crop }` paged-media model;
  full-bleed openers extend `0.125in` past trim on every side.

## Known production hardening (not yet done)

True CMYK / PDF-X-1a export (WeasyPrint emits RGB; a Ghostscript K-only/CMYK
conversion pass belongs after render), font embedding/subset licensing checks,
widow/orphan and image-DPI validation, and a cover-wrap generator (this engine
produces the **interior** only).
