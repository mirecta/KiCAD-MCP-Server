"""
Standalone Manhattan wire router for schematic auto-routing.

Extracted from dispatcher._handle_add_schematic_wire so it can be called
both for single-wire drawing and for the batch optimize_schematic pass.
"""

from __future__ import annotations

import math
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_STUB = 5.08  # escape/approach stub length in mm (2 KiCAD grid squares)


def angle_dir(angle: Optional[float]) -> Tuple[int, int]:
    """Unit (dx, dy) exit vector for a pin angle. KiCAD Y increases downward."""
    if angle is None:
        return (0, 0)
    a = angle % 360
    if abs(a) < 1:        return (1,  0)   # RIGHT
    if abs(a - 90) < 1:   return (0, -1)   # UP   (y decreases on screen)
    if abs(a - 180) < 1:  return (-1, 0)   # LEFT
    if abs(a - 270) < 1:  return (0,  1)   # DOWN (y increases on screen)
    return (0, 0)


def manhattan(pts: List[List[float]]) -> List[List[float]]:
    """Ensure all segments in pts are axis-aligned, inserting corners where needed."""
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        if abs(a[0] - b[0]) > 1e-6 and abs(a[1] - b[1]) > 1e-6:
            out.append([a[0], b[1]])
        out.append(b)
    return out


def route_pins(
    p1: List[float],
    p2: List[float],
    fa: Optional[float],
    ta: Optional[float],
) -> List[List[float]]:
    """
    Route from pin p1 (exit angle fa) to pin p2 (exit angle ta).
    Always exits p1 in fa direction and approaches p2 from ta direction.
    Uses a simple L-bend when possible, otherwise escape+approach stubs.
    """
    x1, y1 = p1[0], p1[1]
    x2, y2 = p2[0], p2[1]

    # Already axis-aligned — straight wire
    if abs(x1 - x2) < 1e-4 or abs(y1 - y2) < 1e-4:
        return [p1, p2]

    fd = angle_dir(fa)
    td = angle_dir(ta)

    # When destination pin exits vertically, V-first arrives at pin y-level
    # from the side — avoids H-first corner landing inside the component body.
    if td[1] != 0:
        v_ok = (fd == (0, 0) or fd[0] != 0
                or (fd[1] != 0 and (y2 - y1) * fd[1] > 0))
        if v_ok:
            return [p1, [x1, y2], p2]

    # H-first valid when: from exits H toward x2, and to exits V from correct side
    h_from = fd[0] != 0 and (x2 - x1) * fd[0] > 0
    h_to   = td == (0, 0) or (td[1] != 0 and (y2 - y1) * (-td[1]) > 0)
    if h_from and h_to:
        return [p1, [x2, y1], p2]

    # V-first valid when: from exits V toward y2, and to exits H from correct side
    v_from = fd[1] != 0 and (y2 - y1) * fd[1] > 0
    v_to   = td == (0, 0) or (td[0] != 0 and (x2 - x1) * (-td[0]) > 0)
    if v_from and v_to:
        return [p1, [x1, y2], p2]

    # Escape + approach: emit stub in each pin's exit direction
    esc = [x1 + fd[0] * _STUB, y1 + fd[1] * _STUB] if fd != (0, 0) else [x1, y1]
    app = [x2 + td[0] * _STUB, y2 + td[1] * _STUB] if td != (0, 0) else [x2, y2]

    ex, ey = esc[0], esc[1]
    ax, ay = app[0], app[1]

    inner: List[List[float]] = []
    if abs(ex - ax) > 1e-4 and abs(ey - ay) > 1e-4:
        if fd[1] != 0:    # escaping vertically → turn H first toward ax
            inner = [[ax, ey]]
        else:              # escaping horizontally → turn V first toward ay
            inner = [[ex, ay]]

    raw = [p1, esc] + inner + [app, p2]

    # Deduplicate consecutive identical points
    result = [raw[0]]
    for pt in raw[1:]:
        if abs(pt[0] - result[-1][0]) > 1e-4 or abs(pt[1] - result[-1][1]) > 1e-4:
            result.append(pt)
    return result


def route_connection(
    sch_path: str | Path,
    conn: Dict,
    locator,
) -> Optional[List[List[float]]]:
    """
    Resolve pin locations for one connection dict and return wire waypoints.
    Returns None if pin lookup fails.
    """
    from_ref = conn["fromRef"]
    from_pin = str(conn["fromPin"])
    to_ref   = conn["toRef"]
    to_pin   = str(conn["toPin"])

    start = locator.get_pin_location(sch_path, from_ref, from_pin)
    if start is None:
        logger.warning(f"Pin {from_ref}/{from_pin} not found — skipping connection")
        return None
    end = locator.get_pin_location(sch_path, to_ref, to_pin)
    if end is None:
        logger.warning(f"Pin {to_ref}/{to_pin} not found — skipping connection")
        return None

    fa = locator.get_pin_angle(sch_path, from_ref, from_pin)
    ta = locator.get_pin_angle(sch_path, to_ref, to_pin)

    x1, y1 = start[0], start[1]
    x2, y2 = end[0],   end[1]
    if abs(x1 - x2) < 1e-4 or abs(y1 - y2) < 1e-4:
        return [start, end]
    return route_pins(start, end, fa, ta)


def route_all(
    sch_path: str | Path,
    connections: List[Dict],
) -> List[Tuple[Dict, Optional[List[List[float]]]]]:
    """
    Route all pending connections.  Sorts by Euclidean distance (short first)
    for cleaner layout.  Returns list of (conn, waypoints_or_None).
    """
    from kicad_mcp.commands.pin_locator import PinLocator
    locator = PinLocator()

    # Pre-resolve positions for sorting
    def dist(conn: Dict) -> float:
        try:
            s = locator.get_pin_location(sch_path, conn["fromRef"], str(conn["fromPin"]))
            e = locator.get_pin_location(sch_path, conn["toRef"],   str(conn["toPin"]))
            if s and e:
                return math.hypot(s[0] - e[0], s[1] - e[1])
        except Exception:
            pass
        return 0.0

    sorted_conns = sorted(connections, key=dist)

    results = []
    for conn in sorted_conns:
        pts = route_connection(sch_path, conn, locator)
        results.append((conn, pts))
    return results
