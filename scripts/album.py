"""Tag the narration clips as two Apple Music albums (one per narrator), for syncing to the iPhone.

Writes album/<set>/*.mp3 (gitignored): disc 1 is the long versions, disc 2 the short ones,
tracks in stop order, with a cover. The clips in docs/audio stay untouched.
Run from scripts/: python3 album.py   (needs ffmpeg; Pillow for the cover)
"""
import json, os, subprocess
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, 'docs')
OUT = os.path.join(ROOT, 'album')
NAMES = {'rob': 'Rob', 'jamie': 'Jamie'}
SERIF = '/System/Library/Fonts/Supplemental/Georgia.ttf'
SERIF_B = '/System/Library/Fonts/Supplemental/Georgia Bold.ttf'


def cover(path, who, line=None):
    s = 1400
    im = Image.new('RGB', (s, s), '#8B3A2F'); d = ImageDraw.Draw(im)
    d.text((s / 2, s * .40), 'Rhodes', font=ImageFont.truetype(SERIF_B, 230), fill='#FAF8F3', anchor='mm')
    d.text((s / 2, s * .56), 'Landfall', font=ImageFont.truetype(SERIF_B, 230), fill='#FAF8F3', anchor='mm')
    d.line([(s * .3, s * .68), (s * .7, s * .68)], fill='#E0A48F', width=8)
    d.text((s / 2, s * .76), line or f"{who}'s track  ·  30 September 2026", font=ImageFont.truetype(SERIF, 64), fill='#F2E3D9', anchor='mm')
    im.save(path, quality=92)


for st in ('rob', 'jamie'):
    m = json.load(open(os.path.join(DOCS, 'audio', st, 'manifest.json')))
    clips = sorted(m['clips'].values(), key=lambda c: (c.get('long') or c['short'])['file'])
    dest = os.path.join(OUT, st); os.makedirs(dest, exist_ok=True)
    art = os.path.join(dest, 'cover.jpg'); cover(art, NAMES[st])
    album = f'Rhodes Landfall · {NAMES[st]}'
    for disc, length in ((1, 'long'), (2, 'short')):
        for i, c in enumerate(clips, 1):
            if length not in c: continue
            src = os.path.join(DOCS, c[length]['file'])
            title = f"{i:02d} {c['title']}" + (' (short)' if length == 'short' else '')
            out = os.path.join(dest, f'{disc}-{i:02d} {c["title"].replace("/", "-")}{" (short)" if length == "short" else ""}.mp3')
            meta = {'title': title, 'album': album, 'artist': f'{NAMES[st]} · Rhodes Landfall',
                    'album_artist': 'Rhodes Landfall', 'genre': 'Spoken Word', 'date': '2026',
                    'track': f'{i}/{len(clips)}', 'disc': f'{disc}/2'}
            cmd = ['ffmpeg', '-v', 'error', '-y', '-i', src, '-i', art, '-map', '0:a', '-map', '1:v', '-c', 'copy',
                   '-id3v2_version', '3', '-metadata:s:v', 'title=Album cover', '-metadata:s:v', 'comment=Cover (front)']
            for k, v in meta.items(): cmd += ['-metadata', f'{k}={v}']
            subprocess.run(cmd + [out], check=True)
    print(st, len(os.listdir(dest)) - 1, 'tracks ->', dest)

# the Colossus extra: one album per voice
xm = os.path.join(DOCS, 'audio', 'colossus', 'manifest.json')
if os.path.exists(xm):
    x = json.load(open(xm))
    chapters = {c['slug']: c for c in json.load(open(os.path.join(ROOT, 'narration', 'colossus.json')))['chapters']}
    for vkey, v in x['voices'].items():
        dest = os.path.join(OUT, 'colossus-' + vkey); os.makedirs(dest, exist_ok=True)
        art = os.path.join(dest, 'cover.jpg'); cover(art, v['name'], f"The Colossus  ·  read by {v['name']}")
        n_total = len(v['clips'])
        for i, (slug, c) in enumerate(sorted(v['clips'].items(), key=lambda kv: kv[1]['file']), 1):
            ch = chapters[slug]
            title = 'Introduction' if ch['n'] == 0 else f"{ch['n']:02d} {ch['title']}"
            out = os.path.join(dest, f"{i:02d} {title}.mp3")
            meta = {'title': title, 'album': f"The Colossus of Rhodes · read by {v['name']}", 'artist': v['name'],
                    'album_artist': 'Rhodes Landfall', 'genre': 'Spoken Word', 'date': '2026', 'track': f'{i}/{n_total}'}
            cmd = ['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(DOCS, c['file']), '-i', art, '-map', '0:a', '-map', '1:v', '-c', 'copy',
                   '-id3v2_version', '3', '-metadata:s:v', 'title=Album cover', '-metadata:s:v', 'comment=Cover (front)']
            for k, val in meta.items(): cmd += ['-metadata', f'{k}={val}']
            subprocess.run(cmd + [out], check=True)
        print('colossus', vkey, n_total, 'tracks ->', dest)
