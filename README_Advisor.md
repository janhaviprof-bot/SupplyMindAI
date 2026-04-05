# SupplyMind What-If Advisor — Documentation

## Table of contents

1. [Setup and run](#setup-and-run) — install, database, env, MCP URL, Shiny, CLI  
2. [Overview](#overview) — what the advisor does  
3. [System architecture](#system-architecture) — agents and workflow  
4. [RAG data source and search](#rag-data-source-and-search)  
5. [Tool functions](#tool-functions)  
6. [Technical details](#technical-details) — env reference, MCP endpoint, packages, file layout  
7. [Related documentation](#related-documentation)

---

## Setup and run

Follow these steps in order. The advisor **requires** a running Postgres database, `OPENAI_API_KEY`, and **`SUPPLYMIND_MCP_URL`** pointing at the **deployed** MCP HTTP endpoint (tools are called over JSON-RPC, not in-process).

### 1. Install dependencies

From the **repository root**:

```bash
pip install -r SupplyMindAI/requirements.txt
```

Use Python **3.12.x** if you are matching Posit Connect / `SupplyMindAI/manifest.json`.

### 2. Database

1. Create a Supabase (or other Postgres) project and copy a connection string from the dashboard.
2. Apply schema and seed data using `SupplyMindAI/supplymind_db/` (e.g. `schema.sql`, `seed.sql`, or `run_seeds.py` — see root `README.md` and `docs/GETTING_STARTED.md`).

### 3. Environment file

1. Copy `.env.example` to `.env` at the **repository root**.
2. Set at minimum:
   - **`POSTGRES_CONNECTION_STRING`** — your Postgres connection URI (e.g. from Supabase).
   - **`OPENAI_API_KEY`** — required for all advisor LLM calls.
   - **`SUPPLYMIND_MCP_URL`** — deployed MCP JSON-RPC endpoint (must end with `/mcp`): [https://connect.systems-apps.com/content/3eb48dc8-0322-4edd-bfd9-9edf10003a4e/mcp](https://connect.systems-apps.com/content/3eb48dc8-0322-4edd-bfd9-9edf10003a4e/mcp) (see `.env.example`). Interactive API docs (Swagger): [https://connect.systems-apps.com/content/3eb48dc8-0322-4edd-bfd9-9edf10003a4e/docs](https://connect.systems-apps.com/content/3eb48dc8-0322-4edd-bfd9-9edf10003a4e/docs).

### 4. Run the Shiny app

From the **repository root**:

```bash
shiny run SupplyMindAI/app.py --launch-browser
```

Windows:

```powershell
py -m shiny run SupplyMindAI/app.py --launch-browser
```

Use the What-If / advisor section in the UI to ask questions.

### 5. CLI (optional)

With **`SUPPLYMIND_MCP_URL`** set to the deployed endpoint, run from the **repository root**.

- **Interactive mode** — use **`-i`** when you want to type many questions in one session (prompts with `user:` until you send an empty line, `quit`, or `exit`).
- **Single question** — omit **`-i`**: pass the question as the last arguments, or use **`-q "…"`** if you prefer a flag. Default output is a short three-part layout (agents, RAG + answer, tools).
- **Verbose / debug** — add **`--full`** when you need the full RAG dump, large tool payloads, JSON `agent_trace`, and `metrics_lines` (e.g. troubleshooting). Combine **`-i --full`** for interactive + verbose every time.
- **Cohort window** — add **`--date-range`** (`yesterday`, `week`, `month`, `year`) when delivered-cohort or optimization tools should use a specific window (default is `week`).
- **Answer text only** — use **`--markdown-only`** when you want just the final markdown (no RAG, tools, or trace), e.g. for piping.

```bash
py scripts/what_if_cli.py "What if we cut capacity at our busiest hub by 20%?"
py scripts/what_if_cli.py -q "Give me an operational snapshot" --date-range week
py scripts/what_if_cli.py -i
py scripts/what_if_cli.py -i --full
py scripts/what_if_cli.py --full "What if we cut capacity at our busiest hub by 20%?"
py scripts/what_if_cli.py --markdown-only "Summarize in-transit risk."
```

### 6. Optional tuning

- **`ADVISOR_PLANNER_MODE=openai_tools`** — planner uses tool calls plus `submit_planner_decision` (see `.env.example`).
- **`RAG_RETRIEVAL_MODE=embed`** or **`hybrid`** — semantic RAG (extra embedding API usage).

---

## Overview

The **What-If Advisor** is a multi-step agent pipeline that answers natural-language questions about your supply chain using **RAG** (retrieval-augmented context), **OpenAI** completions, and **tools** that read Postgres and run simulations. The same tool definitions are served over HTTP as a small **MCP-style** FastAPI app for the Shiny UI and CLI.

**Main code path:** `SupplyMindAI/advisor/what_if.py` — entry point `run_what_if_advisor(question, date_range=..., start_date=..., end_date=...)`.

---

## System architecture

### End-to-end flow

1. **RAG** — `retrieve(user_question)` runs first and returns a short list of text chunks (live SQL summaries + documentation excerpts). These chunks are injected into planner and narration prompts.
2. **Planner** — Chooses exactly one **pipeline** for the rest of the run:
   - `full_stress` — Capacity what-if: interpret scenario → stress simulation → risk interpretation → simulation KPIs → final markdown answer.
   - `operational_snapshot` — Current in-transit picture and hub list only (no delivered cohort, no stress).
   - `delivered_analytics` — Historical delivered cohort metrics and an analytics JSON pass (no stress).
   - `optimization_simulation` — Five-lever optimization recommendations plus ROI / sweet-spot curves.

3. **Heuristic overrides** — After the planner returns, keyword heuristics can force:
   - `full_stress` when the question looks like capacity / what-if / simulation / sweet-spot language.
   - `optimization_simulation` when it looks like ROI / minimum investment / which lever (and not a stress question).

4. **Tool execution** — Pipelines call tools through `ToolDispatch`, which performs **HTTP JSON-RPC** `POST` to **`SUPPLYMIND_MCP_URL`** (deployed MCP endpoint; path `/mcp`). The MCP service runs the tool implementations (`run_supply_tool_local` in the deployed app).

5. **Downstream LLM agents** — Depending on the pipeline, the code runs additional **JSON** agents (structured output) and/or a **Narration** agent (markdown with a fixed section shape and a **Confidence: X/10** line).

### Agent roles (conceptual)

| Role | When it runs | Role |
|------|----------------|------|
| **Planner** | Always | Selects pipeline; in `ADVISOR_PLANNER_MODE=openai_tools`, may call probe tools then `submit_planner_decision`. |
| **PlannerTool** | `openai_tools` mode only | Traces each tool call the planner makes (in-transit, hubs, cohort summary, decision). |
| **Prediction** | `full_stress` | Parses user intent into target hub and capacity multiplier `k`. |
| **Risk** | `full_stress` | Summarizes severity, focus hubs, mitigations from prediction + stress outputs. |
| **Simulation** | `full_stress` | Interprets stress and sweet-spot numbers into KPI narrative JSON. |
| **DeliveredAnalytics** | `delivered_analytics` | Headline and performance summary from cohort metrics. |
| **OptimizationSimulation** | `optimization_simulation` | Trace summary from optimization bundle. |
| **Narration** | All pipelines | Final user-facing markdown grounded in injected numbers. |

Chat model for these steps: **`gpt-4o-mini`** (OpenAI API).

---

## RAG data source and search

**Module:** `SupplyMindAI/advisor/rag.py`  
**Function:** `retrieve(query: str, k: int = 6) -> list[str]`

### What gets retrieved

1. **SQL-backed snippets** (`sql_summary_snippets`) — Built at query time via `execute_query` against your live database:
   - Insight flag counts (`insights` grouped by `flag_status`).
   - Top hub–risk pairs (`risks`).
   - Hub status snapshot (`hubs`: load vs capacity, status), capped for size.

2. **Documentation chunks** (`load_doc_chunks`) — Markdown under:
   - Repository `docs/*.md`
   - `SupplyMindAI/docs/*.md`  
   Files are split on heading boundaries (`#` / `##` / `###`); chunks are capped (long chunks truncated; list capped).

### Search modes (`RAG_RETRIEVAL_MODE`)

| Mode | Behavior |
|------|-----------|
| `keyword` (default) | Token overlap scoring between query and each chunk; SQL snippets get a small score boost. |
| `embed` | OpenAI **`text-embedding-3-small`** embeddings for query and chunks; cosine similarity ranking. Falls back to keyword if `OPENAI_API_KEY` is missing or embedding fails. |
| `hybrid` | Combines embed and keyword results (deduplicated). |

---

## Tool functions

Tools are registered for MCP as JSON-schema **snake_case** names. The Shiny app and planner call these names over HTTP.

| Tool name | Purpose | Parameters | Returns (summary) |
|------------|---------|------------|---------------------|
| `list_hub_names` | List all hub names for grounding and hub picking. | _(none)_ | `list[str]` — sorted hub names from `hubs`. |
| `get_in_transit_aggregate` | Snapshot of in-transit shipments, future risk exposure, insight flags. | _(none)_ | `dict` — e.g. `in_transit_count`, `future_risk_mix`, `hubs_with_future_exposure`, `critical_flagged_count`, `delayed_flagged_count`, sample rows. |
| `get_delivered_cohort_summary` | Aggregated delivered cohort for a time window (no raw shipment rows in the default tool path). | `date_range`: `yesterday` \| `week` \| `month` \| `year` | `dict` — `ok`, window strings, counts, `metrics` (on-time vs delayed stats, top hubs, etc.), `empty` flag. |
| `run_capacity_stress_pipeline` | Stress a hub’s capacity on historical delivered cohort; optional sweet-spot grid over capacity multiplier `k`. | `date_range` (string), `target_hub` (string), `capacity_multiplier` (number, stress `k` in ~0.5–1.0), `run_sweet_spot` (boolean, default true) | `dict` — `ok`, `stress` (baseline vs stressed counts/metrics), optional `sweet_spot`, `touching`, error fields on failure. |
| `run_optimization_simulation` | AI-driven recommendations on five simulatable levers, then ROI sweet-spot curves. | `date_range`, optional `max_levers` (1–5, default 4) | `dict` — `ok`, `summary` / `summary_text_plain`, `control_parameters`, `top_parameters`, `curves_brief`, counts, simulation notes, etc. |

**Planner-only (OpenAI function calling, not in MCP `tools/list`):**

| Name | Purpose | Parameters | Returns |
|------|---------|------------|---------|
| `submit_planner_decision` | Ends the planner tool loop with a chosen pipeline. | `pipeline`, `reason` | `dict` echoing `pipeline` and `reason` for the orchestrator. |

**Internal helper (not MCP-exposed):** `tool_get_delivered_cohort` in `tools_impl.py` loads full cohort structures for the `delivered_analytics` pipeline inside the advisor process.

Schemas and local execution: `SupplyMindAI/advisor/tool_defs.py`. Implementations: `SupplyMindAI/advisor/tools_impl.py`.

---

## Technical details

### API keys and environment

| Variable | Role |
|----------|------|
| `OPENAI_API_KEY` | Required for advisor LLM calls; required for `RAG_RETRIEVAL_MODE=embed` / `hybrid` embedding path. |
| `POSTGRES_CONNECTION_STRING` | Postgres connection URI for the app and advisor tools. |
| `SUPPLYMIND_MCP_URL` | **Required** for the advisor: full URL of the deployed MCP endpoint, normalized to end with `/mcp`. Example: `https://connect.systems-apps.com/content/3eb48dc8-0322-4edd-bfd9-9edf10003a4e/mcp`. Swagger UI for the same deployment: [https://connect.systems-apps.com/content/3eb48dc8-0322-4edd-bfd9-9edf10003a4e/docs](https://connect.systems-apps.com/content/3eb48dc8-0322-4edd-bfd9-9edf10003a4e/docs). |
| `ADVISOR_PLANNER_MODE` | `json` (default): one JSON completion for pipeline choice. `openai_tools`: tool-calling loop with probes + `submit_planner_decision`. |
| `ADVISOR_PLANNER_PROBE_TOOLS` | If `full`, planner sees all tools (not recommended); default is lightweight probes only. |
| `RAG_RETRIEVAL_MODE` | `keyword` \| `embed` \| `hybrid`. |
| `MAX_SHIPMENTS` | Optional cap on in-transit rows for demos (used by analysis pipeline). |

`.env` is loaded from the repository root (and paths above in `supabase_client`). Copy `.env.example` to `.env` and fill in values.

### HTTP endpoint (MCP-style)

- **URL:** `POST` to the deployed MCP path `/mcp`, e.g. `https://connect.systems-apps.com/content/3eb48dc8-0322-4edd-bfd9-9edf10003a4e/mcp`. OpenAPI/Swagger for the service: [https://connect.systems-apps.com/content/3eb48dc8-0322-4edd-bfd9-9edf10003a4e/docs](https://connect.systems-apps.com/content/3eb48dc8-0322-4edd-bfd9-9edf10003a4e/docs).
- **Protocol:** JSON-RPC 2.0 — methods include `initialize`, `ping`, `tools/list`, `tools/call`.
- **Implementation (in repo):** `SupplyMindAI/mcp_server/server.py` (this is what is deployed to Posit Connect).

### Main Python packages (advisor-related)

From `SupplyMindAI/requirements.txt`: `shiny`, `openai`, `psycopg2-binary`, `fastapi`, `uvicorn`, `httpx`, `python-dotenv`, plus UI/plotting deps for the full app.

### File structure (advisor slice)

| Path | Purpose |
|------|---------|
| `SupplyMindAI/advisor/what_if.py` | Orchestration, pipelines, agent prompts. |
| `SupplyMindAI/advisor/rag.py` | RAG retrieval. |
| `SupplyMindAI/advisor/tool_defs.py` | MCP + OpenAI tool schemas; `run_supply_tool_local`. |
| `SupplyMindAI/advisor/tool_dispatch.py` | HTTP client to MCP. |
| `SupplyMindAI/advisor/tools_impl.py` | Tool implementations (DB + analysis). |
| `SupplyMindAI/mcp_server/server.py` | FastAPI MCP HTTP server. |
| `SupplyMindAI/analysis/` | Pipelines, optimization, simulation helpers used by tools. |
| `SupplyMindAI/supplymind_db/` | Postgres client, schema, seeds, CSVs. |
| `scripts/what_if_cli.py` | CLI to run the advisor from the repo root. |
| `SupplyMindAI/app.py` | Shiny UI; calls `run_what_if_advisor` for the What-If section. |

---

## Related documentation

- Course-aligned stack overview: `docs/COURSE_ADVISOR_STACK.md`
- Planner + pipeline behavior notes: `docs/what_if_planner_pipelines.md`
- Project-wide index: `docs/DOCUMENTATION_INDEX.md` and root `README.md`
