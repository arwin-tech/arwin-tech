"""The look every generated graphic shares: palette, typeface, SVG plumbing.

Standard library only, because generate_stats.py imports it inside the nightly
action. Change a colour here and every graphic follows on the next run (the
portrait needs make_portrait.py run again).

GitHub strips <style> from the README itself, but not from inside an image, so
each SVG carries its own small stylesheet: colours for light mode, an override
for dark mode, and the font inlined as a data URI.
"""
import base64
import functools
import os
from html import escape

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

# JBM is the subset inlined into each SVG. The rest only matters if a renderer
# ignores the embedded face; all of them are ligature-free.
FAMILY = "JBM,ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"

WIDTH = 620   # every graphic shares one column, and hangs from the same left edge

# token: (light mode, dark mode). Transparent backgrounds throughout, so these
# sit on GitHub's own canvas: #ffffff in light, #0d1117 in dark.
PALETTE = {
    "ink":    ("#424a53", "#c9d1d9"),   # the portrait, and every data mark
    "strong": ("#1f2328", "#f0f6fc"),   # big numbers and headings
    "muted":  ("#59636e", "#9198a1"),   # small labels; 6:1 on both canvases
    "faint":  ("#d1d9e0", "#3d444d"),   # hairlines and days with nothing in them
    "accent": ("#008bfb", "#008bfb"),   # SHAP's blue, and only for "now"
}

# The ramp, quiet to loud. The portrait uses all 13 steps; the year map and the
# streak strips use five of them, so the stats read as the same material.
RAMP = " .`:-=+*cs#%@"
LEVELS = [".", ":", "+", "#", "@"]


@functools.lru_cache(maxsize=None)
def font_face(filename, weight):
    """An @font-face rule with a subset inlined as base64.

    A URL to a hosted font cannot work: these SVGs load through <img>, and an
    image document is not allowed to fetch anything. Inlining also pins the
    advance width at 0.600 em, which the portrait's grid depends on.
    """
    with open(os.path.join(FONT_DIR, filename), "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return (f"@font-face{{font-family:JBM;font-weight:{weight};font-display:block;"
            f"src:url(data:font/woff2;base64,{data}) format('woff2')}}")


def stylesheet(fonts, extra=""):
    """Fill and stroke classes for each palette token, light then dark."""
    def rules(i):
        out = []
        for name, pair in PALETTE.items():
            out.append(f".f-{name}{{fill:{pair[i]}}}")
            out.append(f".s-{name}{{stroke:{pair[i]}}}")
        return "".join(out)

    return ("<style>" + "".join(font_face(f, w) for f, w in fonts)
            + f"text{{font-family:{FAMILY};font-variant-ligatures:none;white-space:pre}}"
            + rules(0)
            + "@media (prefers-color-scheme:dark){" + rules(1) + "}"
            + extra + "</style>")


def open_svg(width, height, title, fonts, extra_css=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">'
            f"<title>{escape(title)}</title>" + stylesheet(fonts, extra_css))


def text(x, y, content, size, cls, weight=400, anchor="start"):
    """One run of text, pinned to exactly 0.600 em per character.

    textLength matters more than it looks. Browsers without subpixel text
    positioning round every advance to a whole pixel (7.74 becomes 8 at
    12.9 px), which makes a 90-character row about 3% too wide; a viewer whose
    browser falls back to Consolas would see it 7% too narrow. Pinning the
    length keeps the portrait's grid, and every right edge, where it was drawn.
    """
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    w = f' font-weight="{weight}"' if weight != 400 else ""
    return (f'<text x="{x:g}" y="{y:g}" font-size="{size:g}"{w}{a} class="{cls}" '
            f'textLength="{advance(len(content), size):.2f}" lengthAdjust="spacing" '
            f'xml:space="preserve">{escape(content, quote=False)}</text>')


def advance(chars, size):
    """Width of a run of monospace characters: 0.600 em each."""
    return chars * size * 0.6


def write(path, svg):
    """Write only when the bytes differ, so an unchanged night commits nothing."""
    try:
        with open(path, encoding="utf-8") as f:
            if f.read() == svg:
                return False
    except FileNotFoundError:
        pass
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg)
    return True
