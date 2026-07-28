#!/usr/bin/env python3
"""Tests for the stage 5 renderer, run against fixtures rather than the ledger.

The reason this file exists: on the real ledger the lag feature renders
nothing. Stage 2 has not run, so there are no `national` or `sector` rows for a
UCL action to be paired against, and every declared pairing comes out pending.
A feature that has never once produced output is not evidence that it works,
and the lag is the one number in the whole document that the renderer computes
rather than copies. So it is exercised here against a fixture ledger that does
have national rows in it, with the arithmetic and the signs checked.

The same fixtures cover the failure modes, because a check that cannot fail is
not a check: a pairing naming a UCL row that is not in the ledger, and a phase
with no framing prose, must both stop the build.

Standard library only. Usage:
    python3 test_render_md.py
"""
import csv
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
RENDER = HERE / 'render_md.py'

FIELDS = ['date', 'date_kind', 'date_precision', 'track', 'category',
          'headline', 'detail', 'quote', 'source_type', 'source_ref',
          'issue', 'verified', 'notes']


def row(date, track, headline, **kw):
    r = dict.fromkeys(FIELDS, '')
    r.update(date=date, track=track, headline=headline,
             date_kind=kw.get('date_kind', 'announced'),
             date_precision=kw.get('date_precision', 'day'),
             category=kw.get('category', 'restrictions'),
             detail=kw.get('detail', ''), quote=kw.get('quote', ''),
             source_type=kw.get('source_type', 'newsletter'),
             source_ref=kw.get('source_ref', '000_test.html'),
             issue=kw.get('issue', '1'),
             verified=kw.get('verified', 'quote-exact'),
             notes=kw.get('notes', ''))
    return r


# A ledger with both sides of several pairings present, which the real one does
# not yet have. Dates chosen so the three cases the plan cares about all appear:
# UCL ahead of the measure, UCL behind it, and a sector rather than national
# counterpart.
LEDGER = [
    row('2020-03-13', 'ucl', 'UCL stops face-to-face teaching',
        quote='Face-to-face teaching will cease.', category='teaching'),
    row('2020-03-23', 'national', 'The first national lockdown is announced',
        source_type='web', source_ref='https://example.invalid/lockdown',
        verified='primary-retrieved', issue=''),
    row('2020-03-24', 'ucl', 'UCL bars staff from campus',
        quote='Staff must not attend campus.'),
    row('2020-05-26', 'sector', 'The regulator sets its expectations',
        source_type='web', source_ref='https://example.invalid/ofs',
        verified='primary-retrieved', issue=''),
    row('2020-05-26', 'ucl', 'UCL brings its Term 1 planning forward',
        quote='We must decide now.', category='teaching'),
    row('2020-07-08', 'ucl', 'UCL keeps its own distancing rule',
        quote='We will continue to use a 2 metre guideline.'),
    row('2020-11-01', 'ucl', 'UCL stays open',
        quote='We will remain open.'),
    row('2021-01-15', 'data', 'A case-data reading',
        date_kind='observed', category='epidemiology', source_type='dataset',
        source_ref='covid_raw.csv', verified='computed', issue='',
        detail='Nine cases in January 2021.'),
]

CONFIG = '''
[paths]
ledger = "{ledger}"
markdown_out = "{out}"

[markdown]
source_prefix = "updates/"

[[phases]]
name = "First phase"
start = "2020-01-01"
framing = "Framing for the first phase."

[[phases]]
name = "Second phase"
start = "2020-09-01"
{second_framing}

[[links]]
ucl = "2020-03-13|UCL stops face-to-face teaching"
counterpart = "2020-03-23"
label = "The first national lockdown is announced"

[[links]]
ucl = "2020-03-24|UCL bars staff from campus"
counterpart = "2020-03-23"
label = "The first national lockdown is announced"

[[links]]
ucl = "2020-05-26|UCL brings its Term 1 planning forward"
counterpart = "2020-05-26"
track = "sector"
label = "The regulator sets its expectations"

[[links]]
ucl = "2020-11-01|UCL stays open"
counterpart = "2020-10-31"
label = "The second national lockdown is announced"

[[links]]
ucl = "2020-07-08|UCL keeps its own distancing rule"
label = "The government moves to one metre plus"
{stale}
'''

STALE_LINK = '''
[[links]]
ucl = "2020-03-13|A headline that is not in the ledger"
counterpart = "2020-03-23"
label = "Something"
'''

FAILURES = []


def check(name, ok, detail=''):
    print(f'{"pass" if ok else "FAIL"}  {name}' + (f'  {detail}' if detail else ''))
    if not ok:
        FAILURES.append(name)


def write_fixture(tmp, second_framing='framing = "Framing for the second."',
                  stale=''):
    ledger = tmp / 'fixture.csv'
    with open(ledger, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(LEDGER)
    out = tmp / 'FIXTURE.md'
    conf = tmp / 'fixture.toml'
    conf.write_text(CONFIG.format(ledger=ledger, out=out,
                                  second_framing=second_framing, stale=stale),
                    encoding='utf-8')
    return conf, out


def run(conf, *extra):
    return subprocess.run([sys.executable, str(RENDER), '--config', str(conf),
                           *extra],
                          capture_output=True, text=True)


def main():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        conf, out = write_fixture(tmp)

        proc = run(conf)
        check('renders a fixture ledger cleanly', proc.returncode == 0,
              proc.stderr.strip()[:200])
        if proc.returncode != 0:
            return 1
        text = out.read_text(encoding='utf-8')

        # 1. The lag, which is the only number the renderer computes.
        check('negative lag when UCL moves first',
              '| -10 days |' in text,
              '13 March against 23 March')
        check('positive lag when UCL follows',
              '| +1 day |' in text,
              'and singular "day", not "days"')
        check('a same-day response says so rather than reading "+0 days"',
              '| same day |' in text and '+0 day' not in text,
              'the sector pairing on 26 May')
        check('lag also appears on the entry itself',
              'lag **+1 day**' in text and 'lag **-10 days**' in text)

        # 2. Pairings that cannot be measured must not be measured.
        check('a counterpart absent from the ledger stays pending',
              'UCL stays open' in text.split('awaiting primary sources')[1],
              '31 October has no national row')
        check('an undated counterpart says so rather than guessing',
              '*not yet established*' in text)
        check('no lag is invented for a pending pairing',
              '| +1 days |' not in text and '| +2 days |' not in text)

        # 3. Structure.
        rows_in_tables = [l for l in text.splitlines()
                          if l.startswith('|') and not set(l) <= set('|- ')]
        widths = {l.count('|') for l in rows_in_tables}
        check('every table row has a consistent cell count',
              widths in ({5}, {5, 6}), f'pipe counts {sorted(widths)}')
        # The data row must appear in the phase's summary list and nowhere in
        # the dated entries, which is what "a summary line per phase rather
        # than interleaved row by row" means in practice.
        data_lines = [l for l in text.splitlines()
                      if 'A case-data reading' in l]
        check('the data track is summarised, not interleaved',
              len(data_lines) == 1 and data_lines[0].startswith('- **'),
              str(data_lines))
        check('a plural count reads as a plural and a single one does not',
              '1 event and 1 case-data reading,' in text
              and '6 events and 0 case-data readings,' in text)
        check('phase headings and contents anchors agree',
              '[First phase](#1-first-phase)' in text
              and '## 1. First phase' in text)

        # 4. Quotations survive the round trip byte for byte, since that is
        #    what stage 4 verified and what a reader will check against.
        quotes = [r['quote'] for r in LEDGER if r['quote']]
        missing = [q for q in quotes if f'> {q}' not in text]
        check('every quotation renders verbatim', not missing, str(missing[:2]))

        # 5. Failure modes. A check that cannot fail is not a check.
        conf2, _ = write_fixture(tmp, second_framing='')
        proc2 = run(conf2)
        check('a phase with no framing stops the build',
              proc2.returncode != 0 and 'framing' in proc2.stderr.lower())

        proc3 = run(conf2, '--draft')
        check('--draft renders it anyway, visibly marked',
              proc3.returncode == 0 and 'framing not yet written'
              in out.read_text(encoding='utf-8'))

        conf4, _ = write_fixture(tmp, stale=STALE_LINK)
        proc4 = run(conf4)
        check('a pairing naming a row that is not in the ledger stops the build',
              proc4.returncode != 0 and 'stale' in proc4.stderr.lower(),
              proc4.stderr.strip()[:120])

    check_real_output()
    check_html_output()

    print()
    if FAILURES:
        print(f'{len(FAILURES)} failed: ' + ', '.join(FAILURES))
        return 1
    print('all checks passed')
    return 0


def check_real_output():
    """The fixtures prove the renderer behaves; these prove the document it
    actually produced is intact. Skipped rather than failed when TIMELINE.md
    has not been built, so the fixture tests still run on a clean checkout."""
    import config
    cfg, _ = config.load(argv=[])
    out = cfg.path('paths.markdown_out')
    ledger = cfg.path('paths.ledger')
    if not out.exists() or not ledger.exists():
        print('skip  real-output checks (nothing rendered yet)')
        return
    print()
    text = out.read_text(encoding='utf-8')
    with open(ledger, newline='', encoding='utf-8') as fh:
        rows = list(csv.DictReader(fh))

    check('the rendered document has no draft placeholders',
          'framing not yet written' not in text)

    # The caveat is the most important text in the deliverable and the easiest
    # to lose in a refactor, so it is a check rather than a convention.
    head = text[:2500]
    check('TIMELINE.md opens with the AI-generated caveat',
          'AI-generated demonstration' in head
          and 'No human has checked it' in head
          and 'demonstration of what the underlying dataset makes possible' in head,
          'and before the title, not after it')

    # Every newsletter citation must resolve to a file that is actually there.
    prefix = str(cfg.get('markdown.source_prefix', ''))
    targets = re.findall(r'\]\(' + re.escape(prefix) + r'([^)]+)\)', text)
    updates = cfg.path('paths.updates')
    broken = sorted({t for t in targets if not (updates / t).exists()})
    check('every newsletter citation resolves to a file on disk',
          not broken, f'{len(targets)} links, broken: {broken[:3]}')

    # Every contents anchor must match a heading GitHub will generate.
    headings = {re.sub(r'[^\w\s-]', '', h.lower()).strip().replace(' ', '-')
                for h in re.findall(r'^## (.+)$', text, re.M)}
    anchors = set(re.findall(r'\]\(#([^)]+)\)', text))
    check('every contents anchor matches a heading',
          anchors <= headings, f'unmatched: {sorted(anchors - headings)}')

    # The load-bearing one: stage 4 verified these quotations against the
    # newsletters, so the renderer must not alter a single character of them.
    quotes = [q for q in (r['quote'].strip() for r in rows) if q]
    blocks = {l[2:].strip() for l in text.splitlines() if l.startswith('> ')}
    lost = [q for q in quotes if re.sub(r'\s+', ' ', q) not in blocks]
    check('every verified quotation reaches the document unaltered',
          not lost, f'{len(quotes)} quotations, {len(lost)} altered or missing')

    events = [r for r in rows if r['track'] != 'data']
    entries = len(re.findall(r'^\*\d{1,2} \w+ \d{4} · |^\*(?:week of|'
                             r'[A-Z][a-z]+ \d{4}) ', text, re.M))
    check('every non-data row is rendered as an entry',
          entries == len(events), f'{entries} entries for {len(events)} rows')

    # Per table, not across the document: the lag tables have five columns and
    # the pending-counterparts table four, and both are correct.
    blocks, current = [], []
    for line in text.splitlines():
        if line.startswith('|'):
            current.append(line)
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    ragged = [b[0][:60] for b in blocks
              if len({l.count('|') for l in b}) != 1]
    check('every table is internally consistent in its cell count',
          not ragged, f'{len(blocks)} tables, ragged: {ragged}')




def check_html_output():
    """Structural checks on the interactive page.

    These are the properties a screenshot cannot confirm and a reader cannot
    see: that the page reaches for nothing external, that no scraped string is
    ever concatenated into markup, and that no panel crops its own data. The
    last one is here because it happened — an axis whose top tick fell below
    the maximum drew the December 2021 peak out through the top of the plot,
    and only opening the page revealed it.
    """
    import config
    import render_html
    cfg, _ = config.load(argv=[])
    out = cfg.path('paths.html_out')
    if not out.exists():
        print('skip  html checks (nothing rendered yet)')
        return
    print()
    text = out.read_text(encoding='utf-8')

    # What this claims is that nothing is *loaded* from another host, and that
    # is what it now tests. It used to reject any external href at all, which
    # caught <a> as well — but a link is not a load: it fetches nothing, sends
    # nothing, and does not exist until a reader chooses it. The forms that do
    # load are src, an href on <link> (stylesheets, preconnect, icons), @import
    # and url(). Those stay forbidden; an anchor does not.
    loads_external = (
        re.search(r'\bsrc\s*=\s*"https?://', text)
        or re.search(r'<link\b[^>]*\bhref\s*=\s*"https?://', text, re.I)
        or re.search(r'@import|url\(\s*["\']?https?:', text))
    check('the page loads nothing from any external host', not loads_external)
    # The links it does carry are anchors and nothing else, so the distinction
    # above cannot quietly become a loophole.
    external = re.findall(r'<(\w+)\b[^>]*\bhref\s*=\s*"https?://[^"]*"', text)
    check('every external reference is a link a reader chooses to follow',
          set(external) <= {'a'}, f'elements carrying one: {sorted(set(external))}')
    check('the page issues no requests of its own',
          not re.search(r'\bfetch\s*\(|XMLHttpRequest|WebSocket|EventSource',
                        text))
    # Every quotation and headline on this page began as scraped UCL email.
    check('no scraped string can reach the DOM as markup',
          'innerHTML' not in text and 'outerHTML' not in text
          and 'insertAdjacentHTML' not in text and 'document.write' not in text)

    check('gridlines and axes are solid, never dashed',
          'dasharray' not in text)
    check('a legend is present and the table view is linked',
          'class="legend"' in text and 'href="TIMELINE.md"' in text
          and 'href="timeline.csv"' in text)
    check('the chart renders before any script runs',
          '<svg id="chart"' in text.split('<script')[0]
          and 'class="mark"' in text.split('<script')[0])
    check('the no-script path says what it is missing',
          '<noscript>' in text and 'needs JavaScript' in text)
    body = text[text.index('<main'):]
    check('the page carries the caveat above its own title',
          'AI-generated demonstration' in body
          and body.index('AI-generated demonstration') < body.index('<h1>')
          and 'No human has checked it' in body)

    # No axis may crop its own series. nice_ticks is the function that got this
    # wrong; check it directly across the range the page actually plots, plus
    # the awkward values around a decade boundary.
    bad = [hi for hi in (1, 7, 9, 10, 11, 99, 100, 101, 131, 159, 525, 696,
                         1000, 1001, 5922, 9999, 11211)
           if render_html.nice_ticks(hi)[-1] < hi
           or render_html.nice_ticks(hi, 3)[-1] < hi]
    check('no axis top tick ever falls below the data it must show',
          not bad, f'cropped at: {bad}')

    check('every categorical hue is a validated slot',
          len(set(re.findall(r'--series-\d:\s*(#[0-9a-f]{6})', text))) == 8,
          'four light steps and four dark ones, no others')

    # A missing reading must break the line, not be joined across. The server
    # drew one continuous path per series while the script broke on null, so
    # the no-script rendering — which is also every reader's first paint —
    # asserted a week the published series does not report.
    cases = json.loads(
        re.search(r'id="payload">(.*?)</script>', text, re.S).group(1))['cases']
    gaps = sum(1 for r in cases if any(v is None for v in r[1:]))
    starts = [d.count('M') for d in
              re.findall(r'class="series"[^>]*d="(M[^"]+)"', text)
              or re.findall(r'd="(M[^"]+)"[^>]*class="series"', text)]
    check('a gap in the series breaks the line rather than joining across it',
          bool(starts) and all(n >= gaps + 1 for n in starts),
          f'{gaps} gap(s), subpaths per series: {starts}')

    # The background shading is ordinal, so its only job is to be read in
    # order. A step out of sequence would say a lockdown was looser than the
    # tiers, which no legend or label could correct, and swapping two hexes is
    # exactly the edit that would do it silently.
    def lum(h):
        def ch(v):
            v = int(h[v:v + 2], 16) / 255
            return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
        return 0.2126 * ch(1) + 0.7152 * ch(3) + 0.0722 * ch(5)

    ramps = [[m[i] for i in range(3)] for m in
             [re.findall(r'--band-\d:\s*(#[0-9a-f]{6})', block)
              for block in text.split('--surface-1')[1:4]]]
    surfaces = re.findall(r'--surface-1:\s*(#[0-9a-f]{6})', text)
    steps_ok = len(ramps) == 3 and all(len(r) == 3 for r in ramps)
    if steps_ok:
        for ramp, surface in zip(ramps, surfaces):
            # Away from the surface, one direction, no repeats. Which direction
            # is the mode's business; that it never doubles back is not.
            d = [lum(c) - lum(surface) for c in ramp]
            steps_ok = steps_ok and (all(v < 0 for v in d)
                                     or all(v > 0 for v in d))
            steps_ok = steps_ok and abs(d[0]) < abs(d[1]) < abs(d[2])
    check('the restriction shading is one ordered ramp per mode', steps_ok,
          'three steps, monotonically away from the surface')

    # --- the touch paths.
    #
    # What these interactions actually do is checked in test_browser.py, which
    # needs a browser to see it: both faults it exists for were in the
    # arbitration between the browser and the script, and the page reads
    # correctly with either of them in place. Held here are the declarations
    # that whole file rests on, so dropping one fails the suite that always
    # runs rather than the one that needs installing.
    js = re.search(r'<script>(.*?)</script>', text, re.S).group(1)

    # The lane rule is painted over the lane's hit rect, along the exact line
    # the marks sit on. While it took pointers, a fingertip aimed at a mark hit
    # the rule and the lane's handlers never ran: no tooltip, on any mark, on
    # any phone.
    check('nothing drawn inside a lane can take a pointer from it',
          bool(re.search(r'\.lane-rule\s*\{[^}]*pointer-events:\s*none', text)))
    # Without this the browser keeps the two-finger gesture for its own zoom
    # and the script is never given the pinch.
    check("the chart declines the browser's pinch and keeps one-finger pan",
          bool(re.search(r'\bsvg\s*\{[^}]*touch-action:\s*pan-x pan-y', text)))
    # A pointer that cannot hover is destroyed when it is lifted, and the
    # browser fires pointerout and pointerleave straight after the pointerup
    # that ended it. A pointerleave handler that does not say "mouse" therefore
    # runs on every tap, one event after the tap opened the tooltip, and takes
    # it back down before a frame has been painted with it.
    leaves = [js[m.end():m.end() + 240]
              for m in re.finditer(r"addEventListener\('pointerleave'", js)]
    check('no pointerleave undoes the tap that came immediately before it',
          bool(leaves) and all("pointerType !== 'mouse'" in tail
                               for tail in leaves),
          f'{len(leaves)} pointerleave handler(s)')
    # Drag, pinch and the date boxes all set the same range, and a floor that
    # moves with the control used is three different charts.
    check('one floor for the shortest range every control can set',
          js.count('MIN_SPAN') >= 4, f'{js.count("MIN_SPAN")} uses')
    # The page prints different instructions by input, which is only worth
    # doing while both describe something that is actually there.
    touch_text = ' '.join(re.findall(r'<span class="touch-only">(.*?)</span>',
                                     text, re.S)).lower()
    check('the instructions for touch name gestures the script implements',
          'tap any mark' in touch_text and 'pinch' in touch_text
          and 'applyPinch' in js and 'setPointerCapture' in js)

    # Shading that the reader has no way to name is decoration. Every level
    # drawn has to appear in the legend under the figure.
    drawn = {int(n) for n in re.findall(r'class="band band-(\d)"', text)}
    named = {i for i in range(4)
             if f'class="swatch lvl-{i}"' in text}
    check('every shading step drawn is named in the legend',
          drawn and drawn <= named,
          f'drawn {sorted(drawn)}, named {sorted(named)}')

if __name__ == '__main__':
    sys.exit(main())
