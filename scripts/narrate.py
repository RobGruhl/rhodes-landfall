#!/usr/bin/env python3
"""Render the Rhodes Landfall narration with ElevenLabs (eleven_v3) into docs/audio/.

Paid per character. This script never spends without --yes. Without it, it prints the plan:
every clip, its character count, the total, the voice and model, and stops.

Key resolution mirrors the Toolbelt elevenlabs tool: $ELEVENLABS_API_KEY, then the macOS
Keychain item whose service is ELEVENLABS_API_KEY, then ~/.config/toolbelt/elevenlabs.env.
Each rendered clip appends one audit line to ~/.local/state/agent-voice/audit.log, the same
trail the Toolbelt tool writes.

Usage:
  python3 scripts/narrate.py                 # plan only
  python3 scripts/narrate.py --yes           # render everything not yet rendered
  python3 scripts/narrate.py --only short    # short versions only
  python3 scripts/narrate.py --stops 1-5,16  # a subset
  python3 scripts/narrate.py --voice George  # pick a voice by name (default George, then Daniel, Brian)
"""
from __future__ import annotations
import argparse, glob, json, os, stat, subprocess, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NARR = ROOT / "narration"
OUT = ROOT / "docs" / "audio"
MODEL = "eleven_v3"
MAX_RUN_CHARS = 120_000          # per-run ceiling; raising it is a diff, not a flag
MAX_CLIP_CHARS = 5_000           # v3 accepts up to 5,000 characters per request
VOICE_PREFS = ["George", "Daniel", "Brian"]
AUDIT = Path(os.environ.get("AGENT_VOICE_AUDIT_LOG", Path.home() / ".local/state/agent-voice/audit.log"))


def api_key() -> str:
    k = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if k:
        return k
    if sys.platform == "darwin":
        r = subprocess.run(["security", "find-generic-password", "-s", "ELEVENLABS_API_KEY", "-w"],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    p = Path.home() / ".config/toolbelt/elevenlabs.env"
    if p.exists():
        if stat.S_IMODE(p.stat().st_mode) & 0o077:
            sys.exit(f"{p} is group/world readable; chmod 600 it first")
        for line in p.read_text().splitlines():
            if line.startswith("ELEVENLABS_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
    sys.exit("No ElevenLabs key. Add one: security add-generic-password -s ELEVENLABS_API_KEY -a \"$USER\" -w")


def req(key: str, path: str, data: bytes | None = None, headers: dict | None = None):
    h = {"xi-api-key": key}
    if headers:
        h.update(headers)
    r = urllib.request.Request("https://api.elevenlabs.io" + path, data=data, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=300) as resp:
            return resp.read(), resp.headers
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} on {path}: {e.read()[:400]!r}")


def pick_voice(key: str, want: str | None):
    body, _ = req(key, "/v1/voices")
    voices = json.loads(body)["voices"]
    names = {v["name"]: v for v in voices}
    for cand in ([want] if want else []) + VOICE_PREFS:
        for name, v in names.items():
            if name == cand or name.split(" - ")[0].strip().lower() == cand.lower():
                return v
    sys.exit("None of the preferred voices are on this account; pass --voice NAME. Available: " + ", ".join(sorted(names)))


def load_stops():
    stops = []
    for f in sorted(glob.glob(str(NARR / "stops-*.json"))):
        stops.extend(json.load(open(f)))
    stops.sort(key=lambda s: s["n"])
    return stops


def parse_stops(spec: str | None):
    if not spec:
        return None
    out = set()
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out


def duration_seconds(path: Path) -> float | None:
    try:
        r = subprocess.run(["afinfo", str(path)], capture_output=True, text=True, timeout=30)
        for line in r.stdout.splitlines():
            if "estimated duration" in line:
                return float(line.split(":")[1].split()[0])
    except Exception:
        pass
    try:
        r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                           capture_output=True, text=True, timeout=30)
        return float(r.stdout.strip())
    except Exception:
        return None


def audit(line: str):
    AUDIT.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(AUDIT, "a") as f:
        f.write(line + "\n")
    os.chmod(AUDIT, 0o600)
    print(line, file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true", help="actually spend characters")
    ap.add_argument("--only", choices=["short", "long"], help="render one length only")
    ap.add_argument("--stops", help="e.g. 1-5,16")
    ap.add_argument("--voice", help="voice name on the account")
    ap.add_argument("--force", action="store_true", help="re-render clips that already exist")
    a = ap.parse_args()

    stops = load_stops()
    want = parse_stops(a.stops)
    jobs = []
    for s in stops:
        if want and s["n"] not in want:
            continue
        for length in (["short", "long"] if not a.only else [a.only]):
            text = s[length].strip()
            fn = OUT / f"{s['n']:02d}-{s['slug']}-{length}.mp3"
            if len(text) > MAX_CLIP_CHARS:
                sys.exit(f"{fn.name}: {len(text)} chars exceeds the {MAX_CLIP_CHARS}-char clip ceiling")
            if fn.exists() and not a.force:
                continue
            jobs.append((s, length, text, fn))
    total = sum(len(j[2]) for j in jobs)
    print(f"model {MODEL} | {len(jobs)} clips to render | {total:,} characters")
    for s, length, text, fn in jobs:
        print(f"  {fn.name:38s} {len(text):5d} chars")
    if total > MAX_RUN_CHARS:
        sys.exit(f"Total {total:,} exceeds the per-run ceiling of {MAX_RUN_CHARS:,} characters; narrow with --stops or --only")
    if not jobs:
        print("Nothing to render (all clips exist; use --force to re-render)")
        return write_manifest(stops)
    key = api_key()
    voice = pick_voice(key, a.voice)
    print(f"voice {voice['name']} ({voice['voice_id']})")
    sub = json.loads(req(key, "/v1/user/subscription")[0])
    remaining = (sub.get("character_limit") or 0) - (sub.get("character_count") or 0)
    print(f"account tier {sub.get('tier')} | characters remaining this cycle: {remaining:,}")
    if not a.yes:
        print("\nPlan only. Re-run with --yes to render.")
        return
    if remaining < total:
        sys.exit(f"Not enough characters remaining ({remaining:,}) for this run ({total:,}); use --only short or --stops")
    OUT.mkdir(parents=True, exist_ok=True)
    payload_base = {
        "model_id": MODEL,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.8, "use_speaker_boost": True},
    }
    for s, length, text, fn in jobs:
        body = json.dumps({**payload_base, "text": text}).encode()
        t0 = time.time()
        audio, _ = req(key, f"/v1/text-to-speech/{voice['voice_id']}?output_format=mp3_44100_128", body,
                       {"Content-Type": "application/json", "Accept": "audio/mpeg"})
        fn.write_bytes(audio)
        audit(f"[agent-voice audit] {datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')} "
              f"verb=narrate clip={fn.name} voice={voice['voice_id']} model={MODEL} chars={len(text)} bytes={len(audio)} secs={time.time()-t0:.1f}")
        time.sleep(0.5)
    write_manifest(stops, voice)


def write_manifest(stops, voice=None):
    man = {"model": MODEL, "voice": (voice or {}).get("name"), "voice_id": (voice or {}).get("voice_id"), "clips": {}}
    for s in stops:
        entry = {}
        for length in ("short", "long"):
            fn = OUT / f"{s['n']:02d}-{s['slug']}-{length}.mp3"
            if fn.exists():
                entry[length] = {"file": f"audio/{fn.name}", "sec": duration_seconds(fn), "chars": len(s[length])}
        if entry:
            man["clips"][str(s["n"])] = {"title": s["title"], **entry}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "manifest.json").write_text(json.dumps(man, indent=1))
    print(f"manifest: {len(man['clips'])} stops with audio -> {OUT/'manifest.json'}")


if __name__ == "__main__":
    main()
