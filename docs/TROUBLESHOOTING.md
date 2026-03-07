# Troubleshooting — When Something Goes Wrong

Common issues and how to fix them.

---

## "Running analysis" never finishes

**What it means:** The AI analysis is stuck or taking too long.

**What to try:**
1. Check your internet connection. The app talks to OpenAI over the internet.
2. Check your OpenAI API key in `.env`. Make sure it's valid and has not expired.
3. Check [platform.openai.com](https://platform.openai.com) for billing or quota issues.
4. If you have many shipments, try setting `MAX_SHIPMENTS=8` in `.env` for a faster demo.

---

## "No critical shipments" or empty dashboard

**What it means:** The dashboard shows zeros or nothing in the lists.

**What to try:**
1. Make sure there are shipments with `status = 'In Transit'` in your database. The analysis only looks at in-transit shipments.
2. Run the analysis (click **Re-run Analysis**) if you haven't yet.
3. Check that the database connection works (see "Database connection error" below).

---

## Database connection error

**What it means:** The app cannot reach the Supabase database.

**What to try:**
1. Open `.env` and verify `POSTGRES_CONNECTION_STRING`.
2. Get the correct string from Supabase: **Dashboard** → **Project Settings** → **Database** → Copy the connection string.
3. Replace `[YOUR-PASSWORD]` with your actual database password.
4. If the direct connection fails, try the session pooler URL (see `.env.example`).

---

## OpenAI errors

**What it means:** The app cannot call the AI (e.g., "API key invalid" or "Rate limit exceeded").

**What to try:**
1. Check `OPENAI_API_KEY` in `.env`. It should start with `sk-` and have no extra spaces.
2. Verify the key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys).
3. Check billing and usage limits at [platform.openai.com](https://platform.openai.com).
4. If you hit rate limits, wait a few minutes or reduce `MAX_SHIPMENTS` in `.env`.

---

## Map doesn't load or shows "Run analysis to see hub map"

**What it means:** The Prediction Map has no data to show.

**What to try:**
1. Click **Re-run Analysis** in the Delivery Health section first.
2. The map needs insights from the analysis. If there are no in-transit shipments, the map will be empty or show only gray dots.
3. Ensure the `hubs` table has `lat` and `lon` for your hub locations.

---

## Simulation shows nothing

**What it means:** The Simulation Result card is empty or doesn't appear.

**What to try:**
1. Run **Get Supply Chain Insights** first (Supply Chain Optimization section). The Parameter Simulation and Run simulation options only appear after that.
2. Select at least one parameter from "Parameters to simulate" before clicking **Run simulation**.
3. Ensure there are delivered shipments in your chosen date range. Optimization needs historical data.

---

## Custom date range errors

**What it means:** Messages like "Please select a custom date range" or "End date must be >= start date."

**What to try:**
1. If you chose "Custom," pick both a start date and an end date.
2. End date must be on or after the start date.
3. The range cannot exceed 1 year. Pick a shorter period.

---

## App won't start or "Module not found"

**What it means:** Python cannot find a required library.

**What to try:**
1. Install dependencies: `pip install -r SupplyMindAI/requirements.txt`
2. Make sure you're using Python 3.9 or higher: `python --version`
3. Run from the project root: `shiny run SupplyMindAI/app.py --launch-browser`

---

## Still stuck?

- Check the [User Guide](USER_GUIDE.md) for how each section works.
- Check the [Glossary](GLOSSARY.md) for term definitions.
- See [context.md](context.md) and [predictions.md](predictions.md) for technical details on the database and analysis.
