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
from analysis.optimization_pipeline import run_optimization_insights

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
            selected="week",
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
            result = run_optimization_insights(date_range, start_date, end_date)
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

        if top_params:
            panels = [
                ui.accordion_panel(f"param_{i}", tp.get("label", ""), tp.get("detail", ""))
                for i, tp in enumerate(top_params)
            ]
            parts.append(ui.div(
                ui.h5("Top parameters to change", class_="mt-4 mb-2"),
                ui.p("Click to expand for implementation details.", class_="text-muted small mb-2"),
                ui.accordion(*panels, id="opt_param_accordion", open=False),
                class_="mt-2",
            ))

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


app = App(app_ui, server)

if __name__ == "__main__":
    from shiny import run_app
    run_app(app, host="127.0.0.1", port=8000, launch_browser=True)
