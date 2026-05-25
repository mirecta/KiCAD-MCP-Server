"""
Abstract base class for KiCAD API backends.

Defines the interface that all KiCAD backends must implement.
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class KiCADBackend(ABC):
    """Abstract base class for KiCAD API backends."""

    @abstractmethod
    def connect(self) -> bool:
        """Connect to KiCAD. Returns True if successful."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from KiCAD and clean up resources."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if currently connected."""
        pass

    @abstractmethod
    def get_version(self) -> str:
        """Return KiCAD version string (e.g. '9.0.0')."""
        pass

    # Project Operations
    @abstractmethod
    def create_project(self, path: Path, name: str) -> Dict[str, Any]:
        """Create a new KiCAD project; return project info dict."""
        pass

    @abstractmethod
    def open_project(self, path: Path) -> Dict[str, Any]:
        """Open an existing .kicad_pro file; return project info dict."""
        pass

    @abstractmethod
    def save_project(self, path: Optional[Path] = None) -> Dict[str, Any]:
        """Save the current project; return status dict."""
        pass

    @abstractmethod
    def close_project(self) -> None:
        """Close the current project."""
        pass

    @abstractmethod
    def get_board(self) -> "BoardAPI":
        """Return a BoardAPI instance for the current project."""
        pass


class BoardAPI(ABC):
    """Abstract interface for board operations."""

    @abstractmethod
    def set_size(self, width: float, height: float, unit: str = "mm") -> bool:
        pass

    @abstractmethod
    def get_size(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def add_layer(self, layer_name: str, layer_type: str) -> bool:
        pass

    @abstractmethod
    def list_components(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
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
        pass

    # Optional operations with default NotImplementedError
    def add_track(
        self,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        width: float = 0.25,
        layer: str = "F.Cu",
        net_name: Optional[str] = None,
    ) -> bool:
        raise NotImplementedError()

    def add_via(
        self,
        x: float,
        y: float,
        diameter: float = 0.8,
        drill: float = 0.4,
        net_name: Optional[str] = None,
        via_type: str = "through",
    ) -> bool:
        raise NotImplementedError()

    def begin_transaction(self, description: str = "MCP Operation") -> None:
        pass

    def commit_transaction(self, description: str = "MCP Operation") -> None:
        pass

    def rollback_transaction(self) -> None:
        pass

    def save(self) -> bool:
        raise NotImplementedError()

    def get_tracks(self) -> List[Dict[str, Any]]:
        raise NotImplementedError()

    def get_vias(self) -> List[Dict[str, Any]]:
        raise NotImplementedError()

    def get_nets(self) -> List[Dict[str, Any]]:
        raise NotImplementedError()

    def get_selection(self) -> List[Dict[str, Any]]:
        raise NotImplementedError()


class BackendError(Exception):
    """Base exception for backend errors."""
    pass


class ConnectionError(BackendError):
    """Raised when connection to KiCAD fails."""
    pass


class APINotAvailableError(BackendError):
    """Raised when required API is not available."""
    pass
