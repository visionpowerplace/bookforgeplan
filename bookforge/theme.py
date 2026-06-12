"""Design tokens: trim sizes, page geometry, colour modes, and the font stack.

Everything visual that a non-engineer would call a "template choice" is captured
here, so the same Book model can be rendered B&W or colour, 6x9 or 5.5x8.5, etc.
"""
from dataclasses import dataclass, field
from typing import Dict, Tuple


# Standard POD/offset trim sizes (inches). Spine/gutter scale with page count.
TRIM_SIZES: Dict[str, Tuple[float, float]] = {
    "4x6":      (4.0, 6.0),     # pocket / digest
    "5x8":      (5.0, 8.0),     # compact
    "5.25x8":   (5.25, 8.0),
    "5.5x8.5":  (5.5, 8.5),     # trade
    "6x9":      (6.0, 9.0),     # most common nonfiction
    "8.5x11":   (8.5, 11.0),    # workbook
}

BLEED_IN = 0.125   # industry standard


def gutter_for_page_count(pages: int) -> float:
    """KDP-style inside-margin (gutter) growth. Thicker book -> deeper gutter."""
    if pages <= 150:
        return 0.375 + 0.25      # base + safety
    if pages <= 300:
        return 0.5 + 0.25
    if pages <= 500:
        return 0.625 + 0.25
    return 0.75 + 0.25


@dataclass
class Palette:
    ink: str            # body text
    accent: str         # chapter numbers, rules, action-step trims
    accent_soft: str    # tints / fills
    rule: str
    opener_overlay: str # gradient laid over chapter art for legibility
    image_mode: str     # 'grayscale' | 'duotone' | 'color'


PALETTES: Dict[str, Palette] = {
    "bw": Palette(
        ink="#141414",
        accent="#000000",
        accent_soft="#ECECEC",
        rule="#111111",
        opener_overlay="linear-gradient(180deg, rgba(0,0,0,0) 30%, rgba(0,0,0,.16) 70%, rgba(0,0,0,.40) 100%)",
        image_mode="grayscale",
    ),
    "color": Palette(
        ink="#1c2230",
        accent="#2f3a8f",          # deep indigo
        accent_soft="#eaecf8",
        rule="#2f3a8f",
        opener_overlay="linear-gradient(180deg, rgba(18,22,46,0) 30%, rgba(18,22,46,.18) 70%, rgba(18,22,46,.46) 100%)",
        image_mode="duotone",
    ),
}


@dataclass
class Fonts:
    # family names registered via @font-face in styles.py
    display: str = "BF Display"     # heavy condensed grotesque (Oswald)
    body: str = "BF Body"           # book serif (EB Garamond)
    eyebrow: str = "BF Body"        # 'CHAPTER 0X' set in letterspaced caps


# Selectable typeface pairings (display + body). Files live in assets/fonts/.
FONT_THEMES: Dict[str, dict] = {
    "classic": {"label": "Oswald + EB Garamond (condensed sans / classic serif)",
                "display": "Oswald.ttf", "body": "EBGaramond.ttf",
                "body_italic": "EBGaramond-Italic.ttf"},
    "editorial": {"label": "Playfair Display + Lora (elegant serif / readable serif)",
                  "display": "PlayfairDisplay.ttf", "body": "Lora.ttf",
                  "body_italic": "Lora-Italic.ttf"},
    "modern": {"label": "Montserrat + Lora (geometric sans / serif)",
               "display": "Montserrat.ttf", "body": "Lora.ttf",
               "body_italic": "Lora-Italic.ttf"},
    "bold": {"label": "Anton + EB Garamond (heavy display / classic serif)",
             "display": "Anton-Regular.ttf", "body": "EBGaramond.ttf",
             "body_italic": "EBGaramond-Italic.ttf"},
}


@dataclass
class Theme:
    trim: str = "6x9"
    mode: str = "bw"                # 'bw' | 'color'
    crop_marks: bool = True         # printer marks for offset; off for KDP-ready
    base_font_pt: float = 11.0
    leading: float = 1.42
    font: str = "classic"           # key into FONT_THEMES
    art_style: str = "emblem"       # 'emblem' (vector crest) or an AI style, e.g. 'photographic'
    fonts: Fonts = field(default_factory=Fonts)

    @property
    def trim_wh(self) -> Tuple[float, float]:
        return TRIM_SIZES[self.trim]

    @property
    def palette(self) -> Palette:
        return PALETTES[self.mode]

    @property
    def font_files(self) -> dict:
        return FONT_THEMES.get(self.font, FONT_THEMES["classic"])
