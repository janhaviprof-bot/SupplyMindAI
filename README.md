# supplymind-ai

AI-Augmented Delivery System for logistics optimization.

See [SupplyMindAI/README_CONTEXT.md](SupplyMindAI/README_CONTEXT.md) for full project context, requirements, and database schema.

## Shipment Analysis App

1. Copy `.env.example` to `.env` and set:
   - `POSTGRES_CONNECTION_STRING` — from Supabase Dashboard → Project Settings → Database
   - `OPENAI_API_KEY` — your OpenAI API key

2. Install dependencies:
   ```
   pip install -r SupplyMindAI/requirements.txt
   ```

3. Run the Shiny app (opens in browser automatically):
   ```
   shiny run SupplyMindAI/app.py --launch-browser
   ```
   Or use the run script: `.\run.ps1`

The app analyzes in-transit shipments on load and via the "Re-run Analysis" button, flagging them as On Time, Delayed, or Critical, and writing results to the `insights` table.
