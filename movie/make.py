#!/usr/bin/env python3
"""Build the Landfall short from shots.json.

  make.py keyframes [--yes]   one gen4_image still per shot            -> renders/<id>.png
  make.py clips [--yes]       animate each still with gen4_turbo       -> renders/<id>-clip.mp4
  make.py ambience [--yes]    a 30 s looping harbour bed               -> renders/ambience.mp3
  make.py assemble            cut to the narration, mix, write landfall.mp4 (free)

Paid stages print rwy's preview for every missing file and spend nothing without --yes.
Existing outputs are skipped, so a stage can be re-run after a failure; delete a file to redo it.
Needs a sibling Toolbelt clone (or $RWY pointing at rwy.mjs) and ffmpeg (or $FFMPEG).
"""
import json, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "renders"
RWY = os.environ.get("RWY", str(HERE.parent.parent / "Toolbelt/tools/runway-ai/rwy.mjs"))
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
SPEC = json.loads((HERE / "shots.json").read_text())
KEYFRAME_CREDITS, TURBO_PER_S, AMBIENCE_S = 8, 5, 30


def rwy(args, yes):
    cmd = ["node", RWY, *args, "--out", str(OUT)] + (["--yes"] if yes else [])
    return subprocess.run(cmd).returncode


def keyframes(yes):
    todo = [s for s in SPEC["shots"] if not (OUT / f"{s['id']}.png").exists()]
    for s in todo:
        prompt = f"{s['still']}. {SPEC['style']}"
        if rwy(["image", prompt, "--model", "gen4_image", "--ratio", "1280:720", "--name", s["id"]], yes):
            sys.exit(f"{s['id']}: rwy failed")
    return len(todo) * KEYFRAME_CREDITS


def clips(yes):
    todo = [s for s in SPEC["shots"] if not (OUT / f"{s['id']}-clip.mp4").exists()]
    for s in todo:
        still = OUT / f"{s['id']}.png"
        if not still.exists():
            if yes:
                sys.exit(f"{s['id']}: no keyframe; run `make.py keyframes --yes` first")
            print(f"{s['id']}: gen4_turbo {s['dur']} s from {still.name} (not drawn yet), "
                  f"{s['dur'] * TURBO_PER_S} credits: {s['motion']}")
            continue
        if rwy(["video", s["motion"], "--image", str(still), "--model", "gen4_turbo",
                "--ratio", "1280:720", "--duration", str(s["dur"]), "--name", f"{s['id']}-clip"], yes):
            sys.exit(f"{s['id']}: rwy failed")
    return sum(s["dur"] for s in todo) * TURBO_PER_S


def ambience(yes):
    if (OUT / "ambience.mp3").exists():
        return 0
    if rwy(["audio", SPEC["ambience"], "--duration", str(AMBIENCE_S), "--loop", "--name", "ambience"], yes):
        sys.exit("ambience: rwy failed")
    return AMBIENCE_S


def assemble():
    shots, off = SPEC["shots"], SPEC["narration_offset"]
    narration = (HERE / SPEC["narration"]).resolve()
    probe = subprocess.run([FFMPEG, "-i", str(narration)], capture_output=True, text=True).stderr
    h, m, sec = probe.split("Duration: ")[1].split(",")[0].split(":")
    end = int(h) * 3600 + int(m) * 60 + float(sec) + off + SPEC["tail"]
    # Each shot runs from its narration cue to the next one; the first starts at 0.
    starts = [0.0] + [s["at"] + off for s in shots[1:]]
    lengths = [b - a for a, b in zip(starts, starts[1:] + [end])]
    for s, n in zip(shots, lengths):
        if n > s["dur"] + 0.01:
            sys.exit(f"{s['id']}: needs {n:.2f}s but renders {s['dur']}s; raise dur in shots.json")

    inputs, parts = [], []
    for i, (s, n) in enumerate(zip(shots, lengths)):
        inputs += ["-i", str(OUT / f"{s['id']}-clip.mp4")]
        parts.append(f"[{i}:v]trim=0:{n:.3f},setpts=PTS-STARTPTS,scale=1280:720,fps=24,setsar=1[v{i}]")
    k = len(shots)
    video = "".join(f"[v{i}]" for i in range(k)) + f"concat=n={k}:v=1:a=0," \
        f"fade=t=in:d=0.8,fade=t=out:st={end - 1.2:.3f}:d=1.2[v]"
    inputs += ["-i", str(narration)]
    audio_in = [f"[{k}:a]adelay={int(off * 1000)}:all=1,apad[nar]"]
    mix = "[nar]"
    if (OUT / "ambience.mp3").exists():
        inputs += ["-stream_loop", "-1", "-i", str(OUT / "ambience.mp3")]
        audio_in.append(f"[{k + 1}:a]volume=0.18[amb]")
        mix += "[amb]"
    mix += f"amix=inputs={mix.count('[')}:duration=first:normalize=0," \
           f"atrim=0:{end:.3f},afade=t=out:st={end - 1.2:.3f}:d=1.2[a]"
    graph = ";".join(parts + [video] + audio_in + [mix])
    dest = HERE / "landfall.mp4"
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *inputs,
                    "-filter_complex", graph, "-map", "[v]", "-map", "[a]", "-t", f"{end:.3f}",
                    "-c:v", "libx264", "-crf", "20", "-preset", "slow", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(dest)], check=True)
    print(f"wrote {dest} ({end:.1f} s)")


if __name__ == "__main__":
    stage, yes = (sys.argv[1] if len(sys.argv) > 1 else ""), "--yes" in sys.argv
    OUT.mkdir(exist_ok=True)
    if stage == "assemble":
        assemble()
    elif stage in ("keyframes", "clips", "ambience"):
        credits = globals()[stage](yes)
        print(f"\n{stage}: {credits} credits (${credits / 100:.2f}) {'spent' if yes else 'if run with --yes'}")
    else:
        sys.exit(__doc__)
