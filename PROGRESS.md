# ⚠️ This work is AI-generated and has not been verified by a person

Quotations are checked mechanically against their sources; the selection, reading, categorisation, commentary and lag pairings are not. See `README.md` for what that distinction covers. This is a demonstration of what the dataset makes possible, not a reliable chronology of UCL's pandemic response.

---

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

### Second pass: one pending pairing settled, one not

**Face coverings on public transport is now measured, at -24 days.** SI 2020/592 puts the requirement into force on 15 June 2020; UCL had required face coverings on campus where distancing was not possible from 22 May, twenty-four days earlier. This pairing had been carried on a UCL newsletter's authority, withdrawn when reference 7 turned out to give 15 June as the day non-essential shops reopened, and is now restored on the statutory instrument. Both facts are true of that day; only one of them was ever the point.

`fetch_sources.py` gained `[[extra_sources]]` for this. The research synthesis' works-cited list is a secondary source's choice of references and does not carry everything the ledger needs; extra sources are numbered from 101 so they cannot collide with a reference number and are fetched, cached, hashed and verified by exactly the same path. The ledger is **345 rows**, 17 of 20 pairings measured.

**The end of Plan B is settled too, at +26 days.** It took four attempts. Three shell fetches timed out or failed, and the last of those turned out to have failed on my own `grep` pattern exceeding ugrep's complexity limit rather than on the network. Retrieved through `fetch_sources.py` instead, which uses urllib and caches properly, it came back first time.

**SI 2021/1400** amends regulation 15 of SI 2021/1340, substituting "26th January 2022" for "20th December 2021", and its explanatory note reads: *"They also extend the period during which the Regulations are in force until 26th January 2022."* So the Plan B face covering requirement lapsed at the end of 26 January 2022. UCL narrowed its own expectation to teaching settings twenty-six days later — the second time in the record it holds a measure after the law drops it, the first being step 4 in July 2021.

The ledger is **345 rows**, and **17 of 20 pairings are measured**. Three remain pending: the schools and nurseries closure of 18 March 2020, the Coronavirus Job Retention Scheme conditions, and the OfS expectations that forced UCL's May 2020 timing.

### Still to do on this stage

The three claims flagged in stage 1 as relayed by UCL remain unchecked and must not be repeated as established: the ONS finding on ethnic disparity in mortality, the Rt 1.7 reasonable worst case, and the 37% rise in university cyber-attacks.

`sources/ref-09.txt` is the **landing page** for Commons Library CBP-9068, not the briefing; the substance is an 8 MB PDF behind a download link and has not been retrieved. Reference 11 has a font encoding `pdftotext` cannot fully map, so parts of its text are mojibake (`30DQQRXQFHV` for `PM announces`); every quotation taken from it was lifted from a clean passage, but nothing else should be quoted from that file without looking at it first. References 6, 49 and 38 are cached and so far unused.

## Stage 5 — the Markdown chronology — **done**

`build/render_md.py` → `TIMELINE.md`: 190 KB, 2,601 lines, 28,000 words, sectioned by the eight phases in `timeline.toml`. Every one of the 283 non-data rows renders as an entry with its headline, date, category, date kind, a link to the preserved newsletter, the plain reading, the verbatim quotation as a blockquote, and the note. The 38 data rows are summarised under their phase rather than interleaved, per the plan.

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

`build/render_html.py` → `timeline.html`, 260 KB, self-contained. Four event lanes over two case panels on one shared time axis, background shading for the restriction regimes, a filter row scoping the whole page, a crosshair on the case panels and a per-day tooltip on the lanes.

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

The page renders whole without JavaScript: all four series paths, 183 event marks, the Camden line, 17 axis ticks and all thirteen restriction-regime names as native `<title>` elements are in the markup before the first `<script>`. Script adds the crosshair, the tooltips and the filters, and a `<noscript>` note says exactly that.

`build/test_render_md.py` now covers the HTML too, at 37 checks: no external host, no `fetch`/`XHR`/`WebSocket`, no `innerHTML`/`outerHTML`/`insertAdjacentHTML`/`document.write` anywhere, solid rules only, legend and table-view links present, the chart present before any script, and the axis-crop regression.

### The phase bands became restriction shading — **26 July 2026**

The chart's background alternated light and dark by pandemic phase, numbered 1 to 8 along the top. Reported as confusing, and it was: the shading encoded nothing a reader could recover from it. A band was shaded because its phase index was even, so the darker regions and the lighter ones stood for nothing in common, and "phase 4" is not a fact a grey rectangle can convey even once the reader hovers to find the number. It was decoration in the position of data, on the largest area of the figure.

The background now carries one ordinal quantity: **how strict the restrictions legally in force were**, on a four-step scale from no shading at all through limited measures and substantial restrictions to a stay-at-home order. That is a question the shading can answer without help — was there a lockdown on this date, and how hard — and it is the question the whole record is about.

**The regimes are configuration, not renderer.** Thirteen `[[restrictions]]` spans in `timeline.toml`, one per run of a level rather than one per announcement, each with the level, a short chart label, a full name for the tooltip, and a `source` field recording where its start date comes from. Successive regimes at the same strictness are merged, because a boundary drawn where the shading does not change reads as a change that is not there.

**Three decisions inside that are worth stating.** Dates are the days measures came into force, not the days they were announced, so the shading changes a few days to the right of the announcement mark on the National lane — and that gap is the lag the chronology measures, so encoding announcements here would have put the same fact in the figure twice. The scale follows England, and London specifically wherever England was tiered, because UCL is in Camden. And `level = 3` is the legal test, a stay-at-home order, not a measure of how closed the university was: the second national lockdown is shaded as darkly as the first while UCL stayed open, which is precisely the divergence the UCL lane exists to show and which a shading that quietly absorbed it would destroy.

**Ten of the thirteen start dates come from a ledger row or the resources synthesis. Three do not**, and carry `checked = false` in the TOML: 13 May 2020 (the stay-at-home order replaced), 20 December 2020 (Tier 4 in force in London, where the ledger has only the announcement of the 19th), and 29 March 2021 (the stay-at-home rule ended). They come from the general England chronology and want checking against the regulations before publication.

**Checked against Wikipedia's `COVID-19 lockdown in the United Kingdom`, 26 July 2026**, at the user's direction. Every span now carries a `wikipedia` field recording the outcome: **six confirmed** in the article's own words, one partly, **two the article is silent on**, and four outside its scope, which ends in May 2021 and so covers neither step 4, nor Plan B, nor the end of the requirement in 2022. **Nothing contradicted a shading boundary.**

Two things it turned up. **13 May 2020 is corroborated** — "those in England were allowed to meet one other person not from their household outside whilst maintaining a 2-metre social distance" — which is the first external support that date has had. And the article puts the third national lockdown's legal effect at **00:01 on 5 January 2021** where the ledger's cited row says 6 January; no shading turns on it, because level 3 runs unbroken from 20 December, but the ledger row is worth re-reading against its source.

**`checked` did not move on the strength of any of it.** That flag means a source this archive holds and can re-verify by hash, and a tertiary article at a live URL is the kind of thing this project exists to distrust. The two dates the article is silent on — 20 December 2020 and 29 March 2021 — are still unsupported, and 29 March is the weakest date in the file: the article gives the roadmap steps as 8 March, 12 April and 17 May and **states no date at all for the end of the stay-at-home rule**. An intermediate reading of it claimed the rule ended with step 1; checking the article's actual sentences showed it says no such thing, which is the whole reason the fetched summary was not taken at face value.

The proper fix is the one the project already has a mechanism for: the three regulations belong in `sources/` via `[[extra_sources]]` and `fetch_sources.py`, fetched once and verified by SHA-256 thereafter, exactly as SI 2020/592 was. Not done — it is a stage 2 job, not a rendering one.

**Colour, and why it stays grey.** The ramp is neutral in both modes, monotonic in lightness, and deliberately recessive: the darkest light-mode step sits 1.34:1 against the chart surface. The bands lie under the lines and marks that carry the measurements, and a background that competes with them is the worse error, so strictness never rests on the shading alone — a rule at every change, a label along the top, the full name in a `<title>`, and a legend under the figure all repeat it. Grey rather than a hue for the reason the phase bands were grey: a categorical hue in the background impersonates a series, and all four categorical slots are already spent on the case data.

**Band labels are config text now**, so the old fixed 54-pixel threshold for drawing one would have let a longer label spill into the regime beside it. Replaced by a width estimate the script and the renderer share, so a zoomed redraw makes the same decision the server did. Measured on the rendered page: all nine labels that fit sit inside their own band.

Two checks added, and both confirmed to fail on deliberately broken input rather than merely passing on the real thing: the shading is one ordered ramp per mode, monotonically away from the surface, so no edit can silently say a lockdown was looser than the tiers; and every level drawn appears in the legend. 35 checks, all passing at the time. `TIMELINE.md` is byte-identical — the phases still section the chronology, which is the one place a named phase can carry its own prose.

### Whole-project review, and the fourteen things it found — **26 July 2026**

A review of the entire project rather than a diff. The pipeline passed throughout: none of this was caught by `validate.py`, `test_render_md.py` or `review.py`, because none of them was looking.

**A published row was false.** `camden_events.py` emitted "Camden and UCL both peak in {month}" from a bare f-string — nothing computed or checked a peak — and the month it emitted was a peak for neither series. Camden's November 2020 total is **1,243**, below October's 1,313 and far below its 15,901 in December 2021; UCL's on-campus student gain was **43** against 696 in January 2022. The ledger contradicted itself two hundred rows later with the December 2021 weekly peak. The row shipped as `verified=computed`, which `README.md` defines as computed rather than transcribed, and it was live in `TIMELINE.md`, `timeline.html` and the published repository.

**Withdrawn rather than repaired,** because the data cannot carry the claim it was written to make. `ucl_month_gain` returns None for October 2020 and is right to: the series opens on the 9th with a cumulative 371 already banked, so the month is unknowable and there is no autumn co-movement to compute from monthly gains. A version built on the published weekly columns would be a different measurement and would have to be checked before it shipped. The January comparison never depended on it. Ledger now **347 rows, 38 `data`**.

**Why it survived: `review.py` never read `headline`.** `classify()` and `check_corpus_figures()` both built their prose from `detail` and `notes`, and every generated headline puts its superlative and its figure exactly there. Two fixes: the headline is commentary and is now read as such, and `peak` and its relatives joined the superlative vocabulary, which had `highest` and `largest` but not the word this project's own generators use. The withdrawn row now classifies as `[superlative] peak`. Re-run over the ledger, the four remaining extremum claims were checked against `covid_raw.csv` by hand and all four are true.

**The corpus figure check was weaker than it looked.** `digits in corpus` over 1.1M characters called 154 traceable because 1154 appears somewhere, and 525 because 5250 does — in the one check here that adjudicates rather than flags. Now matched as whole numbers.

**The 26 primary quotations rested on unhashed files.** `fetch_sources.py` recorded a sha256 of each original and nothing ever compared anything to it, while `sources/ref-NN.txt` — the file check 3b actually reads, and the one tracked in git — carried no hash at all. Appending a sentence to a `.txt` and citing it as `primary-retrieved` validated clean. `text_sha256` added to the manifest, both halves verified as check 3c, all eleven originals re-verified against their recorded hashes on backfill. Not re-derived at validate time: that would cost the validator a dependency on `pdftotext`. Tamper-tested — appending a sentence to `ref-07.txt` now exits 1 naming the file.

**A gap in the case series was drawn as a straight line.** 4 January 2021 is blank in all four weekly columns, and `load_cases` dropped the row entirely, so the date reached neither renderer and both joined across it — the chart asserted a week the published series does not report. The row is kept now, values None, and the path breaks; only the ends are trimmed, where all-blank means the series has not started rather than that a week went unrecorded. **The review had this wrong in an instructive way**: it reported that the script broke the path and only the server did not, so the two renderings disagreed. They agreed — both were interpolating. Checking the payload rather than taking the report at face value is what found the real cause upstream.

**`render_html.py` never read `date_precision`.** 33 month-precision rows were drawn as a tick on one day and captioned with that day, so a row the ledger dates to a month read "1 November 2020" in the tooltip — a precision invented by the renderer that discarded the field, in the direction that overstates. `fmt_date` now honours precision as `render_md.py` always did, and a mark shared by rows of different precision takes the coarsest. The mark itself is unchanged; widening month rows into bars was considered and rejected, as it would put two meanings on mark width in a lane already fixed once for overplotting.

**Two more chart bugs.** The date inputs clamped each end of the domain independently, so an out-of-range pair inverted it and blanked the chart with no way back but Reset — the interval is clamped now, before the width check. And the tooltip ignored `fig.scrollLeft`, so on a scrolled narrow screen it landed most of a screen from the mark that was tapped: precisely the case the tap path was added for.

**Two invariants the code relied on and nothing enforced.** `date` + `headline` is what `render_md.py` keys its row index on, and what `timeline.toml` claims this file establishes — it did not, since check 6 compares all thirteen fields, so a collision would have resolved to whichever row sorted last and attached the lag to the wrong one. And `date.fromisoformat` accepts `20200309` and `2020-W10-1` on 3.11 and later, both of which then break every string comparison downstream and land at NaN in the browser; the check is a round trip now. Both were confirmed against deliberately broken ledgers.

**Zero was guarded as a missing value in one place and not at all in the other.** `data_events.py` dropped every month whose predecessor gained nothing — the largest relative move there is, and exactly what the data track exists to surface — because the same condition guarded the division and the row. The gate is on the absolute move now, with the percentage stated only where one exists. `camden_events.py` checked `a is None` and not `a == 0`, so a January with no on-campus cases would have divided by zero and taken the batch build down. Neither changes today's output.

**Smaller.** An unreachable guard in `lift()` whose real case raised an uncaught `ValueError` instead of joining the collected errors; a shared notes template that made the November row assert October's completeness, gone with the row; dead `data-cats` and `data-mid` attributes on every mark and lane, read by nothing; `build_links` run a second time after the file was written; "168" written into generated prose twice, now counted from `text/index.csv`; `--out` cwd-relative in two generators and root-relative in a third; a double space in the published notes of both `.off` rows, from an empty interpolation `.strip()` cannot reach; and a `UCLTL_*` variable naming no known setting ignored in silence, which now warns — it cannot be honoured, since an unknown name cannot be turned back into a dotted path, but a typo is exactly what needs saying.

One check added, and confirmed to fail on broken input: a gap in the series breaks the line rather than joining across it. **36 checks, all passing**, `validate.py` clean at 347 rows, `review.py` exit 0 with every commentary figure traceable.

### The page says which build it is — **26 July 2026**

A line under the last paragraph: **Built from `<short hash>`**, the hash linked to its own commit, then the repository. `build.commit` and `build.repo` in `timeline.toml` override the lookup, reachable by `--set` and `UCLTL_*` like every other setting; empty means detect with `git rev-parse` and `git remote get-url origin`, normalising the ssh form and the `.git` suffix. A detection that fails prints nothing rather than a guess, since a reader would try to resolve a wrong hash — verified by rendering with git off `PATH`, which drops the line and leaves the page otherwise identical.

**A page cannot carry its own hash.** It is written before it is committed, so this names the state it was built *from*, which is the ledger and the scripts that produced what the reader sees. That is why the marker lands in two commits: the sources, then the page regenerated against them. The generated outputs are excluded from the dirty check, because rendering writes them and including them would report dirty on every run and make the marker mean nothing.

**The external-host check was narrowed to what it claims.** It rejected any external `href`, which caught `<a>` along with everything else, and that is why the hash shipped as plain text at first. But a link is not a load: it fetches nothing and does not exist until a reader chooses it. The check now forbids the forms that actually load — `src`, an `href` on `<link>`, `@import`, `url()` — and a second check holds the line, asserting that every external reference on the page is an anchor and nothing else, so the distinction cannot quietly become a loophole. Probed with four kinds of external load, a script `src`, a stylesheet `<link>`, an `@import` and an `<img>`: all four still fail it.

### The marker stopped being off by one, and the page is now rendered at deploy — **27 July 2026**

The entry above records a compromise: a page cannot carry its own hash, so the marker named the state it was built *from* and landed in two commits, the sources and then the page regenerated against them. Pages served the branch directly, so the served marker was always one render behind. `.github/workflows/pages.yml` removes the compromise rather than documenting it. Pages is switched from branch-serving to Actions, the workflow re-renders `timeline.html` from the ledger, and `build.commit` is set to the SHA being deployed. The served marker is now correct, and the served page can no longer fall behind the ledger, because it is no longer the committed snapshot.

`render_html.py` needs `covid_raw.csv`, which is in the archive and not here, so `build/fetch_cases.py` fetches it from `raw.githubusercontent.com`. **That is a branch tip, and the risk it introduces is the reason the script exists in the form it does.** The `data` rows were computed from one state of that series by `data_events.py`; the chart is drawn from whatever the fetch returns. If the series moves while the ledger does not, the chart moves and the commentary beneath it does not, and nothing would have said so. The expected SHA-256 is therefore recorded as `[cases] sha256` in `timeline.toml` and a mismatch exits non-zero before anything renders. The remedy is deliberately not "update the hash": it is to re-run `data_events.py`, validate, and commit the ledger the chart will then agree with.

Checked rather than asserted, before the workflow was pushed. The fetched series is byte-identical to the archive checkout the ledger was built from (`6b05e1c0…`). Rendering from the fetched copy with the marker pinned to `8d1f870` reproduces the committed `timeline.html` **byte for byte**, which is what says the workflow publishes the same artifact and not merely a similar one. Both failure paths were exercised: a wrong hash and a URL returning something that is not the series each exit 1 and write no file, so a bad fetch cannot reach the renderer. The staleness comparison excludes the marker line, because that line differs by construction and an always-firing warning would be noise; verified not to fire against a current snapshot.

**What the workflow cannot do is validate**, and this is the real cost of the change. `validate.py` checks quotations against `text/`, regenerated from the newsletters, and neither is in this repository. So the deploy renders without verifying, and verification stays a local gate that has to be run before pushing. The hash pin covers the one out-of-repo input the build reads; it covers nothing else.

### The chart answered no gesture a phone has — **28 July 2026**

Reported: on a mobile device the timeline neither zooms its axis nor opens an event. Both were true. The tap fault had two independent causes, either of which was enough on its own, and the zoom was a design decision that had only ever been half argued.

**A tap aimed at a mark landed on the lane rule.** `.lane-rule` is drawn after the lane's hit rect and along the exact line the marks sit on, and an SVG `<line>` with a stroke is a hit target. The element under a fingertip aiming at a mark was therefore the rule, the lane's handlers never ran, and no mark on the page could be opened at all. A mouse mostly survived it, because it arrives moving and the next pixel either side is lane again — but only mostly: hovering the exact centre of a mark missed it on the desktop too, which is the same fault and had never been noticed. The rule is now `pointer-events:none`, and nothing drawn inside a lane is a pointer target.

**The taps that did reach a lane were undone one event later.** A pointer that cannot hover is destroyed when it is lifted, and the specification has the browser fire `pointerout` and then `pointerleave` immediately after the `pointerup` that ended it. The lane's `pointerleave` handler was written for a mouse leaving the lane and called `hide()`, so every tap opened the tooltip and closed it again before a frame had been painted with it. The case panels had the same handler and the same fault. Both are now mouse-only; touch puts the tooltip away by tapping off the chart, which the document handler already did.

**Zoom on touch was declined by design, and the design was wrong.** The comment in `render_html.py` argued that sideways drag belongs to the browser on a phone — the chart holds a 56rem minimum width, so it is more than two screens across and one finger is how a reader reaches October 2021 — and left the date boxes as the only way to narrow the axis. That reasoning holds for one finger and says nothing about two. `touch-action:pan-x pan-y` on the svg declines the browser's pinch over the chart and nowhere else, and a pinch now scales the domain about the point between the fingers, so the day being held stays under them: measured at 0.2 of a day's drift across a five-fold zoom. One finger still scrolls the figure, the case scales still do not move, and the floor is the same week a drag refuses — `MIN_SPAN`, now shared by the drag, the pinch and the date boxes rather than written as a bare `7` in each of the three. Double tap zooms back out, which is the `dblclick` handler the mouse already had, reached because the browser's own double-tap zoom goes with the pinch.

**Neither fault reproduces with synthesised events**, which is why a suite that reads the rendered page could not have caught them. Dispatching a `pointerup` by hand asserts the model of the browser that was wrong in the first place: it opens the tooltip, and no `pointerleave` follows to take it away. `build/test_browser.py` therefore drives real touch input through CDP and lets the browser generate the pointer sequence itself — 28 checks across a phone and a desktop, covering the tap, the pinch, one-finger scrolling, and every interaction that already worked. Against the page as it stood before this entry it fails 11 of them, two of those on the desktop; against the page now it passes all 28. **Playwright is not a dependency of this repository and CI does not run this file**: without it installed, or without a rendered page to open, it prints a skip line and exits 0. Five structural checks went into `test_render_md.py` as well — the declarations the browser file rests on — so the standard-library suite fails if any of them is dropped. Those five also fail against the old page.

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

### Verification pass: two relayed claims settled, one refused, coverage tested properly

**Two of the three claims stage 1 flagged as relayed by UCL now check out**, and both are on the national track with the primary wording.

The ONS finding UCL relayed on 2 June 2020 is supported: 4.2 for Black males and 4.3 for Black females against White males and females, after adjusting for age. UCL's "four times" is a fair reading. The ONS is explicit that adjusting for age alone does not establish cause, and the row says so.

The Rt 1.7 figure is supported by the Academy of Medical Sciences report itself, with a distinction the newsletter loses and the ledger now keeps: **1.7 is an assumption the model was run under** to explore a reasonable worst case, not a forecast of what Rt would be.

**The third could not be verified and stays flagged.** The 37% rise in university cyber-attacks names no source in the newsletter, and the archive's inventory of every link in that issue shows the only security link goes to UCL's own Stay Secure pages. There is no trail to follow. That is the finding, and the row says not to repeat the figure.

**A third pairing settled.** The Commons Library timeline records the Prime Minister announcing the closure of schools for most pupils on 18 March 2020, which takes the Day Nursery pairing to +1 day. **18 of 20 pairings are now measured.** Two remain: the Coronavirus Job Retention Scheme conditions and the OfS expectations, both diffuse rather than dated. Reference 38 turned out to be an OfS briefing about student accommodation, not admissions, so it does not settle the second.

**`fetch_sources.py` now sniffs magic bytes.** The Academy of Medical Sciences serves its report as `text/plain` from an extensionless URL; trusting either the header or the URL would have run a PDF through the HTML tag-stripper and produced convincing rubbish. The retry logic earned its place on the same file, which failed once with an `IncompleteRead`.

### Coverage tested properly, and what that does and does not show

The first coverage test was a keyword scan of uncited newsletters. It establishes the absence of *obvious* misses and nothing more.

`review.py --coverage` is the stronger test. The newsletters are structured into numbered sections, and a section is the unit UCL itself chose as worth telling people about, so the question becomes checkable: is there a section no row covers? Two rules keep it usable. Headings carried by more than five newsletters are standing content and dropped, the same rule `digest.py` applies to paragraphs. And a section is matched against rows within a week either side rather than only its own issue, because the newsletters restate decisions constantly.

It flags **138 sections across 84 newsletters**. Eight were checked by hand: six are matching artefacts where the ledger plainly covers the section, and two genuinely have no row — a housekeeping note about email signatures, and a call for volunteers to translate guidance that the newsletter describes as "currently exploring whether there is a demand". Both correctly earn no row under the inclusion test, which asks for a decision, a change of state or a dated commitment.

**So: no misses found.** Eight of 138 were examined, not all 138. The remaining 130 are a shortlist a reader can work down, not a verdict, and the check is in the build so it can be re-run.

### Coverage re-checked, and the page reworked

**Traceability.** `review.py` reports none: every figure in the commentary is traceable to a newsletter or a cached primary source. The two corrections it forced are recorded above.

**Coverage.** 133 of the 168 newsletters carry at least one row. The other 35 were re-scanned for decision-signalling language and **three** were flagged, none of them a genuine miss:

- `124_…` is the byte-identical duplicate of `122_…`, already cited through 122.
- Issue 145 of 21 June 2021 matched on "from Monday" inside a list of recorded roadshow dates, which is not a decision.
- Issue 164 of 21 February 2022 matched on the face covering change, which **is** in the ledger, sourced to issue 163 of 14 February — the newsletter that announced it — and filed under 21 February, the date it took effect. That is the convention working, not a gap.

This is a keyword scan and it establishes the absence of *obvious* misses rather than the absence of all misses. A decision phrased without any of those markers would not be caught.

**The page.** Three reported faults fixed: the date inputs had no width and so rendered blank; the date range only hid marks instead of moving the axis, and now rescales everything positioned in time; and the UCL lane's clutter is addressed by that zoom plus category filters drawn from the eleven categories already in the ledger, with no new priority judgement invented. A theme selector was added — the CSS had supported one since stage 6 but nothing ever set the attribute, so the page could only follow the system setting.

### The placement decision, with the figures it turns on

The plan recorded the arguments before the decision so they could not be assembled to fit it. What stage 7 adds is measurement.

**Scale of quotation.** 283 verbatim quotations totalling 48,536 characters against a corpus of 1,085,785 — **4.5% of the newsletters**, median quotation 166 characters, longest 370. The most heavily quoted single issue is issue 82 of 8 July 2020 at 8.3% of its text. No newsletter is reconstructible from the timeline.

**Size added.** 200 KB of `TIMELINE.md`, 256 KB of `timeline.html`, 196 KB of ledger, 356 KB of build scripts, 300 KB of batch JSON, and 3.2 MB of cached primary sources — the last being third-party PDFs that could be excluded and re-fetched.

This is the decision the plan deferred to the end, and it is the user's: it moves a tag that a Zenodo release has not yet consumed, and it sharpens a licensing question about material this project does not own.

---

# Where this stands, and how to pick it up

**Built and working:** `timeline.toml` and `config.py` (TOML with `UCLTL_*` environment and `--set` CLI overrides, precedence verified); `extract_text.py`; `digest.py`; `validate.py`; `add_rows.py`; `data_events.py`; `fetch_camden.py`; `camden_events.py`; `render_md.py` and `test_render_md.py`; `seed_national.py`; `fetch_sources.py`; `make_national_batch.py`; `render_html.py`; `review.py`.

**The ledger:** `timeline.csv`, **347 rows, 0 errors, 0 warnings** — 283 `ucl` rows with every quotation verified as an exact substring of its source newsletter, 26 `national` and `sector` rows with every quotation verified against a cached primary document, and 38 `data` rows all marked `computed`.

**The chronology:** `TIMELINE.md`, generated, 200 KB, with 15 measured lag pairings.

**The interactive page:** `timeline.html`, generated, 260 KB, self-contained and verified to fetch nothing.

**To resume, from `timeline/`:**

```bash
python3 build/validate.py          # should report 347 rows, 0 errors
python3 build/test_render_md.py    # 42 checks, all passing
python3 build/render_md.py         # rebuilds TIMELINE.md from the ledger
python3 build/render_html.py       # rebuilds timeline.html from the ledger
python3 build/review.py            # non-zero if any figure is untraceable
python3 build/test_browser.py      # 28 checks, needs playwright; skips without it
```

The first is the single command that says whether the state is intact. Everything else regenerates: `extract_text.py` and `digest.py` are deterministic and can be re-run at any time, `data_events.py` and `camden_events.py` rewrite their JSON from source, and `TIMELINE.md` is disposable output. Only `batches/batch-01.json` through `batch-12.json` and `batch-08b.json` are irreplaceable — they are the hand-written work of stage 1, and the ledger can be rebuilt from them with `add_rows.py`. To that list two more files must now be added. `timeline.toml` holds the eight framing paragraphs and the twenty declared pairings, hand-written and existing nowhere else. `build/make_national_batch.py` holds the anchors and the notes for the national track, which is the same kind of irreplaceable hand work as the stage 1 batches even though the quotations in it are lifted mechanically. `sources/` is re-fetchable in principle, but only while those URLs still resolve, which is exactly the assumption this project exists to distrust.

## The backup problem — **addressed, 25 July 2026**

`timeline/` is now its own git repository, at the user's direction, with the placement decision deliberately left open. 56 files tracked, 3.4 MB of history, working tree clean.

`.gitignore` excludes only what rebuilds deterministically from the archive — `text/` and `digest/`, 3.1 MB between them — because the archive has its own history and a DOI and is therefore already safe elsewhere. `sources/`, `batches/`, `timeline.toml` and `build/` are all tracked. `sources/` in particular, because those seven documents are re-fetchable only for as long as their URLs resolve, which is the assumption this project exists to distrust.

**There is no remote.** The work is versioned but still on one laptop, so this reduces the risk rather than removing it. Pushing is a separate decision and needs somewhere to push to.

**One thing to know before taking the placement decision:** `home/uclcovid` is at `v1.0-final-3-g6b80f09f`, so the tag is already three commits behind HEAD. The question is not whether committing would move it forward for the first time.

**The backup problem, as it stood before that.** `timeline/` joins `TIMELINE-PLAN.md`, the regenerated `.md`, the blog post and `figures/` in existing only on this laptop, in a directory that is deliberately not a git repository. Stage 1 represents the single largest irreplaceable effort in the project: 283 rows read and quoted out of 1.09 million characters across 168 files. The scripts would take an hour to rewrite; the batch JSON would take the whole exercise again. This was already the one live risk in `ARCHIVE-PLAN.md` and it is now considerably larger.
