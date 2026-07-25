#!/usr/bin/env python3
"""Stage 0: extract readable text from the 168 preserved UCL newsletters.

The output is the substrate for everything downstream. Stage 4's anti-fabrication
check re-derives this same text and requires every quotation in the ledger to be
an exact substring of it, so extraction must be a pure function of the input:
same file in, same bytes out, every run.

Writes:
    timeline/text/<basename>.txt   one per newsletter
    timeline/text/index.csv        basename, body date, filename date, issue,
                                   agreement flag, character count

The date is taken from the document body rather than the filename. Filenames
omit the year before 2021, so the body is the better source; the filename date
is kept as a cross-check and disagreements are reported.

Standard library only. Usage:
    python3 extract_text.py [--config timeline.toml] [--set KEY=VALUE]
"""
import csv
import html
import re
import sys
from datetime import date
from pathlib import Path

import config

# Tags whose content is markup or styling, never prose.
DROP_CONTENT = re.compile(
    r'<(script|style|head|title)\b[^>]*>.*?</\1\s*>', re.I | re.S)
# Word/Outlook conditional comments wrap whole alternative layouts.
COMMENT = re.compile(r'<!--.*?-->', re.S)
# Tags after which a line break is the honest reading of the layout.
BLOCK = re.compile(
    r'</?(p|div|br|tr|td|th|table|h[1-6]|li|ul|ol|blockquote|section|'
    r'article|header|footer|hr)\b[^>]*>', re.I)
TAG = re.compile(r'<[^>]+>', re.S)

# Present in all 168 files, immediately above the newsletter's own dateline.
ANCHOR = 'View in browser'

MONTHS = ('January February March April May June July August September '
          'October November December').split()
MONTH_NUM = {m: i for i, m in enumerate(MONTHS, start=1)}

# "9 March 2020", "13 March", "1st October 2021" — the newsletters use all three.
BODY_DATE = re.compile(
    r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(' + '|'.join(MONTHS) + r')\b'
    r'(?:\s+(20\d{2}))?', re.I)
# Anchored to the three-digit index prefix, so it matches the dated update names
# ("119_12_October__Issue_119_") and not the three special editions, whose
# filenames are titles. "…restrictions_from_5_November_2020" names the day the
# restrictions began, not the day the message was sent; an unanchored pattern
# reads it as a dateline and is wrong by four days.
FILE_DATE = re.compile(
    r'^\d{3}_(\d{1,2})_(' + '|'.join(MONTHS) + r')(?:_(20\d{2}))?_', re.I)
FILE_ISSUE = re.compile(r'_Issue_(\d+)_')

# Body-versus-filename disagreements checked by hand and settled. The filename
# comes from the title on UCL's own index page, so a disagreement means one of
# the two is wrong and the reason has to be established rather than assumed.
REVIEWED = {
    '123_3_November__Issue_122_.html': (
        '2020-11-02',
        'The body says "Monday 2 November 2020" twice; 2 November 2020 was a '
        'Monday and the weekly cadence either side runs 19 and 26 October and '
        '9 November, all Mondays. UCL\'s index page titles this "3 November", '
        'which is the error. The body date is used.'),
}


def to_text(raw):
    """HTML to plain text. Deterministic: no parser heuristics, no dict order."""
    s = DROP_CONTENT.sub(' ', raw)
    s = COMMENT.sub(' ', s)
    s = BLOCK.sub('\n', s)
    s = TAG.sub(' ', s)
    s = html.unescape(s)
    s = s.replace('​', '').replace('﻿', '')
    s = s.replace('\xa0', ' ')
    # Normalise whitespace: spaces collapse within a line, blank lines collapse
    # to one. The quote checker applies the same rule, so a quotation spanning a
    # table cell boundary still matches.
    s = '\n'.join(re.sub(r'[ \t\r\f\v]+', ' ', ln).strip() for ln in s.split('\n'))
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip() + '\n'


def normalise(s):
    """The comparison form: all whitespace runs become one space. Used by the
    validator so a quote copied across a line break still matches."""
    return re.sub(r'\s+', ' ', s).strip()


def body_date(text, window, fallback_year, anchored=True):
    """The newsletter's own date, read from the opening of the document.

    The date is taken from after the "View in browser" link, not from the first
    date anywhere in the file. The line above that link is the email's subject
    or preheader, and it is not reliable: issue 75 carries "Friday 26 June 2020"
    over a newsletter sent on Monday 29 June, and both parts of the 5 November
    special edition carry the date the restrictions began rather than the date
    they were written. The line below the link is the newsletter's own dateline
    and is correct in all 168 files.

    Where the year is absent the newsletter is from 2020 (filenames carry the
    year from 2021 onward), so the surrounding year fills in. Returns
    (date, matched_text) or (None, None).
    """
    if anchored:
        i = text.find(ANCHOR)
        if i >= 0:
            text = text[i + len(ANCHOR):]
    head = text[:window]
    for m in BODY_DATE.finditer(head):
        day, month, year = int(m.group(1)), m.group(2).capitalize(), m.group(3)
        y = int(year) if year else fallback_year
        try:
            return date(y, MONTH_NUM[month], day), m.group(0)
        except ValueError:
            continue          # e.g. "31 April" in prose; keep looking
    return None, None


def filename_date(name):
    m = FILE_DATE.match(name)
    if not m:
        return None, None
    day, month, year = int(m.group(1)), m.group(2).capitalize(), m.group(3)
    if not year:
        return None, (day, MONTH_NUM[month])      # year unknown, day/month known
    try:
        return date(int(year), MONTH_NUM[month], day), (day, MONTH_NUM[month])
    except ValueError:
        return None, (day, MONTH_NUM[month])


def main():
    cfg, _ = config.load()
    updates = cfg.path('paths.updates')
    outdir = cfg.path('paths.text')
    outdir.mkdir(parents=True, exist_ok=True)
    window = int(cfg['extract.date_window'])

    files = sorted(p for p in updates.glob('*.html'))
    if not files:
        sys.exit(f'no newsletters under {updates}')

    rows, problems, reviewed = [], [], []
    # Issues run in file order, so the year advances monotonically; the first
    # file is 9 March 2020 and the last 4 May 2022.
    year_guess = 2020
    for path in files:
        text = to_text(path.read_text(encoding='utf-8', errors='replace'))
        (outdir / (path.stem + '.txt')).write_text(text, encoding='utf-8')

        fdate, fdm = filename_date(path.name)
        if fdate:
            year_guess = fdate.year
        bdate, matched = body_date(text, window, year_guess)
        if bdate:
            year_guess = bdate.year

        issue = FILE_ISSUE.search(path.name)
        issue = issue.group(1) if issue else ''

        if fdate:
            agree = 'yes' if bdate == fdate else 'no'
        elif fdm and bdate:
            # Filename gives day and month only; compare on those.
            agree = 'yes' if (bdate.day, bdate.month) == fdm else 'no'
        else:
            agree = 'n/a'

        settled = REVIEWED.get(path.name)
        if settled and bdate and bdate.isoformat() == settled[0]:
            agree = 'reviewed'
            reviewed.append((path.name, settled[1]))
        elif agree == 'no' or bdate is None:
            problems.append((path.name, bdate, fdate or fdm, matched))

        rows.append({
            'basename': path.name,
            'body_date': bdate.isoformat() if bdate else '',
            'body_date_text': matched or '',
            'filename_date': fdate.isoformat() if fdate else '',
            'issue': issue,
            'agree': agree,
            'chars': len(text),
        })

    index = outdir / 'index.csv'
    with open(index, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    print(f'newsletters read:      {len(rows)}')
    print(f'text files written:    {len(list(outdir.glob("*.txt")))}')
    print(f'total characters:      {sum(r["chars"] for r in rows):,}')
    print(f'body date found:       {sum(1 for r in rows if r["body_date"])}')
    print(f'filename carries year: {sum(1 for r in rows if r["filename_date"])}')
    print(f'agreement:             '
          f'{sum(1 for r in rows if r["agree"] == "yes")} yes, '
          f'{sum(1 for r in rows if r["agree"] == "no")} no, '
          f'{sum(1 for r in rows if r["agree"] == "reviewed")} reviewed, '
          f'{sum(1 for r in rows if r["agree"] == "n/a")} n/a')
    print(f'index:                 {index}')
    for name, why in reviewed:
        print(f'\nreviewed disagreement: {name}\n  {why}')
    if problems:
        print('\nneeds a human decision:')
        for name, b, f, matched in problems:
            print(f'  {name}\n    body={b} ({matched!r}) filename={f}')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
