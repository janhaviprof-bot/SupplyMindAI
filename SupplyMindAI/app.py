"""
SupplyMind Shiny app.
Runs shipment analysis on load and via Re-run button.
"""
import sys
from pathlib import Path

# Ensure project root (for db) and SupplyMindAI (for analysis) are on path
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "SupplyMindAI"))

from shiny import App, Inputs, Outputs, Session, reactive, render, ui

from analysis.pipeline import run_analysis


app_ui = ui.page_fluid(
    ui.panel_title("SupplyMind — Shipment Analysis"),
    ui.p(
        "Analyzes in-transit shipments and flags them as On Time, Delayed, or Critical. "
        "Runs automatically on load; click below to re-run."
    ),
    ui.input_action_button("rerun", "Re-run Analysis", class_="btn-primary"),
    ui.output_ui("status"),
    ui.output_ui("results"),
)


def server(input: Inputs, output: Outputs, session: Session):
    should_run = reactive.value(True)
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
        return ui.div(
            ui.h4("Results", class_="mt-3"),
            ui.p(
                f"On Time: {result.get('on_time', 0)}  |  "
                f"Delayed: {result.get('delayed', 0)}  |  "
                f"Critical: {result.get('critical', 0)}",
                class_="lead",
            ),
            ui.p(
                "Flags and insights have been written to the database.",
                class_="text-muted small",
            ),
            class_="mt-3",
        )


app = App(app_ui, server)

if __name__ == "__main__":
    from shiny import run_app
    run_app(app, host="127.0.0.1", port=8000, launch_browser=True)
