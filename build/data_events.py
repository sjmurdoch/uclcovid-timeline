#!/usr/bin/env python3
"""Stage 3: derive the `data` track from the published case series.

Generated, never hand-written, so that the timeline and the blog post cannot
silently disagree about a number. Every row carries `verified=computed` and a
`source_ref` naming the column and date range it came from.

Emits rows for:
  * the start and end of the series;
  * the record weekly maximum for each of the four series;
  * each month where a group's total moves by more than the configured
    threshold from the previous month (both a fractional and an absolute gate,
    so a jump from 2 to 6 does not register as a surge);
  * the January 2021 against January 2022 comparison, which is the blog post's
    central claim.

Thresholds and paths come from timeline.toml. Standard library only: the
archive's own pipeline needs pandas, this does not.

Usage:
    python3 data_events.py [--config timeline.toml] [--out batches/data.json]
"""
import csv
import json
import sys
from datetime import date

import config

# The four published series. `.on` marks recent presence on campus, not the
# site of infection — carried into notes on every row that uses it.
SERIES = {
    'studenttotal.on':  ('student7.on',  'students, on campus'),
    'studenttotal.off': ('student7.off', 'students, off campus'),
    'stafftotal.on':    ('staff7.on',    'staff, on campus'),
    'stafftotal.off':   ('staff7.off',   'staff, off campus'),
}

PRESENCE = ('"On campus" records a visit of 15 minutes or more in the two days '
            'before symptoms or a test, not where infection occurred.')
REPORTED = ('Reported confirmed cases only, an undercount of unknown size. '
            'Testing intensity changed during the series: asymptomatic testing '
            'was ruled out in September 2020, opened to students in November '
            '2020 and to staff in January 2021, and from 8 February 2021 a '
            'positive lateral flow test entered the count without PCR '
            'confirmation.')
TUESDAY = ('Figures were published each weekday morning correct to 5pm the '
           'previous day, with weekend figures folded into Tuesday, so a '
           'Tuesday reading covers Saturday to Monday.')
OUTAGE = ('The collection had a 50-hour outage from 2021-08-21 08:34 to '
          '2021-08-23 10:34 caused by the git corruption incident.')

OUTAGE_START, OUTAGE_END = date(2021, 8, 21), date(2021, 8, 23)


def load(path):
    with open(path, newline='', encoding='utf-8') as fh:
        rows = []
        for r in csv.DictReader(fh):
            r['_d'] = date.fromisoformat(r['date'])
            rows.append(r)
    return sorted(rows, key=lambda r: r['_d'])


def num(row, col):
    v = (row.get(col) or '').strip()
    return None if v == '' else float(v)


def last_of_month(rows, col):
    """Cumulative total at the last reading of each month that has one."""
    out = {}
    for r in rows:
        v = num(r, col)
        if v is not None:
            out[(r['_d'].year, r['_d'].month)] = (r['_d'], v)
    return out


def month_name(y, m):
    return date(y, m, 1).strftime('%B %Y')


def row(d, headline, detail, ref, notes, kind='observed', precision='day',
        category='epidemiology'):
    return {
        'date': d.isoformat(), 'date_kind': kind, 'date_precision': precision,
        'track': 'data', 'category': category, 'headline': headline,
        'detail': detail, 'quote': '', 'source_type': 'dataset',
        'source_ref': ref, 'issue': '', 'verified': 'computed', 'notes': notes,
    }


def main():
    def opts(ap):
        ap.add_argument('--out', default='batches/data.json')
    cfg, args = config.load(extra_args=opts)

    cases = cfg.path('paths.cases')
    rows = load(cases)
    name = cases.name
    frac = float(cfg.get('data_track.month_change_fraction', 0.5))
    absolute = float(cfg.get('data_track.month_change_absolute', 25))

    out = []
    first, last = rows[0], rows[-1]

    out.append(row(first['_d'], 'UCL begins publishing daily confirmed case counts',
                   f'First row of the published series. {len(rows)} readings follow, '
                   f'to {last["date"]}.',
                   f'{name} first row',
                   'The case page was announced in issue 110 of 9 September 2020 and '
                   'described in issue 119 of 12 October 2020, but the first published '
                   f'figure is dated {first["date"]}. ' + TUESDAY,
                   kind='published'))
    out.append(row(last['_d'], 'The published case series ends',
                   'Last row of the series. The scraper continued to 2022-07-29 against '
                   'a page that had stopped changing.',
                   f'{name} last row',
                   'The record ends because the counting stopped, not because the '
                   'pandemic did: issue 165 of 4 May 2022 withdrew the advice to test '
                   'twice weekly as free national testing ended.',
                   kind='published'))

    # record weekly maxima
    for cum, (weekly, label) in SERIES.items():
        best = max(((num(r, weekly), r) for r in rows if num(r, weekly) is not None),
                   key=lambda t: t[0])
        v, r = best
        out.append(row(
            r['_d'], f'Weekly cases peak at {int(v)} for {label}',
            f'The highest seven-day total for this series anywhere in the record.',
            f'{name} {weekly} maximum',
            f'{REPORTED} {PRESENCE if ".on" in weekly else ""} {TUESDAY}'.strip(),
        ))

    # monthly totals and month-on-month moves
    for cum, (weekly, label) in SERIES.items():
        months = last_of_month(rows, cum)
        keys = sorted(months)
        prev_total = None
        prev_key = None
        for k in keys:
            d, total = months[k]
            if prev_total is None:
                prev_total, prev_key = total, k
                continue
            gained = total - prev_total
            prev_gained = None
            if prev_key is not None:
                i = keys.index(prev_key)
                if i > 0:
                    _, before = months[keys[i - 1]]
                    prev_gained = prev_total - before
            if prev_gained is not None and prev_gained > 0:
                change = (gained - prev_gained) / prev_gained
                if abs(change) >= frac and abs(gained - prev_gained) >= absolute:
                    direction = 'rises' if change > 0 else 'falls'
                    out.append(row(
                        date(k[0], k[1], 1),
                        f'Monthly cases {direction} to {int(gained)} for {label}',
                        f'{int(prev_gained)} in {month_name(*prev_key)}, '
                        f'{int(gained)} in {month_name(*k)}, a change of '
                        f'{change * 100:+.0f}%.',
                        f'{name} {cum} monthly difference',
                        f'Threshold: at least {frac:.0%} and at least {int(absolute)} '
                        f'cases, both from timeline.toml. {REPORTED} '
                        f'{PRESENCE if ".on" in cum else ""}'.strip(),
                        precision='month'))
            prev_total, prev_key = total, k

    # the January 2021 against January 2022 comparison
    months = last_of_month(rows, 'studenttotal.on')
    if (2021, 1) in months and (2022, 1) in months:
        def gained(y, m):
            keys = sorted(months)
            i = keys.index((y, m))
            return months[(y, m)][1] - months[keys[i - 1]][1]
        a, b = gained(2021, 1), gained(2022, 1)
        out.append(row(
            date(2022, 1, 1),
            f'On-campus student cases: {int(a)} in January 2021, {int(b)} in January 2022',
            'The same calendar month under opposite campus policies. In January 2021 '
            'all teaching was online and students were told not to return; in January '
            '2022 campus was open for face-to-face teaching under the higher education '
            'exemption from Plan B.',
            f'{name} studenttotal.on January 2021 and January 2022',
            'The blog post\'s central claim, computed rather than asserted. It shows '
            'that the on-campus line moved with policy, not that policy caused the '
            'difference: national prevalence also differed between the two months, and '
            f'{REPORTED.lower()} {PRESENCE}',
            precision='month'))

    # outage note as its own row, since any claim spanning it needs the caveat
    out.append(row(OUTAGE_START, 'Collection outage of 50 hours',
                   'The hourly scraper stopped for 50 hours, so any page updates in '
                   'that window were not captured.',
                   f'{name} 2021-08-21 to 2021-08-23',
                   OUTAGE + ' Any data-track claim spanning this window carries this '
                   'caveat. The published figures are cumulative, so totals recover; '
                   'daily readings within the window do not.'))

    out.sort(key=lambda r: (r['date'], r['headline']))
    with open(args.out, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f'{len(rows)} readings, {first["date"]} to {last["date"]}')
    print(f'{len(out)} data rows written to {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
