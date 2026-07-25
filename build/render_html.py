#!/usr/bin/env python3
"""Stage 6: render the ledger as a self-contained interactive HTML timeline.

`timeline.csv` plus the case series in, `timeline.html` out. No CDN, no fonts,
no fetches, nothing external at run time: the archive made its visualisation
stand alone deliberately and a companion page that depends on a live host would
undo that.

Three decisions from TIMELINE-PLAN.md section 3a are implemented here rather
than re-argued:

  * **Tracks are lanes, not hues.** Four horizontal lanes on a shared time axis.
    Position separates them completely, so the scarce categorical slots are not
    spent on information the layout carries for free. Event marks take a neutral
    ink and `category` rides in the label and the tooltip.
  * **The categorical slots belong to the case series.** Four UCL series as
    lines, which is an adjacent-pairlist form, with the fixed slot order
    validated in both modes by scripts/validate_palette.js.
  * **No dual axis, ever.** Events have their own baseline in their own lanes.

**Where this departs from the plan, and why.** The plan expected Camden to sit
on the same y-axis as the UCL series, both being confirmed cases per week, and
named indexing to a common base as the fallback if the raw counts would not
co-plot. They will not: Camden peaks at 5,922 cases in a week against 525 for
UCL on-campus students, so a shared scale compresses every UCL line into the
bottom ninth of the plot. Indexing would fix the geometry at the cost of
changing the quantity on display from cases to relative change, and the UCL
series starts from single figures where an index is mostly noise. Camden
therefore gets its own panel underneath, sharing the x-axis and the crosshair,
with its own labelled axis in the same unit. That is two plots, not two scales
on one plot, which is the honest alternative the anti-pattern catalogue names.

The page is generated whole, so it renders without JavaScript. Script adds the
crosshair, the tooltips and the filters; it is not needed to see the chart.

Standard library only. Usage:
    python3 render_html.py [--config timeline.toml] [--set KEY=VALUE]
"""
import csv
import html
import json
import sys
from datetime import date, timedelta

import config
from validate import load_rows

# ---------------------------------------------------------------- palette
#
# Validated, not chosen by eye. Both modes are selected: the light hexes fail
# the dark lightness band outright, so dark is its own set of steps from the
# same ramps rather than an automatic flip. Runs recorded in PROGRESS.md.
#
#   node scripts/validate_palette.js "#2a78d6,#eb6834,#1baf7a,#eda100" --mode light
#   node scripts/validate_palette.js "#3987e5,#d95926,#199e70,#c98500" --mode dark
#
# Colour follows the entity and never its rank, so these bindings are fixed:
# toggling staff off does not repaint students.
SERIES = [
    {'key': 'student7.on',  'label': 'Students, on campus',  'slot': 1,
     'light': '#2a78d6', 'dark': '#3987e5', 'on': True},
    {'key': 'student7.off', 'label': 'Students, off campus', 'slot': 2,
     'light': '#eb6834', 'dark': '#d95926', 'on': True},
    {'key': 'staff7.on',    'label': 'Staff, on campus',     'slot': 3,
     'light': '#1baf7a', 'dark': '#199e70', 'on': False},
    {'key': 'staff7.off',   'label': 'Staff, off campus',    'slot': 4,
     'light': '#eda100', 'dark': '#c98500', 'on': False},
]

TRACKS = [
    ('national', 'National'),
    ('sector', 'Sector'),
    ('ucl', 'UCL'),
    ('data', 'Case data'),
]

MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
          'August', 'September', 'October', 'November', 'December']
SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct',
         'Nov', 'Dec']

# Geometry. Chart internals are system sans throughout; the page prose keeps
# the archive's serif.
W = 1180
PAD_L, PAD_R, PAD_T, PAD_B = 116, 26, 26, 34
LANE_H = 34
GAP = 18
UCL_H = 250
CAM_H = 96
TICK_W = 2.5          # event rug: thin marks, per the mark specs
TICK_H = 15           # tall enough to read, short of the lane rule
LANE_HIT = 26         # the band a pointer must be inside to snap to a lane


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fmt_date(d):
    return f'{d.day} {MONTHS[d.month - 1]} {d.year}'


# ------------------------------------------------------------------- data

def load_cases(cfg):
    """The UCL series as published: the seven-day columns, not a re-derivation.
    Using UCL's own weekly figures is what stops the chart and the ledger's
    weekly-maximum rows from disagreeing."""
    rows = []
    with open(cfg.path('paths.cases'), newline='', encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            d = date.fromisoformat(r['date'])
            vals = {s['key']: num(r.get(s['key'])) for s in SERIES}
            if any(v is not None for v in vals.values()):
                rows.append((d, vals))
    return rows


def load_camden(cfg, on_dates):
    """Camden daily cases summed over the same seven-day windows, so the
    comparator is the same quantity over the same period rather than a daily
    figure standing beside a weekly one."""
    path = config.ROOT / str(cfg['camden.cache'])
    if not path.exists():
        return []
    daily = {}
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            if line.startswith('#'):
                continue
            parts = line.strip().split(',')
            if len(parts) != 2 or parts[0] == 'date':
                continue
            try:
                daily[date.fromisoformat(parts[0])] = float(parts[1])
            except ValueError:
                continue
    out = []
    for d in on_dates:
        window = [daily.get(d - timedelta(days=i)) for i in range(7)]
        if all(v is None for v in window):
            continue
        out.append((d, sum(v for v in window if v is not None)))
    return out


def nice_ticks(hi, count=5):
    """Round axis steps whose top tick is at or above the maximum.

    The `<=` stopping condition this first had stopped *below* the data: a
    peak of 525 produced ticks 0/200/400 and the December 2021 spike was drawn
    out through the top of its panel and across the lanes above it. An axis
    band that crops the data is in the anti-pattern catalogue, and it is the
    kind of fault only looking at the rendered page reveals.
    """
    if hi <= 0:
        return [0]
    raw = hi / count
    mag = 10 ** (len(str(int(raw))) - 1) if raw >= 1 else 1
    step = mag * 10
    for mult in (1, 2, 2.5, 5, 10):
        if mag * mult >= raw:
            step = mag * mult
            break
    ticks, v = [], 0.0
    while v < hi - step * 0.001:
        ticks.append(int(v))
        v += step
    ticks.append(int(v))
    return ticks


# ------------------------------------------------------------------- SVG

def esc(s):
    return html.escape(str(s), quote=True)


class Canvas:
    """Enough SVG to draw this page, with escaping that cannot be forgotten.

    Every string that reaches the DOM from the newsletters goes through the
    JSON payload and is written with textContent on the client. Nothing in the
    scraped corpus is interpolated into markup as markup, here or there.
    """

    def __init__(self):
        self.parts = []

    def add(self, s):
        self.parts.append(s)

    def rect(self, x, y, w, h, cls='', extra=''):
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w, 0):.1f}" '
                 f'height="{max(h, 0):.1f}"'
                 + (f' class="{cls}"' if cls else '') + f' {extra}/>')

    def line(self, x1, y1, x2, y2, cls=''):
        self.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" '
                 f'y2="{y2:.1f}"' + (f' class="{cls}"' if cls else '') + '/>')

    def text(self, x, y, s, cls='', extra=''):
        self.add(f'<text x="{x:.1f}" y="{y:.1f}"'
                 + (f' class="{cls}"' if cls else '')
                 + f' {extra}>{esc(s)}</text>')

    def path(self, d, cls='', extra=''):
        self.add(f'<path d="{d}"' + (f' class="{cls}"' if cls else '')
                 + f' {extra}/>')

    def __str__(self):
        return '\n'.join(self.parts)


def build(rows, cfg):
    ucl_rows = load_cases(cfg)
    case_dates = [d for d, _ in ucl_rows]
    camden = load_camden(cfg, case_dates)

    first = min(date.fromisoformat(r['date']) for r in rows)
    last = max(date.fromisoformat(r['date']) for r in rows)
    if case_dates:
        last = max(last, max(case_dates))
    span = (last - first).days or 1
    inner = W - PAD_L - PAD_R

    def x_of(d):
        return PAD_L + inner * ((d - first).days / span)

    lanes_top = PAD_T
    lanes_h = LANE_H * len(TRACKS)
    ucl_top = lanes_top + lanes_h + GAP
    cam_top = ucl_top + UCL_H + GAP + 22
    height = cam_top + CAM_H + PAD_B + 16

    c = Canvas()

    # --- phase bands, drawn first so everything sits above them.
    # Neutral by rule: a categorical hue here would impersonate a series, and
    # the boundaries are solid because a dashed region reads as a projection.
    phases = cfg.phases()
    band_top, band_bot = lanes_top - 6, cam_top + CAM_H + 6
    for i, p in enumerate(phases):
        start = date.fromisoformat(str(p['start']))
        nxt = (date.fromisoformat(str(phases[i + 1]['start']))
               if i + 1 < len(phases) else last + timedelta(days=1))
        if nxt < first or start > last:
            continue
        x0, x1 = x_of(max(start, first)), x_of(min(nxt, last))
        if i % 2 == 0:
            c.rect(x0, band_top, x1 - x0, band_bot - band_top, 'band')
        if first < start <= last:
            c.line(x0, band_top, x0, band_bot, 'band-edge')
        if x1 - x0 > 54:
            # The number is the whole label there is room for, so the phase
            # name goes in a native <title>: it needs no script, so it still
            # works on the no-JavaScript path.
            c.add(f'<g class="phase-tag"><title>Phase {i + 1}: '
                  f'{esc(p["name"])}</title>')
            c.rect(x0, band_top - 20, min(x1 - x0, 90), 18, 'phase-hit')
            c.text(x0 + 5, band_top - 8, f'{i + 1}', 'phase-num')
            c.add('</g>')

    # --- x axis, shared by every panel. Drawn once at the foot.
    axis_y = cam_top + CAM_H
    c.line(PAD_L, axis_y, W - PAD_R, axis_y, 'axis')
    y, drawn = first.year, 0
    while y <= last.year:
        for m in (1, 4, 7, 10):
            t = date(y, m, 1)
            if not (first <= t <= last):
                continue
            tx = x_of(t)
            c.line(tx, axis_y, tx, axis_y + 4, 'axis')
            # January carries the year, and so does the first tick drawn,
            # which would otherwise read as a bare "Apr" with no year anywhere
            # to its left.
            label = f'{SHORT[m - 1]} {y}' if (m == 1 or drawn == 0) \
                else SHORT[m - 1]
            c.text(tx, axis_y + 16, label, 'tick', 'text-anchor="middle"')
            drawn += 1
        y += 1

    # --- event lanes
    by_track_day = {}
    for r in rows:
        by_track_day.setdefault(r['track'], {}).setdefault(r['date'], []).append(r)

    marks = []
    for li, (track, label) in enumerate(TRACKS):
        top = lanes_top + li * LANE_H
        mid = top + LANE_H / 2
        c.rect(PAD_L, top + 1, inner, LANE_H - 2, 'lane',
               f'data-lane="{track}" data-mid="{mid:.1f}"')
        c.line(PAD_L, mid, W - PAD_R, mid, 'lane-rule')
        c.text(PAD_L - 10, mid + 4, label, 'lane-label', 'text-anchor="end"')
        days = by_track_day.get(track, {})
        for iso, group in sorted(days.items()):
            d = date.fromisoformat(iso)
            cx = x_of(d)
            idx = len(marks)
            marks.append({
                'i': idx, 'track': track, 'date': iso,
                'when': fmt_date(d),
                'events': [{
                    'headline': g['headline'],
                    'category': g['category'],
                    'kind': g['date_kind'],
                    'quote': g['quote'],
                    'detail': g['detail'],
                } for g in group],
            })
            # One mark per day per lane, drawn as a tick rather than a dot.
            #
            # The UCL track has events on 141 separate days inside 1,038
            # pixels, so round markers at the 8px floor overlapped into an
            # unreadable smear: rendering the page is what showed it. A rug of
            # thin ticks is the honest encoding for an event series this
            # dense, and it does not pretend each mark is a measured point.
            #
            # Precise pointing is then handled by nearest-day snapping across
            # the whole lane rather than per-mark hit rectangles, which at 7px
            # spacing would overlap each other anyway. Every mark stays in the
            # DOM and stays focusable, so the keyboard path is unaffected.
            extra = (f'data-i="{idx}" data-track="{track}" data-x="{cx:.1f}" '
                     f'tabindex="0" role="button" '
                     f'aria-label="{esc(fmt_date(d))}, {len(group)} '
                     f'event{"s" if len(group) != 1 else ""} on the '
                     f'{esc(label)} track"')
            c.add(f'<g class="mark" {extra}>')
            c.rect(cx - TICK_W / 2, mid - TICK_H / 2, TICK_W, TICK_H,
                   'tick-mark' + (' multi' if len(group) > 1 else ''),
                   'rx="1"')
            c.add('</g>')

    # --- the UCL case panel
    vals = [v for _, row in ucl_rows for v in row.values() if v is not None]
    ucl_max = max(vals) if vals else 1
    ticks = nice_ticks(ucl_max)
    top_val = ticks[-1]

    def y_ucl(v):
        return ucl_top + UCL_H - (v / top_val) * UCL_H

    for t in ticks:
        yy = y_ucl(t)
        c.line(PAD_L, yy, W - PAD_R, yy, 'grid' if t else 'axis')
        c.text(PAD_L - 10, yy + 4, f'{t:,}', 'tick', 'text-anchor="end"')
    c.text(PAD_L - 10, ucl_top - 10, 'UCL confirmed cases per week',
           'panel-title', 'text-anchor="start"')

    for s in SERIES:
        pts = [(x_of(d), y_ucl(row[s['key']]))
               for d, row in ucl_rows if row[s['key']] is not None]
        if not pts:
            continue
        d = 'M' + ' L'.join(f'{x:.1f},{y:.1f}' for x, y in pts)
        c.path(d, 'series', f'data-series="{s["key"]}" '
                            f'style="stroke:var(--series-{s["slot"]})"'
                            + ('' if s['on'] else ' hidden="hidden"'))

    # Selective direct labels: the December 2021 peak and nothing else. A
    # number on every point is the anti-pattern; the axis and tooltip carry the
    # rest.
    peak_d, peak_v = None, 0
    for d, row in ucl_rows:
        v = row.get('student7.on')
        if v is not None and v > peak_v:
            peak_d, peak_v = d, v
    if peak_d:
        # Placed to the left of the spike and inside the panel. Above it, the
        # label ran out through the top of the plot and into the lanes.
        px, py = x_of(peak_d), y_ucl(peak_v)
        c.add('<g class="callout" data-series="student7.on">')
        c.line(px - 6, py, px - 16, py, 'callout-rule')
        c.text(px - 21, py + 4,
               f'{int(peak_v)} in the week to '
               f'{peak_d.day} {SHORT[peak_d.month - 1]} {peak_d.year}',
               'callout-text', 'text-anchor="end"')
        c.add('</g>')

    # --- the Camden panel. Its own plot, its own axis, the same unit.
    cam_max = max((v for _, v in camden), default=1)
    # count=3 rather than 2: at 2 the rounding jumped to a 10,000 top tick for
    # a 5,922 peak and left half the panel empty.
    cticks = nice_ticks(cam_max, 3)
    ctop = cticks[-1]

    def y_cam(v):
        return cam_top + CAM_H - (v / ctop) * CAM_H

    for t in cticks:
        yy = y_cam(t)
        c.line(PAD_L, yy, W - PAD_R, yy, 'grid' if t else 'axis')
        c.text(PAD_L - 10, yy + 4, f'{t:,}', 'tick', 'text-anchor="end"')
    c.text(PAD_L - 10, cam_top - 10,
           'Camden borough confirmed cases per week', 'panel-title',
           'text-anchor="start"')
    if camden:
        pts = [(x_of(d), y_cam(v)) for d, v in camden]
        area = ('M' + f'{pts[0][0]:.1f},{y_cam(0):.1f} L'
                + ' L'.join(f'{x:.1f},{y:.1f}' for x, y in pts)
                + f' L{pts[-1][0]:.1f},{y_cam(0):.1f} Z')
        c.path(area, 'camden-wash')
        c.path('M' + ' L'.join(f'{x:.1f},{y:.1f}' for x, y in pts), 'camden-line')

    # --- crosshair, hidden until script moves it
    c.add(f'<line id="crosshair" class="crosshair" x1="0" y1="{lanes_top - 6}" '
          f'x2="0" y2="{cam_top + CAM_H:.1f}" hidden="hidden"/>')
    c.rect(PAD_L, ucl_top, inner, (cam_top + CAM_H) - ucl_top, 'plot-hit',
           'id="plot-hit"')

    payload = {
        'first': first.isoformat(),
        'span': span,
        'padL': PAD_L, 'inner': inner,
        'uclTop': ucl_top, 'uclH': UCL_H, 'topVal': top_val,
        'camTop': cam_top, 'camH': CAM_H, 'camTop_val': ctop,
        'series': [{'key': s['key'], 'label': s['label'], 'slot': s['slot'],
                    'on': s['on']} for s in SERIES],
        'cases': [[d.isoformat()] + [row[s['key']] for s in SERIES]
                  for d, row in ucl_rows],
        'camden': [[d.isoformat(), v] for d, v in camden],
        'marks': marks,
        'tracks': [{'key': k, 'label': l} for k, l in TRACKS],
    }
    return str(c), height, payload, first, last


# ------------------------------------------------------------------ page

CSS = """
:root {
  --ink:#1a1a1a; --muted:#5c5c5c; --rule:#d8d8d8; --link:#23527c;
  --bg:#ffffff; --panel:#f6f6f9;
  --surface-1:#fcfcfb; --text-primary:#1a1a1a; --text-secondary:#5c5c5c;
  --grid:#e7e7e4; --mark:#54544e; --mark-strong:#1a1a1a;
  --series-1:#2a78d6; --series-2:#eb6834; --series-3:#1baf7a; --series-4:#eda100;
  --band:#f2f2ef; --band-edge:#e0e0dc; --camden:#8d8d84;
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) {
    color-scheme: dark;
    --ink:#e9e9e4; --muted:#a8a89f; --rule:#3a3a37; --link:#8fb6e8;
    --bg:#141413; --panel:#1f1f1d;
    --surface-1:#1a1a19; --text-primary:#ffffff; --text-secondary:#c3c2b7;
    --grid:#2e2e2b; --mark:#a8a89f; --mark-strong:#ffffff;
    --series-1:#3987e5; --series-2:#d95926; --series-3:#199e70; --series-4:#c98500;
    --band:#201f1e; --band-edge:#333330; --camden:#8b8a81;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --ink:#e9e9e4; --muted:#a8a89f; --rule:#3a3a37; --link:#8fb6e8;
  --bg:#141413; --panel:#1f1f1d;
  --surface-1:#1a1a19; --text-primary:#ffffff; --text-secondary:#c3c2b7;
  --grid:#2e2e2b; --mark:#a8a89f; --mark-strong:#ffffff;
  --series-1:#3987e5; --series-2:#d95926; --series-3:#199e70; --series-4:#c98500;
  --band:#201f1e; --band-edge:#333330; --camden:#8b8a81;
}
*,*::before,*::after { box-sizing:border-box; }
html { -webkit-text-size-adjust:100%; }
body {
  margin:0; background:var(--bg); color:var(--ink);
  font-family:"Charter","Bitstream Charter","Sitka Text",Cambria,Georgia,serif;
  font-size:17px; line-height:1.55;
}
.content { max-width:78rem; margin:0 auto; padding:0 1.25rem 4rem; }
h1,h2 {
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  line-height:1.2;
}
h1 { font-size:2.1rem; margin:2rem 0 .75rem; }
h2 { font-size:1.3rem; margin:2.5rem 0 .75rem; padding-bottom:.3rem;
     border-bottom:1px solid var(--rule); }
p { margin:0 0 1rem; max-width:60rem; }
a { color:var(--link); }
.lede { font-size:1.05rem; }
.muted { color:var(--muted); }

/* One filter row above everything, scoping the whole page. Never a per-lane
   control inside a card. */
.filters {
  display:flex; flex-wrap:wrap; gap:.5rem 1.5rem; align-items:center;
  margin:1.5rem 0 .5rem; padding:.75rem 1rem;
  background:var(--panel); border:1px solid var(--rule); border-radius:6px;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  font-size:.85rem;
}
.filters fieldset { border:0; margin:0; padding:0; display:flex;
  flex-wrap:wrap; gap:.4rem .9rem; align-items:center; }
.filters legend { float:left; margin-right:.75rem; color:var(--muted);
  font-weight:600; }
.filters label { display:inline-flex; align-items:center; gap:.35rem;
  cursor:pointer; min-height:24px; }
.filters input { accent-color:var(--link); width:15px; height:15px; }
.swatch { width:22px; height:3px; border-radius:2px; display:inline-block; }
.range { display:flex; align-items:center; gap:.4rem; }
.range input { font:inherit; padding:.15rem .3rem; min-height:24px;
  background:var(--bg); color:var(--ink); border:1px solid var(--rule);
  border-radius:3px; }
button.reset { font:inherit; font-size:.85rem; padding:.2rem .6rem;
  min-height:24px; cursor:pointer; background:var(--bg); color:var(--ink);
  border:1px solid var(--rule); border-radius:3px; }

.figure { position:relative; margin:0; background:var(--surface-1);
  border:1px solid var(--rule); border-radius:6px; padding:.5rem 0 0;
  overflow-x:auto; }
svg { display:block; width:100%; height:auto; min-width:56rem;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }

.band { fill:var(--band); }
.band-edge { stroke:var(--band-edge); stroke-width:1; }
.phase-num { fill:var(--text-secondary); font-size:10px; font-weight:600;
  pointer-events:none; }
.phase-hit { fill:transparent; }
.phase-tag { cursor:help; }
.lane-rule { stroke:var(--grid); stroke-width:1; }
.lane-label { fill:var(--text-secondary); font-size:12px; }
.axis { stroke:var(--text-secondary); stroke-width:1; }
.grid { stroke:var(--grid); stroke-width:1; }
.tick { fill:var(--text-secondary); font-size:11px;
  font-variant-numeric:tabular-nums; }
.panel-title { fill:var(--text-primary); font-size:12px; font-weight:600; }

.lane { fill:transparent; pointer-events:all; cursor:crosshair; }
.tick-mark { fill:var(--mark); }
.tick-mark.multi { fill:var(--mark-strong); }
.mark { pointer-events:none; }
.mark.on .tick-mark, .mark:focus-visible .tick-mark {
  fill:var(--mark-strong); stroke:var(--link); stroke-width:2.5; }
.mark:focus { outline:none; }
.mark[hidden] { display:none; }

.series { fill:none; stroke-width:2; stroke-linejoin:round;
  stroke-linecap:round; }
.series[hidden] { display:none; }
.callout-rule { stroke:var(--text-secondary); stroke-width:1; }
.callout-text { fill:var(--text-primary); font-size:11.5px; font-weight:600; }
.callout[hidden] { display:none; }
.camden-line { fill:none; stroke:var(--camden); stroke-width:2;
  stroke-linejoin:round; }
.camden-wash { fill:var(--camden); opacity:.1; stroke:none; }
.crosshair { stroke:var(--text-secondary); stroke-width:1; pointer-events:none; }
.plot-hit { fill:transparent; }

.legend { display:flex; flex-wrap:wrap; gap:.4rem 1.25rem; margin:.6rem 0 0;
  padding:0 1rem .75rem;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  font-size:.82rem; color:var(--text-secondary); }
.legend span { display:inline-flex; align-items:center; gap:.4rem; }
.legend .off { opacity:.35; }

#tip {
  position:absolute; z-index:5; max-width:26rem; pointer-events:none;
  background:var(--bg); color:var(--ink);
  border:1px solid var(--rule); border-radius:5px;
  box-shadow:0 2px 10px rgba(0,0,0,.16); padding:.55rem .7rem;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  font-size:.8rem; line-height:1.4;
}
#tip[hidden] { display:none; }
#tip .when { font-weight:600; margin-bottom:.3rem; }
#tip .row { display:flex; gap:.5rem; align-items:baseline; }
#tip .val { font-variant-numeric:tabular-nums; font-weight:600;
  min-width:3.2rem; text-align:right; }
#tip .key { width:14px; height:3px; border-radius:2px; flex:none;
  align-self:center; }
#tip .ev { margin:.35rem 0 0; }
#tip .ev b { font-weight:600; }
#tip .meta { color:var(--muted); font-size:.75rem; }
#tip q { font-style:italic; }

noscript .note { display:block; background:var(--panel);
  border:1px solid var(--rule); border-radius:6px; padding:.75rem 1rem;
  margin:1rem 0; font-size:.9rem; }
@media (prefers-reduced-motion:no-preference) {
  .dot { transition:r .08s ease, fill .08s ease; }
}
"""

JS = r"""
(function () {
  var D = JSON.parse(document.getElementById('payload').textContent);
  var svg = document.getElementById('chart');
  var fig = document.getElementById('figure');
  var tip = document.getElementById('tip');
  var cross = document.getElementById('crosshair');
  var visible = {};
  D.series.forEach(function (s) { visible[s.key] = s.on; });
  var trackOn = {};
  D.tracks.forEach(function (t) { trackOn[t.key] = true; });
  var from = null, to = null;

  var first = new Date(D.first + 'T00:00:00Z');
  function dayOf(iso) {
    return Math.round((new Date(iso + 'T00:00:00Z') - first) / 86400000);
  }
  function xOf(iso) { return D.padL + D.inner * (dayOf(iso) / D.span); }

  // Every string below originates in scraped UCL email or a fetched PDF.
  // It reaches the DOM through textContent only. Nothing is concatenated
  // into markup anywhere in this file.
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null && text !== '') n.textContent = text;
    return n;
  }

  function inRange(iso) {
    if (from && iso < from) return false;
    if (to && iso > to) return false;
    return true;
  }

  function applyFilters() {
    D.series.forEach(function (s) {
      var p = svg.querySelector('path[data-series="' + s.key + '"]');
      if (p) { if (visible[s.key]) p.removeAttribute('hidden');
               else p.setAttribute('hidden', 'hidden'); }
    });
    var call = svg.querySelector('.callout');
    if (call) {
      if (visible['student7.on']) call.removeAttribute('hidden');
      else call.setAttribute('hidden', 'hidden');
    }
    Array.prototype.forEach.call(svg.querySelectorAll('.mark'), function (g) {
      var m = D.marks[+g.getAttribute('data-i')];
      var show = trackOn[m.track] && inRange(m.date);
      if (show) { g.removeAttribute('hidden'); g.setAttribute('tabindex', '0'); }
      else { g.setAttribute('hidden', 'hidden'); g.setAttribute('tabindex', '-1'); }
    });
    Array.prototype.forEach.call(
      document.querySelectorAll('.legend span[data-key]'), function (s) {
        s.classList.toggle('off', !visible[s.getAttribute('data-key')]);
      });
  }

  function place(x, y) {
    var box = fig.getBoundingClientRect();
    tip.hidden = false;
    var w = tip.offsetWidth, h = tip.offsetHeight;
    var left = x - box.left + 14, top = y - box.top - h - 10;
    if (left + w > box.width - 6) left = x - box.left - w - 14;
    if (left < 6) left = 6;
    if (top < 6) top = y - box.top + 18;
    tip.style.left = left + 'px';
    tip.style.top = top + 'px';
  }

  function showMark(g, cx, cy) {
    var m = D.marks[+g.getAttribute('data-i')];
    tip.replaceChildren();
    tip.appendChild(el('div', 'when', m.when));
    m.events.forEach(function (e) {
      var box = el('div', 'ev');
      box.appendChild(el('b', null, e.headline));
      box.appendChild(el('div', 'meta', e.category + ' · ' + e.kind));
      if (e.quote) {
        var q = el('q', null, e.quote.length > 190
          ? e.quote.slice(0, 190).replace(/\s+\S*$/, '') + '…' : e.quote);
        box.appendChild(q);
      } else if (e.detail) {
        box.appendChild(el('div', null, e.detail));
      }
      tip.appendChild(box);
    });
    place(cx, cy);
  }

  // Event marks: nearest-day snapping per lane rather than per-mark hit
  // rectangles. At 141 marks across 1,038 pixels the 24px targets a pointer
  // needs would overlap one another several deep, so the whole lane is the
  // target and the closest mark to the pointer wins.
  var lit = null;
  function light(g) {
    if (lit === g) return;
    if (lit) lit.classList.remove('on');
    lit = g;
    if (lit) lit.classList.add('on');
  }
  Array.prototype.forEach.call(svg.querySelectorAll('.lane'), function (lane) {
    var track = lane.getAttribute('data-lane');
    lane.addEventListener('pointermove', function (ev) {
      var loc = toSvg(ev);
      var best = null, bestD = Infinity;
      Array.prototype.forEach.call(
        svg.querySelectorAll('.mark[data-track="' + track + '"]'),
        function (g) {
          if (g.hasAttribute('hidden')) return;
          var dx = Math.abs(parseFloat(g.getAttribute('data-x')) - loc.x);
          if (dx < bestD) { bestD = dx; best = g; }
        });
      if (!best || bestD > 14) { light(null); hide(); return; }
      light(best);
      var r = best.getBoundingClientRect();
      showMark(best, r.left + r.width / 2, r.top);
    });
    lane.addEventListener('pointerleave', function () { light(null); hide(); });
  });

  // Keyboard focus shows exactly what hover shows.
  svg.addEventListener('focusin', function (ev) {
    var g = ev.target.closest ? ev.target.closest('.mark') : null;
    if (!g) return;
    light(g);
    var r = g.getBoundingClientRect();
    showMark(g, r.left + r.width / 2, r.top);
  });
  svg.addEventListener('focusout', function () { light(null); hide(); });

  function toSvg(ev) {
    var pt = svg.createSVGPoint();
    pt.x = ev.clientX; pt.y = ev.clientY;
    return pt.matrixTransform(svg.getScreenCTM().inverse());
  }

  function hide() { tip.hidden = true; cross.hidden = true; }

  // Crosshair on the case panels: snaps to the nearest reading, so the pointer
  // never has to land on a line.
  var plot = document.getElementById('plot-hit');
  plot.addEventListener('pointermove', function (ev) {
    var loc = toSvg(ev);
    var frac = (loc.x - D.padL) / D.inner;
    var day = frac * D.span;
    var best = null, bestD = Infinity;
    D.cases.forEach(function (row) {
      var dd = Math.abs(dayOf(row[0]) - day);
      if (dd < bestD) { bestD = dd; best = row; }
    });
    if (!best || !inRange(best[0])) { hide(); return; }
    var cx = xOf(best[0]);
    cross.setAttribute('x1', cx); cross.setAttribute('x2', cx);
    cross.hidden = false;

    tip.replaceChildren();
    var when = new Date(best[0] + 'T00:00:00Z');
    tip.appendChild(el('div', 'when', 'Week to ' + when.getUTCDate() + ' ' +
      ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][when.getUTCMonth()] +
      ' ' + when.getUTCFullYear()));
    D.series.forEach(function (s, i) {
      if (!visible[s.key]) return;
      var v = best[i + 1];
      if (v === null) return;
      var row = el('div', 'row');
      var key = el('span', 'key');
      key.style.background = 'var(--series-' + s.slot + ')';
      row.appendChild(el('span', 'val', String(v)));
      row.appendChild(key);
      row.appendChild(el('span', null, s.label));
      tip.appendChild(row);
    });
    var cam = null;
    for (var j = 0; j < D.camden.length; j++) {
      if (D.camden[j][0] === best[0]) { cam = D.camden[j][1]; break; }
    }
    if (cam !== null) {
      var r2 = el('div', 'row');
      var k2 = el('span', 'key');
      k2.style.background = 'var(--camden)';
      r2.appendChild(el('span', 'val', String(Math.round(cam))));
      r2.appendChild(k2);
      r2.appendChild(el('span', null, 'Camden borough'));
      tip.appendChild(r2);
    }
    place(ev.clientX, ev.clientY);
  });
  plot.addEventListener('pointerleave', hide);

  document.querySelectorAll('input[data-series]').forEach(function (box) {
    box.addEventListener('change', function () {
      visible[box.getAttribute('data-series')] = box.checked;
      applyFilters();
    });
  });
  document.querySelectorAll('input[data-track]').forEach(function (box) {
    box.addEventListener('change', function () {
      trackOn[box.getAttribute('data-track')] = box.checked;
      applyFilters();
    });
  });
  var f = document.getElementById('from'), t = document.getElementById('to');
  function onRange() {
    from = f.value || null; to = t.value || null;
    applyFilters();
  }
  f.addEventListener('change', onRange);
  t.addEventListener('change', onRange);
  document.getElementById('reset').addEventListener('click', function () {
    f.value = ''; t.value = ''; from = to = null;
    document.querySelectorAll('input[data-track]').forEach(function (b) {
      b.checked = true; trackOn[b.getAttribute('data-track')] = true;
    });
    document.querySelectorAll('input[data-series]').forEach(function (b) {
      var k = b.getAttribute('data-series');
      var def = D.series.filter(function (s) { return s.key === k; })[0].on;
      b.checked = def; visible[k] = def;
    });
    applyFilters();
  });

  applyFilters();
})();
"""


def page(svg, height, payload, rows, cfg, first, last):
    ucl = sum(1 for r in rows if r['track'] == 'ucl')
    nat = sum(1 for r in rows if r['track'] in ('national', 'sector'))
    dat = sum(1 for r in rows if r['track'] == 'data')

    out = []
    a = out.append
    a('<!doctype html>')
    a('<html lang="en">')
    a('<head>')
    a('<meta charset="utf-8">')
    a('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
    a('<title>UCL and the pandemic: an interactive chronology</title>')
    a('<meta name="description" content="UCL\'s COVID-19 decisions '
      'against national policy and its own case data, 2020 to 2022.">')
    a(f'<style>{CSS}</style>')
    a('</head>')
    a('<body>')
    a('<main class="content">')
    a('<h1>UCL and the pandemic</h1>')
    a(f'<p class="lede">{len(rows)} dated events between {fmt_date(first)} '
      f'and {fmt_date(last)}: {ucl} decisions UCL took, {nat} national and '
      f'sector measures they respond to, and {dat} readings from the case '
      'series UCL published. Every event carries a verbatim quotation from '
      'the document that announced it, checked mechanically against the '
      'preserved source.</p>')
    a('<p class="muted">Hover or focus any mark for the events on that day. '
      'The case panels share one time axis with the lanes above them and with '
      'each other. Camden is drawn in its own panel rather than on the same '
      'scale: it peaks near six thousand cases in a week against UCL\'s five '
      'hundred, so a shared axis would flatten every UCL line. Both panels '
      'show the same quantity, confirmed cases per week.</p>')

    a('<noscript><span class="note">This page needs JavaScript for the '
      'filters, the crosshair and the tooltips. The chart itself is drawn '
      'server-side and is fully visible without it, and every event with its '
      'full quotation is in <a href="TIMELINE.md">TIMELINE.md</a> and '
      '<a href="timeline.csv">timeline.csv</a>.</span></noscript>')

    a('<form class="filters" id="filters" onsubmit="return false">')
    a('<fieldset><legend>Tracks</legend>')
    for k, label in TRACKS:
        a(f'<label><input type="checkbox" data-track="{k}" checked> '
          f'{esc(label)}</label>')
    a('</fieldset>')
    a('<fieldset><legend>Case series</legend>')
    for s in SERIES:
        checked = ' checked' if s['on'] else ''
        a(f'<label><input type="checkbox" data-series="{s["key"]}"{checked}> '
          f'<span class="swatch" style="background:var(--series-{s["slot"]})">'
          f'</span> {esc(s["label"])}</label>')
    a('</fieldset>')
    a('<fieldset><legend>Dates</legend><span class="range">'
      f'<label for="from">from</label><input type="date" id="from" '
      f'min="{first.isoformat()}" max="{last.isoformat()}">'
      f'<label for="to">to</label><input type="date" id="to" '
      f'min="{first.isoformat()}" max="{last.isoformat()}">'
      '</span></fieldset>')
    a('<button type="button" class="reset" id="reset">Reset</button>')
    a('</form>')

    a('<figure class="figure" id="figure">')
    a(f'<svg id="chart" viewBox="0 0 {W} {height:.0f}" '
      f'role="img" aria-label="Timeline of UCL pandemic decisions with '
      f'weekly confirmed case counts">')
    a(svg)
    a('</svg>')
    # A legend is always present for two or more series, so identity is never
    # carried by colour alone.
    a('<figcaption class="legend">')
    for s in SERIES:
        off = '' if s['on'] else ' off'
        a(f'<span data-key="{s["key"]}" class="{off.strip()}">'
          f'<span class="swatch" style="background:var(--series-{s["slot"]})">'
          f'</span>{esc(s["label"])}</span>')
    a('<span><span class="swatch" style="background:var(--camden)"></span>'
      'Camden borough</span>')
    a('</figcaption>')
    a('<div id="tip" hidden></div>')
    a('</figure>')

    a('<h2>Reading this chart</h2>')
    a('<p>The four lanes are the four tracks of the ledger, separated by '
      'position rather than colour so that the categorical palette is free '
      'for the case series. One mark is one day in one lane: several '
      'decisions often landed on a single day, and a mark for each would '
      'overplot into a smear implying a density the record does not support. '
      'The tooltip lists everything that happened on that day.</p>')
    a('<p>Shaded bands are the eight pandemic phases, numbered along the top '
      'and drawn in neutral greys. They are regions, not series, and a '
      'categorical hue there would impersonate one.</p>')
    a('<p>The full chronology, with every quotation and the lag in days '
      'wherever a UCL action responds to a national one, is in '
      '<a href="TIMELINE.md">TIMELINE.md</a>. The ledger behind both is '
      '<a href="timeline.csv">timeline.csv</a>.</p>')
    a('</main>')
    a(f'<script type="application/json" id="payload">'
      f'{json.dumps(payload, separators=(",", ":"))}</script>')
    a(f'<script>{JS}</script>')
    a('</body>')
    a('</html>')
    return '\n'.join(out) + '\n'


def main():
    cfg, _ = config.load()
    ledger = cfg.path('paths.ledger')
    if not ledger.exists():
        sys.exit(f'no ledger at {ledger}')
    rows, _ = load_rows(ledger)
    rows.sort(key=lambda r: (r['date'], r['track'], r['headline']))

    svg, height, payload, first, last = build(rows, cfg)
    text = page(svg, height, payload, rows, cfg, first, last)
    out = cfg.path('paths.html_out')
    out.write_text(text, encoding='utf-8')

    print(f'wrote:    {out}')
    print(f'size:     {len(text):,} bytes')
    print(f'marks:    {len(payload["marks"])} day-marks for {len(rows)} rows')
    print(f'cases:    {len(payload["cases"])} readings, '
          f'{len(payload["camden"])} Camden weeks')
    return 0


if __name__ == '__main__':
    sys.exit(main())
