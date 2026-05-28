"""
Pending connection registry — sidecar JSON that stores fromRef/fromPin/toRef/toPin
connections queued by add_schematic_wire before optimize_schematic routes them.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


def _sidecar(sch_path: str | Path) -> Path:
    p = Path(sch_path)
    return p.with_name(p.stem + ".connections.json")


def load_pending(sch_path: str | Path) -> List[Dict]:
    """Return list of pending connections, or [] if none."""
    sc = _sidecar(sch_path)
    if not sc.exists():
        return []
    try:
        data = json.loads(sc.read_text(encoding="utf-8"))
        return data.get("connections", [])
    except Exception as exc:
        logger.warning(f"Failed to read connection registry {sc}: {exc}")
        return []


def save_pending(sch_path: str | Path, connections: List[Dict]) -> None:
    sc = _sidecar(sch_path)
    sc.write_text(
        json.dumps({"schematic": str(sch_path), "connections": connections}, indent=2),
        encoding="utf-8",
    )


def add_connection(sch_path: str | Path, conn: Dict) -> int:
    """Append one connection and return the new total pending count."""
    existing = load_pending(sch_path)
    existing.append(conn)
    save_pending(sch_path, existing)
    return len(existing)


def clear_pending(sch_path: str | Path) -> None:
    sc = _sidecar(sch_path)
    if sc.exists():
        sc.unlink()
