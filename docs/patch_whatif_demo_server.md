~~~~python
from pathlib import Path

APP = Path(__file__).resolve().parent / "SupplyMindAI" / "app.py"


def main():
    t = APP.read_text(encoding="utf-8")
    if "_WHATIF_DEMO_PROMPTS" in t:
        print("server skip")
        return
    old = """    @reactive.effect
    @reactive.event(input.whatif_run)
    def _on_whatif_send():
        q = (input.whatif_question() or "").strip()
        whatif_last_question.set(q)
        dr = input.whatif_date_range() or "week"
        whatif_task.invoke(q, dr)
        ui.update_text_area("whatif_question", value="")"""
    new = """    _WHATIF_DEMO_PROMPTS = {
        "whatif_demo1": (
            "What if we cut capacity at our busiest hub by about 20%? "
            "For the selected baseline period, how would stressed on-time vs delayed deliveries look, "
            "and what should we watch?"
        ),
        "whatif_demo2": (
            "Give me an operational snapshot: how many shipments are in transit, "
            "how many are flagged critical vs delayed, and which hubs show the most future exposure?"
        ),
    }

    @reactive.effect
    @reactive.event(input.whatif_demo1)
    def _whatif_fill_demo1():
        ui.update_text_area("whatif_question", value=_WHATIF_DEMO_PROMPTS["whatif_demo1"])

    @reactive.effect
    @reactive.event(input.whatif_demo2)
    def _whatif_fill_demo2():
        ui.update_text_area("whatif_question", value=_WHATIF_DEMO_PROMPTS["whatif_demo2"])

    @reactive.effect
    @reactive.event(input.whatif_run)
    def _on_whatif_send():
        q = (input.whatif_question() or "").strip()
        whatif_last_question.set(q)
        dr = input.whatif_date_range() or "week"
        whatif_task.invoke(q, dr)
        ui.update_text_area("whatif_question", value="")"""
    if old not in t:
        raise SystemExit("server needle missing")
    APP.write_text(t.replace(old, new, 1), encoding="utf-8")
    print("server ok")


if __name__ == "__main__":
    main()
~~~~
