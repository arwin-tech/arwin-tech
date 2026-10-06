#!/usr/bin/env python3
"""Rebuild the JetBrains Mono subsets in scripts/fonts/. You rarely need this.

The subsets are already committed. Run this only if a graphic starts drawing a
character the subsets don't cover (a non-ASCII language name, say).

    pip install fonttools brotli
    # download the TTFs from https://github.com/JetBrains/JetBrainsMono/releases
    python scripts/build_fonts.py path/to/JetBrainsMono/fonts/ttf

Every graphic is loaded through <img>, and browsers refuse to fetch anything
from inside an image document, so the font has to travel inside each SVG as a
base64 data URI. Subsetting is what keeps that affordable: about 1-5 KB per
graphic instead of 270 KB.
"""
import os
import sys

from fontTools import subset

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

RAMP = " .`:-=+*cs#%@"                       # the portrait's character ramp
ASCII = "".join(chr(c) for c in range(0x20, 0x7F))
EXTRA = "\u2013\u2014\u2019\u201c\u201d\u2026\u00d7"   # – — ’ “ ” … ×
HEADINGS = "abcdefghijklmnopqrstuvwxyz -"

JOBS = [
    # (output file, source weight, characters)
    ("jbm-ramp.woff2", "Regular", RAMP),
    ("jbm-400.woff2", "Regular", ASCII + EXTRA),
    ("jbm-600.woff2", "SemiBold", ASCII + EXTRA),
    ("jbm-head.woff2", "SemiBold", HEADINGS),
]


def build(src, dst, text):
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = []   # no GSUB: JetBrains Mono ligates "==", "::", "--"
    opts.hinting = False        # and the ramp is full of exactly those pairs
    opts.name_IDs = [0, 1, 2, 3, 4, 5, 6]
    font = subset.load_font(src, opts)
    sub = subset.Subsetter(opts)
    sub.populate(text=text)
    sub.subset(font)
    subset.save_font(font, dst, opts)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    ttf_dir = sys.argv[1]
    os.makedirs(OUT, exist_ok=True)
    for name, weight, text in JOBS:
        src = os.path.join(ttf_dir, f"JetBrainsMono-{weight}.ttf")
        dst = os.path.join(OUT, name)
        build(src, dst, text)
        print(f"{name:16} {os.path.getsize(dst):>6,} bytes  ({len(set(text))} chars)")


if __name__ == "__main__":
    main()
