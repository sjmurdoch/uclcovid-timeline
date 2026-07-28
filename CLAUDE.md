# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **finished, published deliverable**: an AI-generated chronology of UCL's pandemic response, built from the 168 preserved UCL COVID-19 newsletters and the published case series in the sibling `uclcovid` archive. It is its own git repository, `sjmurdoch/uclcovid-timeline`, served at <https://sjmurdoch.github.io/uclcovid-timeline/>. All seven build stages are done; changes now are corrections and presentation, not new construction.

**The AI-generated caveat is load-bearing, not boilerplate.** `README.md`, `TIMELINE.md`, `PROGRESS.md` and `timeline.html` all open with it, and `test_render_md.py` asserts it survives in both rendered outputs. It draws a specific line: quotations and figures are checked mechanically, while selection, reading, categorisation, commentary and the lag pairings are not checked by anything. Never soften that distinction, never move the notice below a title, and do not add a claim to `detail` or `notes` that the sitting quotation does not support — those two fields inherit authority from the verified quote above them and are exactly where this project is weakest.

## The checks

Run from `timeline/`. All five pass on a clean tree as of 28 July 2026:

```bash
python3 build/validate.py          # 347 rows, 0 errors, 0 warnings
python3 build/test_render_md.py    # 42 checks over both renderers
python3 build/review.py            # exit 1 if any figure is untraceable; prints 370 claims to read
python3 build/render_md.py         # 18 lags resolved, 2 pending
python3 build/render_html.py       # 187 day-marks, 336 case readings
```

A sixth, `build/test_browser.py`, drives the page in a real browser: 28 checks over the tap, pinch, drag, hover, keyboard and scroll paths on a phone and a desktop. **It is the only thing that can see an interaction fault** — both faults it was written for left a page that reads correctly and could not be used on a phone, and neither reproduces with events dispatched by hand. It needs Playwright, which is not a dependency of this repository and is not installed by anything here; without it, or without a rendered page, it prints a skip line and exits 0. Run it after any change to the CSS or the script in `render_html.py`:

```bash
uv venv .venv && .venv/bin/python -m pip install playwright
.venv/bin/python build/test_browser.py
```

**`validate.py` is the single command that says whether the state is intact — run it after every change to the ledger.** Its load-bearing check is that every quotation is an exact substring of the text re-derived from the document it cites: 283 against the newsletters in `text/`, 26 against the cached documents in `sources/`. Paraphrase, drift, misattribution and invention all fail it mechanically. Cached sources are hashed against `sources/manifest.csv` before any quote is checked against them, so a `.txt` cannot be edited to make a check pass.

`review.py` does not judge prose, it sorts it into a worklist — 172 superlative, 109 unsourced-number, 50 relayed, 39 causal. A non-zero exit means a figure in the commentary appears in no newsletter and no cached source. `--kind`, `--full` and `--coverage` (newsletter sections no row covers) narrow it.

### Environment

Standard library only, Python 3.11+ for `tomllib`. No test framework, no CI, nothing that has to be installed to build, validate or render. Two things sit outside that and both are optional: `pdftotext` (poppler), needed only to *refresh* the source cache with `fetch_sources.py` — everything downstream reads `sources/ref-NN.txt` — and Playwright, needed only by `test_browser.py`, which skips without it. Keep both optional; nothing on the build path may acquire a dependency.

`fetch_camden.py` needs `dangerouslyDisableSandbox` — the empty host allowlist truncates the response mid-body. It refuses to refetch without `--force`, and nothing else in the project touches the network.

## This repository does not build on its own

It is standalone in git but not in its dependencies. Four paths point outside it, and `validate.py`, `render_md.py`, `render_html.py` and `review.py` all need them:

| Path | Needed for |
|---|---|
| `../home/uclcovid/data/updates/` | the 168 newsletters; check 4 resolves every `source_ref` on disk |
| `../home/uclcovid/data/covid_raw.csv` | the case series `render_html.py` plots; CI fetches it by URL instead, see below |
| `text/` | gitignored, regenerate with `python3 build/extract_text.py` |
| `../TIMELINE-PLAN.md` | the plan; `PROGRESS.md` and code comments cite it by section number |

On a fresh clone with no sibling archive, only the fixture half of `test_render_md.py` runs; the real-output checks skip themselves rather than fail. `digest/` is also gitignored and rebuilds from `text/` with `digest.py`, but stage 1 is finished and nothing reads it now.

## Generated versus hand-written

Everything in the deliverables is generated from `timeline.csv`, and the ledger is generated from the batches. **Four things exist nowhere else and cannot be regenerated:**

- `batches/batch-01.json` … `batch-12.json` and `batch-08b.json` — 283 rows read out of 1.09 million characters, the largest irreplaceable effort in the project;
- `timeline.toml` — eight phase framing paragraphs, thirteen restriction regimes and twenty declared lag pairings, all hand-written;
- `build/make_national_batch.py` — the anchors and notes for the national track, hand work even though the quotations are lifted mechanically;
- `sources/` — eleven fetched documents, re-fetchable only while those URLs resolve, which is the assumption this project exists to distrust.

`TIMELINE.md` and `timeline.html` are disposable output and are versioned only so the diffs are reviewable. **Never edit either by hand** — fix the ledger, the config or the renderer and rebuild.

`render_md.py` is idempotent. `render_html.py` is not: it stamps the short hash at the foot of the page, so a local re-render produces a one-line diff and the committed page names the commit *before* the one containing it. **That no longer affects what is published** — the Pages workflow re-renders at deploy time with the SHA it is deploying, so the served marker is correct and the served page always comes from the committed ledger rather than from the committed snapshot. The snapshot is kept for reviewable diffs, and the workflow emits a warning when it drifts from what the ledger renders. Keep committing it, and ignore the marker line in its diffs.

## Changing the ledger

**Never hand-edit `timeline.csv`.** Quotations carry commas, curly quotes and em rules; hand-built CSV corrupts them and the corruption looks exactly like fabrication to the validator. Write JSON and append it:

```bash
python3 build/add_rows.py batches/batch-NN.json [--replace-source-refs]
python3 build/validate.py
```

`add_rows.py` re-sorts by date, track, headline, so order does not matter and re-running is idempotent; `--replace-source-refs` redoes one batch in place without disturbing the rest. The `data` track is never hand-written at all — `data_events.py` and `camden_events.py` rewrite their JSON from source, so the chronology and the blog post cannot silently disagree about a number.

Row invariants the renderers rely on: `date` must be literal `YYYY-MM-DD` (`fromisoformat` accepts more, and anything else pairs with nothing and sorts to the wrong end), and `date` plus `headline` must be unique together, because `render_md.py` and the `[[links]]` pairings key on that pair.

## Configuration

`timeline.toml`, read through `build/config.py`, with precedence **command line > environment > TOML > built-in default**. Environment variables take `UCLTL_` plus the dotted path upper-cased with dots as underscores; an unrecognised `UCLTL_*` name warns rather than being silently dropped. A local build can point citations at a checkout of the archive without touching anything tracked:

```bash
UCLTL_MARKDOWN_SOURCE_PREFIX=../home/uclcovid/data/updates/ python3 build/render_md.py
python3 build/render_html.py --set build.commit=v1.2.0
```

New settings belong in the TOML, not as constants in a script. Judgement calls in particular — the phase boundaries, the restriction levels, the data-track thresholds, the lag pairings — are config precisely so they can be argued with, and each carries its reasoning in a comment beside it.

## Documentation structure

| | |
|---|---|
| `README.md` | what the thing is, what is and is not checked, licensing of `sources/` |
| `PROGRESS.md` | the build record, stage by stage, including what went wrong and what corrected it |
| `PUBLISH_PLAN.md` | the publishing decisions of 25 July 2026 and why each was taken |
| `../TIMELINE-PLAN.md` | the plan, outside the repo, cited by section number throughout |

`PROGRESS.md` is written by hand as each stage closes so a cold resume knows where it stopped, and it records corrections rather than overwriting the claim that was wrong. Keep that habit: when a check turns up an error, say what the error was and what caught it. Several entries exist only because a mechanical check contradicted prose that had already been drafted, and that record is the most useful thing in the file.

## Traps

- **Newsletter quotations are untrusted scraped HTML.** Insert with `textContent`, never `innerHTML`. `test_render_md.py` checks that no scraped string can reach the DOM as markup.
- **The published page fetches nothing at run time** — no CDN, no fonts, no XHR. Three checks enforce it. Do not introduce an external dependency; the one external *link* is the build marker at the foot.
- **File index is not issue number.** 168 files indexed 000–167 carry issues 1–165; special editions have none. A row's `issue` is checked against `text/index.csv`, not against its date — a row is filed under the date of the event, which may precede the newsletter reporting it.
- **Files 122 and 124 are the same newsletter.** Byte-identical, same source URL, there is no Part 2. 167 distinct newsletters, of which 133 carry at least one row.
- **`date_kind` distinguishes announced from effective**, often by days. Getting it wrong corrupts the lag, which is the one number the renderer computes rather than copies. Restriction spans in the TOML use effective dates deliberately; announcements are event marks on the National lane.
- **Lag pairings are declared, never inferred.** Matching a UCL row to the nearest national row by date would manufacture correspondences nobody has checked. A pairing whose counterpart is not in the ledger renders as pending, not as a provisional number.
- **UCL cases are not a subset of Camden cases.** Presence is not residence. Shape and timing may be compared; shares and proportions may not, and no script computes any.
- **`[N]` citation markers collide with Markdown link syntax.** The validator fails `[7]` followed by `(` or `[`.
- **Do not spend categorical hues on the four tracks** — position separates them; colour belongs to the case series. Never flip the light palette for dark mode: the light hexes fail the dark lightness band outright, so dark is its own set of steps from the same ramps. The `scripts/validate_palette.js` invocations recorded in `render_html.py`'s comments come from the **dataviz skill**, not from this repository — load that skill to re-run them. In-repo, the four palette checks in `test_render_md.py` are what guard the slots.
- **Touch is not a mouse with one button, and neither rule it needs is visible in the rendered page.** Nothing drawn inside a lane may take pointer events: whatever is painted over the lane's hit rect is what a fingertip lands on, and `.lane-rule` runs along the exact line the marks sit on. And no `pointerleave` handler may act on a pointer that is not a mouse: a pointer that cannot hover is destroyed when it is lifted, and the browser fires `pointerout` and `pointerleave` straight after its `pointerup`, so hiding on leave hides what the tap has just opened. Each of these made every mark on every phone unopenable while all five checks passed.
- **The pinch exists only because the chart declines the browser's.** `touch-action:pan-x pan-y` on the svg is what hands the two-finger gesture to the script. Do not drop it — the browser keeps the gesture and the axis stops zooming on touch — and do not widen it to `none`, which takes one-finger scrolling with it on a chart that is two and a half screens wide. Double-tap-to-zoom-out rides on the same declaration.
- **Three restriction start dates are `checked = false`** — 13 May 2020, 20 December 2020, 29 March 2021. They came from the general England chronology, and a Wikipedia read on 26 July 2026 contradicted none of them but does not move the flag, which means a source this archive holds. Do not mark them checked without putting the regulation in `sources/`.

## Publishing

`.github/workflows/pages.yml` renders the page and deploys it; Pages is configured for Actions, not for branch-serving, so **the workflow is the only route to the live site** and a broken workflow means no deploy. It runs on push to `master` and on `workflow_dispatch`. The artifact is the whole tree less `.git` and `.github`, which is what serving the branch root used to do — narrowing it would break any external link into `sources/`. `index.html` redirects to `timeline.html`.

The workflow fetches `covid_raw.csv` from `raw.githubusercontent.com` with `build/fetch_cases.py`, because there is no sibling archive checkout in CI. That reads a **branch tip**, so `[cases] sha256` in `timeline.toml` pins what the ledger was built against and a mismatch fails the deploy. When it fires, do not move the hash on its own: re-run `data_events.py` against the new series, validate, and commit the ledger the chart will then agree with. Moving the hash alone publishes a chart that disagrees with the `data` rows beneath it, which is the whole failure the pin exists to prevent.

**CI does not validate.** `validate.py` needs `text/` and the newsletter files, and neither is in the repository, so quotation checking cannot run there. Validation stays a local gate: run `validate.py` and `test_render_md.py` before pushing, because after the push nothing will.

Pushing to GitHub fails inside the sandbox and needs `dangerouslyDisableSandbox`.

Newsletter citations point at `github.com/sjmurdoch/uclcovid/blob/main/data/updates/` so a reader of the published page can follow any claim to its source — which the page's own notice tells them to do. The repository has no `LICENSE`; the archive uses Apache 2.0 for code and extracted data and does not relicense the UCL material, which is worth mirroring here.
