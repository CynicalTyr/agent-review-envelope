#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
export AGENT_HOME="${AGENT_HOME:-/tmp/$(basename "$ROOT")-smoke}"
mkdir -p "$AGENT_HOME"
python3 -m unittest discover -s tests -q
python3 examples/quickstart.py >/dev/null
echo "smoke ok: $ROOT"
