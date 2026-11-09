# Lessons

What making many films this way taught. The first list is rules: each one is a mistake that cost a render, a round of notes or a person's trust, and the fix. The second list is questions: each one was answered one way for one studio's taste, and your answer belongs in your `look.md`.

## Rules

**Measuring**

- A number on screen that was not measured is a guess dressed as a fact. Measure it, write down how, and show only that.
- A number borrowed from a different measurement is not the measurement. Run the real one.
- Valid audio does not prove the requested instrument, lyric or change happened. A file of the right length, decoding cleanly, can still be the wrong music. Listen, or have the person listen, and record which you did.
- When a person gives a timestamp, measure that moment first: every layer of it, before changing anything.

**Rendering**

- A frame range is half-open: `[from, to)`. Rendering "up to 25.2 s" stops before the frame at 25.2. Check the frame count before encoding: a missing frame encodes as a shorter film without an error.
- A word changed after a render needs its whole life re-rendered, its fade-out included, or the last frames of the old word survive.
- Drafts render at 5 fps. Full rate is for the finish.
- Re-render only the span that changed and prove the rest is byte-identical. A full re-render "to be safe" can drift and costs the most.
- A long render in one browser will eventually crash. Render in slices, resume from what is on disk, and read the tool's result line rather than its log.
- Frames on a RAM-backed `/tmp` eat the memory the render needs. Write frames to a real disk.
- Two heavy renders side by side can run a machine out of memory. Take the render lock.

**Looking**

- A frame you have not looked at is not done. Read a contact sheet at every beat before handing anything over.
- A headless screenshot of a page that draws in turns catches it half drawn. Wait for the page to say it is finished (`window.PRINTED = true`) and photograph it in real time.
- A screenshot of a hidden browser window can time out. Use headless.
- A `save()` without its `restore()` throws nothing and draws everything after it wrong. Probe the canvas state.
- Counters that climb show in-between numbers on the way. Either hold only measured values on screen, or check that each counter settles on its value.

**Sound and picture**

- A cue written on a shot's start second sounds early, because pictures take frames to appear. Put each cue on the frame its picture actually appears, measured from the frames.
- Sound before its picture is noticed from about 45 ms; sound after it from about 125 ms. Fix early misses first.
- Never stretch an approved piece of music to fit the picture. Cut the picture to the music.
- A sample ceiling still leaves true peaks over it. Measure true peak, not sample peak.

**Working**

- A server left running looks like a job that never finished, and a server that stopped breaks every link to it. Start one per job and stop it.
- A preview built from scratch is judged as the film. Draw previews from the real scene.
- When the person names two ways out, build the first and show the second beside it.
- Keep the person's words verbatim. A paraphrase is your opinion of their words.

## Questions for your look

Each of these was answered once for one studio's films. The answers are left out on purpose.

- How many words can a card hold and still be read at a glance?
- How long should the opening hold the subject?
- Where does the film hold still, and for how long?
- What does a dark moment look like?
- After the climax, what is still allowed to happen?
- When a device comes back, how long does it take the second time?
- How much may be on screen at once?
- What is the film's rhythm?
- How does each action get its answer, and how soon?
- How does a sound enter?
