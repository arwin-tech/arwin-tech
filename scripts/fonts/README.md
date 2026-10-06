# Embedded typeface

[JetBrains Mono](https://github.com/JetBrains/JetBrainsMono) 2.305, subset and
inlined into each SVG as a base64 `@font-face`. Rebuild with
`scripts/build_fonts.py` only if a graphic needs a character these don't cover.

| file | weight | covers | used by |
|---|---|---|---|
| `jbm-ramp.woff2` | 400 | the 13 ramp characters | `portrait.svg` |
| `jbm-400.woff2` | 400 | ASCII and a few typographic marks | stat graphics |
| `jbm-600.woff2` | 600 | the same | stat graphics |
| `jbm-head.woff2` | 600 | a-z, space, hyphen | section headings |

Why inline: these SVGs load through `<img>`, and an image document isn't
allowed to fetch anything, so a font URL would silently fail. Layout features
are stripped so pairs like `==` and `::` in the portrait never turn into
ligatures.

SIL Open Font License 1.1, see `OFL.txt`. Subsetting and redistribution are
permitted; the font name is unchanged.
