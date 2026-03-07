"""
Supply chain optimization insights pipeline.
Fetches delivered shipments by date range, enriches with stops/hubs/risks,
splits on-time vs delayed, computes metrics, and gets AI recommendations.
"""
import json
import os
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from db.supabase_client import execute_query, get_connection

MAX_SHIPMENTS = 200  # Cap for large date ranges


def get_all_hub_coords() -> list[dict]:
    """Return all hubs with lat/lon for map base layer (used before analysis runs)."""
    rows = execute_query("SELECT hub_name, lat, lon FROM hubs")
    return [
        {"hub_name": r["hub_name"], "lat": float(r["lat"]), "lon": float(r["lon"])}
        for r in rows
        if r.get("lat") is not None and r.get("lon") is not None
    ]


def _load_env():
    """Load .env from project root."""
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _get_openai_client():
    """Get OpenAI client. Requires OPENAI_API_KEY in .env."""
    _load_env()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Set OPENAI_API_KEY in .env")
    from openai import OpenAI
    return OpenAI(api_key=api_key)


def _parse_date_range(date_range: str, start_date=None, end_date=None) -> tuple[datetime, datetime]:
    """Return (start_ts, end_ts) as timezone-aware datetimes."""
    now = datetime.utcnow()
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=0)

    if date_range == "custom":
        if start_date is None or end_date is None:
            raise ValueError("Custom range requires start_date and end_date")
        start = datetime.combine(start_date, datetime.min.time()) if hasattr(start_date, "day") else datetime.fromisoformat(str(start_date))
        end = datetime.combine(end_date, datetime.max.time()) if hasattr(end_date, "day") else datetime.fromisoformat(str(end_date))
        if end < start:
            raise ValueError("End date must be >= start date")
        if (end - start).days > 365:
            raise ValueError("Custom range cannot exceed 1 year. Please narrow the range.")
        return start, end

    if date_range == "yesterday":
        start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=0)
    elif date_range == "week":
        start = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = today_end
    elif date_range == "month":
        start = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = today_end
    elif date_range == "year":
        start = (now - timedelta(days=365)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = today_end
    else:
        # Default to past week
        start = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = today_end
    return start, end


def _fetch_delivered_shipments_by_date(start_ts: datetime, end_ts: datetime) -> list[dict]:
    """Step 3: Fetch delivered shipments where delivery_ts falls in range. Cap at MAX_SHIPMENTS."""
    rows = execute_query(
        """
        WITH delivery_dates AS (
            SELECT
                s.shipment_id,
                s.material_type,
                s.priority_level,
                s.total_stops,
                s.final_deadline,
                (
                    SELECT MAX(COALESCE(st.actual_arrival, st.actual_departure))
                    FROM stops st
                    WHERE st.shipment_id = s.shipment_id
                ) AS delivery_ts
            FROM shipments s
            WHERE s.status = 'Delivered'
        )
        SELECT shipment_id, material_type, priority_level, total_stops, final_deadline, delivery_ts
        FROM delivery_dates
        WHERE delivery_ts IS NOT NULL
          AND delivery_ts >= %s
          AND delivery_ts <= %s
        ORDER BY delivery_ts DESC
        LIMIT %s
        """,
        (start_ts, end_ts, MAX_SHIPMENTS),
    )
    return [dict(r) for r in rows]


def _fetch_stops_with_hubs_risks(shipment_ids: list[str]) -> dict:
    """Step 4: For each shipment, get all stops with hub occupancy and risks."""
    if not shipment_ids:
        return {}
    placeholders = ",".join(["%s"] * len(shipment_ids))
    rows = execute_query(
        f"""
        SELECT st.shipment_id, st.stop_number, st.hub_name,
               st.planned_arrival, st.actual_arrival,
               st.planned_departure, st.actual_departure
        FROM stops st
        WHERE st.shipment_id IN ({placeholders})
        ORDER BY st.shipment_id, st.stop_number
        """,
        tuple(shipment_ids),
    )
    by_shipment = {}
    all_hub_names = set()
    for r in rows:
        sid = r["shipment_id"]
        if sid not in by_shipment:
            by_shipment[sid] = []
        by_shipment[sid].append(dict(r))
        all_hub_names.add(r["hub_name"])

    # Fetch hubs and risks
    hub_data = {}
    risk_rows = []
    if all_hub_names:
        hp = ",".join(["%s"] * len(all_hub_names))
        hub_rows = execute_query(
            f"SELECT hub_name, lat, lon, current_load, max_capacity, status FROM hubs WHERE hub_name IN ({hp})",
            tuple(all_hub_names),
        )
        hub_data = {r["hub_name"]: dict(r) for r in hub_rows}
        risk_rows = execute_query(
            f"SELECT hub_name, category, severity, est_delay_hrs FROM risks WHERE hub_name IN ({hp})",
            tuple(all_hub_names),
        )

    risks_by_hub = {}
    for r in risk_rows:
        hn = r["hub_name"]
        if hn not in risks_by_hub:
            risks_by_hub[hn] = []
        risks_by_hub[hn].append(dict(r))

    # Build enriched stops
    result = {}
    for sid, stops in by_shipment.items():
        enriched = []
        for s in stops:
            hn = s["hub_name"]
            hub_info = hub_data.get(hn, {})
            stop_data = {
                "stop_number": s["stop_number"],
                "hub_name": hn,
                "planned_arrival": s["planned_arrival"].isoformat() if s.get("planned_arrival") else None,
                "actual_arrival": s["actual_arrival"].isoformat() if s.get("actual_arrival") else None,
                "planned_departure": s["planned_departure"].isoformat() if s.get("planned_departure") else None,
                "actual_departure": s["actual_departure"].isoformat() if s.get("actual_departure") else None,
                "current_load": hub_info.get("current_load"),
                "max_capacity": hub_info.get("max_capacity"),
                "status": hub_info.get("status"),
                "risks": [{"category": x.get("category"), "severity": x.get("severity"), "est_delay_hrs": x.get("est_delay_hrs")} for x in risks_by_hub.get(hn, [])],
            }
            enriched.append(stop_data)
        result[sid] = enriched
    return result


def _build_enriched_payload(shipment: dict, stops: list) -> dict:
    """Step 5: Build enriched payload for AI and simulation."""
    origin = stops[0]["hub_name"] if stops else None
    destination = stops[-1]["hub_name"] if stops else None
    payload = {
        "shipment_id": shipment["shipment_id"],
        "priority_level": shipment["priority_level"],
        "material_type": shipment.get("material_type"),
        "final_deadline": shipment["final_deadline"].isoformat() if shipment.get("final_deadline") else None,
        "origin": origin,
        "destination": destination,
        "stops": stops,
    }
    if shipment.get("delivery_ts"):
        payload["delivery_ts"] = shipment["delivery_ts"]
    return payload


def _split_and_metrics(shipments: list[dict], stops_by_shipment: dict) -> tuple[list, list, dict]:
    """Step 6: Split on-time vs delayed, compute delay metrics."""
    on_time = []
    delayed = []
    delays_hrs = []
    hub_counts_delayed = Counter()
    risk_cats_delayed = Counter()

    for s in shipments:
        sid = s["shipment_id"]
        delivery_ts = s.get("delivery_ts")
        final_deadline = s.get("final_deadline")
        stops = stops_by_shipment.get(sid, [])
        payload = _build_enriched_payload(s, stops)

        if delivery_ts is None:
            continue
        if final_deadline is None:
            on_time.append(payload)
            continue

        is_on_time = delivery_ts <= final_deadline
        if is_on_time:
            on_time.append(payload)
        else:
            delay_sec = (delivery_ts - final_deadline).total_seconds()
            delay_hrs = delay_sec / 3600
            delays_hrs.append(delay_hrs)
            payload["delay_hours"] = round(delay_hrs, 2)
            delayed.append(payload)
            for stop in stops:
                hub_counts_delayed[stop["hub_name"]] += 1
                for r in stop.get("risks", []):
                    if r.get("category"):
                        risk_cats_delayed[r["category"]] += 1

    avg_delay = sum(delays_hrs) / len(delays_hrs) if delays_hrs else 0
    top_hubs = [h for h, _ in hub_counts_delayed.most_common(5)]

    metrics = {
        "avg_delay_hours": round(avg_delay, 2),
        "top_delayed_hubs": top_hubs,
        "common_risk_categories": [c for c, _ in risk_cats_delayed.most_common(5)],
    }
    return on_time, delayed, metrics


def _build_hub_map_data(on_time: list, delayed: list) -> dict:
    """
    Build hub data for map. Returns:
    - "all_hubs": list of {hub_name, lat, lon} for every hub (black base layer)
    - "status_hubs": list of {hub_name, lat, lon, status, in_delayed_count, risk_categories}
      status = red (delayed + risks), orange (delayed, no risks), green (on-time only)
    """
    analysis_hub_names = set()
    hub_delayed_count = Counter()
    hub_has_risks = {}
    hub_risk_cats = {}

    for payload in delayed:
        for stop in payload.get("stops", []):
            hn = stop.get("hub_name")
            if not hn:
                continue
            analysis_hub_names.add(hn)
            hub_delayed_count[hn] += 1
            risks = stop.get("risks", [])
            if risks:
                hub_has_risks[hn] = True
                cats = hub_risk_cats.setdefault(hn, set())
                for r in risks:
                    if r.get("category"):
                        cats.add(r["category"])
                hub_risk_cats[hn] = cats

    for payload in on_time:
        for stop in payload.get("stops", []):
            hn = stop.get("hub_name")
            if hn:
                analysis_hub_names.add(hn)

    # Fetch ALL hubs for black base layer
    all_rows = execute_query("SELECT hub_name, lat, lon FROM hubs")
    all_hubs = []
    coords = {}
    for r in all_rows:
        lat, lon = r.get("lat"), r.get("lon")
        if lat is not None and lon is not None:
            all_hubs.append({"hub_name": r["hub_name"], "lat": float(lat), "lon": float(lon)})
            coords[r["hub_name"]] = (float(lat), float(lon))

    status_hubs = []
    for hn in analysis_hub_names:
        latlon = coords.get(hn)
        if not latlon:
            continue
        lat, lon = latlon
        in_delayed = hub_delayed_count.get(hn, 0)
        has_risks = hub_has_risks.get(hn, False)
        risk_cats = list(hub_risk_cats.get(hn, []))

        if in_delayed and has_risks:
            status = "red"
        elif in_delayed:
            status = "orange"
        else:
            status = "green"

        status_hubs.append({
            "hub_name": hn,
            "lat": lat,
            "lon": lon,
            "status": status,
            "in_delayed_count": in_delayed,
            "risk_categories": risk_cats,
        })
    return {"all_hubs": all_hubs, "status_hubs": status_hubs}


# Canonical simulation parameter types (5 levers)
SIM_PARAM_TYPES = (
    "hub_capacity",
    "dispatch_time_at_hub",
    "transit_mode",
    "earlier_dispatch",
    "risk_based_buffer",
)


def parse_recommendation_to_sim_param(text: str) -> Optional[dict]:
    """
    Parse a recommendation string into a simulatable parameter.
    Returns {type, target_hub, target_route} or None if unparseable.
    """
    if not text or not isinstance(text, str):
        return None
    t = text.strip().lower()
    # Hub capacity / congestion (same lever)
    if "increase capacity" in t or "expand capacity" in t or "reduce congestion" in t:
        # Extract hub name: "X hub:" or "Hub X:" pattern
        for sep in [" hub:", " hub ", ":"]:
            if sep in t:
                parts = t.split(sep, 1)
                if parts:
                    hub = parts[0].replace("hub", "").strip()
                    if hub:
                        return {"type": "hub_capacity", "target_hub": hub, "target_route": None}
        return {"type": "hub_capacity", "target_hub": None, "target_route": None}
    # Dispatch time at hub
    if "reduce dwell" in t or "speed up processing" in t or "dispatch time" in t and "hub" in t:
        for sep in [" hub:", " hub ", ":"]:
            if sep in t:
                parts = t.split(sep, 1)
                if parts:
                    hub = parts[0].replace("hub", "").strip()
                    if hub:
                        return {"type": "dispatch_time_at_hub", "target_hub": hub, "target_route": None}
        return {"type": "dispatch_time_at_hub", "target_hub": None, "target_route": None}
    # Transit mode
    if "faster transit" in t or "faster mode" in t or "switch to faster" in t:
        return {"type": "transit_mode", "target_hub": None, "target_route": None}
    # Earlier dispatch
    if "dispatch earlier" in t or "add buffer time" in t and "risk" not in t:
        return {"type": "earlier_dispatch", "target_hub": None, "target_route": None}
    # Risk-based buffer
    if "risk-based" in t or "risk buffer" in t or "predicted-risk" in t or "eta buffer" in t:
        return {"type": "risk_based_buffer", "target_hub": None, "target_route": None}
    return None


def _truncate_summary(text: str, max_words: int = 100) -> str:
    """Truncate text to max_words."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])


def _call_openai_recommendations(client, on_time: list, delayed: list, metrics: dict, start_str: str, end_str: str) -> dict:
    """Step 7: Call OpenAI for structured supply chain recommendations (JSON)."""
    prompt = f"""You are a supply chain optimization expert. Analyze the following delivered shipment data.

**Date range analyzed:** {start_str} to {end_str}

**On-time deliveries ({len(on_time)}):** These shipments met their deadline.
**Delayed deliveries ({len(delayed)}):** These shipments missed their deadline.

**Delay metrics:**
- Average delay (delayed shipments): {metrics.get('avg_delay_hours', 0)} hours
- Hubs most often in delayed shipments: {metrics.get('top_delayed_hubs', [])}
- Most common risk categories in delayed shipments: {metrics.get('common_risk_categories', [])}

**On-time shipment summary (first 10):**
{json.dumps(on_time[:10], indent=2, default=str)}

**Delayed shipment summary (first 10):**
{json.dumps(delayed[:10], indent=2, default=str)}

Return ONLY valid JSON with no markdown or extra text:
{{
  "summary": "Max 100 words. Brief overview of supply chain findings and key issues.",
  "control_parameters": [
    "Hub Chicago: Increase capacity",
    "Hub Dallas: Reduce dwell time",
    "Priority shipments: Use faster mode",
    "Route LA-Chicago: Add risk-based ETA buffer"
  ],
  "top_parameters": [
    {{"label": "Short label 1", "detail": "Implementation steps."}},
    {{"label": "Short label 2", "detail": "Implementation steps."}},
    {{"label": "Short label 3", "detail": "Implementation steps."}}
  ]
}}

CRITICAL RULES - Use ONLY these 5 parameter types (no others):
1. Hub capacity: Use phrasings like "Hub X: Increase capacity" or "Hub X: Expand capacity" (name the hub from the data).
2. Dispatch time at hub: "Hub X: Reduce dwell time" or "Hub X: Speed up processing".
3. Transit mode: "Route X: Switch to faster transit" or "Priority shipments: Use faster mode".
4. Earlier dispatch: "Shipments via Hub X: Dispatch earlier" or "Route X: Add buffer time".
5. Risk-based buffer: "Route X: Add risk-based ETA buffer" or "Hub X route: Add predicted-risk buffer".

EXCLUDE (do NOT suggest): alternate routing, material type changes, supplier changes, or any action we cannot simulate with these 5 levers.

Rules:
- control_parameters: Exactly 3-4 items. Format as above. Name the specific hub or route from the data (e.g., use hubs from top_delayed_hubs). Never use vague targets.
- top_parameters: Exactly 2-3 objects. "label" = short button name matching one of the 5 types. "detail" = 1-2 sentences.
- Summary must be at most 100 words."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    data = json.loads(text)
    summary = data.get("summary", "")
    if len(summary.split()) > 100:
        summary = _truncate_summary(summary, 100)
    control_parameters = data.get("control_parameters", [])
    if not isinstance(control_parameters, list):
        control_parameters = []
    control_parameters = control_parameters[:4]  # Max 4 changes
    top_params_raw = data.get("top_parameters", [])
    top_parameters = []
    for tp in top_params_raw[:3]:
        if isinstance(tp, dict):
            top_parameters.append({
                "label": tp.get("label", str(tp)),
                "detail": tp.get("detail", ""),
            })
        elif isinstance(tp, str):
            top_parameters.append({"label": tp, "detail": tp})
    return {
        "summary": summary,
        "control_parameters": control_parameters,
        "top_parameters": top_parameters,
    }


def run_optimization_insights(
    date_range: str, start_date=None, end_date=None, include_raw_data: bool = False
) -> dict:
    """
    Run the optimization insights pipeline.
    Returns: {
        "summary": str,           # 100 words max
        "control_parameters": list[str],
        "top_parameters": list[dict],  # [{"label": str, "detail": str}, ...]
        "on_time_count": int,
        "delayed_count": int,
        "summary_text": str,      # "Analyzed X on-time and Y delayed..."
        "error": str | None
        [, "on_time_raw": list, "delayed_raw": list]  # when include_raw_data=True
    }
    """
    result = {
        "summary": "",
        "control_parameters": [],
        "top_parameters": [],
        "on_time_count": 0,
        "delayed_count": 0,
        "summary_text": "",
        "error": None,
    }
    try:
        start_ts, end_ts = _parse_date_range(date_range, start_date, end_date)
        start_str = start_ts.strftime("%b %d, %Y")
        end_str = end_ts.strftime("%b %d, %Y")

        shipments = _fetch_delivered_shipments_by_date(start_ts, end_ts)
        if not shipments:
            result["summary_text"] = f"No delivered shipments in this period ({start_str}–{end_str}). Try a different date range."
            result["hub_map_data"] = _build_hub_map_data([], [])
            return result

        shipment_ids = [s["shipment_id"] for s in shipments]
        stops_by_shipment = _fetch_stops_with_hubs_risks(shipment_ids)

        on_time, delayed, metrics = _split_and_metrics(shipments, stops_by_shipment)

        result["on_time_count"] = len(on_time)
        result["delayed_count"] = len(delayed)
        result["summary_text"] = f"Analyzed <strong>{len(on_time)} on-time</strong> and <strong>{len(delayed)} delayed</strong> deliveries ({start_str}–{end_str})."
        result["hub_map_data"] = _build_hub_map_data(on_time, delayed)
        if include_raw_data:
            result["on_time_raw"] = on_time
            result["delayed_raw"] = delayed

        client = _get_openai_client()
        ai_result = _call_openai_recommendations(
            client, on_time, delayed, metrics, start_str, end_str
        )
        result["summary"] = ai_result.get("summary", "")
        result["control_parameters"] = ai_result.get("control_parameters", [])
        result["top_parameters"] = ai_result.get("top_parameters", [])
        return result
    except json.JSONDecodeError as e:
        result["error"] = f"Failed to parse AI response: {e}"
        return result
    except ValueError as e:
        result["error"] = str(e)
        return result
    except Exception as e:
        result["error"] = str(e)
        return result


def run_optimization_insights_with_data(
    date_range: str, start_date=None, end_date=None
) -> dict:
    """
    Same as run_optimization_insights but includes raw enriched payloads for simulation.
    Returns: { ...result, "on_time_raw": [...], "delayed_raw": [...] }
    """
    return run_optimization_insights(
        date_range, start_date, end_date, include_raw_data=True
    )
