"""
KiCAD MCP Server — pure Python, full parity with mixelpixx/KiCAD-MCP-Server v2.1.0+

Architecture:
  Direct tools  — always visible in tools/list (project lifecycle, meta-router, etc.)
  Routed tools  — discovered via list_tool_categories / get_category_tools / search_tools
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from kicad_mcp.schemas.tool_schemas import TOOL_SCHEMAS
from kicad_mcp.tools.registry import ROUTED_CATEGORIES, DIRECT_TOOL_NAMES

# ---------------------------------------------------------------------------
# Logging setup (mirrors kicad_interface.py from the original)
# ---------------------------------------------------------------------------

def _setup_logging() -> logging.Logger:
    log_dir = os.path.join(os.path.expanduser("~"), ".kicad-mcp", "logs")
    handlers: list[logging.Handler] = []
    try:
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "server.log")
        handlers.append(logging.FileHandler(log_file))
    except (OSError, PermissionError):
        pass
    handlers.append(logging.StreamHandler())

    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        handlers=handlers,
    )
    return logging.getLogger("kicad_mcp")


logger = _setup_logging()

# ---------------------------------------------------------------------------
# FastMCP application
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="kicad-mcp-server",
    instructions=(
        "KiCAD PCB Design MCP Server (Pure Python). "
        "Use list_tool_categories to discover available tool categories, "
        "then get_category_tools to see tools in a specific category. "
        "Direct tools are always available."
    ),
)

# ---------------------------------------------------------------------------
# Backend (lazy-init — only connect when a tool is first called)
# ---------------------------------------------------------------------------

_backend = None


def _get_backend():
    global _backend
    if _backend is None:
        from kicad_mcp.backends.factory import create_backend
        try:
            _backend = create_backend()
            _backend.connect()
        except Exception as exc:
            logger.warning(f"Backend init failed (will retry on demand): {exc}")
    return _backend


# ---------------------------------------------------------------------------
# Helper: uniform success/error response
# ---------------------------------------------------------------------------

def _ok(data: Any = None, message: str = "OK") -> Dict[str, Any]:
    return {"success": True, "message": message, **({"data": data} if data is not None else {})}


def _err(message: str, details: str = "") -> Dict[str, Any]:
    return {"success": False, "error": message, **({"details": details} if details else {})}


# ---------------------------------------------------------------------------
# Direct / always-visible tools
# ---------------------------------------------------------------------------

@mcp.tool()
def ping() -> Dict[str, Any]:
    """Ping the server to check it is alive."""
    return _ok(message="pong")


@mcp.tool()
def get_kicad_version() -> Dict[str, Any]:
    """Return the KiCAD version and backend information."""
    try:
        from kicad_mcp.backends.factory import get_available_backends
        backends = get_available_backends()
        backend = _get_backend()
        version = backend.get_version() if backend and backend.is_connected() else "not connected"
        return _ok({
            "version": version,
            "backends": backends,
            "active_backend": type(backend).__name__ if backend else None,
        })
    except Exception as exc:
        return _err("Failed to get KiCAD version", str(exc))


@mcp.tool()
def get_backend_state() -> Dict[str, Any]:
    """Return the current backend connection state."""
    try:
        from kicad_mcp.backends.factory import get_available_backends
        available = get_available_backends()
        backend = _get_backend()
        return _ok({
            "available": available,
            "active": type(backend).__name__ if backend else None,
            "connected": backend.is_connected() if backend else False,
        })
    except Exception as exc:
        return _err("Failed to get backend state", str(exc))


# ---------------------------------------------------------------------------
# Router meta-tools
# ---------------------------------------------------------------------------

@mcp.tool()
def list_tool_categories() -> Dict[str, Any]:
    """
    List all available routed tool categories.

    Returns a list of category names.  Call get_category_tools(category) to
    see the full schema for tools in any category.
    """
    categories = []
    for cat_name, tool_names in ROUTED_CATEGORIES.items():
        categories.append({
            "name": cat_name,
            "toolCount": len(tool_names),
            "tools": tool_names,
        })
    return _ok({"categories": categories})


@mcp.tool()
def get_category_tools(category: str) -> Dict[str, Any]:
    """
    Get all tools available in a specific category.

    Args:
        category: Category name (from list_tool_categories).

    Returns tool names, descriptions, and input schemas.
    """
    if category not in ROUTED_CATEGORIES:
        available = list(ROUTED_CATEGORIES.keys())
        return _err(
            f"Unknown category: {category!r}",
            f"Available categories: {available}",
        )

    tool_names = ROUTED_CATEGORIES[category]
    tools = []
    for name in tool_names:
        schema = TOOL_SCHEMAS.get(name, {})
        tools.append({
            "name": name,
            "title": schema.get("title", name),
            "description": schema.get("description", ""),
            "inputSchema": schema.get("inputSchema", {}),
        })
    return _ok({"category": category, "tools": tools})


@mcp.tool()
def search_tools(query: str) -> Dict[str, Any]:
    """
    Search for tools by keyword across all categories.

    Args:
        query: Search query string.
    """
    query_lower = query.lower()
    results = []
    for name, schema in TOOL_SCHEMAS.items():
        title = schema.get("title", name)
        description = schema.get("description", "")
        if (
            query_lower in name.lower()
            or query_lower in title.lower()
            or query_lower in description.lower()
        ):
            # Find which category this tool belongs to
            category = next(
                (cat for cat, names in ROUTED_CATEGORIES.items() if name in names),
                "direct",
            )
            results.append({
                "name": name,
                "title": title,
                "description": description,
                "category": category,
            })

    return _ok({"query": query, "count": len(results), "tools": results})


# ---------------------------------------------------------------------------
# Routed tools — registered programmatically from TOOL_SCHEMAS
# ---------------------------------------------------------------------------

_ALREADY_REGISTERED = {
    "ping", "get_kicad_version", "get_backend_state",
    "list_tool_categories", "get_category_tools", "search_tools",
}

# FastMCP requires arg_model to subclass ArgModelBase (which provides model_dump_one_level).
# We create a single FlexArgModelBase with extra="allow" so any kwargs pass through,
# then per-tool subclasses carry the correct JSON schema in tool.parameters.
from pydantic import create_model
from pydantic.config import ConfigDict as _PydanticConfigDict
from mcp.server.fastmcp.utilities.func_metadata import ArgModelBase as _ArgModelBase


class _FlexArgBase(_ArgModelBase):
    """Accept any kwargs and expose them via model_dump_one_level."""
    model_config = _PydanticConfigDict(extra="allow", arbitrary_types_allowed=True)

    def model_dump_one_level(self) -> Dict[str, Any]:
        result = super().model_dump_one_level()
        if self.__pydantic_extra__:
            result.update(self.__pydantic_extra__)
        return result


def _make_json_schema(input_schema: dict) -> dict:
    """Convert a JSON schema dict to a minimal MCP-compatible parameters schema."""
    schema: dict = {"type": "object", "additionalProperties": True}
    if "properties" in input_schema:
        schema["properties"] = input_schema["properties"]
    if "required" in input_schema:
        schema["required"] = input_schema["required"]
    return schema


def _register_routed_tools() -> int:
    """Register all tools from TOOL_SCHEMAS that aren't already registered."""
    count = 0
    for tool_name, schema in TOOL_SCHEMAS.items():
        if tool_name in _ALREADY_REGISTERED:
            continue
        description = schema.get("description", tool_name)
        input_schema = schema.get("inputSchema", {})

        def _make_handler(name: str, desc: str):
            def handler(**kwargs: Any) -> Dict[str, Any]:
                from kicad_mcp.dispatcher import get_dispatcher
                try:
                    return get_dispatcher().dispatch(name, kwargs)
                except Exception as exc:
                    logger.exception(f"Error dispatching {name!r}")
                    return {"success": False, "error": str(exc)}

            handler.__name__ = name
            handler.__qualname__ = name
            handler.__doc__ = desc
            return handler

        mcp.tool()(_make_handler(tool_name, description))

        tool_obj = mcp._tool_manager._tools[tool_name]

        # Replace the arg_model with a flex model so any kwargs are accepted
        flex_model = create_model(f"_{tool_name}Arguments", __base__=_FlexArgBase)
        object.__setattr__(tool_obj.fn_metadata, "arg_model", flex_model)

        # Replace the parameters JSON schema with one built from TOOL_SCHEMAS
        tool_obj.__dict__["parameters"] = _make_json_schema(input_schema)

        count += 1
    return count


_routed_count = _register_routed_tools()

# ---------------------------------------------------------------------------
# Resources — expose KiCAD state as readable resources
# ---------------------------------------------------------------------------

from mcp.server.fastmcp import Context


@mcp.resource("kicad://project/current/info")
def resource_project_info() -> str:
    """Metadata about the currently open KiCAD project."""
    from kicad_mcp.dispatcher import get_dispatcher
    result = get_dispatcher().dispatch("get_project_info", {})
    import json
    return json.dumps(result.get("project", result), indent=2)


@mcp.resource("kicad://project/current/board")
def resource_board_info() -> str:
    """Comprehensive board information including dimensions and layers."""
    from kicad_mcp.dispatcher import get_dispatcher
    result = get_dispatcher().dispatch("get_board_info", {})
    import json
    return json.dumps(result.get("board", result), indent=2)


@mcp.resource("kicad://project/current/components")
def resource_components() -> str:
    """List of all components on the board."""
    from kicad_mcp.dispatcher import get_dispatcher
    result = get_dispatcher().dispatch("get_component_list", {})
    import json
    components = result.get("components", [])
    return json.dumps({"count": len(components), "components": components}, indent=2)


@mcp.resource("kicad://project/current/nets")
def resource_nets() -> str:
    """Electrical nets in the current board."""
    from kicad_mcp.dispatcher import get_dispatcher
    result = get_dispatcher().dispatch("get_nets_list", {})
    import json
    nets = result.get("nets", [])
    return json.dumps({"count": len(nets), "nets": nets}, indent=2)


@mcp.resource("kicad://project/current/layers")
def resource_layers() -> str:
    """Board layer stack configuration."""
    from kicad_mcp.dispatcher import get_dispatcher
    result = get_dispatcher().dispatch("get_layer_list", {})
    import json
    layers = result.get("layers", [])
    return json.dumps({"count": len(layers), "layers": layers}, indent=2)


@mcp.resource("kicad://project/current/design-rules")
def resource_design_rules() -> str:
    """Current design rule settings."""
    from kicad_mcp.dispatcher import get_dispatcher
    result = get_dispatcher().dispatch("get_design_rules", {})
    import json
    return json.dumps(result.get("rules", result), indent=2)


@mcp.resource("kicad://project/current/drc-report")
def resource_drc_report() -> str:
    """DRC violations from the last DRC run."""
    from kicad_mcp.dispatcher import get_dispatcher
    result = get_dispatcher().dispatch("get_drc_violations", {})
    import json
    violations = result.get("violations", [])
    return json.dumps({"count": len(violations), "violations": violations}, indent=2)


@mcp.resource("kicad://board/preview.png", mime_type="image/png")
def resource_board_preview() -> bytes:
    """2D rendering of the current board state (PNG)."""
    from kicad_mcp.dispatcher import get_dispatcher
    import base64
    result = get_dispatcher().dispatch("get_board_2d_view",
                                       {"width": 800, "height": 600, "format": "png"})
    if result.get("success") and "imageData" in result:
        return base64.b64decode(result["imageData"])
    return b""


# ---------------------------------------------------------------------------
# Prompts — design guidance (parity with original 18 prompts + 2 extras)
# ---------------------------------------------------------------------------

# ── Routing prompts ─────────────────────────────────────────────────────────

@mcp.prompt()
def routing_strategy(board_info: str = "") -> str:
    """Develop a routing strategy for a PCB design."""
    return f"""You're helping to develop a routing strategy for a PCB design. Here's information about the board:

{board_info}

Consider the following aspects when developing your routing strategy:

1. Signal Integrity:
   - Group related signals and keep them close
   - Minimize trace length for high-speed signals
   - Consider differential pair routing for appropriate signals
   - Avoid right-angle bends in traces

2. Power Distribution:
   - Use appropriate trace widths for power and ground
   - Consider using power planes for better distribution
   - Place decoupling capacitors close to ICs

3. EMI/EMC Considerations:
   - Keep digital and analog sections separated
   - Consider ground plane partitioning
   - Minimize loop areas for sensitive signals

4. Manufacturing Constraints:
   - Adhere to minimum trace width and spacing requirements
   - Consider via size and placement restrictions
   - Account for soldermask and silkscreen limitations

5. Layer Stack-up Utilization:
   - Determine which signals go on which layers
   - Plan for layer transitions (vias)
   - Consider impedance control requirements

Provide a comprehensive routing strategy that addresses these aspects, with specific recommendations for this particular board design."""


@mcp.prompt()
def differential_pair_routing(differential_pairs: str = "") -> str:
    """Guide routing of differential pairs on a PCB."""
    return f"""You're helping with routing differential pairs on a PCB. Here's information about the differential pairs:

{differential_pairs}

When routing differential pairs, follow these best practices:

1. Length Matching:
   - Keep both traces in each pair the same length
   - Maintain consistent spacing between the traces
   - Use serpentine routing (meanders) for length matching when necessary

2. Impedance Control:
   - Maintain consistent trace width and spacing to control impedance
   - Consider the layer stack-up and dielectric properties
   - Avoid changing layers if possible; when necessary, use symmetrical via pairs

3. Coupling and Crosstalk:
   - Keep differential pairs tightly coupled to each other
   - Maintain adequate spacing between different differential pairs
   - Route away from single-ended signals that could cause interference

4. Reference Planes:
   - Route over continuous reference planes
   - Avoid splits in reference planes under differential pairs
   - Consider the return path for the signals

5. Termination:
   - Plan for proper termination at the ends of the pairs
   - Consider the need for series or parallel termination resistors
   - Place termination components close to the endpoints

Based on the provided information, suggest specific routing approaches for these differential pairs, including recommended trace width, spacing, and any special considerations for this particular design."""


@mcp.prompt()
def high_speed_routing(high_speed_signals: str = "") -> str:
    """Guide routing of high-speed signals on a PCB."""
    return f"""You're helping with routing high-speed signals on a PCB. Here's information about the high-speed signals:

{high_speed_signals}

When routing high-speed signals, consider these critical factors:

1. Impedance Control:
   - Maintain consistent trace width to control impedance
   - Use controlled impedance calculations based on layer stack-up
   - Consider microstrip vs. stripline routing depending on signal requirements

2. Signal Integrity:
   - Minimize trace length to reduce propagation delay
   - Avoid sharp corners (use 45° angles or curves)
   - Minimize vias to reduce discontinuities
   - Consider using teardrops at pad connections

3. Crosstalk Mitigation:
   - Maintain adequate spacing between high-speed traces
   - Use ground traces or planes for isolation
   - Cross traces at 90° when traces must cross on adjacent layers

4. Return Path Management:
   - Ensure continuous return path under the signal
   - Avoid reference plane splits under high-speed signals
   - Use ground vias near signal vias for return path continuity

5. Termination and Loading:
   - Plan for proper termination (series, parallel, AC, etc.)
   - Consider transmission line effects
   - Account for capacitive loading from components and vias

Based on the provided information, suggest specific routing approaches for these high-speed signals, including recommended trace width, layer assignment, and any special considerations for this particular design."""


@mcp.prompt()
def power_distribution(power_requirements: str = "") -> str:
    """Design the power distribution network for a PCB."""
    return f"""You're helping with designing the power distribution network for a PCB. Here's information about the power requirements:

{power_requirements}

Consider these key aspects of power distribution network design:

1. Power Planes vs. Traces:
   - Determine when to use power planes versus wide traces
   - Consider current requirements and voltage drop
   - Plan the layer stack-up to accommodate power distribution

2. Decoupling Strategy:
   - Place decoupling capacitors close to ICs
   - Use appropriate capacitor values and types
   - Consider high-frequency and bulk decoupling needs
   - Plan for power entry filtering

3. Current Capacity:
   - Calculate trace widths based on current requirements
   - Consider thermal issues and heat dissipation
   - Plan for current return paths

4. Voltage Regulation:
   - Place regulators strategically
   - Consider thermal management for regulators
   - Plan feedback paths for regulators

5. EMI/EMC Considerations:
   - Minimize loop areas
   - Keep power and ground planes closely coupled
   - Consider filtering for noise-sensitive circuits

Based on the provided information, suggest a comprehensive power distribution strategy, including specific recommendations for plane usage, trace widths, decoupling, and any special considerations for this particular design."""


@mcp.prompt()
def via_usage(board_info: str = "") -> str:
    """Plan via usage strategy in a PCB design."""
    return f"""You're helping with planning via usage in a PCB design. Here's information about the board:

{board_info}

Consider these important aspects of via usage:

1. Via Types:
   - Through-hole vias (span all layers)
   - Blind vias (connect outer layer to inner layer)
   - Buried vias (connect inner layers only)
   - Microvias (small diameter vias for HDI designs)

2. Manufacturing Constraints:
   - Minimum via diameter and drill size
   - Aspect ratio limitations (board thickness to hole diameter)
   - Annular ring requirements
   - Via-in-pad considerations and special processing

3. Signal Integrity Impact:
   - Capacitive loading effects of vias
   - Impedance discontinuities
   - Stub effects in through-hole vias
   - Strategies to minimize via impact on high-speed signals

4. Thermal Considerations:
   - Using vias for thermal relief
   - Via patterns for heat dissipation
   - Thermal via sizing and spacing

5. Design Optimization:
   - Via fanout strategies
   - Sharing vias between signals vs. dedicated vias
   - Via placement to minimize trace length
   - Tenting and plugging options

Based on the provided information, recommend appropriate via strategies for this PCB design, including specific via types, sizes, and placement guidelines."""


# ── Component prompts ────────────────────────────────────────────────────────

@mcp.prompt()
def component_selection(requirements: str = "") -> str:
    """Select appropriate components for a circuit design."""
    return f"""You're helping to select components for a circuit design. Given the following requirements:

{requirements}

Suggest appropriate components with their values, ratings, and footprints. Consider factors like:
- Power and voltage ratings
- Current handling capabilities
- Tolerance requirements
- Physical size constraints and package types
- Availability and cost considerations
- Thermal characteristics
- Performance specifications

For each component type, recommend specific values and provide a brief explanation of your recommendation. If appropriate, suggest alternatives with different trade-offs."""


@mcp.prompt()
def component_placement_strategy(components: str = "") -> str:
    """Develop a component placement strategy for a PCB layout."""
    return f"""You're helping with component placement for a PCB layout. Here are the components to place:

{components}

Provide a strategy for optimal placement considering:

1. Signal Integrity:
   - Group related components to minimize signal path length
   - Keep sensitive signals away from noisy components
   - Consider appropriate placement for bypass/decoupling capacitors

2. Thermal Management:
   - Distribute heat-generating components
   - Ensure adequate spacing for cooling
   - Placement near heat sinks or vias for thermal dissipation

3. EMI/EMC Concerns:
   - Separate digital and analog sections
   - Consider ground plane partitioning
   - Shield sensitive components

4. Manufacturing and Assembly:
   - Component orientation for automated assembly
   - Adequate spacing for rework
   - Consider component height distribution

Group components functionally and suggest a logical arrangement. If possible, provide a rough sketch or description of component zones."""


@mcp.prompt()
def component_replacement_analysis(component_info: str = "") -> str:
    """Analyze replacement options for an unavailable component."""
    return f"""You're helping to find a replacement for a component that is unavailable or needs to be updated. Here's the original component information:

{component_info}

Consider these factors when suggesting replacements:

1. Electrical Compatibility:
   - Match or exceed key electrical specifications
   - Ensure voltage/current/power ratings are compatible
   - Consider parametric equivalents

2. Physical Compatibility:
   - Footprint compatibility or adaptation requirements
   - Package differences and mounting considerations
   - Size and clearance requirements

3. Performance Impact:
   - How the replacement might affect circuit performance
   - Potential need for circuit adjustments

4. Availability and Cost:
   - Current market availability
   - Cost comparison with original part
   - Lead time considerations

Suggest suitable replacement options and explain the advantages and disadvantages of each. Include any circuit modifications that might be necessary."""


@mcp.prompt()
def component_troubleshooting(issue_description: str = "") -> str:
    """Troubleshoot a component or circuit issue in a PCB design."""
    return f"""You're helping to troubleshoot an issue with a component or circuit section in a PCB design. Here's the issue description:

{issue_description}

Use the following systematic approach to diagnose the problem:

1. Component Verification:
   - Check component values, footprints, and orientation
   - Verify correct part numbers and specifications
   - Examine for potential manufacturing defects

2. Circuit Analysis:
   - Review the schematic for design errors
   - Check for proper connections and signal paths
   - Verify power and ground connections

3. Layout Review:
   - Examine component placement and orientation
   - Check for adequate clearances
   - Review trace routing and potential interference

4. Environmental Factors:
   - Consider temperature, humidity, and other environmental impacts
   - Check for potential EMI/RFI issues
   - Review mechanical stress or vibration effects

Based on the available information, suggest likely causes of the issue and recommend specific steps to diagnose and resolve the problem."""


@mcp.prompt()
def component_sourcing_properties(component_info: str = "") -> str:
    """Attach sourcing and BOM metadata to schematic components."""
    return f"""You are attaching sourcing and BOM metadata to schematic components. Here is the situation:

{component_info}

KiCad symbols carry arbitrary key/value properties on top of the four built-in fields
(Reference, Value, Footprint, Datasheet). These custom properties are written into
the .kicad_sch file, are exported by export_bom, and are picked up by JLCPCB / Digi-Key
sourcing tooling.

Conventional property names (use these so downstream BOM tools recognise them):

  • MPN                — Manufacturer Part Number (canonical)
  • Manufacturer       — Manufacturer name (e.g. "Yageo", "Murata")
  • Manufacturer_PN    — Alias some BOM templates expect; mirror MPN if unsure
  • DigiKey, DigiKey_PN — Digi-Key catalogue number
  • Mouser_PN          — Mouser catalogue number
  • LCSC, JLCPCB_PN    — JLCPCB / LCSC part number (used by JLCPCB assembly)
  • Distributor, Distributor_PN — Generic fallback fields
  • Voltage            — Working voltage rating (e.g. "50V")
  • Tolerance          — Tolerance (e.g. "1%", "±5%")
  • Power              — Power rating (e.g. "0.1W", "1/4W")
  • Dielectric         — Capacitor dielectric (e.g. "X7R", "C0G", "Y5V")
  • Temperature_Coefficient — Resistor TC (e.g. "100ppm/°C")
  • Description        — Free-form human-readable description

Tools to use, in this order:

  1. `list_schematic_components` — confirm which components need updating.
  2. `get_schematic_component` — inspect what properties are already present.
  3. `set_schematic_component_property` — attach or update one property at a time.
  4. `edit_schematic_component` with the `properties` parameter — batch-update many properties.
  5. `remove_schematic_component_property` — delete an obsolete custom field.

Recommend the right set of properties for the components in the brief, generate
the actual tool calls (with concrete values), and explain any sourcing trade-offs."""


@mcp.prompt()
def component_value_calculation(circuit_requirements: str = "") -> str:
    """Calculate appropriate component values for a circuit function."""
    return f"""You're helping to calculate appropriate component values for a specific circuit function. Here's the circuit description and requirements:

{circuit_requirements}

Follow these steps to determine the optimal component values:

1. Identify the relevant circuit equations and design formulas
2. Consider the design constraints and performance requirements
3. Calculate initial component values based on ideal behavior
4. Adjust for real-world factors:
   - Component tolerances
   - Temperature coefficients
   - Parasitic effects
   - Available standard values

Present your calculations step-by-step, showing your work and explaining your reasoning. Recommend specific component values, explaining why they're appropriate for this application. If there are multiple valid approaches, discuss the trade-offs between them."""


# ── Design prompts ───────────────────────────────────────────────────────────

@mcp.prompt()
def pcb_layout_review(pcb_design_info: str = "") -> str:
    """Review a PCB layout for potential issues and improvements."""
    return f"""You're helping to review a PCB layout for potential issues and improvements. Here's information about the current PCB design:

{pcb_design_info}

When reviewing the PCB layout, consider these key areas:

1. Component Placement:
   - Logical grouping of related components
   - Orientation for efficient routing
   - Thermal considerations for heat-generating components
   - Mechanical constraints (mounting holes, connectors at edges)
   - Accessibility for testing and rework

2. Signal Integrity:
   - Trace lengths for critical signals
   - Differential pair routing quality
   - Potential crosstalk issues
   - Return path continuity
   - Decoupling capacitor placement

3. Power Distribution:
   - Adequate copper for power rails
   - Power plane design and continuity
   - Decoupling strategy effectiveness
   - Voltage regulator thermal management

4. EMI/EMC Considerations:
   - Ground plane integrity
   - Potential antenna effects
   - Shielding requirements
   - Loop area minimization
   - Edge radiation control

5. Manufacturing and Assembly:
   - DFM (Design for Manufacturing) issues
   - DFA (Design for Assembly) considerations
   - Testability features
   - Silkscreen clarity and usefulness
   - Solder mask considerations

Based on the provided information, identify potential issues and suggest specific improvements to enhance the PCB design."""


@mcp.prompt()
def layer_stackup_planning(design_requirements: str = "") -> str:
    """Plan an appropriate layer stack-up for a PCB design."""
    return f"""You're helping to plan an appropriate layer stack-up for a PCB design. Here's information about the design requirements:

{design_requirements}

When planning a PCB layer stack-up, consider these important factors:

1. Signal Integrity Requirements:
   - Controlled impedance needs
   - High-speed signal routing
   - EMI/EMC considerations
   - Crosstalk mitigation

2. Power Distribution Needs:
   - Current requirements for power rails
   - Power integrity considerations
   - Decoupling effectiveness
   - Thermal management

3. Manufacturing Constraints:
   - Fabrication capabilities and limitations
   - Cost considerations
   - Available materials and their properties
   - Standard vs. specialized processes

4. Layer Types and Arrangement:
   - Signal layers
   - Power and ground planes
   - Mixed signal/plane layers
   - Microstrip vs. stripline configurations

5. Material Selection:
   - Dielectric constant (Er) requirements
   - Loss tangent considerations for high-speed
   - Thermal properties
   - Mechanical stability

Based on the provided requirements, recommend an appropriate layer stack-up, including the number of layers, their arrangement, material specifications, and thickness parameters. Explain the rationale behind your recommendations."""


@mcp.prompt()
def design_rule_development(project_requirements: str = "") -> str:
    """Develop appropriate design rules for a PCB project."""
    return f"""You're helping to develop appropriate design rules for a PCB project. Here's information about the project requirements:

{project_requirements}

When developing PCB design rules, consider these key areas:

1. Clearance Rules:
   - Minimum spacing between copper features
   - Different clearance requirements for different net classes
   - High-voltage clearance requirements
   - Polygon pour clearances

2. Width Rules:
   - Minimum trace widths for signal nets
   - Power trace width requirements based on current
   - Differential pair width and spacing
   - Net class-specific width rules

3. Via Rules:
   - Minimum via size and drill diameter
   - Via annular ring requirements
   - Microvias and buried/blind via specifications
   - Via-in-pad rules

4. Manufacturing Constraints:
   - Minimum hole size
   - Aspect ratio limitations
   - Soldermask and silkscreen constraints
   - Edge clearances

5. Special Requirements:
   - Impedance control specifications
   - High-speed routing constraints
   - Thermal relief parameters
   - Teardrop specifications

Based on the provided project requirements, recommend a comprehensive set of design rules that will ensure signal integrity, manufacturability, and reliability of the PCB."""


@mcp.prompt()
def component_selection_guidance(circuit_requirements: str = "") -> str:
    """Provide guidance on component selection for a PCB design."""
    return f"""You're helping with component selection for a PCB design. Here's information about the circuit requirements:

{circuit_requirements}

When selecting components for a PCB design, consider these important factors:

1. Electrical Specifications:
   - Voltage and current ratings
   - Power handling capabilities
   - Speed/frequency requirements
   - Noise and precision considerations
   - Operating temperature range

2. Package and Footprint:
   - Space constraints on the PCB
   - Thermal dissipation requirements
   - Manual vs. automated assembly
   - Inspection and rework considerations
   - Available footprint libraries

3. Availability and Sourcing:
   - Multiple source options
   - Lead time considerations
   - Lifecycle status (new, mature, end-of-life)
   - Cost considerations
   - Minimum order quantities

4. Reliability and Quality:
   - Industrial vs. commercial vs. automotive grade
   - Expected lifetime of the product
   - Environmental conditions
   - Compliance with relevant standards

5. Special Considerations:
   - EMI/EMC performance
   - Thermal characteristics
   - Moisture sensitivity
   - RoHS/REACH compliance
   - Special handling requirements

Based on the provided circuit requirements, recommend appropriate component types, packages, and specific considerations for this design."""


@mcp.prompt()
def pcb_design_optimization(design_info: str = "", optimization_goals: str = "") -> str:
    """Optimize a PCB design for specific goals."""
    return f"""You're helping to optimize a PCB design. Here's information about the current design and optimization goals:

{design_info}
{optimization_goals}

When optimizing a PCB design, consider these key areas based on the stated goals:

1. Performance Optimization:
   - Critical signal path length reduction
   - Impedance control improvement
   - Decoupling strategy enhancement
   - Thermal management improvement
   - EMI/EMC reduction techniques

2. Manufacturability Optimization:
   - DFM rule compliance
   - Testability improvements
   - Assembly process simplification
   - Yield improvement opportunities
   - Tolerance and variation management

3. Cost Optimization:
   - Board size reduction opportunities
   - Layer count optimization
   - Component consolidation
   - Alternative component options
   - Panelization efficiency

4. Reliability Optimization:
   - Stress point identification and mitigation
   - Environmental robustness improvements
   - Failure mode mitigation
   - Margin analysis and improvement
   - Redundancy considerations

5. Space/Size Optimization:
   - Component placement density
   - 3D space utilization
   - Flex and rigid-flex opportunities
   - Alternative packaging approaches
   - Connector and interface optimization

Based on the provided information and optimization goals, suggest specific, actionable improvements to the PCB design."""


# ── Footprint prompts ────────────────────────────────────────────────────────

@mcp.prompt()
def create_footprint_guide(component: str = "", library_path: str = "") -> str:
    """Create a correct KiCAD 9 footprint using the create_footprint tool."""
    return f"""You are a KiCAD footprint expert. Create a correct KiCAD 9 footprint using the create_footprint tool.

## Component to footprint
{component}

## Library path
{library_path}

## Rules for correct footprints

### Coordinate system
- Origin (0,0) is the footprint anchor, typically the centre of the pad pattern.
- X increases to the right, Y increases downward (same as KiCAD screen).
- All values in millimetres.

### SMD pads
- type: "smd"
- Default layers: ["F.Cu", "F.Paste", "F.Mask"]
- No drill needed.
- Common shapes: "rect" for square/rectangular, "roundrect" for ICs.

### THT pads
- type: "thru_hole"
- Default layers: ["*.Cu", "*.Mask"]
- drill required (round = scalar, oval = {{w, h}}).
- Pad 1 is typically square (rect), remaining pads are circle.

### Courtyard (F.CrtYd)
- Add 0.25 mm clearance around the outermost extent of pads.
- Line width: 0.05 mm.

### Silkscreen (F.SilkS)
- Shows the component body outline, typically slightly inside the courtyard.
- Line width: 0.12 mm.
- Must not overlap pads.

### Fab layer (F.Fab)
- Shows the realistic component outline with pin-1 marker.
- Line width: 0.10 mm.

### Reference text
- Place "REF**" above the courtyard (negative Y = above).
- Value text below the courtyard (positive Y = below).

## Workflow
1. Calculate pad positions from datasheet pitch and land pattern.
2. Call create_footprint with pads[], courtyard, silkscreen, fabLayer.
3. Verify with edit_footprint_pad if any correction is needed.

## Common packages quick reference
| Package   | Pitch  | Pad size (SMD)   | Notes                        |
|-----------|--------|------------------|------------------------------|
| 0402      | 1.0 mm | 0.6 × 0.7 mm     | Very small, min 0.5 mm drill |
| 0603      | 1.6 mm | 1.0 × 1.0 mm     | Standard small passive       |
| 0805      | 2.0 mm | 1.4 × 1.2 mm     | Easy to hand-solder          |
| SOT-23    | 0.95 mm| 1.0 × 1.3 mm     | 3-pin, 2 on one side         |
| SOT-23-5  | 0.95 mm| 0.6 × 1.0 mm     | 5-pin                        |
| SOIC-8    | 1.27 mm| 1.6 × 0.6 mm     | 4 pins each side             |
| DIP-8     | 2.54 mm| dia 1.6, drill 0.8| THT, 100 mil grid            |

Now create the footprint for: {component}"""


@mcp.prompt()
def footprint_ipc_checklist(footprint_path: str = "") -> str:
    """Review a footprint against IPC-7351 land pattern guidelines."""
    return f"""Review the footprint at {footprint_path} against IPC-7351 land pattern guidelines.

Check:
1. **Pad size** – is the copper area sufficient for soldering (not undersized)?
2. **Courtyard** – at least 0.25 mm clearance around all pads?
3. **Silkscreen** – does it overlap pads? (it should NOT)
4. **Pad 1 marker** – is pin 1 identifiable (square pad or triangle on silkscreen)?
5. **Drill size** – for THT: drill ≥ lead diameter + 0.3 mm?
6. **Layer assignments** – SMD pads: F.Cu/F.Paste/F.Mask; THT: *.Cu/*.Mask?
7. **Anchor** – is the origin centred on the pad pattern?

Use edit_footprint_pad to fix any issues found."""


# ── Extra prompts (beyond original 18) ──────────────────────────────────────

@mcp.prompt()
def jlcpcb_component_selection(
    component_type: str = "resistor",
    value: str = "10k",
    package: str = "0402",
) -> str:
    """JLCPCB component selection guidance."""
    return f"""Help select a JLCPCB-compatible {component_type} ({value}, {package}) for PCB assembly.

Use these MCP tools in order:
1. search_jlcpcb_parts with query="{value}" to find candidates
2. get_jlcpcb_part with the LCSC part number for full details
3. Check stock availability and Basic vs Extended part status

Prefer **Basic** parts (no setup fee) over Extended parts when equivalent.

Key fields to verify:
- componentSpecificationEn: package matches your footprint ({package})
- stockCount: adequate stock for your build quantity
- libraryType: "Basic" preferred
- componentModelEn: manufacturer part number for cross-referencing

After selection, use suggest_jlcpcb_alternatives if the first choice is out of stock."""


@mcp.prompt()
def schematic_design_guide(project_name: str = "my_project") -> str:
    """Step-by-step schematic design workflow."""
    return f"""Design a schematic for '{project_name}' using this workflow:

**Step 1 — Setup**
create_project name="{project_name}" → creates .kicad_pro + .kicad_sch + .kicad_pcb

**Step 2 — Add Power Symbols**
add_schematic_power_symbol: VCC, GND, +3.3V as needed

**Step 3 — Place Components**
add_schematic_component: search symbols with search_symbols first
- Use get_symbol_info for pin details before placing

**Step 4 — Wire Connections**
add_schematic_wire: connect pins point-to-point
add_schematic_net_label: name important nets (especially power rails)
add_no_connect: mark unused pins

**Step 5 — Annotate & Verify**
annotate_schematic: assign reference designators
run_erc: find and fix electrical rule violations

**Step 6 — Sync to PCB**
sync_schematic_to_board: push netlist to .kicad_pcb
export_netlist: generate BOM-compatible netlist"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run() -> None:
    """Start the MCP server using stdio transport."""
    import sys
    logger.info(f"KiCAD MCP Server starting (Python {sys.version})")
    logger.info(f"Direct tools: 6 meta + {_routed_count} routed = {6 + _routed_count} total")
    logger.info(f"Routed categories: {list(ROUTED_CATEGORIES.keys())}")
    mcp.run(transport="stdio")
