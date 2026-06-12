"""Internal document model. The parser produces this; the renderer consumes it.

Keeping a clean intermediate model (rather than going docx->HTML directly) is what
lets the same manuscript drive any template, trim size, or colour mode.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Literal


# ---- inline + block content ------------------------------------------------

@dataclass
class Para:
    """A normal body paragraph (may contain simple inline HTML for italic/bold)."""
    html: str


@dataclass
class Subhead:
    """A section sub-heading within a chapter (bold title line, not a pull-quote)."""
    text: str


@dataclass
class PullQuote:
    """A highlighted callout pulled out of the running text."""
    text: str


@dataclass
class ListBlock:
    items: List[str]
    ordered: bool = False


@dataclass
class ActionStep:
    """The recurring end-of-chapter exercise module."""
    title: str
    blocks: List[object] = field(default_factory=list)   # Para | ListBlock


# ---- chapter + book --------------------------------------------------------

@dataclass
class Chapter:
    number: int
    title: str
    subtitle: str = ""                  # optional deck shown under the opener title
    blocks: List[object] = field(default_factory=list)   # Para | PullQuote | ListBlock | ActionStep | Subhead
    image: Optional[str] = None        # path to chapter-opener art
    image_prompt: str = ""             # the brief used to generate/select the art

    @property
    def anchor(self) -> str:
        return f"chap-{self.number}"


@dataclass
class FrontMatterPiece:
    """A roman-numeralled front-matter section (e.g. 'Before You Begin')."""
    title: str
    blocks: List[object] = field(default_factory=list)
    show_title: bool = True

    @property
    def anchor(self) -> str:
        slug = "".join(c.lower() if c.isalnum() else "-" for c in self.title).strip("-")
        return f"fm-{slug}"


@dataclass
class BookMeta:
    title: str
    subtitle: str = ""
    author: str = ""
    isbn: str = ""
    publisher: str = ""
    publisher_lines: List[str] = field(default_factory=list)
    year: str = ""
    edition: str = "First Edition"
    rights: str = (
        "All rights reserved. No part of this book may be reproduced, distributed, "
        "stored in a retrieval system, or transmitted in any form or by any means, "
        "electronic or mechanical, including photocopying, recording, or otherwise, "
        "without the prior written permission of the author, except in the case of "
        "brief quotations used in reviews or educational materials."
    )
    disclaimer: str = ""
    epigraph: str = ""          # optional opening quote page


@dataclass
class Book:
    meta: BookMeta
    front_matter: List[FrontMatterPiece] = field(default_factory=list)
    chapters: List[Chapter] = field(default_factory=list)
    closing: Optional[FrontMatterPiece] = None   # e.g. "A Final Word"
    back_matter: List[FrontMatterPiece] = field(default_factory=list)  # extra: endnotes, etc.
    notes: str = ""                              # parser diagnostics (e.g. structure fallback)
