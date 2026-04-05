# What-If advisor: planner + conditional tools

Canonical source bundle: [what_if_new.py.md](what_if_new.py.md) (use `~~~python` fences so inner `` ``` `` strings are safe).

Re-apply to `SupplyMindAI/advisor/what_if.py` from repo root:

```text
py -c "import re, pathlib; r=pathlib.Path('.'); md=r.joinpath('docs/what_if_new.py.md').read_text(encoding='utf-8'); m=re.search(r'~~~python\n(.*)\n~~~\\s*$', md, re.DOTALL); r.joinpath('SupplyMindAI/advisor/what_if.py').write_text(m.group(1).strip()+'\n', encoding='utf-8')"
```

## Behavior

1. **RAG** — `retrieve(user_question)` always runs first (lightweight).
2. **Planner agent** — One JSON LLM call chooses pipeline: `full_stress` | `operational_snapshot` | `delivered_analytics`.
3. **Heuristic override** — If the question matches stress/what-if/capacity/simulation keywords, force `full_stress`.
4. **Tools per pipeline**
   - **operational_snapshot:** `tool_get_in_transit_aggregate`, `tool_list_hub_names` only. No cohort, no stress/sweet spot. One Narration LLM.
   - **delivered_analytics:** in-transit + hubs + `tool_get_delivered_cohort`. No stress tools. DeliveredAnalytics JSON LLM + Narration LLM.
   - **full_stress:** Same as before: all tools + Prediction → stress → Risk → Simulation → Narration.

`agent_trace` starts with `Planner` entry: `pipeline=...; reason=...`.
