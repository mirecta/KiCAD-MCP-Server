"""
Backend factory — creates the appropriate KiCAD backend.

Priority (auto mode): IPC → SWIG
Environment override: KICAD_BACKEND=ipc|swig|auto
"""

import logging
import os
from typing import Optional

from kicad_mcp.backends.base import APINotAvailableError, KiCADBackend

logger = logging.getLogger(__name__)


def create_backend(backend_type: Optional[str] = None) -> KiCADBackend:
    """
    Create a KiCAD backend.

    Args:
        backend_type: 'ipc', 'swig', or 'auto' (default).
                      Overridden by KICAD_BACKEND env var.
    """
    if backend_type is None:
        backend_type = os.environ.get("KICAD_BACKEND", "auto").lower()

    logger.info(f"Requested backend: {backend_type}")

    if backend_type == "ipc":
        return _create_ipc()
    elif backend_type == "swig":
        return _create_swig()
    elif backend_type == "auto":
        return _auto_detect()
    else:
        raise ValueError(f"Unknown backend type: {backend_type!r}")


def _create_ipc() -> KiCADBackend:
    try:
        from kicad_mcp.backends.ipc_backend import IPCBackend

        return IPCBackend()
    except ImportError as exc:
        raise APINotAvailableError(
            "IPC backend requires 'kipy'. Install with: pip install kipy"
        ) from exc


def _create_swig() -> KiCADBackend:
    try:
        from kicad_mcp.backends.swig_backend import SWIGBackend

        logger.warning(
            "SWIG backend is DEPRECATED and will be removed in KiCAD 10.0. "
            "Please migrate to IPC backend."
        )
        return SWIGBackend()
    except ImportError as exc:
        raise APINotAvailableError(
            "SWIG backend requires pcbnew. "
            "Ensure KiCAD Python module is in PYTHONPATH."
        ) from exc


def _auto_detect() -> KiCADBackend:
    logger.info("Auto-detecting available KiCAD backend...")

    try:
        backend = _create_ipc()
        if backend.connect():
            logger.info("IPC backend available and connected")
            return backend
        logger.warning("IPC backend available but connection failed")
    except (ImportError, APINotAvailableError) as exc:
        logger.debug(f"IPC backend not available: {exc}")

    try:
        backend = _create_swig()
        logger.warning("Falling back to deprecated SWIG backend.")
        return backend
    except (ImportError, APINotAvailableError) as exc:
        logger.error(f"SWIG backend not available: {exc}")

    raise APINotAvailableError(
        "No KiCAD backend available. Install either:\n"
        "  IPC (recommended): pip install kipy\n"
        "  SWIG: ensure pcbnew is in PYTHONPATH"
    )


def get_available_backends() -> dict:
    """Return availability info for each backend."""
    results: dict = {}
    try:
        import kipy

        results["ipc"] = {"available": True, "version": getattr(kipy, "__version__", "unknown")}
    except ImportError:
        results["ipc"] = {"available": False, "version": None}

    try:
        import pcbnew

        results["swig"] = {"available": True, "version": pcbnew.GetBuildVersion()}
    except ImportError:
        results["swig"] = {"available": False, "version": None}

    return results
