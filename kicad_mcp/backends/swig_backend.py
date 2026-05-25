"""
SWIG Backend (Legacy — DEPRECATED)

Wraps pcbnew Python bindings.  Deprecated as of KiCAD 9.0; removed in 10.0.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from kicad_mcp.backends.base import (
    APINotAvailableError,
    BoardAPI,
    ConnectionError,
    KiCADBackend,
)

logger = logging.getLogger(__name__)


class SWIGBackend(KiCADBackend):
    """Legacy SWIG-based backend — wraps existing command modules."""

    def __init__(self) -> None:
        self._connected = False
        self._pcbnew = None
        logger.warning(
            "Using DEPRECATED SWIG backend. "
            "Will be removed in KiCAD 10.0. Migrate to IPC."
        )

    def connect(self) -> bool:
        try:
            import pcbnew

            self._pcbnew = pcbnew
            logger.info(f"Connected to pcbnew (SWIG): {pcbnew.GetBuildVersion()}")
            self._connected = True
            return True
        except ImportError as exc:
            raise APINotAvailableError(
                "SWIG backend requires pcbnew module. "
                "Ensure KiCAD Python module is in PYTHONPATH."
            ) from exc

    def disconnect(self) -> None:
        self._connected = False
        self._pcbnew = None

    def is_connected(self) -> bool:
        return self._connected

    def get_version(self) -> str:
        if not self._connected:
            raise ConnectionError("Not connected")
        return self._pcbnew.GetBuildVersion()

    def create_project(self, path: Path, name: str) -> Dict[str, Any]:
        if not self._connected:
            raise ConnectionError("Not connected")
        from kicad_mcp.commands.project import ProjectCommands

        return ProjectCommands.create_project(str(path), name)

    def open_project(self, path: Path) -> Dict[str, Any]:
        if not self._connected:
            raise ConnectionError("Not connected")
        from kicad_mcp.commands.project import ProjectCommands

        return ProjectCommands().open_project({"filename": str(path)})

    def save_project(self, path: Optional[Path] = None) -> Dict[str, Any]:
        if not self._connected:
            raise ConnectionError("Not connected")
        from kicad_mcp.commands.project import ProjectCommands

        params: Dict[str, Any] = {}
        if path:
            params["filename"] = str(path)
        return ProjectCommands().save_project(params)

    def close_project(self) -> None:
        pass  # SWIG backend doesn't maintain project state

    def get_board(self) -> BoardAPI:
        if not self._connected:
            raise ConnectionError("Not connected")
        return SWIGBoardAPI(self._pcbnew)


class SWIGBoardAPI(BoardAPI):
    """Board API wrapping SWIG/pcbnew."""

    def __init__(self, pcbnew_module: Any) -> None:
        self.pcbnew = pcbnew_module
        self._board = None

    def set_size(self, width: float, height: float, unit: str = "mm") -> bool:
        from kicad_mcp.commands.board import BoardCommands

        result = BoardCommands(board=self._board).set_board_size(
            {"width": width, "height": height, "unit": unit}
        )
        return result.get("success", False)

    def get_size(self) -> Dict[str, Any]:
        raise NotImplementedError("get_size not yet implemented for SWIG backend")

    def add_layer(self, layer_name: str, layer_type: str) -> bool:
        from kicad_mcp.commands.board import BoardCommands

        result = BoardCommands.add_layer(layer_name, layer_type)
        return result.get("success", False)

    def list_components(self) -> List[Dict[str, Any]]:
        from kicad_mcp.commands.component import ComponentCommands

        result = ComponentCommands(board=self._board).get_component_list({})
        return result.get("components", []) if result.get("success") else []

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
        from kicad_mcp.commands.component import ComponentCommands

        result = ComponentCommands(board=self._board).place_component({
            "componentId": footprint,
            "position": {"x": x, "y": y, "unit": "mm"},
            "reference": reference,
            "rotation": rotation,
            "layer": layer,
        })
        return result.get("success", False)
