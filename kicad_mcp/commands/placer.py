"""
Auto-placement engine for optimize_schematic.

When add_schematic_component is called without x/y, the component is placed at
a staging area (x = STAGING_X).  optimize_schematic calls place_and_move() to
compute a sensible layout and apply it before routing wires.

Algorithm: star-BFS from the anchor (highest-degree node in the connection
graph).  Each unplaced component is positioned one COMP_STEP away from the
connecting pin, in the pin's exit direction.  A simple grid-snapping collision
resolver nudges clashing placements perpendicular to the exit direction.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

STAGING_X: float = -1000.0   # sentinel x for "not yet placed"
ANCHOR_X:  float =  140.0
ANCHOR_Y:  float =  100.0
COMP_STEP: float =   20.32   # 8 × 2.54 mm  — pin-tip to child component centre
GRID:      float =    2.54


def staging_position(index: int) -> Tuple[float, float]:
    return (STAGING_X + index * GRID, 0.0)


def is_staged(x: float) -> bool:
    return x <= STAGING_X + 50.0   # anything within 50 mm of the sentinel


# ---------------------------------------------------------------------------
# schematic S-expr helpers
# ---------------------------------------------------------------------------

def get_component_positions(sch_path) -> Dict[str, Tuple[float, float]]:
    """Return {ref: (x, y)} for every symbol in the schematic."""
    try:
        import sexpdata
        from sexpdata import Symbol
        _SYM  = Symbol("symbol")
        _AT   = Symbol("at")
        _PROP = Symbol("property")
        data = sexpdata.loads(Path(sch_path).read_text(encoding="utf-8"))
        result: Dict[str, Tuple[float, float]] = {}
        for item in data[1:]:
            if not (isinstance(item, list) and item and item[0] == _SYM):
                continue
            ref_val = at_pos = None
            for sub in item[1:]:
                if not isinstance(sub, list) or not sub:
                    continue
                if sub[0] == _PROP and len(sub) >= 3 and str(sub[1]).strip('"') == "Reference":
                    ref_val = str(sub[2]).strip('"').rstrip("_")
                elif sub[0] == _AT:
                    at_pos = (float(sub[1]), float(sub[2]))
            if ref_val and at_pos:
                result[ref_val] = at_pos
        return result
    except Exception as exc:
        logger.warning(f"get_component_positions failed: {exc}")
        return {}


def batch_move_components(sch_path, moves: Dict[str, Tuple[float, float]]) -> int:
    """
    Apply {ref: (new_x, new_y)} moves to the schematic in one pass.
    Returns number of components moved.
    """
    if not moves:
        return 0
    try:
        import sexpdata
        from sexpdata import Symbol
        _SYM  = Symbol("symbol")
        _AT   = Symbol("at")
        _PROP = Symbol("property")
        path = Path(sch_path)
        data = sexpdata.loads(path.read_text(encoding="utf-8"))
        moved = 0
        for item in data[1:]:
            if not (isinstance(item, list) and item and item[0] == _SYM):
                continue
            ref_val = None
            for sub in item[1:]:
                if (isinstance(sub, list) and sub and sub[0] == _PROP
                        and len(sub) >= 3 and str(sub[1]).strip('"') == "Reference"):
                    ref_val = str(sub[2]).strip('"').rstrip("_")
                    break
            if ref_val not in moves:
                continue
            new_x, new_y = moves[ref_val]
            old_x = old_y = None
            for i, sub in enumerate(item):
                if isinstance(sub, list) and sub and sub[0] == _AT:
                    old_x, old_y = float(sub[1]), float(sub[2])
                    item[i] = [_AT, new_x, new_y] + list(sub[3:])
                    break
            if old_x is None:
                continue
            dx, dy = new_x - old_x, new_y - old_y
            for sub in item[1:]:
                if isinstance(sub, list) and sub and sub[0] == _PROP:
                    for j, psub in enumerate(sub):
                        if isinstance(psub, list) and psub and psub[0] == _AT:
                            sub[j] = [_AT, float(psub[1]) + dx,
                                      float(psub[2]) + dy] + list(psub[3:])
            moved += 1
        if moved:
            path.write_text(sexpdata.dumps(data), encoding="utf-8")
        return moved
    except Exception as exc:
        logger.warning(f"batch_move_components failed: {exc}")
        return 0


# ---------------------------------------------------------------------------
# placement algorithm
# ---------------------------------------------------------------------------

def _snap(v: float) -> float:
    return round(v / GRID) * GRID


def _angle_dir(angle) -> Tuple[float, float]:
    """
    Return unit (dx, dy) OUTWARD exit vector for a KiCAD pin.

    get_pin_angle() returns the pin-stub direction (toward component body) for
    horizontal pins (0°/180°) but the outward (wire-exit) direction for vertical
    pins (90°/270°).  We invert the horizontal cases here so the placer always
    walks AWAY from the component body.
    """
    if angle is None:
        return (1.0, 0.0)
    a = float(angle) % 360
    # Horizontal: get_pin_angle gives INWARD → invert to get OUTWARD
    if abs(a) < 1:        return (-1.0,  0.0)   # 0° stub→right  → exit LEFT
    if abs(a - 180) < 1:  return ( 1.0,  0.0)   # 180° stub→left → exit RIGHT
    # Vertical: get_pin_angle already gives OUTWARD (Y-flip corrects these)
    if abs(a - 90) < 1:   return ( 0.0, -1.0)   # 90° → UP (y decreases)
    if abs(a - 270) < 1:  return ( 0.0,  1.0)   # 270° → DOWN (y increases)
    rad = math.radians(a)
    return (-math.cos(rad), math.sin(rad))


def _bbox(cx: float, cy: float, half_w: float = 8.0, half_h: float = 3.5
          ) -> Tuple[float, float, float, float]:
    return (cx - half_w, cy - half_h, cx + half_w, cy + half_h)


def _overlaps(b1, b2, margin: float = 2.54) -> bool:
    x00, y00, x01, y01 = b1
    x10, y10, x11, y11 = b2
    return not (x01 + margin < x10 or x11 + margin < x00 or
                y01 + margin < y10 or y11 + margin < y00)


def _free_slot(prop_x: float, prop_y: float,
               dx: float, dy: float,
               boxes: List) -> Tuple[float, float]:
    """Nudge (prop_x, prop_y) until its bbox doesn't overlap any box in *boxes*."""
    perp_x, perp_y = -dy, dx   # 90° CCW
    for attempt in range(16):
        bb = _bbox(prop_x, prop_y)
        if not any(_overlaps(bb, b) for b in boxes):
            return prop_x, prop_y
        if attempt % 2 == 0:
            prop_x = _snap(prop_x + perp_x * GRID * 4)
            prop_y = _snap(prop_y + perp_y * GRID * 4)
        else:
            prop_x = _snap(prop_x + dx * GRID * 4)
            prop_y = _snap(prop_y + dy * GRID * 4)
    return prop_x, prop_y


def compute_placement(
    connections: List[Dict],
    current_positions: Dict[str, Tuple[float, float]],
    locator,
    sch_path,
) -> Dict[str, Tuple[float, float]]:
    """
    Return {ref: (new_x, new_y)} only for components currently in staging area.
    Does NOT touch the schematic file.
    """
    if not connections:
        return {}

    # Build adjacency: ref → [(my_pin, other_ref, other_pin)]
    adj: Dict[str, List[Tuple[str, str, str]]] = {}
    all_refs: set = set()
    for c in connections:
        fr, fp = c["fromRef"], str(c["fromPin"])
        tr, tp = c["toRef"],   str(c["toPin"])
        all_refs.update([fr, tr])
        adj.setdefault(fr, []).append((fp, tr, tp))
        adj.setdefault(tr, []).append((tp, fr, fp))

    real_refs = {r for r in all_refs if not r.startswith("#")}
    if not real_refs:
        return {}

    # Anchor = highest unique-neighbor count
    degree = {r: len({nb for _, nb, _ in adj.get(r, []) if not nb.startswith("#")})
              for r in real_refs}
    anchor = max(degree, key=degree.get)

    # Anchor position: keep if fixed, else default
    anchor_pos = current_positions.get(anchor)
    if anchor_pos is None or is_staged(anchor_pos[0]):
        anchor_pos = (ANCHOR_X, ANCHOR_Y)

    placed: Dict[str, Tuple[float, float]] = {anchor: anchor_pos}
    boxes: List = [_bbox(*anchor_pos, half_w=14.0, half_h=9.0)]  # anchor is an IC
    visited: set = {anchor}
    queue: List[str] = [anchor]

    while queue:
        parent = queue.pop(0)
        parent_pos = placed[parent]

        for pin_id, child_ref, child_pin in adj.get(parent, []):
            if child_ref in visited or child_ref.startswith("#"):
                continue

            pin_pos = locator.get_pin_location(sch_path, parent, pin_id)
            pin_angle = locator.get_pin_angle(sch_path, parent, pin_id)
            dx, dy = _angle_dir(pin_angle)

            if pin_pos is None:
                pin_pos = parent_pos

            prop_x = _snap(pin_pos[0] + dx * COMP_STEP)
            prop_y = _snap(pin_pos[1] + dy * COMP_STEP)
            final_x, final_y = _free_slot(prop_x, prop_y, dx, dy, boxes)

            placed[child_ref]  = (final_x, final_y)
            visited.add(child_ref)
            boxes.append(_bbox(final_x, final_y))
            queue.append(child_ref)

    # Only return refs that are currently staged (need to move)
    return {ref: pos for ref, pos in placed.items()
            if ref in real_refs
            and is_staged(current_positions.get(ref, (0.0, 0.0))[0])}


def place_and_move(sch_path, connections: List[Dict], locator) -> int:
    """
    Compute placement, apply it to the schematic file.
    Returns number of components repositioned.
    """
    current = get_component_positions(sch_path)
    moves = compute_placement(connections, current, locator, sch_path)
    if not moves:
        return 0
    return batch_move_components(sch_path, moves)
