# ⚠️ AI-generated demonstration, not a verified historical record

**Everything in this directory was produced by an AI system working from the preserved UCL COVID-19 newsletters and the published case data. No human has checked it.**

Some of it is checked mechanically and some of it is not, and the difference matters more than a general disclaimer would suggest.

**What is checked.** Every quotation is verified as an exact substring of the document it cites, re-derived from the source at build time. 283 quotations against the preserved newsletters, 26 against cached copies of primary documents. A paraphrase fails that check, a quotation attributed to the wrong issue fails it, and an invented quotation fails it. The case figures are computed from `covid_raw.csv` rather than transcribed. Every figure appearing in the commentary has been checked to exist somewhere in the corpus.

**What is not checked.** Everything else, which is most of what makes a chronology a chronology:

- whether the right events were selected from 1.09 million characters of newsletters, and whether anything important was passed over;
- whether each event has been *read* correctly, as opposed to quoted correctly;
- whether the dates, categories and phase boundaries are right;
- whether the commentary in the `detail` and `notes` fields is sound — it is interpretation, written by an AI system, sitting directly beneath a verified quotation where it inherits authority it has not earned;
- whether the **lag figures** mean anything. Each rests on a pairing between a UCL action and a national measure that an AI system judged to be a response. Those judgements have not been reviewed by anyone.

**So what is this for?** It is a demonstration of what the [uclcovid dataset](../home/uclcovid) makes possible: that a preserved corpus of institutional email plus a preserved statistical series can be turned into something navigable, with every claim traceable back to a source. That is the point being made. The chronology is the vehicle, not the product.

**Do not rely on it, quote it, or cite it as a record of UCL's pandemic response.** If a fact here is useful to you, follow its citation to the preserved newsletter and read it in context before using it. The sources are real and were preserved carefully; this layer on top of them was not verified by a person.

---

## What is here

| | |
|---|---|
| `TIMELINE.md` | The chronology, sectioned by pandemic phase, with every quotation |
| `timeline.html` | An interactive version, self-contained, no network access at run time |
| `timeline.csv` | The ledger both are generated from |
| `build/` | The scripts, including the checks described above |
| `batches/` | The hand-written row definitions, the irreplaceable part |
| `sources/` | Cached copies of the primary documents cited, with SHA-256 |
| `timeline.toml` | Configuration, phase framing prose, and the declared lag pairings |
| `PROGRESS.md` | The build record, including what went wrong and what was corrected |

## Rebuilding and checking

```bash
python3 build/validate.py          # 348 rows, 0 errors
python3 build/test_render_md.py    # 31 checks over both renderers
python3 build/review.py            # non-zero if any figure is untraceable
python3 build/review.py --coverage # newsletter sections no row covers
python3 build/render_md.py         # rebuild TIMELINE.md
python3 build/render_html.py       # rebuild timeline.html
```

`sources/` holds copies of third-party documents, retrieved for verification. They are not this project's to redistribute, and that needs settling before this directory is published anywhere.
