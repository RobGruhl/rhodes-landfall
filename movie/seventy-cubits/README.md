# Seventy Cubits

A five-minute historical fiction. On the morning after the earthquake of 226 BC, Timon, eighty-nine, walks up to the fallen Colossus and remembers the siege of 305 that killed his father, the twelve years he spent building the god, and the day he put his hand on its face.

`film.json` holds everything that is not code: the narration of each of the ten scenes, the shots under it (a keyframe prompt, a camera move, the characters it needs), the character and statue reference prompts, the voice, and the sound beds. The story follows the tour's research (`research/`, with the fact-checkers' corrections). Where the sources disagree, it takes the version a Rhodian of the time would have told: the engines sold for three hundred talents, the statue cast in rings inside an earth mound, an unnamed oracle. It leaves out what is myth: there is no harbour straddle, no torch and no medieval building.

`film.py` builds it through the Toolbelt's `rwy`. It runs one stage at a time, and every paid stage previews and spends nothing without `--yes`:

1. `audition` renders one line in six candidate voices. Listen, then set `voice.preset`.
2. `refs` draws Timon at ten, twenty-five and eighty-nine, and the bronze head. Every keyframe that shows one of them cites its reference, so he stays the same man.
3. `narration` renders each scene's words in the chosen voice.
4. `keyframes` draws one still per shot. The stills are the storyboard: look at them before animating, because a redraw costs 5 credits and a clip costs up to 50.
5. `clips` animates each still with `gen4_turbo`, long enough to cover its share of the scene's narration.
6. `sound` renders the lyre bed and the scene ambiences.
7. `assemble` is free. It cuts everything to the narration, adds the title and end cards and writes `seventy-cubits.mp4`.

`film.py cost` prints what is left to spend at any point.
