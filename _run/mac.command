#!/usr/bin/env bash
# macOS one-click: double-click opens Terminal and starts the API + frontend in dev mode.
# The real logic lives in _run/lib/dev.sh (do not run that file directly).
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$DIR/lib/dev.sh"
