# Advisor stack (SYSEN / DS-AIforSystemsEng alignment)

This project mirrors themes from [06_agents](https://github.com/janhaviprof-bot/DS-AIforSystemsEng/tree/main/06_agents), [07_rag](https://github.com/janhaviprof-bot/DS-AIforSystemsEng/tree/main/07_rag), and [08_function_calling](https://github.com/janhaviprof-bot/DS-AIforSystemsEng/tree/main/08_function_calling) (including [mcp_fastapi](https://github.com/janhaviprof-bot/DS-AIforSystemsEng/tree/main/08_function_calling/mcp_fastapi)).

## Components

| Piece | Location | Notes |
|--------|-----------|--------|
| Multi-agent pipeline | `SupplyMindAI/advisor/what_if.py` | Planner → conditional pipelines → narration |
| RAG | `SupplyMindAI/advisor/rag.py` | `RAG_RETRIEVAL_MODE`: `keyword` \| `embed` \| `hybrid` |
| Tool definitions + local runner | `SupplyMindAI/advisor/tool_defs.py` | Shared schemas for OpenAI + MCP |
| Local vs MCP dispatch | `SupplyMindAI/advisor/tool_dispatch.py` | `SUPPLYMIND_TOOLS_MODE` |
| MCP HTTP server | `SupplyMindAI/mcp_server/server.py` | `POST /mcp` JSON-RPC, same pattern as course |
| DB/simulation tools | `SupplyMindAI/advisor/tools_impl.py` | Includes MCP-friendly summaries / stress pipeline |

## Environment variables

See [`.env.example`](../.env.example): `SUPPLYMIND_TOOLS_MODE`, `SUPPLYMIND_MCP_URL`, `ADVISOR_PLANNER_MODE`, `RAG_RETRIEVAL_MODE`.

## Run MCP server

From the **inner** `SupplyMindAI` directory (next to `app.py`):

```bash
uvicorn mcp_server.server:app --host 127.0.0.1 --port 8765 --reload
```

Then set `SUPPLYMIND_TOOLS_MODE=mcp` and `SUPPLYMIND_MCP_URL=http://127.0.0.1:8765/mcp` for the Shiny app.

## OpenAI function-calling planner

Set `ADVISOR_PLANNER_MODE=openai_tools`. The planner may call the same tools as MCP, then **must** call `submit_planner_decision` with `pipeline` and `reason`. If the loop ends without a decision, the JSON planner is used as fallback.
