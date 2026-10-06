#!/usr/bin/env python3
"""Turn a photo into portrait.svg: an ASCII portrait that types itself, once.

Run it on your own machine whenever you want a new portrait. It is not part of
the nightly action.

    pip install pillow numpy opencv-python-headless rembg onnxruntime
    python scripts/make_portrait.py me.jpg --preview
    python scripts/make_portrait.py me.jpg --crop 420,160,1180,1010

The first photo run downloads a ~170 MB background-removal model, once. The
model is named explicitly below: recent rembg versions default to a 1 GB model
that can run a laptop out of memory.

No photo yet? Print a word in the same ramp instead (no rembg needed):

    python scripts/make_portrait.py --text arwin

The photo decides almost everything. ASCII draws with shadow rather than
detail, and the ramp has 13 steps. Use side light (one window at about 45
degrees, other lights off), crop from the chin to just above the hair, and
start from a big image: thin features like glasses frames vanish when a small
headshot is shrunk to 90 columns. Flat frontal light renders the face as a hole.

Two grids are drawn from one photo. In light mode the ink is dark, so dense
characters stand for shadow. In dark mode the ink is light, so the same
mapping would print a negative, with hair glowing and skin empty. The dark
grid flips it so density follows brightness, and the SVG shows whichever
grid matches the viewer's theme.
"""
import argparse
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

import profile_style as ps

COLS = 90             # below ~88 the face muddies; far above it, the block dominates
CLAHE_CLIP = 3.0      # local contrast per tile; higher turns skin texture into noise
CURVE = 1.7           # the darkening curve, light grid: keeps brows, lips, glasses
DARK_CURVE = 1.2      # the dark grid's curve: keeps skin from flattening into @@@@
MODEL = "u2net_human_seg"   # ~170 MB, trained on people

FONT_SIZE = 12.9
CHAR_W = FONT_SIZE * 0.6    # 7.74: exactly 0.600 em, the inlined font's advance
LINE_H = FONT_SIZE * 1.2    # 15.48
ROW_RATIO = CHAR_W / LINE_H  # 0.5: a cell is twice as tall as it is wide
ROW_DELAY = 0.09            # seconds per row; a 56-row portrait prints in ~5 s

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------------ photo

def load(path, crop):
    img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    if crop:
        img = img.crop(crop)
    if max(img.size) < 900:
        print(f"warning: {img.size[0]}x{img.size[1]} is small; fine features "
              "will be averaged away. Aim for 1200 px or more.", file=sys.stderr)
    return img


def cut_out(img, model):
    """Remove the background and crop to the person.

    Everything outside the subject is composited to white, which lands on the
    blank end of the ramp. Skip this and the background fills with @ and %.
    """
    try:
        from rembg import new_session, remove
    except ImportError:
        sys.exit("rembg is needed for photos:  pip install rembg onnxruntime\n"
                 "(or try --text to print a word instead)")
    rgba = remove(img, session=new_session(model))
    alpha = np.asarray(rgba.getchannel("A"))

    ys, xs = np.nonzero(alpha > 20)
    if len(xs) == 0:
        sys.exit("couldn't find a person in that photo")
    pad = int(0.02 * max(alpha.shape))
    box = (max(xs.min() - pad, 0), max(ys.min() - pad, 0),
           min(xs.max() + pad, alpha.shape[1]), min(ys.max() + pad, alpha.shape[0]))
    rgba = rgba.crop(box)

    white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    gray = np.asarray(Image.alpha_composite(white, rgba).convert("L"))
    return gray, np.asarray(rgba.getchannel("A"))


def tone(gray):
    gray = cv2.bilateralFilter(gray, 11, 50, 50)    # smooth skin, keep edges
    return cv2.createCLAHE(clipLimit=CLAHE_CLIP, tileGridSize=(8, 8)).apply(gray)


def grids_from_photo(gray, alpha, cols):
    rows = max(1, round(cols * gray.shape[0] / gray.shape[1] * ROW_RATIO))
    lum = cv2.resize(tone(gray), (cols, rows), interpolation=cv2.INTER_AREA) / 255.0
    cov = cv2.resize(alpha, (cols, rows), interpolation=cv2.INTER_AREA) / 255.0
    n = len(ps.RAMP)

    # light mode: ink follows darkness, after the darkening curve
    dark_amt = 1.0 - lum ** CURVE
    dark_amt[cov < 0.08] = 0.0
    light = (dark_amt * n).astype(int).clip(0, n - 1)

    # dark mode: ink follows brightness. The small floor keeps dark hair from
    # vanishing into a dark page: it prints as sparse dots, which reads as dark.
    bright = cov * (0.09 + 0.91 * lum ** DARK_CURVE)
    dark = (bright * n).astype(int).clip(0, n - 1)
    return light, dark


# ------------------------------------------------------------------- text

def grid_from_text(word, cols, font_path):
    """Rasterise a word big, give it a soft light from the upper left, then
    treat it like a photo. Used as a placeholder until there's a portrait."""
    font = None
    for cand in [font_path, "C:/Windows/Fonts/consolab.ttf", "C:/Windows/Fonts/arialbd.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
                 "/System/Library/Fonts/Menlo.ttc"]:
        if cand and os.path.exists(cand):
            font = ImageFont.truetype(cand, 400)
            break
    if font is None:
        sys.exit("no bold font found; pass one with --font path/to/font.ttf")

    l, t, r, b = font.getbbox(word)
    img = Image.new("L", (r - l + 80, b - t + 80), 0)
    ImageDraw.Draw(img).text((40 - l, 40 - t), word, font=font, fill=255)
    mask = np.asarray(img).astype(np.float32) / 255.0

    # a little shading inside the strokes (denser at the core, a soft light
    # from the upper left) so the ramp does more than print a wall of @
    dist = cv2.distanceTransform((mask > 0.5).astype(np.uint8), cv2.DIST_L2, 5)
    dist = np.clip(dist / max(dist.max(), 1.0), 0, 1)
    h, w = mask.shape
    yy, xx = np.mgrid[0:h, 0:w]
    light = 1.0 - 0.18 * ((xx / w) + (yy / h)) / 2
    amount = mask * (0.8 + 0.2 * dist ** 0.5) * light

    rows = max(1, round(cols * h / w * ROW_RATIO))
    small = cv2.resize(amount, (cols, rows), interpolation=cv2.INTER_AREA)
    inked = small[small > 0.05]
    if inked.size:
        small = np.clip(small / np.percentile(inked, 90), 0, 1)
    n = len(ps.RAMP)
    g = (small * (n - 0.01)).astype(int).clip(0, n - 1)
    return g, g


# ------------------------------------------------------------------- grid

def to_lines(light, dark):
    """Characters per row, with blank rows and the shared blank margin removed
    so the portrait hangs from the same left edge as everything below it."""
    lines = []
    for lrow, drow in zip(light, dark):
        lines.append(("".join(ps.RAMP[i] for i in lrow), "".join(ps.RAMP[i] for i in drow)))
    while lines and not (lines[0][0].strip() or lines[0][1].strip()):
        lines.pop(0)
    while lines and not (lines[-1][0].strip() or lines[-1][1].strip()):
        lines.pop()
    if not lines:
        sys.exit("nothing to draw: the grid came out empty")

    def lead(s):
        return len(s) - len(s.lstrip(" ")) if s.strip() else 10**6

    cut = min(min(lead(a), lead(b)) for a, b in lines)
    return [(a[cut:].rstrip(), b[cut:].rstrip()) for a, b in lines]


# -------------------------------------------------------------------- svg

def build_svg(lines, alt):
    themed = any(a != b for a, b in lines)
    cols = max(max(len(a), len(b)) for a, b in lines)
    width = round(cols * CHAR_W + 2)
    height = round(len(lines) * LINE_H + 4)

    # Motion is SMIL, since GitHub strips scripts. Each row is uncovered by a
    # clip-path wipe with a cursor riding its edge, top to bottom, and every
    # animation freezes at the end so the portrait prints once and stays.
    # Visitors who ask for reduced motion get the finished portrait at once.
    css = (".cursor{opacity:0}"
           "@media (prefers-reduced-motion:reduce){.row{clip-path:none}.cursor{display:none}}")
    if themed:
        css += ".dk{display:none}@media (prefers-color-scheme:dark){.lt{display:none}.dk{display:inline}}"

    out = [ps.open_svg(width, height, alt, [("jbm-ramp.woff2", 400)], css)]
    for i, (lt, dk) in enumerate(lines):
        y = i * LINE_H
        base = y + FONT_SIZE * 0.88
        w = max(len(lt), len(dk), 1) * CHAR_W
        t0, t1 = i * ROW_DELAY, (i + 1) * ROW_DELAY
        out.append(
            f'<clipPath id="r{i}"><rect x="0" y="{y:.2f}" width="0" height="{LINE_H:.2f}">'
            f'<animate attributeName="width" from="0" to="{w:.2f}" begin="{t0:.2f}s" '
            f'dur="{ROW_DELAY}s" fill="freeze"/></rect></clipPath>')
        out.append(f'<g class="row" clip-path="url(#r{i})">')
        if themed:
            out.append(ps.text(0, round(base, 2), lt, FONT_SIZE, "f-ink lt"))
            out.append(ps.text(0, round(base, 2), dk, FONT_SIZE, "f-ink dk"))
        else:
            out.append(ps.text(0, round(base, 2), lt, FONT_SIZE, "f-ink"))
        out.append("</g>")
        out.append(
            f'<rect class="cursor f-ink" x="0" y="{y + 1.5:.2f}" width="{CHAR_W * 0.8:.2f}" '
            f'height="{LINE_H - 3:.2f}">'
            f'<animate attributeName="x" from="0" to="{w:.2f}" begin="{t0:.2f}s" '
            f'dur="{ROW_DELAY}s" fill="freeze"/>'
            f'<set attributeName="opacity" to="0.85" begin="{t0:.2f}s"/>'
            f'<set attributeName="opacity" to="0" begin="{t1:.2f}s"/></rect>')
    out.append("</svg>")
    return "".join(out)


# ------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Draw portrait.svg from a photo or a word.")
    ap.add_argument("photo", nargs="?", help="path to your photo")
    ap.add_argument("--text", help="print this word instead of a photo")
    ap.add_argument("--out", default=os.path.join(ROOT, "portrait.svg"))
    ap.add_argument("--crop", help="left,top,right,bottom in pixels, applied first. "
                                   "Crop tight so the whole grid goes to the face")
    ap.add_argument("--cols", type=int, default=COLS)
    ap.add_argument("--font", help="bold .ttf for --text")
    ap.add_argument("--model", default=MODEL,
                    help=f"rembg model (default {MODEL}; u2net or isnet-general-use also work)")
    ap.add_argument("--alt", default="arwin-tech, drawn in ASCII")
    ap.add_argument("--preview", action="store_true",
                    help="print both grids in the terminal too")
    args = ap.parse_args()

    if bool(args.photo) == bool(args.text):
        ap.error("give a photo, or --text WORD")

    if args.text:
        light, dark = grid_from_text(args.text, args.cols, args.font)
    else:
        crop = None
        if args.crop:
            try:
                crop = tuple(int(v) for v in args.crop.split(","))
                assert len(crop) == 4
            except (ValueError, AssertionError):
                ap.error("--crop needs four whole numbers: left,top,right,bottom")
        gray, alpha = cut_out(load(args.photo, crop), args.model)
        light, dark = grids_from_photo(gray, alpha, args.cols)

    lines = to_lines(light, dark)
    if args.preview:
        print("light mode\n" + "\n".join(a for a, _ in lines))
        if any(a != b for a, b in lines):
            print("\ndark mode\n" + "\n".join(b for _, b in lines))

    svg = build_svg(lines, args.alt)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg)
    secs = len(lines) * ROW_DELAY
    print(f"wrote {os.path.relpath(args.out)}: {len(lines)} rows x {args.cols} columns, "
          f"{len(svg) // 1024} KB, prints in {secs:.1f} s")


if __name__ == "__main__":
    main()
