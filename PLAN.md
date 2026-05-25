# KiCad MCP Server — Pure Python Implementation Plan

**Project:** Pure Python MCP server for KiCad PCB design automation
**Source of truth:** `/home/miro/git/KiCAD-MCP-Server` (mixelpixx/KiCAD-MCP-Server v2.1.0+)
**Goal:** 100 % feature parity with the original hybrid Node + Python implementation, using only Python.
**Target clients:** Claude Desktop / Code, Zed, any MCP-2025-06-18 compliant client.
**Scope:** 142 tool registrations (~122 unique user-facing tools after de-dup) across 16 source modules, 8 canonical MCP resources (+ extended/templated TS resources), 18 prompts, dual IPC/SWIG backend, full schematic workflow, Freerouting integration, JLCPCB dual-source database, datasheet enrichment, SVG import, snapshot workflow.

---

## Table of Contents

1. [Reference: Original Implementation](#reference-original-implementation)
2. [Project Overview](#project-overview)
3. [Architecture](#architecture)
4. [Technical Specifications](#technical-specifications)
5. [Project Structure](#project-structure)
6. [Implementation Phases](#implementation-phases)
7. [Full Tool Catalog (142 registrations)](#full-tool-catalog)
8. [Resources Catalog](#resources-catalog)
9. [Prompts Catalog](#prompts-catalog)
10. [Testing Strategy](#testing-strategy)
11. [Deployment](#deployment)
12. [Timeline & Milestones](#timeline--milestones)

---

## Reference: Original Implementation

Authoritative files in `/home/miro/git/KiCAD-MCP-Server` that the port MUST mirror:

| Path | Purpose |
|---|---|
| `src/tools/registry.ts` | Direct-vs-routed tool list, 8 routed categories |
| `src/tools/router.ts` | `list_tool_categories`, `get_category_tools`, `search_tools`, `execute_tool` |
| `src/tools/*.ts` | TypeScript tool registration (board, component, routing, schematic, library, library-symbol, footprint, symbol-creator, design-rules, export, freerouting, jlcpcb-api, datasheet, ui, project) |
| `src/resources/*.ts` | Extended resource registration (project, board, component, library) |
| `src/prompts/*.ts` | 18 prompt templates (routing, component, design, footprint) |
| `python/kicad_interface.py` | Single-process dispatch table; backend auto-selection (lines 137-235); `command_routes` (line 332+) |
| `python/kicad_api/base.py` | `KiCADBackend`/`BoardAPI` ABCs |
| `python/kicad_api/ipc_backend.py` | KiCAD 9.0+ IPC backend (kipy) — real-time UI sync |
| `python/kicad_api/swig_backend.py` | Legacy SWIG `pcbnew` backend (deprecated in KiCAD 10) |
| `python/kicad_api/factory.py` | `create_backend('auto'\|'ipc'\|'swig')` + `KICAD_BACKEND` env override |
| `python/commands/*.py` | 27 command modules implementing the actual KiCad ops |
| `python/parsers/kicad_mod_parser.py` | `.kicad_mod` S-expression parser |
| `python/templates/*.kicad_sch` | 4 schematic seed templates |
| `python/annotations/kicad_ipc_tool_annotations.json` | IPC tool annotations |
| `python/annotations/loader.py` | `AnnotationLoader` merger |
| `python/schemas/tool_schemas.py` | `TOOL_SCHEMAS` — JSON Schema source of truth |
| `python/resources/resource_definitions.py` | Canonical 8 `kicad://...` resources |
| `python/utils/kicad_process.py` | `KiCADProcessManager`, `check_and_launch_kicad` |
| `python/utils/platform_helper.py` | Windows DLL paths, KiCAD bundled-Python `sys.path` injection |
| `download_jlcpcb.py` | Standalone full-catalog downloader (~2.5 M parts) |

The port is a **straight 1:1 functional re-implementation**. Every named tool in the original MUST appear with the same name and same JSON Schema in the Python version. Behaviour differences are bugs.

---

## Project Overview

### Current State (mixelpixx/KiCAD-MCP-Server)

**Architecture:**
- TypeScript MCP server (`src/`) wraps the `@modelcontextprotocol/sdk`
- Spawns a long-running Python interpreter (`python/kicad_interface.py`) over stdin/stdout JSON
- Python side dispatches each command to one of 27 command modules
- Each command runs against either an IPC backend (`kipy`, KiCAD 9+) or the legacy SWIG `pcbnew` backend
- 142 tool registrations across 16 source modules
- 8 canonical resources, 18 prompts
- JLCPCB integration (2.5 M+ parts, dual-source: official API + public)

**Pain points eliminated by the port:**
- ~3 GB `node_modules`
- Two languages and two build systems
- Sub-process JSON protocol layer between TS and Python
- Complex setup (`npm install` + `tsc build` + `python venv --system-site-packages`)
- Cold start still ~60 s for `pcbnew`/`wxApp` init (kept; unavoidable KiCad limitation)

### Desired State (Pure Python)

**Architecture:**
- One MCP server: `kicad_mcp` Python package, stdio transport
- Direct in-process call to IPC (kipy) or SWIG (pcbnew) backend — no subprocess hop
- Same 142 tool names with identical JSON Schemas
- Same backend abstraction (IPC preferred, SWIG fallback)
- Same router pattern (direct tools always visible, routed tools discoverable via 4 meta-tools)
- Same 8 resources and 18 prompts

**Benefits:**
- No Node.js / npm
- Single language, single venv
- One fewer process hop → smaller failure surface, easier debugging
- Easier extension for Python-first KiCad community

**Non-benefits (unchanged from original):**
- First-call init ~60 s when running through SWIG (wxApp); near-zero when using IPC
- Still requires KiCad 9.0+ with Python bindings
- Venv MUST be created with `--system-site-packages` to see `pcbnew` (SWIG path)

### Success Criteria

1. Every one of the 142 tool registrations in `src/tools/*.ts` exists with the same name and same input schema.
2. Every one of the 8 canonical resources (`python/resources/resource_definitions.py`) is served.
3. All 18 prompts (`src/prompts/*.ts`) are served.
4. Dual backend with `KICAD_BACKEND=auto|ipc|swig` env override and IPC auto-fallback to SWIG.
5. Router meta-tools (`list_tool_categories`, `get_category_tools`, `search_tools`) work and reflect the same direct/routed split as `src/tools/registry.ts`. Routed tools are callable directly by name — no `execute_tool` wrapper needed.
6. Schematic workflow end-to-end: dynamic-symbol load → place → wire → label → ERC → netlist → `sync_schematic_to_board`.
7. Freerouting end-to-end: `export_dsn` → `autoroute` (Java) → `import_ses`.
8. JLCPCB: local-DB import via `download_jlcpcb_database`, parametric `search_jlcpcb_parts`, `suggest_jlcpcb_alternatives`, `enrich_datasheets`.
9. Setup time < 5 min on a machine with KiCad already installed.
10. Pure Python — no Node.js, no TypeScript, no npm.

---

## Architecture

### Top-level data flow

```
MCP client (Claude / Zed / Code)
     │ JSON-RPC over stdio
     ▼
kicad_mcp/server.py        ← MCP SDK Server, handlers
     │
     ├─ ToolRegistry        ← direct vs routed split (mirrors registry.ts)
     │      │
     │      ├─ direct tools  (always visible)
     │      └─ routed tools  (discovered via router meta-tools)
     │
     ├─ ResourceRegistry    ← 8 canonical kicad:// URIs + extended/templated
     ├─ PromptRegistry      ← 18 prompts
     │
     └─ KiCadBackend (abstract)
            ├─ IPCBackend   ← kipy / Protocol Buffers, KiCad 9+, real-time UI sync
            └─ SWIGBackend  ← legacy pcbnew, no live UI, deprecated
                 (factory.py: auto / ipc / swig, env KICAD_BACKEND)
```

### Tool registration mirrors `registry.ts`

The port keeps the same two-tier model: **direct** tools are always exposed in `tools/list`; **routed** tools live behind `execute_tool` and are discovered with `list_tool_categories` / `get_category_tools` / `search_tools`. The README claims this reduces AI context cost by ~70 %.

| Routed category | Tools in category |
|---|---|
| board | add_layer, set_active_layer, get_layer_list, add_mounting_hole, add_board_text, add_zone, get_board_extents, get_board_2d_view, launch_kicad_ui |
| component | rotate_component, delete_component, edit_component, find_component, get_component_properties, add_component_annotation, group_components, replace_component |
| export | export_gerber, export_pdf, export_svg, export_3d, export_bom, export_netlist, export_position_file, export_vrml |
| drc | set_design_rules, get_design_rules, run_drc, add_net_class, assign_net_to_class, set_layer_constraints, check_clearance, get_drc_violations |
| schematic | (25 tools — see §Full Tool Catalog) |
| library | list_libraries, search_footprints, list_library_footprints, get_footprint_info |
| routing | add_via, add_copper_pour |
| autoroute | autoroute, export_dsn, import_ses, check_freerouting |

Direct tools (always visible): `create_project`, `open_project`, `save_project`, `snapshot_project`, `get_project_info`, `place_component`, `move_component`, `add_net`, `route_trace`, `get_board_info`, `set_board_size`, `add_board_outline`, `add_schematic_component`, `list_schematic_components`, `annotate_schematic`, `connect_passthrough`, `connect_to_net`, `add_schematic_net_label`, `sync_schematic_to_board`, `get_backend_state`, `check_kicad_ui`.

Router meta-tools: `list_tool_categories`, `get_category_tools`, `search_tools`. (Note: `execute_tool` is not a registered tool — routed tools are called directly by name once discovered.)

Additional always-visible tools (the remaining ~35) come from advanced-routing, advanced-component, footprint creator, symbol creator, JLCPCB, datasheet — see §Full Tool Catalog.

### Backend abstraction

Mirror `python/kicad_api/`:

- `kicad_mcp/backends/base.py` — `KiCadBackend` and `BoardAPI` ABCs. Identical method names to original `base.py`.
- `kicad_mcp/backends/ipc_backend.py` — wraps `kipy`. Unit conventions: 1 mm = 1 000 000 nm, 1 inch = 25 400 000 nm. Socket fallback order: caller arg → `ipc:///tmp/kicad/api.sock` → `ipc:///run/user/<uid>/kicad/api.sock`.
- `kicad_mcp/backends/swig_backend.py` — wraps `pcbnew`. Marked DEPRECATED in docstrings; lifetime tied to KiCad 9.x.
- `kicad_mcp/backends/factory.py` — `create_backend(kind='auto')`. Honours `KICAD_BACKEND` env var. `auto` tries IPC `connect()`; on failure logs a warning and returns SWIG. `ipc` and `swig` raise if the underlying lib is missing.
- `kicad_mcp/backends/__init__.py` — re-exports plus `get_available_backends()` for diagnostics.

### Schematic engine

This is the biggest sub-system. Mirror these modules in `kicad_mcp/schematic/`:

- `dynamic_symbol_loader.py` — text-manipulation injection of any of ~10 000 KiCad symbols into a `.kicad_sch`'s `lib_symbols` block. Must respect KiCad-9 nesting rules (parent before child for `extends`, library prefixes only at top level).
- `wire_manager.py` — direct S-expression generation for wires / labels / junctions (kicad-skip can't create them with full parameters).
- `wire_dragger.py` — when a component is moved with `preserveWires=true` (default), endpoints attached to its pins are re-anchored.
- `wire_connectivity.py` — net-tracing using KiCAD internal units (10 000 IU/mm). Handles hierarchical sheets, hierarchical labels, sheet pins. Underlies `get_net_connections`, `get_wire_connections`, `get_net_at_point`, `list_floating_labels`, `find_orphaned_wires`.
- `pin_locator.py` — reads `.kicad_sym` to compute true pin endpoints (rotation-aware). Required by `connect_to_net`, `add_schematic_net_label`, `connect_passthrough`.
- `schematic_analysis.py` — `find_overlapping_elements`, `get_elements_in_region`, `find_wires_crossing_symbols`, `find_orphaned_wires`, `find_unconnected_pins`, `check_wire_collisions`.
- `snap.py` — `snap_to_grid` for schematic elements.
- `templates/` — copy of the 4 seed `.kicad_sch` files (`empty`, `minimal`, `template_with_symbols`, `template_with_symbols_expanded`).

### Auto-backup and disk safety

Mirror the `_board_disk_signature` mechanism in `kicad_interface.py`:

- Track `(mtime_ns, sha256)` for each open board/schematic.
- Before save, re-stat the file; if signature changed externally, refuse and surface a clear error.
- Keep a `.mcp-backups/` directory inside the project, retention default 20 (configurable via `KICAD_MCP_BACKUP_RETENTION`).

### Platform handling

Mirror `python/utils/platform_helper.py`:

- Windows: prepend cairo DLL dir to `PATH` *before* `cairosvg` import; inject `C:\Program Files\KiCad\<ver>\lib\python3\dist-packages` to `sys.path`.
- macOS: inject `/Applications/KiCad/KiCad.app/Contents/Frameworks/python.framework/...`.
- Linux: inject `/usr/lib/kicad/lib/python3/dist-packages` (and `/usr/lib/python3/dist-packages` for system-installed pcbnew).
- Auto-launch: `KICAD_AUTO_LAUNCH=1` starts KiCad if `check_kicad_ui` reports it's down.
- Dev mode: `KICAD_MCP_DEV=1` auto-saves MCP session log into project's `logs/` directory on every `export_gerber` and `snapshot_project`.

---

## Technical Specifications

### System Requirements

**Required:**
- Python ≥ 3.10 (must match the Python that KiCad ships; KiCad 9 ships 3.11, KiCad 10 ships 3.13)
- KiCad 9.0+ with Python bindings (provides `pcbnew`; optionally `kipy` IPC API)
- Linux, macOS or Windows

**Optional:**
- `kipy` (kicad-python) for IPC backend — auto-installed via `pip install kipy`
- `uv` for faster installs
- Java 11+ and Freerouting JAR for `autoroute`

### Python Dependencies

```toml
# Core MCP
mcp = ">=1.0.0"                  # Official MCP SDK

# KiCad operations
sexpdata = ">=1.0.0"             # S-expression parsing (kicad_mod, kicad_sym, kicad_sch)
kicad-skip = ">=0.2.5"           # High-level schematic helpers
kipy = ">=0.4.0"                 # IPC backend (optional but installed by default)

# JLCPCB integration
requests = ">=2.31.0"            # HTTP client
# sqlite3 is built-in            # Local parts DB

# Image/rendering
pillow = ">=10.0.0"              # 2D board preview
cairosvg = ">=2.7.0"             # SVG → PNG for schematic/board renders

# Utilities
colorlog = ">=6.7.0"             # Pretty logs to stderr
pydantic = ">=2.0.0"             # Schema validation
python-dotenv = ">=1.0.0"        # `.env` loading
```

### MCP Protocol

- **Transport:** stdio
- **Protocol version:** 2025-06-18 (matches original)
- **Capabilities:** tools (listChanged), resources (listChanged, subscribe), prompts (listChanged)

### Environment Variables (mirror originals)

| Variable | Purpose |
|---|---|
| `KICAD_BACKEND` | `auto` (default), `ipc`, `swig` |
| `KICAD_PATH` | KiCad install root (Windows mainly) |
| `KICAD_AUTO_LAUNCH` | `1` to auto-start KiCad UI if needed |
| `KICAD_MCP_DEV` | `1` to dump MCP session logs into project `logs/` |
| `KICAD_MCP_BACKUP_RETENTION` | Number of `.mcp-backups/` files kept (default 20) |
| `JLCPCB_DB_PATH` | Override location of `jlcpcb_parts.db` |
| `FREEROUTING_JAR` | Path to Freerouting JAR for `autoroute` |
| `FREEROUTING_JAVA` | Java binary path (`java` by default) |

---

## Project Structure

```
kicad-mcp-python/
├── README.md
├── PLAN.md                           ← this file
├── pyproject.toml
├── LICENSE
├── .gitignore
├── start-server.sh                   ← wrapper that activates venv and exec's the server
├── start-server.ps1                  ← Windows PowerShell wrapper
├── download_jlcpcb.py                ← standalone JLCPCB full-catalog downloader (mirror)
│
├── kicad_mcp/                        ← main package
│   ├── __init__.py
│   ├── __main__.py                   ← `python -m kicad_mcp`
│   ├── server.py                     ← MCP Server + handler registration
│   ├── interface.py                  ← single-process dispatch (mirrors python/kicad_interface.py)
│   ├── config.py                     ← env loading, defaults
│   ├── logging_setup.py              ← stderr colorlog
│   ├── disk_safety.py                ← _board_disk_signature, .mcp-backups/
│   │
│   ├── backends/                     ← mirror python/kicad_api/
│   │   ├── __init__.py
│   │   ├── base.py                   ← KiCadBackend, BoardAPI ABCs
│   │   ├── ipc_backend.py            ← kipy IPC
│   │   ├── swig_backend.py           ← pcbnew SWIG
│   │   └── factory.py                ← create_backend(), get_available_backends()
│   │
│   ├── tools/                        ← one module per src/tools/*.ts
│   │   ├── __init__.py
│   │   ├── registry.py               ← direct/routed split + categories (mirrors registry.ts)
│   │   ├── router.py                 ← list_tool_categories / get_category_tools / search_tools / execute_tool
│   │   ├── base.py                   ← KiCadTool ABC, BoardTool
│   │   ├── tool_response.py          ← uniform success/error response shapes
│   │   ├── project.py                ← create/open/save/snapshot/get_info
│   │   ├── board.py                  ← 12 board tools + import_svg_logo
│   │   ├── component.py              ← 17 component tools
│   │   ├── routing.py                ← 16 routing tools
│   │   ├── schematic.py              ← 43 schematic tools (entry points)
│   │   ├── library.py                ← footprint-library tools
│   │   ├── library_symbol.py         ← symbol-library tools
│   │   ├── footprint.py              ← footprint creator
│   │   ├── symbol_creator.py         ← symbol creator
│   │   ├── design_rules.py           ← 8 DRC tools
│   │   ├── export.py                 ← 8 export tools
│   │   ├── freerouting.py            ← autoroute / export_dsn / import_ses / check_freerouting
│   │   ├── jlcpcb.py                 ← 5 JLCPCB tools (API + local DB)
│   │   ├── datasheet.py              ← enrich_datasheets, get_datasheet_url
│   │   └── ui.py                     ← get_backend_state, check_kicad_ui, launch_kicad_ui, get_board_2d_view
│   │
│   ├── commands/                     ← actual KiCad implementations (mirror python/commands/)
│   │   ├── __init__.py
│   │   ├── project.py
│   │   ├── board.py
│   │   ├── component.py
│   │   ├── routing.py
│   │   ├── design_rules.py
│   │   ├── export.py
│   │   ├── library.py
│   │   ├── library_symbol.py
│   │   ├── footprint.py
│   │   ├── symbol_creator.py
│   │   ├── freerouting.py
│   │   ├── jlcpcb.py                 ← official API client
│   │   ├── jlcsearch.py              ← public no-auth client
│   │   ├── jlcpcb_parts.py           ← local SQLite manager
│   │   ├── datasheet_manager.py
│   │   ├── svg_import.py
│   │   └── schematic/
│   │       ├── __init__.py
│   │       ├── manager.py            ← create/load schematic
│   │       ├── component.py          ← ComponentManager
│   │       ├── connection.py         ← ConnectionManager (wires, labels, no-connects)
│   │       ├── library.py            ← LibraryManager (schematic-side)
│   │       ├── dynamic_symbol_loader.py
│   │       ├── wire_manager.py
│   │       ├── wire_dragger.py
│   │       ├── wire_connectivity.py
│   │       ├── pin_locator.py
│   │       ├── analysis.py           ← schematic_analysis
│   │       └── snap.py
│   │
│   ├── parsers/
│   │   ├── __init__.py
│   │   └── kicad_mod_parser.py       ← .kicad_mod S-expression parser (mirror)
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── tool_schemas.py           ← TOOL_SCHEMAS dict — single source of truth for JSON Schema
│   │
│   ├── annotations/
│   │   ├── __init__.py
│   │   ├── loader.py                 ← AnnotationLoader
│   │   └── kicad_ipc_tool_annotations.json
│   │
│   ├── resources/
│   │   ├── __init__.py
│   │   ├── definitions.py            ← canonical 8 kicad:// URIs (mirror resource_definitions.py)
│   │   ├── project.py                ← extended TS resources (project_files, project_status, …)
│   │   ├── board.py                  ← layer_list, board_extents, board_2d_view, board_3d_view, board_statistics
│   │   ├── component.py              ← component_list, _details, _connections, _placement, _groups, _visualization
│   │   └── library.py                ← library_list, component_library, footprint, symbol, 3d_model
│   │
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── routing.py                ← 5 routing prompts
│   │   ├── component.py              ← 6 component prompts
│   │   ├── design.py                 ← 5 design prompts
│   │   └── footprint.py              ← 2 footprint prompts
│   │
│   ├── templates/
│   │   ├── empty.kicad_sch
│   │   ├── minimal.kicad_sch
│   │   ├── template_with_symbols.kicad_sch
│   │   └── template_with_symbols_expanded.kicad_sch
│   │
│   └── utils/
│       ├── __init__.py
│       ├── kicad_process.py          ← KiCADProcessManager, check_and_launch_kicad
│       └── platform_helper.py        ← PlatformHelper (Windows DLL, sys.path, etc.)
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_registry.py          ← every tool name from registry.ts is present
│   │   ├── test_schemas.py           ← every TOOL_SCHEMAS entry validates a sample input
│   │   ├── test_backend_factory.py
│   │   ├── test_disk_safety.py
│   │   └── test_router.py
│   ├── integration/
│   │   ├── test_mcp_protocol.py      ← initialize / tools/list / tools/call
│   │   ├── test_project_workflow.py  ← create → open → save → snapshot
│   │   ├── test_schematic_workflow.py← dynamic symbol load → place → wire → label → ERC → netlist
│   │   ├── test_routing.py
│   │   ├── test_drc.py
│   │   ├── test_export.py
│   │   ├── test_freerouting.py       ← gated on FREEROUTING_JAR
│   │   ├── test_jlcpcb_api.py        ← gated on network
│   │   └── test_jlcpcb_local.py      ← uses sqlite fixture
│   └── fixtures/
│       ├── test_project.kicad_pro
│       ├── test_board.kicad_pcb
│       ├── test_schematic.kicad_sch
│       └── jlcpcb_sample.db
│
├── scripts/
│   ├── setup_dev.sh
│   ├── test_mcp.sh                   ← stdio smoke test
│   ├── generate_tool_docs.py         ← auto-gen docs/tools.md from TOOL_SCHEMAS
│   └── parity_check.py               ← assert 142 tool names match registry.ts
│
└── docs/
    ├── setup.md
    ├── tools.md                      ← auto-generated reference for all 142 tools
    ├── resources.md
    ├── prompts.md
    ├── backends.md                   ← IPC vs SWIG, env vars, troubleshooting
    ├── schematic_workflow.md
    ├── jlcpcb_workflow.md
    ├── freerouting_setup.md
    └── examples.md
```

---

## Implementation Phases

Each phase ends with a **parity check** against the corresponding part of the original.

---

### PHASE 0 — Original mapping & schema extraction (1–2 h)

Before writing implementation code, lock in the spec.

1. Copy `/home/miro/git/KiCAD-MCP-Server/python/schemas/tool_schemas.py` verbatim into `kicad_mcp/schemas/tool_schemas.py` (it is already pure Python — no porting needed).
2. Copy `/home/miro/git/KiCAD-MCP-Server/python/annotations/kicad_ipc_tool_annotations.json` and `loader.py` into `kicad_mcp/annotations/`.
3. Copy the 4 schematic templates into `kicad_mcp/templates/`.
4. Extract the direct/routed split from `src/tools/registry.ts` into `kicad_mcp/tools/registry.py` as Python data:

```python
ROUTED_CATEGORIES: dict[str, list[str]] = {
    "board":       [...],   # 9 entries
    "component":   [...],   # 8 entries
    "export":      [...],   # 8 entries
    "drc":         [...],   # 8 entries
    "schematic":   [...],   # 25 entries
    "library":     [...],   # 4 entries
    "routing":     [...],   # 2 entries
    "autoroute":   [...],   # 4 entries
}

DIRECT_TOOL_NAMES: list[str] = [...]   # ~21 entries

# Tools registered in src/tools/*.ts but neither routed nor "direct" — they
# show up always-visible because the server registers everything.
ALWAYS_VISIBLE_EXTRA: list[str] = [...]   # ~35 entries
```

5. Write `scripts/parity_check.py` that parses `src/tools/*.ts` (regex `server\.tool\("(\w+)"`) and asserts the same set of names exists in our `TOOL_SCHEMAS`. **This script is the gate for "done".**

**✓ Checkpoint 0:** `parity_check.py` succeeds (initially fails — list of missing tools is the implementation TODO).

---

### PHASE 1 — Foundation (4–6 h)

#### 1.1 Project setup (1 h)

```bash
git init
mkdir -p kicad_mcp/{backends,tools,commands/schematic,parsers,schemas,annotations,resources,prompts,templates,utils} tests/{unit,integration,fixtures} scripts docs
touch kicad_mcp/__init__.py kicad_mcp/{backends,tools,commands,commands/schematic,parsers,schemas,annotations,resources,prompts,utils}/__init__.py tests/__init__.py
```

`pyproject.toml`:

```toml
[project]
name            = "kicad-mcp-server"
version         = "2.1.0"
description     = "Pure Python MCP server for KiCad PCB design automation (full parity with mixelpixx/KiCAD-MCP-Server)"
readme          = "README.md"
requires-python = ">=3.10"
license         = {text = "MIT"}
authors         = [{name = "Miroslav Talasek", email = "miroslav.talasek@gmail.com"}]

dependencies = [
    "mcp>=1.0.0",
    "requests>=2.31.0",
    "sexpdata>=1.0.0",
    "kicad-skip>=0.2.5",
    "kipy>=0.4.0; platform_system!='Windows'",
    "pillow>=10.0.0",
    "cairosvg>=2.7.0",
    "colorlog>=6.7.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = ["pytest>=7", "pytest-asyncio>=0.21", "black>=23", "ruff>=0.1", "mypy>=1.5"]

[project.scripts]
kicad-mcp = "kicad_mcp.__main__:main"

[build-system]
requires      = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["kicad_mcp"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths    = ["tests"]
```

#### 1.2 Venv (30 min)

```bash
python3 -m venv --system-site-packages .venv          # --system-site-packages is REQUIRED for pcbnew
source .venv/bin/activate
pip install -e '.[dev]'
python -c "import pcbnew; print(pcbnew.GetBuildVersion())"
python -c "import kipy; print(kipy.__version__)" || true
```

#### 1.3 `start-server.sh` and `start-server.ps1` (30 min)

Same shape as original, plus `PlatformHelper.apply_environment()` invocation.

#### 1.4 Backend abstraction (2–3 h)

Direct ports of `python/kicad_api/{base,ipc_backend,swig_backend,factory}.py` into `kicad_mcp/backends/`. Keep method names identical so the existing command modules port over without rename.

#### 1.5 Minimal server with router skeleton (1 h)

`kicad_mcp/server.py` registers:
- `ping`, `get_kicad_version`, `get_backend_state` (always visible)
- 4 router meta-tools (`list_tool_categories`, `get_category_tools`, `search_tools`, `execute_tool`) — initially returning empty categories
- 0 routed tools, 0 prompts, 0 resources

**✓ Checkpoint 1:** `scripts/test_mcp.sh` shows server starts, `tools/list` returns 7 tools, `prompts/list` and `resources/list` return `[]`.

---

### PHASE 2 — Project, Board & UI (4–6 h)

Implement the lifecycle tools that everything else depends on.

| Tool | Source |
|---|---|
| `create_project` | `commands/project.py::create_project` (creates `.kicad_pro` + `.kicad_sch` + `.kicad_pcb` using `templates/minimal.kicad_sch` as seed — NOT empty PCB-only as the obsolete spec implied) |
| `open_project`, `save_project`, `get_project_info` | `commands/project.py` |
| `snapshot_project` | renders PDF + saves `<project>/snapshots/<label>/` |
| `set_board_size`, `add_layer`, `set_active_layer`, `get_board_info`, `get_layer_list` | `commands/board.py` |
| `add_board_outline` (rect / rounded_rectangle with `cornerRadius` fix / circle / polygon) | `commands/board.py` |
| `add_mounting_hole`, `add_board_text`, `add_zone`, `get_board_extents`, `get_board_2d_view` | `commands/board.py` |
| `import_svg_logo` | `commands/svg_import.py` — curves linearised to polygons |
| `get_backend_state`, `check_kicad_ui`, `launch_kicad_ui` | `commands/ui.py` |
| Disk safety (`_board_disk_signature`, `.mcp-backups/`) | `kicad_mcp/disk_safety.py` |

**✓ Checkpoint 2:** `tests/integration/test_project_workflow.py` passes: create project → open → set board size → add outline → snapshot → save.

---

### PHASE 3 — Components, Nets & Routing (6–8 h)

#### 3.1 Component tools (17) — mirror `src/tools/component.ts`

`place_component`, `move_component`, `rotate_component`, `delete_component`, `edit_component`, `find_component`, `get_component_properties`, `add_component_annotation`, `group_components`, `replace_component`, `get_component_pads`, `get_component_list`, `get_pad_position`, `place_component_array`, `align_components`, `check_courtyard_overlaps`, `duplicate_component`.

Bug fix to preserve from the original: B.Cu placement no longer hangs ~30 s in KiCAD 9 (handled by detecting layer before `Flip`).

#### 3.2 Net & routing tools (16) — mirror `src/tools/routing.ts`

`add_net`, `route_trace`, `route_arc_trace`, `add_via`, `add_copper_pour`, `delete_trace`, `query_traces`, `query_zones`, `add_gnd_stitching_vias` (grid / around_refs / in_zones with collision check), `get_nets_list`, `modify_trace`, `create_netclass`, `route_differential_pair`, `refill_zones` (mind SWIG segfault risk — original calls out to Python sub-process for safety), `route_pad_to_pad` (auto-via on layer change, with B.Cu fix), `copy_routing_pattern`.

**✓ Checkpoint 3:** `tests/integration/test_routing.py`: place 2 components → `route_pad_to_pad` → verify via inserted when on opposite layers.

---

### PHASE 4 — Schematic engine (8–12 h)

The largest single subsystem — direct port of `python/commands/{schematic,component_schematic,connection_schematic,library_schematic,dynamic_symbol_loader,wire_manager,wire_dragger,wire_connectivity,pin_locator,schematic_analysis,schematic_snap}.py`.

#### 4.1 Core schematic IO (1 h)
- `create_schematic` (seeded from `templates/minimal.kicad_sch`)
- `load_schematic` (internal — not exposed as MCP tool, used by other tools)
- `export_schematic_svg`, `export_schematic_pdf` (kicad-cli wrappers)

#### 4.2 Dynamic symbol loader (2 h)
Port `dynamic_symbol_loader.py`. Test: load `MCU_ST_STM32F1:STM32F103C8Tx` into an empty schematic and verify `lib_symbols` block.

#### 4.3 Component placement (2 h)
`add_schematic_component`, `delete_schematic_component`, `edit_schematic_component`, `set_schematic_component_property`, `remove_schematic_component_property`, `get_schematic_component`, `list_schematic_components`, `move_schematic_component` (with `preserveWires=true` default via wire_dragger), `rotate_schematic_component`, `annotate_schematic`.

#### 4.4 Wire & label management (2 h)
`add_schematic_wire`, `delete_schematic_wire`, `add_schematic_net_label`, `delete_schematic_net_label`, `move_schematic_net_label`, `add_no_connect`, `add_schematic_hierarchical_label`, `add_sheet_pin`, `add_schematic_text`, `list_schematic_texts`.

#### 4.5 Connectivity tools (2 h)
`connect_to_net` (uses pin_locator), `connect_passthrough` (FFC/ribbon bulk), `get_net_connections`, `get_wire_connections`, `get_net_at_point`, `get_schematic_pin_locations`, `list_schematic_nets`, `list_schematic_wires`, `list_schematic_labels`.

#### 4.6 ERC & netlist & sync (1 h)
`run_erc`, `generate_netlist` (JSON inline, no file), `sync_schematic_to_board` (F8 equivalent — required before any PCB op on a freshly placed schematic).

#### 4.7 Analysis suite (2 h)
`find_overlapping_elements`, `get_elements_in_region`, `find_wires_crossing_symbols`, `find_orphaned_wires`, `list_floating_labels`, `snap_to_grid`, `get_schematic_view`, `get_schematic_view_region`.

**✓ Checkpoint 4:** `tests/integration/test_schematic_workflow.py` end-to-end:
- create project (gets schematic seeded)
- dynamic-load `power:VCC` and `power:GND`
- place STM32 + R1 + C1
- `connect_to_net(U1, VDD, VCC)`, `connect_to_net(U1, VSS, GND)`
- `add_schematic_wire(R1.1, C1.1)`
- `run_erc` returns 0 errors
- `generate_netlist` returns expected pin map
- `sync_schematic_to_board` updates PCB netlist

---

### PHASE 5 — Libraries, Footprint & Symbol Creators (3–4 h)

| Module | Tools |
|---|---|
| `commands/library.py` (footprint libs) | `list_libraries`, `search_footprints`, `list_library_footprints`, `get_footprint_info` |
| `commands/library_symbol.py` | `list_symbol_libraries`, `search_symbols`, `list_library_symbols`, `get_symbol_info` |
| `commands/footprint.py` (creator) | `create_footprint`, `edit_footprint_pad`, `register_footprint_library`, `list_footprint_libraries` |
| `commands/symbol_creator.py` | `create_symbol`, `delete_symbol`, `list_symbols_in_library`, `register_symbol_library` |
| `parsers/kicad_mod_parser.py` | `.kicad_mod` S-expression parser |

**✓ Checkpoint 5:** Create a custom footprint in `tests/fixtures/Custom.pretty`, register it in fp-lib-table, search for it, place it on a board.

---

### PHASE 6 — Design Rules, Export, Freerouting (4–5 h)

#### 6.1 Design rules (8 tools)
`set_design_rules`, `get_design_rules`, `run_drc`, `add_net_class`, `assign_net_to_class`, `set_layer_constraints`, `check_clearance`, `get_drc_violations`.

#### 6.2 Export (8 tools)
`export_gerber` (with drill/map), `export_pdf`, `export_svg`, `export_3d` (STEP/STL/VRML/OBJ via kicad-cli), `export_bom` (CSV/XML/HTML/JSON), `export_netlist` (KiCad XML/Spice/Cadstar/OrcadPCB2 via kicad-cli), `export_position_file`, `export_vrml`.

When `KICAD_MCP_DEV=1`, every `export_gerber` and `snapshot_project` also dumps the MCP session log into `<project>/logs/`.

#### 6.3 Freerouting (4 tools)
`check_freerouting` (verify Java + JAR), `export_dsn`, `autoroute` (DSN → Java → SES → import), `import_ses`. Honour `FREEROUTING_JAR` and `FREEROUTING_JAVA` env vars; fall back to bundled jar inside the package if present.

**✓ Checkpoint 6:** `tests/integration/test_export.py` produces gerbers byte-identical to original output for the fixture board. `test_freerouting.py` (gated on `FREEROUTING_JAR`) routes a 4-net test board.

---

### PHASE 7 — JLCPCB & Datasheet (3–4 h)

#### 7.1 JLCPCB (5 tools)
- `download_jlcpcb_database` — bulk download of 2.5 M+ parts catalog (mirror `download_jlcpcb.py`). Streams to `JLCPCB_DB_PATH` or `~/.kicad-mcp/jlcpcb_parts.db`.
- `search_jlcpcb_parts` — parametric search. **Two sources**: official `commands/jlcpcb.py::JLCPCBClient` (auth-required `jlcpcb.com/shoppingCart/...` endpoint) and public `commands/jlcsearch.py::JLCSearchClient` (no auth). If local DB exists, query it first.
- `get_jlcpcb_part` — by LCSC number; cache-first.
- `get_jlcpcb_database_stats` — local DB counts/last-updated.
- `suggest_jlcpcb_alternatives` — pin-compatible alternatives for a part.

#### 7.2 Datasheet (2 tools)
`enrich_datasheets` (fill missing Datasheet fields in a schematic via LCSC lookup), `get_datasheet_url`.

Standalone CLI: keep `download_jlcpcb.py` at repo root, callable independently for users who want to seed the DB without running the server.

**✓ Checkpoint 7:** `tests/integration/test_jlcpcb_local.py` searches the fixture DB; `test_jlcpcb_api.py` (network-gated) runs a live `search_jlcpcb_parts("10k", package="0603", library_type="Basic")` and gets ≥ 1 result.

---

### PHASE 8 — Resources & Prompts (2–3 h)

#### 8.1 Canonical 8 resources (mirror `python/resources/resource_definitions.py`)
1. `kicad://project/current/info`
2. `kicad://project/current/board`
3. `kicad://project/current/components`
4. `kicad://project/current/nets`
5. `kicad://project/current/layers`
6. `kicad://project/current/design-rules`
7. `kicad://project/current/drc-report`
8. `kicad://board/preview.png`

#### 8.2 Extended TS resources (mirror `src/resources/*.ts`)
- **Project:** `project_files`, `project_status`, `project_summary`, `project_properties`
- **Board:** `board_info`, `layer_list`, `board_extents` (templated), `board_2d_view` (templated), `board_3d_view` (templated), `board_statistics`
- **Component:** `component_list`, `component_details/{ref}`, `component_connections/{ref}`, `component_placement`, `component_groups`, `component_visualization/{ref}`
- **Library:** `component_library/{lib}`, `library_list`, `library_component_details/{lib}/{name}`, `component_footprint/{ref}`, `component_symbol/{ref}`, `component_3d_model/{ref}`

All resources MUST be implemented; the canonical 8 are MVP, the extended set is full parity.

#### 8.3 Prompts (18 — mirror `src/prompts/*.ts`)

| File | Prompt names |
|---|---|
| `routing.py` (5) | `routing_strategy`, `differential_pair_routing`, `high_speed_routing`, `power_distribution`, `via_usage` |
| `component.py` (6) | `component_selection`, `component_placement_strategy`, `component_replacement_analysis`, `component_troubleshooting`, `component_sourcing_properties`, `component_value_calculation` |
| `design.py` (5) | `pcb_layout_review`, `layer_stackup_planning`, `design_rule_development`, `component_selection_guidance`, `pcb_design_optimization` |
| `footprint.py` (2) | `create_footprint_guide`, `footprint_ipc_checklist` |

Each prompt's text body MUST be copied verbatim from the original to preserve LLM behaviour.

**✓ Checkpoint 8:** `tools/list` returns 142 tools; `resources/list` returns the 8 canonical + extended; `prompts/list` returns 18.

---

### PHASE 9 — Testing & Quality (3–4 h)

#### 9.1 Parity check (gate)
`scripts/parity_check.py` regex-scans `src/tools/*.ts` for every `server.tool("...", ...)` call, and asserts each name exists in `kicad_mcp/schemas/tool_schemas.py::TOOL_SCHEMAS`. CI fails on mismatch.

#### 9.2 Unit tests
- `test_registry.py` — direct/routed split matches `registry.ts`.
- `test_schemas.py` — every tool has a schema; every schema validates a sample input.
- `test_backend_factory.py` — auto / ipc / swig selection; `KICAD_BACKEND` env override.
- `test_router.py` — `execute_tool` dispatches; `search_tools` returns expected matches.
- `test_disk_safety.py` — external modification detected; backup rotation.

#### 9.3 Integration tests (per phase)
Already enumerated in checkpoints above.

#### 9.4 MCP protocol compliance
Round-trip every JSON-RPC method against the official MCP test harness if available; otherwise `scripts/test_mcp.sh` covers init / list / call / list-resources / read-resource / list-prompts / get-prompt.

**✓ Checkpoint 9:** `pytest` green; `parity_check.py` green; `test_mcp.sh` green.

---

### PHASE 10 — Documentation (2–3 h)

- `README.md` — install, configure (Claude/Zed/Code), examples, troubleshooting (`No module named 'pcbnew'`, `Context server request timeout`, IPC vs SWIG, KiCad version mismatch).
- `docs/tools.md` — auto-generated from `TOOL_SCHEMAS` by `scripts/generate_tool_docs.py`.
- `docs/backends.md` — IPC vs SWIG comparison, env vars, kicad IPC server enablement.
- `docs/schematic_workflow.md` — dynamic symbol loading, wire engine, connect_to_net, sync_schematic_to_board.
- `docs/jlcpcb_workflow.md` — local DB vs API, downloading the catalog.
- `docs/freerouting_setup.md` — Java install, JAR download, `FREEROUTING_*` env vars.
- `CHANGELOG.md` — track parity-with-upstream.

---

## Full Tool Catalog

**142 server.tool() registrations** grouped by source module. Names and input schemas are taken verbatim from `python/schemas/tool_schemas.py` of the original; the port adds nothing and removes nothing.

### `tools/ui.py` (3)
- `get_backend_state` — active backend, realtime status, loaded paths, dirty state
- `check_kicad_ui` — is KiCAD UI running?
- `launch_kicad_ui` — launch UI (optionally with a project)

### `tools/project.py` (5)
- `create_project`, `open_project`, `save_project`, `get_project_info`, `snapshot_project`

### `tools/board.py` (12)
- `set_board_size`, `add_layer`, `set_active_layer`, `get_board_info`, `get_layer_list`, `add_board_outline`, `add_mounting_hole`, `add_board_text`, `add_zone`, `get_board_extents`, `get_board_2d_view`, `import_svg_logo`

### `tools/component.py` (17)
- `place_component`, `move_component`, `rotate_component`, `delete_component`, `edit_component`, `find_component`, `get_component_properties`, `add_component_annotation`, `group_components`, `replace_component`, `get_component_pads`, `get_component_list`, `get_pad_position`, `place_component_array`, `align_components`, `check_courtyard_overlaps`, `duplicate_component`

### `tools/routing.py` (16)
- `add_net`, `route_trace`, `route_arc_trace`, `add_via`, `add_copper_pour`, `delete_trace`, `query_traces`, `query_zones`, `add_gnd_stitching_vias`, `get_nets_list`, `modify_trace`, `create_netclass`, `route_differential_pair`, `refill_zones`, `route_pad_to_pad`, `copy_routing_pattern`

### `tools/schematic.py` (43)
- `create_schematic`, `add_schematic_component`, `delete_schematic_component`, `edit_schematic_component`, `set_schematic_component_property`, `remove_schematic_component_property`, `get_schematic_component`, `add_schematic_wire`, `add_schematic_net_label`, `add_no_connect`, `connect_to_net`, `get_net_connections`, `get_wire_connections`, `get_schematic_pin_locations`, `connect_passthrough`, `list_schematic_components`, `list_schematic_nets`, `list_schematic_wires`, `list_schematic_labels`, `move_schematic_component`, `rotate_schematic_component`, `annotate_schematic`, `delete_schematic_wire`, `delete_schematic_net_label`, `move_schematic_net_label`, `export_schematic_svg`, `export_schematic_pdf`, `get_schematic_view`, `run_erc`, `generate_netlist`, `sync_schematic_to_board`, `get_schematic_view_region`, `find_overlapping_elements`, `get_elements_in_region`, `find_wires_crossing_symbols`, `list_floating_labels`, `find_orphaned_wires`, `snap_to_grid`, `get_net_at_point`, `add_schematic_hierarchical_label`, `list_schematic_texts`, `add_schematic_text`, `add_sheet_pin`

### `tools/library.py` (4)
- `list_libraries`, `search_footprints`, `list_library_footprints`, `get_footprint_info`

### `tools/library_symbol.py` (4)
- `list_symbol_libraries`, `search_symbols`, `list_library_symbols`, `get_symbol_info`

### `tools/footprint.py` (4 — footprint creator)
- `create_footprint`, `edit_footprint_pad`, `register_footprint_library`, `list_footprint_libraries`

### `tools/symbol_creator.py` (4)
- `create_symbol`, `delete_symbol`, `list_symbols_in_library`, `register_symbol_library`

### `tools/design_rules.py` (8)
- `set_design_rules`, `get_design_rules`, `run_drc`, `add_net_class`, `assign_net_to_class`, `set_layer_constraints`, `check_clearance`, `get_drc_violations`

### `tools/export.py` (8)
- `export_gerber`, `export_pdf`, `export_svg`, `export_3d`, `export_bom`, `export_netlist`, `export_position_file`, `export_vrml`

### `tools/freerouting.py` (4)
- `autoroute`, `export_dsn`, `import_ses`, `check_freerouting`

### `tools/jlcpcb.py` (5)
- `download_jlcpcb_database`, `search_jlcpcb_parts`, `get_jlcpcb_part`, `get_jlcpcb_database_stats`, `suggest_jlcpcb_alternatives`

### `tools/datasheet.py` (2)
- `enrich_datasheets`, `get_datasheet_url`

### `tools/router.py` (3)
- `list_tool_categories` — list all available tool categories and their descriptions
- `get_category_tools` — list the tools in a specific routed category
- `search_tools` — find tools by keyword across all categories

> Note: `execute_tool` is **not** a registered MCP tool. It is only referenced in tool
> description text as guidance for the LLM (telling it to call a discovered routed tool by
> name directly via `tools/call`). The original `src/tools/router.ts` has exactly 3
> `server.tool()` calls, not 4.

**Total:** 3 + 5 + 12 + 17 + 16 + 43 + 4 + 4 + 4 + 4 + 8 + 8 + 4 + 5 + 2 + 3 = **142** registered tools — identical to `src/tools/*.ts`.

---

## Resources Catalog

### Canonical 8 (from `python/resources/resource_definitions.py`)
1. `kicad://project/current/info` — project metadata
2. `kicad://project/current/board` — dims, layers, DRC status
3. `kicad://project/current/components` — components with refs/footprints/positions
4. `kicad://project/current/nets` — nets and connections
5. `kicad://project/current/layers` — layer stack
6. `kicad://project/current/design-rules` — current DR settings
7. `kicad://project/current/drc-report` — last DRC violations/warnings
8. `kicad://board/preview.png` — 2D board PNG (binary)

### Extended (from `src/resources/*.ts`)
- **Project:** `project_files`, `project_status`, `project_summary`, `project_properties`
- **Board:** `board_info`, `layer_list`, `board_extents` (templated), `board_2d_view` (templated), `board_3d_view` (templated), `board_statistics`
- **Component:** `component_list`, `component_details/{ref}`, `component_connections/{ref}`, `component_placement`, `component_groups`, `component_visualization/{ref}`
- **Library:** `component_library/{lib}`, `library_list`, `library_component_details/{lib}/{name}`, `component_footprint/{ref}`, `component_symbol/{ref}`, `component_3d_model/{ref}`

All resources MUST be implemented; the canonical 8 are MVP, the extended set is full parity.

---

## Prompts Catalog

18 prompts mirrored from `src/prompts/*.ts`:

| File | Prompt names |
|---|---|
| `routing.py` (5) | `routing_strategy`, `differential_pair_routing`, `high_speed_routing`, `power_distribution`, `via_usage` |
| `component.py` (6) | `component_selection`, `component_placement_strategy`, `component_replacement_analysis`, `component_troubleshooting`, `component_sourcing_properties`, `component_value_calculation` |
| `design.py` (5) | `pcb_layout_review`, `layer_stackup_planning`, `design_rule_development`, `component_selection_guidance`, `pcb_design_optimization` |
| `footprint.py` (2) | `create_footprint_guide`, `footprint_ipc_checklist` |

Each prompt's text body MUST be copied verbatim from the original to preserve LLM behaviour.

---

## Testing Strategy

### Levels

1. **Parity check** (`scripts/parity_check.py`) — names of tools, resources, prompts match the originals exactly.
2. **Schema unit tests** — every JSON Schema entry validates at least one sample input.
3. **Backend unit tests** — IPC and SWIG implementations against the `KiCadBackend` contract (using `kipy` mock + `pcbnew` if available).
4. **Per-phase integration tests** — listed in each phase checkpoint.
5. **MCP protocol e2e** — `scripts/test_mcp.sh` for stdio smoke; optional MCP Inspector integration.
6. **Golden fixture comparisons** — for `export_gerber`, `export_dsn`, `generate_netlist`, diff against fixtures generated by the original implementation.

### Test environment gating

- `pytest -m "not network"` — skip JLCPCB API live tests
- `pytest -m "not requires_kicad_ui"` — skip IPC live tests
- `pytest -m "not requires_freerouting"` — skip autoroute tests
- CI runs all three exclusions; nightly runs everything.

---

## Deployment

### Installing for end users

```bash
git clone https://github.com/<you>/kicad-mcp-python
cd kicad-mcp-python
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e .
python -c "import pcbnew; print(pcbnew.GetBuildVersion())"
```

### MCP client config

**Claude Desktop / Code (`~/.claude/settings.json`):**
```json
{
  "mcpServers": {
    "kicad": {
      "command": "/abs/path/kicad-mcp-python/start-server.sh",
      "timeout": 120000,
      "env": {
        "KICAD_BACKEND": "auto",
        "KICAD_AUTO_LAUNCH": "1",
        "KICAD_MCP_DEV": "0"
      }
    }
  }
}
```

**Zed (`~/.config/zed/settings.json`):**
```json
{
  "context_servers": {
    "kicad": {
      "command": "/abs/path/kicad-mcp-python/start-server.sh",
      "source": "custom"
    }
  }
}
```

### Optional: Freerouting

```bash
sudo apt install default-jre        # or: brew install openjdk
curl -L -o ~/.kicad-mcp/freerouting.jar https://github.com/freerouting/freerouting/releases/latest/download/freerouting-executable.jar
export FREEROUTING_JAR=~/.kicad-mcp/freerouting.jar
```

### Optional: JLCPCB local database

```bash
python download_jlcpcb.py              # one-time bulk download, ~2 GB
# Or via MCP tool: ask Claude to run `download_jlcpcb_database`
```

---

## Timeline & Milestones

| Phase | Duration | Deliverable | Status |
|---|---|---|---|
| 0 — Mapping & schema extraction | 1–2 h | `TOOL_SCHEMAS`, registry data, parity_check.py | Critical |
| 1 — Foundation + backends + router skeleton | 4–6 h | Minimal server, IPC+SWIG factory, router meta-tools | Critical |
| 2 — Project, board & UI | 4–6 h | Lifecycle tools, disk safety, snapshot | Critical |
| 3 — Components, nets, routing | 6–8 h | 17 + 16 = 33 tools | Critical |
| 4 — Schematic engine | 8–12 h | 43 schematic tools + dynamic loader + wire engine | Critical |
| 5 — Libraries + footprint/symbol creator | 3–4 h | 16 tools | Critical |
| 6 — DRC + export + freerouting | 4–5 h | 20 tools | Critical |
| 7 — JLCPCB + datasheet | 3–4 h | 7 tools, local DB, dual-source API | Important |
| 8 — Resources + prompts | 2–3 h | 8 canonical + extended resources, 18 prompts | Critical |
| 9 — Testing | 3–4 h | parity_check green, pytest green | Critical |
| 10 — Documentation | 2–3 h | README, docs/, auto-gen tool ref | Critical |
| **TOTAL** | **40–57 h** | **Full-parity Pure Python port** | |

### Minimum Viable Product (MVP)

For a useful early version:
1. Phase 0 (mapping)
2. Phase 1 (foundation + backends)
3. Phase 7 (JLCPCB) — the standout feature
4. Phase 2 (basic project/board)
5. Test with Claude Desktop

MVP gives JLCPCB-empowered project bootstrap. **~12–17 h.**

---

## Success Criteria — Final Acceptance

- `scripts/parity_check.py` — every tool name in `src/tools/*.ts` exists in `kicad_mcp/schemas/tool_schemas.py`.
- `tools/list` returns exactly the same direct set as `src/tools/registry.ts::directToolNames` (plus always-visible extras).
- `list_tool_categories` returns the same 8 routed categories with the same membership as `registry.ts`.
- All 8 canonical resources resolve; extended TS resources implemented.
- All 18 prompts implemented with original text bodies.
- IPC backend used when KiCAD is running with IPC API server; SWIG fallback when not. `KICAD_BACKEND` env overrides.
- Full schematic workflow demo (create → dynamic-load STM32 → wire → ERC → netlist → sync_schematic_to_board) succeeds.
- Freerouting `autoroute` succeeds on the fixture board when `FREEROUTING_JAR` is set.
- `search_jlcpcb_parts` returns ≥ 1 part for `"10k", package="0603", library_type="Basic"` via either API path; returns results from local DB when populated.
- Disk safety: external edit of a tracked file is detected; `.mcp-backups/` retains last N versions.
- No Node.js, no npm, no TypeScript in the install path.

---

## Future Enhancements

### v2.2
- Bundled Freerouting JAR (auto-download on first `autoroute` if `FREEROUTING_JAR` unset)
- WebSocket transport in addition to stdio
- Subscribe to KiCAD IPC change-callbacks → MCP resource update notifications

### v2.3
- Multi-board project support
- Panel generation
- Manufacturing DFM checks (acid traps, isolated copper, etc.)

### v3.0
- Collaborative editing via shared IPC session
- AI-suggested placement (LLM-guided `place_component_array`)

---

## Notes

- **Startup time:** ~60 s when using SWIG (wxApp init). Near-zero when using IPC and KiCAD UI is already up. The IPC backend is the recommended default for KiCAD 9.0+.
- **Python version:** MUST match the Python KiCad ships. `python3 --version` and `python -c "import sys; print(sys.path)"` to check. KiCAD 9 ships Python 3.11; KiCAD 10 ships 3.13.
- **`--system-site-packages` is non-negotiable** for the SWIG path — without it `import pcbnew` fails. The IPC path uses `kipy` which is a normal pip package.
- **Tool development order:** start with read-only tools (`get_*`, `list_*`) before mutators. Easier to spot regressions and easier to fixture.
- **Errors:** every tool returns either `{success: true, data: ...}` or `{success: false, error: "<user-readable>"}` (mirror `src/tools/tool-response.ts`). Never leak raw stack traces to the client.
- **Bug-for-bug compatibility:** if the original has a quirk (e.g. B.Cu placement freeze workaround, refill_zones segfault workaround), the port keeps the same workaround so users get the same behaviour. Improvements come later, after parity.

---

## Open Problems & TODO (session 2026-05-25)

### Schematic wire UX — FIXED

**Problem:** `add_schematic_wire` required the caller to look up exact pin coordinates first via
`get_schematic_pin_locations` and pass raw `waypoints`. Forgetting to look up coords, or using
slightly wrong values, broke the connection silently.

**Fix (this session):**
- `add_schematic_wire` now accepts `fromRef`/`fromPin`/`toRef`/`toPin` as a first-class
  alternative to `waypoints`. The dispatcher calls `PinLocator.get_pin_location()` internally
  to resolve exact coordinates.
- Optional `via` list allows intermediate bend-points when routing around obstacles.
- `waypoints` still works for callers that already know coordinates.
- Schema updated; description says "PREFERRED: use fromRef/fromPin/toRef/toPin".

### Unimplemented `_sch_delegate` stubs (~20 tools return "not yet routed")

The following schematic tools hit `_sch_delegate` and return an error instead of working:

| Tool | Needed for |
|------|-----------|
| `move_schematic_component` | repositioning placed parts |
| `rotate_schematic_component` | flipping components |
| `delete_schematic_wire` | editing wiring |
| `delete_schematic_net_label` | editing labels |
| `move_schematic_net_label` | editing labels |
| `list_schematic_nets` | ERC prep, netlist review |
| `list_schematic_labels` | connectivity check |
| `list_schematic_texts` | annotation review |
| `edit_schematic_component` | changing values/footprints |
| `set_schematic_component_property` | setting LCSC/footprint |
| `remove_schematic_component_property` | cleaning properties |
| `get_schematic_component` | inspecting properties |
| `add_schematic_junction` | T-wire junctions |
| `add_schematic_power_symbol` | PWR_FLAG symbols |
| `add_schematic_bus` | bus routing |
| `add_sheet_pin` | hierarchical sheets |
| `annotate_schematic` | auto-reference numbering |
| `run_erc` | error check |
| `export_schematic_pdf` | PDF output |
| `export_schematic_svg` | SVG output |
| `sync_schematic_to_board` | PCB sync after schematic edit |
| `connect_to_net` / `connect_passthrough` | high-level connectivity |

These need concrete implementations (skip/sexpdata/kicad-cli) added to `dispatcher.py`.

### JLCPCB integration

**Fixed this session** (`kicad_mcp/dispatcher.py`):
- `_handle_search_jlcpcb_parts` was passing the raw `params` dict to `JLCPCBPartsManager.search_parts`, which expects named kwargs → crashed with `'dict' object has no attribute 'strip'`. Now unpacks `query`/`category`/`package`/`basic`/`inStock`/`limit`.
- `_handle_get_jlcpcb_part` called non-existent `get_part(params)` → fixed to `get_part_info(partNumber)`.
- `_handle_get_jlcpcb_database_stats` called non-existent `get_stats(params)` → fixed to `get_database_stats()`.
- `_handle_suggest_jlcpcb_alternatives` was passing dict → now unpacks `reference`/`limit`.
- `_handle_download_jlcpcb_database` rewritten to dispatch by `source` param: `jlcsearch` (default) / `sqlite` / `official`.

**Open**:

1. **yaqwsx/jlcparts multi-volume zip not implemented.** The new `kicad_mcp/commands/sqlite_loader.py::SqliteBulkLoader` assumes a single-file artifact (zip-with-one-sqlite, or raw .sqlite3) via GitHub Releases API. Reality:
   - yaqwsx hosts on **GitHub Pages**, not Releases — base URL `https://yaqwsx.github.io/jlcparts/data/`.
   - Files: `cache.zip` + `cache.z01 .. cache.z30+` (~50 MB/part, ~1.5 GB total compressed).
   - This is a **multi-volume split zip**; Python `zipfile` can't extract it. Use `/usr/bin/7z x cache.zip` after downloading all parts.
   - TODO: add URL-list mode to `SqliteBulkLoader`; auto-probe `cache.z01..` until 404; shell out to `7z`; locate the extracted `cache.sqlite3`; pass rows through `import_jlcsearch_parts`. Default URL base = yaqwsx Pages.

2. **yaqwsx schema not verified against `import_jlcsearch_parts` field names.** Once (1) lands, run `PRAGMA table_info(<largest_table>)` on the extracted SQLite and confirm columns map cleanly. Likely needs a `import_yaqwsx_parts()` variant with explicit field mapping.

3. **Official JLCPCB API registration URL unknown.** Code path (`source: "official"`) works if `JLCPCB_APP_ID` / `JLCPCB_API_KEY` / `JLCPCB_API_SECRET` env vars are set, but the public signup URL is undocumented in our repo and my guess of `jlcpcb.com/developer` was 404. Find and document the correct flow, or mark the official path as "bring your own creds, contact JLCPCB support".

4. **JLCSearch full-catalog scrape works but is slow.** ~25k requests at 100 parts/page, ~40-60 min for the full DB. Suitable as default fallback for users who don't want auth; recommend bulk-SQLite once (1) is implemented.

### Live demo deferred

5. **555 astable LED blinker schematic** — pending. Will build with KiCAD's built-in symbol libraries (`Timer:NE555P`, `Device:R/C/LED`) and attach LCSC IDs via live `JLCSearch` query rather than full DB download.

---

END OF PLAN.md
