#!/usr/bin/env python3
"""
Parity check gate: verifies that every tool registered in the original TypeScript
implementation (src/tools/*.ts server.tool() calls) exists in TOOL_SCHEMAS.

Run from repo root:
    python3 scripts/parity_check.py [--ts-root /path/to/KiCAD-MCP-Server/src/tools]

Exit code 0 = full parity.  Non-zero = mismatch (CI gate fails).
"""

import argparse
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_TS_ROOT = Path(__file__).parent.parent.parent / "KiCAD-MCP-Server" / "src" / "tools"
PYTHON_REPO_ROOT = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def extract_ts_tool_names(ts_root: Path) -> list[str]:
    """Regex-scan *.ts files for server.tool("name", ...) registrations."""
    names: list[str] = []
    pattern = re.compile(r'server\.tool\(\s*["\']([^"\']+)["\']')
    for ts_file in sorted(ts_root.glob("*.ts")):
        text = ts_file.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            names.append(match.group(1))
    return names


def load_python_schema_names() -> list[str]:
    sys.path.insert(0, str(PYTHON_REPO_ROOT))
    from kicad_mcp.schemas.tool_schemas import TOOL_SCHEMAS  # noqa: PLC0415
    return list(TOOL_SCHEMAS.keys())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="KiCAD MCP tool parity check")
    parser.add_argument(
        "--ts-root",
        type=Path,
        default=DEFAULT_TS_ROOT,
        help="Path to original TypeScript src/tools/ directory",
    )
    args = parser.parse_args()

    ts_root: Path = args.ts_root
    if not ts_root.is_dir():
        print(f"ERROR: TypeScript tools directory not found: {ts_root}", file=sys.stderr)
        print("Pass --ts-root to override.", file=sys.stderr)
        return 2

    ts_names = extract_ts_tool_names(ts_root)
    py_names = load_python_schema_names()

    ts_set = set(ts_names)
    py_set = set(py_names)

    missing_in_py = ts_set - py_set
    extra_in_py = py_set - ts_set

    ok = True

    if missing_in_py:
        ok = False
        print(f"FAIL: {len(missing_in_py)} tool(s) in original TS but missing from TOOL_SCHEMAS:")
        for name in sorted(missing_in_py):
            print(f"  - {name}")

    if extra_in_py:
        print(f"WARN: {len(extra_in_py)} tool(s) in TOOL_SCHEMAS but not in original TS (may be OK):")
        for name in sorted(extra_in_py):
            print(f"  + {name}")

    if ok:
        print(f"OK: {len(ts_set)} tools in TS, {len(py_set)} in TOOL_SCHEMAS — full parity confirmed.")
        if extra_in_py:
            print(f"     ({len(extra_in_py)} extra Python-only tools are acceptable.)")
    else:
        print(f"\nTotal TS tools: {len(ts_set)}  |  Total Python schemas: {len(py_set)}")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
