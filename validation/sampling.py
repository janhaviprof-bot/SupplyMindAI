"""
Deterministic sample selection for the validation experiments.

The demo SupplyMind dataset is small (5 shipments, narrow time window), so
"sample size" is interpreted as N_total generations per prompt rather than
N_unique inputs. When the unique input pool is smaller than the target, each
input is replicated across multiple `run_id`s and the generator uses
temperature > 0 so each run produces an independent draw.

Returned tuples are stable across runs (seed=42) so the entire experiment is
reproducible.
"""
from __future__ import annotations

import math
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_PROJECT_ROOT / "SupplyMindAI") not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT / "SupplyMindAI"))

from supplymind_db.supabase_client import execute_query  # noqa: E402

DEFAULT_TARGET = 20
DEFAULT_SEED = 42


# ---------------------------------------------------------------------------
# Shipment sampling
# ---------------------------------------------------------------------------

def fetch_all_shipments_for_validation() -> list[dict]:
    """
    Return every shipment row joined with total_stops. We include both
    'In Transit' and 'Delivered' to maximize variety on a small demo DB.
    """
    rows = execute_query(
        """
        SELECT shipment_id, material_type, priority_level, total_stops,
               current_stop_index, final_deadline, status
        FROM shipments
        ORDER BY shipment_id
        """
    )
    return [dict(r) for r in rows]


def pick_shipment_samples(
    target: int = DEFAULT_TARGET,
    seed: int = DEFAULT_SEED,
) -> list[dict]:
    """
    Return `target` (sample) entries shaped as:
        {"sample_id": str, "shipment_id": str, "run_id": int}

    sample_id is `<shipment_id>__r<run_id>` and is unique across the returned
    list. Each unique shipment is replicated across runs as needed to reach
    `target` total entries.
    """
    shipments = fetch_all_shipments_for_validation()
    if not shipments:
        raise RuntimeError(
            "No shipments found in DB. Run the seed (db/full_database.sql) first."
        )

    rng = random.Random(seed)
    ordered = sorted(shipments, key=lambda s: s["shipment_id"])
    n_unique = len(ordered)
    runs_per_shipment = max(1, math.ceil(target / n_unique))

    out: list[dict] = []
    run_counters = {s["shipment_id"]: 0 for s in ordered}
    while len(out) < target:
        rng.shuffle(ordered)
        for s in ordered:
            sid = s["shipment_id"]
            if run_counters[sid] >= runs_per_shipment:
                continue
            run_id = run_counters[sid]
            run_counters[sid] += 1
            out.append({
                "sample_id": f"{sid}__r{run_id}",
                "shipment_id": sid,
                "run_id": run_id,
            })
            if len(out) >= target:
                break
    return out[:target]


# ---------------------------------------------------------------------------
# Optimization sampling (date ranges)
# ---------------------------------------------------------------------------

def _fetch_delivery_window() -> tuple[datetime, datetime] | None:
    """
    Return (min, max) delivery_ts across all Delivered shipments,
    or None if there are no delivered rows.
    """
    rows = execute_query(
        """
        SELECT
            MIN(t.delivery_ts) AS min_ts,
            MAX(t.delivery_ts) AS max_ts
        FROM (
            SELECT (
                SELECT MAX(COALESCE(st.actual_arrival, st.actual_departure))
                FROM stops st
                WHERE st.shipment_id = s.shipment_id
            ) AS delivery_ts
            FROM shipments s
            WHERE s.status = 'Delivered'
        ) t
        WHERE t.delivery_ts IS NOT NULL
        """
    )
    if not rows:
        return None
    r = rows[0]
    if r.get("min_ts") is None or r.get("max_ts") is None:
        return None
    return r["min_ts"], r["max_ts"]


def pick_optimization_samples(
    target: int = DEFAULT_TARGET,
    seed: int = DEFAULT_SEED,
) -> list[dict]:
    """
    Return `target` entries shaped as:
        {"sample_id": str, "range_id": str, "run_id": int,
         "start_date": date, "end_date": date}

    Strategy: build 4-5 candidate date ranges that all contain at least one
    delivered shipment, then replicate across runs to reach `target`.
    """
    window = _fetch_delivery_window()
    if window is None:
        raise RuntimeError(
            "No delivered shipments found. The optimization experiment needs "
            "at least one delivered shipment in the DB."
        )
    min_ts, max_ts = window
    today = max(max_ts.date(), date.today())

    # Build candidate ranges that are likely to overlap with the delivery window.
    span_days = max(1, (max_ts - min_ts).days)
    candidates: list[dict] = [
        {
            "range_id": "all_window",
            "start_date": min_ts.date() - timedelta(days=2),
            "end_date": max_ts.date() + timedelta(days=2),
        },
        {
            "range_id": "year",
            "start_date": today - timedelta(days=365),
            "end_date": today,
        },
        {
            "range_id": "month",
            "start_date": today - timedelta(days=30),
            "end_date": today,
        },
        {
            "range_id": "tight",
            "start_date": min_ts.date(),
            "end_date": max_ts.date(),
        },
        {
            "range_id": "wide_around_window",
            "start_date": min_ts.date() - timedelta(days=max(7, span_days)),
            "end_date": max_ts.date() + timedelta(days=max(7, span_days)),
        },
    ]

    rng = random.Random(seed)
    n_unique = len(candidates)
    runs_per_range = max(1, math.ceil(target / n_unique))

    out: list[dict] = []
    run_counters = {c["range_id"]: 0 for c in candidates}
    while len(out) < target:
        rng.shuffle(candidates)
        for c in candidates:
            rid = c["range_id"]
            if run_counters[rid] >= runs_per_range:
                continue
            run_id = run_counters[rid]
            run_counters[rid] += 1
            out.append({
                "sample_id": f"{rid}__r{run_id}",
                "range_id": rid,
                "run_id": run_id,
                "start_date": c["start_date"],
                "end_date": c["end_date"],
            })
            if len(out) >= target:
                break
    return out[:target]


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    print("=== Shipment samples ===")
    print(json.dumps(pick_shipment_samples(target=8), indent=2, default=str))
    print()
    print("=== Optimization samples ===")
    print(json.dumps(pick_optimization_samples(target=8), indent=2, default=str))
