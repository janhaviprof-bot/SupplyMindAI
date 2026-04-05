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

Set `.env` for the Shiny app (or Connect **Variables** on the Shiny content):

- `SUPPLYMIND_MCP_URL=http://127.0.0.1:8765/mcp` (local) or `https://<connect-host>/content/<id>/mcp` after you deploy the MCP API below.

## Deploy to Posit Connect (`deployme.py`)

From the **inner** `SupplyMindAI` directory (same as for local `uvicorn`):

```bash
pip install rsconnect-python python-dotenv
python mcp_server/deployme.py
```

Put credentials in `.env` in that directory (or export them in the shell):

- `CONNECT_SERVER` or `CONNECT_URL` — Posit Connect base URL
- `CONNECT_API_KEY` — API key from Connect
- Optional: `CONNECT_NAME` (default `supplymind-mcp`) — `rsconnect add` / deploy server nickname; `CONNECT_DEPLOY_TITLE` (default `supplymind-mcp`) — content title

The script bundles the whole inner `SupplyMindAI` folder (so `advisor/`, `analysis/`, `db/` resolve) and uses FastAPI entrypoint `mcp_server.server:app`.

After deploy, on the **API** content set Variables such as `OPENAI_API_KEY` and `POSTGRES_CONNECTION_STRING` (or `DIRECT_URL`) as needed. On the **Shiny** content set `SUPPLYMIND_MCP_URL` to the MCP endpoint, typically `https://<connect-host>/content/<api-content-id>/mcp` (confirm with a `POST` to `/mcp` if unsure).

## Tools

- `list_hub_names`
- `get_in_transit_aggregate`
- `get_delivered_cohort_summary`
- `run_capacity_stress_pipeline` — stress uses capacity k (C_sim = k × max_capacity; k=1.0 nominal, k<1 cut); optional recovery k sweep
- `run_optimization_simulation` — five-lever recommendations + ROI curves; hub capacity k=1.0 baseline, k=1.2 = +20% vs nominal (What-If `optimization_simulation` pipeline)
