"""
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
    tool_run_optimization_simulation,
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
                    "description": (
                        "Capacity k: simulated max_capacity at hub = k × nominal DB value. "
                        "k=1.0 = no change; k=0.8 = 20% below nominal (typical stress). "
                        "Clamped to [0.5, 1.0] for the stress step."
                    ),
                },
                "run_sweet_spot": {
                    "type": "boolean",
                    "description": (
                        "If true, grid-search hub_capacity k (default ~0.75–1.35) for best ROI recovery vs delayed cohort; "
                        "same k semantics as capacity_multiplier."
                    ),
                    "default": True,
                },
            },
            "required": ["date_range", "target_hub", "capacity_multiplier"],
        },
    },
    {
        "name": "run_optimization_simulation",
        "description": (
            "Run supply-chain optimization: AI recommendations constrained to five simulatable levers, "
            "then ROI sweet-spot curves (investment vs on-time recovery). Hub capacity uses k "
            "(C_sim = k × max_capacity; k=1.0 no increase, k=1.2 = +20% vs nominal). "
            "Use for efficiency, minimum investment, ROI, or which lever to pull questions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "date_range": {
                    "type": "string",
                    "description": "One of: yesterday, week, month, year.",
                },
                "max_levers": {
                    "type": "integer",
                    "description": "Max lever curves to compute (1–5). Default 4.",
                    "default": 4,
                },
            },
            "required": ["date_range"],
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
                "capacity_multiplier": {
                    "type": "number",
                    "description": "Hub capacity k (C_sim = k × max_capacity); k=1.0 baseline, k<1 stress.",
                },
                "run_sweet_spot": {
                    "type": "boolean",
                    "description": "Search best recovery k on default grid (~0.75–1.35).",
                },
            },
            "required": ["date_range", "target_hub", "capacity_multiplier"],
        },
    ),
    _openai_fn(
        "run_optimization_simulation",
        "Optimization plus ROI sweet-spot simulation. Hub capacity lever uses k (C_sim = k × max_capacity; k=1.0 baseline, k=1.2 = +20%).",
        {
            "type": "object",
            "properties": {
                "date_range": {
                    "type": "string",
                    "enum": ["yesterday", "week", "month", "year"],
                },
                "max_levers": {"type": "integer", "description": "1–5, default 4"},
            },
            "required": ["date_range"],
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
                        "optimization_simulation",
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
    if name == "run_optimization_simulation":
        ml = args.get("max_levers", 4)
        try:
            ml = int(ml)
        except (TypeError, ValueError):
            ml = 4
        return tool_run_optimization_simulation(
            args.get("date_range") or "week",
            None,
            None,
            ml,
        )
    if name == "submit_planner_decision":
        return {
            "pipeline": args.get("pipeline"),
            "reason": args.get("reason", ""),
        }
    raise ValueError(f"Unknown tool: {name}")


def tool_result_to_text(obj: Any) -> str:
    return json.dumps(obj, indent=2, default=str)
