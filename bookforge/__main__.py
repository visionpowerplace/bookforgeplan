"""CLI:  python -m bookforge manuscript.docx out.pdf --mode bw --trim 6x9 \
            --title "..." --author "..." --isbn "..."  [--no-crop-marks]
"""
import argparse
from .model import BookMeta
from .theme import Theme, Fonts, TRIM_SIZES, FONT_THEMES
from .build import build_book


def main():
    ap = argparse.ArgumentParser(prog="bookforge",
        description="Automatically format a .docx manuscript into a print-ready book PDF.")
    ap.add_argument("docx")
    ap.add_argument("pdf")
    ap.add_argument("--title", default="Untitled")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--author", default="")
    ap.add_argument("--isbn", default="")
    ap.add_argument("--publisher", default="")
    ap.add_argument("--year", default="")
    ap.add_argument("--epigraph", default="")
    ap.add_argument("--mode", choices=["bw", "color"], default="bw")
    ap.add_argument("--trim", choices=list(TRIM_SIZES), default="6x9")
    ap.add_argument("--font", choices=list(FONT_THEMES), default="classic",
                    help="typeface pairing")
    ap.add_argument("--art-style", default="emblem",
                    help="emblem (vector crest) or an AI style: photographic, cinematic, "
                         "watercolor, painterly, lineart, abstract")
    ap.add_argument("--no-crop-marks", action="store_true",
                    help="omit printer crop marks (KDP-ready interior)")
    a = ap.parse_args()

    meta = BookMeta(title=a.title, subtitle=a.subtitle, author=a.author,
                    isbn=a.isbn, publisher=a.publisher, year=a.year, epigraph=a.epigraph)
    theme = Theme(trim=a.trim, mode=a.mode, crop_marks=not a.no_crop_marks,
                  font=a.font, art_style=a.art_style)
    print(f"BookForge: {a.docx} -> {a.pdf}")
    build_book(a.docx, a.pdf, meta, theme)


if __name__ == "__main__":
    main()
