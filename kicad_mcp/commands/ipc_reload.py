"""
IPC-triggered schematic reload for KiCAD 9/10.

After writing changes to a .kicad_sch file we can ask the live KiCAD instance
to reload it immediately via the IPC API's RevertDocument command.  This makes
every MCP schematic operation appear live in the KiCAD GUI without the user
having to press File > Revert.

Requirements:
  - KiCAD must be running
  - IPC API server must be enabled:
      KiCAD menu → Preferences → Plugins → Enable IPC API Server
    OR set env var KICAD_ENABLE_SCRIPTING_SERVER=1 before launching KiCAD.

If KiCAD is not running or IPC is unavailable the call silently returns False
and callers carry on — schematic file is still correctly written to disk.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Cache the last successful KiCad IPC client so we don't reconnect on every op.
_kicad_client = None


def _get_kicad() -> Optional[object]:
    """Return a live KiCad IPC client, or None if unavailable."""
    global _kicad_client
    try:
        if _kicad_client is not None:
            _kicad_client.ping()
            return _kicad_client
    except Exception:
        _kicad_client = None

    try:
        from kipy.kicad import KiCad
        client = KiCad()
        client.ping()
        _kicad_client = client
        logger.info("Connected to KiCAD IPC API")
        return client
    except Exception as exc:
        logger.debug(f"KiCAD IPC not available: {exc}")
        return None


def reload_schematic(sch_path: str | Path) -> bool:
    """
    Tell the live KiCAD instance to reload *sch_path* from disk.

    Returns True  — RevertDocument sent, schematic is now live in KiCAD.
    Returns False — KiCAD not running / IPC disabled (file still saved OK).
    """
    kicad = _get_kicad()
    if kicad is None:
        return False

    try:
        from kipy.proto.common.types.base_types_pb2 import DOCTYPE_SCHEMATIC
        from kipy.proto.common.commands.editor_commands_pb2 import RevertDocument
        from google.protobuf.empty_pb2 import Empty

        sch_str = str(Path(sch_path).resolve())

        docs = kicad.get_open_documents(DOCTYPE_SCHEMATIC)
        if not docs:
            logger.debug("No schematics open in KiCAD")
            return False

        for doc in docs:
            doc_path = str(doc.board_filename or "")
            # Match by resolved path or by basename (handles symlinks / relative paths)
            if (doc_path and
                    (str(Path(doc_path).resolve()) == sch_str
                     or Path(doc_path).name == Path(sch_str).name)):
                cmd = RevertDocument()
                cmd.document.CopyFrom(doc)
                kicad._client.send(cmd, Empty)
                logger.info(f"Reloaded {Path(sch_str).name} in KiCAD GUI")
                return True

        # Schematic not open in KiCAD (open in file-manager only, or different project)
        logger.debug(f"Schematic {Path(sch_str).name} not found among open KiCAD docs")
        return False

    except Exception as exc:
        logger.warning(f"IPC reload failed: {exc}")
        _kicad_client = None  # force reconnect next time
        return False


def try_reload(sch_path: str | Path) -> dict:
    """
    Call reload_schematic() and return a small status dict to include
    in MCP tool responses so callers know whether the GUI updated.
    """
    live = reload_schematic(sch_path)
    return {
        "live_reload": live,
        "live_reload_note": (
            "Changes are visible in KiCAD immediately." if live
            else "KiCAD IPC not connected — open KiCAD, enable the API server "
                 "(Preferences → Plugins → Enable IPC API Server), then reopen "
                 "the schematic to see changes live."
        ),
    }
