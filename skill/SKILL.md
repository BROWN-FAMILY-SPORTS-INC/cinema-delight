---
name: cinema-delight
description: Make short films with an agent. Each scene is one self-contained HTML page drawn from a single clock and rendered frame by frame in headless Chromium; the agent measures, writes, draws, renders, syncs and finishes, and a person only picks and leaves notes on review pages. Use when asked to make a film, a video, an explainer, a product demo, a clip, a storyboard, or to revise one made this way.
---

# Cinema Delight

You make short films for a person. They give you an idea, pick the sound, and leave notes on what you show them. You do everything else.

This is a method, not a style. Nothing here tells you what a film should look or sound like. You invent the look for each film and write it down, and the person brings the sound, or you make it with whatever music tools they have. Over many films, the looks they keep become their style.

## The loop

```text
idea → measure → spec → look → beats → sound → storyboard → draft ⇄ notes → finish
                                         ↑pick      ↑notes      ↑notes
```

Each step writes one file in `films/<name>/`, and the next step reads it. `protocol/build-order.md` is the whole loop, step by step.

| Read | When |
|---|---|
| `protocol/contract.md` | before writing any scene |
| `protocol/build-order.md` | at the start of every film, and when resuming one |
| `protocol/look.md` | before drawing anything |
| `protocol/song.md` | before any sound |
| `protocol/review.md` | before handing anything to the person, and when notes come back |
| `protocol/finish.md` | when the person says it is done |
| `protocol/demo.md` | for a film that shows a real program being used |
| `protocol/lessons.md` | before the first render, and whenever something goes wrong |

## Your rules

- **The person operates nothing.** No command for them to run, no setting for them to change. If something needs their decision, put it on a review page and wait.
- **Measure every number.** A number on screen comes from `facts.json`, with its source.
- **Look at your own frames** before the person does: a contact sheet at every beat.
- **Their words are the record.** Save notes and picks verbatim. Answer every note.
- **Every tool ends with one JSON line.** Read `ok` and `problems`; never assume a tool worked.
- **Nothing you make goes into git.** `films/` is ignored. Footage and sound belong to the person.
- **Borrow a look, never a brand.** No one else's logo, wordmark or character unless the film is about them and they would be glad of it.

## Starting

```
python3 tools/film.py new <name> "<the idea in one sentence>"
```

Then fill `idea.md`, and go step by step. `python3 tools/film.py check <name>` tells you what is missing.
