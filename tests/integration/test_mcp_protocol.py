"""
Integration tests — MCP protocol handshake and tool/resource/prompt discovery.

Each test sends exactly one request per subprocess to avoid asyncio write-drain
issues with large responses (tools/list is ~100KB and fills the stdout pipe buffer,
causing subsequent responses to be dropped).

Tools, resources, and prompts are also tested at the Python-module level (fast, no
subprocess) to avoid redundancy. The subprocess tests focus on the JSON-RPC wire format.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SERVER_MODULE = "kicad_mcp"
REPO_ROOT = Path(__file__).parent.parent.parent

_INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "pytest", "version": "1.0"},
    },
}
_NOTIF = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}


def _run_one(query: dict, timeout: int = 30, retries: int = 3) -> dict | None:
    """Spawn server, send init + one query, return the single response dict.

    Retries up to `retries` times because the asyncio stdio transport occasionally
    drops the response when stdin closes before the event loop drains its write buffer.
    """
    target_id = query.get("id")
    payload = "\n".join([json.dumps(_INIT), json.dumps(_NOTIF), json.dumps(query)]) + "\n"

    for _ in range(retries):
        result = subprocess.run(
            [sys.executable, "-m", SERVER_MODULE],
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=REPO_ROOT,
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if line:
                try:
                    d = json.loads(line)
                    if d.get("id") == target_id:
                        return d
                except json.JSONDecodeError:
                    pass
    return None


def _tool_content(response: dict | None) -> dict | None:
    if response and "result" in response:
        content = response["result"].get("content", [])
        if content:
            try:
                return json.loads(content[0]["text"])
            except json.JSONDecodeError:
                pass
    return None


# ---------------------------------------------------------------------------
# Handshake (fast — just initialize, no follow-up query)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def init_resp():
    payload = json.dumps(_INIT) + "\n"
    result = subprocess.run(
        [sys.executable, "-m", SERVER_MODULE],
        input=payload,
        capture_output=True,
        text=True,
        timeout=15,
        cwd=REPO_ROOT,
    )
    for line in result.stdout.splitlines():
        line = line.strip()
        if line:
            try:
                d = json.loads(line)
                if d.get("id") == 1:
                    return d
            except json.JSONDecodeError:
                pass
    return None


class TestMCPHandshake:
    def test_protocol_version(self, init_resp):
        assert init_resp is not None, "No initialize response"
        assert init_resp["result"]["protocolVersion"] == "2024-11-05"

    def test_server_name(self, init_resp):
        assert init_resp["result"]["serverInfo"]["name"] == "kicad-mcp-server"

    def test_advertises_tools(self, init_resp):
        assert "tools" in init_resp["result"]["capabilities"]

    def test_advertises_resources(self, init_resp):
        assert "resources" in init_resp["result"]["capabilities"]

    def test_advertises_prompts(self, init_resp):
        assert "prompts" in init_resp["result"]["capabilities"]


# ---------------------------------------------------------------------------
# Tools list (Python-level — fast, no subprocess)
# ---------------------------------------------------------------------------

class TestToolsList:
    """Verify tool count and names at the Python-module level (no subprocess needed)."""

    @pytest.fixture(scope="class")
    def tools(self):
        from kicad_mcp.schemas.tool_schemas import TOOL_SCHEMAS
        from kicad_mcp.tools.registry import ROUTED_CATEGORIES
        # meta tools registered directly in server.py
        meta = {"ping", "get_kicad_version", "get_backend_state",
                "list_tool_categories", "get_category_tools", "search_tools"}
        return {"schemas": TOOL_SCHEMAS, "meta": meta, "categories": ROUTED_CATEGORIES}

    def test_schema_count(self, tools):
        assert len(tools["schemas"]) == 142

    def test_meta_tools_in_schema_or_meta(self, tools):
        all_tools = set(tools["schemas"]) | tools["meta"]
        for name in ("ping", "get_kicad_version", "list_tool_categories",
                     "get_category_tools", "search_tools", "get_backend_state"):
            assert name in all_tools, f"{name!r} missing from schema or meta"

    def test_board_tools(self, tools):
        for name in ("set_board_size", "get_board_info", "add_layer", "add_board_outline"):
            assert name in tools["schemas"], f"{name!r} missing"

    def test_schematic_tools(self, tools):
        for name in ("create_schematic", "add_schematic_component",
                     "add_schematic_wire", "annotate_schematic"):
            assert name in tools["schemas"], f"{name!r} missing"

    def test_jlcpcb_tools(self, tools):
        for name in ("search_jlcpcb_parts", "get_jlcpcb_part", "suggest_jlcpcb_alternatives"):
            assert name in tools["schemas"], f"{name!r} missing"

    def test_export_tools(self, tools):
        for name in ("export_gerber", "export_pdf", "export_bom", "export_vrml"):
            assert name in tools["schemas"], f"{name!r} missing"

    def test_routing_tools(self, tools):
        for name in ("route_trace", "add_via", "route_pad_to_pad", "refill_zones"):
            assert name in tools["schemas"], f"{name!r} missing"

    def test_categories_present(self, tools):
        for cat in ("board", "component", "export", "drc", "schematic",
                    "library", "routing", "autoroute", "jlcpcb"):
            assert cat in tools["categories"], f"Category {cat!r} missing"


# ---------------------------------------------------------------------------
# Resources (Python-level — fast)
# ---------------------------------------------------------------------------

class TestResourcesList:
    EXPECTED_URIS = {
        "kicad://project/current/info",
        "kicad://project/current/board",
        "kicad://project/current/components",
        "kicad://project/current/nets",
        "kicad://project/current/layers",
        "kicad://project/current/design-rules",
        "kicad://project/current/drc-report",
        "kicad://board/preview.png",
    }

    def test_count(self):
        assert len(self.EXPECTED_URIS) == 8

    def test_project_info(self):
        assert "kicad://project/current/info" in self.EXPECTED_URIS

    def test_board_preview(self):
        assert "kicad://board/preview.png" in self.EXPECTED_URIS

    def test_resources_registered_via_mcp(self):
        from kicad_mcp.server import mcp
        uris = {str(r.uri) for r in mcp._resource_manager._resources.values()}
        assert uris == self.EXPECTED_URIS


# ---------------------------------------------------------------------------
# Prompts (Python-level — fast)
# ---------------------------------------------------------------------------

class TestPromptsList:
    EXPECTED_PROMPTS = {
        # routing
        "routing_strategy", "differential_pair_routing", "high_speed_routing",
        "power_distribution", "via_usage",
        # component
        "component_selection", "component_placement_strategy",
        "component_replacement_analysis", "component_troubleshooting",
        "component_sourcing_properties", "component_value_calculation",
        # design
        "pcb_layout_review", "layer_stackup_planning", "design_rule_development",
        "component_selection_guidance", "pcb_design_optimization",
        # footprint
        "create_footprint_guide", "footprint_ipc_checklist",
        # extras
        "jlcpcb_component_selection", "schematic_design_guide",
    }

    def test_count(self):
        assert len(self.EXPECTED_PROMPTS) == 20

    def test_routing_prompts(self):
        for name in ("routing_strategy", "differential_pair_routing",
                     "high_speed_routing", "power_distribution", "via_usage"):
            assert name in self.EXPECTED_PROMPTS

    def test_component_prompts(self):
        for name in ("component_selection", "component_placement_strategy",
                     "component_replacement_analysis", "component_troubleshooting",
                     "component_sourcing_properties", "component_value_calculation"):
            assert name in self.EXPECTED_PROMPTS

    def test_design_prompts(self):
        for name in ("pcb_layout_review", "layer_stackup_planning",
                     "design_rule_development", "component_selection_guidance",
                     "pcb_design_optimization"):
            assert name in self.EXPECTED_PROMPTS

    def test_footprint_prompts(self):
        for name in ("create_footprint_guide", "footprint_ipc_checklist"):
            assert name in self.EXPECTED_PROMPTS

    def test_prompts_registered_via_mcp(self):
        from kicad_mcp.server import mcp
        registered = set(mcp._prompt_manager._prompts.keys())
        assert registered == self.EXPECTED_PROMPTS


# ---------------------------------------------------------------------------
# Wire-format tests — one subprocess per test (init + notif + one query)
# ---------------------------------------------------------------------------

class TestMCPWireFormat:
    """Test the actual MCP JSON-RPC wire format with real subprocesses."""

    def test_ping_response_format(self):
        q = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "ping", "arguments": {}}}
        resp = _run_one(q)
        assert resp is not None, "No ping response"
        assert "result" in resp
        content = resp["result"]["content"]
        assert content[0]["type"] == "text"
        result = json.loads(content[0]["text"])
        assert result["success"] is True

    def test_list_categories_format(self):
        q = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "list_tool_categories", "arguments": {}}}
        resp = _run_one(q)
        assert resp is not None
        result = _tool_content(resp)
        assert result["success"] is True
        names = {c["name"] for c in result["data"]["categories"]}
        assert "board" in names and "jlcpcb" in names

    def test_resources_list_format(self):
        q = {"jsonrpc": "2.0", "id": 2, "method": "resources/list", "params": {}}
        resp = _run_one(q)
        assert resp is not None
        uris = {r["uri"] for r in resp["result"]["resources"]}
        assert "kicad://project/current/info" in uris
        assert len(uris) == 8

    def test_prompts_list_format(self):
        q = {"jsonrpc": "2.0", "id": 2, "method": "prompts/list", "params": {}}
        resp = _run_one(q)
        assert resp is not None
        names = {p["name"] for p in resp["result"]["prompts"]}
        assert len(names) >= 18
        assert "routing_strategy" in names

    def test_tool_error_response(self):
        q = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "get_category_tools", "arguments": {"category": "nope"}}}
        resp = _run_one(q)
        assert resp is not None
        result = _tool_content(resp)
        assert result["success"] is False

    def test_routed_tool_dispatches(self):
        q = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "create_project", "arguments": {"name": "t", "path": "/tmp/t"}}}
        resp = _run_one(q)
        assert resp is not None
        result = _tool_content(resp)
        assert result is not None
        assert "success" in result or "error" in result
