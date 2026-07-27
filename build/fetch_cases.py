#!/usr/bin/env python3
"""Fetch the published case series from the archive, and refuse it if it moved.

`render_html.py` plots `covid_raw.csv`, which lives in the archive repository
rather than this one. A local build reads it from a sibling checkout; the Pages
workflow has no such checkout and fetches it from raw.githubusercontent.com
instead. This is that fetch.

**The hash check is the point of this script, not an extra.** The `data` rows in
the ledger were computed from a particular state of that series by
`data_events.py`, and the chart is drawn from whatever this fetches. If the two
diverge, the page's chart and its own data rows quietly stop describing the same
numbers — the chart moves and the commentary beneath it does not. Fetching from a
branch tip means that divergence is one upstream commit away and would otherwise
be invisible, so the expected SHA-256 is recorded in `timeline.toml` and a
mismatch fails the build.

When it does fail, the fix is not to update the hash. It is to re-run
`data_events.py` against the new series, revalidate, and commit the ledger the
chart will now agree with; the hash then moves as part of that change.

Standard library only. Usage:
    python3 fetch_cases.py --out PATH [--allow-drift]
"""
import hashlib
import sys
import time
import urllib.request

import config

TIMEOUT = 60


def get(url, attempts=4):
    """The whole body, then verify. Read separately from parse for the reason
    fetch_camden.py gives: a truncated response must fail loudly here rather
    than yield a short file that looks like a shorter epidemic."""
    last = None
    for i in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as fh:
                if fh.status != 200:
                    raise OSError(f'HTTP {fh.status}')
                return fh.read()
        except Exception as exc:            # noqa: BLE001 — report and retry
            last = exc
            print(f'  attempt {i}/{attempts} failed: '
                  f'{exc.__class__.__name__}: {exc}', file=sys.stderr)
            time.sleep(2 * i)
    raise SystemExit(f'giving up on {url}: {last}')


def main():
    def opts(ap):
        ap.add_argument('--out', required=True,
                        help='where to write the series; keep it outside the '
                             'working tree so the build marker stays clean')
        ap.add_argument('--allow-drift', action='store_true',
                        help='write the file even if the hash moved, and say '
                             'so; for inspecting a change, not for deploying')
    cfg, args = config.load(extra_args=opts)

    url = str(cfg['cases.url'])
    expect = str(cfg.get('cases.sha256', '') or '').strip()

    print(f'fetching {url}')
    raw = get(url)
    got = hashlib.sha256(raw).hexdigest()

    # A CSV that comes back as an HTML error page is still 200 bytes of
    # something. Check the shape before the hash, so the message says which
    # thing went wrong.
    head = raw[:200].decode('utf-8', 'replace').splitlines()[0] if raw else ''
    if not head.startswith('date,'):
        sys.exit(f'not the case series: first line is {head[:80]!r}')

    lines = raw.decode('utf-8').splitlines()
    print(f'bytes:    {len(raw)}')
    print(f'rows:     {len(lines) - 1}')
    print(f'range:    {lines[1].split(",")[0]} to {lines[-1].split(",")[0]}')
    print(f'sha256:   {got}')

    if not expect:
        print('\nno cases.sha256 recorded, so nothing was checked. Record this '
              f'hash in timeline.toml:\n  sha256 = "{got}"', file=sys.stderr)
    elif got != expect:
        msg = (f'\nthe series has moved since the ledger was built from it\n'
               f'  fetched:  {got}\n  expected: {expect}\n\n'
               'The `data` rows in the ledger were computed from the expected\n'
               'state. Re-run build/data_events.py against the new series,\n'
               'validate, and commit the ledger before moving cases.sha256 —\n'
               'do not move the hash on its own.')
        if not args.allow_drift:
            sys.exit(msg)
        print(msg + '\n\nwriting anyway: --allow-drift', file=sys.stderr)
    else:
        print('sha256 matches timeline.toml: the chart and the ledger '
              'describe the same series.')

    with open(args.out, 'wb') as fh:
        fh.write(raw)
    print(f'wrote:    {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
