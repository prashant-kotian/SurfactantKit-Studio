#!/usr/bin/env bash
# SurfactantKit Studio installer for macOS and Linux. Needs Python 3.10 or newer.
# Creates a private environment in .venv next to this file; nothing is installed system-wide.
# SurfactantKit comes from GitHub by default; set SURFACTANTKIT_SRC to a local copy to use that instead.
set -euo pipefail
cd "$(dirname "$0")"

PY=${PYTHON:-python3}
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
  echo "Python 3.10 or newer was not found (set PYTHON=/path/to/python3 to choose one)." >&2
  exit 1
fi
[ -d .venv ] || "$PY" -m venv .venv
VPY=.venv/bin/python
"$VPY" -m pip install --upgrade pip >/dev/null
if [ -n "${SURFACTANTKIT_SRC:-}" ]; then
  "$VPY" -m pip install -e "${SURFACTANTKIT_SRC}[calc]"
else
  "$VPY" -m pip install "surfactantkit[calc] @ git+https://github.com/prashant-kotian/Surfactant-Toolkit.git@v1.3.0"
fi
"$VPY" -m pip install -e .
echo
echo "Installed. Start it with ./run_studio.sh (opens http://127.0.0.1:8770)."
