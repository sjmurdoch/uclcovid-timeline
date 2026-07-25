#!/usr/bin/env python3
"""Stage 5: render the ledger as a Markdown chronology.

Reads `timeline.csv` and writes `TIMELINE.md`, sectioned by the pandemic phases
declared in `timeline.toml`. Nothing here is a source of fact: every date,
headline, quotation and figure in the output comes from a ledger row that
`validate.py` has already checked, and the only prose the renderer supplies of
its own is the per-phase framing, which is written by hand in the config file
beside the phase it frames.

The one thing this script computes rather than copies is the **lag**: where a
UCL action responds to a national or sector one, the gap in days between the
two. That pairing cannot be inferred safely from dates alone, so it is declared
explicitly in `[[links]]` tables in `timeline.toml` and resolved against the
ledger here. A link whose national counterpart is not yet in the ledger is
reported as pending rather than rendered with a provisional number, because a
lag measured against an unverified date is exactly the kind of claim this
project refuses to publish.

Standard library only. Usage:
    python3 render_md.py [--config timeline.toml] [--set KEY=VALUE]
                         [--draft] [--stdout]
"""
import re
import sys
from datetime import date
from pathlib import Path

import config
from validate import load_rows

MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July',
          'August', 'September', 'October', 'November', 'December']

TRACK_LABEL = {'ucl': 'UCL', 'national': 'National', 'sector': 'Sector',
               'data': 'Data'}

# Rendered in the entry's metadata line, so a reader can see at a glance
# whether a date is when something was decided, when it took effect, or when
# the newsletter simply reported it.
KIND_LABEL = {'announced': 'announced', 'effective': 'took effect',
              'published': 'reported', 'observed': 'observed'}

DRAFT_MARKER = '**[framing not yet written]**'

WARNING_MD = """> # ⚠️ AI-generated demonstration, not a verified historical record
>
> **Every part of this document was produced by an AI system working from the preserved newsletters and the published case data. No human has checked it.**
>
> Some things here are checked mechanically and some are not, and the difference matters more than a general disclaimer would suggest. Every quotation is verified as an exact substring of the document it cites, so the words inside blockquotes really do appear in the source. **Everything around them is unverified**: whether the right events were selected, whether each one has been read correctly, whether the categories and dates are right, whether the commentary is sound, and whether anything important is missing. The lag figures depend on pairings an AI system judged to be causal, and those judgements have not been reviewed.
>
> Treat this as a **demonstration of what the underlying dataset makes possible**, not as a chronology of UCL's pandemic response to rely on, quote or cite. Anyone wanting to use a fact from here should follow its link to the preserved newsletter and read it in context first.
"""


# ---------------------------------------------------------------- formatting

def fmt_date(iso, precision='day'):
    """A ledger date as a reader expects to see it, honouring its precision."""
    d = date.fromisoformat(iso)
    if precision == 'month':
        return f'{MONTHS[d.month - 1]} {d.year}'
    if precision == 'week':
        return f'week of {d.day} {MONTHS[d.month - 1]} {d.year}'
    return f'{d.day} {MONTHS[d.month - 1]} {d.year}'


def one_line(s):
    """Collapse whitespace. One ledger quotation carries an embedded newline,
    which would silently end a blockquote."""
    return re.sub(r'\s+', ' ', (s or '')).strip()


def cell(s):
    """Escape what would otherwise break a Markdown table cell."""
    return one_line(s).replace('|', r'\|')


def slug(heading):
    """GitHub's heading anchor, so the contents list resolves."""
    s = heading.lower()
    s = re.sub(r'[^\w\s-]', '', s, flags=re.UNICODE)
    return re.sub(r'\s+', '-', s.strip())


def sentence(s):
    """A note or detail as a sentence, so hand-written fragments end cleanly."""
    s = one_line(s)
    if s and s[-1] not in '.!?:"”)':
        s += '.'
    return s


# ------------------------------------------------------------------- phases

class Phase:
    def __init__(self, n, name, start, end, framing):
        self.n = n
        self.name = name
        self.start = start
        self.end = end              # inclusive; None for the last phase
        self.framing = framing
        self.rows = []

    @property
    def heading(self):
        return f'{self.n}. {self.name}'

    def span(self):
        first = fmt_date(self.start.isoformat())
        if self.end is None:
            return f'from {first}'
        return f'{first} to {fmt_date(self.end.isoformat())}'

    def contains(self, d):
        return d >= self.start and (self.end is None or d <= self.end)


def build_phases(cfg):
    declared = cfg.phases()
    if not declared:
        sys.exit('no [[phases]] in the config; nothing to section the '
                 'chronology by')
    phases = []
    for i, p in enumerate(declared):
        start = date.fromisoformat(str(p['start']))
        nxt = declared[i + 1]['start'] if i + 1 < len(declared) else None
        end = date.fromordinal(date.fromisoformat(str(nxt)).toordinal() - 1) \
            if nxt else None
        phases.append(Phase(i + 1, p['name'], start, end, p.get('framing')))
    return phases


# -------------------------------------------------------------------- links

class Link:
    """A declared correspondence between a UCL action and the national or
    sector event it responds to. Resolved against the ledger, never guessed.

    `counterpart` is optional. Some of these pairings are ones where the
    newsletters make the dependency plain without dating the national measure,
    and inventing a date for it here would defeat the point of the exercise. A
    link with no counterpart date is a pairing stage 2 must both date and
    verify, and it says so.
    """

    def __init__(self, spec, index):
        self.spec = spec
        self.ucl = index.get(spec['ucl'])
        self.label = spec.get('label', '')
        self.note = spec.get('note', '')
        self.track = spec.get('track', 'national')
        raw = spec.get('counterpart')
        self.counterpart_date = date.fromisoformat(str(raw)) if raw else None
        # The counterpart is matched on date and track, not on headline: stage 2
        # writes those headlines and this file must not have to guess them.
        self.counterpart = None
        if raw:
            for row in index.values():
                if row['track'] == self.track and row['date'] == str(raw):
                    self.counterpart = row
                    break

    @property
    def resolved(self):
        return self.ucl is not None and self.counterpart is not None

    @property
    def lag(self):
        return (date.fromisoformat(self.ucl['date'])
                - self.counterpart_date).days

    def sort_key(self):
        """Undated counterparts sort by the UCL row they attach to, so the
        worklist stays chronological rather than clumping them at one end."""
        return (self.counterpart_date.isoformat() if self.counterpart_date
                else self.ucl['date'])


def row_key(row):
    return f'{row["date"]}|{row["headline"]}'


def build_links(cfg, rows):
    index = {row_key(r): r for r in rows}
    links, missing = [], []
    for spec in cfg.get('links', []):
        for field in ('ucl', 'label'):
            if field not in spec:
                sys.exit(f'[[links]] entry is missing {field!r}: {spec}')
        link = Link(spec, index)
        if link.ucl is None:
            missing.append(spec['ucl'])
        links.append(link)
    if missing:
        sys.exit('[[links]] names UCL rows that are not in the ledger, so a '
                 'declared pairing has gone stale:\n  '
                 + '\n  '.join(repr(m) for m in missing))
    return links


# ------------------------------------------------------------------ entries

def source_link(row, prefix):
    """A citation the reader can follow to the preserved newsletter."""
    ref = (row.get('source_ref') or '').strip()
    issue = (row.get('issue') or '').strip()
    if row.get('source_type') == 'newsletter':
        label = f'issue {issue}' if issue else ref
        return f'[{label}]({prefix}{ref})'
    if row.get('source_type') == 'web':
        return f'[source]({ref})'
    return f'`{cell(ref)}`'


def fmt_lag(days):
    """A signed gap in days, or the plain fact that there was no gap."""
    if days == 0:
        return 'same day'
    return f'{days:+d} day' if abs(days) == 1 else f'{days:+d} days'


def plural(n, noun):
    return f'{n} {noun}' if n == 1 else f'{n} {noun}s'


def render_entry(row, prefix, lag_by_key, out):
    out.append(f'**{one_line(row["headline"])}**  ')
    meta = ' · '.join([fmt_date(row['date'], row['date_precision']),
                       row['category'],
                       KIND_LABEL.get(row['date_kind'], row['date_kind'])])
    line = f'*{meta}* · {source_link(row, prefix)}'
    lag = lag_by_key.get(row_key(row))
    if lag is not None:
        line += f' · lag **{lag}**'
    out.append(line)
    out.append('')
    if (row.get('detail') or '').strip():
        out.append(sentence(row['detail']))
        out.append('')
    if (row.get('quote') or '').strip():
        out.append('> ' + one_line(row['quote']))
        out.append('')
    if (row.get('notes') or '').strip():
        out.append(sentence(row['notes']))
        out.append('')


def render_data_summary(rows, out):
    """The data track as a summary under the phase rather than interleaved row
    by row through the chronology, which would swamp it."""
    if not rows:
        return
    out.append('**Case data.** '
               + ('One reading enters the record in this phase.'
                  if len(rows) == 1
                  else f'{len(rows)} readings enter the record in this '
                       'phase.'))
    out.append('')
    for r in rows:
        line = (f'- **{fmt_date(r["date"], r["date_precision"])}** · '
                f'{sentence(r["headline"])}')
        if (r.get('detail') or '').strip():
            line += ' ' + sentence(r['detail'])
        out.append(line)
    out.append('')


def render_lag_table(links, out):
    resolved = [l for l in links if l.resolved]
    if not resolved:
        return
    out.append('| National or sector event | Date | UCL response | Date | Lag |')
    out.append('|---|---|---|---|---|')
    for l in sorted(resolved, key=lambda x: (x.counterpart['date'],
                                             x.ucl['date'])):
        out.append(f'| {cell(l.counterpart["headline"])} '
                   f'| {fmt_date(l.counterpart["date"])} '
                   f'| {cell(l.ucl["headline"])} '
                   f'| {fmt_date(l.ucl["date"])} '
                   f'| {fmt_lag(l.lag)} |')
    out.append('')
    out.append('A negative lag is UCL acting before the national measure, a '
               'positive lag is UCL acting after it.')
    out.append('')


# -------------------------------------------------------------------- render

def render(rows, cfg, draft=False):
    prefix = str(cfg.get('markdown.source_prefix',
                         '../home/uclcovid/data/updates/'))
    phases = build_phases(cfg)
    links = build_links(cfg, rows)
    lag_by_key = {row_key(l.ucl): fmt_lag(l.lag)
                  for l in links if l.resolved}

    unplaced = []
    for r in rows:
        d = date.fromisoformat(r['date'])
        for p in phases:
            if p.contains(d):
                p.rows.append(r)
                break
        else:
            unplaced.append(r)
    if unplaced:
        sys.exit(f'{len(unplaced)} rows fall outside every declared phase, '
                 f'the first being {unplaced[0]["date"]} '
                 f'{unplaced[0]["headline"]!r}')

    missing_framing = [p.name for p in phases if not (p.framing or '').strip()]
    if missing_framing and not draft:
        sys.exit('no framing prose for: ' + ', '.join(missing_framing)
                 + '\nWrite it into the [[phases]] tables in the config, or '
                   'run with --draft to see the shape first.')

    out = []
    render_front_matter(rows, phases, links, out)

    for p in phases:
        events = [r for r in p.rows if r['track'] != 'data']
        data = [r for r in p.rows if r['track'] == 'data']
        out.append(f'## {p.heading}')
        out.append('')
        # The declared window is the sectioning rule; the range the events
        # actually occupy is what the reader is looking at, and in the first
        # phase the two differ by more than two months.
        if events or data:
            covered = sorted(r['date'] for r in p.rows)
            occupied = (f'{fmt_date(covered[0])} to {fmt_date(covered[-1])}'
                        if covered[0] != covered[-1] else fmt_date(covered[0]))
            out.append(f'*Phase window {p.span()}. {plural(len(events), "event")}'
                       f' and {plural(len(data), "case-data reading")}, '
                       f'running {occupied}.*')
        else:
            out.append(f'*Phase window {p.span()}. No events in the ledger.*')
        out.append('')
        out.append(one_line(p.framing) if (p.framing or '').strip()
                   else DRAFT_MARKER)
        out.append('')
        render_lag_table([l for l in links
                          if l.resolved and p.contains(
                              date.fromisoformat(l.ucl['date']))], out)
        render_data_summary(data, out)

        month = None
        for r in sorted(events, key=lambda x: (x['date'], x['track'])):
            d = date.fromisoformat(r['date'])
            if (d.year, d.month) != month:
                month = (d.year, d.month)
                out.append(f'### {MONTHS[d.month - 1]} {d.year}')
                out.append('')
            render_entry(r, prefix, lag_by_key, out)

    render_pending(links, out)
    render_provenance(rows, cfg, out)
    return '\n'.join(out).rstrip() + '\n'


def render_front_matter(rows, phases, links, out):
    ucl = [r for r in rows if r['track'] == 'ucl']
    data = [r for r in rows if r['track'] == 'data']
    other = [r for r in rows if r['track'] in ('national', 'sector')]
    first = min(r['date'] for r in rows)
    last = max(r['date'] for r in rows)
    sources = len({r['source_ref'] for r in ucl})
    resolved = sum(1 for l in links if l.resolved)

    out.append(WARNING_MD)
    out.append('# UCL and the pandemic: a chronology')
    out.append('')
    docs = len({r['source_ref'] for r in other})
    out.append(f'{len(rows)} dated events between {fmt_date(first)} and '
               f'{fmt_date(last)}. {len(ucl)} of them are UCL\'s own '
               f'decisions, taken from {sources} of the 168 COVID-19 update '
               'newsletters it sent its staff and students; '
               f'{len(other)} are the national and sector measures those '
               f'decisions respond to, taken from {docs} retrieved primary '
               f'documents; and {len(data)} are readings from the case series '
               'UCL published between October 2020 and May 2022.')
    out.append('')
    out.append('Every event on the first two tracks carries a verbatim '
               'quotation from the document that announced it, and every one '
               'of those quotations is checked mechanically against the '
               'preserved source before this document is built. Nothing here '
               'rests on a recollection of what a source said.')
    out.append('')
    out.append('## How to read this')
    out.append('')
    out.append('Each entry states what UCL decided, when, and in what words. '
               'The date is the date of the event rather than the date of the '
               'newsletter, so a decision taken on a Friday and reported on '
               'the following Monday is filed under the Friday; the metadata '
               'line says which kind of date it is. **Announced** is the day '
               'the decision was made public, **took effect** the day it began '
               'to bind, **reported** the day the newsletter carried it '
               'without either being separable, and **observed** a measurement '
               'rather than a decision.')
    out.append('')
    out.append('The blockquote under each entry is the newsletter\'s own '
               'wording, not a summary of it. The paragraph above it is a '
               'plain-language reading of what was decided; the paragraph '
               'below it, where there is one, is context or a caveat that the '
               'newsletter itself does not supply. Where the two are in '
               'tension the quotation is the record and the paragraphs are '
               'commentary.')
    out.append('')
    if resolved:
        pending = len(links) - resolved
        line = ('Where a UCL action responds to a national or sector one, the '
                'two are shown side by side at the head of the phase with the '
                '**lag in days** between them. A negative lag is UCL moving '
                'before the national measure, a positive lag is UCL moving '
                f'after it. {resolved} of these pairings are measured.')
        if pending:
            line += (f' A further {pending} are declared but not measured, '
                     'because the national measure has not yet been '
                     'established from a primary source; they are listed at '
                     'the end rather than given a number that would look like '
                     'evidence.')
        out.append(line)
    else:
        out.append('The national and sector tracks are not yet built, so no '
                   'lag is stated anywhere in this document. '
                   f'{len(links)} correspondences between a UCL action and a '
                   'national one have been identified from the newsletters and '
                   'are listed at the end; each needs its national date '
                   'established from a primary source before a lag may be '
                   'computed from it. Until then this is a chronology of what '
                   'UCL did, with the national context named in the commentary '
                   'but not measured.')
    out.append('')
    out.append('## Contents')
    out.append('')
    for p in phases:
        events = [r for r in p.rows if r['track'] != 'data']
        # The occupied range rather than the declared window: the first phase
        # opens on 1 January 2020 and has nothing in it until 9 March, and a
        # contents list should say where the reader will actually land.
        covered = sorted(r['date'] for r in p.rows)
        where = (f'{fmt_date(covered[0])} to {fmt_date(covered[-1])}'
                 if covered else 'empty')
        out.append(f'{p.n}. [{p.name}](#{slug(p.heading)}) · {where} · '
                   f'{plural(len(events), "event")}')
    out.append('')
    groups = [('ucl', ucl),
              ('national', [r for r in other if r['track'] == 'national']),
              ('sector', [r for r in other if r['track'] == 'sector']),
              ('data', data)]
    # 'UCL' keeps its capitals mid-sentence; the other track names do not.
    def name(t):
        return 'UCL' if t == 'ucl' else t
    present = ', '.join(f'{len(g)} {name(t)}' for t, g in groups if g)
    absent = [name(t) for t, g in groups if not g]
    line = f'Tracks in this build: {present}.'
    if absent:
        line += (' Nothing yet on the ' + ' or '.join(absent)
                 + f' {"track" if len(absent) == 1 else "tracks"}.')
    out.append(line)
    out.append('')


def render_pending(links, out):
    pending = [l for l in links if not l.resolved]
    if not pending:
        return
    out.append('## National counterparts awaiting primary sources')
    out.append('')
    out.append('The newsletters name the national measures UCL was responding '
               'to, and those statements are quoted in the entries above. They '
               'are UCL\'s account of national policy, however, not the policy '
               'itself, and this project does not treat a date relayed by an '
               'interested party as established. Each pairing below is '
               'therefore declared but not measured: the lag will be computed '
               'and shown in the phase tables once the national event has been '
               'verified against a primary source. The provisional dates are '
               'shown so the reader can see what is being claimed and what is '
               'not yet evidenced.')
    out.append('')
    out.append('| National or sector measure | Provisional date | UCL response '
               '| Date |')
    out.append('|---|---|---|---|')
    for l in sorted(pending, key=Link.sort_key):
        when = (fmt_date(l.counterpart_date.isoformat())
                if l.counterpart_date else '*not yet established*')
        out.append(f'| {cell(l.label)} | {when} '
                   f'| {cell(l.ucl["headline"])} '
                   f'| {fmt_date(l.ucl["date"])} |')
    out.append('')
    undated = sum(1 for l in pending if l.counterpart_date is None)
    if undated:
        out.append(f'{undated} of these have no provisional date at all. The '
                   'newsletters make the dependency plain without dating the '
                   'measure they are responding to, and a date has not been '
                   'invented for them here.')
        out.append('')


def render_provenance(rows, cfg, out):
    ucl = [r for r in rows if r['track'] == 'ucl']
    out.append('## How this document was built')
    out.append('')
    out.append('This file is generated. Editing it by hand will not survive '
               'the next build, and no fact in it can be changed here: '
               'corrections belong in the ledger, `timeline.csv`, which is the '
               'table view of everything above and carries the same fields in '
               'the same order.')
    out.append('')
    out.append(f'`build/extract_text.py` converts the 168 preserved '
               'newsletters to text and takes each one\'s date from its own '
               'dateline rather than its filename, which three of them '
               'contradict. `build/validate.py` then checks every row in the '
               f'ledger: that its date parses and falls in range, that its '
               'fields take values from their enumerations, that its source '
               'file exists, and, for each of the '
               f'{len(ucl)} UCL rows, that its quotation is an exact substring '
               'of the text extracted from the newsletter it cites. That last '
               'check is the one that matters. A paraphrase fails it, a '
               'quotation attributed to the wrong issue fails it, and an '
               'invented quotation fails it. `build/render_md.py` writes this '
               'document from the ledger only after that check passes.')
    out.append('')
    out.append('**What the case figures do and do not measure.** They are '
               'confirmed cases reported to UCL, so they undercount by however '
               'much went unreported, and the on-campus marker records whether '
               'the person had been on campus while infectious rather than '
               'where they were infected. The series runs from 9 October 2020, '
               'which is seven months into the record above: for the whole of '
               'the first wave UCL was making decisions with no case data of '
               'its own at all.')
    out.append('')
    out.append(f'Ledger: `{cfg["paths.ledger"]}`. '
               f'Configuration: `{Path(cfg.source).name}`. '
               'Newsletters: `home/uclcovid/data/updates/`.')
    out.append('')


# ---------------------------------------------------------------------- main

def main():
    def opts(ap):
        ap.add_argument('--draft', action='store_true',
                        help='render with placeholders where framing prose is '
                             'not yet written, instead of failing')
        ap.add_argument('--stdout', action='store_true',
                        help='write to stdout instead of the output file')
    cfg, args = config.load(extra_args=opts)

    ledger = cfg.path('paths.ledger')
    if not ledger.exists():
        sys.exit(f'no ledger at {ledger}')
    rows, _ = load_rows(ledger)
    rows.sort(key=lambda r: (r['date'], r['track'], r['headline']))

    text = render(rows, cfg, draft=args.draft)

    if args.stdout:
        sys.stdout.write(text)
        return 0

    out_path = cfg.path('paths.markdown_out')
    out_path.write_text(text, encoding='utf-8')

    links = build_links(cfg, rows)
    print(f'wrote:    {out_path}')
    print(f'rows:     {len(rows)}')
    print(f'words:    {len(text.split()):,}')
    print(f'lines:    {text.count(chr(10)):,}')
    print(f'links:    {sum(1 for l in links if l.resolved)} resolved, '
          f'{sum(1 for l in links if not l.resolved)} pending a national row')
    if DRAFT_MARKER in text:
        print(f'DRAFT:    {text.count(DRAFT_MARKER)} phases have no framing '
              'prose')
    return 0


if __name__ == '__main__':
    sys.exit(main())
