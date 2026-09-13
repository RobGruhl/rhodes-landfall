#!/usr/bin/env python3
"""Typeset the long narration scripts as a PDF per set: docs/scripts-rob.pdf, docs/scripts-jamie.pdf.

Usage: python3 scripts/scripts_pdf.py [rob|jamie ...]   (default: both)
Needs typst (brew install typst).
"""
import glob, json, re, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
NAMES = {"rob": "Rob", "jamie": "Jamie"}
DAY = "Wednesday 30 September 2026"

def esc(s):
    return re.sub(r'([\\#*_$@<>\[\]`~])', r'\\\1', s)

def build(narr_set):
    stops = []
    for f in sorted(glob.glob(str(ROOT / "narration" / f"{narr_set}-*.json"))):
        stops += json.load(open(f))
    stops.sort(key=lambda s: s["n"])
    pins = {p.get("aud"): p for p in json.load(open(ROOT / "data" / "pins.json")) if p.get("aud")}
    name = NAMES.get(narr_set, narr_set.title())
    out = [f'''#set page(paper: "a5", margin: (x: 16mm, y: 18mm), numbering: "1", number-align: center)
#set text(font: ("Cardo", "Georgia", "Times New Roman"), size: 10.5pt, lang: "en")
#set par(justify: true, leading: 0.65em, spacing: 0.9em)
#show heading.where(level: 1): it => block(above: 2.2em, below: 1em)[#text(size: 15pt, weight: "bold")[#it.body]]
#v(1fr)
#align(center)[#text(size: 24pt, weight: "bold")[Rhodes Landfall] \\ #v(0.6em) #text(size: 13pt)[{esc(name)}'s track: the long scripts] \\ #v(0.4em) #text(size: 10.5pt, fill: luma(90))[{DAY} · Scarlet Lady · alongside 09:00, sails 18:00]]
#v(1.4fr)
#pagebreak()
''']
    for s in stops:
        pin = pins.get(s["slug"], {})
        place = pin.get("name", "")
        out.append(f'= {s["n"]:02d} · {esc(s["title"])}\n')
        if place:
            out.append(f'#text(size: 9.5pt, fill: luma(90), style: "italic")[{esc(place)}]\n#v(0.4em)\n')
        for para in [p.strip() for p in s["long"].split("\n") if p.strip()]:
            out.append(esc(para) + "\n\n")
        out.append("#pagebreak(weak: true)\n")
    typ = ROOT / "docs" / f"scripts-{narr_set}.typ"
    pdf = ROOT / "docs" / f"scripts-{narr_set}.pdf"
    typ.write_text("".join(out))
    subprocess.run(["typst", "compile", str(typ), str(pdf)], check=True)
    typ.unlink()
    print(f"{pdf} ({len(stops)} stops, {pdf.stat().st_size//1024} KB)")

for narr_set in (sys.argv[1:] or ["rob", "jamie"]):
    build(narr_set)
