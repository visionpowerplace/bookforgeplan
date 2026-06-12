"""
BookForge — automatic manuscript-to-print-ready-book formatter.

Pipeline:  .docx  ->  parse (structure detection)  ->  Book model
                  ->  procedural/AI chapter art
                  ->  HTML + paged-media CSS
                  ->  WeasyPrint  ->  print-ready PDF (B&W or color, with bleed + crop marks)

The valuable, deterministic core lives here. In the hosted product the only
swap-ins are: (1) an LLM call inside parser.py to tag ambiguous structure, and
(2) a text-to-image call inside images.py to replace the procedural art.
"""
__version__ = "0.1.0"
