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
import subprocess
import sys
from datetime import date, timedelta

import config
from validate import load_rows


def build_commit(cfg):
    """The commit the page was rendered from, for the footer.

    A page can never carry its own commit hash — it is written before it is
    committed — so this names the state it was built *from*. That is the useful
    thing anyway: it says which ledger and which scripts produced what the
    reader is looking at.

    `build.commit` in the TOML overrides the lookup, for a build somewhere
    without git or without this checkout. An empty setting means detect, and a
    detection that fails prints nothing rather than guessing: a wrong hash is
    worse than no hash, because a reader would try to resolve it.

    The generated outputs are excluded from the dirty check. Rendering writes
    them, so the tree is modified by the act of building and would report dirty
    on every run, which would make the marker mean nothing.
    """
    override = str(cfg.get('build.commit', '') or '').strip()
    if override:
        return override, False
    def git(*args):
        return subprocess.run(('git', '-C', str(config.ROOT)) + args,
                              capture_output=True, text=True, timeout=10)
    try:
        rev = git('rev-parse', '--short', 'HEAD')
        if rev.returncode != 0:
            return '', False
        status = git('status', '--porcelain')
        generated = {str(cfg.get(k, '')) for k in
                     ('paths.html_out', 'paths.markdown_out')}
        dirty = any(line[3:].strip() not in generated
                    for line in status.stdout.splitlines() if line.strip())
        return rev.stdout.strip(), dirty
    except (OSError, subprocess.SubprocessError):
        return '', False


def build_repo(cfg):
    """The repository this page was built in, as (url, owner/name).

    Detected from `origin` on the same terms as the commit, and overridable by
    `build.repo` for the same reasons. Both the https and the ssh forms of a
    GitHub remote are normalised, and a remote that is neither is used as-is
    with no owner/name label, so a self-hosted checkout still links somewhere
    truthful rather than being silently dropped.
    """
    url = str(cfg.get('build.repo', '') or '').strip()
    if not url:
        try:
            r = subprocess.run(('git', '-C', str(config.ROOT), 'remote',
                                'get-url', 'origin'),
                               capture_output=True, text=True, timeout=10)
            if r.returncode != 0:
                return '', ''
            url = r.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return '', ''
    if url.startswith('git@'):                    # git@host:owner/name.git
        host, _, path = url[4:].partition(':')
        url = f'https://{host}/{path}'
    if url.endswith('.git'):
        url = url[:-4]
    if not url.startswith('https://'):
        return '', ''
    parts = url.split('/')
    label = '/'.join(parts[-2:]) if len(parts) >= 5 else ''
    return url, label

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


def fmt_date(d, precision='day'):
    """A ledger date as a reader expects to see it, honouring its precision.

    render_md.py has always done this; this file did not, so 33 month-precision
    and 1 week-precision rows were drawn as a tick on one day and captioned with
    that day. "Camden and UCL both peak in November 2020" is stored as
    2020-11-01 and read "1 November 2020" in the tooltip -- a precision the
    ledger does not claim, invented by the renderer that discarded the field.
    The mark stays where it is; only the caption stops overstating."""
    if precision == 'month':
        return f'{MONTHS[d.month - 1]} {d.year}'
    if precision == 'week':
        return f'week of {d.day} {MONTHS[d.month - 1]} {d.year}'
    return f'{d.day} {MONTHS[d.month - 1]} {d.year}'


def day_precision(group):
    """The coarsest precision among the events sharing a mark, so a day that
    mixes an exact row with a month-precision one does not promise the exact
    one's precision for both."""
    order = {'day': 0, 'week': 1, 'month': 2}
    worst = max(group, key=lambda g: order.get(g.get('date_precision'), 0))
    return worst.get('date_precision') or 'day'


# Band labels come from the config, so their width is not knowable in advance
# and a fixed threshold would let a longer one spill into the regime next to it.
# Estimated at the band label's 10px semibold system sans, checked against the
# rendered page: the estimate runs a few pixels wide of the truth, which is the
# direction that errs towards dropping a label rather than overlapping one. The
# same three constants are used by the script, so a redraw at a zoomed range
# makes the same decision as the server did.
LABEL_WIDE, LABEL_NARROW, LABEL_THIN = 6.3, 5.2, 3.0
LABEL_PAD = 8.0

# Shading steps the stylesheet defines, .band-1 through .band-3, each a
# validated step of the neutral ramp in both modes. Level 0 is drawn as no fill
# at all, so it needs none. Raising this means adding steps to CSS first.
MAX_BAND_LEVEL = 3


WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight',
         'nine', 'ten', 'eleven', 'twelve', 'thirteen']


def spell(n):
    """Small counts read as words in the page's prose, the way the rest of it
    is written; the sentence they appear in is generated, so the number is not
    known when the sentence is."""
    return WORDS[n] if n < len(WORDS) else str(n)


def label_width(s):
    return sum(LABEL_WIDE if c.isupper() or c.isdigit()
               else LABEL_NARROW if c.isalpha() else LABEL_THIN for c in s)


# ------------------------------------------------------------------- data

def load_cases(cfg):
    """The UCL series as published: the seven-day columns, not a re-derivation.
    Using UCL's own weekly figures is what stops the chart and the ledger's
    weekly-maximum rows from disagreeing.

    A date inside the series that carries no reading at all is kept, with its
    values None, so that the gap is representable. Dropping it instead — which
    is what `if any(v is not None ...)` did — deleted 4 January 2021, the one
    interior date where all four weekly columns are blank, from the row list and
    from the payload alike. Neither renderer could then know a week was missing,
    and both drew a straight line across it: the chart asserted a reading that
    the published series does not make. Only the ends are trimmed, where an
    all-blank row means the series has not started or has stopped rather than
    that a week went unrecorded.
    """
    raw = []
    with open(cfg.path('paths.cases'), newline='', encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            d = date.fromisoformat(r['date'])
            vals = {s['key']: num(r.get(s['key'])) for s in SERIES}
            raw.append((d, vals, any(v is not None for v in vals.values())))
    live = [i for i, (_, _, has) in enumerate(raw) if has]
    if not live:
        return []
    return [(d, vals) for d, vals, _ in raw[live[0]:live[-1] + 1]]


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
    levels = cfg.restriction_levels()
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

    # --- restriction bands, drawn first so everything sits above them.
    #
    # The background used to alternate light and dark by pandemic phase, which
    # encoded nothing a reader could recover: shading that means "an odd
    # numbered phase" is decoration wearing the clothes of data. It now carries
    # one ordinal quantity, the strictness of the restrictions legally in force,
    # on a monotonic neutral ramp: no fill at all when nothing was in force,
    # then three steps to the darkest for a stay-at-home order. Neutral because
    # a categorical hue here would impersonate a series, and grey is the only
    # family the four case slots do not already claim.
    #
    # The steps are recessive by design — the darkest sits 1.34:1 against the
    # chart surface — because the bands lie under the lines and marks that
    # carry the actual measurements, and a background that competes with them
    # is the worse error. Strictness therefore never rests on the shading
    # alone: a boundary rule at every change, a label along the top, and the
    # legend under the figure all repeat it.
    restrictions = cfg.restrictions()
    # A level the CSS has no step for draws with no fill, which is what level 0
    # means, so an ordinal scale would lose its top step and look like its
    # bottom one; a level the legend does not name cannot be read at all, and
    # reached the tooltip as a bare KeyError. Both are config errors and both
    # are caught here, named, before anything is written.
    used = sorted({int(p['level']) for p in restrictions})
    unnamed = [n for n in used if n not in levels]
    if unnamed:
        sys.exit(f'restriction level(s) {unnamed} have no [[restriction_levels]] '
                 f'entry in {cfg.source}: the legend and the tooltip cannot '
                 f'name them')
    unstyled = [n for n in used if n > MAX_BAND_LEVEL]
    if unstyled:
        sys.exit(f'restriction level(s) {unstyled} exceed the {MAX_BAND_LEVEL} '
                 f'shading steps the stylesheet defines: add .band-N and '
                 f'.legend.bands .swatch.lvl-N, and a validated step for each '
                 f'mode, before using them')
    band_top, band_bot = lanes_top - 6, cam_top + CAM_H + 6
    band_spans = []
    c.add('<g id="bands">')
    for i, p in enumerate(restrictions):
        start = date.fromisoformat(str(p['start']))
        nxt = (date.fromisoformat(str(restrictions[i + 1]['start']))
               if i + 1 < len(restrictions) else last + timedelta(days=1))
        if nxt < first or start > last:
            continue
        level = int(p['level'])
        x0, x1 = x_of(max(start, first)), x_of(min(nxt, last))
        if level:
            c.rect(x0, band_top, x1 - x0, band_bot - band_top,
                   f'band band-{level}')
        if first < start <= last:
            c.line(x0, band_top, x0, band_bot, 'band-edge')
        # The hit area spans the whole regime even when the label will not fit.
        # Autumn 2020 changes regime three times in eight weeks, and those are
        # the spans a reader most wants named; without this they are the only
        # ones that cannot be. The full name goes in a native <title>, which
        # needs no script and so survives the no-JavaScript path.
        label = str(p.get('label') or '')
        if label:
            # The regime's name, then the level it sits at — unless they are
            # the same sentence, as they are for the unshaded stretches, where
            # "No legal restrictions (No legal restrictions)" is just a stutter.
            title = esc(p['name'])
            if p['name'] != levels[level]:
                title += f' ({esc(levels[level])})'
            c.add(f'<g class="band-tag"><title>{title}</title>')
            c.rect(x0, band_top - 20, x1 - x0, 18, 'band-hit')
            if x1 - x0 > label_width(label) + LABEL_PAD:
                c.text(x0 + 5, band_top - 8, label, 'band-label')
            c.add('</g>')
        band_spans.append({'level': level, 'name': p['name'], 'label': label,
                           'start': max(start, first).isoformat(),
                           'end': min(nxt, last).isoformat()})
    c.add('</g>')

    # --- x axis, shared by every panel. Drawn once at the foot.
    axis_y = cam_top + CAM_H
    c.line(PAD_L, axis_y, W - PAD_R, axis_y, 'axis')
    c.add('<g id="xticks">')
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
    c.add('</g>')

    # --- event lanes
    by_track_day = {}
    for r in rows:
        by_track_day.setdefault(r['track'], {}).setdefault(r['date'], []).append(r)

    marks = []
    for li, (track, label) in enumerate(TRACKS):
        top = lanes_top + li * LANE_H
        mid = top + LANE_H / 2
        c.rect(PAD_L, top + 1, inner, LANE_H - 2, 'lane',
               f'data-lane="{track}"')
        c.line(PAD_L, mid, W - PAD_R, mid, 'lane-rule')
        c.text(PAD_L - 10, mid + 4, label, 'lane-label', 'text-anchor="end"')
        days = by_track_day.get(track, {})
        for iso, group in sorted(days.items()):
            d = date.fromisoformat(iso)
            cx = x_of(d)
            idx = len(marks)
            precision = day_precision(group)
            marks.append({
                'i': idx, 'track': track, 'date': iso,
                'when': fmt_date(d, precision),
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
            # data-cats and data-mid were written on every mark and lane and
            # read by nothing: the filters work off the payload. Dropped rather
            # than left to imply the DOM is the source of truth for either.
            extra = (f'data-i="{idx}" data-track="{track}" data-x="{cx:.1f}" '
                     f'tabindex="0" role="button" '
                     f'aria-label="{esc(fmt_date(d, precision))}, {len(group)} '
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
        # A missing reading breaks the line; it does not join the readings
        # either side of it. Filtering the Nones out instead drew a straight
        # segment across the week of 4 January 2021, where all four series are
        # blank, and only on the path that renders without JavaScript: the
        # script's layout() already broke there, so the two renderings of the
        # same data disagreed, and the one every reader sees first was the one
        # inventing a week of data.
        runs, run = [], []
        for d_, row in ucl_rows:
            v = row[s['key']]
            if v is None:
                if run:
                    runs.append(run)
                run = []
            else:
                run.append((x_of(d_), y_ucl(v)))
        if run:
            runs.append(run)
        if not runs:
            continue
        d = ' '.join('M' + ' L'.join(f'{x:.1f},{y:.1f}' for x, y in r)
                     for r in runs)
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
    c.add(f'<rect id="brush" class="brush" x="0" y="{lanes_top - 6}" '
          f'width="0" height="{(cam_top + CAM_H) - (lanes_top - 6):.1f}" '
          f'hidden="hidden"/>')
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
        'cats': sorted({r['category'] for r in rows if r['track'] != 'data'}),
        'bands': band_spans,
        'levels': {str(k): v for k, v in levels.items()},
        'labelWide': LABEL_WIDE, 'labelNarrow': LABEL_NARROW,
        'labelThin': LABEL_THIN, 'labelPad': LABEL_PAD,
        'axisY': axis_y, 'bandTop': band_top, 'bandBot': band_bot,
        'tickW': TICK_W,
        'peak': ({'date': peak_d.isoformat(), 'value': peak_v}
                 if peak_d else None),
        'lanes': {t: lanes_top + i * LANE_H + LANE_H / 2
                  for i, (t, _) in enumerate(TRACKS)},
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
  /* Ordinal shading for the restriction bands: one neutral ramp,
     light to dark, monotonic in lightness and deliberately
     recessive so the series stay legible over the darkest step. */
  --band-1:#f4f4f1; --band-2:#e9e9e4; --band-3:#dcdcd5;
  --band-edge:#dcdcd6; --camden:#8d8d84;
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) {
    color-scheme: dark;
    --ink:#e9e9e4; --muted:#a8a89f; --rule:#3a3a37; --link:#8fb6e8;
    --bg:#141413; --panel:#1f1f1d;
    --surface-1:#1a1a19; --text-primary:#ffffff; --text-secondary:#c3c2b7;
    --grid:#2e2e2b; --mark:#a8a89f; --mark-strong:#ffffff;
    --series-1:#3987e5; --series-2:#d95926; --series-3:#199e70; --series-4:#c98500;
    /* Dark is its own set of steps from the same neutral ramp, not a
       flip: the anchor moves to the dark surface and the ramp runs up. */
    --band-1:#232321; --band-2:#2e2e2b; --band-3:#3d3d38;
    --band-edge:#3d3d38; --camden:#8b8a81;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --ink:#e9e9e4; --muted:#a8a89f; --rule:#3a3a37; --link:#8fb6e8;
  --bg:#141413; --panel:#1f1f1d;
  --surface-1:#1a1a19; --text-primary:#ffffff; --text-secondary:#c3c2b7;
  --grid:#2e2e2b; --mark:#a8a89f; --mark-strong:#ffffff;
  --series-1:#3987e5; --series-2:#d95926; --series-3:#199e70; --series-4:#c98500;
  --band-1:#232321; --band-2:#2e2e2b; --band-3:#3d3d38;
  --band-edge:#3d3d38; --camden:#8b8a81;
}
.warning {
  background:#fdf6e3; border:2px solid #d9a441; border-left-width:8px;
  border-radius:5px; color:#4a3a12; padding:1rem 1.15rem; margin:1.5rem 0 0;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  font-size:.92rem; line-height:1.5;
}
.warning h2 { font-size:1.05rem; margin:0 0 .5rem; padding:0; border:0;
  color:#7a4f00; }
.warning p { margin:0 0 .6rem; max-width:none; }
.warning p:last-child { margin-bottom:0; }
.warning strong { color:#3d2f0a; }
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) .warning {
    background:#2a2412; border-color:#8a6a22; color:#e8dcc0; }
  :root:where(:not([data-theme="light"])) .warning h2 { color:#f0c674; }
  :root:where(:not([data-theme="light"])) .warning strong { color:#fff6df; }
}
:root[data-theme="dark"] .warning {
  background:#2a2412; border-color:#8a6a22; color:#e8dcc0; }
:root[data-theme="dark"] .warning h2 { color:#f0c674; }
:root[data-theme="dark"] .warning strong { color:#fff6df; }

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
/* A date input with no width collapses to a sliver in a flex row and shows
   nothing at all, which is what "the date selectors don't show a date"
   turned out to mean: the value was set, the field was too narrow to
   render it. */
.range input[type="date"] { font:inherit; padding:.15rem .35rem;
  min-height:24px; min-width:9.5rem; flex:none;
  background:var(--bg); color:var(--ink); border:1px solid var(--rule);
  border-radius:3px; }
#theme { font:inherit; font-size:.85rem; min-height:24px; padding:.15rem .3rem;
  background:var(--bg); color:var(--ink); border:1px solid var(--rule);
  border-radius:3px; }
button.reset { font:inherit; font-size:.85rem; padding:.2rem .6rem;
  min-height:24px; cursor:pointer; background:var(--bg); color:var(--ink);
  border:1px solid var(--rule); border-radius:3px; }

.figure { position:relative; margin:0; background:var(--surface-1);
  border:1px solid var(--rule); border-radius:6px; padding:.5rem 0 0;
  overflow-x:auto; }
/* pan-x pan-y keeps one finger doing what it already did — scrolling the
   figure sideways and the page down — while taking two-finger zoom away from
   the browser, which is the only way the script can be given the pinch. It is
   scoped to the chart: the prose around it still zooms with the system
   gesture, and nothing here touches the viewport meta. */
svg { display:block; width:100%; height:auto; min-width:56rem;
  touch-action:pan-x pan-y;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }

.band-1 { fill:var(--band-1); }
.band-2 { fill:var(--band-2); }
.band-3 { fill:var(--band-3); }
.band-edge { stroke:var(--band-edge); stroke-width:1; }
.band-label { fill:var(--text-secondary); font-size:10px; font-weight:600;
  pointer-events:none; }
.band-hit { fill:transparent; }
.band-tag { cursor:help; }
/* The shading is an ordinal ramp, so the legend swatches are the same three
   steps in the same order, sitting on the chart surface rather than on the
   page background: a swatch shown against a different backdrop from the band
   it stands for is not the colour the reader is being asked to match. */
.legend.bands { padding-top:0; }
.legend.bands .swatch { width:22px; height:12px; border-radius:2px;
  border:1px solid var(--band-edge); background:var(--surface-1); }
.legend.bands .swatch.lvl-1 { background:var(--band-1); }
.legend.bands .swatch.lvl-2 { background:var(--band-2); }
.legend.bands .swatch.lvl-3 { background:var(--band-3); }
/* The rule is drawn after the lane's hit rect and along the exact line the
   marks sit on, so it painted over the one target the lane handlers need: a
   fingertip aimed at a mark landed on the rule, the lane never saw the
   pointer, and the tap did nothing at all. A mouse got away with it because
   it arrives moving and the next pixel either side is lane again. Nothing
   drawn inside a lane is ever a pointer target. */
.lane-rule { stroke:var(--grid); stroke-width:1; pointer-events:none; }
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
.crosshair[hidden] { display:none; }
.brush { fill:var(--link); opacity:.14; stroke:var(--link); stroke-width:1;
  pointer-events:none; }
.brush.too-narrow { fill:var(--text-secondary); opacity:.07;
  stroke:var(--text-secondary); }
.brush[hidden] { display:none; }
svg.dragging { cursor:ew-resize; }
.plot-hit { fill:transparent; }

/* The page tells the reader how to drive it, and the answer differs by input:
   a mouse drags to zoom, a finger drags to pan a chart wider than the screen.
   Printing an instruction that does not work on the device reading it is worse
   than printing none, so both are rendered and the device picks. */
.touch-only { display:none; }
@media (hover: none) {
  .hover-only { display:none; }
  .touch-only { display:inline; }
}

/* Pinned to the left edge of the figure's scroll, not carried along by it.
   The svg holds a 56rem minimum width, so on a narrow screen the figure
   scrolls — and the legend, sitting inside that scroll, used to travel off to
   the left with it. Reaching late 2021 on a phone means scrolling most of the
   chart's width, which put the colour key out of view at exactly the point a
   reader needs it. Sticky keeps it where the reader is, and costs nothing on a
   wide screen where there is no scroll to stick against. */
.legend { display:flex; flex-wrap:wrap; gap:.4rem 1.25rem; margin:.6rem 0 0;
  padding:0 1rem .75rem;
  position:sticky; left:0; width:100%;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  font-size:.82rem; color:var(--text-secondary); }
.legend span { display:inline-flex; align-items:center; gap:.4rem; }
.legend .off { opacity:.35; }

#tip {
  /* 26rem is wider than a phone. The tooltip is positioned inside the figure,
     which scrolls on its own axis, so an overwide one would be clipped by the
     very container it sits in rather than simply hanging off the edge. */
  position:absolute; z-index:5; max-width:min(26rem, calc(100% - 1rem));
  pointer-events:none;
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

/* The build marker: present for anyone who goes looking, addressed to nobody
   who is not. Smaller and lighter than the body, hard against the foot. */
.build { margin:3rem 0 0; padding-top:.75rem; border-top:1px solid var(--rule);
  color:var(--muted); font-size:.78rem;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
.build code { font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
  font-size:.95em; }

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
  var trackOn = {}, trackLabel = {};
  D.tracks.forEach(function (t) { trackOn[t.key] = true;
                                  trackLabel[t.key] = t.label; });
  var catOn = {};
  D.cats.forEach(function (c) { catOn[c] = true; });

  var first = new Date(D.first + 'T00:00:00Z');
  function dayOf(iso) {
    return Math.round((new Date(iso + 'T00:00:00Z') - first) / 86400000);
  }
  function isoOf(day) {
    return new Date(first.getTime() + day * 86400000).toISOString().slice(0, 10);
  }
  // The visible domain, in days from the first event. Changing the date
  // inputs moves these, and everything positioned in time is laid out again
  // against them. Filtering marks without moving the axis was the bug: the
  // reader narrowed the range and the chart stayed the same width with gaps
  // in it, which is not what a date range is for.
  var dom = {a: 0, b: D.span};
  function xOf(iso) { return xOfDay(dayOf(iso)); }
  function xOfDay(day) {
    return D.padL + D.inner * ((day - dom.a) / (dom.b - dom.a));
  }
  function inDom(day) { return day >= dom.a && day <= dom.b; }
  var SVGNS = 'http://www.w3.org/2000/svg';
  function svgEl(tag, attrs) {
    var n = document.createElementNS(SVGNS, tag);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    return n;
  }
  var MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  // Mirrors label_width() in the renderer, so a band label appears at a zoomed
  // range exactly where the server would have put it at that width.
  function labelWidth(s) {
    var w = 0;
    for (var i = 0; i < s.length; i++) {
      var c = s[i];
      if (/[A-Z0-9]/.test(c)) w += D.labelWide;
      else if (/[a-z]/i.test(c)) w += D.labelNarrow;
      else w += D.labelThin;
    }
    return w;
  }

  // Every string below originates in scraped UCL email or a fetched PDF.
  // It reaches the DOM through textContent only. Nothing is concatenated
  // into markup anywhere in this file.
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null && text !== '') n.textContent = text;
    return n;
  }

  function inRange(iso) { return inDom(dayOf(iso)); }

  // Everything positioned in time, redrawn for the current domain.
  function layout() {
    // 1. series lines
    D.series.forEach(function (s, si) {
      var p = svg.querySelector('path[data-series="' + s.key + '"]');
      if (!p) return;
      var d = '', started = false;
      D.cases.forEach(function (row) {
        var day = dayOf(row[0]), v = row[si + 1];
        if (v === null || !inDom(day)) { started = false; return; }
        var x = xOfDay(day);
        var y = D.uclTop + D.uclH - (v / D.topVal) * D.uclH;
        d += (started ? ' L' : 'M') + x.toFixed(1) + ',' + y.toFixed(1);
        started = true;
      });
      p.setAttribute('d', d || 'M0,0');
    });
    // 2. Camden line and its wash
    var line = svg.querySelector('.camden-line');
    var wash = svg.querySelector('.camden-wash');
    if (line) {
      var pts = [];
      D.camden.forEach(function (row) {
        var day = dayOf(row[0]);
        if (!inDom(day)) return;
        pts.push([xOfDay(day),
          D.camTop + D.camH - (row[1] / D.camTop_val) * D.camH]);
      });
      var dd = pts.map(function (q, i) {
        return (i ? ' L' : 'M') + q[0].toFixed(1) + ',' + q[1].toFixed(1);
      }).join('');
      line.setAttribute('d', dd || 'M0,0');
      if (wash && pts.length) {
        var base = (D.camTop + D.camH).toFixed(1);
        wash.setAttribute('d', 'M' + pts[0][0].toFixed(1) + ',' + base +
          ' L' + dd.slice(1) + ' L' + pts[pts.length - 1][0].toFixed(1) +
          ',' + base + ' Z');
      } else if (wash) { wash.setAttribute('d', 'M0,0'); }
    }
    // 3. event marks
    Array.prototype.forEach.call(svg.querySelectorAll('.mark'), function (g) {
      var m = D.marks[+g.getAttribute('data-i')];
      var day = dayOf(m.date);
      var kept = keptEvents(m);
      var show = trackOn[m.track] && kept.length > 0 && inDom(day);
      var x = xOfDay(day);
      g.setAttribute('data-x', x.toFixed(1));
      var r = g.querySelector('rect');
      if (r) r.setAttribute('x', (x - D.tickW / 2).toFixed(1));
      // The heavier "several events here" tick and the count a screen reader
      // hears both count the kept events, so neither promises more than the
      // tooltip will list.
      if (r) r.classList.toggle('multi', kept.length > 1);
      if (show) {
        g.setAttribute('aria-label', m.when + ', ' + kept.length + ' event' +
          (kept.length === 1 ? '' : 's') + ' on the ' + trackLabel[m.track] +
          ' track');
        g.removeAttribute('hidden'); g.setAttribute('tabindex', '0');
      } else { g.setAttribute('hidden', 'hidden'); g.setAttribute('tabindex', '-1'); }
    });
    // 4. restriction bands. Same rules as the server-side draw: no fill at
    // level 0, a rule at every change, the short label only where it fits.
    var bands = document.getElementById('bands');
    if (bands) {
      bands.replaceChildren();
      D.bands.forEach(function (bd) {
        var a = Math.max(dayOf(bd.start), dom.a);
        var b = Math.min(dayOf(bd.end), dom.b);
        if (b <= a) return;
        var x0 = xOfDay(a), x1 = xOfDay(b);
        if (bd.level) bands.appendChild(svgEl('rect', {
          x: x0.toFixed(1), y: D.bandTop, width: (x1 - x0).toFixed(1),
          height: D.bandBot - D.bandTop, 'class': 'band band-' + bd.level}));
        if (dayOf(bd.start) > dom.a) bands.appendChild(svgEl('line', {
          x1: x0.toFixed(1), y1: D.bandTop, x2: x0.toFixed(1),
          y2: D.bandBot, 'class': 'band-edge'}));
        if (bd.label) {
          var g = svgEl('g', {'class': 'band-tag'});
          var ti = document.createElementNS(SVGNS, 'title');
          ti.textContent = bd.name === D.levels[bd.level] ? bd.name
            : bd.name + ' (' + D.levels[bd.level] + ')';
          g.appendChild(ti);
          g.appendChild(svgEl('rect', {x: x0.toFixed(1), y: D.bandTop - 20,
            width: (x1 - x0).toFixed(1), height: 18, 'class': 'band-hit'}));
          if (x1 - x0 > labelWidth(bd.label) + D.labelPad) {
            var tx = svgEl('text', {x: (x0 + 5).toFixed(1), y: D.bandTop - 8,
              'class': 'band-label'});
            tx.textContent = bd.label;
            g.appendChild(tx);
          }
          bands.appendChild(g);
        }
      });
    }
    // 5. x-axis ticks, at a spacing that suits the visible span
    var xt = document.getElementById('xticks');
    if (xt) {
      xt.replaceChildren();
      var days = dom.b - dom.a;
      var step = days > 540 ? 3 : days > 150 ? 1 : 0;   // months, 0 = weekly
      var marksAt = [];
      if (step === 0) {
        for (var dd2 = Math.ceil(dom.a / 7) * 7; dd2 <= dom.b; dd2 += 7)
          marksAt.push(dd2);
      } else {
        var s0 = new Date(first.getTime() + dom.a * 86400000);
        var yy = s0.getUTCFullYear(), mm = s0.getUTCMonth();
        for (var i = 0; i < 200; i++) {
          var dt = Date.UTC(yy, mm, 1);
          var day = Math.round((dt - first.getTime()) / 86400000);
          if (day > dom.b) break;
          if (day >= dom.a && mm % step === 0) marksAt.push(day);
          mm += 1; if (mm > 11) { mm = 0; yy += 1; }
        }
      }
      var lastYear = null;
      marksAt.forEach(function (day, i) {
        var x = xOfDay(day);
        xt.appendChild(svgEl('line', {x1: x.toFixed(1), y1: D.axisY,
          x2: x.toFixed(1), y2: D.axisY + 4, 'class': 'axis'}));
        var dt = new Date(first.getTime() + day * 86400000);
        var lab = MON[dt.getUTCMonth()];
        if (step === 0) lab = dt.getUTCDate() + ' ' + lab;
        // The year appears on the first tick and whenever it changes, not on
        // every January tick: at weekly spacing that repeated "Jan 2022" four
        // times in a row.
        if (i === 0 || dt.getUTCFullYear() !== lastYear) {
          lab += ' ' + dt.getUTCFullYear();
          lastYear = dt.getUTCFullYear();
        }
        var tx = svgEl('text', {x: x.toFixed(1), y: D.axisY + 16,
          'class': 'tick', 'text-anchor': 'middle'});
        tx.textContent = lab;
        xt.appendChild(tx);
      });
    }
    // 6. the one direct label
    var call = svg.querySelector('.callout');
    if (call && D.peak) {
      var pday = dayOf(D.peak.date);
      var show = visible['student7.on'] && inDom(pday);
      if (show) {
        var px = xOfDay(pday);
        var py = D.uclTop + D.uclH - (D.peak.value / D.topVal) * D.uclH;
        var ln = call.querySelector('line'), tx2 = call.querySelector('text');
        if (ln) { ln.setAttribute('x1', (px - 6).toFixed(1));
                  ln.setAttribute('x2', (px - 16).toFixed(1));
                  ln.setAttribute('y1', py.toFixed(1));
                  ln.setAttribute('y2', py.toFixed(1)); }
        if (tx2) { tx2.setAttribute('x', (px - 21).toFixed(1));
                   tx2.setAttribute('y', (py + 4).toFixed(1)); }
        call.removeAttribute('hidden');
      } else { call.setAttribute('hidden', 'hidden'); }
    }
  }

  function applyFilters() {
    D.series.forEach(function (s) {
      var p = svg.querySelector('path[data-series="' + s.key + '"]');
      if (p) { if (visible[s.key]) p.removeAttribute('hidden');
               else p.setAttribute('hidden', 'hidden'); }
    });
    Array.prototype.forEach.call(
      document.querySelectorAll('.legend span[data-key]'), function (s) {
        s.classList.toggle('off', !visible[s.getAttribute('data-key')]);
      });
    layout();
  }

  function place(x, y) {
    var box = fig.getBoundingClientRect();
    tip.hidden = false;
    var w = tip.offsetWidth, h = tip.offsetHeight;
    // #tip is absolutely positioned inside .figure, which scrolls on its own
    // axis, so its offsets are measured from the unscrolled content origin
    // while x and y arrive from the viewport. Without adding scrollLeft the
    // tooltip lands short by however far the figure is scrolled -- on a phone,
    // where the chart holds a 56rem minimum width and the reader has scrolled
    // to late 2021 to reach a mark, that is most of a screen to the left of
    // the tick that was tapped. Exactly the case the tap path was added for.
    var sx = fig.scrollLeft, sy = fig.scrollTop;
    var left = x - box.left + sx + 14, top = y - box.top + sy - h - 10;
    // The right edge to stay inside is the visible one, which is also
    // scrolled: box.width is the viewport of the figure, not its content.
    if (left + w > sx + box.width - 6) left = x - box.left + sx - w - 14;
    if (left < sx + 6) left = sx + 6;
    if (top < sy + 6) top = y - box.top + sy + 18;
    tip.style.left = left + 'px';
    tip.style.top = top + 'px';
  }

  // A day survives the category filter if any one of its events does, so a
  // mark mixing kept and filtered categories stays on the lane. What it stands
  // for is then the kept events only: listing the filtered ones as well would
  // let a deselected category go on speaking through a tick it no longer owns.
  // The predicate matches the one layout() hides marks by, so a visible mark
  // always has at least one event left to show.
  function keptEvents(m) {
    return m.events.filter(function (e) { return catOn[e.category]; });
  }

  function showMark(g, cx, cy) {
    var m = D.marks[+g.getAttribute('data-i')];
    tip.replaceChildren();
    tip.appendChild(el('div', 'when', m.when));
    keptEvents(m).forEach(function (e) {
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
  // The closest visible mark on a lane to an x in SVG space, or null if the
  // pointer is not near one. A fingertip is a blunter instrument than a mouse,
  // so touch gets a wider reach than the 14 units a pointer is held to. The
  // units are the viewBox's: 1,180 across a chart that is never drawn narrower
  // than 56rem, so 30 of them is about 23 CSS pixels on a phone -- half a
  // fingertip, and still far short of a lane.
  var TOUCH_REACH = 30;
  function nearestMark(track, x, reach) {
    var best = null, bestD = Infinity;
    Array.prototype.forEach.call(
      svg.querySelectorAll('.mark[data-track="' + track + '"]'),
      function (g) {
        if (g.hasAttribute('hidden')) return;
        var dx = Math.abs(parseFloat(g.getAttribute('data-x')) - x);
        if (dx < bestD) { bestD = dx; best = g; }
      });
    return bestD > reach ? null : best;
  }

  function revealMark(g) {
    if (!g) { light(null); hide(); return; }
    light(g);
    var r = g.getBoundingClientRect();
    showMark(g, r.left + r.width / 2, r.top);
  }

  Array.prototype.forEach.call(svg.querySelectorAll('.lane'), function (lane) {
    var track = lane.getAttribute('data-lane');
    lane.addEventListener('pointermove', function (ev) {
      if (dragFrom !== null || ev.pointerType === 'touch') return;
      revealMark(nearestMark(track, toSvg(ev).x, 14));
    });
    // Touch has no hover, and the tooltip is the only place the page says what
    // an event actually was, so without a tap path every mark on a phone is a
    // tick that cannot be read. A tap is also unambiguous here: one finger
    // scrolls and two zoom, so nothing else wants a stationary press.
    lane.addEventListener('pointerup', function (ev) {
      if (ev.pointerType === 'mouse' || afterPinch) return;
      revealMark(nearestMark(track, toSvg(ev).x, TOUCH_REACH));
    });
    // Mouse only. A pointer that cannot hover is destroyed when it is lifted,
    // and the spec has the browser fire pointerout and pointerleave straight
    // after the pointerup that ended it -- so this ran on every tap, one event
    // after the handler above, and took the tooltip back down before a frame
    // had been painted with it. Touch puts it away by tapping off the chart,
    // which the document handler below does.
    lane.addEventListener('pointerleave', function (ev) {
      if (ev.pointerType !== 'mouse') return;
      light(null); hide();
    });
  });

  // Tapping away from the chart puts the tooltip back down again, since touch
  // never fires the pointerleave that does it for a mouse.
  document.addEventListener('pointerup', function (ev) {
    if (ev.pointerType === 'mouse') return;
    if (ev.target && ev.target.closest &&
        ev.target.closest('.lane, .plot-hit')) return;
    light(null); hide();
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

  // SVG elements have no `hidden` IDL property, so el.hidden = false only adds
  // a JS expando and leaves the attribute — and the display:none — in place.
  // The attribute has to be added and removed by hand.
  function setHidden(el, on) {
    if (on) el.setAttribute('hidden', 'hidden');
    else el.removeAttribute('hidden');
  }

  function hide() { tip.hidden = true; setHidden(cross, true); }

  // --- drag to zoom, x only ------------------------------------------------
  //
  // The y scales deliberately do not move. Zooming both axes lets a narrow
  // window rescale its own peak to full height, which makes any rise look
  // equally steep whatever its size; holding the case axes still means a
  // zoomed view says the same thing about magnitude as the full one.
  var brush = document.getElementById('brush');
  var dragFrom = null, dragging = false;
  var DRAG_MIN = 8;             // px, below this it was a click not a drag
  // Days. A window narrower than a week has nothing in it and divides badly,
  // and every way of setting the range -- drag, pinch, the date boxes -- has
  // to refuse the same one, or the floor moves with the input used.
  var MIN_SPAN = 7;

  function clampX(x) { return Math.max(D.padL, Math.min(D.padL + D.inner, x)); }
  function dayAtX(x) {
    return dom.a + ((clampX(x) - D.padL) / D.inner) * (dom.b - dom.a);
  }

  svg.addEventListener('pointerdown', function (ev) {
    if (ev.button !== 0) return;
    // Touch does not get drag-to-zoom, because sideways already means
    // something there: the chart holds a 56rem minimum width, so on a phone it
    // is two and a half screens wide and dragging is how a reader reaches
    // October 2021 at all. The browser owns that gesture and should. Zoom on
    // touch is the date boxes, which are native pickers on a phone and better
    // at the job than a fingertip on a two-year axis.
    if (ev.pointerType === 'touch') return;
    var loc = toSvg(ev);
    if (loc.x < D.padL || loc.x > D.padL + D.inner) return;
    if (loc.y < D.bandTop || loc.y > D.axisY) return;
    dragFrom = loc.x; dragging = false;
    svg.setPointerCapture(ev.pointerId);
  });

  svg.addEventListener('pointermove', function (ev) {
    if (dragFrom === null) return;
    var x = clampX(toSvg(ev).x);
    if (!dragging && Math.abs(x - dragFrom) < DRAG_MIN) return;
    dragging = true;
    svg.classList.add('dragging');
    hide();
    brush.setAttribute('x', Math.min(dragFrom, x).toFixed(1));
    brush.setAttribute('width', Math.abs(x - dragFrom).toFixed(1));
    // A selection endDrag will refuse is drawn faintly, so the highlight says
    // what will actually happen rather than promising a zoom that never comes.
    var d1 = dayAtX(Math.min(dragFrom, x)), d2 = dayAtX(Math.max(dragFrom, x));
    brush.classList.toggle('too-narrow', d2 - d1 < MIN_SPAN);
    setHidden(brush, false);
  });

  // Put the brush away and give up the pointer. Returns where the drag began,
  // or null if there was no drag worth committing.
  function clearDrag(ev) {
    var was = dragging, a0 = dragFrom;
    dragFrom = null; dragging = false;
    setHidden(brush, true);
    brush.classList.remove('too-narrow');
    svg.classList.remove('dragging');
    try { svg.releasePointerCapture(ev.pointerId); } catch (e) {}
    return was ? a0 : null;
  }

  function endDrag(ev) {
    if (dragFrom === null) return;
    var x = clampX(toSvg(ev).x);
    var a0 = clearDrag(ev);
    if (a0 === null) return;
    var d1 = dayAtX(Math.min(a0, x)), d2 = dayAtX(Math.max(a0, x));
    if (d2 - d1 < MIN_SPAN) return;
    dom.a = Math.max(0, Math.round(d1));
    dom.b = Math.min(D.span, Math.round(d2));
    syncDateInputs();
    layout();
  }

  // A cancelled pointer is the gesture being taken away -- a scroll winning
  // the arbitration, the window losing focus -- and not a release, so it must
  // not commit a zoom. It used to, which meant every sideways scroll of the
  // chart on a phone ended by jumping the view to whatever range the finger
  // had happened to cross on its way.
  function abortDrag(ev) {
    if (dragFrom === null) return;
    clearDrag(ev);
  }

  svg.addEventListener('pointerup', endDrag);
  svg.addEventListener('pointercancel', abortDrag);

  // Double-click anywhere on the plot zooms back out to the whole record.
  svg.addEventListener('dblclick', function () {
    dom.a = 0; dom.b = D.span;
    syncDateInputs();
    hide();
    layout();
  });

  // --- pinch to zoom the time axis, touch only -----------------------------
  //
  // Sideways drag is spoken for on a phone: the chart holds a 56rem minimum
  // width, so it is more than two screens across and one finger is how a
  // reader reaches October 2021 at all. That left touch with no way to narrow
  // the axis, only the date boxes, and a reader who wanted a closer look at a
  // fortnight had to type it. Two fingers is the gesture they already have,
  // and the touch-action declared on the svg is what makes it available: the
  // browser's own pinch is declined over the chart and nowhere else.
  //
  // The domain scales about the point between the fingers, so the day being
  // held stays under them and the zoom happens around it rather than around
  // the middle of a chart that is mostly off-screen. Scale is measured from
  // the domain as it stood when the second finger landed, not from the last
  // frame, so a slow pinch and a quick one across the same distance finish on
  // the same range and rounding cannot accumulate through the gesture.
  var touchX = {};        // live touch pointers on the chart, id -> clientX
  var pinch = null;       // the gesture, captured when the second finger lands
  var afterPinch = false; // the releases two fingers leave behind are not taps
  var pinchFrame = 0;

  function touchCount() { return Object.keys(touchX).length; }
  function pinchGap() {
    var ids = Object.keys(touchX);
    return Math.abs(touchX[ids[0]] - touchX[ids[1]]);
  }
  function pinchMid() {
    var ids = Object.keys(touchX);
    return (touchX[ids[0]] + touchX[ids[1]]) / 2;
  }
  // A client x in the SVG user space the domain is laid out in. toSvg wants a
  // whole event; a pinch has two, and what it needs is the point between them.
  function svgXOf(clientX) {
    var pt = svg.createSVGPoint();
    pt.x = clientX; pt.y = 0;
    return pt.matrixTransform(svg.getScreenCTM().inverse()).x;
  }

  function startPinch() {
    var gap = pinchGap();
    if (gap < 1) return;    // two fingers on one spot scale by nothing
    var frac = (clampX(svgXOf(pinchMid())) - D.padL) / D.inner;
    pinch = {gap: gap, frac: frac, a: dom.a, b: dom.b,
             day: dom.a + frac * (dom.b - dom.a)};
    afterPinch = true;
    hide();
  }

  function applyPinch() {
    if (!pinch || touchCount() < 2) return;
    var gap = pinchGap();
    if (gap < 1) return;
    // Fingers spread is zoom in, which is a shorter domain. The floor is the
    // week the drag refuses below; the ceiling is the whole record, so a pinch
    // the other way always gets back to where the page opened.
    var width = (pinch.b - pinch.a) * pinch.gap / gap;
    width = Math.max(MIN_SPAN, Math.min(D.span, width));
    var a = pinch.day - pinch.frac * width;
    if (a < 0) a = 0;
    if (a + width > D.span) a = D.span - width;
    var a2 = Math.round(a), b2 = Math.round(a + width);
    if (a2 === dom.a && b2 === dom.b) return;
    dom.a = a2; dom.b = b2;
    syncDateInputs();
    layout();
  }

  // One relayout per frame at most. A pinch delivers moves faster than the
  // chart can be drawn, and each one moves every mark and rebuilds every path.
  function schedulePinch() {
    if (pinchFrame) return;
    pinchFrame = requestAnimationFrame(function () {
      pinchFrame = 0;
      applyPinch();
    });
  }

  svg.addEventListener('pointerdown', function (ev) {
    if (ev.pointerType === 'mouse') return;
    // A gesture starting from no fingers down is allowed to be a tap again.
    if (!touchCount()) afterPinch = false;
    touchX[ev.pointerId] = ev.clientX;
    if (touchCount() === 2) {
      startPinch();
      // Capture both: the gesture stays ours if a finger wanders off the
      // chart, and neither release can arrive at a lane looking like a tap.
      Object.keys(touchX).forEach(function (id) {
        try { svg.setPointerCapture(+id); } catch (e) {}
      });
    }
  });

  svg.addEventListener('pointermove', function (ev) {
    if (!(ev.pointerId in touchX)) return;
    touchX[ev.pointerId] = ev.clientX;
    if (pinch) schedulePinch();
  });

  // A lifted or cancelled finger leaves the gesture. One finger cannot pinch,
  // so the next pair starts a new one from the range this one finished at.
  function endTouch(ev) {
    if (!(ev.pointerId in touchX)) return;
    delete touchX[ev.pointerId];
    try { svg.releasePointerCapture(ev.pointerId); } catch (e) {}
    if (touchCount() < 2) pinch = null;
  }
  svg.addEventListener('pointerup', endTouch);
  svg.addEventListener('pointercancel', endTouch);

  // Crosshair on the case panels: snaps to the nearest reading, so the pointer
  // never has to land on a line.
  var plot = document.getElementById('plot-hit');
  function showReading(ev) {
    if (dragFrom !== null) return;
    var loc = toSvg(ev);
    var frac = (loc.x - D.padL) / D.inner;
    var day = dom.a + frac * (dom.b - dom.a);
    var best = null, bestD = Infinity;
    D.cases.forEach(function (row) {
      var dd = Math.abs(dayOf(row[0]) - day);
      if (dd < bestD) { bestD = dd; best = row; }
    });
    if (!best || !inRange(best[0])) { hide(); return; }
    var cx = xOf(best[0]);
    cross.setAttribute('x1', cx); cross.setAttribute('x2', cx);
    setHidden(cross, false);

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
  }
  plot.addEventListener('pointermove', function (ev) {
    // A touch pointermove over the case panels is a pan in progress, not a
    // reading. Acting on it paints a crosshair the finger is already dragging
    // away from, and then leaves it standing, because touch fires no
    // pointerleave to take it back down.
    if (ev.pointerType === 'touch') return;
    showReading(ev);
  });
  plot.addEventListener('pointerup', function (ev) {
    if (ev.pointerType === 'mouse' || afterPinch) return;
    showReading(ev);
  });
  // Mouse only, for the reason given on the lanes: a touch pointerup is
  // followed immediately by the pointerleave that destroys the pointer, and
  // hiding on that is hiding what the tap just asked for.
  plot.addEventListener('pointerleave', function (ev) {
    if (ev.pointerType !== 'mouse') return;
    hide();
  });

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
  document.querySelectorAll('input[data-cat]').forEach(function (box) {
    box.addEventListener('change', function () {
      catOn[box.getAttribute('data-cat')] = box.checked;
      syncAllCats();
      layout();
    });
  });
  var allCats = document.getElementById('allcats');
  function syncAllCats() {
    var boxes = document.querySelectorAll('input[data-cat]');
    var on = 0;
    boxes.forEach(function (b) { if (b.checked) on++; });
    allCats.checked = on === boxes.length;
    allCats.indeterminate = on > 0 && on < boxes.length;
  }
  allCats.addEventListener('change', function () {
    document.querySelectorAll('input[data-cat]').forEach(function (b) {
      b.checked = allCats.checked;
      catOn[b.getAttribute('data-cat')] = allCats.checked;
    });
    allCats.indeterminate = false;
    layout();
  });

  var f = document.getElementById('from'), t = document.getElementById('to');
  function syncDateInputs() {
    f.value = isoOf(dom.a); t.value = isoOf(dom.b);
  }
  function onRange() {
    var a = f.value ? dayOf(f.value) : 0;
    var b = t.value ? dayOf(t.value) : D.span;
    // Clamp the interval into the domain first, then check its width. Clamping
    // each end independently let a pair outside the range invert dom: the
    // min/max attributes on a date input only mark it invalid, the browser
    // still sets .value and fires change, so 2019-01-01 to 2019-06-01 gave
    // a = -433, b = -282, passed the width check on their difference, and came
    // out of the two clamps as {a: 0, b: -282}. Every mark then hid, every path
    // collapsed to M0,0, and the chart went blank with no way back but Reset.
    a = Math.min(Math.max(a, 0), D.span);
    b = Math.min(Math.max(b, 0), D.span);
    // A domain needs width. Refuse to inflame the axis rather than dividing
    // by zero, and put the inputs back to what is actually being shown.
    if (b - a < MIN_SPAN) {
      f.value = isoOf(dom.a); t.value = isoOf(dom.b); return;
    }
    dom.a = a; dom.b = b;
    hide();
    layout();
  }
  f.addEventListener('change', onRange);
  t.addEventListener('change', onRange);

  // Theme. The CSS already declares the dark values under both the media
  // query and a [data-theme] scope, with the media block guarded so an
  // explicit light stamp beats an OS set to dark; until now nothing ever set
  // the attribute, so the page could only follow the system.
  var themeSel = document.getElementById('theme');
  function applyTheme(v) {
    if (v === 'auto') document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme', v);
    try { localStorage.setItem('uclcovid-theme', v); } catch (e) {}
  }
  var savedTheme = 'auto';
  try { savedTheme = localStorage.getItem('uclcovid-theme') || 'auto'; } catch (e) {}
  themeSel.value = savedTheme;
  applyTheme(savedTheme);
  themeSel.addEventListener('change', function () { applyTheme(themeSel.value); });

  document.getElementById('reset').addEventListener('click', function () {
    f.value = D.first; t.value = isoOf(D.span);
    dom.a = 0; dom.b = D.span;
    document.querySelectorAll('input[data-track]').forEach(function (b) {
      b.checked = true; trackOn[b.getAttribute('data-track')] = true;
    });
    document.querySelectorAll('input[data-cat]').forEach(function (b) {
      b.checked = true; catOn[b.getAttribute('data-cat')] = true;
    });
    allCats.checked = true; allCats.indeterminate = false;
    document.querySelectorAll('input[data-series]').forEach(function (b) {
      var k = b.getAttribute('data-series');
      var def = D.series.filter(function (s) { return s.key === k; })[0].on;
      b.checked = def; visible[k] = def;
    });
    hide();
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
    a('<meta name="description" content="AI-generated demonstration, not a '
      'verified record: UCL\'s COVID-19 decisions against national policy '
      'and its own case data, 2020 to 2022.">')
    a(f'<style>{CSS}</style>')
    a('</head>')
    a('<body>')
    a('<main class="content">')
    # Before the title, not after it: a caveat below the fold is not a caveat.
    a('<aside class="warning" role="note" aria-label="Important caveat">')
    a('<h2>⚠️ AI-generated demonstration, not a verified historical record</h2>')
    a('<p><strong>Every part of this page was produced by an AI system '
      'working from the preserved newsletters and the published case data. '
      'No human has checked it.</strong></p>')
    a('<p>Some things here are checked mechanically and some are not, and the '
      'difference matters more than a general disclaimer would suggest. Every '
      'quotation is verified as an exact substring of the document it cites, '
      'so the words in the tooltips really do appear in the sources. '
      '<strong>Everything around them is unverified</strong>: whether the '
      'right events were selected, whether each has been read correctly, '
      'whether the dates and categories are right, whether the commentary is '
      'sound, and whether anything important is missing. The lag figures rest '
      'on pairings an AI system judged to be causal, and those judgements '
      'have not been reviewed.</p>')
    a('<p>Treat this as a <strong>demonstration of what the underlying '
      'dataset makes possible</strong>, not as a chronology of UCL\'s '
      'pandemic response to rely on, quote or cite. Anyone wanting to use a '
      'fact from here should open the newsletter it cites and read it in '
      'context first.</p>')
    a('</aside>')
    a('<h1>UCL and the pandemic</h1>')
    a(f'<p class="lede">{len(rows)} dated events between {fmt_date(first)} '
      f'and {fmt_date(last)}: {ucl} decisions UCL took, {nat} national and '
      f'sector measures they respond to, and {dat} readings from the case '
      'series UCL published. Every event carries a verbatim quotation from '
      'the document that announced it, checked mechanically against the '
      'preserved source.</p>')
    a('<p class="muted"><span class="hover-only">Hover or focus any mark for '
      'the events on that day.</span><span class="touch-only">Tap any mark for '
      'the events on that day.</span> '
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
    # The date inputs open showing the full span rather than an empty
    # dd/mm/yyyy, so the reader can see what range they are narrowing from.
    a('<fieldset><legend>Dates</legend><span class="range">'
      f'<label for="from">from</label><input type="date" id="from" '
      f'value="{first.isoformat()}" '
      f'min="{first.isoformat()}" max="{last.isoformat()}">'
      f'<label for="to">to</label><input type="date" id="to" '
      f'value="{last.isoformat()}" '
      f'min="{first.isoformat()}" max="{last.isoformat()}">'
      '</span></fieldset>')
    a('<fieldset><legend>Categories</legend>'
      '<label><input type="checkbox" id="allcats" checked> '
      '<em>all</em></label>')
    for cat in payload['cats']:
        a(f'<label><input type="checkbox" data-cat="{esc(cat)}" checked> '
          f'{esc(cat)}</label>')
    a('</fieldset>')
    a('<fieldset><legend>Theme</legend>'
      '<select id="theme"><option value="auto">match system</option>'
      '<option value="light">light</option>'
      '<option value="dark">dark</option></select></fieldset>')
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
    # The shading is a second encoding and gets a legend of its own, in level
    # order so that the ramp is read as a scale rather than four states.
    levels = cfg.restriction_levels()
    a('<div class="legend bands">')
    a('<span class="muted">Background:</span>')
    for lvl in sorted(levels):
        a(f'<span><span class="swatch lvl-{lvl}"></span>'
          f'{esc(levels[lvl])}</span>')
    a('</div>')
    a('<div id="tip" hidden></div>')
    a('</figure>')

    a('<h2>Reading this chart</h2>')
    a('<p>The four lanes are the four tracks of the ledger, separated by '
      'position rather than colour so that the categorical palette is free '
      'for the case series. One mark is one day in one lane: several '
      'decisions often landed on a single day, and a mark for each would '
      'overplot into a smear implying a density the record does not support. '
      'The tooltip lists what happened on that day in the categories currently '
      'selected, so a mark never speaks for a category you have filtered '
      'out.</p>')
    a('<p><span class="hover-only"><strong>Drag sideways across the chart to '
      'zoom into a date range.</strong> Only the time axis moves; the case '
      'scales stay put, so a zoomed view cannot make a rise look steeper than '
      'it is. Double-click to zoom back out, or use the date boxes, which take '
      'the range you drag and can be typed into directly.</span>'
      '<span class="touch-only"><strong>The chart is wider than this screen: '
      'drag sideways to move through the period, and pinch with two fingers '
      'to zoom the time axis.</strong> Pinching apart narrows the range around '
      'the point between your fingers, pinching together widens it back to the '
      'whole record; the date boxes above take the same range and can be typed '
      'into directly. Zooming moves only the time axis; the case scales stay '
      'put, so a zoomed view cannot make a rise look steeper than it '
      'is.</span></p>')
    a('<p>The background shading is how strict the legal restrictions were, '
      'on one scale from no shading at all when nothing was in force to the '
      'darkest step for a stay-at-home order. It is drawn in neutral greys '
      'because the bands are regions rather than series, and a categorical '
      'hue there would impersonate one. The regime is named along the top and '
      'in full on hovering that label; a vertical rule marks every change. '
      'The shading follows what applied in England, and in London wherever '
      'England was tiered.</p>')
    # The page marks what is checked and what is not everywhere else, and the
    # shading is the one part of the figure that is neither quoted from a
    # newsletter nor computed from the case series. Generated from the config
    # so it cannot go stale: verify a date there and this sentence follows.
    regimes = cfg.restrictions()
    unchecked = [r for r in regimes if not r.get('checked')]
    if unchecked:
        when = ', '.join(fmt_date(date.fromisoformat(str(r['start'])))
                         for r in unchecked)
        a(f'<p class="muted">{spell(len(regimes) - len(unchecked)).title()} of '
          f'the {spell(len(regimes))} shaded regimes begin on a date taken '
          f'from a cited row of the ledger or from the research synthesis. '
          f'{spell(len(unchecked)).title()} do not — {esc(when)} — and come '
          f'from the general '
          f'England chronology with no source in this archive behind them. '
          f'They are marked as unchecked in the configuration and want '
          f'verifying against the regulations.</p>')
    a('<p>The dates are the days measures came into force rather than the days '
      'they were announced, so the shading changes a few days to the right of '
      'the announcement on the National lane. That gap is the point: the '
      'chronology gives the lag in days wherever a UCL action responds to a '
      'national one. A stay-at-home order is a legal test and not a measure of '
      'how closed the university was — the second national lockdown is shaded '
      'as darkly as the first while UCL stayed open, which is exactly the '
      'divergence the UCL lane is there to show.</p>')
    a('<p>The full chronology, with every quotation and the lag in days '
      'wherever a UCL action responds to a national one, is in '
      '<a href="TIMELINE.md">TIMELINE.md</a>. The ledger behind both is '
      '<a href="timeline.csv">timeline.csv</a>.</p>')

    # Which build this is, quietly, at the foot, and where to go and read it.
    # The hash is linked to its own commit rather than left for the reader to
    # paste: an <a> fetches nothing, so the page still reaches for no external
    # host on load, which is the property the archive actually claims. Both
    # links degrade to plain text when there is no remote to point at.
    commit, dirty = build_commit(cfg)
    repo, repo_label = build_repo(cfg)
    if commit:
        shown = (f'<a href="{esc(repo)}/commit/{esc(commit)}">'
                 f'<code>{esc(commit)}</code></a>' if repo
                 else f'<code>{esc(commit)}</code>')
        line = f'Built from {shown}'
        if dirty:
            line += ' with uncommitted changes'
        if repo:
            line += (f' · <a href="{esc(repo)}">'
                     f'{esc(repo_label or repo)}</a>')
        a(f'<p class="build">{line}</p>')
    elif repo:
        a(f'<p class="build"><a href="{esc(repo)}">'
          f'{esc(repo_label or repo)}</a></p>')
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
