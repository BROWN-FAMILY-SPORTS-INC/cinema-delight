#!/usr/bin/env python3
"""Run a command while holding the render lock, so heavy renders take turns instead of competing.

    python3 tools/locked.py <cmd> [args ...]

Two full-rate renders side by side can run a machine out of memory, and both then die halfway. This
takes an advisory lock (the same one flock(1) takes) on $CINEMA_RENDER_LOCK, default
/tmp/cinema-render.lock, runs the command, and releases the lock when it ends.
"""
import fcntl
import os
import subprocess
import sys
import time

if len(sys.argv) < 2:
    sys.exit(__doc__)
with open(os.environ.get("CINEMA_RENDER_LOCK", "/tmp/cinema-render.lock"), "a") as f:
    t0 = time.time()
    fcntl.flock(f, fcntl.LOCK_EX)
    waited = time.time() - t0
    if waited > 1:
        print(f"[locked.py] waited {waited:.0f} s for the render lock", file=sys.stderr, flush=True)
    sys.exit(subprocess.run(sys.argv[1:]).returncode)
