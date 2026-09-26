#!/usr/bin/env python3
"""Render "In the Priesthood of the Sun" from film/shots.json.

Stages (run in order; each skips files that already exist, so reruns resume):
  concept    concept art from concept.json            Gemini image
  cast       one reference sheet per character        Gemini image
  keyframes  one still per shot, cast sheets as refs  Gemini image
  video      animate each keyframe                    Runway image_to_video
  voice      every dialogue line                      ElevenLabs TTS
  sfx        one ambience/effects bed per shot        ElevenLabs sound generation
  music      the three cues in style.json             ElevenLabs music
  assemble   cut, mix, subtitle -> out/film.mp4       ffmpeg (local, free)

`assemble` works with whatever exists: a Runway clip if present, else the keyframe with a slow
push-in, else a drawn storyboard card; so it doubles as the animatic.

Keys: GEMINI_API_KEY, RUNWAYML_API_SECRET, ELEVENLABS_API_KEY.
Nothing that costs money runs without --yes; the estimate is printed first.

  python3 produce.py estimate
  python3 produce.py concept cast keyframes --yes
  python3 produce.py video --yes --only s05,s06
  python3 produce.py assemble
"""
import argparse, base64, io, json, os, re, subprocess, sys, textwrap, time, urllib.error, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
STYLE = json.loads((HERE / "style.json").read_text())
CAST = json.loads((HERE / "cast.json").read_text())
SHOTS = json.loads((HERE / "shots.json").read_text())
CONCEPT = json.loads((HERE / "concept.json").read_text())
W, H, FPS = 1280, 720, 24
SERIF = "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"
SERIF_I = "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf"

# Rough list prices; the estimate is a guide, not a bill.
PRICE_IMAGE = 0.039            # Gemini 2.5 Flash Image, per image
PRICE_RUNWAY_S = 0.05          # gen4_turbo: 5 credits/s at $0.01
PRICE_TTS_CHAR = 0.00022       # ElevenLabs overage-ish, per character
PRICE_SFX = 0.10               # per generation, roughly
PRICE_MUSIC_S = 0.01

# ElevenLabs premade voices, used when the account's library has no voice of that name.
PREMADE = {"George": "JBFqnCBsd6RMkjVDRZzb", "Liam": "TX3LPaxmHKxFdv7VOQHJ", "Bill": "pqHfZKP75CvOlQylNhV4",
           "Charlie": "IKne3meq5aSn9XLyUdCD", "Daniel": "onwK4e9ZLuTAKqWW03F9", "Brian": "nPczCjzI2devNBz1zQrb"}
CHORUS = ["father", "freedman", "merchant", "lysistratos"]


def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit("ffmpeg failed:\n" + " ".join(map(str, cmd)) + "\n" + r.stderr[-2000:])
    return r


def duration(path):
    r = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0.0


def key(name):
    k = os.environ.get(name, "").strip()
    if not k:
        sys.exit(f"{name} is not set.")
    return k


def http(url, body=None, headers=None, method=None, raw=False, timeout=300):
    data = json.dumps(body).encode() if body is not None and not isinstance(body, bytes) else body
    h = {"Content-Type": "application/json"} if body is not None else {}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                b = r.read()
                return b if raw else json.loads(b)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:800]
            if e.code in (429, 500, 502, 503) and attempt < 3:
                time.sleep(2 ** (attempt + 2)); continue
            sys.exit(f"HTTP {e.code} from {url.split('?')[0]}: {msg}")
        except urllib.error.URLError as e:
            if attempt < 3:
                time.sleep(2 ** (attempt + 1)); continue
            sys.exit(f"Network error for {url.split('?')[0]}: {e}")


def shots(only=None):
    s = [x for x in SHOTS if not x.get("card")]
    return [x for x in s if not only or x["id"] in only]


# ---------- Gemini images ----------

def style_text():
    return (f"{STYLE['look']} Setting: {STYLE['period']} Strictly avoid: {STYLE['avoid']}. "
            f"Rule of the film: {STYLE['rule']}")


def gemini_image(prompt, refs, dest):
    parts = [{"text": prompt}]
    for label, p in refs:
        parts.append({"text": f"Reference for {label}: keep this exact face, build, hair and clothing."})
        parts.append({"inline_data": {"mime_type": "image/png", "data": base64.b64encode(p.read_bytes()).decode()}})
    model = STYLE["gemini"]["image_model"]
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": STYLE["aspect"]}}}
    r = http(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
             body, {"x-goog-api-key": key("GEMINI_API_KEY")})
    for part in r.get("candidates", [{}])[0].get("content", {}).get("parts", []):
        d = part.get("inlineData") or part.get("inline_data")
        if d:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(base64.b64decode(d["data"]))
            print("  wrote", dest.relative_to(HERE)); return
    sys.exit(f"No image returned for {dest.name}: {json.dumps(r)[:600]}")


def stage_concept(a):
    for c in CONCEPT:
        dest = OUT / "concept" / f"{c['id']}.png"
        if not dest.exists():
            gemini_image(f"Concept art, {c['title']}. {c['prompt']} {style_text()}", [], dest)


def stage_cast(a):
    for cid, c in CAST.items():
        dest = OUT / "cast" / f"{cid}.png"
        if dest.exists():
            continue
        gemini_image(f"Character reference sheet for a film: {c['look']}. Two views side by side, full body "
                     f"and a head-and-shoulders close-up, plain warm grey backdrop, even soft light. "
                     f"{STYLE['period']} Avoid: {STYLE['avoid']}.", [], dest)


def stage_keyframes(a):
    for s in shots(a.only):
        dest = OUT / "keyframes" / f"{s['id']}.png"
        if dest.exists():
            continue
        refs = [(CAST[c]["name"], OUT / "cast" / f"{c}.png") for c in s["cast"] if (OUT / "cast" / f"{c}.png").exists()]
        gemini_image(f"Film still, {s['shot']}. {s['frame']}. {style_text()}", refs, dest)


# ---------- Runway video ----------

def stage_video(a):
    from PIL import Image
    k = key("RUNWAYML_API_SECRET")
    hdr = {"Authorization": f"Bearer {k}", "X-Runway-Version": "2024-11-06"}
    for s in shots(a.only):
        dest = OUT / "clips" / f"{s['id']}.mp4"
        kf = OUT / "keyframes" / f"{s['id']}.png"
        if dest.exists():
            continue
        if not kf.exists():
            print("  no keyframe for", s["id"], "- run keyframes first"); continue
        buf = io.BytesIO()
        Image.open(kf).convert("RGB").save(buf, "JPEG", quality=90)
        uri = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
        body = {"model": STYLE["runway"]["model"], "promptImage": uri, "ratio": STYLE["runway"]["ratio"],
                "duration": s["dur"], "promptText": f"{s['motion']} Cinematic, 65mm film, natural motion, "
                                                    f"no text, no morphing faces."[:1000]}
        task = http("https://api.dev.runwayml.com/v1/image_to_video", body, hdr)["id"]
        print(f"  {s['id']}: runway task {task}", end="", flush=True)
        while True:
            time.sleep(8)
            t = http(f"https://api.dev.runwayml.com/v1/tasks/{task}", headers=hdr)
            if t["status"] == "SUCCEEDED":
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(http(t["output"][0], raw=True)); print(" ->", dest.relative_to(HERE)); break
            if t["status"] in ("FAILED", "CANCELLED"):
                print(" failed:", t.get("failure") or t); break
            print(".", end="", flush=True)


# ---------- ElevenLabs ----------

_voices = {}


def voice_id(name):
    if not _voices:
        r = http("https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": key("ELEVENLABS_API_KEY")})
        for v in r.get("voices", []):
            _voices.setdefault(v["name"].split(" ")[0].split("-")[0].strip(), v["voice_id"])
    return _voices.get(name) or PREMADE[name]


def tts(text, who, dest):
    v = CAST[who]["voice"]
    body = {"text": text, "model_id": STYLE["elevenlabs"]["tts_model"],
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}}
    audio = http(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id(v['name'])}?output_format=mp3_44100_128",
                 body, {"xi-api-key": key("ELEVENLABS_API_KEY"), "Accept": "audio/mpeg"}, raw=True)
    dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(audio); print("  wrote", dest.relative_to(HERE))


def stage_voice(a):
    for s in shots(a.only):
        for i, ln in enumerate(s["lines"]):
            if ln["who"] == "all":
                for who in CHORUS:
                    d = OUT / "voice" / f"{s['id']}_{i}_{who}.mp3"
                    if not d.exists():
                        tts(ln["text"], who, d)
            else:
                d = OUT / "voice" / f"{s['id']}_{i}.mp3"
                if not d.exists():
                    tts(ln["text"], ln["who"], d)


def stage_sfx(a):
    for s in shots(a.only):
        d = OUT / "sfx" / f"{s['id']}.mp3"
        if d.exists() or not s.get("sfx"):
            continue
        audio = http("https://api.elevenlabs.io/v1/sound-generation",
                     {"text": s["sfx"] + ", realistic, ancient city, no music, no speech",
                      "duration_seconds": min(22, max(1, s["dur"])), "prompt_influence": 0.45},
                     {"xi-api-key": key("ELEVENLABS_API_KEY"), "Accept": "audio/mpeg"}, raw=True)
        d.parent.mkdir(parents=True, exist_ok=True); d.write_bytes(audio); print("  wrote", d.relative_to(HERE))


def stage_music(a):
    for m in STYLE["music"]:
        d = OUT / "music" / f"{m['id']}.mp3"
        if d.exists():
            continue
        audio = http("https://api.elevenlabs.io/v1/music",
                     {"prompt": m["prompt"], "music_length_ms": m["len"] * 1000},
                     {"xi-api-key": key("ELEVENLABS_API_KEY"), "Accept": "audio/mpeg"}, raw=True, timeout=600)
        d.parent.mkdir(parents=True, exist_ok=True); d.write_bytes(audio); print("  wrote", d.relative_to(HERE))


# ---------- local cards and assembly ----------

def font(path, size):
    from PIL import ImageFont
    return ImageFont.truetype(path, size)


def draw_card(entry, dest):
    """Title card, or (for a shot with no image yet) a storyboard panel."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), (12, 10, 9))
    d = ImageDraw.Draw(img)
    if entry.get("card"):
        f1, f2 = font(SERIF, 46), font(SERIF_I, 28)
        lines = textwrap.wrap(entry["text"], 40)
        y = H // 2 - 40 * len(lines) - (20 if entry.get("sub") else 0)
        for ln in lines:
            d.text((W // 2, y), ln, font=f1, fill=(232, 220, 196), anchor="mm"); y += 58
        for ln in textwrap.wrap(entry.get("sub", ""), 60):
            y += 8; d.text((W // 2, y + 20), ln, font=f2, fill=(176, 160, 132), anchor="mm"); y += 36
    else:
        f1, f2, f3 = font(SERIF, 30), font(SERIF, 24), font(SERIF_I, 24)
        d.rectangle([40, 40, W - 40, H - 40], outline=(90, 74, 52), width=2)
        d.text((70, 66), f"{entry['id'].upper()}  ·  {entry['shot']}  ·  {entry['scene']}", font=f1, fill=(214, 170, 90))
        y = 130
        for ln in textwrap.wrap(entry["frame"], 88):
            d.text((70, y), ln, font=f2, fill=(220, 210, 190)); y += 34
        y += 20
        for ln in textwrap.wrap("Motion: " + entry["motion"], 92):
            d.text((70, y), ln, font=f3, fill=(150, 140, 120)); y += 32
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest)


def line_plan(s):
    """Return [(start, [files], who, text)] with lines placed sequentially, and the segment length."""
    t, plan = 0.0, []
    for i, ln in enumerate(s.get("lines", [])):
        files = ([OUT / "voice" / f"{s['id']}_{i}_{w}.mp3" for w in CHORUS] if ln["who"] == "all"
                 else [OUT / "voice" / f"{s['id']}_{i}.mp3"])
        files = [f for f in files if f.exists()]
        spoken = re.sub(r"\[[^\]]*\]\s*", "", ln["text"]).strip()
        est = max(duration(f) for f in files) if files else max(1.2, len(spoken.split()) * 0.36)
        start = max(ln["at"], t + 0.25 if plan else ln["at"])
        plan.append((start, files, ln["who"], spoken, est))
        t = start + est
    return plan, max(s["cut"], t + 0.5)


def render_segment(s, idx, a):
    seg = OUT / "segments" / f"{idx:02d}_{s['id']}.mp4"
    plan, length = ([], s["cut"]) if s.get("card") else line_plan(s)
    clip, kf = OUT / "clips" / f"{s['id']}.mp4", OUT / "keyframes" / f"{s['id']}.png"
    board = OUT / "boards" / f"{s['id']}.png"
    cmd = [ffmpeg(), "-y", "-hide_banner"]
    frames = int(length * FPS)
    if clip.exists() and not s.get("card"):
        cmd += ["-i", str(clip)]
        v = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},tpad=stop_mode=clone:stop_duration={length},trim=duration={length},setpts=PTS-STARTPTS"
    else:
        src = kf if kf.exists() and not s.get("card") else board
        if src == board:
            draw_card(s, board)
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{length:.2f}", "-i", str(src)]
        if src == kf:
            v = (f"[0:v]scale={W*2}:{H*2},zoompan=z='1+0.06*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                 f":d=1:s={W}x{H}:fps={FPS},trim=duration={length}")
        else:
            v = f"[0:v]scale={W}:{H},fps={FPS},trim=duration={length}"
    fade = 0.6 if s.get("card") else 0.15
    v += f",fade=t=in:st=0:d={fade},fade=t=out:st={max(0, length - fade):.2f}:d={fade},format=yuv420p[v]"
    audio_in, filters, n = [], [v], 1
    cmd += ["-f", "lavfi", "-t", f"{length:.2f}", "-i", "anullsrc=r=44100:cl=stereo"]
    mix = [f"[{n}:a]"]; n += 1
    sfx = OUT / "sfx" / f"{s['id']}.mp3"
    if sfx.exists():
        cmd += ["-i", str(sfx)]
        filters.append(f"[{n}:a]volume=0.55,atrim=duration={length},afade=t=out:st={max(0, length - 0.4):.2f}:d=0.4[a{n}]")
        mix.append(f"[a{n}]"); n += 1
    for start, files, who, text, est in plan:
        for f in files:
            cmd += ["-i", str(f)]
            vol = 0.55 if len(files) > 1 else 1.0
            ms = int(start * 1000)
            filters.append(f"[{n}:a]volume={vol},adelay={ms}|{ms}[a{n}]")
            mix.append(f"[a{n}]"); n += 1
    filters.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first[a]")
    cmd += ["-filter_complex", ";".join(filters), "-map", "[v]", "-map", "[a]", "-t", f"{length:.2f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", str(seg)]
    seg.parent.mkdir(parents=True, exist_ok=True)
    run(cmd)
    return seg, length, plan


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def stage_assemble(a):
    segs, subs, starts, t = [], [], {}, 0.0
    for idx, s in enumerate(SHOTS):
        seg, length, plan = render_segment(s, idx, a)
        starts[s["id"]] = t
        for start, files, who, text, est in plan:
            name = "ALL" if who == "all" else CAST[who]["name"].split(" ")[0].upper()
            subs.append((t + start, t + start + est, text))
        segs.append(seg); t += length
        print(f"  {s['id']:6} {length:5.1f}s  (running {t:6.1f}s)")
    lst = OUT / "segments" / "list.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in segs))
    joined = OUT / "segments" / "joined.mp4"
    run([ffmpeg(), "-y", "-hide_banner", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)])
    srt = OUT / "film.srt"
    srt.write_text("".join(f"{i}\n{srt_time(b)} --> {srt_time(e)}\n{txt}\n\n" for i, (b, e, txt) in enumerate(subs, 1)))
    # Music bed under the whole cut, each cue starting at its shot, ducked well below dialogue.
    cmd, parts, n = [ffmpeg(), "-y", "-hide_banner", "-i", str(joined)], ["[0:a]"], 1
    filters = []
    for m in STYLE["music"]:
        f = OUT / "music" / f"{m['id']}.mp3"
        if f.exists() and m["at"] in starts:
            ms = int(starts[m["at"]] * 1000)
            cmd += ["-i", str(f)]
            filters.append(f"[{n}:a]volume=0.22,afade=t=in:d=2,adelay={ms}|{ms}[m{n}]"); parts.append(f"[m{n}]"); n += 1
    filters.append(f"{''.join(parts)}amix=inputs={len(parts)}:normalize=0:duration=first,loudnorm=I=-16:TP=-1.5[a]")
    sub_style = "FontName=Liberation Serif,FontSize=16,PrimaryColour=&H00E6E6F0,OutlineColour=&H80000000,BorderStyle=1,Outline=1,Shadow=0,MarginV=34"
    vf = f"[0:v]subtitles={srt}:force_style='{sub_style}'[v]" if not a.no_subs else "[0:v]null[v]"
    filters.append(vf)
    out = OUT / "film.mp4"
    cmd += ["-filter_complex", ";".join(filters), "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "18",
            "-preset", "medium", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
    run(cmd)
    print(f"  wrote {out.relative_to(HERE)} ({t:.0f}s) and {srt.relative_to(HERE)}")


# ---------- estimate ----------

def estimate(stages, only):
    ss = shots(only)
    lines = [l for s in ss for l in s["lines"]]
    chars = sum(len(l["text"]) * (len(CHORUS) if l["who"] == "all" else 1) for l in lines)
    rows = {
        "concept": (len(CONCEPT) * PRICE_IMAGE, f"{len(CONCEPT)} images"),
        "cast": (sum(1 for c in CAST) * PRICE_IMAGE, f"{len(CAST)} images"),
        "keyframes": (len(ss) * PRICE_IMAGE, f"{len(ss)} images"),
        "video": (sum(s["dur"] for s in ss) * PRICE_RUNWAY_S, f"{sum(s['dur'] for s in ss)} s of Runway {STYLE['runway']['model']}"),
        "voice": (chars * PRICE_TTS_CHAR, f"{chars} characters"),
        "sfx": (sum(1 for s in ss if s.get("sfx")) * PRICE_SFX, f"{sum(1 for s in ss if s.get('sfx'))} effects"),
        "music": (sum(m["len"] for m in STYLE["music"]) * PRICE_MUSIC_S, f"{sum(m['len'] for m in STYLE['music'])} s of music"),
        "assemble": (0, "local ffmpeg"),
    }
    total = 0
    for st in stages:
        c, what = rows[st]; total += c
        print(f"  {st:10} ~${c:6.2f}  {what}")
    print(f"  {'total':10} ~${total:6.2f}  (one take of each; re-rolls cost the same again)")
    return total


STAGES = {"concept": stage_concept, "cast": stage_cast, "keyframes": stage_keyframes, "video": stage_video,
          "voice": stage_voice, "sfx": stage_sfx, "music": stage_music, "assemble": stage_assemble}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("stages", nargs="+", choices=list(STAGES) + ["estimate", "all"])
    p.add_argument("--yes", action="store_true", help="allow paid API calls")
    p.add_argument("--only", type=lambda v: set(v.split(",")), help="comma-separated shot ids")
    p.add_argument("--no-subs", action="store_true", help="do not burn subtitles into film.mp4")
    a = p.parse_args()
    stages = list(STAGES) if "all" in a.stages else [s for s in a.stages if s != "estimate"]
    if "estimate" in a.stages:
        estimate(stages or [s for s in STAGES], a.only); return
    paid = [s for s in stages if s != "assemble"]
    if paid:
        estimate(paid, a.only)
        if not a.yes:
            sys.exit("Paid stages need --yes.")
    for st in stages:
        print(f"== {st}")
        STAGES[st](a)


if __name__ == "__main__":
    main()
