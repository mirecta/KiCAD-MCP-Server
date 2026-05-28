"""
Comprehensive tool schema definitions for all KiCAD MCP commands

Following MCP 2025-06-18 specification for tool definitions.
Each tool includes:
- name: Unique identifier
- title: Human-readable display name
- description: Detailed explanation of what the tool does
- inputSchema: JSON Schema for parameters
- outputSchema: Optional JSON Schema for return values (structured content)
"""

from typing import Any, Dict, List

# =============================================================================
# PROJECT TOOLS
# =============================================================================

PROJECT_TOOLS = [
    {
        "name": "create_project",
        "title": "Create New KiCAD Project",
        "description": "Creates a new KiCAD project with PCB board file and optional project configuration. Automatically creates project directory and initializes board with default settings.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "projectName": {
                    "type": "string",
                    "description": "Name of the project (used for file naming)",
                    "minLength": 1,
                },
                "path": {
                    "type": "string",
                    "description": "Directory path where project will be created (defaults to current working directory)",
                },
                "template": {
                    "type": "string",
                    "description": "Optional path to template board file to copy settings from",
                },
            },
            "required": ["projectName"],
        },
    },
    {
        "name": "open_project",
        "title": "Open Existing KiCAD Project",
        "description": "Opens an existing KiCAD project file (.kicad_pro or .kicad_pcb) and loads the board into memory for manipulation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Path to .kicad_pro or .kicad_pcb file",
                }
            },
            "required": ["filename"],
        },
    },
    {
        "name": "save_project",
        "title": "Save Current Project",
        "description": "Saves the current board to disk. Can optionally save to a new location.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Optional new path to save the board (if not provided, saves to current location)",
                }
            },
        },
    },
    {
        "name": "snapshot_project",
        "title": "Snapshot Project (Checkpoint)",
        "description": "Copies the entire project folder to a new timestamped snapshot directory so you can resume from this checkpoint later without redoing earlier steps. Call this after every successfully completed design step (e.g. after Step 1 schematic, after Step 2 PCB layout) before asking for user confirmation to proceed.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "step": {
                    "type": "string",
                    "description": "Step number or name to include in snapshot folder name, e.g. '1' or '2'",
                },
                "label": {
                    "type": "string",
                    "description": "Optional short label, e.g. 'schematic_ok' or 'layout_ok'",
                },
                "projectPath": {
                    "type": "string",
                    "description": "Project directory path. Auto-detected from loaded board if omitted.",
                },
            },
        },
    },
    {
        "name": "get_project_info",
        "title": "Get Project Information",
        "description": "Retrieves metadata and properties of the currently open project including name, paths, and board status.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

# =============================================================================
# BOARD TOOLS
# =============================================================================

BOARD_TOOLS = [
    {
        "name": "set_board_size",
        "title": "Set Board Dimensions",
        "description": "Sets the PCB board dimensions. The board outline must be added separately using add_board_outline.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "width": {
                    "type": "number",
                    "description": "Board width in millimeters",
                    "minimum": 1,
                },
                "height": {
                    "type": "number",
                    "description": "Board height in millimeters",
                    "minimum": 1,
                },
            },
            "required": ["width", "height"],
        },
    },
    {
        "name": "add_board_outline",
        "title": "Add Board Outline",
        "description": "Adds a board outline shape (rectangle, rounded_rectangle, circle, or polygon) on the Edge.Cuts layer. By default the board top-left corner is placed at (0, 0) so all coordinates are positive. Use x/y to set a different top-left corner position.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "shape": {
                    "type": "string",
                    "enum": ["rectangle", "rounded_rectangle", "circle", "polygon"],
                    "description": "Shape type for the board outline",
                },
                "width": {
                    "type": "number",
                    "description": "Width in mm (for rectangle/rounded_rectangle)",
                    "minimum": 1,
                },
                "height": {
                    "type": "number",
                    "description": "Height in mm (for rectangle/rounded_rectangle)",
                    "minimum": 1,
                },
                "x": {
                    "type": "number",
                    "description": "X coordinate of the top-left corner in mm (default: 0). Board extends from x to x+width.",
                },
                "y": {
                    "type": "number",
                    "description": "Y coordinate of the top-left corner in mm (default: 0). Board extends from y to y+height.",
                },
                "radius": {
                    "type": "number",
                    "description": "Corner radius in mm for rounded_rectangle, or radius for circle",
                    "minimum": 0,
                },
                "points": {
                    "type": "array",
                    "description": "Array of {x, y} point objects in mm (for polygon shape only)",
                    "items": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                        },
                        "required": ["x", "y"],
                    },
                    "minItems": 3,
                },
            },
            "required": ["shape"],
        },
    },
    {
        "name": "add_layer",
        "title": "Add Custom Layer",
        "description": "Adds a new custom layer to the board stack (e.g., User.1, User.Comments).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "layerName": {
                    "type": "string",
                    "description": "Name of the layer to add",
                },
                "layerType": {
                    "type": "string",
                    "enum": ["signal", "power", "mixed", "jumper"],
                    "description": "Type of layer (for copper layers)",
                },
            },
            "required": ["layerName"],
        },
    },
    {
        "name": "set_active_layer",
        "title": "Set Active Layer",
        "description": "Sets the currently active layer for drawing operations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "layerName": {
                    "type": "string",
                    "description": "Name of the layer to make active (e.g., F.Cu, B.Cu, Edge.Cuts)",
                }
            },
            "required": ["layerName"],
        },
    },
    {
        "name": "get_layer_list",
        "title": "List Board Layers",
        "description": "Returns a list of all layers in the board with their properties.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_board_info",
        "title": "Get Board Information",
        "description": "Retrieves comprehensive board information including dimensions, layer count, component count, and design rules.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_board_2d_view",
        "title": "Render Board Preview",
        "description": (
            "Generates a 2D visual representation of the current board state as a PNG, JPG, or SVG image. "
            "Use responseMode to control how the image is returned. "
            'responseMode="inline" (default) returns the image bytes as a base64-encoded imageData '
            "string in the JSON response — convenient for small boards but may exceed message-size limits on "
            "large designs. "
            'responseMode="file" writes the image next to the .kicad_pcb file as '
            "<board>_2d_view.<ext> and returns a filePath; callers that can open local files should "
            "prefer this mode for large boards."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "width": {
                    "type": "number",
                    "description": "Image width in pixels (default: 800)",
                    "minimum": 100,
                    "default": 800,
                },
                "height": {
                    "type": "number",
                    "description": "Image height in pixels (default: 600)",
                    "minimum": 100,
                    "default": 600,
                },
                "format": {
                    "type": "string",
                    "enum": ["png", "jpg", "svg"],
                    "description": "Output image format (default: png)",
                    "default": "png",
                },
                "layers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of layer names to include; all enabled layers if omitted",
                },
                "responseMode": {
                    "type": "string",
                    "enum": ["inline", "file"],
                    "default": "inline",
                    "description": (
                        "How to return the image. "
                        '"inline" (default): base64-encoded bytes in the imageData response field. '
                        '"file": write to <board>_2d_view.<ext> next to the PCB and return filePath.'
                    ),
                },
            },
        },
    },
    {
        "name": "get_board_extents",
        "title": "Get Board Bounding Box",
        "description": "Returns the bounding box extents of the PCB board including all edge cuts, components, and traces.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "unit": {
                    "type": "string",
                    "enum": ["mm", "mil", "inch"],
                    "description": "Unit for returned coordinates (default: mm)",
                    "default": "mm",
                }
            },
        },
    },
    {
        "name": "add_mounting_hole",
        "title": "Add Mounting Hole",
        "description": "Adds a mounting hole at the specified position with given diameter. Defaults to non-plated (NPTH) with mask-only pad layers; set plated=true for a PTH with copper pad.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "position": {
                    "type": "object",
                    "description": "Position of the mounting hole",
                    "properties": {
                        "x": {"type": "number", "description": "X coordinate"},
                        "y": {"type": "number", "description": "Y coordinate"},
                        "unit": {
                            "type": "string",
                            "enum": ["mm", "inch"],
                            "default": "mm",
                            "description": "Unit for x/y (default mm)",
                        },
                    },
                    "required": ["x", "y"],
                },
                "diameter": {
                    "type": "number",
                    "description": "Hole (drill) diameter in millimeters",
                    "minimum": 0.1,
                },
                "padDiameter": {
                    "type": "number",
                    "description": "Pad diameter in millimeters (defaults to diameter + 1mm). For NPTH this only affects the solder-mask opening, not copper.",
                    "minimum": 0.1,
                },
                "plated": {
                    "type": "boolean",
                    "default": False,
                    "description": "True for plated through-hole (PTH) with copper pad; false (default) for NPTH (mask only).",
                },
                "footprintLibId": {
                    "type": "string",
                    "description": "Optional library:name FPID (e.g. 'MountingHole:MountingHole_3.2mm'). Defaults to MountingHole:MountingHole_<diameter>mm. A non-empty FPID is required for the footprint to be selectable in KiCad's GUI Move tool.",
                },
            },
            "required": ["position", "diameter"],
        },
    },
    {
        "name": "import_svg_logo",
        "title": "Import SVG Logo to PCB",
        "description": "Imports an SVG file as filled graphic polygons onto a KiCAD PCB layer (default F.SilkS). Curves are linearised automatically. Supports path, rect, circle, ellipse, polygon and group transforms.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pcbPath": {
                    "type": "string",
                    "description": "Path to the .kicad_pcb file",
                },
                "svgPath": {
                    "type": "string",
                    "description": "Path to the SVG logo file",
                },
                "x": {
                    "type": "number",
                    "description": "X position of the logo top-left corner in mm",
                },
                "y": {
                    "type": "number",
                    "description": "Y position of the logo top-left corner in mm",
                },
                "width": {
                    "type": "number",
                    "description": "Target width of the logo in mm (height scaled to preserve aspect ratio)",
                    "minimum": 0.1,
                },
                "layer": {
                    "type": "string",
                    "description": "PCB layer name, e.g. F.SilkS or B.SilkS (default: F.SilkS)",
                    "default": "F.SilkS",
                },
                "strokeWidth": {
                    "type": "number",
                    "description": "Outline stroke width in mm (0 = no outline, default 0)",
                    "default": 0,
                },
                "filled": {
                    "type": "boolean",
                    "description": "Fill polygons with solid layer colour (default true)",
                    "default": True,
                },
            },
            "required": ["pcbPath", "svgPath", "x", "y", "width"],
        },
    },
    {
        "name": "add_board_text",
        "title": "Add Text to Board",
        "description": "Adds text annotation to the board on a specified layer (e.g., F.SilkS for top silkscreen).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text content to add",
                    "minLength": 1,
                },
                "x": {"type": "number", "description": "X coordinate in millimeters"},
                "y": {"type": "number", "description": "Y coordinate in millimeters"},
                "layer": {
                    "type": "string",
                    "description": "Layer name (e.g., F.SilkS, B.SilkS, F.Cu)",
                    "default": "F.SilkS",
                },
                "size": {
                    "type": "number",
                    "description": "Text size in millimeters",
                    "minimum": 0.1,
                    "default": 1.0,
                },
                "thickness": {
                    "type": "number",
                    "description": "Text thickness in millimeters",
                    "minimum": 0.01,
                    "default": 0.15,
                },
            },
            "required": ["text", "x", "y"],
        },
    },
]

# =============================================================================
# COMPONENT TOOLS
# =============================================================================

COMPONENT_TOOLS = [
    {
        "name": "place_component",
        "title": "Place Component",
        "description": "Places a component with specified footprint at given coordinates on the board.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {
                    "type": "string",
                    "description": "Component reference designator (e.g., R1, C2, U3)",
                },
                "footprint": {
                    "type": "string",
                    "description": "Footprint library:name (e.g., Resistor_SMD:R_0805_2012Metric)",
                },
                "x": {"type": "number", "description": "X coordinate in millimeters"},
                "y": {"type": "number", "description": "Y coordinate in millimeters"},
                "rotation": {
                    "type": "number",
                    "description": "Rotation angle in degrees (0-360)",
                    "minimum": 0,
                    "maximum": 360,
                    "default": 0,
                },
                "layer": {
                    "type": "string",
                    "enum": ["F.Cu", "B.Cu"],
                    "description": "Board layer (top or bottom)",
                    "default": "F.Cu",
                },
            },
            "required": ["reference", "footprint", "x", "y"],
        },
    },
    {
        "name": "move_component",
        "title": "Move Component",
        "description": "Moves an existing component to a new position on the board.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {
                    "type": "string",
                    "description": "Component reference designator",
                },
                "x": {
                    "type": "number",
                    "description": "New X coordinate in millimeters",
                },
                "y": {
                    "type": "number",
                    "description": "New Y coordinate in millimeters",
                },
            },
            "required": ["reference", "x", "y"],
        },
    },
    {
        "name": "rotate_component",
        "title": "Rotate Component",
        "description": "Rotates a component by specified angle. Rotation is cumulative with existing rotation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {
                    "type": "string",
                    "description": "Component reference designator",
                },
                "angle": {
                    "type": "number",
                    "description": "Rotation angle in degrees (positive = counterclockwise)",
                },
            },
            "required": ["reference", "angle"],
        },
    },
    {
        "name": "delete_component",
        "title": "Delete Component",
        "description": "Removes a component from the board.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {
                    "type": "string",
                    "description": "Component reference designator",
                }
            },
            "required": ["reference"],
        },
    },
    {
        "name": "edit_component",
        "title": "Edit Component Properties",
        "description": "Modifies properties of an existing component (value, footprint, etc.).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {
                    "type": "string",
                    "description": "Component reference designator",
                },
                "value": {"type": "string", "description": "New component value"},
                "footprint": {
                    "type": "string",
                    "description": "New footprint library:name",
                },
            },
            "required": ["reference"],
        },
    },
    {
        "name": "get_component_properties",
        "title": "Get Component Properties",
        "description": "Retrieves detailed properties of a specific component.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {
                    "type": "string",
                    "description": "Component reference designator",
                }
            },
            "required": ["reference"],
        },
    },
    {
        "name": "get_component_list",
        "title": "List All Components",
        "description": "Returns a list of all components on the board with their properties.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "find_component",
        "title": "Find Components",
        "description": "Searches for components matching specified criteria. Supports partial matching on reference, value, or footprint patterns.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {
                    "type": "string",
                    "description": "Reference designator pattern to match (e.g., 'R1', 'U', 'C2')",
                },
                "value": {
                    "type": "string",
                    "description": "Value pattern to match (e.g., '10k', '100nF')",
                },
                "footprint": {
                    "type": "string",
                    "description": "Footprint pattern to match (e.g., '0805', 'SOIC')",
                },
            },
        },
    },
    {
        "name": "get_component_pads",
        "title": "Get Component Pads",
        "description": "Returns all pads for a component with their positions, net connections, sizes, and shapes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {
                    "type": "string",
                    "description": "Component reference designator (e.g., U1, R5)",
                }
            },
            "required": ["reference"],
        },
    },
    {
        "name": "get_pad_position",
        "title": "Get Pad Position",
        "description": "Returns the position and properties of a specific pad on a component.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {
                    "type": "string",
                    "description": "Component reference designator",
                },
                "padName": {
                    "type": "string",
                    "description": "Pad name or number (e.g., '1', '2', 'A1')",
                },
                "padNumber": {
                    "type": "string",
                    "description": "Alternative to padName - pad number",
                },
            },
            "required": ["reference"],
        },
    },
    {
        "name": "place_component_array",
        "title": "Place Component Array",
        "description": "Places multiple copies of a component in a grid or circular pattern.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "referencePrefix": {
                    "type": "string",
                    "description": "Reference prefix (e.g., 'R' for R1, R2, R3...)",
                },
                "startNumber": {
                    "type": "integer",
                    "description": "Starting number for references",
                    "minimum": 1,
                    "default": 1,
                },
                "footprint": {
                    "type": "string",
                    "description": "Footprint library:name",
                },
                "pattern": {
                    "type": "string",
                    "enum": ["grid", "circular"],
                    "description": "Array pattern type",
                },
                "count": {
                    "type": "integer",
                    "description": "Total number of components to place",
                    "minimum": 1,
                },
                "startX": {
                    "type": "number",
                    "description": "Starting X coordinate in millimeters",
                },
                "startY": {
                    "type": "number",
                    "description": "Starting Y coordinate in millimeters",
                },
                "spacingX": {
                    "type": "number",
                    "description": "Horizontal spacing in mm (for grid pattern)",
                },
                "spacingY": {
                    "type": "number",
                    "description": "Vertical spacing in mm (for grid pattern)",
                },
                "radius": {
                    "type": "number",
                    "description": "Circle radius in mm (for circular pattern)",
                },
                "rows": {
                    "type": "integer",
                    "description": "Number of rows (for grid pattern)",
                    "minimum": 1,
                },
                "columns": {
                    "type": "integer",
                    "description": "Number of columns (for grid pattern)",
                    "minimum": 1,
                },
            },
            "required": [
                "referencePrefix",
                "footprint",
                "pattern",
                "count",
                "startX",
                "startY",
            ],
        },
    },
    {
        "name": "align_components",
        "title": "Align Components",
        "description": "Aligns multiple components horizontally or vertically.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "references": {
                    "type": "array",
                    "description": "Array of component reference designators to align",
                    "items": {"type": "string"},
                    "minItems": 2,
                },
                "direction": {
                    "type": "string",
                    "enum": ["horizontal", "vertical"],
                    "description": "Alignment direction",
                },
                "spacing": {
                    "type": "number",
                    "description": "Spacing between components in mm (optional, for even distribution)",
                },
            },
            "required": ["references", "direction"],
        },
    },
    {
        "name": "check_courtyard_overlaps",
        "title": "Check Courtyard Overlaps",
        "description": (
            "Detects courtyard overlaps between footprints and (optionally) flags "
            "footprints whose courtyard extends past the board outline. "
            "Returns overlap pairs with intersection extents and per-component "
            "boundary violations, both in mm. Accepts a 'positions' dict to "
            "evaluate a HYPOTHETICAL placement without modifying the board — "
            "use this before committing a move_component / place_component call "
            "to know if it will trigger DRC. "
            "Approach ported from morningfire-pcb-automation "
            "(https://github.com/NiNjA-CodE/morningfire-pcb-automation, "
            "scripts/placement/check_overlaps.py); this version reads real "
            "courtyard polygons from the board (not a static lookup table) and "
            "supports virtual placement + rotation + clearance margin."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "positions": {
                    "type": "object",
                    "description": (
                        "Virtual placements: map of reference designator to "
                        "[x, y] or [x, y, rotation_degrees] in mm. Each listed "
                        "ref is checked AS IF it were at the given coordinates. "
                        "Unspecified refs use their current board position."
                    ),
                    "additionalProperties": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 2,
                        "maxItems": 3,
                    },
                },
                "refs": {
                    "type": "array",
                    "description": (
                        "Limit the check to these refs (default: every "
                        "footprint on the board)."
                    ),
                    "items": {"type": "string"},
                },
                "margin": {
                    "type": "number",
                    "description": (
                        "Extra clearance in mm added around every courtyard "
                        "(default 0). Useful to enforce a manufacturing keepout "
                        "wider than the symbol's declared courtyard."
                    ),
                    "default": 0,
                },
                "include_boundary": {
                    "type": "boolean",
                    "description": (
                        "Also flag courtyards that extend past the board outline "
                        "(default true)."
                    ),
                    "default": True,
                },
                "board_outline": {
                    "type": "object",
                    "description": (
                        "Optional override for the board outline bbox. Default: "
                        "derived from Edge.Cuts."
                    ),
                    "properties": {
                        "x1": {"type": "number"},
                        "y1": {"type": "number"},
                        "x2": {"type": "number"},
                        "y2": {"type": "number"},
                        "unit": {
                            "type": "string",
                            "enum": ["mm", "inch"],
                            "default": "mm",
                        },
                    },
                    "required": ["x1", "y1", "x2", "y2"],
                },
            },
        },
    },
    {
        "name": "duplicate_component",
        "title": "Duplicate Component",
        "description": "Creates a copy of an existing component with new reference designator.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sourceReference": {
                    "type": "string",
                    "description": "Reference of component to duplicate",
                },
                "newReference": {
                    "type": "string",
                    "description": "Reference designator for the new component",
                },
                "offsetX": {
                    "type": "number",
                    "description": "X offset from original position in mm",
                    "default": 0,
                },
                "offsetY": {
                    "type": "number",
                    "description": "Y offset from original position in mm",
                    "default": 0,
                },
            },
            "required": ["sourceReference", "newReference"],
        },
    },
]

# =============================================================================
# ROUTING TOOLS
# =============================================================================

ROUTING_TOOLS = [
    {
        "name": "add_net",
        "title": "Create Electrical Net",
        "description": "Creates a new electrical net for signal routing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "netName": {
                    "type": "string",
                    "description": "Name of the net (e.g., VCC, GND, SDA)",
                    "minLength": 1,
                },
                "netClass": {
                    "type": "string",
                    "description": "Optional net class to assign (must exist first)",
                },
            },
            "required": ["netName"],
        },
    },
    {
        "name": "route_trace",
        "title": "Route PCB Trace",
        "description": "Routes a copper trace between two points or pads on a specified layer.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "netName": {"type": "string", "description": "Net name for this trace"},
                "layer": {
                    "type": "string",
                    "description": "Layer to route on (e.g., F.Cu, B.Cu)",
                    "default": "F.Cu",
                },
                "width": {
                    "type": "number",
                    "description": "Trace width in millimeters",
                    "minimum": 0.1,
                },
                "points": {
                    "type": "array",
                    "description": "Array of [x, y] waypoints in millimeters",
                    "items": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 2,
                        "maxItems": 2,
                    },
                    "minItems": 2,
                },
            },
            "required": ["points", "width"],
        },
    },
    {
        "name": "add_via",
        "title": "Add Via",
        "description": "Adds a via (plated through-hole) to connect traces between layers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "x": {"type": "number", "description": "X coordinate in millimeters"},
                "y": {"type": "number", "description": "Y coordinate in millimeters"},
                "diameter": {
                    "type": "number",
                    "description": "Via diameter in millimeters",
                    "minimum": 0.1,
                },
                "drill": {
                    "type": "number",
                    "description": "Drill diameter in millimeters",
                    "minimum": 0.1,
                },
                "netName": {
                    "type": "string",
                    "description": "Net name to assign to this via",
                },
            },
            "required": ["x", "y", "diameter", "drill"],
        },
    },
    {
        "name": "delete_trace",
        "title": "Delete Trace",
        "description": "Removes traces from the board. Can delete by UUID, position, or bulk-delete all traces on a net.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "uuid": {
                    "type": "string",
                    "description": "UUID of a specific trace to delete",
                },
                "position": {
                    "type": "object",
                    "description": "Delete trace nearest to this position",
                    "properties": {
                        "x": {"type": "number", "description": "X coordinate"},
                        "y": {"type": "number", "description": "Y coordinate"},
                        "unit": {
                            "type": "string",
                            "enum": ["mm", "mil", "inch"],
                            "default": "mm",
                        },
                    },
                    "required": ["x", "y"],
                },
                "net": {
                    "type": "string",
                    "description": "Delete all traces on this net (bulk delete)",
                },
                "layer": {
                    "type": "string",
                    "description": "Filter by layer when using net-based deletion",
                },
                "includeVias": {
                    "type": "boolean",
                    "description": "Include vias in net-based deletion",
                    "default": False,
                },
            },
        },
    },
    {
        "name": "query_traces",
        "title": "Query Traces",
        "description": "Queries traces on the board with optional filters by net, layer, or bounding box. Returns trace details including UUID, positions, width, and length.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "net": {
                    "type": "string",
                    "description": "Filter by net name (e.g., 'GND', 'VCC')",
                },
                "layer": {
                    "type": "string",
                    "description": "Filter by layer name (e.g., 'F.Cu', 'B.Cu')",
                },
                "boundingBox": {
                    "type": "object",
                    "description": "Filter by bounding box region",
                    "properties": {
                        "x1": {"type": "number", "description": "Left X coordinate"},
                        "y1": {"type": "number", "description": "Top Y coordinate"},
                        "x2": {"type": "number", "description": "Right X coordinate"},
                        "y2": {"type": "number", "description": "Bottom Y coordinate"},
                        "unit": {
                            "type": "string",
                            "enum": ["mm", "mil", "inch"],
                            "default": "mm",
                        },
                    },
                },
                "includeVias": {
                    "type": "boolean",
                    "description": "Include vias in the result",
                    "default": False,
                },
            },
        },
    },
    {
        "name": "query_zones",
        "title": "Query Zones",
        "description": "Queries copper zones (filled pours) on the board with optional filters by net, layer, or bounding box. Returns one entry per zone with net, layers, priority, fill state, and bounding box. Useful for auditing power planes and GND pours, which 'query_traces' does not include.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "net": {
                    "type": "string",
                    "description": "Filter by net name (e.g., 'GND', '+3V3')",
                },
                "layer": {
                    "type": "string",
                    "description": "Filter by layer name (e.g., 'In1.Cu', 'B.Cu'). Matches zones that include this layer in their layer set.",
                },
                "boundingBox": {
                    "type": "object",
                    "description": "Filter to zones whose bounding box overlaps this region",
                    "properties": {
                        "x1": {"type": "number", "description": "Left X coordinate"},
                        "y1": {"type": "number", "description": "Top Y coordinate"},
                        "x2": {"type": "number", "description": "Right X coordinate"},
                        "y2": {"type": "number", "description": "Bottom Y coordinate"},
                        "unit": {
                            "type": "string",
                            "enum": ["mm", "inch"],
                            "default": "mm",
                        },
                    },
                },
            },
        },
    },
    {
        "name": "add_gnd_stitching_vias",
        "title": "Add GND Stitching Vias",
        "description": (
            "Drop GND stitching vias across the board with collision "
            "checking against every non-GND segment, via, and pad on "
            "every copper layer (PTH vias penetrate the full stackup, "
            "so missing one layer is the classic silent-short failure "
            "mode that other GND-stitching tools have). Combines three "
            "strategies: a regular `grid` across the interior, "
            "`around_refs` (densify around named ICs like an MCU or "
            "switching regulator), and `in_zones` (only place vias "
            "where they actually land on a GND copper zone so they "
            "stitch real polygons together rather than floating on "
            "silkscreen). Supports `dryRun` to preview placements "
            "without writing to the board. "
            "Approach ported from morningfire-pcb-automation "
            "(https://github.com/NiNjA-CodE/morningfire-pcb-automation, "
            "scripts/ground/add_gnd_vias.py); this version reads "
            "obstacles via the pcbnew API (handles rotation, picks up "
            "net classes, integrates with the live in-memory board) "
            "and adds the in-zones strategy + maxVias cap + dry-run."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "gndNet": {
                    "type": "string",
                    "description": (
                        "Name of the ground net (default: auto-detect "
                        "GND / GROUND / VSS / /GND)."
                    ),
                },
                "strategies": {
                    "type": "array",
                    "description": (
                        "Which placement strategies to combine (default: "
                        "['grid']). Pass ['grid', 'around_refs', "
                        "'in_zones'] for full coverage."
                    ),
                    "items": {
                        "type": "string",
                        "enum": ["grid", "around_refs", "in_zones"],
                    },
                },
                "viaSize": {
                    "type": "number",
                    "description": "Via pad diameter in mm (default 0.6).",
                    "default": 0.6,
                },
                "viaDrill": {
                    "type": "number",
                    "description": (
                        "Via drill diameter in mm (default 0.3). "
                        "Must be smaller than viaSize."
                    ),
                    "default": 0.3,
                },
                "clearance": {
                    "type": "number",
                    "description": (
                        "Extra clearance beyond required between each new "
                        "via and existing copper, in mm. Default 0.2."
                    ),
                    "default": 0.2,
                },
                "spacing": {
                    "type": "number",
                    "description": (
                        "Grid spacing in mm for the `grid` and "
                        "`around_refs` strategies. Default 5.0."
                    ),
                    "default": 5.0,
                },
                "densifyRefs": {
                    "type": "array",
                    "description": (
                        "Reference designators to densify ground around "
                        "(used by `around_refs` strategy). Good targets: "
                        "MCUs, switching regulators, RF parts."
                    ),
                    "items": {"type": "string"},
                },
                "densifyRadius": {
                    "type": "integer",
                    "description": (
                        "How many grid cells around each ref to try "
                        "(default 2 = 5x5 candidate field per ref)."
                    ),
                    "default": 2,
                },
                "edgeMargin": {
                    "type": "number",
                    "description": (
                        "Keep-out from the board edge in mm. Default 0.5."
                    ),
                    "default": 0.5,
                },
                "maxVias": {
                    "type": "integer",
                    "description": (
                        "Cap on total placements across all strategies "
                        "(default unlimited). Useful when iterating."
                    ),
                },
                "dryRun": {
                    "type": "boolean",
                    "description": (
                        "If true, return the placements that would be "
                        "made but don't modify the board. Default false."
                    ),
                    "default": False,
                },
            },
        },
    },
    {
        "name": "modify_trace",
        "title": "Modify Trace",
        "description": "Modifies properties of an existing trace. Find trace by UUID or position, then change width, layer, or net assignment.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "uuid": {
                    "type": "string",
                    "description": "UUID of the trace to modify",
                },
                "position": {
                    "type": "object",
                    "description": "Find trace nearest to this position",
                    "properties": {
                        "x": {"type": "number", "description": "X coordinate"},
                        "y": {"type": "number", "description": "Y coordinate"},
                        "unit": {
                            "type": "string",
                            "enum": ["mm", "mil", "inch"],
                            "default": "mm",
                        },
                    },
                    "required": ["x", "y"],
                },
                "width": {"type": "number", "description": "New trace width in mm"},
                "layer": {
                    "type": "string",
                    "description": "New layer name (e.g., 'F.Cu', 'B.Cu')",
                },
                "net": {"type": "string", "description": "New net name to assign"},
            },
        },
    },
    {
        "name": "copy_routing_pattern",
        "title": "Copy Routing Pattern",
        "description": "Copies routing pattern from source components to target components. Enables routing replication between identical component groups by calculating and applying position offset.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sourceRefs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Source component references (e.g., ['U1', 'U2', 'U3'])",
                },
                "targetRefs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Target component references (e.g., ['U4', 'U5', 'U6'])",
                },
                "includeVias": {
                    "type": "boolean",
                    "description": "Include vias in the pattern copy",
                    "default": True,
                },
                "traceWidth": {
                    "type": "number",
                    "description": "Override trace width in mm (uses original if not specified)",
                },
            },
            "required": ["sourceRefs", "targetRefs"],
        },
    },
    {
        "name": "get_nets_list",
        "title": "List All Nets",
        "description": "Returns a list of all electrical nets defined on the board.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "create_netclass",
        "title": "Create Net Class",
        "description": "Defines a net class with specific routing rules (trace width, clearance, etc.).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Net class name",
                    "minLength": 1,
                },
                "traceWidth": {
                    "type": "number",
                    "description": "Default trace width in millimeters",
                    "minimum": 0.1,
                },
                "clearance": {
                    "type": "number",
                    "description": "Clearance in millimeters",
                    "minimum": 0.1,
                },
                "viaDiameter": {
                    "type": "number",
                    "description": "Via diameter in millimeters",
                },
                "viaDrill": {
                    "type": "number",
                    "description": "Via drill diameter in millimeters",
                },
            },
            "required": ["name", "traceWidth", "clearance"],
        },
    },
    {
        "name": "add_copper_pour",
        "title": "Add Copper Pour",
        "description": "Creates a copper pour/zone (typically for ground or power planes).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "netName": {
                    "type": "string",
                    "description": "Net to connect this copper pour to (e.g., GND, VCC)",
                },
                "layer": {
                    "type": "string",
                    "description": "Layer for the copper pour (e.g., F.Cu, B.Cu)",
                },
                "priority": {
                    "type": "integer",
                    "description": "Pour priority (higher priorities fill first)",
                    "minimum": 0,
                    "default": 0,
                },
                "clearance": {
                    "type": "number",
                    "description": "Clearance from other objects in millimeters",
                    "minimum": 0.1,
                },
                "outline": {
                    "type": "array",
                    "description": "Array of [x, y] points defining the pour boundary",
                    "items": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 2,
                        "maxItems": 2,
                    },
                    "minItems": 3,
                },
            },
            "required": ["netName", "layer", "outline"],
        },
    },
    {
        "name": "route_differential_pair",
        "title": "Route Differential Pair",
        "description": "Routes a differential signal pair with matched lengths and spacing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "positiveName": {
                    "type": "string",
                    "description": "Positive signal net name",
                },
                "negativeName": {
                    "type": "string",
                    "description": "Negative signal net name",
                },
                "layer": {"type": "string", "description": "Layer to route on"},
                "width": {
                    "type": "number",
                    "description": "Trace width in millimeters",
                },
                "gap": {
                    "type": "number",
                    "description": "Gap between traces in millimeters",
                },
                "points": {
                    "type": "array",
                    "description": "Waypoints for the pair routing",
                    "items": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 2,
                        "maxItems": 2,
                    },
                    "minItems": 2,
                },
            },
            "required": ["positiveName", "negativeName", "width", "gap", "points"],
        },
    },
]

# =============================================================================
# LIBRARY TOOLS
# =============================================================================

LIBRARY_TOOLS = [
    {
        "name": "list_libraries",
        "title": "List Footprint Libraries",
        "description": "Lists all available footprint libraries accessible to KiCAD.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "search_footprints",
        "title": "Search Footprints",
        "description": "Searches for footprints matching a query string across all libraries.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (e.g., '0805', 'SOIC', 'QFP')",
                    "minLength": 1,
                },
                "library": {
                    "type": "string",
                    "description": "Optional library to restrict search to",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_library_footprints",
        "title": "List Footprints in Library",
        "description": "Lists all footprints available in a specific library.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "library": {
                    "type": "string",
                    "description": "Library name (e.g., Resistor_SMD, Connector_PinHeader)",
                    "minLength": 1,
                }
            },
            "required": ["library"],
        },
    },
    {
        "name": "get_footprint_info",
        "title": "Get Footprint Details",
        "description": "Retrieves detailed information about a specific footprint including pad layout, dimensions, and description.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "library": {"type": "string", "description": "Library name"},
                "footprint": {"type": "string", "description": "Footprint name"},
            },
            "required": ["library", "footprint"],
        },
    },
]

# =============================================================================
# DESIGN RULE TOOLS
# =============================================================================

DESIGN_RULE_TOOLS = [
    {
        "name": "set_design_rules",
        "title": "Set Design Rules",
        "description": "Configures board design rules including clearances, trace widths, and via sizes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "clearance": {
                    "type": "number",
                    "description": "Minimum clearance between copper in millimeters",
                    "minimum": 0.1,
                },
                "trackWidth": {
                    "type": "number",
                    "description": "Minimum track width in millimeters",
                    "minimum": 0.1,
                },
                "viaDiameter": {
                    "type": "number",
                    "description": "Minimum via diameter in millimeters",
                },
                "viaDrill": {
                    "type": "number",
                    "description": "Minimum via drill diameter in millimeters",
                },
                "microViaD iameter": {
                    "type": "number",
                    "description": "Minimum micro-via diameter in millimeters",
                },
            },
        },
    },
    {
        "name": "get_design_rules",
        "title": "Get Current Design Rules",
        "description": "Retrieves the currently configured design rules from the board.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "run_drc",
        "title": "Run Design Rule Check",
        "description": "Executes a design rule check (DRC) on the current board and reports violations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "includeWarnings": {
                    "type": "boolean",
                    "description": "Include warnings in addition to errors",
                    "default": True,
                }
            },
        },
    },
    {
        "name": "get_drc_violations",
        "title": "Get DRC Violations",
        "description": "Returns a list of design rule violations from the most recent DRC run.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

# =============================================================================
# EXPORT TOOLS
# =============================================================================

EXPORT_TOOLS = [
    {
        "name": "export_gerber",
        "title": "Export Gerber Files",
        "description": "Generates Gerber files for PCB fabrication (industry standard format).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "outputPath": {
                    "type": "string",
                    "description": "Directory path for output files",
                },
                "layers": {
                    "type": "array",
                    "description": "List of layers to export (if not provided, exports all copper and mask layers)",
                    "items": {"type": "string"},
                },
                "includeDrillFiles": {
                    "type": "boolean",
                    "description": "Include drill files (Excellon format)",
                    "default": True,
                },
            },
            "required": ["outputPath"],
        },
    },
    {
        "name": "export_pdf",
        "title": "Export PDF",
        "description": "Exports the board layout as a PDF document for documentation or review.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "outputPath": {
                    "type": "string",
                    "description": "Path for output PDF file",
                },
                "layers": {
                    "type": "array",
                    "description": "Layers to include in PDF",
                    "items": {"type": "string"},
                },
                "colorMode": {
                    "type": "string",
                    "enum": ["color", "black_white"],
                    "description": "Color mode for output",
                    "default": "color",
                },
            },
            "required": ["outputPath"],
        },
    },
    {
        "name": "export_svg",
        "title": "Export SVG",
        "description": "Exports the board as Scalable Vector Graphics for documentation or web display.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "outputPath": {
                    "type": "string",
                    "description": "Path for output SVG file",
                },
                "layers": {
                    "type": "array",
                    "description": "Layers to include in SVG",
                    "items": {"type": "string"},
                },
            },
            "required": ["outputPath"],
        },
    },
    {
        "name": "export_3d",
        "title": "Export 3D Model",
        "description": "Exports a 3D model of the board in STEP or VRML format for mechanical CAD integration.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "outputPath": {
                    "type": "string",
                    "description": "Path for output 3D file",
                },
                "format": {
                    "type": "string",
                    "enum": ["step", "vrml"],
                    "description": "3D model format",
                    "default": "step",
                },
                "includeComponents": {
                    "type": "boolean",
                    "description": "Include 3D component models",
                    "default": True,
                },
            },
            "required": ["outputPath"],
        },
    },
    {
        "name": "export_bom",
        "title": "Export Bill of Materials",
        "description": "Generates a bill of materials (BOM) listing all components with references, values, and footprints.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "outputPath": {
                    "type": "string",
                    "description": "Path for output BOM file",
                },
                "format": {
                    "type": "string",
                    "enum": ["csv", "xml", "html"],
                    "description": "BOM output format",
                    "default": "csv",
                },
                "groupByValue": {
                    "type": "boolean",
                    "description": "Group components with same value together",
                    "default": True,
                },
            },
            "required": ["outputPath"],
        },
    },
]

# =============================================================================
# SCHEMATIC TOOLS
# =============================================================================

SCHEMATIC_TOOLS = [
    {
        "name": "create_schematic",
        "title": "Create New Schematic",
        "description": "Creates a new KiCAD schematic file for circuit design.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Path for the new schematic file (.kicad_sch)",
                },
                "title": {"type": "string", "description": "Schematic title"},
            },
            "required": ["filename"],
        },
    },

    {
        "name": "add_schematic_component",
        "title": "Add Component to Schematic",
        "description": (
            "Places a symbol (resistor, capacitor, IC, etc.) on the schematic. "
            "x and y are OPTIONAL — omit them to let optimize_schematic auto-place the "
            "component. Preferred workflow: add all components (no coords), queue all "
            "connections with add_schematic_wire, then call optimize_schematic once to "
            "auto-layout and route everything."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {
                    "type": "string",
                    "description": "Reference designator (e.g., R1, C2, U3)",
                },
                "symbol": {
                    "type": "string",
                    "description": "Symbol library:name (e.g., Device:R, Device:C)",
                },
                "value": {
                    "type": "string",
                    "description": "Component value (e.g., 10k, 0.1uF)",
                },
                "x": {
                    "type": "number",
                    "description": "X coordinate on schematic. Omit to auto-place via optimize_schematic.",
                },
                "y": {
                    "type": "number",
                    "description": "Y coordinate on schematic. Omit to auto-place via optimize_schematic.",
                },
                "orientation": {
                    "type": "number",
                    "description": "Rotation angle in degrees (0, 90, 180, 270). Default 0.",
                    "default": 0,
                },
            },
            "required": ["reference", "symbol"],
        },
    },
    {
        "name": "add_schematic_wire",
        "title": "Queue Wire Connection Between Pins",
        "description": (
            "Queue a wire connection between two schematic pins for later batch routing. "
            "PREFERRED: use fromRef/fromPin/toRef/toPin — stores the connection and returns "
            "queued:true. Call optimize_schematic afterwards to route all queued connections "
            "at once with global layout awareness. "
            "Example: {fromRef:'R1', fromPin:'2', toRef:'R2', toPin:'1'}. "
            "ALTERNATIVE: supply raw 'waypoints' [[x1,y1],[x2,y2],...] to draw immediately "
            "(bypasses queuing, useful for manual precise wiring). "
            "Pin references accept pin numbers ('1','2') or pin names ('GND','VCC','SDA')."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "schematicPath": {
                    "type": "string",
                    "description": "Path to schematic file",
                },
                "fromRef": {
                    "type": "string",
                    "description": "Reference designator of the source component (e.g. 'R1', 'U1'). Use with fromPin/toRef/toPin instead of waypoints.",
                },
                "fromPin": {
                    "type": ["string", "number"],
                    "description": "Pin number or name on the source component (e.g. '1', '2', 'GND', 'OUT').",
                },
                "toRef": {
                    "type": "string",
                    "description": "Reference designator of the destination component.",
                },
                "toPin": {
                    "type": ["string", "number"],
                    "description": "Pin number or name on the destination component.",
                },
                "via": {
                    "type": "array",
                    "description": "Optional intermediate [x,y] waypoints for routing around obstacles when using fromRef/toRef mode. E.g. [[xMid,y1],[xMid,y2]] creates an L-bend.",
                    "items": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 2,
                        "maxItems": 2,
                    },
                },
                "waypoints": {
                    "type": "array",
                    "description": "Alternative to fromRef/toRef: explicit [x,y] coordinates defining the wire path (at least 2 points). Use get_schematic_pin_locations to look up coordinates first.",
                    "items": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 2,
                        "maxItems": 2,
                    },
                    "minItems": 2,
                },
            },
            "required": ["schematicPath"],
        },
    },
    {
        "name": "optimize_schematic",
        "title": "Route All Pending Wire Connections",
        "description": (
            "Route all wire connections queued by add_schematic_wire in one global pass. "
            "Reads the pending connections sidecar, resolves all pin positions and exit angles, "
            "sorts by distance (short first), then routes every connection with direction-aware "
            "Manhattan routing and writes them all to the schematic at once. "
            "Call this after queuing all your add_schematic_wire connections."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "schematicPath": {
                    "type": "string",
                    "description": "Path to schematic file",
                },
                "clearPending": {
                    "type": "boolean",
                    "default": True,
                    "description": "Clear the pending connections sidecar after routing (default true).",
                },
            },
            "required": ["schematicPath"],
        },
    },
    {
        "name": "add_schematic_net_label",
        "title": "Add Net Label",
        "description": (
            "Add a net label to a schematic. "
            "PREFERRED: supply componentRef + pinNumber to snap the label to the exact pin endpoint — "
            "this guarantees an electrical connection. "
            "Alternatively supply position [x, y], but the coordinates must match the pin endpoint exactly "
            "(even a 0.01 mm offset breaks the connection). "
            "The response includes actual_position (coordinates actually used) and snapped_to_pin "
            "(present when a pin reference was resolved)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "schematicPath": {
                    "type": "string",
                    "description": "Path to schematic file",
                },
                "netName": {
                    "type": "string",
                    "description": "Name of the net (e.g., VCC, GND, SDA)",
                },
                "position": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 2,
                    "maxItems": 2,
                    "description": "Position [x, y] for the label. Required when componentRef/pinNumber are not given.",
                },
                "componentRef": {
                    "type": "string",
                    "description": "Component reference to snap label to (e.g. U1, R1). Use with pinNumber.",
                },
                "pinNumber": {
                    "type": "string",
                    "description": "Pin number or name on componentRef (e.g. '1', 'GND'). Use with componentRef.",
                },
                "labelType": {
                    "type": "string",
                    "enum": ["label", "global_label", "hierarchical_label"],
                    "description": "Label type (default: label)",
                    "default": "label",
                },
                "orientation": {
                    "type": "number",
                    "description": "Rotation angle in degrees (0, 90, 180, 270)",
                    "default": 0,
                },
            },
            "required": ["schematicPath", "netName"],
        },
    },
    {
        "name": "add_schematic_power_symbol",
        "title": "Add Power Symbol",
        "description": (
            "Place a KiCad power symbol (VCC, GND, +3V3, +5V, etc.) on the schematic. "
            "PREFERRED: use componentRef + pinNumber to snap directly to a pin. "
            "Power symbols create proper net connections — use these instead of net labels for power rails. "
            "Do NOT specify orientation — direction is determined automatically from the net name "
            "(VCC/supply symbols point away from pin upward; GND symbols point away downward)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "schematicPath": {"type": "string", "description": "Path to schematic file"},
                "netName": {"type": "string", "description": "Power net name (e.g. VCC, GND, +3V3, +5V, VBAT)"},
                "componentRef": {"type": "string", "description": "Snap to this component's pin (e.g. U1). Use with pinNumber."},
                "pinNumber": {"type": ["string", "number"], "description": "Pin number or name to snap to."},
                "position": {
                    "type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2,
                    "description": "[x, y] position. Required if componentRef/pinNumber not given."
                },
                "orientation": {
                    "type": "number", "default": 0,
                    "description": "Ignored — direction is auto-determined from netName. Do not set."
                },
            },
            "required": ["netName"],
        },
    },
    {
        "name": "connect_to_net",
        "title": "Connect Pin to Net",
        "description": (
            "Connect a component pin to a named net by adding a wire stub and net label at the exact "
            "pin endpoint. The response includes pin_location (exact pin coords), label_location "
            "(where the label was placed), and wire_stub (the wire segment added) so you can confirm "
            "the placement without a separate verification call."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "schematicPath": {
                    "type": "string",
                    "description": "Path to schematic file",
                },
                "componentRef": {
                    "type": "string",
                    "description": "Component reference designator (e.g., R1, U3)",
                },
                "pinName": {
                    "type": "string",
                    "description": "Pin number or name on the component",
                },
                "netName": {
                    "type": "string",
                    "description": "Name of the net to connect to",
                },
            },
            "required": ["schematicPath", "componentRef", "pinName", "netName"],
        },
    },
    {
        "name": "get_net_connections",
        "title": "Get Net Connections",
        "description": "Returns all components and pins connected to a specified net.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "schematicPath": {
                    "type": "string",
                    "description": "Path to schematic file",
                },
                "netName": {
                    "type": "string",
                    "description": "Name of the net to query",
                },
            },
            "required": ["schematicPath", "netName"],
        },
    },
    {
        "name": "get_wire_connections",
        "title": "Get Wire Connections",
        "description": (
            "Returns the net name and all wires and component pins connected at a given point. "
            "Accepts either a component reference + pin number (e.g. reference='U1', pin='3') "
            "or a schematic coordinate (x, y in mm). "
            "The response includes: 'net' (label name or null for unnamed nets), "
            "'pins' (all component pins on the net), 'wires' (all wire segments on the net), "
            "and 'query_point' (the resolved coordinate used). "
            "The query point must be at a wire endpoint or junction — wire midpoints are not matched. "
            "Use get_schematic_pin_locations or list_schematic_wires to obtain exact endpoint coordinates."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "schematicPath": {
                    "type": "string",
                    "description": "Path to the schematic file (.kicad_sch)",
                },
                "reference": {
                    "type": "string",
                    "description": "Component reference (e.g. U1, R1). Pair with pin.",
                },
                "pin": {
                    "type": "string",
                    "description": "Pin number or name (e.g. '3', 'SDA'). Pair with reference.",
                },
                "x": {
                    "type": "number",
                    "description": "X coordinate of a wire endpoint in mm. Pair with y.",
                },
                "y": {
                    "type": "number",
                    "description": "Y coordinate of a wire endpoint in mm. Pair with x.",
                },
            },
            "required": ["schematicPath"],
        },
    },
    {
        "name": "get_net_at_point",
        "title": "Get Net At Point",
        "description": (
            "Returns the net name at a given (x, y) coordinate in a schematic, "
            "or null if no net label or wire endpoint is present at that position. "
            "Checks net label positions first, then wire endpoints. "
            "Useful for quickly identifying what net occupies a specific coordinate "
            "without traversing the full wire graph."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "schematicPath": {
                    "type": "string",
                    "description": "Path to the schematic file (.kicad_sch)",
                },
                "x": {
                    "type": "number",
                    "description": "X coordinate in mm",
                },
                "y": {
                    "type": "number",
                    "description": "Y coordinate in mm",
                },
            },
            "required": ["schematicPath", "x", "y"],
        },
    },
    {
        "name": "get_schematic_pin_locations",
        "title": "Get Schematic Pin Locations",
        "description": "Returns the exact absolute coordinates of all pins on a schematic component. Use this BEFORE placing net labels with add_schematic_net_label to get the correct x/y position for each pin endpoint.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "schematicPath": {
                    "type": "string",
                    "description": "Path to the schematic file",
                },
                "reference": {
                    "type": "string",
                    "description": "Component reference designator (e.g., U1, R1, J2)",
                },
            },
            "required": ["schematicPath", "reference"],
        },
    },
    {
        "name": "connect_passthrough",
        "title": "Connect Passthrough (Pin-to-Pin)",
        "description": "Connects all pins of a source connector to the matching pins of a target connector using shared net labels. Ideal for passthrough adapters where J1 pin N connects directly to J2 pin N. Each pair gets a net label '{netPrefix}_{pinNumber}'. Use this instead of calling connect_to_net 15 times for FFC/ribbon cable passthroughs. NOTE: KiCAD Connector_Generic symbols always have pin 1 at the TOP of the symbol and pin N at the BOTTOM. When assigning named nets (e.g. GND, CAM_SCL) to specific pin numbers, always use the physical pin number as shown in the connector datasheet — pin 1 = top of symbol.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "schematicPath": {
                    "type": "string",
                    "description": "Path to the schematic file",
                },
                "sourceRef": {
                    "type": "string",
                    "description": "Reference of the source connector (e.g., J1)",
                },
                "targetRef": {
                    "type": "string",
                    "description": "Reference of the target connector (e.g., J2)",
                },
                "netPrefix": {
                    "type": "string",
                    "description": "Prefix for generated net names, e.g. 'CSI' produces CSI_1, CSI_2, ... (default: PIN)",
                },
                "pinOffset": {
                    "type": "integer",
                    "description": "Add this value to the pin number when building net names (default: 0)",
                },
            },
            "required": ["schematicPath", "sourceRef", "targetRef"],
        },
    },
    {
        "name": "run_erc",
        "title": "Run Electrical Rules Check (ERC)",
        "description": "Runs the KiCAD Electrical Rules Check (ERC) on a schematic via kicad-cli and returns all violations with type, severity, and location. Use this to verify the schematic is electrically correct before generating a netlist or exporting.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "schematicPath": {
                    "type": "string",
                    "description": "Path to the .kicad_sch schematic file",
                }
            },
            "required": ["schematicPath"],
        },
    },
    {
        "name": "sync_schematic_to_board",
        "title": "Sync Schematic to PCB (F8)",
        "description": "Reads net connections from the schematic and assigns them to matching component pads in the PCB board file. Equivalent to KiCAD Pcbnew F8 'Update PCB from Schematic'. Must be called after placing components and before routing traces, so that pad-to-net assignments are correct.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "schematicPath": {
                    "type": "string",
                    "description": "Path to .kicad_sch file. If omitted, auto-detected from current board path.",
                },
                "boardPath": {
                    "type": "string",
                    "description": "Path to .kicad_pcb file. If omitted, uses currently loaded board.",
                },
            },
        },
    },
    {
        "name": "generate_netlist",
        "title": "Generate Netlist (JSON)",
        "description": (
            "Returns a structured JSON netlist from the schematic: component list "
            "(reference, value, footprint) and net list (net name + all connected "
            "component/pin pairs). Uses kicad-cli internally — requires a saved "
            ".kicad_sch file. For writing to a file or exporting SPICE/Cadstar/OrcadPCB2 "
            "format, use export_netlist instead."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "schematicPath": {
                    "type": "string",
                    "description": "Absolute path to the .kicad_sch schematic file",
                },
            },
            "required": ["schematicPath"],
        },
    },
    {
        "name": "export_schematic_pdf",
        "title": "Export Schematic to PDF",
        "description": "Exports the schematic as a PDF document for printing or documentation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "schematicPath": {
                    "type": "string",
                    "description": "Path to schematic file",
                },
                "outputPath": {"type": "string", "description": "Path for output PDF"},
            },
            "required": ["schematicPath", "outputPath"],
        },
    },
    # --- Schematic Analysis Tools (read-only) ---
    {
        "name": "get_schematic_view_region",
        "title": "Get Schematic View Region",
        "description": "Exports a cropped region of the schematic as an image (PNG or SVG). Specify a bounding box in schematic mm coordinates to zoom into a specific area.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "schematicPath": {
                    "type": "string",
                    "description": "Path to the .kicad_sch schematic file",
                },
                "x1": {
                    "type": "number",
                    "description": "Left X coordinate of the region in mm",
                },
                "y1": {
                    "type": "number",
                    "description": "Top Y coordinate of the region in mm",
                },
                "x2": {
                    "type": "number",
                    "description": "Right X coordinate of the region in mm",
                },
                "y2": {
                    "type": "number",
                    "description": "Bottom Y coordinate of the region in mm",
                },
                "format": {
                    "type": "string",
                    "enum": ["png", "svg"],
                    "description": "Output image format (default: png)",
                },
                "width": {
                    "type": "integer",
                    "description": "Output image width in pixels (default: 800)",
                },
                "height": {
                    "type": "integer",
                    "description": "Output image height in pixels (default: 600)",
                },
            },
            "required": ["schematicPath", "x1", "y1", "x2", "y2"],
        },
    },
    {
        "name": "find_overlapping_elements",
        "title": "Find Overlapping Elements",
        "description": "Detects spatially overlapping symbols, wires, and labels in the schematic. Finds: duplicate power symbols at the same position, collinear overlapping wire segments, and labels stacked on top of each other.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "schematicPath": {
                    "type": "string",
                    "description": "Path to the .kicad_sch schematic file",
                },
                "tolerance": {
                    "type": "number",
                    "description": "Distance threshold in mm for label proximity and wire collinearity checks. Symbol overlap uses bounding-box intersection. (default: 0.5)",
                },
            },
            "required": ["schematicPath"],
        },
    },
    {
        "name": "get_elements_in_region",
        "title": "Get Elements in Region",
        "description": "Lists all symbols, wires, and labels within a rectangular region of the schematic. Useful for understanding what is in a specific area before modifying it.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "schematicPath": {
                    "type": "string",
                    "description": "Path to the .kicad_sch schematic file",
                },
                "x1": {
                    "type": "number",
                    "description": "Left X coordinate of the region in mm",
                },
                "y1": {
                    "type": "number",
                    "description": "Top Y coordinate of the region in mm",
                },
                "x2": {
                    "type": "number",
                    "description": "Right X coordinate of the region in mm",
                },
                "y2": {
                    "type": "number",
                    "description": "Bottom Y coordinate of the region in mm",
                },
            },
            "required": ["schematicPath", "x1", "y1", "x2", "y2"],
        },
    },
    {
        "name": "find_wires_crossing_symbols",
        "title": "Find Wires Crossing Symbols",
        "description": "Find all wires that cross over component symbol bodies. Wires passing over symbols are unacceptable in schematics — they indicate routing mistakes where a wire was drawn across a component instead of around it.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "schematicPath": {
                    "type": "string",
                    "description": "Path to the .kicad_sch schematic file",
                }
            },
            "required": ["schematicPath"],
        },
    },
    {
        "name": "find_orphaned_wires",
        "title": "Find Orphaned Wires",
        "description": (
            "Find wire segments with at least one dangling endpoint — an endpoint not connected "
            "to a component pin, net label, or another wire. "
            "Orphaned wires cause ERC 'wire end unconnected' errors and indicate routing mistakes. "
            "Does not require the KiCad UI to be running."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "schematicPath": {
                    "type": "string",
                    "description": "Path to the .kicad_sch schematic file",
                }
            },
            "required": ["schematicPath"],
        },
    },
    {
        "name": "list_floating_labels",
        "title": "List Floating Net Labels",
        "description": (
            "Returns all net labels in the schematic that are not connected to any component pin. "
            "A label is 'floating' when no component pin's coordinate falls on the wire-network "
            "reachable from the label's anchor position. "
            "Floating labels indicate misplaced or off-grid labels that will cause ERC errors. "
            "Does not require the KiCad UI to be running."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "schematicPath": {
                    "type": "string",
                    "description": "Path to the .kicad_sch schematic file",
                }
            },
            "required": ["schematicPath"],
        },
    },
    {
        "name": "snap_to_grid",
        "title": "Snap Schematic Elements to Grid",
        "description": (
            "Snap schematic element coordinates to the nearest grid point. "
            "KiCAD eeschema uses exact integer matching (10 000 IU/mm) for connectivity, "
            "so even a sub-pixel coordinate offset will make wires appear connected visually "
            "but fail ERC checks. Running this tool before ERC eliminates that class of error. "
            "Modifies the .kicad_sch file in place. "
            "Does not require the KiCAD UI to be running."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "schematicPath": {
                    "type": "string",
                    "description": "Path to the .kicad_sch schematic file",
                },
                "gridSize": {
                    "type": "number",
                    "description": (
                        "Grid spacing in mm (default: 1.27 — standard KiCAD schematic grid). "
                        "Do NOT use 2.54: half of all valid KiCAD pin positions are at odd "
                        "multiples of 1.27 mm and would be displaced 1.27 mm, breaking "
                        "connectivity."
                    ),
                    "default": 1.27,
                },
                "elements": {
                    "type": "array",
                    "description": (
                        "Element types to snap. "
                        'Valid values: "wires", "junctions", "labels", "components". '
                        'Defaults to ["wires", "junctions", "labels"] when omitted. '
                        '"components" is opt-in because moving a component without re-routing '
                        "its wires will create new mismatches."
                    ),
                    "items": {
                        "type": "string",
                        "enum": ["wires", "junctions", "labels", "components"],
                    },
                },
            },
            "required": ["schematicPath"],
        },
    },
]

# =============================================================================
# UI/PROCESS TOOLS
# =============================================================================

UI_TOOLS = [
    {
        "name": "get_backend_state",
        "title": "Get Backend State",
        "description": ("Returns backend, realtime, loaded project/board paths, and dirty state."),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "check_kicad_ui",
        "title": "Check KiCAD UI Status",
        "description": "Checks if KiCAD user interface is currently running and returns process information.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "launch_kicad_ui",
        "title": "Launch KiCAD Application",
        "description": "Opens the KiCAD graphical user interface, optionally with a specific project loaded.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "projectPath": {
                    "type": "string",
                    "description": "Optional path to project file to open in UI",
                },
                "autoLaunch": {
                    "type": "boolean",
                    "description": "Whether to automatically launch if not running",
                    "default": True,
                },
            },
        },
    },
]

# =============================================================================
# ADDITIONAL TOOLS  (missing from original copy – brings total to 142)
# =============================================================================

ADDITIONAL_TOOLS: List[Dict[str, Any]] = [
    # ------------------------------------------------------------------
    # Schematic tools missing from SCHEMATIC_TOOLS above
    # ------------------------------------------------------------------
    {
        "name": "add_no_connect",
        "title": "Add No-Connect Marker",
        "description": "Add a no-connect marker to an unconnected pin in the schematic.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "x": {"type": "number", "description": "X coordinate"},
                "y": {"type": "number", "description": "Y coordinate"},
            },
            "required": ["x", "y"],
        },
    },
    {
        "name": "add_schematic_hierarchical_label",
        "title": "Add Hierarchical Label",
        "description": "Add a hierarchical label to the schematic for sheet connections.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Label text"},
                "x": {"type": "number", "description": "X coordinate"},
                "y": {"type": "number", "description": "Y coordinate"},
                "shape": {
                    "type": "string",
                    "enum": ["input", "output", "bidirectional", "tri_state", "passive"],
                    "description": "Label shape/type",
                },
                "rotation": {"type": "number", "description": "Rotation angle in degrees"},
            },
            "required": ["text", "x", "y"],
        },
    },
    {
        "name": "add_schematic_text",
        "title": "Add Schematic Text",
        "description": "Add a text annotation to the schematic.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text content"},
                "x": {"type": "number", "description": "X coordinate"},
                "y": {"type": "number", "description": "Y coordinate"},
                "size": {"type": "number", "description": "Text size"},
                "rotation": {"type": "number", "description": "Rotation angle in degrees"},
            },
            "required": ["text", "x", "y"],
        },
    },
    {
        "name": "add_sheet_pin",
        "title": "Add Sheet Pin",
        "description": "Add a pin connection to a hierarchical sheet symbol.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sheetId": {"type": "string", "description": "Sheet identifier"},
                "pinName": {"type": "string", "description": "Pin name matching a hierarchical label in the sub-sheet"},
                "side": {
                    "type": "string",
                    "enum": ["left", "right", "top", "bottom"],
                    "description": "Side of the sheet to place the pin",
                },
                "x": {"type": "number", "description": "X position override"},
                "y": {"type": "number", "description": "Y position override"},
            },
            "required": ["sheetId", "pinName"],
        },
    },
    {
        "name": "annotate_schematic",
        "title": "Annotate Schematic",
        "description": "Automatically assign reference designators to all un-annotated components.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "startNumber": {"type": "number", "description": "Starting reference number"},
                "order": {
                    "type": "string",
                    "enum": ["x_position", "y_position", "value"],
                    "description": "Sort order for annotation",
                },
                "clearExisting": {"type": "boolean", "description": "Clear existing annotations first"},
            },
        },
    },
    {
        "name": "delete_schematic_component",
        "title": "Delete Schematic Component",
        "description": "Delete a component/symbol from the schematic.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "Component reference designator (e.g. R1, C3)"},
            },
            "required": ["reference"],
        },
    },
    {
        "name": "delete_schematic_net_label",
        "title": "Delete Schematic Net Label",
        "description": "Delete a net label from the schematic.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "labelId": {"type": "string", "description": "Unique identifier of the label to delete"},
            },
            "required": ["labelId"],
        },
    },
    {
        "name": "delete_schematic_wire",
        "title": "Delete Schematic Wire",
        "description": "Delete a wire segment from the schematic. Provide wireId (UUID from add_schematic_wire response or list_schematic_wires) OR start+end coordinates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "schematicPath": {"type": "string", "description": "Path to schematic file"},
                "wireId": {"type": "string", "description": "UUID of the wire to delete (from prior wire response)"},
                "start": {
                    "type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2,
                    "description": "[x, y] start point of wire (alternative to wireId)"
                },
                "end": {
                    "type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2,
                    "description": "[x, y] end point of wire (alternative to wireId)"
                },
            },
            "required": [],
        },
    },
    {
        "name": "edit_schematic_component",
        "title": "Edit Schematic Component",
        "description": "Edit properties of an existing schematic component.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "Component reference designator"},
                "value": {"type": "string", "description": "New value"},
                "footprint": {"type": "string", "description": "New footprint"},
                "datasheet": {"type": "string", "description": "New datasheet URL"},
                "fields": {
                    "type": "object",
                    "description": "Additional fields as key-value pairs",
                },
            },
            "required": ["reference"],
        },
    },
    {
        "name": "get_schematic_component",
        "title": "Get Schematic Component",
        "description": "Get detailed information about a specific schematic component.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "Component reference designator"},
            },
            "required": ["reference"],
        },
    },
    {
        "name": "get_schematic_view",
        "title": "Get Schematic View",
        "description": "Render a 2D image of the current schematic and return it as PNG or SVG.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "format": {"type": "string", "enum": ["png", "svg"], "description": "Image format"},
                "width": {"type": "number", "description": "Image width in pixels"},
                "height": {"type": "number", "description": "Image height in pixels"},
                "responseMode": {
                    "type": "string",
                    "enum": ["inline", "file"],
                    "description": "inline returns base64; file writes to disk",
                },
            },
        },
    },
    {
        "name": "list_schematic_components",
        "title": "List Schematic Components",
        "description": "List all components/symbols placed in the schematic.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filter": {"type": "string", "description": "Optional filter by reference prefix (e.g. R, C, U)"},
            },
        },
    },
    {
        "name": "list_schematic_labels",
        "title": "List Schematic Labels",
        "description": "List all net labels in the schematic.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "list_schematic_nets",
        "title": "List Schematic Nets",
        "description": "List all nets defined in the schematic.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "list_schematic_texts",
        "title": "List Schematic Texts",
        "description": "List all text annotations in the schematic.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "list_schematic_wires",
        "title": "List Schematic Wires",
        "description": "List all wire segments in the schematic.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "move_schematic_component",
        "title": "Move Schematic Component",
        "description": "Move a schematic component to a new position.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "Component reference designator"},
                "x": {"type": "number", "description": "New X coordinate"},
                "y": {"type": "number", "description": "New Y coordinate"},
            },
            "required": ["reference", "x", "y"],
        },
    },
    {
        "name": "move_schematic_net_label",
        "title": "Move Schematic Net Label",
        "description": "Move a net label to a new position in the schematic.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "labelId": {"type": "string", "description": "Unique identifier of the label"},
                "x": {"type": "number", "description": "New X coordinate"},
                "y": {"type": "number", "description": "New Y coordinate"},
            },
            "required": ["labelId", "x", "y"],
        },
    },
    {
        "name": "remove_schematic_component_property",
        "title": "Remove Schematic Component Property",
        "description": "Remove a custom property/field from a schematic component.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "Component reference designator"},
                "propertyName": {"type": "string", "description": "Name of the property to remove"},
            },
            "required": ["reference", "propertyName"],
        },
    },
    {
        "name": "rotate_schematic_component",
        "title": "Rotate Schematic Component",
        "description": "Rotate a schematic component by a specified angle.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "Component reference designator"},
                "angle": {"type": "number", "description": "Rotation angle in degrees"},
            },
            "required": ["reference", "angle"],
        },
    },
    {
        "name": "set_schematic_component_property",
        "title": "Set Schematic Component Property",
        "description": "Set or update a property/field on a schematic component.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "Component reference designator"},
                "propertyName": {"type": "string", "description": "Property name"},
                "value": {"type": "string", "description": "Property value"},
            },
            "required": ["reference", "propertyName", "value"],
        },
    },
    {
        "name": "export_schematic_svg",
        "title": "Export Schematic to SVG",
        "description": "Export the schematic as an SVG file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "outputPath": {"type": "string", "description": "Path to write the SVG file"},
                "colorTheme": {"type": "string", "description": "Color theme name"},
            },
        },
    },
    # ------------------------------------------------------------------
    # Symbol/Library tools
    # ------------------------------------------------------------------
    {
        "name": "list_symbol_libraries",
        "title": "List Symbol Libraries",
        "description": "List all available KiCAD symbol libraries.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "searchPaths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional extra paths to search",
                },
            },
        },
    },
    {
        "name": "search_symbols",
        "title": "Search Symbols",
        "description": "Search for symbols across all loaded KiCAD symbol libraries.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "library": {"type": "string", "description": "Restrict search to a specific library"},
                "limit": {"type": "number", "description": "Maximum number of results"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_library_symbols",
        "title": "List Library Symbols",
        "description": "List all symbols in a specific symbol library.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "library": {"type": "string", "description": "Library name"},
            },
            "required": ["library"],
        },
    },
    {
        "name": "get_symbol_info",
        "title": "Get Symbol Info",
        "description": "Get detailed information about a specific symbol.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "library": {"type": "string", "description": "Library name"},
                "symbol": {"type": "string", "description": "Symbol name"},
            },
            "required": ["library", "symbol"],
        },
    },
    {
        "name": "create_footprint",
        "title": "Create Footprint",
        "description": "Create a new footprint in a footprint library.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "library": {"type": "string", "description": "Library name"},
                "name": {"type": "string", "description": "Footprint name"},
                "description": {"type": "string", "description": "Footprint description"},
                "tags": {"type": "string", "description": "Space-separated tags"},
            },
            "required": ["library", "name"],
        },
    },
    {
        "name": "edit_footprint_pad",
        "title": "Edit Footprint Pad",
        "description": "Edit an existing pad within a footprint.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "library": {"type": "string", "description": "Library name"},
                "footprint": {"type": "string", "description": "Footprint name"},
                "padNumber": {"type": "string", "description": "Pad number/name"},
                "x": {"type": "number", "description": "X position in mm"},
                "y": {"type": "number", "description": "Y position in mm"},
                "width": {"type": "number", "description": "Pad width in mm"},
                "height": {"type": "number", "description": "Pad height in mm"},
                "shape": {
                    "type": "string",
                    "enum": ["circle", "rect", "oval", "roundrect", "trapezoid", "custom"],
                    "description": "Pad shape",
                },
                "drillDiameter": {"type": "number", "description": "Drill diameter in mm (0 for SMD)"},
            },
            "required": ["library", "footprint", "padNumber"],
        },
    },
    {
        "name": "register_footprint_library",
        "title": "Register Footprint Library",
        "description": "Register a footprint library path with KiCAD.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Library nickname"},
                "path": {"type": "string", "description": "Path to the .pretty directory"},
            },
            "required": ["name", "path"],
        },
    },
    {
        "name": "list_footprint_libraries",
        "title": "List Footprint Libraries",
        "description": "List all registered footprint libraries.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "create_symbol",
        "title": "Create Symbol",
        "description": "Create a new symbol in a symbol library.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "library": {"type": "string", "description": "Library name"},
                "name": {"type": "string", "description": "Symbol name"},
                "description": {"type": "string", "description": "Symbol description"},
                "keywords": {"type": "string", "description": "Space-separated keywords"},
                "reference": {"type": "string", "description": "Default reference prefix (e.g. U, R, C)"},
                "value": {"type": "string", "description": "Default value"},
            },
            "required": ["library", "name"],
        },
    },
    {
        "name": "delete_symbol",
        "title": "Delete Symbol",
        "description": "Delete a symbol from a symbol library.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "library": {"type": "string", "description": "Library name"},
                "symbol": {"type": "string", "description": "Symbol name"},
            },
            "required": ["library", "symbol"],
        },
    },
    {
        "name": "list_symbols_in_library",
        "title": "List Symbols in Library",
        "description": "List all symbols in a specific symbol library.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "library": {"type": "string", "description": "Library name"},
            },
            "required": ["library"],
        },
    },
    {
        "name": "register_symbol_library",
        "title": "Register Symbol Library",
        "description": "Register a symbol library with KiCAD.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Library nickname"},
                "path": {"type": "string", "description": "Path to the .kicad_sym file"},
            },
            "required": ["name", "path"],
        },
    },
    # ------------------------------------------------------------------
    # Router meta-tools
    # ------------------------------------------------------------------
    {
        "name": "list_tool_categories",
        "title": "List Tool Categories",
        "description": "List all available routed tool categories. Use this to discover what categories of tools are available, then call get_category_tools to see tools in a specific category.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_category_tools",
        "title": "Get Category Tools",
        "description": "Get all tools available in a specific category. Returns tool names, descriptions, and input schemas.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Category name (from list_tool_categories)"},
            },
            "required": ["category"],
        },
    },
    {
        "name": "search_tools",
        "title": "Search Tools",
        "description": "Search for tools by keyword across all categories.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
    },
    # ------------------------------------------------------------------
    # Board tools missing from BOARD_TOOLS above
    # ------------------------------------------------------------------
    {
        "name": "add_zone",
        "title": "Add Zone",
        "description": "Create a copper fill zone (pour) on a PCB layer for a specified net.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "layer": {"type": "string", "description": "Layer for the zone"},
                "net": {"type": "string", "description": "Net name for the zone"},
                "points": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                        },
                        "required": ["x", "y"],
                    },
                    "description": "Points defining the zone outline",
                },
                "unit": {"type": "string", "enum": ["mm", "mil", "inch"], "description": "Unit of measurement"},
                "clearance": {"type": "number", "description": "Clearance value"},
                "minWidth": {"type": "number", "description": "Minimum fill width"},
                "padConnection": {
                    "type": "string",
                    "enum": ["thermal", "solid", "none"],
                    "description": "Pad connection type",
                },
            },
            "required": ["layer", "net", "points", "unit"],
        },
    },
    # ------------------------------------------------------------------
    # Component tools missing from COMPONENT_TOOLS above
    # ------------------------------------------------------------------
    {
        "name": "add_component_annotation",
        "title": "Add Component Annotation",
        "description": "Add or update annotation text on a PCB component (e.g. reference or value label).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "Component reference designator"},
                "field": {"type": "string", "enum": ["reference", "value", "footprint", "datasheet"], "description": "Field to annotate"},
                "visible": {"type": "boolean", "description": "Whether the annotation is visible"},
                "layer": {"type": "string", "description": "Layer to place annotation on"},
            },
            "required": ["reference", "field"],
        },
    },
    {
        "name": "group_components",
        "title": "Group Components",
        "description": "Group multiple PCB components together so they move as a unit.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "references": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of component references to group",
                },
                "groupName": {"type": "string", "description": "Optional name for the group"},
            },
            "required": ["references"],
        },
    },
    {
        "name": "replace_component",
        "title": "Replace Component",
        "description": "Replace a component's footprint or symbol with another while preserving position and connections.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "Component reference to replace"},
                "newFootprint": {"type": "string", "description": "New footprint identifier (lib:name)"},
            },
            "required": ["reference", "newFootprint"],
        },
    },
    # ------------------------------------------------------------------
    # Routing tools missing from ROUTING_TOOLS above
    # ------------------------------------------------------------------
    {
        "name": "route_arc_trace",
        "title": "Route Arc Trace",
        "description": "Route a curved (arc) trace between two points on a PCB layer.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "startX": {"type": "number", "description": "Start X coordinate"},
                "startY": {"type": "number", "description": "Start Y coordinate"},
                "endX": {"type": "number", "description": "End X coordinate"},
                "endY": {"type": "number", "description": "End Y coordinate"},
                "midX": {"type": "number", "description": "Arc midpoint X coordinate"},
                "midY": {"type": "number", "description": "Arc midpoint Y coordinate"},
                "layer": {"type": "string", "description": "PCB layer name"},
                "width": {"type": "number", "description": "Trace width in mm"},
                "unit": {"type": "string", "enum": ["mm", "mil", "inch"], "description": "Unit of measurement"},
            },
            "required": ["startX", "startY", "endX", "endY", "midX", "midY", "layer"],
        },
    },
    {
        "name": "route_pad_to_pad",
        "title": "Route Pad to Pad",
        "description": "Route a straight trace between two component pads.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "fromReference": {"type": "string", "description": "Source component reference"},
                "fromPad": {"type": "string", "description": "Source pad number"},
                "toReference": {"type": "string", "description": "Target component reference"},
                "toPad": {"type": "string", "description": "Target pad number"},
                "layer": {"type": "string", "description": "PCB layer name"},
                "width": {"type": "number", "description": "Trace width in mm"},
            },
            "required": ["fromReference", "fromPad", "toReference", "toPad", "layer"],
        },
    },
    {
        "name": "refill_zones",
        "title": "Refill Zones",
        "description": "Refill all copper pour zones on the PCB.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    # ------------------------------------------------------------------
    # Autoroute / Freerouting tools
    # ------------------------------------------------------------------
    {
        "name": "autoroute",
        "title": "Autoroute",
        "description": "Run the Freerouting autorouter on the current board. Exports DSN, calls Freerouting, imports the routed SES.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "freeroutingJarPath": {"type": "string", "description": "Path to the freerouting .jar file"},
                "maxPasses": {"type": "number", "description": "Maximum autorouting passes"},
                "timeout": {"type": "number", "description": "Timeout in seconds"},
            },
        },
    },
    {
        "name": "export_dsn",
        "title": "Export DSN",
        "description": "Export the PCB board as a Specctra DSN file for use with an external autorouter.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "outputPath": {"type": "string", "description": "Output path for the DSN file"},
            },
        },
    },
    {
        "name": "import_ses",
        "title": "Import SES",
        "description": "Import a Specctra SES session file (autorouted result) back into the PCB.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sesPath": {"type": "string", "description": "Path to the SES file to import"},
            },
            "required": ["sesPath"],
        },
    },
    {
        "name": "check_freerouting",
        "title": "Check Freerouting",
        "description": "Check if Freerouting is available and return its version information.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "freeroutingJarPath": {"type": "string", "description": "Optional path to a specific freerouting.jar"},
            },
        },
    },
    # ------------------------------------------------------------------
    # Export tools missing from EXPORT_TOOLS above
    # ------------------------------------------------------------------
    {
        "name": "export_netlist",
        "title": "Export Netlist",
        "description": "Export the board netlist in a specified format.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "outputPath": {"type": "string", "description": "Output file path"},
                "format": {
                    "type": "string",
                    "enum": ["kicad", "orcad", "pads", "cadstar", "spice"],
                    "description": "Netlist format",
                },
            },
        },
    },
    {
        "name": "export_position_file",
        "title": "Export Position File",
        "description": "Export component placement data (pick-and-place) as a position file.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "outputPath": {"type": "string", "description": "Output file path"},
                "format": {"type": "string", "enum": ["csv", "gerber"], "description": "Output format"},
                "unit": {"type": "string", "enum": ["mm", "inch"], "description": "Position units"},
                "side": {
                    "type": "string",
                    "enum": ["front", "back", "both"],
                    "description": "Which board side to export",
                },
            },
        },
    },
    {
        "name": "export_vrml",
        "title": "Export VRML",
        "description": "Export the PCB as a VRML 3D model.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "outputPath": {"type": "string", "description": "Output .wrl file path"},
                "unit": {"type": "string", "enum": ["mm", "meter", "inch"], "description": "Unit scale"},
            },
        },
    },
    # ------------------------------------------------------------------
    # DRC / Design-rule tools missing from DESIGN_RULE_TOOLS above
    # ------------------------------------------------------------------
    {
        "name": "add_net_class",
        "title": "Add Net Class",
        "description": "Define a new net class with specific design-rule constraints.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Net class name"},
                "clearance": {"type": "number", "description": "Minimum clearance in mm"},
                "traceWidth": {"type": "number", "description": "Default trace width in mm"},
                "viaDiameter": {"type": "number", "description": "Via diameter in mm"},
                "viaDrill": {"type": "number", "description": "Via drill size in mm"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "assign_net_to_class",
        "title": "Assign Net to Class",
        "description": "Assign a net to an existing net class.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "net": {"type": "string", "description": "Net name"},
                "netClass": {"type": "string", "description": "Net class name"},
            },
            "required": ["net", "netClass"],
        },
    },
    {
        "name": "check_clearance",
        "title": "Check Clearance",
        "description": "Check the clearance between two specific objects on the board.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "object1": {"type": "string", "description": "First object identifier"},
                "object2": {"type": "string", "description": "Second object identifier"},
            },
            "required": ["object1", "object2"],
        },
    },
    {
        "name": "set_layer_constraints",
        "title": "Set Layer Constraints",
        "description": "Set design-rule constraints for a specific PCB layer.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "layer": {"type": "string", "description": "Layer name"},
                "minTraceWidth": {"type": "number", "description": "Minimum trace width in mm"},
                "minClearance": {"type": "number", "description": "Minimum clearance in mm"},
            },
            "required": ["layer"],
        },
    },
    # ------------------------------------------------------------------
    # JLCPCB / datasheet tools
    # ------------------------------------------------------------------
    {
        "name": "download_jlcpcb_database",
        "title": "Download JLCPCB Database",
        "description": (
            "Download or update the local JLCPCB parts database. "
            "source='jlcsearch' (default, no auth, slow 100-per-page scrape via jlcsearch.tscircuit.com), "
            "'sqlite' (no auth, fast bulk download of a SQLite release artifact such as yaqwsx/jlcparts), "
            "or 'official' (fast, requires JLCPCB_APP_ID/JLCPCB_API_KEY/JLCPCB_API_SECRET env vars)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "enum": ["jlcsearch", "sqlite", "official"],
                    "description": "Which data source to use (default: jlcsearch)",
                },
                "sqliteUrl": {
                    "type": "string",
                    "description": "Override the SQLite asset URL (only for source='sqlite'). Defaults to latest yaqwsx/jlcparts GitHub release.",
                },
                "sqliteTable": {
                    "type": "string",
                    "description": "Override the parts table name in the downloaded SQLite (only for source='sqlite').",
                },
                "keepSqliteAt": {
                    "type": "string",
                    "description": "If set, save the downloaded SQLite file at this path instead of a temp dir (source='sqlite').",
                },
                "outputPath": {"type": "string", "description": "Path to store the imported parts database file"},
                "force": {"type": "boolean", "description": "Force re-download even if local DB already has parts"},
            },
        },
    },
    {
        "name": "search_jlcpcb_parts",
        "title": "Search JLCPCB Parts",
        "description": "Search for components in the JLCPCB parts library (local DB or online).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (part number, description, or keyword)"},
                "category": {"type": "string", "description": "Optional category filter"},
                "inStock": {"type": "boolean", "description": "Only show in-stock parts"},
                "basic": {"type": "boolean", "description": "Only show basic/preferred parts"},
                "limit": {"type": "number", "description": "Maximum number of results"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_jlcpcb_part",
        "title": "Get JLCPCB Part",
        "description": "Get detailed information about a specific JLCPCB part by part number.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "partNumber": {"type": "string", "description": "JLCPCB part number (e.g. C123456)"},
            },
            "required": ["partNumber"],
        },
    },
    {
        "name": "get_jlcpcb_database_stats",
        "title": "Get JLCPCB Database Stats",
        "description": "Get statistics about the local JLCPCB parts database (size, last updated, part counts).",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "suggest_jlcpcb_alternatives",
        "title": "Suggest JLCPCB Alternatives",
        "description": "Suggest JLCPCB-available alternative parts for a given component.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "Component reference or part number to find alternatives for"},
                "limit": {"type": "number", "description": "Maximum number of suggestions"},
            },
            "required": ["reference"],
        },
    },
    {
        "name": "enrich_datasheets",
        "title": "Enrich Datasheets",
        "description": "Automatically populate datasheet URLs for components in the project using online sources.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "overwrite": {"type": "boolean", "description": "Overwrite existing datasheet fields"},
            },
        },
    },
    {
        "name": "get_datasheet_url",
        "title": "Get Datasheet URL",
        "description": "Look up the datasheet URL for a specific component or part number.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "partNumber": {"type": "string", "description": "Part number or component identifier"},
                "manufacturer": {"type": "string", "description": "Optional manufacturer name"},
            },
            "required": ["partNumber"],
        },
    },
]

# =============================================================================
# COMBINED TOOL SCHEMAS
# =============================================================================

TOOL_SCHEMAS: Dict[str, Any] = {}

# Combine all tool categories
for tool in (
    PROJECT_TOOLS
    + BOARD_TOOLS
    + COMPONENT_TOOLS
    + ROUTING_TOOLS
    + LIBRARY_TOOLS
    + DESIGN_RULE_TOOLS
    + EXPORT_TOOLS
    + SCHEMATIC_TOOLS
    + UI_TOOLS
    + ADDITIONAL_TOOLS
):
    TOOL_SCHEMAS[tool["name"]] = tool
