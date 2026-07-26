#!/usr/bin/env python3
"""Stage 4: validate the ledger. Run after every change; non-zero exit on failure.

The load-bearing check is number 3. Every `ucl` row carries a verbatim quotation,
and that quotation must be an exact substring of the text extracted from the file
named in `source_ref`. Paraphrase, drift and invention all fail it mechanically.
That is the difference between a timeline a reader can check and one they have to
take on trust, and it is why stage 0's extraction has to be deterministic.

Standard library only. Usage:
    python3 validate.py [--config timeline.toml] [--set KEY=VALUE] [--quiet]
"""
import csv
import hashlib
import re
import sys
from datetime import date
from pathlib import Path

import config
from extract_text import normalise

FIELDS = ['date', 'date_kind', 'date_precision', 'track', 'category',
          'headline', 'detail', 'quote', 'source_type', 'source_ref',
          'issue', 'verified', 'notes']

REQUIRED = ['date', 'date_kind', 'date_precision', 'track', 'category',
            'headline', 'source_type', 'source_ref', 'verified']

ENUMS = {
    'date_kind': {'announced', 'effective', 'published', 'observed'},
    'date_precision': {'day', 'week', 'month'},
    'track': {'national', 'sector', 'ucl', 'data'},
    'category': {'restrictions', 'teaching', 'testing', 'vaccination',
                 'accommodation', 'assessment', 'wellbeing', 'research',
                 'civic', 'governance', 'epidemiology'},
    'source_type': {'newsletter', 'web', 'dataset'},
    'verified': {'quote-exact', 'primary-retrieved', 'computed', 'unverified'},
}

HEADLINE_MAX = 100
URL = re.compile(r'^https?://[^\s<>"]+$')
# A citation marker such as [7] is not a Markdown link reference. The renderers
# must not treat it as one; this is the test case the plan asked for.
CITE = re.compile(r'\[\d+\]')


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, row, msg):
        self.errors.append((row, msg))

    def warn(self, row, msg):
        self.warnings.append((row, msg))


def load_rows(path):
    with open(path, newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != FIELDS:
            sys.exit(f'header mismatch in {path}\n'
                     f'  expected: {FIELDS}\n'
                     f'  found:    {reader.fieldnames}')
        return list(reader), reader.fieldnames


def check(rows, cfg, rep):
    start = date.fromisoformat(str(cfg['range.start']))
    end = date.fromisoformat(str(cfg['range.end']))
    textdir = cfg.path('paths.text')
    updates = cfg.path('paths.updates')

    # Extracted newsletter text, normalised once. Check 3 runs against this.
    corpus = {}
    for p in textdir.glob('*.txt'):
        corpus[p.stem] = normalise(p.read_text(encoding='utf-8'))

    # Cached primary sources, keyed by the URL a row cites. Check 3b runs
    # against these, so a national row's quotation is checked exactly as a UCL
    # row's is: against the retrieved document, not against a recollection of
    # it. See build/fetch_sources.py.
    #
    # Check 3c hashes both halves of each cached document before any quotation
    # is checked against it. Until it existed, fetch_sources.py recorded a
    # sha256 of the original and nothing ever compared anything to it, while the
    # derived `.txt` — the file check 3b actually reads, and the one tracked in
    # git — carried no hash at all. Appending a sentence to a `.txt` and citing
    # it as `primary-retrieved` therefore validated clean. The newsletter half
    # never had this hole: `text/` is gitignored and regenerated from the
    # archive, so it cannot be edited in place and kept.
    #
    # This does not re-derive the text from the original, which would be
    # stronger and would cost the validator a dependency on `pdftotext`. What it
    # does mean is that editing a cached document now also requires editing the
    # manifest, which is a visible diff rather than a silent one.
    sources = {}
    sdir = config.ROOT / str(cfg.get('sources.cache', 'sources'))
    smanifest = sdir / 'manifest.csv'
    if smanifest.exists():
        with open(smanifest, newline='', encoding='utf-8') as fh:
            for r in csv.DictReader(fh):
                loc = f'sources/{r.get("file", "?")}'
                for name, recorded in (('file', r.get('sha256', '')),
                                       ('text', r.get('text_sha256', ''))):
                    fp = sdir / r[name] if r.get(name) else None
                    if fp is None or not fp.exists():
                        continue
                    if not recorded:
                        rep.error(loc, f'{fp.name} has no hash in manifest.csv')
                        continue
                    got = hashlib.sha256(fp.read_bytes()).hexdigest()
                    if got != recorded:
                        rep.error(loc, f'{fp.name} does not match manifest.csv '
                                       f'({got[:12]}… vs {recorded[:12]}…) — '
                                       f're-run build/fetch_sources.py')
        with open(smanifest, newline='', encoding='utf-8') as fh:
            for r in csv.DictReader(fh):
                tp = sdir / r['text'] if r.get('text') else None
                if tp and tp.exists():
                    sources[r['url']] = normalise(tp.read_text(encoding='utf-8'))

    seen = {}
    pairs = {}
    dated = []

    for n, row in enumerate(rows, start=2):        # 2 = first row after header
        loc = f'row {n} ({row.get("date", "?")} {row.get("track", "?")})'

        # 1. dates
        try:
            d = date.fromisoformat(row['date'])
            # fromisoformat accepts more than YYYY-MM-DD on 3.11 and later:
            # '20200309' and '2020-W10-1' both parse. Everything downstream then
            # compares the raw string — links pair on it, the ledger sorts on
            # it, and the browser builds a Date from it — so a row that parses
            # but is not written this way pairs with nothing, sorts to the wrong
            # end, and lands at NaN on the chart. The round trip is the check.
            if d.isoformat() != row['date']:
                rep.error(loc, f'date {row["date"]!r} is not ISO YYYY-MM-DD '
                               f'(parses as {d.isoformat()})')
            elif not (start <= d <= end):
                rep.error(loc, f'date {d} outside {start}..{end}')
            dated.append((d, row))
        except ValueError:
            rep.error(loc, f'date {row["date"]!r} is not ISO YYYY-MM-DD')
            d = None

        # 2. required fields and enumerations
        for f in REQUIRED:
            if not (row.get(f) or '').strip():
                rep.error(loc, f'{f} is empty')
        for f, allowed in ENUMS.items():
            v = (row.get(f) or '').strip()
            if v and v not in allowed:
                rep.error(loc, f'{f}={v!r} not in {sorted(allowed)}')

        headline = (row.get('headline') or '').strip()
        if len(headline) > HEADLINE_MAX:
            rep.error(loc, f'headline is {len(headline)} chars, max {HEADLINE_MAX}')
        if headline.endswith('.'):
            rep.warn(loc, 'headline ends with a full stop')

        # 3. the anti-fabrication check
        quote = (row.get('quote') or '').strip()
        ref = (row.get('source_ref') or '').strip()
        if row.get('track') == 'ucl':
            if not quote:
                rep.error(loc, 'ucl row has no quote')
            elif row.get('source_type') != 'newsletter':
                rep.error(loc, f'ucl row has source_type={row.get("source_type")!r},'
                               ' expected newsletter')
            else:
                stem = ref[:-5] if ref.endswith('.html') else ref
                if stem not in corpus:
                    rep.error(loc, f'no extracted text for source_ref {ref!r}')
                elif normalise(quote) not in corpus[stem]:
                    rep.error(loc, f'QUOTE NOT FOUND in {ref}: {quote[:90]!r}')
        elif quote and row.get('source_type') == 'newsletter':
            stem = ref[:-5] if ref.endswith('.html') else ref
            if stem in corpus and normalise(quote) not in corpus[stem]:
                rep.error(loc, f'QUOTE NOT FOUND in {ref}: {quote[:90]!r}')

        # 3b. the same check for the national and sector tracks. `verified=
        # primary-retrieved` is a claim that the document was fetched and read,
        # so it has to be in the cache and the quotation has to be in it.
        if row.get('source_type') == 'web':
            if row.get('verified') == 'primary-retrieved':
                if not quote:
                    rep.error(loc, 'primary-retrieved row has no quote')
                elif ref not in sources:
                    rep.error(loc, f'primary-retrieved but {ref} is not in the '
                                   'source cache; run build/fetch_sources.py')
                elif normalise(quote) not in sources[ref]:
                    rep.error(loc, f'QUOTE NOT FOUND in cached {ref}: '
                                   f'{quote[:90]!r}')
            elif quote and ref in sources and normalise(quote) not in sources[ref]:
                rep.error(loc, f'QUOTE NOT FOUND in cached {ref}: {quote[:90]!r}')

        # 4. source references resolve
        st = row.get('source_type')
        if st == 'newsletter':
            if not (updates / ref).exists():
                rep.error(loc, f'newsletter {ref!r} does not exist on disk')
        elif st == 'web':
            if not URL.match(ref):
                rep.error(loc, f'web source_ref is not a URL: {ref!r}')
        elif st == 'dataset' and not ref:
            rep.error(loc, 'dataset row has no source_ref')

        # unverified rows must say what could not be established
        if row.get('verified') == 'unverified' and not (row.get('notes') or '').strip():
            rep.error(loc, 'verified=unverified requires a note saying what failed')

        # the [N] marker must survive into notes/detail without becoming a link
        for f in ('detail', 'notes', 'headline'):
            v = row.get(f) or ''
            for m in CITE.finditer(v):
                after = v[m.end():m.end() + 1]
                if after in ('(', '['):
                    rep.error(loc, f'{f} has {m.group(0)} followed by {after!r} —'
                                   ' a citation marker read as a Markdown link')

        # 6. exact duplicates
        key = tuple(row.get(f, '') for f in FIELDS)
        if key in seen:
            rep.error(loc, f'exact duplicate of row {seen[key]}')
        else:
            seen[key] = n

        # 6c. date and headline together, which the renderers rely on being
        # unique and timeline.toml already states this file establishes. It did
        # not: check 6 compares all thirteen fields, so two rows alike in date
        # and headline but differing in `detail` passed. render_md.py keys its
        # row index on exactly this pair, so the pair would have collapsed
        # silently, the link resolving to whichever sorted last and the lag
        # attaching to the wrong row. No collision exists today; the invariant
        # was simply unguarded.
        pair = (row.get('date', ''), row.get('headline', ''))
        if pair in pairs:
            rep.error(loc, f'date and headline repeat row {pairs[pair]}: '
                           f'{pair[1][:60]!r} — the renderers key on this pair')
        else:
            pairs[pair] = n

    # 5. issue numbers match the newsletter they cite.
    #
    # Not "issue numbers increase with row date" — that is the wrong test. A row
    # is filed under the date of the event, which may precede the newsletter that
    # reports it: the first-year assessment cancellation happened on 20 March 2020
    # and is reported in issue 11 of 23 March. Comparing issue against row date
    # therefore fails on correct data. The real invariant is that a row's `issue`
    # is the issue number of its `source_ref`, and stage 0 already established
    # that those run 1..165 strictly increasing by newsletter date.
    index = textdir / 'index.csv'
    if index.exists():
        with open(index, newline='', encoding='utf-8') as fh:
            issue_of = {r['basename']: r['issue'] for r in csv.DictReader(fh)}
        for n, row in enumerate(rows, start=2):
            if row.get('source_type') != 'newsletter':
                continue
            ref = (row.get('source_ref') or '').strip()
            if ref not in issue_of:
                continue
            want, got = issue_of[ref], (row.get('issue') or '').strip()
            if want != got:
                rep.error(f'row {n} ({row.get("date")} {row.get("track")})',
                          f'issue={got!r} but {ref} is issue {want!r}')
    else:
        rep.warn('index', f'no {index}; issue numbers not checked')

    # 6b. near-duplicates, reported for a human to judge
    by_key = {}
    for d, r in dated:
        k = (r['date'], r['track'], _fold(r.get('headline', '')))
        by_key.setdefault(k, []).append(r)
    for (dt, tr, _), group in sorted(by_key.items()):
        if len(group) > 1:
            rep.warn(f'{dt} {tr}',
                     f'{len(group)} rows with near-identical headlines: '
                     + ' | '.join(g['headline'] for g in group))


def _fold(s):
    return re.sub(r'[^a-z0-9 ]', '', s.lower()).strip()


def main():
    def opts(ap):
        ap.add_argument('--quiet', action='store_true',
                        help='counts only, no per-row detail')
    cfg, args = config.load(extra_args=opts)

    ledger = cfg.path('paths.ledger')
    if not ledger.exists():
        sys.exit(f'no ledger at {ledger} — nothing to validate yet')

    rows, _ = load_rows(ledger)
    rep = Report()
    check(rows, cfg, rep)

    print(f'ledger:   {ledger}')
    print(f'rows:     {len(rows)}')
    by_track = {}
    for r in rows:
        by_track[r.get('track', '?')] = by_track.get(r.get('track', '?'), 0) + 1
    print('by track: ' + ', '.join(f'{k} {v}' for k, v in sorted(by_track.items())))
    by_ver = {}
    for r in rows:
        by_ver[r.get('verified', '?')] = by_ver.get(r.get('verified', '?'), 0) + 1
    print('verified: ' + ', '.join(f'{k} {v}' for k, v in sorted(by_ver.items())))

    if not args.quiet:
        for loc, msg in rep.warnings:
            print(f'WARN  {loc}: {msg}')
        for loc, msg in rep.errors:
            print(f'FAIL  {loc}: {msg}')

    print(f'\nerrors: {len(rep.errors)}   warnings: {len(rep.warnings)}')
    return 1 if rep.errors else 0


if __name__ == '__main__':
    sys.exit(main())
