"""
SupplyMind Shiny app.
Runs shipment analysis on load and via Re-run button.
Includes supply chain optimization insights.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

# Ensure project root (for db) and SupplyMindAI (for analysis) are on path
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "SupplyMindAI"))

from shiny import App, Inputs, Outputs, Session, reactive, render, ui
from htmltools import HTML

from analysis.pipeline import run_analysis, get_all_insights
from analysis.optimization_pipeline import (
    run_optimization_insights,
    run_optimization_insights_with_data,
    parse_recommendation_to_sim_param,
)
from analysis.simulation import find_sweet_spot
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

app_ui = ui.page_fluid(
    ui.panel_title("SupplyMind — Shipment Analysis"),
    ui.p(
        "Analyzes in-transit shipments and flags them as On Time, Delayed, or Critical. "
        + ("Runs automatically on load; " if _RUN_ANALYSIS_ON_LOAD else "")
        + "Click below to run or re-run."
    ),
    ui.input_action_button("rerun", "Re-run Analysis", class_="btn-primary"),
    ui.output_ui("status"),
    ui.output_ui("results"),
    ui.hr(),
    # Optimization card
    ui.div(
        ui.h4("Supply Chain Optimization"),
        ui.p(
            "Get AI-powered recommendations to improve your supply chain based on delivered shipment data."
        ),
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
        ui.input_action_button("opt_get_insights", "Get Supply Chain Insights", class_="btn-primary mt-2"),
        ui.output_ui("opt_status"),
        ui.output_ui("opt_results"),
        class_="card p-4 mt-3",
    ),
    # Simulation card
    ui.div(
        ui.h4("Parameter Simulation"),
        ui.p("Drag a parameter from the list below and drop it into the selected slot. Only one parameter at a time."),
        ui.h6("Parameters to simulate", class_="mt-3"),
        ui.div(ui.output_ui("sim_param_chips"), id="sim-params-source", class_="sim-draggable-source mb-2"),
        ui.h6("Selected parameter", class_="mt-3"),
        ui.div(
            ui.output_ui("sim_selected_display"),
            id="sim-drop-zone",
            class_="sim-drop-zone border border-2 border-dashed rounded p-3 mb-2",
        ),
        ui.div(ui.input_text("sim_selected_param", "", value=""), class_="d-none"),
        ui.tags.script(
            """
            (function() {
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
                var dz = document.getElementById('sim-drop-zone');
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
                    if (param && typeof Shiny !== 'undefined' && Shiny.setInputValue) {
                      Shiny.setInputValue('sim_selected_param', param, {priority: 'event'});
                    }
                  });
                }
                document.addEventListener('click', function(e) {
                  if (e.target && e.target.classList && e.target.classList.contains('sim-clear-link')) {
                    e.preventDefault();
                    if (typeof Shiny !== 'undefined' && Shiny.setInputValue) {
                      Shiny.setInputValue('sim_selected_param', '', {priority: 'event'});
                    }
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
            .sim-draggable-param { cursor: grab; user-select: none; }
            .sim-draggable-param:active { cursor: grabbing; }
            """
        ),
        ui.p("Sweet spot = best ROI: maximum recovered shipments per unit investment.", class_="small text-muted mt-2 mb-0"),
        ui.h6("Configure & run", class_="mt-3"),
        ui.output_ui("sim_config"),
        ui.input_action_button("sim_run", "Run simulation", class_="btn-primary mt-2"),
        ui.output_ui("sim_status"),
        ui.output_ui("sim_results"),
        ui.output_plot("sim_chart", height="250px"),
        class_="card p-4 mt-3",
    ),
)


def server(input: Inputs, output: Outputs, session: Session):
    should_run = reactive.value(_RUN_ANALYSIS_ON_LOAD)
    analysis_result = reactive.value(None)
    is_loading = reactive.value(False)

    @reactive.effect
    @reactive.event(input.rerun)
    def on_rerun():
        should_run.set(True)

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

    def _insights_to_html(rows: list[dict]) -> str:
        """Build HTML table string from insights rows."""
        if not rows:
            return "<p class='text-muted'>No rows.</p>"
        html = '<table class="table table-sm table-bordered table-striped"><thead><tr>'
        html += "<th>Shipment ID</th><th>Flag</th><th>Predicted Arrival</th><th>Reasoning</th></tr></thead><tbody>"
        for r in rows:
            sid = (r.get("shipment_id") or "").replace("<", "&lt;")
            flag = (r.get("flag_status") or "").replace("<", "&lt;")
            pa = str(r.get("predicted_arrival") or "-")[:40].replace("<", "&lt;")
            reason = str(r.get("reasoning") or "-")[:120].replace("<", "&lt;")
            html += f"<tr><td>{sid}</td><td>{flag}</td><td>{pa}</td><td>{reason}</td></tr>"
        html += "</tbody></table>"
        return html

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
        written = result.get("insights_written", [])
        all_insights = []
        try:
            all_insights = get_all_insights()
        except Exception:
            pass
        return ui.TagList(
            ui.h4("Summary", class_="mt-3"),
            ui.p(
                f"On Time: {result.get('on_time', 0)}  |  "
                f"Delayed: {result.get('delayed', 0)}  |  "
                f"Critical: {result.get('critical', 0)}",
                class_="lead",
            ),
            ui.p(
                f"This run wrote {len(written)} insight(s) to the database.",
                class_="text-muted small",
            ),
            ui.h5("Insights written this run", class_="mt-4"),
            ui.div(ui.HTML(_insights_to_html(written)), class_="table-responsive"),
            ui.h5("All insights in database", class_="mt-4"),
            ui.div(ui.HTML(_insights_to_html(all_insights)), class_="table-responsive"),
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

    @render.ui
    def opt_status():
        if opt_loading():
            return ui.div(
                ui.span("Fetching data and generating insights...", class_="text-muted"),
                class_="alert alert-info mt-3",
            )
        return None

    @render.ui
    def opt_results():
        result = opt_result()
        if result is None:
            return None
        err = result.get("error")
        if err:
            return ui.div(
                ui.p("Error:", class_="fw-bold"),
                ui.p(err, class_="text-danger"),
                class_="alert alert-danger mt-3",
            )
        summary_text = result.get("summary_text", "")
        summary = result.get("summary", "")
        control_params = result.get("control_parameters", [])
        top_params = result.get("top_parameters", [])

        if not summary and not control_params and not top_params and summary_text:
            return ui.div(
                ui.p(HTML(summary_text), class_="text-muted mt-3"),
                class_="mt-3",
            )

        parts = [ui.p(HTML(summary_text), class_="text-muted")]

        if summary or control_params:
            changes_list = control_params[:4]
            box_parts = []
            if summary:
                box_parts.append(ui.p(summary, class_="mb-2"))
            if changes_list:
                box_parts.append(ui.p("Changes:", class_="fw-bold mb-1 mt-2"))
                box_parts.append(ui.tags.ul(*[ui.tags.li(p) for p in changes_list], class_="mb-0 small"))
            parts.append(ui.div(*box_parts, class_="bg-light p-3 rounded mt-3"))

        copy_text = f"{summary}\n\nChanges:\n" + "\n".join(f"- {p}" for p in control_params[:4]) if (summary or control_params) else ""
        if copy_text:
            copy_id = "opt-copy-area"
            parts.append(ui.div(
                ui.HTML(
                    f'<button type="button" class="btn btn-secondary btn-sm mt-3" '
                    f'onclick="navigator.clipboard.writeText(document.getElementById(\'{copy_id}\').innerText);this.textContent=\'Copied!\';setTimeout(()=>this.textContent=\'Copy summary & recommendations\',1500)">'
                    "Copy summary & recommendations</button>"
                ),
                ui.pre(copy_text, id=copy_id, style="position:absolute;left:-9999px;"),
                class_="mt-2",
            ))

        return ui.div(*parts, class_="mt-3")

    # --- Simulation card ---
    sim_result = reactive.value(None)
    sim_loading = reactive.value(False)

    def _sim_selected() -> list:
        """Single selection: returns [label] or []."""
        val = input.sim_selected_param()
        if val and isinstance(val, str) and val.strip():
            return [val.strip()]
        return []

    @render.ui
    def sim_param_chips():
        r = opt_result()
        if r is None:
            return ui.span("Run Supply Chain Insights first.", class_="text-muted")
        control = r.get("control_parameters", []) or []
        top = [tp.get("label", "") for tp in (r.get("top_parameters") or []) if tp.get("label")]
        all_labels = list(dict.fromkeys(control + top))
        if not all_labels:
            return ui.span("No parameters from insights yet.", class_="text-muted")
        chips = []
        for lb in all_labels:
            parsed = parse_recommendation_to_sim_param(lb)
            label_short = lb[:50] + ("..." if len(lb) > 50 else "")
            if parsed:
                chips.append(
                    ui.tags.span(
                        label_short,
                        class_="badge bg-primary me-1 mb-1 sim-draggable-param",
                        draggable="true",
                        data_param=lb,
                    )
                )
            else:
                chips.append(
                    ui.tags.span(
                        label_short + " (cannot simulate)",
                        class_="badge bg-secondary me-1 mb-1",
                    )
                )
        return ui.div(*chips, class_="mb-0")

    @render.ui
    def sim_selected_display():
        val = input.sim_selected_param()
        if not val or not str(val).strip():
            return ui.span("Drop parameter here", class_="text-muted")
        lb = str(val).strip()
        return ui.div(
            ui.tags.span(lb[:60] + ("..." if len(lb) > 60 else ""), class_="badge bg-success"),
            ui.tags.a(" (clear)", href="#", class_="ms-1 small text-muted sim-clear-link"),
        )

    @render.ui
    def sim_config():
        sel = _sim_selected()
        if not sel:
            return ui.span("Select at least one parameter above.", class_="text-muted")
        # Build config for first selected (or we could let user pick; use first for simplicity)
        label = sel[0]
        parsed = parse_recommendation_to_sim_param(label)
        if not parsed:
            return ui.span("Selected parameter cannot be simulated.", class_="text-muted")
        ptype = parsed.get("type", "")
        target_hub = parsed.get("target_hub")
        target_route = parsed.get("target_route")

        return ui.TagList(
            ui.p(f"Simulating: {label}", class_="small text-muted"),
            ui.p(f"Type: {ptype}" + (f" | Hub: {target_hub}" if target_hub else ""), class_="small"),
        )

    @reactive.effect
    @reactive.event(input.sim_run)
    def _on_sim_run():
        r = opt_result()
        sel = _sim_selected()
        if not r or not sel:
            return
        on_time = r.get("on_time_raw", [])
        delayed = r.get("delayed_raw", [])
        if not on_time and not delayed:
            sim_result.set({"error": "No raw data from insights. Run Supply Chain Insights first."})
            return
        label = sel[0]
        parsed = parse_recommendation_to_sim_param(label)
        if not parsed:
            sim_result.set({"error": "Selected parameter cannot be simulated."})
            return
        ptype = parsed.get("type", "")
        target_hub = parsed.get("target_hub")
        target_route = parsed.get("target_route")
        ranges = {
            "hub_capacity": (1.0, 2.0),
            "dispatch_time_at_hub": (0, 1),
            "transit_mode": (0, 0.5),
            "earlier_dispatch": (0, 24),
            "risk_based_buffer": (0, 1.5),
        }
        vmin, vmax = ranges.get(ptype, (0, 1))
        sim_loading.set(True)
        try:
            res = find_sweet_spot(on_time, delayed, ptype, target_hub, target_route, vmin, vmax, 11, "roi")
            res["baseline_on_time"] = len(on_time)
            res["baseline_delayed"] = len(delayed)
            sim_result.set(res)
        except Exception as e:
            sim_result.set({"error": str(e)})
        finally:
            sim_loading.set(False)

    @render.ui
    def sim_status():
        if sim_loading():
            return ui.div(ui.span("Running simulation...", class_="text-muted"), class_="alert alert-info mt-2")
        return None

    @render.plot
    def sim_chart():
        res = sim_result()
        if not res or res.get("error") or not res.get("curve"):
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(5, 2.5))
            ax.text(0.5, 0.5, "Run simulation to see chart", ha="center", va="center", transform=ax.transAxes)
            ax.axis("off")
            return fig
        curve = res.get("curve", [])
        sweet = res.get("sweet_spot_value")
        vals = [c[0] for c in curve]
        on_times = [c[1] for c in curve]
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(5, 2.5))
        ax.plot(vals, on_times, "b-o", markersize=4)
        if sweet is not None:
            idx = min(range(len(vals)), key=lambda i: abs(vals[i] - sweet))
            ax.scatter([vals[idx]], [on_times[idx]], color="gold", s=80, zorder=5, label="Sweet spot")
        ax.set_xlabel("Value")
        ax.set_ylabel("On-time count")
        ax.legend(loc="lower right")
        fig.tight_layout()
        return fig

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
        sweet = res.get("sweet_spot_value")
        curve = res.get("curve", [])
        best = res.get("best_metrics", {})
        rows = []
        for v, on_t, dly, avg in curve:
            mark = " ★" if v == sweet else ""
            rows.append((v, on_t, dly, avg, mark))
        table_html = (
            "<table class='table table-sm table-bordered'><thead><tr>"
            "<th>Value</th><th>On-time</th><th>Delayed</th><th>Avg delay (hrs)</th><th></th></tr></thead><tbody>"
        )
        for v, on_t, dly, avg, mark in rows:
            table_html += f"<tr><td>{v}</td><td>{on_t}</td><td>{dly}</td><td>{avg}</td><td>{mark}</td></tr>"
        table_html += "</tbody></table>"
        base_ot = res.get("baseline_on_time")
        base_dly = res.get("baseline_delayed")
        sim_ot = best.get("on_time_count", "-")
        sim_dly = best.get("delayed_count", "-")
        recovered = (base_dly - sim_dly) if isinstance(base_dly, int) and isinstance(sim_dly, int) and sim_dly < base_dly else None
        baseline_str = f"Baseline: {base_ot} on-time, {base_dly} delayed" if base_ot is not None and base_dly is not None else ""
        sim_str = f"At sweet spot {sweet}: {sim_ot} on-time, {sim_dly} delayed"
        recovered_str = f" ({recovered} recovered)" if recovered is not None and recovered > 0 else ""
        return ui.TagList(
            ui.h6("Results", class_="mt-3"),
            ui.p(
                ui.strong(f"{baseline_str} → " if baseline_str else ""),
                f"{sim_str}{recovered_str} | Avg delay: {best.get('avg_delay', '-')} hrs",
                class_="small",
            ),
            ui.div(ui.HTML(table_html), class_="table-responsive mt-2"),
        )


app = App(app_ui, server)

if __name__ == "__main__":
    from shiny import run_app
    run_app(app, host="127.0.0.1", port=8000, launch_browser=True)
