# User Guide — Using the Dashboard (Card by Card)

This guide takes you through the SupplyMind AI dashboard card by card. For each card, you'll learn what you see, what it means, how to use it, and—for those who want the details—what data it uses and how it works.

---

## Header and Status Banner

**Header — What you see:** The Supply Mind AI logo on the left, and on the right: the title "Supply Mind AI" plus a short tagline.

**What it means:** The tagline explains the app in one sentence: it helps you track in-transit deliveries, predict delays, and optimize your supply chain in one place.

**How to use it:** Nothing to do here—it's just the top of the page. Use it to confirm you're in the right app.

**Status Banner — What you see:** A blue bar that says "Running analysis..." sometimes appears below the header.

**What it means:** The AI is working. It's reading shipment data from the database, talking to the AI, and writing predictions. This can take a few seconds to a minute depending on how many shipments are in transit.

**How to use it:** Wait for it to disappear. When it does, the analysis is done and the results are updated.

---

## Card 1: Delivery Health

### What you see

A section titled "Delivery Health" with a **Re-run Analysis** button, several small cards showing numbers (Total In Transit, On Time, Delayed, Critical), and a donut chart in the center.

### What it means

- **Total In Transit:** How many shipments are currently on the road (not yet delivered).
- **On Time:** Shipments expected to arrive by their deadline (green).
- **Delayed:** Shipments likely to arrive late (amber/orange).
- **Critical:** High-priority shipments that are likely late (red). These need your attention.
- **Donut chart:** The same breakdown in a pie view. The center shows **AI confidence**—how sure the AI is about its predictions (0–100%). Higher is better.

### How to use it

1. Click **Re-run Analysis** when you want fresh predictions (e.g., after new data is added).
2. Glance at the KPIs and donut to see the big picture.

### Deep dive: What it does

The Delivery Health card shows AI predictions for all in-transit shipments. It summarizes them as KPI counts (Total, On Time, Delayed, Critical) and a donut chart, and writes results into the `insights` table.

### Deep dive: Data used for analysis

The analysis pipeline reads from four tables. Only shipments with `status = 'In Transit'` are used.

**Dataset structure (headers):**

| Table | Column Headers |
|-------|----------------|
| `shipments` | shipment_id \| material_type \| priority_level \| total_stops \| current_stop_index \| final_deadline \| status |
| `stops` | shipment_id \| stop_number \| hub_name \| planned_arrival \| actual_arrival \| planned_departure \| actual_departure |
| `hubs` | hub_name \| lat \| lon \| current_load \| max_capacity \| status |
| `risks` | hub_name \| category \| severity \| est_delay_hrs |

- **shipments:** Only rows with `status = 'In Transit'`. Provides shipment metadata and the deadline.
- **stops:** For each shipment, all stops (past and future). Used to compare actual vs planned times and to find which hubs the shipment will visit next.
- **hubs:** Only for *future* stops (stop_number > current_stop_index). Provides `current_load`, `max_capacity`, and `status` (Open, Congested, Closed).
- **risks:** For those same future hub names. Provides `category` (Weather, Traffic, Labor), `severity` (1–10), and `est_delay_hrs` (estimated delay in hours).

### Deep dive: Parameters the AI uses to predict the flag

The AI decides On Time / Delayed / Critical based on:

1. **Past stop performance:** For completed stops, is `actual_arrival` after `planned_arrival`? If yes, that suggests delay.
2. **Future hub status:** Are any future hubs Congested or Closed? If yes, more likely delayed.
3. **Future risks:** Any `severity >= 7` or high `est_delay_hrs`? If yes, more likely delayed.
4. **priority_level:** Only shipments with `priority_level >= 8` can be Critical. If `priority_level < 8`, the AI must use Delayed, never Critical.

### Deep dive: Flags and their meanings

| Flag | Meaning | Criteria |
|------|---------|----------|
| **On Time** | Expected to meet the deadline | All past stops on time, future hubs Open, no high-severity risks (severity ≤ 4). |
| **Delayed** | Likely to arrive late | Past stops late, OR future hubs Congested/Closed, OR high-severity risks (severity ≥ 7). |
| **Critical** | High-priority and delayed | Same as Delayed, **and** `priority_level >= 8`. |

### Deep dive: AI confidence

The AI returns a confidence score from 1 to 10. If it is missing or invalid, a **heuristic** is used:

- **High (8):** Data clearly supports the flag—e.g., all past stops on time and no risks for On Time, or clear late signals for Delayed/Critical.
- **Low (4):** Data is mixed or conflicting—e.g., On Time flag but past stops were late, or Delayed flag but all hubs Open and low risk.

The donut chart center shows the average confidence scaled to 0–100%.

### Deep dive: Output

Results are written to the `insights` table:

| Table | Column Headers |
|-------|----------------|
| `insights` | insight_id \| shipment_id \| flag_status \| predicted_arrival \| reasoning \| confidence |

The dashboard reads from `insights` to show the KPIs and donut chart.

### Card 1.2: Needs Attention (Right Panel)

**What you see:** A list of shipments that are marked **Critical**. Each row shows a shipment ID (bold, red, clickable), a short reason (e.g., "Delays at Chicago-Main due to traffic and bad weather."), and an **Escalate** button.

**What it means:** These are the shipments that most need action—high priority and likely late.

**How to use it:**
1. **Click a shipment ID** to open a pop-up with full details.
2. **Click Escalate** to add that shipment to your personal list (saved in the drawer).
3. Use **View Escalated** to open the drawer and see everything you've escalated.

**Deep dive — What it does:** Shows only shipments with `flag_status = 'Critical'` from the `insights` table.

**Deep dive — Data:** Same `insights` table as Card 1. Each row includes `shipment_id`, `reasoning`, and `flag_status`. The UI shows a condensed version of the reasoning.

**Dataset structure (headers):**

| Source | Headers |
|--------|---------|
| `insights` | insight_id \| shipment_id \| flag_status \| predicted_arrival \| reasoning \| confidence |

### Insight Detail Modal (Pop-up)

**What you see:** A pop-up window that opens when you click a shipment ID. It shows the category (On Time / Delayed / Critical), the AI's full reasoning, the predicted arrival time, and the target deadline.

**What it means:** The full story for that shipment—why the AI flagged it and when it expects it to arrive.

**How to use it:** Read the details, then click **Close** or click outside the pop-up to dismiss it.

### Escalated Shipments Drawer

**What you see:** A panel that slides in from the right. It shows a list of shipments you've clicked **Escalate** on.

**What it means:** Your personal to-do list of shipments that need follow-up.

**How to use it:**
1. Click **View Escalated** (or "View Escalated (N)") in the Needs Attention section to open it.
2. Use **Clear all** at the top to remove all items from the list.
3. Click the X or outside the drawer to close it.

---

## Card 2: Prediction Map

**What you see:** A map of the United States with dots at hub locations. Dots can be gray, green, orange, or red. When you hover, you see the hub name and the count of flagged shipments.

**What it means:**
- **Gray dots:** All hubs (base layer).
- **Green:** Hubs where shipments are on time.
- **Orange:** Hubs with delayed shipments.
- **Red:** Hubs with critical shipments (size may be larger for more critical shipments).

**How to use it:** Hover over dots to see which hubs have issues. Use it to spot problem areas geographically.

**Note:** If you see "Run analysis to see hub map," run the analysis first (Re-run Analysis in Delivery Health).

**Deep dive — What it does:** Plots hubs on a US map. Each hub gets a color based on the worst flag among shipments that visit it (Critical > Delayed > On Time). Red dot size can scale with the number of delayed/critical shipments at that hub.

**Deep dive — Data:** Hubs from `hubs` (for coordinates) and flags from `insights` (per shipment). The app joins stops to shipments, then maps each hub to its worst flag.

**Dataset structure (headers):**

| Output | Headers |
|--------|---------|
| `status_hubs` | hub_name \| lat \| lon \| status \| in_delayed_count |

- **status:** "red", "orange", or "green" (worst flag at that hub).
- **in_delayed_count:** Number of shipments with Delayed or Critical that visit that hub.

---

## Card 3: Supply Chain Optimization

### What you see

A section with a date range dropdown (Yesterday, Past week, Past month, Past year, Custom) and a **Get Supply Chain Insights** button. After you run it, you see a summary and a list of suggested changes.

### What it means

The app looks at past *delivered* shipments in the chosen date range and asks the AI what could be improved—for example, "Hub Chicago: Increase capacity" or "Reduce dwell time at Dallas."

### How to use it

1. Choose a date range.
2. If you pick **Custom**, select a start and end date (max 1 year).
3. Click **Get Supply Chain Insights**.
4. Wait for the summary and suggested changes to appear.
5. Read the suggestions—they will feed into Parameter Simulation below.

### Deep dive: What it does

Analyzes *delivered* (historical) shipments in a date range. Splits them into on-time vs delayed, computes metrics, and asks the AI for improvement recommendations. Recommendations are constrained to five levers so they can be simulated.

### Deep dive: Data used

- **Date range:** User selects Yesterday, Past week, Past month, Past year, or Custom (max 1 year).
- **shipments:** Only rows with `status = 'Delivered'` and `delivery_ts` (from last stop) in the range. Capped at 200 shipments.
- **stops, hubs, risks:** Enriched per stop with hub occupancy and risk info.

**Dataset structure (headers):**

| Table/Payload | Headers |
|---------------|---------|
| Delivered shipments | shipment_id \| material_type \| priority_level \| total_stops \| final_deadline \| delivery_ts |
| Enriched stop | stop_number \| hub_name \| planned_arrival \| actual_arrival \| planned_departure \| actual_departure \| current_load \| max_capacity \| status \| risks (array) |
| Metrics | avg_delay_hours \| top_delayed_hubs \| common_risk_categories |
| control_parameters | Array of strings (e.g., "Hub Chicago: Increase capacity") |

### Deep dive: Flow

1. Fetch delivered shipments in the date range.
2. For each shipment, fetch stops with hub and risk data.
3. Split on-time (`delivery_ts <= final_deadline`) vs delayed (`delivery_ts > final_deadline`).
4. Compute metrics: average delay, top delayed hubs, common risk categories.
5. Call OpenAI with a constrained prompt so it recommends only actions that map to the five levers.
6. Display summary, `control_parameters`, and `top_parameters`.

### Deep dive: Parameters → Levers

The AI can only suggest actions that map to these five simulation levers:

| Lever | AI Recommendation Phrasing | What You Control |
|-------|----------------------------|------------------|
| hub_capacity | "Hub X: Increase capacity" | Capacity multiplier (1.0×–2.0×) at target hub |
| dispatch_time_at_hub | "Hub X: Reduce dwell time" | Dwell reduction (0–100%) |
| transit_mode | "Use faster transit" | Transit-time reduction (0–50%) |
| earlier_dispatch | "Dispatch earlier" | Hours earlier (0–24) |
| risk_based_buffer | "Add risk-based ETA buffer" | Buffer factor ρ (0–1.5) |

The Parameter Simulation chips are parsed from these recommendations. When you select parameters and click **Run simulation**, those selections are sent to the simulation engine.

---

## Card 4: Parameter Simulation + Simulation Result

### Parameter Simulation

**What you see:** After you run Supply Chain Insights, a second column appears: **Parameters to simulate**. You see badge chips (e.g., "Hub Chicago: Increase capacity") and a dashed drop zone for "Selected parameters." A **Run simulation** button is at the bottom.

**What it means:** You can pick which suggested changes to simulate—like testing "what if we increased capacity at Chicago?" The simulation shows how many more shipments would be on time and at what cost.

**How to use it:**
1. Click a chip to add it to "Selected parameters," or drag it into the drop zone.
2. Click the chip again or the (x) to remove it.
3. Select one to five parameters.
4. Click **Run simulation**.
5. The Simulation Result card appears below.

### Simulation Result

**What you see:** A card with a chart and a recommendations panel. The chart has Investment ($) on the horizontal axis and On-time count on the vertical axis. Each selected parameter gets a colored line. Gold stars mark the "sweet spot"—the best value for each. The recommendations panel shows AI-generated advice with investment, recovered shipments, and ROI.

**What it means:**
- **Chart:** Shows how many shipments become on time as you invest more in each change.
- **Sweet spot (gold star):** The recommended point—good results without overspending.
- **Recommendations:** The AI picks the best options and explains why.

**How to use it:** Use the recommendations to decide which changes to implement. The caveat at the bottom reminds you that results are based on simulation, not live data.

### Deep dive: What it does

Runs simulations for the parameters you selected. For each lever value, it recomputes delays and reclassifies shipments as on-time if the simulated delay is zero or negative. It finds a "sweet spot" and generates AI recommendations based on the curves.

### Deep dive: Data used

The same enriched payloads from Card 3: `on_time_raw` and `delayed_raw`. Each delayed payload includes `delay_hours` (how late the shipment was).

**Dataset structure (headers):**

| Payload | Headers |
|---------|---------|
| `delayed_raw` (per item) | shipment_id \| delay_hours \| stops (with current_load, max_capacity, risks) |
| Curve output | value \| investment_usd \| on_time_count \| delayed_count \| avg_delay |
| chart_points_3 | (investment_usd, on_time_count, label) for Min, Sweet spot, Max |
| Recommendation output | recommendation_1 \| recommendation_2 \| recommendation_3 \| alternative_params_message |

### Deep dive: Algorithm (per lever)

**Hub capacity (lever 1):**  
Delay is split into congestion and risk. Congestion delay at a hub = `max(0, (current_load - capacity) / capacity) × α` (α = 3). Simulate by scaling capacity: `capacity_new = value × capacity_orig`. Recompute congestion; risk stays the same.

**Time-shift levers (2–5):**  
`D_sim = max(0, D_obs - reduction_hrs)`, where `reduction_hrs` comes from the lever value (e.g., dwell reduction × total dwell, or risk buffer × sum of `est_delay_hrs`).

**Reclassification:**  
If `D_sim ≤ 0`, the shipment is "recovered" (counted as on-time). On-time shipments stay on-time.

**Grid search:**  
11 steps from min to max value. For each step, run `simulate_delays` and get `on_time_count`, `recovered_count`, `avg_delay`.

### Deep dive: Sweet spot

- **ROI (default):** Maximizes `recovered / investment`. Favors the smallest investment that still recovers shipments.
- **on_time:** Maximizes total on-time count.
- **avg_delay:** Minimizes average delay among still-delayed shipments.

The gold star on the chart marks the sweet spot for each curve.

### Deep dive: Recommendation generation

After simulation, the AI receives the curve data (investment, on-time counts, recovered counts) and returns:

- **recommendation_1:** Primary action—best parameter, investment, expected improvement.
- **recommendation_2, recommendation_3:** Alternates or null.
- **alternative_params_message:** Suggests replacing low-impact parameters with others from the simulatable list.

Recommendations are based on investment ($), recovered count, and ROI.

---

## Quick Reference

| Action | Where |
|--------|-------|
| Refresh predictions | Re-run Analysis (Delivery Health) |
| See full details for a shipment | Click shipment ID (Needs Attention) |
| Add shipment to your list | Escalate (Needs Attention) |
| Open your escalated list | View Escalated |
| Get improvement suggestions | Supply Chain Optimization → Get Supply Chain Insights |
| Simulate changes | Parameter Simulation → select params → Run simulation |
