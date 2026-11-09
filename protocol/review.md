# Review: the person's only surface

The person does not operate anything. They watch, they pick, and they write notes. The notes steer the next draft. The pipeline can run without them, but a film made that way is made for nobody.

## A review page

Every hand-over is one local HTML page: the storyboard (`board.html`) or the draft (`review.html`). It shows the film or the frames, a note box on every frame or moment, and a **Copy notes** button that turns everything typed into plain text the person pastes back to you. It loads nothing from outside, and it works opened from disk.

Check the page yourself before handing it over: `node tools/pageshot.mjs file://<page> <out.png>` and read the picture. A film that will not play is caught by `python3 tools/deliver.py <page> <film.mp4>`.

## Before the person sees it

- **Look at every frame that matters.** Make a contact sheet at every beat (`node tools/stills.mjs`), read it, and open at full size only the frames that look wrong. A frame you have not looked at is not done.
- **Sweep for errors.** `node tools/stills.mjs <url> <dir> --sweep <end>` seeks the whole film and reports any second whose draw throws.
- **Probe the drawing state** on canvas scenes: `node tools/state-probe.mjs`.
- **Check the sync** of sound to picture (`protocol/song.md`).

## When notes come back

1. Save them verbatim: `films/<name>/notes/round-N.txt`. Their words are the record; a paraphrase is your opinion of their words.
2. Find the moment each note is about. If it names a second, measure that second first, every layer of it, before changing anything.
3. Write each one into `moments.json`: their words, the second, what the frame shows, what you will change.
4. If a note can be read two ways, take the reading their film's own design supports and say on the next page which reading you took.
5. Change what was noted, and nothing they did not flag. Re-render only the span that changed, plus the whole life of anything you changed, fade-out included.
6. On the next page, answer every note: what changed, or why it did not.

Silence is not agreement. A note with no answer is still open.

## Options

When the direction is open, offer options side by side on one page rather than one guess: often four, two close to what they asked for, one experiment, and one well outside it. Their pick is often a mix of two; when it is, build the mix, then stop varying once they say it is right.
