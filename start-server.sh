#!/usr/bin/env bash
# Start the KiCAD MCP server (Pure Python implementation)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment if it exists
if [ -f ".venv/bin/activate" ]; then
    source ".venv/bin/activate"
fi

# Load .env if present
if [ -f ".env" ]; then
    set -a
    source ".env"
    set +a
fi

exec python3 -m kicad_mcp "$@"
