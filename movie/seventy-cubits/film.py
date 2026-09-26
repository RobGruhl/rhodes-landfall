#!/usr/bin/env python3
"""Build "Seventy Cubits" from film.json.

Paid stages (each previews every call and spends nothing without --yes; finished files in
renders/ are skipped, so delete one to redo it):

  film.py audition [--yes]    one line in each candidate voice      -> renders/voice-<Name>.mp3
  film.py refs [--yes]        a reference image per character       -> renders/ref-<name>.png
  film.py narration [--yes]   each scene spoken in voice.preset     -> renders/nar-<scene>.mp3
  film.py keyframes [--yes]   one still per shot, characters by ref -> renders/<scene>-<n>.png
  film.py clips [--yes]       each still animated, cut to the words -> renders/<scene>-<n>-clip.mp4
  film.py sound [--yes]       the lyre bed and each scene's ambience -> renders/snd-<name>.mp3

Free:

  film.py cost                the whole bill, from the narration if it exists, else estimated
  film.py assemble            titles, cuts, narration over bed and ambience -> seventy-cubits.mp4

Each scene lasts as long as its narration plus LEAD and TAIL; its shots split that evenly and
render whole seconds (2-10) at least that long. Needs a sibling Toolbelt clone (or $RWY pointing
at rwy.mjs), ffmpeg and ffprobe (or $FFMPEG, $FFPROBE) and headless Chrome for the title cards
($CHROME; $FONT is a CSS font-family).
"""
import json, math, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "renders"
RWY = os.environ.get("RWY", str(HERE.parents[2] / "Toolbelt/tools/runway-ai/rwy.mjs"))
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
FFPROBE = os.environ.get("FFPROBE", "ffprobe")
CHROME = os.environ.get("CHROME", "chromium")
FONT = os.environ.get("FONT", "'Palatino Linotype', Palatino, 'DejaVu Serif', Georgia, serif")
FILM = json.loads((HERE / "film.json").read_text())
SCENES = FILM["scenes"]

LEAD, TAIL = 0.8, 1.2          # seconds of picture before and after each scene's narration
TITLE, END = 5.0, 6.0          # title and end cards
CHARS_PER_S = 13.0             # narration pace for estimates before the voice is rendered
IMAGE, TURBO_PER_S, SOUND_S = 5, 5, 30   # credits: gen4_image at 1280:720, gen4_turbo per second, one 30 s bed


def rwy(args, yes):
    return subprocess.run(["node", RWY, *args, "--out", str(OUT)] + (["--yes"] if yes else [])).returncode


def run_all(jobs, yes):
    """jobs: [(output file, rwy args, credits)]. Returns credits for the jobs still to do."""
    todo = [j for j in jobs if not j[0].exists()]
    for f, args, _ in todo:
        if rwy(args, yes):
            sys.exit(f"{f.name}: rwy failed; nothing after it was sent")
    return sum(c for _, _, c in todo)


def duration(f):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout)


def speech_credits(text):
    return math.ceil(len(text) / 50)


def scene_seconds(sc):
    nar = OUT / f"nar-{sc['id']}.mp3"
    spoken = duration(nar) if nar.exists() else len(sc["text"]) / CHARS_PER_S
    return LEAD + spoken + TAIL, nar.exists()


def shot_plan():
    """Per shot: the seconds it is on screen and the whole seconds it is rendered."""
    plan = []
    for sc in SCENES:
        total, measured = scene_seconds(sc)
        each = total / len(sc["shots"])
        for i, sh in enumerate(sc["shots"], 1):
            plan.append({"scene": sc, "shot": sh, "stem": f"{sc['id']}-{i}", "show": each,
                         "render": min(10, max(2, math.ceil(each))), "measured": measured})
    return plan


# -- stages ---------------------------------------------------------------------------------

def audition(yes):
    a, v = FILM["audition"], FILM["voice"]
    return run_all([(OUT / f"voice-{name}.mp3",
                     ["speech", a["line"], "--voice", name, "--model", v["model"], "--stability", str(v["stability"]),
                      "--speed", str(v["speed"]), "--name", f"voice-{name}"], speech_credits(a["line"]))
                    for name in a["voices"]], yes)


def refs(yes):
    return run_all([(OUT / f"ref-{k}.png",
                     ["image", f"{p}. {FILM['style']}", "--model", "gen4_image", "--ratio", "1280:720", "--name", f"ref-{k}"], IMAGE)
                    for k, p in FILM["characters"].items()], yes)


def narration(yes):
    v = FILM["voice"]
    if not v.get("preset"):
        sys.exit("set voice.preset in film.json first (run `film.py audition` and listen)")
    jobs = []
    for sc in SCENES:
        txt = OUT / f"nar-{sc['id']}.txt"
        OUT.mkdir(exist_ok=True)
        txt.write_text(sc["text"] + "\n")
        jobs.append((OUT / f"nar-{sc['id']}.mp3",
                     ["speech", "--text-file", str(txt), "--voice", v["preset"], "--model", v["model"],
                      "--stability", str(v["stability"]), "--speed", str(v["speed"]), "--name", f"nar-{sc['id']}"],
                     speech_credits(sc["text"])))
    return run_all(jobs, yes)


def keyframes(yes):
    jobs = []
    for p in shot_plan():
        sh = p["shot"]
        args = ["image", f"{sh['still']}. {FILM['style']}", "--model", "gen4_image", "--ratio", "1280:720", "--name", p["stem"]]
        for r in sh.get("refs", []):
            ref = OUT / f"ref-{r}.png"
            if yes and not ref.exists():
                sys.exit(f"{p['stem']}: needs {ref.name}; run `film.py refs --yes` first")
            args += ["--ref", f"{r}={ref}"] if ref.exists() else []
        if not all((OUT / f"ref-{r}.png").exists() for r in sh.get("refs", [])):
            print(f"{p['stem']}: gen4_image with refs {sh['refs']} (not drawn yet), {IMAGE} credits: {sh['still']}")
            jobs.append((OUT / f"{p['stem']}.png", None, IMAGE))
            continue
        jobs.append((OUT / f"{p['stem']}.png", args, IMAGE))
    ready = [j for j in jobs if j[1] is not None]
    return run_all(ready, yes) + sum(c for f, a, c in jobs if a is None and not f.exists())


def clips(yes):
    plan = shot_plan()
    if yes and not all(p["measured"] for p in plan):
        sys.exit("render the narration first: clip lengths are cut to it")
    total = 0
    for p in plan:
        f, still = OUT / f"{p['stem']}-clip.mp4", OUT / f"{p['stem']}.png"
        if f.exists():
            continue
        credits = p["render"] * TURBO_PER_S
        if not still.exists():
            if yes:
                sys.exit(f"{p['stem']}: no keyframe; run `film.py keyframes --yes` first")
            print(f"{p['stem']}: gen4_turbo {p['render']} s from {still.name} (not drawn yet), {credits} credits")
            total += credits
            continue
        total += run_all([(f, ["video", p["shot"]["motion"], "--image", str(still), "--model", "gen4_turbo",
                               "--ratio", "1280:720", "--duration", str(p["render"]), "--name", f"{p['stem']}-clip"], credits)], yes)
    return total


def sound(yes):
    return run_all([(OUT / f"snd-{k}.mp3",
                     ["audio", s["prompt"], "--duration", str(SOUND_S), "--loop", "--name", f"snd-{k}"], SOUND_S)
                    for k, s in FILM["sound"].items()], yes)


def cost():
    plan = shot_plan()
    measured = all(p["measured"] for p in plan)
    rows = [
        ("audition", sum(speech_credits(FILM["audition"]["line"]) for n in FILM["audition"]["voices"] if not (OUT / f"voice-{n}.mp3").exists())),
        ("refs", sum(IMAGE for k in FILM["characters"] if not (OUT / f"ref-{k}.png").exists())),
        ("narration", sum(speech_credits(s["text"]) for s in SCENES if not (OUT / f"nar-{s['id']}.mp3").exists())),
        ("keyframes", sum(IMAGE for p in plan if not (OUT / f"{p['stem']}.png").exists())),
        ("clips", sum(p["render"] * TURBO_PER_S for p in plan if not (OUT / f"{p['stem']}-clip.mp4").exists())),
        ("sound", sum(SOUND_S for k in FILM["sound"] if not (OUT / f"snd-{k}.mp3").exists())),
    ]
    runtime = TITLE + sum(p["show"] for p in plan) + END
    for k, c in rows:
        print(f"  {k:10} {c:5} credits  (${c / 100:.2f})")
    t = sum(c for _, c in rows)
    print(f"  {'total':10} {t:5} credits  (${t / 100:.2f}) still to spend")
    print(f"runtime {runtime / 60:.1f} min, {len(plan)} shots, {sum(p['render'] for p in plan)} s rendered"
          f" ({'from the narration' if measured else f'estimated at {CHARS_PER_S:.0f} characters a second'})")


# -- assembly -------------------------------------------------------------------------------

def card(dest, seconds, lines):
    """A black card with centred serif lines, drawn by headless Chrome: [(text, px size)]."""
    html = dest.with_suffix(".html")
    rows = "".join(f'<div style="font-size:{size}px;margin:{size * 0.35:.0f}px 0">{text}</div>' for text, size in lines)
    html.write_text(f"""<!doctype html><meta charset="utf-8"><body style="margin:0;width:1280px;height:720px;background:#000;
        color:#e8dcc0;font-family:{FONT};display:flex;flex-direction:column;align-items:center;justify-content:center;
        letter-spacing:.04em;text-align:center">{rows}</body>""")
    png = dest.with_suffix(".png")
    subprocess.run([CHROME, "--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", f"--screenshot={png}",
                    "--window-size=1280,720", html.as_uri()], check=True, capture_output=True)
    subprocess.run([FFMPEG, "-y", "-v", "error", "-loop", "1", "-framerate", "24", "-t", str(seconds), "-i", str(png),
                    "-vf", f"scale=1280:720,setsar=1,fade=t=in:d=1,fade=t=out:st={seconds - 1}:d=1",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(dest)], check=True)


def assemble():
    plan = shot_plan()
    missing = [p["stem"] for p in plan if not (OUT / f"{p['stem']}-clip.mp4").exists()] + \
              [s["id"] for s in SCENES if not (OUT / f"nar-{s['id']}.mp3").exists()]
    if missing:
        sys.exit(f"missing renders: {' '.join(missing)}")
    work = OUT / "cut"
    work.mkdir(exist_ok=True)
    card(work / "title.mp4", TITLE, [(FILM["title"], 64), ("Rhodes, 305 to 226 BC", 26)])
    card(work / "end.mp4", END, [(FILM["title"], 40), ("A story of the Colossus, built on the tour's research", 22),
                                 ("Pictures by Runway · voice by ElevenLabs through Runway", 20)])

    # Picture: each scene's shots trimmed to their share, scene fades at the joins.
    scene_files, t, starts = [], TITLE, {}
    for sc in SCENES:
        shots = [p for p in plan if p["scene"] is sc]
        n = len(shots)
        length = sum(p["show"] for p in shots)
        inputs = sum((["-i", str(OUT / f"{p['stem']}-clip.mp4")] for p in shots), [])
        parts = [f"[{i}:v]trim=0:{p['show']:.3f},setpts=PTS-STARTPTS,scale=1280:720,fps=24,setsar=1[v{i}]" for i, p in enumerate(shots)]
        graph = ";".join(parts) + ";" + "".join(f"[v{i}]" for i in range(n)) + \
            f"concat=n={n}:v=1:a=0,fade=t=in:d=0.5,fade=t=out:st={length - 0.5:.3f}:d=0.5[v]"
        f = work / f"{sc['id']}.mp4"
        subprocess.run([FFMPEG, "-y", "-v", "error", *inputs, "-filter_complex", graph, "-map", "[v]",
                        "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(f)], check=True)
        scene_files.append(f)
        starts[sc["id"]] = (t, length)
        t += length
    total = t + END
    listing = work / "list.txt"
    listing.write_text("".join(f"file '{f}'\n" for f in [work / "title.mp4", *scene_files, work / "end.mp4"]))
    picture = work / "picture.mp4"
    subprocess.run([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(picture)], check=True)

    # Sound: narration at each scene's start + LEAD; the lyre bed throughout; each scene's ambience under it.
    inputs, chains, mix = ["-i", str(picture)], [], []
    idx = 1
    for sc in SCENES:
        start, _ = starts[sc["id"]]
        inputs += ["-i", str(OUT / f"nar-{sc['id']}.mp3")]
        chains.append(f"[{idx}:a]adelay={int((start + LEAD) * 1000)}:all=1[n{idx}]"); mix.append(f"[n{idx}]"); idx += 1
    bed = FILM["sound"]["bed"]
    inputs += ["-stream_loop", "-1", "-i", str(OUT / "snd-bed.mp3")]
    chains.append(f"[{idx}:a]atrim=0:{total:.3f},volume={bed['volume']},afade=t=in:d=2,afade=t=out:st={total - 3:.3f}:d=3[bed]"); mix.append("[bed]"); idx += 1
    for sc in SCENES:
        if not sc.get("ambience"):
            continue
        start, length = starts[sc["id"]]
        s = FILM["sound"][sc["ambience"]]
        inputs += ["-stream_loop", "-1", "-i", str(OUT / f"snd-{sc['ambience']}.mp3")]
        chains.append(f"[{idx}:a]atrim=0:{length:.3f},asetpts=PTS-STARTPTS,volume={s['volume']},afade=t=in:d=1,"
                      f"afade=t=out:st={length - 1.2:.3f}:d=1.2,adelay={int(start * 1000)}:all=1[a{idx}]")
        mix.append(f"[a{idx}]"); idx += 1
    graph = ";".join(chains) + ";" + "".join(mix) + f"amix=inputs={len(mix)}:duration=longest:normalize=0,atrim=0:{total:.3f},loudnorm=I=-16:TP=-1.5:LRA=11[a]"
    dest = HERE / "seventy-cubits.mp4"
    subprocess.run([FFMPEG, "-y", "-v", "error", *inputs, "-filter_complex", graph, "-map", "0:v", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(dest)], check=True)
    print(f"wrote {dest} ({total / 60:.1f} min)")


if __name__ == "__main__":
    stage, yes = (sys.argv[1] if len(sys.argv) > 1 else ""), "--yes" in sys.argv
    OUT.mkdir(exist_ok=True)
    if stage in ("cost", "assemble"):
        globals()[stage]()
    elif stage in ("audition", "refs", "narration", "keyframes", "clips", "sound"):
        credits = globals()[stage](yes)
        print(f"\n{stage}: {credits} credits (${credits / 100:.2f}) {'spent' if yes else 'if run with --yes'}")
    else:
        sys.exit(__doc__)
