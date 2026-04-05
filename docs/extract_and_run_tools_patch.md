~~~~python
from pathlib import Path

# Run from outer repo root: .../SupplyMindAI/SupplyMindAI/
INNER = Path(__file__).resolve().parent / "SupplyMindAI"
p = INNER / "advisor" / "tools_impl.py"
t = p.read_text(encoding="utf-8")
if "tool_get_delivered_cohort_summary" in t:
    print("skip")
else:
    add = """

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
    }
"""
    p.write_text(t.rstrip() + add + "\n", encoding="utf-8")
    print("ok", p)
~~~~
