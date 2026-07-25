#!/usr/bin/env python3
"""Stage 2, step one: turn the research synthesis into a worklist with
provenance attached.

`UK COVID-19 Timeline Resources.md` is a synthesis, not a source. It makes
dated claims and it cites them, and because the citation markers survived the
conversion from .docx those claims are recoverable with their attribution
intact. This script walks the document, finds every sentence carrying a date,
and emits a candidate row with the reference numbers it cites resolved to their
titles and URLs.

What it emits is a worklist, not ledger rows. Nothing here is verified. The
next step is to retrieve the cited document and check the claim against it,
which is why every candidate carries the URL it must be checked against and
why nothing is written to `timeline.csv`.

Two things it marks, because both change how much care a candidate needs:

  * `cites: []` means the sentence makes a dated claim with no attribution at
    all. 51 of the 84 references are used and not every sentence carries a
    marker, so this set exists and needs the most care, not the least.
  * `wikipedia: true` means the only support is reference 26. Those do not go
    in the ledger without a primary substitute.

And one it cross-references: `needed_by` names any `[[links]]` pairing in
`timeline.toml` whose counterpart falls on that date. Those candidates are the
load-bearing ones, because each is a lag the Markdown chronology is currently
unable to state.

Standard library only. Usage:
    python3 seed_national.py [--config timeline.toml] [--out DIR]
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

import config

MONTHS = {m: i for i, m in enumerate(
    ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
     'September', 'October', 'November', 'December'], start=1)}

# "23 March 2020", and "8 March" whose year has to come from context.
FULL_DATE = re.compile(r'\b(\d{1,2}) (' + '|'.join(MONTHS) + r') (\d{4})\b')
BARE_DATE = re.compile(r'\b(\d{1,2}) (' + '|'.join(MONTHS) + r')\b(?! \d{4})')
CITE = re.compile(r'\[(\d+)\]')
REF_LINE = re.compile(r'^(\d+)\.\s+(.*?)\s+—\s+<(\S+)>\s*$')
YEAR_IN_HEADING = re.compile(r'\b(20\d{2})\b')

WIKIPEDIA_REF = 26


def parse_references(lines):
    """The works-cited list, so a marker resolves to something retrievable."""
    refs, in_list = {}, False
    for line in lines:
        if line.startswith('## Works cited'):
            in_list = True
            continue
        if in_list:
            m = REF_LINE.match(line.strip())
            if m:
                refs[int(m.group(1))] = {'title': m.group(2),
                                         'url': m.group(3)}
    return refs


def split_sentences(text):
    """Good enough for a worklist. Abbreviations that end in a full stop are
    rare in this document and a mis-split costs a reader one glance."""
    text = re.sub(r'\s+', ' ', text).strip()
    parts = re.split(r'(?<=[.:])\s+(?=[A-Z"“(])', text)
    return [p.strip() for p in parts if p.strip()]


def table_cells(line):
    """A row of either summary table, as its cells."""
    cells = [c.strip() for c in line.strip().strip('|').split('|')]
    return [re.sub(r'\*\*', '', c) for c in cells]


def dates_in(text, context_year):
    """Every date in a sentence, with a flag where the year was inferred."""
    found = []
    for m in FULL_DATE.finditer(text):
        d, mon, y = m.group(1), m.group(2), m.group(3)
        try:
            found.append((date(int(y), MONTHS[mon], int(d)), False))
        except ValueError:
            pass
    consumed = {m.start() for m in FULL_DATE.finditer(text)}
    for m in BARE_DATE.finditer(text):
        if any(abs(m.start() - c) < 3 for c in consumed) or not context_year:
            continue
        try:
            found.append((date(context_year, MONTHS[m.group(2)],
                               int(m.group(1))), True))
        except ValueError:
            pass
    return found


def walk(path):
    """Yield (section, kind, text, context_year) for every prose sentence and
    table row in the document."""
    lines = path.read_text(encoding='utf-8').splitlines()
    section, context_year, in_refs = '', None, False
    for line in lines:
        if line.startswith('## Works cited'):
            in_refs = True
        if in_refs:
            continue
        if line.startswith('#'):
            section = line.lstrip('#').strip()
            years = YEAR_IN_HEADING.findall(section)
            context_year = int(years[0]) if years else context_year
            continue
        if not line.strip():
            continue
        if line.lstrip().startswith('|'):
            cells = table_cells(line)
            if len(cells) < 2 or set(''.join(cells)) <= set('-: '):
                continue
            # A summary table sits at the end of a section but summarises the
            # whole document, so attributing its rows to the prose heading
            # above them would file the first lockdown under the 2021 roadmap.
            row_text = ' | '.join(cells)
            # And its year must come from the row itself, not from that
            # heading, or a bare "14 September" in the table inherits 2021.
            row_years = YEAR_IN_HEADING.findall(row_text)
            yield f'{section} (summary table)', 'table', row_text, \
                int(row_years[0]) if row_years else None
            continue
        for s in split_sentences(line):
            yield section, 'prose', s, context_year


def counterpart_dates(cfg):
    """Dates the Markdown chronology is waiting on, from the declared lag
    pairings, so the worklist says which candidates are load-bearing."""
    wanted = {}
    for spec in cfg.get('links', []):
        if spec.get('counterpart'):
            # Several UCL rows can respond to one national measure, so the
            # labels repeat. The worklist wants the measure once.
            labels = wanted.setdefault(str(spec['counterpart']), [])
            if spec.get('label') and spec['label'] not in labels:
                labels.append(spec['label'])
    return wanted


def main():
    def opts(ap):
        ap.add_argument('--out', default='seed',
                        help='directory for the worklist, under timeline/')
    cfg, args = config.load(extra_args=opts)

    src = cfg.path('paths.resources')
    if not src.exists():
        sys.exit(f'no research synthesis at {src}')
    refs = parse_references(src.read_text(encoding='utf-8').splitlines())
    if not refs:
        sys.exit(f'no works-cited list parsed from {src}; the reference '
                 'format may have changed')
    wanted = counterpart_dates(cfg)

    candidates, seen = [], set()
    for section, kind, text, year in walk(src):
        found = dates_in(text, year)
        if not found:
            continue
        cites = sorted({int(c) for c in CITE.findall(text)})
        for d, inferred in found:
            key = (d.isoformat(), text)
            if key in seen:
                continue
            seen.add(key)
            candidates.append({
                'date': d.isoformat(),
                'year_inferred': inferred,
                'section': section,
                'kind': kind,
                'claim': CITE.sub('', text).strip(),
                'cites': cites,
                'sources': [{'ref': c, **refs[c]} for c in cites if c in refs],
                'wikipedia': cites == [WIKIPEDIA_REF],
                'needed_by': wanted.get(d.isoformat(), []),
            })

    candidates.sort(key=lambda c: (c['date'], c['section']))
    out = (config.ROOT / args.out)
    out.mkdir(exist_ok=True)
    (out / 'national-candidates.json').write_text(
        json.dumps(candidates, indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8')
    write_review(out / 'national-candidates.md', candidates, refs, wanted)

    uncited = [c for c in candidates if not c['cites']]
    wiki = [c for c in candidates if c['wikipedia']]
    inferred = [c for c in candidates if c['year_inferred']]
    matched = {c['date'] for c in candidates if c['needed_by']}

    print(f'source:      {src}')
    print(f'references:  {len(refs)} parsed')
    print(f'candidates:  {len(candidates)}')
    print(f'  uncited:      {len(uncited)}  (dated claim, no marker)')
    print(f'  wikipedia:    {len(wiki)}  (ref {WIKIPEDIA_REF} only)')
    print(f'  year guessed: {len(inferred)}  (from the section heading)')
    print(f'  needed by a declared lag pairing: {len(matched)} of '
          f'{len(wanted)} dates')
    missing = sorted(set(wanted) - matched)
    if missing:
        print('  no candidate for: ' + ', '.join(missing))
    print(f'wrote:       {out}/national-candidates.json and .md')
    return 0


def write_review(path, candidates, refs, wanted):
    """The same worklist as something a person can read down."""
    out = ['# National and sector candidates', '',
           'Generated by `build/seed_national.py` from the research synthesis. '
           'Nothing here is verified: each row is a dated claim made by a '
           'secondary source, with the reference it cites resolved so it can '
           'be checked against the primary document. Claims are only promoted '
           'to `timeline.csv` after that check.', '']
    by_ref = {}
    for c in candidates:
        for r in c['cites']:
            by_ref[r] = by_ref.get(r, 0) + 1
    out.append('## Retrieval order, by how much rests on each reference')
    out.append('')
    out.append('| Ref | Citations | Document |')
    out.append('|---|---|---|')
    for r, n in sorted(by_ref.items(), key=lambda kv: (-kv[1], kv[0])):
        title = refs.get(r, {}).get('title', '(not in the works-cited list)')
        url = refs.get(r, {}).get('url', '')
        out.append(f'| {r} | {n} | [{title}]({url}) |' if url
                   else f'| {r} | {n} | {title} |')
    out.append('')

    load_bearing = [c for c in candidates if c['needed_by']]
    if load_bearing:
        out.append('## Load-bearing: candidates a declared lag pairing waits on')
        out.append('')
        out.append('Each of these is a date `TIMELINE.md` currently cannot '
                   'state a lag against. Verifying one turns a pending row in '
                   'the chronology into a measured one.')
        out.append('')
        for c in load_bearing:
            out.append(f'- **{c["date"]}** · {"; ".join(c["needed_by"])} · '
                       f'refs {c["cites"] or "none"}')
        out.append('')
        unmatched = sorted(set(wanted) - {c['date'] for c in load_bearing})
        if unmatched:
            out.append('The synthesis carries no dated claim at all for: '
                       + ', '.join(unmatched)
                       + '. Those need a primary source found directly.')
            out.append('')

    out.append('## All candidates')
    out.append('')
    for c in candidates:
        flags = []
        if c['year_inferred']:
            flags.append('year inferred from the section heading')
        if not c['cites']:
            flags.append('**uncited**')
        if c['wikipedia']:
            flags.append('**Wikipedia only, needs a primary substitute**')
        if c['needed_by']:
            flags.append('**load-bearing**')
        out.append(f'**{c["date"]}** · {c["section"]}'
                   + (f' · {", ".join(flags)}' if flags else ''))
        out.append('')
        out.append(f'> {c["claim"]}')
        out.append('')
        for s in c['sources']:
            out.append(f'- [{s["ref"]}] [{s["title"]}]({s["url"]})')
        if not c['sources']:
            out.append('- no reference cited')
        out.append('')
    path.write_text('\n'.join(out).rstrip() + '\n', encoding='utf-8')


if __name__ == '__main__':
    sys.exit(main())
