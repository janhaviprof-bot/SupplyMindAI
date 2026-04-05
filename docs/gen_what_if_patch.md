~~~~python
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "SupplyMindAI"
P = ROOT / "advisor" / "what_if.py"


def main():
    t = P.read_text(encoding="utf-8")
    if "get_dispatch" in t:
        print("what_if already patched")
        return

    t = t.replace(
        "from advisor.rag import retrieve\n",
        "from advisor.rag import retrieve\n"
        "from advisor.tool_defs import OPENAI_TOOL_FUNCTIONS\n"
        "from advisor.tool_dispatch import get_dispatch\n",
    )

    old_op = """def _run_operational_snapshot(
    client,
    user_question: str,
    rag_chunks: list[str],
    trace: list[dict[str, str]],
    result: dict[str, Any],
) -> dict[str, Any]:
    in_transit = tool_get_in_transit_aggregate()
    known_hubs = tool_list_hub_names()"""

    new_op = """def _run_operational_snapshot(
    client,
    user_question: str,
    rag_chunks: list[str],
    trace: list[dict[str, str]],
    result: dict[str, Any],
) -> dict[str, Any]:
    d = get_dispatch()
    in_transit = d.call("get_in_transit_aggregate")
    known_hubs = d.call("list_hub_names")"""

    t = t.replace(old_op, new_op)

    old_da = """def _run_delivered_analytics(
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
    end_str = cohort.get("end_str", "")"""

    new_da = """def _run_delivered_analytics(
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
    end_str = cohort.get("end_str", "")"""

    # delivered still needs cohort object for empty flag in prompts — keep local cohort fetch
    t = t.replace(old_da, new_da)

    old_fs = """def _run_full_stress(
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
    end_str = cohort.get("end_str", "")"""

    new_fs = """def _run_full_stress(
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
    cohort_empty = bool(cohort_sum.get("empty"))"""

    t = t.replace(old_fs, new_fs)

    t = t.replace(
        "Delivered cohort: empty={cohort.get('empty')}, on_time={len(on_time_raw)}, delayed={len(delayed_raw)}, range {start_str}–{end_str}.\nDelay metrics: {json.dumps(metrics, default=str)}",
        "Delivered cohort: empty={cohort_empty}, on_time={on_time_n}, delayed={delayed_n}, range {start_str}–{end_str}.\nDelay metrics: {json.dumps(metrics, default=str)}",
    )

    old_stress = """    stress = tool_run_hub_capacity_stress(on_time_raw, delayed_raw, hub or "", mult)
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
    )"""

    new_stress = """    pipe = d.call(
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
    )"""

    t = t.replace(old_stress, new_stress)

    t = t.replace(
        "- Delivered cohort: {len(on_time_raw)} on-time, {len(delayed_raw)} delayed (empty cohort: {cohort.get('empty')})",
        "- Delivered cohort: {on_time_n} on-time, {delayed_n} delayed (empty cohort: {cohort_empty})",
    )

    insert_after_plan = '''
def _planner_mode() -> str:
    return (os.environ.get("ADVISOR_PLANNER_MODE") or "json").strip().lower()


def _plan_pipeline_openai_tools(
    client,
    user_question: str,
    rag_chunks: list[str],
    date_range: str,
    trace: list[dict[str, str]],
    dispatch,
) -> tuple[str, str]:
    sys_m = """You are the orchestration planner. Optionally call tools to inspect live logistics data.
You MUST finish by calling submit_planner_decision exactly once with:
- pipeline: full_stress | operational_snapshot | delivered_analytics
- reason: short sentence

full_stress = what-if / capacity / simulation. operational_snapshot = current in-transit picture only.
delivered_analytics = historical on-time/delayed for the baseline period, no simulation."""
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": sys_m},
        {
            "role": "user",
            "content": (
                f"User question: {user_question}\\n\\n"
                f"RAG excerpts:\\n{chr(10).join(rag_chunks[:5])}\\n\\n"
                f"Use date_range={date_range!r} when calling get_delivered_cohort_summary if needed."
            ),
        },
    ]
    tools = OPENAI_TOOL_FUNCTIONS
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
                "content": msg.content or None,
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
                if p in ("full_stress", "operational_snapshot", "delivered_analytics"):
                    return p, r
    return _plan_pipeline(client, user_question, rag_chunks)


'''

    t = t.replace(
        '    return "full_stress", reason or "default"\n\n\ndef _pick_hub',
        '    return "full_stress", reason or "default"\n\n' + insert_after_plan + "\ndef _pick_hub",
    )

    old_rw = """    rag_chunks = retrieve(user_question, k=6)
    pipeline, reason = _plan_pipeline(client, user_question, rag_chunks)
    if _force_full_stress_heuristic(user_question):
        pipeline = "full_stress"
        reason = "heuristic_override_stress_keywords"

    trace.append({"agent": "Planner", "summary": f"pipeline={pipeline}; {reason}"[:500]})"""

    new_rw = """    rag_chunks = retrieve(user_question, k=6)
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

    trace.append(
        {
            "agent": "Planner",
            "summary": f"mode={_planner_mode()}; tools={dispatch.mode}; pipeline={pipeline}; {reason}"[:500],
        }
    )"""

    t = t.replace(old_rw, new_rw)

    P.write_text(t, encoding="utf-8")
    print("patched what_if")


if __name__ == "__main__":
    main()
~~~~
