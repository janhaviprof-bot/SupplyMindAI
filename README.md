# SupplyMind AI

**SupplyMind AI** is a smart dashboard that watches your packages as they travel and tells you which ones might arrive late. It helps supply chain managers track shipments in real time, predict delivery delays, and find ways to improve their operations—all in one place.

**Who is it for?** Supply chain managers who want to see delivery status at a glance and take action before problems grow.

**[Try the live app](https://019cc876-2199-a739-4a67-dc4bb96d2042.share.connect.posit.cloud/)** — Deployed on Posit Connect Cloud.

---

## Documentation

**[Documentation Index](docs/DOCUMENTATION_INDEX.md)** — One place to find everything. Explains what to find where and links to all docs.

| Document | What you'll find |
|----------|------------------|
| [Getting Started](docs/GETTING_STARTED.md) | Your first 10 minutes: setup, install, and run |
| [User Guide](docs/USER_GUIDE.md) | Card-by-card tour: what you see, how to use it, data, flags, levers, algorithms |
| [Glossary](docs/GLOSSARY.md) | Terms, concepts, and plain-language explanations |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | When something goes wrong |
| [Architecture Overview](docs/ARCHITECTURE_OVERVIEW.md) | How it all fits together |

---

## Project structure

| Folder | Description |
|--------|-------------|
| `docs/` | Documentation (guides, context, predictions, optimization) |
| `SupplyMindAI/` | Shiny app (`app.py`), analysis pipeline, logo assets |
| `db/` | Supabase client and database utilities |

See [docs/context.md](docs/context.md) for full project context, requirements, and database schema.

---

## Quick start

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

The app analyzes in-transit shipments on load and via the "Re-run Analysis" button, flagging them as On Time, Delayed, or Critical. The UI works on computers, tablets, and phones.
