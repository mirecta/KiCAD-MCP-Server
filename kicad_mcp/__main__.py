"""Entry point for `python -m kicad_mcp`."""

import sys


def main() -> None:
    from kicad_mcp.server import run
    run()


if __name__ == "__main__":
    main()
