"""
Simulation engine for supply chain parameter levers.
Computes simulated delays under hypothetical lever values and finds sweet spots.
"""
from datetime import datetime
from typing import Any, Optional

ALPHA = 3.0  # Congestion delay coefficient (hours per 100% overflow)

# Cost model: (lever_value - value_min) -> USD investment
# Hub capacity k: k=1.0 = nominal max_capacity (no increase); k=1.2 = 20% above nominal; incremental $ = (k−1.0)×rate.
COST_PER_UNIT_USD = {
    "hub_capacity": 1_000_000,       # $1M per +1.0 on k (e.g. k 1.0→2.0 ⇒ $1M modeled)
    "dispatch_time_at_hub": 500_000,  # $500K per 100% dwell reduction
    "transit_mode": 1_600_000,        # $1.6M per 1.0 fraction of D_obs removed (grid 0–1.0)
    "earlier_dispatch": 2_000,        # $2K per hour earlier dispatch
    "risk_based_buffer": 200_000,     # $200K per 1.0 buffer factor
}

# Shared wording for UI, tools, and LLM prompts (single source of truth).
HUB_CAPACITY_K_EXPLAINER_OPTIMIZATION = (
    "For hub_capacity: k=1.0 means effective capacity equals nominal max_capacity in the DB (no increase). "
    "k=1.2 means effective capacity is 20% above nominal (C_sim = k × max_capacity). "
    "Modeled incremental investment USD = (k − value_min) × $1M "
    "(expansion grids often use value_min=1.0, so k=1.0 → $0 incremental in the model)."
)
HUB_CAPACITY_K_EXPLAINER_STRESS = (
    "Hub capacity uses multiplier k everywhere: C_sim = k × max_capacity (nominal from data). "
    "k=1.0 = no change vs nominal; k=0.8 = 20% below nominal (typical stress). "
    "Recovery sweet-spot search sweeps k on a range (default ~0.75–1.35) with the same formula."
)


def lever_value_to_usd(param_type: str, lever_value: float, value_min: float) -> float:
    """Convert lever value (above grid minimum) to approximate USD investment.

    For ``hub_capacity``, lever value is k; spend is (k − value_min) × $1M (see COST_PER_UNIT_USD).
    """
    cost = COST_PER_UNIT_USD.get(param_type, 10_000)
    delta = max(0.0, lever_value - value_min)
    return delta * cost


def _parse_iso(s: Optional[str]):
    """Parse ISO datetime string to datetime."""
    if not s:
        return None
    if hasattr(s, "isoformat"):  # already datetime
        return s
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _total_dwell_hours(payload: dict) -> float:
    """Sum dwell time (departure - arrival) over all stops, in hours."""
    total = 0.0
    for stop in payload.get("stops", []):
        arr = _parse_iso(stop.get("actual_arrival"))
        dep = _parse_iso(stop.get("actual_departure"))
        if arr and dep and dep > arr:
            total += (dep - arr).total_seconds() / 3600
    return total


def _total_risk_hrs(payload: dict) -> float:
    """Sum est_delay_hrs over all risks at all stops."""
    total = 0.0
    for stop in payload.get("stops", []):
        for r in stop.get("risks", []):
            h = r.get("est_delay_hrs")
            if h is not None:
                total += float(h)
    return total


def _congestion_contrib(L: float, C: float, alpha: float = ALPHA) -> float:
    """Congestion delay at a hub: max(0, (L-C)/C) * alpha."""
    if not C or C <= 0:
        return 0.0
    overflow = max(0, (L - C) / C)
    return overflow * alpha


def _hub_matches(stop: dict, target_hub: Optional[str]) -> bool:
    """True if stop is at target hub, or target_hub is None (apply to all)."""
    if not target_hub:
        return True
    return str(stop.get("hub_name", "")).strip().lower() == str(target_hub).strip().lower()


def _sim_delay_hub_capacity(payload: dict, value: float, target_hub: Optional[str]) -> float:
    """
    Simulate delay with hub capacity multiplier k applied to nominal max_capacity.
    k=1.0: no increase (effective capacity = recorded max_capacity).
    k=1.2: effective capacity 20% above that nominal (congestion uses C_use = k × max_capacity).
    Uses decomposition: D_sim = D_base + sum(D_cong_sim + D_risk).
    When target_hub is set, only that hub's capacity is scaled; others unchanged.
    """
    D_obs = payload.get("delay_hours", 0.0) or 0.0
    if D_obs <= 0:
        return 0.0

    # Current congestion and risk contributions (all stops)
    total_cong = 0.0
    total_risk = 0.0
    for stop in payload.get("stops", []):
        L = stop.get("current_load")
        C = stop.get("max_capacity")
        if L is not None and C is not None and C > 0:
            total_cong += _congestion_contrib(float(L), float(C))
        for r in stop.get("risks", []):
            h = r.get("est_delay_hrs")
            if h is not None:
                total_risk += float(h)

    base = max(0.0, D_obs - total_cong - total_risk)

    # Simulated congestion: apply multiplier only at target hub(s)
    cong_sim = 0.0
    for stop in payload.get("stops", []):
        L = stop.get("current_load")
        C = stop.get("max_capacity")
        if L is None or C is None or C <= 0:
            continue
        C_orig = float(C)
        if _hub_matches(stop, target_hub):
            C_use = value * C_orig
        else:
            C_use = C_orig
        cong_sim += _congestion_contrib(float(L), C_use)

    return base + cong_sim + total_risk


def _sim_delay_time_shift(payload: dict, reduction_hrs: float) -> float:
    """D_sim = max(0, D_obs - reduction_hrs)."""
    D_obs = payload.get("delay_hours", 0.0) or 0.0
    return max(0.0, D_obs - reduction_hrs)


def simulate_delays(
    on_time_raw: list[dict],
    delayed_raw: list[dict],
    param_type: str,
    target_hub: Optional[str],
    target_route: Optional[str],
    value: float,
) -> dict[str, Any]:
    """
    Run simulation for given lever value.
    For ``hub_capacity``, ``value`` is k: C_sim = k × max_capacity (k=1.0 baseline, k=1.2 = +20% vs nominal).
    Returns {on_time_count, delayed_count, avg_delay, details}.
    """
    delayed = delayed_raw  # Process all delayed; per-stop logic handles target_hub
    on_time_count = len(on_time_raw)  # On-time stay on-time
    sim_delays = []

    for p in delayed:
        D_obs = p.get("delay_hours", 0.0) or 0.0
        if param_type == "hub_capacity":
            D_sim = _sim_delay_hub_capacity(p, value, target_hub)
        elif param_type == "dispatch_time_at_hub":
            # value = dwell reduction fraction 0-1. Use max(recorded dwell, min(D_obs, cap)) so long-haul
            # delays still respond (raw dwell sums are often far below total delay_hours in the seed data).
            D_obs = float(p.get("delay_hours", 0.0) or 0.0)
            dwell = _total_dwell_hours(p)
            addressable = max(dwell, min(D_obs, 72.0))
            reduction = value * addressable
            D_sim = _sim_delay_time_shift(p, reduction)
        elif param_type == "transit_mode":
            # value = fraction of observed delay D_obs removed (0–1; v=1 can fully recover in this model)
            reduction = value * D_obs
            D_sim = _sim_delay_time_shift(p, reduction)
        elif param_type == "earlier_dispatch":
            # value = hours earlier
            D_sim = _sim_delay_time_shift(p, value)
        elif param_type == "risk_based_buffer":
            # value = buffer factor rho
            R = _total_risk_hrs(p)
            reduction = value * R
            D_sim = _sim_delay_time_shift(p, reduction)
        else:
            D_sim = D_obs

        sim_delays.append(D_sim)

    # Reclassification: D_sim <= 0 -> recovered (on-time)
    recovered = sum(1 for d in sim_delays if d <= 0)
    still_delayed = [d for d in sim_delays if d > 0]
    on_time_total = on_time_count + recovered
    delayed_total = len(delayed) - recovered
    avg_delay = sum(still_delayed) / len(still_delayed) if still_delayed else 0.0

    return {
        "on_time_count": on_time_total,
        "delayed_count": delayed_total,
        "avg_delay": round(avg_delay, 2),
        "recovered_count": recovered,
        "details": [round(d, 2) for d in sim_delays],
    }


def find_sweet_spot(
    on_time_raw: list[dict],
    delayed_raw: list[dict],
    param_type: str,
    target_hub: Optional[str],
    target_route: Optional[str],
    value_min: float,
    value_max: float,
    steps: int = 11,
    objective: str = "roi",
) -> dict[str, Any]:
    """
    Grid search for sweet spot.
    objective: "roi" = max recovered per unit investment (min investment, good results);
               "on_time" = max on-time count; "avg_delay" = min avg delay.
    Returns {sweet_spot_value, curve, best_metrics, chart_points_3: [(investment, on_time, label), ...]}.
    For hub_capacity, lever value is k: k=1.0 baseline nominal capacity; k=1.2 = 20% increase vs nominal.
    """
    if steps <= 1:
        values = [value_min]
    else:
        values = [
            value_min + (value_max - value_min) * i / (steps - 1)
            for i in range(steps)
        ]
    curve = []
    baseline_on_time = len(on_time_raw)
    baseline_delayed = len(delayed_raw)

    for v in values:
        r = simulate_delays(
            on_time_raw, delayed_raw, param_type, target_hub, target_route, v
        )
        curve.append((v, r["on_time_count"], r["delayed_count"], r["avg_delay"]))

    if objective == "roi":
        # ROI = recovered / investment. Investment = (v - vmin) + eps.
        # Favors smallest v that still recovers shipments.
        def _roi(i: int) -> float:
            v, on_time, delayed, _ = curve[i]
            recovered = on_time - baseline_on_time
            investment = max(v - value_min, 0.001)
            return recovered / investment if recovered > 0 else 0.0

        best_idx = max(range(len(curve)), key=_roi)
    elif objective == "on_time":
        best_idx = max(range(len(curve)), key=lambda i: curve[i][1])
    else:
        best_idx = min(range(len(curve)), key=lambda i: curve[i][3])

    best_v, best_on, best_del, best_avg = curve[best_idx]
    best_metrics = simulate_delays(
        on_time_raw, delayed_raw, param_type, target_hub, target_route, best_v
    )

    # Build chart_points_3: (investment_usd, on_time_count, label) for Min, Sweet spot, Max
    v_min, on_min, _, _ = curve[0]
    v_max, on_max, _, _ = curve[-1]
    inv_usd_min = lever_value_to_usd(param_type, v_min, value_min)
    inv_usd_sweet = lever_value_to_usd(param_type, best_v, value_min)
    inv_usd_max = lever_value_to_usd(param_type, v_max, value_min)
    chart_points_3 = [
        (round(inv_usd_min, 0), on_min, "Min"),
        (round(inv_usd_sweet, 0), best_on, "Sweet spot"),
        (round(inv_usd_max, 0), on_max, "Max"),
    ]

    # Curve with investment_usd for each point
    curve_with_usd = []
    for v, on_time, delayed, avg_delay in curve:
        inv_usd = lever_value_to_usd(param_type, v, value_min)
        curve_with_usd.append((round(v, 2), round(inv_usd, 0), on_time, delayed, round(avg_delay, 2)))

    return {
        "sweet_spot_value": round(best_v, 2),
        "curve": curve_with_usd,
        "best_metrics": best_metrics,
        "chart_points_3": chart_points_3,
    }
