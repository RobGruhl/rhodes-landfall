#!/usr/bin/env python3
"""Render the Colossus long-form extra (narration/colossus.json) in several voices.

Paid per character; plans only unless --yes. One clip per chapter per voice, written to
docs/audio/colossus/<voice>/NN-slug.mp3 with a manifest at docs/audio/colossus/manifest.json.
Delivery is tuned to be soothing (Jamie has sensory sensitivities): the steadier
eleven_multilingual_v2 model, high stability, no style exaggeration, a slightly slower pace,
then every clip is de-essed, loudness-matched to -20 LUFS with a gentle peak ceiling, and faded
in so no chapter starts or sits louder than another.

Usage: python3 scripts/narrate_extra.py [--voices river,jeanette,lily,george] [--yes]
"""
import argparse, json, os, subprocess, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from narrate import api_key, audit, duration_seconds  # same key lookup and audit trail

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'narration' / 'colossus.json'
OUT = ROOT / 'docs' / 'audio' / 'colossus'
MODEL = 'eleven_multilingual_v2'
SETTINGS = {'stability': 0.75, 'similarity_boost': 0.75, 'style': 0.0, 'use_speaker_boost': True, 'speed': 0.92}
VOICES = {  # key: (voice_id, display name, one-line character)
    'river': ('SAz9YHcvj6GT2YYXdXww', 'River', 'calm and even'),
    'jeanette': ('RILOU7YmBhvwJGDGjNmP', 'Jeanette', 'gentle British audiobook'),
    'lily': ('pFZP5JQG7iQjIQuC4Bku', 'Lily', 'velvety British'),
    'george': ('JBFqnCBsd6RMkjVDRZzb', 'George', 'the tour narrator'),
}
WORDS = 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen'.split()
SOFTEN = 'deesser,loudnorm=I=-20:TP=-3:LRA=7,afade=t=in:d=0.6,apad=pad_dur=1.2'


def spoken(doc, c):
    head = f"{doc['title']}. {c['title']}." if c['n'] == 0 else f"Chapter {WORDS[c['n']]}. {c['title']}."
    return head + ' <break time="1.2s" /> ' + '\n\n'.join(c['text'].split('\n'))


def render(key, vkey, c, text, fn):
    vid = VOICES[vkey][0]
    body = json.dumps({'text': text, 'model_id': MODEL, 'voice_settings': SETTINGS}).encode()
    r = urllib.request.Request(f'https://api.elevenlabs.io/v1/text-to-speech/{vid}?output_format=mp3_44100_128', data=body,
                               headers={'xi-api-key': key, 'Content-Type': 'application/json', 'Accept': 'audio/mpeg'})
    t0 = time.time()
    for attempt in range(4):
        try:
            with urllib.request.urlopen(r, timeout=600) as resp:
                raw = resp.read(); break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 3:
                time.sleep(10 * (attempt + 1)); continue
            raise RuntimeError(f'{fn.name}: HTTP {e.code} {e.read()[:300]!r}')
    tmp = fn.with_suffix('.raw.mp3'); tmp.write_bytes(raw)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(tmp), '-af', SOFTEN, '-ar', '44100', '-b:a', '128k', str(fn)], check=True)
    tmp.unlink()
    audit(f"[agent-voice audit] {datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')} "
          f"verb=narrate clip=colossus/{vkey}/{fn.name} voice={vid} model={MODEL} chars={len(text)} bytes={len(raw)} secs={time.time()-t0:.1f}")


def write_manifest(doc, voices):
    man = {'set': 'colossus', 'model': MODEL, 'title': doc['title'], 'voices': {}}
    for vkey in voices:
        d = OUT / vkey
        clips = {}
        for c in doc['chapters']:
            fn = d / f"{c['n']:02d}-{c['slug']}.mp3"
            if fn.exists():
                clips[c['slug']] = {'file': str(fn.relative_to(ROOT / 'docs')), 'sec': duration_seconds(fn)}
        if clips:
            vid, name, blurb = VOICES[vkey]
            man['voices'][vkey] = {'name': name, 'blurb': blurb, 'voice_id': vid, 'clips': clips}
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(man, open(OUT / 'manifest.json', 'w'), indent=1)
    print('manifest:', {k: len(v['clips']) for k, v in man['voices'].items()})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--voices', default=','.join(VOICES))
    ap.add_argument('--yes', action='store_true')
    a = ap.parse_args()
    voices = [v for v in a.voices.split(',') if v]
    for v in voices:
        if v not in VOICES: sys.exit(f'unknown voice {v}; known: {", ".join(VOICES)}')
    doc = json.load(open(SRC))
    jobs = []
    for vkey in voices:
        for c in doc['chapters']:
            fn = OUT / vkey / f"{c['n']:02d}-{c['slug']}.mp3"
            if not fn.exists():
                jobs.append((vkey, c, spoken(doc, c), fn))
    total = sum(len(j[2]) for j in jobs)
    print(f'model {MODEL} | {len(jobs)} clips to render | {total:,} characters | voices {voices}')
    if not jobs:
        return write_manifest(doc, voices)
    key = api_key()
    sub = json.loads(urllib.request.urlopen(urllib.request.Request('https://api.elevenlabs.io/v1/user/subscription', headers={'xi-api-key': key})).read())
    remaining = sub['character_limit'] - sub['character_count']
    print(f'characters remaining this cycle: {remaining:,}')
    if not a.yes:
        print('Plan only. Re-run with --yes to render.'); return
    if remaining < total:
        sys.exit(f'Not enough characters ({remaining:,}) for {total:,}')
    for vkey in voices: (OUT / vkey).mkdir(parents=True, exist_ok=True)
    errors = []
    def run(j):
        try: render(key, *j)
        except Exception as e: errors.append(str(e)); print('FAILED', e, file=sys.stderr)
    with ThreadPoolExecutor(3) as ex:
        list(ex.map(run, jobs))
    write_manifest(doc, voices)
    if errors: sys.exit(f'{len(errors)} clips failed; re-run to retry just those')


if __name__ == '__main__':
    main()
