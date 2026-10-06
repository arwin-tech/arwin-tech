#!/usr/bin/env python3
"""Draw the profile's stat graphics and section headings from the GitHub API.

Standard library only, so nothing can break in CI. The nightly action in
.github/workflows/refresh-stats.yml runs this; you don't need to.

Writes to the repository root:
  stats.svg    contributions in the last year, with a weekly sparkline
  streak.svg   current and longest streak, each drawn as its run of days
  langs.svg    languages by share of bytes, and how many repos each one leads
  year.svg     the year, one character per day, in the portrait's ramp
  hd-*.svg     section headings, in the page's own typeface

Env:
  GITHUB_TOKEN  required (the workflow's built-in token is enough)
  GH_LOGIN      whose profile to draw (default: arwin-tech)

Working on the design? Fetch once, then redraw offline as often as you like:
  python scripts/generate_stats.py --dump data.json
  python scripts/generate_stats.py --data data.json
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

import profile_style as ps
from profile_style import WIDTH, advance, text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGIN = os.environ.get("GH_LOGIN", "arwin-tech")

# file slug: label. Rename freely; the heading font covers a-z, space and "-".
HEADINGS = {
    "about": "about",
    "projects": "projects",
    "stack": "stack",
    "activity": "activity",
    "this-page": "how this page works",
}

IGNORE_LANGUAGES = set()   # e.g. {"Jupyter Notebook"} if notebooks swamp the bytes
MON = "jan feb mar apr may jun jul aug sep oct nov dec".split()

# Two things are pinned so an unchanged night produces identical bytes:
#  * the window, to whole UTC days. Left alone, "the past year" is measured
#    from the moment of the request, days drift between week buckets, and the
#    sparkline moves a fraction of a pixel every run.
#  * privacy: PUBLIC. A personal token sees private repos and the workflow's
#    token doesn't, so language totals would depend on who ran the script.
QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      nodes {
        name
        primaryLanguage { name }
        languages(first: 20, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""


# ------------------------------------------------------------------- data

def fetch(login, token):
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=364)
    body = json.dumps({"query": QUERY, "variables": {
        "login": login,
        "from": f"{start.isoformat()}T00:00:00Z",
        "to": f"{today.isoformat()}T23:59:59Z"}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, headers={
        "Authorization": f"bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": f"{login}-profile-readme"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"GitHub API answered {e.code}: {e.read().decode(errors='replace')[:300]}")
    if payload.get("errors"):
        sys.exit(f"GraphQL errors: {payload['errors']}")
    user = (payload.get("data") or {}).get("user")
    if not user:
        sys.exit(f"no such user: {login}")
    return user


def summarise(user):
    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks = [w["contributionDays"] for w in cal["weeks"] if w["contributionDays"]]
    days = [(date.fromisoformat(d["date"]), d["contributionCount"]) for w in weeks for d in w]
    days.sort()

    by_bytes, leads = {}, {}
    for repo in user["repositories"]["nodes"]:
        for e in (repo.get("languages") or {}).get("edges") or []:
            name = e["node"]["name"]
            if name not in IGNORE_LANGUAGES:
                by_bytes[name] = by_bytes.get(name, 0) + e["size"]
        primary = (repo.get("primaryLanguage") or {}).get("name")
        if primary and primary not in IGNORE_LANGUAGES:
            leads[primary] = leads.get(primary, 0) + 1

    return {
        "days": days,
        "today": days[-1][0],
        "total": cal["totalContributions"],
        "weeks": [(date.fromisoformat(w[0]["date"]), sum(d["contributionCount"] for d in w))
                  for w in weeks],
        "by_bytes": by_bytes,
        "leads": leads,
    }


def level_of(days):
    """Five steps, split at the quartiles of the days that had anything."""
    nz = sorted(n for _, n in days if n > 0)
    if not nz:
        return lambda n: 0
    q = [nz[(len(nz) - 1) * k // 4] for k in (1, 2, 3)]
    return lambda n: 0 if n <= 0 else 1 if n <= q[0] else 2 if n <= q[1] else 3 if n <= q[2] else 4


def streaks(days, today):
    """Current and longest runs of days with at least one contribution.

    A zero today doesn't end the current streak: the day isn't over. Both are
    measured inside the one-year window, so a run older than that is cut short.
    """
    counts = dict(days)
    d = today if counts.get(today, 0) > 0 else today - timedelta(days=1)
    current = []
    while counts.get(d, 0) > 0:
        current.insert(0, (d, counts[d]))
        d -= timedelta(days=1)

    longest, run = [], []
    for d, n in days:
        run = run + [(d, n)] if n > 0 else []
        if run and len(run) >= len(longest):   # ties go to the more recent run
            longest = run
    last = max((d for d, n in days if n > 0), default=None)
    return current, longest, last


def pretty(d):
    return f"{MON[d.month - 1]} {d.day}"


def span(run):
    if not run:
        return ""
    a, b = run[0][0], run[-1][0]
    if a == b:
        return pretty(a)
    return f"{pretty(a)} \u2013 {pretty(b)}"


def plural(n, word):
    return f"{n:,} {word}" + ("" if n == 1 else "s")


# ------------------------------------------------------------------ draw

def draw_stats(s):
    """The total as the start of a sentence, then the year's shape, by week."""
    h = 156
    out = [ps.open_svg(WIDTH, h, f"{s['total']:,} contributions in the last year",
                       [("jbm-600.woff2", 600), ("jbm-400.woff2", 400)])]
    num = f"{s['total']:,}"
    out.append(text(0, 48, num, 48, "f-strong", 600))
    word = "contribution" if s["total"] == 1 else "contributions"
    out.append(text(advance(len(num), 48) + 12, 48, f"{word} in the last year", 15, "f-muted"))

    # Lines are fine here: weekly totals are an aggregate, so drawing through
    # them doesn't invent in-between values the way a daily line chart would.
    vals = [n for _, n in s["weeks"]]
    top, bottom, x0, x1 = 84, 128, 1.0, WIDTH - 4.0
    peak = max(vals) if vals else 0
    step = (x1 - x0) / max(len(vals) - 1, 1)
    pts = [(x0 + i * step, bottom - (v / peak * (bottom - top) if peak else 0))
           for i, v in enumerate(vals)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)

    out.append(f'<path d="M{x0:.1f},{bottom} L{line.replace(" ", " L")} L{x1:.1f},{bottom} Z" '
               f'class="f-ink" opacity="0.12"/>')
    out.append(f'<line x1="{x0:.1f}" y1="{bottom + 0.5}" x2="{x1:.1f}" y2="{bottom + 0.5}" '
               f'class="s-faint" stroke-width="1"/>')
    out.append(f'<polyline points="{line}" fill="none" class="s-ink" stroke-width="1.5" '
               f'stroke-linejoin="round" stroke-linecap="round"/>')
    lx, ly = pts[-1]
    out.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3.5" class="f-accent"/>')

    if peak and vals.index(peak) != len(vals) - 1:
        i = vals.index(peak)
        label = f"{peak:,} in the week of {pretty(s['weeks'][i][0])}"
        half = advance(len(label), 11) / 2
        px = min(max(pts[i][0], half), WIDTH - half)
        out.append(text(round(px, 1), top - 9, label, 11, "f-muted", anchor="middle"))

    start = s["weeks"][0][0]
    out.append(text(0, h - 8, f"{MON[start.month - 1]} {start.year}", 11, "f-muted"))
    out.append(text(WIDTH, h - 8, f"{vals[-1]:,} this week", 11, "f-muted", anchor="end"))
    out.append("</svg>")
    return "".join(out)


def draw_streak(s):
    """Each streak is drawn as its own days, one ramp character each."""
    current, longest, last = streaks(s["days"], s["today"])
    level = level_of(s["days"])
    h = 76
    title = (f"Current streak {plural(len(current), 'day')}, "
             f"longest {plural(len(longest), 'day')}")
    out = [ps.open_svg(WIDTH, h, title, [("jbm-600.woff2", 600), ("jbm-400.woff2", 400)])]

    cols = [(0, "current streak", current, "f-accent"),
            (320, "longest streak", longest, "f-ink")]
    for x, label, run, ink in cols:
        value = plural(len(run), "day")
        out.append(text(x, 14, label, 12, "f-muted"))
        out.append(text(x, 44, value, 26, "f-strong", 600))
        if len(run) > 1:
            sx = x + advance(len(value), 26) + 12
            room = int((x + 300 - sx) / advance(1, 14))
            strip = "".join(ps.LEVELS[level(n)] for _, n in run)
            if len(strip) > room:
                strip = "\u2026" + strip[-(room - 1):] if room >= 2 else ""
            out.append(text(round(sx, 1), 44, strip, 14, ink))
        if run:
            note = span(run)
        elif last:
            note = f"last active {pretty(last)}"
        else:
            note = "nothing yet"
        out.append(text(x, 66, note, 12, "f-muted"))
    out.append("</svg>")
    return "".join(out)


def draw_langs(s):
    """Share of public bytes per language, and how many repos it's the main
    language of. One table instead of two charts, so each language sits on
    one line with both of its numbers."""
    total = sum(s["by_bytes"].values())
    ranked = sorted(s["by_bytes"].items(), key=lambda kv: (-kv[1], kv[0]))
    rows = ranked[:5]
    for name in sorted(s["leads"], key=lambda n: (-s["leads"][n], n)):
        if name not in dict(rows) and name in s["by_bytes"]:
            rows.append((name, s["by_bytes"][name]))
    rows = sorted(rows, key=lambda kv: (-kv[1], kv[0]))[:7]

    row_h, size, bar = 22, 13, 30
    h = max(len(rows), 1) * row_h + 2
    title = "Languages by share of public code: " + ", ".join(
        f"{n} {b / total:.0%}" for n, b in rows) if rows else "No public code yet"
    out = [ps.open_svg(WIDTH, h, title, [("jbm-400.woff2", 400)])]
    if not rows:
        out.append(text(0, 15, "no public code yet", size, "f-muted"))

    bar_x = advance(19, size)
    pct_x = bar_x + advance(bar + 8, size)
    for i, (name, b) in enumerate(rows):
        y = 15 + i * row_h
        share = b / total
        filled = min(bar, int(share * bar + 0.5))
        label = name.lower()
        if len(label) > 18:
            label = label[:17] + "\u2026"
        out.append(text(0, y, label, size, "f-ink"))
        out.append(f'<text x="{bar_x:g}" y="{y}" font-size="{size}" '
                   f'textLength="{advance(bar, size):.2f}" lengthAdjust="spacing" xml:space="preserve">'
                   f'<tspan class="f-ink">{"#" * filled}</tspan>'
                   f'<tspan class="f-faint">{"." * (bar - filled)}</tspan></text>')
        pct = "<0.1%" if share < 0.001 else f"{share:.1%}"
        out.append(text(round(pct_x, 1), y, pct, size, "f-ink", anchor="end"))
        n = s["leads"].get(name, 0)
        if n:
            out.append(text(round(pct_x + advance(2, size), 1), y,
                            plural(n, "repo"), size, "f-muted"))
    out.append("</svg>")
    return "".join(out)


def draw_year(s):
    """One character per day, in the portrait's ramp. Empty days print as a
    faint dot, so the calendar keeps its shape even in a quiet year."""
    level = level_of(s["days"])
    size, sx, sy = 12, 10.8, 13
    gx, gy = 32, 30
    first = s["days"][0][0]
    lead = (first.weekday() + 1) % 7            # Sunday = row 0, as on GitHub
    ncols = (lead + len(s["days"]) + 6) // 7
    h = gy + 6 * sy + 30
    active = sum(1 for _, n in s["days"] if n > 0)

    out = [ps.open_svg(WIDTH, h, f"The last year, one character per day: "
                       f"{plural(active, 'active day')}", [("jbm-400.woff2", 400)])]

    for r, name in ((1, "mon"), (3, "wed"), (5, "fri")):
        out.append(text(0, gy + r * sy, name, 10.5, "f-muted"))

    last_label = -10
    cells = {0: [], 1: [], 2: [], 3: [], 4: []}
    for i, (d, n) in enumerate(s["days"]):
        k = lead + i
        c, r = divmod(k, 7)
        x, y = gx + c * sx, gy + r * sy
        if d.day == 1 or i == 0:
            if c - last_label >= 3 and c <= ncols - 2:
                out.append(text(round(x, 1), 10, MON[d.month - 1], 10.5, "f-muted"))
                last_label = c
        if d == s["today"]:
            continue
        cells[level(n)].append((x, y))
    # one <text> per level, characters placed by x/y lists, keeps the file small
    for lv, pts in cells.items():
        if not pts:
            continue
        cls = "f-faint" if lv == 0 else "f-ink"
        for row_y in sorted({y for _, y in pts}):
            xs = [x for x, y in pts if y == row_y]
            out.append(f'<text x="{" ".join(f"{x:.1f}" for x in xs)}" y="{row_y}" '
                       f'font-size="{size}" class="{cls}">{ps.LEVELS[lv] * len(xs)}</text>')
    tk = lead + len(s["days"]) - 1
    tc, tr = divmod(tk, 7)
    today_n = s["days"][-1][1]
    out.append(text(round(gx + tc * sx, 1), gy + tr * sy, ps.LEVELS[level(today_n)],
                    size, "f-accent"))

    right = gx + (ncols - 1) * sx + advance(1, size)
    ly = gy + 6 * sy + 24
    out.append(text(gx, ly, f"{plural(active, 'active day')}, today in blue", 10.5, "f-muted"))
    legend_w = advance(10, 10.5) + advance(9, size)
    out.append(f'<text x="{right:.1f}" y="{ly}" text-anchor="end" '
               f'textLength="{legend_w:.2f}" lengthAdjust="spacing" xml:space="preserve">'
               f'<tspan font-size="10.5" class="f-muted">less </tspan>'
               f'<tspan font-size="{size}" class="f-faint">.</tspan>'
               f'<tspan font-size="{size}" class="f-ink"> : + # @</tspan>'
               f'<tspan font-size="10.5" class="f-muted"> more</tspan></text>')
    out.append("</svg>")
    return "".join(out)


def draw_heading(label):
    """A lowercase label with a hairline running to the column's edge. An image
    because GitHub strips CSS: this is the only way to set a heading in the
    page's own typeface. The alt text in the README carries the word."""
    size = 15
    out = [ps.open_svg(WIDTH, 30, label, [("jbm-head.woff2", 600)])]
    out.append(text(0, 20, label, size, "f-strong", 600))
    out.append(f'<line x1="{advance(len(label), size) + 12:.1f}" y1="15.5" x2="{WIDTH}" '
               f'y2="15.5" class="s-faint" stroke-width="1"/>')
    out.append("</svg>")
    return "".join(out)


# ------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Draw the profile's stat graphics.")
    ap.add_argument("--data", help="draw from a saved API response instead of fetching")
    ap.add_argument("--dump", help="save the API response to this file")
    ap.add_argument("--out", default=ROOT, help="where to write (default: repo root)")
    args = ap.parse_args()

    if args.data:
        with open(args.data, encoding="utf-8") as f:
            user = json.load(f)
        user = (user.get("data") or {}).get("user", user)
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            sys.exit("set GITHUB_TOKEN (any token works; on Windows: "
                     "$env:GITHUB_TOKEN = (gh auth token))")
        user = fetch(LOGIN, token)
        if args.dump:
            with open(args.dump, "w", encoding="utf-8") as f:
                json.dump(user, f, indent=1)

    s = summarise(user)
    files = {
        "stats.svg": draw_stats(s),
        "streak.svg": draw_streak(s),
        "langs.svg": draw_langs(s),
        "year.svg": draw_year(s),
    }
    files.update({f"hd-{slug}.svg": draw_heading(label) for slug, label in HEADINGS.items()})
    for name, svg in files.items():
        changed = ps.write(os.path.join(args.out, name), svg)
        print(f"{'wrote ' if changed else 'same  '} {name:20} {len(svg) / 1024:5.1f} KB")


if __name__ == "__main__":
    main()
