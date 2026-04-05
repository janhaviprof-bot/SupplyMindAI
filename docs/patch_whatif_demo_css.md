~~~~python
from pathlib import Path

APP = Path(__file__).resolve().parent / "SupplyMindAI" / "app.py"


def main():
    t = APP.read_text(encoding="utf-8")
    if "whatif-demo-row" in t and ".whatif-demo-btn" in t:
        print("css skip")
        return
    old = """        .whatif-baseline-row {{ margin-bottom: 10px; }}
        .whatif-baseline-row label {{ font-size: 0.75rem !important; color: #5f6368 !important; font-weight: 500 !important; }}"""
    new = """        .whatif-baseline-row {{ margin-bottom: 10px; }}
        .whatif-demo-row {{ display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 10px; }}
        .whatif-demo-label {{ font-size: 0.72rem; color: #5f6368; font-weight: 500; width: 100%; margin-bottom: 2px; }}
        @media (min-width: 480px) {{
          .whatif-demo-label {{ width: auto; margin-bottom: 0; margin-right: 4px; }}
        }}
        .whatif-demo-btn {{ font-size: 0.78rem !important; padding: 5px 14px !important; border-radius: 999px !important; border: 1px solid #dadce0 !important; background: #fff !important; color: #1a73e8 !important; line-height: 1.3 !important; }}
        .whatif-demo-btn:hover {{ background: #e8f0fe !important; border-color: #1a73e8 !important; color: #1557b0 !important; }}
        .whatif-baseline-row label {{ font-size: 0.75rem !important; color: #5f6368 !important; font-weight: 500 !important; }}"""
    if old not in t:
        raise SystemExit("css needle missing")
    APP.write_text(t.replace(old, new, 1), encoding="utf-8")
    print("css ok")


if __name__ == "__main__":
    main()
~~~~
