"""
Tool registry: defines which tools are always visible (direct) vs discovered
via the router meta-tools (list_tool_categories / get_category_tools).

This mirrors the TypeScript router.ts design exactly.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Routed categories
# Each value is the ordered list of tool names in that category.
# ---------------------------------------------------------------------------

ROUTED_CATEGORIES: dict[str, list[str]] = {
    "board": [
        "set_board_size",
        "add_layer",
        "set_active_layer",
        "get_board_info",
        "get_layer_list",
        "add_board_outline",
        "add_mounting_hole",
        "add_board_text",
        "add_zone",
    ],
    "component": [
        "add_component",
        "move_component",
        "rotate_component",
        "flip_component",
        "delete_component",
        "get_component_info",
        "add_component_annotation",
        "group_components",
        "replace_component",
        "list_components",
        "align_components",
        "distribute_components",
    ],
    "export": [
        "export_gerber",
        "export_drill",
        "export_pdf",
        "export_dxf",
        "export_svg",
        "export_bom",
        "export_step",
        "export_netlist",
        "export_position_file",
        "export_vrml",
    ],
    "drc": [
        "run_drc",
        "get_drc_results",
        "clear_drc_results",
        "get_design_rules",
        "set_design_rules",
        "add_net_class",
        "assign_net_to_class",
        "check_clearance",
        "set_layer_constraints",
    ],
    "schematic": [
        "create_schematic",
        "open_schematic",
        "save_schematic",
        "add_schematic_component",
        "add_schematic_wire",
        "add_schematic_net_label",
        "add_schematic_bus",
        "add_schematic_junction",
        "add_schematic_power_symbol",
        "add_no_connect",
        "add_schematic_hierarchical_label",
        "add_schematic_text",
        "add_sheet_pin",
        "annotate_schematic",
        "delete_schematic_component",
        "delete_schematic_net_label",
        "delete_schematic_wire",
        "edit_schematic_component",
        "get_schematic_component",
        "get_schematic_view",
        "list_schematic_components",
        "list_schematic_labels",
        "list_schematic_nets",
        "list_schematic_texts",
        "list_schematic_wires",
        "move_schematic_component",
        "move_schematic_net_label",
        "remove_schematic_component_property",
        "rotate_schematic_component",
        "set_schematic_component_property",
        "export_schematic_pdf",
        "export_schematic_svg",
    ],
    "library": [
        "list_symbol_libraries",
        "search_symbols",
        "list_library_symbols",
        "get_symbol_info",
        "create_footprint",
        "edit_footprint_pad",
        "register_footprint_library",
        "list_footprint_libraries",
        "create_symbol",
        "delete_symbol",
        "list_symbols_in_library",
        "register_symbol_library",
    ],
    "routing": [
        "add_trace",
        "add_via",
        "route_pad_to_pad",
        "route_arc_trace",
        "refill_zones",
    ],
    "autoroute": [
        "autoroute",
        "export_dsn",
        "import_ses",
        "check_freerouting",
    ],
    "jlcpcb": [
        "download_jlcpcb_database",
        "search_jlcpcb_parts",
        "get_jlcpcb_part",
        "get_jlcpcb_database_stats",
        "suggest_jlcpcb_alternatives",
        "enrich_datasheets",
        "get_datasheet_url",
    ],
}

# ---------------------------------------------------------------------------
# Direct tools – always returned in tools/list without category discovery
# ---------------------------------------------------------------------------

DIRECT_TOOL_NAMES: list[str] = [
    # Project lifecycle
    "create_project",
    "open_project",
    "save_project",
    "close_project",
    "get_project_info",
    # Board basics
    "get_board_extents",
    "get_board_2d_view",
    "import_svg_logo",
    # UI / focus
    "set_active_layer",
    "get_layer_list",
    # Router meta-tools (always visible so LLM can discover the rest)
    "list_tool_categories",
    "get_category_tools",
    "search_tools",
    # JLCPCB quick-access
    "search_jlcpcb_parts",
]

# ---------------------------------------------------------------------------
# Flattened set of all routed tool names (for fast membership tests)
# ---------------------------------------------------------------------------

ROUTED_TOOL_NAMES: set[str] = {
    name for names in ROUTED_CATEGORIES.values() for name in names
}
