"""The print stylesheet. Tokens (%%NAME%%) are substituted from the Theme so one
template renders any trim size / colour mode. Uses WeasyPrint paged-media:
@page bleed+marks, mirrored margins, named strings (running heads),
target-counter + leader() (auto TOC), and a roman->arabic folio reset.
"""
import os
from .theme import Theme, BLEED_IN, gutter_for_page_count

_TEMPLATE = """
@font-face { font-family:"BF Display"; src:url("%%DISPLAY%%"); font-weight:200 700; }
@font-face { font-family:"BF Body"; src:url("%%BODY%%"); font-weight:400 800; font-style:normal; }
@font-face { font-family:"BF Body"; src:url("%%BODY_IT%%"); font-weight:400 800; font-style:italic; }

:root { --ink:%%INK%%; --accent:%%ACCENT%%; --soft:%%SOFT%%; --rule:%%RULE%%; }

/* ---- page geometry ---- */
@page {
  size: %%TRIM_W%%in %%TRIM_H%%in;
  bleed: %%BLEED%%in;
  %%MARKS%%
  @bottom-center { content: %%FOLIO%%; font-family:"BF Body"; font-size:9pt;
                   color:var(--ink); padding-top:6pt; }
  @top-center    { content: %%RUNHEAD%%; font-family:"BF Body"; font-size:8.5pt;
                   letter-spacing:.18em; text-transform:uppercase; color:var(--ink);
                   padding-bottom:10pt; }
}
@page :left  { margin: %%MT%%in %%MO%%in %%MB%%in %%MI%%in; }
@page :right { margin: %%MT%%in %%MI%%in %%MB%%in %%MO%%in; }

/* front matter: roman folio, no running head */
@page front { @top-center { content:none; }
              @bottom-center { content: counter(page, lower-roman); font-family:"BF Body";
                               font-size:9pt; color:var(--ink); padding-top:6pt; } }
@page plain  { @top-center { content:none; } @bottom-center { content:none; } }
@page :blank { @top-center { content:none; } @bottom-center { content:none; } }

/* full-bleed chapter opener */
@page opener { margin:0; @top-center{content:none;} @bottom-center{content:none;} }

/* ---- base type ---- */
html { font-family:"BF Body"; font-size:%%BASEPT%%pt; color:var(--ink);
       line-height:%%LEAD%%; hyphens:auto; }
body { margin:0; }
p { margin:0; text-align:justify; text-indent:1.25em; orphans:2; widows:2;
    overflow-wrap:break-word; }
p.first, h1 + p, .lead { text-indent:0; }
em { font-style:italic; } strong { font-weight:700; }
h1, h2, h3, .pull-quote, .opener h1, .opener .deck { overflow-wrap:break-word; }

/* ---- title / half-title page ---- */
.titlepage { page:plain; break-before:right; height:%%TRIM_H%%in; display:flex;
  flex-direction:column; justify-content:center; text-align:center; }
.titlepage .bt { font-family:"BF Display"; font-weight:700; text-transform:uppercase;
  font-size:46pt; line-height:.96; letter-spacing:.01em; }
.titlepage .sub { font-family:"BF Display"; font-weight:500; text-transform:uppercase;
  letter-spacing:.16em; font-size:12.5pt; color:var(--accent); margin-top:14pt; }
.titlepage .au { font-family:"BF Body"; font-size:13pt; letter-spacing:.22em;
  text-transform:uppercase; margin-top:42pt; }
.titlepage .orn { color:var(--accent); font-size:16pt; margin:20pt 0; }

/* ---- copyright ---- */
.copyright { page:plain; break-before:left; height:%%TRIM_H%%in; display:flex;
  flex-direction:column; justify-content:center; font-size:9.5pt; line-height:1.5;
  text-align:center; }
.copyright p { text-align:center; text-indent:0; margin:0 0 9pt; }
.copyright .ttl { font-family:"BF Display"; font-weight:700; text-transform:uppercase;
  font-size:18pt; line-height:1; margin-bottom:4pt; }

/* ---- epigraph ---- */
.epigraph { page:plain; break-before:right; height:%%TRIM_H%%in; display:flex;
  align-items:center; justify-content:center; padding:0 .7in; }
.epigraph .q { font-style:italic; font-size:18pt; line-height:1.45; text-align:center;
  text-indent:0; }
.epigraph .q::before { content:"\\201C"; font-family:"BF Display"; font-weight:700;
  font-style:normal; font-size:46pt; color:var(--accent); display:block; line-height:.4;
  margin-bottom:8pt; }

/* ---- table of contents ---- */
.toc { page:front; break-before:right; }
.toc h2 { font-family:"BF Display"; font-weight:600; text-transform:uppercase;
  letter-spacing:.05em; font-size:24pt; text-align:center; margin:.2in 0 .35in; }
.toc h2::after { content:""; display:block; width:60pt; height:2pt; background:var(--accent);
  margin:10pt auto 0; }
.toc ul { list-style:none; margin:0; padding:0; }
.toc li { display:grid; grid-template-columns:26pt 1fr auto; column-gap:9pt;
  align-items:baseline; margin:0 0 11pt; break-inside:avoid; }
.toc li.roman { grid-template-columns:26pt 1fr; }      /* roman page via ::after */
.toc .num { font-family:"BF Display"; font-weight:700; color:#fff; background:var(--accent);
  width:24pt; height:22pt; border-radius:5pt; display:flex; align-items:center;
  justify-content:center; font-size:11pt; }
.toc li.nonum .num { background:none; }                /* keep the column, hide the badge */
.toc a.entry { grid-column:2; color:var(--ink); text-decoration:none; display:block;
  font-family:"BF Display"; font-weight:500; text-transform:uppercase; letter-spacing:.04em;
  font-size:12pt; line-height:1.26; overflow-wrap:break-word; }
.toc a.entry::after { content:leader("."); }           /* dots fill to the page-number column */
.toc li.roman a.entry::after { content:leader(".") " " target-counter(attr(href url), page, lower-roman); }
.toc .pg { grid-column:3; justify-self:end; white-space:nowrap;
  font-family:"BF Body"; font-weight:700; font-size:11pt; }

/* ---- front-matter prose (intro etc.) ---- */
.frontsec { page:front; break-before:right; }
.closing  { break-before:right; }       /* body matter: arabic folio */
.frontsec h1, .closing h1 { font-family:"BF Display"; font-weight:600;
  text-transform:uppercase; font-size:22pt; letter-spacing:.03em; margin:.1in 0 .25in; }

/* ---- chapter opener ---- */
.opener { page:opener; break-before:right; position:relative;
  width:%%TRIM_W%%in; height:%%TRIM_H%%in; overflow:hidden; color:#fff; }
.opener img { position:absolute; top:-%%BLEED%%in; left:-%%BLEED%%in;
  width:%%OIMG_W%%in; height:%%OIMG_H%%in; }
.opener .scrim { position:absolute; inset:0; background:%%OVERLAY%%; }
.opener .inner { position:absolute; left:0; right:0; top:62%; transform:translateY(-50%);
  padding:0 .6in; text-align:center; }
.opener .eyebrow { font-family:"BF Display"; font-weight:500; letter-spacing:.34em;
  text-transform:uppercase; font-size:11pt; }
.opener .eyebrow::after { content:""; display:block; width:46pt; height:1.5pt;
  background:#fff; opacity:.85; margin:9pt auto 16pt; }
.opener h1 { font-family:"BF Display"; font-weight:700; text-transform:uppercase;
  font-size:31pt; line-height:1.04; margin:0; }
.opener .deck { font-family:"BF Body"; font-style:italic; font-size:13pt;
  line-height:1.3; margin-top:12pt; color:rgba(255,255,255,.92); }

/* ---- chapter body ---- */
.chapter-body { break-before:page; }
.chapter-body .run-title { string-set: chaptitle content(); height:0; overflow:hidden; }
h3.subhead { font-family:"BF Display"; font-weight:600; text-transform:uppercase;
  letter-spacing:.04em; font-size:12.5pt; color:var(--accent);
  margin:17pt 0 6pt; text-indent:0; break-after:avoid; }
.pull-quote { font-family:"BF Display"; font-weight:600; text-transform:none;
  font-size:16.5pt; line-height:1.28; text-align:center; text-indent:0;
  margin:20pt .3in; color:var(--ink); }
.pull-quote::before { content:""; display:block; width:34pt; height:2.5pt;
  background:var(--accent); margin:0 auto 12pt; }

ul.bul, ol.num { margin:10pt 0 10pt 1.1em; padding:0; }
ul.bul li, ol.num li { margin:0 0 5pt; text-align:left; }

/* ---- action-step module ---- */
.action { background:var(--soft); border-left:4pt solid var(--accent);
  padding:16pt 18pt; margin:22pt 0 6pt; break-inside:avoid; }
.action h3 { font-family:"BF Display"; font-weight:600; text-transform:uppercase;
  letter-spacing:.06em; font-size:13pt; color:var(--accent); margin:0 0 9pt; }
.action p { text-indent:0; margin:0 0 8pt; text-align:left; }
.action ul.bul, .action ol.num { margin-top:6pt; }
"""


def build_css(theme: Theme, font_dir: str, n_pages_hint: int = 120, part: str = "body") -> str:
    w, h = theme.trim_wh
    pal = theme.palette
    gut = gutter_for_page_count(n_pages_hint)
    folio = "counter(page, lower-roman)" if part == "front" else "counter(page)"
    runhead = "none" if part == "front" else "string(chaptitle)"
    ff = theme.font_files
    repl = {
        "DISPLAY": "file://" + os.path.join(font_dir, ff["display"]),
        "BODY": "file://" + os.path.join(font_dir, ff["body"]),
        "BODY_IT": "file://" + os.path.join(font_dir, ff["body_italic"]),
        "INK": pal.ink, "ACCENT": pal.accent, "SOFT": pal.accent_soft, "RULE": pal.rule,
        "OVERLAY": pal.opener_overlay,
        "TRIM_W": f"{w:g}", "TRIM_H": f"{h:g}",
        "BLEED": f"{BLEED_IN:g}", "BLEED2": f"{BLEED_IN*2:g}",
        "OIMG_W": f"{w + 2 * BLEED_IN:g}", "OIMG_H": f"{h + 2 * BLEED_IN:g}",
        "MARKS": "marks: crop;" if theme.crop_marks else "",
        "FOLIO": folio, "RUNHEAD": runhead,
        "MT": "0.7", "MB": "0.62", "MO": "0.6", "MI": f"{gut:g}",
        "BASEPT": f"{theme.base_font_pt:g}", "LEAD": f"{theme.leading:g}",
    }
    css = _TEMPLATE
    for k, v in repl.items():
        css = css.replace(f"%%{k}%%", str(v))
    return css
