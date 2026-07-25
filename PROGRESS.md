# Build progress

Written by hand as each stage closes, so a cold resume knows where it stopped. Stage numbers refer to `../TIMELINE-PLAN.md` section 4.

## Stage 0 — scaffolding and text extraction — **done**

Ran `python3 build/extract_text.py` from `timeline/`. Exit 0.

```
newsletters read:      168
text files written:    168
total characters:      1,094,598
body date found:       168
filename carries year: 37
agreement:             164 yes, 0 no, 1 reviewed, 3 n/a
```

Gate, checked rather than asserted:

- 168 text files under `text/`, `index.csv` has 168 rows.
- Body date found in all 168 files.
- Zero disagreements on the rows where the filename carries a year.
- Body dates run 2020-03-09 to 2022-05-04 and are monotonic in file order but for one inversion, explained below.
- Issue numbers run 1 to 165 across 165 files, strictly increasing, with three special editions carrying none — matching the plan's trap about file index not being issue number.
- Extraction is deterministic: two consecutive runs produce an identical digest over all 169 outputs (`48e890a6f1f29d039da91e60274275b8`).

### Three things the extraction settled

**1. The date is below the "View in browser" link, not at the top of the file.** The first date in the document is the email's subject or preheader and is not reliable. Issue 75 carries "Friday 26 June 2020" over a newsletter sent Monday 29 June; both parts of the 5 November special edition carry the date the restrictions began rather than the date they were written. The line below the link is the newsletter's own dateline and is correct in all 168 files. Taking the first date anywhere in the file would have filed three newsletters under the wrong date, two of them in the week the second lockdown was announced — precisely where the lag analysis is most sensitive.

**2. UCL's own index page misdates issue 122.** It is titled "Update: 3 November", and the filename inherits that. The body says "Monday 2 November 2020" twice, 2 November 2020 was a Monday, and the weekly cadence either side runs 19 October, 26 October, 9 November — all Mondays. The body date is used and the reasoning is recorded in `REVIEWED` in `build/extract_text.py`.

**3. Files 122 and 124 are the same newsletter.** They are byte-identical (`74435e3020…`) and the manifest gives them the **same source URL**. UCL's index page lists "…from 5 November 2020" and "…from 5 November 2020 – Part 2" as separate entries, but both links resolve to one message. This is the only duplicate in the corpus: 168 files, 167 distinct newsletters, one duplicated source URL, one duplicated content hash.

Consequences for the ledger: the Provost's message of Sunday 1 November 2020 gets **one** `ucl` row, sourced to `122_…`, not two. Stage 4's duplicate check must not be confused by the two filenames, and the plan's trap list needs correcting — it assumed two distinct parts.

The single non-monotonic date is this duplicate: file 124 is dated 1 November and sits after file 123, dated 2 November. Not an error in the data, an artefact of the index ordering.

## Stage 4 — validator — **written and exercised**

`build/validate.py`, plus `build/config.py` (TOML with environment and CLI overrides) and `build/add_rows.py` (JSON batch appends, so quoting cannot corrupt a quotation).

The validator was tested against a deliberately broken fixture before being trusted, because a check that has never failed is not evidence of anything. All of these fire: fabricated quote, out-of-range date, bad `track` and `category` enums, `ucl` row with no quote, non-URL web ref, missing newsletter file, `unverified` with no explanatory note, over-long headline, exact duplicate row, wrong issue number, and a citation marker `[7]` followed by `(` — the Markdown-link collision the plan asked for a test case on. Bare `[7]` and `[9]` correctly pass.

**One check was wrong and has been corrected.** It originally required issue numbers to increase with row date. That fails on correct data: a row is filed under the date of the *event*, which may precede the newsletter reporting it — the first-year assessment cancellation happened on 20 March 2020 and is reported in issue 11 of 23 March. The check now verifies a row's `issue` against the issue number of its `source_ref` as recorded in `text/index.csv`, which is the real invariant and a stronger test.

## Stage 1 — the UCL track — **done, 283 rows**

| Batch | Files | Dates | Rows |
|---|---|---|---|
| 1 | 000–013 | 2020-03-09 to 2020-03-25 | 40 |
| 2 | 014–027 | 2020-03-26 to 2020-04-20 | 26 |
| 3 | 028–041 | 2020-04-21 to 2020-05-11 | 21 |
| 4 | 042–055 | 2020-05-12 to 2020-06-01 | 21 |
| 5 | 056–069 | 2020-06-02 to 2020-06-19 | 18 |
| 6 | 070–083 | 2020-06-22 to 2020-07-09 | 18 |
| 7 | 084–097 | 2020-07-10 to 2020-07-29 | 16 |
| 8 | 098–111 | 2020-07-30 to 2020-09-14 | 24 |
| 9 | 112–125 | 2020-09-16 to 2020-11-09 | 29 |
| 10 | 126–139 | 2020-11-16 to 2021-03-23 | 23 |
| 11 | 140–153 | 2021-03-30 to 2021-09-29 | 23 |
| 12 | 154–167 | 2021-10-11 to 2022-05-04 | 24 |

Validator clean after every batch. Final: **283 rows, 0 errors, 0 warnings, every quotation verified as an exact substring of its source.**

Distribution: 279 day-precise, 1 week, 1 month. By kind, 131 `announced`, 75 `published`, 70 `effective`, 5 `observed`. By category, `restrictions` 77, `governance` 49, `teaching` 40, `testing` 23, `research` 21, `epidemiology` 16, `civic` 15, `assessment` 14, `wellbeing` 13, `accommodation` 8, `vaccination` 5. By year, 218 rows in 2020, 50 in 2021, 15 in 2022 — which tracks the newsletter cadence rather than the pandemic.

**Gate check.** 133 of the 168 newsletters carry at least one row. The other 35 were judged to contain no warranted decision, and that judgement was tested rather than asserted: a scan of the uncited files for decision-signalling language ("we have decided", "with immediate effect", "from Monday", "will now be required") flagged only three. Two were restatements already captured from the issue that announced them. The third, issue 105 of 19 August 2020, was a genuine miss and its two rows — the fieldwork framework and the four-stage Campus Opening Guide — were added as `batches/batch-08b.json`. One of the remaining uncited files is `124_…Part_2`, the duplicate, which is why 133 rather than 134 distinct newsletters are cited: the figure of 134 recorded here originally counted that file twice and was corrected during the stage 7 gate check.

**To resume or redo:** read `digest/batches/batch-NN.txt`, write `batches/batch-NN.json`, then `python3 build/add_rows.py batches/batch-NN.json && python3 build/validate.py` from `timeline/`. A batch can be redone in place with `--replace-source-refs` without disturbing the rest of the ledger.

### The digest, and why reading it is not a shortcut

`build/digest.py` writes `digest/`, a reduced copy of the corpus at 64% of the original character count, and `digest/batches/batch-NN.txt` groups it into the twelve reading batches. It drops paragraphs that repeat across issues — the Care First paragraph, the askUCL sign-off, the daily page-visit counts, the contents list that restates the section headings — while always keeping a paragraph's **first** appearance. That is the plan's own inclusion test made mechanical: recurring standing guidance earns no row, but the start date of a recurring thread does.

Two things make it safe. Verification is untouched: `validate.py` checks every quotation against the full text in `text/`, never the digest, so a quote drawn from a dropped paragraph still validates and a quote that drifts still fails. And it was tested rather than assumed — all 40 of batch 1's already-verified quotations survive into the digest.

### What the batches turned up

**The quote check keeps earning its place.** Batch 1 submitted two quotes that failed: one attributed issue 2's wording to issue 1 (issue 1 says the working group "has been established", issue 2 says it "is meeting daily"), and one dropped the inversion from "Not only have we agreed" to "we have agreed". Neither would have been caught by reading. Batches 2 to 6 passed first time, which is what the check looks like when it is working.

**The lag analysis has its anchors, and they run both ways.** Face-to-face teaching ceased 13 March 2020, ten days *before* the national lockdown. Staff were barred from campus on 24 March, one day *after* it, and that newsletter names the government announcement explicitly. On 11 May UCL responded to the easing of restrictions by asking staff **not** to return — a one-day lag whose substance is divergence rather than compliance. On 4 June UCL published guidance for the quarantine on UK arrivals four days before the rule took effect.

**The sharpest divergence is 8 July 2020**: the government moved to "1 metre plus" and UCL kept 2 metres for Term 1 timetable planning, citing the Chief Medical Officer and PHE. That decision set room capacities for the whole of Term 1 and so directly shaped how many people were on campus when the case counting began in October.

**Scope calls made and recorded.** The denaming of the Galton and Pearson spaces (11 and 19 June 2020) is in the ledger under `category=governance` with a note saying it is *not* pandemic response and is present only because the pandemic newsletters were the channel that carried it — so it can be filtered out. The EU fee-status change of 23 June 2020 was left out entirely: it is a Brexit decision with no pandemic connection in the text.

### Batch 1 notes

Forty rows from fourteen newsletters is above the plan's projected rate, but March 2020 is the densest fortnight in the whole record — near-daily emails, each carrying several decisions. The rate should fall sharply from batch 8 onward as the cadence goes weekly then monthly.

**Two quotes failed the substring check on first submission and both were real errors**, which is the check earning its place on the first batch: one attributed issue 2's wording to issue 1 (issue 1 says the working group "has been established", issue 2 says it "is meeting daily"), and one dropped the inversion from "Not only have we agreed" to "we have agreed". Neither would have been caught by reading.

**The lag analysis already has its two anchor cases.** Face-to-face teaching ceased on 13 March 2020, ten days *before* the national lockdown — a negative lag. Staff were barred from campus on 24 March, one day *after* it — a positive lag of one. Both are quoted, and the second names the national announcement explicitly, which is what makes it usable rather than merely suggestive.

## Stage 3 — the data track — **done, 39 rows**

`build/data_events.py` reads `covid_raw.csv` and emits 37 rows: the series start and end, the record weekly maximum for each of the four series, every month where a group's total moves by at least 50% and at least 25 cases from the previous month (both gates from `timeline.toml`), the January comparison, and the collection outage. `build/camden_events.py` adds two comparator rows. Both write JSON consumed by `add_rows.py`, so nothing here is hand-typed.

**Gate met: both of the blog post's anchor figures reproduce mechanically.** The weekly maximum for on-campus students computes to **525 in the week to 21 December 2021**, and the January comparison to **9 in January 2021 against 696 in January 2022**. Neither number was entered by hand; both fall out of the published series.

### The Camden comparator, and a correction it forced

`build/fetch_camden.py` fetched 2,366 daily records for Camden from the UKHSA dashboard, 2020-01-30 to 2026-07-22, cached at `data/camden-cases.csv` with the retrieval time and exact query URL in the header. It refuses to refetch without `--force`. **All 31 days of October 2020 are present**, confirming that the gap documented for the bulk LTLA archive does not affect the live endpoint.

Two practical notes for anyone re-running it. The sandbox's empty host allowlist truncates the response mid-body, so it needs to run with the sandbox disabled; and long pages were seen to truncate anyway, so `get()` reads the whole body before parsing and retries four times rather than streaming into the JSON decoder, where a partial read would silently yield a short page.

**The comparator immediately corrected a claim I had drafted.** My first pass headlined the January comparison as Camden falling while UCL rose. That is wrong, and the computation said so: Camden rose too, from 4,770 cases to 11,211, a factor of 2.4. UCL's on-campus student cases rose from 9 to 696, a factor of 77 — about **33 times the borough's growth**.

The correction matters for how the finding is stated. The two series do not move in opposite directions, so the evidence is not a divergence in sign. It is a disparity in magnitude: the surrounding epidemic grew 2.4-fold and the campus figure grew 77-fold, which the local epidemic cannot account for on its own. The honest reading is that prevalence explains part of the change and campus policy the rest — closed to most students in January 2021, open in January 2022 under the higher education exemption from Plan B. Had this row been written by hand from the blog post's framing, the error would have shipped.

**The 12 May question is settled, against the snapshots rather than by assumption.** The plan flagged that the brief says the page recorded its final update on 12 May 2022 while the last row of `covid_raw.csv` is dated 2022-05-11, and asked for it to be checked. The snapshot of 2022-05-11 16:34 still reads "last update Thursday 5 May 2022"; the snapshot of 2022-05-12 09:34 reads "last update Thursday 12 May 2022" and carries the final cumulative totals. The page states its own convention: "This data will be updated by 9am Thursday. Figures are correct as of 4.30pm the previous day." So the figures published on 12 May are correct to 11 May, and the CSV dates each reading by the day the figures are correct *to* rather than the day the page changed. There is no discrepancy. One refinement to the plan's wording: the convention in May 2022 is 4.30pm, not the 5pm announced in issue 119.

November 2020 is included as the co-movement case, where borough and campus rise together. October 2020 is deliberately **not** included: the series opens on 9 October with a cumulative total already at 72, so the month is partial and its true figure is unknowable. `ucl_month_gain` returns `None` there rather than a number that looks whole.

## Stage 2 — national and sector tracks — **first pass done, 21 rows**

19 `national` rows and 2 `sector` rows, every one `verified=primary-retrieved` with a quotation lifted from a cached primary document. The ledger is now **343 rows, 0 errors, 0 warnings**.

Three new scripts, and one extension to an old one.

**`build/seed_national.py`** walks the research synthesis and emits a worklist rather than assertions: 44 dated claims, each carrying the reference it cites resolved to a title and URL, written to `seed/national-candidates.json` and a readable `.md`. It marks three things that change how much care a candidate needs — 11 claims are **uncited**, 4 rest on Wikipedia alone, and 16 have a year inferred from the section heading — and cross-references each against the `[[links]]` pairings so the load-bearing ones are visible. It reported that the synthesis carries **no dated claim at all** for five of the nine dates the chronology was waiting on.

**`build/fetch_sources.py`** caches the seven references carrying the most dated claims, with URL, retrieval time, byte count and SHA-256 in `sources/manifest.csv`. It refuses to refetch without `--force`, like the Camden fetcher.

Two things it had to learn. `pdftotext -layout` interleaves the columns of the two Institute for Government timelines so a date lands lines away from its own sentence; `-raw` keeps each dated block together, and the character counts fell by three quarters because `-layout` was padding with whitespace, not because text was lost. And the PDFs contain typographic ligatures, so "first" extracts as "ﬁrst" and no quotation containing it could ever be typed correctly. Ligatures are folded in the derived text; the PDF is kept byte for byte with its hash.

**`build/make_national_batch.py`** does not transcribe quotations. Each row names two ASCII anchors and the exact span is lifted from the cached text, so the quotation is the source's wording by construction. Anchors must be unambiguous or the batch is not written, which caught three real collisions: "PM says UK" opens two entries, "parts of Leicestershire" ends both the Leicester announcement and its commencement 250 characters later, and "UK" appears again in the Eat Out to Help Out entry. Scoping each lift to its own dated block fixed all three.

**`build/validate.py` gained check 3b.** A `web` row's quotation is now checked against the cached source exactly as a `ucl` row's is checked against its newsletter, and `verified=primary-retrieved` is treated as a claim that the document was actually fetched: the URL must be in the cache, the quote must be present, and the quote must match. Tested against a deliberately broken fixture before being trusted — a fabricated quote, an uncached URL and a missing quote all fail, and a genuine quote passes.

### What the primary sources corrected

Retrieval was worth doing for its own sake, because it falsified three things the chronology had been carrying on UCL's authority.

**15 June 2020 was not the face covering date.** Reference 7 gives 15 June as the day non-essential shops reopened in England. The transport mandate came from a UCL newsletter and none of the cached sources carries it, so that pairing has had its date **withdrawn** rather than keeping an unsupported one.

**The step 4 confirmation was 14 June, not 13 July.** Reference 11 records the Prime Minister confirming the four-week delay on 14 June. The UCL row of 19 July is now paired to step 4 itself.

**Neither the "universities stay open" exemption nor the higher education exemption from Plan B is in these sources.** Both are UCL's account of national policy. The national rows say so in their notes, and the labels no longer assert either. This matters more than the other two: the exemption is the reason the case series behaves so differently in the two lockdowns, and it is still unevidenced.

Two pairings gained a date they had never had, which turned the sharpest finding in the record into a measured one: the relaxation of the 2 metre rule was announced on **23 June 2020** and UCL confirmed it would keep 2 metres **fifteen days later**.

### The lag column is now live

**15 of the 20 declared pairings resolve and render with a measured lag.** The first lockdown of 23 March 2020 anchors five of them and they run both ways: -10 days for the end of face-to-face teaching, -6 for students being advised home, -3 for the building closures, and +1 for both the staff campus ban and the closure of the Student Centre.

Five remain pending and are listed in the document with no number attached: the schools and nurseries closure of 18 March 2020, the Coronavirus Job Retention Scheme conditions, the face coverings transport mandate, the OfS expectations that forced UCL's May 2020 timing, and the end of Plan B.

### Still to do on this stage

The three claims flagged in stage 1 as relayed by UCL remain unchecked and must not be repeated as established: the ONS finding on ethnic disparity in mortality, the Rt 1.7 reasonable worst case, and the 37% rise in university cyber-attacks.

`sources/ref-09.txt` is the **landing page** for Commons Library CBP-9068, not the briefing; the substance is an 8 MB PDF behind a download link and has not been retrieved. Reference 11 has a font encoding `pdftotext` cannot fully map, so parts of its text are mojibake (`30DQQRXQFHV` for `PM announces`); every quotation taken from it was lifted from a clean passage, but nothing else should be quoted from that file without looking at it first. References 6, 49 and 38 are cached and so far unused.

## Stage 5 — the Markdown chronology — **done**

`build/render_md.py` → `TIMELINE.md`: 190 KB, 2,601 lines, 28,000 words, sectioned by the eight phases in `timeline.toml`. Every one of the 283 non-data rows renders as an entry with its headline, date, category, date kind, a link to the preserved newsletter, the plain reading, the verbatim quotation as a blockquote, and the note. The 39 data rows are summarised under their phase rather than interleaved, per the plan.

`build/test_render_md.py` is new and runs 22 checks, all passing.

### The lag feature, and why it renders nothing yet

This is the part of the stage that needed a decision. The plan asks for the lag in days wherever a UCL action responds to a national one, computed from the ledger. There are no `national` or `sector` rows in the ledger, because stage 2 has not run, so the honest options were to infer pairings or to declare them.

**Inference was rejected.** Matching a UCL row to the nearest national row by date and category would manufacture correspondences nobody has checked, and a lag is a claim about cause. Pairings are therefore declared in `[[links]]` tables in `timeline.toml`, keyed on the UCL row's date and headline, which validate.py has already established are unique together. A link naming a row that is not in the ledger **stops the build**, so a pairing cannot go stale silently.

**Twenty pairings are declared**, extracted from the stage 1 notes, and they are stage 2's worklist in machine-readable form. All twenty are pending: they render as a table at the end of the document showing the national measure beside the UCL response, with **no lag computed**. Fourteen carry a provisional date, and in every case that date is one the newsletters themselves assert, which makes it UCL's account of national policy rather than the policy. Six have no date at all, including the 8 July 2020 two-metre divergence, and `counterpart` is deliberately optional so that no date had to be invented for them. When stage 2 puts a verified `national` row in the ledger on a declared date, the pairing resolves by itself and the lag appears in that phase's table and on the entry, with no further editing.

**The mechanism was tested rather than assumed**, since on the real ledger it produces nothing and a feature that has never once fired is not evidence of anything. `test_render_md.py` renders a fixture ledger that does have national and sector rows in it and checks the arithmetic in all three directions: -10 days where UCL moves first, +1 day where it follows, and "same day" where the two coincide. It also checks that a pending pairing stays unmeasured, that an undated one says so, that a stale pairing stops the build, and that a phase with no framing prose stops the build.

### Gate, checked rather than asserted

Run against the real rendered document by the same test file:

- All **283 newsletter citations resolve** to a file on disk.
- All **283 verified quotations reach the page unaltered** after whitespace normalisation. Stage 4 checked them against the newsletters; this checks the renderer did not touch them. One quotation carries an embedded newline that would have silently ended its blockquote, which is why the renderer collapses whitespace.
- **283 entries for 283 non-data rows**: nothing dropped.
- Every contents anchor matches a heading, every table row has a consistent cell count, no draft placeholders remain.

### The framing prose

Eight paragraphs, two to four sentences each, one per phase. They live in `framing` fields inside the `[[phases]]` tables rather than in the renderer, so the prose sits beside the phase it frames and a phase with none **fails the build** rather than rendering thin. `--draft` downgrades that to a visible marker while writing.

Every numeric claim in them was verified against `covid_raw.csv` directly, computed independently of the ledger rather than copied from it: staff cases off campus 15 → 154 → 18 across December 2020 to February 2021; nine on-campus student cases in January 2021 against 696 in January 2022; on-campus students 1 in May 2021 to 54 in June; on-campus staff 142 in February 2022 to 339 in March, and every series falls in every month after that, which is what makes "the last increase anywhere in the record" true.

The Omicron framing states the January comparison the way stage 3's correction requires: both series rise, and it is the difference in magnitude and not in direction that the local epidemic cannot account for.

### Two things left for stage 7

**Four em dashes reach the page**, all of them inside ledger `notes` and `detail` written in stages 1 and 3, none from the renderer. `writing-style.md` asks for them to be avoided. Fixing them means editing the batch JSON and regenerating, so it is deliberately deferred rather than churning a validated ledger for punctuation.

**`markdown.source_prefix`** is `../home/uclcovid/data/updates/`, correct for `TIMELINE.md` sitting in `timeline/`. If the placement decision moves the timeline into the archive repository, that one setting changes and nothing else does.

## Stage 6 — the interactive HTML timeline — **done**

`build/render_html.py` → `timeline.html`, 260 KB, self-contained. Four event lanes over two case panels on one shared time axis, eight phase bands, a filter row scoping the whole page, a crosshair on the case panels and a per-day tooltip on the lanes.

**Verified rather than assumed: the page fetches nothing.** `performance.getEntriesByType('resource')` returns an empty array on load, and the network panel shows only the document itself plus a `data:` URI that Chrome generates for its own date-picker icon. No external host appears anywhere in the file.

### The palette, re-run rather than inherited

All four configurations pass, reproducing the plan's section 3a:

| Palette | Pairlist | Mode | Result |
|---|---|---|---|
| light slots 1–3 | all | light | PASS, contrast WARN on aqua 2.74 |
| dark steps 1–3 | all | dark | PASS |
| light slots 1–4 | adjacent | light | PASS, contrast WARN on aqua and yellow |
| dark steps 1–4 | adjacent | dark | PASS |

The light-mode contrast WARN is discharged by a legend that is always present, a selective direct label, and links to both table views.

**Five slots were checked and pass adjacent in both modes**, which changed the design for the better. The plan expected to show three series and offer "staff" as a single toggle, leaving one of the four UCL series unreachable. Slots 1–4 carry all four UCL series instead, students on and off campus visible by default and staff on and off as toggles, so nothing is dropped. Bindings are fixed per entity, so toggling staff never repaints students; the reset path checks it.

### Camden moved to its own panel, and why that is not the plan's answer

The plan expected Camden on the same y-axis, both series being confirmed cases per week, with indexing to a common base as the fallback. Measured: Camden peaks at **5,922 cases in a week against 525** for UCL on-campus students. A shared scale puts every UCL line in the bottom ninth of the plot. Indexing would fix the geometry but changes the quantity on display from cases to relative change, and the UCL series opens in single figures where an index is mostly noise.

Camden therefore has its own panel underneath, sharing the x-axis and the crosshair, in the same unit with its own labelled axis. That is two plots rather than two scales on one plot, which is the alternative the anti-pattern catalogue names, and the page says so in its own words rather than leaving the reader to work it out.

### Three faults only rendering the page revealed

**The December 2021 peak was drawn outside its own panel.** `nice_ticks` stopped at or below the maximum, so a peak of 525 produced ticks 0/200/400 and the spike ran up through the top of the plot and across the lanes. Fixed, and locked by a test that checks the top tick against seventeen awkward values; the original implementation crops on twelve of them.

**The peak callout collided with the lanes.** Moved inside the panel, to the left of the spike with a short leader.

**The UCL lane was an illegible smear.** 141 marks across 1,038 pixels at the 8px marker floor overlapped into a solid bar. Event marks are now a rug of 2.5px ticks, which is the honest encoding for an event series this dense and does not pretend each mark is a measured point. Pointing is handled by nearest-day snapping across the whole lane rather than per-mark hit rectangles, which at 7px spacing would have overlapped several deep — the catalogue's own remedy for dense marks. Every mark keeps its `tabindex` and its `aria-label`, so the keyboard path is untouched.

### Gate

1. Palette validated in both modes for every configuration shipped. **Done, above.**
2. Rendered and looked at, in both light and dark. **Done** — the three faults above came out of it.
3. Checked line by line against `anti-patterns.md`. No dual axis, no dashed rules, no number on every point, no pinpoint hover, no tooltip-gated value, no fixed height cropping the axis band, no serif on a figure, `tabular-nums` only on axis ticks and tooltip rows, four categorical hues against a limit of seven.
4. **No network request on load, verified in the page rather than assumed.**

Interaction was driven and checked: lane hover snaps and lights exactly one mark, keyboard focus shows what hover shows, the series toggle does not repaint survivors, the track toggle scopes every lane, the date range cuts 143 UCL marks to 37, and reset restores the defaults.

The page renders whole without JavaScript: all four series paths, 183 event marks, the Camden line, 17 axis ticks and all eight phase names as native `<title>` elements are in the markup before the first `<script>`. Script adds the crosshair, the tooltips and the filters, and a `<noscript>` note says exactly that.

`build/test_render_md.py` now covers the HTML too, at 31 checks: no external host, no `fetch`/`XHR`/`WebSocket`, no `innerHTML`/`outerHTML`/`insertAdjacentHTML`/`document.write` anywhere, solid rules only, legend and table-view links present, the chart present before any script, and the axis-crop regression.

## Stage 7 — review — **done**. Placement decision — **open, and not mine to take**

### The review was made mechanical

Reading 2,818 lines hoping to notice a bad claim is not a method. `build/review.py` sorts every `detail` and `notes` field into the four kinds of claim that need a human, because those fields are the weak part of this project: they are prose nothing checks, and they sit directly under a verified quotation where they inherit its authority.

It flags 307 claims across 201 rows — 139 superlative, 97 unsourced-number, 37 relayed, 35 causal. Flagging is not judging, so most of that is noise by design.

**One check adjudicates rather than flags, and it found the error.** A figure in the commentary may legitimately not appear in its own quotation, and may legitimately cross-reference another issue. What it may not do is exist in no newsletter, no cached source and no computation, because there is then nowhere for a reader to go. Run against the full corpus plus the seven cached primary sources, that check surfaced **17 candidates, 16 of which were sound cross-references** and one of which was wrong:

> a note claimed a heading recurred in **105 of the 168 newsletters**. It recurs in **110**.

Corrected in `batches/batch-04.json` and re-applied, so the batch and the ledger cannot drift. The check is now part of `review.py` and exits non-zero if anything ever fails it again. It currently reports none.

Two remaining flags were punctuation, not error: the newsletters write `11:00–15:00` and the commentary writes `11.00 to 15.00`. Both sides now collapse to one form before comparison.

**A second real correction.** A note on the Tier 4 row said the Alpha variant *drove* the January 2021 rise. That is an epidemiological claim none of the cached sources makes, so it is not made: the note now says what the ledger supports, which is that restrictions tightened and the figures rose.

**One check was removed for not earning its place.** A heuristic meant to catch "highest" claims naming a figure that is not a recorded peak produced three hits, all false positives from `2020-21` and `15 minutes`. A check that has never been right is not worth a reader's attention.

### What the review confirmed

The three claims stage 1 flagged as relayed by UCL are all **hedged in the row itself**, and those hedges render into `TIMELINE.md`: the ONS finding on ethnic disparity in mortality, the Rt 1.7 reasonable worst case, and the 37% rise in university cyber-attacks each carry an explicit instruction not to repeat the figure as established.

Ten rows make an absolute claim. The three that the ledger can adjudicate all hold: newsletter cadence drops twice and rises once, so **"the only time in the record the cadence goes up"** is true; the flu voucher of 28 September 2020 is the only vaccination row in autumn 2020; and of six vaccination rows, only the one of 6 January 2022 attaches an operational consequence to vaccination status.

### The placement decision, with the figures it turns on

The plan recorded the arguments before the decision so they could not be assembled to fit it. What stage 7 adds is measurement.

**Scale of quotation.** 283 verbatim quotations totalling 48,536 characters against a corpus of 1,085,785 — **4.5% of the newsletters**, median quotation 166 characters, longest 370. The most heavily quoted single issue is issue 82 of 8 July 2020 at 8.3% of its text. No newsletter is reconstructible from the timeline.

**Size added.** 200 KB of `TIMELINE.md`, 256 KB of `timeline.html`, 196 KB of ledger, 356 KB of build scripts, 300 KB of batch JSON, and 3.2 MB of cached primary sources — the last being third-party PDFs that could be excluded and re-fetched.

This is the decision the plan deferred to the end, and it is the user's: it moves a tag that a Zenodo release has not yet consumed, and it sharpens a licensing question about material this project does not own.

---

# Where this stands, and how to pick it up

**Built and working:** `timeline.toml` and `config.py` (TOML with `UCLTL_*` environment and `--set` CLI overrides, precedence verified); `extract_text.py`; `digest.py`; `validate.py`; `add_rows.py`; `data_events.py`; `fetch_camden.py`; `camden_events.py`; `render_md.py` and `test_render_md.py`; `seed_national.py`; `fetch_sources.py`; `make_national_batch.py`; `render_html.py`; `review.py`.

**The ledger:** `timeline.csv`, **343 rows, 0 errors, 0 warnings** — 283 `ucl` rows with every quotation verified as an exact substring of its source newsletter, 21 `national` and `sector` rows with every quotation verified against a cached primary document, and 39 `data` rows all marked `computed`.

**The chronology:** `TIMELINE.md`, generated, 200 KB, with 15 measured lag pairings.

**The interactive page:** `timeline.html`, generated, 260 KB, self-contained and verified to fetch nothing.

**To resume, from `timeline/`:**

```bash
python3 build/validate.py          # should report 343 rows, 0 errors
python3 build/test_render_md.py    # 31 checks, all passing
python3 build/render_md.py         # rebuilds TIMELINE.md from the ledger
python3 build/render_html.py       # rebuilds timeline.html from the ledger
python3 build/review.py            # non-zero if any figure is untraceable
```

The first is the single command that says whether the state is intact. Everything else regenerates: `extract_text.py` and `digest.py` are deterministic and can be re-run at any time, `data_events.py` and `camden_events.py` rewrite their JSON from source, and `TIMELINE.md` is disposable output. Only `batches/batch-01.json` through `batch-12.json` and `batch-08b.json` are irreplaceable — they are the hand-written work of stage 1, and the ledger can be rebuilt from them with `add_rows.py`. To that list two more files must now be added. `timeline.toml` holds the eight framing paragraphs and the twenty declared pairings, hand-written and existing nowhere else. `build/make_national_batch.py` holds the anchors and the notes for the national track, which is the same kind of irreplaceable hand work as the stage 1 batches even though the quotations in it are lifted mechanically. `sources/` is re-fetchable in principle, but only while those URLs still resolve, which is exactly the assumption this project exists to distrust.

## The backup problem — **addressed, 25 July 2026**

`timeline/` is now its own git repository, at the user's direction, with the placement decision deliberately left open. 56 files tracked, 3.4 MB of history, working tree clean.

`.gitignore` excludes only what rebuilds deterministically from the archive — `text/` and `digest/`, 3.1 MB between them — because the archive has its own history and a DOI and is therefore already safe elsewhere. `sources/`, `batches/`, `timeline.toml` and `build/` are all tracked. `sources/` in particular, because those seven documents are re-fetchable only for as long as their URLs resolve, which is the assumption this project exists to distrust.

**There is no remote.** The work is versioned but still on one laptop, so this reduces the risk rather than removing it. Pushing is a separate decision and needs somewhere to push to.

**One thing to know before taking the placement decision:** `home/uclcovid` is at `v1.0-final-3-g6b80f09f`, so the tag is already three commits behind HEAD. The question is not whether committing would move it forward for the first time.

**The backup problem, as it stood before that.** `timeline/` joins `TIMELINE-PLAN.md`, the regenerated `.md`, the blog post and `figures/` in existing only on this laptop, in a directory that is deliberately not a git repository. Stage 1 represents the single largest irreplaceable effort in the project: 283 rows read and quoted out of 1.09 million characters across 168 files. The scripts would take an hour to rewrite; the batch JSON would take the whole exercise again. This was already the one live risk in `ARCHIVE-PLAN.md` and it is now considerably larger.
