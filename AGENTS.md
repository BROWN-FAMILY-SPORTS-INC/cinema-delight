# Cinema Delight, for the agent

You make short films for a person. They give you an idea, pick the sound, and leave notes on what you show them. You do everything else: measure, write, draw, render, sync and finish. Nothing here is meant to be run by a person.

**Read `skill/SKILL.md` first.** It is the method, and it points to the protocol for each step.

## The contract, in one paragraph

A scene is one self-contained HTML page that draws a 1920×1080 frame as a pure function of one clock `t`. It exposes `window.briefStages.seek(id, t)`, freezes at `?t=<seconds>`, uses only seeded randomness, and loads nothing from outside. Because the picture is a function of `t`, it can be watched live, frozen for a still, and rendered one exact frame at a time, and all three agree. `protocol/contract.md` has the rules; `tests/fixture/grey.html` is the smallest scene that keeps them.

## Before you hand anything over

- `tests/run.sh` passes.
- Every tool you call ends with one JSON line: read it, and act on `problems`.
- Your films live in `films/<name>/`. Git ignores them; never commit footage or sound.

## Using it as a skill

Claude Code: `ln -s "$PWD/skill" ~/.claude/skills/cinema-delight`. Other agents read this file and `skill/SKILL.md` directly.
