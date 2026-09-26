#!/usr/bin/env python3
"""Build storyboard.html from shots.json, cast.json, concept.json and style.json.

Keyframes, cast sheets and concept art from out/ are embedded (as small JPEGs) when they exist;
until then each frame shows the scene's lighting as a colour-script panel.
"""
import base64, html, io, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
STYLE = json.loads((HERE / "style.json").read_text())
CAST = json.loads((HERE / "cast.json").read_text())
SHOTS = json.loads((HERE / "shots.json").read_text())
CONCEPT = json.loads((HERE / "concept.json").read_text())

# Colour script: the light of each scene, top of frame to bottom.
LIGHT = {
    "1": ("#1d2a3d", "#3d5670", "#c9954a"),   # before dawn: blue, then first gold
    "2": ("#6b5a45", "#a58458", "#d8b98a"),   # kilns: smoke and ochre
    "3": ("#9fb6c4", "#d9d2bf", "#b98a55"),   # harbour: hard noon
    "4": ("#c98f3e", "#e3bb74", "#8a5a2e"),   # gymnasium: heat
    "5": ("#1a120c", "#6b3d1d", "#d08a3c"),   # club: lamplight
    "6": ("#0c1220", "#24334d", "#8e9bb3"),   # night: moon
    "7": ("#1d2a3d", "#34506b", "#b98646"),   # morning again
    "8": ("#8f8a80", "#c8c2b4", "#a0714a"),   # epilogue: modern daylight
}
E = html.escape


def img_uri(p, w=960):
    if not p.exists():
        return None
    from PIL import Image
    im = Image.open(p).convert("RGB")
    im.thumbnail((w, w))
    b = io.BytesIO(); im.save(b, "JPEG", quality=78)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


def tc(t):
    return f"{int(t // 60)}:{int(t % 60):02d}"


def frame(s):
    uri = img_uri(OUT / "keyframes" / f"{s['id']}.png")
    if uri:
        return f'<img src="{uri}" alt="{E(s["frame"])}">'
    a, b, c = LIGHT[s["scene"].split(".")[0]]
    return (f'<div class="light" style="--a:{a};--b:{b};--c:{c}"><span>{E(s["shot"])}</span></div>')


def line_html(ln):
    who = "ALL" if ln["who"] == "all" else CAST[ln["who"]]["name"].split(" ")[0].upper()
    text = ln["text"]
    paren = ""
    if text.startswith("["):
        end = text.index("]")
        paren, text = text[1:end], text[end + 1:].strip()
    p = f'<span class="paren">({E(paren)})</span>' if paren else ""
    t = f'<span class="said">{E(text)}</span>' if text else ""
    return f'<div class="line"><span class="who">{E(who)}</span>{p}{t}</div>'


def concept_html(c):
    u = img_uri(OUT / "concept" / (c["id"] + ".png"))
    pic = f'<img src="{u}" alt="{E(c["title"])}">' if u else '<div class="pending">Awaiting render</div>'
    return f'<figure class="concept">{pic}<figcaption><b>{E(c["title"])}</b>{E(c["prompt"])}</figcaption></figure>'


def person_html(k, v):
    u = img_uri(OUT / "cast" / (k + ".png"), 480)
    pic = f'<img src="{u}" alt="{E(v["name"])}">' if u else ""
    age = f' <small>{v["age"]}</small>' if v["age"] else ""
    voice = f'<p class="voice">Voice: {E(v["voice"]["name"])}, {E(v["voice"]["direction"])}</p>' if v["voice"] else ""
    return f'<div class="person">{pic}<h4>{E(v["name"])}{age}</h4><p>{E(v["look"])}.</p>{voice}</div>'


def build():
    t, parts, scene, strip = 0.0, [], None, []
    total = sum(s["cut"] for s in SHOTS)
    for s in SHOTS:
        if s.get("card"):
            strip.append(f'<i style="flex:{s["cut"]};background:var(--ink)" title="Title card"></i>')
            parts.append(f'<article class="card-title" id="{s["id"]}"><div class="tc">{tc(t)}</div>'
                         f'<p class="ct">{E(s["text"])}</p><p class="cs">{E(s.get("sub", ""))}</p></article>')
            t += s["cut"]; continue
        if s["scene"] != scene:
            scene = s["scene"]
            num, name = scene.split(". ", 1)
            parts.append(f'<h3 class="scene"><span>Scene {num}</span>{E(name)}</h3>')
        a, b, c = LIGHT[s["scene"].split(".")[0]]
        strip.append(f'<i style="flex:{s["cut"]};background:linear-gradient({a},{b},{c})" title="{s["id"]}"></i>')
        lines = "".join(line_html(l) for l in s["lines"])
        parts.append(f'''<article class="shot" id="{s["id"]}">
  <div class="frame">{frame(s)}</div>
  <div class="meta"><span class="id">{s["id"].upper()}</span><span>{tc(t)}</span><span>{s["cut"]} s</span><span>{E(s["shot"])}</span></div>
  <p class="desc">{E(s["frame"])}.</p>
  <p class="move"><b>Camera and motion</b> {E(s["motion"])}</p>
  {f'<div class="script">{lines}</div>' if lines else ''}
  <p class="sfx"><b>Sound</b> {E(s["sfx"])}</p>
</article>''')
        t += s["cut"]

    concept = "".join(concept_html(c) for c in CONCEPT)
    cast = "".join(person_html(k, v) for k, v in CAST.items())
    music = "".join(f'<li><b>{m["id"].upper()}</b> from {m["at"].upper()}, {m["len"]} s. {E(m["prompt"])}</li>' for m in STYLE["music"])

    page = TEMPLATE.format(title=E(STYLE["title"]), logline=E(STYLE["logline"]), rule=E(STYLE["rule"]),
                           look=E(STYLE["look"]), runtime=tc(total), nshots=sum(1 for s in SHOTS if not s.get("card")),
                           strip="".join(strip), concept=concept, cast=cast, shots="".join(parts), music=music)
    (HERE / "storyboard.html").write_text(page)
    print("wrote storyboard.html")


TEMPLATE = """<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Marcellus&family=Alegreya+Sans:ital,wght@0,400;0,500;0,700;1,400&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{{--ground:#ebe6dc;--panel:#f6f2ea;--ink:#1a2230;--soft:#5b6270;--rule:#cfc6b6;--bronze:#9a6b25;--sea:#2f5d78;
  --disp:"Marcellus",Georgia,serif;--body:"Alegreya Sans",system-ui,sans-serif;--mono:"IBM Plex Mono",ui-monospace,monospace}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--ground:#121821;--panel:#1a222e;--ink:#e6e0d3;--soft:#9aa3b1;--rule:#2d3847;--bronze:#d3a55a;--sea:#7fb0cc;color-scheme:dark}}}}
:root[data-theme="dark"]{{--ground:#121821;--panel:#1a222e;--ink:#e6e0d3;--soft:#9aa3b1;--rule:#2d3847;--bronze:#d3a55a;--sea:#7fb0cc;color-scheme:dark}}
body{{background:var(--ground);color:var(--ink);font:17px/1.55 var(--body);padding-inline:clamp(16px,4vw,56px);padding-block:40px 80px}}
.wrap{{max-width:1180px;margin:0 auto;display:grid;gap:56px}}
header{{display:grid;gap:14px;max-width:62ch}}
.eyebrow{{font:500 12px/1 var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--bronze)}}
h1{{font:400 clamp(38px,6vw,68px)/1.02 var(--disp);letter-spacing:.02em;margin:0;text-wrap:balance}}
.logline{{font-size:21px;margin:0}}
.rule{{margin:0;padding-left:14px;border-left:2px solid var(--bronze);color:var(--soft);font-style:italic}}
h2{{font:400 28px/1.1 var(--disp);margin:0 0 18px;letter-spacing:.03em}}
.strip{{display:flex;height:46px;border-radius:3px;overflow:hidden;gap:1px;background:var(--rule)}}
.strip i{{display:block;min-width:1px}}
.stripcap{{display:flex;justify-content:space-between;font:12px var(--mono);color:var(--soft);margin-top:6px}}
.concepts{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:18px}}
.concept{{margin:0;display:grid;gap:8px}}
.concept img,.pending{{width:100%;aspect-ratio:16/9;object-fit:cover;border-radius:2px;display:block}}
.pending{{display:grid;place-items:center;background:var(--panel);border:1px dashed var(--rule);color:var(--soft);font:12px var(--mono);letter-spacing:.1em;text-transform:uppercase}}
figcaption{{font-size:14px;color:var(--soft)}}
figcaption b{{display:block;color:var(--ink);font:400 17px var(--disp);margin-bottom:2px}}
.cast{{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:22px 28px}}
.person h4{{font:400 20px var(--disp);margin:0 0 4px}}
.person small{{font:12px var(--mono);color:var(--soft);margin-left:6px}}
.person p{{margin:0;font-size:15px}}
.person img{{width:100%;border-radius:2px;margin-bottom:8px}}
.voice{{color:var(--sea);margin-top:6px!important}}
.board{{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,500px),1fr));gap:36px 32px}}
.scene{{grid-column:1/-1;margin:18px 0 -8px;font:400 26px var(--disp);display:flex;gap:14px;align-items:baseline;border-bottom:1px solid var(--rule);padding-bottom:8px}}
.scene span{{font:500 12px var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--bronze)}}
.shot{{display:grid;gap:10px;align-content:start}}
.frame{{aspect-ratio:16/9;max-width:100%;border-radius:2px;overflow:hidden;background:#000}}
.frame img{{width:100%;height:100%;object-fit:cover;display:block}}
.light{{box-sizing:border-box;height:100%;background:linear-gradient(var(--a),var(--b) 62%,var(--c));display:flex;align-items:flex-end;padding:10px 12px}}
.light span{{font:12px var(--mono);letter-spacing:.08em;color:#f3ecdf;text-shadow:0 1px 3px #0008;text-transform:uppercase}}
.meta{{display:flex;flex-wrap:wrap;gap:4px 14px;font:13px var(--mono);color:var(--soft);font-variant-numeric:tabular-nums}}
.meta .id{{color:var(--bronze);font-weight:500}}
.desc{{margin:0}}
.move,.sfx{{margin:0;font-size:15px;color:var(--soft)}}
.move b,.sfx b{{font:500 11px var(--mono);letter-spacing:.12em;text-transform:uppercase;color:var(--ink);margin-right:6px}}
.script{{font-family:var(--mono);font-size:14px;display:grid;gap:10px;padding:14px 16px;background:var(--panel);border-radius:2px}}
.line{{display:grid;gap:1px;justify-items:center;text-align:center}}
.who{{letter-spacing:.1em}}
.paren{{color:var(--soft);font-style:italic}}
.said{{max-width:36ch}}
.card-title{{grid-column:1/-1;background:#0f0d0b;color:#e8dcc4;border-radius:2px;padding:44px 24px;text-align:center;display:grid;gap:8px;position:relative}}
.card-title .tc{{position:absolute;top:12px;left:14px;font:12px var(--mono);color:#8c7f6a}}
.ct{{font:400 clamp(22px,3vw,32px)/1.2 var(--disp);margin:0;text-wrap:balance}}
.cs{{margin:0;color:#b0a084;font-style:italic}}
.notes{{display:grid;gap:10px;max-width:70ch}}
.notes ul{{margin:0;padding-left:20px;display:grid;gap:8px}}
.notes p{{margin:0}}
</style>
<div class="wrap">
<header>
  <div class="eyebrow">Storyboard · historical short · about {runtime} · {nshots} shots</div>
  <h1>{title}</h1>
  <p class="logline">{logline}</p>
  <p class="rule">{rule}</p>
</header>
<section>
  <h2>Colour script</h2>
  <div class="strip">{strip}</div>
  <div class="stripcap"><span>0:00 dawn</span><span>kilns</span><span>harbour</span><span>gymnasium</span><span>club</span><span>night</span><span>{runtime}</span></div>
</section>
<section>
  <h2>Concept art</h2>
  <div class="concepts">{concept}</div>
</section>
<section>
  <h2>Cast</h2>
  <div class="cast">{cast}</div>
</section>
<section>
  <h2>Shots</h2>
  <div class="board">{shots}</div>
</section>
<section class="notes">
  <h2>Look, sound and the rules</h2>
  <p>{look}</p>
  <ul>{music}</ul>
  <p>Dialogue is staged so that lips rarely carry the line: backs, profiles, hands, wide frames and off-screen voices. It suits the film's reticence, and it keeps generated faces from having to lip-sync.</p>
  <p>The Colossus appears only as light on faces, a cropped bronze shin at dawn, the face on a stamp and a coin, and its toes above a pedestal at night. It is never shown whole.</p>
</section>
</div>
"""

if __name__ == "__main__":
    build()
