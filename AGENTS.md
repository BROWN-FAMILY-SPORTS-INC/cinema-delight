# Cinema Delight, for the agent

You make short films for a person. They give you an idea, watch what you make, and leave notes. You do everything else: you measure, write, draw, render, sync and finish. Nothing here is meant to be run by a person.

Read the method before building anything: `skill/SKILL.md`.

## The contract, in one paragraph

A scene is one self-contained HTML page that draws a 1920×1080 frame as a pure function of one clock `t`. It exposes `window.briefStages.seek(id, t)`, freezes at `?t=<seconds>`, uses only seeded randomness, and loads nothing from outside. Because the picture is a function of `t`, it can be watched live, frozen for a still, and rendered one exact frame at a time, and all three agree. `protocol/contract.md` has the rules; `tests/fixture/grey.html` is the smallest scene that keeps them.

## Before you hand anything over

- `tests/run.sh` passes.
- Every tool you call ends with one JSON line: read it, and act on `problems`.
- Your films live in `films/<name>/`. Git ignores them; never commit footage or sound.
