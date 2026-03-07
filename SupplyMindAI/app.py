"""
SupplyMind Shiny app.
Dashboard: KPI cards, donut chart, critical shipments, escalation panel.
"""
import re
import sys
from datetime import datetime
from pathlib import Path

# Ensure project root (for db) and SupplyMindAI (for analysis) are on path
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "SupplyMindAI"))

import plotly.graph_objects as go
from shiny import App, Inputs, Outputs, Session, reactive, render, ui
from shinywidgets import output_widget, render_widget

from analysis.pipeline import run_analysis, get_all_insights


def _priority_word(match):
    try:
        n = int(match.group(1))
        if n >= 7:
            return "high"
        if n >= 4:
            return "medium"
        return "low"
    except (ValueError, IndexError):
        return "medium"


def _fmt_ts(val) -> str:
    """Format timestamp for display (raw)."""
    if val is None:
        return "—"
    if hasattr(val, "isoformat"):
        return val.isoformat()[:19].replace("T", " ")
    return str(val)[:19]


def _fmt_ts_friendly(val) -> str:
    """User-friendly timestamp, e.g. Mar 7, 2026 at 8:30 PM."""
    if val is None:
        return "—"
    try:
        if hasattr(val, "strftime"):
            dt = val
        else:
            s = str(val)[:19].replace("T", " ")
            dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%b %d, %Y at %I:%M %p")
    except (ValueError, TypeError):
        return _fmt_ts(val)


def _simplify_priority(text: str) -> str:
    return re.sub(
        r"priority_?\s*level_?\s*(\d+)",
        _priority_word,
        str(text or ""),
        flags=re.I,
    )


def _normalize_reason(t: str) -> str:
    """Strip severity/priority, normalize risk words to lowercase in middle of sentence."""
    t = str(t or "")
    t = re.sub(r"\(?\s*severity\s*\d+[\s\)]*", " ", t, flags=re.I)
    t = re.sub(r"\(?\s*priority_?\s*level_?\s*\d+[\s\)]*", " ", t, flags=re.I)
    t = re.sub(r"\bpriority_?\s*level_?\s*\d+\b", " ", t, flags=re.I)
    t = re.sub(r"high-severity|high severity|high-priority|high priority", " ", t, flags=re.I)
    t = re.sub(r"priority level is high[^.]*\.?", " ", t, flags=re.I)
    t = re.sub(r"indicating critical status\.?", " ", t, flags=re.I)
    t = re.sub(r"the predicted arrival is after the final deadline due to these delays\.?", " ", t, flags=re.I)
    t = re.sub(r"current load \d+/\d+", " ", t, flags=re.I)
    for s in ["The shipment is ", "The shipment has ", "Classified as Critical due to ",
              "Classified as Delayed due to ", "its high of 9.", "its high of 8."]:
        t = t.replace(s, " ")
    t = re.sub(r"\s+", " ", t).strip()
    for w in ["Congestion", "Traffic", "Labor", "Bad weather", "Bad Weather", "Weather"]:
        t = re.sub(rf"\b{re.escape(w)}\b", w.lower(), t, flags=re.I)
    return t


def _modal_reason(text: str) -> str:
    """Full reasoning for modal: preserve model format (up to 2 sentences), clean and fix capitalization."""
    t = _normalize_reason(text or "")
    if not t:
        return "—"
    lines = [s.strip() for s in t.replace(". ", ".\n").split("\n") if s.strip()]
    bad_ends = ("and", "or", "at", "with", "the", "to", "of")
    out = []
    for line in lines[:2]:
        line = line.rstrip(".,") + "." if line and line[-1] not in ".!?" else line
        if len(line) > 140:
            line = line[:137].rsplit(" ", 1)[0] + "."
            while line and len(line) > 5 and line.rstrip(".").rsplit(" ", 1)[-1].lower().rstrip(".") in bad_ends:
                line = line.rstrip(".").rsplit(" ", 1)[0].rstrip(".,") + "."
        out.append(line)
    result = " ".join(out) if out else "—"
    return (result[0].upper() + result[1:]) if result and result != "—" else result


def _join_list(items: list[str]) -> str:
    """Join with commas for 3+: 'a, b, and c'. For 2: 'a and b'."""
    items = [x for x in items if x]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + ", and " + items[-1]


def _condense_reason(text: str, max_len: int = 95) -> str:
    """One-line list summary: 'Delays at [hubs] due to [risks].' Lowercase risks. Commas for 3+."""
    t = _normalize_reason(text or "")
    hubs = list(dict.fromkeys(re.findall(r"([A-Za-z]+(?:[A-Za-z]*)-[A-Za-z]+(?:-[A-Za-z]+)?)", t)))
    hub_str = _join_list(hubs[:3]) if hubs else None
    lower = t.lower()
    risks = []
    if "congestion" in lower:
        risks.append("congestion")
    if "traffic" in lower:
        risks.append("traffic")
    if "labor" in lower:
        risks.append("labor")
    if "weather" in lower or "bad weather" in lower:
        risks.append("bad weather")
    if "delay" in lower and not risks:
        risks.append("delays")
    if not risks:
        return "Requires attention."
    risk_str = _join_list(risks[:3])
    if hub_str:
        out = f"Delays at {hub_str} due to {risk_str}"
    else:
        out = f"Delays at previous stops due to {risk_str}"
    out = out.rstrip(".,") + "."
    if len(out) > max_len:
        out = out[: max_len - 1].rsplit(" ", 1)[0] + "."
    bad_ends = ("and", "or", "at", "with", "the", "to", "of")
    while out and len(out) > 5 and out.rstrip(".").rsplit(" ", 1)[-1].lower().rstrip(".") in bad_ends:
        out = out.rstrip(".").rsplit(" ", 1)[0].rstrip(".,") + "."
    return (out[0].upper() + out[1:]).rstrip(".,") + "." if out and len(out) > 1 else "Requires attention."


app_ui = ui.page_fluid(
    ui.h4("SupplyMind — Shipment Analysis", class_="mb-2"),
    ui.p("AI-powered analysis. Runs on load.", class_="text-muted small mb-3"),
    ui.output_ui("status"),
    ui.output_ui("results"),
    ui.div(ui.input_text("escalate_which", label="", value=""), class_="d-none"),
    ui.div(ui.input_text("insight_detail_id", label="", value=""), class_="d-none"),
    ui.div(
        ui.div(
            ui.div(
                ui.h5("Escalated Shipments", class_="offcanvas-title mb-0"),
                ui.tags.button(
                    type="button",
                    class_="btn-close",
                    data_bs_dismiss="offcanvas",
                    aria_label="Close",
                ),
                class_="offcanvas-header border-bottom",
            ),
            ui.div(
                ui.output_ui("escalated_list"),
                class_="offcanvas-body p-0",
            ),
            id="escalatedDrawer",
            class_="offcanvas offcanvas-end",
            tabindex="-1",
        ),
    ),
)


def _kpi_cards(on_time: int, delayed: int, critical: int):
    total = on_time + delayed + critical
    pct_on = int(100 * on_time / total) if total else 0
    pct_delayed = int(100 * delayed / total) if total else 0
    pct_critical = int(100 * critical / total) if total else 0

    cards = [
        ui.div(
            ui.div(
                ui.div(
                    ui.span(str(total), class_="fs-2 fw-bold"),
                    ui.div("Total In Transit", class_="text-muted small"),
                    class_="text-center",
                ),
                class_="card-body",
            ),
            class_="card border",
            style="min-width: 100px;",
        ),
        ui.div(
            ui.div(
                ui.div(
                    ui.span(str(on_time), class_="fs-2 fw-bold text-success"),
                    ui.div(f"On Time ({pct_on}%)", class_="text-muted small"),
                    class_="text-center",
                ),
                class_="card-body",
            ),
            class_="card border border-success",
            style="min-width: 100px;",
        ),
        ui.div(
            ui.div(
                ui.div(
                    ui.span(str(delayed), class_="fs-2 fw-bold text-warning"),
                    ui.div(f"Delayed ({pct_delayed}%)", class_="text-muted small"),
                    class_="text-center",
                ),
                class_="card-body",
            ),
            class_="card border border-warning",
            style="min-width: 100px;",
        ),
        ui.div(
            ui.div(
                ui.div(
                    ui.span(str(critical), class_="fs-2 fw-bold text-danger"),
                    ui.div(f"Critical ({pct_critical}%)", class_="text-muted small"),
                    class_="text-center",
                ),
                class_="card-body",
            ),
            class_="card border border-danger",
            style="min-width: 100px;",
        ),
    ]
    return ui.div(*cards, class_="d-flex flex-wrap gap-2")


def _status_donut_with_confidence(on_time: int, delayed: int, critical: int, insights: list[dict]):
    """Status breakdown donut (On Time/Delayed/Critical) with AI confidence % in center."""
    total = on_time + delayed + critical
    if total == 0:
        fig = go.Figure().add_annotation(
            text="No data", x=0.5, y=0.5, showarrow=False, font_size=14
        )
    else:
        conf_pct = 50
        if insights:
            avg_conf = sum(r.get("confidence", 5) for r in insights) / len(insights)
            conf_pct = int(round(avg_conf / 10 * 100))
        fig = go.Figure(
            data=[
                go.Pie(
                    labels=["On Time", "Delayed", "Critical"],
                    values=[on_time, delayed, critical],
                    hole=0.72,
                    marker_colors=["#28a745", "#ffc107", "#dc3545"],
                    textinfo="label+percent",
                    textposition="outside",
                    hovertemplate="%{label}<br>%{value} shipments<extra></extra>",
                    sort=False,
                )
            ],
            layout=go.Layout(
                showlegend=False,
                margin=dict(t=30, b=30, l=30, r=30),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=240,
                annotations=[
                    dict(
                        text=f"<b>{conf_pct}%</b><br>AI confidence",
                        x=0.5,
                        y=0.5,
                        font_size=14,
                        showarrow=False,
                    )
                ],
            ),
        )
    return fig


def _cached_result_from_db():
    """Load counts from existing insights (instant, no OpenAI)."""
    try:
        insights = get_all_insights()
    except Exception:
        return {"on_time": 0, "delayed": 0, "critical": 0}
    on_time = sum(1 for r in insights if (r.get("flag_status") or "").lower() == "on time")
    delayed = sum(1 for r in insights if (r.get("flag_status") or "").lower() == "delayed")
    critical = sum(1 for r in insights if (r.get("flag_status") or "").lower() == "critical")
    return {"on_time": on_time, "delayed": delayed, "critical": critical, "insights_written": insights}


def server(input: Inputs, output: Outputs, session: Session):
    should_run = reactive.value(False)  # Don't run analysis on load
    analysis_result = reactive.value(None)
    is_loading = reactive.value(False)
    escalated_ids = reactive.value(set())

    @reactive.effect
    def load_cached_on_start():
        """Show cached insights immediately for fast load."""
        if analysis_result() is None:
            analysis_result.set(_cached_result_from_db())

    @reactive.effect
    @reactive.event(input.rerun)
    def on_rerun():
        should_run.set(True)

    @reactive.effect
    @reactive.event(input.insight_detail_id)
    def show_insight_modal():
        sid = input.insight_detail_id()
        if not sid:
            return
        try:
            insights = get_all_insights()
        except Exception:
            insights = []
        r = next((x for x in insights if x.get("shipment_id") == sid), None)
        if not r:
            return
        flag = (r.get("flag_status") or "—")
        reasoning = _modal_reason(r.get("reasoning") or "").replace("<", "&lt;")
        pred = r.get("predicted_arrival")
        pred_str = _fmt_ts_friendly(pred)
        deadline = r.get("final_deadline")
        deadline_str = _fmt_ts_friendly(deadline)
        m = ui.modal(
            ui.div(
                ui.p(ui.strong("Category: "), ui.span(flag, class_="text-danger" if (flag or "").lower() == "critical" else "text-warning")),
                ui.hr(class_="my-2"),
                ui.p(ui.strong("AI prediction: "), class_="mb-1"),
                ui.p(reasoning, class_="mb-3", style="line-height: 1.5; white-space: pre-wrap;"),
                ui.div(
                    ui.p(ui.strong("AI predicted arrival: "), pred_str, class_="mb-1"),
                    ui.p(ui.strong("Target deadline: "), deadline_str, class_="mb-0"),
                    class_="small text-muted",
                ),
                class_="text-start",
            ),
            title=f"{sid} DETAILS",
            easy_close=True,
            footer=ui.div(
                ui.input_action_button("close_insight_modal", "Close", class_="btn btn-secondary"),
                class_="d-flex justify-content-end",
            ),
            size="m",
        )
        ui.modal_show(m)

    @reactive.effect
    @reactive.event(input.close_insight_modal)
    def on_close_insight_modal():
        ui.modal_remove()

    @reactive.effect
    @reactive.event(input.escalate_which)
    def on_escalate_add():
        sid = input.escalate_which()
        if sid:
            escalated_ids.set(escalated_ids() | {sid})

    @reactive.effect
    @reactive.event(input.escalate_clear)
    def on_escalate_clear():
        escalated_ids.set(set())

    @reactive.effect
    def run_when_triggered():
        if not should_run():
            return
        is_loading.set(True)
        try:
            result = run_analysis()
            analysis_result.set(result)
        except Exception as e:
            analysis_result.set({"on_time": 0, "delayed": 0, "critical": 0, "error": str(e)})
        finally:
            is_loading.set(False)
            should_run.set(False)

    @render.ui
    def status():
        if is_loading():
            return ui.div(
                ui.span("Running analysis...", class_="text-muted"),
                class_="alert alert-info",
            )
        return None

    @render.ui
    def escalated_list():
        escalated = escalated_ids()
        try:
            all_insights = get_all_insights()
        except Exception:
            all_insights = []
        insights_by_id = {r.get("shipment_id"): r for r in all_insights if r.get("shipment_id")}
        if not escalated:
            return ui.div(
                ui.span("Click Escalate next to a shipment to add it here.", class_="text-muted small"),
                class_="p-4 text-center",
            )
        items = []
        for sid in sorted(escalated):
            r = insights_by_id.get(sid)
            reason = _condense_reason(r.get("reasoning") if r else "Flagged", 80).replace("<", "&lt;")
            sid_safe = sid.replace("<", "&lt;")
            items.append(
                ui.div(
                    ui.span(sid_safe, class_="fw-semibold"),
                    ui.p(reason, class_="mb-0 mt-1 small text-muted", style="font-size: 0.8rem;"),
                    class_="py-2 px-3 border-bottom",
                )
            )
        return ui.div(
            ui.input_action_button("escalate_clear", "Clear all", class_="btn btn-sm btn-link text-muted m-2 p-0"),
            *items,
        )

    @render_widget
    def donut():
        result = analysis_result()
        if result is None or result.get("error"):
            return _status_donut_with_confidence(0, 0, 0, [])
        return _status_donut_with_confidence(
            result.get("on_time", 0),
            result.get("delayed", 0),
            result.get("critical", 0),
            result.get("insights_written", []),
        )

    @render.ui
    def results():
        result = analysis_result()
        if result is None:
            return ui.div("No results yet.", class_="text-muted mt-3")
        err = result.get("error")
        if err:
            return ui.div(
                ui.p("Error:", class_="fw-bold"),
                ui.p(err, class_="text-danger"),
                class_="alert alert-danger mt-3",
            )

        on_time = result.get("on_time", 0)
        delayed = result.get("delayed", 0)
        critical = result.get("critical", 0)

        all_insights = []
        try:
            all_insights = get_all_insights()
        except Exception:
            pass

        insights_by_id = {r.get("shipment_id"): r for r in all_insights if r.get("shipment_id")}
        critical_list = [
            r for r in all_insights
            if (r.get("flag_status") or "").lower() == "critical"
        ][:10]
        critical_ids = [r["shipment_id"] for r in critical_list]


        # Critical items: compact list style, consistent borders
        critical_cards = []
        for i, r in enumerate(critical_list):
            sid_raw = r.get("shipment_id") or ""
            sid_safe = sid_raw.replace("<", "&lt;")
            reason = _condense_reason(r.get("reasoning") or "-").replace("<", "&lt;")
            esc_btn = ui.tags.button(
                "Escalate",
                type="button",
                class_="btn btn-outline-danger btn-sm py-0",
                onclick=f"Shiny.setInputValue('escalate_which', '{sid_raw.replace(chr(39), chr(92)+chr(39))}');" if sid_raw else "",
            )
            js_val = sid_raw.replace("'", "\\'")
            info_trigger = ui.tags.button(
                ui.span(sid_safe, class_="fw-bold text-danger"),
                " ",
                ui.span("✨", class_="small", style="opacity: 0.9;"),
                type="button",
                class_="btn btn-link p-0 text-danger text-decoration-none fw-bold text-start",
                style="cursor: pointer; text-underline-offset: 2px;",
                onclick=f"Shiny.setInputValue('insight_detail_id', '{js_val}', {{priority: 'event'}});",
                title="See full insight",
            )
            is_last = i == len(critical_list) - 1
            critical_cards.append(
                ui.div(
                    ui.div(
                        info_trigger,
                        esc_btn,
                        class_="d-flex align-items-center justify-content-between gap-2 mb-0",
                    ),
                    ui.p(reason, class_="mb-0 mt-1 small text-muted", style="font-size: 0.75rem; line-height: 1.3;"),
                    class_="py-2 px-3 border-bottom" if not is_last else "py-2 px-3",
                    style="max-width: 100%;",
                )
            )

        n_esc = len(escalated_ids())
        view_esc_label = f"View Escalated ({n_esc})" if n_esc else "View Escalated"

        return ui.div(
            ui.div(
                ui.div(
                    ui.div(
                        ui.h5("Delivery Health", class_="mb-0"),
                        ui.input_action_button("rerun", "Re-run Analysis", class_="btn btn-outline-secondary btn-sm"),
                        class_="d-flex align-items-center justify-content-between mb-2",
                    ),
                    _kpi_cards(on_time, delayed, critical),
                    ui.p("AI confidence", class_="text-muted small mt-2 mb-1", style="font-size: 0.75rem;"),
                    output_widget("donut"),
                    class_="p-3",
                    style="flex: 1; min-width: 0;",
                ),
                ui.div(
                    ui.div(
                        ui.h5("Needs Attention", class_="mb-0"),
                        ui.tags.button(
                            view_esc_label,
                            type="button",
                            class_="btn btn-outline-secondary btn-sm",
                            data_bs_toggle="offcanvas",
                            data_bs_target="#escalatedDrawer",
                        ),
                        class_="d-flex align-items-center justify-content-between mb-2",
                    ),
                    ui.div(
                        *critical_cards if critical_cards else [
                            ui.div(ui.span("No critical shipments.", class_="text-muted small"), class_="py-3")
                        ],
                        class_="overflow-auto border rounded",
                        style="flex: 1; min-height: 120px; max-height: 200px;",
                    ),
                    class_="p-3 d-flex flex-column",
                    style="flex: 1; min-width: 0; border-left: 1px solid var(--bs-border-color);",
                ),
                class_="d-flex gap-0",
                style="width: 100%;",
            ),
            class_="card border rounded",
        )


app = App(app_ui, server)

if __name__ == "__main__":
    from shiny import run_app
    run_app(app, host="127.0.0.1", port=8000, launch_browser=True)
