# Rhodes Landfall

A self-guided field guide and pin map for one day in Rhodes, Greece: Wednesday 30 September 2026, 09:00 to 18:00, off Virgin Voyages' *Scarlet Lady*. History told as story, the Colossus in depth, the Knights as a faction system, sieges keyed to the bastions, and where to eat, drink and drink coffee.

- **Live page:** https://robgruhl.github.io/rhodes-landfall/ (map tiles load from OpenStreetMap)
- **Offline page:** https://robgruhl.github.io/rhodes-landfall/offline.html (map tiles embedded, about 4.4 MB; save it to the phone before sailing)

## What is in here

- `docs/` the published pages (`index.html` live tiles, `offline.html` embedded tiles)
- `data/pins.json` every pin: category, coordinates, blurb, hours that apply on the day, price, source URL
- `data/route.json` the walking line, routed over the OpenStreetMap street network, with the ramparts leg on the real wall geometry
- `data/content.html` the briefing text
- `research/` the raw research notes, one file per topic, plus the fact-checkers' corrections (`verify-deltas.md`)
- `scripts/` the build: `router.py` (Dijkstra over OSM ways), `build.py` (assembles the page), `fetch_tiles.py`
- `tiles/` cached OpenStreetMap tiles for the offline page

## Narration

Two narration sets share the 22 stops. `narration/rob-*.json` is Rob's (D&D flavour, sieges, the Knights as factions); `narration/jamie-*.json` is Jamie's (how people organized their lives in each era, anthropology of the walled town, myth as lived practice, the city-state's status, and the Colossus told whole). Each stop has a short (about 35 seconds) and a long (two to four minutes) script written for text-to-speech. `scripts/narrate.py --set rob|jamie` renders a set with ElevenLabs `eleven_v3` (voice: George) into `docs/audio/<set>/`, writes that set's `manifest.json` keyed by stop slug, and the build links every set's clips from the pin whose `aud` field names the slug. The page has a "Listening as" toggle (Rob, Jamie, Both) under the category chips; it is remembered on the phone, and `?as=jamie` in the URL sets it, so Jamie opens https://robgruhl.github.io/rhodes-landfall/?as=jamie once and only sees her clips. The script never spends without `--yes` and prints the character cost first; every clip is logged to `~/.local/state/agent-voice/audit.log`.

## Rebuild

```
cd scripts && ln -sf ../data data && ln -sf ../tiles tiles && python3 build.py
```

Needs `data/ways.json` (OSM highways for the town: Overpass query `way["highway"](36.37,28.13,36.46,28.25); out geom;`) and `data/tiles.js` (one line, `const TILES={"z/x/y":"data:image/png;base64,..."};`, built from `tiles/`); both are gitignored. `build.py` writes `docs/offline.html` and `docs/index.html`.

Map data © OpenStreetMap contributors, ODbL. Hours and prices were checked in late August and early September 2026 against the sources named in each pin; re-check on the morning.
