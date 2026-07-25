#!/usr/bin/env python3
"""Convert 'UK COVID-19 Timeline Resources.docx' to Markdown with citation
markers preserved.

The Markdown copy that previously existed lost its citation apparatus: the
superscript reference numbers were flattened into the prose, so 'pandemic11'
was really 'pandemic[11]'. This reads the .docx directly, detects superscript
runs, and re-emits them as [N], with a numbered reference list built from the
auto-numbered works-cited entries and their hyperlink targets.

Standard library only. Usage:
    python3 docx_to_cited_md.py <input.docx> <output.md>
"""
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def run_text(r):
    return ''.join(t.text or '' for t in r.iter(W + 't'))


def is_super(r):
    rpr = r.find(W + 'rPr')
    if rpr is None:
        return False
    va = rpr.find(W + 'vertAlign')
    return va is not None and va.get(W + 'val') == 'superscript'


def has(r, tag):
    rpr = r.find(W + 'rPr')
    if rpr is None:
        return False
    el = rpr.find(W + tag)
    return el is not None and el.get(W + 'val') not in ('0', 'false')


def para_text(p, markers=True, emphasis=True):
    """Reconstruct a paragraph, emitting superscript runs as [N]."""
    out = []
    for r in p.iter(W + 'r'):
        txt = run_text(r)
        if not txt:
            continue
        if is_super(r):
            out.append('[%s]' % txt if markers else txt)
            continue
        if emphasis and txt.strip():
            lead = txt[:len(txt) - len(txt.lstrip())]
            trail = txt[len(txt.rstrip()):]
            core = txt.strip()
            if has(r, 'b'):
                core = '**%s**' % core
            elif has(r, 'i'):
                core = '*%s*' % core
            txt = lead + core + trail
        out.append(txt)
    return re.sub(r'[ \t]+', ' ', ''.join(out)).strip()


def style_of(p):
    ppr = p.find(W + 'pPr')
    if ppr is None:
        return None
    s = ppr.find(W + 'pStyle')
    return s.get(W + 'val') if s is not None else None


def is_listed(p):
    ppr = p.find(W + 'pPr')
    return ppr is not None and ppr.find(W + 'numPr') is not None


def convert(docx_path, out_path):
    with zipfile.ZipFile(docx_path) as z:
        doc = ET.fromstring(z.read('word/document.xml'))
        rels = {r.get('Id'): r.get('Target')
                for r in ET.fromstring(z.read('word/_rels/document.xml.rels'))}

    body = doc.find(W + 'body')

    # Paragraphs that live inside tables are emitted with their table, not
    # again at top level.
    in_table = {id(p) for tbl in body.iter(W + 'tbl') for p in tbl.iter(W + 'p')}

    # --- works cited: position in the numbered list is the citation number ---
    top = [c for c in body if c.tag in (W + 'p', W + 'tbl')]
    cited_at = None
    for i, el in enumerate(top):
        if el.tag == W + 'p' and para_text(el, emphasis=False).lower().startswith('works cited'):
            cited_at = i
            break
    if cited_at is None:
        sys.exit('could not locate the works-cited heading')

    refs = []
    for el in top[cited_at + 1:]:
        if el.tag != W + 'p':
            continue
        txt = para_text(el, markers=False, emphasis=False)
        if not txt:
            continue
        urls = [rels[h.get(R + 'id')] for h in el.iter(W + 'hyperlink')
                if h.get(R + 'id') in rels]
        url = urls[0] if urls else ''
        # Entries read "Title - Publisher, https://url"; drop the trailing
        # bare URL since it is emitted as a link instead.
        if url:
            txt = re.sub(r',?\s*' + re.escape(url) + r'\s*$', '', txt).rstrip(' ,')
        refs.append((txt, url))

    lines = []
    for el in top[:cited_at]:
        if el.tag == W + 'tbl':
            rows = []
            for tr in el.findall(W + 'tr'):
                cells = [' '.join(para_text(p) for p in tc.iter(W + 'p')).strip()
                         for tc in tr.findall(W + 'tc')]
                rows.append([c.replace('|', r'\|') for c in cells])
            if not rows:
                continue
            width = max(len(r) for r in rows)
            rows = [r + [''] * (width - len(r)) for r in rows]
            lines.append('| ' + ' | '.join(rows[0]) + ' |')
            lines.append('|' + '---|' * width)
            for r in rows[1:]:
                lines.append('| ' + ' | '.join(r) + ' |')
            lines.append('')
            continue

        if id(el) in in_table:
            continue

        txt = para_text(el)
        if not txt:
            continue
        st = style_of(el)
        if st and st.startswith('Heading'):
            level = int(st[len('Heading'):])
            txt = txt.strip('*').strip()
            lines.append('#' * level + ' ' + txt)
        elif is_listed(el):
            lines.append('- ' + txt)
        else:
            lines.append(txt)
        lines.append('')

    lines.append('## Works cited')
    lines.append('')
    for i, (txt, url) in enumerate(refs, start=1):
        lines.append('%d. %s%s' % (i, txt, ' — <%s>' % url if url else ''))

    # collapse runs of blank lines
    text = '\n'.join(lines)
    text = re.sub(r'\n{3,}', '\n\n', text).strip() + '\n'
    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write(text)

    return refs


if __name__ == '__main__':
    refs = convert(sys.argv[1], sys.argv[2])
    print('references emitted: %d' % len(refs))
    print('entries without a URL: %d' % sum(1 for _, u in refs if not u))
