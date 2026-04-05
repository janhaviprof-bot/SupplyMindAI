~~~~python
from pathlib import Path

APP = Path(__file__).resolve().parent / "SupplyMindAI" / "app.py"  # run from outer repo SupplyMindAI folder


def main():
    t = APP.read_text(encoding="utf-8")
    needle = '''                        class_="whatif-baseline-row",
                    ),
                    ui.div(
                        ui.div(
                            ui.div(
                                ui.input_text_area(
                                    "whatif_question",'''
    insert = '''                        class_="whatif-baseline-row",
                    ),
                    ui.div(
                        ui.span("Demo prompts:", class_="whatif-demo-label"),
                        ui.input_action_button(
                            "whatif_demo1",
                            "Capacity what-if",
                            class_="btn whatif-demo-btn",
                            title="Fill message box with a sample capacity scenario",
                        ),
                        ui.input_action_button(
                            "whatif_demo2",
                            "In-transit snapshot",
                            class_="btn whatif-demo-btn",
                            title="Fill message box with a sample operational question",
                        ),
                        class_="whatif-demo-row",
                    ),
                    ui.div(
                        ui.div(
                            ui.div(
                                ui.input_text_area(
                                    "whatif_question",'''
    if "whatif_demo1" in t:
        print("ui skip")
    else:
        if needle not in t:
            raise SystemExit("needle missing")
        t = t.replace(needle, insert, 1)
        APP.write_text(t, encoding="utf-8")
        print("ui ok")


if __name__ == "__main__":
    main()
~~~~
