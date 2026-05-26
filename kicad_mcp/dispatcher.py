"""
KiCAD command dispatcher — mirrors KiCADInterface from the original kicad_interface.py.

Creates all command-handler objects and routes tool calls to them.
Unlike the original (which is a stdin/stdout JSON-RPC loop), this class
is used directly by the MCP tool handlers in server.py.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class KiCADDispatcher:
    """
    Central dispatcher that owns all command objects and routes tool calls.

    Usage:
        d = KiCADDispatcher()
        result = d.dispatch("create_project", {"name": "foo", "path": "/tmp"})
    """

    def __init__(self) -> None:
        self._board: Optional[Any] = None  # pcbnew.BOARD when loaded
        self._sch_manager: Optional[Any] = None  # SchematicManager
        self._sch_path: Optional[str] = None

        # Lazy-import pcbnew (may not be available without SWIG)
        try:
            import pcbnew as _pcbnew
            self._pcbnew = _pcbnew
        except ImportError:
            self._pcbnew = None
            logger.warning("pcbnew not available — SWIG-backed tools will fail gracefully")

        self._init_commands()
        self._build_routes()

    # ------------------------------------------------------------------
    # Command object initialisation
    # ------------------------------------------------------------------

    def _init_commands(self) -> None:
        from kicad_mcp.commands.board import BoardCommands
        from kicad_mcp.commands.component import ComponentCommands
        from kicad_mcp.commands.datasheet_manager import DatasheetManager
        from kicad_mcp.commands.design_rules import DesignRuleCommands
        from kicad_mcp.commands.export import ExportCommands
        from kicad_mcp.commands.footprint import FootprintCreator
        from kicad_mcp.commands.freerouting import FreeroutingCommands
        from kicad_mcp.commands.jlcpcb import JLCPCBClient
        from kicad_mcp.commands.jlcpcb_parts import JLCPCBPartsManager
        from kicad_mcp.commands.library import LibraryCommands, LibraryManager
        from kicad_mcp.commands.library_symbol import SymbolLibraryCommands
        from kicad_mcp.commands.project import ProjectCommands
        from kicad_mcp.commands.routing import RoutingCommands
        from kicad_mcp.commands.schematic import SchematicManager
        from kicad_mcp.commands.symbol_creator import SymbolCreator

        self.project_commands = ProjectCommands(board=self._board)
        self.board_commands = BoardCommands(board=self._board)
        self.component_commands = ComponentCommands(board=self._board)
        self.routing_commands = RoutingCommands(board=self._board)
        self.export_commands = ExportCommands(board=self._board)
        self.design_rule_commands = DesignRuleCommands(board=self._board)
        self.library_manager = LibraryManager()
        self.library_commands = LibraryCommands(library_manager=self.library_manager)
        self.symbol_library_commands = SymbolLibraryCommands()
        self.freerouting_commands = FreeroutingCommands(board=self._board)
        self.footprint_creator = FootprintCreator()
        self.symbol_creator = SymbolCreator()
        self.jlcpcb_client = JLCPCBClient()
        self.jlcpcb_parts_manager = JLCPCBPartsManager()
        self.datasheet_manager = DatasheetManager()
        self.schematic_manager = SchematicManager

    # ------------------------------------------------------------------
    # Board propagation
    # ------------------------------------------------------------------

    def _set_board(self, board: Any) -> None:
        """Propagate a newly loaded board to all command objects."""
        self._board = board
        for attr in ("project_commands", "board_commands", "component_commands",
                     "routing_commands", "export_commands", "design_rule_commands",
                     "freerouting_commands"):
            obj = getattr(self, attr, None)
            if obj is not None:
                obj.board = board
                # Propagate into sub-commands if they exist
                for sub in ("size_commands", "layer_commands", "outline_commands",
                            "view_commands"):
                    sub_obj = getattr(obj, sub, None)
                    if sub_obj is not None:
                        sub_obj.board = board

    # ------------------------------------------------------------------
    # Schematic state
    # ------------------------------------------------------------------

    def _get_schematic(self, path: Optional[str] = None):
        """Return cached SchematicManager instance or load from path."""
        target = path or self._sch_path
        if target and target != self._sch_path:
            self._sch_manager = None
            self._sch_path = target
        if self._sch_manager is None and self._sch_path:
            try:
                from skip import Schematic
                self._sch_manager = Schematic(self._sch_path)
            except Exception as exc:
                logger.error(f"Failed to load schematic {self._sch_path}: {exc}")
        return self._sch_manager

    # ------------------------------------------------------------------
    # Route table
    # ------------------------------------------------------------------

    def _build_routes(self) -> None:
        self._routes: Dict[str, Any] = {
            # Project
            "create_project":           self._handle_create_project,
            "open_project":             self._handle_open_project,
            "save_project":             self.project_commands.save_project,
            "get_project_info":         self.project_commands.get_project_info,
            "snapshot_project":         self._handle_snapshot_project,
            "close_project":            self._handle_close_project,
            # Board
            "set_board_size":           self.board_commands.set_board_size,
            "add_layer":                self.board_commands.add_layer,
            "set_active_layer":         self.board_commands.set_active_layer,
            "get_board_info":           self.board_commands.get_board_info,
            "get_layer_list":           self.board_commands.get_layer_list,
            "get_board_2d_view":        self.board_commands.get_board_2d_view,
            "get_board_extents":        self.board_commands.get_board_extents,
            "add_board_outline":        self.board_commands.add_board_outline,
            "add_mounting_hole":        self.board_commands.add_mounting_hole,
            "add_board_text":           self.board_commands.add_text,
            "add_text":                 self.board_commands.add_text,
            "import_svg_logo":          self._handle_import_svg_logo,
            # Component
            "place_component":          self._handle_place_component,
            "move_component":           self.component_commands.move_component,
            "rotate_component":         self.component_commands.rotate_component,
            "delete_component":         self.component_commands.delete_component,
            "edit_component":           self.component_commands.edit_component,
            "get_component_properties": self.component_commands.get_component_properties,
            "get_component_list":       self.component_commands.get_component_list,
            "list_components":          self.component_commands.get_component_list,
            "find_component":           self.component_commands.find_component,
            "get_component_pads":       self.component_commands.get_component_pads,
            "get_pad_position":         self.component_commands.get_pad_position,
            "place_component_array":    self.component_commands.place_component_array,
            "align_components":         self.component_commands.align_components,
            "check_courtyard_overlaps": self.component_commands.check_courtyard_overlaps,
            "duplicate_component":      self.component_commands.duplicate_component,
            "add_component_annotation": self._handle_add_component_annotation,
            "group_components":         self._handle_group_components,
            "replace_component":        self._handle_replace_component,
            "add_component":            self._handle_place_component,
            # Routing
            "add_net":                  self.routing_commands.add_net,
            "route_trace":              self.routing_commands.route_trace,
            "add_trace":                self.routing_commands.route_trace,
            "route_arc_trace":          self.routing_commands.route_arc_trace,
            "add_via":                  self.routing_commands.add_via,
            "delete_trace":             self.routing_commands.delete_trace,
            "query_traces":             self.routing_commands.query_traces,
            "query_zones":              self.routing_commands.query_zones,
            "add_gnd_stitching_vias":   self.routing_commands.add_gnd_stitching_vias,
            "modify_trace":             self.routing_commands.modify_trace,
            "copy_routing_pattern":     self.routing_commands.copy_routing_pattern,
            "get_nets_list":            self.routing_commands.get_nets_list,
            "create_netclass":          self.routing_commands.create_netclass,
            "add_copper_pour":          self.routing_commands.add_copper_pour,
            "add_zone":                 self.routing_commands.add_copper_pour,
            "route_differential_pair":  self.routing_commands.route_differential_pair,
            "refill_zones":             self._handle_refill_zones,
            "route_pad_to_pad":         self.routing_commands.route_pad_to_pad,
            # Design rules / DRC
            "set_design_rules":         self.design_rule_commands.set_design_rules,
            "get_design_rules":         self.design_rule_commands.get_design_rules,
            "run_drc":                  self.design_rule_commands.run_drc,
            "get_drc_results":          self.design_rule_commands.get_drc_violations,
            "get_drc_violations":       self.design_rule_commands.get_drc_violations,
            "clear_drc_results":        self._handle_clear_drc_results,
            "add_net_class":            self.routing_commands.create_netclass,
            "assign_net_to_class":      self._handle_assign_net_to_class,
            "check_clearance":          self._handle_check_clearance,
            "set_layer_constraints":    self._handle_set_layer_constraints,
            # Export
            "export_gerber":            self.export_commands.export_gerber,
            "export_drill":             self._handle_export_drill,
            "export_pdf":               self.export_commands.export_pdf,
            "export_dxf":               self._handle_export_dxf,
            "export_svg":               self.export_commands.export_svg,
            "export_3d":                self.export_commands.export_3d,
            "export_step":              self.export_commands.export_3d,
            "export_bom":               self.export_commands.export_bom,
            "export_netlist":           self._handle_export_netlist,
            "generate_netlist":         self._handle_export_netlist,
            "export_position_file":     self._handle_export_position_file,
            "export_vrml":              self._handle_export_vrml,
            # Library (footprint)
            "list_libraries":           self.library_commands.list_libraries,
            "search_footprints":        self.library_commands.search_footprints,
            "list_library_footprints":  self.library_commands.list_library_footprints,
            "get_footprint_info":       self.library_commands.get_footprint_info,
            # Symbol library
            "list_symbol_libraries":    self.symbol_library_commands.list_symbol_libraries,
            "search_symbols":           self.symbol_library_commands.search_symbols,
            "list_library_symbols":     self.symbol_library_commands.list_library_symbols,
            "list_symbols_in_library":  self.symbol_library_commands.list_library_symbols,
            "get_symbol_info":          self.symbol_library_commands.get_symbol_info,
            # Footprint creator
            "create_footprint":         self._handle_create_footprint,
            "edit_footprint_pad":       self._handle_edit_footprint_pad,
            "list_footprint_libraries": self._handle_list_footprint_libraries,
            "register_footprint_library": self._handle_register_footprint_library,
            # Symbol creator
            "create_symbol":            self._handle_create_symbol,
            "delete_symbol":            self._handle_delete_symbol,
            "register_symbol_library":  self._handle_register_symbol_library,
            # JLCPCB
            "download_jlcpcb_database":    self._handle_download_jlcpcb_database,
            "search_jlcpcb_parts":         self._handle_search_jlcpcb_parts,
            "get_jlcpcb_part":             self._handle_get_jlcpcb_part,
            "get_jlcpcb_database_stats":   self._handle_get_jlcpcb_database_stats,
            "suggest_jlcpcb_alternatives": self._handle_suggest_jlcpcb_alternatives,
            # Datasheets
            "enrich_datasheets":        self._handle_enrich_datasheets,
            "get_datasheet_url":        self._handle_get_datasheet_url,
            # Freerouting
            "autoroute":                self.freerouting_commands.autoroute,
            "export_dsn":               self.freerouting_commands.export_dsn,
            "import_ses":               self.freerouting_commands.import_ses,
            "check_freerouting":        self.freerouting_commands.check_freerouting,
            # Schematic
            "create_schematic":         self._handle_create_schematic,
            "open_schematic":           self._handle_open_schematic,
            "save_schematic":           self._handle_save_schematic,
            "add_schematic_component":  self._handle_add_schematic_component,
            "delete_schematic_component": self._handle_delete_schematic_component,
            "edit_schematic_component": self._handle_edit_schematic_component,
            "set_schematic_component_property": self._handle_set_schematic_component_property,
            "remove_schematic_component_property": self._handle_remove_schematic_component_property,
            "get_schematic_component":  self._handle_get_schematic_component,
            "add_schematic_wire":       self._handle_add_schematic_wire,
            "add_schematic_net_label":  self._handle_add_schematic_net_label,
            "add_no_connect":           self._handle_add_no_connect,
            "add_schematic_hierarchical_label": self._handle_add_schematic_hierarchical_label,
            "add_schematic_text":       self._handle_add_schematic_text,
            "add_sheet_pin":            self._handle_add_sheet_pin,
            "add_schematic_bus":        self._handle_add_schematic_bus,
            "add_schematic_junction":   self._handle_add_schematic_junction,
            "add_schematic_power_symbol": self._handle_add_schematic_power_symbol,
            "annotate_schematic":       self._handle_annotate_schematic,
            "move_schematic_component": self._handle_move_schematic_component,
            "rotate_schematic_component": self._handle_rotate_schematic_component,
            "delete_schematic_wire":    self._handle_delete_schematic_wire,
            "delete_schematic_net_label": self._handle_delete_schematic_net_label,
            "move_schematic_net_label": self._handle_move_schematic_net_label,
            "list_schematic_components": self._handle_list_schematic_components,
            "list_schematic_nets":      self._handle_list_schematic_nets,
            "list_schematic_wires":     self._handle_list_schematic_wires,
            "list_schematic_labels":    self._handle_list_schematic_labels,
            "list_schematic_texts":     self._handle_list_schematic_texts,
            "get_schematic_view":       self._handle_get_schematic_view,
            "export_schematic_pdf":     self._handle_export_schematic_pdf,
            "export_schematic_svg":     self._handle_export_schematic_svg,
            "export_netlist":           self._handle_export_netlist,
            "run_erc":                  self._handle_run_erc,
            "sync_schematic_to_board":  self._handle_sync_schematic_to_board,
            # Schematic connectivity helpers
            "connect_to_net":           self._handle_connect_to_net,
            "connect_passthrough":      self._handle_connect_passthrough,
            "get_schematic_pin_locations": self._handle_get_schematic_pin_locations,
            "get_net_connections":      self._handle_get_net_connections,
            "get_wire_connections":     self._handle_get_wire_connections,
            "get_net_at_point":         self._handle_get_net_at_point,
            # Schematic analysis
            "get_schematic_view_region":    self._handle_get_schematic_view_region,
            "find_overlapping_elements":    self._handle_find_overlapping_elements,
            "get_elements_in_region":       self._handle_get_elements_in_region,
            "find_wires_crossing_symbols":  self._handle_find_wires_crossing_symbols,
            "find_orphaned_wires":          self._handle_find_orphaned_wires,
            "list_floating_labels":         self._handle_list_floating_labels,
            "snap_to_grid":                 self._handle_snap_to_grid,
            # UI
            "check_kicad_ui":           self._handle_check_kicad_ui,
            "launch_kicad_ui":          self._handle_launch_kicad_ui,
        }

    # ------------------------------------------------------------------
    # Dispatch entry point
    # ------------------------------------------------------------------

    def dispatch(self, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
        handler = self._routes.get(command)
        if handler is None:
            return {"success": False, "error": f"Unknown command: {command!r}"}
        try:
            return handler(params)
        except Exception as exc:
            logger.exception(f"Error in command {command!r}")
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Project handlers
    # ------------------------------------------------------------------

    def _handle_create_project(self, params: Dict) -> Dict:
        result = self.project_commands.create_project(params)
        if result.get("success"):
            proj = result.get("project", {})
            sch_path = proj.get("schematicPath")
            if sch_path:
                self._sch_path = sch_path
                self._sch_manager = None  # force reload on next use
            board_path = proj.get("boardPath")
            if board_path and self._pcbnew:
                try:
                    board = self._pcbnew.LoadBoard(board_path)
                    self._set_board(board)
                except Exception as exc:
                    logger.warning(f"Could not load created board: {exc}")
        return result

    def _handle_open_project(self, params: Dict) -> Dict:
        result = self.project_commands.open_project(params)
        if result.get("success"):
            proj = result.get("project", {})
            # Derive schematic path: project may return it, otherwise infer from .kicad_pro
            sch_path = proj.get("schematicPath")
            if not sch_path:
                proj_file = proj.get("path") or params.get("filename") or ""
                if proj_file.endswith(".kicad_pro"):
                    candidate = proj_file[: -len(".kicad_pro")] + ".kicad_sch"
                    if os.path.exists(candidate):
                        sch_path = candidate
            if sch_path:
                self._sch_path = sch_path
                self._sch_manager = None
            board_path = proj.get("boardPath") or params.get("filename")
            if board_path and self._pcbnew:
                try:
                    board = self._pcbnew.LoadBoard(board_path)
                    self._set_board(board)
                except Exception as exc:
                    logger.warning(f"Could not load opened board: {exc}")
        return result

    def _handle_close_project(self, params: Dict) -> Dict:
        self._set_board(None)
        return {"success": True, "message": "Project closed"}

    def _handle_snapshot_project(self, params: Dict) -> Dict:
        return {"success": False, "error": "snapshot_project not yet implemented"}

    # ------------------------------------------------------------------
    # Board handlers
    # ------------------------------------------------------------------

    def _handle_refill_zones(self, params: Dict) -> Dict:
        if not self._board:
            return {"success": False, "error": "No board loaded"}
        try:
            filler = self._pcbnew.ZONE_FILLER(self._board)
            filler.Fill(self._board.Zones())
            self._pcbnew.SaveBoard(self._board.GetFileName(), self._board)
            return {"success": True, "message": "Zones refilled"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_import_svg_logo(self, params: Dict) -> Dict:
        try:
            from kicad_mcp.commands.svg_import import SVGImporter
            importer = SVGImporter()
            return importer.import_svg(params)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Component handlers
    # ------------------------------------------------------------------

    def _handle_place_component(self, params: Dict) -> Dict:
        return self.component_commands.place_component(params)

    def _handle_add_component_annotation(self, params: Dict) -> Dict:
        return {"success": False, "error": "add_component_annotation not yet implemented"}

    def _handle_group_components(self, params: Dict) -> Dict:
        return {"success": False, "error": "group_components not yet implemented"}

    def _handle_replace_component(self, params: Dict) -> Dict:
        return {"success": False, "error": "replace_component not yet implemented"}

    # ------------------------------------------------------------------
    # DRC / design rule helpers
    # ------------------------------------------------------------------

    def _handle_clear_drc_results(self, params: Dict) -> Dict:
        if not self._board:
            return {"success": False, "error": "No board loaded"}
        try:
            self._board.GetDesignSettings().m_DrcExclusions.clear()
            return {"success": True, "message": "DRC results cleared"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_assign_net_to_class(self, params: Dict) -> Dict:
        return {"success": False, "error": "assign_net_to_class not yet implemented"}

    def _handle_check_clearance(self, params: Dict) -> Dict:
        return {"success": False, "error": "check_clearance not yet implemented"}

    def _handle_set_layer_constraints(self, params: Dict) -> Dict:
        return {"success": False, "error": "set_layer_constraints not yet implemented"}

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------

    def _handle_export_drill(self, params: Dict) -> Dict:
        return {"success": False, "error": "export_drill not yet implemented"}

    def _handle_export_dxf(self, params: Dict) -> Dict:
        return {"success": False, "error": "export_dxf not yet implemented"}

    def _handle_export_netlist(self, params: Dict) -> Dict:
        sch = self._get_schematic()
        if sch is None:
            return {"success": False, "error": "No schematic loaded"}
        try:
            from kicad_mcp.commands.schematic import SchematicManager
            return SchematicManager.generate_netlist(sch, params)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_export_position_file(self, params: Dict) -> Dict:
        return {"success": False, "error": "export_position_file not yet implemented"}

    def _handle_export_vrml(self, params: Dict) -> Dict:
        return {"success": False, "error": "export_vrml not yet implemented"}

    # ------------------------------------------------------------------
    # Footprint / symbol creator
    # ------------------------------------------------------------------

    def _handle_create_footprint(self, params: Dict) -> Dict:
        try:
            return self.footprint_creator.create_footprint(params)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_edit_footprint_pad(self, params: Dict) -> Dict:
        try:
            return self.footprint_creator.edit_pad(params)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_list_footprint_libraries(self, params: Dict) -> Dict:
        return self.library_commands.list_libraries(params)

    def _handle_register_footprint_library(self, params: Dict) -> Dict:
        return {"success": False, "error": "register_footprint_library not yet implemented"}

    def _handle_create_symbol(self, params: Dict) -> Dict:
        try:
            return self.symbol_creator.create_symbol(params)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_delete_symbol(self, params: Dict) -> Dict:
        try:
            return self.symbol_creator.delete_symbol(params)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_register_symbol_library(self, params: Dict) -> Dict:
        return {"success": False, "error": "register_symbol_library not yet implemented"}

    # ------------------------------------------------------------------
    # JLCPCB handlers
    # ------------------------------------------------------------------

    def _handle_download_jlcpcb_database(self, params: Dict) -> Dict:
        try:
            output_path = params.get("outputPath")
            force = bool(params.get("force", False))
            source = (params.get("source") or "jlcsearch").lower()
            if output_path:
                from kicad_mcp.commands.jlcpcb_parts import JLCPCBPartsManager
                self.jlcpcb_parts_manager = JLCPCBPartsManager(db_path=output_path)
            if not force:
                existing = self.jlcpcb_parts_manager.get_database_stats()
                if existing.get("total_parts", 0) > 0:
                    return {"success": True,
                            "message": "Database already populated; pass force=true to re-download",
                            "stats": existing}

            if source == "official":
                parts = self.jlcpcb_client.download_full_database()
                self.jlcpcb_parts_manager.import_parts(parts)
                imported = len(parts)
            elif source == "jlcsearch":
                from kicad_mcp.commands.jlcsearch import JLCSearchClient
                client = JLCSearchClient()
                parts = client.download_all_components()
                self.jlcpcb_parts_manager.import_jlcsearch_parts(parts)
                imported = len(parts)
            elif source == "sqlite":
                from kicad_mcp.commands.sqlite_loader import SqliteBulkLoader
                loader = SqliteBulkLoader(self.jlcpcb_parts_manager)
                result = loader.download_and_import(
                    url=params.get("sqliteUrl"),
                    table=params.get("sqliteTable"),
                    keep_file_at=params.get("keepSqliteAt"),
                )
                if not result.get("success"):
                    return result
                imported = result.get("imported_rows", 0)
            else:
                return {"success": False,
                        "error": f"Unknown source '{source}'. Use 'jlcsearch', 'sqlite', or 'official'."}

            return {"success": True, "source": source,
                    "message": f"Imported {imported} parts via {source}",
                    "stats": self.jlcpcb_parts_manager.get_database_stats()}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_search_jlcpcb_parts(self, params: Dict) -> Dict:
        try:
            parts = self.jlcpcb_parts_manager.search_parts(
                query=params.get("query"),
                category=params.get("category"),
                package=params.get("package"),
                library_type="Basic" if params.get("basic") else params.get("libraryType"),
                manufacturer=params.get("manufacturer"),
                in_stock=bool(params.get("inStock", True)),
                limit=int(params.get("limit", 20)),
            )
            return {"success": True, "parts": parts, "count": len(parts)}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_get_jlcpcb_part(self, params: Dict) -> Dict:
        try:
            part_number = params.get("partNumber") or params.get("lcsc")
            if not part_number:
                return {"success": False, "error": "partNumber required"}
            part = self.jlcpcb_parts_manager.get_part_info(part_number)
            if part is None:
                return {"success": False, "error": f"Part not found: {part_number}"}
            return {"success": True, "part": part}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_get_jlcpcb_database_stats(self, params: Dict) -> Dict:
        try:
            return {"success": True, "stats": self.jlcpcb_parts_manager.get_database_stats()}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_suggest_jlcpcb_alternatives(self, params: Dict) -> Dict:
        try:
            reference = params.get("reference") or params.get("partNumber")
            if not reference:
                return {"success": False, "error": "reference required"}
            limit = int(params.get("limit", 5))
            alternatives = self.jlcpcb_parts_manager.suggest_alternatives(reference, limit=limit)
            return {"success": True, "alternatives": alternatives, "count": len(alternatives)}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Datasheet handlers
    # ------------------------------------------------------------------

    def _handle_enrich_datasheets(self, params: Dict) -> Dict:
        try:
            return self.datasheet_manager.enrich_datasheets(params)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_get_datasheet_url(self, params: Dict) -> Dict:
        try:
            return self.datasheet_manager.get_datasheet_url(params)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Schematic handlers (all via SchematicManager / WireManager)
    # ------------------------------------------------------------------

    def _sch_path_from_params(self, params: Dict) -> Optional[str]:
        return (params.get("schematicPath") or params.get("filename")
                or params.get("path") or self._sch_path)

    def _handle_create_schematic(self, params: Dict) -> Dict:
        try:
            from kicad_mcp.commands.schematic import SchematicManager
            # MCP schema uses `filename` (full path). Original code used `name`+`path`.
            filename = params.get("filename")
            if filename:
                filename = os.path.abspath(os.path.expanduser(filename))
                target_dir = os.path.dirname(filename) or "."
                name = os.path.splitext(os.path.basename(filename))[0]
            else:
                name = params.get("name", "schematic")
                target_dir = params.get("path", ".")
            os.makedirs(target_dir, exist_ok=True)
            sch = SchematicManager.create_schematic(name, path=target_dir)
            actual_path = os.path.join(target_dir, f"{name}.kicad_sch")
            self._sch_path = actual_path
            self._sch_manager = sch
            return {"success": True, "message": f"Created schematic: {actual_path}",
                    "schematicPath": actual_path}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_open_schematic(self, params: Dict) -> Dict:
        path = self._sch_path_from_params(params)
        if not path:
            return {"success": False, "error": "schematicPath required"}
        try:
            from skip import Schematic
            self._sch_manager = Schematic(path)
            self._sch_path = path
            return {"success": True, "message": f"Opened: {path}", "schematicPath": path}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_save_schematic(self, params: Dict) -> Dict:
        sch = self._get_schematic(self._sch_path_from_params(params))
        if sch is None:
            return {"success": False, "error": "No schematic loaded"}
        try:
            sch.write(self._sch_path)
            from kicad_mcp.commands.ipc_reload import try_reload
            result = {"success": True, "message": f"Saved: {self._sch_path}"}
            result.update(try_reload(self._sch_path))
            return result
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _sch_delegate(self, method_chain: list, params: Dict) -> Dict:
        """Stub for schematic ops not yet routed to a specific manager.

        The previous implementation hardcoded ``WireManager(path)`` which
        fails because (a) ``WireManager`` has no ``__init__`` accepting a
        path, and (b) operations like ``add_component`` / ``add_net_label``
        live on ``ComponentManager`` / ``ConnectionManager`` respectively.
        Concrete handlers below now call their managers directly.
        """
        op = method_chain[0] if method_chain else "<unknown>"
        return {"success": False,
                "error": f"Schematic op {op!r} is not yet routed in dispatcher"}

    def _resolve_sch_path(self, params: Dict) -> Optional[Path]:
        """Resolve schematic path from params or cached state, as a Path."""
        p = self._sch_path_from_params(params)
        return Path(p) if p else None

    def _resolve_project_dir(self, sch_file: Path) -> Path:
        """Walk up from a .kicad_sch to find the directory owning the project."""
        proj_dir = sch_file.parent
        for ancestor in [sch_file.parent, *sch_file.parents]:
            if (ancestor / "sym-lib-table").exists() or any(ancestor.glob("*.kicad_pro")):
                return ancestor
        return proj_dir

    # ---- Component ---------------------------------------------------

    def _handle_add_schematic_component(self, params: Dict) -> Dict:
        sch_file = self._resolve_sch_path(params)
        if not sch_file:
            return {"success": False,
                    "error": "No schematic loaded. Call create_project / open_project / create_schematic first."}
        symbol = params.get("symbol", "")
        if ":" not in symbol:
            return {"success": False,
                    "error": f"symbol must be 'Library:Name', got {symbol!r}"}
        library, sym_name = symbol.split(":", 1)
        reference = params.get("reference", "X?")
        value = params.get("value") or sym_name
        footprint = params.get("footprint", "")
        try:
            x = float(params.get("x", 0))
            y = float(params.get("y", 0))
            unit = int(params.get("unit", 1))
        except (TypeError, ValueError) as exc:
            return {"success": False, "error": f"invalid numeric arg: {exc}"}
        try:
            angle = float(params.get("orientation") or params.get("angle") or 0)
        except (TypeError, ValueError):
            angle = 0.0
        try:
            from kicad_mcp.commands.dynamic_symbol_loader import DynamicSymbolLoader
            from kicad_mcp.commands.ipc_reload import try_reload
            proj_dir = self._resolve_project_dir(sch_file)
            loader = DynamicSymbolLoader(project_path=proj_dir)
            ok = loader.add_component(
                sch_file, library, sym_name,
                reference=reference, value=value, footprint=footprint,
                x=x, y=y, unit=unit, project_path=proj_dir, angle=angle,
            )
            if not ok:
                return {"success": False,
                        "error": "DynamicSymbolLoader.add_component returned False"}
            result = {
                "success": True,
                "reference": reference,
                "symbol": symbol,
                "value": value,
                "position": [x, y],
                "schematic": str(sch_file),
            }
            result.update(try_reload(sch_file))
            return result
        except Exception as exc:
            logger.exception("add_schematic_component failed")
            return {"success": False, "error": str(exc)}

    def _handle_delete_schematic_component(self, params: Dict) -> Dict:
        sch_file = self._resolve_sch_path(params)
        if not sch_file:
            return {"success": False, "error": "No schematic loaded"}
        reference = params.get("reference")
        if not reference:
            return {"success": False, "error": "reference required"}
        try:
            import sexpdata
            from sexpdata import Symbol
            content = sch_file.read_text(encoding="utf-8")
            sch_data = sexpdata.loads(content)
            _SYM = Symbol("symbol")
            _PROP = Symbol("property")
            _REF_KEY = "Reference"
            removed = 0
            new_data = [sch_data[0]]  # preserve top-level symbol name
            for item in sch_data[1:]:
                if isinstance(item, list) and item and item[0] == _SYM:
                    # Check if this symbol has a Reference property matching
                    for sub in item[1:]:
                        if (isinstance(sub, list) and len(sub) >= 3
                                and sub[0] == _PROP
                                and str(sub[1]).strip('"') == _REF_KEY
                                and str(sub[2]).strip('"').rstrip("_") == reference):
                            removed += 1
                            break
                    else:
                        new_data.append(item)
                        continue
                    continue  # skip this symbol
                new_data.append(item)
            if removed == 0:
                return {"success": False, "error": f"Component {reference} not found"}
            sch_file.write_text(sexpdata.dumps(new_data), encoding="utf-8")
            from kicad_mcp.commands.ipc_reload import try_reload
            result = {"success": True, "reference": reference, "removed": removed}
            result.update(try_reload(sch_file))
            return result
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_edit_schematic_component(self, params: Dict) -> Dict:
        return self._sch_delegate(["edit_component"], params)

    def _handle_set_schematic_component_property(self, params: Dict) -> Dict:
        return self._sch_delegate(["set_component_property"], params)

    def _handle_remove_schematic_component_property(self, params: Dict) -> Dict:
        return self._sch_delegate(["remove_component_property"], params)

    def _handle_get_schematic_component(self, params: Dict) -> Dict:
        return self._sch_delegate(["get_component"], params)

    # ---- Wires / labels / no-connect / text --------------------------

    def _handle_add_schematic_wire(self, params: Dict) -> Dict:
        sch_file = self._resolve_sch_path(params)
        if not sch_file:
            return {"success": False, "error": "No schematic loaded."}

        from_ref = params.get("fromRef")
        from_pin = params.get("fromPin")
        to_ref = params.get("toRef")
        to_pin = params.get("toPin")
        via_points = params.get("via") or []  # optional intermediate waypoints

        if from_ref and from_pin is not None and to_ref and to_pin is not None:
            # Reference-based mode: resolve pin coordinates automatically
            try:
                from kicad_mcp.commands.pin_locator import PinLocator
                locator = PinLocator()
                start = locator.get_pin_location(sch_file, from_ref, str(from_pin))
                if start is None:
                    return {"success": False,
                            "error": f"Pin {from_ref}/{from_pin} not found in schematic"}
                end = locator.get_pin_location(sch_file, to_ref, str(to_pin))
                if end is None:
                    return {"success": False,
                            "error": f"Pin {to_ref}/{to_pin} not found in schematic"}
            except Exception as exc:
                logger.exception("pin lookup failed in add_schematic_wire")
                return {"success": False, "error": f"pin lookup failed: {exc}"}

            try:
                via_pts = [[float(p[0]), float(p[1])] for p in via_points]
            except (TypeError, ValueError, IndexError) as exc:
                return {"success": False, "error": f"invalid via waypoints: {exc}"}

            # Resolve pin angles for direction-aware routing (only when no manual vias)
            from_angle = None
            to_angle = None
            if not via_pts:
                try:
                    from_angle = locator.get_pin_angle(sch_file, from_ref, str(from_pin))
                    to_angle = locator.get_pin_angle(sch_file, to_ref, str(to_pin))
                except Exception:
                    pass

            resolved_pins = {
                "from": {"ref": from_ref, "pin": str(from_pin), "position": start},
                "to":   {"ref": to_ref,   "pin": str(to_pin),   "position": end},
            }
        else:
            # Coordinate-based mode (original API)
            waypoints = params.get("waypoints") or []
            if len(waypoints) < 2:
                return {"success": False,
                        "error": "Provide either fromRef/fromPin/toRef/toPin, "
                                 "or waypoints with at least 2 [x,y] points"}
            try:
                pts = [[float(p[0]), float(p[1])] for p in waypoints]
            except (TypeError, ValueError, IndexError) as exc:
                return {"success": False, "error": f"invalid waypoints: {exc}"}
            resolved_pins = None
            via_pts = None  # signals: already have pts, skip smart routing

        def _manhattan(pts):
            """Ensure all segments in pts are axis-aligned, inserting corners where needed."""
            out = [pts[0]]
            for a, b in zip(pts, pts[1:]):
                if abs(a[0] - b[0]) > 1e-6 and abs(a[1] - b[1]) > 1e-6:
                    # vertical-first: go to destination y first, then x
                    out.append([a[0], b[1]])
                out.append(b)
            return out

        _STUB = 5.08  # escape/approach stub in mm (2 KiCAD grid squares)

        def _angle_dir(angle):
            """Unit (dx,dy) exit vector. KiCAD: y increases downward on screen."""
            if angle is None:
                return (0, 0)
            a = angle % 360
            if abs(a) < 1:        return (1,  0)   # RIGHT
            if abs(a - 90) < 1:   return (0, -1)   # UP   (y decreases)
            if abs(a - 180) < 1:  return (-1, 0)   # LEFT
            if abs(a - 270) < 1:  return (0,  1)   # DOWN (y increases)
            return (0, 0)

        def _route_pins(p1, p2, fa, ta):
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

            fd = _angle_dir(fa)
            td = _angle_dir(ta)

            # --- Try simple L-bend (no extra stubs) ---
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

            # --- Escape + approach: emit stub in each pin's exit direction ---
            esc = [x1 + fd[0] * _STUB, y1 + fd[1] * _STUB] if fd != (0, 0) else [x1, y1]
            app = [x2 + td[0] * _STUB, y2 + td[1] * _STUB] if td != (0, 0) else [x2, y2]

            ex, ey = esc[0], esc[1]
            ax, ay = app[0], app[1]

            inner = []
            if abs(ex - ax) > 1e-4 and abs(ey - ay) > 1e-4:
                # Corner direction: match the escape axis so the first turn
                # moves perpendicular to the escape stub, avoiding the source component.
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

        if via_pts is None:
            # Coordinate mode — pts already set, just enforce Manhattan
            pts = _manhattan(pts)
        elif via_pts:
            # Ref mode with manual waypoints — enforce Manhattan
            pts = _manhattan([start] + via_pts + [end])
        else:
            # Ref mode, no manual waypoints — direction-aware routing
            x1, y1 = start[0], start[1]
            x2, y2 = end[0], end[1]
            if abs(x1 - x2) < 1e-4 or abs(y1 - y2) < 1e-4:
                pts = [start, end]
            else:
                pts = _route_pins(start, end, from_angle, to_angle)

        try:
            from kicad_mcp.commands.wire_manager import WireManager
            from kicad_mcp.commands.ipc_reload import try_reload
            if len(pts) == 2:
                ok = WireManager.add_wire(sch_file, pts[0], pts[1])
            else:
                ok = WireManager.add_polyline_wire(sch_file, pts)
            if not ok:
                return {"success": False, "error": "WireManager add_wire returned False"}
            result: Dict = {"success": True, "waypoints": pts, "schematic": str(sch_file)}
            if resolved_pins:
                result["resolved_pins"] = resolved_pins
            result.update(try_reload(sch_file))
            return result
        except Exception as exc:
            logger.exception("add_schematic_wire failed")
            return {"success": False, "error": str(exc)}

    def _handle_add_schematic_net_label(self, params: Dict) -> Dict:
        sch_file = self._resolve_sch_path(params)
        if not sch_file:
            return {"success": False, "error": "No schematic loaded."}
        net_name = params.get("netName")
        if not net_name:
            return {"success": False, "error": "netName is required"}
        label_type = params.get("labelType", "label")
        try:
            orientation = int(params.get("orientation", 0))
        except (TypeError, ValueError):
            return {"success": False, "error": "orientation must be integer"}

        component_ref = params.get("componentRef")
        pin_number = params.get("pinNumber")
        position = params.get("position")
        snapped_to_pin = None

        if component_ref and pin_number is not None:
            try:
                from kicad_mcp.commands.pin_locator import PinLocator
                locator = PinLocator()
                pos = locator.get_pin_location(sch_file, component_ref, str(pin_number))
                if pos is None:
                    return {"success": False,
                            "error": f"Pin {component_ref}.{pin_number} not found"}
                position = [pos[0], pos[1]]
                snapped_to_pin = {"reference": component_ref, "pin": str(pin_number)}
            except Exception as exc:
                logger.exception("pin lookup failed")
                return {"success": False, "error": f"pin lookup failed: {exc}"}

        if not position or len(position) != 2:
            return {"success": False,
                    "error": "either position [x,y] or componentRef+pinNumber required"}
        try:
            pos = [float(position[0]), float(position[1])]
        except (TypeError, ValueError) as exc:
            return {"success": False, "error": f"invalid position: {exc}"}
        try:
            from kicad_mcp.commands.wire_manager import WireManager
            from kicad_mcp.commands.ipc_reload import try_reload
            ok = WireManager.add_label(sch_file, net_name, pos,
                                       label_type=label_type, orientation=orientation)
            if not ok:
                return {"success": False, "error": "WireManager.add_label returned False"}
            result = {
                "success": True,
                "netName": net_name,
                "actual_position": pos,
                "snapped_to_pin": snapped_to_pin,
                "schematic": str(sch_file),
            }
            result.update(try_reload(sch_file))
            return result
        except Exception as exc:
            logger.exception("add_schematic_net_label failed")
            return {"success": False, "error": str(exc)}

    def _handle_add_no_connect(self, params: Dict) -> Dict:
        sch_file = self._resolve_sch_path(params)
        if not sch_file:
            return {"success": False, "error": "No schematic loaded."}
        position = params.get("position")
        if not position or len(position) != 2:
            return {"success": False, "error": "position [x,y] required"}
        try:
            pos = [float(position[0]), float(position[1])]
            from kicad_mcp.commands.wire_manager import WireManager
            from kicad_mcp.commands.ipc_reload import try_reload
            ok = WireManager.add_no_connect(sch_file, pos)
            if not ok:
                return {"success": False, "error": "add_no_connect returned False"}
            result = {"success": True, "position": pos, "schematic": str(sch_file)}
            result.update(try_reload(sch_file))
            return result
        except Exception as exc:
            logger.exception("add_no_connect failed")
            return {"success": False, "error": str(exc)}

    def _handle_add_schematic_hierarchical_label(self, params: Dict) -> Dict:
        sch_file = self._resolve_sch_path(params)
        if not sch_file:
            return {"success": False, "error": "No schematic loaded."}
        text = params.get("text") or params.get("netName")
        position = params.get("position")
        if not text or not position or len(position) != 2:
            return {"success": False, "error": "text and position [x,y] required"}
        shape = params.get("shape", "bidirectional")
        try:
            orientation = int(params.get("orientation", 0))
            pos = [float(position[0]), float(position[1])]
            from kicad_mcp.commands.wire_manager import WireManager
            from kicad_mcp.commands.ipc_reload import try_reload
            ok = WireManager.add_hierarchical_label(sch_file, text, pos,
                                                    shape=shape, orientation=orientation)
            if not ok:
                return {"success": False, "error": "add_hierarchical_label returned False"}
            result = {"success": True, "text": text, "position": pos, "schematic": str(sch_file)}
            result.update(try_reload(sch_file))
            return result
        except Exception as exc:
            logger.exception("add_hierarchical_label failed")
            return {"success": False, "error": str(exc)}

    def _handle_add_schematic_text(self, params: Dict) -> Dict:
        sch_file = self._resolve_sch_path(params)
        if not sch_file:
            return {"success": False, "error": "No schematic loaded."}
        text = params.get("text")
        if not text:
            return {"success": False, "error": "text is required"}
        try:
            x = float(params.get("x", 0))
            y = float(params.get("y", 0))
            rotation = float(params.get("rotation", 0))
            size = float(params.get("size", 1.27))
            from kicad_mcp.commands.wire_manager import WireManager
            from kicad_mcp.commands.ipc_reload import try_reload
            ok = WireManager.add_text(sch_file, text, [x, y],
                                      angle=rotation, font_size=size)
            if not ok:
                return {"success": False, "error": "WireManager.add_text returned False"}
            result = {"success": True, "text": text, "position": [x, y],
                      "schematic": str(sch_file)}
            result.update(try_reload(sch_file))
            return result
        except Exception as exc:
            logger.exception("add_schematic_text failed")
            return {"success": False, "error": str(exc)}

    def _handle_add_sheet_pin(self, params: Dict) -> Dict:
        return self._sch_delegate(["add_sheet_pin"], params)

    def _handle_add_schematic_bus(self, params: Dict) -> Dict:
        return self._sch_delegate(["add_bus"], params)

    def _handle_add_schematic_junction(self, params: Dict) -> Dict:
        return self._sch_delegate(["add_junction"], params)

    def _handle_add_schematic_power_symbol(self, params: Dict) -> Dict:
        sch_file = self._resolve_sch_path(params)
        if not sch_file:
            return {"success": False, "error": "No schematic loaded"}
        net_name = params.get("netName")
        if not net_name:
            return {"success": False, "error": "netName required (e.g. VCC, GND, +3V3)"}

        component_ref = params.get("componentRef")
        pin_number = params.get("pinNumber")
        position = params.get("position")

        try:
            orientation = int(params.get("orientation", 0))
        except (TypeError, ValueError):
            orientation = 0

        # Resolve position from pin ref if given
        if component_ref and pin_number is not None:
            try:
                from kicad_mcp.commands.pin_locator import PinLocator
                locator = PinLocator()
                pos = locator.get_pin_location(sch_file, component_ref, str(pin_number))
                if pos is None:
                    return {"success": False, "error": f"Pin {component_ref}.{pin_number} not found"}
                position = [pos[0], pos[1]]
            except Exception as exc:
                return {"success": False, "error": f"pin lookup failed: {exc}"}

        if not position or len(position) < 2:
            return {"success": False, "error": "position [x, y] or componentRef+pinNumber required"}

        try:
            from kicad_mcp.commands.wire_manager import WireManager
            from kicad_mcp.commands.ipc_reload import try_reload
            ok = WireManager.add_power_symbol(sch_file, net_name, position, orientation)
            if not ok:
                return {"success": False, "error": "add_power_symbol returned False"}
            result = {"success": True, "net_name": net_name, "position": position}
            result.update(try_reload(sch_file))
            return result
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_annotate_schematic(self, params: Dict) -> Dict:
        return self._sch_delegate(["annotate"], params)

    def _handle_move_schematic_component(self, params: Dict) -> Dict:
        sch_file = self._resolve_sch_path(params)
        if not sch_file:
            return {"success": False, "error": "No schematic loaded"}
        reference = params.get("reference")
        if not reference:
            return {"success": False, "error": "reference required"}
        try:
            new_x = float(params["x"])
            new_y = float(params["y"])
        except (KeyError, TypeError, ValueError) as exc:
            return {"success": False, "error": f"x/y required: {exc}"}
        try:
            import sexpdata
            from sexpdata import Symbol
            _SYM = Symbol("symbol")
            _AT = Symbol("at")
            _PROP = Symbol("property")
            _REF_KEY = "Reference"
            content = sch_file.read_text(encoding="utf-8")
            sch_data = sexpdata.loads(content)
            moved = 0
            for item in sch_data[1:]:
                if not (isinstance(item, list) and item and item[0] == _SYM):
                    continue
                # Find reference matching this component
                ref_val = None
                for sub in item[1:]:
                    if (isinstance(sub, list) and len(sub) >= 3
                            and sub[0] == _PROP
                            and str(sub[1]).strip('"') == _REF_KEY):
                        ref_val = str(sub[2]).strip('"').rstrip("_")
                        break
                if ref_val != reference:
                    continue
                # Find current (at x y angle)
                old_x = old_y = None
                for i, sub in enumerate(item):
                    if isinstance(sub, list) and sub and sub[0] == _AT:
                        old_x, old_y = float(sub[1]), float(sub[2])
                        item[i] = [_AT, new_x, new_y] + list(sub[3:])
                        break
                if old_x is None:
                    continue
                dx, dy = new_x - old_x, new_y - old_y
                # Shift all property positions by the same delta
                for sub in item[1:]:
                    if isinstance(sub, list) and sub and sub[0] == _PROP:
                        for j, psub in enumerate(sub):
                            if isinstance(psub, list) and psub and psub[0] == _AT:
                                sub[j] = [_AT, float(psub[1]) + dx,
                                          float(psub[2]) + dy] + list(psub[3:])
                moved += 1
            if moved == 0:
                return {"success": False, "error": f"Component {reference} not found"}
            sch_file.write_text(sexpdata.dumps(sch_data), encoding="utf-8")
            from kicad_mcp.commands.wire_manager import WireManager
            from kicad_mcp.commands.ipc_reload import try_reload
            result = {"success": True, "reference": reference,
                      "position": [new_x, new_y]}
            result.update(try_reload(sch_file))
            return result
        except Exception as exc:
            logger.exception("move_schematic_component failed")
            return {"success": False, "error": str(exc)}

    def _handle_rotate_schematic_component(self, params: Dict) -> Dict:
        return self._sch_delegate(["rotate_component"], params)

    def _handle_delete_schematic_wire(self, params: Dict) -> Dict:
        sch_file = self._resolve_sch_path(params)
        if not sch_file:
            return {"success": False, "error": "No schematic loaded"}
        try:
            from kicad_mcp.commands.wire_manager import WireManager
            from kicad_mcp.commands.ipc_reload import try_reload

            wire_id = params.get("wireId")
            start = params.get("start")
            end = params.get("end")

            if wire_id:
                ok = WireManager.delete_wire_by_uuid(sch_file, str(wire_id))
            elif start and end:
                s = [float(start[0]), float(start[1])]
                e = [float(end[0]), float(end[1])]
                ok = WireManager.delete_wire(sch_file, s, e)
            else:
                return {"success": False, "error": "Provide wireId (UUID) or start+end coordinates"}

            if not ok:
                return {"success": False, "error": "Wire not found"}
            result = {"success": True}
            result.update(try_reload(sch_file))
            return result
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_delete_schematic_net_label(self, params: Dict) -> Dict:
        return self._sch_delegate(["delete_net_label"], params)

    def _handle_move_schematic_net_label(self, params: Dict) -> Dict:
        return self._sch_delegate(["move_net_label"], params)

    def _handle_list_schematic_components(self, params: Dict) -> Dict:
        sch_file = self._resolve_sch_path(params)
        if not sch_file:
            return {"success": False, "error": "No schematic loaded"}
        try:
            import sexpdata
            from sexpdata import Symbol
            content = sch_file.read_text(encoding="utf-8")
            sch_data = sexpdata.loads(content)
            _SYM = Symbol("symbol")
            _PROP = Symbol("property")
            filt = params.get("filter", "")
            components = []
            for item in sch_data[1:]:
                if not (isinstance(item, list) and item and item[0] == _SYM):
                    continue
                ref = val = lib_id = ""
                x = y = 0.0
                for sub in item[1:]:
                    if not isinstance(sub, list) or not sub:
                        continue
                    if sub[0] == _PROP and len(sub) >= 3:
                        key = str(sub[1]).strip('"')
                        v = str(sub[2]).strip('"')
                        if key == "Reference":
                            ref = v.rstrip("_")
                        elif key == "Value":
                            val = v
                    elif sub[0] == Symbol("lib_id") and len(sub) >= 2:
                        lib_id = str(sub[1]).strip('"')
                    elif sub[0] == Symbol("at") and len(sub) >= 3:
                        x, y = float(sub[1]), float(sub[2])
                if ref and (not filt or ref.startswith(filt)):
                    components.append({"reference": ref, "value": val,
                                       "lib_id": lib_id, "x": x, "y": y})
            return {"success": True, "components": components, "count": len(components)}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_list_schematic_nets(self, params: Dict) -> Dict:
        return self._sch_delegate(["list_nets"], params)

    def _handle_list_schematic_wires(self, params: Dict) -> Dict:
        sch_file = self._resolve_sch_path(params)
        if not sch_file:
            return {"success": False, "error": "No schematic loaded"}
        try:
            from kicad_mcp.commands.wire_manager import WireManager
            import sexpdata
            from sexpdata import Symbol
            content = sch_file.read_text(encoding="utf-8")
            sch_data = sexpdata.loads(content)
            wires = []
            for item in sch_data[1:]:
                parsed = WireManager._parse_wire(item)
                if parsed:
                    (x1, y1), (x2, y2), w, t = parsed
                    wires.append({"start": [x1, y1], "end": [x2, y2],
                                  "stroke_width": w, "stroke_type": t})
            return {"success": True, "wires": wires, "count": len(wires)}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_list_schematic_labels(self, params: Dict) -> Dict:
        return self._sch_delegate(["list_labels"], params)

    def _handle_list_schematic_texts(self, params: Dict) -> Dict:
        return self._sch_delegate(["list_texts"], params)

    def _handle_get_schematic_view(self, params: Dict) -> Dict:
        sch_path = self._sch_path_from_params(params)
        if not sch_path:
            return {"success": False, "error": "No schematic loaded"}
        try:
            import base64, subprocess, tempfile
            fmt = params.get("format", "png").lower()
            with tempfile.TemporaryDirectory() as tmp:
                out = os.path.join(tmp, f"view.{fmt}")
                cmd = ["kicad-cli", "sch", "export", fmt, "-o", out, sch_path]
                r = subprocess.run(cmd, capture_output=True, timeout=30)
                # kicad-cli svg/png export writes into a directory named by -o;
                # find the actual output file inside it if needed.
                actual = out
                if os.path.isdir(out):
                    base = os.path.splitext(os.path.basename(sch_path))[0]
                    actual = os.path.join(out, f"{base}.{fmt}")
                if r.returncode != 0 or not os.path.exists(actual):
                    return {"success": False, "error": r.stderr.decode()[:500]}
                data = open(actual, "rb").read()
                if params.get("responseMode") == "inline":
                    return {"success": True, "format": fmt,
                            "data": base64.b64encode(data).decode()}
                save_to = params.get("outputPath", actual)
                with open(save_to, "wb") as fh:
                    fh.write(data)
                return {"success": True, "format": fmt, "path": save_to}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_export_schematic_pdf(self, params: Dict) -> Dict:
        return self._sch_delegate(["export_pdf"], params)

    def _handle_export_schematic_svg(self, params: Dict) -> Dict:
        return self._sch_delegate(["export_svg"], params)

    def _handle_run_erc(self, params: Dict) -> Dict:
        sch_path = self._sch_path_from_params(params)
        if not sch_path:
            return {"success": False, "error": "No schematic loaded"}
        try:
            import subprocess, tempfile, json as _json
            with tempfile.TemporaryDirectory() as tmp:
                out_file = os.path.join(tmp, "erc.json")
                cmd = ["kicad-cli", "sch", "erc", "--format", "json",
                       "-o", out_file, sch_path]
                r = subprocess.run(cmd, capture_output=True, timeout=60)
                if os.path.exists(out_file):
                    try:
                        erc_data = _json.loads(open(out_file).read())
                        violations = erc_data.get("violations", [])
                        return {"success": True, "violation_count": len(violations),
                                "violations": violations[:50]}
                    except Exception:
                        pass
                return {"success": r.returncode == 0,
                        "output": r.stdout.decode()[:2000],
                        "error": r.stderr.decode()[:500] if r.returncode != 0 else ""}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_sync_schematic_to_board(self, params: Dict) -> Dict:
        return self._sch_delegate(["sync_to_board"], params)

    # Connectivity helpers
    def _handle_connect_to_net(self, params: Dict) -> Dict:
        return self._sch_delegate(["connect_to_net"], params)

    def _handle_connect_passthrough(self, params: Dict) -> Dict:
        return self._sch_delegate(["connect_passthrough"], params)

    def _handle_get_schematic_pin_locations(self, params: Dict) -> Dict:
        sch_path = self._sch_path_from_params(params)
        if not sch_path:
            return {"success": False, "error": "No schematic loaded"}
        reference = params.get("reference")
        if not reference:
            return {"success": False, "error": "reference required"}
        try:
            from pathlib import Path
            from kicad_mcp.commands.pin_locator import PinLocator
            locator = PinLocator()
            pins = locator.get_all_symbol_pins(Path(sch_path), reference)
            if not pins:
                return {"success": False,
                        "error": f"No pins found for {reference} — symbol may not be in schematic"}
            return {"success": True, "reference": reference,
                    "pins": {num: {"x": xy[0], "y": xy[1]} for num, xy in pins.items()}}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_get_net_connections(self, params: Dict) -> Dict:
        return self._sch_delegate(["get_net_connections"], params)

    def _handle_get_wire_connections(self, params: Dict) -> Dict:
        return self._sch_delegate(["get_wire_connections"], params)

    def _handle_get_net_at_point(self, params: Dict) -> Dict:
        return self._sch_delegate(["get_net_at_point"], params)

    # Analysis
    def _handle_get_schematic_view_region(self, params: Dict) -> Dict:
        return self._sch_delegate(["get_view_region"], params)

    def _handle_find_overlapping_elements(self, params: Dict) -> Dict:
        return self._sch_delegate(["find_overlapping_elements"], params)

    def _handle_get_elements_in_region(self, params: Dict) -> Dict:
        return self._sch_delegate(["get_elements_in_region"], params)

    def _handle_find_wires_crossing_symbols(self, params: Dict) -> Dict:
        return self._sch_delegate(["find_wires_crossing_symbols"], params)

    def _handle_find_orphaned_wires(self, params: Dict) -> Dict:
        return self._sch_delegate(["find_orphaned_wires"], params)

    def _handle_list_floating_labels(self, params: Dict) -> Dict:
        return self._sch_delegate(["list_floating_labels"], params)

    def _handle_snap_to_grid(self, params: Dict) -> Dict:
        return self._sch_delegate(["snap_to_grid"], params)

    # ------------------------------------------------------------------
    # UI handlers
    # ------------------------------------------------------------------

    def _handle_check_kicad_ui(self, params: Dict) -> Dict:
        try:
            from kicad_mcp.utils.kicad_process import KiCADProcessManager
            running = KiCADProcessManager.is_running()
            processes = KiCADProcessManager.get_process_info() if running else []
            return {"success": True, "running": running, "processes": processes}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_launch_kicad_ui(self, params: Dict) -> Dict:
        try:
            from kicad_mcp.utils.kicad_process import KiCADProcessManager
            project_path = params.get("projectPath")
            success = KiCADProcessManager.launch(
                Path(project_path) if project_path else None
            )
            return {"success": success, "message": "KiCAD launched" if success else "Launch failed"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}


# Module-level singleton (lazy init)
_dispatcher: Optional[KiCADDispatcher] = None


def get_dispatcher() -> KiCADDispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = KiCADDispatcher()
    return _dispatcher
