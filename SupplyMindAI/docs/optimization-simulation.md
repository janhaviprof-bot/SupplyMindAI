# Supply Chain Optimization and Simulation

This document describes the optimization insights workflow (Feature 2) and the parameter simulation workflow (Feature 3), including the **five canonical levers** and how they map to recommendations and simulations.

---

## 1. Overview

**Feature 2 (Optimization):** Fetches delivered shipments for a date range, splits them into on-time vs delayed, and uses AI to generate recommendations.

**Feature 3 (Simulation):** Users select recommendations and simulate different lever values to find the optimal "sweet spot."

All recommendations and simulations are expressed in terms of **five parameters only**. The AI is constrained to recommend actions that map to these parameters so that every recommendation is simulatable.

---

## 2. The Five Simulation Parameters (Levers)

These are the only levers you can control. They are the building blocks for both AI recommendations and the simulation engine.

| # | Parameter | Lever (What You Control) | Data Source | Simulation Formula |
|---|-----------|--------------------------|-------------|--------------------|
| 1 | **Hub capacity** | Scale effective capacity at a hub via k (reduces congestion) | `hubs.max_capacity`, `hubs.current_load` | k: `C_sim = k × max_capacity`; k=1.0 = no increase vs nominal; k=1.2 = +20%. Congestion delay = 0 when `current_load ≤ C_sim` |
| 2 | **Dispatch time at hub** | Reduce dwell/processing time at each hub stop | `actual_departure − actual_arrival` per stop | D_sim = max(0, D_obs − ρ × max(total_dwell, min(D_obs, 72h))) |
| 3 | **Transit mode** | Switch to faster transit (e.g., air vs truck) | Not in schema; modeled as time reduction | reduction = k_transit × D_obs, k_transit ∈ [0, 1] |
| 4 | **Earlier dispatch** | Dispatch shipments X hours earlier | Same delay data | D_sim = max(0, D_obs − shift_hrs) |
| 5 | **Risk-based ETA buffer** | Add buffer to planning when predicted risk exists | `risks.est_delay_hrs` per hub on route | Buffer = ρ × Σ est_delay_hrs; D_sim = max(0, D_obs − ρ × R) |

---

## 3. Parameter Details

### 3.1 Hub Capacity

- **What it does:** Reduces congestion by scaling effective capacity with multiplier **k** on the hub’s nominal `max_capacity`: **C_sim = k × max_capacity**.
- **Semantics:** k=1.0 means no increase vs the recorded nominal capacity; k=1.2 means 20% more effective capacity (simulation and dashboard expansion grids typically sweep k from 1.0 to 2.0).
- **Congestion** = how full a hub is relative to capacity. When load exceeds effective capacity, delays occur.
- **Stress / recovery (What-If):** The same k applies; stress scenarios use k≤1 (e.g. k=0.8 = 20% below nominal). Optional recovery sweet-spot search sweeps k on a range such as ~0.75–1.35.

### 3.2 Dispatch Time at Hub

- **What it does:** Reduces the time a shipment spends at each hub before departing.
- **Dwell** = departure − arrival for each stop.
- **Simulation:** Apply dwell reduction factor ρ on `max(total_dwell, min(D_obs, 72h))` so long delays still respond when raw dwell sums are small.

### 3.3 Transit Mode

- **What it does:** Shorter transit between hubs (e.g., switch from truck to air).
- **Simulation:** Modeled as removing a fraction of observed delay D_obs (0–100% at max lever); k=1 can bring D_sim to 0 for that lever alone.

### 3.4 Earlier Dispatch

- **What it does:** Leave the origin X hours earlier. Adds buffer before the deadline.
- **Simulation:** Fixed shift in hours. D_sim = D_obs − shift_hrs (clamped to 0).

### 3.5 Risk-Based ETA Buffer

- **Important:** We **cannot control** risks (weather, traffic, labor). Risks are external.
- **What it does:** Uses predicted risk (from `risks.est_delay_hrs`) to add buffer to planning. If we predict 4 hours of risk, we add ρ × 4 hours of buffer (dispatch earlier).
- **Simulation:** R = sum of est_delay_hrs for all risks at hubs on the route. Buffer = ρ × R. D_sim = max(0, D_obs − ρ × R).

---

## 4. AI Recommendation Constraints

The AI prompt instructs the model to recommend **only** actions that map to the five parameters:

| Parameter | Example Recommendation Phrasing |
|-----------|-------------------------------|
| Hub capacity | "Chicago hub: Increase capacity", "Hub Z: Expand capacity" |
| Dispatch time at hub | "Dallas hub: Reduce dwell time", "Hub X: Speed up processing" |
| Transit mode | "Priority shipments: Switch to faster transit", "Route X: Use faster mode" |
| Earlier dispatch | "Shipments via Chicago: Dispatch earlier", "Route X: Add buffer time" |
| Risk-based buffer | "Chicago route: Add risk-based ETA buffer", "Hub X route: Add predicted-risk buffer" |

**Excluded:** Alternate routing, material type changes, and other actions we cannot simulate with the current data model.

---

## 5. Optimization Workflow (Feature 2)

1. User selects a date range (yesterday, week, month, year, or custom).
2. Pipeline fetches delivered shipments where `delivery_ts` falls in the range.
3. For each shipment: fetch stops with hub data (current_load, max_capacity) and risks (est_delay_hrs).
4. Split into on-time vs delayed based on `delivery_ts` vs `final_deadline`.
5. Compute metrics: avg delay, top delayed hubs, common risk categories.
6. Call OpenAI with constrained prompt; receive `control_parameters` and `top_parameters` in the five-parameter language.
7. Display summary, changes (control_parameters), and top parameters (accordion).

---

## 6. Simulation Workflow (Feature 3)

1. User gets recommendations from Feature 2.
2. User selects parameters to simulate (click-to-add).
3. For each selected parameter, user configures the value range:
   - Hub capacity: k 1.0–2.0 (k=1.0 baseline, k=1.2 = +20% vs nominal)
   - Dispatch time at hub: dwell reduction 0–100%
   - Transit mode: fraction of D_obs removed 0–1.0
   - Earlier dispatch: hours 0–720
   - Risk-based buffer: buffer factor ρ 0–8
4. User clicks "Run simulation."
5. Engine duplicates the dataset and re-runs the delay model for each value in the grid.
6. Compute on-time count, delayed count, avg delay for each value.
7. Find sweet spot: value that maximizes on-time (or minimizes avg delay, or elbow).
8. Display table + chart with sweet spot highlighted.

---

## 7. Mathematical Model (Summary)

**For hub capacity:** Use congestion delay decomposition. Congestion delay at hub h = max(0, (L_h − C_h) / C_h) × α. With capacity multiplier k, use C_h_new = k × C_h (k=1.0 = nominal; k=1.2 = +20% vs that nominal).

**For time-shift levers (2–5):** D_sim = max(0, D_obs − reduction_hrs), where reduction depends on the lever (dwell reduction, transit reduction, fixed hours, or risk-based buffer).

**Reclassification:** Originally on-time stays on-time. Originally delayed: if D_sim ≤ 0, count as recovered (on-time).

---

## 8. File Structure

| File | Purpose |
|------|---------|
| `analysis/optimization_pipeline.py` | Fetches data, splits on-time/delayed, calls AI (constrained to 5 params), returns insights |
| `analysis/simulation.py` | Delay model, simulate_delays(), find_sweet_spot() for all 5 levers |
| `app.py` | UI for optimization (Feature 2) and simulation card (Feature 3) |

---

## 9. Quick Reference: Levers vs Risks

| Concept | Role |
|---------|------|
| **Risks** | External (weather, traffic, labor). We cannot control them. |
| **Mitigation levers** | Actions we take to reduce the impact of risks: capacity, dwell reduction, transit mode, earlier dispatch, risk-based buffer. |
| **Risk-based buffer** | Uses predicted risk (est_delay_hrs) to add buffer to planning. The only lever that directly uses the risk table. |
