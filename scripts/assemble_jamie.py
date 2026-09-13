#!/usr/bin/env python3
"""Turn the writing workflow's JSON result into narration/jamie-01-11.json and narration/jamie-12-22.json.

Usage: python3 scripts/assemble_jamie.py <workflow-output-file>
The output file is the task output written by the Workflow tool; its result object has a `stops` list of
{n, slug, title, short, long, notes}. Checks: 22 stops, no digits, character limits, slug matches Rob's set.
"""
import json, re, sys, glob
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
doc = json.load(open(sys.argv[1]))
res = doc.get('result', doc)
if 'stops' not in res:
    sys.exit("no stops in the result object")
stops = sorted(res['stops'], key=lambda x: x['n'])
rob = {x['n']: x for f in sorted(glob.glob(str(ROOT / 'narration' / 'rob-*.json'))) for x in json.load(open(f))}
problems = []
for st in stops:
    if st['slug'] != rob[st['n']]['slug']:
        problems.append(f"{st['n']}: slug {st['slug']} != {rob[st['n']]['slug']}")
    for k in ('short', 'long'):
        t = st[k]
        if re.search(r'\d', t): problems.append(f"{st['n']} {k}: digits: " + ', '.join(re.findall(r'[^ ]*\d[^ ]*', t)[:4]))
        if re.search(r'[*#\[\]<>_]', t): problems.append(f"{st['n']} {k}: markup characters")
        if len(t) > 4800: problems.append(f"{st['n']} {k}: {len(t)} chars over the ceiling")
    if not (400 <= len(st['short']) <= 800): problems.append(f"{st['n']} short: {len(st['short'])} chars")
    if not (1600 <= len(st['long']) <= 4800): problems.append(f"{st['n']} long: {len(st['long'])} chars")
if len(stops) != 22:
    problems.append(f"{len(stops)} stops, expected 22")
for p in problems: print("WARN", p)
def rec(st): return {"n": st['n'], "slug": st['slug'], "title": st['title'], "short": st['short'].strip(), "long": st['long'].strip()}
json.dump([rec(s) for s in stops if s['n'] <= 11], open(ROOT / 'narration' / 'jamie-01-11.json', 'w'), ensure_ascii=False, indent=1)
json.dump([rec(s) for s in stops if s['n'] >= 12], open(ROOT / 'narration' / 'jamie-12-22.json', 'w'), ensure_ascii=False, indent=1)
notes = ["# Jamie narration: writers' source notes", ""]
for st in stops:
    notes += [f"## {st['n']:02d} {st['slug']}: {st['title']}", "", (st.get('notes') or '(none)').strip(), ""]
(ROOT / 'narration' / 'jamie-notes.md').write_text('\n'.join(notes))
tot = sum(len(s['short']) + len(s['long']) for s in stops)
print(f"wrote {len(stops)} stops; {tot:,} characters to render; {len(problems)} warnings")
