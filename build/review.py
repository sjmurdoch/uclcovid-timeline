#!/usr/bin/env python3
"""Stage 7: find every claim in the ledger that reads as asserted rather than
evidenced.

The quotations are already checked mechanically, and that is the strong part of
this project. The weak part is everything around them: the `detail` and `notes`
fields are prose I wrote, they are not checked by anything, and they sit
directly beneath a verified quotation where they inherit its authority. This
script does not judge them. It sorts them into the four kinds of claim that
need a human to look, so that reading the chronology end to end becomes reading
a worklist rather than hoping to notice.

  * **superlative** — "the clearest", "the only", "anywhere in the record".
    Some of these are checkable against the ledger and this script checks the
    ones that are; the rest need a reader.
  * **causal** — "because", "which is why", "explains". A causal claim is the
    easiest thing to write and the hardest thing to support.
  * **unsourced-number** — a figure in the commentary that does not appear in
    the quotation it sits under. Either it came from somewhere else, in which
    case it needs saying where, or it is wrong.
  * **relayed** — a named external authority (ONS, SAGE, UKHSA, the
    government) reported by UCL. Stage 1 flagged three of these explicitly and
    this finds any others.

Standard library only. Usage:
    python3 review.py [--config timeline.toml] [--kind superlative]
"""
import csv
import re
import sys
from collections import Counter

import config
from validate import load_rows
from extract_text import normalise

SUPERLATIVE = re.compile(
    r'\b(clearest|sharpest|plainest|starkest|only|sole|first|last|largest|'
    r'smallest|highest|lowest|most|least|best|worst|never|always|every|'
    r'unique|unprecedented|densest|thinnest|earliest|latest)\b', re.I)

ANYWHERE = re.compile(
    r'\b(anywhere in the record|in the whole record|in the entire|'
    r'of the whole|in the record|nowhere)\b', re.I)

CAUSAL = re.compile(
    r'\b(because|which is why|that is why|explains|caused|led to|'
    r'as a result|therefore|consequently|so that|resulted in|due to|'
    r'on account of|drove|forced)\b', re.I)

RELAYED = re.compile(
    r'\b(ONS|SAGE|UKHSA|PHE|Public Health England|NHS|DfE|OfS|UKRI|UCEA|'
    r'Office for National Statistics|Department for Education|'
    r'Office for Students|government|Government|Prime Minister|minister|'
    r'Chief Medical Officer)\b')

# Figures written as words that a bare digit scan would miss.
WORD_NUMBER = re.compile(
    r'\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|'
    r'fifteen|twenty|thirty|forty|fifty|hundred|thousand)\b', re.I)

NUMBER = re.compile(r'(?<![\w.])(\d[\d,]*(?:\.\d+)?)\s*(%|per cent)?')

# Figures that are not claims about the world: dates, issue numbers, years,
# and the ordinary furniture of a citation.
DATEISH = re.compile(
    r'\b\d{1,2}\s+(January|February|March|April|May|June|July|August|'
    r'September|October|November|December)\b|\b(19|20)\d{2}\b|'
    r'\bissue\s+\d+\b|\bTerm\s+\d\b|\bstep\s+\d\b|\bTier\s+\d\b|'
    r'\bstage\s+\d\b|\bPhase\s+\d\b|\b20\d{2}-\d{2}\b|'
    r'\b\d{4}-\d{2}-\d{2}\b', re.I)


def numbers_in(text):
    """Figures that assert something, with dates and citations removed."""
    # Clock times are written "11:00" in the newsletters and "11.00" in the
    # commentary. That is a separator, not a discrepancy, so both collapse to
    # one form before anything is compared.
    cleaned = re.sub(r'(\d{1,2})[:.](\d{2})\b', r'\1\2', text or '')
    cleaned = DATEISH.sub(' ', cleaned)
    out = []
    for m in NUMBER.finditer(cleaned):
        raw = m.group(1).replace(',', '')
        try:
            val = float(raw)
        except ValueError:
            continue
        # Single digits are usually counts in prose the quote supports; the
        # interesting case is a specific figure.
        out.append((m.group(1) + (m.group(2) or ''), val))
    return out


def classify(row):
    """Every kind of claim this row's commentary makes. A row can be several."""
    detail = (row.get('detail') or '').strip()
    notes = (row.get('notes') or '').strip()
    prose = f'{detail} {notes}'.strip()
    if not prose:
        return []

    quote = normalise(row.get('quote') or '')
    found = []

    sup = set(m.group(0).lower() for m in SUPERLATIVE.finditer(prose))
    sup |= set(m.group(0).lower() for m in ANYWHERE.finditer(prose))
    if sup:
        found.append(('superlative', ', '.join(sorted(sup))))

    cau = set(m.group(0).lower() for m in CAUSAL.finditer(prose))
    if cau:
        found.append(('causal', ', '.join(sorted(cau))))

    # A figure in the commentary that is not in the quotation it sits under.
    loose = []
    for shown, val in numbers_in(prose):
        digits = shown.replace(',', '').rstrip('%').rstrip()
        if digits and digits in normalise(quote).replace(',', ''):
            continue
        loose.append(shown)
    if loose:
        found.append(('unsourced-number', ', '.join(sorted(set(loose)))))

    rel = set(m.group(0) for m in RELAYED.finditer(prose))
    # Only interesting where the quotation does not itself name the authority:
    # if UCL's own words cite PHE, the row is already showing its working.
    rel = {r for r in rel if r not in quote}
    if rel:
        found.append(('relayed', ', '.join(sorted(rel))))

    return found


def check_corpus_figures(rows, cfg):
    """Figures in the commentary that appear nowhere in the corpus at all.

    This is the one check in this file that adjudicates rather than flags, and
    it is the one that found a real error. A `detail` or `notes` field may
    legitimately carry a figure its own quotation does not — the quote is one
    passage and the detail summarises the newsletter — and it may legitimately
    cross-reference another issue. What it may not do is state a number that
    exists in no newsletter, no source and no computation, because there is
    then nowhere the reader could go to check it.

    Found this way: a note claiming a heading recurred in 105 of the 168
    newsletters. It recurs in 110.
    """
    textdir = cfg.path('paths.text')
    corpus = ' '.join(
        normalise(p.read_text(encoding='utf-8'))
        for p in sorted(textdir.glob('*.txt'))).replace(',', '')
    corpus = re.sub(r'(\d{1,2})[:.](\d{2})\b', r'\1\2', corpus)

    sdir = config.ROOT / str(cfg.get('sources.cache', 'sources'))
    manifest = sdir / 'manifest.csv'
    if manifest.exists():
        with open(manifest, newline='', encoding='utf-8') as fh:
            for m in csv.DictReader(fh):
                if m.get('text') and (sdir / m['text']).exists():
                    corpus += ' ' + normalise(
                        (sdir / m['text']).read_text(encoding='utf-8')
                    ).replace(',', '')

    out = []
    for r in rows:
        if r['track'] == 'data':          # computed; the detail shows the sum
            continue
        prose = ' '.join(x for x in ((r.get('detail') or '').strip(),
                                     (r.get('notes') or '').strip()) if x)
        if not prose or 'Threshold:' in prose:
            continue
        missing = []
        for shown, val in numbers_in(prose):
            digits = shown.replace(',', '').rstrip('%').strip()
            if not digits or val < 10:
                continue
            if digits in corpus:
                continue
            missing.append(shown)
        if missing:
            out.append((r, sorted(set(missing))))
    return out


def main():
    def opts(ap):
        ap.add_argument('--kind', default='',
                        help='show only one kind of claim')
        ap.add_argument('--full', action='store_true',
                        help='print the whole note, not the first 150 chars')
    cfg, args = config.load(extra_args=opts)

    rows, _ = load_rows(cfg.path('paths.ledger'))
    rows.sort(key=lambda r: (r['date'], r['track'], r['headline']))

    tally = Counter()
    flagged = []
    for r in rows:
        kinds = classify(r)
        for kind, hits in kinds:
            tally[kind] += 1
            if not args.kind or args.kind == kind:
                flagged.append((r, kind, hits))
    rows_flagged = len({id(r) for r, _, _ in flagged})

    print(f'rows:            {len(rows)}')
    print(f'rows with prose: {sum(1 for r in rows if (r.get("detail") or r.get("notes")))}')
    for kind in ('superlative', 'causal', 'unsourced-number', 'relayed'):
        print(f'  {kind:18s} {tally[kind]:4d}')
    print(f'flagged shown:   {len(flagged)} claims across {rows_flagged} rows')
    print()

    for r, kind, hits in flagged:
        prose = ' '.join(x for x in ((r.get('detail') or '').strip(),
                                     (r.get('notes') or '').strip()) if x)
        print(f'[{kind}] {r["date"]} {r["track"]} · {r["headline"][:66]}')
        print(f'    hits: {hits}')
        print(f'    {prose if args.full else prose[:150]}')
        print()

    orphans = check_corpus_figures(rows, cfg)
    print('=== figures appearing in no newsletter and no cached source ===')
    if not orphans:
        print('  none: every figure in the commentary is traceable to a '
              'document in the corpus.')
    for r, missing in orphans:
        print(f'  {r["date"]} {r["track"]} · {r["headline"][:58]} — {missing}')
    return 1 if orphans else 0


if __name__ == '__main__':
    sys.exit(main())
