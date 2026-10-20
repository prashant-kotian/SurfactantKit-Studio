#!/usr/bin/env bash
# Start SurfactantKit Studio (local only, http://127.0.0.1:8770). Ctrl+C to stop.
cd "$(dirname "$0")"
if [ ! -x .venv/bin/surfkit-studio ]; then
  echo "SurfactantKit Studio is not installed yet. Run ./install.sh first." >&2
  exit 1
fi
exec .venv/bin/surfkit-studio "$@"
