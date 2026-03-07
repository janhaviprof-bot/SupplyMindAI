# SupplyMindAI — Project Documentation & App

This folder contains all app-related code and documentation for the SupplyMind AI project.

| Item | Description |
|------|-------------|
| [app.py](app.py) | Shiny app entry (run via `shiny run SupplyMindAI/app.py`) |
| [analysis/](analysis/) | Shipment analysis pipeline (flags, OpenAI, insights) |
| [requirements.txt](requirements.txt) | Python dependencies |
| [docs/context.md](../docs/context.md) | Project overview, stakeholders, technical stack, database schema |
| [docs/predictions.md](../docs/predictions.md) | Predictions, AI confidence heuristic, architecture diagram |
| [docs/optimization-simulation.md](../docs/optimization-simulation.md) | Supply chain optimization and simulation |

## Setup for collaborators

1. Install Python 3.9+ and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure `.env` (see root [README](../README.md) for required keys).
3. Run the app:
   ```bash
   shiny run SupplyMindAI/app.py --launch-browser
   ```
   Or from the repo root: `shiny run SupplyMindAI/app.py --launch-browser`

## Responsive design

The UI is responsive and adapts to smaller screens (tablets and phones). Layouts stack vertically on viewports &lt;992px, and font sizes and padding scale down on mobile.
