# /// script
# requires-python = ">=3.11"
# dependencies = ["pyte"]
# ///
"""Run a real program in a hidden terminal and keep what it actually drew, screen by screen, for a scene to redraw.

    uv run tools/tty_capture.py <session.json> <out.json>
    uv run tools/tty_capture.py --text <out.json> <seconds>        # print the screen at a second, to check a capture

A demo shows the program itself, not a drawing of it. This runs the command in a pseudo-terminal of the session's size,
feeds everything it prints to a terminal emulator (pyte), types the session's keys on its clock, and keeps a frame
whenever the screen changed. A scene then draws those exact cells in its own window, in its own look, on the film's
clock (kit/demo/tty.js).

The program is told it is in a truecolor xterm. Programs that ask the terminal for its colours (OSC 10/11/4) are
answered from the session's palette, so they draw themselves in the film's colours for real. Cursor-position and
device-attribute queries are answered too, so nothing waits on a reply that never comes.

session.json:
  { "cols": 150, "rows": 42, "fps": 10, "cwd": "...", "cmd": ["bash", "-l"], "env": { ... }, "unset": ["WAYLAND_DISPLAY"],
    "palette": { "fg": "#rrggbb", "bg": "#rrggbb", "colors": ["#rrggbb", x16] },
    "steps": [ {"wait": 1.0}, {"type": "hsl 4 c\\r", "cps": 14}, {"keys": "\\u0000?"}, {"wait_for": "regex", "timeout": 60},
               {"mark": "name"}, {"wait_quiet": 2.0, "timeout": 90} ],
    "tail": 1.0 }
  Keys are written as given ("\\r" Enter, "\\u0000" ctrl+space, "\\u001b[1;7C" ctrl+alt+right). The environment is the
  session's "env" over a minimal base (see SANDBOX below); nothing else of the caller's environment is passed through.

out.json:
  { "cols", "rows", "fps", "palette", "table": [row, ...], "frames": [[t, [row index x rows], cursor_x, cursor_y, visible]],
    "marks": [[t, name]], "keys": [[t, text]], "dur" }
  A row is a list of runs [col, text, fg, bg, flags]: fg/bg are "default", an ANSI name ("red", "brightblue"...) or a hex
  colour; flags: 1 bold, 2 italic, 4 underline, 8 reverse. A run starts after a wide character's spacer cell, so every
  run's column is exact.
"""

import json
import os
import pty
import re
import select
import signal
import struct
import fcntl
import sys
import termios
import time
from pathlib import Path

import pyte

# What a captured program sees of the machine: no display, compositor, session bus or ssh agent. That is enough for a
# program that only draws. It is NOT enough for a program that runs its own commands, such as a coding agent: give
# those "isolation": "bwrap" and wrap the command in bubblewrap, so it cannot touch the real home.
SANDBOX_UNSET = ["WAYLAND_DISPLAY", "DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE", "DBUS_SESSION_BUS_ADDRESS", "SSH_AUTH_SOCK",
                 "XDG_SESSION_ID", "XDG_SEAT", "TMUX"]


def osc_reply(num, idx, palette):
    def rgb(h):
        h = h.lstrip("#")
        return "rgb:" + "/".join(h[i:i + 2] * 2 for i in (0, 2, 4))
    if num == "10":
        return f"\x1b]10;{rgb(palette['fg'])}\x1b\\"
    if num == "11":
        return f"\x1b]11;{rgb(palette['bg'])}\x1b\\"
    if num == "12":
        return f"\x1b]12;{rgb(palette.get('cursor', palette['fg']))}\x1b\\"
    if num == "4" and idx is not None and idx < len(palette["colors"]):
        return f"\x1b]4;{idx};{rgb(palette['colors'][idx])}\x1b\\"
    return None


OSC_Q = re.compile(rb"\x1b\](10|11|12|4);(?:(\d+);)?\?(?:\x07|\x1b\\)")


class Answering(pyte.Screen):
    """A screen that writes the terminal's answers (cursor position, device attributes) back to the program."""

    def __init__(self, cols, rows, fd):
        super().__init__(cols, rows)
        self.fd = fd

    def write_process_input(self, data):
        os.write(self.fd, data.encode())


def encode_row(line, cols):
    runs, cur = [], None
    for x in range(cols):
        ch = line[x]
        if ch.data == "":                      # the spacer after a wide character: close the run, start fresh after it
            cur = None
            continue
        flags = (1 if ch.bold else 0) | (2 if ch.italics else 0) | (4 if ch.underscore else 0) | (8 if ch.reverse else 0)
        key = (ch.fg, ch.bg, flags)
        if cur is not None and cur[1] == key:
            cur[0][1] += ch.data
        else:
            run = [x, ch.data, ch.fg, ch.bg, flags]
            runs.append(run)
            cur = (run, key)
    # trailing default spaces carry nothing
    while runs and runs[-1][2] == "default" and runs[-1][3] == "default" and runs[-1][4] == 0 and runs[-1][1].strip() == "":
        runs.pop()
    if runs and runs[-1][3] == "default" and runs[-1][4] & 12 == 0:
        runs[-1][1] = runs[-1][1].rstrip(" ") or runs[-1][1][:1]
    return runs


def capture(spec_path, out_path):
    S = json.loads(Path(spec_path).read_text())
    cols, rows, fps = S["cols"], S["rows"], S.get("fps", 10)
    palette = S["palette"]
    env = {"TERM": "xterm-256color", "COLORTERM": "truecolor", "LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8",
           "PATH": "/usr/local/bin:/usr/bin:/bin"}
    env.update(S.get("env", {}))
    for k in SANDBOX_UNSET + S.get("unset", []):
        env.pop(k, None)
    if S.get("isolation") == "bwrap":
        # The command is wrapped in bubblewrap by the caller (its paths are the sandbox's own, not this machine's).
        # Redirected HOME and XDG folders alone do NOT hold: a coding agent run with both pointed at a scratch home has
        # been seen reading and editing the real user's config. Only a mount namespace keeps an agent out.
        if S["cmd"][0] != "bwrap":
            sys.exit("isolation is bwrap but the command is not wrapped in bwrap")
    else:
        # A captured program gets a home of its own, never the caller's: the session's "env" may name one, and any
        # folder it leaves out is made fresh and empty inside it.
        import tempfile
        env.setdefault("HOME", tempfile.mkdtemp(prefix="tty-home-"))
        for k, sub in (("XDG_CONFIG_HOME", ".config"), ("XDG_DATA_HOME", ".local/share"), ("XDG_STATE_HOME", ".local/state"),
                       ("XDG_CACHE_HOME", ".cache"), ("XDG_RUNTIME_DIR", ".run")):
            env.setdefault(k, str(Path(env["HOME"]) / sub))
        for k in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR"):
            Path(env[k]).mkdir(parents=True, exist_ok=True)
        os.chmod(env["XDG_RUNTIME_DIR"], 0o700)

    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(S.get("cwd", env["HOME"]))
        os.execvpe(S["cmd"][0], S["cmd"], env)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    screen = Answering(cols, rows, fd)
    stream = pyte.ByteStream(screen)

    table, index, frames, marks, keys = [], {}, [], [], []
    raw = open(S["raw_log"], "wb") if S.get("raw_log") else None    # everything the program printed, for debugging a capture
    palettes = [[0.0, S.get("palette_name", ""), palette]]          # [t, name, palette]: the terminal's theme from t on
    t0 = time.monotonic()
    now = lambda: time.monotonic() - t0
    last_change = [0.0]
    alive = [True]

    def pump(until):
        while True:
            left = until - time.monotonic()
            if left <= 0 or not alive[0]:
                return
            r, _, _ = select.select([fd], [], [], min(left, 1 / fps / 2))
            if r:
                try:
                    data = os.read(fd, 65536)
                except OSError:
                    alive[0] = False
                    return
                if not data:
                    alive[0] = False
                    return
                if raw:
                    raw.write(data)
                for m in OSC_Q.finditer(data):
                    rep = osc_reply(m.group(1).decode(), int(m.group(2)) if m.group(2) else None, palette)
                    if rep:
                        os.write(fd, rep.encode())
                stream.feed(data)
                last_change[0] = now()
            snap()

    next_snap = [0.0]

    def snap(force=False):
        t = now()
        if not force and t < next_snap[0]:
            return
        if not force and not screen.dirty and frames:
            next_snap[0] = t + 1 / fps
            return
        ids = []
        for y in range(rows):
            key = json.dumps(encode_row(screen.buffer[y], cols), ensure_ascii=False, separators=(",", ":"))
            if key not in index:
                index[key] = len(table)
                table.append(json.loads(key))
            ids.append(index[key])
        cur = [screen.cursor.x, screen.cursor.y, 0 if screen.cursor.hidden else 1]
        if not frames or frames[-1][1] != ids or frames[-1][2:] != cur:
            frames.append([round(t, 3), ids, *cur])
        screen.dirty.clear()
        next_snap[0] = t + 1 / fps

    def send(text, cps=None):
        keys.append([round(now(), 3), text])
        if not cps:
            os.write(fd, text.encode())
            return
        for ch in text:
            os.write(fd, ch.encode())
            pump(time.monotonic() + 1 / cps)

    def screen_text():
        return "\n".join(screen.display)

    for st in S.get("steps", []):
        if not alive[0]:
            break
        if "wait" in st:
            pump(time.monotonic() + st["wait"])
        elif "keys" in st:
            send(st["keys"])
        elif "type" in st:
            send(st["type"], st.get("cps", 14))
        elif "mark" in st:
            marks.append([round(now(), 3), st["mark"]])
        elif "touch" in st:
            # create a file: a trigger for something watching inside a sandbox (e.g. a reload a desktop sends on a
            # theme change), at this moment of the capture
            Path(st["touch"]).touch()
            marks.append([round(now(), 3), f"touch {Path(st['touch']).name}"])
        elif "palette" in st:
            # The terminal changes theme, as a desktop's theme switch changes a terminal's: from here colour queries are
            # answered from the new palette, and a program that asked to be told (DEC mode 2031) is
            # sent the palette-update report, so it asks again and redraws itself in the new colours.
            palette = st["palette"]
            palettes.append([round(now(), 3), st.get("name", ""), palette])
            marks.append([round(now(), 3), f"palette {st.get('name', '')}".strip()])
            if st.get("notify", True):
                os.write(fd, b"\x1b[?997;1n")
        elif "wait_for" in st:
            pat, end = re.compile(st["wait_for"]), time.monotonic() + st.get("timeout", 60)
            while time.monotonic() < end and alive[0] and not pat.search(screen_text()):
                pump(time.monotonic() + 0.1)
            if not pat.search(screen_text()):
                print(f"wait_for {st['wait_for']!r} timed out at {now():.1f} s", file=sys.stderr)
                marks.append([round(now(), 3), f"TIMEOUT {st['wait_for']}"])
        elif "wait_quiet" in st:
            end = time.monotonic() + st.get("timeout", 120)
            while time.monotonic() < end and alive[0] and now() - last_change[0] < st["wait_quiet"]:
                pump(time.monotonic() + 0.1)
        snap()
    pump(time.monotonic() + S.get("tail", 1.0))
    snap(force=True)
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
    except (ProcessLookupError, ChildProcessError):
        pass
    out = {"cols": cols, "rows": rows, "fps": fps, "palette": S["palette"], "dur": round(now(), 3), "table": table,
           "frames": frames, "marks": marks, "keys": keys, "palettes": palettes, "cmd": S["cmd"][S["cmd"].index("--") + 1:] if "--" in S["cmd"] else S["cmd"]}
    Path(out_path).write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(f"{out_path}: {len(frames)} frames over {out['dur']:.1f} s, {len(table)} distinct rows, "
          f"{Path(out_path).stat().st_size // 1024} KB; marks {[m[1] for m in marks]}")


def text_at(path, t):
    C = json.loads(Path(path).read_text())
    fr = [f for f in C["frames"] if f[0] <= t][-1]
    for i in fr[1]:
        line = [" "] * C["cols"]
        for col, text, *_ in C["table"][i]:
            for k, ch in enumerate(text):
                if col + k < C["cols"]:
                    line[col + k] = ch
        print("".join(line).rstrip())
    print(f"-- frame at {fr[0]} s; cursor {fr[2]},{fr[3]} {'shown' if fr[4] else 'hidden'}; marks {C['marks']}")


if __name__ == "__main__":
    if sys.argv[1] == "--text":
        text_at(sys.argv[2], float(sys.argv[3]))
    else:
        capture(sys.argv[1], sys.argv[2])
