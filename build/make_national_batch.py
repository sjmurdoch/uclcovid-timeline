#!/usr/bin/env python3
"""Build the national and sector batch, taking each quotation from the cache.

Every quotation below is identified by a plain-ASCII anchor rather than typed
out, and the exact span is then lifted from the cached primary source. The
sources are PDFs full of curly quotes, en rules and, in reference 11, a font
encoding that pdftotext cannot always map. Transcribing by hand would introduce
errors that look exactly like fabrication to the validator, and correcting them
by hand would risk quietly editing a quotation to make a check pass. Lifting
the span means the quotation is the source's wording by construction.

`start` and `end` are ASCII fragments that must each occur exactly once in the
normalised source text. The emitted quote runs from the beginning of `start` to
the end of `end`. If either is missing or ambiguous the row is not written and
the script exits non-zero, so a batch is never half-built.

Usage:
    python3 make_national_batch.py [--out batches/batch-national-01.json]
"""
import csv
import json
import re
import sys

import config
from extract_text import normalise

IFG_2021 = ('https://www.instituteforgovernment.org.uk/sites/default/files/'
            'timeline-lockdown-web.pdf')
IFG_DEC21 = ('https://www.instituteforgovernment.org.uk/sites/default/files/'
             '2022-12/timeline-coronavirus-lockdown-december-2021.pdf')
DFE_XMAS = ('https://www.gov.uk/government/news/'
            'christmasguidance-set-out-for-university-students')
# Not in the research synthesis' works-cited list. Stage 1 dated this from a
# UCL newsletter; reference 7 turned out to give 15 June 2020 as the day
# non-essential shops reopened, which is true and is a different fact, so the
# date was withdrawn until it could be evidenced. The statutory instrument
# settles it.
SI_FACE_TRANSPORT = 'https://www.legislation.gov.uk/uksi/2020/592/made'
# The instrument that sets the final expiry of the Plan B face covering
# requirement, by amending regulation 15 of SI 2021/1340.
SI_PLAN_B_EXPIRY = 'https://www.legislation.gov.uk/uksi/2021/1400/made'
# Two claims stage 1 recorded as relayed by UCL and flagged not to be repeated
# as established. Both now check out against the body that made them.
ONS_ETHNICITY = ('https://www.ons.gov.uk/peoplepopulationandcommunity/'
                 'birthsdeathsandmarriages/deaths/articles/'
                 'coronavirusrelateddeathsbyethnicgroupenglandandwales/'
                 '2march2020to10april2020')
AMS_WINTER = 'https://acmedsci.ac.uk/file-download/51353957'
HOC_TIMELINE = ('https://commonslibrary.parliament.uk/'
                'house-of-commons-coronavirus-timeline/')

# The scope test from the plan: a national event earns a row when UCL responded
# to it, when it constrained UCL, or when it explains a visible feature of the
# case data. Eat Out to Help Out is in the sources and is not here.
ROWS = [
    dict(date='2020-03-18', kind='announced', track='national', cat='teaching',
         headline='The Prime Minister announces the closure of schools for most pupils',
         src=HOC_TIMELINE, start='announcing closure of schools',
         end='for most pupils from 23 March',
         detail='Schools closed at the end of Friday 20 March and did not '
                'reopen on Monday 23 March, which is why the newsletters and '
                'this source date the same measure differently.',
         notes='UCL restricted its Day Nursery to national-interest and '
               'essential staff the next day, a lag of one. The UCL note '
               'described this as closure "by 20 March" and the Commons '
               'Library timeline as closure "from 23 March"; both describe '
               'the same break, from opposite ends of the weekend.'),
    dict(date='2020-03-23', kind='announced', track='national', cat='restrictions',
         headline='The Prime Minister announces the first national lockdown',
         src=IFG_2021, start='PM announces the first', end='stay at home',
         detail='Announced on the evening of 23 March; the measures became law '
                'three days later.',
         notes='The counterpart for five UCL rows, and the anchor of the lag '
               'analysis in both directions. UCL had already stopped '
               'face-to-face teaching ten days earlier and barred staff from '
               'campus the day after this.'),
    dict(date='2020-03-26', kind='effective', track='national', cat='restrictions',
         headline='The first lockdown measures come into force',
         src=IFG_2021, start='Lockdown measures', end='legally come into force',
         detail='Three days after the announcement.',
         notes='The gap between announcement and legal force is why the ledger '
               'separates announced from effective dates.'),
    dict(date='2020-05-10', kind='announced', track='national', cat='restrictions',
         headline='The Prime Minister announces a conditional plan for lifting the lockdown',
         src=IFG_2021, start='PM announces a conditional plan',
         end='but avoid public transport',
         detail='The first easing of the first lockdown, including a return to '
                'the workplace for those who could not work from home.',
         notes='UCL diverged from this the next day, asking staff not to return '
               'to campus. That is the clearest case in the record of UCL '
               'declining an easing rather than following one.'),
    dict(date='2020-06-01', kind='effective', track='national', cat='teaching',
         headline='Schools in England begin a phased reopening',
         src=IFG_2021, start='Phased re-opening of schools',
         end='schools in England',
         detail='The date UCL aligned its first campus reopening pilots with.',
         notes='UCL said on 26 May that it had aligned its pilot activity with '
               'the proposed dates for schools to return, which makes this a '
               'dependency of a UCL timetable on a national schools decision.'),
    dict(date='2020-06-23', kind='announced', track='national', cat='restrictions',
         headline='The Prime Minister announces a relaxing of the 2 metre distancing rule',
         src=IFG_2021, scope='23 June', start='PM says UK',
         end='2m social distancing rule',
         detail='The move that became the "1 metre plus" guidance, taking '
                'effect with the wider easing of 4 July.',
         notes='The source records a relaxing of the 2 metre rule and does not '
               'use the phrase "one metre plus"; the headline follows the '
               'source rather than UCL\'s wording for it. UCL kept 2 metres for '
               'Term 1 timetable planning, which is the sharpest deliberate '
               'divergence in the whole record.'),
    dict(date='2020-06-15', kind='effective', track='national', cat='restrictions',
         headline='Face coverings become mandatory on public transport in England',
         src=SI_FACE_TRANSPORT, scope='Citation, commencement',
         scope_end='Interpretation',
         start='These Regulations come into force',
         end='come into force on 15th June 2020',
         detail='The Health Protection (Coronavirus, Wearing of Face '
                'Coverings on Public Transport) (England) Regulations 2020, '
                'SI 2020/592.',
         notes='UCL had required face coverings on campus where distancing '
               'was not possible from 22 May, twenty-four days before this. '
               'The date was carried for a while on a UCL newsletter\'s '
               'authority and then withdrawn, because reference 7 gives 15 '
               'June as the day non-essential shops reopened and says nothing '
               'about transport. Both are true of that day; the regulations '
               'are what establish the second.'),
    dict(date='2022-01-26', kind='effective', track='national', cat='restrictions',
         headline='The Plan B face covering requirement in England expires',
         src=SI_PLAN_B_EXPIRY, start='They also extend the period',
         end='until 26th January 2022',
         detail='SI 2021/1400 amends regulation 15 of the Plan B face '
                'covering regulations, substituting 26th January 2022 for '
                '20th December 2021, so the requirement lapses at the end of '
                'that day.',
         notes='UCL kept face coverings mandatory on the day the legal '
               'requirement ended and narrowed them to teaching settings '
               'twenty-six days later. This is the second time the record '
               'shows UCL holding a measure after the law dropped it, the '
               'first being step 4 in July 2021.'),
    dict(date='2020-05-07', kind='published', track='national', cat='epidemiology',
         headline='ONS finds Black adults far likelier to die of COVID-19 after adjusting for age',
         src=ONS_ETHNICITY, start='When taking into account age in the analysis',
         end='times more likely than White ethnicity males and females',
         detail='Deaths from 2 March to 10 April 2020 in England and Wales. '
                'The published figures are 4.2 for Black males and 4.3 for '
                'Black females against White males and females.',
         notes='UCL relayed this on 2 June 2020 and stage 1 flagged it as not '
               'to be repeated until the primary source was checked. It '
               'checks out: UCL\'s "four times" is a fair reading of 4.2 and '
               '4.3. The ONS analysis adjusts for age only; the publication '
               'is explicit that it does not by itself establish cause.'),
    dict(date='2020-07-14', kind='published', track='national', cat='epidemiology',
         headline='Advisory report models an Rt of 1.7 from September as its worst-case scenario',
         src=AMS_WINTER, start='The model assumes that Rt rises',
         end='The model assumes that Rt rises to 1.7 from September 2020',
         detail='"Preparing for a challenging winter 2020/21", produced at '
                'the request of the Government Chief Scientific Adviser.',
         notes='UCL relayed this on 16 July 2020 and stage 1 flagged the Rt '
               'figure as not to be repeated until checked. It checks out, '
               'with a distinction worth keeping: 1.7 is an assumption the '
               'model was run under to explore a reasonable worst case, not '
               'a forecast of what Rt would be. Reporting it as a prediction '
               'would misstate what the report did.'),
    dict(date='2020-06-29', kind='announced', track='national', cat='restrictions',
         headline='The first local lockdown is announced for Leicester',
         src=IFG_2021, scope='29 June', scope_end='4 July',
         start='Matt Hancock', end='parts of Leicestershire',
         detail='Announced by the Secretary of State for Health and Social Care.',
         notes='UCL cited this on 8 July as a reason for caution in its own '
               'planning.'),
    dict(date='2020-07-04', kind='effective', track='national', cat='restrictions',
         headline='The first local lockdown comes into force in Leicester',
         src=IFG_2021, scope='4 July', scope_end='18 July', start='UK',
         end='reopening of pubs, restaurants, hairdressers.',
         detail='The same day as the wider easing in the rest of England.',
         notes='The two limbs of this entry are why 4 July is the phase '
               'boundary in this chronology: England eased and one city did '
               'not.'),
    dict(date='2020-09-14', kind='effective', track='national', cat='restrictions',
         headline='The rule of six bans social gatherings above six in England',
         src=IFG_2021, start='Rule of six', end='above six banned in England',
         detail='Applied indoors and outdoors.',
         notes='UCL noted it on 9 September while saying it had not yet decided '
               'what to do, which is rare candour in the record.'),
    dict(date='2020-10-14', kind='effective', track='national', cat='restrictions',
         headline='A three-tier system of restrictions starts in England',
         src=IFG_2021, start='A new three-tier system',
         end='restrictions starts in England',
         detail='London moved to Tier 2 on 17 October and UCL stayed open.',
         notes='The tier system is the mechanism by which national policy '
               'reached UCL geographically rather than sectorally.'),
    dict(date='2020-10-31', kind='announced', track='national', cat='restrictions',
         headline='The Prime Minister announces a second national lockdown for England',
         src=IFG_2021, start='PM announces a second lockdown',
         end='for the NHS',
         detail='Announced on a Saturday; the measures came into force on 5 '
                'November.',
         notes='This source does not say that universities were to stay open. '
               'That is UCL\'s account of the policy, recorded in the UCL row '
               'of 1 November, and it still needs a primary source of its own. '
               'The distinction matters because the exemption is the reason the '
               'case series behaves differently in the two lockdowns.'),
    dict(date='2020-11-05', kind='effective', track='national', cat='restrictions',
         headline='The second national lockdown comes into force in England',
         src=IFG_2021, start='Second national lockdown comes into force',
         end='into force in England',
         detail='A four-week closure of non-essential retail, with educational '
                'settings treated differently from the first lockdown.',
         notes=''),
    dict(date='2020-11-11', kind='announced', track='sector', cat='teaching',
         headline='The Department for Education publishes Christmas travel guidance for students',
         src=DFE_XMAS, start='University students will be able to travel home',
         end='new Government guidance published today.',
         detail='Published by the Department for Education and the Minister of '
                'State for Universities.',
         notes='The sector-specific counterpart to the second lockdown, and the '
               'reason UCL restricted travel to essential journeys until 2 '
               'December.'),
    dict(date='2020-12-02', kind='effective', track='national', cat='restrictions',
         headline='The second lockdown ends and England returns to the tier system',
         src=IFG_2021, start='Second lockdown ends after four weeks',
         end='three-tier system of restrictions',
         detail='London returned to Tier 2.',
         notes=''),
    dict(date='2020-12-03', kind='effective', track='sector', cat='teaching',
         headline='The student travel window opens',
         src=DFE_XMAS, start='From 3 December to 9 December',
         end='pressure on transport infrastructure.',
         detail='A six-day window with staggered departure dates set by each '
                'university.',
         notes='A national policy written specifically for universities, and one '
               'of the few that treats the student population as an '
               'epidemiological object in its own right.'),
    dict(date='2020-12-19', kind='announced', track='national', cat='restrictions',
         headline='Tier 4 announced for London and the South East',
         src=IFG_2021, start='PM announces tougher restrictions',
         end='Christmas mixing rules tightened.',
         detail='A new "Stay at Home" alert level, with the planned Christmas '
                'relaxation cut short.',
         notes='The start of the phase in which UCL\'s January 2021 rise '
               'occurs. Attributing that rise to the Alpha variant is an '
               'epidemiological claim none of the cached sources makes, so it '
               'is not made here: what the ledger supports is that the '
               'restrictions tightened and the figures rose.'),
    dict(date='2021-01-06', kind='effective', track='national', cat='restrictions',
         headline='England enters the third national lockdown',
         src=IFG_2021, start='England enters', end='third national lockdown',
         detail='Announced by the Prime Minister on the evening of 4 January '
                'and in force from 6 January.',
         notes='UCL responded on 5 January, between the announcement and the '
               'legal commencement. The ledger dates this row to the date this '
               'source gives, which is the commencement.'),
    dict(date='2021-02-22', kind='announced', track='national', cat='restrictions',
         headline='The government publishes the roadmap out of lockdown',
         src=IFG_DEC21, start='PM publishes', end='for lifting the lockdown',
         detail='Four steps, replacing the regional tier system with uniform '
                'national easing.',
         notes='UCL published its own roadmap tracking these four steps on 23 '
               'March 2021.'),
    dict(date='2021-06-14', kind='announced', track='national', cat='restrictions',
         headline='Step 4 of the roadmap delayed by four weeks to 19 July',
         src=IFG_DEC21, start='delayed by four weeks',
         end='accelerates the vaccination programme.',
         detail='Delayed in response to the Delta variant.',
         notes='UCL\'s return timetable slipped with it, which is the clearest '
               'case in the record of a UCL date moving purely because a '
               'national date moved.'),
    dict(date='2021-07-19', kind='effective', track='national', cat='restrictions',
         headline='Step 4 removes most legal limits on social contact in England',
         src=IFG_DEC21, start='Most legal limits on social contact',
         end='social contact removed',
         detail='The end of the legal requirements, including distancing and '
                'face coverings.',
         notes='UCL kept face coverings in all indoor spaces a week later, and '
               'this ends the 2 metre rule UCL had held since 8 July 2020.'),
    dict(date='2021-12-08', kind='announced', track='national', cat='restrictions',
         headline='The government announces a move to Plan B measures in England',
         src=IFG_DEC21, start='PM announces a move',
         end='spread of the Omicron variant.',
         detail='Guidance to work from home, with face coverings and the NHS '
                'Covid Pass.',
         notes='This source does not record the higher education exemption. '
               'That is UCL\'s account, and it is the reason UCL stayed open '
               'through the highest case counts in the whole series.'),
    dict(date='2021-12-10', kind='effective', track='national', cat='restrictions',
         headline='Face masks become compulsory in most indoor venues under Plan B',
         src=IFG_DEC21, start='Face masks become compulsory',
         end='indoor venues under Plan B.',
         detail='',
         notes='UCL had made face coverings mandatory indoors on campus on 30 '
               'November, ten days ahead of this.'),
]


def load_sources(cfg):
    sdir = config.ROOT / str(cfg.get('sources.cache', 'sources'))
    manifest = sdir / 'manifest.csv'
    if not manifest.exists():
        sys.exit(f'no source cache at {manifest}; run build/fetch_sources.py')
    out = {}
    with open(manifest, newline='', encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            if r.get('text'):
                p = sdir / r['text']
                if p.exists():
                    out[r['url']] = normalise(p.read_text(encoding='utf-8'))
    return out


SCOPE_WINDOW = 400


def lift(text, start, end, where, scope=None, scope_end=None):
    """The exact span between two unambiguous anchors, or a loud failure.

    `scope` narrows the search to one entry of a dated timeline before the
    anchors are applied. Both Institute for Government references repeat
    phrases across entries: "parts of Leicestershire" appears in the 29 June
    announcement and again in the 4 July commencement, and "PM says UK" opens
    two separate entries. Scoping to the date line is what makes each
    quotation unambiguously the one intended.
    """
    offset = 0
    if scope is not None:
        n = text.count(scope)
        if n != 1:
            return None, (f'{where}: scope anchor {scope!r} occurs {n} times, '
                          'expected exactly once')
        offset = text.index(scope)
        # Consecutive entries reuse whole phrases: the 29 June announcement and
        # the 4 July commencement both end "Leicester and parts of
        # Leicestershire", within 250 characters of each other. `scope_end`
        # cuts at the next entry so the window really is one entry.
        stop = (text.index(scope_end, offset) if scope_end
                and scope_end in text[offset:] else offset + SCOPE_WINDOW)
        text = text[offset:stop]

    problems = []
    for label, anchor in (('start', start), ('end', end)):
        n = text.count(anchor)
        if n == 0:
            problems.append(f'{label} anchor {anchor!r} not found'
                            + (' within the scoped window' if scope else ''))
        elif n > 1:
            problems.append(f'{label} anchor {anchor!r} occurs {n} times')
    if problems:
        return None, f'{where}: ' + '; '.join(problems)
    i = text.index(start)
    # `text.index(end, i)` searches forward from i, so it can only ever return
    # j >= i — the guard that used to sit here could not run. The case it was
    # written for is real, though: both anchors occur exactly once (checked
    # above) and the end anchor lies before the start. That made index() raise,
    # and the ValueError travelled out of main() as a traceback naming neither
    # the row nor the anchor, against a docstring promising a loud failure and
    # no half-built batch. Detected rather than raised, and returned as one more
    # collected problem.
    if end not in text[i:]:
        return None, (f'{where}: end anchor {end!r} occurs before the start '
                      f'anchor {start!r}, so they do not bound a span')
    j = text.index(end, i)
    k = j + len(end)
    # The anchors are ASCII, so a span that begins or ends at a quoted phrase
    # would be clipped at the curly quotation marks around it: "ordering people
    # to “stay at home" rather than "…“stay at home”". Extend over the matching
    # punctuation so the quotation closes as the source closes it.
    while i > 0 and text[i - 1] in '“‘"\'':
        i -= 1
    while k < len(text) and text[k] in '”’"\'':
        k += 1
    return text[i:k], None


def main():
    def opts(ap):
        ap.add_argument('--out', default='batches/batch-national-01.json')
    cfg, args = config.load(extra_args=opts)
    sources = load_sources(cfg)

    batch, errors = [], []
    for spec in ROWS:
        text = sources.get(spec['src'])
        if text is None:
            errors.append(f'{spec["date"]}: {spec["src"]} is not cached')
            continue
        quote, err = lift(text, spec['start'], spec['end'],
                          f'{spec["date"]} {spec["headline"][:40]}',
                          scope=spec.get('scope'),
                          scope_end=spec.get('scope_end'))
        if err:
            errors.append(err)
            continue
        batch.append({
            'date': spec['date'],
            'date_kind': spec['kind'],
            'date_precision': 'day',
            'track': spec['track'],
            'category': spec['cat'],
            'headline': spec['headline'],
            'detail': spec['detail'],
            'quote': quote,
            'source_type': 'web',
            'source_ref': spec['src'],
            'issue': '',
            'verified': 'primary-retrieved',
            'notes': spec['notes'],
        })

    if errors:
        print('\n'.join(errors), file=sys.stderr)
        sys.exit(f'\n{len(errors)} anchors did not resolve; batch not written')

    out = config.ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(batch, indent=2, ensure_ascii=False) + '\n',
                   encoding='utf-8')
    by_track = {}
    for r in batch:
        by_track[r['track']] = by_track.get(r['track'], 0) + 1
    print(f'wrote {len(batch)} rows to {out}')
    print('by track: ' + ', '.join(f'{k} {v}' for k, v in sorted(by_track.items())))
    print('quotations lifted from the cache, none transcribed by hand')
    return 0


if __name__ == '__main__':
    sys.exit(main())
