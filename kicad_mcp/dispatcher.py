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
            # Load the created board
            board_path = result.get("project", {}).get("boardPath")
            if board_path and self._pcbnew:
                try:
                    board = self._pcbnew.LoadBoard(board_path)
                    self._set_board(board)
                except Exception as exc:
                    logger.warning(f"Could not load created board: {exc}")
        return result

    def _handle_open_project(self, params: Dict) -> Dict:
        result = self.project_commands.open_project(params)
        if result.get("success") and self._pcbnew:
            board_path = result.get("project", {}).get("boardPath") or params.get("filename")
            if board_path:
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
            return self.jlcpcb_parts_manager.download_database(params)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_search_jlcpcb_parts(self, params: Dict) -> Dict:
        try:
            return self.jlcpcb_parts_manager.search_parts(params)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_get_jlcpcb_part(self, params: Dict) -> Dict:
        try:
            return self.jlcpcb_parts_manager.get_part(params)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_get_jlcpcb_database_stats(self, params: Dict) -> Dict:
        try:
            return self.jlcpcb_parts_manager.get_stats(params)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _handle_suggest_jlcpcb_alternatives(self, params: Dict) -> Dict:
        try:
            return self.jlcpcb_parts_manager.suggest_alternatives(params)
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
            name = params.get("name", "schematic")
            path = params.get("path", ".")
            sch = SchematicManager.create_schematic(name, path=path)
            sch_path = os.path.join(path, f"{name}.kicad_sch")
            self._sch_path = sch_path
            self._sch_manager = sch
            return {"success": True, "message": f"Created schematic: {sch_path}",
                    "schematicPath": sch_path}
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
            return {"success": True, "message": f"Saved: {self._sch_path}"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _sch_delegate(self, method_chain: list, params: Dict) -> Dict:
        """Helper: load schematic path from params, then call a chain of methods."""
        path = self._sch_path_from_params(params)
        try:
            from kicad_mcp.commands.wire_manager import WireManager
            wm = WireManager(path)
            obj = wm
            for attr in method_chain:
                obj = getattr(obj, attr)
            return obj(params)
        except Exception as exc:
            logger.error(f"Schematic operation error: {exc}")
            return {"success": False, "error": str(exc)}

    def _handle_add_schematic_component(self, params: Dict) -> Dict:
        return self._sch_delegate(["add_component"], params)

    def _handle_delete_schematic_component(self, params: Dict) -> Dict:
        return self._sch_delegate(["delete_component"], params)

    def _handle_edit_schematic_component(self, params: Dict) -> Dict:
        return self._sch_delegate(["edit_component"], params)

    def _handle_set_schematic_component_property(self, params: Dict) -> Dict:
        return self._sch_delegate(["set_component_property"], params)

    def _handle_remove_schematic_component_property(self, params: Dict) -> Dict:
        return self._sch_delegate(["remove_component_property"], params)

    def _handle_get_schematic_component(self, params: Dict) -> Dict:
        return self._sch_delegate(["get_component"], params)

    def _handle_add_schematic_wire(self, params: Dict) -> Dict:
        return self._sch_delegate(["add_wire"], params)

    def _handle_add_schematic_net_label(self, params: Dict) -> Dict:
        return self._sch_delegate(["add_net_label"], params)

    def _handle_add_no_connect(self, params: Dict) -> Dict:
        return self._sch_delegate(["add_no_connect"], params)

    def _handle_add_schematic_hierarchical_label(self, params: Dict) -> Dict:
        return self._sch_delegate(["add_hierarchical_label"], params)

    def _handle_add_schematic_text(self, params: Dict) -> Dict:
        return self._sch_delegate(["add_text"], params)

    def _handle_add_sheet_pin(self, params: Dict) -> Dict:
        return self._sch_delegate(["add_sheet_pin"], params)

    def _handle_add_schematic_bus(self, params: Dict) -> Dict:
        return self._sch_delegate(["add_bus"], params)

    def _handle_add_schematic_junction(self, params: Dict) -> Dict:
        return self._sch_delegate(["add_junction"], params)

    def _handle_add_schematic_power_symbol(self, params: Dict) -> Dict:
        return self._sch_delegate(["add_power_symbol"], params)

    def _handle_annotate_schematic(self, params: Dict) -> Dict:
        return self._sch_delegate(["annotate"], params)

    def _handle_move_schematic_component(self, params: Dict) -> Dict:
        return self._sch_delegate(["move_component"], params)

    def _handle_rotate_schematic_component(self, params: Dict) -> Dict:
        return self._sch_delegate(["rotate_component"], params)

    def _handle_delete_schematic_wire(self, params: Dict) -> Dict:
        return self._sch_delegate(["delete_wire"], params)

    def _handle_delete_schematic_net_label(self, params: Dict) -> Dict:
        return self._sch_delegate(["delete_net_label"], params)

    def _handle_move_schematic_net_label(self, params: Dict) -> Dict:
        return self._sch_delegate(["move_net_label"], params)

    def _handle_list_schematic_components(self, params: Dict) -> Dict:
        return self._sch_delegate(["list_components"], params)

    def _handle_list_schematic_nets(self, params: Dict) -> Dict:
        return self._sch_delegate(["list_nets"], params)

    def _handle_list_schematic_wires(self, params: Dict) -> Dict:
        return self._sch_delegate(["list_wires"], params)

    def _handle_list_schematic_labels(self, params: Dict) -> Dict:
        return self._sch_delegate(["list_labels"], params)

    def _handle_list_schematic_texts(self, params: Dict) -> Dict:
        return self._sch_delegate(["list_texts"], params)

    def _handle_get_schematic_view(self, params: Dict) -> Dict:
        return self._sch_delegate(["get_view"], params)

    def _handle_export_schematic_pdf(self, params: Dict) -> Dict:
        return self._sch_delegate(["export_pdf"], params)

    def _handle_export_schematic_svg(self, params: Dict) -> Dict:
        return self._sch_delegate(["export_svg"], params)

    def _handle_run_erc(self, params: Dict) -> Dict:
        return self._sch_delegate(["run_erc"], params)

    def _handle_sync_schematic_to_board(self, params: Dict) -> Dict:
        return self._sch_delegate(["sync_to_board"], params)

    # Connectivity helpers
    def _handle_connect_to_net(self, params: Dict) -> Dict:
        return self._sch_delegate(["connect_to_net"], params)

    def _handle_connect_passthrough(self, params: Dict) -> Dict:
        return self._sch_delegate(["connect_passthrough"], params)

    def _handle_get_schematic_pin_locations(self, params: Dict) -> Dict:
        return self._sch_delegate(["get_pin_locations"], params)

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
