# Landfall, the short

A 50-second film cut to Rob's short narration for stop 1 (`docs/audio/rob/01-landfall-short.mp3`): fourteen shots, one per beat of the script, from the view off the gangway through the six peoples who took the town to the walk toward the gate.

`shots.json` is the storyboard. Each shot has the narration line it sits under, a keyframe prompt (`still`, with the shared `style` appended), a camera direction for animating it (`motion`), its cue in the narration (`at`, seconds, taken from the pauses in the clip) and how many seconds to render (`dur`, at least as long as the cut needs).

`make.py` builds it through the Toolbelt's `rwy` (Runway, paid, preview-first) and ffmpeg:

| Stage | What | Cost |
|---|---|---|
| `keyframes` | one `gen4_image` still per shot, 1280×720 | 112 credits ($1.12) at most |
| `clips` | each still animated by `gen4_turbo` | 295 credits ($2.95) |
| `ambience` | 30 s looping harbour bed | 30 credits ($0.30) |
| `assemble` | cut to the cues, narration over ambience at -15 dB, fades, `landfall.mp4` | free |

Each paid stage previews every call and spends nothing without `--yes`. Finished outputs in `renders/` (gitignored) are skipped, so delete one file to redraw that shot. Draw the keyframes first and look at them: they are the storyboard, and redrawing a still costs 8 credits where redoing a clip costs up to 50.
