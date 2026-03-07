"""
Shipment analysis pipeline.
Fetches in-transit shipments, enriches with stops/hubs/risks,
flags via OpenAI (On Time / Delayed / Critical), and writes to insights.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
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


def _call_openai_for_flag(client, payload: dict) -> dict:
    """Step 4: Call OpenAI to get flag and predicted_arrival."""
    prompt = """You are a logistics analyst. Given the following shipment data, determine if it will be:
- "On Time": Parcel will arrive on time
- "Delayed": Parcel will be delayed
- "Critical": A high-priority parcel (priority_level >= 7) that will be delayed

Consider: actual vs planned arrival/departure at past stops, hub status (Open/Congested/Closed), hub occupancy, risks (Weather/Traffic/Labor) with severity and est_delay_hrs, and final_deadline.

Respond with ONLY a JSON object, no markdown:
{"flag": "On Time" | "Delayed" | "Critical", "predicted_arrival": "ISO8601 timestamp or null"}

Shipment data:
"""
    prompt += json.dumps(payload, indent=2, default=str)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    text = response.choices[0].message.content.strip()
    # Remove markdown code blocks if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(text)


def _call_openai_for_reasoning(client, payload: dict, flag: str) -> str:
    """Step 6: Call OpenAI to generate reasoning for Delayed/Critical."""
    prompt = f"""This shipment was flagged as "{flag}". In 1-2 short sentences, explain why (e.g., which hubs, risks, or delays caused it). Be concise.

Shipment data:
{json.dumps(payload, indent=2, default=str)}

Respond with ONLY the reasoning text, no JSON or quotes."""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def _upsert_insight(shipment_id: str, flag_status: str, predicted_arrival, reasoning: str | None = None):
    """UPSERT a row into insights."""
    insight_id = f"insight_{shipment_id}"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO insights (insight_id, shipment_id, flag_status, predicted_arrival, reasoning)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (insight_id) DO UPDATE SET
                    flag_status = EXCLUDED.flag_status,
                    predicted_arrival = EXCLUDED.predicted_arrival,
                    reasoning = COALESCE(EXCLUDED.reasoning, insights.reasoning)
                """,
                (insight_id, shipment_id, flag_status, predicted_arrival, reasoning),
            )
            conn.commit()


def run_analysis() -> dict:
    """
    Run the full analysis pipeline.
    Returns: { "on_time": int, "delayed": int, "critical": int, "error": str | None }
    """
    counts = {"on_time": 0, "delayed": 0, "critical": 0}
    try:
        # Step 1
        shipments = _fetch_in_transit_shipments()
        if not shipments:
            return {**counts, "error": None}

        shipment_ids = [s["shipment_id"] for s in shipments]
        current_stop_index_by_shipment = {s["shipment_id"]: s["current_stop_index"] or 0 for s in shipments}

        # Step 2
        stops_by_shipment = _fetch_stops_and_enrich(shipment_ids)

        # Step 3
        future_data_by_shipment = _fetch_future_hubs_and_risks(shipment_ids, current_stop_index_by_shipment)

        client = _get_openai_client()

        for shipment in shipments:
            sid = shipment["shipment_id"]
            stops = stops_by_shipment.get(sid, [])
            future_data = future_data_by_shipment.get(sid, {"future_hubs": [], "future_risks": []})
            payload = _build_shipment_payload(shipment, stops, future_data)

            # Step 4
            result = _call_openai_for_flag(client, payload)
            flag = result.get("flag", "On Time")
            if flag not in ("On Time", "Delayed", "Critical"):
                flag = "On Time"
            pred_arr = result.get("predicted_arrival")
            if pred_arr and isinstance(pred_arr, str):
                try:
                    pred_arr = datetime.fromisoformat(pred_arr.replace("Z", "+00:00"))
                except Exception:
                    pred_arr = None

            # Step 6: Reasoning for Delayed/Critical (before Step 5 so we upsert once)
            reasoning = None
            if flag in ("Delayed", "Critical"):
                reasoning = _call_openai_for_reasoning(client, payload, flag)

            # Step 5: Populate dataset with flag and reasoning
            _upsert_insight(sid, flag, pred_arr, reasoning)

            if flag == "On Time":
                counts["on_time"] += 1
            elif flag == "Delayed":
                counts["delayed"] += 1
            else:
                counts["critical"] += 1

        return {**counts, "error": None}
    except Exception as e:
        return {**counts, "error": str(e)}
