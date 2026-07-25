# Publishing plan: `sjmurdoch/uclcovid-timeline` on GitHub Pages

Decisions taken 25 July 2026, recorded here so the reasoning survives the shell history.

## What is being published

`timeline/` was already a standalone git repository — 65 tracked files, no remote, on `master`. Publishing it is a matter of giving it a GitHub home, not of extracting it from anything.

| Decision | Choice |
| --- | --- |
| Repository | `sjmurdoch/uclcovid-timeline` |
| Visibility | Public |
| Contents | Everything currently tracked, including `sources/` |
| Newsletter citations | Rewritten to the public `sjmurdoch/uclcovid` repository |
| Pages source | `master` branch, root |

## Why each one

**Public.** GitHub Pages is free on public repositories, and the archive this cites, `sjmurdoch/uclcovid`, is already public with Pages enabled at `sjmurdoch.github.io/uclcovid/`. A private repository would need GitHub Pro before Pages would build at all.

**`sources/` included.** The `.gitignore` carried a standing note that `sources/` needed a second look before any public push, because the seven documents are third-party. That look has now happened and the answer is to include them. Of the eleven fetched documents, the gov.uk, legislation.gov.uk, ONS and House of Commons Library items are Open Government Licence or Open Parliament Licence and are redistributable with attribution; the Institute for Government, Academy of Medical Sciences and Office for Students PDFs are not clearly so, and are reproduced as the evidence behind cited figures rather than relicensed. The `.gitignore` note is updated to record this rather than left standing as a warning about a decision already made.

**Citations rewritten.** All 283 newsletter citations in `TIMELINE.md` pointed at `../home/uclcovid/data/updates/`, a path outside this repository. Every one of them would 404 for a reader of the published site. The same 168 newsletters are already tracked and public in `sjmurdoch/uclcovid`, so the citations now point there.

`timeline.html` needed no such change: it links only to `timeline.csv` and `TIMELINE.md`, both of which travel with it.

## Steps

1. Point `markdown.source_prefix` at the public archive in `timeline.toml`. The existing config layer already gives this TOML, `UCLTL_MARKDOWN_SOURCE_PREFIX` and `--set markdown.source_prefix=…` for free, so a local build can still use relative paths without editing anything tracked.
2. Rebuild `TIMELINE.md`; confirm the citation check still resolves all 283 links against the local newsletters, since the test strips the prefix before looking on disk.
3. Give Pages an `index.html`. The deliverable is `timeline.html`, and Pages serves `index.html` at the site root.
4. Record the `sources/` decision in `.gitignore` and give the README a sources-and-licensing section, since publishing third-party documents makes attribution load-bearing.
5. Commit in logical units, create the repository, push, enable Pages on `master` root.
6. Verify the built site: the page loads, the CSV and Markdown links work, and a sample of citations resolve.

## Known limits

- Citations use `github.com/sjmurdoch/uclcovid/blob/main/…`, which shows each newsletter as source rather than rendered. `https://sjmurdoch.github.io/uclcovid/data/updates/` renders them properly and is a one-line change to `markdown.source_prefix`; it costs a dependency on Pages staying enabled on the archive, which the archive README already flags for its own served files.
- The published page carries its own conspicuous notice that everything on it was produced by an AI system and no human has checked it. That notice is the reason the citations have to work: it tells readers to follow the link and read the newsletter in context.
- The repository has no `LICENSE`. The archive uses Apache 2.0 for code and extracted data, and explicitly does not relicense the UCL material. Worth mirroring here, but it is a licensing choice rather than a mechanical one.
