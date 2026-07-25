#!/usr/bin/env python3
"""Stage 2, step two: cache the primary sources the worklist points at.

`seed_national.py` produces candidate claims with the reference each one cites.
This fetches those references once, writes them to `sources/` with a manifest
recording the URL, the retrieval time and the SHA-256 of what came back, and
stops. Verification then runs against the cached copy, so a claim checked today
is checked against the same bytes as a claim rechecked next year, and a source
that is later edited or withdrawn cannot silently change what this project says
it says.

Which references to retrieve is a setting, not a constant: `sources.retrieve`
in `timeline.toml`, chosen by how many dated claims rest on each one.

**PDFs need `pdftotext`**, which is the project's first dependency outside the
standard library and the Python one it still is not. It is only needed to
refresh the cache; `sources/ref-NN.txt` is what everything downstream reads, so
a machine without poppler installed can still validate and render.

Usage:
    python3 fetch_sources.py [--force] [--only 7,11]
"""
import csv
import hashlib
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

import config
from seed_national import parse_references

TIMEOUT = 60
# Some of these hosts refuse a request with no user agent.
AGENT = ('Mozilla/5.0 (compatible; uclcovid-timeline/1.0; '
         'archival retrieval of cited public documents)')


def get(url, attempts=3):
    """One document, read whole before it is used. Same reasoning as the
    Camden fetcher: a partial read must fail here rather than downstream."""
    last = None
    for i in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as fh:
                return fh.read(), fh.headers.get('Content-Type', '')
        except Exception as exc:                  # noqa: BLE001 — report, retry
            last = exc
            print(f'    attempt {i}/{attempts}: {exc.__class__.__name__}: {exc}',
                  file=sys.stderr)
            time.sleep(2 * i)
    return None, f'FAILED: {last}'


def extension(url, content_type):
    if 'pdf' in content_type.lower() or url.lower().endswith('.pdf'):
        return '.pdf'
    return '.html'


# pdftotext emits the typographic ligatures the PDFs actually contain, so
# "first" comes out as "ﬁrst". A quotation has to be an exact substring of this
# text to validate, and nobody can be expected to type a ligature, so they are
# folded here. The PDF itself is kept byte for byte and its SHA-256 recorded;
# this is a derived reading copy.
LIGATURES = {'ﬀ': 'ff', 'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬃ': 'ffi',
             'ﬄ': 'ffl', 'ﬅ': 'st', 'ﬆ': 'st'}


def to_text(path, out):
    """Cached document as plain text, which is what verification reads."""
    if path.suffix == '.pdf':
        if not shutil.which('pdftotext'):
            print(f'    no pdftotext on PATH, cannot extract {path.name}',
                  file=sys.stderr)
            return False
        # `-raw` rather than `-layout`. Both Institute for Government
        # references are graphic timelines laid out in columns, and -layout
        # interleaves the columns so a date lands several lines from the
        # sentence it belongs to. -raw keeps each dated block together, which
        # is what makes a claim checkable by reading.
        proc = subprocess.run(['pdftotext', '-raw', str(path), str(out)],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            print(f'    pdftotext failed on {path.name}: {proc.stderr[:200]}',
                  file=sys.stderr)
            return False
        text = out.read_text(encoding='utf-8', errors='replace')
        for lig, plain in LIGATURES.items():
            text = text.replace(lig, plain)
        out.write_text(text, encoding='utf-8')
        return True
    # HTML: strip tags crudely. This text is read by a person checking a claim
    # and searched for a date, not parsed, so crude is sufficient and has no
    # dependency. The original bytes stay in the cache either way.
    import html
    import re
    raw = path.read_text(encoding='utf-8', errors='replace')
    raw = re.sub(r'(?is)<(script|style|nav|footer|svg)[^>]*>.*?</\1>', ' ', raw)
    raw = re.sub(r'(?s)<[^>]+>', ' ', raw)
    raw = html.unescape(raw)
    raw = re.sub(r'[ \t]+', ' ', raw)
    raw = re.sub(r'\n\s*\n+', '\n\n', raw)
    out.write_text(raw.strip() + '\n', encoding='utf-8')
    return True


def main():
    def opts(ap):
        ap.add_argument('--force', action='store_true',
                        help='refetch documents already cached')
        ap.add_argument('--only', default='',
                        help='comma-separated reference numbers, for one retry')
        ap.add_argument('--reextract', action='store_true',
                        help='redo text extraction from the cache without '
                             'refetching anything')
    cfg, args = config.load(extra_args=opts)

    src = cfg.path('paths.resources')
    refs = parse_references(src.read_text(encoding='utf-8').splitlines())

    # Works-cited references, plus any [[extra_sources]] the ledger needs that
    # the research synthesis never cited.
    for extra in cfg.get('extra_sources', []):
        refs[int(extra['id'])] = {'title': extra['title'], 'url': extra['url']}

    wanted = list(cfg.get('sources.retrieve') or [])
    wanted += [int(e['id']) for e in cfg.get('extra_sources', [])]
    if args.only:
        wanted = [int(x) for x in args.only.split(',') if x.strip()]
    if not wanted:
        sys.exit('nothing to retrieve: set sources.retrieve in the config')

    out_dir = config.ROOT / str(cfg.get('sources.cache', 'sources'))
    out_dir.mkdir(exist_ok=True)
    manifest_path = out_dir / 'manifest.csv'
    manifest = {}
    if manifest_path.exists():
        with open(manifest_path, newline='', encoding='utf-8') as fh:
            manifest = {int(r['ref']): r for r in csv.DictReader(fh)}

    failures = []
    for ref in wanted:
        if ref not in refs:
            print(f'[{ref}] not in the works-cited list, skipping',
                  file=sys.stderr)
            failures.append(ref)
            continue
        url = refs[ref]['url']
        existing = manifest.get(ref)
        if existing and not args.force and (out_dir / existing['file']).exists():
            cached = out_dir / existing['file']
            if args.reextract:
                text_path = cached.with_suffix('.txt')
                ok = to_text(cached, text_path)
                existing['text'] = text_path.name if ok else ''
                existing['text_chars'] = (
                    len(text_path.read_text(encoding='utf-8')) if ok else 0)
                print(f'[{ref}] re-extracted {existing["text_chars"]:,} '
                      'characters from the cached copy')
            else:
                print(f'[{ref}] cached already: {existing["file"]}')
            continue

        print(f'[{ref}] {url}')
        body, ctype = get(url)
        if body is None:
            print(f'    could not retrieve: {ctype}', file=sys.stderr)
            failures.append(ref)
            continue

        path = out_dir / f'ref-{ref:02d}{extension(url, ctype)}'
        path.write_bytes(body)
        text_path = path.with_suffix('.txt')
        ok = to_text(path, text_path)
        chars = len(text_path.read_text(encoding='utf-8')) if ok else 0
        manifest[ref] = {
            'ref': ref,
            'file': path.name,
            'text': text_path.name if ok else '',
            'url': url,
            'title': refs[ref]['title'],
            'retrieved': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
            'bytes': len(body),
            'sha256': hashlib.sha256(body).hexdigest(),
            'text_chars': chars,
        }
        print(f'    {len(body):,} bytes, {chars:,} characters of text')
        if not ok:
            failures.append(ref)

    fields = ['ref', 'file', 'text', 'url', 'title', 'retrieved', 'bytes',
              'sha256', 'text_chars']
    with open(manifest_path, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for ref in sorted(manifest):
            w.writerow({k: manifest[ref][k] for k in fields})

    print(f'\ncached: {len(manifest)} documents in {out_dir}')
    if failures:
        print(f'FAILED: {sorted(set(failures))} — retry with '
              f'--only {",".join(str(f) for f in sorted(set(failures)))}',
              file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
