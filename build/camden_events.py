#!/usr/bin/env python3
"""Camden comparator rows for the data track. Reads the cache, never the API.

The comparison is of shape and timing only. UCL's cases are **not** a subset of
Camden's: students live across many boroughs and "on campus" marks presence
rather than residence, so a person counted at UCL may be counted in Barnet or
nowhere. Shares and proportions are unsupported by both datasets and this script
does not compute any.

Usage:
    python3 camden_events.py [--out batches/camden.json]
"""
import csv
import json
import sys
from datetime import date

import config

CAVEAT = ('UCL cases are not a subset of Camden cases: students live across many '
          'boroughs and "on campus" marks presence, not residence. Shape and '
          'timing may be compared; shares and proportions may not.')


def read_camden(path):
    out = {}
    with open(path, encoding='utf-8') as fh:
        lines = [ln for ln in fh if not ln.startswith('#')]
    for r in csv.DictReader(lines):
        out[date.fromisoformat(r['date'])] = float(r['metric_value'])
    return out


def read_ucl(path):
    rows = []
    with open(path, newline='', encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            r['_d'] = date.fromisoformat(r['date'])
            rows.append(r)
    return sorted(rows, key=lambda r: r['_d'])


def month_total(camden, y, m):
    return sum(v for d, v in camden.items() if d.year == y and d.month == m)


def ucl_month_gain(rows, col, y, m):
    """Cumulative column differenced across the month, matching data_events."""
    months = {}
    for r in rows:
        v = (r.get(col) or '').strip()
        if v:
            months[(r['_d'].year, r['_d'].month)] = float(v)
    keys = sorted(months)
    if (y, m) not in keys:
        return None
    i = keys.index((y, m))
    if i == 0:
        # The first month of the series has no predecessor to difference
        # against. October 2020 is that month and it is partial: the series
        # opens on the 9th with a cumulative total already at 72, so the
        # month's true figure is unknowable. Return None rather than a number
        # that looks whole.
        return None
    return months[(y, m)] - months[keys[i - 1]]


def row(d, headline, detail, ref, notes):
    return {'date': d.isoformat(), 'date_kind': 'observed',
            'date_precision': 'month', 'track': 'data',
            'category': 'epidemiology', 'headline': headline, 'detail': detail,
            'quote': '', 'source_type': 'dataset', 'source_ref': ref,
            'issue': '', 'verified': 'computed', 'notes': notes}


def main():
    def opts(ap):
        ap.add_argument('--out', default='batches/camden.json')
    cfg, args = config.load(extra_args=opts)

    cache = cfg.path('camden.cache')
    if not cache.exists():
        sys.exit(f'no Camden cache at {cache} — run build/fetch_camden.py first')
    camden = read_camden(cache)
    ucl = read_ucl(cfg.path('paths.cases'))
    ref = 'timeline/data/camden-cases.csv (UKHSA dashboard, cached)'

    out = []

    # The blog post's central claim, tested against the borough rather than the
    # country. This is the comparison the plan asks for first.
    for label, col in (('on-campus students', 'studenttotal.on'),):
        a = ucl_month_gain(ucl, col, 2021, 1)
        b = ucl_month_gain(ucl, col, 2022, 1)
        ca, cb = month_total(camden, 2021, 1), month_total(camden, 2022, 1)
        if a is None or b is None:
            continue
        # A zero baseline is guarded as carefully as a missing one. `a is None`
        # was checked and `a == 0` was not, so a January with no on-campus cases
        # — not far-fetched in a month the campus was shut — would have divided
        # by zero and taken the whole batch build down with a traceback. There
        # is no fold to state against a base of nothing, so the row is skipped
        # rather than fabricated.
        if not ca or not a:
            print(f'    skipped: {label} January 2021 base is '
                  f'{int(a)} UCL / {int(ca)} Camden, so no fold can be stated',
                  file=sys.stderr)
            continue
        cf, uf = cb / ca, b / a
        out.append(row(
            date(2022, 1, 1),
            f'UCL rises {uf:.0f}-fold between the two Januaries, Camden {cf:.1f}-fold',
            f'Camden recorded {int(ca):,} cases in January 2021 and {int(cb):,} in '
            f'January 2022, a factor of {cf:.1f}. UCL {label} went from {int(a)} to '
            f'{int(b)}, a factor of {uf:.0f} — about {uf / cf:.0f} times the '
            'borough\'s growth.',
            ref,
            'The sharpest test of the blog post\'s claim available, and it does not '
            'say what a first glance suggests. **Both** rose: the borough\'s epidemic '
            f'grew {cf:.1f}-fold between the two months, so a purely epidemiological '
            'account does predict a rise at UCL. What it does not predict is the '
            f'size: UCL rose about {uf / cf:.0f} times as steeply as the borough '
            'around it. That gap is the evidence, not a difference in direction. The '
            'plain reading is that the local epidemic accounts for part of the '
            'change and campus policy for the rest — closed to most students in '
            f'January 2021, open in January 2022. {CAVEAT}'))

    # There was a second block here, emitting an autumn 2020 row headlined
    # "Camden and UCL both peak in {month}" as the co-movement against which the
    # January divergence is read. It was withdrawn: the headline was a bare
    # template, nothing computed or checked a peak, and the month it emitted was
    # a peak for neither series. Camden's November 2020 total is 1,243, below
    # October's 1,313 and far below its 15,901 in December 2021; UCL's on-campus
    # student gain was 43 against 696 in January 2022. The ledger's own
    # December 2021 row said as much two hundred rows later.
    #
    # It is not repaired here because the data cannot carry the claim it was
    # written to make. ucl_month_gain returns None for October 2020, correctly:
    # the series opens on the 9th with a cumulative 371 already banked, so the
    # month is unknowable and there is no autumn co-movement to compute from
    # monthly gains. A version built on the published weekly columns would be a
    # different measurement and would have to be checked before it shipped.
    #
    # The January comparison above never depended on it.

    out.sort(key=lambda r: r['date'])
    # Resolved against timeline/, not the caller's cwd, so this writes to
    # the same place whichever directory it is run from -- as
    # make_national_batch.py already did, and as cfg.path() does for every
    # path that comes from the config.
    out_path = config.ROOT / args.out
    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f'{len(camden):,} Camden daily records, '
          f'{min(camden):%Y-%m-%d} to {max(camden):%Y-%m-%d}')
    for r in out:
        print(f'  {r["date"]}  {r["headline"]}')
        print(f'      {r["detail"]}')
    print(f'{len(out)} rows written to {out_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
