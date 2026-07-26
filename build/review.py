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
    r'unique|unprecedented|densest|thinnest|earliest|latest|'
    # An extremum asserted about a series is the same kind of claim as a
    # superlative and needs the same check: the withdrawn "Camden and UCL both
    # peak in November 2020" row said peak, which nothing above matches, and
    # its figures were correct so the number checks passed it through.
    r'peaks?|peaked|peaking|troughs?|maximum|minimum|record high|record low|'
    r'all-time)\b', re.I)

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


TOKEN = re.compile(r'\d+(?:\.\d+)?')


def number_tokens(text):
    """Whole numbers appearing in text, as a set.

    Membership in this set is the word-boundary test the checks below want. A
    bare `digits in text` reports 154 as present because 1154 is, and 525
    because 5250 is, which quietly weakens the only check in this file that
    adjudicates rather than flags.
    """
    return set(TOKEN.findall(text))


def classify(row):
    """Every kind of claim this row's commentary makes. A row can be several.

    The headline counts as commentary. It was left out until a generated data
    row headlined "Camden and UCL both peak in November 2020" reached the
    published ledger, where November was a peak for neither series: the claim
    was in the one field this file did not read. Every generated headline puts
    its superlative and its figure exactly there.
    """
    headline = (row.get('headline') or '').strip()
    detail = (row.get('detail') or '').strip()
    notes = (row.get('notes') or '').strip()
    prose = ' '.join(x for x in (headline, detail, notes) if x)
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
    # Matched as whole numbers: a substring test called 154 supported because
    # the quote happened to contain 1154.
    quoted = number_tokens(normalise(quote).replace(',', ''))
    loose = []
    for shown, val in numbers_in(prose):
        digits = shown.replace(',', '').rstrip('%').rstrip()
        if digits and digits in quoted:
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

    corpus_numbers = number_tokens(corpus)

    out = []
    for r in rows:
        if r['track'] == 'data':          # computed; the detail shows the sum
            continue
        prose = ' '.join(x for x in ((r.get('headline') or '').strip(),
                                     (r.get('detail') or '').strip(),
                                     (r.get('notes') or '').strip()) if x)
        if not prose or 'Threshold:' in prose:
            continue
        missing = []
        for shown, val in numbers_in(prose):
            digits = shown.replace(',', '').rstrip('%').strip()
            if not digits or val < 10:
                continue
            if digits in corpus_numbers:
                continue
            missing.append(shown)
        if missing:
            out.append((r, sorted(set(missing))))
    return out


def main():
    def opts(ap):
        ap.add_argument('--kind', default='',
                        help='show only one kind of claim')
        ap.add_argument('--coverage', action='store_true',
                        help='list newsletter sections no row covers')
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

    if args.coverage:
        gaps = check_sections(rows, cfg)
        print('=== newsletter sections no row from that issue covers ===')
        print(f'  {len(gaps)} sections across '
              f'{len({g[0] for g in gaps})} newsletters\n')
        for ref, head, n in gaps:
            print(f'  {ref[:44]:46s} ({n} rows)  {head}')
        return 0

    orphans = check_corpus_figures(rows, cfg)
    print('=== figures appearing in no newsletter and no cached source ===')
    if not orphans:
        print('  none: every figure in the commentary is traceable to a '
              'document in the corpus.')
    for r, missing in orphans:
        print(f'  {r["date"]} {r["track"]} · {r["headline"][:58]} — {missing}')
    return 1 if orphans else 0




# --- coverage -------------------------------------------------------------
#
# The first coverage test was a keyword scan of the uncited newsletters for
# decision-signalling language. It establishes the absence of *obvious* misses
# and nothing more: a decision phrased without those markers goes straight
# through. This is the stronger test.
#
# The newsletters are structured. Each carries a numbered list of sections, and
# a section is the unit UCL itself chose to treat as a thing worth telling
# people about. So the question "did we miss anything?" becomes checkable: for
# every newsletter that has rows, is there a section whose subject matter no
# row from that newsletter touches? That does not prove a section deserved a
# row — most do not, being standing wellbeing content — but it turns 168 files
# into a list a person can read down.

SECTION = re.compile(r'(?:^|\s)(\d{1,2})\.\s+([A-Z][^.]{6,70}?)(?=\s+[A-Z]|\s\d{1,2}\.)')

STOP = set('the a an and or of for to in on at with from by is are was were be '
           'been will would can could our your their his her its this that '
           'these those new more all any as it we you they ucl update updates '
           'coronavirus covid covid-19 support advice information'.split())


def stem(w):
    """Crude suffix stripping. "Building closures" and "buildings ... close"
    are the same subject, and comparing them as raw tokens said otherwise."""
    for suf in ('ations', 'ation', 'ings', 'ing', 'ies', 'ed', 'es', 's'):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[:-len(suf)]
    return w


def words(text):
    return {stem(w) for w in re.findall(r'[a-z]{4,}', (text or '').lower())
            if w not in STOP}


def check_sections(rows, cfg):
    """Sections of cited newsletters that nothing in the ledger covers.

    Two things keep this usable rather than a wall of 511 false positives.

    **Recurring headings are standing content, not decisions.** "Support
    available for staff and students" appears in scores of issues; the
    inclusion test has always said recurring guidance earns no row and only
    the first appearance of a thread does. A heading carried by more than five
    newsletters is therefore dropped, the same rule digest.py applies to
    paragraphs.

    **A decision is often restated in the next issue.** Matching a section only
    against rows sourced to its own newsletter flags every restatement as a
    gap. Rows within a week either side are considered instead, which is the
    window in which the newsletters repeat themselves.
    """
    from datetime import date, timedelta
    textdir = cfg.path('paths.text')
    index = {}
    idx_path = textdir / 'index.csv'
    if idx_path.exists():
        with open(idx_path, newline='', encoding='utf-8') as fh:
            index = {r['basename']: r['body_date'] for r in csv.DictReader(fh)}

    # Rows keyed by date, so a section can be matched against the week around
    # the newsletter that carried it.
    by_day = {}
    for r in rows:
        by_day.setdefault(r['date'], []).append(
            words(f'{r["headline"]} {r.get("detail", "")} '
                  f'{r.get("notes", "")} {r.get("quote", "")}'))

    # First pass: how many newsletters carry each heading?
    seen_in = {}
    per_file = {}
    for p2 in sorted(textdir.glob('*.txt')):
        text = normalise(p2.read_text(encoding='utf-8'))
        heads = []
        for _, head in SECTION.findall(text):
            head = head.strip()
            if head and head.lower() not in {h.lower() for h in heads}:
                heads.append(head)
        per_file[p2.stem + '.html'] = heads
        for h in heads:
            seen_in[h.lower()] = seen_in.get(h.lower(), 0) + 1

    cited = {r['source_ref'] for r in rows if r.get('source_type') == 'newsletter'}
    out = []
    for ref in sorted(cited):
        iso = index.get(ref)
        if not iso:
            continue
        d0 = date.fromisoformat(iso)
        near = []
        for off in range(-7, 8):
            near.extend(by_day.get((d0 + timedelta(days=off)).isoformat(), []))
        for head in per_file.get(ref, []):
            if seen_in.get(head.lower(), 0) > 5:
                continue                      # standing content
            hw = words(head)
            if len(hw) < 2:
                continue                      # too thin to judge
            if any(len(hw & c) >= 2 for c in near):
                continue
            out.append((ref, head, len(near)))
    return out


if __name__ == '__main__':
    sys.exit(main())
