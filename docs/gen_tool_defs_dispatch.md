~~~~python
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "SupplyMindAI"

TOOL_DEFS = '''"""
OpenAI + MCP tool schemas and local execution for SupplyMind advisor.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from advisor.tools_impl import (
    tool_get_delivered_cohort_summary,
    tool_get_in_transit_aggregate,
    tool_list_hub_names,
    tool_run_capacity_stress_pipeline,
)

# MCP tools/list format (DS-AIforSystemsEng mcp_fastapi style)
MCP_TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_hub_names",
        "description": "List all logistics hub names in the database (sorted).",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_in_transit_aggregate",
        "description": "Aggregate in-transit shipments: counts, future risk mix, hubs with exposure, insight flags.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_delivered_cohort_summary",
        "description": "Summary of delivered shipments for a baseline window (counts and delay metrics, no raw rows).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date_range": {
                    "type": "string",
                    "description": "One of: yesterday, week, month, year.",
                },
            },
            "required": ["date_range"],
        },
    },
    {
        "name": "run_capacity_stress_pipeline",
        "description": "Load delivered cohort for the window, run hub capacity stress simulation and optional recovery sweet-spot search.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date_range": {"type": "string"},
                "target_hub": {"type": "string", "description": "Hub name to stress."},
                "capacity_multiplier": {
                    "type": "number",
                    "description": "1.0 = baseline; 0.8 = 20% capacity cut at hub.",
                },
                "run_sweet_spot": {
                    "type": "boolean",
                    "description": "Whether to search for a recovery multiplier sweet spot.",
                    "default": True,
                },
            },
            "required": ["date_range", "target_hub", "capacity_multiplier"],
        },
    },
]


def _openai_fn(name: str, description: str, schema: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": schema,
        },
    }


OPENAI_TOOL_FUNCTIONS: list[dict[str, Any]] = [
    _openai_fn(
        "list_hub_names",
        "List all logistics hub names in the database.",
        {"type": "object", "properties": {}, "required": []},
    ),
    _openai_fn(
        "get_in_transit_aggregate",
        "In-transit shipment aggregates and risk exposure.",
        {"type": "object", "properties": {}, "required": []},
    ),
    _openai_fn(
        "get_delivered_cohort_summary",
        "Delivered cohort summary for baseline window (counts + metrics).",
        {
            "type": "object",
            "properties": {
                "date_range": {
                    "type": "string",
                    "enum": ["yesterday", "week", "month", "year"],
                },
            },
            "required": ["date_range"],
        },
    ),
    _openai_fn(
        "run_capacity_stress_pipeline",
        "Run capacity stress + optional sweet spot for a hub over a date window.",
        {
            "type": "object",
            "properties": {
                "date_range": {"type": "string"},
                "target_hub": {"type": "string"},
                "capacity_multiplier": {"type": "number"},
                "run_sweet_spot": {"type": "boolean"},
            },
            "required": ["date_range", "target_hub", "capacity_multiplier"],
        },
    ),
    _openai_fn(
        "submit_planner_decision",
        "Submit the chosen advisor pipeline after optional data gathering.",
        {
            "type": "object",
            "properties": {
                "pipeline": {
                    "type": "string",
                    "enum": [
                        "full_stress",
                        "operational_snapshot",
                        "delivered_analytics",
                    ],
                },
                "reason": {"type": "string"},
            },
            "required": ["pipeline", "reason"],
        },
    ),
]


def run_supply_tool_local(name: str, arguments: Optional[dict[str, Any]] = None) -> Any:
    args = arguments or {}
    if name == "list_hub_names":
        return tool_list_hub_names()
    if name == "get_in_transit_aggregate":
        return tool_get_in_transit_aggregate()
    if name == "get_delivered_cohort_summary":
        return tool_get_delivered_cohort_summary(args.get("date_range") or "week")
    if name == "run_capacity_stress_pipeline":
        return tool_run_capacity_stress_pipeline(
            args.get("date_range") or "week",
            args.get("target_hub") or "",
            float(args.get("capacity_multiplier") or 0.8),
            None,
            None,
            bool(args.get("run_sweet_spot", True)),
        )
    if name == "submit_planner_decision":
        return {
            "pipeline": args.get("pipeline"),
            "reason": args.get("reason", ""),
        }
    raise ValueError(f"Unknown tool: {name}")


def tool_result_to_text(obj: Any) -> str:
    return json.dumps(obj, indent=2, default=str)
'''

DISPATCH = '''"""
Route tool calls to local advisor functions or MCP HTTP server (course-style JSON-RPC).
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional

import httpx

from advisor.tool_defs import run_supply_tool_local, tool_result_to_text


def _mcp_url() -> str:
    u = (os.environ.get("SUPPLYMIND_MCP_URL") or "http://127.0.0.1:8765/mcp").strip().rstrip("/")
    return u if u.endswith("/mcp") else u + "/mcp"


def _tools_mode() -> str:
    return (os.environ.get("SUPPLYMIND_TOOLS_MODE") or "local").strip().lower()


class ToolDispatch:
    def __init__(self) -> None:
        self.mode = _tools_mode()
        self.mcp_url = _mcp_url()
        self._rid = 0

    def call(self, name: str, arguments: Optional[dict[str, Any]] = None) -> Any:
        args = arguments or {}
        if self.mode != "mcp":
            return run_supply_tool_local(name, args)
        return self._mcp_tools_call(name, args)

    def _mcp_tools_call(self, name: str, arguments: dict[str, Any]) -> Any:
        self._rid += 1
        body = {
            "jsonrpc": "2.0",
            "id": self._rid,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        with httpx.Client(timeout=120.0) as client:
            r = client.post(self.mcp_url, json=body)
            r.raise_for_status()
            data = r.json()
        if "error" in data:
            raise RuntimeError(data["error"].get("message", str(data["error"])))
        result = data.get("result") or {}
        if result.get("isError"):
            raise RuntimeError(result.get("content", [{}])[0].get("text", "tool error"))
        parts = result.get("content") or []
        if not parts:
            return None
        text = parts[0].get("text") or ""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    def call_text(self, name: str, arguments: Optional[dict[str, Any]] = None) -> str:
        return tool_result_to_text(self.call(name, arguments))


def get_dispatch() -> ToolDispatch:
    return ToolDispatch()
'''

def main():
    (ROOT / "advisor" / "tool_defs.py").write_text(TOOL_DEFS, encoding="utf-8")
    (ROOT / "advisor" / "tool_dispatch.py").write_text(DISPATCH, encoding="utf-8")
    print("wrote tool_defs.py tool_dispatch.py")

if __name__ == "__main__":
    main()
~~~~
