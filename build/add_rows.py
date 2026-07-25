#!/usr/bin/env python3
"""Append a batch of ledger rows, given as JSON, to timeline.csv.

Stage 1 proceeds in batches and each batch must land intact, so rows are handed
over as JSON and written with the csv module rather than assembled as text. The
quote field routinely contains commas, curly quotes and em rules; hand-built CSV
would corrupt it and the corruption would look like a fabricated quotation to
the validator.

The ledger is kept sorted by date, then track, then headline, so appending a
batch out of chronological order is harmless and re-running is idempotent.

Usage:
    python3 add_rows.py batch.json [--replace-source-refs]
"""
import csv
import json
import sys
from pathlib import Path

import config
from validate import FIELDS


def main():
    def opts(ap):
        ap.add_argument('batch', help='JSON file holding a list of row objects')
        ap.add_argument('--replace-source-refs', action='store_true',
                        help='drop existing rows citing any source_ref in this '
                             'batch before appending, so a batch can be redone')
    cfg, args = config.load(extra_args=opts)

    ledger = cfg.path('paths.ledger')
    incoming = json.loads(Path(args.batch).read_text(encoding='utf-8'))
    if not isinstance(incoming, list):
        sys.exit('batch must be a JSON list of row objects')

    for i, row in enumerate(incoming):
        unknown = set(row) - set(FIELDS)
        if unknown:
            sys.exit(f'batch item {i}: unknown fields {sorted(unknown)}')

    existing = []
    if ledger.exists():
        with open(ledger, newline='', encoding='utf-8') as fh:
            existing = list(csv.DictReader(fh))

    if args.replace_source_refs:
        refs = {r.get('source_ref') for r in incoming}
        before = len(existing)
        existing = [r for r in existing if r.get('source_ref') not in refs]
        print(f'dropped {before - len(existing)} existing rows for '
              f'{len(refs)} source refs')

    rows = existing + [{f: str(row.get(f, '') or '') for f in FIELDS}
                       for row in incoming]
    rows.sort(key=lambda r: (r['date'], r['track'], r['headline']))

    ledger.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    print(f'appended {len(incoming)} rows; ledger now {len(rows)} rows '
          f'at {ledger}')


if __name__ == '__main__':
    sys.exit(main())
