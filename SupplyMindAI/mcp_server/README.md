# SupplyMind MCP server

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
- `run_capacity_stress_pipeline` — stress uses capacity k (C_sim = k × max_capacity; k=1.0 nominal, k<1 cut); optional recovery k sweep
- `run_optimization_simulation` — five-lever recommendations + ROI curves; hub capacity k=1.0 baseline, k=1.2 = +20% vs nominal (What-If `optimization_simulation` pipeline)
