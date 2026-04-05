"""
Shipment analysis pipeline.
Fetches in-transit shipments, enriches with stops/hubs/risks,
flags via OpenAI (On Time / Delayed / Critical), and writes to insights.
"""
from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

from db.supabase_client import execute_query, get_connection


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


def _fetch_in_transit_shipments() -> list[dict]:
    """Step 1: Fetch shipments with status 'In Transit'."""
    rows = execute_query(
        """
        SELECT shipment_id, material_type, priority_level, total_stops,
               current_stop_index, final_deadline, status
        FROM shipments
        WHERE status = 'In Transit'
        ORDER BY shipment_id
        """
    )
    return [dict(r) for r in rows]


def _fetch_stops_and_enrich(shipment_ids: list[str]) -> dict[str, list]:
    """Step 2: Get stops (arrival/departure) for each shipment."""
    if not shipment_ids:
        return {}
    placeholders = ",".join(["%s"] * len(shipment_ids))
    rows = execute_query(
        f"""
        SELECT s.shipment_id, s.stop_number, s.hub_name,
               s.planned_arrival, s.actual_arrival,
               s.planned_departure, s.actual_departure
        FROM stops s
        WHERE s.shipment_id IN ({placeholders})
        ORDER BY s.shipment_id, s.stop_number
        """,
        tuple(shipment_ids),
    )
    by_shipment = {}
    for r in rows:
        sid = r["shipment_id"]
        if sid not in by_shipment:
            by_shipment[sid] = []
        by_shipment[sid].append(dict(r))
    return by_shipment


def _fetch_future_hubs_and_risks(shipment_ids: list[str], current_stop_index_by_shipment: dict) -> dict:
    """
    Step 3: For each shipment, get future stops (stop_number > current_stop_index),
    then hubs (occupancy) and risks for those hub_names.
    Returns: { shipment_id: { "future_hubs": [...], "future_risks": [...] } }
    """
    if not shipment_ids:
        return {}
    placeholders = ",".join(["%s"] * len(shipment_ids))
    rows = execute_query(
        f"""
        SELECT st.shipment_id, st.stop_number, st.hub_name,
               st.planned_arrival, st.planned_departure
        FROM stops st
        WHERE st.shipment_id IN ({placeholders})
        ORDER BY st.shipment_id, st.stop_number
        """,
        tuple(shipment_ids),
    )
    # Filter to future stops only
    future_hub_names_by_shipment = {}
    for r in rows:
        sid = r["shipment_id"]
        current_idx = current_stop_index_by_shipment.get(sid, 0)
        if r["stop_number"] > current_idx:
            if sid not in future_hub_names_by_shipment:
                future_hub_names_by_shipment[sid] = []
            future_hub_names_by_shipment[sid].append({
                "stop_number": r["stop_number"],
                "hub_name": r["hub_name"],
                "planned_arrival": r["planned_arrival"].isoformat() if r["planned_arrival"] else None,
                "planned_departure": r["planned_departure"].isoformat() if r["planned_departure"] else None,
            })

    # Fetch hubs for those hub_names
    all_hub_names = set()
    for hubs in future_hub_names_by_shipment.values():
        for h in hubs:
            all_hub_names.add(h["hub_name"])
    hub_data = {}
    if all_hub_names:
        hub_placeholders = ",".join(["%s"] * len(all_hub_names))
        hub_rows = execute_query(
            f"""
            SELECT hub_name, current_load, max_capacity, status
            FROM hubs
            WHERE hub_name IN ({hub_placeholders})
            """,
            tuple(all_hub_names),
        )
        hub_data = {r["hub_name"]: dict(r) for r in hub_rows}

    # Fetch risks for those hub_names
    risk_rows = []
    if all_hub_names:
        risk_placeholders = ",".join(["%s"] * len(all_hub_names))
        risk_rows = execute_query(
            f"""
            SELECT hub_name, category, severity, est_delay_hrs
            FROM risks
            WHERE hub_name IN ({risk_placeholders})
            """,
            tuple(all_hub_names),
        )

    # Build enriched future data per shipment
    risks_by_hub = {}
    for r in risk_rows:
        hn = r["hub_name"]
        if hn not in risks_by_hub:
            risks_by_hub[hn] = []
        risks_by_hub[hn].append(dict(r))

    result = {}
    for sid, future_stops in future_hub_names_by_shipment.items():
        future_hubs = []
        future_risks = []
        for stop in future_stops:
            hn = stop["hub_name"]
            hub_info = hub_data.get(hn, {})
            future_hubs.append({
                **stop,
                "current_load": hub_info.get("current_load"),
                "max_capacity": hub_info.get("max_capacity"),
                "status": hub_info.get("status"),
            })
            for risk in risks_by_hub.get(hn, []):
                future_risks.append({
                    "hub_name": hn,
                    "category": risk.get("category"),
                    "severity": risk.get("severity"),
                    "est_delay_hrs": risk.get("est_delay_hrs"),
                })
        result[sid] = {"future_hubs": future_hubs, "future_risks": future_risks}
    return result


def _confidence_score(conf_raw, payload: dict, flag: str) -> int:
    """
    AI confidence 1-10: use model output if valid, else heuristic from data clarity.
    High = clear signals (all on time + no risks, or clear delays + high risks).
    Low = mixed/ambiguous data.
    """
    try:
        c = int(conf_raw)
        if 1 <= c <= 10:
            return c
    except (TypeError, ValueError):
        pass
    # Heuristic from payload
    stops = payload.get("stops", [])
    future_hubs = payload.get("future_hubs", [])
    future_risks = payload.get("future_risks", [])
    current_idx = payload.get("current_stop_index") or 0
    score = 5
    past_on_time = True
    for s in stops:
        if (s.get("stop_number") or 0) <= current_idx:
            if s.get("actual_arrival") and s.get("planned_arrival"):
                try:
                    a = datetime.fromisoformat(str(s["actual_arrival"]).replace("Z", "+00:00"))
                    p = datetime.fromisoformat(str(s["planned_arrival"]).replace("Z", "+00:00"))
                    if a > p:
                        past_on_time = False
                        break
                except Exception:
                    past_on_time = False
    all_open = all((h.get("status") or "").lower() == "open" for h in future_hubs)
    max_sev = max((r.get("severity") or 0) for r in future_risks) if future_risks else 0
    if flag == "On Time":
        if past_on_time and all_open and max_sev <= 4:
            score = 8
        elif not past_on_time or max_sev >= 7:
            score = 4
    else:
        if not past_on_time or max_sev >= 7:
            score = 8
        elif all_open and max_sev <= 3:
            score = 4
    return max(1, min(10, score))


def _build_shipment_payload(shipment: dict, stops: list, future_data: dict) -> dict:
    """Build a JSON-serializable payload for OpenAI."""
    stops_ser = []
    for s in stops:
        stops_ser.append({
            "stop_number": s["stop_number"],
            "hub_name": s["hub_name"],
            "planned_arrival": s["planned_arrival"].isoformat() if s.get("planned_arrival") else None,
            "actual_arrival": s["actual_arrival"].isoformat() if s.get("actual_arrival") else None,
            "planned_departure": s["planned_departure"].isoformat() if s.get("planned_departure") else None,
            "actual_departure": s["actual_departure"].isoformat() if s.get("actual_departure") else None,
        })
    return {
        "shipment_id": shipment["shipment_id"],
        "priority_level": shipment["priority_level"],
        "final_deadline": shipment["final_deadline"].isoformat() if shipment.get("final_deadline") else None,
        "current_stop_index": shipment["current_stop_index"],
        "stops": stops_ser,
        "future_hubs": future_data.get("future_hubs", []),
        "future_risks": future_data.get("future_risks", []),
    }


def _call_openai(client, payload: dict) -> dict:
    """Single OpenAI call: flag, predicted_arrival, and reasoning."""
    prompt = """You are a logistics analyst. Given the shipment data below, determine:
- flag: "On Time" | "Delayed" | "Critical" (Critical = high-priority parcel that will be delayed)
- predicted_arrival: ISO8601 timestamp. REQUIRED for Delayed and Critical. For Delayed/Critical: predicted_arrival MUST be AFTER final_deadline (delays push arrival later than target). Use est_delay_hrs from risks and past delays to estimate. Use null only for On Time.
- reasoning: Use this EXACT format for Delayed/Critical. 1–2 sentences. Risk words lowercase: congestion, traffic, bad weather, labor. No severity or priority numbers. Use commas for 3+ items: "traffic, labor, and bad weather".
  Format: "Delays at [hub(s)] due to [risks]." Optional: "Additional delays at [hub] from [risks]."
  Do NOT add "The predicted arrival is after the final deadline" or similar—that is obvious. Be SPECIFIC to this shipment: use the exact hub names and risk types from the payload (future_hubs, future_risks). Different shipments must have different reasoning.
  Examples:
  - "Delays at Detroit-Midwest due to congestion and bad weather."
  - "Delays at Chicago-Main and Detroit-Midwest due to traffic, labor, and bad weather."

Classification rules:
- On Time: Use when (a) all past stops show actual_arrival/actual_departure on or before planned times, AND (b) future hubs are Open (not Congested/Closed), AND (c) future hubs have no high-severity risks (severity <= 4) or no risks at all. Do not flag Delayed/Critical just because some low-severity risks exist; weigh past performance and hub status.
- CRITICAL: For Delayed or Critical, predicted_arrival must be LATER than final_deadline—delays mean the shipment arrives after the target. Use est_delay_hrs from risks to add delay.
- Delayed: Use when there are clear delays (past stops late) or future hubs Congested/Closed or high-severity risks (severity >= 7) that will likely cause delay.
- Critical: ONLY when priority_level >= 8 in the shipment data. If priority_level < 8, you MUST use Delayed, never Critical.

Also include: confidence (1-10, how confident you are in this classification based on data clarity).
Respond with ONLY this JSON, no markdown:
{"flag": "On Time"|"Delayed"|"Critical", "predicted_arrival": "ISO8601 or null (required for Delayed/Critical)", "reasoning": "1-2 detailed sentences", "confidence": 1-10}

Shipment data:
"""
    prompt += json.dumps(payload, indent=2, default=str)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(text)


def get_all_insights() -> list[dict]:
    """Fetch all insights with shipment final_deadline for display."""
    rows = execute_query(
        """
        SELECT i.insight_id, i.shipment_id, i.flag_status, i.predicted_arrival, i.reasoning,
               i.confidence, s.final_deadline
        FROM insights i
        LEFT JOIN shipments s ON s.shipment_id = i.shipment_id
        ORDER BY i.shipment_id
        """
    )
    return [dict(r) for r in rows]


def get_in_transit_dashboard_summary() -> dict:
    """
    Counts for the main dashboard card: every shipment with status 'In Transit',
    joined to its latest insight row (if any). Shipments without a usable flag
    count as pending (no AI prediction in DB yet).
    """
    rows = execute_query(
        """
        SELECT s.shipment_id,
               x.flag_status, x.predicted_arrival, x.reasoning, x.confidence, x.insight_id
        FROM shipments s
        LEFT JOIN LATERAL (
            SELECT insight_id, shipment_id, flag_status, predicted_arrival, reasoning, confidence
            FROM insights
            WHERE shipment_id = s.shipment_id
            ORDER BY insight_id DESC
            LIMIT 1
        ) x ON true
        WHERE s.status = 'In Transit'
        ORDER BY s.shipment_id
        """
    )
    on_time = delayed = critical = pending = 0
    insights_written: list[dict] = []
    for r in rows:
        fl = (r.get("flag_status") or "").strip().lower()
        if fl == "on time":
            on_time += 1
        elif fl == "delayed":
            delayed += 1
        elif fl == "critical":
            critical += 1
        else:
            pending += 1
        if r.get("insight_id"):
            insights_written.append(
                {
                    "shipment_id": r["shipment_id"],
                    "flag_status": r.get("flag_status"),
                    "predicted_arrival": r.get("predicted_arrival"),
                    "reasoning": r.get("reasoning"),
                    "confidence": r.get("confidence"),
                }
            )
    return {
        "on_time": on_time,
        "delayed": delayed,
        "critical": critical,
        "pending": pending,
        "in_transit_total": len(rows),
        "insights_written": insights_written,
    }


def get_hub_map_data_from_insights() -> dict:
    """
    Build hub map data from Feature 1 (in-transit predictions).
    Returns {all_hubs: [...], status_hubs: [...]} for map display.
    Status: red=Critical, orange=Delayed, green=On Time (worst flag among shipments using that hub).
    """
    in_transit_rows = execute_query(
        "SELECT shipment_id FROM shipments WHERE status = 'In Transit'"
    )
    in_transit_ids = {r["shipment_id"] for r in in_transit_rows}
    insights = [r for r in get_all_insights() if r.get("shipment_id") in in_transit_ids]
    if not insights:
        all_rows = execute_query("SELECT hub_name, lat, lon FROM hubs")
        all_hubs = [
            {"hub_name": r["hub_name"], "lat": float(r["lat"]), "lon": float(r["lon"])}
            for r in all_rows
            if r.get("lat") is not None and r.get("lon") is not None
        ]
        return {"all_hubs": all_hubs, "status_hubs": []}
    sid_to_flag = {r["shipment_id"]: (r.get("flag_status") or "").strip().lower() for r in insights if r.get("shipment_id")}
    shipment_ids = list(sid_to_flag.keys())
    stops_by_shipment = _fetch_stops_and_enrich(shipment_ids)
    hub_to_shipment_flags = {}  # hub_name -> set of (sid, flag) to count shipments per hub
    for sid, stops in stops_by_shipment.items():
        flag = sid_to_flag.get(sid, "on time")
        for s in stops:
            hn = s.get("hub_name")
            if hn:
                hub_to_shipment_flags.setdefault(hn, set()).add((sid, flag))
    all_rows = execute_query("SELECT hub_name, lat, lon FROM hubs")
    coords = {r["hub_name"]: (float(r["lat"]), float(r["lon"])) for r in all_rows if r.get("lat") is not None and r.get("lon") is not None}
    all_hubs = [{"hub_name": h, "lat": coords[h][0], "lon": coords[h][1]} for h in coords]
    status_order = {"critical": 3, "delayed": 2, "on time": 1}
    status_hubs = []
    for hn, shipment_flags in hub_to_shipment_flags.items():
        if hn not in coords:
            continue
        flags = {f for _, f in shipment_flags}
        worst = max(flags, key=lambda f: status_order.get(f, 0))
        status = "red" if worst == "critical" else ("orange" if worst == "delayed" else "green")
        critical_count = sum(1 for _, f in shipment_flags if f == "critical")
        delayed_count = sum(1 for _, f in shipment_flags if f == "delayed")
        on_time_count = sum(1 for _, f in shipment_flags if f == "on time")
        total_flagged = critical_count + delayed_count
        status_hubs.append({
            "hub_name": hn,
            "lat": coords[hn][0],
            "lon": coords[hn][1],
            "status": status,
            "critical_count": critical_count,
            "delayed_count": delayed_count,
            "on_time_count": on_time_count,
            "in_delayed_count": total_flagged,
            "risk_categories": [],
        })
    return {"all_hubs": all_hubs, "status_hubs": status_hubs}


def _upsert_insight(
    shipment_id: str,
    flag_status: str,
    predicted_arrival,
    reasoning: str | None = None,
    confidence: int | None = None,
):
    """UPSERT a row into insights."""
    insight_id = f"insight_{shipment_id}"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO insights (insight_id, shipment_id, flag_status, predicted_arrival, reasoning, confidence)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (insight_id) DO UPDATE SET
                    flag_status = EXCLUDED.flag_status,
                    predicted_arrival = EXCLUDED.predicted_arrival,
                    reasoning = COALESCE(EXCLUDED.reasoning, insights.reasoning),
                    confidence = COALESCE(EXCLUDED.confidence, insights.confidence)
                """,
                (insight_id, shipment_id, flag_status, predicted_arrival, reasoning, confidence),
            )
            conn.commit()


def run_analysis() -> dict:
    """
    Run the full analysis pipeline.
    Returns: {
        "on_time": int, "delayed": int, "critical": int,
        "insights_written": list[dict],  # rows added/updated this run
        "error": str | None
    }
    """
    counts = {"on_time": 0, "delayed": 0, "critical": 0}
    insights_written = []
    try:
        # Step 1
        shipments = _fetch_in_transit_shipments()
        if not shipments:
            return {**counts, "insights_written": [], "error": None}

        # Optional: limit for faster demos (set MAX_SHIPMENTS=8 in .env)
        _load_env()
        max_ship = os.environ.get("MAX_SHIPMENTS")
        if max_ship:
            try:
                n = int(max_ship)
                if n > 0:
                    shipments = shipments[:n]
            except ValueError:
                pass

        shipment_ids = [s["shipment_id"] for s in shipments]
        current_stop_index_by_shipment = {s["shipment_id"]: s["current_stop_index"] or 0 for s in shipments}

        # Step 2
        stops_by_shipment = _fetch_stops_and_enrich(shipment_ids)

        # Step 3
        future_data_by_shipment = _fetch_future_hubs_and_risks(shipment_ids, current_stop_index_by_shipment)

        client = _get_openai_client()

        def _process_one(shipment):
            sid = shipment["shipment_id"]
            stops = stops_by_shipment.get(sid, [])
            future_data = future_data_by_shipment.get(sid, {"future_hubs": [], "future_risks": []})
            payload = _build_shipment_payload(shipment, stops, future_data)
            result = _call_openai(client, payload)
            flag = result.get("flag", "On Time")
            if flag not in ("On Time", "Delayed", "Critical"):
                flag = "On Time"
            # Enforce: Critical only when priority_level >= 8
            pri = shipment.get("priority_level") or 0
            if flag == "Critical" and pri < 8:
                flag = "Delayed"
            pred_arr = result.get("predicted_arrival")
            pred_arr_str = None
            pred_arr_dt = None
            if pred_arr and isinstance(pred_arr, str):
                pred_arr_str = pred_arr
                try:
                    pred_arr_dt = datetime.fromisoformat(pred_arr.replace("Z", "+00:00"))
                except Exception:
                    pred_arr_dt = None
            # For Delayed/Critical: predicted_arrival must be after final_deadline (delays = later arrival)
            final_dl = shipment.get("final_deadline")
            if flag in ("Delayed", "Critical") and pred_arr_dt and final_dl:
                try:
                    fd = final_dl if isinstance(final_dl, datetime) else datetime.fromisoformat(str(final_dl).replace("Z", "+00:00"))
                    if pred_arr_dt <= fd:
                        pred_arr_dt = fd + timedelta(hours=24)
                        pred_arr_str = pred_arr_dt.isoformat()
                except Exception:
                    pass
            reasoning = result.get("reasoning") or None
            conf_raw = result.get("confidence")
            conf = _confidence_score(conf_raw, payload, flag)
            _upsert_insight(sid, flag, pred_arr_dt, reasoning, confidence=conf)
            return {
                "shipment_id": sid,
                "flag_status": flag,
                "predicted_arrival": pred_arr_str or (pred_arr_dt.isoformat() if pred_arr_dt else None),
                "reasoning": reasoning or "-",
                "confidence": conf,
            }, flag

        # Run in parallel (15 workers)
        with ThreadPoolExecutor(max_workers=15) as ex:
            futures = {ex.submit(_process_one, s): s for s in shipments}
            for future in as_completed(futures):
                row, flag = future.result()
                insights_written.append(row)
                if flag == "On Time":
                    counts["on_time"] += 1
                elif flag == "Delayed":
                    counts["delayed"] += 1
                else:
                    counts["critical"] += 1

        # Sort by shipment_id for consistent display
        insights_written.sort(key=lambda x: x["shipment_id"])

        return {**counts, "insights_written": insights_written, "error": None}
    except Exception as e:
        return {**counts, "insights_written": insights_written, "error": str(e)}
