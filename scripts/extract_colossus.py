"""Split the Colossus white paper (Colossus_of_Rhodes.docx, repo root) into reader chapters.

Writes narration/colossus.json:
  chapters: intro + the 14 numbered sections, as plain paragraphs with the bracketed
            citations removed (this is also exactly what gets narrated)
  appendix: chronology, evidence guide, notes and references as HTML, text only
Run from scripts/: python3 extract_colossus.py   (needs pandoc)
"""
import json, os, re, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCX = os.path.join(ROOT, 'Colossus_of_Rhodes.docx')
md = subprocess.run(['pandoc', '-t', 'markdown', '--wrap=none', DOCX], capture_output=True, text=True, check=True).stdout


TABLE = re.compile(r'^ *-{20,} *\n(?:.*\n)+? *-{20,} *$', re.M)   # a pandoc multiline table


def table_prose(block):
    """A table read aloud: one sentence group per row, headed by the column names."""
    h = subprocess.run(['pandoc', '-f', 'markdown', '-t', 'html', '--wrap=none'], input=block, capture_output=True, text=True, check=True).stdout
    cell = lambda x: re.sub(r'<[^>]+>', '', x).strip()
    heads = [cell(x) for x in re.findall(r'<th[^>]*>(.*?)</th>', h, re.S)]
    rows = [[cell(x) for x in re.findall(r'<td[^>]*>(.*?)</td>', r, re.S)] for r in re.findall(r'<tr[^>]*>(.*?)</tr>', h, re.S)]
    lines = []
    for r in rows:
        if not r: continue
        bits = [r[0].rstrip('.') + '.'] + [f'{heads[i]}: {v}' for i, v in enumerate(r[1:], 1) if i < len(heads) and v]
        lines.append(' '.join(b if b.endswith('.') else b + '.' for b in bits))
    return '\n\n'.join(lines)


def plain(s):
    s = re.sub(r'\s*\[\\\[[^\]]*\\\]\]\(#ref_\d+\)', '', s)          # [\[1,8\]](#ref_1)
    s = TABLE.sub(lambda m: table_prose(m.group(0)), s)
    out = subprocess.run(['pandoc', '-f', 'markdown', '-t', 'plain', '--wrap=none'], input=s, capture_output=True, text=True, check=True).stdout
    return '\n'.join(p.strip() for p in out.split('\n\n') if p.strip())


def html(s):
    s = re.sub(r'\[\\\[([^\]]*)\\\]\]\(#ref_\d+\)', r'<sup>[\1]</sup>', s)
    s = re.sub(r'\[\]\{#ref_\d+ \.anchor\}', '', s)
    return subprocess.run(['pandoc', '-f', 'markdown', '-t', 'html', '--wrap=none', '--shift-heading-level-by=1'], input=s, capture_output=True, text=True, check=True).stdout


parts = re.split(r'^# (.+)$', md, flags=re.M)
intro, heads = parts[0], list(zip(parts[1::2], parts[2::2]))
intro = intro.replace('White paper \\| Research current to 20 September 2026', '')
chapters = [{'n': 0, 'slug': 'introduction', 'title': 'The Colossus in three lives', 'text': plain(intro)}]
appendix = []
for title, body in heads:
    m = re.match(r'(\d+) (.+)', title)
    if m:
        n, t = int(m.group(1)), m.group(2).strip()
        slug = re.sub(r'[^a-z0-9]+', '-', t.lower()).strip('-')[:40].strip('-')
        ch = {'n': n, 'slug': slug, 'title': t, 'text': plain(body)}
        if TABLE.search(body): ch['html'] = html(body)
        chapters.append(ch)
    else:
        appendix.append('# ' + title + '\n' + body)
out = {'title': 'The Colossus of Rhodes', 'subtitle': 'A long-form history · research current to 20 September 2026',
       'chapters': chapters, 'appendix': html('\n\n'.join(appendix))}
json.dump(out, open(os.path.join(ROOT, 'narration', 'colossus.json'), 'w'), ensure_ascii=False, indent=1)
for c in chapters: print(f"{c['n']:2d} {len(c['text']):5d}  {c['title']}")
print('spoken total', sum(len(c['text']) for c in chapters), '| appendix html', len(out['appendix']))
