#!/usr/bin/env python3
"""Stage 1 reading aid: drop standing boilerplate, keep first appearances.

Roughly two fifths of the newsletter corpus is text that repeats across issues —
the Care First counselling paragraph, the askUCL sign-off, "keep checking
ucl.ac.uk/coronavirus", the contents list that restates the section headings, the
daily page-visit counts. None of it is a decision, and the plan's inclusion test
already excludes it: recurring wellbeing content and unchanged repetitions of
standing guidance do not earn ledger rows.

The rule implements the other half of that test exactly. A paragraph's FIRST
appearance is always kept, because the start date of a recurring thread is a fact
about the institution's response; later repetitions are dropped. So "Remote, Not
Distant launches" survives in the issue that launched it and disappears from the
thirty issues that went on mentioning it.

Matching ignores digits, so the visit-count and date variants of an otherwise
identical paragraph collapse together.

**This changes nothing about verification.** The digest is a reading aid only.
`validate.py` checks every quotation against the FULL extracted text in `text/`,
so a quote taken from a dropped paragraph still validates, and a quote that
drifts still fails.

Usage:
    python3 digest.py [--config timeline.toml] [--min-repeats 2]
"""
import csv
import re
import sys
from pathlib import Path

import config

# Lines that are pure email furniture, dropped wherever they appear.
CHROME = {
    'view in browser', 'unsub', 'unsubscribe', 'dear colleagues,',
    'best wishes,', 'questions?', 'coronavirus mitigation group',
    'ucl communications', 'coronavirus information hub',
}


def fingerprint(p):
    """Identity for repetition purposes: digits and punctuation ignored, so
    'there were 9,542 visits' and 'there were 5,368 visits' are one paragraph."""
    s = re.sub(r'\d+', '#', p.lower())
    s = re.sub(r'[^a-z# ]', ' ', s)
    return ' '.join(s.split())[:160]


def main():
    def opts(ap):
        ap.add_argument('--min-repeats', type=int, default=2,
                        help='keep the first N appearances of a paragraph '
                             '(default 2: first appearance only... see below)')
    cfg, args = config.load(extra_args=opts)

    textdir = cfg.path('paths.text')
    outdir = textdir.parent / 'digest'
    outdir.mkdir(parents=True, exist_ok=True)

    index = textdir / 'index.csv'
    with open(index, newline='', encoding='utf-8') as fh:
        rows = list(csv.DictReader(fh))

    seen = {}
    kept_chars = total_chars = 0
    report = []

    # Chronological, so "first appearance" means first in time, not first by
    # filename. They coincide here, but the intent is the chronological one.
    for r in sorted(rows, key=lambda r: (r['body_date'], r['basename'])):
        src = textdir / r['basename'].replace('.html', '.txt')
        paras = [re.sub(r'[ \t]+', ' ', p).strip()
                 for p in src.read_text(encoding='utf-8').split('\n\n')]
        paras = [p for p in paras if p]

        out, dropped = [], 0
        for p in paras:
            total_chars += len(p)
            flat = ' '.join(p.split())
            if flat.lower() in CHROME:
                dropped += len(p)
                continue
            f = fingerprint(p)
            seen[f] = seen.get(f, 0) + 1
            if seen[f] < args.min_repeats:
                out.append(p)
                kept_chars += len(p)
            else:
                dropped += len(p)

        header = (f"# {r['body_date']} | issue {r['issue'] or '-'} | "
                  f"{r['basename']}")
        (outdir / src.name).write_text(
            header + '\n\n' + '\n\n'.join(out) + '\n', encoding='utf-8')
        report.append((r['basename'], len(''.join(paras)), dropped))

    print(f'newsletters:  {len(rows)}')
    print(f'characters:   {total_chars:,} -> {kept_chars:,} '
          f'({kept_chars / total_chars:.0%} kept)')
    print(f'digest:       {outdir}')
    print('\nverification is unaffected: validate.py checks quotes against '
          f'{textdir}, not the digest.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
