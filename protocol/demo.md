# Demos of a real program

A demo shows a person how to use something, step by step, so they can do it themselves afterwards. It is the opposite of a hype cut: instead of telling the viewer the product is good over flashes of features, it shows them how to use it, and they conclude the rest. The sound can carry the excitement; the picture's job is to be calm, legible and true.

`kit/demo/frame.js` gives the layout and the timing of keys, typing and the pointer. `kit/demo/tty.js` draws a real terminal capture. `tools/tty_capture.py` makes the capture. None of them decides how the demo looks: that is your `look.md`.

## The grammar

- **Chapters, one action each.** Each chapter is a step someone could follow: install, open, the core move, a second move, the move on a real file, the result. Number them.
- **Words on one side, the program on the other.** A short label for the chapter, a statement of what to do, and at most a few small notes. The program's window takes the rest, large, in its real states.
- **The real program, captured.** Its own strings, its own placeholder text, its real output. Run it with `tools/tty_capture.py` and draw the capture; never draw a mock-up of what it would show. A program that runs commands of its own (a coding agent, an installer) runs inside a sandbox: `"isolation": "bwrap"` in the session.
- **Keys and the pointer are the viewer's hands.** A key presses on the beat that answers it; a click shows where it landed; a drag is seen moving. Every action gets its answer on screen soon after.
- **Lean in when it is too small to read.** Move the camera into the part of the window being used (`tools/camera.js`), and keep the window's edges on screen so the viewer knows where they are.
- **Say how to get it.** Near the end, the exact command or link, readable and held long enough to copy, with any prerequisite named where it is first needed rather than hidden at the end.
- **Production notes stay off the picture.** What was captured, what was drawn and what was edited belongs on the review page, not in the frame.

## A short demo's order

Use this when the viewer needs a quick introduction and enough to try it. Its timing is yours to choose.

| Passage | What the viewer sees |
|---|---|
| Intro | What it is, named, and the idea of the film |
| Purpose | The problem it solves, and what using it gets you |
| How to use | The essential steps, each action followed by its answer |
| In action | The problem visibly solved, on something real |
| One detail, optional | One thing worth the time, or nothing |
| Get it | The exact install or access route, with its prerequisites |
| Outro | The intro's idea resolved; who made it |

## Capturing

```json
{ "cols": 120, "rows": 34, "fps": 10, "cwd": "/tmp/demo", "cmd": ["bash", "--noprofile", "--norc"],
  "palette": { "fg": "#d0d0d0", "bg": "#101010", "colors": ["#000000", "#cc0000", "#00cc00", "#cccc00", "#0000cc", "#cc00cc", "#00cccc", "#cccccc",
                                                           "#555555", "#ff5555", "#55ff55", "#ffff55", "#5555ff", "#ff55ff", "#55ffff", "#ffffff"] },
  "steps": [ {"wait": 0.5}, {"type": "ls -la\r", "cps": 12}, {"wait_quiet": 1.0, "timeout": 10}, {"mark": "listed"} ],
  "tail": 1.0 }
```

The program gets a fresh, empty home of its own unless the session's `env` names one; the caller's home is never passed through. The palette is the film's: take it from your `look.md`. `uv run tools/tty_capture.py session.json capture.json`, then `uv run tools/tty_capture.py --text capture.json <seconds>` prints the screen at a second, to check it before drawing. In the scene, `TTY.draw(ctx, x, y, w, h, capture, TTY.at(map, t), { face: <your look's monospace face> })` draws it, with `map` saying which capture second plays at which film second.
