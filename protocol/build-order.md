# The build order

Nine steps. Each writes a file in `films/<name>/`, and the next step reads it. A step whose file is missing is not done, so a film can be resumed by anyone who reads the folder, including you in a later session.

A person comes in three times: to pick the sound, to leave notes on the storyboard, and to leave notes on each draft. Everything else is yours.

| Step | You write | What it is |
|---|---|---|
| 1 Idea | `idea.md` | The one sentence the film tells, who it is for, and what they should do or know after |
| 2 Measure | `facts.json` | Every number the film will show, each with its source and how it was measured |
| 3 Spec | `spec.md` | The story beats, the cards, which fact each card uses |
| 3½ Look | `look.md` | The look you invent for this film (`look.md` in this folder says how) |
| 4 Beats | `beats.json`, `shots.json` | The beats on the film's clock; the shots and camera if it moves |
| 5 Sound | `song/` | The essay, the options, the person's pick (`song.md`) |
| 6 Storyboard | `board.html` | One frame per beat, drawn by the real scene, a note on each |
| 7 Draft | `drafts/draft-N.mp4`, `review.html` | The film at 5 fps with its sound, on a review page |
| 8 Notes | `notes/round-N.txt`, `moments.json` | The person's notes, verbatim, each answered |
| 9 Finish | `finish/` | The full-rate film, its record, checksums, a poster |

`python3 tools/film.py check <name>` says which step a film is on.

## 1. Idea

Write the sentence before anything else. If you cannot say what the film is about in one sentence, the film cannot either. Name the viewer: what do they know already, and what should they know or do at the end?

## 2. Measure

Every number on screen is measured, and the measurement is written down: the value, its unit, where it came from, the command or source that produced it, and when. If the story needs a number nobody has measured, measure it; do not estimate it. A true number is usually a better story than a guessed one, and a guessed number on screen is a lie that looks exactly like a fact.

Claim only what was actually done. If a tool did not do the thing, no card says it did.

## 3. Spec

The story as beats: what happens, in what order, what each card says, which fact it shows. Order serves the story, and the facts stay true. When several looks or versions are tried, they all read this one spec, which is what keeps them telling the same true story.

## 3½. Look

You invent the look for each film; nothing in this repository hands you one. See `protocol/look.md`. Write `look.md` before drawing a frame.

## 4. Beats

The beats as data, on the film's clock. Each beat has a second, a kind (a title, an action, the answer to an action, or where the story stands emotionally) and, if it should be heard, a sound word. The scene, the sound and the sync check all read this one file, so they cannot drift apart. `node tools/beats.mjs check films/<name>/beats.json`.

If the camera moves, `shots.json` holds the shots: each shot's length, which story seconds it plays (the story points), and where the camera is (the flyby points). `tools/camera.js` runs both in the scene and on the storyboard alike.

## 5. Sound

`protocol/song.md`. The person describes what they want or brings their own audio. You write an essay, make options with whatever music tools the person has, and the person picks one.

## 6. Storyboard

Build the scene to the contract, then draw one frame per beat from the real scene, not from a sketch: a sketch is judged as if it were the film. `python3 tools/film.py board <name>` writes `board.html` with a note box on every frame. Hand it over and wait for notes.

## 7. Draft

Freeze the words, then render at 5 fps: drafts are for judging timing and story, and 5 fps costs a twelfth of 60. `python3 tools/film.py draft <name>` renders, puts the sound under it, and writes `review.html`. Look at the contact sheet yourself before the person sees anything.

## 8. Notes

The person pastes their notes back. Save them verbatim as `notes/round-N.txt`, never paraphrased. Turn each into a moment on the film's clock in `moments.json`: their words, the second it lands on (measured from the beats or the sound, never guessed), what the frame shows, and what you changed. Answer every note; a note with no answer is still open. Then draft again. `protocol/review.md`.

## 9. Finish

When the person says it is done: render at full rate, encode, write the record, checksums and a poster. `protocol/finish.md`.
