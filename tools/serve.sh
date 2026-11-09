#!/usr/bin/env bash
# Serve a folder on 127.0.0.1:<port>, for watching a scene live in a browser.
#   tools/serve.sh <dir> [port=8795]
# Runs in the foreground: start it in the background, and stop it when the work is done. A server
# left running looks like a job that never finished; one that stopped breaks every link to it.
set -euo pipefail
exec python3 -m http.server "${2:-8795}" --bind 127.0.0.1 --directory "${1:-.}"
