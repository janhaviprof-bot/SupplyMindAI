"""
What-If Advisor: planner chooses pipeline, then RAG + conditional tools + LLM agents.
Pipelines: full_stress (simulation), operational_snapshot (in-transit + hubs only),
delivered_analytics (historical cohort metrics, no stress tools).
"""
from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any, Optional

from advisor.rag import retrieve
from advisor.tool_dispatch import get_dispatch
from advisor.tools_impl import tool_get_delivered_cohort
from analysis.simulation import HUB_CAPACITY_K_EXPLAINER_STRESS


def _load_env():
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _get_openai_client():
    _load_env()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Set OPENAI_API_KEY in .env")
    from openai import OpenAI

    return OpenAI(api_key=api_key)


def _strip_json_fence(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return text.strip()


def _call_json_agent(client, system: str, user: str, temperature: float = 0.2) -> dict:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
    )
    text = response.choices[0].message.content or "{}"
    text = _strip_json_fence(text)
    return json.loads(text)


def _call_text_agent(client, system: str, user: str, temperature: float = 0.35) -> str:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
    )
    return (response.choices[0].message.content or "").strip()


_NARRATION_MARKDOWN_SHAPE = """Output markdown in this exact shape:
1) Direct answer (NO ## heading): at least 3–4 lines of prose that speak straight to the user's question—clear, managerial tone. Each line can be a sentence or a short line; the opening must feel like a substantive direct answer, not a one-liner.
2) Blank line, then ## Details — explain the reasoning and evidence behind that answer (numbers, hubs, risks, simulation, cohort, trade-offs). Use bullets or paragraphs. Use only facts from the user message; do not invent counts.
3) Do NOT use markdown tables unless they are strictly required to make the data understandable; prefer prose and bullet lists.
4) Blank line, then exactly one final line: **Confidence:** X/10 — brief reason (plain language). Nothing after this line."""


def _confidence_from_json(d: dict, key: str = "confidence", default: int = 5) -> int:
    try:
        v = int(d.get(key))
        return max(1, min(10, v))
    except (TypeError, ValueError):
        return default


def _aggregate_narration_confidence(*scores: int) -> int:
    vals = [s for s in scores if isinstance(s, int) and 1 <= s <= 10]
    if not vals:
        return 5
    return max(1, min(10, round(sum(vals) / len(vals))))


def _force_full_stress_heuristic(question: str) -> bool:
    q = (question or "").lower()
    return bool(
        re.search(
            r"what[\s-]?if|stress|capacity|multiplier|simulate|simulation|"
            r"overload|bottleneck|sweet[\s-]?spot|recovery[\s-]?sweep|"
            r"reduc(e|ing).{0,12}capacity|cut.{0,12}capacity|"
            r"if.{0,20}(hub|capacity).{0,20}(drop|fall|less|reduce)",
            q,
            re.DOTALL,
        )
    )


def _force_optimization_heuristic(question: str) -> bool:
    """Route to optimization+simulation when user asks for ROI / minimum spend / levers (not capacity stress)."""
    if _force_full_stress_heuristic(question):
        return False
    q = (question or "").lower()
    return bool(
        re.search(
            r"minimum investment|min investment|lowest cost|least cost|cost-effective|cost effective|"
            r"\broi\b|return on investment|optimi[sz]e|optimi[sz]ation|efficien.*invest|invest.*efficien|"
            r"where (should|to) i invest|which lever|best lever|bang for|marginal return|"
            r"minimum spend|smallest budget|cheap(est)? way to improve",
            q,
            re.DOTALL,
        )
    )


def _plan_pipeline(client, user_question: str, rag_chunks: list[str]) -> tuple[str, str]:
    """Returns (pipeline_id, reason). Includes optimization_simulation for lever/ROI paths."""
    sys_pl = """You are the orchestration planner for a logistics advisor. Pick exactly ONE pipeline:

- "full_stress" — User wants a what-if or simulation: capacity change at a hub, stress test, multiplier, impact on delays, recovery/sweet spot, "what happens if…" scenarios.
- "operational_snapshot" — User wants current operational picture only: in-transit counts, today's risks, exposure, general "how are we doing now", hub list context, without historical delivered cohort analysis or simulation.
- "delivered_analytics" — User wants historical / baseline performance: on-time vs delayed for the selected period, past trends, cohort summaries, KPIs from completed deliveries — but NOT a capacity stress simulation.
- "optimization_simulation" — User wants cost-efficient improvements, minimum investment, ROI, which lever to fund, or tradeoffs between spend and on-time performance using the five simulatable levers (NOT a single-hub capacity stress what-if).

Output ONLY valid JSON:
{"pipeline":"full_stress"|"operational_snapshot"|"delivered_analytics"|"optimization_simulation","reason":"one short sentence"}"""

    user_pl = f"""User question: {user_question}

Retrieved context (RAG excerpts):
{chr(10).join(rag_chunks[:5])}
"""
    try:
        plan = _call_json_agent(client, sys_pl, user_pl, temperature=0.1)
    except Exception:
        return "full_stress", "planner_parse_failed_default_full_stress"

    p = (plan.get("pipeline") or "").strip().lower().replace("-", "_")
    reason = str(plan.get("reason") or "")[:300]
    if p in ("operational_snapshot", "snapshot", "operational"):
        return "operational_snapshot", reason
    if p in ("delivered_analytics", "delivered", "analytics", "historical"):
        return "delivered_analytics", reason
    if p in (
        "optimization_simulation",
        "optimization",
        "lever_optimization",
        "roi_simulation",
    ):
        return "optimization_simulation", reason
    return "full_stress", reason or "default"


def _planner_mode() -> str:
    return (os.environ.get("ADVISOR_PLANNER_MODE") or "json").strip().lower()


def _planner_openai_tools() -> list[dict[str, Any]]:
    """Light probe tools by default; set ADVISOR_PLANNER_PROBE_TOOLS=full to expose all tools to the planner."""
    if (os.environ.get("ADVISOR_PLANNER_PROBE_TOOLS") or "").strip().lower() == "full":
        from advisor.tool_defs import OPENAI_TOOL_FUNCTIONS

        return OPENAI_TOOL_FUNCTIONS
    from advisor.tool_defs import OPENAI_PLANNER_TOOL_FUNCTIONS

    return OPENAI_PLANNER_TOOL_FUNCTIONS


def _plan_pipeline_openai_tools(
    client,
    user_question: str,
    rag_chunks: list[str],
    date_range: str,
    trace: list[dict[str, str]],
    dispatch,
) -> tuple[str, str]:
    sys_m = """You are the orchestration planner. You may call ONLY lightweight tools to inspect data:
list_hub_names, get_in_transit_aggregate, get_delivered_cohort_summary (use date_range from the user message).
Do NOT attempt capacity stress or optimization simulations here—those run automatically AFTER you pick a pipeline.

You MUST finish by calling submit_planner_decision exactly once with:
- pipeline: full_stress | operational_snapshot | delivered_analytics | optimization_simulation
- reason: short sentence

full_stress = what-if / capacity / simulation. operational_snapshot = current in-transit picture only.
delivered_analytics = historical on-time/delayed for the baseline period, no simulation.
optimization_simulation = ROI / minimum investment / which lever."""
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": sys_m},
        {
            "role": "user",
            "content": (
                f"User question: {user_question}\n\n"
                f"RAG excerpts:\n{chr(10).join(rag_chunks[:5])}\n\n"
                f"Use date_range={date_range!r} when calling get_delivered_cohort_summary."
            ),
        },
    ]
    tools = _planner_openai_tools()
    for _ in range(8):
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.1,
        )
        msg = resp.choices[0].message
        tcalls = getattr(msg, "tool_calls", None) or []
        if not tcalls:
            break
        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments or "{}",
                        },
                    }
                    for tc in tcalls
                ],
            }
        )
        for tc in tcalls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            try:
                out = dispatch.call(name, args)
            except Exception as e:
                out = {"error": str(e)}
            trace.append({"agent": "PlannerTool", "summary": f"{name}: {str(out)[:450]}"})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(out, default=str)[:24000],
                }
            )
            if name == "submit_planner_decision" and isinstance(out, dict):
                p = (out.get("pipeline") or "").strip().lower().replace("-", "_")
                r = str(out.get("reason") or "")
                if p in (
                    "full_stress",
                    "operational_snapshot",
                    "delivered_analytics",
                    "optimization_simulation",
                ):
                    return p, r
    return _plan_pipeline(client, user_question, rag_chunks)



def _pick_hub(raw: Optional[str], known: list[str], fallback_hubs: list[str]) -> Optional[str]:
    if not known:
        return None
    if raw:
        rl = str(raw).strip().lower()
        for h in known:
            if h.lower() == rl:
                return h
        for h in known:
            if rl in h.lower() or h.lower() in rl:
                return h
    for h in fallback_hubs:
        for k in known:
            if k.lower() == h.lower():
                return k
    return known[0]


def _metrics_lines(
    stress: dict,
    sweet: Optional[dict],
    in_transit: dict,
    start_str: str,
    end_str: str,
    hub: str,
    mult: float,
    touching: int,
    cohort_empty: bool,
) -> list[str]:
    lines = [
        f"Cohort window: {start_str} – {end_str} (empty={cohort_empty})",
        f"Hub stressed: {hub} · capacity k={mult} ({round((mult - 1) * 100)}% vs nominal; k=1.0 = no change)",
        f"Baseline delivered: {stress['baseline_on_time']} on-time, {stress['baseline_delayed']} delayed",
        f"After stress: {stress['stressed_on_time']} on-time, {stress['stressed_delayed']} delayed (Δ delayed: {stress['stressed_delayed'] - stress['baseline_delayed']})",
        f"In transit: {in_transit.get('in_transit_count')} · critical/delayed (insights): {in_transit.get('critical_flagged_count')}/{in_transit.get('delayed_flagged_count')}",
        f"Delayed delivered journeys through hub: {touching}",
    ]
    if sweet:
        bm = sweet.get("best_metrics") or {}
        lines.append(
            f"Recovery sweep sweet-spot k={sweet.get('sweet_spot_value')} · recovered {bm.get('recovered_count', '—')}"
        )
    return lines


def _run_operational_snapshot(
    client,
    user_question: str,
    rag_chunks: list[str],
    trace: list[dict[str, str]],
    result: dict[str, Any],
) -> dict[str, Any]:
    d = get_dispatch()
    in_transit = d.call("get_in_transit_aggregate")
    known_hubs = d.call("list_hub_names")
    sys_n = f"""You are the Narration agent for supply chain managers. Answer using ONLY the JSON and RAG excerpts in the user message.
{_NARRATION_MARKDOWN_SHAPE}
Do not invent shipment counts—use only numbers from the user message.
For **Confidence:**, choose X from 1–10 from data completeness (e.g. sparse in-transit, missing context).
Keep total output under 550 words."""

    user_n = f"""User question: {user_question}

Retrieved context (RAG):
{chr(10).join(rag_chunks[:5])}

In-transit aggregate (JSON):
{json.dumps(in_transit, indent=2, default=str)}

Known hub names (first 40): {json.dumps(known_hubs[:40])}
"""
    try:
        narrative = _call_text_agent(client, sys_n, user_n, temperature=0.35)
    except Exception as e:
        narrative = f"## Error\nFailed to generate narration: {e}"

    result["metrics_lines"] = [
        "Pipeline: operational_snapshot (no delivered cohort / no stress simulation)",
        f"In transit: {in_transit.get('in_transit_count')} · critical/delayed (insights): {in_transit.get('critical_flagged_count')}/{in_transit.get('delayed_flagged_count')}",
        f"Hubs listed: {len(known_hubs)}",
    ]
    trace.append({"agent": "Narration", "summary": narrative[:400]})
    result["narrative_markdown"] = narrative
    return result


def _run_delivered_analytics(
    client,
    user_question: str,
    rag_chunks: list[str],
    date_range: str,
    start_date: Optional[date],
    end_date: Optional[date],
    trace: list[dict[str, str]],
    result: dict[str, Any],
) -> dict[str, Any]:
    d = get_dispatch()
    in_transit = d.call("get_in_transit_aggregate")
    known_hubs = d.call("list_hub_names")
    cohort = tool_get_delivered_cohort(date_range, start_date, end_date)
    if not cohort.get("ok"):
        result["error"] = cohort.get("error", "Failed to load delivered cohort.")
        return result

    on_time_raw = cohort.get("on_time_raw") or []
    delayed_raw = cohort.get("delayed_raw") or []
    metrics = cohort.get("metrics") or {}
    start_str = cohort.get("start_str", "")
    end_str = cohort.get("end_str", "")

    sys_a = """You are the Delivered-data analytics agent. Output ONLY valid JSON:
{
  "headline": "one sentence",
  "performance_summary": "2-4 sentences on on-time vs delayed using only provided counts",
  "hubs_to_watch": ["name or theme", "..."],
  "confidence": 1-10
}
Do not invent counts; use only numbers from the user message."""

    user_a = f"""User question: {user_question}

Retrieved context (RAG):
{chr(10).join(rag_chunks[:5])}

In-transit snapshot (no simulation): {json.dumps({k: in_transit.get(k) for k in ['in_transit_count', 'critical_flagged_count', 'delayed_flagged_count', 'hubs_with_future_exposure']}, default=str)}

Delivered cohort window: {start_str} – {end_str}
empty_cohort={cohort.get('empty')}
on_time_shipments={len(on_time_raw)}, delayed_shipments={len(delayed_raw)}
metrics: {json.dumps(metrics, default=str)}
Hub sample: {json.dumps(known_hubs[:20])}
"""
    try:
        analytics = _call_json_agent(client, sys_a, user_a, temperature=0.2)
    except Exception as e:
        analytics = {
            "headline": "Delivered cohort loaded.",
            "performance_summary": str(e),
            "hubs_to_watch": [],
            "confidence": 5,
        }

    trace.append({"agent": "DeliveredAnalytics", "summary": json.dumps(analytics)[:500]})

    ac = _confidence_from_json(analytics)
    sys_n = f"""You are the Narration agent for supply chain managers.
{_NARRATION_MARKDOWN_SHAPE}
Use ONLY the numbers in the user message. No capacity simulation was run.
The final **Confidence:** line MUST use exactly {ac}/10 (match Analytics JSON "confidence") plus a short reason after the em dash.
Keep total output under 550 words."""

    user_n = f"""User question: {user_question}

Analytics JSON:
{json.dumps(analytics, indent=2)}

Hard numbers:
- Date range: {start_str} to {end_str}
- Delivered: {len(on_time_raw)} on-time, {len(delayed_raw)} delayed (empty cohort: {cohort.get('empty')})
- In-transit count: {in_transit.get('in_transit_count')}
"""
    try:
        narrative = _call_text_agent(client, sys_n, user_n, temperature=0.35)
    except Exception as e:
        narrative = f"## Error\nFailed to generate narration: {e}"

    trace.append({"agent": "Narration", "summary": narrative[:400]})
    result["narrative_markdown"] = narrative
    result["metrics_lines"] = [
        "Pipeline: delivered_analytics (no stress simulation)",
        f"Cohort window: {start_str} – {end_str} (empty={bool(cohort.get('empty'))})",
        f"On-time / delayed shipments: {len(on_time_raw)} / {len(delayed_raw)}",
        f"In transit: {in_transit.get('in_transit_count')} · critical/delayed (insights): {in_transit.get('critical_flagged_count')}/{in_transit.get('delayed_flagged_count')}",
    ]
    return result


def _narration_confidence_from_opt_bundle(bundle: dict[str, Any]) -> int:
    base = 6
    if not bundle.get("ok"):
        return max(3, base - 2)
    n = int(bundle.get("on_time_count") or 0) + int(bundle.get("delayed_count") or 0)
    if n < 5:
        base -= 2
    elif n > 40:
        base += 1
    curves = bundle.get("curves_brief") or []
    if curves:
        base = min(9, base + min(2, len(curves)))
    return max(1, min(10, base))


def _run_optimization_simulation(
    client,
    user_question: str,
    rag_chunks: list[str],
    date_range: str,
    start_date: Optional[date],
    end_date: Optional[date],
    trace: list[dict[str, str]],
    result: dict[str, Any],
) -> dict[str, Any]:
    d = get_dispatch()
    try:
        bundle = d.call(
            "run_optimization_simulation",
            {"date_range": date_range, "max_levers": 4},
        )
    except Exception as e:
        bundle = {"ok": False, "error": str(e)}
    if not isinstance(bundle, dict):
        bundle = {"ok": False, "error": str(bundle)}

    trace.append(
        {
            "agent": "OptimizationSimulation",
            "summary": str(bundle.get("curves_brief") or bundle.get("error") or "")[:500],
        }
    )

    lines = ["Pipeline: optimization_simulation (five levers + ROI sweet-spot curves)"]
    stp = bundle.get("summary_text_plain") or ""
    if stp:
        lines.append(stp[:220])
    for c in (bundle.get("curves_brief") or [])[:6]:
        inv = float(c.get("sweet_spot_investment_usd") or 0)
        hub = c.get("target_hub")
        hub_bit = f' · hub={hub}' if hub else ""
        lines.append(
            f"{(c.get('label') or '')[:50]}{hub_bit} · ~${inv:,.0f} · +{c.get('recovered_on_time_shipments', 0)} on-time"
        )
    result["metrics_lines"] = lines

    payload = {
        "ok": bundle.get("ok"),
        "error": bundle.get("error"),
        "date_range": bundle.get("date_range"),
        "summary": bundle.get("summary"),
        "summary_text_plain": bundle.get("summary_text_plain"),
        "control_parameters": bundle.get("control_parameters"),
        "top_parameters": bundle.get("top_parameters"),
        "on_time_count": bundle.get("on_time_count"),
        "delayed_count": bundle.get("delayed_count"),
        "curves_brief": bundle.get("curves_brief"),
        "sim_insights": bundle.get("sim_insights"),
        "simulation_note": bundle.get("simulation_note"),
        "capacity_multiplier_k_meaning": bundle.get("capacity_multiplier_k_meaning"),
    }

    oc = _narration_confidence_from_opt_bundle(bundle)
    sys_n = f"""You are the Narration agent for supply chain managers.
{_NARRATION_MARKDOWN_SHAPE}
This answer uses optimization recommendations plus simulated investment vs on-time recovery (sweet spots).
Tie advice to dollars and recovered on-time counts only when the JSON provides them.
Use ONLY facts from the user message. Prefer bullets in ## Details over tables unless a small table is strictly clearer.

CRITICAL (hub capacity / investment):
- Follow JSON field capacity_multiplier_k_meaning for hub_capacity k (C_sim = k × max_capacity) and modeled $ vs grid value_min.
- When curves_brief[].target_hub is set, name that hub explicitly for capacity levers (e.g. "Atlanta-South").
- If investment_interpretation_note is present, reflect it in ## Details: k=1.0 yields $0 incremental in the model only—not free real-world expansion. Cite modeled_investment_max_usd at the grid max k (e.g. k=2.0 = 100% above nominal in the simulation).
- Never claim that increasing physical hub capacity costs $0 in the real world.

The final **Confidence:** line MUST use exactly {oc}/10 plus a short reason (cohort size, how many levers were simulated, missing data).
Keep total output under 600 words."""

    user_n = f"""User question: {user_question}

Retrieved context (RAG):
{chr(10).join(rag_chunks[:5])}

Optimization + simulation bundle (JSON):
{json.dumps(payload, indent=2, default=str)[:22000]}
"""
    try:
        narrative = _call_text_agent(client, sys_n, user_n, temperature=0.35)
    except Exception as e:
        narrative = f"## Error\nFailed to generate narration: {e}"

    trace.append({"agent": "Narration", "summary": narrative[:400]})
    result["narrative_markdown"] = narrative
    return result


def _run_full_stress(
    client,
    user_question: str,
    rag_chunks: list[str],
    date_range: str,
    start_date: Optional[date],
    end_date: Optional[date],
    trace: list[dict[str, str]],
    result: dict[str, Any],
) -> dict[str, Any]:
    d = get_dispatch()
    in_transit = d.call("get_in_transit_aggregate")
    known_hubs = d.call("list_hub_names")
    cohort_sum = d.call("get_delivered_cohort_summary", {"date_range": date_range})
    if not cohort_sum.get("ok"):
        result["error"] = cohort_sum.get("error", "Failed to load delivered cohort summary.")
        return result

    metrics = cohort_sum.get("metrics") or {}
    start_str = cohort_sum.get("start_str", "")
    end_str = cohort_sum.get("end_str", "")
    on_time_n = int(cohort_sum.get("on_time_count") or 0)
    delayed_n = int(cohort_sum.get("delayed_count") or 0)
    cohort_empty = bool(cohort_sum.get("empty"))

    sys1 = """You are the Prediction agent for a logistics what-if advisor.
Output ONLY valid JSON:
{
  "interpreted_scenario": "short plain English",
  "target_hub": "exact hub name from context lists or null",
  "capacity_multiplier": number,
  "confidence": 1-10,
  "notes": "optional"
}
capacity_multiplier is k where simulated capacity = k × nominal max_capacity: k=1.0 no change vs nominal; k=0.8 = 20% below nominal (stress). Use k between 0.65 and 1.0 for stress scenarios."""

    user1 = f"""User question: {user_question}

Retrieved context (RAG):
{chr(10).join(rag_chunks[:5])}

In-transit aggregate (JSON):
{json.dumps(in_transit, indent=2, default=str)}

Known hub names:
{json.dumps(known_hubs[:40])}

Delivered cohort: empty={cohort_empty}, on_time={on_time_n}, delayed={delayed_n}, range {start_str}–{end_str}.
Delay metrics: {json.dumps(metrics, default=str)}

Hub capacity semantics:
{HUB_CAPACITY_K_EXPLAINER_STRESS}
"""

    try:
        pred = _call_json_agent(client, sys1, user1, temperature=0.15)
    except Exception as e:
        result["error"] = f"Prediction agent failed: {e}"
        return result

    trace.append({"agent": "Prediction", "summary": pred.get("interpreted_scenario", "")[:500]})

    fallback_hubs = [h for h, _ in (in_transit.get("hubs_with_future_exposure") or [])]
    if not fallback_hubs:
        fallback_hubs = list(metrics.get("top_delayed_hubs") or [])

    hub = _pick_hub(pred.get("target_hub"), known_hubs, fallback_hubs)
    if not hub and known_hubs:
        hub = known_hubs[0]
    try:
        mult = float(pred.get("capacity_multiplier") or 0.8)
    except (TypeError, ValueError):
        mult = 0.8
    mult = max(0.5, min(1.0, mult))

    pipe = d.call(
        "run_capacity_stress_pipeline",
        {
            "date_range": date_range,
            "target_hub": hub or "",
            "capacity_multiplier": mult,
            "run_sweet_spot": True,
        },
    )
    if not pipe.get("ok"):
        result["error"] = str(pipe.get("error", "stress_pipeline_failed"))
        return result
    stress = pipe["stress"]
    touching = int(pipe.get("touching") or 0)
    sweet = pipe.get("sweet_spot")
    cohort_empty = bool(pipe.get("empty"))

    result["metrics_lines"] = _metrics_lines(
        stress,
        sweet,
        in_transit,
        start_str,
        end_str,
        hub or "—",
        mult,
        touching,
        cohort_empty,
    )

    sys2 = """You are the Risk agent. Output ONLY JSON:
{
  "severity_overall": "low"|"medium"|"high",
  "critical_focus": ["hub or theme", "..."],
  "mitigations": ["action 1", "action 2", "action 3"],
  "confidence": 1-10
}"""

    user2 = f"""Prediction JSON:
{json.dumps(pred, indent=2)}
Resolved hub: {hub}, capacity k: {mult}
In-transit: {json.dumps({k: in_transit.get(k) for k in ['in_transit_count', 'future_risk_mix', 'critical_flagged_count', 'delayed_flagged_count']}, default=str)}
Delayed journeys through hub: {touching}
Stress sim: {json.dumps(stress, indent=2, default=str)}
"""

    try:
        risk = _call_json_agent(client, sys2, user2, temperature=0.2)
    except Exception as e:
        risk = {"severity_overall": "medium", "critical_focus": [], "mitigations": [], "confidence": 5, "_error": str(e)}

    trace.append({"agent": "Risk", "summary": json.dumps(risk)[:500]})

    sys3 = """You are the Simulation agent. Interpret only the numeric results provided. Output ONLY JSON:
{
  "headline": "one sentence",
  "kpi_interpretation": "2-3 sentences",
  "next_levers_to_try": ["short string", "..."],
  "confidence": 1-10
}"""

    user3 = f"""Hub {hub}, capacity k={mult}.
Semantics: {HUB_CAPACITY_K_EXPLAINER_STRESS}
Baseline: on_time={stress['baseline_on_time']}, delayed={stress['baseline_delayed']}
Stressed: on_time={stress['stressed_on_time']}, delayed={stress['stressed_delayed']}, avg_delay={stress.get('avg_delay_stressed')}
Sweet spot JSON (truncated; sweet_spot_value is k on same scale): {json.dumps(sweet, default=str)[:4000]}
Risk: {json.dumps(risk, indent=2)}
"""

    try:
        sim_agent = _call_json_agent(client, sys3, user3, temperature=0.2)
    except Exception as e:
        sim_agent = {
            "headline": "Simulation results computed.",
            "kpi_interpretation": str(e),
            "next_levers_to_try": [],
            "confidence": 5,
        }

    trace.append({"agent": "Simulation", "summary": sim_agent.get("headline", "")[:500]})

    pc = _confidence_from_json(pred)
    rc = _confidence_from_json(risk)
    sc = _confidence_from_json(sim_agent)
    agg_conf = _aggregate_narration_confidence(pc, rc, sc)

    sys4 = f"""You are the Narration agent for supply chain managers (what-if / stress scenario).
{_NARRATION_MARKDOWN_SHAPE}
Use bullet lists in ## Details where helpful. Use ONLY the numbers provided in the user message—do not invent counts.
The final **Confidence:** line MUST use exactly {agg_conf}/10 (rounded mean of Prediction/Risk/Simulation agent scores: {pc}, {rc}, {sc}) plus a short reason tied to those inputs.
Keep total output under 650 words. Friendly tone is OK."""

    user4 = f"""User question: {user_question}

Prediction: {json.dumps(pred, indent=2)}
Risk: {json.dumps(risk, indent=2)}
Simulation: {json.dumps(sim_agent, indent=2)}

Hard numbers (must match):
- Date range: {start_str} to {end_str}
- Delivered cohort: {on_time_n} on-time, {delayed_n} delayed (empty cohort: {cohort_empty})
- In-transit count: {in_transit.get('in_transit_count')}
- Stress hub: {hub}, capacity k: {mult}
- After stress: on_time={stress['stressed_on_time']}, delayed={stress['stressed_delayed']} (baseline delayed {stress['baseline_delayed']})
- Delayed journeys through hub: {touching}

Anchored narration confidence: {agg_conf}/10 (from agent confidences {pc}, {rc}, {sc}).

Hub capacity semantics:
{HUB_CAPACITY_K_EXPLAINER_STRESS}
"""

    try:
        narrative = _call_text_agent(client, sys4, user4, temperature=0.35)
    except Exception as e:
        narrative = f"## Error\nFailed to generate narration: {e}"

    trace.append({"agent": "Narration", "summary": narrative[:400]})
    result["narrative_markdown"] = narrative
    return result


def run_what_if_advisor(
    user_question: str,
    date_range: str = "week",
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> dict[str, Any]:
    trace: list[dict[str, str]] = []
    result: dict[str, Any] = {
        "narrative_markdown": "",
        "agent_trace": trace,
        "metrics_lines": [],
        "error": None,
    }

    if not (user_question or "").strip():
        result["error"] = "Please enter a question."
        return result

    try:
        client = _get_openai_client()
    except Exception as e:
        result["error"] = str(e)
        return result

    rag_chunks = retrieve(user_question, k=6)
    dispatch = get_dispatch()
    if _planner_mode() == "openai_tools":
        pipeline, reason = _plan_pipeline_openai_tools(
            client, user_question, rag_chunks, date_range, trace, dispatch
        )
    else:
        pipeline, reason = _plan_pipeline(client, user_question, rag_chunks)
    if _force_full_stress_heuristic(user_question):
        pipeline = "full_stress"
        reason = "heuristic_override_stress_keywords"
    elif _force_optimization_heuristic(user_question):
        pipeline = "optimization_simulation"
        reason = "heuristic_override_optimization_keywords"

    trace.append(
        {
            "agent": "Planner",
            "summary": f"mode={_planner_mode()}; tools={dispatch.mode}; pipeline={pipeline}; {reason}"[:500],
        }
    )

    if pipeline == "operational_snapshot":
        return _run_operational_snapshot(client, user_question, rag_chunks, trace, result)

    if pipeline == "delivered_analytics":
        return _run_delivered_analytics(
            client, user_question, rag_chunks, date_range, start_date, end_date, trace, result
        )

    if pipeline == "optimization_simulation":
        return _run_optimization_simulation(
            client, user_question, rag_chunks, date_range, start_date, end_date, trace, result
        )

    return _run_full_stress(
        client, user_question, rag_chunks, date_range, start_date, end_date, trace, result
    )

