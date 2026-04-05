"""
Route What-If advisor tool calls to the MCP HTTP server (course-style JSON-RPC POST /mcp).

The MCP process must be running (e.g. uvicorn mcp_server.server:app) or tool calls will fail.
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional

import httpx

from advisor.tool_defs import tool_result_to_text


def _mcp_url() -> str:
    u = (os.environ.get("SUPPLYMIND_MCP_URL") or "http://127.0.0.1:8765/mcp").strip().rstrip("/")
    return u if u.endswith("/mcp") else u + "/mcp"


class ToolDispatch:
    def __init__(self) -> None:
        self.mode = "mcp"
        self.mcp_url = _mcp_url()
        self._rid = 0

    def call(self, name: str, arguments: Optional[dict[str, Any]] = None) -> Any:
        args = arguments or {}
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
