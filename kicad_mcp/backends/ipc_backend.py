"""
IPC API Backend (KiCAD 9.0+)

Uses the official kipy library for inter-process communication with a running
KiCAD instance.  Changes appear in real-time in the UI.

Requires KiCAD to be running with IPC enabled:
    Preferences > Plugins > Enable IPC API Server
"""

import logging
import os
import platform
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from kicad_mcp.backends.base import (
    APINotAvailableError,
    BoardAPI,
    ConnectionError,
    KiCADBackend,
)

logger = logging.getLogger(__name__)

MM_TO_NM = 1_000_000
INCH_TO_NM = 25_400_000


class IPCBackend(KiCADBackend):
    """KiCAD IPC API backend for real-time UI synchronization."""

    def __init__(self) -> None:
        self._kicad = None
        self._connected = False
        self._version: Optional[str] = None
        self._on_change_callbacks: List[Callable] = []

    def connect(self, socket_path: Optional[str] = None) -> bool:
        try:
            from kipy import KiCad

            logger.info("Connecting to KiCAD via IPC...")

            paths_to_try: List[Optional[str]] = []
            if socket_path:
                paths_to_try.append(socket_path)
            else:
                if platform.system() != "Windows":
                    paths_to_try.append("ipc:///tmp/kicad/api.sock")
                    if hasattr(os, "getuid"):
                        paths_to_try.append(f"ipc:///run/user/{os.getuid()}/kicad/api.sock")
                paths_to_try.append(None)  # auto-detect

            last_error: Optional[Exception] = None
            for path in paths_to_try:
                try:
                    self._kicad = KiCad(socket_path=path) if path else KiCad()
                    self._kicad.ping()
                    logger.info(f"Connected via socket: {path or 'auto-detected'}")
                    break
                except Exception as exc:
                    last_error = exc
                    logger.debug(f"Failed to connect via {path}: {exc}")
            else:
                raise ConnectionError(f"Could not connect to KiCAD IPC: {last_error}")

            self._version = self._get_kicad_version()
            logger.info(f"Connected to KiCAD {self._version} via IPC")
            self._connected = True
            return True

        except ImportError as exc:
            raise APINotAvailableError(
                "IPC backend requires 'kipy'. Install with: pip install kipy"
            ) from exc
        except Exception as exc:
            logger.error(f"Failed to connect via IPC: {exc}")
            raise ConnectionError(f"IPC connection failed: {exc}") from exc

    def _get_kicad_version(self) -> str:
        try:
            if self._kicad.check_version():
                return self._kicad.get_api_version()
            return "9.0+ (version mismatch)"
        except Exception:
            return "unknown"

    def disconnect(self) -> None:
        self._kicad = None
        self._connected = False
        logger.info("Disconnected from KiCAD IPC")

    def is_connected(self) -> bool:
        if not self._connected or not self._kicad:
            return False
        try:
            self._kicad.ping()
            return True
        except Exception:
            self._connected = False
            return False

    def get_version(self) -> str:
        return self._version or "unknown"

    def register_change_callback(self, callback: Callable) -> None:
        self._on_change_callbacks.append(callback)

    def _notify_change(self, change_type: str, details: Dict[str, Any]) -> None:
        for cb in self._on_change_callbacks:
            try:
                cb(change_type, details)
            except Exception as exc:
                logger.warning(f"Change callback error: {exc}")

    # Project Operations
    def create_project(self, path: Path, name: str) -> Dict[str, Any]:
        if not self.is_connected():
            raise ConnectionError("Not connected to KiCAD")
        return {
            "success": False,
            "message": "Direct project creation not supported via IPC",
            "suggestion": "Open KiCAD and create a new project, or use SWIG backend",
        }

    def open_project(self, path: Path) -> Dict[str, Any]:
        if not self.is_connected():
            raise ConnectionError("Not connected to KiCAD")
        try:
            documents = self._kicad.get_open_documents()
            path_str = str(path)
            for doc in documents:
                if path_str in str(doc):
                    return {"success": True, "message": f"Project already open: {path}", "path": path_str}
            return {
                "success": False,
                "message": "Project not currently open in KiCAD",
                "suggestion": "Open the project in KiCAD first",
            }
        except Exception as exc:
            return {"success": False, "message": "Failed to check project", "errorDetails": str(exc)}

    def save_project(self, path: Optional[Path] = None) -> Dict[str, Any]:
        if not self.is_connected():
            raise ConnectionError("Not connected to KiCAD")
        try:
            board = self._kicad.get_board()
            if path:
                board.save_as(str(path))
            else:
                board.save()
            self._notify_change("save", {"path": str(path) if path else "current"})
            return {"success": True, "message": "Project saved successfully"}
        except Exception as exc:
            return {"success": False, "message": "Failed to save project", "errorDetails": str(exc)}

    def close_project(self) -> None:
        logger.warning("Closing projects via IPC is not supported")

    def get_board(self) -> BoardAPI:
        if not self.is_connected():
            raise ConnectionError("Not connected to KiCAD")
        return IPCBoardAPI(self._kicad, self._notify_change)


class IPCBoardAPI(BoardAPI):
    """Board API using IPC — changes appear immediately in KiCAD UI."""

    def __init__(self, kicad_instance: Any, notify_callback: Callable) -> None:
        self._kicad = kicad_instance
        self._board = None
        self._notify = notify_callback
        self._current_commit = None

    def _get_board(self) -> Any:
        if self._board is None:
            try:
                self._board = self._kicad.get_board()
            except Exception as exc:
                raise ConnectionError(f"No board open in KiCAD: {exc}")
        return self._board

    def begin_transaction(self, description: str = "MCP Operation") -> None:
        board = self._get_board()
        self._current_commit = board.begin_commit()

    def commit_transaction(self, description: str = "MCP Operation") -> None:
        if self._current_commit:
            board = self._get_board()
            board.push_commit(self._current_commit, description)
            self._current_commit = None

    def rollback_transaction(self) -> None:
        if self._current_commit:
            board = self._get_board()
            board.drop_commit(self._current_commit)
            self._current_commit = None

    def save(self) -> bool:
        try:
            self._get_board().save()
            self._notify("save", {})
            return True
        except Exception as exc:
            logger.error(f"Failed to save board: {exc}")
            return False

    def set_size(self, width: float, height: float, unit: str = "mm") -> bool:
        try:
            from kipy.board_types import BoardRectangle
            from kipy.geometry import Vector2
            from kipy.proto.board.board_types_pb2 import BoardLayer
            from kipy.util.units import from_mm

            board = self._get_board()
            w = from_mm(width) if unit == "mm" else int(width * INCH_TO_NM)
            h = from_mm(height) if unit == "mm" else int(height * INCH_TO_NM)

            rect = BoardRectangle()
            rect.start = Vector2.from_xy(0, 0)
            rect.end = Vector2.from_xy(w, h)
            rect.layer = BoardLayer.BL_Edge_Cuts
            rect.width = from_mm(0.1)

            commit = board.begin_commit()
            board.create_items(rect)
            board.push_commit(commit, f"Set board size to {width}x{height} {unit}")
            self._notify("board_size", {"width": width, "height": height, "unit": unit})
            return True
        except Exception as exc:
            logger.error(f"Failed to set board size: {exc}")
            return False

    def get_size(self) -> Dict[str, Any]:
        try:
            from kipy.util.units import to_mm

            board = self._get_board()
            shapes = board.get_shapes()
            if not shapes:
                return {"width": 0, "height": 0, "unit": "mm"}

            min_x = min_y = float("inf")
            max_x = max_y = float("-inf")
            for shape in shapes:
                bbox = board.get_item_bounding_box(shape)
                if bbox:
                    left, top, right, bottom = self._bbox_extents(bbox)
                    min_x = min(min_x, left)
                    min_y = min(min_y, top)
                    max_x = max(max_x, right)
                    max_y = max(max_y, bottom)

            if min_x == float("inf"):
                return {"width": 0, "height": 0, "unit": "mm"}
            return {"width": to_mm(max_x - min_x), "height": to_mm(max_y - min_y), "unit": "mm"}
        except Exception as exc:
            logger.error(f"Failed to get board size: {exc}")
            return {"width": 0, "height": 0, "unit": "mm", "error": str(exc)}

    @staticmethod
    def _bbox_extents(bbox: Any) -> tuple:
        if hasattr(bbox, "min") and hasattr(bbox, "max"):
            return bbox.min.x, bbox.min.y, bbox.max.x, bbox.max.y
        if hasattr(bbox, "pos") and hasattr(bbox, "size"):
            x1, y1 = bbox.pos.x, bbox.pos.y
            x2, y2 = x1 + bbox.size.x, y1 + bbox.size.y
            return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
        raise AttributeError("Unsupported Box2 shape: expected min/max or pos/size")

    def add_layer(self, layer_name: str, layer_type: str) -> bool:
        logger.warning("Layer management via IPC is limited — layers are predefined")
        return False

    def list_components(self) -> List[Dict[str, Any]]:
        try:
            from kipy.util.units import to_mm

            board = self._get_board()
            footprints = board.get_footprints()
            components = []
            for fp in footprints:
                try:
                    pos = fp.position
                    components.append({
                        "reference": fp.reference_field.text.value if fp.reference_field else "",
                        "value": fp.value_field.text.value if fp.value_field else "",
                        "footprint": (
                            str(fp.definition.library_link)
                            if fp.definition and hasattr(fp.definition, "library_link")
                            else ""
                        ),
                        "position": {
                            "x": to_mm(pos.x) if pos else 0,
                            "y": to_mm(pos.y) if pos else 0,
                            "unit": "mm",
                        },
                        "rotation": fp.orientation.degrees if fp.orientation else 0,
                        "layer": str(fp.layer) if hasattr(fp, "layer") else "F.Cu",
                        "id": str(fp.id) if hasattr(fp, "id") else "",
                    })
                except Exception as exc:
                    logger.warning(f"Error processing footprint: {exc}")
            return components
        except Exception as exc:
            logger.error(f"Failed to list components: {exc}")
            return []

    def place_component(
        self,
        reference: str,
        footprint: str,
        x: float,
        y: float,
        rotation: float = 0,
        layer: str = "F.Cu",
        value: str = "",
    ) -> bool:
        try:
            loaded = self._load_footprint_from_library(footprint)
            if loaded:
                return self._place_loaded_footprint(loaded, reference, x, y, rotation, layer, value)
            logger.warning(f"Footprint '{footprint}' not found; creating placeholder")
            return self._place_placeholder_footprint(reference, footprint, x, y, rotation, layer, value)
        except Exception as exc:
            logger.error(f"Failed to place component: {exc}")
            return False

    def _load_footprint_from_library(self, footprint_path: str) -> Any:
        try:
            import pcbnew

            if ":" in footprint_path:
                lib_name, fp_name = footprint_path.split(":", 1)
            else:
                lib_name, fp_name = None, footprint_path

            fp_lib_table = pcbnew.GetGlobalFootprintLib()
            if lib_name:
                try:
                    return pcbnew.FootprintLoad(fp_lib_table, lib_name, fp_name)
                except Exception:
                    pass
            else:
                for lib in fp_lib_table.GetLogicalLibs():
                    try:
                        fp = pcbnew.FootprintLoad(fp_lib_table, lib, fp_name)
                        if fp:
                            return fp
                    except Exception:
                        continue
            return None
        except ImportError:
            return None
        except Exception as exc:
            logger.error(f"Error loading footprint: {exc}")
            return None

    def _place_loaded_footprint(
        self, loaded_fp: Any, reference: str, x: float, y: float,
        rotation: float, layer: str, value: str,
    ) -> bool:
        try:
            import pcbnew

            scale = MM_TO_NM
            loaded_fp.SetPosition(pcbnew.VECTOR2I(int(x * scale), int(y * scale)))
            loaded_fp.SetOrientationDegrees(rotation)
            loaded_fp.SetReference(reference)
            if value:
                loaded_fp.SetValue(value)
            if layer == "B.Cu" and not loaded_fp.IsFlipped():
                loaded_fp.Flip(loaded_fp.GetPosition(), False)

            board_path = self._get_board_file_path()
            if board_path:
                pcb_board = pcbnew.LoadBoard(board_path)
            else:
                pcb_board = pcbnew.GetBoard()

            if not pcb_board:
                return self._place_placeholder_footprint(reference, "", x, y, rotation, layer, value)

            pcb_board.Add(loaded_fp)
            pcbnew.SaveBoard(board_path, pcb_board)
            try:
                self._get_board().revert()
            except Exception:
                pass

            self._notify("component_placed", {
                "reference": reference, "position": {"x": x, "y": y},
                "rotation": rotation, "layer": layer, "loaded_from_library": True,
            })
            return True
        except Exception as exc:
            logger.error(f"Error placing loaded footprint: {exc}")
            return self._place_placeholder_footprint(reference, "", x, y, rotation, layer, value)

    def _get_board_file_path(self) -> Optional[str]:
        try:
            docs = self._kicad.get_open_documents()
            for doc in docs:
                if hasattr(doc, "path") and str(doc.path).endswith(".kicad_pcb"):
                    return str(doc.path)
        except Exception:
            pass
        return None

    def _place_placeholder_footprint(
        self, reference: str, footprint: str, x: float, y: float,
        rotation: float, layer: str, value: str,
    ) -> bool:
        try:
            from kipy.board_types import Footprint
            from kipy.geometry import Angle, Vector2
            from kipy.proto.board.board_types_pb2 import BoardLayer
            from kipy.util.units import from_mm

            board = self._get_board()
            fp = Footprint()
            fp.position = Vector2.from_xy(from_mm(x), from_mm(y))
            fp.orientation = Angle.from_degrees(rotation)
            fp.layer = BoardLayer.BL_B_Cu if layer == "B.Cu" else BoardLayer.BL_F_Cu
            if fp.reference_field:
                fp.reference_field.text.value = reference
            if fp.value_field:
                fp.value_field.text.value = value or footprint

            commit = board.begin_commit()
            board.create_items(fp)
            board.push_commit(commit, f"Placed component {reference}")
            self._notify("component_placed", {
                "reference": reference, "position": {"x": x, "y": y},
                "rotation": rotation, "layer": layer, "is_placeholder": True,
            })
            return True
        except Exception as exc:
            logger.error(f"Failed to place placeholder: {exc}")
            return False

    def add_track(
        self, start_x: float, start_y: float, end_x: float, end_y: float,
        width: float = 0.25, layer: str = "F.Cu", net_name: Optional[str] = None,
    ) -> bool:
        try:
            from kipy.board_types import Track
            from kipy.geometry import Vector2
            from kipy.proto.board.board_types_pb2 import BoardLayer
            from kipy.util.units import from_mm

            LAYER_MAP = {
                "F.Cu": BoardLayer.BL_F_Cu, "B.Cu": BoardLayer.BL_B_Cu,
                "In1.Cu": BoardLayer.BL_In1_Cu, "In2.Cu": BoardLayer.BL_In2_Cu,
            }
            board = self._get_board()
            track = Track()
            track.start = Vector2.from_xy(from_mm(start_x), from_mm(start_y))
            track.end = Vector2.from_xy(from_mm(end_x), from_mm(end_y))
            track.width = from_mm(width)
            track.layer = LAYER_MAP.get(layer, BoardLayer.BL_F_Cu)
            if net_name:
                for net in board.get_nets():
                    if net.name == net_name:
                        track.net = net
                        break
            commit = board.begin_commit()
            board.create_items(track)
            board.push_commit(commit, "Added track")
            self._notify("track_added", {"start": {"x": start_x, "y": start_y},
                                          "end": {"x": end_x, "y": end_y}, "layer": layer})
            return True
        except Exception as exc:
            logger.error(f"Failed to add track: {exc}")
            return False

    def add_via(
        self, x: float, y: float, diameter: float = 0.8, drill: float = 0.4,
        net_name: Optional[str] = None, via_type: str = "through",
    ) -> bool:
        try:
            from kipy.board_types import Via
            from kipy.geometry import Vector2
            from kipy.proto.board.board_types_pb2 import ViaType
            from kipy.util.units import from_mm

            board = self._get_board()
            via = Via()
            via.position = Vector2.from_xy(from_mm(x), from_mm(y))
            via.diameter = from_mm(diameter)
            via.drill_diameter = from_mm(drill)
            via.type = {"through": ViaType.VT_THROUGH, "blind": ViaType.VT_BLIND_BURIED,
                        "micro": ViaType.VT_MICRO}.get(via_type, ViaType.VT_THROUGH)
            if net_name:
                for net in board.get_nets():
                    if net.name == net_name:
                        via.net = net
                        break
            commit = board.begin_commit()
            board.create_items(via)
            board.push_commit(commit, "Added via")
            self._notify("via_added", {"position": {"x": x, "y": y}, "diameter": diameter})
            return True
        except Exception as exc:
            logger.error(f"Failed to add via: {exc}")
            return False

    def get_tracks(self) -> List[Dict[str, Any]]:
        try:
            from kipy.util.units import to_mm

            board = self._get_board()
            return [
                {
                    "start": {"x": to_mm(t.start.x), "y": to_mm(t.start.y)},
                    "end": {"x": to_mm(t.end.x), "y": to_mm(t.end.y)},
                    "width": to_mm(t.width),
                    "layer": str(t.layer),
                    "net": t.net.name if t.net else "",
                }
                for t in board.get_tracks()
            ]
        except Exception as exc:
            logger.error(f"Failed to get tracks: {exc}")
            return []

    def get_vias(self) -> List[Dict[str, Any]]:
        try:
            from kipy.util.units import to_mm

            board = self._get_board()
            return [
                {
                    "position": {"x": to_mm(v.position.x), "y": to_mm(v.position.y)},
                    "diameter": to_mm(v.diameter),
                    "drill": to_mm(v.drill_diameter),
                    "net": v.net.name if v.net else "",
                }
                for v in board.get_vias()
            ]
        except Exception as exc:
            logger.error(f"Failed to get vias: {exc}")
            return []

    def get_nets(self) -> List[Dict[str, Any]]:
        try:
            board = self._get_board()
            return [
                {"name": net.name, "code": getattr(net, "code", 0)}
                for net in board.get_nets()
            ]
        except Exception as exc:
            logger.error(f"Failed to get nets: {exc}")
            return []

    def get_selection(self) -> List[Dict[str, Any]]:
        try:
            board = self._get_board()
            return [
                {"type": type(item).__name__, "id": str(getattr(item, "id", ""))}
                for item in board.get_selection()
            ]
        except Exception as exc:
            logger.error(f"Failed to get selection: {exc}")
            return []


__all__ = ["IPCBackend", "IPCBoardAPI"]
