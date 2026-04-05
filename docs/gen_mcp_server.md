~~~~python
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "SupplyMindAI"

SERVER = '''# SupplyMind MCP server — FastAPI, course-style JSON-RPC POST /mcp
# Run: uvicorn mcp_server.server:app --host 127.0.0.1 --port 8765
# From inner SupplyMindAI dir (same as shiny), or set PYTHONPATH.

from __future__ import annotations

import json
import sys
from pathlib import Path

_inner = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_inner.parent))
sys.path.insert(0, str(_inner))

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from advisor.tool_defs import MCP_TOOLS, run_supply_tool_local, tool_result_to_text

app = FastAPI()


def run_tool(name: str, args: dict) -> str:
    try:
        out = run_supply_tool_local(name, args)
        return tool_result_to_text(out)
    except Exception as e:
        raise ValueError(str(e)) from e


@app.post("/mcp")
async def mcp_post(request: Request):
    body = await request.json()
    method = body.get("method")
    id_ = body.get("id")
    if isinstance(method, str) and method.startswith("notifications/"):
        return Response(status_code=202)
    try:
        if method == "initialize":
            result = {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "supplymind-mcp", "version": "0.1.0"},
            }
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": MCP_TOOLS}
        elif method == "tools/call":
            tool_result = run_tool(
                body["params"]["name"],
                body["params"].get("arguments") or {},
            )
            result = {
                "content": [{"type": "text", "text": tool_result}],
                "isError": False,
            }
        else:
            raise ValueError(f"Method not found: {method}")
    except Exception as e:
        return JSONResponse(
            {"jsonrpc": "2.0", "id": id_, "error": {"code": -32601, "message": str(e)}}
        )
    return JSONResponse({"jsonrpc": "2.0", "id": id_, "result": result})


@app.options("/mcp")
async def mcp_options():
    return Response(
        status_code=204,
        headers={"Allow": "GET, POST, OPTIONS"},
    )


@app.get("/mcp")
async def mcp_get():
    return Response(
        content=json.dumps(
            {"error": "This MCP server uses stateless HTTP. Use POST."}
        ),
        status_code=405,
        headers={"Allow": "GET, POST, OPTIONS"},
        media_type="application/json",
    )
'''

RUNME = '''import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "mcp_server.server:app",
        host="127.0.0.1",
        port=8765,
        reload=True,
    )
'''

README = '''# SupplyMind MCP server

Stateless MCP over HTTP (`POST /mcp`), aligned with
[DS-AIforSystemsEng mcp_fastapi](https://github.com/janhaviprof-bot/DS-AIforSystemsEng/tree/main/08_function_calling/mcp_fastapi).

## Run

From the **inner** `SupplyMindAI` folder (the one that contains `app.py` and `advisor/`):

```bash
pip install fastapi uvicorn httpx
uvicorn mcp_server.server:app --host 127.0.0.1 --port 8765 --reload
```

Or: `python -m mcp_server.runme` (if runme is wired).

Set `.env` for the Shiny app:

- `SUPPLYMIND_TOOLS_MODE=mcp`
- `SUPPLYMIND_MCP_URL=http://127.0.0.1:8765/mcp`

## Tools

- `list_hub_names`
- `get_in_transit_aggregate`
- `get_delivered_cohort_summary`
- `run_capacity_stress_pipeline`
'''

def main():
    d = ROOT / "mcp_server"
    d.mkdir(exist_ok=True)
    (d / "__init__.py").write_text("", encoding="utf-8")
    (d / "server.py").write_text(SERVER, encoding="utf-8")
    (d / "runme.py").write_text(RUNME, encoding="utf-8")
    (d / "README.md").write_text(README, encoding="utf-8")
    print("mcp_server ok")

if __name__ == "__main__":
    main()
~~~~
