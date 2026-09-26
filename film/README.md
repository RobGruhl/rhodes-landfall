# In the Priesthood of the Sun: the film

A historical short of about four minutes, adapted from `stories/in-the-priesthood-of-the-sun.md`. It follows one day in Rhodes in 255 BC. The Colossus is the backdrop, never the subject.

- `shots.json`: the screenplay. It has 33 shots and 3 title cards, each with a camera note, a keyframe prompt, a motion prompt, dialogue and sound. Everything else is built from it.
- `cast.json`: what each character looks like and which ElevenLabs voice they use.
- `style.json`: the look, the period rules, what to avoid, the models and the music cues.
- `concept.json`: briefs for seven pieces of concept art.
- `produce.py`: the render pipeline (Gemini images, Runway video, ElevenLabs voice, sound effects and music, then ffmpeg assembly). Stages resume where they left off. Paid stages need `--yes`, and the cost estimate prints first.
- `build_board.py` writes `storyboard.html` and embeds any keyframes, cast sheets and concept art found in `out/`.
- `animatic.mp4`: the current cut, with storyboard panels and subtitles in place of footage and no audio yet.

```
pip install pillow imageio-ffmpeg
export GEMINI_API_KEY=... RUNWAYML_API_SECRET=... ELEVENLABS_API_KEY=...
python3 produce.py estimate                  # about $19 for one take of everything
python3 produce.py concept cast --yes        # look at out/concept and out/cast; re-roll by deleting a file
python3 produce.py keyframes --yes           # approve the stills before spending on video
python3 produce.py video voice sfx music --yes
python3 produce.py assemble                  # out/film.mp4 and out/film.srt
python3 build_board.py                       # storyboard with real frames
```

The pipeline needs these hosts reachable: `generativelanguage.googleapis.com`, `api.dev.runwayml.com`, `api.elevenlabs.io`.
