# Bundle: replace `SupplyMindAI/advisor/what_if.py` with the code below (extract via Agent or shell).

~~~python
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
from advisor.tools_impl import (
    tool_find_recovery_sweet_spot,
    tool_get_delivered_cohort,
    tool_get_in_transit_aggregate,
    tool_list_hub_names,
    tool_run_hub_capacity_stress,
    tool_count_touching_hub,
)


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


def _plan_pipeline(client, user_question: str, rag_chunks: list[str]) -> tuple[str, str]:
    """Returns (pipeline_id, reason). pipeline_id in full_stress | operational_snapshot | delivered_analytics."""
    sys_pl = """You are the orchestration planner for a logistics advisor. Pick exactly ONE pipeline:

- "full_stress" — User wants a what-if or simulation: capacity change at a hub, stress test, multiplier, impact on delays, recovery/sweet spot, "what happens if…" scenarios.
- "operational_snapshot" — User wants current operational picture only: in-transit counts, today's risks, exposure, general "how are we doing now", hub list context, without historical delivered cohort analysis or simulation.
- "delivered_analytics" — User wants historical / baseline performance: on-time vs delayed for the selected period, past trends, cohort summaries, KPIs from completed deliveries — but NOT a capacity stress simulation.

Output ONLY valid JSON:
{"pipeline":"full_stress"|"operational_snapshot"|"delivered_analytics","reason":"one short sentence"}"""

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
    return "full_stress", reason or "default"


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
        f"Hub stressed: {hub} · capacity multiplier: {mult} ({round((mult - 1) * 100)}% vs baseline)",
        f"Baseline delivered: {stress['baseline_on_time']} on-time, {stress['baseline_delayed']} delayed",
        f"After stress: {stress['stressed_on_time']} on-time, {stress['stressed_delayed']} delayed (Δ delayed: {stress['stressed_delayed'] - stress['baseline_delayed']})",
        f"In transit: {in_transit.get('in_transit_count')} · critical/delayed (insights): {in_transit.get('critical_flagged_count')}/{in_transit.get('delayed_flagged_count')}",
        f"Delayed delivered journeys through hub: {touching}",
    ]
    if sweet:
        bm = sweet.get("best_metrics") or {}
        lines.append(
            f"Recovery sweep sweet spot × {sweet.get('sweet_spot_value')} · recovered {bm.get('recovered_count', '—')}"
        )
    return lines


def _run_operational_snapshot(
    client,
    user_question: str,
    rag_chunks: list[str],
    trace: list[dict[str, str]],
    result: dict[str, Any],
) -> dict[str, Any]:
    in_transit = tool_get_in_transit_aggregate()
    known_hubs = tool_list_hub_names()
    sys_n = """You are the Narration agent. Answer using ONLY the JSON and RAG excerpts provided.
Write concise markdown for supply chain managers.
Use ## headings: ## Current picture, ## Risks and exposure, ## Suggested focus
Use bullet lists. Do not invent shipment counts—use only numbers from the user message.
Keep under 350 words."""

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
    in_transit = tool_get_in_transit_aggregate()
    known_hubs = tool_list_hub_names()
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

    sys_n = """You are the Narration agent. Write concise markdown for supply chain managers.
Use ## headings: ## Summary, ## Delivered performance, ## In transit snapshot, ## Next steps
Use bullet lists. Use ONLY the numbers in the user message. No capacity simulation was run.
Keep under 400 words."""

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
    in_transit = tool_get_in_transit_aggregate()
    known_hubs = tool_list_hub_names()
    cohort = tool_get_delivered_cohort(date_range, start_date, end_date)

    if not cohort.get("ok"):
        result["error"] = cohort.get("error", "Failed to load delivered cohort.")
        return result

    on_time_raw = cohort.get("on_time_raw") or []
    delayed_raw = cohort.get("delayed_raw") or []
    metrics = cohort.get("metrics") or {}
    start_str = cohort.get("start_str", "")
    end_str = cohort.get("end_str", "")

    sys1 = """You are the Prediction agent for a logistics what-if advisor.
Output ONLY valid JSON:
{
  "interpreted_scenario": "short plain English",
  "target_hub": "exact hub name from context lists or null",
  "capacity_multiplier": number (1.0 = baseline; 0.8 = 20% capacity reduction at that hub),
  "confidence": 1-10,
  "notes": "optional"
}
Use capacity_multiplier between 0.65 and 1.0 for stress scenarios."""

    user1 = f"""User question: {user_question}

Retrieved context (RAG):
{chr(10).join(rag_chunks[:5])}

In-transit aggregate (JSON):
{json.dumps(in_transit, indent=2, default=str)}

Known hub names:
{json.dumps(known_hubs[:40])}

Delivered cohort: empty={cohort.get('empty')}, on_time={len(on_time_raw)}, delayed={len(delayed_raw)}, range {start_str}–{end_str}.
Delay metrics: {json.dumps(metrics, default=str)}
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

    stress = tool_run_hub_capacity_stress(on_time_raw, delayed_raw, hub or "", mult)
    touching = tool_count_touching_hub(delayed_raw, hub or "")

    sweet = None
    if hub and delayed_raw:
        try:
            sweet = tool_find_recovery_sweet_spot(on_time_raw, delayed_raw, hub, 0.75, 1.35)
        except Exception:
            sweet = None

    result["metrics_lines"] = _metrics_lines(
        stress,
        sweet,
        in_transit,
        start_str,
        end_str,
        hub or "—",
        mult,
        touching,
        bool(cohort.get("empty")),
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
Resolved hub: {hub}, multiplier: {mult}
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

    user3 = f"""Hub {hub}, multiplier {mult}.
Baseline: on_time={stress['baseline_on_time']}, delayed={stress['baseline_delayed']}
Stressed: on_time={stress['stressed_on_time']}, delayed={stress['stressed_delayed']}, avg_delay={stress.get('avg_delay_stressed')}
Sweet spot JSON (truncated): {json.dumps(sweet, default=str)[:4000]}
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

    sys4 = """You are the Narration agent. Write a concise markdown report for supply chain managers.
Use ## headings: ## Scenario, ## Key findings, ## Recommended actions, ## Confidence
Use bullet lists. Use ONLY the numbers provided in the user message—do not invent counts.
Keep under 400 words. Friendly chat tone is OK."""

    user4 = f"""User question: {user_question}

Prediction: {json.dumps(pred, indent=2)}
Risk: {json.dumps(risk, indent=2)}
Simulation: {json.dumps(sim_agent, indent=2)}

Hard numbers (must match):
- Date range: {start_str} to {end_str}
- Delivered cohort: {len(on_time_raw)} on-time, {len(delayed_raw)} delayed (empty cohort: {cohort.get('empty')})
- In-transit count: {in_transit.get('in_transit_count')}
- Stress hub: {hub}, capacity multiplier: {mult}
- After stress: on_time={stress['stressed_on_time']}, delayed={stress['stressed_delayed']} (baseline delayed {stress['baseline_delayed']})
- Delayed journeys through hub: {touching}
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
    pipeline, reason = _plan_pipeline(client, user_question, rag_chunks)
    if _force_full_stress_heuristic(user_question):
        pipeline = "full_stress"
        reason = "heuristic_override_stress_keywords"

    trace.append({"agent": "Planner", "summary": f"pipeline={pipeline}; {reason}"[:500]})

    if pipeline == "operational_snapshot":
        return _run_operational_snapshot(client, user_question, rag_chunks, trace, result)

    if pipeline == "delivered_analytics":
        return _run_delivered_analytics(
            client, user_question, rag_chunks, date_range, start_date, end_date, trace, result
        )

    return _run_full_stress(
        client, user_question, rag_chunks, date_range, start_date, end_date, trace, result
    )
~~~
