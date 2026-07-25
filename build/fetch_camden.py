#!/usr/bin/env python3
"""Fetch the Camden case comparator once and cache it. See TIMELINE-PLAN.md 2b.

This is the only external dependency in the project. The archive's established
value is that everything regenerates from committed sources, so this script runs
once, writes a CSV with the retrieval date and exact query URL in a header
comment, and stops. No renderer and no published page may fetch at run time.

**The API accepts `date_from` and `date_to` and silently ignores them** — the
record count comes back unchanged and results start from 2020-01-30 regardless.
Slice with `page_size` and `page`, and verify the window actually received
rather than the one requested. This script therefore pages through everything
and filters locally.

Standard library only. Usage:
    python3 fetch_camden.py [--force]
"""
import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone

import config

TIMEOUT = 60


def build_url(cfg, page, page_size):
    parts = [
        'themes', cfg['camden.theme'],
        'sub_themes', cfg['camden.sub_theme'],
        'topics', cfg['camden.topic'],
        'geography_types', cfg['camden.geography_type'],
        'geographies', cfg['camden.geography'],
        'metrics', cfg['camden.metric'],
    ]
    path = '/'.join(urllib.parse.quote(p, safe='') for p in parts)
    q = urllib.parse.urlencode({'page': page, 'page_size': page_size})
    return f"{cfg['camden.base']}/{path}?{q}"


def get(url, attempts=4):
    """One page, with retries. Long responses have been seen to truncate
    mid-body, so read the whole thing and parse it separately rather than
    streaming into the JSON decoder — a partial read then fails loudly here
    instead of silently yielding a short page."""
    last = None
    for i in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as fh:
                raw = fh.read()
            return json.loads(raw.decode('utf-8'))
        except Exception as exc:                     # noqa: BLE001 — report and retry
            last = exc
            print(f'    attempt {i}/{attempts} failed: {exc.__class__.__name__}: {exc}',
                  file=sys.stderr)
            time.sleep(2 * i)
    raise SystemExit(f'giving up on {url}: {last}')


def main():
    def opts(ap):
        ap.add_argument('--force', action='store_true',
                        help='refetch even though a cache exists')
    cfg, args = config.load(extra_args=opts)

    out = cfg.path('camden.cache')
    if out.exists() and not args.force:
        print(f'cache already present at {out} — not refetching.\n'
              'This file is fetched once by design; pass --force to override.')
        return 0

    page_size = int(cfg['camden.page_size'])
    rows, page, count = [], 1, None
    while True:
        url = build_url(cfg, page, page_size)
        payload = get(url)
        if count is None:
            count = payload.get('count')
            print(f'records reported by the API: {count}')
        got = payload.get('results') or []
        rows.extend(got)
        print(f'  page {page}: {len(got)} records (total so far {len(rows)})')
        if not payload.get('next') or not got:
            break
        page += 1

    if not rows:
        sys.exit('no records returned')

    rows.sort(key=lambda r: r['date'])
    if count is not None and len(rows) != count:
        print(f'WARNING: fetched {len(rows)} but the API reported {count}',
              file=sys.stderr)

    first, last = rows[0]['date'], rows[-1]['date']
    print(f'window actually received: {first} to {last}')

    out.parent.mkdir(parents=True, exist_ok=True)
    fetched = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    with open(out, 'w', newline='', encoding='utf-8') as fh:
        fh.write(f'# Camden daily confirmed COVID-19 cases, UKHSA dashboard API.\n')
        fh.write(f'# retrieved: {fetched}\n')
        fh.write(f'# query: {build_url(cfg, 1, page_size)}\n')
        fh.write(f'# metric: {cfg["camden.metric"]}\n')
        fh.write(f'# records: {len(rows)}, {first} to {last}\n')
        fh.write('# Fetched once and cached. Nothing may fetch this at run time.\n')
        w = csv.writer(fh)
        w.writerow(['date', 'metric_value'])
        for r in rows:
            w.writerow([r['date'], r['metric_value']])

    print(f'wrote {len(rows)} rows to {out}')

    # The October 2020 check the plan asked for: the bulk archive documents a
    # gap there for Lower Tier Local Authority data, which would fall exactly on
    # the student-return surge. Verify the live endpoint does not share it.
    oct20 = [r for r in rows if r['date'].startswith('2020-10')]
    print(f'October 2020: {len(oct20)} of 31 days present')
    return 0


if __name__ == '__main__':
    sys.exit(main())
