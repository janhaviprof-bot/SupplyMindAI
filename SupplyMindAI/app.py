"""
SupplyMind Shiny app.
Dashboard: KPI cards, donut chart, critical shipments, escalation panel.
Runs shipment analysis on load and via Re-run button.
Includes supply chain optimization insights.
"""
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Ensure project root (for db) and SupplyMindAI (for analysis) are on path
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "SupplyMindAI"))

import plotly.graph_objects as go
from shiny import App, Inputs, Outputs, Session, reactive, render, ui
from htmltools import HTML
from shinywidgets import output_widget, render_widget

from analysis.pipeline import run_analysis, get_all_insights, get_hub_map_data_from_insights
from analysis.optimization_pipeline import (
    run_optimization_insights_with_data,
    parse_recommendation_to_sim_param,
    call_openai_sim_insights,
)
from analysis.simulation import find_sweet_spot, lever_value_to_usd
# -----------------------------------------------------------------------------
# TEMPORARY: Feature 1 run-on-load toggle. Set False to skip analysis when app opens.
# Remove this block before push — restore "Runs automatically on load" behavior.
# -----------------------------------------------------------------------------
_RUN_ANALYSIS_ON_LOAD = False
# -----------------------------------------------------------------------------

# Default custom date range: past week
_today = date.today()
_default_start = _today - timedelta(days=7)
_default_end = _today

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
    ui.tags.header(
        ui.div(
            ui.div(
                ui.tags.img(
                    src="supplymind-logo.png",
                    alt="SupplyMind",
                    style="width: 100%; height: 100%; object-fit: contain; display: block;",
                ),
                class_="d-flex align-items-center justify-content-center",
                style="flex-shrink: 0; margin-right: 1rem; width: 128px; height: 128px;",
            ),
            ui.div(
                ui.span("Supply Mind AI", class_="fw-bold d-block", style="font-size: 1.25rem; letter-spacing: -0.02em; color: #212529; line-height: 1.3;"),
                ui.p(
                    "AI-powered shipment intelligence. Track in-transit deliveries, predict delays, and optimize your supply chain in one dashboard.",
                    class_="mb-0 mt-0.5",
                    style="font-size: 0.8rem; line-height: 1.35; color: #6c757d;",
                ),
                class_="flex-grow-1 d-flex flex-column justify-content-center",
                style="min-width: 0; height: 128px;",
            ),
            class_="d-flex align-items-center",
            style="padding: 0.4rem 1rem; min-height: 0; justify-content: flex-start; align-items: center;",
        ),
        class_="py-1",
        style="border-bottom: 1px solid #e9ecef; background: #fff;",
    ),
    ui.output_ui("status"),
    ui.output_ui("results"),
    ui.div(
        ui.h5("Prediction Map", class_="mb-2"),
        ui.p(
            "Hubs colored by AI prediction insights for in-transit shipments.",
            class_="text-muted small mb-2",
        ),
        output_widget("hub_map"),
        class_="card p-4 mt-3",
    ),
    ui.div(ui.input_text("escalate_which", label="", value=""), class_="d-none"),
    ui.div(ui.input_text("insight_detail_id", label="", value=""), class_="d-none"),
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
    ui.hr(),
    # Single Supply Chain Optimization card (LHS + RHS divided)
    ui.div(
        ui.h5("Supply Chain Optimization", class_="mb-0"),
        ui.p(
            "Get AI-powered recommendations to improve your supply chain based on delivered shipment data."
        ),
        ui.div(
            # LHS column (with vertical divider)
            ui.div(
                ui.output_ui("opt_status"),
                ui.output_ui("opt_results"),
                class_="col-lg-6 border-end pe-4 d-flex flex-column",
            ),
            # RHS column: Parameter Simulation (hidden until user runs Get Supply Chain Insights)
            ui.div(
                ui.div(ui.input_text("opt_insights_ready", "", value="no"), class_="d-none"),
                ui.div(
                    ui.panel_conditional(
                        "input.opt_insights_ready === 'yes'",
                        ui.div(
                        ui.h5("Parameter Simulation", class_="h6 mb-2"),
                        ui.h6("Parameters to simulate", class_="mt-2 mb-1"),
                        ui.div(ui.output_ui("sim_param_chips"), id="sim-params-source", class_="sim-draggable-source mb-2"),
                        ui.h6("Selected parameters", class_="mt-2 mb-1"),
                        ui.div(
                            ui.span("Click a parameter above to select", class_="text-muted"),
                            id="sim-selected-zone",
                            class_="sim-drop-zone border border-2 border-dashed rounded p-3 mb-2",
                        ),
                        ui.div(ui.input_text("sim_selected_param", "", value=""), class_="d-none"),
                        ui.input_action_button("sim_run", "Run simulation", class_="btn-primary mt-2"),
                        class_="card border rounded mt-3 p-3 h-100",
                    ),
                ),
                class_="flex-grow-1 d-flex flex-column",
                ),
                class_="col-lg-6 ps-4 d-flex flex-column",
            ),
            class_="row",
        ),
        ui.tags.script(
            """
            (function() {
              var selected = [];
              var MAX = 5;
              function updateZone() {
                var z = document.getElementById('sim-selected-zone');
                if (!z) return;
                if (selected.length === 0) {
                  z.innerHTML = '<span class="text-muted">Click a parameter above to select</span>';
                } else {
                  var html = selected.map(function(p) {
                    var lab = p.length > 45 ? p.substring(0,45)+'...' : p;
                    return '<span class="badge bg-success me-1 mb-1">'+lab+'</span> <a href="#" class="sim-clear-one small text-muted" data-p="'+p.replace(/"/g,'&quot;')+'">(x)</a> ';
                  }).join('') + '<a href="#" class="sim-clear-link small ms-1">Clear all</a>';
                  z.innerHTML = html;
                }
                if (typeof Shiny !== 'undefined' && Shiny.setInputValue) {
                  Shiny.setInputValue('sim_selected_param', selected.join('|||'), {priority: 'event'});
                }
              }
              document.addEventListener('DOMContentLoaded', function() {
                document.addEventListener('dragstart', function(e) {
                  var t = e.target;
                  if (t && t.classList && t.classList.contains('sim-draggable-param') && t.dataset && t.dataset.param) {
                    e.dataTransfer.setData('text/plain', t.dataset.param);
                    e.dataTransfer.effectAllowed = 'copy';
                    t.style.opacity = '0.5';
                  }
                });
                document.addEventListener('dragend', function(e) {
                  if (e.target && e.target.classList && e.target.classList.contains('sim-draggable-param')) {
                    e.target.style.opacity = '1';
                  }
                });
                var dz = document.getElementById('sim-selected-zone');
                if (dz) {
                  dz.addEventListener('dragover', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    e.dataTransfer.dropEffect = 'copy';
                    dz.classList.add('sim-drag-over');
                  });
                  dz.addEventListener('dragleave', function(e) {
                    dz.classList.remove('sim-drag-over');
                  });
                  dz.addEventListener('drop', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    dz.classList.remove('sim-drag-over');
                    var param = e.dataTransfer.getData('text/plain');
                    if (param && selected.indexOf(param)===-1 && selected.length < MAX) {
                      selected.push(param);
                      updateZone();
                    }
                  });
                }
                document.addEventListener('click', function(e) {
                  var t = e.target;
                  if (t && t.classList && t.classList.contains('sim-draggable-param') && t.dataset && t.dataset.param) {
                    e.preventDefault();
                    var p = t.dataset.param;
                    var i = selected.indexOf(p);
                    if (i >= 0) selected.splice(i,1);
                    else if (selected.length < MAX) selected.push(p);
                    updateZone();
                  } else if (t && t.classList && t.classList.contains('sim-clear-link')) {
                    e.preventDefault();
                    selected = [];
                    updateZone();
                  } else if (t && t.classList && t.classList.contains('sim-clear-one') && t.dataset && t.dataset.p) {
                    e.preventDefault();
                    var idx = selected.indexOf(t.dataset.p);
                    if (idx >= 0) { selected.splice(idx,1); updateZone(); }
                  }
                });
              });
            })();
            """
        ),
        ui.tags.style(
            """
            .sim-drop-zone { min-height: 48px; transition: background 0.15s; }
            .sim-drop-zone.sim-drag-over { background: rgba(13, 110, 253, 0.08); border-color: #0d6efd !important; }
            .sim-draggable-param { cursor: pointer; user-select: none; }
            .sim-draggable-param:active { cursor: grabbing; }
            .sim-chart-wrap { width: 100%; max-width: 100%; min-width: 300px; min-height: 420px; }
            .sim-results-row { display: flex; align-items: stretch; flex-wrap: nowrap; gap: 0.5rem; }
            .sim-results-row > .sim-results-chart { flex: 2 1 0%; min-width: 0; }
            .sim-results-row > .sim-results-rec { flex: 1 1 0%; min-width: 0; min-height: 420px; }
            """
        ),
        class_="card p-4 mt-3",
    ),
    ui.output_ui("sim_results_card"),
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
            avg_conf = sum((r.get("confidence") or 5) for r in insights) / len(insights)
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
    should_run = reactive.value(_RUN_ANALYSIS_ON_LOAD)
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

    # --- Optimization insights ---
    opt_should_run = reactive.value(False)
    opt_result = reactive.value(None)
    opt_loading = reactive.value(False)

    @reactive.effect
    @reactive.event(input.opt_get_insights)
    def on_opt_click():
        opt_should_run.set(True)

    @reactive.effect
    def run_optimization():
        if not opt_should_run():
            return
        opt_loading.set(True)
        opt_should_run.set(False)
        try:
            date_range = input.opt_date_range()
            start_date, end_date = None, None
            if date_range == "custom":
                dr = input.opt_custom_dates()
                if not dr or len(dr) < 2:
                    opt_result.set({
                        "error": "Please select a custom date range.",
                        "summary_text": "",
                        "summary": "",
                        "control_parameters": [],
                        "top_parameters": [],
                        "on_time_count": 0,
                        "delayed_count": 0,
                    })
                    return
                start_date, end_date = dr[0], dr[1]
                if end_date < start_date:
                    opt_result.set({
                        "error": "End date must be >= start date.",
                        "summary_text": "",
                        "summary": "",
                        "control_parameters": [],
                        "top_parameters": [],
                        "on_time_count": 0,
                        "delayed_count": 0,
                    })
                    return
                if (end_date - start_date).days > 365:
                    opt_result.set({
                        "error": "Custom range cannot exceed 1 year. Please narrow the range.",
                        "summary_text": "",
                        "summary": "",
                        "control_parameters": [],
                        "top_parameters": [],
                        "on_time_count": 0,
                        "delayed_count": 0,
                    })
                    return
            result = run_optimization_insights_with_data(date_range, start_date, end_date)
            opt_result.set(result)
        except Exception as e:
            opt_result.set({
                "error": str(e),
                "summary_text": "",
                "summary": "",
                "control_parameters": [],
                "top_parameters": [],
                "on_time_count": 0,
                "delayed_count": 0,
            })
        finally:
            opt_loading.set(False)

    @reactive.effect
    def _update_opt_insights_ready():
        r = opt_result()
        ui.update_text(
            "opt_insights_ready",
            value="yes" if r is not None else "no",
        )

    @render.ui
    def opt_status():
        if opt_loading():
            return ui.div(
                ui.span("Fetching data and generating insights...", class_="text-muted"),
                class_="alert alert-info mt-3",
            )
        return None

    @render_widget
    def hub_map():
        """Feature 1: Hub map from in-transit predictions (On Time / Delayed / Critical)."""
        try:
            map_data = get_hub_map_data_from_insights()
        except Exception:
            map_data = {"all_hubs": [], "status_hubs": []}
        all_hubs = map_data.get("all_hubs") or []
        status_hubs = map_data.get("status_hubs") or []
        if not all_hubs and not status_hubs:
            try:
                from analysis.optimization_pipeline import get_all_hub_coords
                all_hubs = get_all_hub_coords()
            except Exception:
                pass
        if not all_hubs and not status_hubs:
            fig = go.Figure().add_annotation(
                text="Run analysis to see hub map", x=0.5, y=0.5, showarrow=False, font_size=14
            )
            fig.update_layout(height=420, margin=dict(t=10, b=10, l=10, r=10))
            return fig
        fig = go.Figure()
        if all_hubs:
            fig.add_trace(
                go.Scattergeo(
                    lat=[h["lat"] for h in all_hubs],
                    lon=[h["lon"] for h in all_hubs],
                    text=[h["hub_name"] for h in all_hubs],
                    name="All hubs",
                    marker=dict(size=6, color="#212529", symbol="circle"),
                    hovertemplate="%{text}<extra></extra>",
                    mode="markers",
                )
            )
        dot_size_base = 8
        red = [h for h in status_hubs if h.get("status") == "red"]
        orange = [h for h in status_hubs if h.get("status") == "orange"]
        green = [h for h in status_hubs if h.get("status") == "green"]
        for color, data, name in [
            ("#dc3545", red, "Critical"),
            ("#ffc107", orange, "Delayed"),
            ("#28a745", green, "On-time"),
        ]:
            if not data:
                continue
            texts = [
                f"{h['hub_name']}<br>"
                + (f"{h.get('in_delayed_count', 0)} shipment(s) flagged" if h.get("in_delayed_count") else "On-time")
                for h in data
            ]
            if color == "#dc3545":
                sizes = [min(dot_size_base + 2 * (h.get("in_delayed_count") or 0), 16) for h in data]
            else:
                sizes = [dot_size_base] * len(data)
            fig.add_trace(
                go.Scattergeo(
                    lat=[h["lat"] for h in data],
                    lon=[h["lon"] for h in data],
                    text=texts,
                    name=name,
                    marker=dict(size=sizes, color=color, line=dict(width=1, color="white"), symbol="circle"),
                    hovertemplate="%{text}<extra></extra>",
                    mode="markers",
                )
            )
        fig.update_geos(
            scope="usa",
            showland=True,
            landcolor="rgb(243, 243, 243)",
            coastlinecolor="rgb(204, 204, 204)",
            projection_type="albers usa",
        )
        fig.update_layout(
            height=420,
            margin=dict(t=10, b=10, l=10, r=10),
            autosize=True,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(size=10)),
            geo=dict(center=dict(lat=39, lon=-98)),
        )
        return fig

    @render.ui
    def opt_results():
        result = opt_result()
        err = result.get("error") if result else None

        # Top of left card: date range + button (Feature 1 style)
        header_row = ui.div(
            ui.div(
                ui.input_select(
                    "opt_date_range",
                    "Date range",
                    choices={
                        "yesterday": "Yesterday",
                        "week": "Past week",
                        "month": "Past month",
                        "year": "Past year",
                        "custom": "Custom",
                    },
                    selected="year",
                ),
                ui.panel_conditional(
                    "input.opt_date_range === 'custom'",
                    ui.input_date_range(
                        "opt_custom_dates",
                        "Custom date range",
                        start=_default_start,
                        end=_default_end,
                    ),
                ),
                class_="flex-grow-1",
            ),
            ui.input_action_button("opt_get_insights", "Get Supply Chain Insights", class_="btn btn-outline-secondary btn-sm"),
            class_="d-flex align-items-center justify-content-between gap-2 mb-3",
        )

        left_content = [header_row]
        if err:
            left_content.append(ui.div(ui.p("Error:", class_="fw-bold"), ui.p(err, class_="text-danger"), class_="alert alert-danger small"))
        elif result is None:
            left_content.append(ui.p("Select date range and click to analyze.", class_="text-muted small"))
        else:
            summary_text = result.get("summary_text", "")
            summary = result.get("summary", "")
            control_params = result.get("control_parameters", [])
            left_content.append(ui.p(HTML(summary_text), class_="text-muted small"))
            if summary or control_params:
                changes_list = control_params[:4]
                box_parts = []
                if summary:
                    box_parts.append(ui.p(summary, class_="mb-2 small"))
                if changes_list:
                    box_parts.append(ui.p("Suggested changes:", class_="fw-bold mb-1 mt-2 small"))
                    # Replace "mode" with "mode of transportation" for clarity
                    def _fmt_change(p):
                        s = str(p) if p else ""
                        return re.sub(r"\b([Ff]aster|[Tt]ransit)\s+mode\b", r"\1 mode of transportation", s)
                    box_parts.append(ui.tags.ul(*[ui.tags.li(_fmt_change(p), class_="small") for p in changes_list], class_="mb-0"))
                left_content.append(ui.div(*box_parts, class_="bg-light p-3 rounded mt-2"))

        return ui.div(*left_content, class_="card border rounded mt-3 p-3 h-100 flex-grow-1")

    # --- Simulation card ---
    sim_result = reactive.value(None)
    sim_loading = reactive.value(False)
    sim_ai_insights = reactive.value(None)

    def _fallback_recommendation(res: dict):
        """Fallback when AI insights unavailable."""
        curves = res.get("curves", [])
        base_ot = res.get("baseline_on_time", 0)
        parts = []
        for c in curves:
            label = c.get("label", "")
            best = c.get("best_metrics", {})
            pts = c.get("chart_points_3", [])
            inv_sweet = pts[1][0] if len(pts) >= 2 else 0
            sim_ot = best.get("on_time_count", base_ot)
            recovered = sim_ot - base_ot
            if recovered > 0:
                parts.append(
                    ui.p(
                        ui.strong(label + ": "),
                        f"Invest ${inv_sweet:,.0f} to recover ~{recovered} shipment(s). ROI favorable.",
                        class_="mb-2 small",
                    )
                )
            else:
                parts.append(
                    ui.p(
                        ui.strong(label + ": "),
                        "Limited impact. Consider alternative levers.",
                        class_="mb-2 small text-muted",
                    )
                )
        if not parts:
            return ui.p("Review chart to compare options.", class_="text-muted small")
        return ui.div(*parts, class_="small")

    def _sim_selected() -> list:
        """Returns selected param labels (up to 5)."""
        val = input.sim_selected_param()
        if not val or not isinstance(val, str):
            return []
        parts = [p.strip() for p in val.split("|||") if p.strip()]
        return parts[:5]

    @render.ui
    def sim_param_chips():
        r = opt_result()
        if r is None:
            return ui.span("Run Supply Chain Insights first.", class_="text-muted")
        control = r.get("control_parameters", []) or []
        top = [tp.get("label", "") for tp in (r.get("top_parameters") or []) if tp.get("label")]
        all_labels = list(dict.fromkeys(control + top))
        simulatable = [lb for lb in all_labels if parse_recommendation_to_sim_param(lb)]
        if not simulatable:
            return ui.span("No simulatable parameters from insights.", class_="text-muted")
        chips = []
        for lb in simulatable[:5]:
            label_short = lb[:50] + ("..." if len(lb) > 50 else "")
            chips.append(
                ui.tags.span(
                    label_short,
                    class_="badge bg-primary me-1 mb-1 sim-draggable-param",
                    draggable="true",
                    data_param=lb,
                )
            )
        return ui.div(*chips, class_="mb-0")

    @reactive.effect
    @reactive.event(input.sim_run)
    def _on_sim_run():
        r = opt_result()
        sel = _sim_selected()
        on_time = r.get("on_time_raw", []) if r else []
        delayed = r.get("delayed_raw", []) if r else []
        if not r or (not on_time and not delayed):
            sim_result.set({"error": "No raw data. Run Supply Chain Insights first."})
            sim_ai_insights.set(None)
            return
        control = r.get("control_parameters", []) or []
        top = [tp.get("label", "") for tp in (r.get("top_parameters") or []) if tp.get("label")]
        all_labels = list(dict.fromkeys(control + top))
        simulatable = [lb for lb in all_labels if parse_recommendation_to_sim_param(lb)][:5]
        params_to_run = sel if sel else simulatable
        if not params_to_run:
            sim_result.set({"error": "No simulatable parameters."})
            sim_ai_insights.set(None)
            return
        sim_ai_insights.set(None)
        ranges = {
            "hub_capacity": (1.0, 2.0),
            "dispatch_time_at_hub": (0, 1),
            "transit_mode": (0, 0.5),
            "earlier_dispatch": (0, 24),
            "risk_based_buffer": (0, 1.5),
        }
        curves = []
        sim_loading.set(True)
        try:
            for label in params_to_run:
                parsed = parse_recommendation_to_sim_param(label)
                if not parsed:
                    continue
                ptype = parsed.get("type", "")
                target_hub = parsed.get("target_hub")
                target_route = parsed.get("target_route")
                vmin, vmax = ranges.get(ptype, (0, 1))
                res = find_sweet_spot(on_time, delayed, ptype, target_hub, target_route, vmin, vmax, 11, "roi")
                curve_data = res.get("curve", [])
                pts = res.get("chart_points_3", [])
                curves.append({
                    "label": label[:50] + ("..." if len(label) > 50 else ""),
                    "curve": curve_data,
                    "chart_points_3": pts,
                    "sweet_spot_value": res.get("sweet_spot_value"),
                    "best_metrics": res.get("best_metrics", {}),
                })
            if not curves:
                sim_result.set({"error": "Could not simulate any selected parameter."})
                return
            sim_result.set({
                "curves": curves,
                "baseline_on_time": len(on_time),
                "baseline_delayed": len(delayed),
            })
            # Generate AI insights from graph data
            try:
                graph_data = {
                    "curves": curves,
                    "baseline_on_time": len(on_time),
                    "baseline_delayed": len(delayed),
                    "simulatable_params": simulatable,
                    "simulated_params": [c["label"] for c in curves],
                }
                insights = call_openai_sim_insights(graph_data)
                sim_ai_insights.set(insights)
            except Exception as ai_err:
                sim_ai_insights.set({"error": str(ai_err)})
        except Exception as e:
            sim_result.set({"error": str(e)})
            sim_ai_insights.set(None)
        finally:
            sim_loading.set(False)

    @render.ui
    def sim_status():
        if sim_loading():
            return ui.div(ui.span("Running simulation...", class_="text-muted"), class_="alert alert-info mt-2")
        return None

    @render.ui
    def sim_results_card():
        res = sim_result()
        if res is None:
            return None
        return ui.div(
            ui.div(
                ui.h5("Simulation result", class_="card-title mb-0"),
                class_="card-header",
            ),
            ui.div(
                ui.output_ui("sim_status"),
                ui.output_ui("sim_results"),
                class_="card-body p-4",
            ),
            class_="card border mt-3",
        )

    @render.ui
    def sim_results():
        res = sim_result()
        if res is None:
            return None
        if res.get("error"):
            return ui.div(
                ui.p("Error:", class_="fw-bold"),
                ui.p(res["error"], class_="text-danger"),
                class_="alert alert-danger mt-3",
            )
        if not res.get("curves"):
            return None
        n_shipments = (res.get("baseline_on_time") or 0) + (res.get("baseline_delayed") or 0)
        caveat = f"* Analysis based on {n_shipments} shipments. Values reflect simulation results."
        return ui.div(
            ui.div(
                ui.div(
                    ui.div(output_widget("sim_chart"), class_="sim-chart-wrap"),
                    class_="sim-results-chart",
                ),
                ui.div(
                    ui.div(
                        ui.h6("Recommendations", class_="card-title"),
                        ui.output_ui("sim_recommendation"),
                        class_="card-body",
                    ),
                    class_="card border sim-results-rec",
                ),
                class_="sim-results-row",
            ),
            ui.p(HTML(caveat), class_="text-muted mb-2 mt-3", style="font-size: 0.75rem;"),
        )

    @render_widget
    def sim_chart():
        res = sim_result()
        if not res or res.get("error") or not res.get("curves"):
            fig = go.Figure().add_annotation(
                text="Run simulation to see chart", x=0.5, y=0.5, showarrow=False, font_size=14
            )
            fig.update_layout(height=420, margin=dict(t=30, b=30, l=30, r=30), xaxis=dict(visible=False), yaxis=dict(visible=False))
            return fig
        fig = go.Figure()
        colors = ["#0d6efd", "#198754", "#fd7e14", "#6f42c1", "#dc3545"]
        for i, c in enumerate(res.get("curves", [])):
            curve = c.get("curve", [])
            label = c.get("label", f"Case {i+1}")
            inv_vals = [p[1] for p in curve]
            on_times = [p[2] for p in curve]
            color = colors[i % len(colors)]
            fig.add_trace(go.Scatter(
                x=inv_vals, y=on_times, mode="lines+markers",
                marker=dict(size=6, color=color),
                line=dict(color=color),
                name=label,
            ))
            pts = c.get("chart_points_3", [])
            if len(pts) >= 2:
                inv_sweet, on_sweet, _ = pts[1]
                fig.add_trace(go.Scatter(
                    x=[inv_sweet], y=[on_sweet], mode="markers",
                    marker=dict(size=12, color="gold", symbol="star", line=dict(width=1, color="gray")),
                    showlegend=False,
                ))
        fig.update_layout(
            height=420,
            autosize=True,
            xaxis_title="Investment ($)",
            yaxis_title="On-time count",
            margin=dict(t=50, b=80, l=55, r=30),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.18,
                xanchor="center",
                x=0.5,
                bgcolor="rgba(255,255,255,0.9)",
                bordercolor="rgba(0,0,0,0.1)",
                borderwidth=1,
            ),
            paper_bgcolor="rgba(248,250,252,0.8)",
            plot_bgcolor="rgba(255,255,255,0.95)",
            font=dict(family="Inter, system-ui, sans-serif", size=12),
            hovermode="x unified",
        )
        return fig

    @render.ui
    def sim_recommendation():
        res = sim_result()
        if not res or res.get("error") or not res.get("curves"):
            return ui.span("Run simulation for recommendations.", class_="text-muted")
        insights = sim_ai_insights()
        # Show loading while AI generates
        if insights is None and sim_loading():
            return ui.p("Generating insights...", class_="text-muted small")
        if insights is None:
            return ui.p("Generating insights...", class_="text-muted small")
        # AI error fallback
        if isinstance(insights, dict) and insights.get("error"):
            return _fallback_recommendation(res)
        # Render AI-generated insights
        parts = []
        r1 = insights.get("recommendation_1", "").strip()
        if r1:
            parts.append(ui.p(ui.strong("1. "), r1, class_="mb-2 small"))
        r2 = insights.get("recommendation_2")
        if r2 and str(r2).strip():
            parts.append(ui.p(ui.strong("2. "), str(r2).strip(), class_="mb-2 small"))
        r3 = insights.get("recommendation_3")
        if r3 and str(r3).strip():
            parts.append(ui.p(ui.strong("3. "), str(r3).strip(), class_="mb-2 small"))
        alt = insights.get("alternative_params_message", "").strip()
        if alt:
            parts.append(ui.p(alt, class_="mb-0 small text-muted"))
        if not parts:
            return _fallback_recommendation(res)
        return ui.div(*parts, class_="small")


_logo_dir = Path(__file__).resolve().parent / "logo"
app = App(app_ui, server, static_assets=_logo_dir)

if __name__ == "__main__":
    from shiny import run_app
    run_app(app, host="127.0.0.1", port=8000, launch_browser=True)
