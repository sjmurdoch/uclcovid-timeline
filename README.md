# ⚠️ AI-generated demonstration, not a verified historical record

**Everything in this directory was produced by an AI system working from the preserved UCL COVID-19 newsletters and the published case data. No human has checked it.**

Some of it is checked mechanically and some of it is not, and the difference matters more than a general disclaimer would suggest.

**What is checked.** Every quotation is verified as an exact substring of the document it cites, re-derived from the source at build time. 283 quotations against the preserved newsletters, 26 against cached copies of primary documents. A paraphrase fails that check, a quotation attributed to the wrong issue fails it, and an invented quotation fails it. The case figures are computed from `covid_raw.csv` rather than transcribed. Every figure appearing in the commentary has been checked to exist somewhere in the corpus.

**What is not checked.** Everything else, which is most of what makes a chronology a chronology:

- whether the right events were selected from 1.09 million characters of newsletters, and whether anything important was passed over;
- whether each event has been *read* correctly, as opposed to quoted correctly;
- whether the dates, categories and phase boundaries are right;
- whether the chart's background shading is right. It encodes how strict the legal restrictions were, and ten of its thirteen start dates come from a cited row or the research synthesis. **Three do not** — 13 May 2020, 20 December 2020 and 29 March 2021 — and are marked `checked = false` in `timeline.toml`. All thirteen were checked against Wikipedia's `COVID-19 lockdown in the United Kingdom` on 26 July 2026, which contradicted none of them, corroborated 13 May 2020, and is silent on the other two; that check is recorded per span but does not move the flag, which means a source this archive holds and can re-verify;
- whether the commentary in the `detail` and `notes` fields is sound — it is interpretation, written by an AI system, sitting directly beneath a verified quotation where it inherits authority it has not earned;
- whether the **lag figures** mean anything. Each rests on a pairing between a UCL action and a national measure that an AI system judged to be a response. Those judgements have not been reviewed by anyone.

**So what is this for?** It is a demonstration of what the [uclcovid dataset](https://github.com/sjmurdoch/uclcovid) makes possible: that a preserved corpus of institutional email plus a preserved statistical series can be turned into something navigable, with every claim traceable back to a source. That is the point being made. The chronology is the vehicle, not the product.

**Do not rely on it, quote it, or cite it as a record of UCL's pandemic response.** If a fact here is useful to you, follow its citation to the preserved newsletter and read it in context before using it. The sources are real and were preserved carefully; this layer on top of them was not verified by a person.

---

## Where it is published

The interactive page is served at **<https://sjmurdoch.github.io/uclcovid-timeline/>**, and the newsletters it cites are preserved in the [uclcovid archive](https://github.com/sjmurdoch/uclcovid). Every citation in `TIMELINE.md` points there, so a claim can be followed to its newsletter from the published page alone — which, given everything above, is the only responsible way to use one.

## What is here

| | |
|---|---|
| `TIMELINE.md` | The chronology, sectioned by pandemic phase, with every quotation |
| `timeline.html` | An interactive version, self-contained, no network access at run time |
| `index.html` | The site's front door, which redirects to `timeline.html` |
| `timeline.csv` | The ledger both are generated from |
| `build/` | The scripts, including the checks described above |
| `batches/` | The hand-written row definitions, the irreplaceable part |
| `sources/` | Cached copies of the primary documents cited, with SHA-256 |
| `timeline.toml` | Configuration, phase framing prose, the restriction regimes, and the declared lag pairings |
| `PROGRESS.md` | The build record, including what went wrong and what was corrected |

## Rebuilding and checking

```bash
python3 build/validate.py          # 347 rows, 0 errors
python3 build/test_render_md.py    # 36 checks over both renderers
python3 build/review.py            # non-zero if any figure is untraceable
python3 build/review.py --coverage # newsletter sections no row covers
python3 build/render_md.py         # rebuild TIMELINE.md
python3 build/render_html.py       # rebuild timeline.html
```

A local build can point the citations back at a checkout of the archive without editing anything tracked:

```bash
UCLTL_MARKDOWN_SOURCE_PREFIX=../home/uclcovid/data/updates/ python3 build/render_md.py
```

## Sources and rights

`sources/` holds copies of eleven third-party documents, retrieved so that the figures citing them could be checked against what they actually say rather than against a link that might rot. They are reproduced as evidence, not relicensed.

- The [gov.uk](https://www.gov.uk/), [legislation.gov.uk](https://www.legislation.gov.uk/) and [ONS](https://www.ons.gov.uk/) items are covered by the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/), and the House of Commons Library briefings by the [Open Parliament Licence](https://www.parliament.uk/site-information/copyright-parliament/open-parliament-licence/). Both permit redistribution with attribution, which this section is.
- The Institute for Government, Academy of Medical Sciences and Office for Students PDFs carry no such licence. They are their authors' copyright, cached here unmodified and cited with their source URL and retrieval date in `sources/manifest.csv`.
- The newsletter quotations throughout are copyright University College London, quoted for the purpose of citing them and preserved in full in the [uclcovid archive](https://github.com/sjmurdoch/uclcovid), which records the same position.

The build scripts and the generated chronology are this project's own work.
