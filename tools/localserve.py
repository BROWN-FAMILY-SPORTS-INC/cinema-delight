"""Serve this repository on 127.0.0.1 for as long as a job needs it, unless a server of it is already there.

    from localserve import served
    with served("http://127.0.0.1:8791/films/demo/scene/scene.html") as url:
        ...   # url answers with this repository's file; a server started here stops when the block ends

Some scenes need http:// rather than file:// (a browser refuses some things on file://). Two failures
this avoids: a tool that assumes someone left a server running hangs for its whole timeout and then
blames the page; and servers left running pile up until nobody knows which one serves what.

A server already on the URL's port is used only if it answers with this repository's own file at that
path (200, and the same size as the file on disk). Anything else there means starting our own: on the
URL's port if it is free, otherwise on a free port, with the URL rewritten to match.
"""
from __future__ import annotations

import contextlib
import socket
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def listening(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex((host, port)) == 0


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def serves_repo(url: str, root: Path) -> bool:
    """The server at url answers with root's own file at that path."""
    u = urllib.parse.urlparse(url)
    local = root / urllib.parse.unquote(u.path).lstrip("/")
    if local.is_dir():
        local = local / "index.html"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=3) as r:
            size = r.headers.get("Content-Length")
            return r.status == 200 and local.exists() and (size is None or int(size) == local.stat().st_size)
    except Exception:
        return False


@contextlib.contextmanager
def served(url: str, root: Path = REPO):
    u = urllib.parse.urlparse(url)
    if u.scheme not in ("http", "https") or u.hostname not in ("127.0.0.1", "localhost") or not u.port:
        yield url   # not a local server URL: nothing to start
        return
    if listening(u.port) and serves_repo(url, root):
        yield url
        return
    port = u.port if not listening(u.port) else free_port()
    proc = subprocess.Popen(["python3", "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", str(root)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            if listening(port):
                break
            time.sleep(0.1)
        else:
            raise RuntimeError(f"could not start a server on 127.0.0.1:{port}")
        yield urllib.parse.urlunparse(u._replace(netloc=f"127.0.0.1:{port}"))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
