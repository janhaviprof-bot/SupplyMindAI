"""
Named tools for the What-If advisor: DB + optimization pipeline + simulation.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any, Optional

from analysis.optimization_pipeline import (
    _fetch_delivered_shipments_by_date,
    _fetch_stops_with_hubs_risks,
    _parse_date_range,
    _split_and_metrics,
    call_openai_sim_insights,
    parse_recommendation_to_sim_param,
    run_optimization_insights_with_data,
)
from analysis.pipeline import (
    _fetch_future_hubs_and_risks,
    _fetch_in_transit_shipments,
    _fetch_stops_and_enrich,
    get_all_insights,
)
from analysis.simulation import (
    HUB_CAPACITY_K_EXPLAINER_OPTIMIZATION,
    HUB_CAPACITY_K_EXPLAINER_STRESS,
    find_sweet_spot,
    simulate_delays,
)
from supplymind_db.supabase_client import execute_query


def tool_list_hub_names() -> list[str]:
    rows = execute_query("SELECT hub_name FROM hubs ORDER BY hub_name", fetch=True)
    return [r["hub_name"] for r in (rows or []) if r.get("hub_name")]


def tool_get_delivered_cohort(
    date_range: str,
    start_date=None,
    end_date=None,
) -> dict[str, Any]:
    try:
        start_ts, end_ts = _parse_date_range(date_range, start_date, end_date)
        start_str = start_ts.strftime("%b %d, %Y")
        end_str = end_ts.strftime("%b %d, %Y")
        shipments = _fetch_delivered_shipments_by_date(start_ts, end_ts)
        if not shipments:
            return {
                "ok": True,
                "empty": True,
                "on_time_raw": [],
                "delayed_raw": [],
                "metrics": {},
                "start_str": start_str,
                "end_str": end_str,
            }
        shipment_ids = [s["shipment_id"] for s in shipments]
        stops_by_shipment = _fetch_stops_with_hubs_risks(shipment_ids)
        on_time, delayed, metrics = _split_and_metrics(shipments, stops_by_shipment)
        return {
            "ok": True,
            "empty": False,
            "on_time_raw": on_time,
            "delayed_raw": delayed,
            "metrics": metrics,
            "start_str": start_str,
            "end_str": end_str,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def tool_get_in_transit_aggregate() -> dict[str, Any]:
    shipments = _fetch_in_transit_shipments()
    if not shipments:
        return {
            "in_transit_count": 0,
            "future_risk_mix": [],
            "hubs_with_future_exposure": [],
            "critical_flagged_count": 0,
            "delayed_flagged_count": 0,
            "samples": [],
        }
    sids = [s["shipment_id"] for s in shipments]
    idx = {s["shipment_id"]: s.get("current_stop_index") or 0 for s in shipments}
    future_by = _fetch_future_hubs_and_risks(sids, idx)
    insights_by = {r["shipment_id"]: r for r in get_all_insights()}
    cat_counter: Counter[str] = Counter()
    hub_counter: Counter[str] = Counter()
    critical_flagged = 0
    delayed_flagged = 0

    for s in shipments:
        sid = s["shipment_id"]
        fd = future_by.get(sid, {})
        fr = fd.get("future_risks") or []
        for r in fr:
            c = r.get("category")
            if c:
                cat_counter[str(c)] += 1
            hn = r.get("hub_name")
            if hn:
                hub_counter[str(hn)] += 1
        ins = insights_by.get(sid) or {}
        fl = (ins.get("flag_status") or "").lower()
        if "critical" in fl:
            critical_flagged += 1
        elif "delayed" in fl:
            delayed_flagged += 1

    samples: list[dict] = []
    for s in shipments[:3]:
        sid = s["shipment_id"]
        fd = future_by.get(sid, {})
        samples.append(
            {
                "shipment_id": sid,
                "priority_level": s.get("priority_level"),
                "future_hubs": [h.get("hub_name") for h in (fd.get("future_hubs") or [])[:4]],
                "future_risk_categories": list(
                    {r.get("category") for r in (fd.get("future_risks") or []) if r.get("category")}
                )[:5],
            }
        )

    return {
        "in_transit_count": len(shipments),
        "future_risk_mix": cat_counter.most_common(10),
        "hubs_with_future_exposure": hub_counter.most_common(12),
        "critical_flagged_count": critical_flagged,
        "delayed_flagged_count": delayed_flagged,
        "samples": samples,
    }


def tool_count_touching_hub(delayed_raw: list[dict], hub_name: str) -> int:
    if not hub_name:
        return 0
    hn = hub_name.strip().lower()
    n = 0
    for p in delayed_raw:
        for stop in p.get("stops") or []:
            if str(stop.get("hub_name") or "").strip().lower() == hn:
                n += 1
                break
    return n


def tool_run_hub_capacity_stress(
    on_time_raw: list[dict],
    delayed_raw: list[dict],
    target_hub: str,
    capacity_multiplier: float,
) -> dict[str, Any]:
    baseline_ot = len(on_time_raw)
    baseline_del = len(delayed_raw)
    sim = simulate_delays(
        on_time_raw,
        delayed_raw,
        "hub_capacity",
        target_hub,
        None,
        capacity_multiplier,
    )
    return {
        "lever": "hub_capacity",
        "target_hub": target_hub,
        "capacity_multiplier": capacity_multiplier,
        "baseline_on_time": baseline_ot,
        "baseline_delayed": baseline_del,
        "stressed_on_time": sim["on_time_count"],
        "stressed_delayed": sim["delayed_count"],
        "recovered_vs_baseline_delayed": baseline_del - sim["delayed_count"],
        "avg_delay_stressed": sim.get("avg_delay"),
    }


def tool_find_recovery_sweet_spot(
    on_time_raw: list[dict],
    delayed_raw: list[dict],
    target_hub: str,
    value_min: float = 0.75,
    value_max: float = 1.35,
) -> Optional[dict[str, Any]]:
    """Grid-search k (hub_capacity) between value_min and value_max; same k semantics as stress/expansion."""
    if not delayed_raw:
        return None
    return find_sweet_spot(
        on_time_raw,
        delayed_raw,
        "hub_capacity",
        target_hub,
        None,
        value_min,
        value_max,
        11,
        "roi",
    )

def tool_get_delivered_cohort_summary(
    date_range: str,
    start_date=None,
    end_date=None,
) -> dict[str, Any]:
    c = tool_get_delivered_cohort(date_range, start_date, end_date)
    if not c.get("ok"):
        return c
    return {
        "ok": True,
        "empty": c.get("empty"),
        "start_str": c.get("start_str"),
        "end_str": c.get("end_str"),
        "on_time_count": len(c.get("on_time_raw") or []),
        "delayed_count": len(c.get("delayed_raw") or []),
        "metrics": c.get("metrics") or {},
    }


def tool_run_capacity_stress_pipeline(
    date_range: str,
    target_hub: str,
    capacity_multiplier: float,
    start_date=None,
    end_date=None,
    run_sweet_spot: bool = True,
    sweet_value_min: float = 0.75,
    sweet_value_max: float = 1.35,
) -> dict[str, Any]:
    """Delivered cohort + hub capacity stress (k≤1) + optional ROI sweet-spot on k (default grid ~0.75–1.35)."""
    cohort = tool_get_delivered_cohort(date_range, start_date, end_date)
    if not cohort.get("ok"):
        return {"ok": False, "error": cohort.get("error", "cohort_failed")}
    on_time_raw = cohort.get("on_time_raw") or []
    delayed_raw = cohort.get("delayed_raw") or []
    hub = (target_hub or "").strip()
    try:
        mult = float(capacity_multiplier)
    except (TypeError, ValueError):
        mult = 0.8
    mult = max(0.5, min(1.0, mult))
    stress = tool_run_hub_capacity_stress(on_time_raw, delayed_raw, hub, mult)
    touching = tool_count_touching_hub(delayed_raw, hub)
    sweet: Optional[dict[str, Any]] = None
    if run_sweet_spot and hub and delayed_raw:
        try:
            sweet = tool_find_recovery_sweet_spot(
                on_time_raw, delayed_raw, hub, sweet_value_min, sweet_value_max
            )
        except Exception:
            sweet = None
    return {
        "ok": True,
        "empty": cohort.get("empty"),
        "start_str": cohort.get("start_str"),
        "end_str": cohort.get("end_str"),
        "on_time_count": len(on_time_raw),
        "delayed_count": len(delayed_raw),
        "metrics": cohort.get("metrics") or {},
        "stress": stress,
        "touching": touching,
        "sweet_spot": sweet,
        "hub_capacity_k_semantics": HUB_CAPACITY_K_EXPLAINER_STRESS,
    }


_LEVER_RANGES: dict[str, tuple[float, float]] = {
    "hub_capacity": (1.0, 2.0),
    "dispatch_time_at_hub": (0, 1),
    "transit_mode": (0, 1.0),
    "earlier_dispatch": (0, 720),
    "risk_based_buffer": (0, 8.0),
}


def _strip_html(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"<[^>]+>", "", str(s)).replace("&nbsp;", " ").strip()


def tool_run_optimization_simulation(
    date_range: str,
    start_date=None,
    end_date=None,
    max_levers: int = 4,
) -> dict[str, Any]:
    """
    Run optimization insights (five-lever recommendations) plus ROI sweet-spot curves
    on simulatable parameters — same core logic as the dashboard simulation card.
    """
    try:
        ml = int(max_levers) if max_levers is not None else 4
    except (TypeError, ValueError):
        ml = 4
    ml = max(1, min(5, ml))

    opt = run_optimization_insights_with_data(date_range, start_date, end_date)
    out: dict[str, Any] = {
        "ok": True,
        "error": opt.get("error"),
        "date_range": date_range,
        "summary": opt.get("summary") or "",
        "summary_text_plain": _strip_html(opt.get("summary_text") or ""),
        "control_parameters": opt.get("control_parameters") or [],
        "top_parameters": opt.get("top_parameters") or [],
        "on_time_count": int(opt.get("on_time_count") or 0),
        "delayed_count": int(opt.get("delayed_count") or 0),
        "curves_brief": [],
        "sim_insights": None,
        "simulation_note": None,
    }
    if opt.get("error"):
        out["ok"] = False
        return out

    on_time = opt.get("on_time_raw") or []
    delayed = opt.get("delayed_raw") or []
    if not on_time and not delayed:
        out["simulation_note"] = "No delivered shipments in range; simulation skipped."
        out["ok"] = True
        return out

    control = opt.get("control_parameters") or []
    top = [tp.get("label", "") for tp in (opt.get("top_parameters") or []) if tp.get("label")]
    all_labels = list(dict.fromkeys(control + top))
    simulatable = [lb for lb in all_labels if parse_recommendation_to_sim_param(lb)][:5]
    params_to_run = simulatable[:ml]
    if not params_to_run:
        out["simulation_note"] = "No simulatable lever labels from recommendations; only qualitative summary available."
        return out

    curves: list[dict[str, Any]] = []
    try:
        for label in params_to_run:
            parsed = parse_recommendation_to_sim_param(label)
            if not parsed:
                continue
            ptype = parsed.get("type", "")
            target_hub = parsed.get("target_hub")
            target_route = parsed.get("target_route")
            vmin, vmax = _LEVER_RANGES.get(ptype, (0, 1))
            res = find_sweet_spot(
                on_time, delayed, ptype, target_hub, target_route, vmin, vmax, 11, "roi"
            )
            curve_data = res.get("curve", [])
            pts = res.get("chart_points_3", [])
            curves.append(
                {
                    "label": label[:80] + ("..." if len(label) > 80 else ""),
                    "lever_type": ptype,
                    "target_hub": target_hub,
                    "target_route": target_route,
                    "value_min": vmin,
                    "value_max": vmax,
                    "sweet_spot_value": res.get("sweet_spot_value"),
                    "chart_points_3": pts,
                    "curve": curve_data,
                    "best_metrics": res.get("best_metrics", {}),
                }
            )
    except Exception as e:
        out["ok"] = False
        out["error"] = str(e)
        return out

    if not curves:
        out["simulation_note"] = "Simulation produced no curves."
        return out

    baseline_ot = len(on_time)
    baseline_dly = len(delayed)
    for c in curves:
        pts = c.get("chart_points_3") or []
        best = c.get("best_metrics") or {}
        inv_min = float(pts[0][0]) if pts else 0.0
        inv_sweet = float(pts[1][0]) if len(pts) >= 2 else 0.0
        inv_max = float(pts[2][0]) if len(pts) > 2 else 0.0
        recovered = int(best.get("on_time_count", baseline_ot) - baseline_ot)
        ptype = c.get("lever_type") or ""
        sweet_k = c.get("sweet_spot_value")
        vmin = c.get("value_min")
        vmax = c.get("value_max")
        th = c.get("target_hub")

        interpretation_note: str | None = None
        if ptype == "hub_capacity" and recovered > 0 and inv_sweet < 1.0:
            hub_phrase = f' at hub "{th}"' if th else " at the named hub"
            interpretation_note = (
                "k=1.0 means effective capacity equals nominal max_capacity (no increase vs that baseline); "
                "k=1.2 means effective capacity 20% above nominal. "
                "Modeled incremental USD = (k − 1.0) × $1M, so k=1.0 ⇒ $0 incremental in the model only. "
                f"The ROI search picked k={sweet_k} on a grid from k={vmin} to k={vmax}{hub_phrase}. "
                f"At k={vmax}, indicative modeled incremental spend is about ${inv_max:,.0f}. "
                "Real-world capacity expansion still requires capex/opex; never imply physical expansion is free."
            )

        row: dict[str, Any] = {
            "label": c.get("label"),
            "lever_type": ptype,
            "target_hub": th,
            "target_route": c.get("target_route"),
            "lever_value_sweet_spot": sweet_k,
            "lever_value_grid_min": vmin,
            "lever_value_grid_max": vmax,
            "sweet_spot_investment_usd": inv_sweet,
            "modeled_investment_min_usd": inv_min,
            "modeled_investment_max_usd": inv_max,
            "recovered_on_time_shipments": recovered,
            "on_time_at_min_mid_max_investment": [
                (pts[i][1] if len(pts) > i else baseline_ot) for i in range(3)
            ]
            if pts
            else [],
        }
        if interpretation_note:
            row["investment_interpretation_note"] = interpretation_note
        out["curves_brief"].append(row)

    graph_data = {
        "curves": curves,
        "baseline_on_time": baseline_ot,
        "baseline_delayed": baseline_dly,
        "simulatable_params": simulatable,
        "simulated_params": [c["label"] for c in curves],
    }
    try:
        out["sim_insights"] = call_openai_sim_insights(graph_data)
    except Exception as e:
        out["sim_insights"] = {"error": str(e)}

    out["capacity_multiplier_k_meaning"] = HUB_CAPACITY_K_EXPLAINER_OPTIMIZATION

    return out

